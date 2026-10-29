import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


class DataLoader:
    """Load and validate the retail and wholesale CSV source files."""

    REQUIRED_COLUMNS = {"date", "state_name", "commodity", "price"}
    MAX_INVALID_DATE_FRACTION = 0.01

    def __init__(
        self,
        retail_path: str | Path,
        wholesale_path: str | Path,
    ) -> None:
        self.retail_path = Path(retail_path)
        self.wholesale_path = Path(wholesale_path)
        self.load_stats: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _validate_columns(
        path: Path,
        required_columns: set[str],
        dataset_name: str,
    ) -> None:
        """Check a CSV's header before asking pandas to select columns."""
        try:
            header = pd.read_csv(path, nrows=0)
        except pd.errors.EmptyDataError as exc:
            raise ValueError(f"{dataset_name} dataset is empty: {path}") from exc
        except (OSError, pd.errors.ParserError) as exc:
            raise ValueError(
                f"Could not read the {dataset_name} CSV header: {path}"
            ) from exc

        missing = sorted(required_columns - set(header.columns))
        if missing:
            raise ValueError(
                f"{dataset_name} dataset is missing required columns: {missing}"
            )

    def _load_dataset(
        self,
        path: Path,
        dataset_name: str,
        output_price_column: str,
        date_format: str | None = None,
    ) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(
                f"{dataset_name} dataset not found at: {path.resolve()}"
            )

        logging.info("Loading %s data from %s...", dataset_name.lower(), path.name)
        self._validate_columns(path, self.REQUIRED_COLUMNS, dataset_name)

        try:
            df = pd.read_csv(
                path,
                usecols=["date", "state_name", "commodity", "price"],
                dtype={
                    "date": "string",
                    "state_name": "category",
                    "commodity": "category",
                    "price": "string",
                },
            )
        except (ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc:
            raise ValueError(
                f"Could not parse the {dataset_name} CSV; check its encoding and structure."
            ) from exc

        original_rows = len(df)
        if original_rows == 0:
            raise ValueError(f"{dataset_name} dataset contains no data rows.")

        # The current retail source uses ISO YYYY-MM-DD dates; wholesale uses
        # the source-defined DD-MM-YYYY format. Strict parsing prevents valid-
        # looking but misinterpreted ambiguous dates from silently shifting.
        effective_date_format = date_format or "%Y-%m-%d"
        parsed_dates = pd.to_datetime(
            df["date"],
            format=effective_date_format,
            errors="coerce",
        )
        invalid_date_mask = parsed_dates.isna()
        invalid_date_count = int(invalid_date_mask.sum())
        invalid_date_fraction = invalid_date_count / original_rows

        if invalid_date_count == original_rows:
            raise ValueError(
                f"{dataset_name} dataset has no valid dates; check its date format."
            )

        if invalid_date_fraction > self.MAX_INVALID_DATE_FRACTION:
            raise ValueError(
                f"{dataset_name} dataset has {invalid_date_count:,} invalid dates "
                f"out of {original_rows:,} rows ({invalid_date_fraction:.2%}), "
                f"exceeding the {self.MAX_INVALID_DATE_FRACTION:.2%} limit."
            )

        raw_price = df["price"]
        blank_price_mask = raw_price.isna() | raw_price.str.strip().eq("").fillna(False)
        numeric_price = pd.to_numeric(raw_price, errors="coerce").astype("float64")
        values = numeric_price.to_numpy(dtype="float64", na_value=np.nan)
        finite_mask = pd.Series(np.isfinite(values), index=df.index)
        non_numeric_mask = numeric_price.isna() & ~blank_price_mask
        non_finite_mask = numeric_price.notna() & ~finite_mask
        non_positive_mask = numeric_price.notna() & finite_mask & (numeric_price <= 0)

        state_missing = df["state_name"].isna() | df["state_name"].astype("string").str.strip().eq("").fillna(False)
        commodity_missing = df["commodity"].isna() | df["commodity"].astype("string").str.strip().eq("").fillna(False)
        missing_key_mask = state_missing | commodity_missing

        # Counts can overlap (e.g. a row may have both an invalid date and price).
        stats = {
            "source_rows": int(original_rows),
            "invalid_dates": invalid_date_count,
            "blank_prices": int(blank_price_mask.sum()),
            "non_numeric_prices": int(non_numeric_mask.sum()),
            "non_finite_prices": int(non_finite_mask.sum()),
            "non_positive_prices": int(non_positive_mask.sum()),
            "missing_state_or_commodity": int(missing_key_mask.sum()),
        }

        valid_mask = (
            ~invalid_date_mask
            & ~blank_price_mask
            & ~non_numeric_mask
            & ~non_finite_mask
            & ~non_positive_mask
            & ~missing_key_mask
        )

        retained_rows = int(valid_mask.sum())
        stats["retained_rows"] = retained_rows
        stats["excluded_rows"] = int(original_rows - retained_rows)
        self.load_stats[dataset_name.lower()] = stats

        issues = {
            "invalid dates": invalid_date_count,
            "blank prices": stats["blank_prices"],
            "non-numeric prices": stats["non_numeric_prices"],
            "non-finite prices": stats["non_finite_prices"],
            "non-positive prices": stats["non_positive_prices"],
            "missing state/commodity": stats["missing_state_or_commodity"],
        }
        issue_text = "; ".join(f"{name}={count:,}" for name, count in issues.items())
        if any(issues.values()):
            logging.warning("%s data-quality counts: %s", dataset_name, issue_text)
        else:
            logging.info("%s data-quality checks found no invalid rows.", dataset_name)

        if retained_rows == 0:
            raise ValueError(
                f"{dataset_name} dataset has no valid rows after date, price, "
                "and key validation."
            )

        result = df.loc[valid_mask, ["state_name", "commodity"]].copy()
        result["date"] = parsed_dates.loc[valid_mask]
        result[output_price_column] = numeric_price.loc[valid_mask].astype("float64")
        result = result[["date", "state_name", "commodity", output_price_column]]
        result = result.reset_index(drop=True)

        logging.info(
            "%s loaded: %s valid rows retained out of %s.",
            dataset_name,
            f"{len(result):,}",
            f"{original_rows:,}",
        )
        return result

    def load_retail(self) -> pd.DataFrame:
        """Load retail prices whose current source uses YYYY-MM-DD dates."""
        return self._load_dataset(
            path=self.retail_path,
            dataset_name="Retail",
            output_price_column="retail_price_kg",
        )

    def load_wholesale(self) -> pd.DataFrame:
        """Load wholesale prices whose source dates are DD-MM-YYYY."""
        return self._load_dataset(
            path=self.wholesale_path,
            dataset_name="Wholesale",
            output_price_column="wholesale_price_quintal",
            date_format="%d-%m-%Y",
        )


if __name__ == "__main__":
    loader = DataLoader(
        retail_path="data/daily-retail-prices-of-essential-commodities.csv",
        wholesale_path="data/state-level-daily-wholesale-price.csv",
    )
    retail = loader.load_retail()
    wholesale = loader.load_wholesale()
    print("\n--- DATA LOAD VERIFIED ---")
    print(f"Retail shape: {retail.shape}")
    print(f"Wholesale shape: {wholesale.shape}")
