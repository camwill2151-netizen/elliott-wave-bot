# Elliott Wave Trading Bot

An automated trading bot that detects Elliott Wave patterns and executes trades based on identified wave structures.

## Features

- **Automated Elliott Wave Detection**: Identifies impulsive (5-wave) and corrective (3-wave) patterns
- **Backtest Engine**: Full backtesting capabilities with performance metrics
- **Binance Integration**: Live trading support via Binance API
- **Confirmation Signals**: Uses RSI, MACD, and Fibonacci levels for trade confirmation
- **Risk Management**: Built-in stop loss and position sizing

## Project Structure

```
elliott-wave-bot/
├── data/                      # Market data storage
├── src/
│   ├── wave_detector.py       # Elliott Wave pattern detection
│   ├── trader.py              # Trading logic and execution
│   ├── backtester.py          # Backtesting engine
│   ├── indicators.py          # Technical indicators (RSI, MACD, etc.)
│   ├── config.py              # Configuration and constants
│   └── exchange_connector.py   # Binance API integration
├── notebooks/
│   ├── analysis.ipynb         # Data analysis and visualization
│   └── backtest_results.ipynb  # Backtest performance analysis
├── tests/
│   ├── test_wave_detector.py
│   └── test_indicators.py
├── requirements.txt            # Python dependencies
├── config.example.yaml         # Example configuration
└── main.py                     # Entry point

```

## Installation

```bash
# Clone the repository
git clone https://github.com/camwill2151-netizen/elliott-wave-bot.git
cd elliott-wave-bot

# Install dependencies
pip install -r requirements.txt

# Copy and configure
cp config.example.yaml config.yaml
```

## Quick Start

### 1. Backtesting

```python
from src.backtester import BacktestEngine
from src.wave_detector import WaveDetector

# Run backtest
engine = BacktestEngine(
    symbol="BTC-USD",
    start_date="2023-01-01",
    end_date="2024-01-01",
    initial_capital=10000
)

detector = WaveDetector()
results = engine.run(detector)
print(results.summary())
```

### 2. Live Trading (Paper Trading First!)

```python
from src.trader import LiveTrader
from src.wave_detector import WaveDetector

trader = LiveTrader(
    api_key="your_binance_api_key",
    api_secret="your_binance_api_secret",
    symbol="BTCUSDT",
    paper_trading=True  # Start with paper trading
)

detector = WaveDetector()
trader.run(detector)
```

## Elliott Wave Basics

- **Impulse Wave (5-wave)**: Moves in the direction of the trend (Wave 1,3,5 move up; 2,4 correct)
- **Corrective Wave (3-wave)**: Moves against the trend (A, B, C)
- **Fibonacci Ratios**: Waves follow predictable ratios (1.618, 0.618, etc.)

## Configuration

Edit `config.yaml` to customize:

```yaml
trading:
  symbol: "BTCUSDT"
  timeframe: "1h"
  
risk_management:
  stop_loss_percent: 2.0
  take_profit_percent: 5.0
  position_size: 0.05
  
wave_detection:
  min_wave_length: 5
  confirmation_threshold: 0.75
  use_fibonacci: true
```

## Trading Strategy

1. **Detect Waves**: Identify 5-wave impulse or 3-wave corrective patterns
2. **Confirm Signal**: Use RSI, MACD, and Fibonacci levels
3. **Enter Trade**: Buy at wave 3 or after wave 5 completion
4. **Manage Risk**: Set stop loss below wave 2 or wave 4
5. **Exit Trade**: Take profit at Fibonacci extensions

## Important Warnings ⚠️

- **Elliott Wave analysis is subjective** - No guaranteed signals
- **Backtesting ≠ Live Performance** - Past results don't guarantee future gains
- **Start with paper trading** - Test extensively before risking real capital
- **Use risk management** - Never risk more than 1-2% per trade
- **Monitor constantly** - Don't leave bot unattended

## Dependencies

- Python 3.8+
- pandas, numpy
- ta-lib (technical analysis)
- ccxt (exchange connectivity)
- backtrader (backtesting)
- matplotlib, seaborn (visualization)
- python-binance (Binance API)

## Testing

```bash
pytest tests/
```

## Backtesting Results

Run backtests and analyze results:

```bash
python main.py --mode backtest --symbol BTC-USD --period 1y
```

## Contributing

Pull requests welcome! Please ensure:
- Code passes tests
- Documentation is updated
- Changes are well-commented

## License

MIT License

## Disclaimer

This bot is for educational purposes. Trading carries risk. Use at your own discretion. Always test thoroughly before using real capital.

## Support

For issues, questions, or improvements, open an issue on GitHub.