# import time
# import asyncio
# import ccxt
# import concurrent.futures
# from telegram.constants import ParseMode

# # --- Библиотеки ---
# from binance.um_futures import UMFutures  # Оставляем официальную либу для Binance
# from binance.error import ClientError

# # --- База Данных ---
# from database import (
#     get_users_for_copytrade,
#     get_users_with_api_keys,
#     get_user_decrypted_keys, 
#     record_trade_entry, 
#     get_open_trade, 
#     close_trade_in_db, 
#     get_referrer_upline,
#     credit_referral_tokens,
#     deduct_performance_fee,
#     set_copytrading_status
# )

# import os
# from dotenv import load_dotenv
# load_dotenv()

# class TradeCopier:
#     def __init__(self, bot_instance=None):
#         self.bot = bot_instance
#         self.masters = {}
#         self._init_masters()

#     def _init_masters(self):
#         # Инициализация мастеров (только для баланса)
#         # Binance
#         key_b = os.getenv("BINANCE_MASTER_KEY")
#         sec_b = os.getenv("BINANCE_MASTER_SECRET")
#         key_o = os.getenv("OKX_MASTER_KEY")
#         sec_o = os.getenv("OKX_MASTER_SECRET")
#         pass_o = os.getenv("OKX_MASTER_PASSWORD")
#         if key_b:
#             self.masters['binance'] = UMFutures(
#                 key=key_b, 
#                 secret=sec_b, 
#                 base_url="https://fapi.binance.com" # <--- БЫЛ testnet, СТАЛ fapi (Реал)
#             )
#             print("✅ Master [binance] initialized (REAL).")
#         if key_o:
#             try:
#                 self.masters['okx'] = ccxt.okx({
#                     'apiKey': key_o, 'secret': sec_o, 'password': pass_o,
#                     'options': {'defaultType': 'spot'}
#                 })
#                 print("✅ Master [okx] initialized.")
#             except: pass
#         # Остальные через CCXT
#         for name in ['bybit', 'bingx']:
#             key = os.getenv(f"{name.upper()}_MASTER_KEY")
#             sec = os.getenv(f"{name.upper()}_MASTER_SECRET")
#             if key:
#                 try:
#                     ex_class = getattr(ccxt, name)
#                     ex = ex_class({'apiKey': key, 'secret': sec, 'options': {'defaultType': 'future'}})
#                     # if name == 'bybit': ex.set_sandbox_mode(True)
#                     self.masters[name] = ex
#                     print(f"✅ Master [{name}] initialized.")
#                 except: pass

#     def _get_master_balance(self, exchange_name):
#         try:
#             if exchange_name == 'binance':
#                 acc = self.masters['binance'].account()
#                 for a in acc['assets']:
#                     if a['asset'] == 'USDT': return float(a['walletBalance'])
#             else:
#                 master = self.masters.get(exchange_name)
#                 if master:
#                     bal = master.fetch_balance()
#                     return float(bal['USDT']['free'])
#         except: pass
#         return 10000.0

#     # --- CONSUMER ---
#     def start_consuming(self, queue):
#         print("--- [Worker: HYBRID CONSUMER] Started ---")
#         with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
#             while True:
#                 event_data = queue.get()
#                 if event_data is None: break
#                 try: self.process_signal(event_data, executor)
#                 except Exception as e: print(f"❌ Worker Error: {e}")
#                 finally: queue.task_done()
#         print("--- [Worker] Stopped ---")
        
#     def process_signal(self, event_data, executor):
#         master_exchange = event_data.get('master_exchange', 'binance')
#         symbol = event_data.get('s'); side = event_data.get('S')
#         order_type = event_data.get('o'); status = event_data.get('X')
#         orig_type = event_data.get('ot')
#         qty = float(event_data.get('q', 0))
#         price = float(event_data.get('ap', 0)) or float(event_data.get('p', 0))
#         if master_exchange == 'okx':
#             if status == 'FILLED':
#                 # Для Spot стратегии нет понятия "закрытие позиции", есть просто BUY и SELL.
#                 # Но мы можем использовать логику "Продать всё" если сигнал SELL.
                
#                 master_bal = self._get_master_balance('okx')
#                 # Для Spot баланс может быть в монете, но мы считаем ratio от USDT
#                 if master_bal == 0: master_bal = 1000.0 # Fallback
                
#                 trade_cost = qty * price
#                 ratio = trade_cost / master_bal
#                 ratio = min(ratio, 0.99)

#                 print(f"\n🚀 [QUEUE] SIGNAL (OKX SPOT): {side} {symbol} | Ratio: {ratio*100:.2f}%")
#                 self.execute_trade_parallel(symbol, side.lower(), ratio, executor)
#             return # Выходим, чтобы не попасть в фьючерсную логику
#         if status in ['FILLED', 'PARTIALLY_FILLED']:
#             # ЗАКРЫТИЕ (SL/TP)
#             if orig_type in ['STOP_MARKET', 'TAKE_PROFIT_MARKET']:
#                 print(f"\n🚨 [QUEUE] CLOSE ALL ({master_exchange}): {symbol}")
#                 self.close_all_positions_parallel(symbol, executor)
            
#             # ВХОД / УСРЕДНЕНИЕ
#             elif order_type in ['MARKET', 'LIMIT']:
#                 master_bal = self._get_master_balance(master_exchange)
                
#                 # --- ИСПРАВЛЕНИЕ: Защита от бешеных процентов ---
#                 if master_bal > 0:
#                     raw_ratio = (qty * price) / master_bal
#                     # Ограничиваем максимум 100% (1.0), чтобы не было 910%
#                     ratio = min(raw_ratio, 0.99) 
#                 else:
#                     ratio = 0
                
#                 print(f"\n🚀 [QUEUE] SIGNAL ({master_exchange}): {side} {symbol} | Ratio: {ratio*100:.2f}%")
#                 self.execute_trade_parallel(symbol, side.lower(), ratio, executor)
#     # --- PARALLEL EXECUTORS ---
#     def execute_trade_parallel(self, symbol, side, percentage_used, executor):
#         subscribers = get_users_for_copytrade()
#         print(f"⚡ [WORKER] Executing concurrently for {len(subscribers)} users...")
#         for user_id in subscribers:
#             executor.submit(self._execute_single_user, user_id, symbol, side, percentage_used)

#     def close_all_positions_parallel(self, symbol, executor):
#         subscribers = get_users_with_api_keys()
#         print(f"⚡ [WORKER] Closing concurrently for {len(subscribers)} users...")
#         for user_id in subscribers:
#             executor.submit(self._close_single_user, user_id, symbol)


#     def _execute_single_user(self, user_id, symbol, side, percentage_used):
#         keys = get_user_decrypted_keys(user_id)
#         if not keys: return
#         exchange_id = keys.get('exchange', 'binance').lower()

#         if exchange_id == 'binance':
#             try:
#                 # ВАЖНО: base_url="https://fapi.binance.com" (Реал)
#                 client = UMFutures(key=keys['apiKey'], secret=keys['secret'], base_url="https://fapi.binance.com")
                
#                 open_trade = get_open_trade(user_id, symbol)
#                 is_closing = False
#                 if open_trade and open_trade['side'] != side: is_closing = True

#                 acc = client.account()
#                 usdt = float(next((a['availableBalance'] for a in acc['assets'] if a['asset']=='USDT'), 0))
#                 amt_usd = usdt * percentage_used
#                 if amt_usd < 5 and not is_closing: return

#                 ticker = float(client.ticker_price(symbol)['price'])
#                 prec = 3 if symbol.startswith("BTC") else (2 if symbol.startswith("ETH") else 0)
#                 qty = round(amt_usd / ticker, prec)
#                 if qty == 0: return

#                 try: client.change_leverage(symbol=symbol, leverage=20)
#                 except: pass
                
#                 resp = client.new_order(symbol=symbol, side=side.upper(), type="MARKET", quantity=qty)
#                 time.sleep(0.5)
#                 det = client.query_order(symbol=symbol, orderId=resp['orderId'])
#                 exec_p = float(det['avgPrice']) or ticker
#                 exec_q = float(det['executedQty'])

#                 print(f"   ✅ User {user_id} [BINANCE REAL]: {side.upper()} {exec_q} @ {exec_p}")
#                 self._safe_db_write(user_id, symbol, side, exec_p, exec_q, is_closing, open_trade)
#             except Exception as e:
#                 print(f"   ❌ User {user_id} Binance Error: {e}")

#         # >>> ЛОГИКА ДЛЯ BINGX / BYBIT (CCXT) - ВОТ ТУТ ИЗМЕНЕНИЯ <<<
#         else:
#             try:
#                 ex_class = getattr(ccxt, exchange_id)
#                 config = {'apiKey': keys['apiKey'], 'secret': keys['secret'], 'options': {'defaultType': 'future'}, 'enableRateLimit': True}
#                 client = ex_class(config)
#                 # if exchange_id == 'bybit': client.set_sandbox_mode(True)

#                 ccxt_sym = symbol
#                 if 'USDT' in symbol and '/' not in symbol: ccxt_sym = symbol.replace('USDT', '/USDT:USDT')

#                 open_trade = get_open_trade(user_id, symbol)
#                 is_closing = False
#                 if open_trade and open_trade['side'] != side: is_closing = True

#                 bal = client.fetch_balance({'type': 'future'})
#                 usdt = float(bal['USDT']['free'])
#                 amt_usd = usdt * percentage_used
#                 if amt_usd < 2 and not is_closing: return # BingX не любит пыль

#                 ticker = client.fetch_ticker(ccxt_sym)
#                 price = float(ticker['last'])
#                 qty_raw = amt_usd / price
#                 qty_str = client.amount_to_precision(ccxt_sym, qty_raw)
#                 qty = float(qty_str)
#                 if qty == 0: return
#                 target_leverage = 20 # База для Binance
                
#                 if exchange_id == 'bingx': target_leverage = 4
#                 if exchange_id == 'bybit': target_leverage = 20 # <-- ПОСТАВЬ СКОЛЬКО ХОЧЕШЬ (хоть 100)
#                 try: client.set_leverage(target_leverage, ccxt_sym)
#                 except: pass
#                 # try: client.set_leverage(20, ccxt_sym)
#                 # except: pass

#                 # --- ДОБАВЛЕНО: HEDGE MODE PARAMS ---
#                 params = {}
#                 if exchange_id in ['bingx', 'bybit']:
#                     if is_closing:
#                         # Если закрываем Long -> positionSide=LONG
#                         pos_side = 'LONG' if open_trade['side'] == 'buy' else 'SHORT'
#                         params['positionSide'] = pos_side
#                         params['reduceOnly'] = True
#                     else:
#                         # Если открываем Buy -> positionSide=LONG
#                         pos_side = 'LONG' if side == 'buy' else 'SHORT'
#                         params['positionSide'] = pos_side

#                 order = client.create_order(ccxt_sym, 'market', side, qty, params=params)
#                 time.sleep(0.5)
#                 filled = client.fetch_order(order['id'], ccxt_sym)
#                 exec_p = filled['average'] or price
#                 exec_q = filled['filled']

#                 print(f"   ✅ User {user_id} [{exchange_id}]: {side.upper()} {exec_q} @ {exec_p}")
#                 self._safe_db_write(user_id, symbol, side, exec_p, exec_q, is_closing, open_trade)

#             except Exception as e:
#                 print(f"   ❌ User {user_id} {exchange_id} Error: {e}")

           
#     def _close_single_user(self, user_id, symbol):
#         keys = get_user_decrypted_keys(user_id)
#         if not keys: return
#         exchange_id = keys.get('exchange', 'binance').lower()

#         # BINANCE CLOSE
#         if exchange_id == 'binance':
#             try:
#                 client = UMFutures(key=keys['apiKey'], secret=keys['secret'], base_url="https://fapi.binance.com")
#                 pos = client.account()['positions']
#                 target = next((p for p in pos if p['symbol'] == symbol and float(p['positionAmt']) != 0), None)
#                 if target:
#                     amt = float(target['positionAmt'])
#                     side = "SELL" if amt > 0 else "BUY"
#                     client.new_order(symbol=symbol, side=side, type="MARKET", quantity=abs(amt), reduceOnly="true")
#                     print(f"   👉 User {user_id}: Closed {abs(amt)}")
#                     time.sleep(0.5)
#                     exit_p = float(client.ticker_price(symbol)['price'])
#                     op = get_open_trade(user_id, symbol)
#                     if op: self._handle_pnl_and_billing(user_id, symbol, op['entry_price'], exit_p, op['quantity'], op['side'])
#                 close_trade_in_db(user_id, symbol)
#             except Exception as e: print(f"   ❌ User {user_id} Close Error: {e}")

#         # CCXT CLOSE
#         else:
#             try:
#                 ex_class = getattr(ccxt, exchange_id)
#                 config = {'apiKey': keys['apiKey'], 'secret': keys['secret'], 'options': {'defaultType': 'future'}}
#                 client = ex_class(config)
#                 # if exchange_id == 'bybit': client.set_sandbox_mode(True)

#                 ccxt_sym = symbol
#                 if 'USDT' in symbol and '/' not in symbol: ccxt_sym = symbol.replace('USDT', '/USDT:USDT')

#                 positions = client.fetch_positions([ccxt_sym])
#                 target = next((p for p in positions if float(p['contracts']) > 0), None)
#                 if target:
#                     amt = float(target['contracts'])
#                     side = 'sell' if target['side'] == 'long' else 'buy'
#                     client.create_order(ccxt_sym, 'market', side, amt, params={'reduceOnly': True})
#                     print(f"   👉 User {user_id}: Closed {amt}")
#                     time.sleep(0.5)
#                     ticker = client.fetch_ticker(ccxt_sym)
#                     op = get_open_trade(user_id, symbol)
#                     if op: self._handle_pnl_and_billing(user_id, symbol, op['entry_price'], ticker['last'], op['quantity'], op['side'])
#                 close_trade_in_db(user_id, symbol)
#             except Exception as e: print(f"   ❌ User {user_id} Close Error: {e}")

#     def _safe_db_write(self, user_id, symbol, side, price, qty, is_closing, open_trade):
#         try:
#             if is_closing:
#                 self._handle_pnl_and_billing(user_id, symbol, open_trade['entry_price'], price, qty, open_trade['side'])
#                 close_trade_in_db(user_id, symbol)
#             else:
#                 record_trade_entry(user_id, symbol, side, price, qty)
#         except Exception:
#             if is_closing: 
#                 try: close_trade_in_db(user_id, symbol)
#                 except: pass
#             else: 
#                 try: record_trade_entry(user_id, symbol, side, price, qty)
#                 except: pass

# def _handle_pnl_and_billing(self, user_id, symbol, entry, exit_p, qty, side):
#         """
#         Расчет PnL, списание комиссии 40% и распределение реферальных наград.
#         """
#         # 1. Считаем чистый PnL сделки
#         pnl = (exit_p - entry) * qty if side == 'buy' else (entry - exit_p) * qty
        
#         if pnl > 0:
#             # 2. Считаем общую комиссию (40% от профита) и списываем её
#             total_fee = pnl * 0.40
#             new_bal = deduct_performance_fee(user_id, total_fee)
            
#             print(f"   💰 User {user_id} Profit: ${pnl:.2f} | Total Fee: {total_fee:.2f}")
            
#             # 3. Отправляем уведомление пользователю о профите
#             if self.bot:
#                 try:
#                     msg = (
#                         f"💰 <b>Profit Realized!</b>\n"
#                         f"📈 {symbol}\n"
#                         f"💵 Profit: <b>${pnl:.2f}</b>\n"
#                         f"💸 Fee (40%): <b>{total_fee:.2f} tokens</b>\n"
#                         f"🏦 Balance: <b>{new_bal:.2f} tokens</b>"
#                     )
#                     # Используем новый цикл событий для асинхронной отправки из потока
#                     loop = asyncio.new_event_loop()
#                     asyncio.set_event_loop(loop)
#                     loop.run_until_complete(self.bot.send_message(user_id, msg, parse_mode=ParseMode.HTML))
#                     loop.close()
#                 except Exception as e:
#                     print(f"   ⚠️ Failed to send user notification: {e}")

#             # 4. MLM РАСПРЕДЕЛЕНИЕ (20% - 7% - 3% от суммы профита)
#             try:
#                 # Получаем цепочку рефереров [L1, L2, L3]
#                 upline = get_referrer_upline(user_id, levels=3)
#                 percentages = [0.20, 0.07, 0.03] # Проценты для уровней
                
#                 for i, referrer_id in enumerate(upline):
#                     if i < len(percentages):
#                         reward = pnl * percentages[i] # Считаем награду
#                         credit_referral_tokens(referrer_id, reward) # Начисляем
                        
#                         print(f"     -> MLM Level {i+1}: Sent {reward:.2f} to {referrer_id}")
                        
#                         # Уведомляем реферера
#                         if self.bot:
#                             try:
#                                 ref_msg = (
#                                     f"🎉 <b>Referral Bonus!</b>\n"
#                                     f"Level {i+1} referral closed a profitable trade.\n"
#                                     f"💵 You earned: <b>{reward:.2f} tokens</b>"
#                                 )
#                                 loop = asyncio.new_event_loop()
#                                 asyncio.set_event_loop(loop)
#                                 loop.run_until_complete(self.bot.send_message(referrer_id, ref_msg, parse_mode=ParseMode.HTML))
#                                 loop.close()
#                             except: pass
#             except Exception as e:
#                 print(f"   ❌ MLM Error: {e}")

#             # 5. Проверка баланса и блокировка, если ушли в минус/ноль
#             if new_bal <= 0:
#                 print(f"   ⛔ User {user_id} balance empty. Pausing.")
#                 set_copytrading_status(user_id, is_enabled=False)
#                 if self.bot:
#                     try: 
#                         loop = asyncio.new_event_loop()
#                         asyncio.set_event_loop(loop)
#                         loop.run_until_complete(self.bot.send_message(user_id, "⚠️ <b>Balance Empty</b>\nCopy Trading Paused. Please Top Up.", parse_mode=ParseMode.HTML))
#                         loop.close()
#                     except: pass
#         else:
#             print(f"   📉 User {user_id} Loss: ${pnl:.2f}")


import time
import asyncio
import ccxt
import concurrent.futures
from telegram.constants import ParseMode

# --- Библиотеки ---
from binance.um_futures import UMFutures
from binance.error import ClientError

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
    set_copytrading_status
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
        # 1. Binance (Futures)
        key_b = os.getenv("BINANCE_MASTER_KEY")
        sec_b = os.getenv("BINANCE_MASTER_SECRET")
        if key_b:
            self.masters['binance'] = UMFutures(
                key=key_b, 
                secret=sec_b, 
                base_url="https://fapi.binance.com"
            )
            print("✅ Master [binance] initialized (REAL).")

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
        for name in ['bybit', 'bingx']:
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
            if exchange_name == 'binance':
                acc = self.masters['binance'].account()
                for a in acc['assets']:
                    if a['asset'] == 'USDT': return float(a['walletBalance'])
            elif exchange_name == 'okx':
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
        strategy = event_data.get('strategy', 'ratner') # ratner (futures) или cgt (spot)
        
        symbol = event_data.get('s'); side = event_data.get('S')
        order_type = event_data.get('o'); status = event_data.get('X')
        orig_type = event_data.get('ot')
        qty = float(event_data.get('q', 0))
        price = float(event_data.get('ap', 0)) or float(event_data.get('p', 0))

        # --- ЛОГИКА ДЛЯ OKX (SPOT) ---
        if master_exchange == 'okx':
            if status == 'FILLED':
                master_bal = self._get_master_balance('okx')
                if master_bal == 0: master_bal = 1000.0
                
                trade_cost = qty * price
                ratio = trade_cost / master_bal
                ratio = min(ratio, 0.99)

                print(f"\n🚀 [QUEUE] SIGNAL (OKX SPOT): {side} {symbol} | Ratio: {ratio*100:.2f}%")
                # Передаем strategy='cgt'
                self.execute_trade_parallel(symbol, side.lower(), ratio, executor, strategy='cgt')
            return

        # --- ЛОГИКА ДЛЯ FUTURES ---
        if status in ['FILLED', 'PARTIALLY_FILLED']:
            # ЗАКРЫТИЕ (SL/TP)
            if orig_type in ['STOP_MARKET', 'TAKE_PROFIT_MARKET']:
                print(f"\n🚨 [QUEUE] CLOSE ALL ({master_exchange}): {symbol}")
                self.close_all_positions_parallel(symbol, executor)
            
            # ВХОД / УСРЕДНЕНИЕ
            elif order_type in ['MARKET', 'LIMIT']:
                master_bal = self._get_master_balance(master_exchange)
                if master_bal > 0:
                    raw_ratio = (qty * price) / master_bal
                    ratio = min(raw_ratio, 0.99) 
                else:
                    ratio = 0
                
                print(f"\n🚀 [QUEUE] SIGNAL ({master_exchange}): {side} {symbol} | Ratio: {ratio*100:.2f}%")
                # Передаем strategy='ratner'
                self.execute_trade_parallel(symbol, side.lower(), ratio, executor, strategy='ratner')

    # --- PARALLEL EXECUTORS ---
    def execute_trade_parallel(self, symbol, side, percentage_used, executor, strategy='ratner'):
        # Фильтруем юзеров по стратегии (кто выбрал CGT, а кто Ratner)
        subscribers = get_users_for_copytrade(strategy=strategy)
        print(f"⚡ [WORKER] Executing ({strategy}) for {len(subscribers)} users...")
        for user_id in subscribers:
            executor.submit(self._execute_single_user, user_id, symbol, side, percentage_used, strategy)

    def close_all_positions_parallel(self, symbol, executor):
        # Закрытие нужно только для Futures (Ratner)
        # Для Spot (CGT) закрытие - это просто сигнал SELL, который идет через execute_trade
        subscribers = get_users_with_api_keys()
        print(f"⚡ [WORKER] Closing concurrently for {len(subscribers)} users...")
        for user_id in subscribers:
            executor.submit(self._close_single_user, user_id, symbol)


    def _execute_single_user(self, user_id, symbol, side, percentage_used, strategy='ratner'):
        keys = get_user_decrypted_keys(user_id)
        if not keys: return
        exchange_id = keys.get('exchange', 'binance').lower()

        # >>> СЦЕНАРИЙ 1: CGT (OKX SPOT) <<<
        # ВОТ ЭТОГО НЕ БЫЛО В ТВОЕМ ПРОШЛОМ КОДЕ
        if strategy == 'cgt':
            if exchange_id != 'okx': return # CGT только для OKX клиентов
            try:
                # ВАЖНО: Передаем password для OKX
                client = ccxt.okx({
                    'apiKey': keys['apiKey'], 
                    'secret': keys['secret'], 
                    'password': keys.get('password', ''), # <--- ПАРОЛЬ
                    'options': {'defaultType': 'spot'}
                })
                
                bal = client.fetch_balance()
                # Для спота свободный баланс это USDT
                usdt = float(bal['USDT']['free']) if 'USDT' in bal else 0
                amt_usd = usdt * percentage_used
                
                if amt_usd < 2: return 

                ticker = client.fetch_ticker(symbol)
                price = ticker['last']
                
                if side == 'buy':
                    amount_coin = amt_usd / price
                    # tdMode: cash для спота
                    params = {'tdMode': 'cash'}
                    order = client.create_order(symbol, 'market', 'buy', amount_coin, params=params)
                    
                    time.sleep(1)
                    filled = client.fetch_order(order['id'], symbol)
                    exec_p = filled['average'] or price
                    exec_q = filled['filled']
                    
                    record_trade_entry(user_id, symbol, side, exec_p, exec_q)
                    print(f"   ✅ User {user_id} [OKX SPOT]: BUY {exec_q} @ {exec_p}")

                elif side == 'sell':
                    # Продаем всё, что есть
                    base_currency = symbol.split('/')[0]
                    coin_bal = float(bal[base_currency]['free']) if base_currency in bal else 0
                    
                    if coin_bal > 0:
                        params = {'tdMode': 'cash'}
                        order = client.create_order(symbol, 'market', 'sell', coin_bal, params=params)
                        
                        time.sleep(1)
                        filled = client.fetch_order(order['id'], symbol)
                        exit_price = filled['average'] or price
                        
                        open_trade = get_open_trade(user_id, symbol)
                        if open_trade:
                            # Для Spot PnL = (Exit - Entry) * Qty. Передаем side='buy' чтобы формула сработала верно
                            self._handle_pnl_and_billing(user_id, symbol, open_trade['entry_price'], exit_price, open_trade['quantity'], 'buy')
                        
                        close_trade_in_db(user_id, symbol)
                        print(f"   ✅ User {user_id} [OKX SPOT]: SOLD ALL")

            except Exception as e:
                print(f"   ❌ User {user_id} OKX Error: {e}")
            return


        # >>> СЦЕНАРИЙ 2: RATNER (FUTURES) - BINANCE <<<
        if exchange_id == 'binance':
            try:
                # REAL URL
                client = UMFutures(key=keys['apiKey'], secret=keys['secret'], base_url="https://fapi.binance.com")
                
                open_trade = get_open_trade(user_id, symbol)
                is_closing = False
                if open_trade and open_trade['side'] != side: is_closing = True

                acc = client.account()
                usdt = float(next((a['availableBalance'] for a in acc['assets'] if a['asset']=='USDT'), 0))
                amt_usd = usdt * percentage_used
                if amt_usd < 5 and not is_closing: return

                ticker = float(client.ticker_price(symbol)['price'])
                prec = 3 if symbol.startswith("BTC") else (2 if symbol.startswith("ETH") else 0)
                qty = round(amt_usd / ticker, prec)
                if qty == 0: return

                try: client.change_leverage(symbol=symbol, leverage=20)
                except: pass
                
                resp = client.new_order(symbol=symbol, side=side.upper(), type="MARKET", quantity=qty)
                time.sleep(0.5)
                det = client.query_order(symbol=symbol, orderId=resp['orderId'])
                exec_p = float(det['avgPrice']) or ticker
                exec_q = float(det['executedQty'])

                print(f"   ✅ User {user_id} [BINANCE REAL]: {side.upper()} {exec_q} @ {exec_p}")
                self._safe_db_write(user_id, symbol, side, exec_p, exec_q, is_closing, open_trade)
            except Exception as e:
                print(f"   ❌ User {user_id} Binance Error: {e}")

        # >>> СЦЕНАРИЙ 3: RATNER (FUTURES) - CCXT (BYBIT/BINGX) <<<
        else:
            try:
                ex_class = getattr(ccxt, exchange_id)
                config = {
                    'apiKey': keys['apiKey'], 
                    'secret': keys['secret'], 
                    'password': keys.get('password', ''), # <--- ПАРОЛЬ ДЛЯ ДРУГИХ БИРЖ (ЕСЛИ НАДО)
                    'options': {'defaultType': 'future'}, 
                    'enableRateLimit': True
                }
                client = ex_class(config)

                ccxt_sym = symbol
                if 'USDT' in symbol and '/' not in symbol: ccxt_sym = symbol.replace('USDT', '/USDT:USDT')

                open_trade = get_open_trade(user_id, symbol)
                is_closing = False
                if open_trade and open_trade['side'] != side: is_closing = True

                bal = client.fetch_balance({'type': 'future'})
                usdt = float(bal['USDT']['free'])
                amt_usd = usdt * percentage_used
                if amt_usd < 2 and not is_closing: return 

                ticker = client.fetch_ticker(ccxt_sym)
                price = float(ticker['last'])
                qty_raw = amt_usd / price
                qty_str = client.amount_to_precision(ccxt_sym, qty_raw)
                qty = float(qty_str)
                if qty == 0: return

                target_leverage = 20
                if exchange_id == 'bingx': target_leverage = 4
                try: client.set_leverage(target_leverage, ccxt_sym)
                except: pass

                params = {}
                if exchange_id in ['bingx', 'bybit']:
                    if is_closing:
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

                print(f"   ✅ User {user_id} [{exchange_id}]: {side.upper()} {exec_q} @ {exec_p}")
                self._safe_db_write(user_id, symbol, side, exec_p, exec_q, is_closing, open_trade)

            except Exception as e:
                print(f"   ❌ User {user_id} {exchange_id} Error: {e}")

    # ... (Остальные методы _close_single_user, _safe_db_write, _handle_pnl... без изменений)
    # Скопируй их из предыдущего рабочего кода, если они тут сокращены.
    # Главное изменение было в _execute_single_user.
    
    def _close_single_user(self, user_id, symbol):
        keys = get_user_decrypted_keys(user_id)
        if not keys: return
        exchange_id = keys.get('exchange', 'binance').lower()

        # BINANCE CLOSE
        if exchange_id == 'binance':
            try:
                client = UMFutures(key=keys['apiKey'], secret=keys['secret'], base_url="https://fapi.binance.com")
                pos = client.account()['positions']
                target = next((p for p in pos if p['symbol'] == symbol and float(p['positionAmt']) != 0), None)
                if target:
                    amt = float(target['positionAmt'])
                    side = "SELL" if amt > 0 else "BUY"
                    client.new_order(symbol=symbol, side=side, type="MARKET", quantity=abs(amt), reduceOnly="true")
                    print(f"   👉 User {user_id}: Closed {abs(amt)}")
                    time.sleep(0.5)
                    exit_p = float(client.ticker_price(symbol)['price'])
                    op = get_open_trade(user_id, symbol)
                    if op: self._handle_pnl_and_billing(user_id, symbol, op['entry_price'], exit_p, op['quantity'], op['side'])
                close_trade_in_db(user_id, symbol)
            except Exception as e: print(f"   ❌ User {user_id} Close Error: {e}")

        # CCXT CLOSE
        else:
            try:
                ex_class = getattr(ccxt, exchange_id)
                config = {'apiKey': keys['apiKey'], 'secret': keys['secret'], 'options': {'defaultType': 'future'}}
                client = ex_class(config)
                # if exchange_id == 'bybit': client.set_sandbox_mode(True)

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
        Расчет PnL, списание комиссии 40% и распределение реферальных наград.
        """
        pnl = (exit_p - entry) * qty if side == 'buy' else (entry - exit_p) * qty
        
        if pnl > 0:
            total_fee = pnl * 0.40
            new_bal = deduct_performance_fee(user_id, total_fee)
            
            print(f"   💰 User {user_id} Profit: ${pnl:.2f} | Total Fee: {total_fee:.2f}")
            
            # Уведомление
            if self.bot:
                try:
                    msg = (
                        f"💰 <b>Profit Realized!</b>\n"
                        f"📈 {symbol}\n"
                        f"💵 Profit: <b>${pnl:.2f}</b>\n"
                        f"💸 Fee (40%): <b>{total_fee:.2f} tokens</b>\n"
                        f"🏦 Balance: <b>{new_bal:.2f} tokens</b>"
                    )
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.bot.send_message(user_id, msg, parse_mode=ParseMode.HTML))
                    loop.close()
                except Exception as e:
                    print(f"   ⚠️ Failed to send user notification: {e}")

            # MLM
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
                                    f"💵 You earned: <b>{reward:.2f} tokens</b>"
                                )
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                loop.run_until_complete(self.bot.send_message(referrer_id, ref_msg, parse_mode=ParseMode.HTML))
                                loop.close()
                            except: pass
            except Exception as e:
                print(f"   ❌ MLM Error: {e}")

            # Блокировка
            if new_bal <= 0:
                print(f"   ⛔ User {user_id} balance empty. Pausing.")
                set_copytrading_status(user_id, is_enabled=False)
                if self.bot:
                    try: 
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.bot.send_message(user_id, "⚠️ <b>Balance Empty</b>\nCopy Trading Paused. Please Top Up.", parse_mode=ParseMode.HTML))
                        loop.close()
                    except: pass
        else:
            print(f"   📉 User {user_id} Loss: ${pnl:.2f}")