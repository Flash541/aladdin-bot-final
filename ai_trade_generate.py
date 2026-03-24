import sqlite3
import json
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import database

DB_PATH = database.DB_NAME

def distribution_log(msg):
    log_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(log_msg)
    with open("ai_trade_distribution.log", "a") as f:
        f.write(log_msg + "\n")

def send_telegram_message(user_id, text):
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        distribution_log("TELEGRAM_TOKEN not found in environment.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": user_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        distribution_log(f"Failed to send Telegram message to {user_id}: {e}")

def run_daily_ai_trade_generation():
    distribution_log("Starting AI Trade daily GENERATION (22:00 CET)...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Fetch the monthly setting and schedule
        cursor.execute("SELECT value FROM global_settings WHERE key = 'ai_trade_monthly_percent' LIMIT 1")
        monthly_row = cursor.fetchone()
        
        cursor.execute("SELECT value FROM global_settings WHERE key = 'ai_trade_schedule_json' LIMIT 1")
        schedule_row = cursor.fetchone()
        
        cursor.execute("SELECT value FROM global_settings WHERE key = 'ai_trade_current_day' LIMIT 1")
        day_row = cursor.fetchone()
        
        if not monthly_row or not schedule_row or not day_row:
            distribution_log("No global settings or schedule found. Admin must set the percentage first.")
            return

        monthly_percent = float(monthly_row[0])
        schedule = json.loads(schedule_row[0])
        current_day = int(day_row[0])

        if current_day >= 30:
            # We reached the end of the 30 days. We should restart a new schedule.
            distribution_log("30-day schedule completed. Automatically generating a new schedule for the next 30 days...")
            import random
            random_parts = [random.uniform(0.5, 1.5) for _ in range(30)]
            total_parts = sum(random_parts)
            schedule = [(p / total_parts) * monthly_percent for p in random_parts]
            schedule[-1] = monthly_percent - sum(schedule[:-1])
            schedule = [max(0.0001, x) for x in schedule]
            
            cursor.execute("UPDATE global_settings SET value = ? WHERE key = 'ai_trade_schedule_json'", (json.dumps(schedule),))
            current_day = 0

        # Run today's percent
        actual_daily_percent = schedule[current_day]
        distribution_log(f"Day {current_day+1}/30: Today's exact percent is {actual_daily_percent:.4f}%")

        # Find all users with AI Trade Balance > 0
        cursor.execute("SELECT user_id, ai_trade_balance, COALESCE(language_code, 'en') FROM users WHERE ai_trade_balance > 0")
        eligible_users = cursor.fetchall()

        if not eligible_users:
            distribution_log("No users found with an active AI Trade balance.")
        else:
            total_generated = 0.0
            for user_id, ai_balance, lang in eligible_users:
                # Calculate profit
                profit = ai_balance * (actual_daily_percent / 100.0)
                
                # Update user's PENDING profit
                cursor.execute('''
                    UPDATE users 
                    SET pending_ai_profit = ?, ai_trade_daily_profit = ?
                    WHERE user_id = ?
                ''', (profit, profit, user_id))
                
                total_generated += profit

                # Notify user via Telegram in their preferred language
                lang = lang.lower()
                if "ru" in lang:
                    msg = (
                        f"🤖 <b>Ежедневная прибыль AI Trade!</b>\n\n"
                        f"Вы можете забрать свою прибыль: <b>{profit:.2f} USDT</b>.\n\n"
                        f"⚠️ <i>У вас есть ровно 20 минут, чтобы забрать прибыль в WebApp!</i>\n"
                        f"Если вы ее не заберете, она будет автоматически реинвестирована на ваш баланс AI Trade."
                    )
                elif "uk" in lang or "ua" in lang:
                    msg = (
                        f"🤖 <b>Щоденний прибуток AI Trade!</b>\n\n"
                        f"Ви можете забрати свій прибуток: <b>{profit:.2f} USDT</b>.\n\n"
                        f"⚠️ <i>У вас є рівно 20 хвилин, щоб забрати прибуток у WebApp!</i>\n"
                        f"Якщо ви його не заберете, він буде автоматично реінвестований на ваш баланс AI Trade."
                    )
                else:
                    msg = (
                        f"🤖 <b>AI Trade Daily Profit!</b>\n\n"
                        f"You can claim your profit: <b>{profit:.2f} USDT</b>.\n\n"
                        f"⚠️ <i>You have exactly 20 minutes to claim this profit in the WebApp!</i>\n"
                        f"If you don't claim it, it will automatically be reinvested into your AI Trade Balance."
                    )
                send_telegram_message(user_id, msg)

            distribution_log(f"Generated {total_generated:.4f} USDT in pending profits across {len(eligible_users)} users.")

        # Update current day and generation timestamp
        next_day = current_day + 1
        cursor.execute("UPDATE global_settings SET value = ? WHERE key = 'ai_trade_current_day'", (str(next_day),))
        
        now_str = datetime.now().isoformat()
        cursor.execute("UPDATE global_settings SET value = ? WHERE key = 'ai_trade_last_generation_time'", (now_str,))
        
        conn.commit()

    except Exception as e:
        distribution_log(f"ERROR during generation: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run_daily_ai_trade_generation()
