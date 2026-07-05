"""Quick test of the correct /v4/candles endpoint."""

import asyncio
import aiohttp
import json


async def test_candles():
    """Test the correct candles endpoint."""
    
    url = "https://indexer.dydx.trade/v4/candles"
    params = {
        "market": "BTC-USD",
        "resolution": "1HOUR",
        "limit": 10
    }
    
    print("=" * 70)
    print("Testing /v4/candles endpoint")
    print("=" * 70)
    print(f"\nURL: {url}")
    print(f"Params: {params}\n")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                status = response.status
                text = await response.text()
                
                print(f"Status: {status}")
                
                if status == 200:
                    data = json.loads(text)
                    print(f"✅ SUCCESS!\n")
                    print(f"Response keys: {list(data.keys())}")
                    
                    if "candles" in data:
                        candles = data["candles"]
                        print(f"Number of candles: {len(candles)}")
                        if candles:
                            print(f"\nFirst candle:")
                            print(json.dumps(candles[0], indent=2))
                else:
                    print(f"❌ HTTP {status}")
                    print(f"Response: {text[:200]}")
    
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_candles())
