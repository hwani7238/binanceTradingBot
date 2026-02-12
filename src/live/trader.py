"""
Live Trading Module - Executes real orders on Binance Futures (Testnet or Live).
Replaces PaperTradingSession when LIVETRADING=True.
"""
import os
import time
import ccxt
from dotenv import load_dotenv

load_dotenv()

COMMISSION_RATE = 0.0005
MAX_LEVERAGE = 20


class LiveTradingSession:
    def __init__(self, symbol='BTC/USDT', max_leverage=20):
        self.symbol = symbol
        self.max_leverage = max_leverage
        
        # Exchange Setup
        use_testnet = os.getenv('USE_TESTNET', 'True').lower() == 'true'
        
        config = {
            'apiKey': os.getenv('BINANCE_API_KEY'),
            'secret': os.getenv('BINANCE_SECRET_KEY'),
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'recvWindow': 60000
            }
        }
        
        self.exchange = ccxt.binance(config)
        
        if use_testnet:
            self.exchange.enable_demo_trading(True)
            print("[LIVE] Connected to Binance Futures DEMO TRADING")
        else:
            print("[LIVE] Connected to Binance Futures LIVE")
        
        # Set initial leverage on exchange
        try:
            # Use standard CCXT method
            self.exchange.set_leverage(int(max_leverage), symbol)
            # self.exchange.fapiPrivate_post_leverage({
            #     'symbol': symbol.replace('/', ''),
            #     'leverage': max_leverage
            # })
            print(f"[LIVE] Max leverage set to {max_leverage}x")
        except Exception as e:
            print(f"[LIVE] Warning: Could not set leverage: {e}")
        
        # Track state
        self.initial_balance = self._fetch_balance()
        self.realized_pnl = 0.0
        self.total_fees = 0.0
        self.total_fees = 0.0
        self.history_file = "live_trades.json"
        
        # Load history
        self.history = self._load_history()
        
        print(f"[LIVE] Initial balance: ${self.initial_balance:,.2f}")
        
        # Check for low balance
        if self.initial_balance < 20.0:
            print(f"[LIVE] ⚠️ 경고: 현재 잔고(${self.initial_balance:,.2f})가 매우 부족합니다!")
            print(f"[LIVE] 최소 주문 금액($100 이상)을 충족하지 못해 포지션 진입이 불가능할 수 있습니다.")
            if use_testnet:
                print(f"[LIVE] 💡 다음 링크에서 테스트넷 자금을 충전해주세요: https://testnet.binancefuture.com/en/futures/delivery/BTCUSDT (Faucet)")

    
    def _load_history(self):
        import json
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[LIVE] Failed to load history: {e}")
                return []
        return []

    def _save_history(self):
        import json
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=4)
        except Exception as e:
            print(f"[LIVE] Failed to save history: {e}")
    
    def _fetch_balance(self):
        """Fetch USDT balance from exchange."""
        try:
            balance = self.exchange.fetch_balance()
            # For futures, use 'total' USDT
            usdt = balance.get('USDT', {})
            return float(usdt.get('total', 0))
        except Exception as e:
            print(f"[LIVE] Error fetching balance: {e}")
            return 0.0
    
    def _fetch_position(self):
        """Fetch current position from exchange."""
        try:
            positions = self.exchange.fetch_positions([self.symbol])
            print(f"[DEBUG] Fetching positions for {self.symbol}...")
            for pos in positions:
                # CCXT can return 'BTCUSDT', 'BTC/USDT', or 'BTC/USDT:USDT'
                s = pos['symbol']
                target = self.symbol # 'BTC/USDT'
                target_alt = self.symbol.replace('/', '') # 'BTCUSDT'
                
                print(f"[DEBUG] Checking pos symbol: '{s}' vs target '{target}' or '{target_alt}'")
                
                # Check for match (including valid ccxt formats)
                if s == target or s == target_alt or target in s or target_alt in s:
                    print(f"[DEBUG] MATCH FOUND for {s}!")
                    side = pos.get('side', 'none')
                    contracts = float(pos.get('contracts', 0) or 0)
                    notional = float(pos.get('notional', 0) or 0)
                    entry_price = float(pos.get('entryPrice', 0) or 0)
                    unrealized_pnl = float(pos.get('unrealizedPnl', 0) or 0)
                    leverage = float(pos.get('leverage', 0) or 0)
                    
                    # Calculate signed quantity
                    quantity = contracts if side == 'long' else -contracts if side == 'short' else 0
                    
                    return {
                        'side': side,
                        'quantity': quantity,
                        'contracts': contracts,
                        'notional': notional,
                        'entry_price': entry_price,
                        'unrealized_pnl': unrealized_pnl,
                        'leverage': leverage
                    }
            return {
                'side': 'none', 'quantity': 0, 'contracts': 0,
                'notional': 0, 'entry_price': 0, 'unrealized_pnl': 0, 'leverage': 0
            }
        except Exception as e:
            print(f"[LIVE] Error fetching position: {e}")
            return {
                'side': 'none', 'quantity': 0, 'contracts': 0,
                'notional': 0, 'entry_price': 0, 'unrealized_pnl': 0, 'leverage': 0
            }
    
    def _fetch_price(self):
        """Fetch current market price."""
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            return float(ticker['last'])
        except Exception as e:
            print(f"[LIVE] Error fetching price: {e}")
            return 0.0

    @property
    def net_worth(self):
        return self._fetch_balance()
    
    @property
    def current_leverage(self):
        pos = self._fetch_position()
        balance = self._fetch_balance()
        if balance > 0 and pos['notional'] != 0:
            return pos['notional'] / balance
        return 0.0
    
    @property 
    def held_quantity(self):
        pos = self._fetch_position()
        return pos['quantity']
    
    @property
    def entry_price(self):
        pos = self._fetch_position()
        return pos['entry_price']
    
    def get_unrealized_pnl(self, current_price=None):
        """Get unrealized PnL from exchange."""
        pos = self._fetch_position()
        return pos['unrealized_pnl']
    
    def get_win_rate(self):
        if not self.history:
            return 0.0
        wins = sum(1 for trade in self.history if trade['realized_pnl'] > 0)
        total = len(self.history)
        return (wins / total) * 100.0

    def execute_target_leverage(self, target_leverage, current_price, symbol):
        """
        Execute trades on the exchange to match target leverage.
        target_leverage: float between -MAX_LEV and +MAX_LEV
        """
        try:
            # 1. Get current state from exchange
            pos = self._fetch_position()
            balance = self._fetch_balance()
            
            if balance <= 0:
                print("[LIVE] No balance available!")
                return "NO BALANCE"
            
            # 2. Calculate target position
            # Add Safety Margin to avoid "Margin is insufficient"
            # If we go for max leverage, we need room for fees and price moves
            SAFETY_MARGIN = 0.98 
            target_notional = balance * target_leverage * SAFETY_MARGIN
            current_notional = pos['notional']
            
            # Ensure correct sign for current_notional
            if pos['side'] == 'short':
                current_notional = -abs(current_notional)
            elif pos['side'] == 'long':
                current_notional = abs(current_notional)
            else:
                current_notional = 0
            
            trade_notional = target_notional - current_notional
            
            # 3. Determine if this is a position-reducing trade
            is_reducing = (pos['side'] == 'long' and trade_notional < 0) or \
                          (pos['side'] == 'short' and trade_notional > 0)
            
            # 4. Skip dust trades (Binance Futures min notional = $100 for new orders)
            MIN_NOTIONAL = 110.0  # Increased buffer for safety (Binance min is $100)
            MIN_DUST = 5.0        # Minimum for reduce-only orders
            
            # --- AUTO-SCALE LEVERAGE LOGIC ---
            # If opening/increasing position and trade size is too small, try to scale up
            if not is_reducing and abs(trade_notional) < MIN_NOTIONAL:
                # Check if we can scale up to MIN_NOTIONAL within MAX_LEVERAGE
                # We need trade_notional to be at least MIN_NOTIONAL
                # This implies using more leverage.
                
                # Check max possible trade size at max leverage
                max_possible_notional = balance * self.max_leverage * SAFETY_MARGIN
                
                # We need to see if we can afford the MIN_NOTIONAL trade
                if max_possible_notional >= MIN_NOTIONAL:
                    print(f"[LIVE] Auto-scaling trade from ${abs(trade_notional):.2f} to ${MIN_NOTIONAL:.2f} using higher leverage")
                    if trade_notional > 0:
                        trade_notional = MIN_NOTIONAL
                    else:
                        trade_notional = -MIN_NOTIONAL
                else:
                    print(f"[LIVE] Skipping: Balance ${balance:.2f} too low to meet ${MIN_NOTIONAL} min trade (Max possible: ${max_possible_notional:.2f})")
                    return f"HOLD (Low Bal)"

            if is_reducing:
                if abs(trade_notional) < MIN_DUST:
                    print(f"[LIVE] Skipping tiny reduce: ${trade_notional:.2f}")
                    return f"HOLD ({target_leverage:.2f}x)"
            else:
                if abs(trade_notional) < MIN_NOTIONAL:
                    print(f"[LIVE] Skipping sub-minimum trade: ${trade_notional:.2f} (min: ${MIN_NOTIONAL})")
                    return f"HOLD ({target_leverage:.2f}x)"
            
            # 5. Calculate quantity to trade
            trade_qty = abs(trade_notional) / current_price
            
            # Round to exchange precision
            trade_qty = float(self.exchange.amount_to_precision(self.symbol, trade_qty))
            
            # --- POST-ROUNDING VALIDATION & CORRECTION ---
            effective_value = trade_qty * current_price
            
            # If rounding pushed us below $100, but we want to trade, try to bump up
            if not is_reducing and effective_value < 100.0:
                 print(f"[LIVE] Effective value ${effective_value:.2f} < $100. Attempting to bump quantity...")
                 
                 # Try increasing by small increments until > 100 or max leverage exceeded
                 # Use a heuristic step size. For BTC (price ~60k), 0.001 is common. 
                 # We can try adding 10% of current qty or estimates.
                 # Better: calculate exact needed
                 needed_qty = 100.0 / current_price
                 # Add 1% buffer
                 needed_qty = needed_qty * 1.01
                 
                 new_qty = float(self.exchange.amount_to_precision(self.symbol, needed_qty))
                 
                 # Get Precision Step
                 try:
                     market = self.exchange.market(self.symbol)
                     step_size = float(market['precision']['amount'])
                 except:
                     step_size = 0.001 # Default fallback for BTC
                 
                 if new_qty <= trade_qty or (new_qty * current_price < 100.0):
                      # If rounding brings it back down/same OR it's still < 100, manually add a step
                      print(f"[LIVE] Bump ineffective (qty={new_qty}, val=${new_qty*current_price:.2f}). Adding step {step_size}...")
                      new_qty = trade_qty + step_size
                      # Re-round to be safe
                      new_qty = float(self.exchange.amount_to_precision(self.symbol, new_qty))
                      
                 new_val = new_qty * current_price
                 
                 # Check if we can afford this new quantity
                 max_leverage_cap = (balance * MAX_LEVERAGE * 0.99) # 20x capacity
                 if new_val <= max_leverage_cap:
                     print(f"[LIVE] Bumped quantity to {new_qty} (${new_val:.2f}). Within limit (${max_leverage_cap:.2f}).")
                     trade_qty = new_qty
                     effective_value = new_val
                 else:
                     print(f"[LIVE] Cannot bump to {new_qty} (${new_val:.2f}). Exceeds max leverage cap (${max_leverage_cap:.2f}).")
                     return f"HOLD (Bal Limit)"

            if not is_reducing and effective_value < 100.0:
                 print(f"[LIVE] Skipping: Effective value ${effective_value:.2f} < $100 after correction.")
                 return f"HOLD (Round Fail)"

            if trade_qty <= 0:
                print("[LIVE] Trade quantity too small after rounding")
                return f"HOLD ({target_leverage:.2f}x)"
            
            # 6. Determine order side
            if trade_notional > 0:
                side = 'buy'
            else:
                side = 'sell'
            
            # 7. Execute market order
            reduce_only = is_reducing
            print(f"[LIVE] Placing {side.upper()} market order: {trade_qty} {symbol} (reduceOnly={reduce_only})")
            
            order = self.exchange.create_market_order(
                symbol=self.symbol,
                side=side,
                amount=trade_qty,
                params={'reduceOnly': reduce_only}
            )
            
            # 8. Get order result
            order_id = order.get('id', 'unknown')
            filled_qty = float(order.get('filled', trade_qty))
            avg_price = float(order.get('average', current_price) or current_price)
            fee_cost = 0.0
            
            if order.get('fees'):
                fee_cost = sum(float(f.get('cost', 0)) for f in order['fees'])
            elif order.get('fee'):
                fee_cost = float(order['fee'].get('cost', 0))
            
            if fee_cost == 0:
                fee_cost = abs(trade_notional) * COMMISSION_RATE
            
            self.total_fees += fee_cost
            
            # 9. Calculate realized PnL (from exchange position change)
            step_realized_pnl = 0.0
            
            if is_reducing and pos['entry_price'] > 0:
                closed_qty = min(filled_qty, pos['contracts'])
                if pos['side'] == 'long':
                    step_realized_pnl = (avg_price - pos['entry_price']) * closed_qty
                else:
                    step_realized_pnl = (pos['entry_price'] - avg_price) * closed_qty
                self.realized_pnl += step_realized_pnl
            
            # 10. Get updated position
            time.sleep(0.5)  # Small delay for exchange to update
            new_pos = self._fetch_position()
            new_balance = self._fetch_balance()
            new_leverage = new_pos['notional'] / new_balance if new_balance > 0 else 0
            
            if new_pos['side'] == 'short':
                new_leverage = -new_leverage
            
            # 11. Determine position type
            if abs(new_leverage) < 0.1:
                position_type = "CLOSE"
            elif new_leverage > 0:
                position_type = "LONG"
            else:
                position_type = "SHORT"
            
            unrealized = new_pos['unrealized_pnl']
            
            print(f"[LIVE] Order filled: {side.upper()} {filled_qty} @ ${avg_price:,.2f} | "
                  f"Fee: ${fee_cost:.2f} | Realized: ${step_realized_pnl:.2f} | "
                  f"Position: {position_type} {abs(new_leverage):.2f}x")
            
            self.history.append({
                'timestamp': time.strftime('%H:%M:%S'),
                'type': position_type,
                'price': avg_price,
                'amount': filled_qty,
                'realized_pnl': round(step_realized_pnl, 2),
                'unrealized_pnl': round(unrealized, 2),
                'fee': round(fee_cost, 2),
                'net_worth': round(new_balance, 2),
                'leverage': round(new_leverage, 2)
            })
            self._save_history()
            
            return f"{position_type} {abs(new_leverage):.1f}x"
            
        except Exception as e:
            # Retry logic for Insufficient Margin
            if "Margin is insufficient" in str(e) or "InsufficientFunds" in str(e):
                print("[LIVE] Margin insufficient. Retrying with 95% size...")
                try:
                    retry_qty = float(self.exchange.amount_to_precision(self.symbol, trade_qty * 0.95))
                    print(f"[LIVE] Retrying {side.upper()} {retry_qty} {symbol}")
                    self.exchange.create_market_order(self.symbol, side, retry_qty)
                    return f"RETRY {side} OK"
                except Exception as retry_e:
                    print(f"[LIVE] Retry failed: {retry_e}")
                    return f"RETRY FAIL: {str(retry_e)[:50]}"

            import traceback
            print(f"[LIVE] ORDER ERROR: {e}")
            traceback.print_exc()
            return f"ERROR: {str(e)[:50]}"
