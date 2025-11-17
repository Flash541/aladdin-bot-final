# # database.py (v6 - With Promocodes and Risk Management)
# import sqlite3
# import uuid
# from datetime import datetime, timedelta
# from typing import Literal
# import os

# # --- ГЛАВНОЕ ИСПРАВЛЕНИЕ ---
# # Render автоматически предоставляет абсолютный путь к диску в переменной RENDER_DISK_PATH
# # Мы будем использовать его. Если его нет (локальный запуск), используем текущую папку.
# RENDER_DISK_PATH = os.getenv("RENDER_DISK_PATH")

# if RENDER_DISK_PATH:
#     # На сервере Render мы храним базу в корне постоянного диска.
#     # Render сам создает эту папку, нам не нужно ее проверять или создавать.
#     DB_NAME = os.path.join(RENDER_DISK_PATH, "aladdin_users.db")
# else:
#     # Локально мы храним базу в той же папке, что и раньше.
#     DB_NAME = "aladdin_users.db"

# print(f"Database path set to: {DB_NAME}") # Добавим лог для отладки

# UserStatus = Literal["pending_payment", "active", "expired"]


# def initialize_db():
#     """Initializes the database with the complete schema including risk management and promo codes."""
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
#             token_balance REAL DEFAULT 0,
#             account_balance REAL DEFAULT 1000.0,
#             risk_per_trade_pct REAL DEFAULT 1.0
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
    
#     # --- НОВАЯ ТАБЛИЦА ДЛЯ ПРОМОКОДОВ ---
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS promo_codes (
#             code TEXT PRIMARY KEY,
#             duration_days INTEGER,
#             is_used INTEGER DEFAULT 0,
#             used_by_user_id INTEGER,
#             activation_date TEXT
#         )
#     """)
    
#     # --- Migration Logic for new columns ---
#     try:
#         cursor.execute("SELECT account_balance FROM users LIMIT 1")
#     except sqlite3.OperationalError:
#         cursor.execute("ALTER TABLE users ADD COLUMN account_balance REAL DEFAULT 1000.0")
    
#     try:
#         cursor.execute("SELECT risk_per_trade_pct FROM users LIMIT 1")
#     except sqlite3.OperationalError:
#         cursor.execute("ALTER TABLE users ADD COLUMN risk_per_trade_pct REAL DEFAULT 1.0")
    
#     # Existing migration logic for other columns
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
#     try:
#         cursor.execute("SELECT duration_days FROM promo_codes LIMIT 1")
#     except sqlite3.OperationalError:
#         cursor.execute("ALTER TABLE promo_codes ADD COLUMN duration_days INTEGER DEFAULT 30")

#     conn.commit()
#     conn.close()


# database.py (v-FINAL - Correct Path & Clean Init)
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Literal
import os

# --- ПРАВИЛЬНЫЙ ПУТЬ К ДИСКУ RENDER ---
RENDER_DISK_PATH = os.getenv("RENDER_DISK_PATH")
if RENDER_DISK_PATH:
    DB_NAME = os.path.join(RENDER_DISK_PATH, "aladdin_users.db")
else:
    DB_NAME = "aladdin_users.db"
print(f"Database path set to: {DB_NAME}")

UserStatus = Literal["pending_payment", "active", "expired"]

# --- ЧИСТАЯ И НАДЕЖНАЯ ФУНКЦИЯ ИНИЦИАЛИЗАЦИИ ---
def initialize_db():
    """Создает все таблицы с правильной структурой, если их еще не существует."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблица пользователей со всеми колонками
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
    
    # Таблица использованных хэшей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS used_tx_hashes (
            tx_hash TEXT PRIMARY KEY
        )
    """)
    
    # Таблица заявок на вывод
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
    
    # Таблица промокодов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT PRIMARY KEY,
            duration_days INTEGER,
            is_used INTEGER DEFAULT 0,
            used_by_user_id INTEGER,
            activation_date TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    print("Database initialized successfully with all tables.")

def generate_promo_codes(count: int, duration_days: int) -> list[str]:
    """Генерирует N промокодов с указанным сроком действия."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    new_codes = []
    for _ in range(count):
        code = f"ALADDIN-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:4].upper()}"
        cursor.execute("INSERT OR IGNORE INTO promo_codes (code, duration_days) VALUES (?, ?)", (code, duration_days))
        new_codes.append(code)
    conn.commit()
    conn.close()
    return new_codes

def validate_and_use_promo_code(code: str, user_id: int) -> int | None:
    """Проверяет промокод. Если валидный, помечает как использованный и возвращает срок действия в днях."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT duration_days FROM promo_codes WHERE code = ? AND is_used = 0", (code.upper(),))
    result = cursor.fetchone()
    
    if not result:
        conn.close(); return None # Код не найден или уже использован
        
    duration = result[0]
    activation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE promo_codes SET is_used = 1, used_by_user_id = ?, activation_date = ? WHERE code = ?", (user_id, activation_date, code.upper()))
    conn.commit()
    conn.close()
    return duration

def check_and_expire_subscriptions():
    """Находит и деактивирует всех пользователей с истекшей подпиской."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Находим всех, у кого статус 'active' и дата истечения прошла
    cursor.execute("SELECT user_id FROM users WHERE status = 'active' AND subscription_expiry < ?", (today_str,))
    expired_users = [row[0] for row in cursor.fetchall()]
    
    if expired_users:
        # Обновляем их статус на 'expired'
        cursor.executemany("UPDATE users SET status = 'expired' WHERE user_id = ?", [(user_id,) for user_id in expired_users])
        conn.commit()
        print(f"Expired subscriptions for users: {expired_users}")
        
    conn.close()
    return expired_users # Возвращаем список, чтобы бот мог отправить им уведомления

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

def get_referrer(user_id: int) -> int | None:
    """Gets the direct referrer (level 1) for a user."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] else None

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
    
    # Статистика по промокодам
    total_promo_codes = cursor.execute("SELECT COUNT(*) FROM promo_codes").fetchone()[0]
    used_promo_codes = cursor.execute("SELECT COUNT(*) FROM promo_codes WHERE is_used = 1").fetchone()[0]
    available_promo_codes = total_promo_codes - used_promo_codes
    
    conn.close()
    return {
        "total_users": total_users,
        "active_users": active_users,
        "pending_payment": pending_payment,
        "total_tokens": total_tokens,
        "pending_withdrawals_count": pending_withdrawals_count,
        "pending_withdrawals_sum": pending_withdrawals_sum,
        "total_promo_codes": total_promo_codes,
        "used_promo_codes": used_promo_codes,
        "available_promo_codes": available_promo_codes
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
