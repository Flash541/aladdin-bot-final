import asyncio
import ccxt
from binance.um_futures import UMFutures

async def fetch_exchange_balance_safe(exchange_name, api_key, secret, passphrase=None):
    """Helper to fetch USDT balance safely via thread."""
    exchange_name = exchange_name.lower()
    
    def _fetch():
        try:
            if exchange_name == 'binance':
                c = UMFutures(key=api_key, secret=secret, base_url="https://fapi.binance.com")
                acc = c.account()
                # If USDT not found, balance is 0.0 (Status: Connected)
                return float(next((a['walletBalance'] for a in acc['assets'] if a['asset']=='USDT'), 0))
            
            elif exchange_name == 'okx':
                ex = ccxt.okx({
                    'apiKey': api_key, 'secret': secret, 'password': passphrase, 
                    'options': {'defaultType': 'spot'} # OKX spot for TradeMax
                })
                bal = ex.fetch_balance()
                # Handle possible missing keys if wallet empty
                if 'USDT' in bal and 'free' in bal['USDT']:
                     return float(bal['USDT']['free'])
                return 0.0

            else: # bybit, bingx
                ex_class = getattr(ccxt, exchange_name)
                options = {}
                if exchange_name == 'bingx': 
                    options['defaultType'] = 'swap' # Start with swap for BingBot
                elif exchange_name == 'bybit':
                    options['defaultType'] = 'future'
                
                ex = ex_class({'apiKey': api_key, 'secret': secret, 'options': options})
                # ex.load_markets() # Optional: verify connectivity
                bal = ex.fetch_balance() 
                
                # Check structure
                if 'USDT' in bal:
                    if 'total' in bal['USDT']: return float(bal['USDT']['total'])
                    if 'free' in bal['USDT']: return float(bal['USDT']['free'])
                
                # If we got here, fetch_balance succeeded but no USDT found -> Success (0.0)
                return 0.0

        except (ccxt.AuthenticationError, ccxt.PermissionDenied, ccxt.AccountSuspended) as e:
            print(f"🔐 Auth Error ({exchange_name}): {e}")
            return None # Invalid Keys
        except Exception as e:
            print(f"❌ Connection Error ({exchange_name}): {e}")
            # If it's a generic logic error but not Auth, it might be connectivity. 
            # We return None to be safe, but log it.
            return None
            
    return await asyncio.to_thread(_fetch)

async def validate_exchange_credentials(exchange_name, api_key, secret, passphrase=None):
    """
    Validates API and returns balance info if successful.
    Returns: {'total': float} or None
    """
    bal = await fetch_exchange_balance_safe(exchange_name, api_key, secret, passphrase)
    
    if bal is None:
        print(f"❌ Validation Failed ({exchange_name}): Invalid API keys or connection error")
        return None
    
    # We still want to ensure at least some connectivity/balance logic if needed, 
    # but the strict $100 check is done in the caller for trading eligibility.
    # The $5 check here was for "is connection valid". 
    # Let's keep a minimal check for validity but return the full object.
    
    print(f"✅ Validation Success ({exchange_name}): Balance ${bal:.2f}")
    return {'total': bal}

