"""Live trading module for Elliott Wave bot."""

import pandas as pd
import numpy as np
from typing import Optional, Dict
from datetime import datetime
import time
import logging
from binance.client import Client
from binance.exceptions import BinanceAPIException

from src.wave_detector import WaveDetector, WavePattern\nfrom src.indicators import Indicators, SignalGenerator


class ExchangeConnector:
    \"\"\"Connector for Binance exchange API.\"\"\"
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        \"\"\"
        Initialize Binance connector.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet if True
        \"\"\"
        self.testnet = testnet
        
        if testnet:
            self.client = Client(api_key, api_secret, testnet=True)
        else:
            self.client = Client(api_key, api_secret)
        
        self.logger = logging.getLogger(__name__)
    
    def get_account_balance(self) -> Dict[str, float]:
        \"\"\"Get account balance for all assets.\"\"\"
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
            self.logger.error(f\"Error fetching account balance: {e}\")
            return {}
    
    def get_klines(self, symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
        \"\"\"
        Get historical klines (candlesticks).
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            interval: Kline interval (1m, 5m, 1h, 4h, 1d, etc.)
            limit: Number of klines to fetch (max 1000)
            
        Returns:
            DataFrame with OHLCV data
        \"\"\"
        try:
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
            
            df = pd.DataFrame(klines, columns=[\n                'Time', 'Open', 'High', 'Low', 'Close', 'Volume',\n                'Close Time', 'Quote Asset Volume', 'Number of Trades',\n                'Taker Buy Base', 'Taker Buy Quote', 'Ignore'\n            ])\n            \n            # Convert to numeric and set datetime index\n            df['Time'] = pd.to_datetime(df['Time'], unit='ms')\n            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:\n                df[col] = df[col].astype(float)\n            \n            df.set_index('Time', inplace=True)\n            \n            return df[['Open', 'High', 'Low', 'Close', 'Volume']]\n        \n        except BinanceAPIException as e:\n            self.logger.error(f\"Error fetching klines: {e}\")\n            return pd.DataFrame()\n    \n    def place_order(self, symbol: str, side: str, order_type: str, \n                   quantity: float, price: Optional[float] = None) -> Dict:\n        \"\"\"
        Place an order on Binance.\n        \n        Args:\n            symbol: Trading pair (e.g., 'BTCUSDT')\n            side: 'BUY' or 'SELL'\n            order_type: 'LIMIT' or 'MARKET'\n            quantity: Order quantity\n            price: Order price (required for LIMIT orders)\n            \n        Returns:\n            Order details\n        \"\"\"
        try:\n            if order_type == 'LIMIT' and price is None:\n                raise ValueError(\"Price required for LIMIT orders\")\n            \n            if order_type == 'LIMIT':\n                order = self.client.order_limit(\n                    symbol=symbol,\n                    side=side,\n                    quantity=quantity,\n                    price=price\n                )\n            else:\n                order = self.client.order_market(\n                    symbol=symbol,\n                    side=side,\n                    quantity=quantity\n                )\n            \n            self.logger.info(f\"Order placed: {side} {quantity} {symbol} @ {price}\")\n            return order\n        \n        except BinanceAPIException as e:\n            self.logger.error(f\"Error placing order: {e}\")\n            return {}\n    \n    def place_stop_loss_order(self, symbol: str, side: str, quantity: float, \n                             stop_price: float) -> Dict:\n        \"\"\"Place a stop loss order.\"\"\"\n        try:\n            order = self.client.order_stop_loss(\n                symbol=symbol,\n                side=side,\n                quantity=quantity,\n                stopPrice=stop_price\n            )\n            self.logger.info(f\"Stop loss order placed: {side} {quantity} {symbol} @ {stop_price}\")\n            return order\n        \n        except BinanceAPIException as e:\n            self.logger.error(f\"Error placing stop loss order: {e}\")\n            return {}\n    \n    def cancel_order(self, symbol: str, order_id: int) -> Dict:\n        \"\"\"Cancel an open order.\"\"\"\n        try:\n            result = self.client.cancel_order(symbol=symbol, orderId=order_id)\n            self.logger.info(f\"Order {order_id} cancelled\")\n            return result\n        \n        except BinanceAPIException as e:\n            self.logger.error(f\"Error cancelling order: {e}\")\n            return {}


class LiveTrader:\n    \"\"\"Live trading bot using Elliott Wave detection.\"\"\"\n    \n    def __init__(self, api_key: str, api_secret: str, symbol: str, \n                 timeframe: str = '1h', paper_trading: bool = True):\n        \"\"\"
        Initialize live trader.\n        \n        Args:\n            api_key: Binance API key\n            api_secret: Binance API secret\n            symbol: Trading pair (e.g., 'BTCUSDT')\n            timeframe: Kline interval (1m, 5m, 1h, 4h, 1d, etc.)\n            paper_trading: Use paper trading (simulation) if True\n        \"\"\"
        self.symbol = symbol\n        self.timeframe = timeframe\n        self.paper_trading = paper_trading\n        \n        self.exchange = ExchangeConnector(api_key, api_secret, testnet=paper_trading)\n        self.wave_detector = WaveDetector()\n        self.signals = SignalGenerator()\n        \n        # Logging\n        logging.basicConfig(level=logging.INFO)\n        self.logger = logging.getLogger(__name__)\n        \n        # Trading state\n        self.position = None\n        self.entry_price = None\n        self.quantity = None\n        \n        self.logger.info(f\"Initialized LiveTrader for {symbol} (Paper: {paper_trading})\")\n    \n    def get_current_data(self, limit: int = 100) -> pd.DataFrame:\n        \"\"\"Fetch current market data.\"\"\"\n        return self.exchange.get_klines(self.symbol, self.timeframe, limit=limit)\n    \n    def check_and_execute(self) -> Optional[Dict]:\n        \"\"\"
        Check for trading signals and execute if conditions are met.\n        \n        Returns:\n            Trade details if executed, None otherwise\n        \"\"\"
        # Get current data\n        data = self.get_current_data(limit=100)\n        \n        if data.empty:\n            self.logger.warning(\"Could not fetch market data\")\n            return None\n        \n        close_prices = data['Close']\n        high_prices = data['High']\n        low_prices = data['Low']\n        \n        # Detect wave patterns\n        pattern = self.wave_detector.get_latest_pattern(close_prices)\n        \n        if pattern is None or pattern.confidence < 0.70:\n            return None\n        \n        # Generate signal\n        signal = self.signals.generate_combined_signal(close_prices, high_prices, low_prices)\n        \n        current_price = close_prices.iloc[-1]\n        current_time = data.index[-1]\n        \n        # Entry logic\n        if self.position is None and pattern.pattern_type == \"impulse\":\n            if signal['confidence'] > 0.6:\n                self.logger.info(f\"\\n{'='*60}\")\n                self.logger.info(f\"ENTRY SIGNAL DETECTED @ {current_time}\")\n                self.logger.info(f\"Pattern: {pattern.pattern_type} (Confidence: {pattern.confidence:.2%})\")\n                self.logger.info(f\"Signal Confidence: {signal['confidence']:.2%}\")\n                self.logger.info(f\"Current Price: {current_price:.2f}\")\n                self.logger.info(f\"{'='*60}\\n\")\n                \n                # Get account balance\n                balance = self.exchange.get_account_balance()\n                base_asset = self.symbol.replace('USDT', '')\n                quote_balance = balance.get('USDT', {}).get('free', 0)\n                \n                if quote_balance > 0:\n                    # Calculate position size (use 50% of available capital)\n                    position_size = quote_balance * 0.5\n                    quantity = position_size / current_price\n                    \n                    if not self.paper_trading:\n                        # Place actual order\n                        order = self.exchange.place_order(\n                            self.symbol, 'BUY', 'MARKET', quantity\n                        )\n                        self.position = order.get('orderId')\n                    else:\n                        # Simulate in paper trading\n                        self.position = \"PAPER\"\n                    \n                    self.entry_price = current_price\n                    self.quantity = quantity\n                    \n                    self.logger.info(f\"Position opened: {quantity:.4f} {base_asset}\")\n                    \n                    return {\n                        'type': 'ENTRY',\n                        'time': current_time,\n                        'price': current_price,\n                        'quantity': quantity,\n                        'pattern': pattern.pattern_type\n                    }\n        \n        # Exit logic\n        elif self.position is not None:\n            targets = self.wave_detector.predict_next_target(pattern, close_prices)\n            take_profit = targets.get('likely', self.entry_price * 1.05)\n            support = self.wave_detector.get_support_resistance(pattern)\n            stop_loss = support.get('support', self.entry_price * 0.98)\n            \n            # Check take profit\n            if current_price >= take_profit:\n                self.logger.info(f\"\\n{'='*60}\")\n                self.logger.info(f\"TAKE PROFIT @ {current_time}\")\n                self.logger.info(f\"Exit Price: {current_price:.2f}\")\n                pnl = (current_price - self.entry_price) * self.quantity\n                pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100\n                self.logger.info(f\"PnL: {pnl:.2f} ({pnl_percent:.2f}%)\")\n                self.logger.info(f\"{'='*60}\\n\")\n                \n                if not self.paper_trading:\n                    self.exchange.place_order(\n                        self.symbol, 'SELL', 'MARKET', self.quantity\n                    )\n                \n                self.position = None\n                self.entry_price = None\n                self.quantity = None\n                \n                return {'type': 'EXIT', 'time': current_time, 'price': current_price}\n            \n            # Check stop loss\n            elif current_price <= stop_loss:\n                self.logger.info(f\"\\n{'='*60}\")\n                self.logger.info(f\"STOP LOSS @ {current_time}\")\n                self.logger.info(f\"Exit Price: {current_price:.2f}\")\n                pnl = (current_price - self.entry_price) * self.quantity\n                pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100\n                self.logger.info(f\"PnL: {pnl:.2f} ({pnl_percent:.2f}%)\")\n                self.logger.info(f\"{'='*60}\\n\")\n                \n                if not self.paper_trading:\n                    self.exchange.place_order(\n                        self.symbol, 'SELL', 'MARKET', self.quantity\n                    )\n                \n                self.position = None\n                self.entry_price = None\n                self.quantity = None\n                \n                return {'type': 'STOP', 'time': current_time, 'price': current_price}\n        \n        return None\n    \n    def run(self, check_interval: int = 60):\n        \"\"\"
        Run the trading bot continuously.\n        \n        Args:\n            check_interval: Seconds between checks\n        \"\"\"
        self.logger.info(f\"Starting {'PAPER' if self.paper_trading else 'LIVE'} trading bot for {self.symbol}\")\n        \n        try:\n            while True:\n                self.check_and_execute()\n                time.sleep(check_interval)\n        \n        except KeyboardInterrupt:\n            self.logger.info(\"\\nStopping bot...\")\n        \n        except Exception as e:\n            self.logger.error(f\"Unexpected error: {e}\", exc_info=True)\n