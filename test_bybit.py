import os
from dotenv import load_dotenv
from pybit.unified_trading import HTTP
from pybit.exceptions import InvalidRequestError, FailedRequestError

# Загружаем переменные из .env
load_dotenv()

def check_bybit_connection():
    api_key = os.getenv("BYBIT_MASTER_KEY")
    api_secret = os.getenv("BYBIT_MASTER_SECRET")

    print("--- 🔍 BYBIT KEYS CHECKER ---")

    if not api_key or not api_secret:
        print("❌ ОШИБКА: Ключи не найдены в .env файле.")
        print("Убедитесь, что прописаны BYBIT_MASTER_KEY и BYBIT_MASTER_SECRET")
        return

    print(f"🔑 API Key: {api_key[:6]}******")
    print(f"🔒 Secret:  {api_secret[:6]}******")
    
    try:
        # Инициализация сессии
        # testnet=False означает, что мы проверяем РЕАЛЬНЫЙ Bybit, а не демо.
        session = HTTP(
            testnet=False,
            api_key=api_key,
            api_secret=api_secret,
        )

        print("\n📡 Попытка подключения к Bybit API...")

        # 1. Проверка информации о ключе (Permissions)
        key_info = session.get_api_key_information()
        
        # Если метод выше не вызвал ошибку, значит подпись верна
        print("✅ АВТОРИЗАЦИЯ УСПЕШНА!")
        
        permissions = key_info.get('result', {}).get('permissions', {})
        print(f"📝 Права доступа ключа: {permissions}")

        # 2. Проверка доступа к кошельку (Баланс)
        # accountType="UNIFIED" используется для Единых торговых аккаунтов (сейчас стандарт)
        # Если у вас старый аккаунт, можно попробовать без этого параметра или "CONTRACT"
        try:
            balance_data = session.get_wallet_balance(accountType="UNIFIED")
            
            # Если у вас не Единый аккаунт, код может упасть здесь, попробуем перехватить
            if balance_data['retCode'] == 0:
                coins = balance_data['result']['list'][0]['coin']
                usdt_balance = next((item for item in coins if item["coin"] == "USDT"), None)
                
                if usdt_balance:
                    print(f"💰 Баланс USDT: {usdt_balance['walletBalance']}")
                else:
                    print("💰 Баланс: Данные получены, но USDT не найден или равен 0.")
            else:
                print(f"⚠️ Ошибка получения баланса: {balance_data['retMsg']}")

        except InvalidRequestError as e:
            # Часто бывает, если аккаунт не Unified, а Классический
            print("⚠️ Не удалось получить баланс через UNIFIED (возможно, классический аккаунт).")
            print(f"   Ответ биржи: {e}")

    except InvalidRequestError as e:
        print("\n❌ КЛЮЧИ НЕВАЛИДНЫ!")
        print(f"Причина: {e.message}")
    except FailedRequestError as e:
        print("\n❌ ОШИБКА СЕТИ ИЛИ API:")
        print(f"Причина: {e.message}")
    except Exception as e:
        print(f"\n❌ НЕИЗВЕСТНАЯ ОШИБКА: {e}")

if __name__ == "__main__":
    check_bybit_connection()