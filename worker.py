# Legacy code removed.
# Active TradeCopier implementation starts below.


import time
import asyncio
import ccxt
import concurrent.futures
import sqlite3
from telegram.constants import ParseMode

# --- Библиотеки ---
# from binance.um_futures import UMFutures
# from binance.error import ClientError

# --- База Данных ---
from database import (
    get_users_for_copytrade,
    get_users_with_api_keys,
    get_user_decrypted_keys, 
    record_trade_entry, 
    get_open_trade, 
    close_trade_in_db, 
    get_referrer_upline,
    credit_referral_tokens,
    deduct_performance_fee,
    set_copytrading_status,
    get_active_exchange_connections,
    execute_write_query,
    DB_NAME,
    get_user_risk_profile
)


import os
from dotenv import load_dotenv
load_dotenv()

class TradeCopier:
    def __init__(self, bot_instance=None):
        self.bot = bot_instance
        self.masters = {}
        self._init_masters()

    def _init_masters(self):
        # 1. Binance (Futures) - DISABLED
        # key_b = os.getenv("BINANCE_MASTER_KEY")
        # sec_b = os.getenv("BINANCE_MASTER_SECRET")
        # if key_b:
        #     self.masters['binance'] = UMFutures(
        #         key=key_b, 
        #         secret=sec_b, 
        #         base_url="https://fapi.binance.com"
        #     )
        #     print("✅ Master [binance] initialized (REAL).")

        # 2. OKX (Spot)
        key_o = os.getenv("OKX_MASTER_KEY")
        sec_o = os.getenv("OKX_MASTER_SECRET")
        pass_o = os.getenv("OKX_MASTER_PASSWORD")
        if key_o:
            try:
                self.masters['okx'] = ccxt.okx({
                    'apiKey': key_o, 'secret': sec_o, 'password': pass_o,
                    'options': {'defaultType': 'spot'}
                })
                print("✅ Master [okx] initialized.")
            except: pass

        # 3. Bybit/BingX (Futures)
        # ONLY BINGX ENABLED
        for name in ['bingx']: # Removed 'bybit'
            key = os.getenv(f"{name.upper()}_MASTER_KEY")
            sec = os.getenv(f"{name.upper()}_MASTER_SECRET")
            if key:
                try:
                    ex_class = getattr(ccxt, name)
                    ex = ex_class({'apiKey': key, 'secret': sec, 'options': {'defaultType': 'future'}})
                    self.masters[name] = ex
                    print(f"✅ Master [{name}] initialized.")
                except: pass

    def _get_master_balance(self, exchange_name):
        try:
            # DISABLED: Binance
            # if exchange_name == 'binance':
            #     acc = self.masters['binance'].account()
            #     for a in acc['assets']:
            #         if a['asset'] == 'USDT': return float(a['walletBalance'])
            if exchange_name == 'okx':
                # Для OKX Spot баланс
                bal = self.masters['okx'].fetch_balance()
                return float(bal['USDT']['free'])
            else:
                master = self.masters.get(exchange_name)
                if master:
                    bal = master.fetch_balance()
                    return float(bal['USDT']['free'])
        except: pass
        return 10000.0

    # --- CONSUMER ---
    def start_consuming(self, queue):
        print("--- [Worker: FINAL HYBRID] Started ---")
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            while True:
                event_data = queue.get()
                if event_data is None: break
                try: self.process_signal(event_data, executor)
                except Exception as e: print(f"❌ Worker Error: {e}")
                finally: queue.task_done()
        print("--- [Worker] Stopped ---")

    def process_signal(self, event_data, executor):
        master_exchange = event_data.get('master_exchange', 'binance')
        strategy = event_data.get('strategy', 'bro-bot') # bro-bot (futures) или cgt (spot)
        master_order_id = event_data.get('master_order_id')  # NEW: Extract master order ID
        
        symbol = event_data.get('s'); side = event_data.get('S')
        order_type = event_data.get('o'); status = event_data.get('X')
        orig_type = event_data.get('ot'); qty = float(event_data.get('q', 0))
        price = float(event_data.get('ap', 0)) or float(event_data.get('p', 0))
        
        # --- ИЗВЛЕКАЕМ ФЛАГ "ТОЛЬКО ВЫХОД" ---
        is_reduce_only = event_data.get('ro', False)

        # --- ЛОГИКА ДЛЯ OKX (SPOT) ---
        if master_exchange == 'okx':
            if status == 'FILLED':
                # MULTI-COIN FILTER: Check if any users have this coin configured
                from database import get_active_coins_for_strategy
                active_coins = get_active_coins_for_strategy('cgt')
                
                if symbol not in active_coins:
                    print(f"⏭ [SKIP] {symbol} - No users configured for this coin")
                    return
                
                master_bal = self._get_master_balance('okx')
                if master_bal == 0: master_bal = 1000.0
                
                trade_cost = qty * price
                ratio = min((trade_cost / master_bal), 0.99)

                print(f"\n🚀 [QUEUE] SIGNAL (OKX SPOT): {side} {symbol} | Ratio: {ratio*100:.2f}%")
                # Pass symbol to execute_trade_parallel for per-coin filtering
                self.execute_trade_parallel(symbol, side.lower(), ratio, executor, 'cgt', master_order_id=master_order_id)
            return

        # --- ЛОГИКА ДЛЯ FUTURES ---
        if status in ['FILLED', 'PARTIALLY_FILLED']:
            # ЗАКРЫТИЕ (SL/TP)
            if orig_type in ['STOP_MARKET', 'TAKE_PROFIT_MARKET']:
                print(f"\n🚨 [QUEUE] CLOSE ALL ({master_exchange}): {symbol}")
                self.close_all_positions_parallel(symbol, executor)
            
            # ВХОД / УСРЕДНЕНИЕ / РУЧНОЕ ЗАКРЫТИЕ
            elif order_type in ['MARKET', 'LIMIT']:
                # FIX: Calculate master balance BEFORE using it
                master_bal = self._get_master_balance(master_exchange)
                
                # Decoupled Mode: Ratio is only used for logging/master context, not for User sizing.
                # User sizing happens inside _execute_single_user using Capital * Risk
                ratio = 0 
                if master_bal > 0:
                     ratio = min((qty * price) / master_bal, 0.99)
                
                
                # Use strategy from event (default to 'ratner' if missing)
                use_strategy = event_data.get('strategy', 'ratner') 

                print(f"\n🚀 [QUEUE] SIGNAL ({master_exchange}): {side} {symbol} | Ratio: {ratio*100:.2f}% (RO={is_reduce_only})")
                
                # --- ПЕРЕДАЕМ ФЛАГ is_reduce_only И master_order_id ДАЛЬШЕ ---
                self.execute_trade_parallel(symbol, side.lower(), ratio, executor, use_strategy, is_reduce_only=is_reduce_only, master_order_id=master_order_id)



    def execute_trade_parallel(self, symbol, side, percentage_used, executor, strategy='bro-bot', is_reduce_only=False, master_order_id=None):
        # Используем список подключений (Multi-Exchange)
        # For CGT strategy, filter by symbol to get per-coin configs
        connections = get_active_exchange_connections(strategy=strategy, symbol=symbol if strategy == 'cgt' else None)
        
        if len(connections) == 0:
            print(f"⏭ [WORKER] No active connections for {strategy} / {symbol}")
            return
            
        print(f"⚡ [WORKER] Executing ({strategy}) for {symbol}: {len(connections)} connections...")
        
        for conn in connections:
            user_id = conn['user_id']
            exchange_name = conn['exchange_name']
            reserve = conn['reserved_amount']
            risk_pct = conn.get('risk_pct', 1.0) # Default 1% if missing
            if risk_pct is None: risk_pct = 1.0

            # --- ПЕРЕДАЕМ is_reduce_only, PARAMS И master_order_id ---
            executor.submit(self._execute_single_user, user_id, symbol, side, percentage_used, strategy, is_reduce_only, exchange_name, reserve, risk_pct, master_order_id)

    def close_all_positions_parallel(self, symbol, executor):
        # Закрываем для всех активных подключений (BingBot/Bybit = ratner strategy)
        connections = get_active_exchange_connections(strategy='ratner') 
        
        print(f"⚡ [WORKER] Closing concurrently for {len(connections)} connections...")
        for conn in connections:
            user_id = conn['user_id']
            exchange = conn['exchange_name']
            executor.submit(self._close_single_user, user_id, symbol, exchange)


    def _execute_single_user(self, user_id, symbol, side, percentage_used, strategy='ratner', is_reduce_only=False, exchange_name=None, reserve=0.0, risk_pct=1.0, master_order_id=None):
        """
        Единичная задача исполнения. 
        Логика расчета суммы:
        - CGT (Spot): Сумма = Reserve (Капитал) * (Risk % / 100)
        - Ratner (Futures): Сумма = Reserve (Капитал) * Пропорция_Мастера (percentage_used)
        """
        # Import investigation functions
        from database import get_open_client_copy, record_client_copy, close_client_copy
        
        keys = get_user_decrypted_keys(user_id, exchange_name)
        if not keys: return
        exchange_id = keys.get('exchange', 'binance').lower()

        # --- ТВОЯ НОВАЯ ЛОГИКА РАСЧЕТА СУММЫ ---
        # reserve — это "Торговый капитал", который юзер ввел в боте (например 1000$)
        # risk_pct — это процент на одну сделку (например 5%)
        
        if strategy == 'cgt':
            # For Spot: Trade = (Balance - Reserve) * (Risk / 100)
            # Reserve is the UNTOUCHABLE amount. Trading capital = Balance - Reserve.
            # Actual calculation happens below AFTER fetching real balance.
            target_entry_usd = 0  # Will be calculated in buy block after balance fetch
            print(f"💰 [User {user_id}] {symbol} - Reserve (untouchable): ${reserve:.2f}, Risk: {risk_pct}%")
        else:
            # Для фьючерсов (если нужно зеркалить мастера):
            target_entry_usd = float(reserve) * percentage_used

        # 1. ЗАЩИТА ОТ ПОЗДНЕГО ВХОДА (NEW INVESTIGATION SYSTEM)
        open_client_copy = get_open_client_copy(user_id, symbol)
        
        # LATE ENTRY PROTECTION: Skip sell if client doesn't have open buy
        if side == 'sell' and not open_client_copy:
            print(f"   ⚠️ [LATE ENTRY PROTECTION] User {user_id}: SKIP SELL (no open buy for {symbol})")
            return
        
        # Legacy support: also check old table
        open_trade = get_open_trade(user_id, symbol)
        if is_reduce_only and not open_trade:
            print(f"   ⚠️ User {user_id}: Ignoring ReduceOnly signal (no open position).")
            return
            
        is_closing = True if open_trade and open_trade['side'] != side else False

        try:
            # 2. Инициализация клиента
            ex_class = getattr(ccxt, exchange_id)
            config = {
                'apiKey': keys['apiKey'], 
                'secret': keys['secret'], 
                'password': keys.get('password', ''), 
                'enableRateLimit': True
            }
            config['options'] = {'defaultType': 'spot' if strategy == 'cgt' else 'future'}
            client = ex_class(config)

            # --- СЦЕНАРИЙ: OKX SPOT (CGT) ---
            if strategy == 'cgt' and exchange_id == 'okx':
                ticker = client.fetch_ticker(symbol)
                price = ticker['last']
                
                if side == 'buy':
                    # Fetch real USDT balance
                    bal = client.fetch_balance()
                    real_usdt = float(bal['USDT']['free']) if 'USDT' in bal else 0
                    
                    # --- MIN BALANCE CHECK ---
                    if real_usdt < 5:
                        print(f"   ⚠️ User {user_id}: Balance too low (${real_usdt:.2f} < $5). Skipping.")
                        return

                    # Calculate TRADING CAPITAL = Balance - Reserve (untouchable)
                    trading_capital = max(0, real_usdt - float(reserve))
                    if trading_capital < 2:
                        print(f"   ⚠️ User {user_id}: No trading capital left (Balance: ${real_usdt:.2f}, Reserve: ${reserve:.2f})")
                        return
                    
                    # Trade size = Trading Capital * Risk%
                    target_entry_usd = trading_capital * (float(risk_pct) / 100.0)
                    
                    # Don't spend more than available
                    amount_to_spend = min(target_entry_usd, trading_capital)
                    
                    if amount_to_spend < 2: 
                        print(f"   ⚠️ User {user_id}: Trade too small (${amount_to_spend:.2f})")
                        return

                    qty_coin = amount_to_spend / price
                    print(f"   🚀 User {user_id} [OKX SPOT]: BUY {qty_coin:.6f} {symbol} for ${amount_to_spend:.2f} (Balance: ${real_usdt:.2f}, Reserve: ${reserve:.2f}, Trading Capital: ${trading_capital:.2f}, Risk: {risk_pct}%)")
                    
                    order = client.create_order(symbol, 'market', 'buy', qty_coin, params={'tdMode': 'cash'})
                    time.sleep(1)
                    filled = client.fetch_order(order['id'], symbol)
                    exec_p = filled['average'] or price
                    exec_q = filled['filled']
                    
                    # NEW: Record client copy (investigation system)
                    if master_order_id:
                        record_client_copy(master_order_id, user_id, symbol, side, exec_p, exec_q)
                    
                    # Legacy: also record in old table
                    record_trade_entry(user_id, symbol, side, exec_p, exec_q)
                    print(f"   ✅ User {user_id} Filled: {exec_q} @ {exec_p}")

                elif side == 'sell':
                    # Продаем ВЕСЬ баланс этой монеты
                    bal = client.fetch_balance()
                    base_coin = symbol.split('/')[0]
                    coin_qty = float(bal[base_coin]['free']) if base_coin in bal else 0
                    
                    if coin_qty > 0:
                        # Check value of coin_qty vs USDT
                        # We need price. If price is not available, skip check or fetch it.
                        # Variable 'price' is available from top of loop (line 218 approx)
                        
                        value_usd = coin_qty * price
                        if value_usd < 2.0:
                            print(f"   ⚠️ User {user_id} [OKX SPOT]: Skipping DUST sell (${value_usd:.2f} < $2.00)")
                            return

                        print(f"   🔻 User {user_id} [OKX SPOT]: SELL ALL {coin_qty} {base_coin} (${value_usd:.2f})")
                        
                        order = client.create_order(symbol, 'market', 'sell', coin_qty, params={'tdMode': 'cash'})
                        time.sleep(1)
                        filled = client.fetch_order(order['id'], symbol)
                        exit_price = filled['average'] or price
                        
                        # NEW: Close client copy and get PnL
                        pnl = 0.0
                        if open_client_copy:
                            pnl = close_client_copy(user_id, symbol, exit_price)
                            # Billing happens in close_client_copy via _handle_pnl_and_billing
                            self._handle_pnl_and_billing(user_id, symbol, open_client_copy['entry_price'], exit_price, open_client_copy['quantity'], 'buy')
                        
                        # Legacy: also close in old table
                        if open_trade:
                            close_trade_in_db(user_id, symbol)
                        
                        print(f"   ✅ User {user_id} [OKX SPOT]: SOLD ALL | PnL: ${pnl:.2f}")
                return

            # --- СЦЕНАРИЙ: BINGX FUTURES (RATNER) ---
            elif strategy == 'ratner' and exchange_id == 'bingx':
                ccxt_sym = symbol.replace('USDT', '/USDT:USDT') if '/' not in symbol else symbol
                ticker = client.fetch_ticker(ccxt_sym)
                price = ticker['last']

                try: client.set_leverage(4, ccxt_sym)
                except: pass

                params = {}
                if is_closing or is_reduce_only:
                    pos_side = 'LONG' if open_trade['side'] == 'buy' else 'SHORT'
                    params['positionSide'] = pos_side
                    params['reduceOnly'] = True
                    # При закрытии фьючерсов используем объем из базы/позиции
                    qty = open_trade['quantity'] if open_trade else 0
                else:
                    params['positionSide'] = 'LONG' if side == 'buy' else 'SHORT'
                    qty_raw = target_entry_usd / price
                    qty = float(client.amount_to_precision(ccxt_sym, qty_raw))

                if qty > 0:
                    print(f"   🚀 User {user_id} [BINGX FUT]: {side.upper()} {qty} (from pool ${reserve})")
                    order = client.create_order(ccxt_sym, 'market', side, qty, params=params)
                    time.sleep(0.5)
                    filled = client.fetch_order(order['id'], ccxt_sym)
                    exec_p = filled['average'] or price
                    exec_q = filled['filled']
                    self._safe_db_write(user_id, symbol, side, exec_p, exec_q, is_closing, open_trade)

        except Exception as e:
            print(f"   ❌ Execution Error for User {user_id}: {e}")

        # >>> SCENARIO 2: RATNER (FUTURES) - BINANCE <<< [DISABLED]
        # if exchange_id == 'binance':
        #     try:
        #         client = UMFutures(key=keys['apiKey'], secret=keys['secret'], base_url="https://fapi.binance.com")
        #         
        #         # Check Min Balance (Safety)
        #         acc = client.account()
        #         # We don't strictly *need* to check balance if we trust 'target_entry_usd', but good practice.
        #         
        #         ticker = float(client.ticker_price(symbol)['price'])
        #         prec = 3 if symbol.startswith("BTC") else (2 if symbol.startswith("ETH") else 0)
        #         
        #         # Setup Leverage
        #         try: client.change_leverage(symbol=symbol, leverage=20)
        #         except: pass
        #
        #         if not is_closing and not is_reduce_only:
        #             # ENTRY
        #             qty = round(target_entry_usd / ticker, prec)
        #             if qty == 0: return
        #
        #             print(f"   🚀 User {user_id} [BINANCE]: {side.upper()} {qty} {symbol} (${target_entry_usd:.2f})")
        #             resp = client.new_order(symbol=symbol, side=side.upper(), type="MARKET", quantity=qty)
        #             
        #             time.sleep(0.5)
        #             det = client.query_order(symbol=symbol, orderId=resp['orderId'])
        #             exec_p = float(det['avgPrice']) or ticker
        #             exec_q = float(det['executedQty'])
        #             
        #             self._safe_db_write(user_id, symbol, side, exec_p, exec_q, False, open_trade)
        #             print(f"   ✅ User {user_id} [BINANCE] ENTRY FILLED")
        #             
        #         else:
        #             # EXIT / CLOSE ALL
        #             # Fetch Position to Close 100%
        #             positions = client.account()['positions']
        #             pos = next((p for p in positions if p['symbol'] == symbol), None)
        #             if pos and float(pos['positionAmt']) != 0:
        #                 pos_amt = abs(float(pos['positionAmt']))
        #                 print(f"   🔻 User {user_id} [BINANCE]: CLOSE ALL {pos_amt} {symbol}")
        #                 
        #                 client.new_order(symbol=symbol, side=side.upper(), type="MARKET", quantity=pos_amt, reduceOnly='true')
        #                 
        #                 # Close DB
        #                 close_trade_in_db(user_id, symbol)
        #                 print(f"   ✅ User {user_id} [BINANCE] CLOSED")
        #
        #     except Exception as e:
        #         print(f"   ❌ User {user_id} Binance Error: {e}")

        # >>> SCENARIO 3: RATNER (FUTURES) - CCXT (BINGX ONLY, BYBIT DISABLED) <<<
        if exchange_id == 'bingx':
            try:
                ex_class = getattr(ccxt, exchange_id)
                config = {'apiKey': keys['apiKey'], 'secret': keys['secret'], 'password': keys.get('password', ''), 'options': {'defaultType': 'future'}, 'enableRateLimit': True}
                client = ex_class(config)

                ccxt_sym = symbol
                if 'USDT' in symbol and '/' not in symbol: ccxt_sym = symbol.replace('USDT', '/USDT:USDT')

                ticker = client.fetch_ticker(ccxt_sym)
                price = float(ticker['last'])
                
                # Leverage
                try: 
                    client.set_leverage(4, ccxt_sym)  # BingX uses 4x
                except: pass

                if not is_closing and not is_reduce_only:
                    # ENTRY
                    qty_raw = target_entry_usd / price
                    qty_str = client.amount_to_precision(ccxt_sym, qty_raw)
                    qty = float(qty_str)
                    if qty == 0: return

                    print(f"   🚀 User {user_id} [BINGX]: {side.upper()} {qty} (${target_entry_usd:.2f})")
                    
                    params = {'positionSide': 'LONG' if side == 'buy' else 'SHORT'}

                    order = client.create_order(ccxt_sym, 'market', side, qty, params=params)
                    time.sleep(0.5)
                    filled = client.fetch_order(order['id'], ccxt_sym)
                    exec_p = filled['average'] or price
                    exec_q = filled['filled']
                    
                    self._safe_db_write(user_id, symbol, side, exec_p, exec_q, False, open_trade)
                    print(f"   ✅ User {user_id} [BINGX] ENTRY FILLED")

                else:
                    # EXIT / CLOSE ALL
                    # Fetch Position
                    positions = client.fetch_positions([ccxt_sym])
                    pos = next((p for p in positions if p['symbol'] == ccxt_sym), None)
                    
                    if pos and float(pos['contracts']) > 0:
                        pos_amt = float(pos['contracts'])
                        print(f"   🔻 User {user_id} [BINGX]: CLOSE ALL {pos_amt}")
                        
                        ps = 'LONG' if open_trade['side'] == 'buy' else 'SHORT' if open_trade['side'] == 'sell' else 'BOTH'
                        params = {'reduceOnly': True, 'positionSide': ps}

                        client.create_order(ccxt_sym, 'market', side, pos_amt, params=params)
                        close_trade_in_db(user_id, symbol)
                        print(f"   ✅ User {user_id} [BINGX] CLOSED")

            except Exception as e:
                print(f"   ❌ User {user_id} BingX Error: {e}")

        # >>> СЦЕНАРИЙ 2: RATNER (FUTURES) - BINANCE <<< [DISABLED]
        # if exchange_id == 'binance':
        #     try:
        #         # REAL URL
        #         client = UMFutures(key=keys['apiKey'], secret=keys['secret'], base_url="https://fapi.binance.com")
        #         
        #         acc = client.account()
        #         usdt = float(next((a['availableBalance'] for a in acc['assets'] if a['asset']=='USDT'), 0))
        #         
        #         # --- MIN BALANCE CHECK ($100) ---
        #         if usdt < 100:
        #             print(f"   ⚠️ User {user_id}: Balance too low (${usdt:.2f} < $100). Skipping.")
        #             return
        #
        #         usdt = max(0, usdt - reserve) # APPLY RESERVE
        #         amt_usd = usdt * percentage_used
        #         if amt_usd < 5 and not is_closing: return
        #
        #         ticker = float(client.ticker_price(symbol)['price'])
        #         prec = 3 if symbol.startswith("BTC") else (2 if symbol.startswith("ETH") else 0)
        #         qty = round(amt_usd / ticker, prec)
        #         if qty == 0: return
        #
        #         try: client.change_leverage(symbol=symbol, leverage=20)
        #         except: pass
        #         
        #         # Для Binance reduceOnly передается как параметр в ордер
        #         params = {}
        #         if is_closing or is_reduce_only:
        #             params['reduceOnly'] = 'true'
        #         
        #         # resp = client.new_order(symbol=symbol, side=side.upper(), type="MARKET", quantity=qty, params=params)
        #         resp = client.new_order(symbol=symbol, side=side.upper(), type="MARKET", quantity=qty, **params)
        #         time.sleep(0.5)
        #         det = client.query_order(symbol=symbol, orderId=resp['orderId'])
        #         exec_p = float(det['avgPrice']) or ticker
        #         exec_q = float(det['executedQty'])
        #
        #         print(f"   ✅ User {user_id} [BINANCE REAL]: {side.upper()} {exec_q} @ {exec_p}")
        #         self._safe_db_write(user_id, symbol, side, exec_p, exec_q, is_closing, open_trade)
        #     except Exception as e:
        #         print(f"   ❌ User {user_id} Binance Error: {e}")

        # >>> СЦЕНАРИЙ 3: RATNER (FUTURES) - CCXT (BINGX ONLY, BYBIT DISABLED) <<<
        if exchange_id == 'bingx':
            try:
                ex_class = getattr(ccxt, exchange_id)
                config = {'apiKey': keys['apiKey'], 'secret': keys['secret'], 'password': keys.get('password', ''), 'options': {'defaultType': 'future'}, 'enableRateLimit': True}
                client = ex_class(config)

                ccxt_sym = symbol
                if 'USDT' in symbol and '/' not in symbol: ccxt_sym = symbol.replace('USDT', '/USDT:USDT')

                bal = client.fetch_balance({'type': 'future'})
                usdt = float(bal['USDT']['free'])
                
                # --- MIN BALANCE CHECK ($100) ---
                if usdt < 100:
                    print(f"   ⚠️ User {user_id}: Balance too low (${usdt:.2f} < $100). Skipping.")
                    return

                usdt = max(0, usdt - reserve) # APPLY RESERVE
                amt_usd = usdt * percentage_used
                if amt_usd < 2 and not is_closing: return 

                ticker = client.fetch_ticker(ccxt_sym)
                price = float(ticker['last'])
                qty_raw = amt_usd / price
                qty_str = client.amount_to_precision(ccxt_sym, qty_raw)
                qty = float(qty_str)
                if qty == 0: return

                try: client.set_leverage(4, ccxt_sym)  # BingX uses 4x
                except: pass

                # Hedge Mode + ReduceOnly
                params = {}
                if is_closing or is_reduce_only:
                    pos_side = 'LONG' if open_trade['side'] == 'buy' else 'SHORT'
                    params['positionSide'] = pos_side
                    params['reduceOnly'] = True
                else:
                    pos_side = 'LONG' if side == 'buy' else 'SHORT'
                    params['positionSide'] = pos_side

                order = client.create_order(ccxt_sym, 'market', side, qty, params=params)
                time.sleep(0.5)
                filled = client.fetch_order(order['id'], ccxt_sym)
                exec_p = filled['average'] or price
                exec_q = filled['filled']

                print(f"   ✅ User {user_id} [BINGX]: {side.upper()} {exec_q} @ {exec_p}")
                self._safe_db_write(user_id, symbol, side, exec_p, exec_q, is_closing, open_trade)

            except Exception as e:
                print(f"   ❌ User {user_id} BingX Error: {e}")



    # ... (Остальные методы _close_single_user, _safe_db_write, _handle_pnl... без изменений)
    # Скопируй их из предыдущего рабочего кода, если они тут сокращены.
    # Главное изменение было в _execute_single_user.
    
    def _close_single_user(self, user_id, symbol, exchange_name=None):
        keys = get_user_decrypted_keys(user_id, exchange_name)
        if not keys: return
        exchange_id = keys.get('exchange', 'binance').lower()

        # BINANCE CLOSE [DISABLED]
        # if exchange_id == 'binance':
        #     try:
        #         client = UMFutures(key=keys['apiKey'], secret=keys['secret'], base_url="https://fapi.binance.com")
        #         pos = client.account()['positions']
        #         target = next((p for p in pos if p['symbol'] == symbol and float(p['positionAmt']) != 0), None)
        #         if target:
        #             amt = float(target['positionAmt'])
        #             side = "SELL" if amt > 0 else "BUY"
        #             client.new_order(symbol=symbol, side=side, type="MARKET", quantity=abs(amt), reduceOnly="true")
        #             print(f"   👉 User {user_id}: Closed {abs(amt)}")
        #             time.sleep(0.5)
        #             exit_p = float(client.ticker_price(symbol)['price'])
        #             op = get_open_trade(user_id, symbol)
        #             if op: self._handle_pnl_and_billing(user_id, symbol, op['entry_price'], exit_p, op['quantity'], op['side'])
        #         close_trade_in_db(user_id, symbol)
        #     except Exception as e: print(f"   ❌ User {user_id} Close Error: {e}")

        # CCXT CLOSE (BINGX ONLY, BYBIT DISABLED)
        if exchange_id == 'bingx':
            try:
                ex_class = getattr(ccxt, exchange_id)
                config = {'apiKey': keys['apiKey'], 'secret': keys['secret'], 'options': {'defaultType': 'future'}}
                client = ex_class(config)

                ccxt_sym = symbol
                if 'USDT' in symbol and '/' not in symbol: ccxt_sym = symbol.replace('USDT', '/USDT:USDT')

                positions = client.fetch_positions([ccxt_sym])
                target = next((p for p in positions if float(p['contracts']) > 0), None)
                if target:
                    amt = float(target['contracts'])
                    side = 'sell' if target['side'] == 'long' else 'buy'
                    client.create_order(ccxt_sym, 'market', side, amt, params={'reduceOnly': True})
                    print(f"   👉 User {user_id}: Closed {amt}")
                    time.sleep(0.5)
                    ticker = client.fetch_ticker(ccxt_sym)
                    op = get_open_trade(user_id, symbol)
                    if op: self._handle_pnl_and_billing(user_id, symbol, op['entry_price'], ticker['last'], op['quantity'], op['side'])
                close_trade_in_db(user_id, symbol)
            except Exception as e: print(f"   ❌ User {user_id} Close Error: {e}")

    def _safe_db_write(self, user_id, symbol, side, price, qty, is_closing, open_trade):
        try:
            if is_closing:
                self._handle_pnl_and_billing(user_id, symbol, open_trade['entry_price'], price, qty, open_trade['side'])
                close_trade_in_db(user_id, symbol)
            else:
                record_trade_entry(user_id, symbol, side, price, qty)
        except Exception:
            if is_closing: 
                try: close_trade_in_db(user_id, symbol)
                except: pass
            else: 
                try: record_trade_entry(user_id, symbol, side, price, qty)
                except: pass

    def _handle_pnl_and_billing(self, user_id, symbol, entry, exit_p, qty, side):
        """
        Расчет PnL, списание комиссии 40% (UNC или USDT) и распределение реферальных наград.
        """
        print(f"   💰 [BILLING] User {user_id}, Entry: {entry}, Exit: {exit_p}, Qty: {qty}")
        pnl = (exit_p - entry) * qty if side == 'buy' else (entry - exit_p) * qty
        print(f"   💰 [BILLING] PnL: {pnl:.4f} USDT")
        
        if pnl > 0:
            total_fee = pnl * 0.40
            
            # --- ПРОВЕРЯЕМ БАЛАНС UNC ---
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT unc_balance, token_balance FROM users WHERE user_id = ?", (user_id,))
            res = cursor.fetchone()
            unc_bal = res[0] if res and res[0] else 0.0
            usdt_bal = res[1] if res and res[1] else 0.0
            
            fee_currency = "USDT"
            used_unc = False
            
            # ЛОГИКА ОПЛАТЫ КОМИССИИ
            if unc_bal >= total_fee:
                # 1. ПЛАТИМ ПОЛНОСТЬЮ UNC (Рефералки НЕТ)
                execute_write_query("UPDATE users SET unc_balance = unc_balance - ? WHERE user_id = ?", (total_fee, user_id))
                new_bal = usdt_bal
                new_unc_bal = unc_bal - total_fee
                fee_currency = "UNC"
                used_unc = True
                print(f"   💰 User {user_id} Paid Fee: {total_fee:.2f} UNC.")
                
            elif unc_bal > 0:
                 # 2. ПЛАТИМ ЧАСТИЧНО UNC (Рефералки НЕТ, так как часть покрыта UNC - упрощение)
                 # Либо можно списать все UNC и остаток с USDT. 
                 # По ТЗ: "пока есть UNC, рефералки не работают".
                 # Спишем все UNC и остаток с USDT.
                 remaining_fee = total_fee - unc_bal
                 execute_write_query("UPDATE users SET unc_balance = 0 WHERE user_id = ?", (user_id,))
                 execute_write_query("UPDATE users SET token_balance = token_balance - ? WHERE user_id = ?", (remaining_fee, user_id))
                 
                 new_unc_bal = 0.0
                 # Читаем новый баланс USDT
                 cursor.execute("SELECT token_balance FROM users WHERE user_id = ?", (user_id,))
                 new_bal = cursor.fetchone()[0]
                 
                 used_unc = True # Считаем, что использовался UNC, поэтому рефералки нет? 
                 # Уточнение юзера: "пока у нашего клиента есть баланс UNC никакие рефки не будут срабатыывать"
                 # Раз мы использовали UNC (даже часть), значит рефки нет.
                 fee_currency = "MIXED"
                 print(f"   💰 User {user_id} Paid Fee: {unc_bal:.2f} UNC + {remaining_fee:.2f} USDT.")
                 
            else:
                # 3. ПЛАТИМ ТОЛЬКО USDT (Рефералка ЕСТЬ)
                execute_write_query("UPDATE users SET token_balance = token_balance - ? WHERE user_id = ?", (total_fee, user_id))
                
                # Читаем новый баланс
                cursor.execute("SELECT token_balance FROM users WHERE user_id = ?", (user_id,))
                new_bal = cursor.fetchone()[0]
                new_unc_bal = 0.0
                
                print(f"   💰 User {user_id} Paid Fee: {total_fee:.2f} USDT.")
                
                # MLM (ТОЛЬКО ЕСЛИ НЕ ЗАДЕЙСТВОВАН UNC)
                try:
                    upline = get_referrer_upline(user_id, levels=3)
                    percentages = [0.20, 0.07, 0.03]
                    
                    for i, referrer_id in enumerate(upline):
                        if i < len(percentages):
                            reward = pnl * percentages[i]
                            credit_referral_tokens(referrer_id, reward)
                            print(f"     -> MLM Level {i+1}: Sent {reward:.2f} to {referrer_id}")
                            if self.bot:
                                try:
                                    ref_msg = (
                                        f"🎉 <b>Referral Bonus!</b>\n"
                                        f"Level {i+1} referral closed a profitable trade.\n"
                                        f"💵 You earned: <b>{reward:.2f} USDT</b>"
                                    )
                                    loop = None
                                    try:
                                        loop = asyncio.new_event_loop()
                                        asyncio.set_event_loop(loop)
                                        loop.run_until_complete(self.bot.send_message(referrer_id, ref_msg, parse_mode=ParseMode.HTML))
                                    finally:
                                        if loop and not loop.is_closed():
                                            loop.close()
                                except: pass
                except Exception as e:
                    print(f"   ❌ MLM Error: {e}")

            conn.close()

            # Уведомление
            if self.bot:
                try:
                    # Формируем текст балансов
                    bal_text = f"{new_bal:.2f} USDT"
                    if new_unc_bal > 0:
                        bal_text += f"\nUNC Balance: {new_unc_bal:.2f}"
                        
                    msg = (
                        f"✅ <b>TradeMax Trade Closed ({symbol})</b>\n"
                        f"💵 Profit: <b>${pnl:.2f}</b>\n"
                        f"💰 Balance: <b>{bal_text}</b>"
                    )
                    
                    # Fix: Use try/finally to ensure loop cleanup
                    loop = None
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.bot.send_message(user_id, msg, parse_mode=ParseMode.HTML))
                    finally:
                        if loop and not loop.is_closed():
                            loop.close()
                except Exception as e:
                    print(f"   ⚠️ Failed to send user notification: {e}")

            # Блокировка (Если USDT кончился и UNC кончился)
            if new_bal <= 0 and new_unc_bal <= 0:
                print(f"   ⛔ User {user_id} balance empty. Pausing.")
                set_copytrading_status(user_id, is_enabled=False)
                if self.bot:
                    try:
                        loop = None
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self.bot.send_message(user_id, "⚠️ <b>Balance Empty</b>\nCopy Trading Paused. Please Top Up.", parse_mode=ParseMode.HTML))
                        finally:
                            if loop and not loop.is_closed():
                                loop.close()
                    except: pass
        else:
            print(f"   📉 User {user_id} Loss: ${pnl:.2f}")