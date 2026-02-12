import sys
import time

print("Starting debug check...", flush=True)

try:
    print("1. Testing Imports...", flush=True)
    
    t0 = time.time()
    import numpy
    print(f"   - numpy: OK ({time.time()-t0:.2f}s)", flush=True)
    
    t0 = time.time()
    import pandas
    print(f"   - pandas: OK ({time.time()-t0:.2f}s)", flush=True)
    
    t0 = time.time()
    import torch
    print(f"   - torch: OK ({time.time()-t0:.2f}s)", flush=True)
    
    t0 = time.time()
    import gymnasium
    print(f"   - gymnasium: OK ({time.time()-t0:.2f}s)", flush=True)
    
    t0 = time.time()
    import stable_baselines3
    print(f"   - stable_baselines3: OK ({time.time()-t0:.2f}s)", flush=True)
    
    t0 = time.time()
    import ccxt
    print(f"   - ccxt: OK ({time.time()-t0:.2f}s)", flush=True)
    
    t0 = time.time()
    import matplotlib
    # Force minimal backend to avoid GUI hanging if that's the issue
    matplotlib.use('Agg') 
    import matplotlib.pyplot as plt
    print(f"   - matplotlib: OK ({time.time()-t0:.2f}s)", flush=True)

except Exception as e:
    print(f"\nCRITICAL IMPORT ERROR: {e}")
    sys.exit(1)

print("\n2. Testing Data Fetching (CCXT)...", flush=True)
try:
    exchange = ccxt.binance({'enableRateLimit': True})
    print("   - Exchange initialized", flush=True)
    ticker = exchange.fetch_ticker('BTC/USDT')
    print(f"   - Network Test (BTC/USDT): {ticker['last']}", flush=True)
except Exception as e:
    print(f"   - Network/CCXT Error: {e}")

print("\nDebug check completed.")
