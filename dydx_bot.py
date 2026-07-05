"""dYdX v4 Live Trading Bot with Elliott Wave Analysis."""

import asyncio
import argparse
import logging
from datetime import datetime
import sys

from src.dydx_connector import DydxExchangeConnector
from src.wave_detector import WaveDetector
from src.signal_generator import SignalGenerator


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_live_trading(market_id: str = "BTC-USD", network: str = "testnet",
                          private_key: str = None, check_interval: int = 60):
    """Run live trading on dYdX v4."""
    
    print(f"""
╔════════════════════════════════════════════════════════╗
║     ELLIOTT WAVE BOT - dYdX v4 LIVE TRADING MODE      ║
╠═════════════════���══════════════════════════════════════╣
║ Market:         {market_id}
║ Network:        {network.upper()}
║ Check Interval: {check_interval}s
║ Time:           {datetime.utcnow().isoformat()}Z
╠════════════════════════════════════════════════════════╣
║ ⚠️  LIVE TRADING MODE - Real money on the line!       ║
║ ⚠️  Make sure you've backtested and understand risks! ║
╚════════════════════════════════════════════════════════╝
    """)
    
    # Initialize connector
    connector = DydxExchangeConnector(private_key=private_key, network=network)
    wave_detector = WaveDetector()
    signal_gen = SignalGenerator()
    
    logger.info(f"Starting live trading loop for {market_id}...")
    
    try:
        iteration = 0
        while True:
            iteration += 1
            logger.info(f"\n{'='*70}")
            logger.info(f"Iteration {iteration} - {datetime.utcnow().isoformat()}Z")
            logger.info(f"{'='*70}")
            
            # Fetch current price
            price = await connector.get_current_price(market_id)
            if not price:
                logger.warning(f"Could not fetch price for {market_id}")
                await asyncio.sleep(check_interval)
                continue
            
            logger.info(f"✅ Current {market_id} price: ${price:,.2f}")
            
            # Fetch market data
            logger.info("Fetching market data...")
            df = await connector.get_price_data(market_id, resolution="1HOUR", limit=100)
            
            if df.empty:
                logger.warning("No data available")
                await asyncio.sleep(check_interval)
                continue
            
            logger.info(f"✅ Got {len(df)} candles")
            
            # Detect Elliott Wave patterns
            logger.info("Analyzing Elliott Wave patterns...")
            patterns = wave_detector.detect(df)
            
            if patterns:
                logger.info(f"✅ Found {len(patterns)} pattern(s)")
                for pattern in patterns:
                    logger.info(f"   - {pattern['type']}: confidence={pattern['confidence']:.2%}")
            else:
                logger.info("⚠️  No patterns detected")
            
            # Generate signals
            logger.info("Generating trading signals...")
            signals = signal_gen.generate(df, patterns)
            
            if signals:
                logger.info(f"✅ Generated {len(signals)} signal(s)")
                for i, signal in enumerate(signals, 1):
                    logger.info(f"\n   Signal #{i}:")
                    logger.info(f"   - Type: {signal.get('type', 'UNKNOWN')}")
                    logger.info(f"   - Confidence: {signal.get('confidence', 0):.2%}")
                    logger.info(f"   - RSI: {signal.get('rsi', 0):.2f}")
                    logger.info(f"   - MACD: {signal.get('macd_status', 'UNKNOWN')}")
                    
                    # TODO: Execute trade based on signal
                    # if signal['type'] == 'BUY':
                    #     logger.info("   🟢 BUY signal - executing trade...")
                    # elif signal['type'] == 'SELL':
                    #     logger.info("   🔴 SELL signal - executing trade...")
            else:
                logger.info("⚠️  No signals generated")
            
            # Get market stats
            stats = await connector.get_market_stats(market_id)
            if stats:
                logger.info(f"\n24h Stats for {market_id}:")
                logger.info(f"   - Price change: {stats.get('priceChange24H', 'N/A')}")
                logger.info(f"   - Volume: ${float(stats.get('volume24H', 0)):,.0f}")
                logger.info(f"   - Trades: {stats.get('trades24H', 'N/A')}")
                logger.info(f"   - Funding rate: {stats.get('nextFundingRate', 'N/A')}")
            
            logger.info(f"\nNext check in {check_interval} seconds...")
            await asyncio.sleep(check_interval)
    
    except KeyboardInterrupt:
        logger.info("\n\n✅ Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Elliott Wave Trading Bot - dYdX v4 Live Trading'
    )
    
    parser.add_argument('--market', type=str, default='BTC-USD',
                       help='Market to trade (default: BTC-USD)')
    parser.add_argument('--network', type=str, default='testnet',
                       choices=['testnet', 'mainnet'],
                       help='Network to use (default: testnet)')
    parser.add_argument('--private-key', type=str, default=None,
                       help='Private key for wallet (required for real trading)')
    parser.add_argument('--interval', type=int, default=60,
                       help='Check interval in seconds (default: 60)')
    
    args = parser.parse_args()
    
    # Run the trading loop
    asyncio.run(run_live_trading(
        market_id=args.market,
        network=args.network,
        private_key=args.private_key,
        check_interval=args.interval
    ))


if __name__ == '__main__':
    main()
