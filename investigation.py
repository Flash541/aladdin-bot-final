#!/usr/bin/env python3
"""
Investigation Tool для анализа копирования сделок
Использование:
  python investigation.py master              # показать последние ордера мастера
  python investigation.py copies [user_id]    # показать копии клиентов
  python investigation.py check               # проверить integrity
"""

import sqlite3
import sys
import os
from tabulate import tabulate
from datetime import datetime

# Определяем путь к БД
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RENDER_DISK_PATH = os.getenv("RENDER_DISK_PATH")

if RENDER_DISK_PATH:
    DB_NAME = os.path.join(RENDER_DISK_PATH, "aladdin_users.db")
else:
    DB_NAME = os.path.join(BASE_DIR, "aladdin_dev.db")


def show_master_orders(limit=50):
    """Показать последние ордера мастера"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT order_id, master_exchange, symbol, side, order_type, price, quantity, timestamp, strategy
        FROM master_orders
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("📭 No master orders found in database")
        return
    
    headers = ["ID", "Exchange", "Symbol", "Side", "Type", "Price", "Qty", "Time", "Strategy"]
    print(f"\n📊 MASTER ORDERS (Last {limit}):")
    print(tabulate(rows, headers=headers, tablefmt="grid"))
    print(f"\nTotal: {len(rows)} orders")


def show_client_copies(user_id=None, symbol=None):
    """Показать копии клиентов с PnL"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    query = """
        SELECT 
            cc.copy_id,
            cc.user_id,
            cc.symbol,
            cc.side,
            cc.entry_price,
            cc.exit_price,
            cc.quantity,
            cc.profit_loss,
            cc.opened_at,
            cc.closed_at,
            cc.status
        FROM client_copies cc
        WHERE 1=1
    """
    params = []
    
    if user_id:
        query += " AND cc.user_id = ?"
        params.append(user_id)
    if symbol:
        query += " AND cc.symbol = ?"
        params.append(symbol)
    
    query += " ORDER BY cc.opened_at DESC LIMIT 100"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print(f"📭 No client copies found{f' for user {user_id}' if user_id else ''}")
        return
    
    # Format для display
    formatted_rows = []
    for row in rows:
        copy_id, uid, sym, side, entry, exit_p, qty, pnl, opened, closed, status = row
        
        # Format PnL with color indicator
        pnl_str = f"${pnl:.2f}" if pnl else "-"
        if pnl and pnl > 0:
            pnl_str = f"✅ {pnl_str}"
        elif pnl and pnl < 0:
            pnl_str = f"❌ {pnl_str}"
        
        # Shorten timestamps
        opened_short = opened.split()[1] if opened else "-"
        closed_short = closed.split()[1] if closed else "-"
        
        formatted_rows.append([
            copy_id, uid, sym, side.upper(), 
            f"${entry:.2f}", f"${exit_p:.2f}" if exit_p else "-", 
            f"{qty:.4f}", pnl_str, 
            opened_short, closed_short, status
        ])
    
    headers = ["ID", "User", "Symbol", "Side", "Entry", "Exit", "Qty", "PnL", "Opened", "Closed", "Status"]
    print(f"\n💼 CLIENT COPIES:")
    print(tabulate(formatted_rows, headers=headers, tablefmt="grid"))
    
    # Summary
    total_trades = len(rows)
    closed_trades = len([r for r in rows if r[10] == 'closed'])
    open_trades = total_trades - closed_trades
    total_pnl = sum(r[7] for r in rows if r[7])
    
    print(f"\n📈 SUMMARY:")
    print(f"  Total Trades: {total_trades}")
    print(f"  Open: {open_trades} | Closed: {closed_trades}")
    print(f"  Total PnL: ${total_pnl:.2f}")


def show_mismatches():
    """Найти проблемные сделки (закрытие без входа)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    print("\n🔍 CHECKING FOR ORPHAN SELLS (sell without buy)...\n")
    
    # Найти клиентов с SELL без соответствующего BUY
    cursor.execute("""
        SELECT 
            user_id, 
            symbol, 
            COUNT(*) as count,
            GROUP_CONCAT(copy_id) as copy_ids
        FROM client_copies
        WHERE side = 'sell'
          AND copy_id NOT IN (
              SELECT cc2.copy_id 
              FROM client_copies cc2 
              WHERE cc2.user_id = client_copies.user_id 
                AND cc2.symbol = client_copies.symbol 
                AND cc2.side = 'buy'
                AND cc2.opened_at < client_copies.opened_at
          )
        GROUP BY user_id, symbol
    """)
    
    orphan_sells = cursor.fetchall()
    
    if orphan_sells:
        print("🚨 FOUND ORPHAN SELLS:")
        headers = ["User ID", "Symbol", "Count", "Copy IDs"]
        print(tabulate(orphan_sells, headers=headers, tablefmt="grid"))
    else:
        print("✅ No orphan sells found - all sells have corresponding buys!")
    
    # Проверить открытые позиции, которые не закрыты долго
    print("\n🕐 CHECKING FOR OLD OPEN POSITIONS (>7 days)...\n")
    
    cursor.execute("""
        SELECT 
            user_id,
            symbol,
            side,
            entry_price,
            quantity,
            opened_at,
            CAST((julianday('now') - julianday(opened_at)) AS INTEGER) as days_open
        FROM client_copies
        WHERE status = 'open'
          AND julianday('now') - julianday(opened_at) > 7
        ORDER BY opened_at ASC
    """)
    
    old_positions = cursor.fetchall()
    
    if old_positions:
        print("⚠️ FOUND OLD OPEN POSITIONS:")
        headers = ["User", "Symbol", "Side", "Entry", "Qty", "Opened", "Days"]
        formatted = [[r[0], r[1], r[2].upper(), f"${r[3]:.2f}", f"{r[4]:.4f}", r[5], r[6]] for r in old_positions]
        print(tabulate(formatted, headers=headers, tablefmt="grid"))
    else:
        print("✅ No stale open positions!")
    
    conn.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "master":
        show_master_orders()
    elif cmd == "copies":
        uid = int(sys.argv[2]) if len(sys.argv) > 2 else None
        show_client_copies(user_id=uid)
    elif cmd == "check":
        show_mismatches()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
