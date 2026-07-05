"""Quick diagnostic script to test dYdX API endpoints."""

import asyncio
import aiohttp
import json


async def test_endpoints():
    """Test various dYdX API endpoints to find working ones."""
    
    endpoints_to_test = [
        # Official indexer
        ("https://indexer.dydx.trade/v4/perpetualMarkets", "Official - List markets"),
        ("https://indexer.dydx.trade/v4/perpetualMarkets/BTC-USD/candles", "Official - BTC candles"),
        
        # Alternative indexers
        ("https://dydx-mainnet-lcd.allthatnode.com:1317/swagger/", "Allthatnode REST"),
        ("https://indexer.dydx.exchange/v4/perpetualMarkets", "Alternative domain - perpetualMarkets"),
        
        # Try different base paths
        ("https://indexer.dydx.trade/perpetualMarkets/BTC-USD/candles", "No /v4 prefix"),
        ("https://indexer.dydx.trade/api/v4/perpetualMarkets", "With /api prefix"),
    ]
    
    print("=" * 70)
    print("Testing dYdX API Endpoints")
    print("=" * 70)
    
    async with aiohttp.ClientSession() as session:
        for url, description in endpoints_to_test:
            try:
                print(f"\n[*] {description}")
                print(f"    URL: {url}")
                
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    status = response.status
                    text = await response.text()
                    
                    if status == 200:
                        print(f"    ✅ HTTP {status} - SUCCESS")
                        try:
                            data = json.loads(text)
                            print(f"    Response preview: {str(data)[:100]}...")
                        except:
                            print(f"    Response: {text[:100]}...")
                    else:
                        print(f"    ❌ HTTP {status}")
                        print(f"    Error: {text[:100]}")
            
            except asyncio.TimeoutError:
                print(f"    ❌ TIMEOUT (5s)")
            except Exception as e:
                print(f"    ❌ ERROR: {str(e)[:100]}")
    
    print("\n" + "=" * 70)
    print("Diagnosis complete")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_endpoints())
