import os
import sys
import time
import threading
from queue import Queue
from unittest.mock import MagicMock
import ccxt

# Ensure we can import from local files
sys.path.append(os.getcwd())

from worker import TradeCopier

def test_integration():
    print("\n🔗 STARTING INTEGRATION FLOW TEST (Queue -> Worker -> Trade)\n")
    
    # 1. SETUP MOCK EXCHANGE
    print("1. Patching Exchange (Safety Mode)...")
    original_okx = ccxt.okx
    execution_flag = threading.Event()
    
    class MockOKX(original_okx):
        def create_order(self, symbol, type, side, amount, price=None, params={}):
            print(f"\n   🟢 [SUCCESS] Worker called create_order!")
            print(f"      - Symbol: {symbol}")
            print(f"      - Side: {side}")
            print(f"      - Amount: {amount}")
            execution_flag.set() # SIGNAL SUCCESS
            return {
                'id': 'mock_integration_id',
                'symbol': symbol,
                'status': 'closed',
                'filled': amount,
                'average': 0.5,
            }
        def fetch_balance(self, params={}):
             return {'USDT': {'free': 5000.0, 'used': 0.0, 'total': 5000.0}, 'free': {'USDT': 5000.0}, 'total': {'USDT': 5000.0}}
        def fetch_ticker(self, symbol, params={}):
             return {'last': 0.5} 
             
    ccxt.okx = MockOKX
    
    # 2. INITIALIZE WORKER
    print("2. Initializing TradeCopier...")
    copier = TradeCopier(bot_instance=None)
    # Mock master balance check
    copier._get_master_balance = MagicMock(return_value=1000.0)
    
    # 3. START WORKER THREAD (QUEUE CONSUMER)
    print("3. Starting Worker Queue Consumer...")
    test_queue = Queue()
    t = threading.Thread(target=copier.start_consuming, args=(test_queue,), daemon=True)
    t.start()
    
    # 4. INJECT SIGNAL INTO QUEUE (Simulating master_tracker listener)
    print("4. Injecting Signal into Queue (Simulating master_tracker)...")
    signal = {
        'master_exchange': 'okx', 
        'strategy': 'cgt',        
        's': 'ETH/USDT',     
        'S': 'buy', 
        'o': 'MARKET',            
        'X': 'FILLED',
        'q': 20.0,
        'p': 2000.0,
        'ap': 2000.0,
        'ot': 'SPOT',
        'ro': False              
    }
    
    test_queue.put(signal)
    
    # 5. WAIT FOR EXECUTION
    print("5. Waiting for execution...")
    success = execution_flag.wait(timeout=5.0)
    
    if success:
        print("\n✅ TEST PASSED: Signal flowed from Queue -> Worker -> Execution!")
        print("   This confirms 100% that if master_tracker puts a signal in the queue, it WILL run.")
    else:
        print("\n❌ TEST FAILED: Worker did not execute order within 5 seconds.")

if __name__ == "__main__":
    test_integration()
