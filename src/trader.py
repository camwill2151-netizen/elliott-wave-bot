"""Live trading module for Elliott Wave bot."""

import pandas as pd
import numpy as np
from typing import Optional, Dict
from datetime import datetime
import time
import logging
from binance.client import Client
from binance.exceptions import BinanceAPIException

from src.wave_detector import WaveDetector, WavePattern
from src.indicators import Indicators, SignalGenerator


class ExchangeConnector:
    """Connector for Binance exchange API."""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        """
        Initialize Binance connector.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet if True
        """
        self.testnet = testnet
        
        if testnet:
            self.client = Client(api_key, api_secret, testnet=True)
        else:
            self.client = Client(api_key, api_secret)
        
        self.logger = logging.getLogger(__name__)
    
    def get_account_balance(self) -> Dict[str, float]:
        """Get account balance for all assets."""
        try:
            account = self.client.get_account()
            balances = {}
            
            for balance in account['balances']:
                free = float(balance['free'])
                locked = float(balance['locked'])
                total = free + locked
                
                if total > 0:
                    balances[balance['asset']] = {
                        'free': free,
                        'locked': locked,
                        'total': total
                    }
            
            return balances
        except BinanceAPIException as e:
            self.logger.error(f"Error fetching account balance: {e}")
            return {}
    
    def get_klines(self, symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
        """
        Get historical klines (candlesticks).
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            interval: Kline interval (1m, 5m, 1h, 4h, 1d, etc.)
            limit: Number of klines to fetch (max 1000)
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
            
            df = pd.DataFrame(klines, columns=[
                'Time', 'Open', 'High', 'Low', 'Close', 'Volume',
                'Close Time', 'Quote Asset Volume', 'Number of Trades',
                'Taker Buy Base', 'Taker Buy Quote', 'Ignore'
            ])
            
            # Convert to numeric and set datetime index
            df['Time'] = pd.to_datetime(df['Time'], unit='ms')
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                df[col] = df[col].astype(float)
            
            df.set_index('Time', inplace=True)
            
            return df[['Open', 'High', 'Low', 'Close', 'Volume']]
        
        except BinanceAPIException as e:
            self.logger.error(f"Error fetching klines: {e}")
            return pd.DataFrame()
    
    def place_order(self, symbol: str, side: str, order_type: str, 
                   quantity: float, price: Optional[float] = None) -> Dict:
        """
        Place an order on Binance.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            side: 'BUY' or 'SELL'
            order_type: 'LIMIT' or 'MARKET'
            quantity: Order quantity
            price: Order price (required for LIMIT orders)
            
        Returns:
            Order details
        """
        try:
            if order_type == 'LIMIT' and price is None:
                raise ValueError("Price required for LIMIT orders")
            
            if order_type == 'LIMIT':
                order = self.client.order_limit(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=price
                )
            else:
                order = self.client.order_market(
                    symbol=symbol,
                    side=side,
                    quantity=quantity
                )
            
            self.logger.info(f"Order placed: {side} {quantity} {symbol} @ {price}")
            return order
        
        except BinanceAPIException as e:
            self.logger.error(f"Error placing order: {e}")
            return {}
    
    def place_stop_loss_order(self, symbol: str, side: str, quantity: float, 
                             stop_price: float) -> Dict:
        """Place a stop loss order."""
        try:
            order = self.client.order_stop_loss(
                symbol=symbol,
                side=side,
                quantity=quantity,
                stopPrice=stop_price
            )
            self.logger.info(f"Stop loss order placed: {side} {quantity} {symbol} @ {stop_price}")
            return order
        
        except BinanceAPIException as e:
            self.logger.error(f"Error placing stop loss order: {e}")
            return {}
    
    def cancel_order(self, symbol: str, order_id: int) -> Dict:
        """Cancel an open order."""
        try:
            result = self.client.cancel_order(symbol=symbol, orderId=order_id)
            self.logger.info(f"Order {order_id} cancelled")
            return result
        
        except BinanceAPIException as e:
            self.logger.error(f"Error cancelling order: {e}")
            return {}


class LiveTrader:
    """Live trading bot using Elliott Wave detection."""
    
    def __init__(self, api_key: str, api_secret: str, symbol: str, 
                 timeframe: str = '1h', paper_trading: bool = True):
        """
        Initialize live trader.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            symbol: Trading pair (e.g., 'BTCUSDT')
            timeframe: Kline interval (1m, 5m, 1h, 4h, 1d, etc.)
            paper_trading: Use paper trading (simulation) if True
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.paper_trading = paper_trading
        
        self.exchange = ExchangeConnector(api_key, api_secret, testnet=paper_trading)
        self.wave_detector = WaveDetector()
        self.signals = SignalGenerator()
        
        # Logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Trading state
        self.position = None
        self.entry_price = None
        self.quantity = None
        
        self.logger.info(f"Initialized LiveTrader for {symbol} (Paper: {paper_trading})")
    
    def get_current_data(self, limit: int = 100) -> pd.DataFrame:
        """Fetch current market data."""
        return self.exchange.get_klines(self.symbol, self.timeframe, limit=limit)
    
    def check_and_execute(self) -> Optional[Dict]:
        """
        Check for trading signals and execute if conditions are met.
        
        Returns:
            Trade details if executed, None otherwise
        """
        # Get current data
        data = self.get_current_data(limit=100)
        
        if data.empty:
            self.logger.warning("Could not fetch market data")
            return None
        
        close_prices = data['Close']
        high_prices = data['High']
        low_prices = data['Low']
        
        # Detect wave patterns
        pattern = self.wave_detector.get_latest_pattern(close_prices)
        
        if pattern is None or pattern.confidence < 0.70:
            return None
        
        # Generate signal
        signal = self.signals.generate_combined_signal(close_prices, high_prices, low_prices)
        
        current_price = close_prices.iloc[-1]
        current_time = data.index[-1]
        
        # Entry logic
        if self.position is None and pattern.pattern_type == "impulse":
            if signal['confidence'] > 0.6:
                self.logger.info(f"\n{'='*60}")
                self.logger.info(f"ENTRY SIGNAL DETECTED @ {current_time}")
                self.logger.info(f"Pattern: {pattern.pattern_type} (Confidence: {pattern.confidence:.2%})")
                self.logger.info(f"Signal Confidence: {signal['confidence']:.2%}")
                self.logger.info(f"Current Price: {current_price:.2f}")
                self.logger.info(f"{'='*60}\n")
                
                # Get account balance
                balance = self.exchange.get_account_balance()
                base_asset = self.symbol.replace('USDT', '')
                quote_balance = balance.get('USDT', {}).get('free', 0)
                
                if quote_balance > 0:
                    # Calculate position size (use 50% of available capital)
                    position_size = quote_balance * 0.5
                    quantity = position_size / current_price
                    
                    if not self.paper_trading:
                        # Place actual order
                        order = self.exchange.place_order(
                            self.symbol, 'BUY', 'MARKET', quantity
                        )
                        self.position = order.get('orderId')
                    else:
                        # Simulate in paper trading
                        self.position = "PAPER"
                    
                    self.entry_price = current_price
                    self.quantity = quantity
                    
                    self.logger.info(f"Position opened: {quantity:.4f} {base_asset}")
                    
                    return {
                        'type': 'ENTRY',
                        'time': current_time,
                        'price': current_price,
                        'quantity': quantity,
                        'pattern': pattern.pattern_type
                    }
        
        # Exit logic
        elif self.position is not None:
            targets = self.wave_detector.predict_next_target(pattern, close_prices)
            take_profit = targets.get('likely', self.entry_price * 1.05)
            support = self.wave_detector.get_support_resistance(pattern)
            stop_loss = support.get('support', self.entry_price * 0.98)
            
            # Check take profit
            if current_price >= take_profit:
                self.logger.info(f"\n{'='*60}")
                self.logger.info(f"TAKE PROFIT @ {current_time}")
                self.logger.info(f"Exit Price: {current_price:.2f}")
                pnl = (current_price - self.entry_price) * self.quantity
                pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100
                self.logger.info(f"PnL: {pnl:.2f} ({pnl_percent:.2f}%)")
                self.logger.info(f"{'='*60}\n")
                
                if not self.paper_trading:
                    self.exchange.place_order(
                        self.symbol, 'SELL', 'MARKET', self.quantity
                    )
                
                self.position = None
                self.entry_price = None
                self.quantity = None
                
                return {'type': 'EXIT', 'time': current_time, 'price': current_price}
            
            # Check stop loss
            elif current_price <= stop_loss:
                self.logger.info(f"\n{'='*60}")
                self.logger.info(f"STOP LOSS @ {current_time}")
                self.logger.info(f"Exit Price: {current_price:.2f}")
                pnl = (current_price - self.entry_price) * self.quantity
                pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100
                self.logger.info(f"PnL: {pnl:.2f} ({pnl_percent:.2f}%)")
                self.logger.info(f"{'='*60}\n")
                
                if not self.paper_trading:
                    self.exchange.place_order(
                        self.symbol, 'SELL', 'MARKET', self.quantity
                    )
                
                self.position = None
                self.entry_price = None
                self.quantity = None
                
                return {'type': 'STOP', 'time': current_time, 'price': current_price}
        
        return None
    
    def run(self, check_interval: int = 60):
        """
        Run the trading bot continuously.
        
        Args:
            check_interval: Seconds between checks
        """
        self.logger.info(f"Starting {'PAPER' if self.paper_trading else 'LIVE'} trading bot for {self.symbol}")
        
        try:
            while True:
                self.check_and_execute()
                time.sleep(check_interval)
        
        except KeyboardInterrupt:
            self.logger.info("\nStopping bot...")
        
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}", exc_info=True)
