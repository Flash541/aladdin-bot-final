import asyncio
import ccxt


async def fetch_exchange_balance_safe(exchange_name, api_key, secret, passphrase=None):
    """fetch USDT balance safely via thread. returns float or None on error."""
    exchange_name = exchange_name.lower()

    def _fetch():
        try:
            if exchange_name == 'okx':
                ex = ccxt.okx({
                    'apiKey': api_key, 'secret': secret, 'password': passphrase,
                    'options': {'defaultType': 'spot'}
                })
                bal = ex.fetch_balance()
                return float(bal['USDT']['free']) if 'USDT' in bal and 'free' in bal['USDT'] else 0.0

            # bingx, bybit, etc
            ex_class = getattr(ccxt, exchange_name)
            options = {}
            if exchange_name == 'bingx': options['defaultType'] = 'swap'
            elif exchange_name == 'bybit': options['defaultType'] = 'linear'

            ex = ex_class({'apiKey': api_key, 'secret': secret, 'options': options})
            bal = ex.fetch_balance()

            if 'USDT' in bal:
                if 'total' in bal['USDT']: return float(bal['USDT']['total'])
                if 'free' in bal['USDT']: return float(bal['USDT']['free'])
            return 0.0

        except (ccxt.AuthenticationError, ccxt.PermissionDenied, ccxt.AccountSuspended) as e:
            print(f"🔐 Auth Error ({exchange_name}): {e}")
            return None
        except Exception as e:
            print(f"❌ Connection Error ({exchange_name}): {e}")
            return None

    return await asyncio.to_thread(_fetch)


async def validate_exchange_credentials(exchange_name, api_key, secret, passphrase=None):
    """validate API keys, returns {'total': float} or None"""
    bal = await fetch_exchange_balance_safe(exchange_name, api_key, secret, passphrase)
    if bal is None:
        print(f"❌ Validation Failed ({exchange_name})")
        return None

    print(f"✅ Validation OK ({exchange_name}): ${bal:.2f}")
    return {'total': bal}
