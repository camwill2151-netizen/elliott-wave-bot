"""dYdX v4 Exchange Integration Module."""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import aiohttp

# Optional: dYdX v4 client imports for advanced wallet features
# Most users won't need these - the REST API works fine
try:
    from cosmpy.aerial.client import LedgerClient
    from cosmpy.aerial.wallet import LocalWallet
    from cosmpy.crypto.keypairs import PrivateKey
    HAS_COSMPY = True
except ImportError:
    HAS_COSMPY = False
    print("Note: For wallet features, install cosmpy with: pip install cosmpy")


class DydxIndexerClient:
    """Client for dYdX v4 Indexer (read-only operations)."""
    
    def __init__(self, indexer_url: str = "https://indexer.dydx.trade"):
        """
        Initialize dYdX Indexer client.
        
        Args:
            indexer_url: Base URL for dYdX indexer (mainnet or testnet)
        """
        self.indexer_url = indexer_url.rstrip('/')
        self.logger = logging.getLogger(__name__)
        self.session = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def get_markets(self) -> Dict:
        """
        Get all perpetual markets.
        
        Returns:
            Dictionary of markets data
        """
        try:
            url = f"{self.indexer_url}/v4/perpetualMarkets"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        self.logger.error(f"HTTP {response.status}: {await response.text()}")
                        return {}
        except Exception as e:
            self.logger.error(f"Error fetching markets: {e}")
            return {}
    
    async def get_market_candles(self, market_id: str, resolution: str = "1HOUR",
                                 limit: int = 100) -> pd.DataFrame:
        """
        Get candlestick data for a market.
        
        Args:
            market_id: Market identifier (e.g., "BTC-USD")
            resolution: Candle resolution (1MIN, 5MIN, 15MIN, 30MIN, 1HOUR, 4HOUR, 1DAY)
            limit: Number of candles to fetch
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            # dYdX v4 API endpoint format
            url = f"{self.indexer_url}/v4/candles"
            params = {
                "market": market_id,
                "resolution": resolution,
                "limit": limit
            }
            
            self.logger.info(f"Fetching candles from: {url} with params: {params}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    response_text = await response.text()
                    
                    if response.status != 200:
                        self.logger.error(f"HTTP {response.status} for {market_id}: {response_text[:200]}")
                        return pd.DataFrame()
                    
                    try:
                        data = json.loads(response_text)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Invalid JSON response: {response_text[:200]}")
                        return pd.DataFrame()
            
            if not data or not isinstance(data, dict):
                self.logger.error(f"Invalid response format: {type(data)}")
                return pd.DataFrame()
            
            # Try different possible response formats
            candles = data.get("candles") or data.get("data") or data
            
            if isinstance(candles, dict) and "candles" in candles:
                candles = candles["candles"]
            
            if not isinstance(candles, list):
                self.logger.error(f"No candles list in response. Keys: {data.keys() if isinstance(data, dict) else 'N/A'}")
                return pd.DataFrame()
            
            if not candles:
                self.logger.warning(f"No candles returned for {market_id}")
                return pd.DataFrame()
            
            self.logger.info(f"Got {len(candles)} candles for {market_id}")
            
            df = pd.DataFrame(candles)
            
            # Find and rename timestamp column (could be startedAt, time, timestamp, etc)
            time_col = None
            for col in ["startedAt", "time", "timestamp", "Time"]:
                if col in df.columns:
                    time_col = col
                    break
            
            if time_col:
                df[time_col] = pd.to_datetime(df[time_col])
                df.rename(columns={time_col: "Time"}, inplace=True)
                df.set_index("Time", inplace=True)
            
            # Convert price/size to float - handle various naming conventions
            price_cols = {
                "open": "Open", "Open": "Open",
                "high": "High", "High": "High",
                "low": "Low", "Low": "Low",
                "close": "Close", "Close": "Close",
                "baseTokenVolume": "Volume", "volume": "Volume", "Volume": "Volume"
            }
            
            for old_col, new_col in price_cols.items():
                if old_col in df.columns:
                    df[old_col] = pd.to_numeric(df[old_col], errors='coerce')
                    if old_col != new_col:
                        df.rename(columns={old_col: new_col}, inplace=True)
            
            # Only return if we have the required columns
            required_cols = ["Open", "High", "Low", "Close"]
            available_cols = [col for col in required_cols if col in df.columns]
            
            if len(available_cols) < 4:
                self.logger.error(f"Missing OHLC columns. Available: {df.columns.tolist()}")
                return pd.DataFrame()
            
            # Add Volume if available
            if "Volume" in df.columns:
                available_cols.append("Volume")
            
            return df[available_cols]
        
        except Exception as e:
            self.logger.error(f"Error fetching candles for {market_id}: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    async def get_market_orderbook(self, market_id: str) -> Dict:
        """
        Get current orderbook for a market.
        
        Args:
            market_id: Market identifier
            
        Returns:
            Orderbook data (bids, asks)
        """
        try:
            url = f"{self.indexer_url}/v4/orderbooks"
            params = {"market": market_id}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return await response.json()
                    return {}
        
        except Exception as e:
            self.logger.error(f"Error fetching orderbook for {market_id}: {e}")
            return {}
    
    async def get_market_trades(self, market_id: str, limit: int = 100) -> List[Dict]:
        """
        Get recent trades for a market.
        
        Args:
            market_id: Market identifier
            limit: Number of trades to fetch
            
        Returns:
            List of recent trades
        """
        try:
            url = f"{self.indexer_url}/v4/trades"
            params = {"market": market_id, "limit": limit}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("trades", [])
                    return []
        
        except Exception as e:
            self.logger.error(f"Error fetching trades for {market_id}: {e}")
            return []
    
    async def get_market_funding(self, market_id: str) -> Dict:
        """
        Get funding rate data for a market.
        
        Args:
            market_id: Market identifier
            
        Returns:
            Funding rate information
        """
        try:
            url = f"{self.indexer_url}/v4/perpetualMarkets/{market_id}/fundingRate"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return await response.json()
                    return {}
        
        except Exception as e:
            self.logger.error(f"Error fetching funding for {market_id}: {e}")
            return {}


class DydxChainClient:
    """Client for dYdX v4 Chain (read/write operations with wallet)."""
    
    def __init__(self, private_key: str, network: str = "mainnet"):
        """
        Initialize dYdX Chain client.
        
        Args:
            private_key: Private key (hex string without 0x prefix)
            network: Network to connect to ("mainnet" or "testnet")
        """
        if not HAS_COSMPY:
            raise ImportError("cosmpy is required for wallet operations. Install with: pip install cosmpy")
        
        self.logger = logging.getLogger(__name__)
        self.network = network
        
        # Configure network
        if network == "testnet":
            self.chain_id = "dydx-testnet-1"
            self.node_url = "https://dydx-testnet-lcd.allthatnode.com:1317"
            self.grpc_url = "dydx-testnet-grpc.allthatnode.com:9090"
        else:
            self.chain_id = "dydx-mainnet-1"
            self.node_url = "https://dydx-mainnet-lcd.allthatnode.com:1317"
            self.grpc_url = "dydx-mainnet-grpc.allthatnode.com:9090"
        
        # Initialize wallet
        try:
            self.private_key_obj = PrivateKey(bytes.fromhex(private_key))
            self.wallet = LocalWallet(self.private_key_obj)
            self.account_address = self.wallet.public_key().to_public_key().to_account()
            
            self.logger.info(f"Initialized wallet: {self.account_address}")
        except Exception as e:
            self.logger.error(f"Error initializing wallet: {e}")
            raise
    
    async def get_account(self) -> Dict:
        """Get account information."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.node_url}/cosmos/auth/v1beta1/accounts/{self.account_address}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return await response.json()
                    return {}
        except Exception as e:
            self.logger.error(f"Error fetching account: {e}")
            return {}
    
    async def get_balances(self) -> Dict[str, float]:
        """
        Get account balances.
        
        Returns:
            Dictionary of asset -> balance
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.node_url}/cosmos/bank/v1beta1/balances/{self.account_address}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 200:
                        return {}
                    data = await response.json()
            
            balances = {}
            for balance in data.get("balances", []):
                denom = balance["denom"]
                amount = float(balance["amount"]) / 1e18  # Convert from smallest unit
                balances[denom] = amount
            
            return balances
        
        except Exception as e:
            self.logger.error(f"Error fetching balances: {e}")
            return {}
    
    async def get_positions(self) -> List[Dict]:
        """
        Get open perpetual positions.
        
        Returns:
            List of position dictionaries
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.node_url}/dydxprotocol/perpetuals/positions"
                params = {"address": self.account_address}
                
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("positions", [])
                    return []
        
        except Exception as e:
            self.logger.error(f"Error fetching positions: {e}")
            return []
    
    def place_order(self, market_id: str, side: str, size: float, 
                   price: float, leverage: float = 1.0,
                   order_type: str = "LIMIT") -> Optional[Dict]:
        """
        Place an order (requires wallet signing).
        
        Note: Full implementation requires more complex transaction building.
        This is a placeholder showing the structure.
        
        Args:
            market_id: Market to trade
            side: "BUY" or "SELL"
            size: Order size
            price: Order price
            leverage: Leverage multiplier (1-20)
            order_type: "LIMIT" or "MARKET"
            
        Returns:
            Order details if successful
        """
        self.logger.warning("Place order requires full transaction signing implementation")
        self.logger.info(f"Order: {side} {size} {market_id} @ {price} (Leverage: {leverage}x)")
        return None


class DydxExchangeConnector:
    """High-level connector for dYdX v4 with both indexer and chain clients."""
    
    def __init__(self, private_key: Optional[str] = None, network: str = "mainnet"):
        """
        Initialize dYdX exchange connector.
        
        Args:
            private_key: Private key for trading (optional, for read-only set to None)
            network: "mainnet" or "testnet"
        """
        self.logger = logging.getLogger(__name__)
        self.indexer = DydxIndexerClient()
        self.chain = None
        self.network = network
        
        if private_key:
            self.chain = DydxChainClient(private_key, network=network)
    
    async def get_price_data(self, market_id: str, resolution: str = "1HOUR",
                            limit: int = 100) -> pd.DataFrame:
        """Fetch OHLCV data for analysis."""
        return await self.indexer.get_market_candles(market_id, resolution, limit)
    
    async def get_current_price(self, market_id: str) -> float:
        """Get the current price of a market."""
        candles = await self.indexer.get_market_candles(market_id, resolution="1MIN", limit=1)
        
        if candles.empty:
            return None
        
        return float(candles["Close"].iloc[-1])
    
    async def get_funding_rate(self, market_id: str) -> Optional[float]:
        """Get current funding rate."""
        funding_data = await self.indexer.get_market_funding(market_id)
        
        if funding_data and isinstance(funding_data, dict) and "fundingRate" in funding_data:
            return float(funding_data["fundingRate"]["fundingRate"])
        
        return None
    
    def get_supported_markets(self) -> List[str]:
        """Get list of supported perpetual markets."""
        return [
            "BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "MATIC-USD",
            "ARBITRUM-USD", "DOGE-USD", "XRP-USD", "SUI-USD", "LINK-USD"
        ]
