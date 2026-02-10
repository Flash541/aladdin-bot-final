
import sqlite3

try:
    conn = sqlite3.connect('aladdin_dev.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM master_orders ORDER BY order_id DESC LIMIT 10")
    rows = cursor.fetchall()
    
    if not rows:
        print("master_orders table is empty.")
    else:
        for row in rows:
            print(row)
    conn.close()
except Exception as e:
    print(f"Error: {e}")
