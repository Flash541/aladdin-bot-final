# # chart_analyzer.py (v6.1 - Fixed Ticker Parsing)
# import cv2
# import numpy as np
# import pytesseract
# import re
# from openai import OpenAI
# from dotenv import load_dotenv
# import os

# load_dotenv()
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# def extract_ticker_with_gpt(ocr_text: str) -> str | None:
#     """Использует GPT для точного определения тикера из OCR текста"""
#     if not client:
#         print("OpenAI client not available, falling back to basic OCR")
#         return extract_ticker_basic(ocr_text)
    
#     try:
#         system_prompt = """Ты - эксперт по распознаванию криптовалютных тикеров из текста OCR. 
#         Анализируй предоставленный текст и определяй, какой криптовалютный тикер (например, BTCUSDT, ETHUSDT) показан на графике.
        
#         ВАЖНЫЕ ПРАВИЛА:
#         1. Возвращай ТОЛЬКО тикер в формате БАЗАКОТИРОВКА (например: BTCUSDT, ETHUSDT, SOLUSDT)
#         2. Всегда используй USDT как котируемую валюту для Binance
#         3. Если не уверен - возвращай None
#         4. Игнорируй опечатки и ошибки OCR
        
#         Основные пары для Binance:
#         - Bitcoin: BTCUSDT  
#         - Ethereum: ETHUSDT
#         - Solana: SOLUSDT
#         - XRP: XRPUSDT
#         - BNB: BNBUSDT
#         - Cardano: ADAUSDT
#         - Dogecoin: DOGEUSDT
#         - Polygon: MATICUSDT
#         - Avalanche: AVAXUSDT
#         - Chainlink: LINKUSDT
#         - Polkadot: DOTUSDT
#         - Pepe: PEPEUSDT
        
#         Примеры:
#         - "XRP/TETHERUS-15-BINANCE" → XRPUSDT
#         - "BINANCE COIN / TETHERUS" → BNBUSDT
#         - "BITCOIN / TETHERUS" → BTCUSDT"""
        
#         user_prompt = f"Проанализируй этот OCR текст и определи тикер:\n\n{ocr_text}"
        
#         response = client.chat.completions.create(
#             model="gpt-3.5-turbo",
#             messages=[
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": user_prompt}
#             ],
#             temperature=0.1,
#             max_tokens=50
#         )
        
#         gpt_response = response.choices[0].message.content.strip()
#         print(f"GPT Response: {gpt_response}")
        
#         # Проверяем, что ответ валидный тикер
#         if gpt_response and gpt_response.upper() != "NONE":
#             gpt_response = gpt_response.upper()
#             # Убедимся, что это похоже на тикер (буквы + цифры, 4+ символов)
#             if re.match(r'^[A-Z0-9]{4,20}$', gpt_response):
#                 return gpt_response
#             else:
#                 print(f"GPT returned invalid format: {gpt_response}")
#                 return extract_ticker_basic(ocr_text)
#         else:
#             print("GPT couldn't identify ticker, falling back to basic OCR")
#             return extract_ticker_basic(ocr_text)
            
#     except Exception as e:
#         print(f"Error in GPT analysis: {e}")
#         return extract_ticker_basic(ocr_text)

# def extract_ticker_basic(ocr_text: str) -> str | None:
#     """Резервный метод OCR когда GPT недоступен"""
#     crypto_pairs = {
#         "BTC": ["BITCOIN", "BTC"],
#         "ETH": ["ETHEREUM", "ETH"], 
#         "SOL": ["SOLANA", "SOL"],
#         "XRP": ["XRP"],
#         "BNB": ["BNB", "BINANCE COIN"],
#         "DOGE": ["DOGE", "DOGECOIN"],
#         "AVAX": ["AVAX", "AVALANCHE"],
#         "LINK": ["LINK", "CHAINLINK"],
#         "MATIC": ["MATIC", "POLYGON"],
#         "PEPE": ["PEPE"],
#         "ADA": ["ADA", "CARDANO"],
#         "DOT": ["DOT", "POLKADOT"]
#     }
    
#     scores = {pair: 0 for pair in crypto_pairs.keys()}
    
#     for pair, keywords in crypto_pairs.items():
#         for keyword in keywords:
#             if keyword.upper() in ocr_text:
#                 if len(keyword) > 3:
#                     scores[pair] += 2
#                 else:
#                     scores[pair] += 1
    
#     max_score_pair = max(scores, key=scores.get)
#     max_score = scores[max_score_pair]
    
#     if max_score < 1:
#         return None
        
#     # Всегда используем USDT для Binance
#     return f"{max_score_pair}USDT"

# def extract_ticker_from_image(image: np.ndarray) -> str | None:
#     """Основная функция извлечения тикера с GPT"""
#     try:
#         h, w, _ = image.shape
#         top_section = image[0:min(150, int(h * 0.15)), 0:w]
        
#         # Получаем OCR текст разными методами для лучшего качества
#         texts = set()
#         for threshold_val in [100, 120, 150]:
#             gray_top = cv2.cvtColor(top_section, cv2.COLOR_BGR2GRAY)
#             _, binary_img = cv2.threshold(gray_top, threshold_val, 255, cv2.THRESH_BINARY)
#             text = pytesseract.image_to_string(binary_img, config='--psm 6')
#             texts.add(text.upper())

#         full_text = " ".join(texts)
#         print(f"OCR Raw Text: '{full_text.strip()}'")
        
#         # Используем GPT для анализа
#         ticker = extract_ticker_with_gpt(full_text)
        
#         if ticker:
#             print(f"Final ticker (GPT): {ticker}")
#         else:
#             print("No ticker identified")
            
#         return ticker
            
#     except Exception as e:
#         print(f"Error during OCR: {e}")
#         return None

# def find_candlesticks(image_path: str):
#     """Гибридный метод: ищет цвета и затем проверяет форму."""
#     print(f"Analyzing image: {image_path}")
#     image = cv2.imread(image_path)
#     if image is None: 
#         return [], None

#     ticker = extract_ticker_from_image(image)
    
#     # Поиск свечей (оставляем твою проверенную логику)
#     hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
#     lower_red1 = np.array([0, 100, 100]); upper_red1 = np.array([10, 255, 255])
#     lower_red2 = np.array([160, 100, 100]); upper_red2 = np.array([180, 255, 255])
#     red_mask = cv2.bitwise_or(cv2.inRange(hsv, lower_red1, upper_red1), cv2.inRange(hsv, lower_red2, upper_red2))
    
#     lower_green = np.array([40, 50, 50]); upper_green = np.array([80, 255, 255])
#     green_mask = cv2.inRange(hsv, lower_green, upper_green)
    
#     combined_mask = cv2.bitwise_or(red_mask, green_mask)
    
#     contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
#     candlesticks = []
#     for cnt in contours:
#         x, y, w, h = cv2.boundingRect(cnt)
        
#         # Фильтруем по форме свечи
#         if h > 5 and w > 1 and h / w > 1.2 and w < 30:
#             center_x = x + w // 2
#             center_y = y + h // 2
            
#             # Находим тени
#             gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
#             _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY_INV)
            
#             col = thresh[:, center_x]
#             wick_points = np.where(col > 0)[0]
            
#             high_y, low_y = y, y + h
#             if wick_points.size > 0:
#                 high_y = min(y, wick_points.min())
#                 low_y = max(y + h, wick_points.max())
                
#             candle = {
#                 "body_x": x, "body_y": y, "body_w": w, "body_h": h,
#                 "color": "green" if green_mask[center_y, center_x] > 0 else "red",
#                 "high": high_y,
#                 "low": low_y
#             }
#             candlesticks.append(candle)
            
#     candlesticks.sort(key=lambda c: c["body_x"])
#     print(f"Found {len(candlesticks)} potential candlesticks.")
#     return candlesticks, ticker

# def candlesticks_to_ohlc(candlesticks: list):
#     if not candlesticks: 
#         return []
    
#     all_lows = [c.get('low') for c in candlesticks]
#     all_highs = [c.get('high') for c in candlesticks]
#     min_low = min(all_lows)
#     max_high = max(all_highs)
#     price_range = max_high - min_low
    
#     if price_range == 0: 
#         return []
    
#     ohlc_data = []
#     for c in candlesticks:
#         high = c.get('high')
#         low = c.get('low')
        
#         high_norm = 1 - (high - min_low) / price_range
#         low_norm = 1 - (low - min_low) / price_range
        
#         if c['color'] == 'green':
#             open_norm = 1 - ((c['body_y'] + c['body_h']) - min_low) / price_range
#             close_norm = 1 - (c['body_y'] - min_low) / price_range
#         else:
#             open_norm = 1 - (c['body_y'] - min_low) / price_range
#             close_norm = 1 - ((c['body_y'] + c['body_h']) - min_low) / price_range
            
#         ohlc_data.append({
#             'open': open_norm, 
#             'high': high_norm, 
#             'low': low_norm, 
#             'close': close_norm
#         })
    
#     return ohlc_data



# chart_analyzer.py (v6.1 - Fixed Ticker Parsing)
import cv2
import numpy as np
import pytesseract
import base64
import re
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# def extract_ticker_with_gpt(ocr_text: str) -> str | None:
#     """Использует GPT для точного определения тикера из OCR текста"""
#     if not client:
#         print("OpenAI client not available, falling back to basic OCR")
#         return extract_ticker_basic(ocr_text)
    
#     try:
#         system_prompt = """Ты - эксперт по распознаванию криптовалютных тикеров из текста OCR. 
#         Анализируй предоставленный текст и определяй, какой криптовалютный тикер (например, BTCUSDT, ETHUSDT) показан на графике.
        
#         ВАЖНЫЕ ПРАВИЛА:
#         1. Возвращай ТОЛЬКО тикер в формате БАЗАКОТИРОВКА (например: BTCUSDT, ETHUSDT, SOLUSDT)
#         2. Всегда используй USDT как котируемую валюту для Binance
#         3. Если не уверен - возвращай None
#         4. Игнорируй опечатки и ошибки OCR
        
#         Основные пары для Binance:
#         - Bitcoin: BTCUSDT  
#         - Ethereum: ETHUSDT
#         - Solana: SOLUSDT
#         - XRP: XRPUSDT
#         - BNB: BNBUSDT
#         - Cardano: ADAUSDT
#         - Dogecoin: DOGEUSDT
#         - Polygon: MATICUSDT
#         - Avalanche: AVAXUSDT
#         - Chainlink: LINKUSDT
#         - Polkadot: DOTUSDT
#         - Pepe: PEPEUSDT
        
#         Примеры:
#         - "XRP/TETHERUS-15-BINANCE" → XRPUSDT
#         - "BINANCE COIN / TETHERUS" → BNBUSDT
#         - "BITCOIN / TETHERUS" → BTCUSDT"""
        
#         user_prompt = f"Проанализируй этот OCR текст и определи тикер:\n\n{ocr_text}"
        
#         response = client.chat.completions.create(
#             model="gpt-3.5-turbo",
#             messages=[
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": user_prompt}
#             ],
#             temperature=0.1,
#             max_tokens=50
#         )
        
#         gpt_response = response.choices[0].message.content.strip()
#         print(f"GPT Response: {gpt_response}")
        
#         # Проверяем, что ответ валидный тикер
#         if gpt_response and gpt_response.upper() != "NONE":
#             gpt_response = gpt_response.upper()
#             # Убедимся, что это похоже на тикер (буквы + цифры, 4+ символов)
#             if re.match(r'^[A-Z0-9]{4,20}$', gpt_response):
#                 return gpt_response
#             else:
#                 print(f"GPT returned invalid format: {gpt_response}")
#                 return extract_ticker_basic(ocr_text)
#         else:
#             print("GPT couldn't identify ticker, falling back to basic OCR")
#             return extract_ticker_basic(ocr_text)
            
#     except Exception as e:
#         print(f"Error in GPT analysis: {e}")
#         return extract_ticker_basic(ocr_text)


def extract_ticker_with_gpt(image_path: str) -> str | None:
    """Использует GPT-4 Vision для распознавания тикера на изображении."""
    if not client:
        print("WARNING: OpenAI API key not found. Cannot perform Vision analysis.")
        return None

    try:
        # Кодируем изображение в base64
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        print("--- Sending image to GPT-4 Vision for ticker recognition ---")
        
        response = client.chat.completions.create(
            model="gpt-4o", # Или "gpt-4-vision-preview"
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "What is the cryptocurrency ticker symbol shown in this chart image? Respond with ONLY the ticker symbol (e.g., BTCUSDT, ETHUSD). If you are unsure, respond with 'UNKNOWN'."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=10,
        )

        ticker = response.choices[0].message.content.strip().upper()
        
        if "UNKNOWN" in ticker or len(ticker) < 4:
            print("GPT-4 Vision could not confidently identify a ticker.")
            return None
            
        print(f"GPT-4 Vision identified ticker: {ticker}")
        return ticker
    except Exception as e:
        print(f"Error during GPT-4 Vision analysis: {e}")
        return None

def find_candlesticks(image_path: str):
    """
    Основная функция: вызывает GPT для тикера и CV для свечей.
    """
    ticker = extract_ticker_with_gpt(image_path)
    
    # --- Логика поиска свечей (остается без изменений) ---
    # Мы все еще можем пытаться найти свечи на случай, если GPT не найдет тикер,
    # но основной упор теперь на тикер.
    
    print(f"Analyzing image for candlesticks: {image_path}")
    image = cv2.imread(image_path)
    if image is None: return [], ticker
    
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_red1 = np.array([0, 100, 100]); upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 100, 100]); upper_red2 = np.array([180, 255, 255])
    red_mask = cv2.bitwise_or(cv2.inRange(hsv, lower_red1, upper_red1), cv2.inRange(hsv, lower_red2, upper_red2))
    lower_green = np.array([40, 50, 50]); upper_green = np.array([80, 255, 255])
    green_mask = cv2.inRange(hsv, lower_green, upper_green)
    combined_mask = cv2.bitwise_or(red_mask, green_mask)
    contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candlesticks = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if h > 5 and w > 1 and h / w > 1.2 and w < 30:
            candlesticks.append({"body_x": x, "body_y": y, "body_w": w, "body_h": h})
    candlesticks.sort(key=lambda c: c["body_x"])
    print(f"Found {len(candlesticks)} potential candlesticks.")
    return candlesticks, ticker


# def extract_ticker_basic(ocr_text: str) -> str | None:
#     """Резервный метод OCR когда GPT недоступен"""
#     crypto_pairs = {
#         "BTC": ["BITCOIN", "BTC"],
#         "ETH": ["ETHEREUM", "ETH"], 
#         "SOL": ["SOLANA", "SOL"],
#         "XRP": ["XRP"],
#         "BNB": ["BNB", "BINANCE COIN"],
#         "DOGE": ["DOGE", "DOGECOIN"],
#         "AVAX": ["AVAX", "AVALANCHE"],
#         "LINK": ["LINK", "CHAINLINK"],
#         "MATIC": ["MATIC", "POLYGON"],
#         "PEPE": ["PEPE"],
#         "ADA": ["ADA", "CARDANO"],
#         "DOT": ["DOT", "POLKADOT"]
#     }
    
#     scores = {pair: 0 for pair in crypto_pairs.keys()}
    
#     for pair, keywords in crypto_pairs.items():
#         for keyword in keywords:
#             if keyword.upper() in ocr_text:
#                 if len(keyword) > 3:
#                     scores[pair] += 2
#                 else:
#                     scores[pair] += 1
    
#     max_score_pair = max(scores, key=scores.get)
#     max_score = scores[max_score_pair]
    
#     if max_score < 1:
#         return None
        
#     # Всегда используем USDT для Binance
#     return f"{max_score_pair}USDT"

def extract_ticker_from_image(image: np.ndarray) -> str | None:
    """Основная функция извлечения тикера с GPT"""
    try:
        h, w, _ = image.shape
        top_section = image[0:min(150, int(h * 0.15)), 0:w]
        
        # Получаем OCR текст разными методами для лучшего качества
        texts = set()
        for threshold_val in [100, 120, 150]:
            gray_top = cv2.cvtColor(top_section, cv2.COLOR_BGR2GRAY)
            _, binary_img = cv2.threshold(gray_top, threshold_val, 255, cv2.THRESH_BINARY)
            text = pytesseract.image_to_string(binary_img, config='--psm 6')
            texts.add(text.upper())

        full_text = " ".join(texts)
        print(f"OCR Raw Text: '{full_text.strip()}'")
        
        # Используем GPT для анализа
        ticker = extract_ticker_with_gpt(full_text)
        
        if ticker:
            print(f"Final ticker (GPT): {ticker}")
        else:
            print("No ticker identified")
            
        return ticker
            
    except Exception as e:
        print(f"Error during OCR: {e}")
        return None

def find_candlesticks(image_path: str):
    """Гибридный метод: ищет цвета и затем проверяет форму."""
    print(f"Analyzing image: {image_path}")
    image = cv2.imread(image_path)
    if image is None: 
        return [], None

    ticker = extract_ticker_from_image(image)
    
    # Поиск свечей (оставляем твою проверенную логику)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_red1 = np.array([0, 100, 100]); upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 100, 100]); upper_red2 = np.array([180, 255, 255])
    red_mask = cv2.bitwise_or(cv2.inRange(hsv, lower_red1, upper_red1), cv2.inRange(hsv, lower_red2, upper_red2))
    
    lower_green = np.array([40, 50, 50]); upper_green = np.array([80, 255, 255])
    green_mask = cv2.inRange(hsv, lower_green, upper_green)
    
    combined_mask = cv2.bitwise_or(red_mask, green_mask)
    
    contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    candlesticks = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        
        # Фильтруем по форме свечи
        if h > 5 and w > 1 and h / w > 1.2 and w < 30:
            center_x = x + w // 2
            center_y = y + h // 2
            
            # Находим тени
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY_INV)
            
            col = thresh[:, center_x]
            wick_points = np.where(col > 0)[0]
            
            high_y, low_y = y, y + h
            if wick_points.size > 0:
                high_y = min(y, wick_points.min())
                low_y = max(y + h, wick_points.max())
                
            candle = {
                "body_x": x, "body_y": y, "body_w": w, "body_h": h,
                "color": "green" if green_mask[center_y, center_x] > 0 else "red",
                "high": high_y,
                "low": low_y
            }
            candlesticks.append(candle)
            
    candlesticks.sort(key=lambda c: c["body_x"])
    print(f"Found {len(candlesticks)} potential candlesticks.")
    return candlesticks, ticker

def candlesticks_to_ohlc(candlesticks: list):
    if not candlesticks: 
        return []
    
    all_lows = [c.get('low') for c in candlesticks]
    all_highs = [c.get('high') for c in candlesticks]
    min_low = min(all_lows)
    max_high = max(all_highs)
    price_range = max_high - min_low
    
    if price_range == 0: 
        return []
    
    ohlc_data = []
    for c in candlesticks:
        high = c.get('high')
        low = c.get('low')
        
        high_norm = 1 - (high - min_low) / price_range
        low_norm = 1 - (low - min_low) / price_range
        
        if c['color'] == 'green':
            open_norm = 1 - ((c['body_y'] + c['body_h']) - min_low) / price_range
            close_norm = 1 - (c['body_y'] - min_low) / price_range
        else:
            open_norm = 1 - (c['body_y'] - min_low) / price_range
            close_norm = 1 - ((c['body_y'] + c['body_h']) - min_low) / price_range
            
        ohlc_data.append({
            'open': open_norm, 
            'high': high_norm, 
            'low': low_norm, 
            'close': close_norm
        })
    
    return ohlc_data
