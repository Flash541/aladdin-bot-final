# Локальное Тестирование Investigation System

## Шаг 1: Подготовка Тестового Клиента

### 1.1 Добавить тестовый аккаунт в БД

```python
# test_setup.py
from database import execute_write_query, save_user_exchange

# Твой Telegram ID (тестовый клиент)
TEST_USER_ID = 502483421  # Замени на свой ID

# 1. Создать пользователя если нет
execute_write_query("""
    INSERT OR IGNORE INTO users 
    (user_id, username, join_date, token_balance, is_copytrading_enabled, status) 
    VALUES (?, 'test_user', datetime('now'), 1000.0, 1, 'active')
""", (TEST_USER_ID,))

# 2. Добавить OKX подключение для CGT (Spot)
save_user_exchange(
    user_id=TEST_USER_ID,
    exchange='okx',
    api_key='YOUR_OKX_API_KEY',
    secret_key='YOUR_OKX_SECRET',
    passphrase='YOUR_OKX_PASSWORD',
    strategy='cgt'
)

# 3. Установить капитал и риск
execute_write_query("""
    UPDATE user_exchanges 
    SET reserved_amount = 100.0, risk_pct = 1.0
    WHERE user_id = ? AND exchange_name = 'okx'
""", (TEST_USER_ID,))

print(f"✅ Test user {TEST_USER_ID} configured!")
print("   Strategy: CGT (Spot)")
print("   Capital: $100")
print("   Risk: 1% per trade")
```

Запусти:
```bash
python3 test_setup.py
```

---

## Шаг 2: Запуск Системы Локально

### 2.1 Терминал 1: Master Tracker + Worker

```bash
cd /Users/kamronbekjurabaev/Desktop/crypto_aladdin
python3 master_tracker.py
```

**Что будешь видеть:**
```
🎧 OKX Listener: WEBSOCKET REAL-TIME
✅ OKX WebSocket: Authenticated!
🔔 OKX WEBSOCKET: 21:15:30 | BTC/USDT | BUY | $1000.50
   📝 [MASTER ORDER] ID=1 BUY BTC/USDT @ $85000
🚀 [QUEUE] SIGNAL (OKX SPOT): buy BTC/USDT | Ratio: 10.50%
⚡ [WORKER] Executing (cgt) for 1 connections...
   🚀 User 502483421 [OKX SPOT]: BUY 0.001176 BTC/USDT for $100.00 (Risk 1%)
   ✅ [CLIENT COPY] User 502483421: BUY 0.001176 BTC/USDT @ $85000.00
   ✅ User 502483421 Filled: 0.001176 @ 85000.00
```

---

## Шаг 3: Мониторинг в Реальном Времени

### 3.1 Терминал 2: Watch Investigation

```bash
# Автоматическое обновление каждые 3 секунды
watch -n 3 'python3 investigation.py copies 502483421'
```

**Вывод:**
```
💼 CLIENT COPIES:
╒══════╤═════════════╤═══════════╤════════╤══════════╤════════╤══════════╤══════════╤══════════╤══════════╤══════════╕
│   ID │        User │ Symbol    │ Side   │ Entry    │ Exit   │      Qty │ PnL      │ Opened   │ Closed   │ Status   │
╞══════╪═════════════╪═══════════╪════════╪══════════╪════════╪══════════╪══════════╪══════════╪══════════╪══════════╡
│    1 │   502483421 │ BTC/USDT  │ BUY    │ $85000   │ -      │   0.0012 │ -        │ 21:15:30 │ -        │ open     │
╘══════╧═════════════╧═══════════╧════════╧══════════╧════════╧══════════╧══════════╧══════════╧══════════╧══════════╛

📈 SUMMARY:
  Total Trades: 1
  Open: 1 | Closed: 0
  Total PnL: $0.00
```

### 3.2 Одноразовые Проверки

```bash
# Показать последние мастер ордера
python3 investigation.py master

# Проверить integrity (orphan sells)
python3 investigation.py check

# Твои копии
python3 investigation.py copies 502483421
```

---

## Шаг 4: Симуляция Сценариев

### Сценарий 1: Нормальная Сделка (BUY → SELL)

**Ожидания:**
1. Мастер BUY → Клиент BUY (записано в `client_copies`)
2. Мастер SELL → Клиент SELL (PnL рассчитан, статус = `closed`)

**Проверка:**
```bash
python3 investigation.py copies 502483421
# Должно показать:
# - Entry Price: $85000
# - Exit Price: $85500 (если прибыль)
# - PnL: +$0.58 (пример)
# - Status: closed
```

---

### Сценарий 2: Late Entry Protection

**Симуляция:**
1. Мастер уже имеет открытую позицию BTC
2. Запусти `test_setup.py` (подключаешь "нового" клиента)
3. Мастер закрывает BTC

**Ожидания:**
```
⚠️ [LATE ENTRY PROTECTION] User 502483421: SKIP SELL (no open buy for BTC/USDT)
```

**Проверка:**
```bash
python3 investigation.py check
# Должно показать:
# ✅ No orphan sells found
```

---

## Шаг 5: Проверка PnL Calculation

### Ручная Проверка Формулы

Когда мастер закрывает сделку, в логах увидишь:

```
💰 [CLOSE COPY] User 502483421: PnL = $0.58
💰 [BILLING] User 502483421, Entry: 85000, Exit: 85500, Qty: 0.001176
💰 [BILLING] PnL: 0.588000 USDT
```

**Формула:**
```
PnL = (Exit - Entry) * Quantity
    = (85500 - 85000) * 0.001176
    = 500 * 0.001176
    = $0.588
```

**Проверь в БД:**
```bash
sqlite3 aladdin_dev.db "SELECT * FROM client_copies WHERE user_id=502483421 ORDER BY copy_id DESC LIMIT 1"
```

---

## Шаг 6: Real-Time Dashboard (Optional)

### Простой Monitoring Script

```python
# monitor.py
import time
import os
from database import get_investigation_report

def clear_screen():
    os.system('clear')

while True:
    clear_screen()
    print("=" * 80)
    print("📊 LIVE TRADING MONITOR")
    print("=" * 80)
    
    report = get_investigation_report(user_id=502483421, limit=10)
    
    print(f"\n📈 Your Copies: {report['stats']['total_trades']}")
    print(f"   Open: {report['stats']['open_trades']} | Closed: {report['stats']['closed_trades']}")
    print(f"   Total PnL: ${report['stats']['total_pnl']:.2f}")
    
    if report['copies']:
        print("\n🔄 Recent Trades:")
        for c in report['copies'][:5]:
            status_icon = "🟢" if c['status'] == 'open' else "🔴"
            pnl_str = f"${c['profit_loss']:.2f}" if c['profit_loss'] else "-"
            print(f"  {status_icon} {c['symbol']} {c['side'].upper()} @ ${c['entry_price']:.2f} | PnL: {pnl_str}")
    
    print(f"\n🕐 Last update: {time.strftime('%H:%M:%S')}")
    print("Press Ctrl+C to exit")
    
    time.sleep(5)  # Update every 5 seconds
```

Запуск:
```bash
python3 monitor.py
```

---

## Common Issues & Solutions

### Issue 1: "No connections found"
```
⚡ [WORKER] Executing (cgt) for 0 connections...
```

**Solution:**
```bash
sqlite3 aladdin_dev.db "SELECT * FROM user_exchanges WHERE user_id=502483421"
# Проверь что is_active=1 и strategy='cgt'
```

---

### Issue 2: Клиент не копирует сделки

**Checklist:**
```bash
# 1. Check user token balance
sqlite3 aladdin_dev.db "SELECT token_balance FROM users WHERE user_id=502483421"
# Должно быть > 0

# 2. Check copytrading enabled
sqlite3 aladdin_dev.db "SELECT is_copytrading_enabled FROM users WHERE user_id=502483421"
# Должно быть 1

# 3. Check API keys
python3 -c "from database import get_user_decrypted_keys; print(get_user_decrypted_keys(502483421, 'okx'))"
```

---

## Success Criteria ✅

После тестирования должно быть:

- [ ] Мастер ордер записан в `master_orders`
- [ ] Клиент скопировал сделку в `client_copies`  
- [ ] PnL рассчитан правильно (формула совпадает)
- [ ] Late entry protection работает (skip sell without buy)
- [ ] `investigation.py check` показывает ✅ No orphan sells

---

## Quick Commands Reference

```bash
# Setup
python3 test_setup.py

# Start system
python3 master_tracker.py

# Monitor (auto-refresh)
watch -n 3 'python3 investigation.py copies 502483421'

# One-time checks
python3 investigation.py master
python3 investigation.py copies 502483421
python3 investigation.py check

# Manual DB check
sqlite3 aladdin_dev.db "SELECT * FROM client_copies WHERE user_id=502483421"
```
