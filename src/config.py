"""Configuration management for Elliott Wave Bot."""

import os
from pathlib import Path
from typing import Any, Dict
import yaml
from pydantic import BaseSettings


class Settings(BaseSettings):
    """Bot settings loaded from config.yaml and environment variables."""
    
    # Trading
    symbol: str = "BTCUSDT"
    base_symbol: str = "BTC"
    quote_symbol: str = "USDT"
    timeframe: str = "1h"
    update_interval: int = 3600
    
    # Risk Management
    stop_loss_percent: float = 2.0
    take_profit_percent: float = 5.0
    max_position_size: float = 0.05
    max_concurrent_trades: int = 2
    
    # Wave Detection
    min_wave_length: int = 5
    extrema_order: int = 5
    confirmation_threshold: float = 0.75
    use_fibonacci: bool = True
    
    # Indicators
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    
    # Backtesting
    backtest_start_date: str = "2023-01-01"
    backtest_end_date: str = "2024-01-01"
    initial_capital: float = 10000
    commission: float = 0.001
    slippage: float = 0.002
    
    # Exchange
    exchange_name: str = "binance"
    api_key: str = ""
    api_secret: str = ""
    sandbox: bool = True
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/bot.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file."""
    if not Path(config_path).exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


def get_settings() -> Settings:
    """Get settings from environment and config file."""
    config_path = os.getenv("CONFIG_PATH", "config.yaml")
    
    if Path(config_path).exists():
        config_data = load_config(config_path)
        # Flatten nested config for pydantic
        flat_config = _flatten_config(config_data)
        return Settings(**flat_config)
    
    return Settings()


def _flatten_config(config: Dict[str, Any], parent_key: str = "") -> Dict[str, Any]:
    """Flatten nested config dictionary."""
    items = []
    for k, v in config.items():
        new_key = f"{parent_key}_{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_config(v, new_key).items())
        else:
            items.append((new_key, v))
    return dict(items)


# Global settings instance
settings = get_settings()