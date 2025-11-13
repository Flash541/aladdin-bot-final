

# # core_analyzer.py (v10.1 - Fixed Indicators & Better Formatting)
# import os
# import requests
# from dotenv import load_dotenv
# import ccxt
# import pandas as pd
# import pandas_ta as ta
# from openai import OpenAI

# load_dotenv()
# CRYPTO_PANIC_API_KEY = os.getenv("CRYPTO_PANIC_API_KEY")
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
# exchange = ccxt.binance()

# def format_price(price):
#     """Умное форматирование цены для любых монет"""
#     try:
#         price = float(price)
#         if price == 0:
#             return "0.00"
#         elif price < 0.0001:
#             # Для очень мелких цен (тип PEPE)
#             return f"{price:.8f}".rstrip('0').rstrip('.')
#         elif price < 0.01:
#             return f"{price:.6f}".rstrip('0').rstrip('.')
#         elif price < 1:
#             return f"{price:.5f}".rstrip('0').rstrip('.')
#         elif price < 10:
#             return f"{price:.4f}".rstrip('0').rstrip('.')
#         elif price < 1000:
#             return f"{price:.3f}".rstrip('0').rstrip('.')
#         else:
#             return f"{price:.2f}".rstrip('0').rstrip('.')
#     except:
#         return str(price)

# def get_general_market_sentiment() -> float:
#     """ВРЕМЕННАЯ ЗАГЛУШКА"""
#     return 0.0

# def fetch_data(symbol="BTC/USDT", timeframe="1h", limit=200):
#     print(f"Fetching {symbol} {timeframe} data...")
#     try:
#         bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
#         df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
#         df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
#         return df
#     except Exception as e:
#         print(f"Error fetching data for {symbol}: {e}")
#         return pd.DataFrame()

# def compute_features(df):
#     if df.empty: 
#         return df
    
#     # ИСПРАВЛЕННЫЕ ИНДИКАТОРЫ - с правильными именами колонок
#     df.ta.ema(length=12, append=True, col_names=('EMA_fast',))
#     df.ta.ema(length=26, append=True, col_names=('EMA_slow',))
#     df.ta.rsi(length=14, append=True, col_names=('RSI',))
#     df.ta.atr(length=14, append=True, col_names=('ATR',))
#     df.ta.bbands(length=20, append=True, col_names=('BB_lower', 'BB_mid', 'BB_upper', 'BB_width', 'BB_percent'))
    
#     # Объем
#     if len(df) >= 20:
#         df['volume_z'] = (df['volume'] - df['volume'].rolling(20).mean()) / df['volume'].rolling(20).std()
#     else:
#         df['volume_z'] = 0
        
#     return df

# def generate_signal_from_chart(df, symbol_ccxt: str, timeframe="Chart"):
#     """Решительная версия для графиков"""
#     if df.empty or len(df) < 20: 
#         return {"view": "neutral", "notes": "Not enough data from chart."}
    
#     latest = df.iloc[-1]
#     long_score, short_score = 0, 0
    
#     # ПРОВЕРЕННАЯ ЛОГИКА
#     is_trend_up = latest['EMA_fast'] > latest['EMA_slow']
#     if is_trend_up: 
#         long_score += 1
#     else: 
#         short_score += 1
    
#     if latest['RSI'] > 52: 
#         long_score += 1
#     if latest['RSI'] < 48: 
#         short_score += 1
    
#     if latest['volume_z'] > 0:
#         if is_trend_up: 
#             long_score += 1
#         else: 
#             short_score += 1
    
#     current_price = latest['close']
    
#     if long_score > short_score:
#         stop = current_price - 1.8 * latest['ATR']
#         target1 = current_price + 2.2 * latest['ATR']
#         notes = f"Analysis of the provided chart suggests a bullish bias. Score: Long {long_score:.1f} vs Short {short_score:.1f}."
        
#         return {
#             "symbol": symbol_ccxt.replace("/", ""),
#             "timeframe": timeframe,
#             "view": "long",
#             "strategy": "Chart Analysis",
#             "entry_zone": [format_price(current_price), format_price(current_price * 1.002)],
#             "stop": format_price(stop),
#             "targets": [format_price(target1)],
#             "confidence": 0.60,
#             "notes": notes
#         }
#     else:
#         stop = current_price + 1.8 * latest['ATR']
#         target1 = current_price - 2.2 * latest['ATR']
#         notes = f"Analysis of the provided chart suggests a bearish bias. Score: Short {short_score:.1f} vs Long {long_score:.1f}."
        
#         return {
#             "symbol": symbol_ccxt.replace("/", ""),
#             "timeframe": timeframe,
#             "view": "short",
#             "strategy": "Chart Analysis", 
#             "entry_zone": [format_price(current_price * 0.998), format_price(current_price)],
#             "stop": format_price(stop),
#             "targets": [format_price(target1)],
#             "confidence": 0.60,
#             "notes": notes
#         }

# def generate_signal(df, symbol_ccxt: str, news_score: float, timeframe="1h"):
#     """Основная функция с улучшенным выводом"""
#     if df.empty or len(df) < 50: 
#         return {"view": "neutral", "notes": "Not enough data for analysis."}
    
#     latest = df.iloc[-1]
#     long_score, short_score = 0, 0
    
#     # ТВОЯ ПРОВЕРЕННАЯ ЛОГИКА
#     is_trend_up = latest['EMA_fast'] > latest['EMA_slow']
#     if is_trend_up: 
#         long_score += 1
#     else: 
#         short_score += 1
        
#     if latest['RSI'] > 55: 
#         long_score += 1
#     if latest['RSI'] < 45: 
#         short_score += 1
        
#     if latest['volume_z'] > 0.8:
#         if is_trend_up: 
#             long_score += 1
#         else: 
#             short_score += 1
            
#     if latest['BB_width'] > df['BB_width'].rolling(50).mean().iloc[-1]:
#         if is_trend_up: 
#             long_score += 0.5
#         else: 
#             short_score += 0.5

#     CONFIDENCE_THRESHOLD = 2.5
#     current_price = latest['close']
    
#     if long_score >= CONFIDENCE_THRESHOLD and latest['RSI'] < 80:
#         stop = current_price - 1.8 * latest['ATR']
#         target1 = current_price + 2.2 * latest['ATR']
        
#         return {
#             "symbol": symbol_ccxt.replace("/", ""),
#             "timeframe": timeframe,
#             "view": "long",
#             "strategy": f"Confluence Score: {long_score:.1f}",
#             "entry_zone": [format_price(current_price), format_price(current_price * 1.002)],
#             "stop": format_price(stop),
#             "targets": [format_price(target1)],
#             "confidence": min(0.9, 0.5 + (long_score - CONFIDENCE_THRESHOLD) * 0.1),
#             "notes": f"Multiple bullish factors converged. Market sentiment ({news_score:.2f})."
#         }
        
#     if short_score >= CONFIDENCE_THRESHOLD and latest['RSI'] > 20:
#         stop = current_price + 1.8 * latest['ATR']
#         target1 = current_price - 2.2 * latest['ATR']
        
#         return {
#             "symbol": symbol_ccxt.replace("/", ""),
#             "timeframe": timeframe,
#             "view": "short",
#             "strategy": f"Confluence Score: {short_score:.1f}",
#             "entry_zone": [format_price(current_price * 0.998), format_price(current_price)],
#             "stop": format_price(stop),
#             "targets": [format_price(target1)],
#             "confidence": min(0.9, 0.5 + (short_score - CONFIDENCE_THRESHOLD) * 0.1),
#             "notes": f"Multiple bearish factors converged. Market sentiment ({news_score:.2f})."
#         }
    
#     # КРАСИВЫЙ ВЫВОД ДЛЯ NEUTRAL
#     notes_details = (
#         f"<b>Rationale:</b>\n"
#         f"No strong confluence of factors found (Long: {long_score:.1f}, Short: {short_score:.1f} vs Threshold: {CONFIDENCE_THRESHOLD}).\n\n"
#         f"<b>Current Key Metrics:</b>\n"
#         f"— Trend: <code>{'Up' if is_trend_up else 'Down'}</code>\n"
#         f"— RSI: <code>{latest['RSI']:.2f}</code>\n"
#         f"— Volume: <code>{latest['volume_z']:.2f}</code>\n"
#         f"— Market Sentiment: <code>{news_score:.2f}</code>\n\n"
#         f"<i>Waiting for a clearer setup.</i>"
#     )
    
#     return {
#         "symbol": symbol_ccxt.replace("/", ""),
#         "timeframe": timeframe,
#         "view": "neutral",
#         "notes": notes_details
#     }



# # core_analyzer.py (v11 - Impulse Detection)
# import os
# import requests
# from dotenv import load_dotenv
# import ccxt
# import pandas as pd
# import pandas_ta as ta
# from openai import OpenAI

# load_dotenv()
# CRYPTO_PANIC_API_KEY = os.getenv("CRYPTO_PANIC_API_KEY")
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
# exchange = ccxt.binance()

# def format_price(price):
#     """Умное форматирование цены для любых монет"""
#     try:
#         price = float(price)
#         if price == 0:
#             return "0.00"
#         elif price < 0.0001:
#             return f"{price:.8f}".rstrip('0').rstrip('.')
#         elif price < 0.01:
#             return f"{price:.6f}".rstrip('0').rstrip('.')
#         elif price < 1:
#             return f"{price:.5f}".rstrip('0').rstrip('.')
#         elif price < 10:
#             return f"{price:.4f}".rstrip('0').rstrip('.')
#         elif price < 1000:
#             return f"{price:.3f}".rstrip('0').rstrip('.')
#         else:
#             return f"{price:.2f}".rstrip('0').rstrip('.')
#     except:
#         return str(price)

# def get_general_market_sentiment() -> float:
#     """ВРЕМЕННАЯ ЗАГЛУШКА"""
#     return 0.0

# def fetch_data(symbol="BTC/USDT", timeframe="1h", limit=200):
#     print(f"Fetching {symbol} {timeframe} data...")
#     try:
#         bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
#         df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
#         df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
#         return df
#     except Exception as e:
#         print(f"Error fetching data for {symbol}: {e}")
#         return pd.DataFrame()

# def compute_features(df):
#     if df.empty: 
#         return df
    
#     # ИСПРАВЛЕННЫЕ ИНДИКАТОРЫ
#     df.ta.ema(length=12, append=True, col_names=('EMA_fast',))
#     df.ta.ema(length=26, append=True, col_names=('EMA_slow',))
#     df.ta.rsi(length=14, append=True, col_names=('RSI',))
#     df.ta.atr(length=14, append=True, col_names=('ATR',))
#     df.ta.bbands(length=20, append=True, col_names=('BB_lower', 'BB_mid', 'BB_upper', 'BB_width', 'BB_percent'))
    
#     # Объем
#     if len(df) >= 20:
#         df['volume_z'] = (df['volume'] - df['volume'].rolling(20).mean()) / df['volume'].rolling(20).std()
#     else:
#         df['volume_z'] = 0
        
#     return df

# def generate_decisive_signal(df, symbol_ccxt: str, timeframe="Chart"):
#     """
#     ФИНАЛЬНАЯ "РЕШИТЕЛЬНАЯ" ВЕРСИЯ. Понимает импульсы.
#     Всегда возвращает LONG или SHORT.
#     """
#     if df.empty or len(df) < 20: 
#         return {"view": "neutral", "notes": "Not enough data from chart."}
    
#     latest = df.iloc[-1]
#     long_score, short_score = 0, 0
    
#     # 1. Фактор Тренда
#     is_trend_up = latest['EMA_fast'] > latest['EMA_slow']
#     if is_trend_up: 
#         long_score += 1
#     else: 
#         short_score += 1
    
#     # 2. Фактор RSI
#     if latest['RSI'] > 52: 
#         long_score += 1
#     if latest['RSI'] < 48: 
#         short_score += 1
    
#     # 3. НОВЫЙ ФАКТОР: "Импульс Объема"
#     # Сравниваем объем последней свечи со средним объемом 10 предыдущих
#     if len(df) > 11:
#         recent_avg_volume = df['volume'].iloc[-11:-1].mean()
#         # Если объем последней свечи в 2.5 раза больше среднего, это сильный импульс
#         if latest['volume'] > recent_avg_volume * 2.5:
#             print("🎯 Volume Impulse Detected!")
#             if is_trend_up: 
#                 long_score += 1.5  # Даем большой вес
#             else: 
#                 short_score += 1.5
#         else:
#             # Стандартный анализ объема (как было)
#             if latest.get('volume_z', 0) > 0:
#                 if is_trend_up: 
#                     long_score += 0.5
#                 else: 
#                     short_score += 0.5
    
#     # Определяем победителя
#     current_price = latest['close']
    
#     if long_score > short_score:
#         stop = current_price - 1.8 * latest['ATR']
#         target1 = current_price + 2.2 * latest['ATR']
#         notes = f"Chart analysis suggests a bullish bias (Score: {long_score:.1f} vs {short_score:.1f})."
        
#         return {
#             "symbol": symbol_ccxt.replace("/", ""),
#             "timeframe": timeframe,
#             "view": "long",
#             "strategy": "Impulse Analysis",
#             "entry_zone": [format_price(current_price), format_price(current_price * 1.002)],
#             "stop": format_price(stop),
#             "targets": [format_price(target1)],
#             "confidence": min(0.9, 0.5 + long_score * 0.1),
#             "notes": notes
#         }
#     else:
#         stop = current_price + 1.8 * latest['ATR']
#         target1 = current_price - 2.2 * latest['ATR']
#         notes = f"Chart analysis suggests a bearish bias (Score: {short_score:.1f} vs {long_score:.1f})."
        
#         return {
#             "symbol": symbol_ccxt.replace("/", ""),
#             "timeframe": timeframe,
#             "view": "short",
#             "strategy": "Impulse Analysis",
#             "entry_zone": [format_price(current_price * 0.998), format_price(current_price)],
#             "stop": format_price(stop),
#             "targets": [format_price(target1)],
#             "confidence": min(0.9, 0.5 + short_score * 0.1),
#             "notes": notes
#         }

# def generate_signal(df, symbol_ccxt: str, news_score: float, timeframe="1h"):
#     """Осторожная версия для сканера (оставляем как есть)"""
#     if df.empty or len(df) < 50: 
#         return {"view": "neutral", "notes": "Not enough data for analysis."}
    
#     latest = df.iloc[-1]
#     long_score, short_score = 0, 0
    
#     # ТВОЯ ПРОВЕРЕННАЯ ЛОГИКА
#     is_trend_up = latest['EMA_fast'] > latest['EMA_slow']
#     if is_trend_up: 
#         long_score += 1
#     else: 
#         short_score += 1
        
#     if latest['RSI'] > 55: 
#         long_score += 1
#     if latest['RSI'] < 45: 
#         short_score += 1
        
#     if latest['volume_z'] > 0.8:
#         if is_trend_up: 
#             long_score += 1
#         else: 
#             short_score += 1
            
#     if latest['BB_width'] > df['BB_width'].rolling(50).mean().iloc[-1]:
#         if is_trend_up: 
#             long_score += 0.5
#         else: 
#             short_score += 0.5

#     CONFIDENCE_THRESHOLD = 2.5
#     current_price = latest['close']
    
#     if long_score >= CONFIDENCE_THRESHOLD and latest['RSI'] < 80:
#         stop = current_price - 1.8 * latest['ATR']
#         target1 = current_price + 2.2 * latest['ATR']
        
#         return {
#             "symbol": symbol_ccxt.replace("/", ""),
#             "timeframe": timeframe,
#             "view": "long",
#             "strategy": f"Confluence Score: {long_score:.1f}",
#             "entry_zone": [format_price(current_price), format_price(current_price * 1.002)],
#             "stop": format_price(stop),
#             "targets": [format_price(target1)],
#             "confidence": min(0.9, 0.5 + (long_score - CONFIDENCE_THRESHOLD) * 0.1),
#             "notes": f"Multiple bullish factors converged. Market sentiment ({news_score:.2f})."
#         }
        
#     if short_score >= CONFIDENCE_THRESHOLD and latest['RSI'] > 20:
#         stop = current_price + 1.8 * latest['ATR']
#         target1 = current_price - 2.2 * latest['ATR']
        
#         return {
#             "symbol": symbol_ccxt.replace("/", ""),
#             "timeframe": timeframe,
#             "view": "short",
#             "strategy": f"Confluence Score: {short_score:.1f}",
#             "entry_zone": [format_price(current_price * 0.998), format_price(current_price)],
#             "stop": format_price(stop),
#             "targets": [format_price(target1)],
#             "confidence": min(0.9, 0.5 + (short_score - CONFIDENCE_THRESHOLD) * 0.1),
#             "notes": f"Multiple bearish factors converged. Market sentiment ({news_score:.2f})."
#         }
    
#     # КРАСИВЫЙ ВЫВОД ДЛЯ NEUTRAL
#     notes_details = (
#         f"<b>Rationale:</b>\n"
#         f"No strong confluence of factors found (Long: {long_score:.1f}, Short: {short_score:.1f} vs Threshold: {CONFIDENCE_THRESHOLD}).\n\n"
#         f"<b>Current Key Metrics:</b>\n"
#         f"— Trend: <code>{'Up' if is_trend_up else 'Down'}</code>\n"
#         f"— RSI: <code>{latest['RSI']:.2f}</code>\n"
#         f"— Volume: <code>{latest['volume_z']:.2f}</code>\n"
#         f"— Market Sentiment: <code>{news_score:.2f}</code>\n\n"
#         f"<i>Waiting for a clearer setup.</i>"
#     )
    
#     return {
#         "symbol": symbol_ccxt.replace("/", ""),
#         "timeframe": timeframe,
#         "view": "neutral",
#         "notes": notes_details
#     }


# core_analyzer.py (v13 - Context-Aware with Impulse Detection)
# import os
# import math
# import pandas as pd
# import pandas_ta as ta
# import ccxt
# from dotenv import load_dotenv

# load_dotenv()
# exchange = ccxt.binance()

# def format_price(price):
#     """Умное форматирование цены для любых монет"""
#     try:
#         price = float(price)
#         if price == 0:
#             return "0.00"
#         elif price < 0.0001:
#             return f"{price:.8f}".rstrip('0').rstrip('.')
#         elif price < 0.01:
#             return f"{price:.6f}".rstrip('0').rstrip('.')
#         elif price < 1:
#             return f"{price:.5f}".rstrip('0').rstrip('.')
#         elif price < 10:
#             return f"{price:.4f}".rstrip('0').rstrip('.')
#         elif price < 1000:
#             return f"{price:.3f}".rstrip('0').rstrip('.')
#         else:
#             return f"{price:.2f}".rstrip('0').rstrip('.')
#     except:
#         return str(price)

# def get_general_market_sentiment() -> float:
#     """ВРЕМЕННАЯ ЗАГЛУШКА"""
#     print("News analysis is temporarily disabled.")
#     return 0.0

# def fetch_data(symbol="BTC/USDT", timeframe="1h", limit=200):
#     print(f"Fetching {symbol} {timeframe} data...")
#     try:
#         bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
#         df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
#         df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
#         return df
#     except Exception as e:
#         print(f"Error fetching data for {symbol}: {e}")
#         return pd.DataFrame()

# def compute_features(df):
#     if df.empty: 
#         return df
    
#     # ИСПРАВЛЕННЫЕ ИНДИКАТОРЫ
#     df.ta.ema(length=12, append=True, col_names=('EMA_fast',))
#     df.ta.ema(length=26, append=True, col_names=('EMA_slow',))
#     df.ta.rsi(length=14, append=True, col_names=('RSI',))
#     df.ta.atr(length=14, append=True, col_names=('ATR',))
#     df.ta.bbands(length=20, append=True, col_names=('BB_lower', 'BB_mid', 'BB_upper', 'BB_width', 'BB_percent'))
    
#     # Объем
#     if len(df) >= 20:
#         df['volume_z'] = (df['volume'] - df['volume'].rolling(20).mean()) / df['volume'].rolling(20).std()
#     else:
#         df['volume_z'] = 0
        
#     return df

# def generate_decisive_signal(df, symbol_ccxt: str, timeframe="Chart"):
#     """
#     ФИНАЛЬНАЯ "РЕШИТЕЛЬНАЯ" ВЕРСИЯ. Понимает импульсы.
#     Теперь возвращает (trade_plan, context) для LLM объяснений.
#     """
#     if df.empty or len(df) < 20: 
#         return None, None
    
#     latest = df.iloc[-1]
#     long_score, short_score = 0, 0
    
#     # --- Собираем контекст для LLM ---
#     context = {}
    
#     # 1. Фактор Тренда
#     is_trend_up = latest['EMA_fast'] > latest['EMA_slow']
#     context['trend'] = "Upward (Fast EMA > Slow EMA)" if is_trend_up else "Downward (Fast EMA < Slow EMA)"
#     if is_trend_up: 
#         long_score += 1
#     else: 
#         short_score += 1
    
#     # 2. Фактор RSI
#     context['rsi'] = f"{latest['RSI']:.2f}"
#     if latest['RSI'] > 52: 
#         long_score += 1
#     if latest['RSI'] < 48: 
#         short_score += 1
    
#     # 3. Фактор Объема
#     volume_z = latest.get('volume_z', 0)
#     context['volume'] = f"Above average (Z-Score: {volume_z:.2f})" if volume_z > 0 else f"Below average (Z-Score: {volume_z:.2f})"
    
#     # 4. НОВЫЙ ФАКТОР: "Импульс Объема"
#     volume_impulse_detected = False
#     if len(df) > 11:
#         recent_avg_volume = df['volume'].iloc[-11:-1].mean()
#         if latest['volume'] > recent_avg_volume * 2.5:
#             volume_impulse_detected = True
#             context['volume_impulse'] = "STRONG - Volume spike detected (2.5x above average)"
#             if is_trend_up: 
#                 long_score += 1.5
#             else: 
#                 short_score += 1.5
#         else:
#             context['volume_impulse'] = "Normal - No significant volume spike"
#             if volume_z > 0:
#                 if is_trend_up: 
#                     long_score += 0.5
#                 else: 
#                     short_score += 0.5
    
#     # 5. Фактор Волатильности (Bollinger Bands)
#     bb_width = latest.get('BB_width', 0)
#     if bb_width > df['BB_width'].rolling(50).mean().iloc[-1]:
#         context['volatility'] = "High - Bollinger Bands widening"
#         if is_trend_up: 
#             long_score += 0.5
#         else: 
#             short_score += 0.5
#     else:
#         context['volatility'] = "Normal - Bollinger Bands stable"
    
#     # Определяем победителя
#     current_price = latest['close']
#     context['final_scores'] = f"Long: {long_score:.1f} vs Short: {short_score:.1f}"
    
#     # --- Принятие решения и формирование плана ---
#     view, stop, target1, notes = None, None, None, None
    
#     if long_score > short_score:
#         view = "long"
#         stop = current_price - 1.8 * latest['ATR']
#         target1 = current_price + 2.2 * latest['ATR']
#         notes = f"Chart structure suggests a bullish bias (Score: {long_score:.1f} vs {short_score:.1f})."
#         context['final_view'] = "long"
#         context['reasoning'] = "Bullish trend with supportive indicators"
#     else:
#         view = "short"
#         stop = current_price + 1.8 * latest['ATR']
#         target1 = current_price - 2.2 * latest['ATR']
#         notes = f"Chart analysis suggests a bearish bias (Score: {short_score:.1f} vs {long_score:.1f})."
#         context['final_view'] = "short"
#         context['reasoning'] = "Bearish trend with supportive indicators"

#     trade_plan = {
#         "symbol": symbol_ccxt.replace("/", ""),
#         "timeframe": timeframe,
#         "view": view,
#         "strategy": "Impulse Analysis",
#         "entry_zone": [format_price(current_price), format_price(current_price * 1.001)],
#         "stop": format_price(stop),
#         "targets": [format_price(target1)],
#         "confidence": min(0.9, 0.5 + max(long_score, short_score) * 0.1),
#         "notes": notes
#     }
    
#     return trade_plan, context

# def generate_signal(df, symbol_ccxt: str, news_score: float, timeframe="1h"):
#     """'Осторожная' версия. Теперь возвращает (trade_plan, context)."""
#     if df.empty or len(df) < 50: 
#         return None, None
    
#     latest = df.iloc[-1]
#     long_score, short_score = 0, 0
    
#     # --- Собираем контекст для LLM ---
#     context = {}
    
#     is_trend_up = latest['EMA_fast'] > latest['EMA_slow']
#     context['trend'] = "Upward" if is_trend_up else "Downward"
#     if is_trend_up: 
#         long_score += 1
#     else: 
#         short_score += 1

#     context['rsi'] = f"{latest['RSI']:.2f}"
#     if latest['RSI'] > 55: 
#         long_score += 1
#     if latest['RSI'] < 45: 
#         short_score += 1

#     volume_z = latest.get('volume_z', 0)
#     context['volume'] = f"Elevated (Z-Score: {volume_z:.2f})" if volume_z > 0.8 else f"Normal (Z-Score: {volume_z:.2f})"
#     if volume_z > 0.8:
#         if is_trend_up: 
#             long_score += 1
#         else: 
#             short_score += 1

#     # Bollinger Bands анализ
#     bb_width = latest.get('BB_width', 0)
#     if bb_width > df['BB_width'].rolling(50).mean().iloc[-1]:
#         context['volatility'] = "High"
#         if is_trend_up: 
#             long_score += 0.5
#         else: 
#             short_score += 0.5
#     else:
#         context['volatility'] = "Normal"

#     CONFIDENCE_THRESHOLD = 2.5
#     current_price = latest['close']
#     context['final_scores'] = f"Long: {long_score:.1f} vs Short: {short_score:.1f}"
    
#     # --- Принятие решения ---
#     trade_plan = None
    
#     if long_score >= CONFIDENCE_THRESHOLD and latest['RSI'] < 80:
#         stop = current_price - 1.8 * latest['ATR']
#         target1 = current_price + 2.2 * latest['ATR']
        
#         trade_plan = {
#             "symbol": symbol_ccxt.replace("/", ""),
#             "timeframe": timeframe,
#             "view": "long",
#             "strategy": f"Confluence Score: {long_score:.1f}",
#             "entry_zone": [format_price(current_price), format_price(current_price * 1.002)],
#             "stop": format_price(stop),
#             "targets": [format_price(target1)],
#             "confidence": min(0.9, 0.5 + (long_score - CONFIDENCE_THRESHOLD) * 0.1),
#             "notes": f"Multiple bullish factors converged. Market sentiment ({news_score:.2f})."
#         }
#         context['final_view'] = "long"
#         context['reasoning'] = "Strong bullish confluence with multiple confirming indicators"
        
#     elif short_score >= CONFIDENCE_THRESHOLD and latest['RSI'] > 20:
#         stop = current_price + 1.8 * latest['ATR']
#         target1 = current_price - 2.2 * latest['ATR']
        
#         trade_plan = {
#             "symbol": symbol_ccxt.replace("/", ""),
#             "timeframe": timeframe,
#             "view": "short",
#             "strategy": f"Confluence Score: {short_score:.1f}",
#             "entry_zone": [format_price(current_price * 0.998), format_price(current_price)],
#             "stop": format_price(stop),
#             "targets": [format_price(target1)],
#             "confidence": min(0.9, 0.5 + (short_score - CONFIDENCE_THRESHOLD) * 0.1),
#             "notes": f"Multiple bearish factors converged. Market sentiment ({news_score:.2f})."
#         }
#         context['final_view'] = "short"
#         context['reasoning'] = "Strong bearish confluence with multiple confirming indicators"
#     else:
#         # NEUTRAL случай
#         notes_details = (
#             f"<b>Rationale:</b>\n"
#             f"No strong confluence of factors found (Long: {long_score:.1f}, Short: {short_score:.1f} vs Threshold: {CONFIDENCE_THRESHOLD}).\n\n"
#             f"<b>Current Key Metrics:</b>\n"
#             f"— Trend: <code>{'Up' if is_trend_up else 'Down'}</code>\n"
#             f"— RSI: <code>{latest['RSI']:.2f}</code>\n"
#             f"— Volume: <code>{latest['volume_z']:.2f}</code>\n"
#             f"— Market Sentiment: <code>{news_score:.2f}</code>\n\n"
#             f"<i>Waiting for a clearer setup.</i>"
#         )
        
#         trade_plan = {
#             "symbol": symbol_ccxt.replace("/", ""),
#             "timeframe": timeframe,
#             "view": "neutral",
#             "notes": notes_details
#         }
#         context['final_view'] = "neutral"
#         context['reasoning'] = "Insufficient confluence for directional bias"

#     return trade_plan, context


# core_analyzer.py (v14 - With Risk Calculation)
import os
import math
import pandas as pd
import pandas_ta as ta
import ccxt
from dotenv import load_dotenv

load_dotenv()
exchange = ccxt.binance()

def format_price(price):
    """Умное форматирование цены для любых монет"""
    try:
        price = float(price)
        if price == 0:
            return "0.00"
        elif price < 0.0001:
            return f"{price:.8f}".rstrip('0').rstrip('.')
        elif price < 0.01:
            return f"{price:.6f}".rstrip('0').rstrip('.')
        elif price < 1:
            return f"{price:.5f}".rstrip('0').rstrip('.')
        elif price < 10:
            return f"{price:.4f}".rstrip('0').rstrip('.')
        elif price < 1000:
            return f"{price:.3f}".rstrip('0').rstrip('.')
        else:
            return f"{price:.2f}".rstrip('0').rstrip('.')
    except:
        return str(price)

def get_general_market_sentiment() -> float:
    """ВРЕМЕННАЯ ЗАГЛУШКА"""
    print("News analysis is temporarily disabled.")
    return 0.0

def fetch_data(symbol="BTC/USDT", timeframe="1h", limit=200):
    print(f"Fetching {symbol} {timeframe} data...")
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return pd.DataFrame()

def compute_features(df):
    if df.empty: 
        return df
    
    # ИСПРАВЛЕННЫЕ ИНДИКАТОРЫ
    df.ta.ema(length=12, append=True, col_names=('EMA_fast',))
    df.ta.ema(length=26, append=True, col_names=('EMA_slow',))
    df.ta.rsi(length=14, append=True, col_names=('RSI',))
    df.ta.atr(length=14, append=True, col_names=('ATR',))
    df.ta.bbands(length=20, append=True, col_names=('BB_lower', 'BB_mid', 'BB_upper', 'BB_width', 'BB_percent'))
    
    # Объем
    if len(df) >= 20:
        df['volume_z'] = (df['volume'] - df['volume'].rolling(20).mean()) / df['volume'].rolling(20).std()
    else:
        df['volume_z'] = 0
        
    return df

def calculate_position_size(entry_price: float, stop_loss_price: float, account_balance: float, risk_per_trade_pct: float) -> dict:
    """Calculates position size based on user's risk settings."""
    if entry_price is None or stop_loss_price is None: 
        return {}
    
    risk_amount_usd = account_balance * (risk_per_trade_pct / 100.0)
    sl_distance = abs(entry_price - stop_loss_price)
    
    if sl_distance == 0: 
        return {}
    
    position_size_asset = risk_amount_usd / sl_distance
    position_size_usd = position_size_asset * entry_price
    
    return {
        "position_size_asset": f"{position_size_asset:.4f}",
        "position_size_usd": f"${position_size_usd:,.2f}",
        "potential_loss_usd": f"${risk_amount_usd:,.2f}"
    }

def generate_decisive_signal(df, symbol_ccxt: str, risk_settings: dict, timeframe="Chart"):
    """
    ФИНАЛЬНАЯ "РЕШИТЕЛЬНАЯ" ВЕРСИЯ. Понимает импульсы.
    Теперь возвращает (trade_plan, context) для LLM объяснений.
    """
    if df.empty or len(df) < 20: 
        return None, None
    
    latest = df.iloc[-1]
    long_score, short_score = 0, 0
    
    # --- Собираем контекст для LLM ---
    context = {}
    
    # 1. Фактор Тренда
    is_trend_up = latest['EMA_fast'] > latest['EMA_slow']
    context['trend'] = "Upward (Fast EMA > Slow EMA)" if is_trend_up else "Downward (Fast EMA < Slow EMA)"
    if is_trend_up: 
        long_score += 1
    else: 
        short_score += 1
    
    # 2. Фактор RSI
    context['rsi'] = f"{latest['RSI']:.2f}"
    if latest['RSI'] > 52: 
        long_score += 1
    if latest['RSI'] < 48: 
        short_score += 1
    
    # 3. Фактор Объема
    volume_z = latest.get('volume_z', 0)
    context['volume'] = f"Above average (Z-Score: {volume_z:.2f})" if volume_z > 0 else f"Below average (Z-Score: {volume_z:.2f})"
    
    # 4. НОВЫЙ ФАКТОР: "Импульс Объема"
    volume_impulse_detected = False
    if len(df) > 11:
        recent_avg_volume = df['volume'].iloc[-11:-1].mean()
        if latest['volume'] > recent_avg_volume * 2.5:
            volume_impulse_detected = True
            context['volume_impulse'] = "STRONG - Volume spike detected (2.5x above average)"
            if is_trend_up: 
                long_score += 1.5
            else: 
                short_score += 1.5
        else:
            context['volume_impulse'] = "Normal - No significant volume spike"
            if volume_z > 0:
                if is_trend_up: 
                    long_score += 0.5
                else: 
                    short_score += 0.5
    
    # 5. Фактор Волатильности (Bollinger Bands)
    bb_width = latest.get('BB_width', 0)
    if bb_width > df['BB_width'].rolling(50).mean().iloc[-1]:
        context['volatility'] = "High - Bollinger Bands widening"
        if is_trend_up: 
            long_score += 0.5
        else: 
            short_score += 0.5
    else:
        context['volatility'] = "Normal - Bollinger Bands stable"
    
    # Определяем победителя
    current_price = latest['close']
    context['final_scores'] = f"Long: {long_score:.1f} vs Short: {short_score:.1f}"
    
    # --- Принятие решения и формирование плана ---
    view, stop, target1, notes = None, None, None, None
    
    if long_score > short_score:
        view = "long"
        stop = current_price - 1.8 * latest['ATR']
        target1 = current_price + 2.2 * latest['ATR']
        notes = f"Chart structure suggests a bullish bias (Score: {long_score:.1f} vs {short_score:.1f})."
        context['final_view'] = "long"
        context['reasoning'] = "Bullish trend with supportive indicators"
    else:
        view = "short"
        stop = current_price + 1.8 * latest['ATR']
        target1 = current_price - 2.2 * latest['ATR']
        notes = f"Chart analysis suggests a bearish bias (Score: {short_score:.1f} vs {long_score:.1f})."
        context['final_view'] = "short"
        context['reasoning'] = "Bearish trend with supportive indicators"

    # --- РАСЧЕТ РИСКА И ПОЗИЦИИ ---
    risk_data = calculate_position_size(current_price, stop, risk_settings['balance'], risk_settings['risk_pct'])
    
    trade_plan = {
        "symbol": symbol_ccxt.replace("/", ""),
        "timeframe": timeframe,
        "view": view,
        "strategy": "Impulse Analysis",
        "entry_zone": [format_price(current_price), format_price(current_price * 1.001)],
        "stop": format_price(stop),
        "targets": [format_price(target1)],
        "confidence": min(0.9, 0.5 + max(long_score, short_score) * 0.1),
        "notes": notes
    }
    
    # Добавляем данные о риске в trade_plan
    trade_plan.update(risk_data)
    
    return trade_plan, context

def generate_signal(df, symbol_ccxt: str, news_score: float, risk_settings: dict, timeframe="1h"):
    """'Осторожная' версия. Теперь возвращает (trade_plan, context)."""
    if df.empty or len(df) < 50: 
        return None, None
    
    latest = df.iloc[-1]
    long_score, short_score = 0, 0
    
    # --- Собираем контекст для LLM ---
    context = {}
    
    is_trend_up = latest['EMA_fast'] > latest['EMA_slow']
    context['trend'] = "Upward" if is_trend_up else "Downward"
    if is_trend_up: 
        long_score += 1
    else: 
        short_score += 1

    context['rsi'] = f"{latest['RSI']:.2f}"
    if latest['RSI'] > 55: 
        long_score += 1
    if latest['RSI'] < 45: 
        short_score += 1

    volume_z = latest.get('volume_z', 0)
    context['volume'] = f"Elevated (Z-Score: {volume_z:.2f})" if volume_z > 0.8 else f"Normal (Z-Score: {volume_z:.2f})"
    if volume_z > 0.8:
        if is_trend_up: 
            long_score += 1
        else: 
            short_score += 1

    # Bollinger Bands анализ
    bb_width = latest.get('BB_width', 0)
    if bb_width > df['BB_width'].rolling(50).mean().iloc[-1]:
        context['volatility'] = "High"
        if is_trend_up: 
            long_score += 0.5
        else: 
            short_score += 0.5
    else:
        context['volatility'] = "Normal"

    CONFIDENCE_THRESHOLD = 2.5
    current_price = latest['close']
    context['final_scores'] = f"Long: {long_score:.1f} vs Short: {short_score:.1f}"
    
    # --- Принятие решения ---
    trade_plan = None
    
    if long_score >= CONFIDENCE_THRESHOLD and latest['RSI'] < 80:
        stop = current_price - 1.8 * latest['ATR']
        target1 = current_price + 2.2 * latest['ATR']
        
        # РАСЧЕТ РИСКА ДЛЯ LONG
        risk_data = calculate_position_size(current_price, stop, risk_settings['balance'], risk_settings['risk_pct'])
        
        trade_plan = {
            "symbol": symbol_ccxt.replace("/", ""),
            "timeframe": timeframe,
            "view": "long",
            "strategy": f"Confluence Score: {long_score:.1f}",
            "entry_zone": [format_price(current_price), format_price(current_price * 1.002)],
            "stop": format_price(stop),
            "targets": [format_price(target1)],
            "confidence": min(0.9, 0.5 + (long_score - CONFIDENCE_THRESHOLD) * 0.1),
            "notes": f"Multiple bullish factors converged. Market sentiment ({news_score:.2f})."
        }
        trade_plan.update(risk_data)
        context['final_view'] = "long"
        context['reasoning'] = "Strong bullish confluence with multiple confirming indicators"
        
    elif short_score >= CONFIDENCE_THRESHOLD and latest['RSI'] > 20:
        stop = current_price + 1.8 * latest['ATR']
        target1 = current_price - 2.2 * latest['ATR']
        
        # РАСЧЕТ РИСКА ДЛЯ SHORT
        risk_data = calculate_position_size(current_price, stop, risk_settings['balance'], risk_settings['risk_pct'])
        
        trade_plan = {
            "symbol": symbol_ccxt.replace("/", ""),
            "timeframe": timeframe,
            "view": "short",
            "strategy": f"Confluence Score: {short_score:.1f}",
            "entry_zone": [format_price(current_price * 0.998), format_price(current_price)],
            "stop": format_price(stop),
            "targets": [format_price(target1)],
            "confidence": min(0.9, 0.5 + (short_score - CONFIDENCE_THRESHOLD) * 0.1),
            "notes": f"Multiple bearish factors converged. Market sentiment ({news_score:.2f})."
        }
        trade_plan.update(risk_data)
        context['final_view'] = "short"
        context['reasoning'] = "Strong bearish confluence with multiple confirming indicators"
    else:
        # NEUTRAL случай
        notes_details = (
            f"<b>Rationale:</b>\n"
            f"No strong confluence of factors found (Long: {long_score:.1f}, Short: {short_score:.1f} vs Threshold: {CONFIDENCE_THRESHOLD}).\n\n"
            f"<b>Current Key Metrics:</b>\n"
            f"— Trend: <code>{'Up' if is_trend_up else 'Down'}</code>\n"
            f"— RSI: <code>{latest['RSI']:.2f}</code>\n"
            f"— Volume: <code>{latest['volume_z']:.2f}</code>\n"
            f"— Market Sentiment: <code>{news_score:.2f}</code>\n\n"
            f"<i>Waiting for a clearer setup.</i>"
        )
        
        trade_plan = {
            "symbol": symbol_ccxt.replace("/", ""),
            "timeframe": timeframe,
            "view": "neutral",
            "notes": notes_details
        }
        context['final_view'] = "neutral"
        context['reasoning'] = "Insufficient confluence for directional bias"

    return trade_plan, context