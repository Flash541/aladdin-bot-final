import os
import ccxt
from dotenv import load_dotenv

load_dotenv()

def check_balance():
    print("--- 🔍 OKX BALANCE INSPECTOR ---")
    
    key = os.getenv("OKX_MASTER_KEY")
    secret = os.getenv("OKX_MASTER_SECRET")
    password = os.getenv("OKX_MASTER_PASSWORD")

    if not key:
        print("❌ Нет ключей в .env")
        return

    try:
        okx = ccxt.okx({
            'apiKey': key,
            'secret': secret,
            'password': password,
            'options': {'defaultType': 'spot'}
        })
        
        # Загружаем баланс
        bal = okx.fetch_balance()
        
        # Смотрим USDT
        if 'USDT' in bal:
            usdt = bal['USDT']
            free = float(usdt['free'])      # Доступно для торговли
            used = float(usdt['used'])      # Заморожено в ордерах
            total = float(usdt['total'])    # Всего на счету
            
            print(f"💰 USDT TOTAL (Всего):     ${total:,.2f}")
            print(f"🔒 USDT USED (В ордерах):  ${used:,.2f}  <-- Если тут не 0, значит висят лимитки")
            print(f"✅ USDT FREE (Свободно):   ${free:,.2f}  <-- Бот использует ЭТУ сумму")
        else:
            print("⚠️ USDT на счету не найдено!")

        # Проверка других монет (чтобы понять, где остальные деньги)
        print("\n--- 💼 ДРУГИЕ АКТИВЫ ---")
        for coin, amount in bal['total'].items():
            if float(amount) > 0 and coin != 'USDT':
                print(f"🔹 {coin}: {amount}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    check_balance()