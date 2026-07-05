"""Elliott Wave pattern detection algorithm."""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from scipy.signal import argrelextrema
from dataclasses import dataclass


@dataclass
class WavePoint:
    """Represents a wave point (peak or trough)."""
    index: int
    price: float
    is_peak: bool
    wave_type: Optional[str] = None
    wave_number: Optional[int] = None


@dataclass
class WavePattern:
    """Represents a complete wave pattern."""
    pattern_type: str  # "impulse" or "corrective"
    waves: List[WavePoint]
    start_index: int
    end_index: int
    start_price: float
    end_price: float
    confidence: float  # 0-1
    is_valid: bool


class WaveDetector:
    """Detects Elliott Wave patterns in price data."""
    
    def __init__(self, min_wave_length: int = 5, extrema_order: int = 5):
        """
        Initialize wave detector.
        
        Args:
            min_wave_length: Minimum number of candles for a wave
            extrema_order: Order parameter for finding peaks/troughs
        """
        self.min_wave_length = min_wave_length
        self.extrema_order = extrema_order
    
    def find_extrema(self, prices: pd.Series) -> Tuple[List[WavePoint], List[WavePoint]]:
        """
        Find local peaks and troughs in price data.
        
        Args:
            prices: Price series (typically close prices)
            
        Returns:
            Tuple of (peaks, troughs)
        """
        prices_array = prices.values
        
        # Find local maxima and minima
        peaks_idx = argrelextrema(prices_array, np.greater, order=self.extrema_order)[0]
        troughs_idx = argrelextrema(prices_array, np.less, order=self.extrema_order)[0]
        
        # Create WavePoint objects
        peaks = [WavePoint(idx, prices_array[idx], is_peak=True) for idx in peaks_idx]
        troughs = [WavePoint(idx, prices_array[idx], is_peak=False) for idx in troughs_idx]
        
        return peaks, troughs
    
    def get_combined_extrema(self, prices: pd.Series) -> List[WavePoint]:
        """Get all extrema (peaks and troughs) in chronological order."""
        peaks, troughs = self.find_extrema(prices)
        combined = sorted(peaks + troughs, key=lambda x: x.index)
        return combined
    
    def detect_impulse_wave(self, prices: pd.Series, 
                           start_idx: int, extrema: List[WavePoint]) -> Optional[WavePattern]:
        """
        Detect a 5-wave impulse pattern starting from a trough.
        
        Impulse wave structure:
        - Wave 1: Up (from trough to peak)
        - Wave 2: Down (retraces Wave 1, but not below start)
        - Wave 3: Up (moves beyond Wave 1 peak) - Usually longest
        - Wave 4: Down (retraces Wave 3, but not below Wave 1 peak)
        - Wave 5: Up (final push upward)
        
        Args:
            prices: Price series
            start_idx: Starting index
            extrema: List of extrema points
            
        Returns:
            WavePattern if valid impulse found, None otherwise
        """
        # Find extrema after start index
        future_extrema = [e for e in extrema if e.index > start_idx]
        
        if len(future_extrema) < 9:  # Need at least 9 points for 5 waves
            return None
        
        # Wave points: trough, peak, trough, peak, trough, peak (6+ points for 5 waves)
        wave_points = []
        start_price = prices.iloc[start_idx]
        
        # Expected pattern: low, high, low, high, low, high
        for i in range(min(9, len(future_extrema))):
            if i % 2 == 0:  # Even indices should be troughs
                if not future_extrema[i].is_peak:
                    wave_points.append(future_extrema[i])
            else:  # Odd indices should be peaks
                if future_extrema[i].is_peak:
                    wave_points.append(future_extrema[i])
        
        if len(wave_points) < 6:
            return None
        
        # Validate wave ratios
        wave_1_size = wave_points[1].price - wave_points[0].price
        wave_2_size = wave_points[1].price - wave_points[2].price
        wave_3_size = wave_points[3].price - wave_points[2].price
        wave_4_size = wave_points[3].price - wave_points[4].price
        wave_5_size = wave_points[5].price - wave_points[4].price
        
        # Validation rules
        validations = [
            wave_3_size > 0,  # Wave 3 should be positive
            wave_1_size > 0,  # Wave 1 should be positive
            wave_5_size > 0,  # Wave 5 should be positive
            wave_3_size > wave_1_size * 0.5,  # Wave 3 should be substantial
            wave_2_size < wave_1_size,  # Wave 2 shouldn't retrace beyond 100%
            wave_4_size < wave_3_size * 0.75,  # Wave 4 is shallow
            wave_points[2].price > wave_points[0].price,  # Wave 2 low above Wave 1 low
            wave_points[4].price > wave_points[2].price,  # Wave 4 low above Wave 2 low
        ]
        
        is_valid = sum(validations) >= 7  # Most rules should pass
        confidence = sum(validations) / len(validations)
        
        if not is_valid:
            return None
        
        pattern = WavePattern(
            pattern_type="impulse",
            waves=wave_points[:6],
            start_index=wave_points[0].index,
            end_index=wave_points[5].index,
            start_price=wave_points[0].price,
            end_price=wave_points[5].price,
            confidence=confidence,
            is_valid=True
        )
        
        # Label the waves
        for i, wave in enumerate(pattern.waves):
            if i % 2 == 0:
                wave.wave_number = i // 2 + 1
                wave.wave_type = "impulsive" if (i + 1) % 2 != 0 else "corrective"
        
        return pattern
    
    def detect_corrective_wave(self, prices: pd.Series,
                              start_idx: int, extrema: List[WavePoint]) -> Optional[WavePattern]:
        """
        Detect a 3-wave corrective pattern (A-B-C).
        
        Corrective wave structure:
        - Wave A: First move against the trend
        - Wave B: Partial retracement of Wave A
        - Wave C: Final move to new low
        
        Args:
            prices: Price series
            start_idx: Starting index (should be a peak for downward correction)
            extrema: List of extrema points
            
        Returns:
            WavePattern if valid correction found, None otherwise
        """
        future_extrema = [e for e in extrema if e.index > start_idx]
        
        if len(future_extrema) < 5:
            return None
        
        wave_points = []
        
        # Pattern: high, low, high, low
        for i in range(min(5, len(future_extrema))):
            if i % 2 == 0:  # Even indices
                if not future_extrema[i].is_peak:
                    wave_points.append(future_extrema[i])
            else:  # Odd indices
                if future_extrema[i].is_peak:
                    wave_points.append(future_extrema[i])
        
        if len(wave_points) < 4:
            return None
        
        # Validate wave sizes
        wave_a_size = wave_points[0].price - wave_points[1].price
        wave_b_size = wave_points[2].price - wave_points[1].price
        wave_c_size = wave_points[2].price - wave_points[3].price
        
        validations = [
            wave_a_size > 0,  # Wave A should move down
            wave_b_size > 0,  # Wave B should move up
            wave_c_size > 0,  # Wave C should move down
            wave_b_size < wave_a_size,  # Wave B retraces less than 100% of A
            wave_c_size >= wave_a_size * 0.5,  # Wave C is substantial
        ]
        
        is_valid = sum(validations) >= 4
        confidence = sum(validations) / len(validations)
        
        if not is_valid:
            return None
        
        pattern = WavePattern(
            pattern_type="corrective",
            waves=wave_points[:4],
            start_index=wave_points[0].index,
            end_index=wave_points[3].index,
            start_price=wave_points[0].price,
            end_price=wave_points[3].price,
            confidence=confidence,
            is_valid=True
        )
        
        return pattern
    
    def detect_all_patterns(self, prices: pd.Series) -> List[WavePattern]:
        """
        Detect all valid wave patterns in the price data.
        
        Args:
            prices: Price series
            
        Returns:
            List of detected patterns
        """
        extrema = self.get_combined_extrema(prices)
        patterns = []
        
        # Look for impulse waves starting from each trough
        for i, point in enumerate(extrema):
            if not point.is_peak:  # Starting from a trough
                impulse = self.detect_impulse_wave(prices, point.index, extrema)
                if impulse and impulse.is_valid:
                    patterns.append(impulse)
            else:  # Starting from a peak
                correction = self.detect_corrective_wave(prices, point.index, extrema)
                if correction and correction.is_valid:
                    patterns.append(correction)
        
        # Sort by confidence
        patterns.sort(key=lambda x: x.confidence, reverse=True)
        
        return patterns
    
    def get_latest_pattern(self, prices: pd.Series) -> Optional[WavePattern]:
        """Get the most recent valid pattern."""
        patterns = self.detect_all_patterns(prices)
        
        if patterns:
            return patterns[0]  # Already sorted by confidence
        
        return None
    
    def predict_next_target(self, pattern: WavePattern, 
                          prices: pd.Series) -> Dict[str, float]:
        """
        Predict price targets based on detected pattern.
        
        Uses Fibonacci extensions and retracements.
        
        Args:
            pattern: Detected wave pattern
            prices: Price series
            
        Returns:
            Dictionary with target prices
        """
        if pattern.pattern_type == "impulse":
            # For impulse, predict Wave 5 target
            if len(pattern.waves) >= 5:
                wave_1_size = pattern.waves[1].price - pattern.waves[0].price
                wave_3_start = pattern.waves[2].price
                
                # Wave 5 typically = Wave 1 or 1.618 * Wave 1
                target_1 = pattern.waves[4].price + wave_1_size
                target_2 = pattern.waves[4].price + (wave_1_size * 1.618)
                target_3 = pattern.waves[4].price + (wave_1_size * 0.618)
                
                return {
                    'conservative': target_3,
                    'likely': target_1,
                    'bullish': target_2
                }
        
        else:  # Corrective
            # For correction, predict start of next impulse
            current_price = prices.iloc[-1]
            wave_move = pattern.start_price - pattern.end_price
            
            return {
                'next_support': pattern.end_price,
                'next_resistance': pattern.start_price,
                'extended_target': pattern.end_price - (wave_move * 0.618)
            }
        
        return {}
    
    def get_support_resistance(self, pattern: WavePattern) -> Dict[str, float]:
        """Extract support and resistance levels from wave pattern."""
        if pattern.pattern_type == "impulse":
            return {
                'strong_support': pattern.waves[4].price if len(pattern.waves) > 4 else pattern.waves[2].price,
                'support': pattern.waves[2].price if len(pattern.waves) > 2 else pattern.waves[0].price,
                'resistance': max(w.price for w in pattern.waves),
                'strong_resistance': pattern.end_price
            }
        else:
            return {
                'support': pattern.end_price,
                'resistance': pattern.start_price,
            }
