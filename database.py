# # database.py
# import sqlite3
# from typing import Literal

# DB_NAME = "aladdin_users.db"
# UserStatus = Literal["pending_payment", "active", "expired"]

# def initialize_db():
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS users (
#             user_id INTEGER PRIMARY KEY,
#             status TEXT DEFAULT 'pending_payment'
#         )
#     """)
#     # Таблица для использованных хэшей
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS used_tx_hashes (
#             tx_hash TEXT PRIMARY KEY
#         )
#     """)
#     # Проверяем, существует ли колонка status, и добавляем если нет (для старых баз)
#     try:
#         cursor.execute("SELECT status FROM users LIMIT 1")
#     except sqlite3.OperationalError:
#         cursor.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'pending_payment'")
#     conn.commit()
#     conn.close()

# def add_user(user_id: int):
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
#     cursor.execute("INSERT OR IGNORE INTO users (user_id, status) VALUES (?, 'pending_payment')", (user_id,))
#     conn.commit()
#     conn.close()

# def get_user_status(user_id: int) -> UserStatus | None:
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
#     cursor.execute("SELECT status FROM users WHERE user_id = ?", (user_id,))
#     result = cursor.fetchone()
#     conn.close()
#     return result[0] if result else None

# def activate_user(user_id: int):
#     """Активирует пользователя после успешной оплаты."""
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
#     cursor.execute("UPDATE users SET status = 'active' WHERE user_id = ?", (user_id,))
#     conn.commit()
#     conn.close()
#     print(f"User {user_id} has been activated.")

# def is_tx_hash_used(tx_hash: str) -> bool:
#     """Проверяет, был ли хэш уже использован."""
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
#     cursor.execute("SELECT tx_hash FROM used_tx_hashes WHERE tx_hash = ?", (tx_hash,))
#     result = cursor.fetchone()
#     conn.close()
#     return result is not None

# def mark_tx_hash_as_used(tx_hash: str):
#     """Помечает хэш как использованный."""
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
#     cursor.execute("INSERT OR IGNORE INTO used_tx_hashes (tx_hash) VALUES (?)", (tx_hash,))
#     conn.commit()
#     conn.close()

# initialize_db()

# database.py (v3 - Complete Subscription & Referral System)
# import sqlite3
# from datetime import datetime, timedelta
# from typing import Literal

# DB_NAME = "aladdin_users.db"
# UserStatus = Literal["pending_payment", "active", "expired"]

# def initialize_db():
#     """Initializes the database with the complete schema for subscription and referral system."""
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
    
#     # Create the main users table with all necessary columns
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS users (
#             user_id INTEGER PRIMARY KEY,
#             username TEXT,
#             join_date TEXT,
#             status TEXT DEFAULT 'pending_payment',
#             subscription_expiry TEXT,
#             referrer_id INTEGER,
#             referral_code TEXT UNIQUE,
#             token_balance REAL DEFAULT 0
#         )
#     """)
    
#     # Create the used transaction hashes table
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS used_tx_hashes (
#             tx_hash TEXT PRIMARY KEY
#         )
#     """)
    
#     # Create the withdrawal requests table
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS withdrawals (
#             request_id INTEGER PRIMARY KEY AUTOINCREMENT,
#             user_id INTEGER,
#             amount REAL,
#             wallet_address TEXT,
#             request_date TEXT,
#             status TEXT DEFAULT 'pending'
#         )
#     """)
    
#     # Check and add missing columns to existing tables (for migration)
#     try:
#         cursor.execute("SELECT username FROM users LIMIT 1")
#     except sqlite3.OperationalError:
#         cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
    
#     try:
#         cursor.execute("SELECT join_date FROM users LIMIT 1")
#     except sqlite3.OperationalError:
#         cursor.execute("ALTER TABLE users ADD COLUMN join_date TEXT")
    
#     try:
#         cursor.execute("SELECT subscription_expiry FROM users LIMIT 1")
#     except sqlite3.OperationalError:
#         cursor.execute("ALTER TABLE users ADD COLUMN subscription_expiry TEXT")
    
#     try:
#         cursor.execute("SELECT referrer_id FROM users LIMIT 1")
#     except sqlite3.OperationalError:
#         cursor.execute("ALTER TABLE users ADD COLUMN referrer_id INTEGER")
    
#     try:
#         cursor.execute("SELECT referral_code FROM users LIMIT 1")
#     except sqlite3.OperationalError:
#         cursor.execute("ALTER TABLE users ADD COLUMN referral_code TEXT UNIQUE")
    
#     try:
#         cursor.execute("SELECT token_balance FROM users LIMIT 1")
#     except sqlite3.OperationalError:
#         cursor.execute("ALTER TABLE users ADD COLUMN token_balance REAL DEFAULT 0")
    
#     conn.commit()
#     conn.close()

# def add_user(user_id: int, username: str = None, referrer_id: int = None):
#     """Adds a new user or updates their referrer if they joined via a referral link."""
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
    
#     # Check if user already exists
#     cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
#     exists = cursor.fetchone()

#     if not exists:
#         join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         referral_code = f"ref_{user_id}"  # Simple referral code
#         cursor.execute("""
#             INSERT INTO users (user_id, username, join_date, referrer_id, referral_code, status)
#             VALUES (?, ?, ?, ?, ?, 'pending_payment')
#         """, (user_id, username, join_date, referrer_id, referral_code))
#         print(f"New user {user_id} added with referrer {referrer_id}.")
#     else:
#         # Update referrer if provided and not already set
#         if referrer_id is not None:
#             cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
#             current_referrer = cursor.fetchone()
#             if not current_referrer or current_referrer[0] is None:
#                 cursor.execute("UPDATE users SET referrer_id = ? WHERE user_id = ?", (referrer_id, user_id))
#                 print(f"Updated referrer for user {user_id} to {referrer_id}.")
    
#     conn.commit()
#     conn.close()

# def get_user_status(user_id: int) -> UserStatus | None:
#     """Gets the current status of a user."""
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
#     cursor.execute("SELECT status FROM users WHERE user_id = ?", (user_id,))
#     result = cursor.fetchone()
#     conn.close()
#     return result[0] if result else None

# def activate_user(user_id: int):
#     """Legacy function: Activates user without subscription expiry (for backward compatibility)."""
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
#     cursor.execute("UPDATE users SET status = 'active' WHERE user_id = ?", (user_id,))
#     conn.commit()
#     conn.close()
#     print(f"User {user_id} has been activated.")

# def activate_user_subscription(user_id: int, duration_days: int = 30) -> int | None:
#     """Activates a user's subscription for a set duration and returns their referrer ID."""
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
    
#     expiry_date = (datetime.now() + timedelta(days=duration_days)).strftime("%Y-%m-%d")
    
#     cursor.execute("UPDATE users SET status = 'active', subscription_expiry = ? WHERE user_id = ?", 
#                    (expiry_date, user_id))
    
#     # Get the referrer ID to award tokens
#     cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
#     referrer = cursor.fetchone()
    
#     conn.commit()
#     conn.close()
#     print(f"User {user_id} activated. Subscription expires on {expiry_date}.")
#     return referrer[0] if referrer and referrer[0] else None

# def get_user_by_referral_code(code: str) -> int | None:
#     """Finds a user by their referral code."""
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
#     cursor.execute("SELECT user_id FROM users WHERE referral_code = ?", (code,))
#     result = cursor.fetchone()
#     conn.close()
#     return result[0] if result else None

# def get_user_profile(user_id: int) -> dict | None:
#     """Gets all profile data for a user."""
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
#     cursor.execute("""
#         SELECT join_date, status, subscription_expiry, referral_code, token_balance 
#         FROM users WHERE user_id = ?
#     """, (user_id,))
#     result = cursor.fetchone()
#     conn.close()
    
#     if not result:
#         return None
        
#     return {
#         "join_date": result[0],
#         "status": result[1],
#         "expiry": result[2],
#         "ref_code": result[3],
#         "balance": result[4] or 0.0
#     }

# def credit_referral_tokens(user_id: int, amount: float):
#     """Adds tokens to a user's balance."""
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
#     cursor.execute("UPDATE users SET token_balance = token_balance + ? WHERE user_id = ?", 
#                    (amount, user_id))
#     conn.commit()
#     conn.close()
#     print(f"Credited {amount} tokens to user {user_id}.")

# def get_referrer_chain(user_id: int, levels: int = 3) -> list:
#     """Gets the chain of referrers up to N levels."""
#     chain = []
#     current_id = user_id
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
    
#     for _ in range(levels):
#         cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (current_id,))
#         result = cursor.fetchone()
#         if result and result[0]:
#             chain.append(result[0])
#             current_id = result[0]
#         else:
#             break
            
#     conn.close()
#     return chain

# def create_withdrawal_request(user_id: int, amount: float, wallet: str) -> bool:
#     """Creates a new withdrawal request for the admin."""
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
    
#     # Check balance
#     cursor.execute("SELECT token_balance FROM users WHERE user_id = ?", (user_id,))
#     result = cursor.fetchone()
    
#     if not result or amount > result[0]:
#         conn.close()
#         return False

#     # Deduct from balance and create request
#     cursor.execute("UPDATE users SET token_balance = token_balance - ? WHERE user_id = ?", 
#                    (amount, user_id))
#     cursor.execute("""
#         INSERT INTO withdrawals (user_id, amount, wallet_address, request_date) 
#         VALUES (?, ?, ?, ?)
#     """, (user_id, amount, wallet, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
#     conn.commit()
#     conn.close()
#     return True

# def is_tx_hash_used(tx_hash: str) -> bool:
#     """Checks if a transaction hash has already been used."""
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
#     cursor.execute("SELECT tx_hash FROM used_tx_hashes WHERE tx_hash = ?", (tx_hash,))
#     result = cursor.fetchone()
#     conn.close()
#     return result is not None

# def mark_tx_hash_as_used(tx_hash: str):
#     """Marks a transaction hash as used."""
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
#     cursor.execute("INSERT OR IGNORE INTO used_tx_hashes (tx_hash) VALUES (?)", (tx_hash,))
#     conn.commit()
#     conn.close()

# # Initialize the database when module is imported
# initialize_db()



# database.py (v4 - With Risk Management)
import sqlite3
from datetime import datetime, timedelta
from typing import Literal
import os

# DB_NAME = "aladdin_users.db"
if os.getenv("RENDER"):
    # На сервере Render мы храним базу в постоянной папке 'storage'
    STORAGE_DIR = 'storage'
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)
    DB_NAME = os.path.join(STORAGE_DIR, "aladdin_users.db")
else:
    # Локально мы храним базу в той же папке, что и раньше
    DB_NAME = "aladdin_users.db"
    
UserStatus = Literal["pending_payment", "active", "expired"]

def initialize_db():
    """Initializes the database with the complete schema including risk management."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create the main users table with all necessary columns
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            join_date TEXT,
            status TEXT DEFAULT 'pending_payment',
            subscription_expiry TEXT,
            referrer_id INTEGER,
            referral_code TEXT UNIQUE,
            token_balance REAL DEFAULT 0,
            account_balance REAL DEFAULT 1000.0,
            risk_per_trade_pct REAL DEFAULT 1.0
        )
    """)
    
    # Create the used transaction hashes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS used_tx_hashes (
            tx_hash TEXT PRIMARY KEY
        )
    """)
    
    # Create the withdrawal requests table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            wallet_address TEXT,
            request_date TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    
    # --- Migration Logic for new columns ---
    try:
        cursor.execute("SELECT account_balance FROM users LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE users ADD COLUMN account_balance REAL DEFAULT 1000.0")
    
    try:
        cursor.execute("SELECT risk_per_trade_pct FROM users LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE users ADD COLUMN risk_per_trade_pct REAL DEFAULT 1.0")
    
    # Existing migration logic for other columns
    try:
        cursor.execute("SELECT username FROM users LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
    
    try:
        cursor.execute("SELECT join_date FROM users LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE users ADD COLUMN join_date TEXT")
    
    try:
        cursor.execute("SELECT subscription_expiry FROM users LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE users ADD COLUMN subscription_expiry TEXT")
    
    try:
        cursor.execute("SELECT referrer_id FROM users LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE users ADD COLUMN referrer_id INTEGER")
    
    try:
        cursor.execute("SELECT referral_code FROM users LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE users ADD COLUMN referral_code TEXT UNIQUE")
    
    try:
        cursor.execute("SELECT token_balance FROM users LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE users ADD COLUMN token_balance REAL DEFAULT 0")
    
    conn.commit()
    conn.close()

def add_user(user_id: int, username: str = None, referrer_id: int = None):
    """Adds a new user or updates their referrer if they joined via a referral link."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Check if user already exists
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()

    if not exists:
        join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        referral_code = f"ref_{user_id}"  # Simple referral code
        cursor.execute("""
            INSERT INTO users (user_id, username, join_date, referrer_id, referral_code, status, account_balance, risk_per_trade_pct)
            VALUES (?, ?, ?, ?, ?, 'pending_payment', 1000.0, 1.0)
        """, (user_id, username, join_date, referrer_id, referral_code))
        print(f"New user {user_id} added with referrer {referrer_id}.")
    else:
        # Update referrer if provided and not already set
        if referrer_id is not None:
            cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
            current_referrer = cursor.fetchone()
            if not current_referrer or current_referrer[0] is None:
                cursor.execute("UPDATE users SET referrer_id = ? WHERE user_id = ?", (referrer_id, user_id))
                print(f"Updated referrer for user {user_id} to {referrer_id}.")
    
    conn.commit()
    conn.close()

def get_user_status(user_id: int) -> UserStatus | None:
    """Gets the current status of a user."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def activate_user(user_id: int):
    """Legacy function: Activates user without subscription expiry (for backward compatibility)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = 'active' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    print(f"User {user_id} has been activated.")

def activate_user_subscription(user_id: int, duration_days: int = 30) -> int | None:
    """Activates a user's subscription for a set duration and returns their referrer ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    expiry_date = (datetime.now() + timedelta(days=duration_days)).strftime("%Y-%m-%d")
    
    cursor.execute("UPDATE users SET status = 'active', subscription_expiry = ? WHERE user_id = ?", 
                   (expiry_date, user_id))
    
    # Get the referrer ID to award tokens
    cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    referrer = cursor.fetchone()
    
    conn.commit()
    conn.close()
    print(f"User {user_id} activated. Subscription expires on {expiry_date}.")
    return referrer[0] if referrer and referrer[0] else None

def get_user_by_referral_code(code: str) -> int | None:
    """Finds a user by their referral code."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE referral_code = ?", (code,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_user_profile(user_id: int) -> dict | None:
    """Gets all profile data for a user."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT join_date, status, subscription_expiry, referral_code, token_balance, account_balance, risk_per_trade_pct
        FROM users WHERE user_id = ?
    """, (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return None
        
    return {
        "join_date": result[0],
        "status": result[1],
        "expiry": result[2],
        "ref_code": result[3],
        "balance": result[4] or 0.0,
        "account_balance": result[5] or 1000.0,
        "risk_pct": result[6] or 1.0
    }

def get_user_risk_settings(user_id: int) -> dict:
    """Gets a user's balance and risk percentage."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT account_balance, risk_per_trade_pct FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {"balance": result[0], "risk_pct": result[1]}
    return {"balance": 1000.0, "risk_pct": 1.0} # Default values

def update_user_risk_settings(user_id: int, balance: float, risk_pct: float):
    """Updates a user's risk settings."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET account_balance = ?, risk_per_trade_pct = ? WHERE user_id = ?", 
                   (balance, risk_pct, user_id))
    conn.commit()
    conn.close()
    print(f"Updated risk settings for user {user_id}: Balance=${balance}, Risk={risk_pct}%")

def credit_referral_tokens(user_id: int, amount: float):
    """Adds tokens to a user's balance."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET token_balance = token_balance + ? WHERE user_id = ?", 
                   (amount, user_id))
    conn.commit()
    conn.close()
    print(f"Credited {amount} tokens to user {user_id}.")

def get_referrer_chain(user_id: int, levels: int = 3) -> list:
    """Gets the chain of referrers up to N levels."""
    chain = []
    current_id = user_id
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    for _ in range(levels):
        cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (current_id,))
        result = cursor.fetchone()
        if result and result[0]:
            chain.append(result[0])
            current_id = result[0]
        else:
            break
            
    conn.close()
    return chain

def create_withdrawal_request(user_id: int, amount: float, wallet: str) -> bool:
    """Creates a new withdrawal request for the admin."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Check balance
    cursor.execute("SELECT token_balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if not result or amount > result[0]:
        conn.close()
        return False

    # Deduct from balance and create request
    cursor.execute("UPDATE users SET token_balance = token_balance - ? WHERE user_id = ?", 
                   (amount, user_id))
    cursor.execute("""
        INSERT INTO withdrawals (user_id, amount, wallet_address, request_date) 
        VALUES (?, ?, ?, ?)
    """, (user_id, amount, wallet, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    conn.commit()
    conn.close()
    return True

def is_tx_hash_used(tx_hash: str) -> bool:
    """Checks if a transaction hash has already been used."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT tx_hash FROM used_tx_hashes WHERE tx_hash = ?", (tx_hash,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def mark_tx_hash_as_used(tx_hash: str):
    """Marks a transaction hash as used."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO used_tx_hashes (tx_hash) VALUES (?)", (tx_hash,))
    conn.commit()
    conn.close()

def get_admin_stats():
    """Собирает общую статистику для админ-панели."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    total_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active_users = cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'active'").fetchone()[0]
    pending_payment = cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'pending_payment'").fetchone()[0]
    total_tokens = cursor.execute("SELECT SUM(token_balance) FROM users").fetchone()[0] or 0
    pending_withdrawals_count = cursor.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'").fetchone()[0]
    pending_withdrawals_sum = cursor.execute("SELECT SUM(amount) FROM withdrawals WHERE status = 'pending'").fetchone()[0] or 0
    
    conn.close()
    return {
        "total_users": total_users,
        "active_users": active_users,
        "pending_payment": pending_payment,
        "total_tokens": total_tokens,
        "pending_withdrawals_count": pending_withdrawals_count,
        "pending_withdrawals_sum": pending_withdrawals_sum
    }

def get_active_users_report(limit=20):
    """Возвращает детальный отчет по активным пользователям."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT user_id, username, token_balance FROM users WHERE status = 'active' ORDER BY join_date DESC LIMIT ?", (limit,))
    users = cursor.fetchall()
    
    report = []
    for user in users:
        user_id, username, token_balance = user
        
        # Считаем рефералов для каждого уровня
        l1_count = cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,)).fetchone()[0]
        
        l1_ids = [row[0] for row in cursor.execute("SELECT user_id FROM users WHERE referrer_id = ?", (user_id,)).fetchall()]
        l2_count = 0
        if l1_ids:
            l2_count = cursor.execute(f"SELECT COUNT(*) FROM users WHERE referrer_id IN ({','.join('?' for _ in l1_ids)})", l1_ids).fetchone()[0]

        report.append({
            "user_id": user_id,
            "username": username,
            "balance": token_balance,
            "referrals": {"l1": l1_count, "l2": l2_count} # L3 для краткости опустим в отчете
        })
        
    conn.close()
    return report

def get_pending_withdrawals():
    """Возвращает список всех ожидающих вывода заявок."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT request_id, user_id, amount, wallet_address, request_date FROM withdrawals WHERE status = 'pending' ORDER BY request_id ASC")
    withdrawals = cursor.fetchall()
    conn.close()
    return withdrawals

# Initialize the database when module is imported
initialize_db()
