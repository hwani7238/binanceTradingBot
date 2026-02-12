import os
import pymongo
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
import datetime

class MongoStorage:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoStorage, cls).__new__(cls)
            cls._instance.client = None
            cls._instance.db = None
            cls._instance.collection = None
            cls._instance._connect()
        return cls._instance

    def _connect(self):
        load_dotenv()
        uri = os.getenv("MONGODB_URI")
        if not uri:
            print("[Storage] Warning: MONGODB_URI not found in .env")
            return

        try:
            # Connect with a timeout
            self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            # Trigger a connection verification
            self.client.admin.command('ping')
            
            self.db = self.client.get_database("binance_bot_db")
            self.collection = self.db.get_collection("market_data_1m")
            
            # Create TTL Index (Expire after 1 year = 31536000 seconds)
            self.collection.create_index("timestamp", expireAfterSeconds=31536000)
            print("[Storage] Connected to MongoDB Atlas successfully.")
            
        except ConnectionFailure as e:
            print(f"[Storage] Connection to MongoDB failed: {e}")
            self.client = None

    def save_market_data(self, data: dict):
        """
        Saves a single data point to MongoDB.
        data: dict containing timestamp, price, funding_rate, open_interest, order_book_imbalance, etc.
        """
        if self.collection is None:
            # Try reconnecting if connection was lost or never established
            self._connect()
            if not self.collection:
                return

        try:
            # Ensure timestamp is a datetime object for TTL to work
            if 'timestamp' in data and not isinstance(data['timestamp'], datetime.datetime):
                # If it's a timestamp string or int, convert it? 
                # Usually we expect datetime object.
                pass
            
            self.collection.insert_one(data)
            # print(f"[Storage] Saved data for {data.get('timestamp')}")
        except Exception as e:
            print(f"[Storage] Error saving data: {e}")

    def get_latest_data(self, limit=100):
        if self.collection is None: return []
        return list(self.collection.find().sort("timestamp", -1).limit(limit))
