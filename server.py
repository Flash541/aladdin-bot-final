from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from telegram import Bot
from telegram.constants import ParseMode
import uvicorn
import asyncio
import os
import shutil
import uuid
import requests
import sqlite3
from urllib.parse import urlencode

from database import (
    get_user_exchanges, get_user_decrypted_keys, get_user_language,
    save_user_language, execute_write_query, check_analysis_limit,
    get_user_risk_profile, get_referral_count, get_coin_configs,
    add_coin_config, update_coin_config, delete_coin_config,
    validate_coin_allocation, DB_NAME, get_text, credit_tokens_from_payment,
    encrypt_data
)
from exchange_utils import fetch_exchange_balance_safe, validate_exchange_credentials
from tx_verifier import verify_bsc_tx
from chart_analyzer import analyze_chart_with_gpt
from core_analyzer import fetch_data, compute_features, generate_decisive_signal
from llm_explainer import get_explanation

NGROK_URL = os.getenv("WEBAPP_URL")
YOUR_WALLET = os.getenv("YOUR_WALLET_ADDRESS")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CRYPTAPI_SECRET = "SOME_SECRET_WORD_TO_VALIDATE"
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0")) if os.getenv("ADMIN_USER_ID") else None

app = FastAPI()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    print(f"❌ Validation Error: {errors}")
    try: print(f"📥 Body: {(await request.body()).decode()}")
    except: pass
    return JSONResponse(status_code=422, content={"detail": errors})


app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── models ──

class ConnectRequest(BaseModel):
    user_id: int
    exchange: Optional[str] = None
    exchange_name: Optional[str] = None
    api_key: str
    secret: Optional[str] = None
    secret_key: Optional[str] = None
    password: Optional[str] = None
    strategy: str = 'ratner'
    reserve: Optional[float] = None
    reserve_amount: Optional[float] = None
    reserved_amount: Optional[float] = None
    risk_pct: Optional[float] = None

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

class PaymentRequest(BaseModel):
    user_id: int

class UpdateParamsRequest(BaseModel):
    user_id: int
    exchange: str
    reserve: float
    risk_pct: float

class DisconnectRequest(BaseModel):
    user_id: int
    exchange: str

class WithdrawRequest(BaseModel):
    user_id: int
    amount: float
    wallet_address: str

class ExplainRequest(BaseModel):
    user_id: int
    context: dict

class CoinConfig(BaseModel):
    symbol: str
    capital: float
    risk: float

class SaveCoinConfigsRequest(BaseModel):
    user_id: int
    exchange: str
    coins: List[CoinConfig]

class UpdateCoinConfigRequest(BaseModel):
    user_id: int
    exchange: str
    symbol: str
    capital: float
    risk: float

class DeleteCoinConfigRequest(BaseModel):
    user_id: int
    exchange: str
    symbol: str

class SaveSingleCoinRequest(BaseModel):
    user_id: int
    exchange: str
    symbol: str
    reserved_amount: float = 0.0
    risk_pct: float = 0.0
    is_active: bool = True

class DeleteCoinConfig(BaseModel):
    user_id: int
    exchange: str
    symbol: str


# ── helpers ──

def get_icon(name):
    name = name.lower()
    if 'binance' in name: return "🔸"
    if 'okx' in name: return "⚫"
    if 'bingx' in name: return "🟦"
    if 'bybit' in name: return "⬛"
    return "🔹"


# ── api endpoints ──

@app.get("/api/data")
async def get_user_data(user_id: int):
    exchanges = get_user_exchanges(user_id)
    language = get_user_language(user_id)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT token_balance, unc_balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    token_balance = res[0] if res else 0.0
    unc_balance = res[1] if (res and len(res) > 1 and res[1] is not None) else 0.0
    conn.close()

    # fetch balances concurrently
    tasks = []
    for ex in exchanges:
        keys = get_user_decrypted_keys(user_id, ex['exchange_name'])
        if keys:
            tasks.append(fetch_exchange_balance_safe(ex['exchange_name'], keys['apiKey'], keys['secret'], keys['password']))
        else:
            tasks.append(asyncio.sleep(0, result=None))

    results = await asyncio.gather(*tasks) if tasks else []

    total_balance = 0.0
    ex_list = []
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
            "reserve": ex['reserved_amount'],
            "risk": ex['risk_pct'],
            "coins": get_coin_configs(ex['user_id'], ex['exchange_name'])
        })

    return {
        "totalBalance": total_balance,
        "pnl": "+0.0%",
        "exchanges": ex_list,
        "language": language,
        "credits": token_balance,
        "unc_balance": unc_balance
    }


@app.post("/api/analyze")
async def analyze_chart_endpoint(file: UploadFile = File(...), user_id: int = 0):
    if user_id > 0:
        if not check_analysis_limit(user_id):
            raise HTTPException(status_code=429, detail="Daily limit reached")

    temp_filename = f"temp_{uuid.uuid4()}.jpg"
    with open(temp_filename, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        vision_result = analyze_chart_with_gpt(temp_filename)
        if not vision_result:
            return {"status": "error", "msg": "Could not recognize chart"}

        ticker = vision_result['ticker']
        timeframe = vision_result['timeframe']
        print(f"🔍 Analyzing {ticker} on {timeframe}...")

        df = fetch_data(ticker, timeframe=timeframe, limit=200)
        if df.empty:
            return {"status": "error", "msg": f"Could not fetch data for {ticker}"}

        df = compute_features(df)
        risk_profile = get_user_risk_profile(user_id) if user_id > 0 else {'balance': 1000, 'risk_pct': 1.0}
        trade_plan, context = generate_decisive_signal(df, ticker, risk_profile, timeframe)

        if not trade_plan:
            return {"status": "error", "msg": "Not enough data for analysis"}

        return {"status": "ok", "ticker": ticker, "timeframe": timeframe, "plan": trade_plan, "context": context}

    except Exception as e:
        print(f"❌ Analysis Error: {e}")
        return {"status": "error", "msg": str(e)}
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)


@app.post("/api/explain")
async def explain_signal_endpoint(req: ExplainRequest):
    explanation = get_explanation(req.context, get_user_language(req.user_id))
    return {"status": "ok", "explanation": explanation}


@app.post("/api/create_payment")
async def create_payment_address(req: PaymentRequest):
    try:
        callback_url = f"{NGROK_URL}/cryptapi_webhook?{urlencode({'user_id': req.user_id, 'secret': CRYPTAPI_SECRET})}"
        resp = requests.get("https://api.cryptapi.io/bep20/usdt/create/", params={
            'callback': callback_url, 'address': YOUR_WALLET, 'convert': 0
        })
        data = resp.json()

        if data.get('status') == 'success':
            return {"status": "ok", "address": data['address_in'], "min_deposit": data['minimum_transaction_coin']}
        return {"status": "error", "msg": "Provider Error"}
    except Exception as e:
        print(f"Payment Gen Error: {e}")
        return {"status": "error", "msg": str(e)}


async def top_up(req: TopUpRequest):
    success, result = verify_bsc_tx(req.tx_id, req.user_id)
    if success:
        return {"status": "ok", "msg": f"Successfully credited {result} USDT", "amount": result}
    raise HTTPException(status_code=400, detail=result)


@app.post("/api/language")
async def set_language(req: LanguageRequest):
    save_user_language(req.user_id, req.language)
    return {"status": "ok"}


@app.post("/api/reserve")
async def set_reserve(req: ReserveRequest):
    try:
        execute_write_query("UPDATE user_exchanges SET reserved_amount = ? WHERE user_id = ? AND exchange_name = ?",
                            (req.reserve, req.user_id, req.exchange.lower()))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/update-params")
async def update_strategy_params(req: UpdateParamsRequest):
    try:
        execute_write_query(
            "UPDATE user_exchanges SET reserved_amount = ?, risk_pct = ? WHERE user_id = ? AND exchange_name = ?",
            (req.reserve, req.risk_pct, req.user_id, req.exchange.lower()))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/disconnect")
async def disconnect_exchange(req: DisconnectRequest):
    try:
        execute_write_query("DELETE FROM user_exchanges WHERE user_id = ? AND exchange_name = ?",
                            (req.user_id, req.exchange.lower()))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/validate_okx_balance")
async def validate_okx_balance(request: Request):
    try:
        body = await request.json()
        api_key = body.get('api_key')
        secret_key = body.get('secret_key')
        passphrase = body.get('passphrase')

        if not all([api_key, secret_key, passphrase]):
            raise HTTPException(status_code=400, detail="Missing API credentials")

        balance_info = await validate_exchange_credentials('okx', api_key, secret_key, passphrase)
        if not balance_info:
            raise HTTPException(status_code=400, detail="Invalid API credentials or connection failed")

        return {"status": "ok", "balance": balance_info.get('total', 0.0)}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] validate_okx_balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/connect_exchange")
async def connect_exchange(req: ConnectRequest):
    exchange = req.exchange or req.exchange_name
    secret = req.secret or req.secret_key
    reserve = req.reserve if req.reserve is not None else (req.reserve_amount if req.reserve_amount is not None else (req.reserved_amount if req.reserved_amount is not None else 0.0))

    # normalize strategy names
    if req.strategy == 'trademax': req.strategy = 'cgt'
    if req.strategy == 'bingbot': req.strategy = 'ratner'
    if exchange and exchange.lower() == 'bingx' and req.strategy not in ['ratner']:
        req.strategy = 'ratner'

    if not exchange or not secret:
        raise HTTPException(status_code=422, detail="Missing required fields (exchange/secret)")

    balance_info = await validate_exchange_credentials(exchange, req.api_key, secret, req.password)
    if not balance_info:
        raise HTTPException(status_code=400, detail="Invalid API Keys or Connection Failed")

    total_balance = balance_info.get('total', 0.0)
    if (total_balance - reserve) < 10:
        raise HTTPException(status_code=400,
            detail=f"Insufficient trading balance. Available: {total_balance:.2f}, Reserve: {reserve:.2f}. Need > $10.")

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_exchanges (user_id, exchange_name, api_key, api_secret_encrypted, passphrase_encrypted, strategy, reserved_amount, risk_pct, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))
            ON CONFLICT(user_id, exchange_name) DO UPDATE SET
            api_key=excluded.api_key, api_secret_encrypted=excluded.api_secret_encrypted,
            passphrase_encrypted=excluded.passphrase_encrypted, strategy=excluded.strategy,
            reserved_amount=excluded.reserved_amount, risk_pct=excluded.risk_pct, is_active=1
        """, (req.user_id, exchange.lower(), req.api_key, encrypt_data(secret),
              encrypt_data(req.password) if req.password else None, req.strategy, reserve, req.risk_pct))
        conn.commit()
        conn.close()
        return {"status": "ok", "msg": "Exchange connected successfully"}
    except Exception as e:
        print(f"DB Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/withdraw")
async def withdraw_funds(req: WithdrawRequest):
    from database import create_withdrawal_request

    try:
        if req.amount <= 0:
            raise HTTPException(status_code=400, detail="Invalid amount")
        if not req.wallet_address.startswith('0x') or len(req.wallet_address) != 42:
            raise HTTPException(status_code=400, detail="Invalid wallet address")

        success = create_withdrawal_request(req.user_id, req.amount, req.wallet_address)
        if not success:
            raise HTTPException(status_code=400, detail="Insufficient balance or error")

        if TELEGRAM_TOKEN and ADMIN_USER_ID:
            try:
                bot = Bot(token=TELEGRAM_TOKEN)
                await bot.send_message(
                    chat_id=ADMIN_USER_ID, parse_mode=ParseMode.HTML,
                    text=f"⚠️ New Withdrawal Request ⚠️\n\nUser ID: {req.user_id}\nAmount: {req.amount} USDT\nWallet: <code>{req.wallet_address}</code>"
                )
            except Exception as e:
                print(f"Telegram notification failed: {e}")

        return {"success": True, "message": "Withdrawal request submitted"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Withdrawal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── coin config endpoints ──

@app.post("/api/save_coin_configs")
async def save_coin_configs_endpoint(req: SaveCoinConfigsRequest):
    try:
        for coin in req.coins:
            validation = validate_coin_allocation(req.user_id, req.exchange, coin.capital, coin.symbol)
            if not validation['valid']:
                raise HTTPException(status_code=400, detail=validation['message'])

        for coin in req.coins:
            add_coin_config(user_id=req.user_id, exchange=req.exchange.lower(),
                            symbol=coin.symbol, capital=coin.capital, risk_pct=coin.risk)

        return {"success": True, "message": "Coin configs saved"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Save coin configs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/get_coin_configs")
async def get_coin_configs_endpoint(user_id: int, exchange: str):
    try:
        return {"success": True, "coins": get_coin_configs(user_id, exchange.lower())}
    except Exception as e:
        print(f"Get coin configs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/update_coin_config")
async def update_coin_config_endpoint(req: UpdateCoinConfigRequest):
    try:
        validation = validate_coin_allocation(req.user_id, req.exchange.lower(), req.capital, req.symbol)
        if not validation['valid']:
            raise HTTPException(status_code=400, detail=validation['message'])

        update_coin_config(user_id=req.user_id, exchange=req.exchange.lower(),
                           symbol=req.symbol, capital=req.capital, risk_pct=req.risk)
        return {"success": True, "message": "Coin config updated"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Update coin config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/delete_coin_config")
async def delete_coin_config_endpoint(req: DeleteCoinConfigRequest):
    try:
        delete_coin_config(req.user_id, req.exchange.lower(), req.symbol)
        return {"success": True, "message": "Coin config deleted"}
    except Exception as e:
        print(f"Delete coin config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/referral_stats")
async def get_referral_stats(data: dict):
    try:
        user_id = data.get('user_id')
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id required")

        bot_username = os.getenv('BOT_USERNAME', 'BlackAladinBot')
        return {
            'referral_link': f"https://t.me/{bot_username}?start={user_id}",
            'level_1': get_referral_count(user_id, level=1),
            'level_2': get_referral_count(user_id, level=2),
            'level_3': get_referral_count(user_id, level=3)
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
        params = dict(request.query_params)

        if params.get('secret') != CRYPTAPI_SECRET:
            return "error: invalid secret"

        user_id = int(params.get('user_id', 0))
        amount = float(params.get('value_coin', 0))
        credit_tokens_from_payment(user_id, amount)

        if TELEGRAM_TOKEN:
            try:
                bot = Bot(token=TELEGRAM_TOKEN)
                await bot.send_message(chat_id=user_id, text=get_text(user_id, "msg_payment_received_notification", amount=amount), parse_mode=ParseMode.HTML)
            except Exception as e:
                print(f"❌ Notification failed: {e}")

        return "*ok*"
    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        return "error"


@app.post("/api/save_coin_config")
async def save_single_coin_endpoint(req: SaveSingleCoinRequest):
    try:
        add_coin_config(user_id=req.user_id, exchange=req.exchange.lower(),
                        symbol=req.symbol, capital=req.reserved_amount, risk_pct=req.risk_pct)
        return {"status": "ok", "msg": "Coin saved"}
    except Exception as e:
        print(f"Error saving coin: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/delete_coin_config")
async def delete_coin_config_alt(req: DeleteCoinConfig):
    try:
        delete_coin_config(req.user_id, req.exchange.lower(), req.symbol)
        return {"status": "ok", "msg": "Coin deleted"}
    except Exception as e:
        print(f"Error deleting coin: {e}")
        raise HTTPException(status_code=500, detail=str(e))


app.mount("/", StaticFiles(directory="webapp", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
