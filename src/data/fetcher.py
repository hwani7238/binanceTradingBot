import ccxt
import pandas as pd
import time
from datetime import datetime

import os
from dotenv import load_dotenv

class BinanceDataFetcher:
    def __init__(self, symbol='BTC/USDT', timeframe='15m', limit=1000, testnet=True, use_keys=True, force_production=False):
        load_dotenv()
        
        config = {
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
            }
        }

        # Note: Do NOT include API keys for the data fetcher.
        # Demo Trading API keys only work on the demo endpoint,
        # not on production api.binance.com.
        # Public data (OHLCV, orderbook) doesn't need authentication.
        
        self.exchange = ccxt.binance(config)
        
        # Note: Binance Futures Sandbox/Testnet is deprecated.
        # For public market data (OHLCV, orderbook), production API works fine.
        # Demo trading mode is only needed for private endpoints (orders, balance).
        print("Using Binance Futures (Production Data)")

        self.symbol = symbol
        self.timeframe = timeframe
        self.limit = limit

    def fetch_ohlcv(self, timeframe=None, limit=None, since=None):
        """
        Fetches historical OHLCV data for a specific timeframe.
        """
        tf = timeframe or self.timeframe
        lim = limit or self.limit
        print(f"Fetching {self.symbol} {tf} data...")
        
        all_ohlcv = []
        if since is None:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, tf, limit=lim)
            all_ohlcv.extend(ohlcv)
        else:
            while True:
                ohlcv = self.exchange.fetch_ohlcv(self.symbol, tf, since=since, limit=lim)
                if not ohlcv: break
                since = ohlcv[-1][0] + 1
                all_ohlcv.extend(ohlcv)
                if len(ohlcv) < lim: break
                time.sleep(self.exchange.rateLimit / 1000)

        df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df

    def fetch_multi_timeframes(self, timeframes=['5m', '15m', '1h'], limit=1000):
        """
        Fetches multiple timeframes and returns a dictionary of DataFrames.
        """
        data = {}
        for tf in timeframes:
            data[tf] = self.fetch_ohlcv(timeframe=tf, limit=limit)
        return data

    def fetch_funding_rate(self):
        try:
            # fetchFundingRate is supported by ccxt for binance
            funding = self.exchange.fetch_funding_rate(self.symbol)
            return funding['fundingRate']
        except Exception as e:
            print(f"Error fetching funding rate: {e}")
            return 0.0

    def fetch_open_interest(self):
        try:
            # fetchOpenInterest is supported by ccxt for binance
            oi = self.exchange.fetch_open_interest(self.symbol)
            return float(oi['openInterestAmount']) # Amount in base currency (BTC)
        except Exception as e:
            print(f"Error fetching open interest: {e}")
            return 0.0

    def fetch_order_book_imbalance(self):
        try:
            # Fetch top 20 bids and asks
            orderbook = self.exchange.fetch_order_book(self.symbol, limit=20)
            bids = orderbook['bids']
            asks = orderbook['asks']
            
            total_bid_qty = sum([b[1] for b in bids])
            total_ask_qty = sum([a[1] for a in asks])
            
            if (total_bid_qty + total_ask_qty) == 0: return 0.0
            
            # Ratio: (Bid - Ask) / (Bid + Ask) -> Range [-1, 1]
            imbalance = (total_bid_qty - total_ask_qty) / (total_bid_qty + total_ask_qty)
            return imbalance
        except Exception as e:
            print(f"Error fetching order book: {e}")
            return 0.0

if __name__ == "__main__":
    fetcher = BinanceDataFetcher()
    df = fetcher.fetch_ohlcv()
    print(df.tail())
    df.to_csv("data.csv")
