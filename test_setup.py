#!/usr/bin/env python3
"""
Setup тестового клиента для локального тестирования
"""

from database import execute_write_query, save_user_exchange

# НАСТРОЙКИ - ИЗМЕНИ ПОД СЕБЯ
TEST_USER_ID = 502483421  # Твой Telegram ID

OKX_API_KEY = "35da235c-fa34-4717-b392-7e2113703c7d"
OKX_SECRET = "FED6775506E418C26A9B45A6434E3591"
OKX_PASSWORD = "Qwertyuiop1."



CAPITAL = 100.0  # Торговый капитал в USDT
RISK_PCT = 1.0   # Риск на сделку в %

def setup_test_user():
    print(f"🔧 Setting up test user {TEST_USER_ID}...")
    
    # 1. Создать/обновить пользователя
    execute_write_query("""
        INSERT OR REPLACE INTO users 
        (user_id, username, join_date, token_balance, is_copytrading_enabled, status) 
        VALUES (?, 'test_local', datetime('now'), 1000.0, 1, 'active')
    """, (TEST_USER_ID,))
    print("   ✅ User created/updated")
    
    # 2. Добавить OKX подключение для CGT (Spot)
    save_user_exchange(
        user_id=TEST_USER_ID,
        exchange='okx',
        api_key=OKX_API_KEY,
        secret_key=OKX_SECRET,
        passphrase=OKX_PASSWORD,
        strategy='cgt'
    )
    print("   ✅ OKX exchange connected")
    
    # 3. Установить капитал и риск
    execute_write_query("""
        UPDATE user_exchanges 
        SET reserved_amount = ?, risk_pct = ?
        WHERE user_id = ? AND exchange_name = 'okx'
    """, (CAPITAL, RISK_PCT, TEST_USER_ID))
    print(f"   ✅ Capital set to ${CAPITAL:.2f}, Risk {RISK_PCT}%")
    
    print(f"\n🎉 Test user {TEST_USER_ID} configured successfully!")
    print(f"\n📋 Configuration:")
    print(f"   User ID: {TEST_USER_ID}")
    print(f"   Exchange: OKX (Spot)")
    print(f"   Strategy: CGT")
    print(f"   Capital: ${CAPITAL:.2f}")
    print(f"   Risk per Trade: {RISK_PCT}%")
    print(f"   Max Trade Size: ${CAPITAL * RISK_PCT / 100:.2f}")
    
    print(f"\n▶️ Next Steps:")
    print(f"   1. Run: python3 master_tracker.py")
    print(f"   2. Monitor: watch -n 3 'python3 investigation.py copies {TEST_USER_ID}'")

if __name__ == "__main__":
    # Validation
    if OKX_API_KEY == "YOUR_API_KEY_HERE":
        print("❌ ERROR: Please edit test_setup.py and set your OKX API credentials!")
        exit(1)
    
    setup_test_user()
