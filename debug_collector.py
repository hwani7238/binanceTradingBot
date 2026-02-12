from src.data.collector import DataCollector
import time
import logging

# Configure logging to see everything
logging.basicConfig(level=logging.DEBUG)

def test_collector():
    print("Initializing DataCollector...")
    # Initialize with force_production=True (although it's default in the updated class now, being explicit helps)
    collector = DataCollector(symbol='BTC/USDT')
    
    print("Testing Fetcher...")
    try:
        funding = collector.fetcher.fetch_funding_rate()
        print(f"Funding Rate: {funding}")
        
        oi = collector.fetcher.fetch_open_interest()
        print(f"Open Interest: {oi}")
        
        imbalance = collector.fetcher.fetch_order_book_imbalance()
        print(f"Imbalance: {imbalance}")
        
        df = collector.fetcher.fetch_ohlcv(timeframe='1m', limit=2)
        print(f"OHLCV: \n{df}")
        
    except Exception as e:
        print(f"Fetcher failed: {e}")
        return

    print("\nTesting Storage...")
    try:
        # Try saving a dummy point
        import datetime
        data_point = {
            'timestamp': datetime.datetime.utcnow(),
            'symbol': 'DEBUG_TEST',
            'price': 12345.67,
            'note': 'This is a debug test point'
        }
        collector.storage.save_market_data(data_point)
        print("Data saved successfully (check MongoDB 'market_data_1m' collection for DEBUG_TEST symbol)")
    except Exception as e:
        print(f"Storage failed: {e}")

if __name__ == "__main__":
    test_collector()
