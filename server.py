from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
import uvicorn
import asyncio
import os
import shutil
import uuid
import requests
from urllib.parse import urlencode

# --- OUR MODULES ---
from database import get_user_exchanges, get_user_decrypted_keys, get_user_language, save_user_language, execute_write_query, check_analysis_limit, get_user_risk_profile, get_referral_count
from exchange_utils import fetch_exchange_balance_safe, validate_exchange_credentials
from tx_verifier import verify_bsc_tx
import sqlite3
from database import DB_NAME

# --- ANALYZER MODULES ---
from chart_analyzer import analyze_chart_with_gpt
from core_analyzer import fetch_data, compute_features, generate_decisive_signal
from llm_explainer import get_explanation

# --- CONSTANTS ---
NGROK_URL = "http://167.99.130.80:8080"
YOUR_WALLET = os.getenv("YOUR_WALLET_ADDRESS")

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_details = exc.errors()
    print(f"❌ Validation Error: {error_details}")
    try:
        body = await request.body()
        print(f"📥 Received Body: {body.decode()}")
    except:
        pass
    return JSONResponse(
        status_code=422,
        content={"detail": error_details},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ... (Previous API code) ...

@app.post("/api/analyze")
async def analyze_chart_endpoint(file: UploadFile = File(...), user_id: int = 0):
    """
    1. Check daily limit
    2. Save image
    3. Analyze with GPT (OpenRouter) -> Ticker/TF
    4. Fetch market data -> Technical Analysis
    5. Return result
    """
    # 1. Check Limits (if user_id provided)
    if req.user_id > 0:
        can_analyze = check_analysis_limit(req.user_id)
        if not can_analyze:
             raise HTTPException(status_code=429, detail="Daily limit reached")

    # 2. Save File Temporarily
    temp_filename = f"temp_{uuid.uuid4()}.jpg"
    with open(temp_filename, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # 3. Vision Analysis (Ticker & Timeframe)
        vision_result = analyze_chart_with_gpt(temp_filename)
        
        if not vision_result:
            return {"status": "error", "msg": "Could not recognize chart"}
        
        ticker = vision_result['ticker']
        timeframe = vision_result['timeframe']
        
        print(f"🔍 Analyzing {ticker} on {timeframe}...")

        # 4. Technical Analysis (Core Engine)
        # Fetch Data
        df = fetch_data(ticker, timeframe=timeframe, limit=200)
        if df.empty:
             return {"status": "error", "msg": f"Could not fetch data for {ticker}"}
        
        # Compute Features
        df = compute_features(df)
        
        # Get Risk Profile (Balance/Risk%)
        risk_profile = get_user_risk_profile(user_id) if user_id > 0 else {'balance': 1000, 'risk_pct': 1.0}
        
        # Generate Signal
        trade_plan, context = generate_decisive_signal(df, ticker, risk_profile, timeframe)
        
        if not trade_plan:
            return {"status": "error", "msg": "Not enough data for analysis"}

        # 5. Return Result
        return {
            "status": "ok",
            "ticker": ticker,
            "timeframe": timeframe,
            "plan": trade_plan,
            "context": context
        }

    except Exception as e:
        print(f"❌ Analysis Error: {e}")
        return {"status": "error", "msg": str(e)}
    finally:
        # Cleanup
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

class ExplainRequest(BaseModel):
    user_id: int
    context: dict

@app.post("/api/explain")
async def explain_signal_endpoint(req: ExplainRequest):
    lang = get_user_language(req.user_id)
    explanation = get_explanation(req.context, lang)
    return {"status": "ok", "explanation": explanation}


@app.get("/cryptapi_webhook")

# --- MODELS ---
class ConnectRequest(BaseModel):
    user_id: int
    exchange: Optional[str] = None
    exchange_name: Optional[str] = None # Legacy support
    api_key: str
    secret: Optional[str] = None
    secret_key: Optional[str] = None # Legacy support
    password: Optional[str] = None
    strategy: str = 'ratner'
    reserve: Optional[float] = None
    reserve_amount: Optional[float] = None # Legacy support

class LanguageRequest(BaseModel):
    user_id: int
    language: str

class ReserveRequest(BaseModel):
    user_id: int
    exchange: str
    reserve: float

class TopUpRequest(BaseModel):
    user_id: int
    tx_id: str

# --- API ---

@app.get("/api/data")
async def get_user_data(user_id: int):
    """Returns total balance, connected exchanges list, current language, and internal token balance."""
    exchanges = get_user_exchanges(user_id)
    language = get_user_language(user_id)
    
    # Get internal token balance & UNC balance
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT token_balance, unc_balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    token_balance = res[0] if res else 0.0
    unc_balance = res[1] if (res and len(res) > 1 and res[1] is not None) else 0.0
    conn.close()
    
    total_balance = 0.0
    ex_list = []
    
    # Process exchanges concurrently? For simplicity loop (concurrent better)
    tasks = []
    
    for ex in exchanges:
        keys = get_user_decrypted_keys(user_id, ex['exchange_name'])
        if keys:
            tasks.append(
                fetch_exchange_balance_safe(
                    ex['exchange_name'], 
                    keys['apiKey'], 
                    keys['secret'], 
                    keys['password']
                )
            )
        else:
            tasks.append(asyncio.sleep(0, result=None)) # Dummy

    # Run all fetches
    if tasks:
        results = await asyncio.gather(*tasks)
    else:
        results = []

    for i, ex in enumerate(exchanges):
        bal = results[i]
        status = "Connected" if bal is not None else "Error"
        if not ex['is_active']: status = "Disconnected"
        
        real_bal = bal if bal is not None else 0.0
        if status == "Connected":
            total_balance += real_bal
            
        ex_list.append({
            "name": ex['exchange_name'].capitalize(),
            "status": status,
            "balance": real_bal,
            "icon": get_icon(ex['exchange_name']),
            "strategy": ex['strategy'],
            "reserve": ex['reserved_amount']
        })
        
    return {
        "totalBalance": total_balance,
        "pnl": "+0.0%", # Todo: calculate PnL
        "exchanges": ex_list,
        "language": language,
        "credits": token_balance,
        "unc_balance": unc_balance
    }

class PaymentRequest(BaseModel):
    user_id: int

@app.post("/api/create_payment")
async def create_payment_address(req: PaymentRequest):
    """Generates a personal deposit address via CryptAPI."""
    try:
        # NGROK_URL must be set (see top of file)
        callback_base = f"{NGROK_URL}/cryptapi_webhook"
        callback_params = {'user_id': req.user_id, 'secret': 'SOME_SECRET_WORD_TO_VALIDATE'}
        callback_url = f"{callback_base}?{urlencode(callback_params)}"
        
        api_url = "https://api.cryptapi.io/bep20/usdt/create/"
        params = {
            'callback': callback_url,
            'address': YOUR_WALLET,
            'convert': 0 # We want USDT directly
        }
        
        # Requests is blocking, but for low traffic prototype it's fine. 
        # Ideally use aiohttp/httpx.
        response = requests.get(api_url, params=params)
        data = response.json()
        
        if data.get('status') == 'success':
            return {
                "status": "ok",
                "address": data['address_in'],
                "min_deposit": data['minimum_transaction_coin']
            }
        else:
            return {"status": "error", "msg": "Provider Error"}
            
    except Exception as e:
        print(f"Payment Gen Error: {e}")
        return {"status": "error", "msg": str(e)}
async def top_up(req: TopUpRequest):
    success, result = verify_bsc_tx(req.tx_id, req.user_id)
    if success:
        return {"status": "ok", "msg": f"Successfully credited {result} USDT", "amount": result}
    else:
        raise HTTPException(status_code=400, detail=result)

@app.post("/api/language")
async def set_language(req: LanguageRequest):
    save_user_language(req.user_id, req.language)
    return {"status": "ok"}

@app.post("/api/reserve")
async def set_reserve(req: ReserveRequest):
    try:
        execute_write_query("""
            UPDATE user_exchanges 
            SET reserved_amount = ? 
            WHERE user_id = ? AND exchange_name = ?
        """, (req.reserve, req.user_id, req.exchange.lower()))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class UpdateParamsRequest(BaseModel):
    user_id: int
    exchange: str
    reserve: float
    risk_pct: float

@app.post("/api/update-params")
async def update_strategy_params(req: UpdateParamsRequest):
    try:
        execute_write_query("""
            UPDATE user_exchanges 
            SET reserved_amount = ?, risk_pct = ?
            WHERE user_id = ? AND exchange_name = ?
        """, (req.reserve, req.risk_pct, req.user_id, req.exchange.lower()))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DisconnectRequest(BaseModel):
    user_id: int
    exchange: str

class WithdrawRequest(BaseModel):
    user_id: int
    amount: float
    wallet_address: str

@app.post("/api/disconnect")
async def disconnect_exchange(req: DisconnectRequest):
    try:
        execute_write_query("""
            DELETE FROM user_exchanges 
            WHERE user_id = ? AND exchange_name = ?
        """, (req.user_id, req.exchange.lower()))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/connect")
async def connect_exchange(req: ConnectRequest):
    # Resolve fields (Legacy support)
    exchange = req.exchange or req.exchange_name
    secret = req.secret or req.secret_key
    reserve = req.reserve if req.reserve is not None else (req.reserve_amount if req.reserve_amount is not None else 0.0)
    
    # Resolve strategy (frontend sends 'trademax' for OKX, backend uses 'cgt')
    if req.strategy == 'trademax':
        req.strategy = 'cgt'
    
    if not exchange or not secret:
        raise HTTPException(status_code=422, detail="Missing required fields (exchange/secret)")

    # 1. Validate
    is_valid = await validate_exchange_credentials(exchange, req.api_key, secret, req.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid API Keys or Connection Failed")
    
    # 2. Save to DB
    try:
        from database import encrypt_data
        
        enc_secret = encrypt_data(secret)
        enc_pass = encrypt_data(req.password) if req.password else None
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Insert or Replace
        cursor.execute("""
            INSERT INTO user_exchanges (user_id, exchange_name, api_key, api_secret_encrypted, passphrase_encrypted, strategy, reserved_amount, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))
            ON CONFLICT(user_id, exchange_name) DO UPDATE SET
            api_key=excluded.api_key,
            api_secret_encrypted=excluded.api_secret_encrypted,
            passphrase_encrypted=excluded.passphrase_encrypted,
            strategy=excluded.strategy,
            reserved_amount=excluded.reserved_amount,
            is_active=1
        """, (req.user_id, exchange.lower(), req.api_key, enc_secret, enc_pass, req.strategy, reserve))
        
        conn.commit()
        conn.close()
        
        return {"status": "ok", "msg": "Exchange connected successfully"}
    except Exception as e:
        print(f"DB Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def get_icon(name):
    name = name.lower()
    if 'binance' in name: return "🔸"
    if 'okx' in name: return "⚫"
    if 'bingx' in name: return "🟦"
    if 'bybit' in name: return "⬛"
    return "🔹"

from telegram import Bot
from telegram.constants import ParseMode
from database import get_text, credit_tokens_from_payment

# --- CONFIG ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CRYPTAPI_SECRET = "SOME_SECRET_WORD_TO_VALIDATE" # Or load from env
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0")) if os.getenv("ADMIN_USER_ID") else None

# ... existing code ...

@app.post("/api/withdraw")
async def withdraw_funds(req: WithdrawRequest):
    from database import create_withdrawal_request
    
    try:
        # Validate amount
        if req.amount <= 0:
            raise HTTPException(status_code=400, detail="Invalid amount")
        
        # Validate wallet address
        if not req.wallet_address.startswith('0x') or len(req.wallet_address) != 42:
            raise HTTPException(status_code=400, detail="Invalid wallet address")
        
        # Create withdrawal request in database
        success = create_withdrawal_request(req.user_id, req.amount, req.wallet_address)
        
        if not success:
            raise HTTPException(status_code=400, detail="Insufficient balance or error creating request")
        
        # Notify admin via Telegram
        if TELEGRAM_TOKEN and ADMIN_USER_ID:
            try:
                bot = Bot(token=TELEGRAM_TOKEN)
                admin_message = (
                    f"⚠️ New Withdrawal Request ⚠️\n\n"
                    f"User ID: {req.user_id}\n"
                    f"Amount: {req.amount} USDT\n"
                    f"Wallet: <code>{req.wallet_address}</code>"
                )
                await bot.send_message(
                    chat_id=ADMIN_USER_ID,
                    text=admin_message,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                print(f"Failed to send Telegram notification: {e}")
        
        return {"success": True, "message": "Withdrawal request submitted"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Withdrawal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/referral_stats")
async def get_referral_stats(data: dict):
    """
    Get referral statistics for a user.
    Returns referral link and counts for each level.
    """
    try:
        user_id = data.get('user_id')
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id required")
        
        # Get bot username from environment
        bot_username = os.getenv('BOT_USERNAME', 'BlackAladinBot')
        
        # Generate referral link
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        
        # Get referral counts from database
        level_1_count = get_referral_count(user_id, level=1)
        level_2_count = get_referral_count(user_id, level=2)
        level_3_count = get_referral_count(user_id, level=3)
        
        return {
            'referral_link': referral_link,
            'level_1': level_1_count,
            'level_2': level_2_count,
            'level_3': level_3_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Referral stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cryptapi_webhook")
@app.post("/cryptapi_webhook")
async def cryptapi_webhook(request: Request):
    try:
        # CryptAPI sends data as Query Params for GET (and mostly for callbacks)
        params = dict(request.query_params)
        
        # 1. Validation
        if params.get('secret') != CRYPTAPI_SECRET:
             # Basic text response 'error' is what they expect if something wrong, 
             # but strictly they look for 'ok' to stop retries.
             return "error: invalid secret"

        # 2. Extract Data
        user_id = int(params.get('user_id', 0))
        amount = float(params.get('value_coin', 0))
        
        # 3. Credit Balance
        credit_tokens_from_payment(user_id, amount)
        
        # 4. Notify User via Telegram
        if TELEGRAM_TOKEN:
            try:
                bot = Bot(token=TELEGRAM_TOKEN)
                msg = get_text(user_id, "msg_payment_received_notification", amount=amount)
                
                # Send async using asyncio to not block
                # Since we are in an async FastAPI handler, we can await directly?
                # python-telegram-bot async methods are awaitable.
                await bot.send_message(chat_id=user_id, text=msg, parse_mode=ParseMode.HTML)
                print(f"✅ Notification sent to user {user_id}")
            except Exception as notify_error:
                print(f"❌ Failed to send notification: {notify_error}")
        
        # 5. Success Response
        return "*ok*"
        
    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        return "error"

# --- STATIC FILES ---
# Mount webapp to root
app.mount("/", StaticFiles(directory="webapp", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
