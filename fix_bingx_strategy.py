import sqlite3
import os

DB_NAME = 'aladdin_dev.db'

def fix_bingx_strategy():
    print("🔧 STARTING BINGX STRATEGY FIX...")
    
    if not os.path.exists(DB_NAME):
        print(f"❌ Error: Database {DB_NAME} not found.")
        return

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # 1. Check current state
    print("   🔎 Current BingX Users:")
    c.execute("SELECT user_id, exchange_name, strategy FROM user_exchanges WHERE exchange_name = 'bingx'")
    rows = c.fetchall()
    
    found_mismatch = False
    for r in rows:
        print(f"      - User {r['user_id']} | Strategy: {r['strategy']}")
        if r['strategy'] != 'ratner':
            found_mismatch = True
            
    if not rows:
        print("      (No BingX users found)")
        
    # 2. Update to 'ratner'
    if found_mismatch:
        print("\n   ⚠️  Found inconsistencies. Updating to 'ratner'...")
        c.execute("UPDATE user_exchanges SET strategy = 'ratner' WHERE exchange_name = 'bingx'")
        conn.commit()
        print("   ✅ Database Updated. New State:")
        
        c.execute("SELECT user_id, exchange_name, strategy FROM user_exchanges WHERE exchange_name = 'bingx'")
        for r in c.fetchall():
            print(f"      - User {r['user_id']} | Strategy: {r['strategy']}")
    else:
        print("\n   ✅ All BingX users already have correct strategy ('ratner').")

    conn.close()
    print("\n✅ Verification Complete.")

if __name__ == "__main__":
    fix_bingx_strategy()
