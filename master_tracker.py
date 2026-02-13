
import time
import os
import json
import threading
import requests
import websocket
import hmac
import hashlib
import gzip
import io
from urllib.parse import urlencode
from queue import Queue
from datetime import datetime
from dotenv import load_dotenv
from telegram import Bot
import ccxt 

# --- Библиотеки бирж ---
# from binance.um_futures import UMFutures
# from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient
# from pybit.unified_trading import WebSocket as BybitWS

# --- Наш Воркер ---
from worker import TradeCopier

import logging
logging.basicConfig(level=logging.ERROR)
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
event_queue = Queue()

def start_binance_listener():
    key = os.getenv("BINANCE_MASTER_KEY")
    secret = os.getenv("BINANCE_MASTER_SECRET")
    if not key or len(key) < 10: return

    print("🎧 Starting Binance Listener (REAL)...")

    def on_message(_, message):
        try:
            if isinstance(message, str): message = json.loads(message)
            if message.get('e') == 'ORDER_TRADE_UPDATE':
                order_data = message.get('o', {})
                order_data['master_exchange'] = 'binance'
                order_data['ro'] = order_data.get('R', False) 
                event_queue.put(order_data)
        except: pass

    while True:
        try:
            # 1. REST CLIENT (Боевой URL)
            # base_url="https://fapi.binance.com" - это основной адрес фьючерсов
            client = UMFutures(key=key, secret=secret, base_url="https://fapi.binance.com")
            
            listen_key = client.new_listen_key()["listenKey"]
            print(f"✅ Binance Connected (REAL).")
            
            # 2. WEBSOCKET CLIENT (Боевой URL)
            # wss://fstream.binance.com/ws - это боевой стрим
            ws = UMFuturesWebsocketClient(on_message=on_message, stream_url="wss://fstream.binance.com/ws")
            
            ws.user_data(listen_key=listen_key)
            time.sleep(50 * 60) 
            ws.stop()
        except Exception as e:
            print(f"❌ Binance Listener Error: {e}. Retry in 10s...")
            time.sleep(10)



# ==========================================
# 2. СЛУШАТЕЛЬ BYBIT
# ==========================================
def start_bybit_listener():
    key = os.getenv("BYBIT_MASTER_KEY")
    secret = os.getenv("BYBIT_MASTER_SECRET")
    if not key or len(key) < 10 or "..." in key: return

    print("🎧 Starting Bybit Listener...")

    def on_message(message):
        try:
            data = message.get('data', [])
            for order in data:
                if order.get('orderStatus') in ['Filled', 'PartiallyFilled']:
                    norm = {
                        'master_exchange': 'bybit',
                        's': order['symbol'],
                        'S': order['side'].upper(),
                        'o': order['orderType'].upper(),
                        'X': 'FILLED',
                        'q': float(order['qty']),
                        'p': float(order['price'] or 0),
                        'ap': float(order['avgPrice'] or 0),
                        'ro': order.get('reduceOnly', False),
                        'ot': 'LIMIT'
                    }
                    if order.get('stopOrderType'): norm['ot'] = 'STOP_MARKET'
                    event_queue.put(norm)
                    print(f"🚀 Bybit Signal: {order['symbol']}")
        except: pass

    while True:
        try:
            ws = BybitWS(testnet=False, channel_type="private", api_key=key, api_secret=secret)
            ws.order_stream(callback=on_message)
            print("✅ Bybit Connected.")
            while True: time.sleep(60)
        except Exception as e:
            print(f"❌ Bybit Error: {e}. Retry in 10s...")
            time.sleep(10)

# ==========================================
# 3. СЛУШАТЕЛЬ BINGX (ETALON)
# ==========================================
def start_bingx_listener():
    key = os.getenv("BINGX_MASTER_KEY")
    secret = os.getenv("BINGX_MASTER_SECRET")
    if not key or len(key) < 10 or not secret:
        print("ℹ️ BingX Listener skipped (No key).")
        return

    print("🎧 Starting BingX Listener...")

    def get_listen_key():
        """Получение ListenKey через REST API (Swap V2) - С ПОДПИСЬЮ."""
        try:
            # Correct Swap V2 Endpoint
            path = "/openApi/swap/v2/user/auth/userDataStream"
            base_url = "https://open-api.bingx.com"
            url = base_url + path
            
            # 1. Signature Params
            timestamp = int(time.time() * 1000)
            params = {"timestamp": timestamp}
            
            # 2. Sign
            query_string = urlencode(sorted(params.items()))
            signature = hmac.new(
                secret.encode("utf-8"),
                query_string.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()
            
            final_url = f"{url}?{query_string}&signature={signature}"
            
            headers = {"X-BX-APIKEY": key}
            
            # POST request
            response = requests.post(final_url, headers=headers, timeout=5)
            
            if response.status_code != 200:
                print(f"❌ BingX Auth Failed: {response.status_code} - {response.text}")
                return None
                
            data = response.json()
            
            if data.get('code') == 0:
                return data['data']['listenKey']
            
            # print(f"❌ BingX ListenKey Error: {data}")
            return None

        except Exception as e:
            print(f"❌ BingX Request Error: {repr(e)}")
            return None

    def on_message(ws, message):
        try:
            if isinstance(message, bytes):
                with gzip.GzipFile(fileobj=io.BytesIO(message)) as f:
                    message = f.read().decode()

            msg = json.loads(message)

            # 1. PING/PONG (BingX specific)
            if "ping" in msg:
                ws.send(json.dumps({"pong": msg["ping"]}))
                return
            
            # Simple Pong check (sometimes needed)
            if message == "Ping":
                ws.send("Pong")
                return

            # ListenKey Expiry
            if msg.get("e") == "listenKeyExpired":
                print("⚠️ BingX listenKey expired. Reconnecting...")
                ws.close()
                return

            # 2. EVENT PARSING (BingX Futures)
            if msg.get("dataType") == "ORDER_UPDATE":
                order = msg.get("data", {})
                status = order.get("status")

                if status in ["FILLED", "PARTIALLY_FILLED"]:
                    # Normalize Symbol
                    symbol = order["symbol"].replace("-", "").replace("VST", "USDT")
                    
                    # Normalize Side/Type
                    side = order["side"]
                    raw_type = order.get("orderType", "LIMIT")
                    
                    # Determine Original Type
                    orig_type = "LIMIT"
                    if "STOP" in raw_type or "TAKE" in raw_type:
                        orig_type = "STOP_MARKET"
                    elif raw_type == "MARKET":
                         orig_type = "MARKET"
                    
                    # RECORD MASTER ORDER (INVESTIGATION SYSTEM)
                    from database import record_master_order
                    master_order_id = record_master_order(
                        master_exchange='bingx',
                        symbol=symbol,
                        side=side,
                        order_type=orig_type,
                        price=float(order.get("avgPrice") or order.get("price") or 0),
                        quantity=float(order["orderQty"]),
                        strategy='ratner'
                    )

                    event_queue.put({
                        "master_order_id": master_order_id,  # NEW: Pass ID to worker
                        "master_exchange": "bingx",
                        "s": symbol,
                        "S": side,
                        "o": raw_type,
                        "X": status,
                        "q": float(order["orderQty"]),
                        "p": float(order.get("price") or 0),
                        "ap": float(order.get("avgPrice") or 0),
                        "ot": orig_type,
                        "strategy": "ratner", # Defined strategy for BingX Futures
                        'ro': order.get('reduceOnly', False)
                    })
                    print(f"🚀 BingX Signal: {symbol} ({status})")

        except Exception as e:
            # print("BingX Parse Error:", e)
            pass

    def on_error(ws, error):
        print(f"❌ BingX WS Error: {error}")
        
    def on_close(ws, code, msg):
        print(f"⚠️ BingX WS Closed: {code} {msg}")
    def on_open(ws):
        print("✅ BingX WS connected (listenKey OK)")
        # Subscribe to order updates
        sub_msg = {
            "id": "sub-1",
            "reqType": "sub",
            "dataType": "listenKey" # BingX V2 Swap specific subscription? Or seemingly auto-subscribed?
            # Actually, attaching listenKey to URL is enough for User Data Stream.
            # But docs often say "Subscribe". For User Data, URL parameter is usually sufficient.
            # We'll stick to URL param + Ping/Pong for now as per user instruction.
        }

    while True:
        listen_key = get_listen_key()
        if not listen_key:
            time.sleep(5)
            continue

        # Authenticated WS URL (Standard)
        ws_url = f"wss://open-api-swap.bingx.com/swap-market?listenKey={listen_key}"
        
        # Событие для остановки авто-продления
        stop_extend = threading.Event()

        def auto_extend():
            while not stop_extend.is_set():
                time.sleep(30 * 60) # 30 минут
                if stop_extend.is_set(): break
                try:
                    # EXTEND KEY (PUT) - ALSO SIGNED
                    path = "/openApi/swap/v2/user/auth/userDataStream"
                    base_url = "https://open-api.bingx.com"
                    url = base_url + path
                    
                    timestamp = int(time.time() * 1000)
                    params = {
                        "timestamp": timestamp,
                        "listenKey": listen_key
                    }
                    
                    query = urlencode(sorted(params.items()))
                    signature = hmac.new(
                        secret.encode("utf-8"),
                        query.encode("utf-8"),
                        hashlib.sha256
                    ).hexdigest()
                    
                    final_url = f"{url}?{query}&signature={signature}"
                    
                    requests.put(final_url, headers={"X-BX-APIKEY": key}, timeout=5)
                    # print("♻️ BingX Key Extended")
                except: pass

        # Запускаем продление ключа
        threading.Thread(target=auto_extend, daemon=True).start()

        ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open,
        )
        
        ws.run_forever()
        
        # Останавливаем продление при разрыве соединения
        stop_extend.set()
        
        print("♻️ Reconnecting BingX in 5 sec...")
        time.sleep(5)

# ==========================================
# 4. СЛУШАТЕЛЬ OKX (SPOT - WEBSOCKET REAL-TIME)
# ==========================================
def start_okx_listener():
    key = os.getenv("OKX_MASTER_KEY")
    secret = os.getenv("OKX_MASTER_SECRET")
    password = os.getenv("OKX_MASTER_PASSWORD")
    
    if not key: 
        print("ℹ️ OKX Listener skipped (No keys).")
        return

    print("🎧 OKX Listener: WEBSOCKET REAL-TIME (<500ms latency)")

    try:
        okx = ccxt.okx({
            'apiKey': key,
            'secret': secret,
            'password': password,
            'options': {'defaultType': 'spot'}
        })
    except Exception as e:
        print(f"❌ OKX Init Error: {e}")
        return

    # OKX требует timestamp в секундах для подписи
    import base64
    from collections import OrderedDict
    
    # Track processed order IDs to prevent duplicates (ordered for FIFO eviction)
    processed_order_ids = OrderedDict()
    
    # Track last disconnect time for REST API fallback
    last_disconnect_time = [None]  # mutable container for closure
    
    def get_ws_auth():
        """Генерирует подпись для WebSocket аутентификации"""
        timestamp = str(int(time.time()))
        method = 'GET'
        request_path = '/users/self/verify'
        
        # Подпись: timestamp + method + requestPath
        message = timestamp + method + request_path
        mac = hmac.new(
            secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        )
        signature = base64.b64encode(mac.digest()).decode()
        
        return {
            "op": "login",
            "args": [{
                "apiKey": key,
                "passphrase": password,
                "timestamp": timestamp,
                "sign": signature
            }]
        }

    def on_message(ws, message):
        try:
            # PING/PONG heartbeat (OKX требует ping каждые 25 сек)
            if message == 'pong':
                # print("[DEBUG] OKX: pong received")
                return
            
            msg = json.loads(message)
            
            # 1. Логин успешен
            if msg.get('event') == 'login':
                if msg.get('code') == '0':
                    print("✅ OKX WebSocket: Authenticated!")
                    # Подписываемся на ордера
                    ws.send(json.dumps({
                        "op": "subscribe",
                        "args": [{
                            "channel": "orders",
                            "instType": "SPOT"
                        }]
                    }))
                else:
                    print(f"❌ OKX Login Failed: {msg}")
                return
            
            # 2. Подписка подтверждена
            if msg.get('event') == 'subscribe':
                print(f"✅ OKX: Subscribed to orders channel")
                return
            
            # 3. ORDER DATA (main!)
            if msg.get('arg', {}).get('channel') == 'orders' and 'data' in msg:
                for order in msg['data']:
                    state = order.get('state')
                    order_id = order.get('ordId')  # Unique order ID
                    
                    # Only filled orders
                    if state in ['filled', 'partially_filled']:
                        # DEDUPLICATION CHECK
                        if order_id in processed_order_ids:
                            # print(f"   ⏭ Skipping duplicate order {order_id}")
                            continue
                        
                        # Mark as processed (OrderedDict for FIFO eviction)
                        processed_order_ids[order_id] = time.time()
                        
                        # Keep only last 2000 IDs, evict OLDEST first
                        while len(processed_order_ids) > 2000:
                            processed_order_ids.popitem(last=False)
                        
                        symbol = order['instId'].replace('-', '/')  # BTC-USDT -> BTC/USDT
                        side = order['side']  # buy/sell
                        filled_qty = float(order['accFillSz'])  # Accumulated fill size
                        avg_price = float(order['avgPx']) if order['avgPx'] else float(order['px'])
                        trade_usd = filled_qty * avg_price
                        
                        # Time
                        fill_time = int(order['fillTime']) / 1000 if order.get('fillTime') else time.time()
                        dt = datetime.fromtimestamp(fill_time).strftime("%d.%m.%Y %H:%M:%S")
                        
                        print(f"\n🔔 OKX WEBSOCKET: {dt} | {symbol} | {side.upper()} | ${trade_usd:.2f}")
                        
                        # RECORD MASTER ORDER (INVESTIGATION SYSTEM)
                        from database import record_master_order
                        master_order_id = record_master_order(
                            master_exchange='okx',
                            symbol=symbol,
                            side=side,
                            order_type='spot_trade',
                            price=avg_price,
                            quantity=filled_qty,
                            strategy='cgt'
                        )
                        
                        # --- MASTER POSITION TRACKING (PARTIAL SELLS) ---
                        from database import update_master_position, get_master_position
                        
                        sell_ratio = 1.0 # Default to 100% (Safety)
                        
                        if side == 'buy':
                            # Increase Master Position
                            update_master_position(symbol, 'cgt', filled_qty)
                            print(f"   📈 Master Position INC: +{filled_qty} {symbol}")
                            
                        elif side == 'sell':
                            # Calculate Ratio BEFORE updating DB
                            current_master_qty = get_master_position(symbol, 'cgt')
                            
                            if current_master_qty > 0:
                                # Ratio = Amount Sold / Total Held
                                # Example: Held 10, Sell 5 -> Ratio 0.5 (50%)
                                sell_ratio = filled_qty / current_master_qty
                                if sell_ratio > 1.0: sell_ratio = 1.0 # Cap at 100%
                                print(f"   📉 Master Partial Sell: {filled_qty} / {current_master_qty} = {sell_ratio*100:.1f}%")
                            else:
                                print(f"   ⚠️ Master Sell (Cold Start): Pos 0, defaulting to 100%")
                                sell_ratio = 1.0
                            
                            # Decrease Master Position
                            update_master_position(symbol, 'cgt', -filled_qty)
                        
                        # Send to worker queue
                        event_queue.put({
                            'master_order_id': master_order_id,
                            'master_exchange': 'okx',
                            'strategy': 'cgt',
                            's': symbol,
                            'S': side.upper(),
                            'o': 'MARKET',
                            'X': 'FILLED',
                            'q': filled_qty,
                            'p': avg_price,
                            'ap': avg_price,
                            'ot': 'SPOT',
                            'ro': False,
                            'ratio': sell_ratio # <--- NEW FIELD
                        })
        
        except Exception as e:
            print(f"⚠️ OKX WS Parse Error: {e}")

    def on_error(ws, error):
        print(f"❌ OKX WS Error: {error}")

    def on_close(ws, close_code, close_msg):
        print(f"⚠️ OKX WS Closed: {close_code} {close_msg}")
        last_disconnect_time[0] = time.time()

    def on_open(ws):
        print("🔗 OKX WebSocket Connected. Authenticating...")
        auth_msg = get_ws_auth()
        ws.send(json.dumps(auth_msg))
        
        # OKX-level text 'ping' every 15s — in ADDITION to native WebSocket ping frames
        # OKX docs: "send 'ping' if no message within 30s, server replies 'pong'"
        def ping_loop():
            consecutive_failures = 0
            while True:
                time.sleep(15)  # Every 15s (OKX timeout is 30s, so 15s gives safe margin)
                try:
                    ws.send('ping')
                    consecutive_failures = 0
                except Exception as e:
                    consecutive_failures += 1
                    print(f"⚠️ OKX Ping failed ({consecutive_failures}x): {e}")
                    if consecutive_failures >= 3:
                        print("❌ OKX Ping failed 3x, closing WS for reconnect...")
                        try:
                            ws.close()
                        except:
                            pass
                        break
        
        threading.Thread(target=ping_loop, daemon=True).start()
    
    def check_missed_orders_after_reconnect():
        """After reconnect, use REST API to check recent orders and process any missed ones."""
        if last_disconnect_time[0] is None:
            return
        
        gap_seconds = time.time() - last_disconnect_time[0]
        if gap_seconds < 3:
            return  # Very short gap, likely no missed orders
        
        print(f"🔍 [RECOVERY] Checking missed orders (gap: {gap_seconds:.0f}s)...")
        
        try:
            # Fetch recent filled orders from OKX REST API
            recent_orders = okx.fetch_orders(
                symbol=None,  # All symbols
                since=int((last_disconnect_time[0] - 5) * 1000),  # 5s buffer before disconnect
                limit=50,
                params={'instType': 'SPOT', 'state': 'filled'}
            )
            
            recovered = 0
            for order in recent_orders:
                order_id = order.get('id')
                if order_id and order_id not in processed_order_ids:
                    # This order was missed!
                    symbol = order['symbol']  # Already in 'BTC/USDT' format from ccxt
                    side = order['side']  # 'buy' or 'sell'
                    filled_qty = float(order['filled'])
                    avg_price = float(order['average']) if order['average'] else float(order['price'])
                    
                    if filled_qty <= 0:
                        continue
                    
                    trade_usd = filled_qty * avg_price
                    dt = datetime.fromtimestamp(order['timestamp'] / 1000).strftime("%d.%m.%Y %H:%M:%S")
                    
                    print(f"\n🔄 [RECOVERED] OKX: {dt} | {symbol} | {side.upper()} | ${trade_usd:.2f}")
                    
                    # Mark as processed
                    processed_order_ids[order_id] = time.time()
                    
                    # Record master order
                    from database import record_master_order
                    master_order_id = record_master_order(
                        master_exchange='okx',
                        symbol=symbol,
                        side=side,
                        order_type='spot_trade',
                        price=avg_price,
                        quantity=filled_qty,
                        strategy='cgt'
                    )
                    
                    # Master position tracking
                    from database import update_master_position, get_master_position
                    sell_ratio = 1.0
                    
                    if side == 'buy':
                        update_master_position(symbol, 'cgt', filled_qty)
                        print(f"   📈 [RECOVERED] Master Position INC: +{filled_qty} {symbol}")
                    elif side == 'sell':
                        current_master_qty = get_master_position(symbol, 'cgt')
                        if current_master_qty > 0:
                            sell_ratio = min(filled_qty / current_master_qty, 1.0)
                            print(f"   📉 [RECOVERED] Partial Sell: {filled_qty}/{current_master_qty} = {sell_ratio*100:.1f}%")
                        update_master_position(symbol, 'cgt', -filled_qty)
                    
                    # Send to worker queue
                    event_queue.put({
                        'master_order_id': master_order_id,
                        'master_exchange': 'okx',
                        'strategy': 'cgt',
                        's': symbol,
                        'S': side.upper(),
                        'o': 'MARKET',
                        'X': 'FILLED',
                        'q': filled_qty,
                        'p': avg_price,
                        'ap': avg_price,
                        'ot': 'SPOT',
                        'ro': False,
                        'ratio': sell_ratio
                    })
                    recovered += 1
            
            if recovered > 0:
                print(f"✅ [RECOVERY] Recovered {recovered} missed order(s)!")
            else:
                print(f"✅ [RECOVERY] No missed orders found.")
                
        except Exception as e:
            print(f"⚠️ [RECOVERY] REST API check failed: {e}")

    # Главный цикл с автореконнектом
    while True:
        try:
            ws = websocket.WebSocketApp(
                "wss://ws.okx.com:8443/ws/v5/private",
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            
            # Native WebSocket ping frames every 20s (OKX timeout = 30s)
            # This is IN ADDITION to the OKX text 'ping' in ping_loop
            ws.run_forever(ping_interval=20, ping_timeout=10)
            
        except Exception as e:
            print(f"❌ OKX WS Exception: {e}")
        
        print("♻️ Reconnecting OKX WebSocket in 2 sec...")
        time.sleep(2)
        
        # After reconnect, check for any missed orders via REST API
        try:
            check_missed_orders_after_reconnect()
        except Exception as e:
            print(f"⚠️ Recovery check error: {e}")


# ==========================================
# MAIN
# ==========================================
def main():
    print("\n--- [Master Tracker: MULTI-EXCHANGE HUB] Started ---")
    if not TELEGRAM_TOKEN: return
    
    bot = Bot(token=TELEGRAM_TOKEN)
    copier = TradeCopier(bot_instance=bot)

    threading.Thread(target=copier.start_consuming, args=(event_queue,), daemon=True).start()
    print("✅ Worker Thread: RUNNING")

    # threading.Thread(target=start_binance_listener, daemon=True).start()
    
    # if os.getenv("BYBIT_MASTER_KEY") and len(os.getenv("BYBIT_MASTER_KEY")) > 10:
    #     threading.Thread(target=start_bybit_listener, daemon=True).start()
        
    if os.getenv("BINGX_MASTER_KEY") and len(os.getenv("BINGX_MASTER_KEY")) > 10:
        threading.Thread(target=start_bingx_listener, daemon=True).start()

    if os.getenv("OKX_MASTER_KEY") and len(os.getenv("OKX_MASTER_KEY")) > 10:
        threading.Thread(target=start_okx_listener, daemon=True).start()

    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopped.")

if __name__ == "__main__":
    main()