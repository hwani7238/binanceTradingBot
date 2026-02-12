
import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv('BINANCE_API_KEY')
secret = os.getenv('BINANCE_SECRET_KEY')

print(f"Key: {key[:5]}...")

# Use binanceusdm which is specialized for USDT futures
exchange = ccxt.binanceusdm({
    'apiKey': key,
    'secret': secret,
})

try:
    print("Connecting to Testnet (Manual Overrides)...")
    # Manual URL override for Legacy Testnet
    exchange.urls['api']['public'] = 'https://testnet.binancefuture.com/fapi/v1'
    exchange.urls['api']['private'] = 'https://testnet.binancefuture.com/fapi/v1'
    exchange.urls['api']['fapiPublic'] = 'https://testnet.binancefuture.com/fapi/v1'
    exchange.urls['api']['fapiPrivate'] = 'https://testnet.binancefuture.com/fapi/v1'

    print("Checking Balance...")
    balance = exchange.fetch_balance()
    usdt = balance['USDT']['total']
    print(f"USDT Balance: {usdt}")

    print("Checking Market Limits...")
    market = exchange.load_markets()['BTC/USDT']
    print(f"Min Amount: {market['limits']['amount']['min']}")
    print(f"Min Cost: {market['limits']['cost']['min']}")
    
    print("Checking Current Price...")
    ticker = exchange.fetch_ticker('BTC/USDT')
    print(f"Price: {ticker['last']}")
    
    print("Connection Successful!")

except Exception as e:
    print(f"ERROR: {e}")
