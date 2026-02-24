import time
import asyncio
import ccxt
import concurrent.futures
import sqlite3
import os
from telegram.constants import ParseMode
from dotenv import load_dotenv

from database import (
    get_users_for_copytrade, get_users_with_api_keys, get_user_decrypted_keys,
    record_trade_entry, get_open_trade, close_trade_in_db,
    get_referrer_upline, credit_referral_tokens, deduct_performance_fee,
    set_copytrading_status, get_active_exchange_connections, execute_write_query,
    DB_NAME, get_user_risk_profile
)

load_dotenv()


class TradeCopier:
    _send_loop = None  # persistent event loop for telegram messages

    def __init__(self, bot_instance=None):
        self.bot = bot_instance
        self.masters = {}
        self._init_masters()

    def _init_masters(self):
        # okx spot
        key_o = os.getenv("OKX_MASTER_KEY")
        if key_o:
            try:
                self.masters['okx'] = ccxt.okx({
                    'apiKey': key_o,
                    'secret': os.getenv("OKX_MASTER_SECRET"),
                    'password': os.getenv("OKX_MASTER_PASSWORD"),
                    'options': {'defaultType': 'spot'}
                })
                print("✅ Master [okx] initialized.")
            except: pass

        # bingx futures
        key_b = os.getenv("BINGX_MASTER_KEY")
        sec_b = os.getenv("BINGX_MASTER_SECRET")
        if key_b:
            try:
                self.masters['bingx'] = ccxt.bingx({
                    'apiKey': key_b, 'secret': sec_b,
                    'options': {'defaultType': 'future'}
                })
                print("✅ Master [bingx] initialized.")
            except: pass

        # bybit futures
        key_by = os.getenv("BYBIT_MASTER_KEY")
        sec_by = os.getenv("BYBIT_MASTER_SECRET")
        if key_by:
            try:
                self.masters['bybit'] = ccxt.bybit({
                    'apiKey': key_by, 'secret': sec_by,
                    'options': {'defaultType': 'linear'}
                })
                print("✅ Master [bybit] initialized.")
            except: pass

    def _get_master_balance(self, exchange_name):
        try:
            if exchange_name == 'okx':
                bal = self.masters['okx'].fetch_balance()
                return float(bal['USDT']['free'])
            master = self.masters.get(exchange_name)
            if master:
                return float(master.fetch_balance()['USDT']['free'])
        except: pass
        return 10000.0

    # ── event consumer ──

    def start_consuming(self, queue):
        print("--- [Worker] Started ---")
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
        strategy = event_data.get('strategy', 'bro-bot')
        master_order_id = event_data.get('master_order_id')

        symbol = event_data.get('s')
        side = event_data.get('S')
        status = event_data.get('X')
        orig_type = event_data.get('ot')
        order_type = event_data.get('o')
        qty = float(event_data.get('q', 0))
        price = float(event_data.get('ap', 0)) or float(event_data.get('p', 0))
        is_reduce_only = event_data.get('ro', False)

        # okx spot signals
        if master_exchange == 'okx':
            if status != 'FILLED': return

            from database import get_active_coins_for_strategy
            if symbol not in get_active_coins_for_strategy('cgt'):
                print(f"⏭ [SKIP] {symbol} - no users configured")
                return

            ratio = event_data.get('ratio')
            if ratio is None:
                master_bal = self._get_master_balance('okx') or 1000.0
                ratio = min((qty * price) / master_bal, 0.99)

            print(f"\n🚀 [SIGNAL] OKX SPOT: {side} {symbol} | Ratio: {ratio*100:.2f}%")
            self.execute_trade_parallel(symbol, side.lower(), ratio, executor, 'cgt', master_order_id=master_order_id)
            return

        # futures signals (bingx)
        if master_exchange == 'bingx':
            if status not in ['FILLED', 'PARTIALLY_FILLED']: return

            if orig_type in ['STOP_MARKET', 'TAKE_PROFIT_MARKET']:
                print(f"\n🚨 [SIGNAL] CLOSE ALL ({master_exchange}): {symbol}")
                self.close_all_positions_parallel(symbol, executor, strategy='ratner')

            elif order_type in ['MARKET', 'LIMIT']:
                master_bal = self._get_master_balance(master_exchange)
                ratio = min((qty * price) / master_bal, 0.99) if master_bal > 0 else 0
                use_strategy = event_data.get('strategy', 'ratner')

                print(f"\n🚀 [SIGNAL] {master_exchange}: {side} {symbol} | Ratio: {ratio*100:.2f}% (RO={is_reduce_only})")
                self.execute_trade_parallel(symbol, side.lower(), ratio, executor, use_strategy, is_reduce_only=is_reduce_only, master_order_id=master_order_id)
            return

        # futures signals (bybit) — BTC only
        if master_exchange == 'bybit':
            if status != 'FILLED': return

            master_bal = self._get_master_balance('bybit')
            ratio = min((qty * price) / master_bal, 0.99) if master_bal > 0 else 0

            print(f"\n🚀 [SIGNAL] Bybit AiTrading: {side} {symbol} | Ratio: {ratio*100:.2f}% (RO={is_reduce_only})")
            self.execute_trade_parallel(symbol, side.lower(), ratio, executor, 'aitrading', is_reduce_only=is_reduce_only, master_order_id=master_order_id)
            return

    # ── parallel execution ──

    def execute_trade_parallel(self, symbol, side, percentage_used, executor, strategy='bro-bot', is_reduce_only=False, master_order_id=None):
        connections = get_active_exchange_connections(strategy=strategy, symbol=symbol if strategy == 'cgt' else None)
        if not connections:
            print(f"⏭ No active connections for {strategy}/{symbol}")
            return

        print(f"⚡ Executing ({strategy}) {symbol}: {len(connections)} connections")
        for conn in connections:
            risk_pct = conn.get('risk_pct', 1.0) or 1.0
            executor.submit(
                self._execute_single_user,
                conn['user_id'], symbol, side, percentage_used, strategy,
                is_reduce_only, conn['exchange_name'], conn['reserved_amount'],
                risk_pct, master_order_id
            )

    def close_all_positions_parallel(self, symbol, executor, strategy='ratner'):
        connections = get_active_exchange_connections(strategy=strategy)
        print(f"⚡ Closing {symbol} for {len(connections)} connections ({strategy})")
        for conn in connections:
            executor.submit(self._close_single_user, conn['user_id'], symbol, conn['exchange_name'])

    # ── single user trade execution ──

    def _execute_single_user(self, user_id, symbol, side, percentage_used, strategy='ratner',
                             is_reduce_only=False, exchange_name=None, reserve=0.0, risk_pct=1.0, master_order_id=None):
        from database import get_open_client_copy, record_client_copy, close_client_copy

        keys = get_user_decrypted_keys(user_id, exchange_name)
        if not keys: return
        exchange_id = keys.get('exchange', 'binance').lower()

        # late entry protection: skip sell if no open buy (for spot CGT)
        open_client_copy = get_open_client_copy(user_id, symbol)
        if strategy == 'cgt' and side == 'sell' and not open_client_copy:
            print(f"   ⚠️ User {user_id}: SKIP SELL (no open buy for {symbol})")
            return

        open_trade = get_open_trade(user_id, symbol)
        if is_reduce_only and not open_trade:
            print(f"   ⚠️ User {user_id}: ignoring ReduceOnly (no position)")
            return

        # determine if this signal closes an existing position
        is_closing = is_reduce_only or bool(open_trade and open_trade['side'] != side)

        try:
            # init exchange client
            ex_class = getattr(ccxt, exchange_id)
            config = {
                'apiKey': keys['apiKey'], 'secret': keys['secret'],
                'password': keys.get('password', ''), 'enableRateLimit': True,
                'options': {'defaultType': 'spot' if strategy == 'cgt' else 'future'}
            }
            client = ex_class(config)

            # ── OKX SPOT (CGT) ──
            if strategy == 'cgt' and exchange_id == 'okx':
                self._execute_okx_spot(client, user_id, symbol, side, reserve, risk_pct,
                                       master_order_id, open_client_copy, open_trade, percentage_used)
                return

        except Exception as e:
            print(f"   ❌ User {user_id} Error: {e}")

        # ── BINGX FUTURES (RATNER) ──
        if exchange_id == 'bingx' and strategy == 'ratner':
            self._execute_bingx_futures(keys, user_id, symbol, side, reserve, percentage_used,
                                        is_closing, is_reduce_only, open_trade,
                                        master_order_id, open_client_copy, risk_pct)

        # ── BYBIT FUTURES (AITRADING) ──
        elif exchange_id == 'bybit' and strategy == 'aitrading':
            self._execute_bybit_futures(keys, user_id, symbol, side, reserve, percentage_used,
                                        is_closing, is_reduce_only, open_trade,
                                        master_order_id, open_client_copy, risk_pct)

    def _execute_okx_spot(self, client, user_id, symbol, side, reserve, risk_pct,
                          master_order_id, open_client_copy, open_trade, sell_ratio_raw):
        from database import record_client_copy, close_client_copy

        ticker = client.fetch_ticker(symbol)
        price = ticker['last']

        if side == 'buy':
            bal = client.fetch_balance()
            real_usdt = float(bal['USDT']['free']) if 'USDT' in bal else 0

            if real_usdt < 5:
                print(f"   ⚠️ User {user_id}: balance too low (${real_usdt:.2f})")
                return

            trading_capital = max(0, real_usdt - float(reserve))
            if trading_capital < 2:
                print(f"   ⚠️ User {user_id}: no trading capital (bal=${real_usdt:.2f}, reserve=${reserve:.2f})")
                return

            amount = min(trading_capital * (float(risk_pct) / 100.0), trading_capital)
            if amount < 2:
                print(f"   ⚠️ User {user_id}: trade too small (${amount:.2f})")
                return

            qty_coin = amount / price
            print(f"   🚀 User {user_id} [OKX]: BUY {qty_coin:.6f} {symbol} ${amount:.2f} (cap=${trading_capital:.2f}, risk={risk_pct}%)")

            order = client.create_order(symbol, 'market', 'buy', qty_coin, params={'tdMode': 'cash'})
            time.sleep(1)
            filled = client.fetch_order(order['id'], symbol)
            exec_p = filled['average'] or price
            exec_q = filled['filled']

            if master_order_id:
                record_client_copy(master_order_id, user_id, symbol, side, exec_p, exec_q)
            record_trade_entry(user_id, symbol, side, exec_p, exec_q)
            print(f"   ✅ User {user_id}: filled {exec_q} @ {exec_p}")

        elif side == 'sell':
            if not open_client_copy and not open_trade:
                print(f"   ⚠️ User {user_id}: SKIP SELL {symbol} (no position)")
                return

            sell_ratio = float(sell_ratio_raw) if sell_ratio_raw else 1.0
            bal = client.fetch_balance()
            base_coin = symbol.split('/')[0]
            held_qty = float(bal[base_coin]['free']) if base_coin in bal else 0

            if held_qty <= 0: return

            # if ~100%, sell everything to avoid dust
            qty_to_sell = held_qty if sell_ratio >= 0.99 else held_qty * sell_ratio
            print(f"   🔻 User {user_id}: SELL {sell_ratio*100:.1f}% -> {qty_to_sell:.6f}")

            if qty_to_sell * price < 2.0:
                print(f"   ⚠️ User {user_id}: dust sell skipped (${qty_to_sell * price:.2f})")
                return

            order = client.create_order(symbol, 'market', 'sell', qty_to_sell, params={'tdMode': 'cash'})
            time.sleep(1)
            filled = client.fetch_order(order['id'], symbol)
            exit_price = filled['average'] or price

            # Use AVERAGE entry price from copied_trades (real position cost basis)
            # NOT the latest individual buy from client_copies (which can be misleading)
            if open_trade and open_trade.get('entry_price', 0) > 0:
                entry_price = open_trade['entry_price']
            elif open_client_copy:
                entry_price = open_client_copy['entry_price']
            else:
                entry_price = 0

            print(f"   📊 User {user_id}: avg_entry=${entry_price:.2f}, exit=${exit_price:.2f}, qty={qty_to_sell:.6f}")

            if entry_price > 0:
                self._handle_pnl_and_billing(user_id, symbol, entry_price, exit_price, qty_to_sell, 'buy')

            if sell_ratio >= 0.99:
                # full close — mark the open client_copy as closed
                close_client_copy(user_id, symbol, exit_price)
                if open_trade: close_trade_in_db(user_id, symbol)
            else:
                # partial sell — record PnL as a separate closed entry for daily reports
                from database import record_partial_sell_pnl
                if entry_price > 0:
                    record_partial_sell_pnl(user_id, symbol, 'buy', entry_price, exit_price, qty_to_sell)

            pnl = (exit_price - entry_price) * qty_to_sell if entry_price > 0 else 0
            print(f"   ✅ User {user_id} [OKX]: SOLD | PnL: ${pnl:.2f}")

    def _execute_bingx_futures(self, keys, user_id, symbol, side, reserve, percentage_used,
                                is_closing, is_reduce_only, open_trade,
                                master_order_id=None, open_client_copy=None, risk_pct=1.0):
        from database import record_client_copy, close_client_copy

        try:
            client = ccxt.bingx({
                'apiKey': keys['apiKey'], 'secret': keys['secret'],
                'password': keys.get('password', ''),
                'options': {'defaultType': 'future'}, 'enableRateLimit': True
            })

            ccxt_sym = symbol
            if 'USDT' in symbol and '/' not in symbol:
                ccxt_sym = symbol.replace('USDT', '/USDT:USDT')

            # ── CLOSING: use real position size from exchange ──
            if is_closing or is_reduce_only:
                if not open_trade:
                    print(f"   ⚠️ User {user_id}: SKIP close (no open position for {symbol})")
                    return

                pos_side = 'LONG' if open_trade['side'] == 'buy' else 'SHORT'

                # fetch actual position from exchange
                try:
                    positions = client.fetch_positions([ccxt_sym])
                    target_pos = None
                    for pos in positions:
                        if pos['side'] and pos['side'].upper() == pos_side[0].upper() + pos_side[1:].lower():
                            if abs(float(pos['contracts'] or 0)) > 0:
                                target_pos = pos
                                break
                        # fallback: match by positionSide string
                        if pos.get('info', {}).get('positionSide', '').upper() == pos_side:
                            if abs(float(pos['contracts'] or 0)) > 0:
                                target_pos = pos
                                break

                    if target_pos:
                        qty = abs(float(target_pos['contracts']))
                        print(f"   📊 User {user_id}: Real position = {qty} {symbol} ({pos_side})")
                    else:
                        print(f"   ⚠️ User {user_id}: No open {pos_side} position on exchange for {symbol}")
                        return
                except Exception as e:
                    print(f"   ⚠️ User {user_id}: fetch_positions failed ({e}), falling back to DB qty")
                    # fallback: use quantity from our DB record
                    db_qty = open_trade.get('quantity', 0)
                    if db_qty > 0:
                        qty = db_qty
                    else:
                        return

                try: client.set_leverage(4, ccxt_sym)
                except: pass

                params = {'positionSide': pos_side, 'reduceOnly': True}
                order = client.create_order(ccxt_sym, 'market', side, qty, params=params)

            # ── OPENING: calculate from live balance × ratio ──
            else:
                bal = client.fetch_balance({'type': 'future'})
                usdt = float(bal['USDT']['free'])

                if usdt < 100:
                    print(f"   ⚠️ User {user_id}: balance too low (${usdt:.2f})")
                    return

                usdt = max(0, usdt - reserve)
                # use user's risk_pct (e.g. 1% of available capital)
                amt_usd = usdt * (float(risk_pct) / 100.0)
                if amt_usd < 2: return

                print(f"   📊 User {user_id} [BINGX]: bal=${usdt+reserve:.2f}, reserve=${reserve:.2f}, risk={risk_pct}%, trade=${amt_usd:.2f}")

                ticker = client.fetch_ticker(ccxt_sym)
                price = float(ticker['last'])
                qty = float(client.amount_to_precision(ccxt_sym, amt_usd / price))
                if qty == 0: return

                try: client.set_leverage(4, ccxt_sym)
                except: pass

                params = {'positionSide': 'LONG' if side == 'buy' else 'SHORT'}
                order = client.create_order(ccxt_sym, 'market', side, qty, params=params)
            time.sleep(0.5)
            filled = client.fetch_order(order['id'], ccxt_sym)
            exec_p = filled['average'] or filled.get('price') or 0
            exec_q = filled['filled']

            print(f"   ✅ User {user_id} [BINGX]: {side.upper()} {exec_q} @ {exec_p}")

            # write to copied_trades (legacy)
            self._safe_db_write(user_id, symbol, side, exec_p, exec_q, is_closing, open_trade)

            # write to client_copies (for daily PnL reports)
            if is_closing and open_trade:
                entry_price = open_client_copy['entry_price'] if open_client_copy else open_trade.get('entry_price', 0)
                if entry_price > 0:
                    self._handle_pnl_and_billing(user_id, symbol, entry_price, exec_p, exec_q, open_trade['side'])
                close_client_copy(user_id, symbol, exec_p)
            elif master_order_id:
                record_client_copy(master_order_id, user_id, symbol, side, exec_p, exec_q)

        except Exception as e:
            print(f"   ❌ User {user_id} BingX Error: {e}")

    def _execute_bybit_futures(self, keys, user_id, symbol, side, reserve, percentage_used,
                                is_closing, is_reduce_only, open_trade,
                                master_order_id=None, open_client_copy=None, risk_pct=1.0):
        from database import record_client_copy, close_client_copy

        try:
            client = ccxt.bybit({
                'apiKey': keys['apiKey'], 'secret': keys['secret'],
                'options': {'defaultType': 'linear'}, 'enableRateLimit': True
            })

            ccxt_sym = 'BTC/USDT:USDT'

            # ── CLOSING: use real position size from exchange ──
            if is_closing or is_reduce_only:
                if not open_trade:
                    print(f"   ⚠️ User {user_id}: SKIP close (no open position for {symbol})")
                    return

                close_side_expected = 'long' if open_trade['side'] == 'buy' else 'short'

                try:
                    positions = client.fetch_positions([ccxt_sym])
                    target_pos = None
                    for pos in positions:
                        if pos.get('side', '').lower() == close_side_expected:
                            if abs(float(pos['contracts'] or 0)) > 0:
                                target_pos = pos
                                break

                    if target_pos:
                        qty = abs(float(target_pos['contracts']))
                        print(f"   📊 User {user_id}: Real Bybit position = {qty} BTC ({close_side_expected})")
                    else:
                        print(f"   ⚠️ User {user_id}: No open {close_side_expected} position on Bybit for BTC")
                        return
                except Exception as e:
                    print(f"   ⚠️ User {user_id}: fetch_positions failed ({e}), falling back to DB qty")
                    db_qty = open_trade.get('quantity', 0)
                    if db_qty > 0:
                        qty = db_qty
                    else:
                        return

                try: client.set_leverage(5, ccxt_sym)
                except: pass

                params = {'reduceOnly': True}
                order = client.create_order(ccxt_sym, 'market', side, qty, params=params)

            # ── OPENING: calculate from live balance × ratio ──
            else:
                bal = client.fetch_balance({'type': 'linear'})
                usdt = float(bal['USDT']['free'])

                if usdt < 100:
                    print(f"   ⚠️ User {user_id}: Bybit balance too low (${usdt:.2f})")
                    return

                usdt = max(0, usdt - reserve)
                # use user's risk_pct (e.g. 1% of available capital)
                amt_usd = usdt * (float(risk_pct) / 100.0)
                if amt_usd < 2: return

                print(f"   📊 User {user_id} [BYBIT]: bal=${usdt+reserve:.2f}, reserve=${reserve:.2f}, risk={risk_pct}%, trade=${amt_usd:.2f}")

                ticker = client.fetch_ticker(ccxt_sym)
                price = float(ticker['last'])
                qty = float(client.amount_to_precision(ccxt_sym, amt_usd / price))
                if qty == 0: return

                try: client.set_leverage(5, ccxt_sym)
                except: pass

                order = client.create_order(ccxt_sym, 'market', side, qty)

            time.sleep(0.5)
            filled = client.fetch_order(order['id'], ccxt_sym)
            exec_p = filled['average'] or filled.get('price') or 0
            exec_q = filled['filled']

            print(f"   ✅ User {user_id} [BYBIT]: {side.upper()} {exec_q} BTC @ {exec_p}")

            # write to copied_trades (legacy)
            self._safe_db_write(user_id, symbol, side, exec_p, exec_q, is_closing, open_trade)

            # write to client_copies (for daily PnL reports)
            if is_closing and open_trade:
                entry_price = open_client_copy['entry_price'] if open_client_copy else open_trade.get('entry_price', 0)
                if entry_price > 0:
                    self._handle_pnl_and_billing(user_id, symbol, entry_price, exec_p, exec_q, open_trade['side'])
                close_client_copy(user_id, symbol, exec_p)
            elif master_order_id:
                record_client_copy(master_order_id, user_id, symbol, side, exec_p, exec_q)

        except Exception as e:
            print(f"   ❌ User {user_id} Bybit Error: {e}")

    # ── close positions ──

    def _close_single_user(self, user_id, symbol, exchange_name=None):
        from database import close_client_copy

        keys = get_user_decrypted_keys(user_id, exchange_name)
        if not keys: return
        exchange_id = keys.get('exchange', 'binance').lower()

        if exchange_id not in ('bingx', 'bybit'): return

        try:
            if exchange_id == 'bingx':
                client = ccxt.bingx({
                    'apiKey': keys['apiKey'], 'secret': keys['secret'],
                    'options': {'defaultType': 'future'}
                })
            else:
                client = ccxt.bybit({
                    'apiKey': keys['apiKey'], 'secret': keys['secret'],
                    'options': {'defaultType': 'linear'}
                })

            ccxt_sym = symbol
            if 'USDT' in symbol and '/' not in symbol:
                ccxt_sym = symbol.replace('USDT', '/USDT:USDT')

            positions = client.fetch_positions([ccxt_sym])
            target = next((p for p in positions if float(p['contracts']) > 0), None)
            if target:
                amt = float(target['contracts'])
                close_side = 'sell' if target['side'] == 'long' else 'buy'

                if exchange_id == 'bingx':
                    pos_side_str = 'LONG' if target['side'] == 'long' else 'SHORT'
                    client.create_order(ccxt_sym, 'market', close_side, amt,
                                        params={'positionSide': pos_side_str, 'reduceOnly': True})
                else:
                    client.create_order(ccxt_sym, 'market', close_side, amt,
                                        params={'reduceOnly': True})

                print(f"   👉 User {user_id}: closed {amt} on {exchange_id}")
                time.sleep(0.5)
                ticker = client.fetch_ticker(ccxt_sym)
                exit_price = ticker['last']
                op = get_open_trade(user_id, symbol)
                if op:
                    self._handle_pnl_and_billing(user_id, symbol, op['entry_price'], exit_price, op['quantity'], op['side'])
                # record in client_copies for daily PnL reports
                close_client_copy(user_id, symbol, exit_price)
            close_trade_in_db(user_id, symbol)
        except Exception as e:
            print(f"   ❌ User {user_id} Close Error: {e}")

    # ── db helpers ──

    def _safe_db_write(self, user_id, symbol, side, price, qty, is_closing, open_trade):
        try:
            if is_closing:
                self._handle_pnl_and_billing(user_id, symbol, open_trade['entry_price'], price, qty, open_trade['side'])
                close_trade_in_db(user_id, symbol)
            else:
                record_trade_entry(user_id, symbol, side, price, qty)
        except Exception:
            try:
                if is_closing: close_trade_in_db(user_id, symbol)
                else: record_trade_entry(user_id, symbol, side, price, qty)
            except: pass

    # ── telegram ──

    def _safe_send_message(self, user_id, text):
        try:
            if not self.bot: return

            # try existing running loop first
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(self.bot.send_message(user_id, text, parse_mode=ParseMode.HTML), loop)
                    return
            except: pass

            # reuse persistent loop (don't close — kills bot's http client)
            if TradeCopier._send_loop is None or TradeCopier._send_loop.is_closed():
                TradeCopier._send_loop = asyncio.new_event_loop()

            asyncio.set_event_loop(TradeCopier._send_loop)
            TradeCopier._send_loop.run_until_complete(self.bot.send_message(user_id, text, parse_mode=ParseMode.HTML))
        except Exception as e:
            print(f"   ⚠️ Send Error: {e}")

    # ── pnl + billing ──

    def _handle_pnl_and_billing(self, user_id, symbol, entry, exit_p, qty, side):
        print(f"   💰 [BILLING] User {user_id}, Entry: {entry}, Exit: {exit_p}, Qty: {qty}")

        gross_pnl = (exit_p - entry) * qty if side == 'buy' else (entry - exit_p) * qty

        # subtract exchange fees (~0.1% taker per side)
        exchange_fees = (entry * qty + exit_p * qty) * 0.001
        pnl = gross_pnl - exchange_fees
        trade_amount_usd = entry * qty

        print(f"   💰 [BILLING] Gross: {gross_pnl:.4f}, Fees: {exchange_fees:.4f}, Net: {pnl:.4f} USDT")

        if pnl <= 0:
            print(f"   📉 User {user_id} Loss: ${pnl:.2f}")
            return

        total_fee = pnl * 0.40

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT unc_balance, token_balance FROM users WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        unc_bal = res[0] if res and res[0] else 0.0
        usdt_bal = res[1] if res and res[1] else 0.0

        if unc_bal >= total_fee:
            # pay fully with UNC — no referral payout
            execute_write_query("UPDATE users SET unc_balance = unc_balance - ? WHERE user_id = ?", (total_fee, user_id))
            new_bal = usdt_bal
            new_unc_bal = unc_bal - total_fee
            print(f"   💰 User {user_id} Fee: {total_fee:.2f} UNC")

        elif unc_bal > 0:
            # pay partially with UNC — no referral payout while UNC exists
            remaining = total_fee - unc_bal
            execute_write_query("UPDATE users SET unc_balance = 0 WHERE user_id = ?", (user_id,))
            execute_write_query("UPDATE users SET token_balance = token_balance - ? WHERE user_id = ?", (remaining, user_id))
            new_unc_bal = 0.0
            cursor.execute("SELECT token_balance FROM users WHERE user_id = ?", (user_id,))
            new_bal = cursor.fetchone()[0]
            print(f"   💰 User {user_id} Fee: {unc_bal:.2f} UNC + {remaining:.2f} USDT")

        else:
            # pay with USDT — referral payouts active
            execute_write_query("UPDATE users SET token_balance = token_balance - ? WHERE user_id = ?", (total_fee, user_id))
            cursor.execute("SELECT token_balance FROM users WHERE user_id = ?", (user_id,))
            new_bal = cursor.fetchone()[0]
            new_unc_bal = 0.0
            print(f"   💰 User {user_id} Fee: {total_fee:.2f} USDT")

            # mlm — % of platform fee (industry standard)
            try:
                upline = get_referrer_upline(user_id, levels=3)
                mlm_pcts = [0.20, 0.07, 0.03]
                for i, referrer_id in enumerate(upline):
                    if i >= len(mlm_pcts): break
                    reward = total_fee * mlm_pcts[i]
                    credit_referral_tokens(referrer_id, reward)
                    print(f"     -> MLM L{i+1}: {reward:.2f} to {referrer_id}")
                    if self.bot:
                        try:
                            self._safe_send_message(referrer_id,
                                f"🎉 <b>Referral Bonus!</b>\n"
                                f"Level {i+1} referral closed a profitable trade.\n"
                                f"💵 You earned: <b>{reward:.2f} USDT</b>"
                            )
                        except: pass
            except Exception as e:
                print(f"   ❌ MLM Error: {e}")

        conn.close()

        # notify user
        if self.bot:
            try:
                bal_text = f"{new_bal:.2f} USDT"
                if new_unc_bal > 0:
                    bal_text += f"\nUNC Balance: {new_unc_bal:.2f}"

                self._safe_send_message(user_id,
                    f"✅ <b>TradeMax Trade Closed ({symbol})</b>\n"
                    f"💰 Amount: <b>${trade_amount_usd:.2f}</b>\n"
                    f"💵 Profit: <b>${pnl:.2f}</b>\n"
                    f"💰 Balance: <b>{bal_text}</b>"
                )
            except Exception as e:
                print(f"   ⚠️ Notification failed: {e}")