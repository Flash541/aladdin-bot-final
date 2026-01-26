import os
import sys
import time
import threading
from queue import Queue
from unittest.mock import MagicMock
# NO MOCKS FOR CCXT - WE WANT REAL EXECUTION

# Ensure we can import from local files
sys.path.append(os.getcwd())

from worker import TradeCopier
from database import save_user_exchange, add_user, update_exchange_reserve, set_copytrading_status

# USER CREDENTIALS PROVIDED
USER_ID = 502483421 # Using the ID from previous logs
API_KEY = "35da235c-fa34-4717-b392-7e2113703c7d"
SECRET = "FED6775506E418C26A9B45A6434E3591"
PASS = "Qwertyuiop1."
EXCHANGE = "okx"
STRATEGY = "cgt"

def run_live_test():
    print("\n⚠️  STARTING LIVE REAL-MONEY TEST (OKX) ⚠️")
    print("   This will place a REAL MARKET BUY order for XRP/USDT.")
    print("   Cost approx: $10 USDT. Please ensure you have USDT in Funding/Trading account.\n")
    
    # 1. SETUP DATABASE
    print("1. Setting up User in Database...")
    add_user(USER_ID, "live_tester")
    
    # Save keys (Encrypted via database.py)
    save_user_exchange(USER_ID, EXCHANGE, API_KEY, SECRET, PASS, strategy=STRATEGY)
    
    # Set Capital & Risk
    # Reserve = 1000, Risk = 1% => $10 Trade
    update_exchange_reserve(USER_ID, EXCHANGE, 1000.0) 
    set_copytrading_status(USER_ID, True)
    
    print("   ✅ User Credentials & Config Saved.")
    
    # 2. INITIALIZE WORKER
    print("2. Initializing TradeCopier (REAL MODE)...")
    copier = TradeCopier(bot_instance=None)
    
    # Mock master balance only (since we don't have master keys access in this script context easily/safely)
    # But we want the USER side to be real.
    copier._get_master_balance = MagicMock(return_value=1000.0)
    
    # 3. START WORKER
    print("3. Starting Worker Loop...")
    test_queue = Queue()
    t = threading.Thread(target=copier.start_consuming, args=(test_queue,), daemon=True)
    t.start()
    
    # 4. INJECT SIGNAL
    print("4. Injecting SIGNAL: BUY XRP/USDT...")
    # Taking current price approx 2.5 for XRP? No it's ~3.0 or ~0.5? 
    # Let's use a safe coin. XRP is cheap. Price ~3.33 (2025? No 2026? Wait, price doesn't matter for Market buy of $10 value)
    # Worker calculates: target_usd = 1000 * 0.01 = $10.
    # Quantity = $10 / Price.
    
    signal = {
        'master_exchange': 'okx', 
        'strategy': 'cgt',        
        's': 'XRP/USDT',     
        'S': 'buy', 
        'o': 'MARKET',            
        'X': 'FILLED',
        'q': 100.0, # Master bought 100 XRP
        'p': 0.50,  # Fake price for calculation reference (Worker fetches real price if not provided? No worker uses this 'p' or gets ticker)
        # Worker logic: current_price = ticker['last']
        'ap': 0.50,
        'ot': 'SPOT',
        'ro': False              
    }
    
    test_queue.put(signal)
    
    print("   👉 Signal Sent. Check your OKX Account for a new XRP trade!")
    print("   Waiting 10 seconds for logs...")
    time.sleep(10)
    print("\n✅ Test Completed. Check logs above for 'Confirmed Trade'.")

if __name__ == "__main__":
    run_live_test()
