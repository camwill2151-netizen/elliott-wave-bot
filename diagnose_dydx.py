"""Quick diagnostic script to test dYdX candles endpoint variations."""

import asyncio
import aiohttp
import json


async def test_candles_endpoints():
    """Test various candle endpoint formats."""
    
    endpoints_to_test = [
        # Based on what works for markets
        ("https://indexer.dydx.trade/v4/perpetualMarkets/BTC-USD/candles", "Original format"),
        ("https://indexer.dydx.trade/v4/perpetualMarkets/BTC-USD/candles?resolution=1HOUR&limit=10", "With query params"),
        
        # Try sparklines
        ("https://indexer.dydx.trade/v4/perpetualMarkets/sparklines", "Sparklines endpoint"),
        
        # Try trades instead
        ("https://indexer.dydx.trade/v4/perpetualMarkets/BTC-USD/trades", "Trades endpoint"),
        
        # Try orderbook
        ("https://indexer.dydx.trade/v4/perpetualMarkets/BTC-USD/orderbook", "Orderbook endpoint"),
        
        # Try funding
        ("https://indexer.dydx.trade/v4/perpetualMarkets/BTC-USD/fundingRate", "Funding endpoint"),
    ]
    
    print("=" * 70)
    print("Testing dYdX Candles & Market Data Endpoints")
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
                            # Show structure
                            if isinstance(data, dict):
                                print(f"    Keys: {list(data.keys())}")
                                for key in list(data.keys())[:3]:
                                    val = data[key]
                                    if isinstance(val, list):
                                        print(f"      - {key}: list[{len(val)}]")
                                    elif isinstance(val, dict):
                                        print(f"      - {key}: dict with keys {list(val.keys())[:3]}")
                                    else:
                                        print(f"      - {key}: {str(val)[:50]}")
                        except:
                            print(f"    Response: {text[:150]}...")
                    else:
                        print(f"    ❌ HTTP {status}")
                        if text:
                            print(f"    Error: {text[:100]}")
            
            except asyncio.TimeoutError:
                print(f"    ❌ TIMEOUT (5s)")
            except Exception as e:
                print(f"    ❌ ERROR: {str(e)[:100]}")
    
    print("\n" + "=" * 70)
    print("Diagnosis complete")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_candles_endpoints())
