import asyncio
import ccxt.async_support as ccxt
import sys

# OKX Credentials provided by user
API_KEY = "35da235c-fa34-4717-b392-7e2113703c7d"
SECRET = "FED6775506E418C26A9B45A6434E3591"
PASSWORD = "Qwertyuiop1."

async def test_okx_connection():
    print(f"🔄 Testing OKX Connection...")
    print(f"API Key: {API_KEY[:4]}...{API_KEY[-4:]}")
    
    try:
        exchange = ccxt.okx({
            'apiKey': API_KEY,
            'secret': SECRET,
            'password': PASSWORD,
            'options': {'defaultType': 'spot'}
        })
        
        # 1. Fetch Balance
        print("\n1. Fetching Balance...")
        balance = await exchange.fetch_balance()
        
        usdt_bal = 0
        if 'USDT' in balance:
            if 'free' in balance['USDT']:
                usdt_bal = float(balance['USDT']['free'])
        
        print(f"✅ Balance Fetch Success!")
        print(f"💰 USDT Free: {usdt_bal}")
        
        # 2. Check Minimum Requirement ($5)
        if usdt_bal < 5:
            print(f"⚠️ WARNING: Balance ${usdt_bal} is less than $5 minimum!")
        else:
            print(f"✅ Balance matches requirement (>= $5)")
            
        await exchange.close()
        return True
        
    except ccxt.AuthenticationError as e:
        print(f"\n❌ AUTHENTICATION ERROR: Invalid API Key, Secret or Password.")
        print(f"Error details: {e}")
        return False
    except Exception as e:
        print(f"\n❌ CONNECTION ERROR: {e}")
        return False

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_okx_connection())
