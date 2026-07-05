"""dYdX v4 Exchange Integration Module - 2026 API Structure."""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import aiohttp

# Optional: dYdX v4 client imports for advanced wallet features
try:
    from cosmpy.aerial.client import LedgerClient
    from cosmpy.aerial.wallet import LocalWallet
    from cosmpy.crypto.keypairs import PrivateKey
    HAS_COSMPY = True
except ImportError:
    HAS_COSMPY = False


class DydxIndexerClient:
    """Client for dYdX v4 Indexer (read-only operations) - 2026 API."""
    
    def __init__(self, indexer_url: str = "https://indexer.dydx.trade"):
        """Initialize dYdX Indexer client."""
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
        """Get all perpetual markets."""
        try:
            # 2026 endpoint: /v4/markets/perpetual
            url = f"{self.indexer_url}/v4/markets/perpetual"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return await response.json()
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
            # 2026 endpoint: /v4/markets/perpetual/{market}/candles
            url = f"{self.indexer_url}/v4/markets/perpetual/{market_id}/candles"
            params = {
                "resolution": resolution,
                "limit": limit
            }
            
            self.logger.info(f"Fetching from: {url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    response_text = await response.text()
                    
                    if response.status != 200:
                        self.logger.error(f"HTTP {response.status}: {response_text[:200]}")
                        return pd.DataFrame()
                    
                    try:
                        data = json.loads(response_text)
                    except json.JSONDecodeError:
                        self.logger.error(f"Invalid JSON: {response_text[:200]}")
                        return pd.DataFrame()
            
            if not data or not isinstance(data, dict):
                self.logger.error(f"Invalid response type: {type(data)}")
                return pd.DataFrame()
            
            # Extract candles from response
            candles = data.get("candles") or data
            
            if not isinstance(candles, list):
                self.logger.error(f"Expected list, got {type(candles)}")
                return pd.DataFrame()
            
            if not candles:
                self.logger.warning(f"No candles for {market_id}")
                return pd.DataFrame()
            
            self.logger.info(f"✅ Got {len(candles)} candles for {market_id}")
            
            df = pd.DataFrame(candles)
            
            # Handle timestamp column
            for col in ["startedAt", "time", "timestamp"]:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col])
                    df.rename(columns={col: "Time"}, inplace=True)
                    df.set_index("Time", inplace=True)
                    break
            
            # Standardize column names
            column_mapping = {
                "open": "Open", "high": "High", "low": "Low", 
                "close": "Close", "baseTokenVolume": "Volume"
            }
            
            for old, new in column_mapping.items():
                if old in df.columns:
                    df[old] = pd.to_numeric(df[old], errors='coerce')
                    df.rename(columns={old: new}, inplace=True)
            
            # Return OHLCV
            cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
            return df[cols] if cols else pd.DataFrame()
        
        except Exception as e:
            self.logger.error(f"Error fetching candles: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    async def get_market_orderbook(self, market_id: str) -> Dict:
        """Get current orderbook for a market."""
        try:
            # 2026 endpoint: /v4/markets/perpetual/{market}/orderbook
            url = f"{self.indexer_url}/v4/markets/perpetual/{market_id}/orderbook"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return await response.json()
            return {}
        except Exception as e:
            self.logger.error(f"Error fetching orderbook: {e}")
            return {}
    
    async def get_market_trades(self, market_id: str, limit: int = 100) -> List[Dict]:
        """Get recent trades for a market."""
        try:
            # 2026 endpoint: /v4/markets/perpetual/{market}/trades
            url = f"{self.indexer_url}/v4/markets/perpetual/{market_id}/trades"
            params = {"limit": limit}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("trades", [])
            return []
        except Exception as e:
            self.logger.error(f"Error fetching trades: {e}")
            return []
    
    async def get_market_funding(self, market_id: str) -> Dict:
        """Get funding rate data for a market."""
        try:
            # 2026 endpoint: /v4/markets/perpetual/{market}/funding-history
            url = f"{self.indexer_url}/v4/markets/perpetual/{market_id}/funding-history"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return await response.json()
            return {}
        except Exception as e:
            self.logger.error(f"Error fetching funding: {e}")
            return {}


class DydxChainClient:
    """Client for dYdX v4 Chain (read/write operations with wallet)."""
    
    def __init__(self, private_key: str, network: str = "mainnet"):
        """Initialize dYdX Chain client."""
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
        """Get account balances."""
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
                amount = float(balance["amount"]) / 1e18
                balances[denom] = amount
            return balances
        except Exception as e:
            self.logger.error(f"Error fetching balances: {e}")
            return {}
    
    async def get_positions(self) -> List[Dict]:
        """Get open perpetual positions."""
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
        """Place an order (placeholder)."""
        self.logger.info(f"Order: {side} {size} {market_id} @ {price} (Leverage: {leverage}x)")
        return None


class DydxExchangeConnector:
    """High-level connector for dYdX v4 - 2026 API."""
    
    def __init__(self, private_key: Optional[str] = None, network: str = "mainnet"):
        """Initialize dYdX exchange connector."""
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
