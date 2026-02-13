import time
import os
import threading
import subprocess
import sys
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import ccxt
from stable_baselines3 import PPO

from src.data.fetcher import BinanceDataFetcher
from src.data.processor import DataProcessor
from src.data.collector import DataCollector

# Load Environment Variables
load_dotenv()

from src.live.trader import LiveTradingSession

# Configuration
SYMBOL = os.getenv('SYMBOL', 'BTC/USDT')
TIMEFRAME = os.getenv('TIMEFRAME', '5m')
USE_TESTNET = os.getenv('USE_TESTNET', 'True').lower() == 'true'
LIVETRADING = os.getenv('LIVETRADING', 'False').lower() == 'true'
MODEL_PATH = "models/ppo_trading_bot"
LOOKBACK_WINDOW = 50
MAX_LEVERAGE = 20.0
COMMISSION_RATE = 0.0005
RETRAIN_INTERVAL = 2 * 60 * 60 # 2 Hours

class PaperTradingSession:
    def __init__(self, initial_balance=10000.0):
        self.initial_balance = initial_balance
        self.balance = initial_balance # Cash Balance (minus fees)
        self.net_worth = initial_balance # Equity
        self.held_quantity = 0.0
        self.entry_price = 0.0
        self.current_leverage = 0.0
        self.realized_pnl = 0.0   # Cumulative realized PnL
        self.total_fees = 0.0     # Cumulative fees paid
        self.history_file = "paper_trades.json"
        self.history = self._load_history()

    def _load_history(self):
        import json
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Failed to load history: {e}")
                return []
        return []

    def _save_history(self):
        import json
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=4)
        except Exception as e:
            print(f"Failed to save history: {e}")

    def execute_target_leverage(self, target_leverage, current_price, symbol):
        """
        Adjust position to match target leverage.
        target_leverage: float between -20 and +20
        """
        # Calculate Net Worth first
        self._update_net_worth(current_price)
        
        # 1. Calculate Target Position Value
        # Value = NetWorth * Leverage
        target_position_value = self.net_worth * target_leverage
        
        # 2. Calculate Current Position Value
        current_position_value = self.held_quantity * current_price
        
        # 3. Calculate Trade Value needed
        trade_value = target_position_value - current_position_value
        
        # Avoid dust trades (e.g. less than $10 change as requested)
        if abs(trade_value) < 10.0:
            print(f"Skipping small trade: ${trade_value:.2f} (Minimum $10 required)")
            return f"HOLD (Target {target_leverage:.2f}x)"
            
        # 4. Calculate Fees
        fee = abs(trade_value) * COMMISSION_RATE
        self.balance -= fee
        self.total_fees += fee
        
        # 5. Calculate Realized PnL for the closed portion
        trade_quantity = trade_value / current_price
        step_realized_pnl = 0.0
        
        # Realized PnL occurs when reducing position (opposite direction trade)
        is_reducing = (self.held_quantity > 0 and trade_quantity < 0) or \
                      (self.held_quantity < 0 and trade_quantity > 0)
        
        if is_reducing and self.entry_price > 0:
            # How much of the position is being closed
            closed_qty = min(abs(trade_quantity), abs(self.held_quantity))
            if self.held_quantity > 0:  # Was long, selling some
                step_realized_pnl = (current_price - self.entry_price) * closed_qty
            else:  # Was short, buying some
                step_realized_pnl = (self.entry_price - current_price) * closed_qty
            self.realized_pnl += step_realized_pnl
        
        # 6. Update Entry Price
        old_quantity = self.held_quantity
        if (self.held_quantity > 0 and trade_quantity > 0) or (self.held_quantity < 0 and trade_quantity < 0):
             # Adding to position - weighted average
             total_qty = self.held_quantity + trade_quantity
             total_val = (self.held_quantity * self.entry_price) + (trade_quantity * current_price)
             self.entry_price = abs(total_val / total_qty)
        elif self.held_quantity == 0 and trade_quantity != 0:
             # New position
             self.entry_price = current_price
        
        self.held_quantity += trade_quantity
        
        # If position flipped direction, reset entry price
        if (old_quantity > 0 and self.held_quantity < 0) or (old_quantity < 0 and self.held_quantity > 0):
            self.entry_price = current_price
        
        # If position fully closed, reset entry
        if abs(self.held_quantity) < 1e-10:
            self.held_quantity = 0.0
            self.entry_price = 0.0
        
        self._update_net_worth(current_price)
        
        # Determine position type
        if abs(self.current_leverage) < 0.1:
            position_type = "CLOSE"
        elif self.current_leverage > 0:
            position_type = "LONG"
        else:
            position_type = "SHORT"
        
        # Calculate current unrealized PnL
        unrealized = self.get_unrealized_pnl(current_price)
        
        print(f"Trade: {position_type} {abs(self.current_leverage):.2f}x | Fee: {fee:.2f} | Realized: {step_realized_pnl:.2f} | Unrealized: {unrealized:.2f} | Price: {current_price:.2f}")
        
        self.history.append({
            'timestamp': time.strftime('%H:%M:%S'),
            'type': position_type,
            'price': current_price,
            'amount': abs(trade_quantity),
            'realized_pnl': round(step_realized_pnl, 2),
            'unrealized_pnl': round(unrealized, 2),
            'fee': round(fee, 2),
            'net_worth': round(self.net_worth, 2),
            'leverage': round(self.current_leverage, 2)
        })
        self._save_history()
        
        return f"{position_type} {abs(self.current_leverage):.1f}x"

    def _update_net_worth(self, current_price):
        # Position Value
        # PnL
        pnl = 0
        if self.held_quantity != 0:
            if self.held_quantity > 0:
                pnl = (current_price - self.entry_price) * self.held_quantity
            else:
                pnl = (self.entry_price - current_price) * abs(self.held_quantity)
                
        # Net Worth = Balance (which tracks Cash - Realized Fees) + Unrealized PnL? 
        # Wait, strictly speaking:
        # Net Worth = Cash + Margin Balance + Unrealized PnL
        # In our simplified model:
        # We started with Cash. Fees reduce Cash. PnL adds to Net Worth.
        # Let's trust the logic: Net Worth = Initial + Realized PnL + Unrealized PnL - Fees
        # Or easier: Net Worth = Current Cash Equivalent of everything.
        
        # Let's stick to the Env logic which tracks Net Worth directly.
        # But here we need to be careful about 'balance'.
        # Let's simplify: Balance is just a tracker for Fees processing.
        # Real Metric is Net Worth.
        
        total_asset_value = self.balance # This balance has fees deducted
        # Add PnL from *current open position* (compared to entry)
        # BUT 'balance' assumes we bought the asset?
        # NO, this is futures. We have Margin.
        # Balance = Margin Balance.
        
        # Let's reset:
        # Net Worth = Balance + Unrealized PnL
        self.net_worth = self.balance + pnl
        
        if self.net_worth > 0:
            self.current_leverage = (self.held_quantity * current_price) / self.net_worth
        else:
            self.current_leverage = 0
            
        return self.net_worth

    def get_unrealized_pnl(self, current_price):
        """Calculate unrealized PnL on the current open position."""
        if self.held_quantity == 0 or self.entry_price == 0:
            return 0.0
        if self.held_quantity > 0:
            return (current_price - self.entry_price) * self.held_quantity
        else:
            return (self.entry_price - current_price) * abs(self.held_quantity)

    def get_win_rate(self):
        if not self.history:
            return 0.0
        
        wins = sum(1 for trade in self.history if trade['realized_pnl'] > 0)
        total = len(self.history)
        return (wins / total) * 100.0

class TradingBot:
    def __init__(self):
        self.running = False
        self.thread = None
        
        if LIVETRADING:
            print("🚀 INITIALIZING LIVE TRADING SESSION")
            self.paper_session = LiveTradingSession(symbol=SYMBOL, max_leverage=MAX_LEVERAGE)
        else:
            print("📝 Initializing Paper Trading Session")
            self.paper_session = PaperTradingSession(initial_balance=10000.0)
            
        self.fetcher = BinanceDataFetcher(symbol=SYMBOL, timeframe=TIMEFRAME, limit=100, testnet=USE_TESTNET, use_keys=True) # Enable keys for advanced data
        self.processor = DataProcessor(pd.DataFrame())
        
        # Data Collector (Background Service)
        self.collector = DataCollector(symbol=SYMBOL)
        
        # GUI State
        self.current_price = 0.0
        self.current_action = "STOPPED"
        self.current_action = "STOPPED"
        self.last_update_time = "N/A"
        self.last_retrain_time = time.time()
        
        # Load Model
        if os.path.exists(MODEL_PATH + ".zip"):
            self.model = PPO.load(MODEL_PATH)
            self.model_timestamp = os.path.getmtime(MODEL_PATH + ".zip")
            print(f"Model loaded successfully (Timestamp: {self.model_timestamp})")
        else:
            self.model = None
            self.model_timestamp = 0
            print(f"Model not found at {MODEL_PATH}")
            
        self.retrain_process = None # Track background training process

    def start(self):
        if self.running: return
        self.running = True
        
        # Start Collector
        self.collector.start()
        
        # Start Self-Play Training
        self.self_play_process = subprocess.Popen([sys.executable, "src/agent/train.py"])
        print(f"✅ Self-Play training started (PID: {self.self_play_process.pid}).")
        
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print("Bot started.")

    def stop(self):
        self.running = False
        
        # Stop Collector
        self.collector.stop()
        
        print("Bot stop signal sent.")
        self.current_action = "STOPPED"

    def get_status(self):
        """Returns a dict of current status for UI"""
        unrealized = self.paper_session.get_unrealized_pnl(self.current_price) if self.current_price > 0 else 0.0
        
        # Check if training
        is_training = self.retrain_process is not None and self.retrain_process.poll() is None
        
        return {
            'running': self.running,
            'price': self.current_price,
            'balance': self.paper_session.net_worth,
            'position': self.paper_session.current_leverage,
            'realized_pnl': self.paper_session.realized_pnl,
            'unrealized_pnl': unrealized,
            'total_fees': self.paper_session.total_fees,
            'action': "TRAINING..." if is_training else self.current_action,
            'last_update': self.last_update_time,
            'next_retrain': "ON EXIT"
        }

    def _get_latest_observation(self, lookback=50):
        # 1. Fetch Multi-Timeframe Data
        # We fetch a bit more for other TFs to ensure alignment
        df_5m = self.fetcher.fetch_ohlcv(timeframe='5m', limit=200)
        others = {
            '15m': self.fetcher.fetch_ohlcv(timeframe='15m', limit=100),
            '1h': self.fetcher.fetch_ohlcv(timeframe='1h', limit=50),
            '1m': self.fetcher.fetch_ohlcv(timeframe='1m', limit=1000)
        }
        
        # 2. Process and Merge
        self.processor = DataProcessor(df_5m)
        df_base = self.processor.add_technical_indicators()
        df_base = self.processor.normalize_features() # Apply Normalization to match training
        
        df_merged = DataProcessor.merge_timeframes(df_base, others)
        
        if len(df_merged) < lookback: 
            print(f"Warning: Not enough data points ({len(df_merged)} < {lookback})")
            return None
            
        frame = df_merged.iloc[-lookback:]
        # Save raw close price BEFORE selecting normalized features
        self.current_price = frame.iloc[-1]['close'] # Raw price for trading logic
        
        # 3. Construct Observation - MUST match TradingEnv._next_observation() exactly
        # TradingEnv uses exactly these 7 + 5 feature columns (total 14 with state)
        feature_cols = [
            'close_pct', 'high_pct', 'low_pct', 'volume_pct', 'rsi', 'macd', 'bb_position',
            'close_pct_1m', 'volume_pct_1m', 'rsi_1m', 'macd_1m', 'bb_position_1m'
        ]
        # print(f"DEBUG: feature_cols length: {len(feature_cols)}")
        # print(f"DEBUG: feature_cols: {feature_cols}")
        obs_data = frame[feature_cols].values
        
        # State Features
        unrealized_pnl_ratio = 0.0
        if self.paper_session.held_quantity != 0:
            if self.paper_session.held_quantity > 0:
                pnl = (self.current_price - self.paper_session.entry_price) * self.paper_session.held_quantity
            else:
                pnl = (self.paper_session.entry_price - self.current_price) * abs(self.paper_session.held_quantity)
            if self.paper_session.net_worth > 0:
                unrealized_pnl_ratio = pnl / self.paper_session.net_worth
        
        current_lev_norm = self.paper_session.current_leverage / MAX_LEVERAGE
        
        lev_array = np.full((lookback, 1), current_lev_norm)
        pnl_array = np.full((lookback, 1), unrealized_pnl_ratio)
        
        # Stack: [7 features] + [leverage] + [pnl] = 9 features
        obs = np.hstack((obs_data, lev_array, pnl_array))
        
        # Replace NaN with 0 (same as TradingEnv)
        obs = np.nan_to_num(obs)
                
        return obs.astype(np.float32)

    def _check_and_reload_model(self):
        try:
            path = MODEL_PATH + ".zip"
            if os.path.exists(path):
                mod_time = os.path.getmtime(path)
                if mod_time > self.model_timestamp:
                    print(f"🔄 Model file changed. Reloading from {path}...")
                    self.model = PPO.load(MODEL_PATH)
                    self.model_timestamp = mod_time
                    print("✅ Model hot-reloaded successfully.")
        except Exception as e:
            print(f"⚠️ Failed to reload model: {e}")

    def _trigger_retrain(self):
        """Starts the retraining process in background"""
        if self.retrain_process and self.retrain_process.poll() is None:
            print("⚠️ Retraining already in progress.")
            return

        print("🚀 Triggering Event-Based Retraining...")
        try:
            self.retrain_process = subprocess.Popen([sys.executable, "src/agent/retrainer.py"])
            print(f"✅ Background retraining started (PID: {self.retrain_process.pid}).")
        except Exception as e:
            print(f"❌ Failed to start retraining: {e}")

    def _run_loop(self):
        # Action Smoothing State
        ema_leverage = self.paper_session.current_leverage
        alpha = 0.3 # Smoothing factor (0 to 1)
        
        while self.running:
            try:
                # 1. Blocking Check: Pause if training
                if self.retrain_process:
                    if self.retrain_process.poll() is None:
                        # process is still running
                        self.current_action = "TRAINING..."
                        print(f"⏳ Training in progress... Trading Paused. (PID: {self.retrain_process.pid})")
                        time.sleep(10)
                        continue
                    else:
                        # process finished
                        print("✅ Training process finished.")
                        self.retrain_process = None
                        # proceeding to reload model below

                self.last_update_time = time.strftime('%H:%M:%S')
                print(f"--- Cycle at {self.last_update_time} ---")
                
                # Check for model update
                self._check_and_reload_model()
                # self._check_auto_retrain() # REMOVED: Time-based
                
                obs = self._get_latest_observation(lookback=LOOKBACK_WINDOW)
                
                if obs is not None and self.model:
                    # Predict Continuous Action
                    action, _ = self.model.predict(obs)
                    
                    # action is array [-1, 1]
                    raw_target_leverage = float(action[0]) * MAX_LEVERAGE
                    
                    # Apply Smoothing (EMA)
                    ema_leverage = (alpha * raw_target_leverage) + ((1 - alpha) * ema_leverage)
                    
                    print(f"Price: {self.current_price:.2f} | Raw Target: {raw_target_leverage:.2f}x | Smoothed: {ema_leverage:.2f}x")
                    
                    # Track Previous State
                    prev_qty = self.paper_session.held_quantity

                    # Execute
                    action_msg = self.paper_session.execute_target_leverage(ema_leverage, self.current_price, SYMBOL)
                    self.current_action = action_msg
                    print(f"Action result: {action_msg}")

                    # Track New State
                    curr_qty = self.paper_session.held_quantity

                    # EVENT: Trade Closed (Was holding, now 0)
                    if abs(prev_qty) > 0 and abs(curr_qty) == 0:
                        print("🎉 TRADE CLOSED! Triggering Retraining...")
                        self._trigger_retrain()

                else:
                    print(f"Skipping: obs is {'None' if obs is None else 'OK'}, model is {'None' if self.model is None else 'OK'}")
                
                # Slower cycle: Wait 10 seconds
                for _ in range(10): 
                    if not self.running: break
                    time.sleep(1)
                    
            except Exception as e:
                import traceback
                print(f"ERROR in loop: {e}")
                traceback.print_exc()
                time.sleep(5)

if __name__ == "__main__":
    bot = TradingBot()
    bot.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: bot.stop()
