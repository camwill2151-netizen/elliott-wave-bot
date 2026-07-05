"""Backtesting engine for Elliott Wave bot."""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
import yfinance as yf

from src.wave_detector import WaveDetector, WavePattern
from src.indicators import Indicators, SignalGenerator


@dataclass
class Trade:
    """Represents a single trade."""
    entry_date: datetime
    entry_price: float
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    quantity: float = 1.0
    side: str = "BUY"  # BUY or SELL
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    status: str = "OPEN"  # OPEN, CLOSED, STOPPED
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    
    def close(self, exit_price: float, exit_date: datetime, status: str = "CLOSED"):
        """Close the trade."""
        self.exit_price = exit_price
        self.exit_date = exit_date
        self.status = status
        
        if self.side == "BUY":
            self.pnl = (exit_price - self.entry_price) * self.quantity
            self.pnl_percent = ((exit_price - self.entry_price) / self.entry_price) * 100
        else:
            self.pnl = (self.entry_price - exit_price) * self.quantity
            self.pnl_percent = ((self.entry_price - exit_price) / self.entry_price) * 100


@dataclass
class BacktestResults:
    """Backtesting results and metrics."""
    trades: List[Trade] = field(default_factory=list)
    initial_capital: float = 0.0
    final_capital: float = 0.0
    total_return: float = 0.0
    return_percent: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    equity_curve: List[float] = field(default_factory=list)
    
    def calculate_metrics(self):
        """Calculate all performance metrics."""
        self.total_trades = len(self.trades)
        self.winning_trades = sum(1 for t in self.trades if t.pnl and t.pnl > 0)
        self.losing_trades = sum(1 for t in self.trades if t.pnl and t.pnl < 0)
        
        if self.total_trades > 0:
            self.win_rate = (self.winning_trades / self.total_trades) * 100
        
        winning_pnl = sum(t.pnl for t in self.trades if t.pnl and t.pnl > 0)
        losing_pnl = sum(abs(t.pnl) for t in self.trades if t.pnl and t.pnl < 0)
        
        if self.winning_trades > 0:
            self.avg_win = winning_pnl / self.winning_trades
        
        if self.losing_trades > 0:
            self.avg_loss = losing_pnl / self.losing_trades
        
        if losing_pnl > 0:
            self.profit_factor = winning_pnl / losing_pnl
        
        self.total_return = self.final_capital - self.initial_capital
        self.return_percent = (self.total_return / self.initial_capital) * 100
        
        # Calculate max drawdown
        if self.equity_curve:
            cumulative_returns = np.array(self.equity_curve) / self.initial_capital
            running_max = np.maximum.accumulate(cumulative_returns)
            drawdown = (cumulative_returns - running_max) / running_max
            self.max_drawdown = np.min(drawdown) * 100
    
    def summary(self) -> str:
        """Return a summary of backtest results."""
        self.calculate_metrics()
        
        summary = f"""
╔══════════════════════════════════════════════════════╗
║         ELLIOTT WAVE BOT - BACKTEST RESULTS          ║
╠══════════════════════════════════════════════════════╣
║ Initial Capital:        ${self.initial_capital:,.2f}
║ Final Capital:          ${self.final_capital:,.2f}
║ Total Return:           ${self.total_return:,.2f}
║ Return %:               {self.return_percent:.2f}%
╠══════════════════════════════════════════════════════╣
║ Total Trades:           {self.total_trades}
║ Winning Trades:         {self.winning_trades}
║ Losing Trades:          {self.losing_trades}
║ Win Rate:               {self.win_rate:.2f}%
║ Avg Win:                ${self.avg_win:.2f}
║ Avg Loss:               ${self.avg_loss:.2f}
║ Profit Factor:          {self.profit_factor:.2f}
║ Max Drawdown:           {self.max_drawdown:.2f}%
║ Sharpe Ratio:           {self.sharpe_ratio:.2f}
╚══════════════════════════════════════════════════════╝
        """
        
        return summary


class BacktestEngine:
    """Backtesting engine for Elliott Wave strategies."""
    
    def __init__(self, symbol: str, start_date: str, end_date: str, 
                 initial_capital: float = 10000, commission: float = 0.001,
                 slippage: float = 0.002):
        """
        Initialize backtester.
        
        Args:
            symbol: Trading symbol (e.g., "BTC-USD")
            start_date: Start date for backtest (YYYY-MM-DD)
            end_date: End date for backtest (YYYY-MM-DD)
            initial_capital: Starting capital
            commission: Commission per trade (e.g., 0.001 = 0.1%)
            slippage: Slippage percentage
        """
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        
        self.data = None
        self.results = BacktestResults(initial_capital=initial_capital)
    
    def fetch_data(self):
        """Fetch historical price data using yfinance."""
        print(f"Fetching {self.symbol} data from {self.start_date} to {self.end_date}...")
        self.data = yf.download(self.symbol, start=self.start_date, end=self.end_date)
        print(f"Loaded {len(self.data)} candles")
        return self.data
    
    def run(self, wave_detector: WaveDetector, min_confidence: float = 0.70) -> BacktestResults:
        """
        Run backtest with Elliott Wave strategy.
        
        Args:
            wave_detector: WaveDetector instance
            min_confidence: Minimum wave pattern confidence (0-1)
            
        Returns:
            BacktestResults object
        """
        if self.data is None:
            self.fetch_data()
        
        capital = self.initial_capital
        position = None
        signals = SignalGenerator()
        
        print(f"Running backtest with min confidence: {min_confidence}...")
        
        # Iterate through data
        for i in range(50, len(self.data)):  # Start at 50 to have enough data for indicators
            current_date = self.data.index[i]
            current_price = self.data['Close'].iloc[i]
            
            # Get price data up to current point
            price_data = self.data['Close'].iloc[:i+1]
            
            # Detect wave patterns
            pattern = wave_detector.get_latest_pattern(price_data)
            
            if pattern is None or pattern.confidence < min_confidence:
                continue
            
            # Generate confirmation signal
            high_data = self.data['High'].iloc[:i+1]
            low_data = self.data['Low'].iloc[:i+1]
            confirmation = signals.generate_combined_signal(price_data, high_data, low_data)
            
            # Entry logic
            if position is None and pattern.pattern_type == "impulse":
                if confirmation['confidence'] > 0.5:
                    # Open long position
                    entry_price = current_price * (1 + self.slippage)
                    quantity = capital / entry_price
                    
                    # Calculate stop loss and take profit
                    support_levels = wave_detector.get_support_resistance(pattern)
                    stop_loss = support_levels.get('support', entry_price * 0.98)
                    targets = wave_detector.predict_next_target(pattern, price_data)
                    take_profit = targets.get('likely', entry_price * 1.05)
                    
                    position = Trade(
                        entry_date=current_date,
                        entry_price=entry_price,
                        quantity=quantity,
                        side="BUY",
                        stop_loss=stop_loss,
                        take_profit=take_profit
                    )
                    print(f"[{current_date}] BUY @ {entry_price:.2f} (Confidence: {pattern.confidence:.2%})")
            
            # Exit logic
            elif position is not None:
                # Check stop loss
                if current_price <= position.stop_loss:
                    exit_price = position.stop_loss * (1 - self.slippage)
                    position.close(exit_price, current_date, "STOPPED")
                    capital += position.pnl - (position.entry_price * position.quantity * self.commission)
                    self.results.trades.append(position)
                    print(f"[{current_date}] STOP LOSS @ {exit_price:.2f} | PnL: {position.pnl:.2f}")
                    position = None
                
                # Check take profit
                elif current_price >= position.take_profit:
                    exit_price = position.take_profit * (1 - self.slippage)
                    position.close(exit_price, current_date, "CLOSED")
                    capital += position.pnl - (position.entry_price * position.quantity * self.commission)
                    self.results.trades.append(position)
                    print(f"[{current_date}] TAKE PROFIT @ {exit_price:.2f} | PnL: {position.pnl:.2f}")
                    position = None
            
            # Track equity
            current_equity = capital
            if position:
                current_equity += (current_price - position.entry_price) * position.quantity
            
            self.results.equity_curve.append(current_equity)
        
        # Close any open position at end
        if position:
            final_price = self.data['Close'].iloc[-1]
            position.close(final_price, self.data.index[-1], "CLOSED")
            capital += position.pnl
            self.results.trades.append(position)
        
        self.results.final_capital = capital
        self.results.equity_curve.append(capital)
        self.results.calculate_metrics()
        
        print("\nBacktest completed!")
        print(self.results.summary())
        
        return self.results
    
    def save_results(self, filename: str = "backtest_results.csv"):
        """Save trade results to CSV."""
        if not self.results.trades:
            print("No trades to save")
            return
        
        trades_data = []
        for trade in self.results.trades:
            trades_data.append({
                'Entry Date': trade.entry_date,
                'Entry Price': trade.entry_price,
                'Exit Date': trade.exit_date,
                'Exit Price': trade.exit_price,
                'Side': trade.side,
                'Quantity': trade.quantity,
                'PnL': trade.pnl,
                'PnL %': trade.pnl_percent,
                'Status': trade.status
            })
        
        df = pd.DataFrame(trades_data)
        df.to_csv(filename, index=False)
        print(f"Results saved to {filename}")
