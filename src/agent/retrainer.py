import os
import time
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
import sys
sys.path.append(os.getcwd())

from src.data.fetcher import BinanceDataFetcher
from src.data.processor import DataProcessor
from src.env.trading_env import TradingEnv

def retrain_model(total_timesteps=5000):
    """
    Loads the existing model, fetches RECENT data, and performs a QUICK update.
    This is now an incremental learning step (Fine-Tuning) after each trade.
    """
    MODEL_PATH = "models/ppo_trading_bot"
    
    print(f"[Retrainer] Starting incremental update ({total_timesteps} steps)...")
    
    # 1. Fetch Latest Data (Focus on recent context for faster adaptation)
    # Reduced from 30 days to 7 days for speed and relevance to current market regime.
    days_back = 7
    start_time = int(time.time() * 1000) - (days_back * 24 * 60 * 60 * 1000)
    
    fetcher = BinanceDataFetcher(symbol='BTC/USDT')
    print(f"[Retrainer] Fetching data since {pd.to_datetime(start_time, unit='ms')}...")
    
    try:
        df_5m = fetcher.fetch_ohlcv(timeframe='5m', since=start_time)
        others = {
            '15m': fetcher.fetch_ohlcv(timeframe='15m', since=start_time),
            '1h': fetcher.fetch_ohlcv(timeframe='1h', since=start_time),
            '1m': fetcher.fetch_ohlcv(timeframe='1m', since=start_time)
        }
        
        # 2. Process
        processor = DataProcessor(df_5m)
        df_base = processor.add_technical_indicators()
        df_base = processor.normalize_features() # Apply Normalization
        
        df_merged = DataProcessor.merge_timeframes(df_base, others)
        print(f"[Retrainer] Data ready. Shape: {df_merged.shape}")
        
        # 3. Create Environment
        env = DummyVecEnv([lambda: TradingEnv(df_merged)])
        
        # 4. Load Existing Model & Resume Training
        if os.path.exists(MODEL_PATH + ".zip"):
            print(f"[Retrainer] Loading existing model from {MODEL_PATH}...")
            try:
                model = PPO.load(MODEL_PATH, env=env)
            except ValueError as e:
                print(f"[Retrainer] ⚠️ Model shape mismatch (New Feature Set?): {e}")
                print("[Retrainer] Creating NEW model from scratch...")
                model = PPO('MlpPolicy', env, verbose=1)
        else:
            print("[Retrainer] No existing model found. Creating new PPO model...")
            model = PPO('MlpPolicy', env, verbose=1)
            
        # 5. Learn
        model.learn(total_timesteps=total_timesteps)
        
        # 6. Save
        model.save(MODEL_PATH)
        print(f"[Retrainer] Model updated and saved to {MODEL_PATH}")
        return True
        
    except Exception as e:
        print(f"[Retrainer] Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    retrain_model()
