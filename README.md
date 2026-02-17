# Black Aladdin — Crypto Copy-Trading Telegram Bot

Telegram-бот с Mini App для автоматического копирования сделок мастер-трейдеров на BingX (фьючерсы) и OKX (спот). Включает реферальную систему, биллинг, AI-анализатор графиков и ежедневные PnL-отчёты.

---

## Архитектура

Система состоит из **3 независимых процессов**, которые работают параллельно:

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   bot.py     │     │   server.py      │     │ master_tracker.py│
│  Telegram    │     │  FastAPI (8000)   │     │  WebSocket +     │
│  Bot + Jobs  │     │  REST API для     │     │  Trade Copier    │
│              │     │  Mini App         │     │  (Worker)        │
└──────┬───────┘     └────────┬─────────┘     └────────┬─────────┘
       │                      │                        │
       └──────────────────────┴────────────────────────┘
                              │
                     ┌────────▼────────┐
                     │   database.py   │
                     │   SQLite (DB)   │
                     └─────────────────┘
```

---

## Ключевые файлы

### Ядро системы

| Файл | Описание |
|------|----------|
| **`bot.py`** | Главный Telegram-бот. Все хэндлеры команд (`/start`, `/menu`, настройки, подписки, промокоды, админка). Scheduler-задачи (ежедневная проверка подписок, PnL-отчёты). ~2500 строк. |
| **`server.py`** | FastAPI-сервер (порт 8000). REST API для Mini App: получение данных юзера, подключение/отключение бирж, сохранение монет, анализ графиков, платежи (CryptAPI). Раздаёт статику `webapp/`. |
| **`master_tracker.py`** | WebSocket-слушатели для BingX и OKX. Ловит ордера мастер-трейдера в реальном времени, записывает в БД (`master_orders`), ставит в очередь для Worker'а. Запускает `TradeCopier` из `worker.py`. |
| **`worker.py`** | `TradeCopier` — потребляет события из очереди и исполняет сделки на аккаунтах клиентов (BingX futures / OKX spot). Логика хедж-мода, leverage, PnL-расчёт, биллинг (40% fee), MLM-реферальные выплаты. |
| **`database.py`** | SQLite ORM. Все таблицы, миграции, CRUD-операции. Шифрование API-ключей через Fernet. |
| **`daily_report.py`** | Генерация ежедневных PnL-отчётов в виде PNG-картинок (Pillow). Отправка через Telegram в 07:00 UTC. |

### Вспомогательные

| Файл | Описание |
|------|----------|
| `chart_analyzer.py` | Обработка загруженных графиков (OpenCV, Tesseract OCR). |
| `core_analyzer.py` | AI-анализ графиков через OpenRouter (LLM). Генерирует сигналы: вход, цели, стоп-лосс. |
| `llm_explainer.py` | Текстовые объяснения торговых сигналов через LLM. |
| `exchange_utils.py` | Утилиты для работы с биржами (валидация, баланс). |
| `tx_verifier.py` | Верификация BEP-20 транзакций через BSCScan. |
| `webhook_server.py` | Обработка вебхуков от CryptAPI (USDT пополнения). |
| `monitor.py` | Мониторинг состояния WebSocket-подключений. |
| `scanner.py` | Сканер рынков (вспомогательный). |

### Утилиты / отладка (можно игнорировать)

`check_api_keys.py`, `check_bingx.py`, `check_leverage.py`, `check_logs.py`, `check_master_orders.py`, `check_referrals.py`, `debug_okx.py`, `fix_bingx_strategy.py`, `fix_db.py`, `fix_db_keys.py`, `fix_reserve.py`, `investigation.py`, `migrate_ratner.py`, `test.py`, `test_integration_flow.py`, `test_setup.py`

---

## Структура директорий

```
crypto_aladdin/
├── bot.py                  # Telegram-бот
├── server.py               # FastAPI REST API
├── master_tracker.py       # WebSocket + Worker
├── worker.py               # Копировщик сделок
├── database.py             # SQLite + ORM
├── daily_report.py         # Ежедневные PnL-отчёты
├── chart_analyzer.py       # OCR графиков
├── core_analyzer.py        # AI-анализ
├── llm_explainer.py        # LLM объяснения
├── exchange_utils.py       # Утилиты бирж
├── tx_verifier.py          # BEP-20 верификация
├── webhook_server.py       # CryptAPI вебхуки
├── .env                    # 🔑 Все ключи и токены
├── requirements.txt        # Python зависимости
├── Dockerfile              # Docker-образ
├── run_all.sh              # Локальный запуск (macOS)
│
├── webapp/                 # Telegram Mini App (фронтенд)
│   ├── index.html          # Главная страница (SPA)
│   ├── script.js           # Вся логика (~3200 строк)
│   ├── style.css           # Основные стили
│   ├── settings_styles.css # Стили настроек
│   ├── copytrading_styles.css
│   ├── coin_config_styles.css
│   ├── dashboard_styles.css
│   ├── lamp.png            # Фон
│   ├── logo_bots/          # Иконки бирж
│   └── coin_img/           # Иконки монет
│
├── locales/                # Переводы (i18n)
│   ├── en.json             # English
│   ├── ru.json             # Русский
│   └── uk.json             # Українська
│
└── assets/                 # Ресурсы для PnL-отчётов
    ├── coins/              # 13 иконок монет (PNG)
    ├── fonts/              # Montserrat Bold + Regular (TTF)
    └── logo.png            # Логотип
```

---

## База данных (SQLite)

Файл: `aladdin.db` (production) / `aladdin_dev.db` (dev)

| Таблица | Назначение |
|---------|-----------|
| **`users`** | Юзеры: баланс (USDT + UNC), подписка, реферальная цепочка, язык, статус копитрейдинга |
| **`user_exchanges`** | Подключённые биржи: API-ключи (зашифрованы Fernet), стратегия (`ratner`/`cgt`), reserve, risk_pct |
| **`coin_configs`** | Настройки монет для OKX CGT (per-coin capital + risk) |
| **`master_orders`** | Все ордера мастер-трейдера (BingX/OKX) |
| **`client_copies`** | Копии сделок клиентов с PnL (для отчётов и биллинга) |
| **`copied_trades`** | Legacy-таблица открытых позиций клиентов |
| **`master_positions`** | Текущие позиции мастера |
| **`transactions`** | История транзакций (пополнения, выводы) |
| **`used_tx_hashes`** | Использованные хэши транзакций (защита от дублей) |
| **`withdrawals`** | Запросы на вывод |
| **`promo_codes`** | Промокоды |

---

## Переменные окружения (.env)

```bash
# === Telegram ===
TELEGRAM_TOKEN=            # Токен бота от @BotFather
BOT_USERNAME=              # Username бота (без @)
CHANNEL_ID=                # ID канала для уведомлений
ADMIN_USER_ID=             # Telegram ID админа

# === Mini App ===
WEBAPP_URL=                # URL фронтенда (ngrok для dev, домен для prod)

# === BingX Master (Futures) ===
BINGX_MASTER_KEY=          # API Key мастер-аккаунта BingX
BINGX_MASTER_SECRET=       # Secret Key мастер-аккаунта BingX

# === OKX Master (Spot) ===
OKX_MASTER_KEY=            # API Key мастер-аккаунта OKX
OKX_MASTER_SECRET=         # Secret Key мастер-аккаунта OKX
OKX_MASTER_PASSWORD=       # Passphrase мастер-аккаунта OKX

# === AI ===
OPENROUTER_API_KEY=        # Ключ OpenRouter для AI-анализа графиков
OPENROUTER_BASE_URL=       # https://openrouter.ai/api/v1

# === Платежи ===
BSCSCAN_API_KEY=           # BSCScan API для верификации BEP-20
YOUR_WALLET_ADDRESS=       # Кошелёк для приёма USDT (BEP-20)
PAYMENT_ENABLED=           # true / false

# === Безопасность ===
FERNET_KEY=                # Ключ шифрования API-ключей клиентов

# === Не используется (legacy) ===
BINANCE_MASTER_KEY=
BINANCE_MASTER_SECRET=
BYBIT_MASTER_KEY=
BYBIT_MASTER_SECRET=
CRYPTO_PANIC_API_KEY=
```

---

## Стратегии копитрейдинга

| Стратегия | Биржа | Тип | Код в БД |
|-----------|-------|-----|----------|
| **BingBot** | BingX | Futures (leverage 4x, hedge mode) | `ratner` |
| **TradeMax (CGT)** | OKX | Spot (per-coin configs) | `cgt` |

---

## Биллинг

- **Performance Fee**: 40% от чистой прибыли (после вычета биржевых комиссий ~0.1%)
- **UNC Balance**: приоритетная оплата (при наличии UNC-баланса — реферальные не начисляются)
- **MLM Referral**: 3 уровня — 20% / 7% / 3% от комиссии платформы (только при оплате USDT)

---

## Деплой (Production)

### Сервер
- **ОС**: Ubuntu/Debian
- **IP**: `167.99.130.80`
- **Path**: `/opt/aladdin-bot/`
- **Process Manager**: Supervisor

### Supervisor — 3 процесса

```bash
# Telegram-бот
[program:aladdin-tg]
command=python3 /opt/aladdin-bot/bot.py

# FastAPI-сервер
[program:aladdin-payment]
command=uvicorn server:app --host 0.0.0.0 --port 8000
directory=/opt/aladdin-bot

# Master Tracker + Worker
[program:aladdin-master]
command=python3 /opt/aladdin-bot/master_tracker.py
```

### Обновление на сервере

```bash
cd /opt/aladdin-bot
git pull origin main
pip3 install -r requirements.txt --break-system-packages
supervisorctl restart all
```

### Полезные команды

```bash
# Статус процессов
supervisorctl status

# Логи в реальном времени
supervisorctl tail -f aladdin-master
supervisorctl tail -f aladdin-tg
supervisorctl tail -f aladdin-payment

# Проверить WebSocket-подключения
supervisorctl tail -f aladdin-master | grep "CONNECTED\|RECONNECT"

# Проверить последние сделки
sqlite3 /opt/aladdin-bot/aladdin.db "SELECT * FROM client_copies ORDER BY copy_id DESC LIMIT 10;"

# Проверить мастер-ордера
sqlite3 /opt/aladdin-bot/aladdin.db "SELECT * FROM master_orders ORDER BY order_id DESC LIMIT 10;"

# Проверить подключённых юзеров
sqlite3 /opt/aladdin-bot/aladdin.db "SELECT u.user_id, ue.exchange_name, ue.strategy, ue.is_active FROM user_exchanges ue JOIN users u ON ue.user_id = u.user_id WHERE ue.is_active = 1;"
```

---

## Локальный запуск (macOS)

```bash
# 1. Клонировать репо
git clone <repo-url>
cd crypto_aladdin

# 2. Установить зависимости
pip3 install -r requirements.txt

# 3. Настроить .env (скопировать и заполнить)
cp .env.example .env

# 4. Запустить ngrok для Mini App
ngrok http 8000
# Скопировать URL в .env → WEBAPP_URL

# 5. Запустить все 3 процесса
bash run_all.sh
# или вручную в 3 терминалах:
python3 server.py      # терминал 1
python3 bot.py         # терминал 2
python3 master_tracker.py  # терминал 3
```

---

## Зависимости (requirements.txt)

```
python-telegram-bot[job-queue]   # Telegram Bot API
python-dotenv                    # .env
ccxt                             # Биржевые API (BingX, OKX)
requests                         # HTTP
websocket-client                 # WebSocket для BingX
cryptography                     # Fernet шифрование
Pillow                           # Генерация PnL-отчётов
pandas / pandas_ta               # Технический анализ
opencv-python / scikit-image     # Обработка графиков
pytesseract                      # OCR
openai                           # LLM (через OpenRouter)
```

---

## Поток копирования сделки (BingX)

```
1. Мастер открывает сделку на BingX
         ↓
2. WebSocket (master_tracker.py) ловит ORDER_UPDATE
         ↓
3. Сохраняет master_order в БД
         ↓
4. Кладёт событие в Queue → Worker (TradeCopier)
         ↓
5. Worker получает список активных юзеров (strategy=ratner)
         ↓
6. Для каждого юзера: рассчитать qty (% от баланса) → выставить ордер на BingX юзера
         ↓
7. Записать в copied_trades + client_copies
         ↓
8. При закрытии: PnL-расчёт → 40% fee → MLM → уведомление юзеру
```

---

## Важные замечания

1. **API-ключи клиентов** зашифрованы Fernet (`FERNET_KEY` в `.env`). Без этого ключа данные нечитаемы.
2. **SQLite** — одна БД для всего. При масштабировании стоит мигрировать на PostgreSQL.
3. **Mini App URL** (`WEBAPP_URL`) должен совпадать с тем, что указан в @BotFather → Web App Settings.
4. **IP сервера** (167.99.130.80) должен быть в whitelist API-ключей всех клиентских бирж.
5. **Supervisor** автоматически перезапускает упавшие процессы.
6. **Ежедневные отчёты** отправляются в 07:00 UTC (08:00 CET) только юзерам с положительным PnL.
