import sqlite3
import random
import time
import os
from datetime import datetime
import database

# Setup DB path dynamically or hardcode for now
DB_PATH = database.DB_NAME

def distribution_log(msg):
    log_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(log_msg)
    # Optional: Write to a separate log file
    with open("ai_trade_distribution.log", "a") as f:
        f.write(log_msg + "\n")

def run_daily_ai_trade_distribution():
    distribution_log("Starting AI Trade daily distribution...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Fetch the global monthly percent from global_settings table
        cursor.execute("SELECT value FROM global_settings WHERE key = 'ai_trade_monthly_percent' LIMIT 1")
        row = cursor.fetchone()
        
        if not row:
            distribution_log("No global settings found. Cannot distribute profits.")
            return

        monthly_percent = float(row[0])
        
        # 2. Calculate base daily percent
        daily_percent_base = monthly_percent / 30.0
        
        # 3. Apply slight randomization (e.g. +/- 10% of the daily percent)
        # If daily is 0.5%, variation is 0.05%, so it can be 0.45% to 0.55%
        variation = daily_percent_base * 0.10
        actual_daily_percent = daily_percent_base + random.uniform(-variation, variation)
        
        # Ensure it doesn't go below 0 (though theoretically impossible with positive monthly)
        actual_daily_percent = max(0.0001, actual_daily_percent)
        
        distribution_log(f"Monthly Target: {monthly_percent}%. Base Daily: {daily_percent_base:.4f}%. Actual Randomized Daily: {actual_daily_percent:.4f}%")

        # 4. Find all users with AI Trade Balance > 0
        cursor.execute("SELECT user_id, ai_trade_balance FROM users WHERE ai_trade_balance > 0")
        eligible_users = cursor.fetchall()

        if not eligible_users:
            distribution_log("No users found with an active AI Trade balance.")
            return

        total_distributed = 0.0
        for user_id, ai_balance in eligible_users:
            # 5. Calculate profit
            profit = ai_balance * (actual_daily_percent / 100.0)
            
            # 6. Update user's balance and today's profit
            new_balance = ai_balance + profit
            
            cursor.execute('''
                UPDATE users 
                SET ai_trade_balance = ?, ai_trade_daily_profit = ?
                WHERE user_id = ?
            ''', (new_balance, profit, user_id))
            
            total_distributed += profit

        conn.commit()
        distribution_log(f"Successfully distributed {total_distributed:.4f} USDT across {len(eligible_users)} users.")

    except Exception as e:
        distribution_log(f"ERROR during distribution: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    # When run directly, just execute the distribution
    run_daily_ai_trade_distribution()
