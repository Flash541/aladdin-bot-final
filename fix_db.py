
import sqlite3
import os

db_path = 'aladdin_dev.db'

if not os.path.exists(db_path):
    print(f"❌ Database {db_path} not found!")
    exit()

print(f"✅ Connecting to database: {db_path}")
conn = sqlite3.connect(db_path)
c = conn.cursor()

try:
    print("🔄 Ensuring table 'master_positions' exists...")
    c.execute("""
        CREATE TABLE IF NOT EXISTS master_positions (
            symbol TEXT NOT NULL,
            strategy TEXT NOT NULL,
            net_quantity REAL DEFAULT 0.0,
            updated_at TEXT,
            PRIMARY KEY (symbol, strategy)
        )
    """)
    print("✅ Table 'master_positions' checked/created.")
    
    # Optional: Clear it if we want a fresh start, but better to keep if manual
    # c.execute("DELETE FROM master_positions")

    conn.commit()
    print("🚀 Database Update Complete.")

except Exception as e:
    print(f"❌ Error: {e}")
finally:
    conn.close()
