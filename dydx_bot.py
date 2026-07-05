"""dYdX v4 Live Trading Bot with Elliott Wave Analysis."""

import asyncio
import argparse
import logging
from datetime import datetime
import sys

from src.dydx_connector import DydxExchangeConnector
from src.wave_detector import WaveDetector
from src.indicators import SignalGenerator, Indicators


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
╠═══════════════���══════���═════════════════════════════════╣
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
    indicators = Indicators()
    signal_gen = SignalGenerator(indicators)
    
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
            
            # Generate signals from indicators
            logger.info("Generating trading signals...")
            try:
                combined_signal = signal_gen.generate_combined_signal(
                    prices=df['Close'],
                    high=df['High'],
                    low=df['Low']
                )
                
                logger.info(f"✅ Generated signal:")
                logger.info(f"   - Confidence: {combined_signal['confidence']:.2%}")
                logger.info(f"   - RSI: {combined_signal['rsi']['rsi_value']:.2f}")
                logger.info(f"   - MACD Bullish: {combined_signal['macd']['bullish_crossover']}")
                logger.info(f"   - Signal Type: ", end="")
                
                if combined_signal['strong_buy']:
                    logger.info("🟢 STRONG BUY")
                elif combined_signal['buy']:
                    logger.info("🟢 BUY")
                elif combined_signal['hold']:
                    logger.info("🟡 HOLD")
                elif combined_signal['sell']:
                    logger.info("🔴 SELL")
                
                # TODO: Execute trade based on signal
                # if combined_signal['strong_buy'] or combined_signal['buy']:
                #     logger.info("   Executing BUY order...")
                # elif combined_signal['sell']:
                #     logger.info("   Executing SELL order...")
            
            except Exception as e:
                logger.error(f"Error generating signals: {e}")
            
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
