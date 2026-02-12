import os
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv

from src.data.fetcher import BinanceDataFetcher
from src.data.processor import DataProcessor
from src.env.trading_env import TradingEnv

def train():
    import time
    
    # 1. Fetch Multi-Timeframe Data
    # Calculate start time (e.g., 20 days ago to cover 1500+ periods of 15m)
    # 20 days * 24h * 60m * 60s * 1000ms
    days_back = 20
    start_time = int(time.time() * 1000) - (days_back * 24 * 60 * 60 * 1000)
    
    fetcher = BinanceDataFetcher(symbol='BTC/USDT')
    
    # Fetch all from start_time
    print(f"Fetching data starting from {pd.to_datetime(start_time, unit='ms')}...")
    
    # Primary TF: 15m
    df_15m = fetcher.fetch_ohlcv(timeframe='15m', since=start_time)
    
    # Secondary TFs: 5m, 1h, 1m
    others = {
        '5m': fetcher.fetch_ohlcv(timeframe='5m', since=start_time),
        '1h': fetcher.fetch_ohlcv(timeframe='1h', since=start_time),
        '1m': fetcher.fetch_ohlcv(timeframe='1m', since=start_time)
    }
    
    # 2. Process and Merge
    processor_15m = DataProcessor(df_15m)
    df_base = processor_15m.add_technical_indicators()
    df_base = processor_15m.normalize_features() # Add Normalization!
    
    df_merged = DataProcessor.merge_timeframes(df_base, others)
    print(f"Final merged features: {df_merged.columns.tolist()}")
    
    # 3. Create Environment
    env = DummyVecEnv([lambda: TradingEnv(df_merged)])
    
    # 4. Define Model (PPO)
    model = PPO('MlpPolicy', env, verbose=1, tensorboard_log="./logs/")
    
    # 5. Train Model (Increase Steps to 100k)
    print("Training model with Multi-Timeframe data (100k steps)...")
    model.learn(total_timesteps=100000)
    
    # 6. Save Model
    models_dir = "models"
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)
    
    model_path = f"{models_dir}/ppo_trading_bot"
    model.save(model_path)
    print(f"Model saved to {model_path}")

if __name__ == "__main__":
    train()
