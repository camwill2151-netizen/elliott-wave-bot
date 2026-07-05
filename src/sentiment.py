"""Sentiment analysis module for trading signals."""

import logging
from typing import Dict, List
import re

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Analyzes sentiment from market data and social signals."""
    
    def __init__(self):
        """Initialize sentiment analyzer with keyword dictionaries."""
        # Bullish keywords
        self.bullish_keywords = {
            'bull', 'bullish', 'up', 'surge', 'rally', 'moon', 'rocket',
            'pump', 'gain', 'profit', 'buy', 'long', 'breakout', 'strong',
            'surge', 'jump', 'soar', 'rise', 'bull run', 'explosive',
            'institutional', 'adoption', 'partnership', 'upgrade', 'success'
        }
        
        # Bearish keywords
        self.bearish_keywords = {
            'bear', 'bearish', 'down', 'crash', 'dump', 'drop', 'sell',
            'short', 'loss', 'decline', 'fall', 'weakness', 'fear',
            'panic', 'collapse', 'plunge', 'tumble', 'bear trap',
            'regulation', 'ban', 'investigation', 'hack', 'exploit',
            'vulnerability', 'negative', 'problem', 'issue'
        }
        
        # Neutral/Uncertain keywords
        self.neutral_keywords = {
            'sideways', 'consolidation', 'ranging', 'uncertain', 'mixed',
            'possibly', 'maybe', 'unclear', 'wait', 'hold', 'stable',
            'neutral', 'flat', 'pending', 'watch'
        }
    
    def analyze_text_sentiment(self, text: str) -> Dict[str, float]:
        """
        Analyze sentiment from text input.
        
        Args:
            text: Text to analyze (news, tweets, etc.)
            
        Returns:
            Dictionary with sentiment scores
        """
        if not text:
            return {'bullish': 0.0, 'bearish': 0.0, 'neutral': 1.0}
        
        text_lower = text.lower()
        
        # Count keyword matches
        bullish_count = sum(1 for keyword in self.bullish_keywords 
                           if keyword in text_lower)
        bearish_count = sum(1 for keyword in self.bearish_keywords 
                           if keyword in text_lower)
        neutral_count = sum(1 for keyword in self.neutral_keywords 
                           if keyword in text_lower)
        
        total = bullish_count + bearish_count + neutral_count
        
        if total == 0:
            return {'bullish': 0.0, 'bearish': 0.0, 'neutral': 1.0}
        
        return {
            'bullish': bullish_count / total,
            'bearish': bearish_count / total,
            'neutral': neutral_count / total
        }
    
    def analyze_price_action_sentiment(self, price_data: dict) -> Dict[str, float]:
        """
        Analyze sentiment from price action metrics.
        
        Args:
            price_data: Dictionary with price metrics
                - price_change_24h: 24-hour price change percentage
                - volume_change: Volume change percentage
                - momentum: Price momentum indicator
                
        Returns:
            Dictionary with sentiment scores
        """
        bullish_score = 0.0
        bearish_score = 0.0
        
        # Price change analysis
        price_change = price_data.get('price_change_24h', 0)
        if price_change > 5:
            bullish_score += 0.3
        elif price_change > 2:
            bullish_score += 0.15
        elif price_change < -5:
            bearish_score += 0.3
        elif price_change < -2:
            bearish_score += 0.15
        
        # Volume analysis
        volume_change = price_data.get('volume_change', 0)
        if volume_change > 20:
            bullish_score += 0.2
        elif volume_change < -20:
            bearish_score += 0.2
        
        # Momentum analysis
        momentum = price_data.get('momentum', 0)
        if momentum > 0.6:
            bullish_score += 0.2
        elif momentum < 0.4:
            bearish_score += 0.2
        
        # Fear and Greed Index simulation (0-100, 50 is neutral)
        fgi = price_data.get('fear_greed_index', 50)
        if fgi > 70:  # Greed
            bullish_score += 0.1
        elif fgi < 30:  # Fear
            bearish_score += 0.1
        
        # Normalize scores
        total = max(bullish_score + bearish_score, 1.0)
        neutral_score = 1.0 - (bullish_score + bearish_score) / total if total > 0 else 1.0
        
        return {
            'bullish': min(bullish_score, 1.0),
            'bearish': min(bearish_score, 1.0),
            'neutral': max(neutral_score, 0.0)
        }
    
    def analyze_volume_sentiment(self, df) -> Dict[str, float]:
        """
        Analyze sentiment based on volume patterns.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Dictionary with sentiment scores
        """
        if df.empty or 'Volume' not in df.columns:
            return {'bullish': 0.0, 'bearish': 0.0, 'neutral': 1.0}
        
        recent_volume = df['Volume'].tail(5).mean()
        historical_volume = df['Volume'].tail(20).mean()
        
        volume_ratio = recent_volume / historical_volume if historical_volume > 0 else 1.0
        
        # Price direction with volume
        recent_close = df['Close'].tail(5).mean()
        historical_close = df['Close'].tail(20).mean()
        
        bullish_score = 0.0
        bearish_score = 0.0
        
        if recent_close > historical_close and volume_ratio > 1.2:
            bullish_score = 0.6  # Bullish with volume
        elif recent_close > historical_close and volume_ratio > 1.0:
            bullish_score = 0.4  # Weak bullish
        elif recent_close < historical_close and volume_ratio > 1.2:
            bearish_score = 0.6  # Bearish with volume
        elif recent_close < historical_close and volume_ratio > 1.0:
            bearish_score = 0.4  # Weak bearish
        
        neutral_score = 1.0 - (bullish_score + bearish_score)
        
        return {
            'bullish': bullish_score,
            'bearish': bearish_score,
            'neutral': max(neutral_score, 0.0)
        }
    
    def combine_sentiments(self, sentiments: List[Dict[str, float]]) -> Dict[str, float]:
        """
        Combine multiple sentiment analyses.
        
        Args:
            sentiments: List of sentiment dictionaries
            
        Returns:
            Combined sentiment scores
        """
        if not sentiments:
            return {'bullish': 0.0, 'bearish': 0.0, 'neutral': 1.0}
        
        avg_bullish = sum(s.get('bullish', 0) for s in sentiments) / len(sentiments)
        avg_bearish = sum(s.get('bearish', 0) for s in sentiments) / len(sentiments)
        avg_neutral = sum(s.get('neutral', 0) for s in sentiments) / len(sentiments)
        
        # Normalize to sum to 1.0
        total = avg_bullish + avg_bearish + avg_neutral
        if total > 0:
            return {
                'bullish': avg_bullish / total,
                'bearish': avg_bearish / total,
                'neutral': avg_neutral / total
            }
        
        return {'bullish': 0.0, 'bearish': 0.0, 'neutral': 1.0}
    
    def generate_sentiment_signal(self, sentiment: Dict[str, float]) -> Dict[str, any]:
        """
        Generate trading signal from sentiment analysis.
        
        Args:
            sentiment: Sentiment scores dictionary
            
        Returns:
            Trading signal with confidence
        """
        bullish = sentiment.get('bullish', 0)
        bearish = sentiment.get('bearish', 0)
        
        signal_type = "HOLD"
        confidence = sentiment.get('neutral', 1.0)
        
        if bullish > bearish + 0.2:
            signal_type = "STRONG BUY" if bullish > 0.6 else "BUY"
            confidence = bullish
        elif bearish > bullish + 0.2:
            signal_type = "STRONG SELL" if bearish > 0.6 else "SELL"
            confidence = bearish
        else:
            signal_type = "HOLD"
            confidence = max(bullish, bearish, sentiment.get('neutral', 0))
        
        return {
            'signal_type': signal_type,
            'confidence': confidence,
            'bullish_score': bullish,
            'bearish_score': bearish,
            'neutral_score': sentiment.get('neutral', 0)
        }
    
    def get_sentiment_report(self, price_data: dict = None, text_input: str = None, 
                            df = None) -> Dict[str, any]:
        """
        Generate comprehensive sentiment report.
        
        Args:
            price_data: Price action data
            text_input: Text to analyze
            df: OHLCV dataframe
            
        Returns:
            Complete sentiment analysis report
        """
        sentiments = []
        
        # Text sentiment
        if text_input:
            text_sentiment = self.analyze_text_sentiment(text_input)
            sentiments.append(text_sentiment)
        
        # Price action sentiment
        if price_data:
            price_sentiment = self.analyze_price_action_sentiment(price_data)
            sentiments.append(price_sentiment)
        
        # Volume sentiment
        if df is not None:
            volume_sentiment = self.analyze_volume_sentiment(df)
            sentiments.append(volume_sentiment)
        
        # Combine all sentiments
        combined = self.combine_sentiments(sentiments)
        signal = self.generate_sentiment_signal(combined)
        
        return {
            'text_sentiment': self.analyze_text_sentiment(text_input) if text_input else None,
            'price_sentiment': self.analyze_price_action_sentiment(price_data) if price_data else None,
            'volume_sentiment': self.analyze_volume_sentiment(df) if df is not None else None,
            'combined_sentiment': combined,
            'signal': signal,
            'components_used': len(sentiments)
        }
