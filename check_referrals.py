import sqlite3
import os

DB_NAME = "aladdin_dev.db"
USER_ID = 502483421

def check_referrals():
    if not os.path.exists(DB_NAME):
        print(f"❌ Database {DB_NAME} not found!")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        # Check if user exists
        user = cursor.execute("SELECT * FROM users WHERE user_id = ?", (USER_ID,)).fetchone()
        if not user:
            print(f"❌ User {USER_ID} NOT found in database.")
        else:
            print(f"✅ User {USER_ID} found: {user}")

        # Check for referrals
        print(f"\n🔍 checking referrals for {USER_ID}...")
        
        # Leve 1
        l1 = cursor.execute("SELECT user_id, username, join_date FROM users WHERE referred_by = ?", (USER_ID,)).fetchall()
        print(f"Level 1 (Direct): {len(l1)} referrals")
        for r in l1:
            print(f" - {r}")

        if len(l1) > 0:
            # Level 2
            ids_l1 = [u[0] for u in l1]
            placeholders = ','.join('?' for _ in ids_l1)
            l2 = cursor.execute(f"SELECT user_id, username, referred_by FROM users WHERE referred_by IN ({placeholders})", ids_l1).fetchall()
            print(f"Level 2: {len(l2)} referrals")
            for r in l2:
                print(f" - {r}")
        else:
            print("Level 2: 0 referrals (No L1)")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_referrals()
