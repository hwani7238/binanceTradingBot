from src.data.storage import MongoStorage
import pandas as pd

def check_data():
    storage = MongoStorage()
    data = storage.get_latest_data(limit=5)
    
    if not data:
        print("No data found in MongoDB yet.")
        return

    df = pd.DataFrame(data)
    # Reorder columns for readability
    cols = ['timestamp', 'close', 'volume', 'funding_rate', 'open_interest', 'order_book_imbalance']
    # Filter only existing cols
    cols = [c for c in cols if c in df.columns]
    
    print(f"Found {len(data)} recent records:")
    print(df[cols].to_string(index=False))

if __name__ == "__main__":
    check_data()
