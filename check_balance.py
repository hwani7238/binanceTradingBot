
import os
import sys
from dotenv import load_dotenv
import ccxt

# Load environment variables
load_dotenv()

def check_balance():
    api_key = os.getenv('BINANCE_API_KEY')
    secret = os.getenv('BINANCE_SECRET_KEY')
    # Force testnet behavior consistent with src/live/trader.py
    use_testnet = os.getenv('USE_TESTNET', 'True').lower() == 'true'

    if not api_key or not secret:
        print("Error: API keys not found in environment variables.")
        return

    try:
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': secret,
            'options': {
                'defaultType': 'future',
            }
        })
        
        # Use the new way to enable testnet/demo if needed
        # In src/live/trader.py we see: self.exchange.enable_demo_trading(True)
        if use_testnet:
             # This method might be specific to recent ccxt versions or a wrapper?
             # Let's try setting the URLs manually if enable_demo_trading doesn't work,
             # or just use set_sandbox_mode which failed.
             # Actually, checking src/live/trader.py:
             # self.exchange.enable_demo_trading(True)
             if hasattr(exchange, 'enable_demo_trading'):
                 exchange.enable_demo_trading(True)
             else:
                 exchange.set_sandbox_mode(True) # Fallback

        print("Connecting...")
        balance = exchange.fetch_balance()
        
        # Debug structure
        # print(list(balance.keys()))
        
        usdt_total = balance['USDT']['total']
        usdt_free = balance['USDT']['free']
        
        print(f"USDT Total Balance: {usdt_total}")
        print(f"USDT Free Balance: {usdt_free}")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    check_balance()
