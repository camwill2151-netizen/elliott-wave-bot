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
    
    def __init__(self, indexer_url: str = "https://indexer.dydx.trade/v1"):
        """
        Initialize dYdX Indexer client.
        
        Args:
            indexer_url: Base URL for dYdX indexer (mainnet or testnet)
        """
        self.indexer_url = indexer_url
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
            url = f"{self.indexer_url}/perpetualMarkets"
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
            url = f"{self.indexer_url}/perpetualMarkets/{market_id}/candles"
            params = {"resolution": resolution, "limit": limit}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 200:
                        self.logger.error(f"HTTP {response.status} for {market_id}: {await response.text()}")
                        return pd.DataFrame()
                    
                    data = await response.json()
            
            if not data or not isinstance(data, dict):
                self.logger.error(f"Invalid response format: {data}")
                return pd.DataFrame()
            
            if "candles" not in data:
                self.logger.error(f"No 'candles' key in response: {data.keys()}")
                return pd.DataFrame()
            
            candles = data.get("candles", [])
            
            if not candles:
                self.logger.warning(f"No candles returned for {market_id}")
                return pd.DataFrame()
            
            df = pd.DataFrame(candles)
            
            # Convert timestamp to datetime
            if "startedAt" in df.columns:
                df["startedAt"] = pd.to_datetime(df["startedAt"])
            
            # Convert price/size to float
            for col in ["open", "high", "low", "close", "baseTokenVolume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Rename for consistency
            df = df.rename(columns={
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "baseTokenVolume": "Volume",
                "startedAt": "Time"
            })
            
            if "Time" in df.columns:
                df.set_index("Time", inplace=True)
            
            # Only return if we have the required columns
            required_cols = ["Open", "High", "Low", "Close", "Volume"]
            available_cols = [col for col in required_cols if col in df.columns]
            
            if available_cols:
                return df[available_cols]
            else:
                self.logger.error(f"Missing required columns. Available: {df.columns.tolist()}")
                return pd.DataFrame()
        
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
            url = f"{self.indexer_url}/perpetualMarkets/{market_id}/orderbook"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
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
            url = f"{self.indexer_url}/perpetualMarkets/{market_id}/trades"
            params = {"limit": limit}
            
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
            url = f"{self.indexer_url}/perpetualMarkets/{market_id}/fundingRate"
            
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
