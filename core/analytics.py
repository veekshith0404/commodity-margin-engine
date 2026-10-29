import logging

import numpy as np
import pandas as pd


def assign_alert_event_ids(
    alert_mask: pd.Series, event_gap_days: int = 3
) -> pd.Series:
    """Assign IDs to alert dates separated by at most `event_gap_days`.

    The input Series must use a sorted, unique DatetimeIndex. Non-alert rows
    keep a nullable ID. This helper is kept separate to make event semantics
    straightforward to test independently of the statistical detector.
    """
    if not isinstance(alert_mask.index, pd.DatetimeIndex):
        raise TypeError("alert_mask must use a DatetimeIndex.")
    if not alert_mask.index.is_monotonic_increasing or alert_mask.index.has_duplicates:
        raise ValueError("alert_mask index must be sorted and unique.")
    if (
        not isinstance(event_gap_days, (int, np.integer))
        or isinstance(event_gap_days, bool)
        or event_gap_days < 1
    ):
        raise ValueError("event_gap_days must be a positive integer.")

    flags = alert_mask.fillna(False).astype(bool)
    event_ids = pd.Series(pd.NA, index=flags.index, dtype="Int64")
    event_number = 0
    previous_alert_date = None
    for alert_date in flags.index[flags]:
        if (
            previous_alert_date is None
            or (alert_date - previous_alert_date).days > event_gap_days
        ):
            event_number += 1
        event_ids.loc[alert_date] = event_number
        previous_alert_date = alert_date
    return event_ids


class CommodityAnalytics:
    """Compute descriptive price statistics and statistical price-change alerts."""

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df.copy()

    @staticmethod
    def _validate_positive_prices(prices: pd.Series, context: str) -> pd.Series:
        numeric = pd.to_numeric(prices, errors="coerce").astype("float64")
        malformed = prices.notna() & numeric.isna()
        values = numeric.to_numpy(dtype="float64", na_value=np.nan)
        finite = pd.Series(np.isfinite(values), index=prices.index)
        non_finite = numeric.notna() & ~finite
        non_positive = numeric.notna() & finite & (numeric <= 0)
        if malformed.any() or non_finite.any() or non_positive.any():
            raise ValueError(
                f"{context} contains invalid prices: "
                f"malformed={int(malformed.sum())}, "
                f"non-finite={int(non_finite.sum())}, "
                f"non-positive={int(non_positive.sum())}. "
                "Validate source prices before analysis."
            )
        return numeric

    def compute_volatility_table(self) -> pd.DataFrame:
        """Calculate overall CV from valid prices across the available period."""
        required = {"commodity", "retail_price_normalized"}
        missing = required - set(self.df.columns)
        if missing:
            raise ValueError(
                f"Cannot calculate CV; missing columns: {sorted(missing)}"
            )

        prices = self._validate_positive_prices(
            self.df["retail_price_normalized"], "CV input"
        )
        working = self.df[["commodity"]].copy()
        working["retail_price_normalized"] = prices
        stats = (
            working.groupby("commodity", observed=True)["retail_price_normalized"]
            .agg(
                mean_price="mean",
                std_price="std",
                min_price="min",
                max_price="max",
                observations="count",
            )
            .reset_index()
        )
        stats["cv_pct"] = np.where(
            stats["mean_price"] > 0,
            stats["std_price"] / stats["mean_price"] * 100.0,
            np.nan,
        )
        return stats.sort_values(
            "cv_pct", ascending=False, na_position="last"
        ).reset_index(drop=True)

    def detect_price_change_alerts(
        self,
        commodity: str,
        z_threshold: float = 2.5,
        min_pct_change: float = 10.0,
        window_weeks: int = 30,
        event_gap_days: int = 3,
    ) -> pd.DataFrame:
        """Flag unusual exact seven-calendar-day retail price changes.

        Both the current date and the exact date seven days earlier must have a
        reported price. No forward fill is used. Z-scores use log price changes
        while the second alert gate uses conventional absolute percentage
        change. The prior-only same-weekday baseline has a maximum 30-week span
        by default, with at least five valid historical values required.
        The current change is excluded from the baseline.

        Alerts are two-sided: unusual increases and decreases may be flagged.
        Alert observations are grouped when successive alert dates are no more
        than `event_gap_days` calendar days apart. These are analytical groups,
        not independently verified market events.
        """
        if not np.isfinite(z_threshold) or z_threshold < 0:
            raise ValueError("z_threshold must be a finite non-negative number.")
        if not np.isfinite(min_pct_change) or min_pct_change < 0:
            raise ValueError("min_pct_change must be a finite non-negative number.")
        if not isinstance(window_weeks, (int, np.integer)) or isinstance(window_weeks, bool) or window_weeks < 5:
            raise ValueError("window_weeks must be an integer of at least 5.")
        if not isinstance(event_gap_days, (int, np.integer)) or isinstance(event_gap_days, bool) or event_gap_days < 1:
            raise ValueError("event_gap_days must be a positive integer.")

        required = {"date", "commodity", "retail_price_normalized"}
        missing = required - set(self.df.columns)
        if missing:
            raise ValueError(
                f"Cannot detect price changes; missing columns: {sorted(missing)}"
            )

        sub = self.df.loc[self.df["commodity"] == commodity].copy()
        if sub.empty:
            logging.warning("No records found for commodity '%s'.", commodity)
            return pd.DataFrame()

        sub["date"] = pd.to_datetime(sub["date"], errors="coerce")
        sub = sub.dropna(subset=["date"])
        if sub.empty:
            logging.warning("No valid dates found for commodity '%s'.", commodity)
            return pd.DataFrame()
        if sub["date"].duplicated().any():
            duplicates = int(sub["date"].duplicated().sum())
            raise ValueError(
                f"Found {duplicates} duplicate dates for '{commodity}'. "
                "Aggregate to one observation per date before alert detection."
            )

        sub["retail_price_normalized"] = self._validate_positive_prices(
            sub["retail_price_normalized"], f"{commodity} alert input"
        )
        sub = sub.sort_values("date").set_index("date")

        # Flag a transparent, deliberately simple heuristic for isolated points:
        # the previous and next reported observations agree within 15% of their
        # mean, while the middle value differs from each by at least 40%.
        original_prices = sub["retail_price_normalized"]
        isolated_outlier_flags = pd.Series(False, index=sub.index, dtype=bool)
        if len(original_prices) >= 3:
            values = original_prices.to_numpy(dtype="float64")
            flags = np.zeros(len(values), dtype=bool)
            for position in range(1, len(values) - 1):
                previous_value = values[position - 1]
                current_value = values[position]
                next_value = values[position + 1]
                neighbour_mean = (previous_value + next_value) / 2.0
                neighbours_agree = (
                    abs(previous_value - next_value) / neighbour_mean <= 0.15
                ) if neighbour_mean > 0 else False
                differs_from_both = (
                    abs(current_value - previous_value) / previous_value > 0.40
                    and abs(current_value - next_value) / next_value > 0.40
                )
                flags[position] = neighbours_agree and differs_from_both
            isolated_outlier_flags = pd.Series(flags, index=sub.index, dtype=bool)
        sub["is_isolated_price_outlier"] = isolated_outlier_flags

        unit = (
            sub["normalized_unit"].dropna().iloc[0]
            if "normalized_unit" in sub.columns and sub["normalized_unit"].notna().any()
            else "₹/kg"
        )
        state = (
            sub["state_name"].dropna().iloc[0]
            if "state_name" in sub.columns and sub["state_name"].notna().any()
            else "Unknown"
        )

        calendar = pd.date_range(sub.index.min(), sub.index.max(), freq="D")
        sub = sub.reindex(calendar)
        sub.index.name = "date"
        sub["is_isolated_price_outlier"] = sub["is_isolated_price_outlier"].eq(True)
        sub["commodity"] = commodity
        sub["normalized_unit"] = unit
        sub["state_name"] = state

        current_price = sub["retail_price_normalized"]
        previous_week_price = current_price.shift(7)
        actual_price_reported = current_price.notna()
        exact_reference_available = previous_week_price.notna()

        price_diff = (current_price - previous_week_price).where(
            actual_price_reported & exact_reference_available
        )
        percent_change = (
            price_diff / previous_week_price * 100.0
        ).where(previous_week_price > 0)

        log_change = np.log(current_price / previous_week_price).where(
            actual_price_reported & exact_reference_available
        )
        sub["price_diff_7d"] = price_diff
        sub["price_change_pct_7d"] = percent_change
        sub["price_change_log_7d"] = log_change
        sub["reference_price_7d"] = previous_week_price.where(
            actual_price_reported & exact_reference_available
        )

        # Z-scores use log price changes to avoid the directionally asymmetric
        # scale of ordinary percentage returns. The alert gate below remains
        # an absolute percentage-change threshold (for example, at least 10%
        # up or down). Same-weekday history avoids overlapping weekly windows.
        z_scores = pd.Series(np.nan, index=sub.index, dtype="float64")
        for weekday in range(7):
            positions = np.flatnonzero(sub.index.day_of_week == weekday)
            weekday_changes = log_change.iloc[positions]
            prior_changes = weekday_changes.shift(1)
            rolling_mean = prior_changes.rolling(
                window=window_weeks, min_periods=5
            ).mean()
            rolling_std = prior_changes.rolling(
                window=window_weeks, min_periods=5
            ).std(ddof=1)
            difference = weekday_changes - rolling_mean
            valid = (
                rolling_mean.notna()
                & rolling_std.notna()
                & weekday_changes.notna()
            )
            z = np.where(
                ~valid,
                np.nan,
                np.where(
                    rolling_std > 1e-12,
                    difference / rolling_std,
                    np.where(np.abs(difference) > 1e-12, np.sign(difference) * np.inf, 0.0),
                ),
            )
            z_scores.iloc[positions] = z

        sub["z_score"] = z_scores
        sub["is_alert"] = (
            sub["z_score"].abs().ge(z_threshold)
            & sub["price_change_pct_7d"].abs().ge(min_pct_change)
            & actual_price_reported
            & exact_reference_available
        ).fillna(False).astype(bool)

        # An alert is associated with the heuristic if its current observation
        # or its exact seven-day reference is an isolated point. Association is
        # a review cue, not proof that the point is erroneous or caused the move.
        referenced_outlier = sub["is_isolated_price_outlier"].shift(7).eq(True)
        sub["outlier_associated_alert"] = (
            sub["is_alert"]
            & (sub["is_isolated_price_outlier"] | referenced_outlier)
        ).astype(bool)

        # Group alert observations across short gaps. IDs are assigned only
        # to alert rows; intervening non-alert dates remain NA.
        sub["alert_event_id"] = assign_alert_event_ids(
            sub["is_alert"], event_gap_days=event_gap_days
        )

        if "indicative_spread" in sub.columns:
            # Tolerance avoids treating tiny floating-point residue as a
            # meaningful negative spread.
            sub["spread_review_flag"] = (
                sub["indicative_spread"] < -1e-6
            ).fillna(False)
        else:
            sub["spread_review_flag"] = False

        alert_days = int(sub["is_alert"].sum())
        group_count = int(sub["alert_event_id"].nunique())
        infinite_z_scores = int(np.isinf(sub["z_score"].to_numpy(dtype="float64")).sum())
        logging.info(
            "Detected %s alert days across %s grouped alert episodes for %s (%s); "
            "%s infinite Z-scores.",
            alert_days,
            group_count,
            commodity,
            unit,
            infinite_z_scores,
        )
        return sub.reset_index()
