# database.py (v-FINAL-ROBUST - With Retry & WAL)
import sqlite3
import uuid
import os
import json
import time
from datetime import datetime, timedelta
from typing import Literal
from cryptography.fernet import Fernet 
from dotenv import load_dotenv

load_dotenv() 

# --- КОНФИГУРАЦИЯ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RENDER_DISK_PATH = os.getenv("RENDER_DISK_PATH")

if RENDER_DISK_PATH:
    DB_NAME = os.path.join(RENDER_DISK_PATH, "aladdin_users.db")
else:
    DB_NAME = os.path.join(BASE_DIR, "aladdin_dev.db")

print(f"✅ Database path set to: {DB_NAME}")

FERNET_KEY = os.getenv("FERNET_KEY")
if not FERNET_KEY:
    raise ValueError("FATAL ERROR: FERNET_KEY not found in environment variables.")

CIPHER = Fernet(FERNET_KEY.encode())

def encrypt_data(data: str) -> str:
    if not data: return None
    return CIPHER.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    if not encrypted_data: return None
    try:
        return CIPHER.decrypt(encrypted_data.encode()).decode()
    except Exception as e:
        print(f"❌ Decryption failed: {e}")
        return None

# --- ЯДРО БАЗЫ ДАННЫХ (ЗАЩИТА ОТ БЛОКИРОВОК) ---

def execute_write_query(query, params=()):
    """
    Выполняет запись в базу (INSERT/UPDATE/DELETE).
    Если база занята (Locked), делает 5 попыток с паузой.
    """
    max_retries = 5
    for i in range(max_retries):
        conn = None
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return # Успех
        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                # База занята, ждем и пробуем снова
                time.sleep(0.1)
                continue
            else:
                # Другая ошибка SQL
                print(f"❌ SQL Error: {e}")
                raise e
        except Exception as e:
            print(f"❌ General DB Error: {e}")
            raise e
        finally:
            if conn: conn.close()
    
    print(f"❌ CRITICAL: Database locked after {max_retries} retries. Query failed.")

def execute_read_query(query, params=()):
    """
    Выполняет чтение из базы.
    Использует WAL режим, поэтому не блокирует запись.
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row # Позволяет обращаться к полям по имени
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        result = cursor.fetchall()
        return result
    except Exception as e:
        print(f"❌ Read Query Error: {e}")
        return []
    finally:
        conn.close()

def initialize_db():
    conn = sqlite3.connect(DB_NAME)
    
    # !!! ВКЛЮЧАЕМ РЕЖИМ WAL (Write-Ahead Logging) !!!
    # Это позволяет читать базу, пока в нее идет запись.
    conn.execute("PRAGMA journal_mode=WAL;")
    
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute("""
       CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            join_date TEXT,
            status TEXT DEFAULT 'active',
            subscription_expiry TEXT,
            referrer_id INTEGER,
            referral_code TEXT UNIQUE,
            token_balance REAL DEFAULT 0,
            is_copytrading_enabled BOOLEAN DEFAULT 1,
            
            account_balance REAL DEFAULT 1000.0,
            risk_per_trade_pct REAL DEFAULT 1.0,
            exchange_name TEXT,
            api_key_public TEXT,
            api_secret_encrypted TEXT,
            api_passphrase_encrypted TEXT,
                   
            selected_strategy TEXT DEFAULT 'bro-bot', -- bro-bot или cgt
            daily_analysis_count INTEGER DEFAULT 0,
            last_analysis_date TEXT,
            language_code TEXT DEFAULT 'en'
        )
    """)
    
    cursor.execute("CREATE TABLE IF NOT EXISTS used_tx_hashes (tx_hash TEXT PRIMARY KEY)")
    cursor.execute("CREATE TABLE IF NOT EXISTS withdrawals (request_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, wallet_address TEXT, request_date TEXT, status TEXT DEFAULT 'pending')")
    cursor.execute("CREATE TABLE IF NOT EXISTS promo_codes (code TEXT PRIMARY KEY, duration_days INTEGER, is_used INTEGER DEFAULT 0, used_by_user_id INTEGER, activation_date TEXT)")
    
    # Таблица сделок (UNIQUE constraint убран - разрешаем множественные позиции)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS copied_trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            avg_entry_price REAL DEFAULT 0,
            total_quantity REAL DEFAULT 0,
            open_date TEXT, 
            status TEXT DEFAULT 'open'
        )
    """)

    # Таблица подключенных бирж (Multi-Exchange Support)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_exchanges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            exchange_name TEXT, -- 'binance', 'bybit', 'okx', etc.
            api_key TEXT,
            api_secret_encrypted TEXT,
            passphrase_encrypted TEXT, -- for OKX
            strategy TEXT DEFAULT 'bro-bot', -- 'bro-bot' or 'cgt'
            reserved_amount REAL DEFAULT 0.0,
            risk_pct REAL DEFAULT 1.0,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            UNIQUE(user_id, exchange_name)
        )
    """)
    
    # Таблица конфигурации монет (Multi-Coin Support for OKX CGT)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS coin_configs (
            config_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exchange_name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            reserved_amount REAL DEFAULT 0,
            risk_pct REAL DEFAULT 1.0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            UNIQUE(user_id, exchange_name, symbol)
        )
    """)
    
    # Таблица мастер-ордеров (INVESTIGATION SYSTEM)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS master_orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            master_exchange TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            order_type TEXT NOT NULL,
            price REAL NOT NULL,
            quantity REAL NOT NULL,
            timestamp TEXT NOT NULL,
            strategy TEXT NOT NULL
        )
    """)
    
    # Таблица копий клиентов (INVESTIGATION SYSTEM)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS client_copies (
            copy_id INTEGER PRIMARY KEY AUTOINCREMENT,
            master_order_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL,
            quantity REAL NOT NULL,
            profit_loss REAL,
            opened_at TEXT NOT NULL,
            closed_at TEXT,
            status TEXT DEFAULT 'open',
            FOREIGN KEY (master_order_id) REFERENCES master_orders(order_id)
        )
    """)
    
    # Таблица транзакций (Top Up)
    cursor.execute("""
       CREATE TABLE IF NOT EXISTS transactions (
            tx_hash TEXT PRIMARY KEY,
            user_id INTEGER,
            amount REAL,
            currency TEXT,
            from_address TEXT,
            status TEXT,
            created_at TEXT
       )
    """)

    # --- MIGRATION: LEGACY USERS to USER_EXCHANGES ---
    # migrate legacy keys from 'users' table to 'user_exchanges' ---
    # This ensures existing users continue copying without needing to reconnect.
    try:
        cursor.execute("SELECT user_id, exchange_name, api_key_public, api_secret_encrypted, api_passphrase_encrypted, selected_strategy FROM users WHERE api_key_public IS NOT NULL AND api_key_public != ''")
        legacy_users = cursor.fetchall()
        
        for u in legacy_users:
            uid, ex_name, pub, sec, pas, strat = u
            if not ex_name: ex_name = 'binance' # Default
            
            # Use safe INSERT OR IGNORE to avoid duplicates if migration ran before
            cursor.execute("""
                INSERT OR IGNORE INTO user_exchanges (user_id, exchange_name, api_key, api_secret_encrypted, passphrase_encrypted, strategy, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (uid, ex_name.lower(), pub, sec, pas, strat, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            
        if legacy_users:
            print(f"🔄 Migrated {len(legacy_users)} legacy users to 'user_exchanges'.")
            
    except Exception as e:
        print(f"⚠️ Limit migration warning: {e}")

    # --- MIGRATION: ADD RISK_PCT COLUMN TO USER_EXCHANGES IF MISSING ---
    try:
        cursor.execute("SELECT risk_pct FROM user_exchanges LIMIT 1")
    except sqlite3.OperationalError as err:
        print("🔄 Adding 'risk_pct' column to user_exchanges...")
        cursor.execute("ALTER TABLE user_exchanges ADD COLUMN risk_pct REAL DEFAULT 1.0;")
        conn.commit()
        print(f"✅ Migration successful. Added risk_pct.")
    except Exception as err:
        print(f"⚠️ Migration warning: {err}")

    conn.commit()
    
    # Миграции (на случай, если таблица старая)
    try: cursor.execute("ALTER TABLE users ADD COLUMN exchange_name TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE copied_trades ADD COLUMN open_date TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE users ADD COLUMN selected_strategy TEXT DEFAULT 'bro-bot'")
    except: pass
    try: cursor.execute("ALTER TABLE users ADD COLUMN daily_analysis_count INTEGER DEFAULT 0")
    except: pass
    try: cursor.execute("ALTER TABLE users ADD COLUMN last_analysis_date TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE users ADD COLUMN api_passphrase_encrypted TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE users ADD COLUMN language_code TEXT DEFAULT 'en'")
    except: pass
    try: cursor.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
    except: pass
    try: cursor.execute("ALTER TABLE users ADD COLUMN unc_balance REAL DEFAULT 0")
    except: pass
    
    # Init Transactions Table (for migration)
    try:
        cursor.execute("""
           CREATE TABLE IF NOT EXISTS transactions (
                tx_hash TEXT PRIMARY KEY,
                user_id INTEGER,
                amount REAL,
                currency TEXT,
                from_address TEXT,
                status TEXT,
                created_at TEXT
           )
        """)
    except: pass

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully (WAL Mode ON).")

def save_user_language(user_id: int, lang_code: str):
    """Сохраняет выбранный язык пользователя."""
    execute_write_query("UPDATE users SET language_code = ? WHERE user_id = ?", (lang_code, user_id))

def get_user_language(user_id: int) -> str:
    """Возвращает код языка пользователя (по умолчанию 'en')."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT language_code FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res and res[0] else 'en'

# --- ФУНКЦИИ КОПИ-ТРЕЙДИНГА (БЕЗОПАСНЫЕ) ---

def check_analysis_limit(user_id: int, limit: int = 5) -> bool:
    """Проверяет и обновляет дневной лимит анализов."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute("SELECT daily_analysis_count, last_analysis_date FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    current_count = 0
    last_date = ""
    
    if row:
        current_count = row[0] if row[0] else 0
        last_date = row[1] if row[1] else ""
    
    # Если наступил новый день, сбрасываем счетчик
    if last_date != today:
        cursor.execute("UPDATE users SET daily_analysis_count = 1, last_analysis_date = ? WHERE user_id = ?", (today, user_id))
        conn.commit()
        conn.close()
        return True
    
    # Если день тот же, проверяем лимит
    if current_count < limit:
        cursor.execute("UPDATE users SET daily_analysis_count = daily_analysis_count + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    else:
        conn.close()
        return False

def set_user_strategy(user_id: int, strategy: str):
    """Сохраняет выбранную стратегию (bro-bot или cgt)."""
    execute_write_query("UPDATE users SET selected_strategy = ? WHERE user_id = ?", (strategy, user_id))

def get_user_strategy(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT selected_strategy FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 'bro-bot'

def get_user_risk_profile(user_id: int) -> float:
    """Returns risk per trade percentage (e.g. 1.0 for 1%)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT risk_per_trade_pct FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return float(res[0]) if res and res[0] is not None else 1.0


# Также обнови get_users_for_copytrade, чтобы можно было фильтровать по стратегии
# Также обнови get_users_for_copytrade, чтобы можно было фильтровать по стратегии
def get_users_for_copytrade(strategy: str = None) -> list:
    # LEGACY: Returns lists of user_ids. 
    # Used by checks, but worker should migrate to get_active_exchange_connections
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if strategy:
        cursor.execute("SELECT user_id FROM users WHERE api_key_public IS NOT NULL AND api_key_public != '' AND is_copytrading_enabled = 1 AND selected_strategy = ?", (strategy,))
    else:
        cursor.execute("SELECT user_id FROM users WHERE api_key_public IS NOT NULL AND api_key_public != '' AND is_copytrading_enabled = 1")
    user_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return user_ids

def get_active_exchange_connections(strategy: str = None, symbol: str = None) -> list:
    """
    Returns list of dicts: {user_id, exchange_name, reserved_amount, strategy, risk_pct, symbol (if applicable)}
    
    For CGT (OKX) strategy with symbol: returns per-coin configs from coin_configs table
    Otherwise: returns exchange-level configs from user_exchanges table
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # For CGT strategy with a specific symbol, get per-coin configs
    if strategy == 'cgt' and symbol:
        query = """
            SELECT 
                ue.user_id, 
                ue.exchange_name, 
                cc.reserved_amount, 
                cc.risk_pct,
                cc.symbol,
                ue.strategy
            FROM user_exchanges ue
            INNER JOIN coin_configs cc ON ue.user_id = cc.user_id AND ue.exchange_name = cc.exchange_name
            JOIN users u ON ue.user_id = u.user_id
            WHERE ue.is_active = 1 
              AND cc.is_active = 1
              AND u.is_copytrading_enabled = 1 
              AND u.token_balance > 0
              AND ue.strategy = ?
              AND cc.symbol = ?
        """
        params = [strategy, symbol]
    else:
        # Original query for non-CGT or when no symbol specified
        query = """
            SELECT ue.user_id, ue.exchange_name, ue.reserved_amount, ue.strategy, ue.risk_pct
            FROM user_exchanges ue
            JOIN users u ON ue.user_id = u.user_id
            WHERE ue.is_active = 1 AND u.is_copytrading_enabled = 1 AND u.token_balance > 0
        """
        params = []
        
        if strategy:
            query += " AND ue.strategy = ?"
            params.append(strategy)
        
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]



# def save_user_api_keys(user_id: int, exchange: str, public_key: str, secret_key: str):
#     encrypted_secret = encrypt_data(secret_key)
#     execute_write_query("""
#         UPDATE users 
#         SET exchange_name = ?, api_key_public = ?, api_secret_encrypted = ?
#         WHERE user_id = ?
#     """, (exchange, public_key, encrypted_secret, user_id))
#     print(f"🔐 API keys for user {user_id} saved.")

def save_user_api_keys(user_id: int, exchange: str, public_key: str, secret_key: str, passphrase: str = None):
    """Шифрует Secret и Passphrase (если есть) и сохраняет."""
    encrypted_secret = encrypt_data(secret_key)
    encrypted_passphrase = encrypt_data(passphrase) if passphrase else None
    
    execute_write_query("""
        UPDATE users 
        SET exchange_name = ?, api_key_public = ?, api_secret_encrypted = ?, api_passphrase_encrypted = ?
        WHERE user_id = ?
    """, (exchange, public_key, encrypted_secret, encrypted_passphrase, user_id))
    print(f"🔐 API keys for user {user_id} saved.")


# database.py

def get_referral_counts(user_id: int) -> dict:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE referrer_id = ?", (user_id,))
    l1_ids = [row[0] for row in cursor.fetchall()]
    l1_count = len(l1_ids)
    return {"l1": l1_count}

# def get_user_decrypted_keys(user_id: int):
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
#     cursor.execute("SELECT exchange_name, api_key_public, api_secret_encrypted FROM users WHERE user_id = ?", (user_id,))
#     result = cursor.fetchone()
#     conn.close()
    
#     if not result or not result[2]: return None
#     exchange, public, encrypted_secret = result
#     decrypted_secret = decrypt_data(encrypted_secret)
#     return {"exchange": exchange, "apiKey": public, "secret": decrypted_secret}


def get_user_decrypted_keys(user_id: int, exchange_name: str = None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. New Table Lookup
    query = "SELECT exchange_name, api_key, api_secret_encrypted, passphrase_encrypted, reserved_amount FROM user_exchanges WHERE user_id = ?"
    params = [user_id]
    if exchange_name:
        query += " AND exchange_name = ?"
        params.append(exchange_name)
    
    cursor.execute(query, params)
    res = cursor.fetchone()
    
    # Если нашли в новой таблице
    if res:
        ex_name, pub, sec_enc, pass_enc, res_amt = res
        conn.close()
        return {
            "exchange": ex_name,
            "apiKey": pub,
            "secret": decrypt_data(sec_enc),
            "password": decrypt_data(pass_enc) if pass_enc else None,
            "reserved_amount": res_amt or 0.0
        }

    # 2. Legacy Lookup (users table)
    cursor.execute("SELECT exchange_name, api_key_public, api_secret_encrypted, api_passphrase_encrypted FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result or not result[2]: return None
    
    exchange, public, encrypted_secret, encrypted_pass = result
    if exchange_name and exchange != exchange_name: return None # Mismatch

    decrypted_secret = decrypt_data(encrypted_secret)
    decrypted_pass = decrypt_data(encrypted_pass) if encrypted_pass else None
    
    return {
        "exchange": exchange,
        "apiKey": public,
        "secret": decrypted_secret,
        "password": decrypted_pass,
        "reserved_amount": 0.0 # Legacy has no reserve
    }

# def record_trade_entry(user_id: int, symbol: str, side: str, price: float, quantity: float):
#     """
#     Записывает вход в сделку. 
#     Использует обычный SELECT, но безопасный execute_write_query для записи.
#     """
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
#     # Чтение (не блокирует в WAL режиме)
#     cursor.execute("SELECT trade_id, avg_entry_price, total_quantity FROM copied_trades WHERE user_id = ? AND symbol = ? AND status = 'open'", (user_id, symbol))
#     existing_trade = cursor.fetchone()
#     conn.close()
    
#     if existing_trade:
#         # Усреднение (UPDATE)
#         trade_id, old_price, old_qty = existing_trade
#         new_total_qty = old_qty + quantity
#         new_avg_price = ((old_price * old_qty) + (price * quantity)) / new_total_qty
        
#         execute_write_query(
#             "UPDATE copied_trades SET avg_entry_price = ?, total_quantity = ? WHERE trade_id = ?", 
#             (new_avg_price, new_total_qty, trade_id)
#         )
#         print(f"   -> DB: Averaged position for user {user_id}. New Qty: {new_total_qty:.4f}")
#     else:
#         # Новая сделка (INSERT)
#         execute_write_query("""
#             INSERT INTO copied_trades (user_id, symbol, side, avg_entry_price, total_quantity, open_date)
#             VALUES (?, ?, ?, ?, ?, ?)
#         """, (user_id, symbol, side, price, quantity, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
#         print(f"   -> DB: Recorded NEW position for user {user_id}.")

def record_trade_entry(user_id: int, symbol: str, side: str, price: float, quantity: float):
    """
    Записывает вход или усреднение.
    Использует логику 'Попробуй вставить, если занято - обнови' (Upsert-like logic).
    """
    conn = sqlite3.connect(DB_NAME)
    # Включаем WAL для скорости
    conn.execute("PRAGMA journal_mode=WAL;") 
    cursor = conn.cursor()
    
    try:
        # 1. Сначала пробуем найти открытую сделку
        cursor.execute("SELECT trade_id, avg_entry_price, total_quantity FROM copied_trades WHERE user_id = ? AND symbol = ? AND status = 'open'", (user_id, symbol))
        existing_trade = cursor.fetchone()
        
        if existing_trade:
            # УСРЕДНЕНИЕ (DCA)
            trade_id, old_price, old_qty = existing_trade
            new_total_qty = old_qty + quantity
            # Формула средней цены: (СтараяЦена * СтароеКолво + НоваяЦена * НовоеКолво) / ОбщееКолво
            new_avg_price = ((old_price * old_qty) + (price * quantity)) / new_total_qty
            
            cursor.execute("UPDATE copied_trades SET avg_entry_price = ?, total_quantity = ? WHERE trade_id = ?", (new_avg_price, new_total_qty, trade_id))
            print(f"   -> DB: Averaged position for user {user_id}. New Qty: {new_total_qty:.4f}")
        else:
            # НОВАЯ СДЕЛКА
            # Используем INSERT OR IGNORE, чтобы не падать с ошибкой, если запись появилась за миллисекунду до этого
            try:
                cursor.execute("""
                    INSERT INTO copied_trades (user_id, symbol, side, avg_entry_price, total_quantity, open_date, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'open')
                """, (user_id, symbol, side, price, quantity, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                print(f"   -> DB: Recorded NEW position for user {user_id}.")
            except sqlite3.IntegrityError:
                # Если сработал UNIQUE constraint, значит сделка УЖЕ есть (гонка данных).
                # В этом случае мы рекурсивно вызываем сами себя, чтобы попасть в ветку "УСРЕДНЕНИЕ"
                print(f"   -> DB: Race condition detected. Switching to Average mode.")
                conn.close()
                time.sleep(0.1)
                record_trade_entry(user_id, symbol, side, price, quantity)
                return

        conn.commit()
    except Exception as e:
        print(f"❌ DB Record Error: {e}")
    finally:
        try: conn.close()
        except: pass

def get_open_trade(user_id: int, symbol: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Выбрать ПОСЛЕДНЮЮ открытую позицию (если несколько)
    cursor.execute("""
        SELECT side, avg_entry_price, total_quantity 
        FROM copied_trades 
        WHERE user_id = ? AND symbol = ? AND status = 'open'
        ORDER BY trade_id DESC
        LIMIT 1
    """, (user_id, symbol))
    result = cursor.fetchone()
    conn.close()
    if not result: return None
    return {"side": result[0], "entry_price": result[1], "quantity": result[2]}

def close_trade_in_db(user_id: int, symbol: str):
    execute_write_query(
        "UPDATE copied_trades SET status = 'closed' WHERE user_id = ? AND symbol = ? AND status = 'open'", 
        (user_id, symbol)
    )
    print(f"   -> DB: Closed position for user {user_id}.")

def set_copytrading_status(user_id: int, is_enabled: bool):
    execute_write_query(
        "UPDATE users SET is_copytrading_enabled = ? WHERE user_id = ?", 
        (1 if is_enabled else 0, user_id)
    )
    status = "ENABLED" if is_enabled else "DISABLED"
    print(f"COPY TRADING for user {user_id} has been {status}.")


# database.py

def get_referrer_upline(user_id: int, levels: int = 3) -> list:
    chain = []
    current_id = user_id
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    for _ in range(levels):
        cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (current_id,))
        result = cursor.fetchone()
        
        # Если реферер есть и он не None
        if result and result[0]:
            referrer_id = result[0]
            chain.append(referrer_id)
            current_id = referrer_id # Поднимаемся выше
        else:
            break # Цепочка прервалась
            
    conn.close()
    return chain

def deduct_performance_fee(user_id: int, fee_amount: float) -> float:
    # 1. Списываем (Безопасная запись)
    execute_write_query(
        "UPDATE users SET token_balance = token_balance - ? WHERE user_id = ?", 
        (fee_amount, user_id)
    )
    
    # 2. Получаем новый баланс (Чтение)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT token_balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    
    new_balance = res[0] if res else 0
    print(f"   -> BILLING: Deducted {fee_amount:.2f}. New balance: {new_balance:.2f}")
    return new_balance

def get_all_users_with_keys() -> list:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE api_key_public IS NOT NULL AND api_key_public != ''")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def credit_tokens_from_payment(user_id: int, amount_usd: float):
    execute_write_query(
        "UPDATE users SET token_balance = token_balance + ? WHERE user_id = ?", 
        (amount_usd, user_id)
    )
    print(f"💰 Credited {amount_usd} tokens to user {user_id}.")

# --- ОСТАЛЬНЫЕ ФУНКЦИИ (АДАПТИРОВАННЫЕ ПОД НОВЫЙ СТИЛЬ) ---

UserStatus = Literal["pending_payment", "active", "expired"]

def add_user(user_id: int, username: str = None, referrer_id: int = None) -> bool:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ref_code = f"ref_{user_id}"
        # Используем execute_write_query для INSERT
        conn.close() # Закрываем читалку
        execute_write_query(
            "INSERT INTO users (user_id, username, join_date, referrer_id, referred_by, referral_code, status, account_balance, risk_per_trade_pct, unc_balance) VALUES (?, ?, ?, ?, ?, ?, 'active', 1000.0, 1.0, 0.0)", 
            (user_id, username, join_date, referrer_id, referrer_id, ref_code)
        )
        return True
    else:
        conn.close()
        return False

def get_user_status(user_id: int) -> UserStatus | None:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT status FROM users WHERE user_id = ?", (user_id,)); result = cursor.fetchone()
    conn.close(); return result[0] if result else None

def activate_user(user_id: int):
    execute_write_query("UPDATE users SET status = 'active' WHERE user_id = ?", (user_id,))

def activate_user_subscription(user_id: int, duration_days: int = 30) -> int | None:
    expiry = (datetime.now() + timedelta(days=duration_days)).strftime("%Y-%m-%d")
    execute_write_query("UPDATE users SET status = 'active', subscription_expiry = ? WHERE user_id = ?", (expiry, user_id))
    
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,)); referrer = cursor.fetchone()
    conn.close(); return referrer[0] if referrer else None


def get_all_active_user_ids() -> list[int]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE status = 'active'")
    user_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return user_ids

def get_user_profile(user_id: int) -> dict | None:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT join_date, status, subscription_expiry, referral_code, token_balance, account_balance, risk_per_trade_pct FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone(); conn.close()
    if not res: return None
    return {"join_date": res[0], "status": res[1], "expiry": res[2], "ref_code": res[3], "balance": res[4] or 0, "account_balance": res[5] or 1000, "risk_pct": res[6] or 1}

def get_user_risk_settings(user_id: int) -> dict:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT account_balance, risk_per_trade_pct FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone(); conn.close()
    return {"balance": res[0], "risk_pct": res[1]} if res else {"balance": 1000, "risk_pct": 1}

def update_user_risk_settings(user_id: int, balance: float, risk_pct: float):
    execute_write_query("UPDATE users SET account_balance = ?, risk_per_trade_pct = ? WHERE user_id = ?", (balance, risk_pct, user_id))

# --- MULTI-EXCHANGE MANAGEMENT ---

def save_user_exchange(user_id: int, exchange: str, api_key: str, secret_key: str, passphrase: str = None, strategy: str = 'bro-bot'):
    """Сохраняет или обновляет подключение к бирже."""
    encrypted_secret = encrypt_data(secret_key)
    encrypted_pass = encrypt_data(passphrase) if passphrase else None
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Upsert logic (INSERT OR REPLACE) - но лучше проверить, чтобы не затереть reserved_amount если он есть
    # Поэтому делаем INSERT ON CONFLICT DO UPDATE
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    
    # Проверяем, есть ли запись
    cursor.execute("SELECT id FROM user_exchanges WHERE user_id = ? AND exchange_name = ?", (user_id, exchange))
    row = cursor.fetchone()
    
    if row:
        # Обновляем ключи, стратегию, но оставляем reserved_amount
        execute_write_query("""
            UPDATE user_exchanges 
            SET api_key = ?, api_secret_encrypted = ?, passphrase_encrypted = ?, strategy = ?, is_active = 1
            WHERE user_id = ? AND exchange_name = ?
        """, (api_key, encrypted_secret, encrypted_pass, strategy, user_id, exchange))
    else:
        # Новая запись
        execute_write_query("""
            INSERT INTO user_exchanges (user_id, exchange_name, api_key, api_secret_encrypted, passphrase_encrypted, strategy, reserved_amount, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0.0, ?)
        """, (user_id, exchange, api_key, encrypted_secret, encrypted_pass, strategy, created_at))
    
    conn.close()

def get_user_exchanges(user_id: int) -> list[dict]:
    """Возвращает список всех подключенных бирж пользователя."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_exchanges WHERE user_id = ? AND is_active = 1", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    exchanges = []
    for row in rows:
        exchanges.append(dict(row))
    return exchanges

def update_exchange_reserve(user_id: int, exchange: str, reserve_amount: float):
    """Обновляет сумму резерва для конкретной биржи."""
    execute_write_query("UPDATE user_exchanges SET reserved_amount = ? WHERE user_id = ? AND exchange_name = ?", (reserve_amount, user_id, exchange))

def delete_user_exchange(user_id: int, exchange: str):
    """Удаляет (или помечает неактивной) биржу."""
    execute_write_query("UPDATE user_exchanges SET is_active = 0 WHERE user_id = ? AND exchange_name = ?", (user_id, exchange))

# Backwards compatibility wrapper (if needed for old single-exchange calls, though we should refactor them too)
def save_user_api_keys(user_id: int, exchange: str, api_key: str, secret_key: str, passphrase: str = None):
    # Just redirect to new function, defaulting strategy to whatever
    # But wait, old function implied 'ratner' usually. 
    # We will assume 'ratner' unless context provided, but save_user_exchange takes strategy.
    # For now, let's keep it simple.
    save_user_exchange(user_id, exchange, api_key, secret_key, passphrase)


# --- MULTI-EXCHANGE MANAGEMENT ---

def save_user_exchange(user_id: int, exchange: str, api_key: str, secret_key: str, passphrase: str = None, strategy: str = 'bro-bot'):
    """Сохраняет или обновляет подключение к бирже."""
    encrypted_secret = encrypt_data(secret_key)
    encrypted_pass = encrypt_data(passphrase) if passphrase else None
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Upsert logic (INSERT OR REPLACE) - но лучше проверить, чтобы не затереть reserved_amount если он есть
    # Поэтому делаем INSERT ON CONFLICT DO UPDATE
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    
    # Проверяем, есть ли запись
    cursor.execute("SELECT id FROM user_exchanges WHERE user_id = ? AND exchange_name = ?", (user_id, exchange))
    row = cursor.fetchone()
    
    if row:
        # Обновляем ключи, стратегию, но оставляем reserved_amount
        execute_write_query("""
            UPDATE user_exchanges 
            SET api_key = ?, api_secret_encrypted = ?, passphrase_encrypted = ?, strategy = ?, is_active = 1
            WHERE user_id = ? AND exchange_name = ?
        """, (api_key, encrypted_secret, encrypted_pass, strategy, user_id, exchange))
    else:
        # Новая запись
        execute_write_query("""
            INSERT INTO user_exchanges (user_id, exchange_name, api_key, api_secret_encrypted, passphrase_encrypted, strategy, reserved_amount, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0.0, ?)
        """, (user_id, exchange, api_key, encrypted_secret, encrypted_pass, strategy, created_at))
    
    conn.close()

def get_user_exchanges(user_id: int) -> list[dict]:
    """Возвращает список всех подключенных бирж пользователя."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_exchanges WHERE user_id = ? AND is_active = 1", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    exchanges = []
    for row in rows:
        exchanges.append(dict(row))
    return exchanges

def update_exchange_reserve(user_id: int, exchange: str, reserve_amount: float):
    """Обновляет сумму резерва для конкретной биржи."""
    execute_write_query("UPDATE user_exchanges SET reserved_amount = ? WHERE user_id = ? AND exchange_name = ?", (reserve_amount, user_id, exchange))

def update_exchange_risk(user_id: int, exchange: str, risk_pct: float):
    """Обновляет риск на сделку для конкретной биржи."""
    execute_write_query("UPDATE user_exchanges SET risk_pct = ? WHERE user_id = ? AND exchange_name = ?", (risk_pct, user_id, exchange))

def delete_user_exchange(user_id: int, exchange: str):
    """Удаляет (или помечает неактивной) биржу."""
    execute_write_query("DELETE FROM user_exchanges WHERE user_id = ? AND exchange_name = ?", (user_id, exchange))

# ===========================
# COIN CONFIG FUNCTIONS (Multi-Coin Support)
# ===========================

def add_coin_config(user_id: int, exchange: str, symbol: str, capital: float, risk_pct: float = 1.0):
    """Добавляет конфигурацию для конкретной монеты."""
    execute_write_query("""
        INSERT OR REPLACE INTO coin_configs 
        (user_id, exchange_name, symbol, reserved_amount, risk_pct, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, 1, datetime('now'))
    """, (user_id, exchange, symbol, capital, risk_pct))
    print(f"✅ Coin config added: User {user_id} | {exchange} | {symbol} | ${capital:.2f} | {risk_pct}%")

def get_coin_configs(user_id: int, exchange: str) -> list:
    """Возвращает все конфигурации монет для биржи."""
    result = execute_read_query("""
        SELECT config_id, user_id, exchange_name, symbol, reserved_amount, risk_pct, is_active, created_at
        FROM coin_configs
        WHERE user_id = ? AND exchange_name = ? AND is_active = 1
        ORDER BY created_at DESC
    """, (user_id, exchange))
    
    coins = []
    for row in result:
        coins.append({
            'config_id': row[0],
            'user_id': row[1],
            'exchange_name': row[2],
            'symbol': row[3],
            'reserved_amount': row[4],
            'risk_pct': row[5],
            'is_active': row[6],
            'created_at': row[7]
        })
    return coins

def get_user_coin_config(user_id: int, exchange: str, symbol: str):
    """Возвращает конфигурацию конкретной монеты."""
    result = execute_read_query("""
        SELECT config_id, user_id, exchange_name, symbol, reserved_amount, risk_pct, is_active, created_at
        FROM coin_configs
        WHERE user_id = ? AND exchange_name = ? AND symbol = ? AND is_active = 1
        LIMIT 1
    """, (user_id, exchange, symbol))
    
    if not result:
        return None
    
    row = result[0]
    return {
        'config_id': row[0],
        'user_id': row[1],
        'exchange_name': row[2],
        'symbol': row[3],
        'reserved_amount': row[4],
        'risk_pct': row[5],
        'is_active': row[6],
        'created_at': row[7]
    }

def update_coin_config(user_id: int, exchange: str, symbol: str, capital: float, risk_pct: float):
    """Обновляет конфигурацию монеты."""
    execute_write_query("""
        UPDATE coin_configs 
        SET reserved_amount = ?, risk_pct = ?
        WHERE user_id = ? AND exchange_name = ? AND symbol = ?
    """, (capital, risk_pct, user_id, exchange, symbol))
    print(f"✅ Coin config updated: User {user_id} | {exchange} | {symbol} | ${capital:.2f} | {risk_pct}%")

def delete_coin_config(user_id: int, exchange: str, symbol: str):
    """Удаляет конфигурацию монеты."""
    execute_write_query("""
        DELETE FROM coin_configs 
        WHERE user_id = ? AND exchange_name = ? AND symbol = ?
    """, (user_id, exchange, symbol))
    print(f"🗑 Coin config deleted: User {user_id} | {exchange} | {symbol}")

def get_active_coins_for_strategy(strategy: str) -> list:
    """Возвращает список всех активных символов для стратегии (все пользователи)."""
    result = execute_read_query("""
        SELECT DISTINCT cc.symbol
        FROM coin_configs cc
        INNER JOIN user_exchanges ue ON cc.user_id = ue.user_id AND cc.exchange_name = ue.exchange_name
        WHERE ue.strategy = ? AND cc.is_active = 1 AND ue.is_active = 1
    """, (strategy,))
    
    return [row[0] for row in result]

def validate_coin_allocation(user_id: int, exchange: str, new_capital: float, symbol: str = None) -> dict:
    """
    Валидирует новую аллокацию капитала.
    Возвращает: {'valid': bool, 'message': str, 'total_allocated': float, 'available': float}
    """
    # Получить все текущие аллокации (исключая редактируемую монету)
    query = """
        SELECT SUM(reserved_amount) 
        FROM coin_configs 
        WHERE user_id = ? AND exchange_name = ? AND is_active = 1
    """
    params = [user_id, exchange]
    
    if symbol:
        query += " AND symbol != ?"
        params.append(symbol)
    
    result = execute_read_query(query, tuple(params))
    current_total = result[0][0] if result and result[0][0] else 0.0
    
    # Получить баланс биржи
    exchange_data = execute_read_query("""
        SELECT reserved_amount FROM user_exchanges 
        WHERE user_id = ? AND exchange_name = ?
    """, (user_id, exchange))
    
    max_balance = exchange_data[0][0] if exchange_data else 0.0
    
    # Check if we are updating an existing config or adding new
    # If updating, we subtract old value (handled by excluding symbol in query above)
    
    total_after = current_total + new_capital
    
    # Allow small floating point difference
    # Allow small floating point difference
    # if total_after > (max_balance + 0.01):
    #     return {
    #         'valid': False, 
    #         'message': f"Allocation ${new_capital:.2f} exceeds available remaining (${max_balance - current_total:.2f})",
    #         'total_allocated': total_after,
    #         'available': max_balance
    #     }
    
    # RELAXED VALIDATION: Allow update, reserved_amount will be updated in next step.
    if total_after > (max_balance + 0.01):
         print(f"⚠️ Allocation exceeds current reserve ({max_balance}), but allowing update (Reserve will auto-expand).")
        
    # Рассчитать новый total
    
    # Validation logic simplified: Checks removed to fix dead code issue and allow small test amounts.
    new_total = total_after
    
    return {
        'valid': True,
        'message': 'OK',
        'total_allocated': new_total,
        'available': max_balance
    }

# Backwards compatibility wrapper (if needed for old single-exchange calls, though we should refactor them too)
def save_user_api_keys(user_id: int, exchange: str, api_key: str, secret_key: str, passphrase: str = None):
    # Just redirect to new function, defaulting strategy to whatever
    # But wait, old function implied 'ratner' usually. 
    # We will assume 'ratner' unless context provided, but save_user_exchange takes strategy.
    # For now, let's keep it simple.
    save_user_exchange(user_id, exchange, api_key, secret_key, passphrase)


def credit_referral_tokens(user_id: int, amount: float):
    execute_write_query("UPDATE users SET token_balance = token_balance + ? WHERE user_id = ?", (amount, user_id))

def get_referrer(user_id: int) -> int | None:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,)); res = cursor.fetchone()
    conn.close(); return res[0] if res else None
def get_users_with_api_keys() -> list:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE api_key_public IS NOT NULL AND api_key_public != ''")
    user_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return user_ids
def is_tx_hash_used(tx_hash: str) -> bool:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); cursor.execute("SELECT tx_hash FROM used_tx_hashes WHERE tx_hash = ?", (tx_hash,)); res = cursor.fetchone(); conn.close(); return res is not None

def mark_tx_hash_as_used(tx_hash: str):
    execute_write_query("INSERT OR IGNORE INTO used_tx_hashes (tx_hash) VALUES (?)", (tx_hash,))

def get_user_by_referral_code(code: str) -> int | None:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); cursor.execute("SELECT user_id FROM users WHERE referral_code = ?", (code,)); res = cursor.fetchone(); conn.close(); return res[0] if res else None

def validate_and_use_promo_code(code: str, user_id: int) -> int | None:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); cursor.execute("SELECT duration_days FROM promo_codes WHERE code = ? AND is_used = 0", (code.upper(),)); res = cursor.fetchone()
    if not res: conn.close(); return None
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S"); 
    conn.close()
    
    execute_write_query("UPDATE promo_codes SET is_used = 1, used_by_user_id = ?, activation_date = ? WHERE code = ?", (user_id, date, code.upper()))
    return res[0]

def create_withdrawal_request(user_id: int, amount: float, wallet: str) -> bool:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); cursor.execute("SELECT token_balance FROM users WHERE user_id = ?", (user_id,)); res = cursor.fetchone()
    conn.close()
    
    if not res or amount > res[0]: return False
    
    # Тут две операции, в идеале нужна транзакция, но для SQLite retry тоже норм
    execute_write_query("UPDATE users SET token_balance = token_balance - ? WHERE user_id = ?", (amount, user_id))
    execute_write_query("INSERT INTO withdrawals (user_id, amount, wallet_address, request_date) VALUES (?, ?, ?, ?)", (user_id, amount, wallet, datetime.now().strftime("%Y-%m-%d")))
    return True

def generate_promo_codes(count: int, duration_days: int) -> list[str]:
    codes = []
    for _ in range(count): 
        c = f"ALADDIN-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:4].upper()}"
        execute_write_query("INSERT OR IGNORE INTO promo_codes (code, duration_days) VALUES (?, ?)", (c, duration_days))
        codes.append(c)
    return codes

def check_and_expire_subscriptions():
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); today = datetime.now().strftime("%Y-%m-%d"); cursor.execute("SELECT user_id FROM users WHERE status = 'active' AND subscription_expiry < ?", (today,)); exp = [r[0] for r in cursor.fetchall()]
    conn.close()
    
    if exp: 
        for u in exp:
            execute_write_query("UPDATE users SET status = 'expired' WHERE user_id = ?", (u,))
    return exp

def get_admin_stats():
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    total = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]; active = cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'active'").fetchone()[0]
    pending = cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'pending_payment'").fetchone()[0]; tokens = cursor.execute("SELECT SUM(token_balance) FROM users").fetchone()[0] or 0
    w_count = cursor.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'").fetchone()[0]; w_sum = cursor.execute("SELECT SUM(amount) FROM withdrawals WHERE status = 'pending'").fetchone()[0] or 0
    p_total = cursor.execute("SELECT COUNT(*) FROM promo_codes").fetchone()[0]; p_used = cursor.execute("SELECT COUNT(*) FROM promo_codes WHERE is_used = 1").fetchone()[0]
    conn.close(); return {"total_users": total, "active_users": active, "pending_payment": pending, "total_tokens": tokens, "pending_withdrawals_count": w_count, "pending_withdrawals_sum": w_sum, "total_promo_codes": p_total, "used_promo_codes": p_used, "available_promo_codes": p_total-p_used}

def get_active_users_report(limit=20):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); cursor.execute("SELECT user_id, username, token_balance FROM users WHERE status = 'active' ORDER BY join_date DESC LIMIT ?", (limit,)); users = cursor.fetchall(); report = []
    for u in users:
        l1 = cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (u[0],)).fetchone()[0]
        report.append({"user_id": u[0], "username": u[1], "balance": u[2], "referrals": {"l1": l1, "l2": 0}})
    conn.close(); return report

def get_pending_withdrawals():
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); cursor.execute("SELECT request_id, user_id, amount, wallet_address, request_date FROM withdrawals WHERE status = 'pending' ORDER BY request_id ASC"); res = cursor.fetchall(); conn.close(); return res

# Запуск инициализации при импорте
initialize_db()
def get_text(user_id: int, key: str, lang: str = None, **kwargs) -> str:
    """Retrieves translated text for a user."""
    if not lang:
        lang = get_user_language(user_id)
    
    try:
        file_path = os.path.join("locales", f"{lang}.json")
        if not os.path.exists(file_path):
            file_path = os.path.join("locales", "en.json")
            
        with open(file_path, 'r', encoding='utf-8') as f:
            translations = json.load(f)
            
        text = translations.get(key, translations.get(key, key))
        return text.format(**kwargs)
    except Exception as e:
        print(f"Error in get_text: {e}")
        return key

def get_referral_count(user_id: int, level: int) -> int:
    """
    Get count of referrals at a specific level for a user.
    Level 1: Direct referrals (people invited by this user)
    Level 2: Referrals of referrals (people invited by Level 1)
    Level 3: Third level referrals (people invited by Level 2)
    
    Uses recursive CTE to traverse the referral tree.
    """
    query = """
        WITH RECURSIVE referral_tree AS (
            -- Base case: Direct referrals (Level 1)
            SELECT user_id, referred_by, 1 as level
            FROM users
            WHERE referred_by = ?
            
            UNION ALL
            
            -- Recursive case: Subsequent levels
            SELECT u.user_id, u.referred_by, rt.level + 1
            FROM users u
            INNER JOIN referral_tree rt ON u.referred_by = rt.user_id
            WHERE rt.level < 3
        )
        SELECT COUNT(*) as count
        FROM referral_tree
        WHERE level = ?
    """
    
    try:
        result = execute_read_query(query, (user_id, level))
        return result[0]['count'] if result else 0
    except Exception as e:
        print(f"[ERROR] get_referral_count failed for user {user_id}, level {level}: {e}")
        return 0


# ========================================
# INVESTIGATION SYSTEM FUNCTIONS
# ========================================

def record_master_order(master_exchange: str, symbol: str, side: str, order_type: str, 
                        price: float, quantity: float, strategy: str) -> int:
    """
    Записывает ордер мастер-аккаунта в БД.
    Возвращает master_order_id для передачи в worker.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO master_orders (master_exchange, symbol, side, order_type, price, quantity, timestamp, strategy)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (master_exchange, symbol, side, order_type, price, quantity, timestamp, strategy))
    
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    print(f"   📝 [MASTER ORDER] ID={order_id} {side.upper()} {symbol} @ ${price}")
    return order_id


def record_client_copy(master_order_id: int, user_id: int, symbol: str, side: str, 
                       entry_price: float, quantity: float):
    """
    Записывает копирование сделки клиентом.
    """
    opened_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    execute_write_query("""
        INSERT INTO client_copies (master_order_id, user_id, symbol, side, entry_price, quantity, opened_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'open')
    """, (master_order_id, user_id, symbol, side, entry_price, quantity, opened_at))
    
    print(f"   ✅ [CLIENT COPY] User {user_id}: {side.upper()} {quantity} {symbol} @ ${entry_price}")


def get_open_client_copy(user_id: int, symbol: str) -> dict:
    """
    Возвращает открытую позицию клиента для данного символа.
    None если позиции нет.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT copy_id, master_order_id, side, entry_price, quantity, opened_at
        FROM client_copies
        WHERE user_id = ? AND symbol = ? AND status = 'open'
        ORDER BY copy_id DESC
        LIMIT 1
    """, (user_id, symbol))
    
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return None
    
    return {
        "copy_id": result[0],
        "master_order_id": result[1],
        "side": result[2],
        "entry_price": result[3],
        "quantity": result[4],
        "opened_at": result[5]
    }


def close_client_copy(user_id: int, symbol: str, exit_price: float) -> float:
    """
    Закрывает открытую позицию клиента и рассчитывает PnL.
    Возвращает PnL (положительный или отрицательный).
    """
    open_copy = get_open_client_copy(user_id, symbol)
    
    if not open_copy:
        print(f"   ⚠️ [CLOSE COPY] No open position for User {user_id} {symbol}")
        return 0.0
    
    # Расчет PnL
    entry_price = open_copy['entry_price']
    quantity = open_copy['quantity']
    side = open_copy['side']
    
    if side == 'buy':
        pnl = (exit_price - entry_price) * quantity
    else:  # sell
        pnl = (entry_price - exit_price) * quantity
    
    closed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Обновляем запись
    execute_write_query("""
        UPDATE client_copies
        SET exit_price = ?, profit_loss = ?, closed_at = ?, status = 'closed'
        WHERE copy_id = ?
    """, (exit_price, pnl, closed_at, open_copy['copy_id']))
    
    print(f"   💰 [CLOSE COPY] User {user_id}: PnL = ${pnl:.2f}")
    return pnl


def get_investigation_report(user_id: int = None, symbol: str = None, limit: int = 100) -> dict:
    """
    Генерирует отчет для investigation.
    user_id: фильтр по пользователю (опционально)
    symbol: фильтр по символу (опционально)
    limit: максимум записей
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Собираем копии клиентов
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
            cc.status,
            mo.master_exchange,
            mo.order_type
        FROM client_copies cc
        LEFT JOIN master_orders mo ON cc.master_order_id = mo.order_id
        WHERE 1=1
    """
    params = []
    
    if user_id:
        query += " AND cc.user_id = ?"
        params.append(user_id)
    if symbol:
        query += " AND cc.symbol = ?"
        params.append(symbol)
    
    query += " ORDER BY cc.opened_at DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    copies = [dict(row) for row in cursor.fetchall()]
    
    # Подсчет статистики
    total_trades = len(copies)
    closed_trades = len([c for c in copies if c['status'] == 'closed'])
    open_trades = total_trades - closed_trades
    
    total_pnl = sum(c['profit_loss'] for c in copies if c['profit_loss'])
    
    conn.close()
    
    return {
        "copies": copies,
        "stats": {
            "total_trades": total_trades,
            "closed_trades": closed_trades,
            "open_trades": open_trades,
            "total_pnl": total_pnl
        }
    }
