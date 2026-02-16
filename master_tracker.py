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
import base64
import ccxt
import logging
from urllib.parse import urlencode
from queue import Queue
from datetime import datetime
from collections import OrderedDict
from dotenv import load_dotenv
from telegram import Bot

from worker import TradeCopier

logging.basicConfig(level=logging.ERROR)
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
event_queue = Queue()


# ── bingx listener ──

def start_bingx_listener():
    key = os.getenv("BINGX_MASTER_KEY")
    secret = os.getenv("BINGX_MASTER_SECRET")
    if not key or len(key) < 10 or not secret:
        print("ℹ️ BingX Listener skipped (no key)")
        return

    print("🎧 Starting BingX Listener...")

    def get_listen_key():
        try:
            path = "/openApi/swap/v2/user/auth/userDataStream"
            base_url = "https://open-api.bingx.com"
            timestamp = int(time.time() * 1000)
            params = {"timestamp": timestamp}
            query_string = urlencode(sorted(params.items()))
            signature = hmac.new(secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()

            resp = requests.post(
                f"{base_url}{path}?{query_string}&signature={signature}",
                headers={"X-BX-APIKEY": key}, timeout=5
            )
            if resp.status_code != 200: return None

            data = resp.json()
            return data['data']['listenKey'] if data.get('code') == 0 else None
        except Exception as e:
            print(f"❌ BingX Request Error: {repr(e)}")
            return None

    def on_message(ws, message):
        try:
            if isinstance(message, bytes):
                with gzip.GzipFile(fileobj=io.BytesIO(message)) as f:
                    message = f.read().decode()

            msg = json.loads(message)

            if "ping" in msg:
                ws.send(json.dumps({"pong": msg["ping"]}))
                return
            if message == "Ping":
                ws.send("Pong")
                return
            if msg.get("e") == "listenKeyExpired":
                print("⚠️ BingX listenKey expired, reconnecting...")
                ws.close()
                return

            if msg.get("dataType") != "ORDER_UPDATE": return
            order = msg.get("data", {})
            if order.get("status") not in ["FILLED", "PARTIALLY_FILLED"]: return

            symbol = order["symbol"].replace("-", "").replace("VST", "USDT")
            raw_type = order.get("orderType", "LIMIT")
            orig_type = "STOP_MARKET" if "STOP" in raw_type or "TAKE" in raw_type else ("MARKET" if raw_type == "MARKET" else "LIMIT")

            from database import record_master_order
            master_order_id = record_master_order(
                master_exchange='bingx', symbol=symbol, side=order["side"],
                order_type=orig_type,
                price=float(order.get("avgPrice") or order.get("price") or 0),
                quantity=float(order["orderQty"]), strategy='ratner'
            )

            event_queue.put({
                "master_order_id": master_order_id,
                "master_exchange": "bingx", "s": symbol, "S": order["side"],
                "o": raw_type, "X": order.get("status"),
                "q": float(order["orderQty"]),
                "p": float(order.get("price") or 0),
                "ap": float(order.get("avgPrice") or 0),
                "ot": orig_type, "strategy": "ratner",
                "ro": order.get("reduceOnly", False)
            })
            print(f"🚀 BingX Signal: {symbol}")
        except: pass

    def on_error(ws, error): print(f"❌ BingX WS Error: {error}")
    def on_close(ws, code, msg): print(f"⚠️ BingX WS Closed: {code} {msg}")
    def on_open(ws): print("✅ BingX WS connected")

    while True:
        listen_key = get_listen_key()
        if not listen_key:
            time.sleep(5)
            continue

        ws_url = f"wss://open-api-swap.bingx.com/swap-market?listenKey={listen_key}"
        stop_extend = threading.Event()

        def auto_extend():
            while not stop_extend.is_set():
                time.sleep(30 * 60)
                if stop_extend.is_set(): break
                try:
                    path = "/openApi/swap/v2/user/auth/userDataStream"
                    base_url = "https://open-api.bingx.com"
                    timestamp = int(time.time() * 1000)
                    params = {"timestamp": timestamp, "listenKey": listen_key}
                    query = urlencode(sorted(params.items()))
                    sig = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
                    requests.put(f"{base_url}{path}?{query}&signature={sig}", headers={"X-BX-APIKEY": key}, timeout=5)
                except: pass

        threading.Thread(target=auto_extend, daemon=True).start()

        ws = websocket.WebSocketApp(ws_url, on_message=on_message, on_error=on_error, on_close=on_close, on_open=on_open)
        ws.run_forever()

        stop_extend.set()
        print("♻️ Reconnecting BingX in 5 sec...")
        time.sleep(5)


# ── okx listener ──

def start_okx_listener():
    key = os.getenv("OKX_MASTER_KEY")
    secret = os.getenv("OKX_MASTER_SECRET")
    password = os.getenv("OKX_MASTER_PASSWORD")

    if not key:
        print("ℹ️ OKX Listener skipped (no keys)")
        return

    print("🎧 OKX Listener: WEBSOCKET REAL-TIME")

    try:
        okx = ccxt.okx({
            'apiKey': key, 'secret': secret, 'password': password,
            'options': {'defaultType': 'spot'}
        })
    except Exception as e:
        print(f"❌ OKX Init Error: {e}")
        return

    processed_order_ids = OrderedDict()
    last_disconnect_time = [None]

    def get_ws_auth():
        timestamp = str(int(time.time()))
        message = timestamp + 'GET' + '/users/self/verify'
        signature = base64.b64encode(
            hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
        ).decode()
        return {"op": "login", "args": [{"apiKey": key, "passphrase": password, "timestamp": timestamp, "sign": signature}]}

    def on_message(ws, message):
        try:
            if message == 'pong': return

            msg = json.loads(message)

            if msg.get('event') == 'login':
                if msg.get('code') == '0':
                    print("✅ OKX WebSocket: Authenticated!")
                    ws.send(json.dumps({"op": "subscribe", "args": [{"channel": "orders", "instType": "SPOT"}]}))
                else:
                    print(f"❌ OKX Login Failed: {msg}")
                return

            if msg.get('event') == 'subscribe':
                print("✅ OKX: Subscribed to orders channel")
                return

            if msg.get('arg', {}).get('channel') != 'orders' or 'data' not in msg: return

            for order in msg['data']:
                if order.get('state') not in ['filled', 'partially_filled']: continue

                order_id = order.get('ordId')
                if order_id in processed_order_ids: continue

                # dedup — keep last 2000 ids
                processed_order_ids[order_id] = time.time()
                while len(processed_order_ids) > 2000:
                    processed_order_ids.popitem(last=False)

                symbol = order['instId'].replace('-', '/')
                side = order['side']
                filled_qty = float(order['accFillSz'])
                avg_price = float(order['avgPx']) if order['avgPx'] else float(order['px'])
                trade_usd = filled_qty * avg_price

                fill_time = int(order['fillTime']) / 1000 if order.get('fillTime') else time.time()
                dt = datetime.fromtimestamp(fill_time).strftime("%d.%m.%Y %H:%M:%S")
                print(f"\n🔔 OKX WS: {dt} | {symbol} | {side.upper()} | ${trade_usd:.2f}")

                from database import record_master_order, update_master_position, get_master_position
                master_order_id = record_master_order(
                    master_exchange='okx', symbol=symbol, side=side,
                    order_type='spot_trade', price=avg_price,
                    quantity=filled_qty, strategy='cgt'
                )

                # track master position for partial sell ratios
                sell_ratio = 1.0
                if side == 'buy':
                    update_master_position(symbol, 'cgt', filled_qty)
                    print(f"   📈 Master +{filled_qty} {symbol}")
                elif side == 'sell':
                    current_qty = get_master_position(symbol, 'cgt')
                    if current_qty > 0:
                        sell_ratio = min(filled_qty / current_qty, 1.0)
                        print(f"   📉 Master sell: {filled_qty}/{current_qty} = {sell_ratio*100:.1f}%")
                    update_master_position(symbol, 'cgt', -filled_qty)

                event_queue.put({
                    'master_order_id': master_order_id,
                    'master_exchange': 'okx', 'strategy': 'cgt',
                    's': symbol, 'S': side.upper(),
                    'o': 'MARKET', 'X': 'FILLED',
                    'q': filled_qty, 'p': avg_price, 'ap': avg_price,
                    'ot': 'SPOT', 'ro': False, 'ratio': sell_ratio
                })

        except Exception as e:
            print(f"⚠️ OKX WS Parse Error: {e}")

    def on_error(ws, error): print(f"❌ OKX WS Error: {error}")

    def on_close(ws, close_code, close_msg):
        print(f"⚠️ OKX WS Closed: {close_code} {close_msg}")
        last_disconnect_time[0] = time.time()

    def on_open(ws):
        print("🔗 OKX WebSocket Connected. Authenticating...")
        ws.send(json.dumps(get_ws_auth()))

        def ping_loop():
            failures = 0
            while True:
                time.sleep(15)
                try:
                    ws.send('ping')
                    failures = 0
                except Exception as e:
                    failures += 1
                    print(f"⚠️ OKX Ping failed ({failures}x): {e}")
                    if failures >= 3:
                        print("❌ OKX Ping failed 3x, closing for reconnect")
                        try: ws.close()
                        except: pass
                        break

        threading.Thread(target=ping_loop, daemon=True).start()

    def check_missed_orders():
        """after reconnect, check REST API for orders missed during downtime"""
        if last_disconnect_time[0] is None: return

        gap = time.time() - last_disconnect_time[0]
        if gap < 3: return

        print(f"🔍 [RECOVERY] Checking missed orders (gap: {gap:.0f}s)...")
        try:
            recent = okx.fetch_orders(
                symbol=None,
                since=int((last_disconnect_time[0] - 5) * 1000),
                limit=50,
                params={'instType': 'SPOT', 'state': 'filled'}
            )

            recovered = 0
            for order in recent:
                oid = order.get('id')
                if not oid or oid in processed_order_ids: continue

                symbol = order['symbol']
                side = order['side']
                filled_qty = float(order['filled'])
                avg_price = float(order['average']) if order['average'] else float(order['price'])
                if filled_qty <= 0: continue

                dt = datetime.fromtimestamp(order['timestamp'] / 1000).strftime("%d.%m.%Y %H:%M:%S")
                print(f"\n🔄 [RECOVERED] OKX: {dt} | {symbol} | {side.upper()} | ${filled_qty * avg_price:.2f}")

                processed_order_ids[oid] = time.time()

                from database import record_master_order, update_master_position, get_master_position
                master_order_id = record_master_order(
                    master_exchange='okx', symbol=symbol, side=side,
                    order_type='spot_trade', price=avg_price,
                    quantity=filled_qty, strategy='cgt'
                )

                sell_ratio = 1.0
                if side == 'buy':
                    update_master_position(symbol, 'cgt', filled_qty)
                elif side == 'sell':
                    current_qty = get_master_position(symbol, 'cgt')
                    if current_qty > 0:
                        sell_ratio = min(filled_qty / current_qty, 1.0)
                    update_master_position(symbol, 'cgt', -filled_qty)

                event_queue.put({
                    'master_order_id': master_order_id,
                    'master_exchange': 'okx', 'strategy': 'cgt',
                    's': symbol, 'S': side.upper(),
                    'o': 'MARKET', 'X': 'FILLED',
                    'q': filled_qty, 'p': avg_price, 'ap': avg_price,
                    'ot': 'SPOT', 'ro': False, 'ratio': sell_ratio
                })
                recovered += 1

            print(f"✅ [RECOVERY] {'Recovered ' + str(recovered) + ' order(s)' if recovered else 'No missed orders'}")
        except Exception as e:
            print(f"⚠️ [RECOVERY] REST check failed: {e}")

    # main reconnect loop
    while True:
        try:
            ws = websocket.WebSocketApp(
                "wss://ws.okx.com:8443/ws/v5/private",
                on_message=on_message, on_error=on_error,
                on_close=on_close, on_open=on_open
            )
            ws.run_forever(ping_interval=20, ping_timeout=10)
        except Exception as e:
            print(f"❌ OKX WS Exception: {e}")

        print("♻️ Reconnecting OKX in 2 sec...")
        time.sleep(2)

        try: check_missed_orders()
        except Exception as e: print(f"⚠️ Recovery error: {e}")


# ── main ──

def main():
    print("\n--- [Master Tracker] Started ---")
    if not TELEGRAM_TOKEN: return

    bot = Bot(token=TELEGRAM_TOKEN)
    copier = TradeCopier(bot_instance=bot)

    threading.Thread(target=copier.start_consuming, args=(event_queue,), daemon=True).start()
    print("✅ Worker Thread: RUNNING")

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