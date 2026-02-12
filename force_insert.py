from src.data.storage import MongoStorage
import datetime

def force_insert():
    print("Testing MongoDB Write...")
    storage = MongoStorage()
    
    data = {
        'timestamp': datetime.datetime.utcnow(),
        'symbol': 'TEST_INSERT',
        'price': 100.0,
        'note': 'Forced insertion test'
    }
    
    try:
        storage.save_market_data(data)
        print("Successfully sent insert command.")
        
        # Immediate verification
        latest = storage.get_latest_data(limit=1)
        print(f"Read back latest data: {latest}")
    except Exception as e:
        print(f"Insert failed: {e}")

if __name__ == "__main__":
    force_insert()
