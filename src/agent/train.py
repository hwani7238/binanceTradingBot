import os
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
import numpy as np

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
    
    # 2.1 Fetch Self-Play Data
    from src.env.self_play_env import SelfPlayTradingEnv
    self_play_env = SelfPlayTradingEnv()
    self_play_data = []

    for _ in range(100):  # Generate 100 episodes of self-play data
        state = self_play_env.reset()
        done = False
        while not done:
            action = self_play_env.action_space.sample()  # Random actions for now
            next_state, reward, done, _ = self_play_env.step(action)
            self_play_data.append({
                'state': state,
                'action': action,
                'reward': reward,
                'next_state': next_state
            })
            state = next_state

    # Convert self-play data to DataFrame
    self_play_df = pd.DataFrame(self_play_data)

    # Debugging Self-Play Data
    print("Self-Play Data Sample:")
    print(self_play_df.head())

    # Add 'close' column to Self-Play Data
    self_play_df['close'] = np.random.uniform(10000, 60000, size=len(self_play_df))
    # Add 'volume' column to Self-Play Data
    self_play_df['volume'] = np.random.uniform(100, 10000, size=len(self_play_df))

    # Add Timestamp index to Self-Play Data
    self_play_df['timestamp'] = pd.date_range(start='2026-01-01', periods=len(self_play_df), freq='T')
    self_play_df.set_index('timestamp', inplace=True)

    # 2.2 Combine Self-Play Data with Market Data
    df_combined = processor_15m.combine_self_play_and_market_data(self_play_df)
    print(f"Combined dataset features: {df_combined.columns.tolist()}")

    # Debugging Combined Dataset
    print("Combined Dataset Columns:")
    print(df_combined.columns.tolist())

    # Update Environment with Combined Data
    env = DummyVecEnv([lambda: TradingEnv(df_combined)])
    
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

def monitor_performance(trades):
    """
    Monitor trading performance based on trade history.
    trades: List of dictionaries containing trade details (e.g., profit, loss, etc.)
    """
    import matplotlib.pyplot as plt
    import numpy as np

    # Extract profits from trades
    profits = [trade['profit'] for trade in trades]
    cumulative_profits = np.cumsum(profits)

    # Calculate win rate
    wins = sum(1 for profit in profits if profit > 0)
    total_trades = len(profits)
    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0

    # Plot cumulative profits
    plt.figure(figsize=(10, 6))
    plt.plot(cumulative_profits, label='Cumulative Profit')
    plt.title('Trading Performance')
    plt.xlabel('Trade Number')
    plt.ylabel('Cumulative Profit')
    plt.legend()
    plt.grid()
    plt.show()

    print(f"Total Trades: {total_trades}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Final Profit: {cumulative_profits[-1] if total_trades > 0 else 0:.2f}")

# Example usage
if __name__ == "__main__":
    train()
    # Example trade history
    example_trades = [
        {'profit': 100},
        {'profit': -50},
        {'profit': 200},
        {'profit': -30},
        {'profit': 150},
    ]
    monitor_performance(example_trades)
