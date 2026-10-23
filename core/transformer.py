import logging
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Authoritative unit mapping based on Department of Consumer Affairs (DCA) metadata:
# - Cereal/Vegetable wholesale reporting: ₹/quintal (1 quintal = 100 kg) -> normalized to ₹/kg
# - Dairy wholesale reporting: ₹/100 litres -> normalized to ₹/litre
COMMODITY_UNIT_REGISTRY = {
    "Tomato": {"unit": "₹/kg", "divisor": 100.0, "description": "Vegetable (₹/kg)"},
    "Onion": {"unit": "₹/kg", "divisor": 100.0, "description": "Vegetable (₹/kg)"},
    "Potato": {"unit": "₹/kg", "divisor": 100.0, "description": "Vegetable (₹/kg)"},
    "Rice": {"unit": "₹/kg", "divisor": 100.0, "description": "Food Grain (₹/kg)"},
    "Wheat": {"unit": "₹/kg", "divisor": 100.0, "description": "Food Grain (₹/kg)"},
    "Milk": {"unit": "₹/litre", "divisor": 100.0, "description": "Dairy (₹/litre)"},
}

class DataTransformer:
    """
    Standardizes categorical schemas, validates and converts units,
    detects duplicates, joins retail/wholesale datasets, and calculates
    indicative price spreads.
    """
    def __init__(self, df_retail: pd.DataFrame, df_wholesale: pd.DataFrame):
        self.df_retail = df_retail.copy()
        self.df_wholesale = df_wholesale.copy()

    def standardize_strings(self) -> None:
        """Strips whitespace, symbols like '@', and normalizes text casing."""
        for df in [self.df_retail, self.df_wholesale]:
            df['state_name'] = (
                df['state_name']
                .astype(str)
                .str.strip()
                .str.title()
                .astype('category')
            )
            df['commodity'] = (
                df['commodity']
                .astype(str)
                .str.replace(r'[@#*]', '', regex=True)
                .str.strip()
                .str.title()
                .astype('category')
            )

    def transform(
        self,
        state: str = "Karnataka",
        commodities: list[str] | None = None
    ) -> pd.DataFrame:
        """
        Validates, filters, deduplicates, converts units, and merges retail and wholesale data.
        """
        self.standardize_strings()
        clean_state = state.strip().title()

        if commodities is None:
            commodities = list(COMMODITY_UNIT_REGISTRY.keys())
        clean_commodities = [c.strip().title() for c in commodities]

        # Verify unit metadata exists for all requested commodities
        unverified = [c for c in clean_commodities if c not in COMMODITY_UNIT_REGISTRY]
        if unverified:
            raise ValueError(f"Unverified commodity units: {unverified}. Please check DCA metadata registry.")

        logging.info(f"Filtering records for State='{clean_state}'...")
        r_sub = self.df_retail[
            (self.df_retail['state_name'] == clean_state) & 
            (self.df_retail['commodity'].isin(clean_commodities))
        ].copy()

        w_sub = self.df_wholesale[
            (self.df_wholesale['state_name'] == clean_state) & 
            (self.df_wholesale['commodity'].isin(clean_commodities))
        ].copy()

        if r_sub.empty or w_sub.empty:
            logging.warning(f"No matching records found for State='{clean_state}' in retail or wholesale data.")
            return pd.DataFrame()

        # Data quality: Check and report missing prices before join
        r_nulls = r_sub['retail_price_kg'].isna().sum()
        w_nulls = w_sub['wholesale_price_quintal'].isna().sum()
        if r_nulls > 0 or w_nulls > 0:
            logging.info(f"Data Quality: Dropped {r_nulls} null retail prices and {w_nulls} null wholesale prices.")

        r_sub = r_sub.dropna(subset=['retail_price_kg'])
        w_sub = w_sub.dropna(subset=['wholesale_price_quintal'])

        # Deduplication check on join keys
        r_dups = r_sub.duplicated(subset=['date', 'state_name', 'commodity']).sum()
        w_dups = w_sub.duplicated(subset=['date', 'state_name', 'commodity']).sum()

        if r_dups > 0:
            logging.warning(f"Retail: Detected {r_dups} duplicate keys. Aggregating by daily mean.")
            r_sub = r_sub.groupby(['date', 'state_name', 'commodity'], observed=True)['retail_price_kg'].mean().reset_index()

        if w_dups > 0:
            logging.warning(f"Wholesale: Detected {w_dups} duplicate keys. Aggregating by daily mean.")
            w_sub = w_sub.groupby(['date', 'state_name', 'commodity'], observed=True)['wholesale_price_quintal'].mean().reset_index()

        logging.info("Merging Retail and Wholesale datasets on [date, state_name, commodity]...")
        merged = pd.merge(
            r_sub,
            w_sub,
            on=['date', 'state_name', 'commodity'],
            how='inner'
        )

        coverage_pct = (len(merged) / max(len(r_sub), 1)) * 100.0
        logging.info(f"Merge coverage: {len(merged):,} records merged ({coverage_pct:.1f}% of retail records matched).")

        if merged.empty:
            logging.warning("Merged dataset is empty after join.")
            return pd.DataFrame()

        # Verified Unit Conversion
        commodity_str = merged['commodity'].astype(str)
        merged['normalized_unit'] = commodity_str.map(lambda c: COMMODITY_UNIT_REGISTRY.get(c, {}).get('unit', '₹/kg'))
        merged['divisor'] = commodity_str.map(lambda c: COMMODITY_UNIT_REGISTRY.get(c, {}).get('divisor', 100.0))
        
        merged['retail_price_normalized'] = merged['retail_price_kg']
        merged['wholesale_price_normalized'] = merged['wholesale_price_quintal'] / merged['divisor']

        # Indicative Gross Price Spread (Retail - Wholesale in normalized units)
        merged['indicative_spread'] = merged['retail_price_normalized'] - merged['wholesale_price_normalized']

        merged = merged.drop(columns=['divisor'])
        merged = merged.sort_values(by=['commodity', 'date']).reset_index(drop=True)
        
        logging.info(f"Transformation complete: {len(merged):,} merged records generated.")
        return merged