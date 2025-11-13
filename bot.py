# # bot.py (v19 Enhanced - Full Subscription & Referral System)

# import os
# import asyncio
# import pandas as pd
# import requests
# from datetime import datetime
# from dotenv import load_dotenv
# from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
# from telegram.ext import (Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler)
# from telegram.constants import ParseMode
# from chart_analyzer import find_candlesticks, candlesticks_to_ohlc
# from database import * # Import all our new DB functions
# from core_analyzer import fetch_data, compute_features, generate_decisive_signal

# load_dotenv()
# TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
# BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY")
# WALLET_ADDRESS = os.getenv("YOUR_WALLET_ADDRESS")
# ADMIN_USER_ID = os.getenv("ADMIN_USER_ID") # Add your own Telegram ID to .env

# PAYMENT_AMOUNT = 1.5
# USDT_CONTRACT_ADDRESS = "0x55d398326f99059fF775485246999027B3197955"

# # Conversation states for withdrawal
# ASK_AMOUNT, ASK_WALLET = range(2)


# async def verify_payment_and_activate(tx_hash: str, user_id: int, context: ContextTypes.DEFAULT_TYPE):
#     """
#     ФИНАЛЬНАЯ ВЕРСИЯ: Проверяет платеж с детальной отладкой и ПРАВИЛЬНО начисляет реферальные бонусы.
#     """
#     if is_tx_hash_used(tx_hash):
#         await context.bot.send_message(user_id, "❌ Verification failed.\nReason: This transaction has already been used.")
#         return

#     # Etherscan V2 API URL for BSC (chainid=56)
#     url = f"https://api.etherscan.io/v2/api?chainid=56&module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}&apikey={BSCSCAN_API_KEY}"
    
#     try:
#         print(f"DEBUG: Requesting TxInfo from Etherscan V2 for {tx_hash}")
#         response = requests.get(url, timeout=15)
#         data = response.json()
        
#         # Детальная отладка для анализа ответа от API
#         print(f"DEBUG: Etherscan V2 API Response: {data}")

#         if "result" not in data:
#             await context.bot.send_message(user_id, "❌ Verification failed.\nReason: Invalid response from blockchain explorer.")
#             return
            
#         tx = data.get("result")
        
#         # Надежная проверка на ошибки от API
#         if not isinstance(tx, dict) or not tx:
#             error_message = data.get('message', 'Transaction not found or API error.')
#             if 'Invalid API Key' in str(data):
#                 await context.bot.send_message(user_id, "❌ Verification failed.\nReason: API Key is invalid. Please contact support.")
#             else:
#                 await context.bot.send_message(user_id, f"❌ Verification failed.\nReason: Transaction details could not be fetched. Please wait a few minutes and try again. (API: {error_message})")
#             return
        
#         # --- Проверка деталей транзакции ---
#         contract_address = tx.get('to', '').lower()
#         tx_input = tx.get('input', '')
        
#         if contract_address != USDT_CONTRACT_ADDRESS.lower() or len(tx_input) < 138:
#             await context.bot.send_message(user_id, "❌ Verification failed.\nReason: Payment was not made in USDT (BEP-20).")
#             return
            
#         to_address_in_data = tx_input[34:74]
#         if WALLET_ADDRESS[2:].lower() not in to_address_in_data.lower():
#             await context.bot.send_message(user_id, "❌ Verification failed.\nReason: Payment sent to wrong address.")
#             return

#         amount_token = int(tx_input[74:138], 16) / (10**18)
#         if not (PAYMENT_AMOUNT <= amount_token < PAYMENT_AMOUNT + 0.1):
#             await context.bot.send_message(user_id, f"❌ Verification failed.\nReason: Incorrect amount. Expected {PAYMENT_AMOUNT}, received {amount_token:.4f} USDT.")
#             return
            
#         # --- УСПЕХ! АКТИВАЦИЯ ПОЛЬЗОВАТЕЛЯ ---
#         activate_user_subscription(user_id)
#         mark_tx_hash_as_used(tx_hash)
        
#         keyboard = [["Analyze Chart 📈", "Profile 👤"]]
#         reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
#         await context.bot.send_message(user_id, "✅ Payment successful! Welcome to Aladdin. You now have full access.", reply_markup=reply_markup)
        
#         # --- ПРАВИЛЬНАЯ ЛОГИКА РАСПРЕДЕЛЕНИЯ РЕФЕРАЛЬНЫХ НАГРАД ---
#         # 1. Строим цепочку рефереров для ТОЛЬКО ЧТО АКТИВИРОВАННОГО пользователя (user_id)
#         #    get_referrer_chain вернет [прямой_реферер, реферер_2_уровня, реферер_3_уровня]
#         referral_chain = get_referrer_chain(user_id, levels=3)
        
#         # 2. Определяем награды для каждого уровня
#         rewards = [15, 10, 5] # Уровень 1, Уровень 2, Уровень 3
        
#         # 3. Проходим по цепочке и начисляем правильные награды
#         #    i = 0 -> referrer_user_id = прямой реферер, получает rewards[0] = 15
#         #    i = 1 -> referrer_user_id = реферер 2-го уровня, получает rewards[1] = 10
#         #    ...и так далее
#         for i, referrer_user_id in enumerate(referral_chain):
#             if i < len(rewards): # Защита на случай, если цепочка короче
#                 reward_amount = rewards[i]
#                 credit_referral_tokens(referrer_user_id, reward_amount)
#                 try:
#                     await context.bot.send_message(
#                         referrer_user_id, 
#                         f"🎉 Congratulations! You received {reward_amount} tokens from a level {i+1} referral."
#                     )
#                 except Exception as e:
#                     print(f"Could not notify referrer {referrer_user_id}: {e}")

#     except Exception as e:
#         print(f"Error in verify_payment: {e}")
#         await context.bot.send_message(user_id, "❌ An unexpected error occurred during verification.")
# async def simulate_thinking(duration=2):
#     """Задержка для естественности"""
#     await asyncio.sleep(duration)

# def format_plan_to_message(plan):
#     symbol = plan.get('symbol', 'N/A')
#     timeframe = plan.get('timeframe', 'N/A')
#     view = plan.get('view', 'neutral')
    
#     if view == 'long':
#         icon = "🟢"
#         title = f"<b>Long Idea: ${symbol}</b> ({timeframe})"
#     elif view == 'short':
#         icon = "🔴"
#         title = f"<b>Short Idea: ${symbol}</b> ({timeframe})"
#     else:
#         icon = "⚪️"
#         title = f"<b>Analysis: ${symbol}</b> ({timeframe})"
#         message = f"{icon} {title}\n\n{plan.get('notes', 'No notes.')}"
#         return message
    
#     entry_zone = plan.get('entry_zone', ['N/A'])
#     stop_loss = plan.get('stop', 'N/A')
#     targets = plan.get('targets', ['N/A'])
#     notes = plan.get('notes', 'No notes.')
    
#     message = (
#         f"{icon} {title}\n\n"
#         f"<b>🔹 Entry Zone:</b> <code>{entry_zone[0]} - {entry_zone[1]}</code>\n"
#         f"<b>🔸 Stop Loss:</b> <code>{stop_loss}</code>\n"
#         f"<b>🎯 Target(s):</b> <code>{', '.join(map(str, targets))}</code>\n\n"
#         f"📝 <b>Rationale:</b>\n"
#         f"<i>{notes}</i>\n\n"
#         f"<pre>⚠️ Not financial advice. DYOR.</pre>"
#     )
#     return message

# # --- Enhanced Bot Command Handlers ---

# async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user = update.effective_user
    
#     # Check for referral code in start parameter (e.g., /start ref_12345)
#     referrer_id = None
#     if context.args and context.args[0].startswith('ref_'):
#         code = context.args[0]
#         referrer_id = get_user_by_referral_code(code)
    
#     add_user(user.id, user.username, referrer_id)
#     status = get_user_status(user.id)

#     if status == 'active':
#         keyboard = [["Analyze Chart 📈", "Profile 👤"]]
#         reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
#         await update.message.reply_text("Welcome back! Your subscription is active.", reply_markup=reply_markup)
#     else:
#         payment_message = (
#             f"Welcome to <b>Aladdin Bot!</b> 🧞‍♂️\n\n"
#             f"To activate your 1-month subscription, please send exactly <b>{PAYMENT_AMOUNT} USDT</b> (BEP-20) to:\n\n"
#             f"<code>{WALLET_ADDRESS}</code>\n\n"
#             f"Then, paste the <b>Transaction Hash (TxID)</b> here to verify."
#         )
#         await update.message.reply_text(payment_message, parse_mode=ParseMode.HTML)

# async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = update.effective_user.id
#     profile = get_user_profile(user_id)
    
#     if not profile:
#         await update.message.reply_text("Couldn't find your profile. Please /start the bot.")
#         return
        
#     bot_username = (await context.bot.get_me()).username
#     referral_link = f"https://t.me/{bot_username}?start={profile['ref_code']}"
    
#     status_emoji = "✅ Active" if profile['status'] == 'active' else "⏳ Pending Payment"
#     expiry_text = f"Expires on: {profile['expiry']}" if profile['expiry'] else "N/A"
    
#     profile_text = (
#         f"👤 <b>Your Profile</b>\n\n"
#         f"<b>Status:</b> {status_emoji}\n"
#         f"<b>Subscription:</b> {expiry_text}\n"
#         f"<b>Token Balance:</b> {profile['balance']:.2f} Tokens\n\n"
#         f"🔗 <b>Your Referral Link:</b>\n"
#         f"<code>{referral_link}</code>\n\n"
#         f"Invite friends and earn tokens!\n"
#         f"Level 1: 15 tokens\n"
#         f"Level 2: 10 tokens\n"
#         f"Level 3: 5 tokens"
#     )
#     keyboard = [["Withdraw Tokens 💵", "Back to Menu ↩️"]]
#     reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
#     await update.message.reply_text(profile_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

# async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Enhanced help command with subscription info."""
#     user_id = update.effective_user.id
#     status = get_user_status(user_id)
    
#     if status == 'active':
#         help_text = (
#             "🧞‍♂️ <b>Aladdin - Crypto Chart Analyst</b>\n\n"
#             "Here's how you can use me:\n\n"
#             "1. Press the <b>'Analyze Chart 📈'</b> button below.\n"
#             "2. Send me a clear screenshot of a candlestick chart.\n"
#             "3. I will analyze it and provide a technical outlook.\n\n"
#             "<b>What I can do:</b>\n"
#             "• Recognize cryptocurrency symbols from charts\n"
#             "• Fetch live market data from Binance\n"
#             "• Analyze technical indicators (EMA, RSI, ATR, Bollinger Bands)\n"
#             "• Provide trading ideas with entry zones and targets\n\n"
#             "<b>Referral System:</b>\n"
#             "• Earn 15 tokens for Level 1 referrals\n"
#             "• Earn 10 tokens for Level 2 referrals\n"
#             "• Earn 5 tokens for Level 3 referrals\n"
#             "• Withdraw tokens to your wallet\n\n"
#             "<b>Available Commands:</b>\n"
#             "/start - Restart the bot and show the main menu\n"
#             "/help - Show this help message\n"
#             "/profile - View your profile and referral link\n\n"
#             "<i>Your access is active! Press the buttons below to get started!</i>"
#         )
#     else:
#         help_text = (
#             "🧞‍♂️ <b>Aladdin - Crypto Chart Analyst</b>\n\n"
#             "This bot provides AI-powered technical analysis of cryptocurrency charts.\n\n"
#             "<b>How it works:</b>\n"
#             "1. Send a screenshot of any crypto chart\n"
#             "2. I'll recognize the symbol and analyze it\n"
#             "3. Get detailed trading insights with entry/exit points\n\n"
#             "<b>Subscription:</b>\n"
#             f"• One-time payment of {PAYMENT_AMOUNT} USDT for 1 month access\n"
#             "• Full access to all analysis features\n"
#             "• Referral system to earn tokens\n\n"
#             "<b>To get started:</b>\n"
#             "Use /start to activate your access with a one-time payment.\n\n"
#             "<i>Use /start to begin the activation process!</i>"
#         )
    
#     await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

# # --- Withdrawal Conversation Handlers ---

# async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text("Please enter the amount of tokens you wish to withdraw:", reply_markup=ReplyKeyboardRemove())
#     return ASK_AMOUNT

# async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     try:
#         amount = float(update.message.text)
#         if amount <= 0: raise ValueError
        
#         profile = get_user_profile(update.effective_user.id)
#         if amount > profile['balance']:
#             await update.message.reply_text(f"Insufficient balance. You only have {profile['balance']:.2f} tokens. Please enter a valid amount.")
#             return ASK_AMOUNT
            
#         context.user_data['withdraw_amount'] = amount
#         await update.message.reply_text("Great! Now, please paste your BEP-20 (BSC) wallet address for the withdrawal.")
#         return ASK_WALLET
#     except ValueError:
#         await update.message.reply_text("Invalid amount. Please enter a number greater than 0.")
#         return ASK_AMOUNT

# async def ask_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     wallet_address = update.message.text
#     if not (wallet_address.startswith("0x") and len(wallet_address) == 42):
#         await update.message.reply_text("Invalid wallet address. Please paste a valid BEP-20 address (starts with 0x).")
#         return ASK_WALLET
        
#     amount = context.user_data['withdraw_amount']
#     user_id = update.effective_user.id
    
#     # Create request in DB
#     success = create_withdrawal_request(user_id, amount, wallet_address)
    
#     if not success:
#         await update.message.reply_text("An error occurred. Please try again.")
#         return ConversationHandler.END

#     # Notify admin
#     if ADMIN_USER_ID:
#         admin_message = (
#             f"⚠️ New Withdrawal Request ⚠️\n\n"
#             f"User ID: {user_id}\n"
#             f"Username: @{update.effective_user.username}\n"
#             f"Amount: {amount} tokens\n"
#             f"Wallet: <code>{wallet_address}</code>"
#         )
#         await context.bot.send_message(ADMIN_USER_ID, admin_message, parse_mode=ParseMode.HTML)
    
#     keyboard = [["Analyze Chart 📈", "Profile 👤"]]
#     reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
#     await update.message.reply_text("✅ Your withdrawal request has been submitted! Please allow up to 24 hours for processing.", reply_markup=reply_markup)
    
#     return ConversationHandler.END

# async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     keyboard = [["Analyze Chart 📈", "Profile 👤"]]
#     reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
#     await update.message.reply_text("Withdrawal cancelled.", reply_markup=reply_markup)
#     return ConversationHandler.END

# # --- Enhanced Text & Button Handler ---

# async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     text = update.message.text
    
#     # Handle main menu buttons
#     if text == "Analyze Chart 📈": 
#         await analyze_chart_start(update, context)
#     elif text == "Profile 👤": 
#         await profile_command(update, context)
#     elif text == "Withdraw Tokens 💵":
#         await withdraw_start(update, context)
#     elif text == "Back to Menu ↩️":
#         keyboard = [["Analyze Chart 📈", "Profile 👤"]]
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
#     if get_user_status(update.effective_user.id) != 'active':
#         await update.message.reply_text("❌ Access Required. Please use /start to activate your subscription.")
#         return
#     await update.message.reply_text("I'm ready! Please send a clear screenshot of a candlestick chart.")

# async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """
#     УМНАЯ ОБРАБОТКА ГРАФИКОВ С ИМПУЛЬСНЫМ АНАЛИЗОМ И ПРОВЕРКОЙ ПОДПИСКИ
#     """
#     user = update.message.from_user
#     user_id = user.id
    
#     # Check subscription status
#     if get_user_status(user_id) != 'active':
#         await update.message.reply_text(
#             "❌ <b>Access Required</b>\n\n"
#             "Your access is not active. Please use the /start command to make a payment and activate full access.",
#             parse_mode=ParseMode.HTML
#         )
#         return
    
#     file_path = f'chart_for_{user.id}.jpg'
#     processing_message = await update.message.reply_text("📨 Chart received! Starting analysis...")
    
#     try:
#         photo_file = await update.message.photo[-1].get_file()
#         await photo_file.download_to_drive(file_path)

#         # Этап 1: Анализ изображения с GPT
#         await processing_message.edit_text("🔍 Analyzing chart with AI...")
#         await simulate_thinking(3)
        
#         candlesticks, ticker = find_candlesticks(file_path)
        
#         df = None  # Инициализируем DataFrame
#         symbol_for_analysis = "USER_CHART"
#         timeframe_for_analysis = "Chart"

#         # СЦЕНАРИЙ 1: ТИКЕР НАЙДЕН GPT - получаем реальные данные
#         if ticker:
#             await processing_message.edit_text(f"✅ AI identified: <b>{ticker}</b>\n\nFetching live data...", parse_mode=ParseMode.HTML)
#             await simulate_thinking(2)
            
#             # Конвертируем тикер в формат Binance
#             symbol_for_api = None
#             possible_quotes = ["USDT", "BUSD", "TUSD", "USDC"]
            
#             for quote in possible_quotes:
#                 if ticker.endswith(quote):
#                     base = ticker[:-len(quote)]
#                     symbol_for_api = f"{base}/{quote}"
#                     break
            
#             # Если не нашли стандартную котируемую, используем USDT по умолчанию
#             if not symbol_for_api:
#                 if len(ticker) >= 7:
#                     base = ticker[:-4]
#                     quote = ticker[-4:]
#                     symbol_for_api = f"{base}/{quote}"
#                 else:
#                     symbol_for_api = f"{ticker}/USDT"
            
#             print(f"Fetching data for: {symbol_for_api}")
#             df = fetch_data(symbol=symbol_for_api, timeframe="15m")
#             symbol_for_analysis = symbol_for_api
#             timeframe_for_analysis = "15m"

#         # СЦЕНАРИЙ 2: ТИКЕР НЕ НАЙДЕН или не удалось получить данные - используем CV
#         if df is None or df.empty:
#             await processing_message.edit_text("📈 Analyzing chart structure patterns...")
#             await simulate_thinking(3)
            
#             if candlesticks and len(candlesticks) >= 30:
#                 ohlc_list = candlesticks_to_ohlc(candlesticks)
#                 df = pd.DataFrame(ohlc_list)
#                 df['volume'] = 1000  # Заглушка для объема
#                 symbol_for_analysis = "USER_CHART"
#                 timeframe_for_analysis = "Chart"
#             else:
#                 await processing_message.edit_text(f"❌ Sorry, I couldn't find enough candlesticks ({len(candlesticks)}) or recognize a ticker.")
#                 return

#         # ФИНАЛЬНЫЙ АНАЛИЗ: ВСЕГДА ИСПОЛЬЗУЕМ РЕШИТЕЛЬНУЮ ФУНКЦИЮ
#         await processing_message.edit_text("🤖 Running impulse analysis engine...")
#         await simulate_thinking(4)
        
#         features = compute_features(df)
#         # !!! ВЫЗЫВАЕМ РЕШИТЕЛЬНУЮ ФУНКЦИЮ ВО ВСЕХ СЛУЧАЯХ !!!
#         trade_plan = generate_decisive_signal(features, symbol_ccxt=symbol_for_analysis, timeframe=timeframe_for_analysis)

#         # ФИНАЛЬНЫЙ РЕЗУЛЬТАТ
#         await processing_message.edit_text("🎯 Generating trading plan...")
#         await simulate_thinking(2)
        
#         message = format_plan_to_message(trade_plan)
#         await processing_message.edit_text(text=message, parse_mode=ParseMode.HTML)

#     except Exception as e:
#         print(f"Error in photo_handler: {e}")
#         await processing_message.edit_text("❌ An unexpected error occurred. Please try again with a different chart.")

# def main():
#     print("Starting bot with Enhanced Subscription & Referral System...")
#     application = Application.builder().token(TELEGRAM_TOKEN).build()
    
#     # Withdrawal conversation handler
#     conv_handler = ConversationHandler(
#         entry_points=[MessageHandler(filters.Regex('^Withdraw Tokens 💵$'), withdraw_start)],
#         states={
#             ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_amount)],
#             ASK_WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_wallet)],
#         },
#         fallbacks=[CommandHandler('cancel', cancel)]
#     )
    
#     application.add_handler(CommandHandler("start", start_command))
#     application.add_handler(CommandHandler("help", help_command))
#     application.add_handler(CommandHandler("profile", profile_command))
#     application.add_handler(conv_handler)
#     application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
#     application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
#     print("Bot is running...")
#     application.run_polling()

# if __name__ == "__main__":
#     main()



# bot.py (v19 - Full Subscription & Referral System with LLM Explanations)
# import os
# import asyncio
# import pandas as pd
# import requests
# from datetime import datetime
# from dotenv import load_dotenv
# from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
# from telegram.ext import (Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler, CallbackQueryHandler)
# from telegram.constants import ParseMode

# from database import * # Import all our new DB functions
# from chart_analyzer import find_candlesticks, candlesticks_to_ohlc
# from core_analyzer import fetch_data, compute_features, generate_decisive_signal
# from llm_explainer import get_explanation  # <-- Новый модуль для объяснений

# load_dotenv()
# TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
# BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY")
# WALLET_ADDRESS = os.getenv("YOUR_WALLET_ADDRESS")
# ADMIN_USER_ID = os.getenv("ADMIN_USER_ID") # Add your own Telegram ID to .env

# PAYMENT_AMOUNT = 1.5
# USDT_CONTRACT_ADDRESS = "0x55d398326f99059fF775485246999027B3197955"

# # Conversation states for withdrawal
# ASK_AMOUNT, ASK_WALLET = range(2)

# # --- Enhanced Payment & Activation Logic ---

# async def verify_payment_and_activate(tx_hash: str, user_id: int, context: ContextTypes.DEFAULT_TYPE):
#     """
#     ФИНАЛЬНАЯ ВЕРСИЯ: Проверяет платеж с детальной отладкой и ПРАВИЛЬНО начисляет реферальные бонусы.
#     """
#     if is_tx_hash_used(tx_hash):
#         await context.bot.send_message(user_id, "❌ Verification failed.\nReason: This transaction has already been used.")
#         return

#     # Etherscan V2 API URL for BSC (chainid=56)
#     url = f"https://api.etherscan.io/v2/api?chainid=56&module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}&apikey={BSCSCAN_API_KEY}"
    
#     try:
#         print(f"DEBUG: Requesting TxInfo from Etherscan V2 for {tx_hash}")
#         response = requests.get(url, timeout=15)
#         data = response.json()
        
#         # Детальная отладка для анализа ответа от API
#         print(f"DEBUG: Etherscan V2 API Response: {data}")

#         if "result" not in data:
#             await context.bot.send_message(user_id, "❌ Verification failed.\nReason: Invalid response from blockchain explorer.")
#             return
            
#         tx = data.get("result")
        
#         # Надежная проверка на ошибки от API
#         if not isinstance(tx, dict) or not tx:
#             error_message = data.get('message', 'Transaction not found or API error.')
#             if 'Invalid API Key' in str(data):
#                 await context.bot.send_message(user_id, "❌ Verification failed.\nReason: API Key is invalid. Please contact support.")
#             else:
#                 await context.bot.send_message(user_id, f"❌ Verification failed.\nReason: Transaction details could not be fetched. Please wait a few minutes and try again. (API: {error_message})")
#             return
        
#         # --- Проверка деталей транзакции ---
#         contract_address = tx.get('to', '').lower()
#         tx_input = tx.get('input', '')
        
#         if contract_address != USDT_CONTRACT_ADDRESS.lower() or len(tx_input) < 138:
#             await context.bot.send_message(user_id, "❌ Verification failed.\nReason: Payment was not made in USDT (BEP-20).")
#             return
            
#         to_address_in_data = tx_input[34:74]
#         if WALLET_ADDRESS[2:].lower() not in to_address_in_data.lower():
#             await context.bot.send_message(user_id, "❌ Verification failed.\nReason: Payment sent to wrong address.")
#             return

#         amount_token = int(tx_input[74:138], 16) / (10**18)
#         if not (PAYMENT_AMOUNT <= amount_token < PAYMENT_AMOUNT + 0.1):
#             await context.bot.send_message(user_id, f"❌ Verification failed.\nReason: Incorrect amount. Expected {PAYMENT_AMOUNT}, received {amount_token:.4f} USDT.")
#             return
            
#         # --- УСПЕХ! АКТИВАЦИЯ ПОЛЬЗОВАТЕЛЯ ---
#         activate_user_subscription(user_id)
#         mark_tx_hash_as_used(tx_hash)
        
#         keyboard = [["Analyze Chart 📈", "Profile 👤"]]
#         reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
#         await context.bot.send_message(user_id, "✅ Payment successful! Welcome to Aladdin. You now have full access.", reply_markup=reply_markup)
        
#         # --- ПРАВИЛЬНАЯ ЛОГИКА РАСПРЕДЕЛЕНИЯ РЕФЕРАЛЬНЫХ НАГРАД ---
#         # 1. Строим цепочку рефереров для ТОЛЬКО ЧТО АКТИВИРОВАННОГО пользователя (user_id)
#         #    get_referrer_chain вернет [прямой_реферер, реферер_2_уровня, реферер_3_уровня]
#         referral_chain = get_referrer_chain(user_id, levels=3)
        
#         # 2. Определяем награды для каждого уровня
#         rewards = [15, 10, 5] # Уровень 1, Уровень 2, Уровень 3
        
#         # 3. Проходим по цепочке и начисляем правильные награды
#         #    i = 0 -> referrer_user_id = прямой реферер, получает rewards[0] = 15
#         #    i = 1 -> referrer_user_id = реферер 2-го уровня, получает rewards[1] = 10
#         #    ...и так далее
#         for i, referrer_user_id in enumerate(referral_chain):
#             if i < len(rewards): # Защита на случай, если цепочка короче
#                 reward_amount = rewards[i]
#                 credit_referral_tokens(referrer_user_id, reward_amount)
#                 try:
#                     await context.bot.send_message(
#                         referrer_user_id, 
#                         f"🎉 Congratulations! You received {reward_amount} tokens from a level {i+1} referral."
#                     )
#                 except Exception as e:
#                     print(f"Could not notify referrer {referrer_user_id}: {e}")

#     except Exception as e:
#         print(f"Error in verify_payment: {e}")
#         await context.bot.send_message(user_id, "❌ An unexpected error occurred during verification.")

# async def simulate_thinking(duration=2):
#     """Задержка для естественности"""
#     await asyncio.sleep(duration)

# def format_plan_to_message(plan):
#     symbol = plan.get('symbol', 'N/A')
#     timeframe = plan.get('timeframe', 'N/A')
#     view = plan.get('view', 'neutral')
    
#     if view == 'long':
#         icon = "🟢"
#         title = f"<b>Long Idea: ${symbol}</b> ({timeframe})"
#     elif view == 'short':
#         icon = "🔴"
#         title = f"<b>Short Idea: ${symbol}</b> ({timeframe})"
#     else:
#         icon = "⚪️"
#         title = f"<b>Analysis: ${symbol}</b> ({timeframe})"
#         message = f"{icon} {title}\n\n{plan.get('notes', 'No notes.')}"
#         return message
    
#     entry_zone = plan.get('entry_zone', ['N/A'])
#     stop_loss = plan.get('stop', 'N/A')
#     targets = plan.get('targets', ['N/A'])
#     notes = plan.get('notes', 'No notes.')
    
#     message = (
#         f"{icon} {title}\n\n"
#         f"<b>🔹 Entry Zone:</b> <code>{entry_zone[0]} - {entry_zone[1]}</code>\n"
#         f"<b>🔸 Stop Loss:</b> <code>{stop_loss}</code>\n"
#         f"<b>🎯 Target(s):</b> <code>{', '.join(map(str, targets))}</code>\n\n"
#         f"📝 <b>Rationale:</b>\n"
#         f"<i>{notes}</i>\n\n"
#         f"<pre>⚠️ Not financial advice. DYOR.</pre>"
#     )
#     return message

# # --- Enhanced Bot Command Handlers ---

# async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user = update.effective_user
    
#     # Check for referral code in start parameter (e.g., /start ref_12345)
#     referrer_id = None
#     if context.args and context.args[0].startswith('ref_'):
#         code = context.args[0]
#         referrer_id = get_user_by_referral_code(code)
    
#     add_user(user.id, user.username, referrer_id)
#     status = get_user_status(user.id)

#     if status == 'active':
#         keyboard = [["Analyze Chart 📈", "Profile 👤"]]
#         reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
#         await update.message.reply_text("Welcome back! Your subscription is active.", reply_markup=reply_markup)
#     else:
#         payment_message = (
#             f"Welcome to <b>Aladdin Bot!</b> 🧞‍♂️\n\n"
#             f"To activate your 1-month subscription, please send exactly <b>{PAYMENT_AMOUNT} USDT</b> (BEP-20) to:\n\n"
#             f"<code>{WALLET_ADDRESS}</code>\n\n"
#             f"Then, paste the <b>Transaction Hash (TxID)</b> here to verify."
#         )
#         await update.message.reply_text(payment_message, parse_mode=ParseMode.HTML)

# async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = update.effective_user.id
#     profile = get_user_profile(user_id)
    
#     if not profile:
#         await update.message.reply_text("Couldn't find your profile. Please /start the bot.")
#         return
        
#     bot_username = (await context.bot.get_me()).username
#     referral_link = f"https://t.me/{bot_username}?start={profile['ref_code']}"
    
#     status_emoji = "✅ Active" if profile['status'] == 'active' else "⏳ Pending Payment"
#     expiry_text = f"Expires on: {profile['expiry']}" if profile['expiry'] else "N/A"
    
#     profile_text = (
#         f"👤 <b>Your Profile</b>\n\n"
#         f"<b>Status:</b> {status_emoji}\n"
#         f"<b>Subscription:</b> {expiry_text}\n"
#         f"<b>Token Balance:</b> {profile['balance']:.2f} Tokens\n\n"
#         f"🔗 <b>Your Referral Link:</b>\n"
#         f"<code>{referral_link}</code>\n\n"
#         f"Invite friends and earn tokens!\n"
#         f"Level 1: 15 tokens\n"
#         f"Level 2: 10 tokens\n"
#         f"Level 3: 5 tokens"
#     )
#     keyboard = [["Withdraw Tokens 💵", "Back to Menu ↩️"]]
#     reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
#     await update.message.reply_text(profile_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

# async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Enhanced help command with subscription info."""
#     user_id = update.effective_user.id
#     status = get_user_status(user_id)
    
#     if status == 'active':
#         help_text = (
#             "🧞‍♂️ <b>Aladdin - Crypto Chart Analyst</b>\n\n"
#             "Here's how you can use me:\n\n"
#             "1. Press the <b>'Analyze Chart 📈'</b> button below.\n"
#             "2. Send me a clear screenshot of a candlestick chart.\n"
#             "3. I will analyze it and provide a technical outlook.\n\n"
#             "<b>What I can do:</b>\n"
#             "• Recognize cryptocurrency symbols from charts\n"
#             "• Fetch live market data from Binance\n"
#             "• Analyze technical indicators (EMA, RSI, ATR, Bollinger Bands)\n"
#             "• Provide trading ideas with entry zones and targets\n\n"
#             "<b>Referral System:</b>\n"
#             "• Earn 15 tokens for Level 1 referrals\n"
#             "• Earn 10 tokens for Level 2 referrals\n"
#             "• Earn 5 tokens for Level 3 referrals\n"
#             "• Withdraw tokens to your wallet\n\n"
#             "<b>Available Commands:</b>\n"
#             "/start - Restart the bot and show the main menu\n"
#             "/help - Show this help message\n"
#             "/profile - View your profile and referral link\n\n"
#             "<i>Your access is active! Press the buttons below to get started!</i>"
#         )
#     else:
#         help_text = (
#             "🧞‍♂️ <b>Aladdin - Crypto Chart Analyst</b>\n\n"
#             "This bot provides AI-powered technical analysis of cryptocurrency charts.\n\n"
#             "<b>How it works:</b>\n"
#             "1. Send a screenshot of any crypto chart\n"
#             "2. I'll recognize the symbol and analyze it\n"
#             "3. Get detailed trading insights with entry/exit points\n\n"
#             "<b>Subscription:</b>\n"
#             f"• One-time payment of {PAYMENT_AMOUNT} USDT for 1 month access\n"
#             "• Full access to all analysis features\n"
#             "• Referral system to earn tokens\n\n"
#             "<b>To get started:</b>\n"
#             "Use /start to activate your access with a one-time payment.\n\n"
#             "<i>Use /start to begin the activation process!</i>"
#         )
    
#     await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

# # --- Withdrawal Conversation Handlers ---

# async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text("Please enter the amount of tokens you wish to withdraw:", reply_markup=ReplyKeyboardRemove())
#     return ASK_AMOUNT

# async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     try:
#         amount = float(update.message.text)
#         if amount <= 0: raise ValueError
        
#         profile = get_user_profile(update.effective_user.id)
#         if amount > profile['balance']:
#             await update.message.reply_text(f"Insufficient balance. You only have {profile['balance']:.2f} tokens. Please enter a valid amount.")
#             return ASK_AMOUNT
            
#         context.user_data['withdraw_amount'] = amount
#         await update.message.reply_text("Great! Now, please paste your BEP-20 (BSC) wallet address for the withdrawal.")
#         return ASK_WALLET
#     except ValueError:
#         await update.message.reply_text("Invalid amount. Please enter a number greater than 0.")
#         return ASK_AMOUNT

# async def ask_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     wallet_address = update.message.text
#     if not (wallet_address.startswith("0x") and len(wallet_address) == 42):
#         await update.message.reply_text("Invalid wallet address. Please paste a valid BEP-20 address (starts with 0x).")
#         return ASK_WALLET
        
#     amount = context.user_data['withdraw_amount']
#     user_id = update.effective_user.id
    
#     # Create request in DB
#     success = create_withdrawal_request(user_id, amount, wallet_address)
    
#     if not success:
#         await update.message.reply_text("An error occurred. Please try again.")
#         return ConversationHandler.END

#     # Notify admin
#     if ADMIN_USER_ID:
#         admin_message = (
#             f"⚠️ New Withdrawal Request ⚠️\n\n"
#             f"User ID: {user_id}\n"
#             f"Username: @{update.effective_user.username}\n"
#             f"Amount: {amount} tokens\n"
#             f"Wallet: <code>{wallet_address}</code>"
#         )
#         await context.bot.send_message(ADMIN_USER_ID, admin_message, parse_mode=ParseMode.HTML)
    
#     keyboard = [["Analyze Chart 📈", "Profile 👤"]]
#     reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
#     await update.message.reply_text("✅ Your withdrawal request has been submitted! Please allow up to 24 hours for processing.", reply_markup=reply_markup)
    
#     return ConversationHandler.END

# async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     keyboard = [["Analyze Chart 📈", "Profile 👤"]]
#     reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
#     await update.message.reply_text("Withdrawal cancelled.", reply_markup=reply_markup)
#     return ConversationHandler.END

# # --- Enhanced Text & Button Handler ---

# async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     text = update.message.text
    
#     # Handle main menu buttons
#     if text == "Analyze Chart 📈": 
#         await analyze_chart_start(update, context)
#     elif text == "Profile 👤": 
#         await profile_command(update, context)
#     elif text == "Withdraw Tokens 💵":
#         await withdraw_start(update, context)
#     elif text == "Back to Menu ↩️":
#         keyboard = [["Analyze Chart 📈", "Profile 👤"]]
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
#     if get_user_status(update.effective_user.id) != 'active':
#         await update.message.reply_text("❌ Access Required. Please use /start to activate your subscription.")
#         return
#     await update.message.reply_text("I'm ready! Please send a clear screenshot of a candlestick chart.")

# # --- LLM Explanation Handler ---

# async def explain_analysis_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Обрабатывает нажатие на кнопку 'Explain Factors'."""
#     query = update.callback_query
#     await query.answer()

#     # Убираем кнопку, чтобы избежать повторных нажатий
#     await query.edit_message_reply_markup(reply_markup=None)
    
#     analysis_context = context.user_data.get('last_analysis_context')
#     if not analysis_context:
#         await query.message.reply_text("Sorry, I couldn't find the context for this analysis. Please try again.")
#         return

#     await query.message.reply_text("<i>Aladdin is thinking... 🧞‍♂️</i>", parse_mode=ParseMode.HTML)
    
#     # Получаем объяснение от LLM
#     explanation = get_explanation(analysis_context)
    
#     await query.message.reply_text(explanation, parse_mode=ParseMode.MARKDOWN)

# async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """
#     УМНАЯ ОБРАБОТКА ГРАФИКОВ С ИМПУЛЬСНЫМ АНАЛИЗОМ И ПРОВЕРКОЙ ПОДПИСКИ
#     """
#     user = update.message.from_user
#     user_id = user.id
    
#     # Check subscription status
#     if get_user_status(user_id) != 'active':
#         await update.message.reply_text(
#             "❌ <b>Access Required</b>\n\n"
#             "Your access is not active. Please use the /start command to make a payment and activate full access.",
#             parse_mode=ParseMode.HTML
#         )
#         return
    
#     file_path = f'chart_for_{user.id}.jpg'
#     processing_message = await update.message.reply_text("📨 Chart received! Starting analysis...")
    
#     try:
#         photo_file = await update.message.photo[-1].get_file()
#         await photo_file.download_to_drive(file_path)

#         # Этап 1: Анализ изображения с GPT
#         await processing_message.edit_text("🔍 Analyzing chart with AI...")
#         await simulate_thinking(3)
        
#         candlesticks, ticker = find_candlesticks(file_path)
        
#         df = None  # Инициализируем DataFrame
#         symbol_for_analysis = "USER_CHART"
#         timeframe_for_analysis = "Chart"
#         analysis_context = None  # Для хранения контекста анализа

#         # СЦЕНАРИЙ 1: ТИКЕР НАЙДЕН GPT - получаем реальные данные
#         if ticker:
#             await processing_message.edit_text(f"✅ AI identified: <b>{ticker}</b>\n\nFetching live data...", parse_mode=ParseMode.HTML)
#             await simulate_thinking(2)
            
#             # Конвертируем тикер в формат Binance
#             symbol_for_api = None
#             possible_quotes = ["USDT", "BUSD", "TUSD", "USDC"]
            
#             for quote in possible_quotes:
#                 if ticker.endswith(quote):
#                     base = ticker[:-len(quote)]
#                     symbol_for_api = f"{base}/{quote}"
#                     break
            
#             # Если не нашли стандартную котируемую, используем USDT по умолчанию
#             if not symbol_for_api:
#                 if len(ticker) >= 7:
#                     base = ticker[:-4]
#                     quote = ticker[-4:]
#                     symbol_for_api = f"{base}/{quote}"
#                 else:
#                     symbol_for_api = f"{ticker}/USDT"
            
#             print(f"Fetching data for: {symbol_for_api}")
#             df = fetch_data(symbol=symbol_for_api, timeframe="15m")
#             symbol_for_analysis = symbol_for_api
#             timeframe_for_analysis = "15m"

#         # СЦЕНАРИЙ 2: ТИКЕР НЕ НАЙДЕН или не удалось получить данные - используем CV
#         if df is None or df.empty:
#             await processing_message.edit_text("📈 Analyzing chart structure patterns...")
#             await simulate_thinking(3)
            
#             if candlesticks and len(candlesticks) >= 30:
#                 ohlc_list = candlesticks_to_ohlc(candlesticks)
#                 df = pd.DataFrame(ohlc_list)
#                 df['volume'] = 1000  # Заглушка для объема
#                 symbol_for_analysis = "USER_CHART"
#                 timeframe_for_analysis = "Chart"
#             else:
#                 await processing_message.edit_text(f"❌ Sorry, I couldn't find enough candlesticks ({len(candlesticks)}) or recognize a ticker.")
#                 return

#         # ФИНАЛЬНЫЙ АНАЛИЗ: ВСЕГДА ИСПОЛЬЗУЕМ РЕШИТЕЛЬНУЮ ФУНКЦИЮ
#         await processing_message.edit_text("🤖 Running impulse analysis engine...")
#         await simulate_thinking(4)
        
#         features = compute_features(df)
#         # !!! ВЫЗЫВАЕМ РЕШИТЕЛЬНУЮ ФУНКЦИЮ ВО ВСЕХ СЛУЧАЯХ !!!
#         trade_plan, analysis_context = generate_decisive_signal(features, symbol_ccxt=symbol_for_analysis, timeframe=timeframe_for_analysis)

#         if not trade_plan:
#             await processing_message.edit_text("❌ Sorry, I couldn't analyze this chart properly.")
#             return

#         # Сохраняем контекст для будущего использования
#         context.user_data['last_analysis_context'] = analysis_context
        
#         # Создаем кнопку для объяснения
#         keyboard = [[InlineKeyboardButton("Explain Factors 🔬", callback_data="explain_analysis")]]
#         reply_markup = InlineKeyboardMarkup(keyboard)

#         # ФИНАЛЬНЫЙ РЕЗУЛЬТАТ с кнопкой
#         await processing_message.edit_text("🎯 Generating trading plan...")
#         await simulate_thinking(2)
        
#         message = format_plan_to_message(trade_plan)
#         await processing_message.edit_text(text=message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

#     except Exception as e:
#         print(f"Error in photo_handler: {e}")
#         await processing_message.edit_text("❌ An unexpected error occurred. Please try again with a different chart.")

# def main():
#     print("Starting bot with Enhanced Subscription & Referral System...")
#     application = Application.builder().token(TELEGRAM_TOKEN).build()
    
#     # Withdrawal conversation handler
#     conv_handler = ConversationHandler(
#         entry_points=[MessageHandler(filters.Regex('^Withdraw Tokens 💵$'), withdraw_start)],
#         states={
#             ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_amount)],
#             ASK_WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_wallet)],
#         },
#         fallbacks=[CommandHandler('cancel', cancel)]
#     )
    
#     application.add_handler(CommandHandler("start", start_command))
#     application.add_handler(CommandHandler("help", help_command))
#     application.add_handler(CommandHandler("profile", profile_command))
#     application.add_handler(conv_handler)
#     application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
#     application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
#     # --- НОВЫЙ ОБРАБОТЧИК ДЛЯ КНОПКИ ОБЪЯСНЕНИЯ ---
#     application.add_handler(CallbackQueryHandler(explain_analysis_handler, pattern="^explain_analysis$"))
    
#     print("Bot is running...")
#     application.run_polling()

# if __name__ == "__main__":
#     main()


# bot.py (v20 - Full Risk Management Integration)
import os
import asyncio
import pandas as pd
import requests
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler, CallbackQueryHandler)
from telegram.constants import ParseMode

from database import * # Import all our new DB functions including risk management
from chart_analyzer import find_candlesticks, candlesticks_to_ohlc
from core_analyzer import fetch_data, compute_features, generate_decisive_signal, generate_signal
from llm_explainer import get_explanation

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY")
WALLET_ADDRESS = os.getenv("YOUR_WALLET_ADDRESS")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")

PAYMENT_AMOUNT = 1.5
USDT_CONTRACT_ADDRESS = "0x55d398326f99059fF775485246999027B3197955"

# Conversation states
ASK_AMOUNT, ASK_WALLET = range(2)  # Withdrawal
ASK_BALANCE, ASK_RISK_PCT = range(2, 4)  # Risk management

# --- Enhanced Payment & Activation Logic ---
async def verify_payment_and_activate(tx_hash: str, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """
    ФИНАЛЬНАЯ ВЕРСИЯ: Проверяет платеж с детальной отладкой и ПРАВИЛЬНО начисляет реферальные бонусы.
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
                await context.bot.send_message(user_id, f"❌ Verification failed.\nReason: Transaction details could not be fetched. Please wait a few minutes and try again. (API: {error_message})")
            return
        
        # --- Проверка деталей транзакции ---
        contract_address = tx.get('to', '').lower()
        tx_input = tx.get('input', '')
        
        if contract_address != USDT_CONTRACT_ADDRESS.lower() or len(tx_input) < 138:
            await context.bot.send_message(user_id, "❌ Verification failed.\nReason: Payment was not made in USDT (BEP-20).")
            return
            
        to_address_in_data = tx_input[34:74]
        if WALLET_ADDRESS[2:].lower() not in to_address_in_data.lower():
            await context.bot.send_message(user_id, "❌ Verification failed.\nReason: Payment sent to wrong address.")
            return

        amount_token = int(tx_input[74:138], 16) / (10**18)
        if not (PAYMENT_AMOUNT <= amount_token < PAYMENT_AMOUNT + 0.1):
            await context.bot.send_message(user_id, f"❌ Verification failed.\nReason: Incorrect amount. Expected {PAYMENT_AMOUNT}, received {amount_token:.4f} USDT.")
            return
            
        # --- УСПЕХ! АКТИВАЦИЯ ПОЛЬЗОВАТЕЛЯ ---
        activate_user_subscription(user_id)
        mark_tx_hash_as_used(tx_hash)
        
        keyboard = [["Analyze Chart 📈", "Profile 👤", "Risk Settings ⚙️"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await context.bot.send_message(user_id, "✅ Payment successful! Welcome to Aladdin. You now have full access.", reply_markup=reply_markup)
        
        # --- ПРАВИЛЬНАЯ ЛОГИКА РАСПРЕДЕЛЕНИЯ РЕФЕРАЛЬНЫХ НАГРАД ---
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

    except Exception as e:
        print(f"Error in verify_payment: {e}")
        await context.bot.send_message(user_id, "❌ An unexpected error occurred during verification.")

async def simulate_thinking(duration=2):
    """Задержка для естественности"""
    await asyncio.sleep(duration)

def format_plan_to_message(plan):
    symbol = plan.get('symbol', 'N/A')
    timeframe = plan.get('timeframe', 'N/A')
    view = plan.get('view', 'neutral')
    
    if view == 'long':
        icon = "🟢"
        title = f"<b>Long Idea: ${symbol}</b> ({timeframe})"
    elif view == 'short':
        icon = "🔴"
        title = f"<b>Short Idea: ${symbol}</b> ({timeframe})"
    else:
        icon = "⚪️"
        title = f"<b>Analysis: ${symbol}</b> ({timeframe})"
        message = f"{icon} {title}\n\n{plan.get('notes', 'No notes.')}"
        return message
    
    entry_zone = plan.get('entry_zone', ['N/A'])
    stop_loss = plan.get('stop', 'N/A')
    targets = plan.get('targets', ['N/A'])
    notes = plan.get('notes', 'No notes.')
    
    message = (
        f"{icon} {title}\n\n"
        f"<b>🔹 Entry Zone:</b> <code>{entry_zone[0]} - {entry_zone[1]}</code>\n"
        f"<b>🔸 Stop Loss:</b> <code>{stop_loss}</code>\n"
        f"<b>🎯 Target(s):</b> <code>{', '.join(map(str, targets))}</code>\n\n"
        f"📝 <b>Rationale:</b>\n"
        f"<i>{notes}</i>"
    )
    
    # --- ADD NEW LINES FOR RISK DATA ---
    if view != 'neutral':
        pos_size_asset = plan.get('position_size_asset', 'N/A')
        symbol_base = plan.get('symbol', 'ASSET').replace('USDT', '')
        pos_size_usd = plan.get('position_size_usd', 'N/A')
        potential_loss = plan.get('potential_loss_usd', 'N/A')
        
        risk_section = (
            f"\n\n"
            f"<b>Risk Profile:</b>\n"
            f"  - Position Size: <code>{pos_size_asset} {symbol_base}</code> ({pos_size_usd})\n"
            f"  - Max Loss on this trade: <code>{potential_loss}</code>"
        )
        message += risk_section
        
    message += "\n\n<pre>⚠️ Not financial advice. DYOR.</pre>"
    return message

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
        keyboard = [["Analyze Chart 📈", "Profile 👤", "Risk Settings ⚙️"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Welcome back! Your subscription is active.", reply_markup=reply_markup)
    else:
        payment_message = (
            f"Welcome to <b>Aladdin Bot!</b> 🧞‍♂️\n\n"
            f"To activate your 1-month subscription, please send exactly <b>{PAYMENT_AMOUNT} USDT</b> (BEP-20) to:\n\n"
            f"<code>{WALLET_ADDRESS}</code>\n\n"
            f"Then, paste the <b>Transaction Hash (TxID)</b> here to verify."
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
            "• Full access to all analysis features\n"
            "• Referral system to earn tokens\n"
            "• Risk management with position sizing\n\n"
            "<b>To get started:</b>\n"
            "Use /start to activate your access with a one-time payment.\n\n"
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
    
    keyboard = [["Analyze Chart 📈", "Profile 👤", "Risk Settings ⚙️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("✅ Your withdrawal request has been submitted! Please allow up to 24 hours for processing.", reply_markup=reply_markup)
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Analyze Chart 📈", "Profile 👤", "Risk Settings ⚙️"]]
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
    
    keyboard = [["Analyze Chart 📈", "Profile 👤", "Risk Settings ⚙️"]]
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
    keyboard = [["Analyze Chart 📈", "Profile 👤", "Risk Settings ⚙️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Risk setup cancelled.", reply_markup=reply_markup)
    context.user_data.clear()
    return ConversationHandler.END

# --- Enhanced Text & Button Handler ---

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # Handle main menu buttons
    if text == "Analyze Chart 📈": 
        await analyze_chart_start(update, context)
    elif text == "Profile 👤": 
        await profile_command(update, context)
    elif text == "Risk Settings ⚙️":
        await risk_command(update, context)
    elif text == "Withdraw Tokens 💵":
        await withdraw_start(update, context)
    elif text == "Back to Menu ↩️":
        keyboard = [["Analyze Chart 📈", "Profile 👤", "Risk Settings ⚙️"]]
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
    if get_user_status(update.effective_user.id) != 'active':
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

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    УМНАЯ ОБРАБОТКА ГРАФИКОВ С ИМПУЛЬСНЫМ АНАЛИЗОМ И ПРОВЕРКОЙ ПОДПИСКИ
    """
    user = update.message.from_user
    user_id = user.id
    
    # Check subscription status
    if get_user_status(user_id) != 'active':
        await update.message.reply_text(
            "❌ <b>Access Required</b>\n\n"
            "Your access is not active. Please use the /start command to make a payment and activate full access.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # --- GET USER RISK SETTINGS ---
    risk_settings = get_user_risk_settings(user_id)
    
    file_path = f'chart_for_{user.id}.jpg'
    processing_message = await update.message.reply_text("📨 Chart received! Starting analysis...")
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        await photo_file.download_to_drive(file_path)

        # Этап 1: Анализ изображения с GPT
        await processing_message.edit_text("🔍 Analyzing chart with AI...")
        await simulate_thinking(3)
        
        candlesticks, ticker = find_candlesticks(file_path)
        
        df = None  # Инициализируем DataFrame
        symbol_for_analysis = "USER_CHART"
        timeframe_for_analysis = "Chart"
        analysis_context = None  # Для хранения контекста анализа

        # СЦЕНАРИЙ 1: ТИКЕР НАЙДЕН GPT - получаем реальные данные
        if ticker:
            await processing_message.edit_text(f"✅ AI identified: <b>{ticker}</b>\n\nFetching live data...", parse_mode=ParseMode.HTML)
            await simulate_thinking(2)
            
            # Конвертируем тикер в формат Binance
            symbol_for_api = None
            possible_quotes = ["USDT", "BUSD", "TUSD", "USDC"]
            
            for quote in possible_quotes:
                if ticker.endswith(quote):
                    base = ticker[:-len(quote)]
                    symbol_for_api = f"{base}/{quote}"
                    break
            
            # Если не нашли стандартную котируемую, используем USDT по умолчанию
            if not symbol_for_api:
                if len(ticker) >= 7:
                    base = ticker[:-4]
                    quote = ticker[-4:]
                    symbol_for_api = f"{base}/{quote}"
                else:
                    symbol_for_api = f"{ticker}/USDT"
            
            print(f"Fetching data for: {symbol_for_api}")
            df = fetch_data(symbol=symbol_for_api, timeframe="15m")
            symbol_for_analysis = symbol_for_api
            timeframe_for_analysis = "15m"

        # СЦЕНАРИЙ 2: ТИКЕР НЕ НАЙДЕН или не удалось получить данные - используем CV
        if df is None or df.empty:
            await processing_message.edit_text("📈 Analyzing chart structure patterns...")
            await simulate_thinking(3)
            
            if candlesticks and len(candlesticks) >= 30:
                ohlc_list = candlesticks_to_ohlc(candlesticks)
                df = pd.DataFrame(ohlc_list)
                df['volume'] = 1000  # Заглушка для объема
                symbol_for_analysis = "USER_CHART"
                timeframe_for_analysis = "Chart"
            else:
                await processing_message.edit_text(f"❌ Sorry, I couldn't find enough candlesticks ({len(candlesticks)}) or recognize a ticker.")
                return

        # ФИНАЛЬНЫЙ АНАЛИЗ: ВСЕГДА ИСПОЛЬЗУЕМ РЕШИТЕЛЬНУЮ ФУНКЦИЮ
        await processing_message.edit_text("🤖 Running impulse analysis engine...")
        await simulate_thinking(4)
        
        features = compute_features(df)
        # !!! ВЫЗЫВАЕМ РЕШИТЕЛЬНУЮ ФУНКЦИЮ ВО ВСЕХ СЛУЧАЯХ !!!
        trade_plan, analysis_context = generate_decisive_signal(features, symbol_ccxt=symbol_for_analysis, risk_settings=risk_settings, timeframe=timeframe_for_analysis)

        if not trade_plan:
            await processing_message.edit_text("❌ Sorry, I couldn't analyze this chart properly.")
            return

        # Сохраняем контекст для будущего использования
        context.user_data['last_analysis_context'] = analysis_context
        
        # Создаем кнопку для объяснения
        keyboard = [[InlineKeyboardButton("Explain Factors 🔬", callback_data="explain_analysis")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # ФИНАЛЬНЫЙ РЕЗУЛЬТАТ с кнопкой
        await processing_message.edit_text("🎯 Generating trading plan...")
        await simulate_thinking(2)
        
        message = format_plan_to_message(trade_plan)
        await processing_message.edit_text(text=message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

    except Exception as e:
        print(f"Error in photo_handler: {e}")
        await processing_message.edit_text("❌ An unexpected error occurred. Please try again with a different chart.")

def main():
    print("Starting bot with Enhanced Subscription & Referral System...")
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
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(withdraw_conv_handler)
    application.add_handler(risk_conv_handler)
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    # --- НОВЫЙ ОБРАБОТЧИК ДЛЯ КНОПКИ ОБЪЯСНЕНИЯ ---
    application.add_handler(CallbackQueryHandler(explain_analysis_handler, pattern="^explain_analysis$"))
    
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()