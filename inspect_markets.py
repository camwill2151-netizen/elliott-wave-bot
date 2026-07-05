"""Inspect what data is available in the perpetualMarkets response."""

import asyncio
import aiohttp
import json


async def inspect_markets_data():
    """Fetch and inspect the perpetualMarkets response structure."""
    
    url = "https://indexer.dydx.trade/v4/perpetualMarkets"
    
    print("=" * 70)
    print("Inspecting dYdX perpetualMarkets Response")
    print("=" * 70)
    print(f"\nFetching: {url}\n")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    print(f"✅ HTTP 200 - SUCCESS\n")
                    print(f"Top-level keys: {list(data.keys())}\n")
                    
                    # Inspect markets structure
                    if "markets" in data:
                        markets = data["markets"]
                        print(f"Markets type: {type(markets)}")
                        if isinstance(markets, dict):
                            print(f"Number of markets: {len(markets)}")
                            print(f"Market IDs: {list(markets.keys())[:5]}...\n")
                            
                            # Show BTC-USD structure
                            if "BTC-USD" in markets:
                                btc = markets["BTC-USD"]
                                print("=" * 70)
                                print("BTC-USD Market Data:")
                                print("=" * 70)
                                print(json.dumps(btc, indent=2)[:1000])
                                print("\n... (truncated)")
                                
                                # Check what fields are available
                                print(f"\nAvailable fields: {list(btc.keys())}")
                else:
                    print(f"❌ HTTP {response.status}")
                    print(await response.text())
    
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(inspect_markets_data())
