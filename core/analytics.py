import logging
import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

class CommodityAnalytics:
    """
    Computes statistical indicators: Coefficient of Variation (CV) for relative volatility
    and calendar-aware, leakage-free rolling Z-scores for statistical price-change alerts.
    """
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def compute_volatility_table(self) -> pd.DataFrame:
        """
        Calculates Coefficient of Variation (CV = std / mean * 100)
        to compare price risk fairly across commodities with disparate price bases.
        Safely handles zero/negative means.
        """
        logging.info("Computing commodity volatility metrics...")
        stats = self.df.groupby('commodity', observed=True)['retail_price_normalized'].agg(
            mean_price='mean',
            std_price='std',
            min_price='min',
            max_price='max',
            observations='count'
        ).reset_index()

        stats['cv_pct'] = np.where(
            stats['mean_price'] > 1e-4,
            (stats['std_price'] / stats['mean_price']) * 100.0,
            np.nan
        )
        stats = stats.sort_values(by='cv_pct', ascending=False).reset_index(drop=True)
        return stats

    def detect_shocks(
        self,
        commodity: str,
        z_threshold: float = 2.5,
        min_price_change: float = 5.0,
        window: int = 30
    ) -> pd.DataFrame:
        """
        Gap-resilient, calendar-aware statistical price-change alert detector:
        1. Aligns onto a daily calendar using max 3-day forward-fill ONLY for velocity
           reference so non-reporting weekends/holidays don't void 7-day velocity.
        2. Applies .shift(1) on rolling 30-day baseline to eliminate lookahead leakage.
        3. Safely evaluates zero variance baselines and applies dual criteria:
           |Z| >= z_threshold AND |Delta P_7d| >= min_price_change.
        """
        sub = self.df[self.df['commodity'] == commodity].sort_values('date').copy()
        if sub.empty:
            logging.warning(f"No records found for commodity '{commodity}'.")
            return pd.DataFrame()

        unit = sub['normalized_unit'].iloc[0] if 'normalized_unit' in sub.columns else "₹/kg"
        state = sub['state_name'].iloc[0] if 'state_name' in sub.columns else "Unknown"

        # Continuous daily calendar
        sub = sub.set_index('date')
        full_idx = pd.date_range(start=sub.index.min(), end=sub.index.max(), freq='D')
        sub = sub.reindex(full_idx)
        sub.index.name = 'date'

        sub['commodity'] = commodity
        sub['normalized_unit'] = unit
        sub['state_name'] = state

        # Limited forward fill (max 3 days for weekends/holidays) so 7-day velocity is reliable
        price_daily_filled = sub['retail_price_normalized'].ffill(limit=3)

        # 7-calendar-day price velocity (P_t - P_{t-7})
        # Evaluated only on days where an actual retail price was reported
        velocity_7d = price_daily_filled.diff(periods=7)
        sub['price_diff_7d'] = np.where(sub['retail_price_normalized'].notna(), velocity_7d, np.nan)

        # Leakage-free baseline strictly using prior observed velocities
        baseline_diff = sub['price_diff_7d'].shift(1)
        rolling_mean = baseline_diff.rolling(window=window, min_periods=5).mean()
        rolling_std = baseline_diff.rolling(window=window, min_periods=5).std()

        # Safe Z-score calculation handling zero std dev and insufficient history
        is_valid_baseline = rolling_mean.notna() & rolling_std.notna() & sub['price_diff_7d'].notna()
        diff_from_mean = sub['price_diff_7d'] - rolling_mean

        z_score = np.where(
            ~is_valid_baseline,
            np.nan,
            np.where(
                rolling_std > 1e-5,
                diff_from_mean / rolling_std,
                np.where(diff_from_mean != 0, np.sign(diff_from_mean) * np.inf, 0.0)
            )
        )
        sub['z_score'] = z_score

        # Dual-criteria Statistical Price-Change Alert
        sub['is_alert'] = (
            (np.abs(sub['z_score']) >= z_threshold) & 
            (np.abs(sub['price_diff_7d']) >= min_price_change)
        ).fillna(False)

        alert_count = int(sub['is_alert'].sum())
        logging.info(f"Detected {alert_count} calendar-verified statistical price-change alerts for {commodity} ({unit}).")
        
        return sub.reset_index()