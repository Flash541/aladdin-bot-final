
import sqlite3
import os

# Try to find the DB
db_files = ['aladdin_users.db', 'aladdin_dev.db']
db_path = next((f for f in db_files if os.path.exists(f)), None)

if not db_path:
    print("❌ No database file found!")
    exit()

print(f"✅ Connecting to database: {db_path}")
conn = sqlite3.connect(db_path)
c = conn.cursor()

user_id = 1778819795
new_reserve = 2000.0  # Set to a reasonable default based on 4 coins x 500

try:
    # 1. Update User Exchange Reserve
    print(f"🔄 Updating OKX Reserve for user {user_id} to {new_reserve} USDT...")
    c.execute("""
        UPDATE user_exchanges 
        SET reserved_amount = ? 
        WHERE user_id = ? AND exchange_name = 'okx'
    """, (new_reserve, user_id))
    
    if c.rowcount > 0:
        print("✅ Success! Global Reserve updated.")
    else:
        print("⚠️ User/Exchange not found in DB.")

    # 2. Verify Result
    c.execute("SELECT reserved_amount FROM user_exchanges WHERE user_id=? AND exchange_name='okx'", (user_id,))
    row = c.fetchone()
    if row:
        print(f"🔍 Current OKX Global Reserve in DB: {row[0]}")
    
    conn.commit()

except Exception as e:
    print(f"❌ Error: {e}")
finally:
    conn.close()
