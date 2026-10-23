import logging
from pathlib import Path
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

class DataLoader:
    """
    Ingests and validates historical Retail and Wholesale price datasets
    sourced from the Department of Consumer Affairs.
    """
    REQUIRED_RETAIL_COLS = {'date', 'state_name', 'commodity', 'price'}
    REQUIRED_WHOLESALE_COLS = {'date', 'state_name', 'commodity', 'price'}

    def __init__(self, retail_path: str | Path, wholesale_path: str | Path):
        self.retail_path = Path(retail_path)
        self.wholesale_path = Path(wholesale_path)

    def load_retail(self) -> pd.DataFrame:
        """Loads and validates state-level daily retail prices (₹/kg)."""
        if not self.retail_path.exists():
            raise FileNotFoundError(f"Retail dataset not found at: {self.retail_path.resolve()}")

        logging.info(f"Loading retail data from {self.retail_path.name}...")
        df = pd.read_csv(
            self.retail_path,
            usecols=['date', 'state_name', 'commodity', 'price'],
            dtype={
                'state_name': 'category',
                'commodity': 'category',
                'price': 'float32'
            }
        )

        missing_cols = self.REQUIRED_RETAIL_COLS - set(df.columns)
        if missing_cols:
            raise ValueError(f"Retail dataset missing required columns: {missing_cols}")

        df['date'] = pd.to_datetime(df['date'])
        df = df.rename(columns={'price': 'retail_price_kg'})
        
        logging.info(f"Retail loaded successfully: {len(df):,} rows.")
        return df

    def load_wholesale(self) -> pd.DataFrame:
        """Loads and validates state-level daily wholesale prices (₹/Quintal)."""
        if not self.wholesale_path.exists():
            raise FileNotFoundError(f"Wholesale dataset not found at: {self.wholesale_path.resolve()}")

        logging.info(f"Loading wholesale data from {self.wholesale_path.name}...")
        df = pd.read_csv(
            self.wholesale_path,
            usecols=['date', 'state_name', 'commodity', 'price'],
            dtype={
                'state_name': 'category',
                'commodity': 'category',
                'price': 'float32'
            }
        )

        missing_cols = self.REQUIRED_WHOLESALE_COLS - set(df.columns)
        if missing_cols:
            raise ValueError(f"Wholesale dataset missing required columns: {missing_cols}")

        # Wholesale dataset uses DD-MM-YYYY format
        df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y', errors='coerce')
        df = df.rename(columns={'price': 'wholesale_price_quintal'})

        logging.info(f"Wholesale loaded successfully: {len(df):,} rows.")
        return df


if __name__ == "__main__":
    loader = DataLoader(
        retail_path="data/daily-retail-prices-of-essential-commodities.csv",
        wholesale_path="data/state-level-daily-wholesale-price.csv"
    )
    
    df_retail = loader.load_retail()
    df_wholesale = loader.load_wholesale()
    
    print("\n--- DATA LOAD VERIFIED ---")
    print(f"Retail shape: {df_retail.shape}")
    print(f"Wholesale shape: {df_wholesale.shape}")