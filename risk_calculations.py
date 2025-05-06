import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import adfuller
from typing import Dict, List, Tuple, Optional

class RiskCalculator:
    def __init__(self):
        self.risk_thresholds = {
            'high_volatility': 25,  # VIX threshold
            'low_volatility': 15,
            'steep_curve': 0.5,     # 2s10s spread threshold
            'flat_curve': 0.1,
            'inverted_curve': 0
        }
    
    def calculate_real_rates(self, nominal_rates: pd.Series, inflation_expectations: pd.Series) -> pd.Series:
        """Calculate real rates using Fisher equation."""
        return nominal_rates - inflation_expectations
    
    def calculate_implied_rates(self, fed_funds_futures: pd.Series) -> pd.Series:
        """Calculate implied rates from Fed Funds futures."""
        return (100 - fed_funds_futures) / 100
    
    def analyze_yield_curve(self, yields: pd.DataFrame) -> Dict:
        """Analyze yield curve shape and changes."""
        latest = yields.iloc[-1]
        previous = yields.iloc[-2]
        
        # Calculate spreads
        current_2s10s = latest['10Y'] - latest['2Y']
        previous_2s10s = previous['10Y'] - previous['2Y']
        spread_change = current_2s10s - previous_2s10s
        
        # Determine curve shape
        if current_2s10s < self.risk_thresholds['inverted_curve']:
            shape = "Inverted"
        elif current_2s10s < self.risk_thresholds['flat_curve']:
            shape = "Flat"
        elif current_2s10s > self.risk_thresholds['steep_curve']:
            shape = "Steep"
        else:
            shape = "Normal"
        
        # Determine if steepener or flattener
        if spread_change > 0.05:
            movement = "Steepener"
        elif spread_change < -0.05:
            movement = "Flattener"
        else:
            movement = "Unchanged"
        
        return {
            'shape': shape,
            'movement': movement,
            'current_spread': current_2s10s,
            'spread_change': spread_change,
            'latest_yields': latest,
            'previous_yields': previous
        }
    
    def calculate_risk_score(self, 
                           yield_curve: pd.DataFrame,
                           vix: Optional[float] = None,
                           real_rates: Optional[pd.Series] = None,
                           implied_rates: Optional[pd.Series] = None) -> float:
        """Calculate comprehensive risk score (0-100)."""
        score = 50  # Base score
        
        # Yield curve component (40% weight)
        curve_analysis = self.analyze_yield_curve(yield_curve)
        if curve_analysis['shape'] == "Inverted":
            score += 20
        elif curve_analysis['shape'] == "Flat":
            score += 10
        
        # Volatility component (20% weight)
        if vix is not None:
            if vix > self.risk_thresholds['high_volatility']:
                score += 15
            elif vix < self.risk_thresholds['low_volatility']:
                score -= 10
        
        # Real rates component (20% weight)
        if real_rates is not None:
            real_rates_avg = real_rates.mean()
            if real_rates_avg < 0:
                score += 15
            elif real_rates_avg > 1:
                score -= 10
        
        # Implied rates component (20% weight)
        if implied_rates is not None:
            implied_rates_avg = implied_rates.mean()
            if implied_rates_avg > 5:
                score += 15
            elif implied_rates_avg < 2:
                score -= 10
        
        # Cap score between 0 and 100
        return max(0, min(100, score))
    
    def determine_risk_status(self, risk_score: float, curve_analysis: Dict) -> str:
        """Determine overall risk status based on multiple factors."""
        if risk_score > 70:
            return "Risk Off"
        elif risk_score < 30:
            return "Risk On"
        else:
            return "Neutral"
    
    def calculate_market_trend(self, prices: pd.Series, window: int = 20) -> Dict:
        """Calculate market trend using technical indicators."""
        # Calculate moving averages
        sma = prices.rolling(window=window).mean()
        ema = prices.ewm(span=window).mean()
        
        # Calculate momentum
        momentum = prices.pct_change(periods=window)
        
        # Determine trend
        if prices.iloc[-1] > sma.iloc[-1] and prices.iloc[-1] > ema.iloc[-1]:
            trend = "Up"
        elif prices.iloc[-1] < sma.iloc[-1] and prices.iloc[-1] < ema.iloc[-1]:
            trend = "Down"
        else:
            trend = "Sideways"
        
        return {
            'trend': trend,
            'momentum': momentum.iloc[-1],
            'sma': sma.iloc[-1],
            'ema': ema.iloc[-1]
        }
    
    def calculate_volatility(self, prices: pd.Series, window: int = 20) -> float:
        """Calculate historical volatility."""
        returns = prices.pct_change()
        return returns.rolling(window=window).std() * np.sqrt(252)  # Annualized 