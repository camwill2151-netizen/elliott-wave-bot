"""Technical indicators for wave confirmation and signal generation."""

import numpy as np
import pandas as pd
from typing import Tuple, Dict, List


class Indicators:
    """Technical indicators calculation."""
    
    @staticmethod
    def rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index (RSI).
        
        Args:
            prices: Price series
            period: RSI period (default: 14)
            
        Returns:
            RSI series (0-100)
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def macd(prices: pd.Series, fast: int = 12, slow: int = 26, 
             signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate MACD (Moving Average Convergence Divergence).
        
        Args:
            prices: Price series
            fast: Fast EMA period (default: 12)
            slow: Slow EMA period (default: 26)
            signal: Signal line period (default: 9)
            
        Returns:
            MACD line, Signal line, Histogram
        """
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def bollinger_bands(prices: pd.Series, period: int = 20, 
                       std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands.
        
        Args:
            prices: Price series
            period: SMA period (default: 20)
            std_dev: Standard deviation multiplier (default: 2.0)
            
        Returns:
            Upper band, Middle band (SMA), Lower band
        """
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        
        return upper, sma, lower
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, 
            period: int = 14) -> pd.Series:
        """
        Calculate Average True Range (ATR).
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ATR period (default: 14)
            
        Returns:
            ATR series
        """
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    @staticmethod
    def fibonacci_levels(high: float, low: float) -> Dict[str, float]:
        """
        Calculate Fibonacci retracement and extension levels.
        
        Args:
            high: High price
            low: Low price
            
        Returns:
            Dictionary of Fibonacci levels
        """
        diff = high - low
        
        levels = {
            '0.0%': low,
            '23.6%': high - (diff * 0.236),
            '38.2%': high - (diff * 0.382),
            '50.0%': high - (diff * 0.5),
            '61.8%': high - (diff * 0.618),
            '78.6%': high - (diff * 0.786),
            '100.0%': high,
            '127.2%': low + (diff * 1.272),
            '161.8%': low + (diff * 1.618),
            '200.0%': low + (diff * 2.0),
        }
        
        return levels
    
    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
                   period: int = 14) -> Tuple[pd.Series, pd.Series]:
        """
        Calculate Stochastic Oscillator.
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: Stochastic period (default: 14)
            
        Returns:
            %K line, %D line
        """
        lowest_low = low.rolling(window=period).min()
        highest_high = high.rolling(window=period).max()
        
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=3).mean()
        
        return k_percent, d_percent
    
    @staticmethod
    def ema(prices: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return prices.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def sma(prices: pd.Series, period: int) -> pd.Series:
        """Calculate Simple Moving Average."""
        return prices.rolling(window=period).mean()
    
    @staticmethod
    def volume_profile(volumes: pd.Series, prices: pd.Series, 
                      bins: int = 20) -> Dict[float, float]:
        """
        Calculate volume profile.
        
        Args:
            volumes: Volume series
            prices: Price series
            bins: Number of price bins
            
        Returns:
            Dictionary mapping price levels to volume
        """
        price_bins = pd.cut(prices, bins=bins)
        profile = volumes.groupby(price_bins).sum()
        
        return profile.to_dict()


class SignalGenerator:
    """Generate trading signals based on indicators."""
    
    def __init__(self, indicators: Indicators = None):
        self.indicators = indicators or Indicators()
    
    def generate_rsi_signal(self, prices: pd.Series, period: int = 14) -> Dict[str, any]:
        """Generate RSI-based signals."""
        rsi = self.indicators.rsi(prices, period)
        
        latest_rsi = rsi.iloc[-1]
        
        return {
            'rsi_value': latest_rsi,
            'overbought': latest_rsi > 70,
            'oversold': latest_rsi < 30,
            'neutral': 30 <= latest_rsi <= 70
        }
    
    def generate_macd_signal(self, prices: pd.Series) -> Dict[str, any]:
        """Generate MACD-based signals."""
        macd_line, signal_line, histogram = self.indicators.macd(prices)
        
        latest_macd = macd_line.iloc[-1]
        latest_signal = signal_line.iloc[-1]
        latest_histogram = histogram.iloc[-1]
        
        bullish = latest_macd > latest_signal and latest_histogram > 0
        bearish = latest_macd < latest_signal and latest_histogram < 0
        
        return {
            'macd': latest_macd,
            'signal': latest_signal,
            'histogram': latest_histogram,
            'bullish_crossover': bullish,
            'bearish_crossover': bearish
        }
    
    def generate_combined_signal(self, prices: pd.Series, 
                                high: pd.Series, low: pd.Series) -> Dict[str, any]:
        """Generate combined signal from multiple indicators."""
        rsi_signal = self.generate_rsi_signal(prices)
        macd_signal = self.generate_macd_signal(prices)
        
        # Count bullish signals
        bullish_count = 0
        if not rsi_signal['overbought']:
            bullish_count += 1
        if macd_signal['bullish_crossover']:
            bullish_count += 1
        
        confidence = bullish_count / 2.0  # 0-1 scale
        
        return {
            'rsi': rsi_signal,
            'macd': macd_signal,
            'confidence': confidence,
            'strong_buy': confidence > 0.7,
            'buy': confidence > 0.5,
            'hold': 0.3 < confidence <= 0.5,
            'sell': confidence <= 0.3
        }