import os
import asyncio
import pandas as pd
import requests
import concurrent.futures
import time
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler, CallbackQueryHandler)
from telegram.constants import ParseMode
from telegram.ext import JobQueue
from telegram import InputMediaPhoto
from database import * 
from database import set_copytrading_status 
from database import check_analysis_limit
from chart_analyzer import find_candlesticks, candlesticks_to_ohlc
from core_analyzer import fetch_data, compute_features, generate_decisive_signal, generate_signal
from llm_explainer import get_explanation

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY")
WALLET_ADDRESS = os.getenv("YOUR_WALLET_ADDRESS")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID")) 
REFERRAL_REWARD = 24.5
PAYMENT_AMOUNT = 49
# PAYMENT_AMOUNT = 1.5
USDT_CONTRACT_ADDRESS = "0x55d398326f99059fF775485246999027B3197955"
ASK_PROMO_COUNT, ASK_PROMO_DURATION = range(2)
ASK_BROADCAST_MESSAGE, CONFIRM_BROADCAST = range(9, 11)


ASK_AMOUNT, ASK_WALLET = range(2)  
ASK_BALANCE, ASK_RISK_PCT = range(2, 4)  
ASK_PROMO_COUNT = range(4, 5)  
ASK_STRATEGY, ASK_EXCHANGE, ASK_API_KEY, ASK_SECRET_KEY = range(6, 10)



async def verify_payment_and_activate(tx_hash: str, user_id: int, context: ContextTypes.DEFAULT_TYPE):

    if is_tx_hash_used(tx_hash):
        await context.bot.send_message(user_id, "❌ Verification failed.\nReason: This transaction has already been used.")
        return

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
            
        activate_user_subscription(user_id)
        mark_tx_hash_as_used(tx_hash)
        
        # main_keyboard = [["Analyze Chart 📈", "View Chart 📊"], ["Profile 👤", "Risk Settings ⚙️"]]
        main_keyboard = [
        ["Analyze Chart 📈", "Copy Trade 🚀"], # Copy Trade теперь здесь
        ["View Chart 📊", "Profile 👤"],
        ["Risk Settings ⚙️"]
    ]
        main_reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
        
        await context.bot.send_message(user_id, "✅ Payment successful! Welcome to Aladdin. You now have full access.", reply_markup=main_reply_markup)
        referrer_id = get_referrer(user_id)
        
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


def format_plan_to_message(plan):
    print("\n--- [FORMATTER] Received plan ---")
    import json
    print(json.dumps(plan, indent=2))
    print("---------------------------------")
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
    else: # neutral
        icon = "⚪️"; title = f"<b>Neutral: ${symbol}</b> ({timeframe})"
        
        print("\n--- [FORMATTER] Generated HTML ---")
        print(message)
        print("----------------------------------\n")
        message = f"{icon} {title}\n\n<b>Rationale:</b>\n<i>{notes}</i>"
        
        metrics = plan.get('metrics')
        if metrics:
            metrics_text = "\n\n<b>Current Key Metrics:</b>\n"
            for key, value in metrics.items():
                metrics_text += f"— {key}: <code>{value}</code>\n"
            message += metrics_text
        
        message += "\n<i>Waiting for a clearer setup.</i>"
        return message

    entry_zone = plan.get('entry_zone', ['N/A']); stop_loss = plan.get('stop', 'N/A'); targets = plan.get('targets', ['N/A'])
    
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
        potential_profit = plan.get('potential_profit_usd', 'N/A')
        rr_ratio = plan.get('risk_reward_ratio', 'N/A')
        message += (f"\n\n<b>Risk Profile:</b>\n"
                    f"  - Position Size: <code>{pos_size_asset} {symbol_base}</code> ({pos_size_usd})\n"
                    f"  - Max Loss on this trade: <code>{potential_loss}</code>\n"
                    f"  - Max Profit (TP1): <code>{potential_profit}</code>\n"
                    f"  - Risk/Reward Ratio: <code>{rr_ratio}</code>" )
    # message += "\n\n<pre>⚠️ Not financial advice. DYOR.</pre>"
    return message


def blocking_chart_analysis(file_path: str, risk_settings: dict, progress_callback) -> tuple:
    try:
        print(f"\n--- [START] BLOCKING ANALYSIS in thread for {file_path} ---")
        if progress_callback:
            progress_callback("🔍 Analyzing chart with AI (recognizing symbol and timeframe)...")
        time.sleep(5)
        
        candlesticks, chart_info = find_candlesticks(file_path)
        
        print(f"LOG: GPT Vision Raw Info: {chart_info}")
        
        df = None; trade_plan = None; analysis_context = None
        ticker = chart_info.get('ticker') if chart_info else None
        
        if ticker:
            display_timeframe = chart_info.get('timeframe', '15m')
            fetch_timeframe = '15m'
            
            print(f"LOG: Ticker '{ticker}' and Timeframe '{display_timeframe}' identified.")
            if progress_callback:
                progress_callback(f"✅ AI identified: <b>{ticker}</b> at <b>{display_timeframe}</b>\n\nFetching live data...")
            time.sleep(2)
            
            base_currency = None; known_quotes = ["USDT", "BUSD", "TUSD", "USDC", "USD"]
            for quote in known_quotes:
                if ticker.endswith(quote):
                    base_currency = ticker[:-len(quote)]; break
            
            if base_currency:
                symbol_for_api = f"{base_currency}/USDT"
                print(f"LOG: Formatted symbol for API: {symbol_for_api}, requesting timeframe: {fetch_timeframe}")
                
                df = fetch_data(symbol=symbol_for_api, timeframe=fetch_timeframe)
                
                if df is not None and not df.empty:
                    print(f"LOG: Successfully fetched {len(df)} candles for {symbol_for_api}.")
                    if progress_callback:
                        progress_callback("🤖 Running technical analysis...")
                    time.sleep(4)
                    features = compute_features(df)
                    trade_plan, analysis_context = generate_decisive_signal(
                        features, symbol_ccxt=symbol_for_api, risk_settings=risk_settings, display_timeframe=display_timeframe
                    )
                else:
                    print(f"LOG: FAILED to fetch data for {symbol_for_api}.")
                    return None, None, f"❌ Found {ticker}, but couldn't fetch its data from the exchange."
            else:
                print(f"LOG: Ticker '{ticker}' was identified, but not recognized as a valid pair.")
                ticker = None 

        if ticker is None:
            print("LOG: Ticker not identified by AI.")
            return None, None, "❌ Sorry, the AI could not identify a valid ticker on this chart."

        if not trade_plan:
            print("LOG: Analysis engine did not produce a valid trade plan.")
            return None, None, "❌ Sorry, analysis did not produce a valid trade plan."

        print(f"LOG: Trade plan generated successfully: {trade_plan.get('view')}")
        if progress_callback:
            progress_callback("🎯 Generating final report...")
        time.sleep(1)
        print(f"--- [END] BLOCKING ANALYSIS for {file_path} ---")
        return trade_plan, analysis_context, None

    except Exception as e:
        print(f"FATAL ERROR in blocking_chart_analysis for {file_path}: {e}")
        return None, None, "❌ An unexpected error occurred during the analysis."

async def run_analysis_in_background(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, processing_message: object, file_path: str, risk_settings: dict):
    try:
        progress_queue = asyncio.Queue()
        async def progress_updater():
            while True:
                message_text = await progress_queue.get()
                if message_text is None:  
                    break
                try:
                    await processing_message.edit_text(message_text, parse_mode=ParseMode.HTML)
                except Exception as e:
                    print(f"Progress update failed (this might be normal on the final step): {e}")
        
        progress_task = asyncio.create_task(progress_updater())
        def progress_callback(message_text):
            try:
                asyncio.get_running_loop().call_soon_threadsafe(
                    progress_queue.put_nowait, message_text
                )
            except Exception as e:
                print(f"Error putting message in progress queue: {e}")
        
        trade_plan, analysis_context, error_message = await asyncio.to_thread(
            blocking_chart_analysis, file_path, risk_settings, progress_callback
        )
        
        await progress_queue.put(None)
        await progress_task
        
        if error_message:
            await processing_message.edit_text(error_message)
            return
            
        context.user_data['last_analysis_context'] = analysis_context
        
        message_text = format_plan_to_message(trade_plan)
        
        profile = get_user_profile(user_id)
        referral_link = None
        if profile and profile.get('ref_code'):
            bot_username = (await context.bot.get_me()).username
            referral_link = f"https://t.me/{bot_username}?start={profile['ref_code']}"
        
        inline_keyboard = []
        if referral_link:
            inline_keyboard.append([InlineKeyboardButton("Click here to subscribe", url=referral_link)])
        reply_markup_inline = InlineKeyboardMarkup(inline_keyboard) if inline_keyboard else None
        
        await processing_message.delete()
        await update.message.reply_text(
            text=message_text, 
            parse_mode=ParseMode.HTML, 
            reply_markup=reply_markup_inline
        )
        
        reply_keyboard = [["Explain Analysis 🔬", "Back to Main Menu ⬅️"]]
        reply_markup_reply = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        await update.message.reply_text("What would you like to do next?", reply_markup=reply_markup_reply)

    except Exception as e:
        print(f"FATAL Error in background analysis task for user {user_id}: {e}")
        try:
            await processing_message.edit_text("❌ An unexpected error occurred during the analysis process.")
        except Exception as edit_e:
            print(f"Could not even inform user {user_id} about the error: {edit_e}")
    finally:
        # Важнейшее улучшение: удаляем временный файл после использования
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Cleaned up temporary file: {file_path}")

# --- (BROADCAST) ---

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает диалог создания рассылки."""
    await update.message.reply_text(
        "Please type the message you want to broadcast to all active users.\n\n"
        "You can use HTML tags for formatting (e.g., <b>bold</b>, <i>italic</i>).\n\n"
        "Type /cancel to abort.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ASK_BROADCAST_MESSAGE

async def broadcast_ask_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает текст, показывает превью и просит подтверждения."""
    message_text = update.message.text
    context.user_data['broadcast_message'] = message_text
    
    # Считаем, скольким пользователям будет отправлено сообщение
    active_users_count = len(get_all_active_user_ids())
    
    # Показываем админу превью
    await update.message.reply_text("--- PREVIEW ---")
    await update.message.reply_text(message_text, parse_mode=ParseMode.HTML)
    await update.message.reply_text("--- END PREVIEW ---")
    
    keyboard = [["SEND NOW ✅", "Cancel ❌"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        f"This message will be sent to <b>{active_users_count}</b> active users. "
        f"Are you sure you want to proceed?",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )
    return CONFIRM_BROADCAST

async def broadcast_send_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет сообщение всем активным пользователям."""
    message_text = context.user_data.get('broadcast_message')
    if not message_text:
        await update.message.reply_text("Error: Message not found. Please start over.")
        return ConversationHandler.END
        
    user_ids = get_all_active_user_ids()
    
    await update.message.reply_text(f"Starting broadcast to {len(user_ids)} users... This may take a while.", reply_markup=ReplyKeyboardRemove())
    
    success_count = 0
    fail_count = 0
    
    for user_id in user_ids:
        try:
            await context.bot.send_message(user_id, text=message_text, parse_mode=ParseMode.HTML)
            success_count += 1
        except Exception as e:
            print(f"Failed to send broadcast to user {user_id}: {e}")
            fail_count += 1
        await asyncio.sleep(0.1) # Важная задержка, чтобы не попасть под rate-limit
    
    # Возвращаем админ-клавиатуру
    admin_keyboard = [["User Stats 👥", "Withdrawals 🏧"], ["Generate Promos 🎟️", "Broadcast 📢"], ["Back to Main Menu ⬅️"]]
    reply_markup = ReplyKeyboardMarkup(admin_keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"✅ Broadcast complete!\n\n"
        f"Successfully sent: {success_count}\n"
        f"Failed to send: {fail_count}",
        reply_markup=reply_markup
    )
    
    context.user_data.clear()
    return ConversationHandler.END


# async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = update.effective_user.id
#     if not has_access(user_id):
#         await update.message.reply_text("❌ Access Required. Please use /start to activate.")
#         return
        
#     risk_settings = get_user_risk_settings(user_id)
#     # Создаем уникальное имя файла, чтобы избежать конфликтов при одновременной обработке
#     timestamp = int(time.time())
#     file_path = f'chart_{user_id}_{timestamp}.jpg'
    
#     try:
#         photo_file = await update.message.photo[-1].get_file()
#         await photo_file.download_to_drive(file_path)
        
#         # 1. Отправляем пользователю моментальный ответ
#         processing_message = await update.message.reply_text("📨 Chart received! Your request is in the queue...")
        
#         # 2. Запускаем "тяжелую" задачу в ФОНЕ, не дожидаясь ее завершения
#         asyncio.create_task(
#             run_analysis_in_background(
#                 update=update,
#                 context=context,
#                 user_id=user_id,
#                 processing_message=processing_message,
#                 file_path=file_path,
#                 risk_settings=risk_settings
#             )
#         )
#         # `photo_handler` завершает свою работу здесь, и бот готов принимать новые команды

#     except Exception as e:
#         print(f"Error in initial photo_handler for user {user_id}: {e}")
#         await update.message.reply_text("❌ An error occurred while receiving your chart.")
#         # Если файл был создан, но задача не запустилась, удаляем его
#         if os.path.exists(file_path):
#             os.remove(file_path)


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    НОВЫЙ ОБРАБОТЧИК: Неблокирующий анализ + Проверка лимитов (5 раз в день).
    """
    user_id = update.effective_user.id
    
    # 1. ПРОВЕРКА ЛИМИТА (ГЛАВНОЕ ИЗМЕНЕНИЕ)
    # Если лимит исчерпан, check_analysis_limit вернет False
    if not check_analysis_limit(user_id, limit=5):
        await update.message.reply_text(
            "⛔ <b>Daily Limit Reached</b>\n\n"
            "You have used your <b>5 free chart analyses</b> for today.\n"
            "Please come back tomorrow (UTC time) to analyze more charts.",
            parse_mode=ParseMode.HTML
        )
        return

    # 2. Получаем настройки риска
    risk_settings = get_user_risk_settings(user_id)
    
    # 3. Создаем уникальное имя файла
    timestamp = int(time.time())
    file_path = f'chart_{user_id}_{timestamp}.jpg'
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        await photo_file.download_to_drive(file_path)
        
        # 4. Отправляем пользователю моментальный ответ
        processing_message = await update.message.reply_text("📨 Chart received! Analysis in queue (Limit: -1)...")
        
        # 5. Запускаем "тяжелую" задачу в ФОНЕ через create_task
        # Это гарантирует, что бот не зависнет для других юзеров
        asyncio.create_task(
            run_analysis_in_background(
                update=update,
                context=context,
                user_id=user_id,
                processing_message=processing_message,
                file_path=file_path,
                risk_settings=risk_settings
            )
        )

    except Exception as e:
        print(f"Error in initial photo_handler for user {user_id}: {e}")
        await update.message.reply_text("❌ An error occurred while receiving your chart.")
        # Если файл был создан, но задача не запустилась, удаляем его
        if os.path.exists(file_path):
            os.remove(file_path)



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
    # status = get_user_status(user.id)

    # if status == 'active':
    #     # --- ОСНОВНЫЕ КНОПКИ ВНИЗУ С VIEW CHART ---
    #     # main_keyboard = [
    #     #     ["Analyze Chart 📈", "View Chart 📊"],
    #     #     ["Profile 👤", "Risk Settings ⚙️"]
    #     # ]
    #     main_keyboard = [
    #     ["Analyze Chart 📈", "Copy Trade 🚀"], # Copy Trade теперь здесь
    #     ["View Chart 📊", "Profile 👤"],
    #     ["Risk Settings ⚙️"]
    #     ]

    #     main_reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
        
    #     await update.message.reply_text(
    #         "Welcome back! Your subscription is active. Use the buttons below to start.",
    #         reply_markup=main_reply_markup
    #     )
        
    # else: # Если подписка не активна
    #     payment_message = (
    #         f"Welcome to <b>Aladdin Bot!</b> 🧞‍♂️\n\n"
    #         f"To activate your 1-month subscription, please send exactly <b>{PAYMENT_AMOUNT} USDT</b> (BEP-20) to:\n\n"
    #         f"<i>⬇️⬇️⬇️ Tap the address to copy it ⬇️⬇️⬇️</i>\n\n"
    #         # f"<code>{WALLET_ADDRESS}</code>\n\n"
    #         f"<b><code>{WALLET_ADDRESS}</code></b>\n\n"
    #         f"Then, paste the <b>Transaction Hash (TxID)</b> here to verify.\n\n"
    #         f"<i>Alternatively, you can use a promo code if you have one!</i>"
    #     )
    #     await update.message.reply_text(payment_message, parse_mode=ParseMode.HTML)

    main_keyboard = [
        ["Analyze Chart 📈", "Copy Trade 🚀"],
        ["View Chart 📊", "Profile 👤"],
        ["Risk Settings ⚙️"]
    ]
    reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Welcome back to Aladdin! 🧞‍♂️\n\n"
        "You have <b>5 free chart analyses</b> per day.\n"
        "Copy Trading requires a token balance for fees.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = get_user_profile(user_id)
    
    if not profile:
        await update.message.reply_text("Couldn't find your profile. Please /start the bot.")
        return
        
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={profile['ref_code']}"
    referral_counts = get_referral_counts(user_id)
    
    status_emoji = "✅ Active" if profile['status'] == 'active' else "⏳ Pending Payment"
    expiry_text = f"Expires on: {profile['expiry']}" if profile['expiry'] else "N/A"
    
    # --- НОВЫЙ БЛОК ДЛЯ ОТОБРАЖЕНИЯ БАЛАНСА И КНОПОК ---
    profile_text = (
        f"👤 <b>Your Profile</b>\n\n"
        f"<b>Status:</b> {status_emoji}\n"
        f"<b>Subscription:</b> {expiry_text}\n"
        f"<b>Token Balance:</b> {profile['balance']:.2f} 🪙\n"
        f"<b>Trading Balance:</b> ${profile['account_balance']:,.2f}\n"
        f"<b>Risk per Trade:</b> {profile['risk_pct']}%\n\n"
        f"🔗 <b>Your Referral Link:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"Invite friends and earn tokens!\n"
        f"Level 1: 24.5 tokens\n"
        f"👥 <b>Your Referrals:</b>\n"
        f"  - Level 1: <b>{referral_counts['l1']}</b> users\n"
    )
    
    # Разные кнопки для активных и неактивных
    if profile['status'] == 'active':
        keyboard = [
            ["Top Up Balance 💵", "Withdraw Tokens 💰"],
            ["Connect Exchange 🔌", "Back to Main Menu ⬅️"]
        ]
    else:
        keyboard = [["Back to Main Menu ⬅️"]]
        
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(profile_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

async def top_up_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает инструкцию по пополнению баланса."""
    top_up_message = (
        "<b>How to Top Up Your Token Balance:</b>\n\n"
        "Tokens are used to pay the 40% performance fee on profitable trades.\n"
        "The exchange rate is <b>1 USDT = 1 Token</b>.\n\n"
        "1. Send any amount of USDT (BEP-20) to this address:\n"
        f"<code>{WALLET_ADDRESS}</code>\n\n"
        "2. After sending, paste the <b>Transaction Hash (TxID)</b> here in the chat to credit your balance."
    )
    await update.message.reply_text(top_up_message, parse_mode=ParseMode.HTML)

# --- НОВАЯ ФУНКЦИЯ ДЛЯ ПРОВЕРКИ ПЛАТЕЖА ЗА ПОПОЛНЕНИЕ ---
async def verify_top_up_payment(tx_hash: str, user_id: int) -> tuple[bool, str, float]:
    """Проверяет транзакцию пополнения и возвращает сумму."""
    if is_tx_hash_used(tx_hash):
        return False, "This transaction has already been used.", 0
    
    url = f"https://api.etherscan.io/v2/api?chainid=56&module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}&apikey={BSCSCAN_API_KEY}"
    
    try:
        print(f"DEBUG: Requesting TxInfo from Etherscan V2 for {tx_hash}")
        response = requests.get(url, timeout=15)
        data = response.json()
        
        print(f"DEBUG: Etherscan V2 API Response: {data}")

        if "result" not in data:
            return False, "Invalid response from blockchain explorer.", 0
            
        tx = data.get("result")
        
        if not isinstance(tx, dict) or not tx:
            error_message = data.get('message', 'Transaction not found or API error.')
            if 'Invalid API Key' in str(data):
                return False, "API Key is invalid. Please contact support.", 0
            else:
                return False, "Please wait a few minutes and try again.", 0
        
        contract_address = tx.get('to', '').lower()
        tx_input = tx.get('input', '')
        if contract_address != USDT_CONTRACT_ADDRESS.lower() or len(tx_input) < 138:
            return False, "Payment was not made in USDT (BEP-20).", 0
            
        to_address_in_data = tx_input[34:74]
        if WALLET_ADDRESS[2:].lower() not in to_address_in_data.lower():
            return False, "Payment sent to wrong address.", 0
            
        amount_token = int(tx_input[74:138], 16) / (10**18)
        if amount_token <= 0:
            return False, "Invalid payment amount.", 0
            
        return True, "Payment verified successfully!", amount_token
        
    except Exception as e:
        print(f"Error in verify_top_up_payment: {e}")
        return False, "An unexpected error occurred during verification.", 0

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
            "• Earn 25 tokens for Level 1 referrals\n"
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

# async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text("Please enter the amount of tokens you wish to withdraw:", reply_markup=ReplyKeyboardRemove())
#     return ASK_AMOUNT
async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Cancel"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Please enter the amount of tokens you wish to withdraw:", 
        reply_markup=reply_markup
    )
    return ASK_AMOUNT


async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Cancel"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    try:
        amount = float(update.message.text)
        if amount <= 0: raise ValueError
        
        profile = get_user_profile(update.effective_user.id)
        if amount > profile['balance']:
            await update.message.reply_text(f"Insufficient balance. You only have {profile['balance']:.2f} tokens. Please enter a valid amount.")
            return ASK_AMOUNT
            
        context.user_data['withdraw_amount'] = amount
        await update.message.reply_text("Great! Now, please paste your BEP-20 (BSC) wallet address for the withdrawal.",reply_markup=reply_markup)
        return ASK_WALLET
    except ValueError:
        await update.message.reply_text("Invalid amount. Please enter a number greater than 0.",reply_markup=reply_markup)
        return ASK_AMOUNT

async def ask_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet_address = update.message.text
    if not (wallet_address.startswith("0x") and len(wallet_address) == 42):
        keyboard = [["Cancel"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Invalid wallet address. Please paste a valid BEP-20 address (starts with 0x).",reply_markup=reply_markup )
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
        ["Analyze Chart 📈", "Copy Trade 🚀"],
        ["View Chart 📊", "Profile 👤"],
        ["Risk Settings ⚙️"]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("✅ Your withdrawal request has been submitted! Please allow up to 24 hours for processing.", reply_markup=reply_markup)
    
    return ConversationHandler.END


# async def connect_exchange_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Начинает диалог подключения к бирже."""
#     if not has_access(update.effective_user.id):
#         await update.message.reply_text("❌ Access Required. Please use /start to activate.")
#         return ConversationHandler.END

#     keyboard = [["Binance", "Bybit"], ["MEXC", "BingX"], ["Back to Main Menu ⬅️"]]
#     reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
#     await update.message.reply_text(
#         "⚙️ <b>Exchange Setup</b>\n\n"
#         "Select the exchange you want to connect.\n"
#         "Make sure your API keys have <b>Futures Trading</b> permissions enabled.",
#         reply_markup=reply_markup,
#         parse_mode=ParseMode.HTML
#     )
#     return ASK_EXCHANGE

async def connect_exchange_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сразу спрашиваем стратегию
    keyboard = [["Ratner (Futures)", "CGT Robot (Spot)"], ["Cancel"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "🤖 <b>Select Trading Strategy</b>\n\n"
        "<b>Ratner:</b> Futures trading (Binance, Bybit, etc.)\n"
        "<b>CGT Robot:</b> Spot trading (OKX Only)",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return ASK_STRATEGY

async def ask_strategy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    
    if choice == "Ratner (Futures)":
        context.user_data['strategy'] = 'ratner'
        # Показываем биржи для Ратнера
        keyboard = [["Binance", "Bybit"], ["BingX", "MEXC"], ["Back to Main Menu ⬅️"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Select Futures Exchange:", reply_markup=reply_markup)
        return ASK_EXCHANGE

    elif choice == "CGT Robot (Spot)":
        context.user_data['strategy'] = 'cgt'
        # Показываем ТОЛЬКО OKX
        keyboard = [["OKX"], ["Back to Main Menu ⬅️"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Select Spot Exchange:", reply_markup=reply_markup)
        return ASK_EXCHANGE

    else:
        await update.message.reply_text("Please select a valid strategy.")
        return ASK_STRATEGY

# async def ask_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Сохраняет биржу, отправляет инструкцию (ссылка + фото) и просит API Key."""
#     exchange_name = update.message.text
#     # Добавляем OKX или другие, если нужно
#     supported_exchanges = ["Binance", "Bybit", "BingX", "MEXC"]
    
#     if exchange_name not in supported_exchanges:
#         await update.message.reply_text("Invalid selection. Please choose an exchange from the list.")
#         return ASK_EXCHANGE
    
#     context.user_data['exchange_name'] = exchange_name.lower()
    
#     # 1. Отправляем ссылку на API Management
#     links = {
#         "Binance": "https://www.binance.com/en/my/settings/api-management",
#         "Bybit": "https://www.bybit.com/app/user/api-management",
#         "BingX": "https://www.bingx.com/en-us/account/api/",
#         "MEXC": "https://www.mexc.com/user/openapi" 
#     }
    
#     link = links.get(exchange_name, "")
    
#     msg_text = (
#         f"🔶 <b>{exchange_name} Configuration</b>\n\n"
#         f"👉 <b>Step 1:</b> Go to API Management:\n{link}\n"
#         f"<i>(Login if required)</i>\n\n"
#         f"👉 <b>Step 2:</b> Create new API Keys.\n"
#         f"⚠️ <b>IMPORTANT:</b> Enable <b>'Futures Trading'</b> permission.\n"
#         f"❌ <b>DO NOT</b> enable 'Withdrawals'.\n\n"
#         f"👉 <b>Step 3:</b> See the screenshots below for guidance 👇"
#     )
    
#     await update.message.reply_text(msg_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    
#     try:
#         folder_path = os.path.join("instructions", f"{exchange_name.lower()}_pic")
#         if os.path.exists(folder_path):
#             files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
#             files.sort()
#             if files:
#                 media_group = []
#                 for file_name in files[:10]:
#                     file_path_img = os.path.join(folder_path, file_name)
#                     media_group.append(InputMediaPhoto(open(file_path_img, "rb")))
#                 if media_group:
#                     await update.message.reply_media_group(media=media_group)
#     except Exception as e:
#         print(f"Error sending instructions: {e}")

#     # --- ВАЖНОЕ ИЗМЕНЕНИЕ: Клавиатура с кнопкой "Назад" для следующего шага ---
#     keyboard = [["Back to Main Menu ⬅️"]]
#     reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
#     await update.message.reply_text(
#         "🔑 <b>Enter API Key</b>\n\n"
#         "Please paste your <b>API Key</b> below:",
#         reply_markup=reply_markup,
#         parse_mode=ParseMode.HTML
#     )
#     return ASK_API_KEY

# async def ask_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Сохраняет API Key и запрашивает Secret Key."""
#     api_key = update.message.text.strip()
    
#     # Валидация (Красивая ошибка)
#     if len(api_key) < 10: 
#         await update.message.reply_text(
#             "❌ <b>Invalid API Key</b>\n\n"
#             "The key you entered seems too short. Please check and try again.",
#             parse_mode=ParseMode.HTML
#         )
#         return ASK_API_KEY

#     context.user_data['api_key'] = api_key
    
#     # Клавиатура с кнопкой "Назад"
#     keyboard = [["Back to Main Menu ⬅️"]]
#     reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
#     await update.message.reply_text(
#         "🔒 <b>Enter Secret Key</b>\n\n"
#         "Great! Now please paste your <b>Secret Key</b>:",
#         reply_markup=reply_markup,
#         parse_mode=ParseMode.HTML
#     )
#     return ASK_SECRET_KEY


# async def ask_secret_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Сохраняет ключи в базу данных и завершает диалог."""
#     secret_key = update.message.text.strip()
    
#     # Валидация (Красивая ошибка)
#     if len(secret_key) < 10:
#         await update.message.reply_text(
#             "❌ <b>Invalid Secret Key</b>\n\n"
#             "The secret key seems too short. Please check and try again.",
#             parse_mode=ParseMode.HTML
#         )
#         return ASK_SECRET_KEY

#     user_id = update.effective_user.id
#     exchange = context.user_data['exchange_name']
#     api_key = context.user_data['api_key']
    
#     # Сохраняем
#     save_user_api_keys(user_id, exchange, api_key, secret_key)
    
#     context.user_data.clear()
    
#     # Возвращаем основное меню
#     main_keyboard = [
#         ["Analyze Chart 📈", "Copy Trade 🚀"],
#         ["View Chart 📊", "Profile 👤"],
#         ["Risk Settings ⚙️"]
#     ]
#     reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
    
#     await update.message.reply_text(
#         f"✅ <b>Connected Successfully!</b>\n\n"
#         f"Your <b>{exchange.capitalize()}</b> account is now linked.\n"
#         "Aladdin will now automatically copy trades to your account according to your risk settings.",
#         reply_markup=reply_markup,
#         parse_mode=ParseMode.HTML
#     )
#     return ConversationHandler.END



async def ask_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 3: Проверка биржи, Инструкции (Фото + Ссылка) и запрос API Key."""
    exchange_name = update.message.text
    strategy = context.user_data.get('strategy', 'ratner')
    
    if exchange_name == "Back to Main Menu ⬅️":
        return await cancel(update, context)

    # Валидация бирж
    valid_ratner = ["Binance", "Bybit", "BingX", "MEXC"]
    valid_cgt = ["OKX"]
    
    if strategy == 'ratner' and exchange_name not in valid_ratner:
        await update.message.reply_text(f"For Ratner strategy, please choose: {', '.join(valid_ratner)}")
        return ASK_EXCHANGE
        
    if strategy == 'cgt' and exchange_name not in valid_cgt:
        await update.message.reply_text("For CGT Robot, only OKX is supported.")
        return ASK_EXCHANGE
    
    context.user_data['exchange_name'] = exchange_name.lower()
    
    # Ссылки (добавил OKX)
    links = {
        "Binance": "https://www.binance.com/en/my/settings/api-management",
        "Bybit": "https://www.bybit.com/app/user/api-management",
        "BingX": "https://www.bingx.com/en-us/account/api/",
        "MEXC": "https://www.mexc.com/user/openapi",
        "OKX": "https://www.okx.com/account/my-api"
    }
    link = links.get(exchange_name, "")
    
    # Текст инструкции
    msg_text = (
        f"🔶 <b>{exchange_name} Configuration</b>\n\n"
        f"👉 <b>Step 1:</b> Go to API Management:\n{link}\n"
        f"<i>(Login if required)</i>\n\n"
        f"👉 <b>Step 2:</b> Create new API Keys.\n"
        f"⚠️ <b>IMPORTANT:</b> Enable <b>'{'Spot' if strategy == 'cgt' else 'Futures'} Trading'</b> permission.\n"
        f"❌ <b>DO NOT</b> enable 'Withdrawals'.\n\n"
        f"👉 <b>Step 3:</b> See the screenshots below for guidance 👇"
    )
    
    await update.message.reply_text(msg_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    
    # Отправка ФОТО (Твой код)
    try:
        # Для OKX убедись, что папка называется okx_pic
        folder_path = os.path.join("instructions", f"{exchange_name.lower()}_pic")
        if os.path.exists(folder_path):
            files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            files.sort()
            if files:
                media_group = []
                for file_name in files[:10]:
                    file_path_img = os.path.join(folder_path, file_name)
                    media_group.append(InputMediaPhoto(open(file_path_img, "rb")))
                if media_group:
                    await update.message.reply_media_group(media=media_group)
    except Exception as e:
        print(f"Error sending instructions: {e}")

    # Клавиатура "Назад"
    keyboard = [["Back to Main Menu ⬅️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "🔑 <b>Enter API Key</b>\n\n"
        "Please paste your <b>API Key</b> below:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return ASK_API_KEY

async def ask_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 4: Получение API Key."""
    api_key = update.message.text.strip()
    
    if api_key == "Back to Main Menu ⬅️":
        return await cancel(update, context)
        
    if len(api_key) < 10: 
        await update.message.reply_text("❌ <b>Invalid API Key</b>\nTry again.", parse_mode=ParseMode.HTML)
        return ASK_API_KEY

    context.user_data['api_key'] = api_key
    
    keyboard = [["Back to Main Menu ⬅️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "🔒 <b>Enter Secret Key</b>\n\n"
        "Now paste your <b>Secret Key</b>:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return ASK_SECRET_KEY

async def ask_secret_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 5: Сохранение всего (Ключи + Стратегия)."""
    secret_key = update.message.text.strip()
    
    if secret_key == "Back to Main Menu ⬅️":
        return await cancel(update, context)

    if len(secret_key) < 10:
        await update.message.reply_text("❌ <b>Invalid Secret Key</b>\nTry again.", parse_mode=ParseMode.HTML)
        return ASK_SECRET_KEY

    user_id = update.effective_user.id
    exchange = context.user_data['exchange_name']
    api_key = context.user_data['api_key']
    strategy = context.user_data.get('strategy', 'ratner') # Получаем стратегию
    
    # 1. Сохраняем ключи
    save_user_api_keys(user_id, exchange, api_key, secret_key)
    # 2. Сохраняем стратегию
    set_user_strategy(user_id, strategy)
    
    context.user_data.clear()
    
    main_keyboard = [
        ["Analyze Chart 📈", "Copy Trade 🚀"],
        ["View Chart 📊", "Profile 👤"],
        ["Risk Settings ⚙️"]
    ]
    reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"✅ <b>Connected Successfully!</b>\n\n"
        f"Exchange: <b>{exchange.capitalize()}</b>\n"
        f"Strategy: <b>{strategy.upper()}</b>\n\n"
        "Aladdin is now ready to copy trades according to your strategy.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END




async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["Analyze Chart 📈", "Copy Trade 🚀"],
        ["View Chart 📊", "Profile 👤"],
        ["Risk Settings ⚙️"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Operation cancelled.", reply_markup=reply_markup)
    context.user_data.clear()
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
        ["Analyze Chart 📈", "Copy Trade 🚀"],
        ["View Chart 📊", "Profile 👤"],
        ["Risk Settings ⚙️"]
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
        ["Analyze Chart 📈", "Copy Trade 🚀"],
        ["View Chart 📊", "Profile 👤"],
        ["Risk Settings ⚙️"]
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
    keyboard = [
        ["User Stats 👥", "Withdrawals 🏧"], 
        ["Generate Promos 🎟️", "Broadcast 📢"], 
        ["Back to Main Menu ⬅️"]
    ]
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
            f"   - Referrals: L1: <b>{user['referrals']['l1']}</b>\n"
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

# async def generate_promos_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Начинает диалог генерации промокодов."""
#     await update.message.reply_text("How many promo codes do you want to generate? (e.g., 10)", reply_markup=ReplyKeyboardRemove())
#     return ASK_PROMO_COUNT

# async def generate_promos_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Получает количество, генерирует и отправляет промокоды."""
#     try:
#         count = int(update.message.text)
#         if not (0 < count <= 100): # Ограничим до 100 за раз
#             raise ValueError
#     except ValueError:
#         await update.message.reply_text("Please enter a valid number between 1 and 100.")
#         return ASK_PROMO_COUNT

#     await update.message.reply_text(f"Generating {count} promo codes, please wait...")
    
#     new_codes = generate_promo_codes(count)
    
#     # Отправляем коды в текстовом файле, чтобы их было удобно копировать
#     codes_text = "\n".join(new_codes)
#     file_path = "promo_codes.txt"
#     with open(file_path, "w") as f:
#         f.write(codes_text)
    
#     await context.bot.send_document(
#         chat_id=update.effective_chat.id,
#         document=open(file_path, "rb"),
#         caption=f"✅ Here are your {count} new promo codes."
#     )
#     os.remove(file_path) # Удаляем временный файл
    
#     # Возвращаем админ-клавиатуру
#     keyboard = [["User Stats 👥", "Withdrawals 🏧"], ["Generate Promos 🎟️"], ["Back to Main Menu ⬅️"]]
#     reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
#     await update.message.reply_text("What would you like to do next?", reply_markup=reply_markup)
    
#     return ConversationHandler.END


# --- НОВЫЙ ДИАЛОГ ГЕНЕРАЦИИ ПРОМОКОДОВ ---
async def generate_promos_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("How many promo codes do you want to generate? (e.g., 10)")
    return ASK_PROMO_COUNT

async def generate_promos_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text)
        if not (0 < count <= 100): raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a valid number between 1 and 100."); return ASK_PROMO_COUNT

    context.user_data['promo_count'] = count
    
    # Создаем кнопки для выбора срока действия
    keyboard = [
        ["1 day", "7 days"],
        ["15 days", "30 days"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Great. Now select the duration for these codes:", reply_markup=reply_markup)
    return ASK_PROMO_DURATION


async def generate_promos_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    duration_map = {"1 day": 1, "7 days": 7, "15 days": 15, "30 days": 30}
    duration_text = update.message.text
    
    if duration_text not in duration_map:
        await update.message.reply_text("Please select a valid duration from the buttons."); return ASK_PROMO_DURATION

    duration_days = duration_map[duration_text]
    count = context.user_data['promo_count']
    
    await update.message.reply_text(f"Generating {count} promo codes for {duration_days} days...", reply_markup=ReplyKeyboardRemove())
    
    new_codes = generate_promo_codes(count, duration_days)
    
    codes_text = "\n".join(new_codes)
    file_path = f"promo_codes_{count}_{duration_days}d.txt"
    with open(file_path, "w") as f:
        f.write(codes_text)
    
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=open(file_path, "rb"),
        caption=f"✅ Here are your {count} new promo codes, each valid for {duration_days} days."
    )
    os.remove(file_path)
    
    # Возвращаем админ-клавиатуру
    keyboard = [["User Stats 👥", "Withdrawals 🏧"], ["Generate Promos 🎟️"], ["Back to Main Menu ⬅️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Promo codes generated. What would you like to do next?", reply_markup=reply_markup)
    
    context.user_data.clear()
    return ConversationHandler.END

# --- ОБНОВЛЕННЫЙ text_handler для активации по промокоду ---
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # --- Админ-панель ---
    if user_id == ADMIN_USER_ID:
        if text == "User Stats 👥": await handle_admin_stats(update, context); return
        elif text == "Withdrawals 🏧": await handle_admin_withdrawals(update, context); return
        # Кнопка Generate Promos теперь запускает диалог, поэтому ее здесь нет
        elif text == "Back to Main Menu ⬅️":
            keyboard = [        ["Analyze Chart 📈", "Copy Trade 🚀"],
        ["View Chart 📊", "Profile 👤"],
        ["Risk Settings ⚙️"]]
            
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text("Returned to main menu.", reply_markup=reply_markup)
            return
            
    # --- ПРОВЕРКА НА ПРОМОКОД ---
    if text.upper().startswith("ALADDIN-"):
        if get_user_status(user_id) == 'active':
            await update.message.reply_text("Your account is already active."); return

        await update.message.reply_text("Checking your promo code...")
        
        # validate_and_use... теперь возвращает срок действия или None
        duration_days = validate_and_use_promo_code(text, user_id)
        
        if duration_days:
            activate_user_subscription(user_id, duration_days=duration_days)
            
            keyboard = [        ["Analyze Chart 📈", "Copy Trade 🚀"],
        ["View Chart 📊", "Profile 👤"],
        ["Risk Settings ⚙️"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(f"✅ Promo code accepted! Your access is active for {duration_days} days.", reply_markup=reply_markup)
        else:
            await update.message.reply_text("❌ This promo code is invalid or has already been used.")
        return

    # --- Основные кнопки ---
    if text == "Analyze Chart 📈": await analyze_chart_start(update, context)
    elif text == "View Chart 📊": await view_chart_command(update, context)
    elif text == "Profile 👤": await profile_command(update, context)
    elif text == "Top Up Balance 💵": await top_up_balance_command(update, context)
    elif text == "Copy Trade 🚀":
        await connect_exchange_start(update, context)
    elif text == "Risk Settings ⚙️":
        await risk_command(update, context)
    elif text == "Withdraw Tokens 💰":  
        await withdraw_start(update, context)
    elif text == "Cancel":
        await cancel(update, context)
    # elif text == "Back to Menu ↩️":
    elif text in ("Back to Menu ↩️", "Back to Main Menu ⬅️"):
        keyboard = [
            ["Analyze Chart 📈", "Copy Trade 🚀"],
            ["View Chart 📊", "Profile 👤"],
            ["Risk Settings ⚙️"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Main menu:", reply_markup=reply_markup)
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
    # Кнопки Risk, Withdraw, Back to Menu обрабатываются своими диалогами или как здесь
        # --- НОВЫЙ БЛОК ДЛЯ КНОПКИ EXPLAIN ---
    elif text == "Explain Analysis 🔬":
        # Возвращаем пользователя в основное меню
        keyboard = [        ["Analyze Chart 📈", "Copy Trade 🚀"],
        ["View Chart 📊", "Profile 👤"],
        ["Risk Settings ⚙️"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Getting explanation...", reply_markup=reply_markup)

        # Вызываем тот же код, что был в explain_analysis_handler
        analysis_context = context.user_data.get('last_analysis_context')
        if not analysis_context:
            await update.message.reply_text("Sorry, the context for this analysis has expired.")
            return

        thinking_message = await update.message.reply_text("<i>Aladdin is thinking... 🧞‍♂️</i>", parse_mode=ParseMode.HTML)
        explanation = get_explanation(analysis_context)
        await thinking_message.edit_text(explanation, parse_mode=ParseMode.MARKDOWN)
    # --- Проверка на TxHash ---
    # elif text.startswith("0x") and len(text) == 66:
    #     if get_user_status(user_id) == 'active':
    #         await update.message.reply_text("Your account is already active."); return
    #     await update.message.reply_text("Verifying transaction, please wait...")
    #     await verify_payment_and_activate(text, user_id, context)
    # else:
    #     pass
        # --- ОБНОВЛЕННАЯ ПРОВЕРКА НА ХЭШ ТРАНЗАКЦИИ ---
    elif text.startswith("0x") and len(text) == 66:
        status = get_user_status(user_id)
        
        # Если юзер еще не активен, это оплата подписки
        if status != 'active':
            await update.message.reply_text("Verifying your subscription payment...")
            await verify_payment_and_activate(text, user_id, context)
        
        # Если юзер уже активен, это пополнение баланса
        # else:
        #     await update.message.reply_text("Verifying your balance top-up...")
        #     is_valid, message, amount = await verify_top_up_payment(text, user_id)
        #     if is_valid:
        #         credit_tokens_from_payment(user_id, amount)
        #         mark_tx_hash_as_used(text)
        #         await update.message.reply_text(f"✅ Success! Your balance has been topped up with {amount:.2f} tokens.")
        #     else:
        #         await update.message.reply_text(f"❌ Top-up failed.\nReason: {message}")
        # return
        # Сценарий 2: Пополнение баланса
        else:
            await update.message.reply_text("Verifying your balance top-up...")
            # is_valid, message, amount = await verify_top_up_payment(text)
            is_valid, message, amount = await verify_top_up_payment(text, user_id)
            
            if is_valid:
                # --- НОВАЯ ЛОГИКА РАЗБЛОКИРОВКИ ---
                profile_before_topup = get_user_profile(user_id)
                
                credit_tokens_from_payment(user_id, amount)
                mark_tx_hash_as_used(text)
                
                profile_after_topup = get_user_profile(user_id)
                new_balance = profile_after_topup['balance']
                
                await update.message.reply_text(f"✅ Success! Topped up with {amount:.2f} tokens. Your new balance is {new_balance:.2f} 🪙.")

                # ПРОВЕРКА НА РАЗБЛОКИРОВКУ
                # Если баланс был <= 0, а стал > 0, включаем копи-трейдинг
                if profile_before_topup['balance'] <= 0 and new_balance > 0:
                    set_copytrading_status(user_id, is_enabled=True)
                    await update.message.reply_text("✅ Your token balance is now positive. Copy trading has been re-enabled!")
            else:
                await update.message.reply_text(f"❌ Top-up failed.\nReason: {message}")
        return
    


# --- Enhanced Text & Button Handler ---

# async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     text = update.message.text
#     user_id = update.effective_user.id

#     # --- Сначала проверяем, не админ ли это и не в админ-панели ли он ---
#     if user_id == ADMIN_USER_ID:
#         if text == "User Stats 👥":
#             await handle_admin_stats(update, context)
#             return
#         elif text == "Withdrawals 🏧":
#             await handle_admin_withdrawals(update, context)
#             return
#         elif text == "Generate Promos 🎟️":
#             await generate_promos_start(update, context)
#             return
#         elif text == "Back to Main Menu ⬅️":
#             # Возвращаем обычную клавиатуру
#             keyboard = [
#                 ["Analyze Chart 📈", "View Chart 📊"],
#                 ["Profile 👤", "Risk Settings ⚙️"]
#             ]
#             reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
#             await update.message.reply_text("Returned to main menu.", reply_markup=reply_markup)
#             return
            
#     # --- ТЕПЕРЬ ПРОВЕРЯЕМ НА ПРОМОКОД ---
#     if text.upper().startswith("ALADDIN-"):
#         if get_user_status(user_id) == 'active':
#             await update.message.reply_text("Your account is already active.")
#             return

#         await update.message.reply_text("Checking your promo code...")
        
#         is_valid = validate_and_use_promo_code(text, user_id)
        
#         if is_valid:
#             # Активируем подписку и делаем все то же, что и при оплате
#             referrer_id = activate_user_subscription(user_id)
            
#             # Начисляем реферальные бонусы, если есть реферер
#             if referrer_id:
#                 referral_chain = get_referrer_chain(user_id, levels=3)
#                 rewards = [15, 10, 5]
                
#                 for i, referrer_user_id in enumerate(referral_chain):
#                     if i < len(rewards):
#                         reward_amount = rewards[i]
#                         credit_referral_tokens(referrer_user_id, reward_amount)
#                         try:
#                             await context.bot.send_message(
#                                 referrer_user_id, 
#                                 f"🎉 Congratulations! You received {reward_amount} tokens from a level {i+1} referral."
#                             )
#                         except Exception as e:
#                             print(f"Could not notify referrer {referrer_user_id}: {e}")
            
#             keyboard = [
#                 ["Analyze Chart 📈", "View Chart 📊"],
#                 ["Profile 👤", "Risk Settings ⚙️"]
#             ]
#             reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
#             await update.message.reply_text("✅ Promo code accepted! Welcome to Aladdin. You now have full access.", reply_markup=reply_markup)
#         else:
#             await update.message.reply_text("❌ This promo code is invalid or has already been used.")
#         return

#     # Handle main menu buttons
#     if text == "Analyze Chart 📈": 
#         await analyze_chart_start(update, context)
#     elif text == "View Chart 📊":
#         await view_chart_command(update, context)
#     elif text == "Profile 👤": 
#         await profile_command(update, context)
#     elif text == "Risk Settings ⚙️":
#         await risk_command(update, context)
#     elif text == "Withdraw Tokens 💵":
#         await withdraw_start(update, context)
#     elif text == "Back to Menu ↩️":
#         keyboard = [
#             ["Analyze Chart 📈", "View Chart 📊"],
#             ["Profile 👤", "Risk Settings ⚙️"]
#         ]
#         reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
#         await update.message.reply_text("Main menu:", reply_markup=reply_markup)
    
#     # Handle TxHash for payment
#     elif text.startswith("0x") and len(text) == 66:
#         if get_user_status(update.effective_user.id) == 'active':
#             await update.message.reply_text("Your account is already active.")
#             return
#         await update.message.reply_text("Verifying transaction, please wait...")
#         await verify_payment_and_activate(text, update.effective_user.id, context)
#     else:
#         await update.message.reply_text("Unknown command. Please use the buttons below.")

# async def analyze_chart_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Enhanced chart analysis with subscription check"""
#     if not has_access(update.effective_user.id):
#         await update.message.reply_text("❌ Access Required. Please use /start to activate your subscription.")
#         return
#     await update.message.reply_text("I'm ready! Please send a clear screenshot of a candlestick chart.")

async def analyze_chart_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "I'm ready! Please send a clear screenshot of a candlestick chart.\n\n"
        "<i>Remember: You have a daily limit of 5 free analyses.</i>",
        parse_mode=ParseMode.HTML
    )


# --- НОВЫЙ ОБРАБОТЧИК ДЛЯ КНОПКИ "EXPLAIN" ---
# async def explain_analysis_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     await query.answer()

#     # Убираем все кнопки с исходного сообщения, чтобы избежать повторных нажатий
#     try:
#         await query.edit_message_reply_markup(reply_markup=None)
#     except Exception as e:
#         print(f"Could not remove keyboard: {e}") # Игнорируем ошибку, если не удалось
    
#     analysis_context = context.user_data.get('last_analysis_context')
#     if not analysis_context:
#         await query.message.reply_text("Sorry, the context for this analysis has expired. Please run a new analysis.")
#         return

#     # Отправляем новое сообщение "думаю..."
#     thinking_message = await query.message.reply_text("<i>Aladdin is thinking... 🧞‍♂️</i>", parse_mode=ParseMode.HTML)
    
#     # Получаем объяснение от LLM
#     explanation = get_explanation(analysis_context)
    
#     # Редактируем сообщение "думаю..." на финальный ответ
#     await thinking_message.edit_text(explanation, parse_mode=ParseMode.MARKDOWN)

# bot.py

async def explain_analysis_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass 
    
    analysis_context = context.user_data.get('last_analysis_context')
    if not analysis_context:
        await query.message.reply_text("Sorry, the context for this analysis has expired. Please run a new analysis.")
        return

    thinking_message = await query.message.reply_text("<i>Aladdin is thinking... 🧞‍♂️</i>", parse_mode=ParseMode.HTML)
    explanation = await asyncio.to_thread(get_explanation, analysis_context)
    
    await thinking_message.edit_text(explanation, parse_mode=ParseMode.MARKDOWN)


async def daily_subscription_check(context: ContextTypes.DEFAULT_TYPE):
    """Каждый день проверяет, деактивирует истекшие подписки и отключает копи-трейдинг."""
    print("--- [SCHEDULER] Running daily subscription check ---")
    
    # 1. Эта функция меняет статус юзера в БД на 'expired' и возвращает ID
    expired_user_ids = check_and_expire_subscriptions()
    
    for user_id in expired_user_ids:
        # 2. !!! ВАЖНОЕ ДОБАВЛЕНИЕ !!!
        # Мы физически отключаем копирование сделок для этого юзера
        set_copytrading_status(user_id, is_enabled=False)
        
        try:
            # 3. Отправляем уведомление
            await context.bot.send_message(
                user_id,
                "⛔ <b>Subscription Expired</b>\n\n"
                "Your subscription period has ended. Copy trading has been disabled.\n"
                "Please use /start to renew your access and resume trading.",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print(f"Failed to notify expired user {user_id}: {e}")

def main():
    print("Starting bot with Enhanced Subscription & Referral System & Admin Panel & View Chart & Promocodes...")
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    job_queue = application.job_queue
    # Запускать каждый день в 00:05 по UTC
    job_queue.run_daily(daily_subscription_check, time=datetime.strptime("00:05", "%H:%M").time())
    # Withdrawal conversation handler
    withdraw_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^Withdraw Tokens 💰$'), withdraw_start)],  
        states={
            ASK_AMOUNT: [MessageHandler(filters.Regex('^Cancel$'), cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, ask_amount)],
            ASK_WALLET: [ MessageHandler(filters.Regex('^Cancel$'), cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, ask_wallet)],
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
            ASK_PROMO_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_promos_duration)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    broadcast_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^Broadcast 📢$'), broadcast_start)],
        states={
            ASK_BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_ask_confirmation)],
            CONFIRM_BROADCAST: [
                MessageHandler(filters.Regex('^SEND NOW ✅$'), broadcast_send_message),
                MessageHandler(filters.Regex('^Cancel ❌$'), cancel) # Используем общую отмену
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    connect_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^Copy Trade 🚀$'), connect_exchange_start)],
        states={
            ASK_EXCHANGE: [
                MessageHandler(filters.Regex('^Back to Main Menu ⬅️$'), cancel), # Обработка кнопки Назад
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_exchange)
            ],
            ASK_API_KEY: [
                MessageHandler(filters.Regex('^Back to Main Menu ⬅️$'), cancel), # Обработка кнопки Назад
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_api_key)
            ],
            ASK_SECRET_KEY: [
                MessageHandler(filters.Regex('^Back to Main Menu ⬅️$'), cancel), # Обработка кнопки Назад
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_secret_key)
            ],
            ASK_STRATEGY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_strategy)],
        },
        # fallbacks обрабатывают команды типа /cancel, но лучше добавить кнопку и сюда
        fallbacks=[
            CommandHandler('cancel', cancel),
            MessageHandler(filters.Regex('^Back to Main Menu ⬅️$'), cancel)
        ]
    )
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("admin", admin_command))  # Новая админ-команда
    application.add_handler(connect_conv_handler)
    application.add_handler(withdraw_conv_handler)
    application.add_handler(risk_conv_handler)
    application.add_handler(promo_conv_handler)
    application.add_handler(broadcast_conv_handler)
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    # --- НОВЫЙ ОБРАБОТЧИК ДЛЯ КНОПКИ ОБЪЯСНЕНИЯ ---
    application.add_handler(CallbackQueryHandler(explain_analysis_handler, pattern="^explain_analysis$"))
    
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
