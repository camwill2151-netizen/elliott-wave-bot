"""Backtest mode for Elliott Wave Bot with sentiment analysis."""

import asyncio
import argparse
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from src.dydx_connector import DydxExchangeConnector
from src.wave_detector import WaveDetector
from src.indicators import SignalGenerator, Indicators
from src.sentiment import SentimentAnalyzer
from src.backtester_engine import Backtester

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_backtest(market_id: str = "BTC-USD", lookback_days: int = 14,
                       initial_capital: float = 1000, position_size_percent: float = 0.25):
    """Run backtest on historical data."""
    
    print(f"""
╔════════════════════════════════════════════════════════╗
║    ELLIOTT WAVE BOT - BACKTEST MODE WITH SENTIMENT    ║
╠════════════════════════════════════════════════════════╣
║ Market:          {market_id}
║ Lookback Period: {lookback_days} days
║ Initial Capital: ${initial_capital:,.2f}
║ Position Size:   {position_size_percent*100:.0f}% per trade
║ Stop Loss:       2.0%
║ Take Profit:     5.0%
╚════════════════════════════════════════════════════════╝
    """)
    
    # Initialize components
    connector = DydxExchangeConnector(network="testnet")
    wave_detector = WaveDetector()
    indicators = Indicators()
    signal_gen = SignalGenerator(indicators)
    sentiment_analyzer = SentimentAnalyzer()
    backtester = Backtester(initial_capital=initial_capital, 
                           position_size_percent=position_size_percent)
    
    logger.info(f"Fetching {lookback_days} days of historical data...")
    
    # Fetch historical data
    df = await connector.get_price_data(market_id, resolution="1HOUR", limit=lookback_days*24)
    
    if df.empty:
        logger.error(f"No data available for {market_id}")
        return
    
    logger.info(f"Got {len(df)} candles")
    
    # Backtest each candle
    print(f"\nRunning backtest...\n")
    
    for i in range(1, len(df)):
        try:
            timestamp = df.index[i] if hasattr(df.index[i], 'to_pydatetime') else datetime.now()
            current_close = df['Close'].iloc[i]
            current_high = df['High'].iloc[i]
            current_low = df['Low'].iloc[i]
            
            # Use lookback window (last 20 candles for pattern detection)
            lookback_df = df.iloc[max(0, i-100):i+1]
            
            # Detect patterns
            patterns = wave_detector.detect_all_patterns(lookback_df['Close'])
            
            # Generate indicator signals
            combined_signal = signal_gen.generate_combined_signal(
                prices=lookback_df['Close'],
                high=lookback_df['High'],
                low=lookback_df['Low']
            )
            
            # Generate sentiment signals
            price_data = {
                'price_change_24h': ((lookback_df['Close'].iloc[-1] - lookback_df['Close'].iloc[0]) / lookback_df['Close'].iloc[0]) * 100,
                'volume_change': 0,
                'momentum': 0.5,
                'fear_greed_index': 50
            }
            
            sentiment_report = sentiment_analyzer.get_sentiment_report(
                price_data=price_data,
                df=lookback_df
            )
            
            sentiment_signal = sentiment_report['signal']
            
            # Consensus decision
            bullish_votes = 0
            bearish_votes = 0
            
            # Wave vote
            if patterns and patterns[0].confidence > 0.6:
                if patterns[0].pattern_type == "impulse":
                    bullish_votes += 1
                else:
                    bearish_votes += 1
            
            # Indicator vote
            if combined_signal['strong_buy'] or combined_signal['buy']:
                bullish_votes += 1
            elif combined_signal['sell']:
                bearish_votes += 1
            
            # Sentiment vote
            if sentiment_signal['signal_type'] in ["STRONG BUY", "BUY"]:
                bullish_votes += 1
            elif sentiment_signal['signal_type'] in ["STRONG SELL", "SELL"]:
                bearish_votes += 1
            
            # Generate final signal
            final_signal = "HOLD"
            if bullish_votes >= 2:
                final_signal = "BUY"
            elif bearish_votes >= 2:
                final_signal = "SELL"
            
            # Execute signal
            backtester.execute_signal(i, current_close, final_signal, timestamp)
            
            # Check stop loss/take profit
            backtester.check_stops(i, current_high, current_low, current_close, timestamp)
            
            # Update equity curve
            equity = backtester.capital
            if backtester.current_position:
                if backtester.current_position.signal_type == "BUY":
                    equity += (current_close - backtester.current_position.entry_price) * backtester.current_position.position_size
                else:
                    equity += (backtester.current_position.entry_price - current_close) * backtester.current_position.position_size
            
            backtester.equity_curve.append(equity)
            
        except Exception as e:
            logger.error(f"Error at candle {i}: {e}")
            continue
    
    # Close all positions at end
    backtester.close_all_positions(len(df)-1, df['Close'].iloc[-1])
    
    # Print results
    backtester.print_results()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Elliott Wave Bot Backtest - 2 weeks of data with sentiment analysis'
    )
    
    parser.add_argument('--market', type=str, default='BTC-USD',
                       help='Market to backtest (default: BTC-USD)')
    parser.add_argument('--lookback', type=int, default=14,
                       help='Lookback period in days (default: 14)')
    parser.add_argument('--capital', type=float, default=1000,
                       help='Initial capital (default: 1000)')
    parser.add_argument('--position-size', type=float, default=0.25,
                       help='Position size as % of capital (default: 0.25 = 25%)')
    
    args = parser.parse_args()
    
    # Run backtest
    asyncio.run(run_backtest(
        market_id=args.market,
        lookback_days=args.lookback,
        initial_capital=args.capital,
        position_size_percent=args.position_size
    ))


if __name__ == '__main__':
    main()
