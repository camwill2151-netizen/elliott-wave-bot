"""Backtesting engine for Elliott Wave Bot with sentiment analysis."""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


class BacktestTrade:
    """Represents a single trade in the backtest."""
    
    def __init__(self, entry_index: int, entry_price: float, position_size: float,
                 signal_type: str, timestamp: datetime):
        self.entry_index = entry_index
        self.entry_price = entry_price
        self.position_size = position_size
        self.signal_type = signal_type
        self.timestamp = timestamp
        self.exit_index = None
        self.exit_price = None
        self.exit_type = None  # "signal", "stop_loss", "take_profit"
        self.pnl = None
        self.pnl_percent = None
    
    def close(self, exit_index: int, exit_price: float, exit_type: str = "signal"):
        """Close the trade."""
        self.exit_index = exit_index
        self.exit_price = exit_price
        self.exit_type = exit_type
        
        if self.signal_type == "BUY":
            self.pnl = (exit_price - self.entry_price) * self.position_size
            self.pnl_percent = ((exit_price - self.entry_price) / self.entry_price) * 100
        else:  # SELL (short)
            self.pnl = (self.entry_price - exit_price) * self.position_size
            self.pnl_percent = ((self.entry_price - exit_price) / self.entry_price) * 100
    
    def __repr__(self):
        if self.exit_price:
            return f"Trade({self.signal_type} @ {self.entry_price:.2f} -> {self.exit_price:.2f}, PnL: ${self.pnl:.2f})"
        return f"Trade({self.signal_type} @ {self.entry_price:.2f}, OPEN)"


class Backtester:
    """Backtests trading signals with Elliott Wave + Sentiment analysis."""
    
    def __init__(self, initial_capital: float = 1000, position_size_percent: float = 0.25,
                 stop_loss_percent: float = 2.0, take_profit_percent: float = 5.0):
        """
        Initialize backtester.
        
        Args:
            initial_capital: Starting capital
            position_size_percent: Percentage of capital to use per trade (0.25 = 25%)
            stop_loss_percent: Stop loss percentage
            take_profit_percent: Take profit percentage
        """
        self.initial_capital = initial_capital
        self.position_size_percent = position_size_percent
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent
        
        # Trading state
        self.capital = initial_capital
        self.trades: List[BacktestTrade] = []
        self.current_position = None
        self.equity_curve = [initial_capital]
        self.timestamps = []
        self.last_signal = None
    
    def execute_signal(self, index: int, price: float, signal: str, timestamp: datetime):
        """
        Execute a trading signal.
        
        Args:
            index: Candle index
            price: Current price
            signal: "BUY", "SELL", or "HOLD"
            timestamp: Current timestamp
        """
        if signal == "HOLD" or signal == self.last_signal:
            return
        
        self.last_signal = signal
        
        # Close existing position if opposite signal
        if self.current_position and self.current_position.signal_type != signal:
            self.current_position.close(index, price, "signal")
            self.capital += self.current_position.pnl
            self.trades.append(self.current_position)
            self.current_position = None
        
        # Open new position
        if not self.current_position and signal in ["BUY", "SELL"]:
            position_size = (self.capital * self.position_size_percent) / price
            self.current_position = BacktestTrade(index, price, position_size, signal, timestamp)
    
    def check_stops(self, index: int, high: float, low: float, close: float, timestamp: datetime):
        """Check stop loss and take profit."""
        if not self.current_position:
            return
        
        if self.current_position.signal_type == "BUY":
            # Stop loss
            if low < self.current_position.entry_price * (1 - self.stop_loss_percent / 100):
                stop_price = self.current_position.entry_price * (1 - self.stop_loss_percent / 100)
                self.current_position.close(index, stop_price, "stop_loss")
                self.capital += self.current_position.pnl
                self.trades.append(self.current_position)
                self.current_position = None
                return
            
            # Take profit
            if high > self.current_position.entry_price * (1 + self.take_profit_percent / 100):
                tp_price = self.current_position.entry_price * (1 + self.take_profit_percent / 100)
                self.current_position.close(index, tp_price, "take_profit")
                self.capital += self.current_position.pnl
                self.trades.append(self.current_position)
                self.current_position = None
                return
        
        else:  # SELL (short)
            # Stop loss (price goes up)
            if high > self.current_position.entry_price * (1 + self.stop_loss_percent / 100):
                stop_price = self.current_position.entry_price * (1 + self.stop_loss_percent / 100)
                self.current_position.close(index, stop_price, "stop_loss")
                self.capital += self.current_position.pnl
                self.trades.append(self.current_position)
                self.current_position = None
                return
            
            # Take profit (price goes down)
            if low < self.current_position.entry_price * (1 - self.take_profit_percent / 100):
                tp_price = self.current_position.entry_price * (1 - self.take_profit_percent / 100)
                self.current_position.close(index, tp_price, "take_profit")
                self.capital += self.current_position.pnl
                self.trades.append(self.current_position)
                self.current_position = None
                return
    
    def close_all_positions(self, index: int, close_price: float):
        """Close all open positions at end of backtest."""
        if self.current_position:
            self.current_position.close(index, close_price, "end_of_backtest")
            self.capital += self.current_position.pnl
            self.trades.append(self.current_position)
            self.current_position = None
    
    def get_results(self) -> Dict:
        """Get backtest results."""
        results = {
            'initial_capital': self.initial_capital,
            'final_capital': self.capital,
            'total_return_dollars': self.capital - self.initial_capital,
            'total_return_percent': ((self.capital - self.initial_capital) / self.initial_capital) * 100,
            'total_trades': len(self.trades),
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'profit_factor': 0,
            'max_drawdown': 0,
            'sharpe_ratio': 0,
            'trades': self.trades
        }
        
        if not self.trades:
            return results
        
        winning_trades = [t for t in self.trades if t.pnl and t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl and t.pnl < 0]
        
        results['winning_trades'] = len(winning_trades)
        results['losing_trades'] = len(losing_trades)
        results['win_rate'] = (len(winning_trades) / len(self.trades)) * 100 if self.trades else 0
        results['avg_win'] = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0
        results['avg_loss'] = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        total_wins = sum(t.pnl for t in winning_trades)
        total_losses = abs(sum(t.pnl for t in losing_trades))
        results['profit_factor'] = total_wins / total_losses if total_losses > 0 else 0
        
        # Calculate drawdown
        equity_peak = self.initial_capital
        max_drawdown = 0
        for capital in self.equity_curve:
            if capital > equity_peak:
                equity_peak = capital
            drawdown = (equity_peak - capital) / equity_peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        results['max_drawdown'] = max_drawdown * 100
        
        # Sharpe ratio
        returns = np.diff(self.equity_curve) / np.array(self.equity_curve[:-1])
        if len(returns) > 0 and np.std(returns) > 0:
            results['sharpe_ratio'] = (np.mean(returns) / np.std(returns)) * np.sqrt(252)
        
        return results
    
    def print_results(self):
        """Print backtest results."""
        results = self.get_results()
        
        print(f"""
╔════════════════════════════════════════════════════════╗
║         ELLIOTT WAVE BOT - BACKTEST RESULTS            ║
╠════════════════════════════════════════════════════════╣
║ Initial Capital:        ${results['initial_capital']:>10,.2f}
║ Final Capital:          ${results['final_capital']:>10,.2f}
║ Total Return:           ${results['total_return_dollars']:>10,.2f}
║ Return %:               {results['total_return_percent']:>10.2f}%
╠════════════════════════════════════════════════════════╣
║ Total Trades:           {results['total_trades']:>10}
║ Winning Trades:         {results['winning_trades']:>10}
║ Losing Trades:          {results['losing_trades']:>10}
║ Win Rate:               {results['win_rate']:>10.2f}%
║ Avg Win:                ${results['avg_win']:>10,.2f}
║ Avg Loss:               ${results['avg_loss']:>10,.2f}
║ Profit Factor:          {results['profit_factor']:>10.2f}
║ Max Drawdown:           {results['max_drawdown']:>10.2f}%
║ Sharpe Ratio:           {results['sharpe_ratio']:>10.2f}
╚════════════════════════════════════════════════════════╝
        """)
        
        # Print trade log
        if results['trades']:
            print("\n📊 TRADE LOG:")
            print("=" * 100)
            print(f"{'#':<4} {'Type':<6} {'Entry Price':<12} {'Exit Price':<12} {'PnL $':<12} {'PnL %':<8} {'Exit Type':<12}")
            print("=" * 100)
            
            for i, trade in enumerate(results['trades'], 1):
                pnl_str = f"${trade.pnl:,.2f}" if trade.pnl else "OPEN"
                pnl_pct_str = f"{trade.pnl_percent:.2f}%" if trade.pnl_percent else "N/A"
                exit_price_str = f"${trade.exit_price:.2f}" if trade.exit_price else "N/A"
                print(f"{i:<4} {trade.signal_type:<6} ${trade.entry_price:<11,.2f} {exit_price_str:<12} {pnl_str:<12} {pnl_pct_str:<8} {trade.exit_type:<12}")
            
            print("=" * 100)
        else:
            print("\n⚠️  No trades executed during backtest period.")
