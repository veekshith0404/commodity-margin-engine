import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from core.loader import DataLoader


class LoaderHardeningTests(unittest.TestCase):
    def make_loader(self, directory: str, filename: str = "retail.csv"):
        path = Path(directory) / filename
        loader = DataLoader(
            retail_path=path,
            wholesale_path=Path(directory) / "wholesale.csv",
        )
        return loader, path

    def test_missing_required_column_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            loader, path = self.make_loader(tmp)
            path.write_text(
                "date,state_name,commodity\n2024-01-01,Karnataka,Tomato\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "missing required columns"):
                loader.load_retail()

    def test_retail_parser_rejects_non_iso_date_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            loader, path = self.make_loader(tmp)
            path.write_text(
                'date,state_name,commodity,price\n'
                '2024-01-01,Karnataka,Tomato,20.0\n'
                '05-03-2024,Karnataka,Tomato,21.0\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "exceeding the"):
                loader.load_retail()

    def test_invalid_retail_date_is_counted_and_excluded_for_small_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            loader, path = self.make_loader(tmp)
            rows = ["date,state_name,commodity,price"]
            rows.extend(
                f"2024-01-{(i % 28) + 1:02d},Karnataka,Tomato,{20 + i / 10}"
                for i in range(99)
            )
            rows.append("not-a-date,Karnataka,Tomato,25.0")
            path.write_text("\n".join(rows), encoding="utf-8")
            result = loader.load_retail()
            self.assertEqual(len(result), 99)
            self.assertEqual(loader.load_stats["retail"]["invalid_dates"], 1)
            self.assertEqual(loader.load_stats["retail"]["excluded_rows"], 1)

    def test_all_invalid_dates_raise_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            loader, path = self.make_loader(tmp)
            path.write_text(
                "date,state_name,commodity,price\n"
                "bad-date,Karnataka,Tomato,20.0\n"
                "also-bad,Karnataka,Tomato,21.0\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "no valid dates"):
                loader.load_retail()

    def test_large_invalid_date_fraction_raises_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            loader, path = self.make_loader(tmp)
            rows = ["date,state_name,commodity,price"]
            rows.extend(
                f"2024-01-01,Karnataka,Tomato,{20 + i / 100}"
                for i in range(98)
            )
            rows.extend([
                "bad-date,Karnataka,Tomato,20.0",
                "also-bad,Karnataka,Tomato,21.0",
            ])
            path.write_text("\n".join(rows), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exceeding the"):
                loader.load_retail()

    def test_invalid_prices_are_excluded_and_float64_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            loader, path = self.make_loader(tmp)
            path.write_text(
                "date,state_name,commodity,price\n"
                "2024-01-01,Karnataka,Tomato,20.0\n"
                "2024-01-02,Karnataka,Tomato,0\n"
                "2024-01-03,Karnataka,Tomato,-5\n"
                "2024-01-04,Karnataka,Tomato,not-a-number\n"
                "2024-01-05,Karnataka,Tomato,\n",
                encoding="utf-8",
            )
            result = loader.load_retail()
            self.assertEqual(len(result), 1)
            self.assertEqual(result.iloc[0]["retail_price_kg"], 20.0)
            self.assertEqual(result["retail_price_kg"].dtype, np.dtype("float64"))
            stats = loader.load_stats["retail"]
            self.assertEqual(stats["non_positive_prices"], 2)
            self.assertEqual(stats["non_numeric_prices"], 1)
            self.assertEqual(stats["blank_prices"], 1)

    def test_infinite_prices_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            loader, path = self.make_loader(tmp)
            path.write_text(
                "date,state_name,commodity,price\n"
                "2024-01-01,Karnataka,Tomato,20.0\n"
                "2024-01-02,Karnataka,Tomato,inf\n"
                "2024-01-03,Karnataka,Tomato,-inf\n",
                encoding="utf-8",
            )
            result = loader.load_retail()
            self.assertEqual(len(result), 1)
            self.assertEqual(loader.load_stats["retail"]["non_finite_prices"], 2)

    def test_no_valid_prices_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            loader, path = self.make_loader(tmp)
            path.write_text(
                "date,state_name,commodity,price\n"
                "2024-01-01,Karnataka,Tomato,0\n"
                "2024-01-02,Karnataka,Tomato,-2\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "no valid rows"):
                loader.load_retail()

    def test_missing_state_or_commodity_rows_are_excluded_and_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            loader, path = self.make_loader(tmp)
            path.write_text(
                "date,state_name,commodity,price\n"
                "2024-01-01,Karnataka,Tomato,20.0\n"
                "2024-01-02,,Tomato,21.0\n"
                "2024-01-03,Karnataka,,22.0\n",
                encoding="utf-8",
            )
            result = loader.load_retail()
            self.assertEqual(len(result), 1)
            self.assertEqual(
                loader.load_stats["retail"]["missing_state_or_commodity"], 2
            )

    def test_wholesale_wrong_date_format_raises_instead_of_returning_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wholesale.csv"
            path.write_text(
                "date,state_name,commodity,price\n"
                "2024-01-02,Karnataka,Tomato,2000.0\n",
                encoding="utf-8",
            )
            loader = DataLoader(Path(tmp) / "retail.csv", path)
            with self.assertRaisesRegex(ValueError, "no valid dates"):
                loader.load_wholesale()

    def test_wholesale_uses_day_month_year(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wholesale.csv"
            path.write_text(
                "date,state_name,commodity,price\n"
                "02-01-2024,Karnataka,Tomato,2000.0\n",
                encoding="utf-8",
            )
            loader = DataLoader(Path(tmp) / "retail.csv", path)
            result = loader.load_wholesale()
            self.assertEqual(result.iloc[0]["date"], pd.Timestamp("2024-01-02"))


if __name__ == "__main__":
    unittest.main()
