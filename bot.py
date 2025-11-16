# bot.py (v23 - Admin Promocodes & God Mode & View Chart)

import os
import asyncio
import pandas as pd
import requests
import time
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler, CallbackQueryHandler)
from telegram.constants import ParseMode

from database import * # Import all our new DB functions including risk management and promocodes
from chart_analyzer import find_candlesticks, candlesticks_to_ohlc
from core_analyzer import fetch_data, compute_features, generate_decisive_signal, generate_signal
from llm_explainer import get_explanation

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY")
WALLET_ADDRESS = os.getenv("YOUR_WALLET_ADDRESS")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID"))  # Важно: конвертируем в int
REFERRAL_REWARD = 24.5
PAYMENT_AMOUNT = 49
USDT_CONTRACT_ADDRESS = "0x55d398326f99059fF775485246999027B3197955"

# Conversation states
ASK_AMOUNT, ASK_WALLET = range(2)  # Withdrawal
ASK_BALANCE, ASK_RISK_PCT = range(2, 4)  # Risk management
ASK_PROMO_COUNT = range(4, 5)  # Promo code generation



async def verify_payment_and_activate(tx_hash: str, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """
    ФИНАЛЬНАЯ И ИСПРАВЛЕННАЯ ВЕРСИЯ: Проверяет платеж и начисляет реферальные бонусы с правильными отступами.
    """
    if is_tx_hash_used(tx_hash):
        await context.bot.send_message(user_id, "❌ Verification failed.\nReason: This transaction has already been used.")
        return

    # Etherscan V2 API URL for BSC (chainid=56)
    url = f"https://api.etherscan.io/v2/api?chainid=56&module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}&apikey={BSCSCAN_API_KEY}"
    
    try:
        print(f"DEBUG: Requesting TxInfo from Etherscan V2 for {tx_hash}")
        response = requests.get(url, timeout=15)
        data = response.json()
        
        print(f"DEBUG: Etherscan V2 API Response: {data}")

        if "result" not in data:
            await context.bot.send_message(user_id, "❌ Verification failed.\nReason: Invalid response from blockchain explorer.")
            return
            
        tx = data.get("result")
        
        if not isinstance(tx, dict) or not tx:
            error_message = data.get('message', 'Transaction not found or API error.')
            if 'Invalid API Key' in str(data):
                await context.bot.send_message(user_id, "❌ Verification failed.\nReason: API Key is invalid. Please contact support.")
            else:
                await context.bot.send_message(user_id, "⏳ Verification pending.\nReason: Please wait a few minutes and try again.")
            return
        
        # --- Проверка деталей транзакции (без изменений) ---
        contract_address = tx.get('to', '').lower()
        tx_input = tx.get('input', '')
        if contract_address != USDT_CONTRACT_ADDRESS.lower() or len(tx_input) < 138:
            await context.bot.send_message(user_id, "❌ Verification failed.\nReason: Payment was not made in USDT (BEP-20)."); return
        to_address_in_data = tx_input[34:74]
        if WALLET_ADDRESS[2:].lower() not in to_address_in_data.lower():
            await context.bot.send_message(user_id, "❌ Verification failed.\nReason: Payment sent to wrong address."); return
        amount_token = int(tx_input[74:138], 16) / (10**18)
        if not (PAYMENT_AMOUNT <= amount_token < PAYMENT_AMOUNT + 0.1):
            await context.bot.send_message(user_id, f"❌ Verification failed.\nReason: Incorrect amount. Expected {PAYMENT_AMOUNT}, received {amount_token:.4f} USDT."); return
            
        # --- УСПЕХ! АКТИВАЦИЯ И РЕФЕРАЛЫ ---
        activate_user_subscription(user_id)
        mark_tx_hash_as_used(tx_hash)
        
        # Новая клавиатура
        main_keyboard = [["Analyze Chart 📈", "View Chart 📊"], ["Profile 👤", "Risk Settings ⚙️"]]
        main_reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
        
        await context.bot.send_message(user_id, "✅ Payment successful! Welcome to Aladdin. You now have full access.", reply_markup=main_reply_markup)
        
        # --- ИСПРАВЛЕНИЕ: Этот блок теперь НАХОДИТСЯ ВНУТРИ `try` ---
        # 1. Находим прямого реферера
        referrer_id = get_referrer(user_id)
        
        # 2. Если он есть, начисляем награду
        if referrer_id:
            credit_referral_tokens(referrer_id, REFERRAL_REWARD)
            try:
                await context.bot.send_message(
                    referrer_id, 
                    f"🎉 Congratulations! You received {REFERRAL_REWARD} tokens for a successful referral."
                )
            except Exception as e:
                print(f"Could not notify referrer {referrer_id}: {e}")
                
    except Exception as e:
        print(f"Error in verify_payment: {e}")
        await context.bot.send_message(user_id, "❌ An unexpected error occurred during verification.")

async def simulate_thinking(duration=2):
    """Задержка для естественности"""
    await asyncio.sleep(duration)

    
# --- ИСПРАВЛЕННЫЙ ФОРМАТТЕР (ВОЗВРАЩАЕТ ТОЛЬКО ТЕКСТ) ---
def format_plan_to_message(plan):
    symbol = plan.get('symbol', 'N/A')
    timeframe = plan.get('timeframe', 'N/A')
    view = plan.get('view', 'neutral')
    notes = plan.get('notes', 'No notes.')
    
    if view == 'long': 
        icon = "🟢"
        title = f"<b>Long Idea: ${symbol}</b> ({timeframe})"
    elif view == 'short': 
        icon = "🔴"
        title = f"<b>Short Idea: ${symbol}</b> ({timeframe})"
    else:
        icon = "⚪️"
        title = f"<b>Analysis: ${symbol}</b> ({timeframe})"
        return f"{icon} {title}\n\n{notes}"
        
    entry_zone = plan.get('entry_zone', ['N/A'])
    stop_loss = plan.get('stop', 'N/A')
    targets = plan.get('targets', ['N/A'])
    
    message = (f"{icon} {title}\n\n"
               f"<b>🔹 Entry Zone:</b> <code>{entry_zone[0]} - {entry_zone[1]}</code>\n"
               f"<b>🔸 Stop Loss:</b> <code>{stop_loss}</code>\n"
               f"<b>🎯 Target(s):</b> <code>{', '.join(map(str, targets))}</code>\n\n"
               f"📝 <b>Rationale:</b>\n<i>{notes}</i>")
               
    if plan.get('position_size_asset'):
        pos_size_asset = plan.get('position_size_asset', 'N/A')
        symbol_base = plan.get('symbol', 'ASSET').replace('USDT', '')
        pos_size_usd = plan.get('position_size_usd', 'N/A')
        potential_loss = plan.get('potential_loss_usd', 'N/A')
        message += (f"\n\n<b>Risk Profile:</b>\n"
                    f"  - Position Size: <code>{pos_size_asset} {symbol_base}</code> ({pos_size_usd})\n"
                    f"  - Max Loss on this trade: <code>{potential_loss}</code>")
                    
    message += "\n\n<pre>⚠️ Not financial advice. DYOR.</pre>"
    return message

# def blocking_chart_analysis(file_path: str, risk_settings: dict, message_to_edit, bot_instance, loop) -> tuple:
#     def update_progress(text):
#         async def edit():
#             try: await message_to_edit.edit_text(text, parse_mode=ParseMode.HTML)
#             except Exception as e: print(f"Progress update failed: {e}")
#         future = asyncio.run_coroutine_threadsafe(edit(), loop)
#         future.result()

#     try:
#         update_progress("🔍 Analyzing chart with AI (recognizing symbol and timeframe)...")
#         time.sleep(5) # GPT-4 Vision может думать дольше
        
#         # --- ИЗМЕНЕНИЕ: find_candlesticks теперь возвращает словарь ---
#         candlesticks, chart_info = find_candlesticks(file_path)
        
#         df = None
#         trade_plan = None
#         analysis_context = None
        
#         ticker = chart_info.get('ticker') if chart_info else None
#         timeframe_for_analysis = chart_info.get('timeframe', '15m') if chart_info else '15m'
        
#         # --- СЦЕНАРИЙ 1: ТИКЕР НАЙДЕН ---
#         if ticker:
#             update_progress(f"✅ AI identified: <b>{ticker}</b> at <b>{timeframe_for_analysis}</b>\n\nFetching live data...")
#             time.sleep(2)
            
#             base_currency = None; known_quotes = ["USDT", "BUSD", "TUSD", "USDC", "USD"]
#             for quote in known_quotes:
#                 if ticker.endswith(quote): base_currency = ticker[:-len(quote)]; break
            
#             if base_currency:
#                 symbol_for_api = f"{base_currency}/USDT"
                
#                 # --- ИЗМЕНЕНИЕ: Используем распознанный таймфрейм ---
#                 df = fetch_data(symbol=symbol_for_api, timeframe=timeframe_for_analysis)
                
#                 if df is not None and not df.empty:
#                     update_progress("🤖 Running technical analysis...")
#                     time.sleep(4)
#                     features = compute_features(df)
#                     trade_plan, analysis_context = generate_decisive_signal(
#                         features, symbol_ccxt=symbol_for_api, risk_settings=risk_settings, timeframe=timeframe_for_analysis
#                     )
#                 else:
#                     return None, None, f"❌ Found {ticker}, but couldn't fetch its data from the exchange."
#             else:
#                 ticker = None # Сбрасываем, если тикер не похож на пару

#         # --- СЦЕНАРИЙ 2: ТИКЕР НЕ НАЙДЕН ---
#         if ticker is None:
#             # Этот фоллбэк на анализ по структуре теперь менее важен, но пусть останется
#             update_progress("📈 Ticker not recognized. Analyzing chart structure only...")
#             time.sleep(3)
#             if candlesticks and len(candlesticks) >= 30:
#                 ohlc_list = candlesticks_to_ohlc(candlesticks)
#                 df = pd.DataFrame(ohlc_list); df['volume'] = 1000
#                 features = compute_features(df)
#                 trade_plan, analysis_context = generate_decisive_signal(
#                     features, symbol_ccxt="USER_CHART", risk_settings=risk_settings, timeframe="Chart"
#                 )
#             else:
#                 return None, None, "❌ Sorry, I couldn't recognize a valid ticker or enough candlesticks."

#         if not trade_plan:
#             return None, None, "❌ Sorry, analysis did not produce a valid trade plan."

#         update_progress("🎯 Generating final report...")
#         time.sleep(2)
#         return trade_plan, analysis_context, None

#     except Exception as e:
#         print(f"Error in blocking_chart_analysis: {e}")
#         return None, None, "❌ An unexpected error occurred during the analysis."


# # --- ФИНАЛЬНЫЙ "ЛЕГКИЙ" ОБРАБОТЧИК ---
# async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = update.effective_user.id
#     if not has_access(user_id):
#         await update.message.reply_text("❌ Access Required. Please use /start to activate.")
#         return
        
#     risk_settings = get_user_risk_settings(user_id)
#     file_path = f'chart_for_{user_id}.jpg'
    
#     try:
#         photo_file = await update.message.photo[-1].get_file()
#         await photo_file.download_to_drive(file_path)
        
#         processing_message = await update.message.reply_text("📨 Chart received! Your request is in the queue...")
        
#         loop = asyncio.get_running_loop()
        
#         trade_plan, analysis_context, error_message = await asyncio.to_thread(
#             blocking_chart_analysis, file_path, risk_settings, processing_message, context.bot, loop
#         )
        
#         if error_message:
#             await processing_message.edit_text(error_message)
#             return
            
#         context.user_data['last_analysis_context'] = analysis_context
        
#         message_text = format_plan_to_message(trade_plan)
        
#         profile = get_user_profile(user_id); referral_link = None
#         if profile and profile.get('ref_code'):
#             bot_username = (await context.bot.get_me()).username
#             referral_link = f"https://t.me/{bot_username}?start={profile['ref_code']}"
        
#         keyboard = []
#         if referral_link:
#             keyboard.append([InlineKeyboardButton("Powered by Aladdin 🧞‍♂️ (Join Here)", url=referral_link)])
#         keyboard.append([InlineKeyboardButton("Explain Factors 🔬", callback_data="explain_analysis")])
#         reply_markup = InlineKeyboardMarkup(keyboard)

#         await processing_message.edit_text(text=message_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

#     except Exception as e:
#         print(f"Error in photo_handler: {e}")
#         await update.message.reply_text("❌ An unexpected error occurred.")

def blocking_chart_analysis(file_path: str, risk_settings: dict, message_to_edit, bot_instance, loop) -> tuple:
    # Внутренняя функция для безопасного обновления сообщения из потока
    def update_progress(text):
        async def edit():
            try: await message_to_edit.edit_text(text, parse_mode=ParseMode.HTML)
            except Exception as e: print(f"Progress update failed: {e}")
        # Безопасно отправляем асинхронную задачу в основной поток
        future = asyncio.run_coroutine_threadsafe(edit(), loop)
        future.result() # Ждем завершения

    try:
        update_progress("🔍 Analyzing chart with AI...")
        time.sleep(5) # Имитация работы GPT-Vision
        candlesticks, chart_info = find_candlesticks(file_path)
        
        trade_plan, analysis_context = None, None
        ticker = chart_info.get('ticker') if chart_info else None
        
        # --- ИСПРАВЛЕННАЯ ЛОГИКА IF/ELSE ---
        
        # СЦЕНАРИЙ 1: ТИКЕР НАЙДЕН
        if ticker:
            timeframe = chart_info.get('timeframe', '15m')
            update_progress(f"✅ AI identified: <b>{ticker}</b> at <b>{timeframe}</b>\n\nFetching live data...")
            time.sleep(2)
            
            base_currency = None; known_quotes = ["USDT", "BUSD", "TUSD", "USDC", "USD"]
            for quote in known_quotes:
                if ticker.endswith(quote):
                    base_currency = ticker[:-len(quote)]; break
            
            if base_currency:
                symbol_for_api = f"{base_currency}/USDT" # Всегда используем USDT для Binance
                df = fetch_data(symbol=symbol_for_api, timeframe=timeframe)
                
                if df is not None and not df.empty:
                    update_progress("🤖 Running technical analysis...")
                    time.sleep(4)
                    features = compute_features(df)
                    trade_plan, analysis_context = generate_decisive_signal(
                        features, symbol_ccxt=symbol_for_api, risk_settings=risk_settings, timeframe=timeframe
                    )
                else: # Если не удалось получить данные по найденному тикеру
                    return None, None, f"❌ Found {ticker}, but couldn't fetch data from the exchange."
            else: # Если тикер не похож на пару
                return None, None, f"❌ AI recognized '{ticker}', but it's not a standard pair."

        # СЦЕНАРИЙ 2: ТИКЕР НЕ НАЙДЕН
        else:
            update_progress("📈 Ticker not recognized. Analyzing chart structure...")
            time.sleep(3)
            if candlesticks and len(candlesticks) >= 30:
                ohlc_list = candlesticks_to_ohlc(candlesticks)
                df = pd.DataFrame(ohlc_list); df['volume'] = 1000
                features = compute_features(df)
                trade_plan, analysis_context = generate_decisive_signal(
                    features, symbol_ccxt="USER_CHART", risk_settings=risk_settings, timeframe="Chart"
                )
            else:
                return None, None, "❌ Sorry, I couldn't recognize a ticker or enough candlesticks."

        if not trade_plan:
            return None, None, "❌ Analysis did not produce a valid trade plan. The chart might be too ambiguous."

        update_progress("🎯 Generating final report...")
        time.sleep(2)
        return trade_plan, analysis_context, None

    except Exception as e:
        print(f"Error in blocking_chart_analysis: {e}")
        return None, None, "❌ An unexpected error occurred during analysis."


# --- "ЛЕГКИЙ" ОБРАБОТЧИК ФОТО ---
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not has_access(user_id):
        await update.message.reply_text("❌ Access Required. Please use /start to activate.")
        return
        
    risk_settings = get_user_risk_settings(user_id)
    file_path = f'chart_for_{user_id}.jpg'
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        await photo_file.download_to_drive(file_path)
        
        processing_message = await update.message.reply_text("📨 Chart received! Your request is in the queue...")
        
        loop = asyncio.get_running_loop()
        
        trade_plan, analysis_context, error_message = await asyncio.to_thread(
            blocking_chart_analysis, file_path, risk_settings, processing_message, context.bot, loop
        )
        
        if error_message:
            await processing_message.edit_text(error_message)
            return
            
        context.user_data['last_analysis_context'] = analysis_context
        
        message_text = format_plan_to_message(trade_plan)
        
        profile = get_user_profile(user_id); referral_link = None
        if profile and profile.get('ref_code'):
            bot_username = (await context.bot.get_me()).username
            referral_link = f"https://t.me/{bot_username}?start={profile['ref_code']}"
        
        keyboard = []
        if referral_link:
            keyboard.append([InlineKeyboardButton("Powered by Aladdin 🧞‍♂️ (Join Here)", url=referral_link)])
        keyboard.append([InlineKeyboardButton("Explain Factors 🔬", callback_data="explain_analysis")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await processing_message.edit_text(text=message_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

    except Exception as e:
        print(f"Error in photo_handler: {e}")
        await update.message.reply_text("❌ An unexpected error occurred.")


# --- ФУНКЦИЯ ПРОВЕРКИ ДОСТУПА С УЧЕТОМ АДМИНА ---
def has_access(user_id: int) -> bool:
    """Проверяет, активна ли подписка ИЛИ является ли пользователь админом."""
    if user_id == ADMIN_USER_ID:
        return True # "Режим Бога" для админа
    
    status = get_user_status(user_id)
    return status == 'active'

# --- Enhanced Bot Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Check for referral code in start parameter
    referrer_id = None
    if context.args and context.args[0].startswith('ref_'):
        code = context.args[0]
        referrer_id = get_user_by_referral_code(code)
    
    add_user(user.id, user.username, referrer_id)
    status = get_user_status(user.id)

    if status == 'active':
        # --- ОСНОВНЫЕ КНОПКИ ВНИЗУ С VIEW CHART ---
        main_keyboard = [
            ["Analyze Chart 📈", "View Chart 📊"],
            ["Profile 👤", "Risk Settings ⚙️"]
        ]
        main_reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Welcome back! Your subscription is active. Use the buttons below to start.",
            reply_markup=main_reply_markup
        )
        
    else: # Если подписка не активна
        payment_message = (
            f"Welcome to <b>Aladdin Bot!</b> 🧞‍♂️\n\n"
            f"To activate your 1-month subscription, please send exactly <b>{PAYMENT_AMOUNT} USDT</b> (BEP-20) to:\n\n"
            f"<code>{WALLET_ADDRESS}</code>\n\n"
            f"Then, paste the <b>Transaction Hash (TxID)</b> here to verify.\n\n"
            f"<i>Alternatively, you can use a promo code if you have one!</i>"
        )
        await update.message.reply_text(payment_message, parse_mode=ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = get_user_profile(user_id)
    
    if not profile:
        await update.message.reply_text("Couldn't find your profile. Please /start the bot.")
        return
        
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={profile['ref_code']}"
    
    status_emoji = "✅ Active" if profile['status'] == 'active' else "⏳ Pending Payment"
    expiry_text = f"Expires on: {profile['expiry']}" if profile['expiry'] else "N/A"
    
    profile_text = (
        f"👤 <b>Your Profile</b>\n\n"
        f"<b>Status:</b> {status_emoji}\n"
        f"<b>Subscription:</b> {expiry_text}\n"
        f"<b>Token Balance:</b> {profile['balance']:.2f} Tokens\n"
        f"<b>Trading Balance:</b> ${profile['account_balance']:,.2f}\n"
        f"<b>Risk per Trade:</b> {profile['risk_pct']}%\n\n"
        f"🔗 <b>Your Referral Link:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"Invite friends and earn tokens!\n"
        f"Level 1: 15 tokens\n"
        f"Level 2: 10 tokens\n"
        f"Level 3: 5 tokens"
    )
    keyboard = [["Withdraw Tokens 💵", "Risk Settings ⚙️", "Back to Menu ↩️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(profile_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced help command with risk management info."""
    user_id = update.effective_user.id
    status = get_user_status(user_id)
    
    if status == 'active':
        help_text = (
            "🧞‍♂️ <b>Aladdin - Crypto Chart Analyst</b>\n\n"
            "Here's how you can use me:\n\n"
            "1. Press the <b>'Analyze Chart 📈'</b> button below.\n"
            "2. Send me a clear screenshot of a candlestick chart.\n"
            "3. I will analyze it and provide a technical outlook.\n\n"
            "<b>What I can do:</b>\n"
            "• Recognize cryptocurrency symbols from charts\n"
            "• Fetch live market data from Binance\n"
            "• Analyze technical indicators (EMA, RSI, ATR, Bollinger Bands)\n"
            "• Provide trading ideas with entry zones and targets\n"
            "• Calculate position sizes based on your risk profile\n\n"
            "<b>Risk Management:</b>\n"
            "• Set your account balance and risk percentage\n"
            "• Get automatic position size calculations\n"
            "• Manage your risk per trade\n\n"
            "<b>Referral System:</b>\n"
            "• Earn 15 tokens for Level 1 referrals\n"
            "• Earn 10 tokens for Level 2 referrals\n"
            "• Earn 5 tokens for Level 3 referrals\n"
            "• Withdraw tokens to your wallet\n\n"
            "<b>Available Commands:</b>\n"
            "/start - Restart the bot\n"
            "/help - Show this help message\n"
            "/profile - View your profile\n"
            "/risk - Set up risk management\n\n"
            "<i>Your access is active! Press the buttons below to get started!</i>"
        )
    else:
        help_text = (
            "🧞‍♂️ <b>Aladdin - Crypto Chart Analyst</b>\n\n"
            "This bot provides AI-powered technical analysis of cryptocurrency charts.\n\n"
            "<b>How it works:</b>\n"
            "1. Send a screenshot of any crypto chart\n"
            "2. I'll recognize the symbol and analyze it\n"
            "3. Get detailed trading insights with entry/exit points\n\n"
            "<b>Subscription:</b>\n"
            f"• One-time payment of {PAYMENT_AMOUNT} USDT for 1 month access\n"
            "• Or use a valid promo code\n"
            "• Full access to all analysis features\n"
            "• Referral system to earn tokens\n"
            "• Risk management with position sizing\n\n"
            "<b>To get started:</b>\n"
            "Use /start to activate your access with payment or promo code.\n\n"
            "<i>Use /start to begin the activation process!</i>"
        )
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

# --- Withdrawal Conversation Handlers ---

async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please enter the amount of tokens you wish to withdraw:", reply_markup=ReplyKeyboardRemove())
    return ASK_AMOUNT

async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        if amount <= 0: raise ValueError
        
        profile = get_user_profile(update.effective_user.id)
        if amount > profile['balance']:
            await update.message.reply_text(f"Insufficient balance. You only have {profile['balance']:.2f} tokens. Please enter a valid amount.")
            return ASK_AMOUNT
            
        context.user_data['withdraw_amount'] = amount
        await update.message.reply_text("Great! Now, please paste your BEP-20 (BSC) wallet address for the withdrawal.")
        return ASK_WALLET
    except ValueError:
        await update.message.reply_text("Invalid amount. Please enter a number greater than 0.")
        return ASK_AMOUNT

async def ask_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet_address = update.message.text
    if not (wallet_address.startswith("0x") and len(wallet_address) == 42):
        await update.message.reply_text("Invalid wallet address. Please paste a valid BEP-20 address (starts with 0x).")
        return ASK_WALLET
        
    amount = context.user_data['withdraw_amount']
    user_id = update.effective_user.id
    
    # Create request in DB
    success = create_withdrawal_request(user_id, amount, wallet_address)
    
    if not success:
        await update.message.reply_text("An error occurred. Please try again.")
        return ConversationHandler.END

    # Notify admin
    if ADMIN_USER_ID:
        admin_message = (
            f"⚠️ New Withdrawal Request ⚠️\n\n"
            f"User ID: {user_id}\n"
            f"Username: @{update.effective_user.username}\n"
            f"Amount: {amount} tokens\n"
            f"Wallet: <code>{wallet_address}</code>"
        )
        await context.bot.send_message(ADMIN_USER_ID, admin_message, parse_mode=ParseMode.HTML)
    
    # Возвращаем к основной клавиатуре с View Chart
    keyboard = [
        ["Analyze Chart 📈", "View Chart 📊"],
        ["Profile 👤", "Risk Settings ⚙️"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("✅ Your withdrawal request has been submitted! Please allow up to 24 hours for processing.", reply_markup=reply_markup)
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["Analyze Chart 📈", "View Chart 📊"],
        ["Profile 👤", "Risk Settings ⚙️"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Operation cancelled.", reply_markup=reply_markup)
    return ConversationHandler.END

# --- RISK MANAGEMENT CONVERSATION ---

async def risk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the risk settings conversation."""
    user_id = update.effective_user.id
    settings = get_user_risk_settings(user_id)
    await update.message.reply_text(
        f"Let's set up your risk profile.\n\n"
        f"Your current trading account balance is set to: ${settings['balance']:,.2f}\n"
        f"Please enter your new account balance (e.g., 10000), or type 'skip' to keep the current value.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ASK_BALANCE

async def ask_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if text != 'skip':
        try:
            balance = float(text)
            if balance <= 0: raise ValueError
            context.user_data['risk_balance'] = balance
        except ValueError:
            await update.message.reply_text("Invalid number. Please enter a positive number for your balance (e.g., 10000).")
            return ASK_BALANCE
    
    user_id = update.effective_user.id
    settings = get_user_risk_settings(user_id)
    await update.message.reply_text(
        f"Great. Your current risk per trade is: {settings['risk_pct']}%\n"
        f"Please enter your new risk percentage (e.g., 1 for 1%), or type 'skip' to keep it."
    )
    return ASK_RISK_PCT

async def ask_risk_pct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    settings = get_user_risk_settings(user_id)
    
    # Get balance from previous step or DB
    balance = context.user_data.get('risk_balance', settings['balance'])
    risk_pct = settings['risk_pct']
    
    text = update.message.text.lower()
    if text != 'skip':
        try:
            risk_pct_new = float(text)
            if not (0 < risk_pct_new <= 100): raise ValueError
            risk_pct = risk_pct_new
        except ValueError:
            await update.message.reply_text("Invalid percentage. Please enter a number between 0 and 100 (e.g., 1.5).")
            return ASK_RISK_PCT
            
    # Save to DB
    update_user_risk_settings(user_id, balance, risk_pct)
    
    keyboard = [
        ["Analyze Chart 📈", "View Chart 📊"],
        ["Profile 👤", "Risk Settings ⚙️"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        f"✅ Risk profile updated!\n\n"
        f"  - Account Balance: ${balance:,.2f}\n"
        f"  - Risk per Trade: {risk_pct}%\n\n"
        f"I will now use these settings to calculate position sizes for your trades.",
        reply_markup=reply_markup
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the risk setup process."""
    keyboard = [
        ["Analyze Chart 📈", "View Chart 📊"],
        ["Profile 👤", "Risk Settings ⚙️"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Risk setup cancelled.", reply_markup=reply_markup)
    context.user_data.clear()
    return ConversationHandler.END

# --- VIEW CHART FUNCTION ---

async def view_chart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открывает TradingView для просмотра графиков"""
    # Создаем Inline-кнопку, которая ведет на TradingView
    inline_keyboard = [[
        InlineKeyboardButton("📊 Open TradingView Charts", url="https://www.tradingview.com/chart/")
    ]]
    inline_reply_markup = InlineKeyboardMarkup(inline_keyboard)
    
    message = (
        "📈 <b>Live Chart Analysis</b>\n\n"
        "Click the button below to open TradingView where you can:\n\n"
        "• View real-time cryptocurrency charts\n"
        "• Analyze different timeframes\n"
        "• Use technical indicators\n"
        "• Take screenshots for analysis\n\n"
        "After analyzing the chart, come back and use the <b>'Analyze Chart 📈'</b> button to get my insights!"
    )
    
    await update.message.reply_text(message, parse_mode=ParseMode.HTML, reply_markup=inline_reply_markup)

# --- ADMIN PANEL FUNCTIONS WITH PROMOCODES ---

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вход в админ-панель."""
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return

    keyboard = [["User Stats 👥", "Withdrawals 🏧"], ["Generate Promos 🎟️"], ["Back to Main Menu ⬅️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("👑 Welcome to the Admin Panel!", reply_markup=reply_markup)

async def handle_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает общую статистику и отчет по пользователям."""
    stats = get_admin_stats()
    users_report = get_active_users_report()
    
    stats_text = (
        f"📊 <b>Overall Statistics</b> 📊\n\n"
        f"Total Users: <b>{stats['total_users']}</b>\n"
        f"Active Subscribers: <b>{stats['active_users']}</b>\n"
        f"Pending Payment: <b>{stats['pending_payment']}</b>\n\n"
        f"Total Token Balance (all users): <b>{stats['total_tokens']:.2f}</b>\n"
        f"Pending Withdrawals: <b>{stats['pending_withdrawals_count']}</b> requests for <b>{stats['pending_withdrawals_sum']:.2f}</b> tokens.\n\n"
        f"🎟️ <b>Promo Codes Stats:</b>\n"
        f"Total Codes: <b>{stats['total_promo_codes']}</b>\n"
        f"Used Codes: <b>{stats['used_promo_codes']}</b>\n"
        f"Available Codes: <b>{stats['available_promo_codes']}</b>"
    )
    await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

    if not users_report:
        await update.message.reply_text("No active users found.")
        return

    report_text = "👥 <b>Active Users Report (Recent 20)</b> 👥\n\n"
    for user in users_report:
        report_text += (
            f"👤 <b>User:</b> <code>{user['user_id']}</code> (@{user['username']})\n"
            f"   - Balance: <b>{user['balance']:.2f}</b> Tokens\n"
            f"   - Referrals: L1: <b>{user['referrals']['l1']}</b>, L2: <b>{user['referrals']['l2']}</b>\n"
            f"--------------------\n"
        )
    
    await update.message.reply_text(report_text, parse_mode=ParseMode.HTML)

async def handle_admin_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список заявок на вывод."""
    withdrawals = get_pending_withdrawals()
    
    if not withdrawals:
        await update.message.reply_text("✅ No pending withdrawal requests.")
        return

    report_text = "🏧 <b>Pending Withdrawal Requests</b> 🏧\n\n"
    for req in withdrawals:
        req_id, user_id, amount, wallet, date = req
        report_text += (
            f"<b>Request ID: #{req_id}</b>\n"
            f"  - User ID: <code>{user_id}</code>\n"
            f"  - Amount: <b>{amount:.2f}</b> Tokens\n"
            f"  - Wallet (BEP-20): <code>{wallet}</code>\n"
            f"  - Date: {date}\n"
            f"--------------------\n"
        )
    
    await update.message.reply_text(report_text, parse_mode=ParseMode.HTML)

# --- PROMO CODE GENERATION CONVERSATION ---

async def generate_promos_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает диалог генерации промокодов."""
    await update.message.reply_text("How many promo codes do you want to generate? (e.g., 10)", reply_markup=ReplyKeyboardRemove())
    return ASK_PROMO_COUNT

async def generate_promos_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает количество, генерирует и отправляет промокоды."""
    try:
        count = int(update.message.text)
        if not (0 < count <= 100): # Ограничим до 100 за раз
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a valid number between 1 and 100.")
        return ASK_PROMO_COUNT

    await update.message.reply_text(f"Generating {count} promo codes, please wait...")
    
    new_codes = generate_promo_codes(count)
    
    # Отправляем коды в текстовом файле, чтобы их было удобно копировать
    codes_text = "\n".join(new_codes)
    file_path = "promo_codes.txt"
    with open(file_path, "w") as f:
        f.write(codes_text)
    
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=open(file_path, "rb"),
        caption=f"✅ Here are your {count} new promo codes."
    )
    os.remove(file_path) # Удаляем временный файл
    
    # Возвращаем админ-клавиатуру
    keyboard = [["User Stats 👥", "Withdrawals 🏧"], ["Generate Promos 🎟️"], ["Back to Main Menu ⬅️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("What would you like to do next?", reply_markup=reply_markup)
    
    return ConversationHandler.END

# --- Enhanced Text & Button Handler ---

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # --- Сначала проверяем, не админ ли это и не в админ-панели ли он ---
    if user_id == ADMIN_USER_ID:
        if text == "User Stats 👥":
            await handle_admin_stats(update, context)
            return
        elif text == "Withdrawals 🏧":
            await handle_admin_withdrawals(update, context)
            return
        elif text == "Generate Promos 🎟️":
            await generate_promos_start(update, context)
            return
        elif text == "Back to Main Menu ⬅️":
            # Возвращаем обычную клавиатуру
            keyboard = [
                ["Analyze Chart 📈", "View Chart 📊"],
                ["Profile 👤", "Risk Settings ⚙️"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text("Returned to main menu.", reply_markup=reply_markup)
            return
            
    # --- ТЕПЕРЬ ПРОВЕРЯЕМ НА ПРОМОКОД ---
    if text.upper().startswith("ALADDIN-"):
        if get_user_status(user_id) == 'active':
            await update.message.reply_text("Your account is already active.")
            return

        await update.message.reply_text("Checking your promo code...")
        
        is_valid = validate_and_use_promo_code(text, user_id)
        
        if is_valid:
            # Активируем подписку и делаем все то же, что и при оплате
            referrer_id = activate_user_subscription(user_id)
            
            # Начисляем реферальные бонусы, если есть реферер
            if referrer_id:
                referral_chain = get_referrer_chain(user_id, levels=3)
                rewards = [15, 10, 5]
                
                for i, referrer_user_id in enumerate(referral_chain):
                    if i < len(rewards):
                        reward_amount = rewards[i]
                        credit_referral_tokens(referrer_user_id, reward_amount)
                        try:
                            await context.bot.send_message(
                                referrer_user_id, 
                                f"🎉 Congratulations! You received {reward_amount} tokens from a level {i+1} referral."
                            )
                        except Exception as e:
                            print(f"Could not notify referrer {referrer_user_id}: {e}")
            
            keyboard = [
                ["Analyze Chart 📈", "View Chart 📊"],
                ["Profile 👤", "Risk Settings ⚙️"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text("✅ Promo code accepted! Welcome to Aladdin. You now have full access.", reply_markup=reply_markup)
        else:
            await update.message.reply_text("❌ This promo code is invalid or has already been used.")
        return

    # Handle main menu buttons
    if text == "Analyze Chart 📈": 
        await analyze_chart_start(update, context)
    elif text == "View Chart 📊":
        await view_chart_command(update, context)
    elif text == "Profile 👤": 
        await profile_command(update, context)
    elif text == "Risk Settings ⚙️":
        await risk_command(update, context)
    elif text == "Withdraw Tokens 💵":
        await withdraw_start(update, context)
    elif text == "Back to Menu ↩️":
        keyboard = [
            ["Analyze Chart 📈", "View Chart 📊"],
            ["Profile 👤", "Risk Settings ⚙️"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Main menu:", reply_markup=reply_markup)
    
    # Handle TxHash for payment
    elif text.startswith("0x") and len(text) == 66:
        if get_user_status(update.effective_user.id) == 'active':
            await update.message.reply_text("Your account is already active.")
            return
        await update.message.reply_text("Verifying transaction, please wait...")
        await verify_payment_and_activate(text, update.effective_user.id, context)
    else:
        await update.message.reply_text("Unknown command. Please use the buttons below.")

async def analyze_chart_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced chart analysis with subscription check"""
    if not has_access(update.effective_user.id):
        await update.message.reply_text("❌ Access Required. Please use /start to activate your subscription.")
        return
    await update.message.reply_text("I'm ready! Please send a clear screenshot of a candlestick chart.")

# --- LLM Explanation Handler ---

async def explain_analysis_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатие на кнопку 'Explain Factors'."""
    query = update.callback_query
    await query.answer()

    # Убираем кнопку, чтобы избежать повторных нажатий
    await query.edit_message_reply_markup(reply_markup=None)
    
    analysis_context = context.user_data.get('last_analysis_context')
    if not analysis_context:
        await query.message.reply_text("Sorry, I couldn't find the context for this analysis. Please try again.")
        return

    await query.message.reply_text("<i>Aladdin is thinking... 🧞‍♂️</i>", parse_mode=ParseMode.HTML)
    
    # Получаем объяснение от LLM
    explanation = get_explanation(analysis_context)
    
    await query.message.reply_text(explanation, parse_mode=ParseMode.MARKDOWN)

def main():
    print("Starting bot with Enhanced Subscription & Referral System & Admin Panel & View Chart & Promocodes...")
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Withdrawal conversation handler
    withdraw_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^Withdraw Tokens 💵$'), withdraw_start)],
        states={
            ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_amount)],
            ASK_WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_wallet)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Risk management conversation handler
    risk_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('risk', risk_command), MessageHandler(filters.Regex('^Risk Settings ⚙️$'), risk_command)],
        states={
            ASK_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_balance)],
            ASK_RISK_PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_risk_pct)],
        },
        fallbacks=[CommandHandler('cancel', cancel_risk)]
    )
    
    # Promo code generation conversation handler
    promo_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^Generate Promos 🎟️$'), generate_promos_start)],
        states={
            ASK_PROMO_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_promos_count)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("admin", admin_command))  # Новая админ-команда
    application.add_handler(withdraw_conv_handler)
    application.add_handler(risk_conv_handler)
    application.add_handler(promo_conv_handler)  # Новый обработчик для промокодов
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    # --- НОВЫЙ ОБРАБОТЧИК ДЛЯ КНОПКИ ОБЪЯСНЕНИЯ ---
    application.add_handler(CallbackQueryHandler(explain_analysis_handler, pattern="^explain_analysis$"))
    
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
