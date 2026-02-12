import time
import threading
import datetime
from src.data.fetcher import BinanceDataFetcher
from src.data.storage import MongoStorage

class DataCollector:
    def __init__(self, symbol='BTC/USDT'):
        self.symbol = symbol
        # Use Production API for data collection even if trading on Testnet
        self.fetcher = BinanceDataFetcher(symbol=symbol, use_keys=True, force_production=True)
        self.storage = MongoStorage()
        self.running = False
        self.thread = None

    def start(self):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print(f"[Collector] Started data collection for {self.symbol}")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        print("[Collector] Stopped data collection")

    def _run_loop(self):
        while self.running:
            try:
                # 1. Fetch Data
                # Get latest 1m candle
                df_1m = self.fetcher.fetch_ohlcv(timeframe='1m', limit=2) # Get last 2 to ensure we have the closed one or latest
                if df_1m.empty:
                    time.sleep(10)
                    continue

                latest_candle = df_1m.iloc[-1]
                timestamp = latest_candle.name.to_pydatetime()
                
                # Fetch Advanced Data
                funding_rate = self.fetcher.fetch_funding_rate()
                open_interest = self.fetcher.fetch_open_interest()
                imbalance = self.fetcher.fetch_order_book_imbalance()

                # 2. Construct Data Point
                data_point = {
                    'timestamp': timestamp,
                    'symbol': self.symbol,
                    'open': float(latest_candle['open']),
                    'high': float(latest_candle['high']),
                    'low': float(latest_candle['low']),
                    'close': float(latest_candle['close']),
                    'volume': float(latest_candle['volume']),
                    'funding_rate': float(funding_rate),
                    'open_interest': float(open_interest),
                    'order_book_imbalance': float(imbalance),
                    'collected_at': datetime.datetime.utcnow()
                }

                # 3. Save to Storage
                self.storage.save_market_data(data_point)
                
                # print(f"[Collector] Saved data: {data_point['close']} | FR: {funding_rate} | OI: {open_interest}")

                # Wait for next minute (align to minute boundary roughly)
                # Simple sleep 60s for now, can be improved to sync with clock
                time.sleep(60)

            except Exception as e:
                print(f"[Collector] Error: {e}")
                time.sleep(10)

if __name__ == "__main__":
    collector = DataCollector()
    collector.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        collector.stop()
