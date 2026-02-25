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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RENDER_DISK_PATH = os.getenv("RENDER_DISK_PATH")
DB_NAME = os.path.join(RENDER_DISK_PATH, "aladdin_users.db") if RENDER_DISK_PATH else os.path.join(BASE_DIR, "aladdin_dev.db")
print(f"✅ Database path: {DB_NAME}")

FERNET_KEY = os.getenv("FERNET_KEY")
if not FERNET_KEY:
    raise ValueError("FATAL: FERNET_KEY not found in env")
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


# ── core db helpers (retry + WAL) ──

def execute_write_query(query, params=()):
    """write with retry on lock (5 attempts)"""
    for i in range(5):
        conn = None
        try:
            conn = sqlite3.connect(DB_NAME)
            conn.cursor().execute(query, params)
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                time.sleep(0.1)
                continue
            raise
        except Exception as e:
            print(f"❌ DB Error: {e}")
            raise
        finally:
            if conn: conn.close()
    print(f"❌ CRITICAL: DB locked after 5 retries")

def execute_read_query(query, params=()):
    """read with row_factory for named access"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    except Exception as e:
        print(f"❌ Read Error: {e}")
        return []
    finally:
        conn.close()


# ── schema + migrations ──

def initialize_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()

    cursor.execute("""
       CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            join_date TEXT,
            status TEXT DEFAULT 'active',
            subscription_expiry TEXT,
            referrer_id INTEGER,
            referred_by INTEGER,
            referral_code TEXT UNIQUE,
            token_balance REAL DEFAULT 0,
            unc_balance REAL DEFAULT 0,
            is_copytrading_enabled BOOLEAN DEFAULT 1,
            account_balance REAL DEFAULT 1000.0,
            risk_per_trade_pct REAL DEFAULT 1.0,
            exchange_name TEXT,
            api_key_public TEXT,
            api_secret_encrypted TEXT,
            api_passphrase_encrypted TEXT,
            selected_strategy TEXT DEFAULT 'bro-bot',
            daily_analysis_count INTEGER DEFAULT 0,
            last_analysis_date TEXT,
            language_code TEXT DEFAULT 'en'
        )
    """)

    cursor.execute("CREATE TABLE IF NOT EXISTS used_tx_hashes (tx_hash TEXT PRIMARY KEY)")
    cursor.execute("CREATE TABLE IF NOT EXISTS withdrawals (request_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, wallet_address TEXT, request_date TEXT, status TEXT DEFAULT 'pending')")
    cursor.execute("CREATE TABLE IF NOT EXISTS promo_codes (code TEXT PRIMARY KEY, duration_days INTEGER, is_used INTEGER DEFAULT 0, used_by_user_id INTEGER, activation_date TEXT)")

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_exchanges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            exchange_name TEXT,
            api_key TEXT,
            api_secret_encrypted TEXT,
            passphrase_encrypted TEXT,
            strategy TEXT DEFAULT 'bro-bot',
            reserved_amount REAL DEFAULT 0.0,
            risk_pct REAL DEFAULT 1.0,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            UNIQUE(user_id, exchange_name)
        )
    """)

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS master_positions (
            symbol TEXT NOT NULL,
            strategy TEXT NOT NULL,
            net_quantity REAL DEFAULT 0.0,
            updated_at TEXT,
            PRIMARY KEY (symbol, strategy)
        )
    """)

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

    # legacy migration: users table -> user_exchanges
    try:
        cursor.execute("SELECT user_id, exchange_name, api_key_public, api_secret_encrypted, api_passphrase_encrypted, selected_strategy FROM users WHERE api_key_public IS NOT NULL AND api_key_public != ''")
        legacy = cursor.fetchall()
        for u in legacy:
            uid, ex_name, pub, sec, pas, strat = u
            if not ex_name: ex_name = 'binance'
            cursor.execute("""
                INSERT OR IGNORE INTO user_exchanges (user_id, exchange_name, api_key, api_secret_encrypted, passphrase_encrypted, strategy, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (uid, ex_name.lower(), pub, sec, pas, strat, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        if legacy:
            print(f"🔄 Migrated {len(legacy)} legacy users to user_exchanges")
    except Exception as e:
        print(f"⚠️ Migration warning: {e}")

    # column migrations (safe — silently ignored if column exists)
    migrations = [
        "ALTER TABLE user_exchanges ADD COLUMN risk_pct REAL DEFAULT 1.0",
        "ALTER TABLE users ADD COLUMN exchange_name TEXT",
        "ALTER TABLE copied_trades ADD COLUMN open_date TEXT",
        "ALTER TABLE users ADD COLUMN selected_strategy TEXT DEFAULT 'bro-bot'",
        "ALTER TABLE users ADD COLUMN daily_analysis_count INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN last_analysis_date TEXT",
        "ALTER TABLE users ADD COLUMN api_passphrase_encrypted TEXT",
        "ALTER TABLE users ADD COLUMN language_code TEXT DEFAULT 'en'",
        "ALTER TABLE users ADD COLUMN referred_by INTEGER",
        "ALTER TABLE users ADD COLUMN unc_balance REAL DEFAULT 0",
    ]
    for m in migrations:
        try: cursor.execute(m)
        except: pass

    conn.commit()
    conn.close()
    print("✅ Database initialized (WAL mode)")


# ── user settings ──

def save_user_language(user_id: int, lang_code: str):
    execute_write_query("UPDATE users SET language_code = ? WHERE user_id = ?", (lang_code, user_id))

def get_user_language(user_id: int) -> str:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT language_code FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res and res[0] else 'en'

def check_analysis_limit(user_id: int, limit: int = 5) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT daily_analysis_count, last_analysis_date FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    count = row[0] if row and row[0] else 0
    last_date = row[1] if row and row[1] else ""

    if last_date != today:
        cursor.execute("UPDATE users SET daily_analysis_count = 1, last_analysis_date = ? WHERE user_id = ?", (today, user_id))
        conn.commit(); conn.close()
        return True
    if count < limit:
        cursor.execute("UPDATE users SET daily_analysis_count = daily_analysis_count + 1 WHERE user_id = ?", (user_id,))
        conn.commit(); conn.close()
        return True
    conn.close()
    return False

def set_user_strategy(user_id: int, strategy: str):
    execute_write_query("UPDATE users SET selected_strategy = ? WHERE user_id = ?", (strategy, user_id))

def get_user_strategy(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT selected_strategy FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 'bro-bot'

def get_user_risk_profile(user_id: int) -> float:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT risk_per_trade_pct FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return float(res[0]) if res and res[0] is not None else 1.0


# ── copy trading connections ──

def get_users_for_copytrade(strategy: str = None) -> list:
    """legacy: returns user_ids from users table"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if strategy:
        cursor.execute("SELECT user_id FROM users WHERE api_key_public IS NOT NULL AND api_key_public != '' AND is_copytrading_enabled = 1 AND selected_strategy = ?", (strategy,))
    else:
        cursor.execute("SELECT user_id FROM users WHERE api_key_public IS NOT NULL AND api_key_public != '' AND is_copytrading_enabled = 1")
    ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return ids

def get_active_exchange_connections(strategy: str = None, symbol: str = None) -> list:
    """returns active connections. for cgt+symbol: joins coin_configs for per-coin filtering."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if strategy == 'cgt' and symbol:
        cursor.execute("""
            SELECT ue.user_id, ue.exchange_name, ue.reserved_amount, ue.risk_pct, cc.symbol, ue.strategy
            FROM user_exchanges ue
            INNER JOIN coin_configs cc ON ue.user_id = cc.user_id AND ue.exchange_name = cc.exchange_name
            JOIN users u ON ue.user_id = u.user_id
            WHERE ue.is_active = 1 AND cc.is_active = 1 AND u.is_copytrading_enabled = 1
              AND u.token_balance > 0 AND ue.strategy = ? AND cc.symbol = ?
        """, (strategy, symbol))
    else:
        query = """
            SELECT ue.user_id, ue.exchange_name, ue.reserved_amount, ue.strategy, ue.risk_pct
            FROM user_exchanges ue JOIN users u ON ue.user_id = u.user_id
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


# ── api keys ──

def save_user_api_keys(user_id: int, exchange: str, api_key: str, secret_key: str, passphrase: str = None):
    """redirects to save_user_exchange"""
    save_user_exchange(user_id, exchange, api_key, secret_key, passphrase)

def save_user_exchange(user_id: int, exchange: str, api_key: str, secret_key: str, passphrase: str = None, strategy: str = 'bro-bot'):
    enc_secret = encrypt_data(secret_key)
    enc_pass = encrypt_data(passphrase) if passphrase else None
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM user_exchanges WHERE user_id = ? AND exchange_name = ?", (user_id, exchange))

    if cursor.fetchone():
        execute_write_query("""
            UPDATE user_exchanges SET api_key = ?, api_secret_encrypted = ?, passphrase_encrypted = ?, strategy = ?, is_active = 1
            WHERE user_id = ? AND exchange_name = ?
        """, (api_key, enc_secret, enc_pass, strategy, user_id, exchange))
    else:
        execute_write_query("""
            INSERT INTO user_exchanges (user_id, exchange_name, api_key, api_secret_encrypted, passphrase_encrypted, strategy, reserved_amount, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0.0, ?)
        """, (user_id, exchange, api_key, enc_secret, enc_pass, strategy, now))
    conn.close()

def get_user_decrypted_keys(user_id: int, exchange_name: str = None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # new table lookup
    query = "SELECT exchange_name, api_key, api_secret_encrypted, passphrase_encrypted, reserved_amount FROM user_exchanges WHERE user_id = ?"
    params = [user_id]
    if exchange_name:
        query += " AND exchange_name = ?"
        params.append(exchange_name)

    cursor.execute(query, params)
    res = cursor.fetchone()
    if res:
        conn.close()
        return {"exchange": res[0], "apiKey": res[1], "secret": decrypt_data(res[2]),
                "password": decrypt_data(res[3]) if res[3] else None, "reserved_amount": res[4] or 0.0}

    # legacy fallback (users table)
    cursor.execute("SELECT exchange_name, api_key_public, api_secret_encrypted, api_passphrase_encrypted FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    if not result or not result[2]: return None
    if exchange_name and result[0] != exchange_name: return None

    return {"exchange": result[0], "apiKey": result[1], "secret": decrypt_data(result[2]),
            "password": decrypt_data(result[3]) if result[3] else None, "reserved_amount": 0.0}


# ── referrals ──

def get_referral_count(user_id: int, level: int = 1) -> int:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if level == 1:
        cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
    elif level == 2:
        cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id IN (SELECT user_id FROM users WHERE referrer_id = ?)", (user_id,))
    elif level == 3:
        cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id IN (SELECT user_id FROM users WHERE referrer_id IN (SELECT user_id FROM users WHERE referrer_id = ?))", (user_id,))
    else:
        conn.close(); return 0
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_referrer_upline(user_id: int, levels: int = 3) -> list:
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

def credit_referral_tokens(user_id: int, amount: float):
    execute_write_query("UPDATE users SET token_balance = token_balance + ? WHERE user_id = ?", (amount, user_id))

def get_referrer(user_id: int) -> int | None:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone(); conn.close()
    return res[0] if res else None


# ── trades ──

def record_trade_entry(user_id: int, symbol: str, side: str, price: float, quantity: float):
    """upsert: average into existing open position or create new one"""
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT trade_id, avg_entry_price, total_quantity FROM copied_trades WHERE user_id = ? AND symbol = ? AND status = 'open'", (user_id, symbol))
        existing = cursor.fetchone()

        if existing:
            trade_id, old_price, old_qty = existing
            new_qty = old_qty + quantity
            new_avg = ((old_price * old_qty) + (price * quantity)) / new_qty
            cursor.execute("UPDATE copied_trades SET avg_entry_price = ?, total_quantity = ? WHERE trade_id = ?", (new_avg, new_qty, trade_id))
            print(f"   -> DB: averaged position for user {user_id}, qty: {new_qty:.4f}")
        else:
            try:
                cursor.execute("""
                    INSERT INTO copied_trades (user_id, symbol, side, avg_entry_price, total_quantity, open_date, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'open')
                """, (user_id, symbol, side, price, quantity, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                print(f"   -> DB: new position for user {user_id}")
            except sqlite3.IntegrityError:
                # race condition — retry as average
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
    cursor.execute("""
        SELECT side, avg_entry_price, total_quantity FROM copied_trades
        WHERE user_id = ? AND symbol = ? AND status = 'open'
        ORDER BY trade_id DESC LIMIT 1
    """, (user_id, symbol))
    result = cursor.fetchone()
    conn.close()
    if not result: return None
    return {"side": result[0], "entry_price": result[1], "quantity": result[2]}

def close_trade_in_db(user_id: int, symbol: str):
    execute_write_query("UPDATE copied_trades SET status = 'closed' WHERE user_id = ? AND symbol = ? AND status = 'open'", (user_id, symbol))

def set_copytrading_status(user_id: int, is_enabled: bool):
    execute_write_query("UPDATE users SET is_copytrading_enabled = ? WHERE user_id = ?", (1 if is_enabled else 0, user_id))


# ── billing ──

def deduct_performance_fee(user_id: int, fee_amount: float) -> float:
    execute_write_query("UPDATE users SET token_balance = token_balance - ? WHERE user_id = ?", (fee_amount, user_id))
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT token_balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone(); conn.close()
    new_bal = res[0] if res else 0
    print(f"   -> BILLING: deducted {fee_amount:.2f}, balance: {new_bal:.2f}")
    return new_bal

def credit_tokens_from_payment(user_id: int, amount_usd: float):
    execute_write_query("UPDATE users SET token_balance = token_balance + ? WHERE user_id = ?", (amount_usd, user_id))
    print(f"💰 Credited {amount_usd} to user {user_id}")


# ── exchange management ──

def get_user_exchanges(user_id: int) -> list[dict]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_exchanges WHERE user_id = ? AND is_active = 1", (user_id,))
    rows = cursor.fetchall(); conn.close()
    return [dict(row) for row in rows]

def update_exchange_reserve(user_id: int, exchange: str, reserve_amount: float):
    execute_write_query("UPDATE user_exchanges SET reserved_amount = ? WHERE user_id = ? AND exchange_name = ?", (reserve_amount, user_id, exchange))

def update_exchange_risk(user_id: int, exchange: str, risk_pct: float):
    execute_write_query("UPDATE user_exchanges SET risk_pct = ? WHERE user_id = ? AND exchange_name = ?", (risk_pct, user_id, exchange))

def delete_user_exchange(user_id: int, exchange: str):
    execute_write_query("DELETE FROM user_exchanges WHERE user_id = ? AND exchange_name = ?", (user_id, exchange))


# ── coin configs ──

def add_coin_config(user_id: int, exchange: str, symbol: str, capital: float, risk_pct: float = 1.0):
    execute_write_query("""
        INSERT OR REPLACE INTO coin_configs (user_id, exchange_name, symbol, reserved_amount, risk_pct, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, 1, datetime('now'))
    """, (user_id, exchange, symbol, capital, risk_pct))

def get_coin_configs(user_id: int, exchange: str) -> list:
    result = execute_read_query("""
        SELECT config_id, user_id, exchange_name, symbol, reserved_amount, risk_pct, is_active, created_at
        FROM coin_configs WHERE user_id = ? AND exchange_name = ? AND is_active = 1
        ORDER BY created_at DESC
    """, (user_id, exchange))
    return [{'config_id': r[0], 'user_id': r[1], 'exchange_name': r[2], 'symbol': r[3],
             'reserved_amount': r[4], 'risk_pct': r[5], 'is_active': r[6], 'created_at': r[7]} for r in result]

def get_user_coin_config(user_id: int, exchange: str, symbol: str):
    result = execute_read_query("""
        SELECT config_id, user_id, exchange_name, symbol, reserved_amount, risk_pct, is_active, created_at
        FROM coin_configs WHERE user_id = ? AND exchange_name = ? AND symbol = ? AND is_active = 1 LIMIT 1
    """, (user_id, exchange, symbol))
    if not result: return None
    r = result[0]
    return {'config_id': r[0], 'user_id': r[1], 'exchange_name': r[2], 'symbol': r[3],
            'reserved_amount': r[4], 'risk_pct': r[5], 'is_active': r[6], 'created_at': r[7]}

def update_coin_config(user_id: int, exchange: str, symbol: str, capital: float, risk_pct: float):
    execute_write_query("UPDATE coin_configs SET reserved_amount = ?, risk_pct = ? WHERE user_id = ? AND exchange_name = ? AND symbol = ?",
                        (capital, risk_pct, user_id, exchange, symbol))

def delete_coin_config(user_id: int, exchange: str, symbol: str):
    execute_write_query("DELETE FROM coin_configs WHERE user_id = ? AND exchange_name = ? AND symbol = ?", (user_id, exchange, symbol))

def get_active_coins_for_strategy(strategy: str) -> list:
    result = execute_read_query("""
        SELECT DISTINCT cc.symbol FROM coin_configs cc
        INNER JOIN user_exchanges ue ON cc.user_id = ue.user_id AND cc.exchange_name = ue.exchange_name
        WHERE ue.strategy = ? AND cc.is_active = 1 AND ue.is_active = 1
    """, (strategy,))
    return [row[0] for row in result]

def validate_coin_allocation(user_id: int, exchange: str, new_capital: float, symbol: str = None) -> dict:
    query = "SELECT SUM(reserved_amount) FROM coin_configs WHERE user_id = ? AND exchange_name = ? AND is_active = 1"
    params = [user_id, exchange]
    if symbol:
        query += " AND symbol != ?"
        params.append(symbol)

    result = execute_read_query(query, tuple(params))
    current_total = result[0][0] if result and result[0][0] else 0.0

    exchange_data = execute_read_query("SELECT reserved_amount FROM user_exchanges WHERE user_id = ? AND exchange_name = ?", (user_id, exchange))
    max_balance = exchange_data[0][0] if exchange_data else 0.0

    total_after = current_total + new_capital
    if total_after > (max_balance + 0.01):
        print(f"⚠️ Allocation exceeds reserve ({max_balance}), allowing (auto-expand)")

    return {'valid': True, 'message': 'OK', 'total_allocated': total_after, 'available': max_balance}


# ── master positions (partial sell support) ──

def update_master_position(symbol: str, strategy: str, quantity_change: float):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT net_quantity FROM master_positions WHERE symbol = ? AND strategy = ?", (symbol, strategy))
    row = cursor.fetchone()

    if row:
        new_qty = max(0, row[0] + quantity_change)
        cursor.execute("UPDATE master_positions SET net_quantity = ?, updated_at = datetime('now') WHERE symbol = ? AND strategy = ?", (new_qty, symbol, strategy))
    else:
        new_qty = max(0, quantity_change)
        cursor.execute("INSERT INTO master_positions (symbol, strategy, net_quantity, updated_at) VALUES (?, ?, ?, datetime('now'))", (symbol, strategy, new_qty))

    conn.commit(); conn.close()
    return new_qty

def get_master_position(symbol: str, strategy: str) -> float:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT net_quantity FROM master_positions WHERE symbol = ? AND strategy = ?", (symbol, strategy))
    row = cursor.fetchone(); conn.close()
    return row[0] if row else 0.0


# ── investigation system ──

def record_master_order(master_exchange: str, symbol: str, side: str, order_type: str,
                        price: float, quantity: float, strategy: str) -> int:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO master_orders (master_exchange, symbol, side, order_type, price, quantity, timestamp, strategy)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (master_exchange, symbol, side, order_type, price, quantity, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), strategy))
    order_id = cursor.lastrowid
    conn.commit(); conn.close()
    print(f"   📝 [MASTER] ID={order_id} {side.upper()} {symbol} @ ${price}")
    return order_id

def record_client_copy(master_order_id: int, user_id: int, symbol: str, side: str,
                       entry_price: float, quantity: float):
    execute_write_query("""
        INSERT INTO client_copies (master_order_id, user_id, symbol, side, entry_price, quantity, opened_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'open')
    """, (master_order_id, user_id, symbol, side, entry_price, quantity, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

def get_open_client_copy(user_id: int, symbol: str) -> dict:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT copy_id, master_order_id, side, entry_price, quantity, opened_at
        FROM client_copies WHERE user_id = ? AND symbol = ? AND status = 'open'
        ORDER BY copy_id DESC LIMIT 1
    """, (user_id, symbol))
    r = cursor.fetchone(); conn.close()
    if not r: return None
    return {"copy_id": r[0], "master_order_id": r[1], "side": r[2], "entry_price": r[3], "quantity": r[4], "opened_at": r[5]}

def close_client_copy(user_id: int, symbol: str, exit_price: float) -> float:
    open_copy = get_open_client_copy(user_id, symbol)
    if not open_copy: return 0.0

    entry = open_copy['entry_price']
    qty = open_copy['quantity']
    pnl = (exit_price - entry) * qty if open_copy['side'] == 'buy' else (entry - exit_price) * qty

    execute_write_query("""
        UPDATE client_copies SET exit_price = ?, profit_loss = ?, closed_at = ?, status = 'closed'
        WHERE copy_id = ?
    """, (exit_price, pnl, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), open_copy['copy_id']))
    return pnl


def record_partial_sell_pnl(user_id: int, symbol: str, side: str,
                            entry_price: float, exit_price: float, quantity: float):
    """Record PnL for a partial sell as a new already-closed entry in client_copies.
    This ensures daily reports capture partial sell profits."""
    pnl = (exit_price - entry_price) * quantity if side == 'buy' else (entry_price - exit_price) * quantity
    execute_write_query("""
        INSERT INTO client_copies (master_order_id, user_id, symbol, side, entry_price, exit_price,
                                   quantity, profit_loss, opened_at, closed_at, status)
        VALUES (0, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'closed')
    """, (user_id, symbol, side, entry_price, exit_price, quantity, pnl,
          datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print(f"   📝 [PARTIAL PnL] User {user_id}: {symbol} qty={quantity:.6f}, PnL=${pnl:.4f}")

def get_investigation_report(user_id: int = None, symbol: str = None, limit: int = 100) -> dict:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT cc.copy_id, cc.user_id, cc.symbol, cc.side, cc.entry_price, cc.exit_price,
               cc.quantity, cc.profit_loss, cc.opened_at, cc.closed_at, cc.status,
               mo.master_exchange, mo.order_type
        FROM client_copies cc LEFT JOIN master_orders mo ON cc.master_order_id = mo.order_id
        WHERE 1=1
    """
    params = []
    if user_id: query += " AND cc.user_id = ?"; params.append(user_id)
    if symbol: query += " AND cc.symbol = ?"; params.append(symbol)
    query += " ORDER BY cc.opened_at DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    copies = [dict(row) for row in cursor.fetchall()]
    conn.close()

    closed = [c for c in copies if c['status'] == 'closed']
    return {
        "copies": copies,
        "stats": {
            "total_trades": len(copies), "closed_trades": len(closed),
            "open_trades": len(copies) - len(closed),
            "total_pnl": sum(c['profit_loss'] for c in copies if c['profit_loss'])
        }
    }


# ── user management ──

UserStatus = Literal["pending_payment", "active", "expired"]

def add_user(user_id: int, username: str = None, referrer_id: int = None) -> bool:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        execute_write_query(
            "INSERT INTO users (user_id, username, join_date, referrer_id, referred_by, referral_code, status, account_balance, risk_per_trade_pct, unc_balance) VALUES (?, ?, ?, ?, ?, ?, 'active', 1000.0, 1.0, 0.0)",
            (user_id, username, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), referrer_id, referrer_id, f"ref_{user_id}")
        )
        return True
    conn.close()
    return False

def get_user_status(user_id: int) -> UserStatus | None:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT status FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone(); conn.close()
    return res[0] if res else None

def activate_user(user_id: int):
    execute_write_query("UPDATE users SET status = 'active' WHERE user_id = ?", (user_id,))

def activate_user_subscription(user_id: int, duration_days: int = 30) -> int | None:
    expiry = (datetime.now() + timedelta(days=duration_days)).strftime("%Y-%m-%d")
    execute_write_query("UPDATE users SET status = 'active', subscription_expiry = ? WHERE user_id = ?", (expiry, user_id))
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone(); conn.close()
    return res[0] if res else None

def get_all_active_user_ids() -> list[int]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE status = 'active'")
    ids = [row[0] for row in cursor.fetchall()]; conn.close()
    return ids

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

def get_all_users_with_keys() -> list:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE api_key_public IS NOT NULL AND api_key_public != ''")
    users = [row[0] for row in cursor.fetchall()]; conn.close()
    return users

def get_users_with_api_keys() -> list:
    return get_all_users_with_keys()


# ── misc ──

def is_tx_hash_used(tx_hash: str) -> bool:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT tx_hash FROM used_tx_hashes WHERE tx_hash = ?", (tx_hash,))
    res = cursor.fetchone(); conn.close()
    return res is not None

def mark_tx_hash_as_used(tx_hash: str):
    execute_write_query("INSERT OR IGNORE INTO used_tx_hashes (tx_hash) VALUES (?)", (tx_hash,))

def get_user_by_referral_code(code: str) -> int | None:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE referral_code = ?", (code,))
    res = cursor.fetchone(); conn.close()
    return res[0] if res else None

def validate_and_use_promo_code(code: str, user_id: int) -> int | None:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT duration_days FROM promo_codes WHERE code = ? AND is_used = 0", (code.upper(),))
    res = cursor.fetchone()
    if not res: conn.close(); return None
    conn.close()
    execute_write_query("UPDATE promo_codes SET is_used = 1, used_by_user_id = ?, activation_date = ? WHERE code = ?",
                        (user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), code.upper()))
    return res[0]

def create_withdrawal_request(user_id: int, amount: float, wallet: str) -> bool:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT token_balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone(); conn.close()
    if not res or amount > res[0]: return False
    execute_write_query("UPDATE users SET token_balance = token_balance - ? WHERE user_id = ?", (amount, user_id))
    execute_write_query("INSERT INTO withdrawals (user_id, amount, wallet_address, request_date) VALUES (?, ?, ?, ?)",
                        (user_id, amount, wallet, datetime.now().strftime("%Y-%m-%d")))
    return True

def generate_promo_codes(count: int, duration_days: int) -> list[str]:
    codes = []
    for _ in range(count):
        c = f"ALADDIN-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:4].upper()}"
        execute_write_query("INSERT OR IGNORE INTO promo_codes (code, duration_days) VALUES (?, ?)", (c, duration_days))
        codes.append(c)
    return codes

def check_and_expire_subscriptions():
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT user_id FROM users WHERE status = 'active' AND subscription_expiry < ?", (today,))
    expired = [r[0] for r in cursor.fetchall()]; conn.close()
    for u in expired:
        execute_write_query("UPDATE users SET status = 'expired' WHERE user_id = ?", (u,))
    return expired

def get_admin_stats():
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    total = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active = cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'active'").fetchone()[0]
    pending = cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'pending_payment'").fetchone()[0]
    tokens = cursor.execute("SELECT SUM(token_balance) FROM users").fetchone()[0] or 0
    w_count = cursor.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'").fetchone()[0]
    w_sum = cursor.execute("SELECT SUM(amount) FROM withdrawals WHERE status = 'pending'").fetchone()[0] or 0
    p_total = cursor.execute("SELECT COUNT(*) FROM promo_codes").fetchone()[0]
    p_used = cursor.execute("SELECT COUNT(*) FROM promo_codes WHERE is_used = 1").fetchone()[0]
    conn.close()
    return {"total_users": total, "active_users": active, "pending_payment": pending, "total_tokens": tokens,
            "pending_withdrawals_count": w_count, "pending_withdrawals_sum": w_sum,
            "total_promo_codes": p_total, "used_promo_codes": p_used, "available_promo_codes": p_total - p_used}

def get_active_users_report(limit=20):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, token_balance FROM users WHERE status = 'active' ORDER BY join_date DESC LIMIT ?", (limit,))
    users = cursor.fetchall()
    report = []
    for u in users:
        l1 = cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (u[0],)).fetchone()[0]
        report.append({"user_id": u[0], "username": u[1], "balance": u[2], "referrals": {"l1": l1, "l2": 0}})
    conn.close()
    return report

def get_pending_withdrawals():
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT request_id, user_id, amount, wallet_address, request_date FROM withdrawals WHERE status = 'pending' ORDER BY request_id ASC")
    res = cursor.fetchall(); conn.close()
    return res

def get_text(user_id: int, key: str, lang: str = None, **kwargs) -> str:
    if not lang: lang = get_user_language(user_id)
    try:
        file_path = os.path.join("locales", f"{lang}.json")
        if not os.path.exists(file_path):
            file_path = os.path.join("locales", "en.json")
        with open(file_path, 'r', encoding='utf-8') as f:
            translations = json.load(f)
        return translations.get(key, key).format(**kwargs)
    except Exception:
        return key


# ── daily pnl report ──

def get_daily_pnl_report(date_str: str) -> list[dict]:
    """returns per-user per-exchange pnl for a given date (YYYY-MM-DD).
    includes ALL closed trades grouped by exchange.
    result: [{user_id, exchange, pnl}, ...]"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT cc.user_id, COALESCE(mo.master_exchange, 'okx') as exchange, SUM(cc.profit_loss) as total_pnl
        FROM client_copies cc
        LEFT JOIN master_orders mo ON cc.master_order_id = mo.order_id
        WHERE cc.status = 'closed' AND cc.closed_at LIKE ? AND cc.profit_loss IS NOT NULL
        GROUP BY cc.user_id, exchange
        ORDER BY cc.user_id, total_pnl DESC
    """, (f"{date_str}%",))
    rows = cursor.fetchall()
    conn.close()
    return [{"user_id": r[0], "exchange": r[1], "pnl": r[2]} for r in rows]


# auto-init on import
initialize_db()
