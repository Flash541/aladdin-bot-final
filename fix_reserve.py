
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

# IMPORTANT: reserved_amount = money that is NOT touched (savings)
# If user has $1000 and sets reserve to $200, they trade with $800
# Setting to 200 as a reasonable default
new_reserve = 200.0

try:
    # 1. Update User Exchange Reserve
    print(f"🔄 Updating OKX Reserve (untouchable amount) for user {user_id} to ${new_reserve}...")
    c.execute("""
        UPDATE user_exchanges 
        SET reserved_amount = ? 
        WHERE user_id = ? AND exchange_name = 'okx'
    """, (new_reserve, user_id))
    
    if c.rowcount > 0:
        print("✅ Success! Reserve updated.")
    else:
        print("⚠️ User/Exchange not found in DB.")

    # 2. Verify Result
    c.execute("SELECT reserved_amount FROM user_exchanges WHERE user_id=? AND exchange_name='okx'", (user_id,))
    row = c.fetchone()
    if row:
        print(f"🔍 Current OKX Reserve (untouchable): ${row[0]}")
        print(f"💡 This means: Trading Capital = Your OKX Balance - ${row[0]}")
    
    conn.commit()

except Exception as e:
    print(f"❌ Error: {e}")
finally:
    conn.close()
