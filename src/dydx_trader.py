"""Live trading module for dYdX v4 perpetual exchanges."""

import asyncio
import pandas as pd
import logging
from typing import Optional, Dict
from datetime import datetime
from dataclasses import dataclass

from src.wave_detector import WaveDetector, WavePattern
from src.indicators import Indicators, SignalGenerator
from src.dydx_connector import DydxExchangeConnector


@dataclass
class DydxPosition:
    """Represents an open perpetual position on dYdX."""
    market_id: str
    side: str  # "LONG" or "SHORT"
    size: float
    entry_price: float
    leverage: float
    margin: float
    unrealized_pnl: float = 0.0
    liquidation_price: float = 0.0
    entry_time: datetime = None
    
    def __post_init__(self):
        if self.entry_time is None:
            self.entry_time = datetime.now()
    
    def update_pnl(self, current_price: float):
        """Update unrealized PnL based on current price."""
        if self.side == "LONG":
            self.unrealized_pnl = (current_price - self.entry_price) * self.size
        else:  # SHORT
            self.unrealized_pnl = (self.entry_price - current_price) * self.size
    
    def calculate_liquidation_price(self, maintenance_margin: float = 0.05):
        """Calculate liquidation price based on leverage and maintenance margin."""
        if self.side == "LONG":
            # Long position: price below this triggers liquidation
            self.liquidation_price = self.entry_price * (1 - (1 / self.leverage) + maintenance_margin)
        else:  # SHORT
            # Short position: price above this triggers liquidation
            self.liquidation_price = self.entry_price * (1 + (1 / self.leverage) - maintenance_margin)


class DydxLiveTrader:
    """Live trading bot for dYdX v4 perpetuals using Elliott Wave detection."""
    
    def __init__(self, private_key: str, market_id: str = "BTC-USD",
                 leverage: float = 2.0, network: str = "testnet"):
        """
        Initialize dYdX trader.
        
        Args:
            private_key: Private key for wallet signing (hex format)
            market_id: Market to trade (e.g., "BTC-USD")
            leverage: Leverage multiplier (1-20, default 2x)
            network: "mainnet" or "testnet"
        """
        self.market_id = market_id
        self.leverage = leverage
        self.network = network
        
        # Initialize components
        self.exchange = DydxExchangeConnector(private_key=private_key, network=network)
        self.wave_detector = WaveDetector()
        self.signals = SignalGenerator()
        
        # Trading state
        self.position: Optional[DydxPosition] = None
        self.trading_history = []
        
        # Logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"Initialized DydxLiveTrader for {market_id} (Leverage: {leverage}x, Network: {network})")
    
    async def fetch_market_data(self, limit: int = 100) -> pd.DataFrame:
        """Fetch OHLCV data for analysis."""
        return await self.exchange.get_price_data(self.market_id, resolution="1HOUR", limit=limit)
    
    async def check_signal(self) -> Optional[Dict]:
        """
        Check for Elliott Wave signals and execute trades.
        
        Returns:
            Signal details if triggered, None otherwise
        """
        try:
            # Fetch market data
            data = await self.fetch_market_data(limit=100)
            
            if data.empty:
                self.logger.warning("Could not fetch market data")
                return None
            
            close_prices = data["Close"]
            high_prices = data["High"]
            low_prices = data["Low"]
            current_price = float(close_prices.iloc[-1])
            current_time = data.index[-1]
            
            # Get funding rate
            funding_rate = await self.exchange.get_funding_rate(self.market_id)
            self.logger.info(f"Current Price: {current_price:.2f}, Funding Rate: {funding_rate:.4f}%")
            
            # Detect Elliott Wave patterns
            pattern = self.wave_detector.get_latest_pattern(close_prices)
            
            if pattern is None or pattern.confidence < 0.70:
                return None
            
            # Generate trading signal
            signal = self.signals.generate_combined_signal(close_prices, high_prices, low_prices)
            
            # Entry logic
            if self.position is None:
                return await self._handle_entry(pattern, signal, current_price, current_time, funding_rate, close_prices)
            
            # Exit logic
            else:
                return await self._handle_exit(pattern, signal, current_price, current_time, close_prices)
        
        except Exception as e:
            self.logger.error(f"Error checking signal: {e}", exc_info=True)
            return None
    
    async def _handle_entry(self, pattern: WavePattern, signal: Dict,
                           current_price: float, current_time: datetime,
                           funding_rate: float, close_prices: pd.Series) -> Optional[Dict]:
        """Handle entry signal."""
        if signal["confidence"] < 0.6:
            return None
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"ENTRY SIGNAL @ {current_time}")
        self.logger.info(f"Pattern: {pattern.pattern_type.upper()} (Confidence: {pattern.confidence:.2%})")
        self.logger.info(f"Signal Confidence: {signal['confidence']:.2%}")
        self.logger.info(f"Current Price: {current_price:.2f}")
        self.logger.info(f"Funding Rate: {funding_rate:.4f}%")
        
        # Determine trade direction based on pattern
        if pattern.pattern_type == "impulse":
            side = "LONG"
            direction_text = "GOING LONG 📈"
        else:
            side = "SHORT"
            direction_text = "GOING SHORT 📉"
        
        self.logger.info(f"{direction_text}")
        
        # Calculate position size (simplified: assume $1000 margin per position)
        margin = 1000  # $1000 margin
        position_size = (margin * self.leverage) / current_price
        
        # Calculate stop loss and take profit
        support_levels = self.wave_detector.get_support_resistance(pattern)
        targets = self.wave_detector.predict_next_target(pattern, close_prices)
        
        if side == "LONG":
            stop_loss = support_levels.get("support", current_price * 0.98)
            take_profit = targets.get("likely", current_price * 1.05)
        else:  # SHORT
            stop_loss = support_levels.get("resistance", current_price * 1.02)
            take_profit = targets.get("likely", current_price * 0.95)
        
        # Create position object
        self.position = DydxPosition(
            market_id=self.market_id,
            side=side,
            size=position_size,
            entry_price=current_price,
            leverage=self.leverage,
            margin=margin
        )
        self.position.calculate_liquidation_price()
        
        self.logger.info(f"Position Opened:")
        self.logger.info(f"  Size: {position_size:.4f} {self.market_id.split('-')[0]}")
        self.logger.info(f"  Margin: ${margin}")
        self.logger.info(f"  Leverage: {self.leverage}x")
        self.logger.info(f"  Stop Loss: {stop_loss:.2f}")
        self.logger.info(f"  Take Profit: {take_profit:.2f}")
        self.logger.info(f"  Liquidation Price: {self.position.liquidation_price:.2f}")
        self.logger.info(f"{'='*70}\n")
        
        return {
            "type": "ENTRY",
            "time": current_time,
            "price": current_price,
            "side": side,
            "size": position_size,
            "leverage": self.leverage,
            "pattern": pattern.pattern_type
        }
    
    async def _handle_exit(self, pattern: WavePattern, signal: Dict,
                          current_price: float, current_time: datetime,
                          close_prices: pd.Series) -> Optional[Dict]:
        """Handle exit signal."""
        self.position.update_pnl(current_price)
        
        # Get exit targets
        targets = self.wave_detector.predict_next_target(pattern, close_prices)
        
        if self.position.side == "LONG":
            take_profit = targets.get("likely", self.position.entry_price * 1.05)
            stop_loss = self.wave_detector.get_support_resistance(pattern).get("support",
                                                                              self.position.entry_price * 0.98)
        else:  # SHORT
            take_profit = targets.get("likely", self.position.entry_price * 0.95)
            stop_loss = self.wave_detector.get_support_resistance(pattern).get("resistance",
                                                                              self.position.entry_price * 1.02)
        
        exit_reason = None
        exit_type = None
        
        # Check exit conditions
        if self.position.side == "LONG":
            if current_price >= take_profit:
                exit_reason = "TAKE PROFIT"
                exit_type = "TP"
            elif current_price <= stop_loss:
                exit_reason = "STOP LOSS"
                exit_type = "SL"
            elif current_price <= self.position.liquidation_price:
                exit_reason = "LIQUIDATION"
                exit_type = "LIQ"
        else:  # SHORT
            if current_price <= take_profit:
                exit_reason = "TAKE PROFIT"
                exit_type = "TP"
            elif current_price >= stop_loss:
                exit_reason = "STOP LOSS"
                exit_type = "SL"
            elif current_price >= self.position.liquidation_price:
                exit_reason = "LIQUIDATION"
                exit_type = "LIQ"
        
        if exit_reason:
            self.logger.info(f"\n{'='*70}")
            self.logger.info(f"{exit_reason} @ {current_time} - {exit_type}")
            self.logger.info(f"Entry Price: {self.position.entry_price:.2f}")
            self.logger.info(f"Exit Price: {current_price:.2f}")
            self.logger.info(f"Unrealized PnL: ${self.position.unrealized_pnl:.2f}")
            self.logger.info(f"PnL %: {(self.position.unrealized_pnl / self.position.margin) * 100:.2f}%")
            self.logger.info(f"{'='*70}\n")
            
            # Record in history
            self.trading_history.append({
                "market": self.market_id,
                "side": self.position.side,
                "entry_price": self.position.entry_price,
                "exit_price": current_price,
                "size": self.position.size,
                "leverage": self.position.leverage,
                "pnl": self.position.unrealized_pnl,
                "pnl_percent": (self.position.unrealized_pnl / self.position.margin) * 100,
                "exit_reason": exit_reason,
                "entry_time": self.position.entry_time,
                "exit_time": current_time
            })
            
            # Close position
            self.position = None
            
            return {
                "type": "EXIT",
                "time": current_time,
                "price": current_price,
                "reason": exit_reason,
                "pnl": self.position.unrealized_pnl if self.position else None
            }
        
        return None
    
    async def run(self, check_interval: int = 60):
        """
        Run the trading bot continuously.
        
        Args:
            check_interval: Seconds between checks
        """
        self.logger.info(f"Starting dYdX trading bot for {self.market_id}")
        self.logger.info(f"Network: {self.network}")
        self.logger.info(f"Leverage: {self.leverage}x")
        self.logger.info("="*70)
        
        try:
            while True:
                await self.check_signal()
                await asyncio.sleep(check_interval)
        
        except KeyboardInterrupt:
            self.logger.info("\\nStopping bot...")
            self._print_summary()
        
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}", exc_info=True)
    
    def _print_summary(self):
        """Print trading session summary."""
        if not self.trading_history:
            self.logger.info("No trades executed.")
            return
        
        df = pd.DataFrame(self.trading_history)
        total_trades = len(df)
        winning_trades = (df["pnl"] > 0).sum()
        losing_trades = (df["pnl"] < 0).sum()
        total_pnl = df["pnl"].sum()
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info("TRADING SESSION SUMMARY")
        self.logger.info(f"{'='*70}")
        self.logger.info(f"Total Trades: {total_trades}")
        self.logger.info(f"Winning Trades: {winning_trades}")
        self.logger.info(f"Losing Trades: {losing_trades}")
        self.logger.info(f"Win Rate: {win_rate:.2f}%")
        self.logger.info(f"Total PnL: ${total_pnl:.2f}")
        self.logger.info(f"Average Trade PnL: ${df['pnl'].mean():.2f}")
        self.logger.info(f"{'='*70}")
