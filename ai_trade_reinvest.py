import sqlite3
import os
from datetime import datetime

import database

DB_PATH = database.DB_NAME

def distribution_log(msg):
    log_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(log_msg)
    with open("ai_trade_distribution.log", "a") as f:
        f.write(log_msg + "\n")

def run_daily_ai_trade_reinvest():
    distribution_log("Starting AI Trade REINVESTMENT (22:20 CET)...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if there are any pending profits
        cursor.execute("SELECT user_id, pending_ai_profit FROM users WHERE pending_ai_profit > 0")
        users_with_pending = cursor.fetchall()
        
        if not users_with_pending:
            distribution_log("No users with pending (unclaimed) profits found. Everything was claimed or no profits generated.")
            return

        total_reinvested = 0.0
        
        for user_id, pending_val in users_with_pending:
            cursor.execute('''
                UPDATE users 
                SET ai_trade_balance = ai_trade_balance + ?, 
                    pending_ai_profit = 0
                WHERE user_id = ?
            ''', (pending_val, user_id))
            total_reinvested += pending_val
            
        conn.commit()
        distribution_log(f"Successfully auto-reinvested {total_reinvested:.4f} USDT across {len(users_with_pending)} users.")

    except Exception as e:
        distribution_log(f"ERROR during reinvestment: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run_daily_ai_trade_reinvest()
