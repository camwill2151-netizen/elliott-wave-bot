"""Main entry point for Elliott Wave trading bot."""

import argparse
import sys
from src.wave_detector import WaveDetector
from src.backtester import BacktestEngine
from src.trader import LiveTrader


def main():
    parser = argparse.ArgumentParser(description='Elliott Wave Trading Bot')
    
    subparsers = parser.add_subparsers(dest='mode', help='Operation mode')
    
    # Backtest mode
    backtest_parser = subparsers.add_parser('backtest', help='Run backtesting')
    backtest_parser.add_argument('--symbol', type=str, default='BTC-USD',
                                help='Trading symbol (default: BTC-USD)')
    backtest_parser.add_argument('--start', type=str, default='2023-01-01',
                                help='Start date (YYYY-MM-DD)')
    backtest_parser.add_argument('--end', type=str, default='2024-01-01',
                                help='End date (YYYY-MM-DD)')
    backtest_parser.add_argument('--capital', type=float, default=10000,
                                help='Initial capital (default: 10000)')
    backtest_parser.add_argument('--commission', type=float, default=0.001,
                                help='Commission per trade (default: 0.001)')
    backtest_parser.add_argument('--save', type=str, default=None,
                                help='Save results to CSV file')
    
    # Live trading mode
    live_parser = subparsers.add_parser('live', help='Run live trading')
    live_parser.add_argument('--api-key', type=str, required=True,
                            help='Binance API key')
    live_parser.add_argument('--api-secret', type=str, required=True,
                            help='Binance API secret')
    live_parser.add_argument('--symbol', type=str, default='BTCUSDT',
                            help='Trading symbol (default: BTCUSDT)')
    live_parser.add_argument('--timeframe', type=str, default='1h',
                            help='Kline interval (default: 1h)')
    live_parser.add_argument('--paper', action='store_true',
                            help='Use paper trading (simulation)')
    live_parser.add_argument('--interval', type=int, default=60,
                            help='Check interval in seconds (default: 60)')
    
    args = parser.parse_args()
    
    if args.mode == 'backtest':
        run_backtest(args)
    elif args.mode == 'live':
        run_live(args)
    else:
        parser.print_help()


def run_backtest(args):
    """Run backtesting."""
    print(f"""
╔════════════════════════════════════════════════════════╗
║         ELLIOTT WAVE BOT - BACKTESTING MODE             ║
╠════════════════════════════════════════════════════════╣
║ Symbol:         {args.symbol}
║ Period:         {args.start} to {args.end}
║ Initial Capital: ${args.capital:,.2f}
║ Commission:     {args.commission*100:.2f}%
╚════════════════════════════════════════════════════════╝
    """)
    
    # Create backtester
    engine = BacktestEngine(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
        commission=args.commission
    )
    
    # Create wave detector
    detector = WaveDetector()
    
    # Run backtest
    results = engine.run(detector)
    
    # Save results if requested
    if args.save:
        engine.save_results(args.save)


def run_live(args):
    """Run live trading."""
    print(f"""
╔════════════════════════════════════════════════════════╗
║         ELLIOTT WAVE BOT - LIVE TRADING MODE            ║
╠════════════════════════════════════════════════════════╣
║ Symbol:         {args.symbol}
║ Timeframe:      {args.timeframe}
║ Paper Trading:  {'YES' if args.paper else 'NO (LIVE MONEY!)'}
║ Check Interval: {args.interval}s
╠════════════════════════════════════════════════════════╣
║ ⚠️  WARNING: Make sure to test on paper trading first!  ║
║ ⚠️  Only use real capital after thorough testing!       ║
╚════════════════════════════════════════════════════════╝
    """)
    
    if not args.paper:
        response = input("\n⚠️  You are about to trade with REAL money!")
        response += "\nType 'YES I UNDERSTAND' to continue: "
        if response != 'YES I UNDERSTAND':
            print("Cancelled.")
            return
    
    # Create trader
    trader = LiveTrader(
        api_key=args.api_key,
        api_secret=args.api_secret,
        symbol=args.symbol,
        timeframe=args.timeframe,
        paper_trading=args.paper
    )
    
    # Run trader
    trader.run(check_interval=args.interval)


if __name__ == '__main__':
    main()
