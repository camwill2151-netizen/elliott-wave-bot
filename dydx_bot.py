"""dYdX v4 Live Trading Bot with Elliott Wave Analysis and Sentiment."""

import asyncio
import argparse
import logging
from datetime import datetime
import sys

from src.dydx_connector import DydxExchangeConnector
from src.wave_detector import WaveDetector
from src.indicators import SignalGenerator, Indicators
from src.sentiment import SentimentAnalyzer


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_live_trading(market_id: str = "BTC-USD", network: str = "testnet",
                          private_key: str = None, check_interval: int = 60):
    """Run live trading on dYdX v4 with sentiment analysis."""
    
    print(f"""
╔════════════════════════════════════════════════════════╗
║    ELLIOTT WAVE BOT - dYdX v4 LIVE TRADING MODE       ║
╠════════════════════════════════════════════════════════╣
║ Market:         {market_id}
║ Network:        {network.upper()}
║ Check Interval: {check_interval}s
║ Time:           {datetime.utcnow().isoformat()}Z
╠════════════════════════════════════════════════════════╣
║ ✅ TESTNET MODE - No real money at risk!              ║
║ Features: Elliott Waves + Indicators + Sentiment      ║
╚════════════════════════════════════════════════════════╝
    """)
    
    # Initialize components
    connector = DydxExchangeConnector(private_key=private_key, network=network)
    wave_detector = WaveDetector()
    indicators = Indicators()
    signal_gen = SignalGenerator(indicators)
    sentiment_analyzer = SentimentAnalyzer()
    
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
            patterns = wave_detector.detect_all_patterns(df['Close'])
            
            if patterns:
                logger.info(f"✅ Found {len(patterns)} pattern(s)")
                for i, pattern in enumerate(patterns[:3], 1):  # Show top 3
                    logger.info(f"   Pattern {i}:")
                    logger.info(f"   - Type: {pattern.pattern_type}")
                    logger.info(f"   - Confidence: {pattern.confidence:.2%}")
                    logger.info(f"   - Valid: {pattern.is_valid}")
            else:
                logger.info("⚠️  No patterns detected")
            
            # Generate indicator signals
            logger.info("Generating indicator signals...")
            try:
                combined_signal = signal_gen.generate_combined_signal(
                    prices=df['Close'],
                    high=df['High'],
                    low=df['Low']
                )
                
                logger.info(f"✅ Indicator Signal:")
                logger.info(f"   - Confidence: {combined_signal['confidence']:.2%}")
                logger.info(f"   - RSI: {combined_signal['rsi']['rsi_value']:.2f}")
                logger.info(f"   - MACD Bullish: {combined_signal['macd']['bullish_crossover']}")
                
                # Determine indicator signal type
                indicator_signal_type = ""
                if combined_signal['strong_buy']:
                    indicator_signal_type = "🟢 STRONG BUY"
                elif combined_signal['buy']:
                    indicator_signal_type = "🟢 BUY"
                elif combined_signal['hold']:
                    indicator_signal_type = "🟡 HOLD"
                elif combined_signal['sell']:
                    indicator_signal_type = "🔴 SELL"
                
                logger.info(f"   - Signal Type: {indicator_signal_type}")
            
            except Exception as e:
                logger.error(f"Error generating indicator signals: {e}")
                combined_signal = None
            
            # Generate sentiment signals
            logger.info("Analyzing sentiment...")
            try:
                # Create price data dict for sentiment analysis
                price_data = {
                    'price_change_24h': ((df['Close'].iloc[-1] - df['Close'].iloc[0]) / df['Close'].iloc[0]) * 100,
                    'volume_change': ((df['Volume'].tail(5).mean() - df['Volume'].tail(20).mean()) / df['Volume'].tail(20).mean()) * 100 if 'Volume' in df.columns else 0,
                    'momentum': 0.5,  # Placeholder
                    'fear_greed_index': 50  # Placeholder
                }
                
                sentiment_report = sentiment_analyzer.get_sentiment_report(
                    price_data=price_data,
                    df=df
                )
                
                sentiment_signal = sentiment_report['signal']
                combined_sentiment = sentiment_report['combined_sentiment']
                
                logger.info(f"✅ Sentiment Analysis:")
                logger.info(f"   - Bullish: {combined_sentiment['bullish']:.2%}")
                logger.info(f"   - Bearish: {combined_sentiment['bearish']:.2%}")
                logger.info(f"   - Neutral: {combined_sentiment['neutral']:.2%}")
                logger.info(f"   - Signal: {sentiment_signal['signal_type']} ({sentiment_signal['confidence']:.2%})")
                
            except Exception as e:
                logger.error(f"Error analyzing sentiment: {e}")
                sentiment_signal = None
            
            # COMBINED DECISION
            logger.info("\n" + "="*70)
            logger.info("COMBINED DECISION:")
            logger.info("="*70)
            
            if combined_signal and sentiment_signal:
                # Score all three methods
                wave_score = patterns[0].confidence if patterns else 0
                indicator_score = combined_signal['confidence']
                sentiment_score = sentiment_signal['confidence']
                
                avg_confidence = (wave_score + indicator_score + sentiment_score) / 3
                
                logger.info(f"Wave Confidence:      {wave_score:.2%}")
                logger.info(f"Indicator Confidence: {indicator_score:.2%}")
                logger.info(f"Sentiment Confidence: {sentiment_score:.2%}")
                logger.info(f"\nAverage Confidence:   {avg_confidence:.2%}")
                
                # Consensus decision
                bullish_votes = 0
                bearish_votes = 0
                
                if patterns and patterns[0].pattern_type == "impulse":
                    bullish_votes += 1
                
                if combined_signal['strong_buy'] or combined_signal['buy']:
                    bullish_votes += 1
                
                if sentiment_signal['signal_type'] in ["STRONG BUY", "BUY"]:
                    bullish_votes += 1
                
                if combined_signal['sell']:
                    bearish_votes += 1
                    
                if sentiment_signal['signal_type'] in ["STRONG SELL", "SELL"]:
                    bearish_votes += 1
                
                # Final recommendation
                if bullish_votes >= 2 and avg_confidence > 0.65:
                    logger.info(f"\n🟢🟢 FINAL SIGNAL: STRONG BUY (Consensus: {bullish_votes}/3 methods agree)")
                elif bullish_votes >= 2 and avg_confidence > 0.55:
                    logger.info(f"\n🟢 FINAL SIGNAL: BUY (Consensus: {bullish_votes}/3 methods agree)")
                elif bearish_votes >= 2 and avg_confidence > 0.65:
                    logger.info(f"\n🔴🔴 FINAL SIGNAL: STRONG SELL (Consensus: {bearish_votes}/3 methods agree)")
                elif bearish_votes >= 2 and avg_confidence > 0.55:
                    logger.info(f"\n🔴 FINAL SIGNAL: SELL (Consensus: {bearish_votes}/3 methods agree)")
                else:
                    logger.info(f"\n🟡 FINAL SIGNAL: HOLD (No consensus or low confidence)")
            
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
        description='Elliott Wave Trading Bot - dYdX v4 Live Trading with Sentiment Analysis'
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
