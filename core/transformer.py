import logging
from typing import Any

import numpy as np
import pandas as pd


# Source-derived working assumptions. Recheck these if the source files change.
COMMODITY_UNIT_REGISTRY = {
    "Tomato": {"unit": "₹/kg", "divisor": 100.0, "description": "Vegetable (₹/kg)"},
    "Onion": {"unit": "₹/kg", "divisor": 100.0, "description": "Vegetable (₹/kg)"},
    "Potato": {"unit": "₹/kg", "divisor": 100.0, "description": "Vegetable (₹/kg)"},
    "Rice": {"unit": "₹/kg", "divisor": 100.0, "description": "Food grain (₹/kg)"},
    "Wheat": {"unit": "₹/kg", "divisor": 100.0, "description": "Food grain (₹/kg)"},
    "Milk": {"unit": "₹/litre", "divisor": 100.0, "description": "Dairy (₹/litre)"},
}

JOIN_KEYS = ["date", "state_name", "commodity"]
SPREAD_NUMERICAL_TOLERANCE = 1e-6


class DataTransformer:
    """Normalize labels/units, validate rows, deduplicate, and join prices."""

    def __init__(
        self,
        df_retail: pd.DataFrame,
        df_wholesale: pd.DataFrame,
    ) -> None:
        self.df_retail = df_retail.copy()
        self.df_wholesale = df_wholesale.copy()
        self.quality_summary: dict[str, Any] = {}

    @staticmethod
    def _normalize_text(value: object, remove_markers: bool = False) -> object:
        if pd.isna(value):
            return pd.NA
        text = str(value).strip()
        if remove_markers:
            for marker in ("@", "#", "*"):
                text = text.replace(marker, "")
        normalized = " ".join(text.split()).title()
        # Harmonize known names used differently by the two source files.
        aliases = {
            "Andaman And Nicobar": "Andaman And Nicobar Islands",
            "Andaman And Nicobar Islands": "Andaman And Nicobar Islands",
            "Dnh And Dd": "Dadra And Nagar Haveli And Daman And Diu",
            "The Dadra And Nagar Haveli And Daman And Diu": "Dadra And Nagar Haveli And Daman And Diu",
            "Dadra And Nagar Haveli And Daman And Diu": "Dadra And Nagar Haveli And Daman And Diu",
        }
        return aliases.get(normalized, normalized)

    @classmethod
    def _standardize_frame(cls, frame: pd.DataFrame) -> pd.DataFrame:
        normalized = frame.copy()
        normalized["state_name"] = normalized["state_name"].map(
            lambda value: cls._normalize_text(value)
        ).astype("category")
        normalized["commodity"] = normalized["commodity"].map(
            lambda value: cls._normalize_text(value, remove_markers=True)
        ).astype("category")
        return normalized

    @staticmethod
    def _validate_columns(
        frame: pd.DataFrame,
        required: set[str],
        dataset_name: str,
    ) -> None:
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(
                f"{dataset_name} input is missing required columns: {missing}"
            )

    @staticmethod
    def _prepare_prices(
        frame: pd.DataFrame,
        date_column: str,
        price_column: str,
    ) -> tuple[pd.DataFrame, dict[str, int]]:
        prepared = frame.copy()
        prepared[date_column] = pd.to_datetime(
            prepared[date_column], errors="coerce"
        )
        prepared[price_column] = pd.to_numeric(
            prepared[price_column], errors="coerce"
        ).astype("float64")

        price_values = prepared[price_column].to_numpy(
            dtype="float64", na_value=np.nan
        )
        finite = pd.Series(np.isfinite(price_values), index=prepared.index)
        invalid_date = prepared[date_column].isna()
        missing_price = prepared[price_column].isna()
        non_finite = prepared[price_column].notna() & ~finite
        non_positive = (
            prepared[price_column].notna()
            & finite
            & (prepared[price_column] <= 0)
        )
        invalid = invalid_date | missing_price | non_finite | non_positive
        counts = {
            "input_rows": int(len(prepared)),
            "invalid_dates": int(invalid_date.sum()),
            "missing_or_non_numeric_prices": int(missing_price.sum()),
            "non_finite_prices": int(non_finite.sum()),
            "non_positive_prices": int(non_positive.sum()),
            "excluded_rows": int(invalid.sum()),
        }
        return prepared.loc[~invalid].copy(), counts


    def prepare_retail_series(
        self,
        state: str,
        commodity: str,
    ) -> pd.DataFrame:
        """Return cleaned retail observations independently of wholesale coverage.

        The output has one row per date/state/commodity after averaging duplicate
        daily keys. It is suitable for retail-only price-change detection.
        """
        required = {"date", "state_name", "commodity", "retail_price_kg"}
        self._validate_columns(self.df_retail, required, "Retail")
        clean_state = str(self._normalize_text(state))
        clean_commodity = str(self._normalize_text(commodity, remove_markers=True))
        if clean_commodity not in COMMODITY_UNIT_REGISTRY:
            raise ValueError(f"Unsupported commodity: {clean_commodity}")

        retail = self._standardize_frame(self.df_retail)
        retail = retail.loc[
            retail["state_name"].eq(clean_state)
            & retail["commodity"].eq(clean_commodity)
        ].copy()
        if retail.empty:
            return pd.DataFrame(columns=[
                "date", "state_name", "commodity", "retail_price_normalized",
                "normalized_unit",
            ])

        retail, invalid_stats = self._prepare_prices(
            retail, "date", "retail_price_kg"
        )
        if invalid_stats["excluded_rows"]:
            logging.warning(
                "Retail-only alert preparation excluded %s invalid row(s) for %s / %s.",
                f"{invalid_stats['excluded_rows']:,}", clean_state, clean_commodity,
            )
        if retail.empty:
            return pd.DataFrame(columns=[
                "date", "state_name", "commodity", "retail_price_normalized",
                "normalized_unit",
            ])

        retail = (
            retail.groupby(JOIN_KEYS, observed=True, as_index=False)
            .agg(retail_price_kg=("retail_price_kg", "mean"))
        )
        retail = retail.rename(columns={"retail_price_kg": "retail_price_normalized"})
        retail["normalized_unit"] = COMMODITY_UNIT_REGISTRY[clean_commodity]["unit"]
        return retail.sort_values("date").reset_index(drop=True)

    def transform(
        self,
        state: str = "Karnataka",
        commodities: list[str] | None = None,
    ) -> pd.DataFrame:
        """Return matched valid observations with normalized wholesale prices."""
        retail_required = {"date", "state_name", "commodity", "retail_price_kg"}
        wholesale_required = {
            "date", "state_name", "commodity", "wholesale_price_quintal"
        }
        self._validate_columns(self.df_retail, retail_required, "Retail")
        self._validate_columns(self.df_wholesale, wholesale_required, "Wholesale")

        if commodities is None:
            commodities = list(COMMODITY_UNIT_REGISTRY)
        clean_commodities = [
            str(self._normalize_text(item, remove_markers=True))
            for item in commodities
        ]
        unsupported = [
            item for item in clean_commodities
            if item not in COMMODITY_UNIT_REGISTRY
        ]
        if unsupported:
            raise ValueError(
                f"Unsupported commodity unit mappings: {unsupported}. "
                "Check the source metadata before adding commodities."
            )

        clean_state = str(self._normalize_text(state))
        retail = self._standardize_frame(self.df_retail)
        wholesale = self._standardize_frame(self.df_wholesale)

        r_sub = retail.loc[
            retail["state_name"].eq(clean_state)
            & retail["commodity"].isin(clean_commodities)
        ].copy()
        w_sub = wholesale.loc[
            wholesale["state_name"].eq(clean_state)
            & wholesale["commodity"].isin(clean_commodities)
        ].copy()

        if r_sub.empty or w_sub.empty:
            logging.warning(
                "No source rows found for state '%s' in retail or wholesale data.",
                clean_state,
            )
            self.quality_summary = {
                "state": clean_state,
                "filtered_retail_rows": int(len(r_sub)),
                "filtered_wholesale_rows": int(len(w_sub)),
                "retail_invalid": {},
                "wholesale_invalid": {},
                "coverage_by_commodity": {},
                "matched_rows": 0,
                "retail_key_coverage_pct": 0.0,
            }
            return pd.DataFrame()

        r_sub, retail_invalid = self._prepare_prices(
            r_sub, "date", "retail_price_kg"
        )
        w_sub, wholesale_invalid = self._prepare_prices(
            w_sub, "date", "wholesale_price_quintal"
        )

        if retail_invalid["excluded_rows"]:
            logging.warning(
                "Retail transformer validation excluded %s state/commodity row(s).",
                f"{retail_invalid['excluded_rows']:,}",
            )
        if wholesale_invalid["excluded_rows"]:
            logging.warning(
                "Wholesale transformer validation excluded %s state/commodity row(s).",
                f"{wholesale_invalid['excluded_rows']:,}",
            )

        if not r_sub.empty:
            duplicate_rows = int(r_sub.duplicated(subset=JOIN_KEYS).sum())
            if duplicate_rows:
                logging.warning(
                    "Retail has %s duplicate join-key rows; aggregating daily means.",
                    f"{duplicate_rows:,}",
                )
            r_sub = (
                r_sub.groupby(JOIN_KEYS, observed=True, as_index=False)
                .agg(retail_price_kg=("retail_price_kg", "mean"))
            )

        if not w_sub.empty:
            duplicate_rows = int(w_sub.duplicated(subset=JOIN_KEYS).sum())
            if duplicate_rows:
                logging.warning(
                    "Wholesale has %s duplicate join-key rows; aggregating daily means.",
                    f"{duplicate_rows:,}",
                )
            w_sub = (
                w_sub.groupby(JOIN_KEYS, observed=True, as_index=False)
                .agg(wholesale_price_quintal=("wholesale_price_quintal", "mean"))
            )

        r_counts = r_sub.groupby("commodity", observed=True).size().to_dict()
        w_counts = w_sub.groupby("commodity", observed=True).size().to_dict()

        merged = pd.merge(
            r_sub,
            w_sub,
            on=JOIN_KEYS,
            how="inner",
            validate="one_to_one",
        )

        merged_counts = merged.groupby("commodity", observed=True).size().to_dict()
        coverage_by_commodity = {}
        for commodity in clean_commodities:
            r_count = int(r_counts.get(commodity, 0))
            w_count = int(w_counts.get(commodity, 0))
            matched_count = int(merged_counts.get(commodity, 0))
            coverage_by_commodity[commodity] = {
                "valid_retail_keys": r_count,
                "valid_wholesale_keys": w_count,
                "matched_keys": matched_count,
                "retail_match_pct": (
                    100.0 * matched_count / r_count if r_count else 0.0
                ),
                "wholesale_match_pct": (
                    100.0 * matched_count / w_count if w_count else 0.0
                ),
            }

        total_retail_keys = len(r_sub)
        overall_coverage = (
            100.0 * len(merged) / total_retail_keys
            if total_retail_keys else 0.0
        )
        self.quality_summary = {
            "state": clean_state,
            "filtered_retail_rows": int(retail_invalid["input_rows"]),
            "filtered_wholesale_rows": int(wholesale_invalid["input_rows"]),
            "valid_retail_keys": int(total_retail_keys),
            "valid_wholesale_keys": int(len(w_sub)),
            "retail_invalid": retail_invalid,
            "wholesale_invalid": wholesale_invalid,
            "coverage_by_commodity": coverage_by_commodity,
            "matched_rows": int(len(merged)),
            "retail_key_coverage_pct": overall_coverage,
        }

        logging.info(
            "Merge coverage: %s matched unique keys out of %s valid, deduplicated "
            "retail keys (%.1f%%).",
            f"{len(merged):,}",
            f"{total_retail_keys:,}",
            overall_coverage,
        )

        if merged.empty:
            logging.warning("No records matched on date, state, and commodity.")
            return pd.DataFrame()

        commodity_text = merged["commodity"].astype("string")
        units = commodity_text.map(
            {name: item["unit"] for name, item in COMMODITY_UNIT_REGISTRY.items()}
        )
        divisors = commodity_text.map(
            {name: item["divisor"] for name, item in COMMODITY_UNIT_REGISTRY.items()}
        )
        if units.isna().any() or divisors.isna().any():
            raise ValueError(
                "A merged commodity has no explicit unit mapping. "
                "Review COMMODITY_UNIT_REGISTRY."
            )

        merged["normalized_unit"] = units
        merged["retail_price_normalized"] = merged["retail_price_kg"].astype("float64")
        merged["wholesale_price_normalized"] = (
            merged["wholesale_price_quintal"].astype("float64")
            / divisors.astype("float64")
        )
        merged["indicative_spread"] = (
            merged["retail_price_normalized"]
            - merged["wholesale_price_normalized"]
        )
        merged["spread_review_flag"] = (
            merged["indicative_spread"] < -SPREAD_NUMERICAL_TOLERANCE
        )

        return merged.sort_values(["commodity", "date"]).reset_index(drop=True)
