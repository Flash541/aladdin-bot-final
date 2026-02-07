#!/usr/bin/env python3
"""
Real-time monitoring dashboard для локального тестирования
"""

import time
import os
from database import get_investigation_report

# Твой User ID
USER_ID = 502483421  # Измени если нужно

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')

def main():
    print("Starting Live Trading Monitor...")
    print("Press Ctrl+C to exit\n")
    time.sleep(2)
    
    try:
        while True:
            clear_screen()
            print("=" * 80)
            print("📊 LIVE TRADING MONITOR - Investigation System")
            print("=" * 80)
            
            # Get report
            report = get_investigation_report(user_id=USER_ID, limit=20)
            
            # Summary
            print(f"\n📈 SUMMARY (User {USER_ID}):")
            print(f"   Total Trades: {report['stats']['total_trades']}")
            print(f"   Open: {report['stats']['open_trades']} | Closed: {report['stats']['closed_trades']}")
            
            # PnL with color
            pnl = report['stats']['total_pnl']
            pnl_color = "✅" if pnl > 0 else "❌" if pnl < 0 else "⚪"
            print(f"   Total PnL: {pnl_color} ${pnl:.2f}")
            
            # Recent trades
            if report['copies']:
                print(f"\n🔄 RECENT TRADES:")
                print("-" * 80)
                
                for i, c in enumerate(report['copies'][:10], 1):
                    status_icon = "🟢" if c['status'] == 'open' else "🔴"
                    side_icon = "📈" if c['side'] == 'buy' else "📉"
                    
                    # Format prices
                    entry = f"${c['entry_price']:.2f}"
                    exit_str = f"${c['exit_price']:.2f}" if c['exit_price'] else "-"
                    
                    # Format PnL
                    if c['profit_loss']:
                        pnl_sign = "+" if c['profit_loss'] > 0 else ""
                        pnl_str = f"{pnl_sign}${c['profit_loss']:.2f}"
                        pnl_color = "✅" if c['profit_loss'] > 0 else "❌"
                    else:
                        pnl_str = "-"
                        pnl_color = "⚪"
                    
                    # Opened time
                    opened = c['opened_at'].split()[1] if c['opened_at'] else "-"
                    closed = c['closed_at'].split()[1] if c['closed_at'] else "-"
                    
                    print(f"{i:2d}. {status_icon} {side_icon} {c['symbol']:12} "
                          f"| Entry: {entry:10} | Exit: {exit_str:10} "
                          f"| PnL: {pnl_color} {pnl_str:10} "
                          f"| {opened} → {closed}")
                
                print("-" * 80)
            else:
                print(f"\n📭 No trades yet. Waiting for master signals...")
            
            # Update time
            print(f"\n🕐 Last update: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print("Press Ctrl+C to exit")
            
            # Wait before refresh
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\n👋 Monitor stopped. Goodbye!")

if __name__ == "__main__":
    main()
