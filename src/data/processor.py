import pandas as pd
import ta

class DataProcessor:
    def __init__(self, dataframe):
        self.df = dataframe.copy()

    def add_technical_indicators(self, suffix=""):
        """
        Adds technical indicators to the DataFrame.
        """
        # RSI
        self.df[f'rsi{suffix}'] = ta.momentum.RSIIndicator(self.df['close'], window=14).rsi()
        
        # MACD
        macd = ta.trend.MACD(self.df['close'])
        self.df[f'macd{suffix}'] = macd.macd()
        self.df[f'macd_signal{suffix}'] = macd.macd_signal()
        
        # Bollinger Bands
        bollinger = ta.volatility.BollingerBands(self.df['close'], window=20, window_dev=2)
        self.df[f'bb_high{suffix}'] = bollinger.bollinger_hband()
        self.df[f'bb_low{suffix}'] = bollinger.bollinger_lband()
        
        # EMA
        self.df[f'ema_20{suffix}'] = ta.trend.EMAIndicator(self.df['close'], window=20).ema_indicator()
        
        return self.df

    def normalize_features(self):
        """
        Normalize features for RL agent.
        - Price matches -> Log Returns or % Change
        - Volume -> Log Volume
        - Indicators -> Scaled
        """
        # 1. Log Returns for Price
        self.df['close_pct'] = self.df['close'].pct_change()
        self.df['high_pct'] = self.df['high'].pct_change()
        self.df['low_pct'] = self.df['low'].pct_change()
        self.df['open_pct'] = self.df['open'].pct_change()
        
        # 2. Log Volume
        import numpy as np
        self.df['log_volume'] = np.log1p(self.df['volume'])
        self.df['volume_pct'] = self.df['log_volume'].pct_change()
        
        # 3. Scale Indicators
        # RSI is 0-100, scale to 0-1
        cols = [c for c in self.df.columns if 'rsi' in c]
        for c in cols:
            self.df[c] = self.df[c] / 100.0
            
        # MACD - usually small, but let's leave as is or scale? 
        # Better to use MACD Histogram sign or trend.
        # For simplicity in V2, let's keep raw MACD but it's small enough.
        
        # Bollinger Bands -> Convert to % distance from mid
        # (Price - Lower) / (Upper - Lower) -> % position within band
        # This is a very strong feature: "Band Position"
        # 0 = Lower Band, 0.5 = Mid, 1 = Upper Band
        bb_cols = [c for c in self.df.columns if 'bb_high' in c]
        suffixes = [c.replace('bb_high', '') for c in bb_cols]
        
        for s in suffixes:
            high = self.df[f'bb_high{s}']
            low = self.df[f'bb_low{s}']
            close = self.df['close'] 
            
            # Calculate BB Position
            # For secondary TFs, 'close' might be the same column name but different data
            # normalize_features is called on the TF-specific dataframe in merge_timeframes
            self.df[f'bb_position{s}'] = (close - low) / (high - low)
                
        # Drop NaN
        self.df.dropna(inplace=True)
        return self.df

    @staticmethod
    def merge_timeframes(base_df, other_dfs_dict):
        """
        Merge different timeframes into a single base DataFrame.
        other_dfs_dict: {'5m': df5, '1h': df1h}
        """
        final_df = base_df.copy()
        for tf, df_tf in other_dfs_dict.items():
            # 1. Add indicators to the other timeframe first
            proc_tf = DataProcessor(df_tf)
            df_tf_feat = proc_tf.add_technical_indicators(suffix=f"_{tf}")
            
            # 2. Normalize features (creates close_pct, bb_position_{tf}, etc.)
            df_tf_feat = proc_tf.normalize_features()
            
            # 3. Rename generic normalized columns to include suffix
            # normalize_features creates: close_pct, high_pct, low_pct, open_pct, volume_pct, log_volume
            # It also scales rsi_{tf} (in place) and creates bb_position_{tf} (handled by loop above)
            
            rename_map = {
                'close_pct': f'close_pct_{tf}',
                'high_pct': f'high_pct_{tf}',
                'low_pct': f'low_pct_{tf}',
                'open_pct': f'open_pct_{tf}',
                'volume_pct': f'volume_pct_{tf}',
                'log_volume': f'log_volume_{tf}'
            }
            df_tf_feat.rename(columns=rename_map, inplace=True)
            
            # 4. Select features to merge
            # We want all the new suffixed columns + the indicators that were already suffixed
            # Indicators: rsi_{tf}, macd_{tf}, bb_position_{tf}
            # Normalized: close_pct_{tf}, volume_pct_{tf}
            
            # Simply select all columns that end with _{tf}
            features = [c for c in df_tf_feat.columns if c.endswith(f"_{tf}")]
            
            # Join and forward fill
            final_df = final_df.join(df_tf_feat[features], how='left')
            final_df.ffill(inplace=True)
            
        final_df.dropna(inplace=True)
        return final_df

if __name__ == "__main__":
    # Test with dummy data or load from CSV if available
    try:
        df = pd.read_csv("data.csv", index_col='timestamp', parse_dates=True)
        processor = DataProcessor(df)
        df_processed = processor.add_technical_indicators()
        print(df_processed.tail())
        print(f"Features added: {df_processed.columns.tolist()}")
    except FileNotFoundError:
        print("data.csv not found. Run fetcher.py first.")
