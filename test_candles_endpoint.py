"""Test different parameter formats for the candles endpoint."""

import asyncio
import aiohttp
import json


async def test_candles_variations():
    """Test various parameter formats for candles endpoint."""
    
    base_url = "https://indexer.dydx.trade"
    
    test_cases = [
        # Different parameter names
        ("/v4/candles", {"market": "BTC-USD", "resolution": "1HOUR", "limit": "10"}),
        ("/v4/candles", {"ticker": "BTC-USD", "resolution": "1HOUR", "limit": "10"}),
        ("/v4/candles", {"symbol": "BTC-USD", "resolution": "1HOUR"}),
        
        # Different resolution formats
        ("/v4/candles", {"market": "BTC-USD", "resolution": "1h", "limit": "10"}),
        ("/v4/candles", {"market": "BTC-USD", "resolution": "1H", "limit": "10"}),
        
        # Check if it's nested under markets
        ("/v4/markets/candles", {"market": "BTC-USD", "resolution": "1HOUR"}),
        
        # Try with market in path
        ("/v4/candles/BTC-USD", {"resolution": "1HOUR", "limit": "10"}),
        
        # Try historic endpoint
        ("/v4/historicalCandles", {"market": "BTC-USD", "resolution": "1HOUR"}),
        
        # Try ohlc
        ("/v4/ohlc", {"market": "BTC-USD", "resolution": "1HOUR"}),
    ]
    
    print("=" * 70)
    print("Testing Candles Endpoint Variations")
    print("=" * 70)
    
    async with aiohttp.ClientSession() as session:
        for path, params in test_cases:
            url = base_url + path
            try:
                print(f"\n[*] {path}")
                print(f"    Params: {params}")
                
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    status = response.status
                    text = await response.text()
                    
                    if status == 200:
                        print(f"    ✅ HTTP {status} - SUCCESS")
                        data = json.loads(text)
                        print(f"    Keys: {list(data.keys())}")
                        if "candles" in data:
                            print(f"    Candles: {len(data.get('candles', []))} items")
                    else:
                        print(f"    ❌ HTTP {status}")
            
            except asyncio.TimeoutError:
                print(f"    ❌ TIMEOUT")
            except Exception as e:
                print(f"    ❌ ERROR: {str(e)[:60]}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(test_candles_variations())
