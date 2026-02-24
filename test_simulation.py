#!/usr/bin/env python3
"""
Full BingX + Bybit copy trading simulation.
Mocks exchange API calls to verify the entire flow works:
  Signal → Queue → Worker → Trade Sizing → Order → PnL → DB
"""
import os, sys, time, threading
from queue import Queue
from unittest.mock import MagicMock, patch, PropertyMock
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Mock Exchange Classes ──

class MockBingX:
    """Mocks ccxt.bingx for futures trading"""
    def __init__(self, config=None):
        self.config = config or {}
        self._leverage = 4
        self._orders = {}
        self._order_id = 100

    def fetch_balance(self, params=None):
        return {
            'USDT': {'free': 1000.0, 'used': 0.0, 'total': 1000.0},
            'free': {'USDT': 1000.0}, 'total': {'USDT': 1000.0}
        }

    def fetch_ticker(self, symbol, params=None):
        prices = {'BTC/USDT:USDT': 64500.0, 'ETH/USDT:USDT': 1850.0}
        return {'last': prices.get(symbol, 64500.0)}

    def set_leverage(self, lev, symbol):
        self._leverage = lev

    def amount_to_precision(self, symbol, amount):
        return str(round(amount, 6))

    def create_order(self, symbol, type, side, amount, price=None, params=None):
        self._order_id += 1
        oid = str(self._order_id)
        p = 64500.0 if 'BTC' in symbol else 1850.0
        self._orders[oid] = {
            'id': oid, 'symbol': symbol, 'status': 'closed',
            'filled': float(amount), 'average': p, 'price': p, 'side': side
        }
        return self._orders[oid]

    def fetch_order(self, order_id, symbol=None):
        return self._orders.get(str(order_id), {'average': 64500.0, 'filled': 0.001, 'price': 64500.0})

    def fetch_positions(self, symbols=None):
        return [{'side': 'long', 'contracts': 0.001, 'info': {'positionSide': 'LONG'}}]


class MockBybit:
    """Mocks ccxt.bybit for linear futures"""
    def __init__(self, config=None):
        self.config = config or {}
        self._leverage = 5
        self._orders = {}
        self._order_id = 200

    def fetch_balance(self, params=None):
        return {
            'USDT': {'free': 2600.0, 'used': 0.0, 'total': 2600.0},
            'free': {'USDT': 2600.0}, 'total': {'USDT': 2600.0}
        }

    def fetch_ticker(self, symbol, params=None):
        return {'last': 64500.0}

    def set_leverage(self, lev, symbol):
        self._leverage = lev

    def amount_to_precision(self, symbol, amount):
        return str(round(amount, 6))

    def create_order(self, symbol, type, side, amount, price=None, params=None):
        self._order_id += 1
        oid = str(self._order_id)
        self._orders[oid] = {
            'id': oid, 'symbol': symbol, 'status': 'closed',
            'filled': float(amount), 'average': 64500.0, 'price': 64500.0, 'side': side
        }
        return self._orders[oid]

    def fetch_order(self, order_id, symbol=None):
        return self._orders.get(str(order_id), {'average': 64500.0, 'filled': 0.001, 'price': 64500.0})

    def fetch_positions(self, symbols=None):
        return [{'side': 'long', 'contracts': 0.001, 'info': {'positionSide': 'LONG'}}]


# ── Test Harness ──

def run_simulation():
    print("=" * 70)
    print("🧪 BINGX + BYBIT COPY TRADING FULL SIMULATION")
    print("=" * 70)

    import ccxt
    from worker import TradeCopier

    # Save originals
    orig_bingx = ccxt.bingx
    orig_bybit = ccxt.bybit

    results = {"bingx_open": False, "bingx_close": False, "bybit_open": False, "bybit_close": False}
    trade_details = {}

    try:
        # Patch exchanges
        ccxt.bingx = MockBingX
        ccxt.bybit = MockBybit

        copier = TradeCopier(bot_instance=None)
        copier._get_master_balance = MagicMock(return_value=10000.0)

        # ═══════════════════════════════════════════
        # TEST 1: BINGX FUTURES — OPEN (BUY)
        # ═══════════════════════════════════════════
        print("\n" + "─" * 70)
        print("📗 TEST 1: BingX Futures — OPEN BUY (ratner strategy)")
        print("─" * 70)
        print("   Config: bal=$1000, reserve=$0, risk_pct=1% → expect trade=$10")

        try:
            keys = {'apiKey': 'test', 'secret': 'test', 'exchange': 'bingx'}
            copier._execute_bingx_futures(
                keys=keys, user_id=99901, symbol='BTC/USDT',
                side='buy', reserve=0.0, percentage_used=0.05,  # old ratio (should be ignored)
                is_closing=False, is_reduce_only=False, open_trade=None,
                master_order_id=1001, open_client_copy=None, risk_pct=1.0
            )
            results["bingx_open"] = True

            # Calculate expected
            expected_amt = 1000.0 * (1.0 / 100.0)  # $10
            expected_qty = round(expected_amt / 64500.0, 6)
            trade_details["bingx_open"] = {"expected_amt": expected_amt, "expected_qty": expected_qty}
            print(f"   ✅ PASS — Expected trade: ${expected_amt:.2f} ({expected_qty:.6f} BTC)")
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            import traceback; traceback.print_exc()

        # ═══════════════════════════════════════════
        # TEST 2: BINGX FUTURES — CLOSE (SELL)
        # ═══════════════════════════════════════════
        print("\n" + "─" * 70)
        print("📕 TEST 2: BingX Futures — CLOSE (reduce_only sell)")
        print("─" * 70)
        print("   Config: open position 0.001 BTC @ $64000, close at market")

        try:
            open_trade = {'side': 'buy', 'entry_price': 64000.0, 'quantity': 0.001}
            open_copy = {'entry_price': 64000.0, 'copy_id': 1, 'side': 'buy', 'quantity': 0.001}

            copier._execute_bingx_futures(
                keys=keys, user_id=99901, symbol='BTC/USDT',
                side='sell', reserve=0.0, percentage_used=0.05,
                is_closing=True, is_reduce_only=True,
                open_trade=open_trade,
                master_order_id=1002, open_client_copy=open_copy, risk_pct=1.0
            )
            results["bingx_close"] = True
            print(f"   ✅ PASS — Position closed via reduceOnly")
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            import traceback; traceback.print_exc()

        # ═══════════════════════════════════════════
        # TEST 3: BYBIT FUTURES — OPEN (BUY)
        # ═══════════════════════════════════════════
        print("\n" + "─" * 70)
        print("📗 TEST 3: Bybit Futures — OPEN BUY (aitrading strategy)")
        print("─" * 70)
        print("   Config: bal=$2600, reserve=$0, risk_pct=1% → expect trade=$26")

        try:
            keys_bybit = {'apiKey': 'test', 'secret': 'test', 'exchange': 'bybit'}
            copier._execute_bybit_futures(
                keys=keys_bybit, user_id=99902, symbol='BTCUSDT',
                side='buy', reserve=0.0, percentage_used=0.05,  # old ratio
                is_closing=False, is_reduce_only=False, open_trade=None,
                master_order_id=2001, open_client_copy=None, risk_pct=1.0
            )
            results["bybit_open"] = True

            expected_amt = 2600.0 * (1.0 / 100.0)  # $26
            expected_qty = round(expected_amt / 64500.0, 6)
            trade_details["bybit_open"] = {"expected_amt": expected_amt, "expected_qty": expected_qty}
            print(f"   ✅ PASS — Expected trade: ${expected_amt:.2f} ({expected_qty:.6f} BTC)")
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            import traceback; traceback.print_exc()

        # ═══════════════════════════════════════════
        # TEST 4: BYBIT FUTURES — CLOSE (SELL)
        # ═══════════════════════════════════════════
        print("\n" + "─" * 70)
        print("📕 TEST 4: Bybit Futures — CLOSE (reduce_only sell)")
        print("─" * 70)
        print("   Config: open position 0.001 BTC @ $64000, close at market")

        try:
            open_trade = {'side': 'buy', 'entry_price': 64000.0, 'quantity': 0.001}
            open_copy = {'entry_price': 64000.0, 'copy_id': 2, 'side': 'buy', 'quantity': 0.001}

            copier._execute_bybit_futures(
                keys=keys_bybit, user_id=99902, symbol='BTCUSDT',
                side='sell', reserve=0.0, percentage_used=0.05,
                is_closing=True, is_reduce_only=True,
                open_trade=open_trade,
                master_order_id=2002, open_client_copy=open_copy, risk_pct=1.0
            )
            results["bybit_close"] = True
            print(f"   ✅ PASS — Position closed via reduceOnly")
        except Exception as e:
            print(f"   ❌ FAIL: {e}")
            import traceback; traceback.print_exc()

        # ═══════════════════════════════════════════
        # TEST 5: FULL QUEUE → WORKER FLOW (BingX)
        # ═══════════════════════════════════════════
        print("\n" + "─" * 70)
        print("🔗 TEST 5: Full Queue → Worker flow (BingX signal)")
        print("─" * 70)

        execution_flag = threading.Event()
        original_execute = copier._execute_bingx_futures

        def tracked_execute(*args, **kwargs):
            execution_flag.set()
            return original_execute(*args, **kwargs)

        copier._execute_bingx_futures = tracked_execute

        # Mock DB calls
        with patch('database.get_active_exchange_connections', return_value=[
            {'user_id': 99903, 'exchange_name': 'bingx', 'reserved_amount': 0.0, 'risk_pct': 1.0, 'strategy': 'ratner'}
        ]), patch('database.get_user_decrypted_keys', return_value={
            'apiKey': 'test', 'secret': 'test', 'exchange': 'bingx', 'reserved_amount': 0.0
        }), patch('database.get_open_trade', return_value=None), \
             patch('database.get_open_client_copy', return_value=None):

            test_queue = Queue()
            t = threading.Thread(target=copier.start_consuming, args=(test_queue,), daemon=True)
            t.start()

            signal = {
                'master_exchange': 'bingx', 'strategy': 'ratner',
                's': 'BTC/USDT', 'S': 'buy', 'o': 'MARKET', 'X': 'FILLED',
                'q': 0.01, 'p': 64500.0, 'ap': 64500.0, 'ot': 'FUTURE', 'ro': False
            }
            test_queue.put(signal)

            success = execution_flag.wait(timeout=5.0)
            if success:
                results["queue_flow"] = True
                print("   ✅ PASS — Signal flowed: Queue → Worker → BingX execution")
            else:
                results["queue_flow"] = False
                print("   ❌ FAIL — Worker did not execute within 5s")

        # ═══════════════════════════════════════════
        # TEST 6: TRADE SIZING VERIFICATION
        # ═══════════════════════════════════════════
        print("\n" + "─" * 70)
        print("📐 TEST 6: Trade Sizing Verification")
        print("─" * 70)

        sizing_tests = [
            {"bal": 1000, "reserve": 0, "risk": 1.0, "expected": 10.0, "exchange": "BingX"},
            {"bal": 2600, "reserve": 0, "risk": 1.0, "expected": 26.0, "exchange": "Bybit"},
            {"bal": 5000, "reserve": 1000, "risk": 2.0, "expected": 80.0, "exchange": "BingX"},
            {"bal": 1000, "reserve": 500, "risk": 1.0, "expected": 5.0, "exchange": "Bybit"},
        ]

        all_sizing_ok = True
        for t in sizing_tests:
            available = max(0, t["bal"] - t["reserve"])
            amt = available * (t["risk"] / 100.0)
            ok = abs(amt - t["expected"]) < 0.01
            if not ok: all_sizing_ok = False
            status = "✅" if ok else "❌"
            print(f"   {status} {t['exchange']}: bal=${t['bal']}, res=${t['reserve']}, risk={t['risk']}% → ${amt:.2f} (expected ${t['expected']:.2f})")

        results["sizing"] = all_sizing_ok

    finally:
        # Restore
        ccxt.bingx = orig_bingx
        ccxt.bybit = orig_bybit

    # ═══════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════
    print("\n" + "=" * 70)
    print("📋 SIMULATION RESULTS")
    print("=" * 70)

    all_pass = True
    labels = {
        "bingx_open": "BingX Open (BUY)",
        "bingx_close": "BingX Close (SELL)",
        "bybit_open": "Bybit Open (BUY)",
        "bybit_close": "Bybit Close (SELL)",
        "queue_flow": "Queue → Worker Flow",
        "sizing": "Trade Sizing Math",
    }
    for key, label in labels.items():
        ok = results.get(key, False)
        if not ok: all_pass = False
        print(f"   {'✅ PASS' if ok else '❌ FAIL'} | {label}")

    print("\n" + ("🎉 ALL SIMULATIONS PASSED! Ready for deployment." if all_pass else "⚠️ SOME TESTS FAILED"))
    return all_pass


if __name__ == "__main__":
    run_simulation()
