
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
from dotenv import load_dotenv
from telegram import Bot

# --- Библиотеки бирж ---
from binance.um_futures import UMFutures
from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient
from pybit.unified_trading import WebSocket as BybitWS

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
    if not key or len(key) < 10:
        print("ℹ️ BingX Listener skipped (No key).")
        return

    print("🎧 Starting BingX Listener...")

    def get_listen_key():
        try:
            url = "https://open-api.bingx.com/openApi/user/auth/userDataStream"
            headers = {"X-BX-APIKEY": key}
            # Таймаут 5 сек, чтобы не виснуть
            response = requests.post(url, headers=headers, timeout=5)
            data = response.json()
            if "listenKey" in data: return data["listenKey"]
            print("❌ BingX listenKey Error:", data)
            return None
        except Exception as e:
            print("❌ BingX listenKey request error:", e)
            return None

    def on_message(ws, message):
        try:

            if isinstance(message, bytes):
                with gzip.GzipFile(fileobj=io.BytesIO(message)) as f:
                    message = f.read().decode()

            if message == "Ping":
                ws.send("Pong")
                return

            msg = json.loads(message)

            # Обработка истечения ключа
            if msg.get("e") == "listenKeyExpired":
                print("⚠️ BingX listenKey expired. Reconnecting...")
                ws.close()
                return

            if msg.get("e") == "ORDER_TRADE_UPDATE":
                order = msg.get("o", {})
                status = order.get("X")
                
                if status in ["FILLED", "PARTIALLY_FILLED"]:
                    # Нормализация символа (VST -> USDT)
                    symbol = order["s"].replace("-", "").replace("VST", "USDT")
                    
                    # Определение типа ордера (STOP/TAKE)
                    raw_type = order.get("o", "")
                    orig_type = "LIMIT"
                    if "STOP" in raw_type or "TAKE" in raw_type:
                        orig_type = "STOP_MARKET"

                    event_queue.put({
                        "master_exchange": "bingx",
                        "s": symbol,
                        "S": order["S"],
                        "o": raw_type,
                        "X": status, # Передаем реальный статус
                        "q": float(order["q"]),
                        "p": float(order.get("p", 0)),
                        "ap": float(order.get("ap") or order.get("p") or 0),
                        "ot": orig_type
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

    while True:
        listen_key = get_listen_key()
        if not listen_key:
            time.sleep(5)
            continue

        ws_url = f"wss://open-api-swap.bingx.com/swap-market?listenKey={listen_key}"
        
        # Событие для остановки авто-продления
        stop_extend = threading.Event()

        def auto_extend():
            while not stop_extend.is_set():
                time.sleep(30 * 60) # 30 минут
                if stop_extend.is_set(): break
                try:
                    requests.put(
                        "https://open-api.bingx.com/openApi/user/auth/userDataStream",
                        params={"listenKey": listen_key},
                        headers={"X-BX-APIKEY": key},
                        timeout=5
                    )
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
# 4. СЛУШАТЕЛЬ OKX (SPOT POLLING)
# ==========================================
def start_okx_listener():
    key = os.getenv("OKX_MASTER_KEY")
    secret = os.getenv("OKX_MASTER_SECRET")
    password = os.getenv("OKX_MASTER_PASSWORD")
    
    if not key: 
        print("ℹ️ OKX Listener skipped (No keys).")
        return

    print("🎧 Starting OKX Listener (Spot)...")

    # Инициализация CCXT
    okx = ccxt.okx({
        'apiKey': key,
        'secret': secret,
        'password': password,
        'options': {'defaultType': 'spot'}
    })

    last_processed_ids = set()

    while True:
        try:
            # Опрашиваем последние сделки/ордера каждые 2 секунды
            # fetch_open_orders или fetch_closed_orders
            orders = okx.fetch_orders(limit=5) 
            
            for order in orders:
                oid = order['id']
                # Если ордер новый и исполнен
                if order['status'] == 'closed' and oid not in last_processed_ids:
                    last_processed_ids.add(oid)
                    
                    # Чтобы список не рос бесконечно
                    if len(last_processed_ids) > 100: last_processed_ids.clear()

                    # Нормализация
                    event_queue.put({
                        'master_exchange': 'okx', # Метка биржи
                        's': order['symbol'],     # ETH/USDT
                        'S': order['side'].upper(), # BUY/SELL
                        'o': 'MARKET',            # Spot обычно маркет
                        'X': 'FILLED',
                        'q': float(order['amount']),
                        'p': float(order['average'] or order['price'] or 0),
                        'ap': float(order['average'] or 0),
                        'ot': 'SPOT'              # Метка типа
                    })
                    print(f"🚀 OKX Signal: {order['side']} {order['symbol']}")

            time.sleep(2) # Пауза между опросами

        except Exception as e:
            print(f"❌ OKX Error: {e}")
            time.sleep(5)

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

    threading.Thread(target=start_binance_listener, daemon=True).start()
    
    if os.getenv("BYBIT_MASTER_KEY") and len(os.getenv("BYBIT_MASTER_KEY")) > 10:
        threading.Thread(target=start_bybit_listener, daemon=True).start()
        
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