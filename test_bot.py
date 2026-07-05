"""Simple test script to verify dYdX v4 bot setup."""

import asyncio
import sys


async def test_dydx_bot():
    """Test basic dYdX bot functionality."""
    
    print("=" * 70)
    print("Elliott Wave Bot - dYdX v4 Test")
    print("=" * 70)
    
    # Test 1: Import modules
    print("\n[1/4] Testing imports...")
    try:
        from src.wave_detector import WaveDetector
        from src.indicators import Indicators, SignalGenerator
        from src.dydx_connector import DydxExchangeConnector
        print("✅ All imports successful!")
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False
    
    # Test 2: Fetch market data
    print("\n[2/4] Fetching BTC-USD market data from dYdX...")
    try:
        connector = DydxExchangeConnector(network="testnet")
        data = await connector.get_price_data("BTC-USD", resolution="1HOUR", limit=50)
        
        if data.empty:
            print("❌ No market data returned")
            return False
        
        latest_price = float(data["Close"].iloc[-1])
        print(f"✅ Current BTC price: ${latest_price:,.2f}")
        print(f"   Data points: {len(data)}")
    except Exception as e:
        print(f"❌ Market data error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Detect Elliott Wave patterns
    print("\n[3/4] Testing Elliott Wave detection...")
    try:
        detector = WaveDetector()
        pattern = detector.get_latest_pattern(data["Close"])
        
        if pattern:
            print(f"✅ Pattern detected: {pattern.pattern_type.upper()}")
            print(f"   Confidence: {pattern.confidence:.2%}")
        else:
            print("⚠️  No pattern detected (this is normal)")
    except Exception as e:
        print(f"❌ Wave detection error: {e}")
        return False
    
    # Test 4: Generate trading signals
    print("\n[4/4] Testing signal generation...")
    try:
        signals = SignalGenerator()
        signal = signals.generate_combined_signal(data["Close"], data["High"], data["Low"])
        
        print(f"✅ Signal generated:")
        print(f"   Confidence: {signal['confidence']:.2%}")
        print(f"   RSI: {signal['rsi']['rsi_value']:.2f}")
        print(f"   MACD Status: {'Bullish' if signal['macd']['bullish_crossover'] else 'Bearish'}")
    except Exception as e:
        print(f"❌ Signal generation error: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED! Bot is ready to run!")
    print("=" * 70)
    print("\nRun the bot with:")
    print("python dydx_trading.py dydx --private-key YOUR_KEY --network testnet")
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_dydx_bot())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
