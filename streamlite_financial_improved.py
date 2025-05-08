import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import threading
import queue
import time
import json
import logging
from dataclasses import dataclass
import requests
from concurrent.futures import ThreadPoolExecutor
import backoff
from functools import lru_cache
import random  # Added for random jitter in retry logic
import warnings
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set page config - MUST be the first Streamlit command
st.set_page_config(
    page_title="Enhanced Market Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state variables if they don't exist
if 'market_data' not in st.session_state:
    st.session_state['market_data'] = None
if 'market_analysis' not in st.session_state:
    st.session_state['market_analysis'] = None
if 'yield_curve_plot' not in st.session_state:
    st.session_state['yield_curve_plot'] = None
if 'vix_premium_plot' not in st.session_state:
    st.session_state['vix_premium_plot'] = None
if 'expected_range_plot' not in st.session_state:
    st.session_state['expected_range_plot'] = None
if 'gold_term_plot' not in st.session_state:
    st.session_state['gold_term_plot'] = None
if 'skew_plot' not in st.session_state:
    st.session_state['skew_plot'] = None

# Define date variables
TODAY = datetime.now()
YESTERDAY = TODAY - timedelta(days=1)

# Global variables for data fetching
FETCH_TIMEOUT = 45  # seconds
INITIAL_RETRY_DELAY = 2  # seconds
MAX_RETRIES = 5
MAX_WORKERS = 3  # Reduced to avoid rate limits
RATE_LIMIT_DELAY = 1  # seconds between requests
MAX_DATA_AGE = 300  # 5 minutes in seconds

class MarketAnalyzer:
    def __init__(self):
        self.risk_thresholds = {
            'vix': {'low': 15, 'medium': 20, 'high': 30},
            'yield_spread': {'low': 0.1, 'medium': 0.2, 'high': 0.3},
            'gold_change': {'low': 0.5, 'medium': 1.0, 'high': 2.0}
        }
        
    def analyze_market_conditions(self, current_data: Dict[str, Any], historical_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze current market conditions"""
        if not isinstance(current_data, dict):
            return {
                'risk_on_off': 'Unknown',
                'yield_curve': {'curve_type': 'Unknown', 'change': 0, 'implications': []},
                'market_direction': {'trend': 'Unknown', 'strength': 'Unknown', 'key_levels': []},
                'correlations': {}
            }
        
        analysis = {
            'risk_on_off': self._determine_risk_on_off(current_data),
            'yield_curve': self._analyze_yield_curve(current_data),
            'market_direction': self._determine_market_direction(current_data),
            'correlations': self._analyze_correlations(current_data)
        }
        
        if historical_data and isinstance(historical_data, dict):
            analysis['trends'] = self._analyze_trends(current_data, historical_data)
            
        return analysis
        
    def _determine_risk_on_off(self, data: Dict[str, Any]) -> str:
        """Determine if market is in risk-on or risk-off mode"""
        signals = []
        
        # VIX analysis
        if 'VIX' in data:
            vix = data['VIX'].get('current', 0)
            if vix > self.risk_thresholds['vix']['high']:
                signals.append("Risk-Off (High VIX)")
            elif vix < self.risk_thresholds['vix']['low']:
                signals.append("Risk-On (Low VIX)")
        
        # Treasury spread analysis
        if 'Treasury' in data:
            treasury = data['Treasury']
            if '2Y' in treasury and '10Y' in treasury:
                spread = treasury['10Y']['current'] - treasury['2Y']['current']
                if spread < -self.risk_thresholds['yield_spread']['high']:
                    signals.append("Risk-Off (Inverted Curve)")
                elif spread > self.risk_thresholds['yield_spread']['high']:
                    signals.append("Risk-On (Steep Curve)")
        
        # Gold analysis
        if 'Commodities' in data and 'Gold' in data['Commodities']:
            gold_change = data['Commodities']['Gold']['current'] - data['Commodities']['Gold']['previous']
            if abs(gold_change) > self.risk_thresholds['gold_change']['high']:
                signals.append("Risk-Off (Gold Volatility)")
        
        return " | ".join(signals) if signals else "Neutral"
        
    def _analyze_yield_curve(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze yield curve shape and changes"""
        if 'Treasury' not in data:
            return {'curve_type': None, 'change': 0, 'implications': []}
            
        treasury = data['Treasury']
        if not all(k in treasury for k in ['2Y', '5Y', '10Y', '30Y']):
            return {'curve_type': None, 'change': 0, 'implications': []}
            
        # Calculate spreads
        spreads = {
            '2s10s': treasury['10Y']['current'] - treasury['2Y']['current'],
            '5s10s': treasury['10Y']['current'] - treasury['5Y']['current'],
            '10s30s': treasury['30Y']['current'] - treasury['10Y']['current']
        }
        
        # Determine curve type
        curve_type = "Normal"
        if spreads['2s10s'] < 0:
            curve_type = "Inverted"
        elif spreads['2s10s'] > 0.5:
            curve_type = "Steep"
            
        # Calculate changes
        changes = {
            '2s10s': (treasury['10Y']['current'] - treasury['2Y']['current']) - 
                     (treasury['10Y']['previous'] - treasury['2Y']['previous'])
        }
        
        # Determine implications
        implications = []
        if curve_type == "Inverted":
            implications.append("Potential recession risk")
        elif curve_type == "Steep":
            implications.append("Economic expansion expected")
            
        if changes['2s10s'] > 0.1:
            implications.append("Curve steepening (risk-on)")
        elif changes['2s10s'] < -0.1:
            implications.append("Curve flattening (risk-off)")
            
        return {
            'curve_type': curve_type,
            'change': changes['2s10s'],
            'implications': implications
        }
        
    def _determine_market_direction(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Determine market direction and strength"""
        if 'SPY' not in data:
            return {'trend': None, 'strength': 0, 'key_levels': []}
            
        spy = data['SPY']
        change = spy['current'] - spy['previous']
        percent_change = (change / spy['previous']) * 100
        
        # Determine trend
        trend = "Neutral"
        if percent_change > 1:
            trend = "Up"
        elif percent_change < -1:
            trend = "Down"
            
        # Determine strength
        strength = "Weak"
        if abs(percent_change) > 2:
            strength = "Strong"
            
        # Calculate key levels
        key_levels = []
        if 'high' in spy and 'low' in spy:
            key_levels.append(f"Resistance: {spy['high']:.2f}")
            key_levels.append(f"Support: {spy['low']:.2f}")
            
        return {
            'trend': trend,
            'strength': strength,
            'key_levels': key_levels
        }
        
    def _analyze_correlations(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Analyze correlations between key assets"""
        correlations = {}
        
        # Gold vs USD
        if 'Commodities' in data and 'Gold' in data['Commodities'] and \
           'Currencies' in data and 'DXY' in data['Currencies']:
            gold_change = data['Commodities']['Gold']['current'] - data['Commodities']['Gold']['previous']
            dxy_change = data['Currencies']['DXY']['current'] - data['Currencies']['DXY']['previous']
            if gold_change * dxy_change < 0:
                correlations['gold_usd'] = "Negative"
            else:
                correlations['gold_usd'] = "Positive"
                
        # SPY vs VIX
        if 'SPY' in data and 'VIX' in data:
            spy_change = data['SPY']['current'] - data['SPY']['previous']
            vix_change = data['VIX']['current'] - data['VIX']['previous']
            if spy_change * vix_change < 0:
                correlations['spy_vix'] = "Negative"
            else:
                correlations['spy_vix'] = "Positive"
                
        # Treasury vs Gold
        if 'Treasury' in data and '10Y' in data['Treasury'] and \
           'Commodities' in data and 'Gold' in data['Commodities']:
            treasury_change = data['Treasury']['10Y']['current'] - data['Treasury']['10Y']['previous']
            gold_change = data['Commodities']['Gold']['current'] - data['Commodities']['Gold']['previous']
            if treasury_change * gold_change < 0:
                correlations['treasury_gold'] = "Negative"
            else:
                correlations['treasury_gold'] = "Positive"
                
        return correlations
        
    def _analyze_trends(self, current_data: Dict[str, Any], historical_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze trends by comparing current and historical data"""
        trends = {}
        
        # VIX trend
        if 'VIX' in current_data and 'VIX' in historical_data:
            vix_trend = current_data['VIX']['current'] - historical_data['VIX']['current']
            trends['vix'] = "Rising" if vix_trend > 0 else "Falling"
            
        # Yield trend
        if 'Treasury' in current_data and 'Treasury' in historical_data:
            if '10Y' in current_data['Treasury'] and '10Y' in historical_data['Treasury']:
                yield_trend = current_data['Treasury']['10Y']['current'] - historical_data['Treasury']['10Y']['current']
                trends['yield'] = "Rising" if yield_trend > 0 else "Falling"
                
        # Gold trend
        if 'Commodities' in current_data and 'Commodities' in historical_data:
            if 'Gold' in current_data['Commodities'] and 'Gold' in historical_data['Commodities']:
                gold_trend = current_data['Commodities']['Gold']['current'] - historical_data['Commodities']['Gold']['current']
                trends['gold'] = "Rising" if gold_trend > 0 else "Falling"
                
        return trends

class VIXAnalyzer:
    def __init__(self):
        self.vix_thresholds = {
            'low': 15,
            'medium': 20,
            'high': 30
        }
    
    def analyze_vix(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze VIX data"""
        if 'VIX' not in data:
            return {'status': 'No VIX data available'}
        
        vix = data['VIX'].get('current', 0)
        prev_vix = data['VIX'].get('previous', 0)
        change = vix - prev_vix
        
        status = "Neutral"
        if vix > self.vix_thresholds['high']:
            status = "High (Risk-Off)"
        elif vix < self.vix_thresholds['low']:
            status = "Low (Risk-On)"
        
        return {
            'status': status,
            'current': vix,
            'change': change
        }
    
    def create_vix_premium_plot(self, vix_data: Dict[str, Any], spy_data: Dict[str, Any]) -> go.Figure:
        """Create VIX premium plot"""
        fig = go.Figure()
        
        if vix_data and spy_data:
            vix = vix_data.get('current', 0)
            spy = spy_data.get('current', 0)
            
            fig.add_trace(go.Scatter(
                x=['VIX', 'SPY'],
                y=[vix, spy],
                mode='lines+markers',
                name='Market Indicators'
            ))
        
        fig.update_layout(
            title='VIX vs SPY',
            xaxis_title='Indicator',
            yaxis_title='Value',
            showlegend=True
        )
        
        return fig

class VolatilityAnalyzer:
    def __init__(self):
        self.vol_thresholds = {
            'low': 0.1,
            'medium': 0.2,
            'high': 0.3
        }
    
    def analyze_volatility(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze market volatility"""
        if 'VIX' not in data:
            return {'status': 'No volatility data available'}
        
        vix = data['VIX'].get('current', 0)
        status = "Normal"
        if vix > self.vol_thresholds['high']:
            status = "High Volatility"
        elif vix < self.vol_thresholds['low']:
            status = "Low Volatility"
        
        return {
            'status': status,
            'current_vix': vix
        }
    
    def calculate_expected_range(self, vix: float, current_price: float) -> Dict[str, Any]:
        """Calculate expected price range based on VIX"""
        daily_vol = vix / 100 / np.sqrt(252)  # Convert VIX to daily volatility
        
        return {
            'daily': {
                '1sigma': {
                    'lower': current_price * (1 - daily_vol),
                    'upper': current_price * (1 + daily_vol)
                },
                '2sigma': {
                    'lower': current_price * (1 - 2 * daily_vol),
                    'upper': current_price * (1 + 2 * daily_vol)
                },
                '3sigma': {
                    'lower': current_price * (1 - 3 * daily_vol),
                    'upper': current_price * (1 + 3 * daily_vol)
                }
            }
        }

class GoldAnalyzer:
    def __init__(self):
        self.term_structure_thresholds = {
            'contango': 0.02,
            'backwardation': -0.02
        }
    
    def analyze_gold_term_structure(self, gold_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze gold term structure"""
        if not gold_data:
            return None
        
        current_price = gold_data.get('current', 0)
        term_prices = {
            '1M': {'price': current_price * 1.001, 'contango': 0.001},
            '3M': {'price': current_price * 1.003, 'contango': 0.003},
            '6M': {'price': current_price * 1.006, 'contango': 0.006},
            '1Y': {'price': current_price * 1.012, 'contango': 0.012}
        }
        
        structure = "Normal"
        if term_prices['1Y']['contango'] > self.term_structure_thresholds['contango']:
            structure = "Strong Contango"
        elif term_prices['1Y']['contango'] < self.term_structure_thresholds['backwardation']:
            structure = "Backwardation"
        
        return {
            'term_structure': structure,
            'term_prices': term_prices
        }

class VolatilitySkewAnalyzer:
    def __init__(self):
        self.skew_thresholds = {
            'high': 0.1,
            'low': 0.05
        }
    
    def analyze_volatility_skew(self, options_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze volatility skew"""
        if not options_data:
            return None
        
        # Simulate some option data
        strikes = np.linspace(0.8, 1.2, 9)
        put_vols = [0.3, 0.28, 0.26, 0.24, 0.22, 0.24, 0.26, 0.28, 0.3]
        call_vols = [0.3, 0.28, 0.26, 0.24, 0.22, 0.24, 0.26, 0.28, 0.3]
        
        skew_status = "Normal"
        if max(put_vols) - min(put_vols) > self.skew_thresholds['high']:
            skew_status = "High Skew"
        elif max(put_vols) - min(put_vols) < self.skew_thresholds['low']:
            skew_status = "Low Skew"
        
        return {
            'skew_status': skew_status,
            'put_skew': {
                'strikes': strikes,
                'vols': put_vols
            },
            'call_skew': {
                'strikes': strikes,
                'vols': call_vols
            }
        }

# API Configuration
class APIConfig:
    def __init__(self):
        try:
            self.alpha_vantage_key = st.secrets.get("ALPHA_VANTAGE_KEY", "")
            self.fred_api_key = st.secrets.get("FRED_API_KEY", "")
            self.tradier_api_key = st.secrets.get("TRADIER_API_KEY", "")
            self.iex_api_key = st.secrets.get("IEX_API_KEY", "")
            self.finnhub_key = st.secrets.get("FINNHUB_KEY", "")
            self.newsapi_key = st.secrets.get("NEWSAPI_KEY", "")
            self.marketaux_key = st.secrets.get("MARKETAUX_KEY", "")
            
            # Validate API keys
            self._validate_api_keys()
            
            # API endpoints
            self.alpha_vantage_base = "https://www.alphavantage.co/query"
            self.fred_base = "https://api.stlouisfed.org/fred/series"
            self.tradier_base = "https://api.tradier.com/v1/markets"
            self.iex_base = "https://cloud.iexapis.com/v1"
            self.finnhub_base = "https://finnhub.io/api/v1"
            self.newsapi_base = "https://newsapi.org/v2"
            self.marketaux_base = "https://api.marketaux.com/v1"
            
        except Exception as e:
            logger.error(f"Error initializing API configuration: {str(e)}")
            st.error("Failed to initialize API configuration. Please check your secrets configuration.")
            raise
    
    def _validate_api_keys(self):
        """Validate that required API keys are present"""
        required_keys = {
            'ALPHA_VANTAGE_KEY': self.alpha_vantage_key,
            'FRED_API_KEY': self.fred_api_key,
            'FINNHUB_KEY': self.finnhub_key,
            'NEWSAPI_KEY': self.newsapi_key
        }
        
        missing_keys = [key for key, value in required_keys.items() if not value]
        
        if missing_keys:
            error_msg = f"Missing required API keys: {', '.join(missing_keys)}"
            logger.error(error_msg)
            st.error(error_msg)
            raise ValueError(error_msg)
    
    def get_api_key(self, service: str) -> str:
        """Safely get API key for a service"""
        key_map = {
            'alpha_vantage': self.alpha_vantage_key,
            'fred': self.fred_api_key,
            'tradier': self.tradier_api_key,
            'iex': self.iex_api_key,
            'finnhub': self.finnhub_key,
            'newsapi': self.newsapi_key,
            'marketaux': self.marketaux_key
        }
        
        if service not in key_map:
            raise ValueError(f"Unknown service: {service}")
            
        key = key_map[service]
        if not key:
            raise ValueError(f"API key not configured for service: {service}")
            
        return key
    
    def get_base_url(self, service: str) -> str:
        """Safely get base URL for a service"""
        url_map = {
            'alpha_vantage': self.alpha_vantage_base,
            'fred': self.fred_base,
            'tradier': self.tradier_base,
            'iex': self.iex_base,
            'finnhub': self.finnhub_base,
            'newsapi': self.newsapi_base,
            'marketaux': self.marketaux_base
        }
        
        if service not in url_map:
            raise ValueError(f"Unknown service: {service}")
            
        return url_map[service]

class DataSource:
    def __init__(self, name: str, priority: int):
        self.name = name
        self.priority = priority
        self.last_success = None
        self.failure_count = 0

class DataFetchError(Exception):
    """Custom exception for data fetching errors"""
    pass

class RateLimiter:
    def __init__(self, calls_per_minute):
        self.calls_per_minute = calls_per_minute
        self.calls = []
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.time()
            # Remove calls older than 1 minute
            self.calls = [call for call in self.calls if now - call < 60]
            
            if len(self.calls) >= self.calls_per_minute:
                sleep_time = 60 - (now - self.calls[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            self.calls.append(now)

class EnhancedRateLimiter:
    def __init__(self, calls_per_minute: int, burst_limit: int = 5):
        self.calls_per_minute = calls_per_minute
        self.burst_limit = burst_limit
        self.calls = []
        self.lock = threading.Lock()
        self.last_burst_time = time.time()
        self.burst_count = 0
        
    def wait(self):
        """Enhanced rate limiting with burst protection"""
        with self.lock:
            now = time.time()
            
            # Reset burst count if more than 1 minute has passed
            if now - self.last_burst_time > 60:
                self.burst_count = 0
                self.last_burst_time = now
            
            # Check burst limit
            if self.burst_count >= self.burst_limit:
                sleep_time = 60 - (now - self.last_burst_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                self.burst_count = 0
                self.last_burst_time = time.time()
            
            # Remove calls older than 1 minute
            self.calls = [call for call in self.calls if now - call < 60]
            
            # Check rate limit
            if len(self.calls) >= self.calls_per_minute:
                sleep_time = 60 - (now - self.calls[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            self.calls.append(now)
            self.burst_count += 1

class DataFetcher:
    def __init__(self):
        self.api_config = APIConfig()
        # Reduced rate limits to prevent API overload
        self.rate_limiters = {
            'alpha_vantage': EnhancedRateLimiter(st.secrets.get('ALPHA_VANTAGE_RATE_LIMIT', 3)),  # Reduced from 5
            'fred': EnhancedRateLimiter(st.secrets.get('FRED_RATE_LIMIT', 60)),  # Reduced from 120
            'finnhub': EnhancedRateLimiter(st.secrets.get('FINNHUB_RATE_LIMIT', 30)),  # Reduced from 60
            'newsapi': EnhancedRateLimiter(st.secrets.get('NEWSAPI_RATE_LIMIT', 50)),  # Reduced from 100
            'marketaux': EnhancedRateLimiter(st.secrets.get('MARKETAUX_RATE_LIMIT', 25))  # Reduced from 50
        }
        
    def fetch_with_retry(self, fetch_func, *args, **kwargs):
        """Enhanced retry mechanism with exponential backoff"""
        max_retries = st.secrets.get('MAX_RETRIES', 3)
        initial_retry_delay = st.secrets.get('RETRY_DELAY', 2)
        timeout = st.secrets.get('TIMEOUT', 10)
        
        for attempt in range(max_retries):
            try:
                return fetch_func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise DataFetchError(f"Failed after {max_retries} attempts: {str(e)}")
                # Exponential backoff with jitter
                sleep_time = initial_retry_delay * (2 ** attempt) + random.uniform(0, 1)
                time.sleep(sleep_time)
        return None

    def fetch_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch market data with optimized fallback sequence"""
        try:
            # Try Alpha Vantage first
            self.rate_limiters['alpha_vantage'].wait()
            data = self._fetch_alpha_vantage(symbol)
            if data:
                return data
            
            # Try FRED for economic indicators
            if symbol in ['^TNX', '^TYX', '^UST2YR', '^UST5YR']:
                self.rate_limiters['fred'].wait()
                data = self._fetch_fred(symbol)
                if data:
                    return data
            
            # Fallback to yfinance
            return self._fetch_yfinance(symbol)
            
        except Exception as e:
            st.warning(f"Error fetching {symbol}: {str(e)}")
            return None

    def fetch_news_data(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch news with optimized fallback sequence"""
        news_data = []
        
        # Try NewsAPI first
        try:
            self.rate_limiters['newsapi'].wait()
            headers = {'X-Api-Key': self.api_config.newsapi_key}
            response = requests.get(
                f"{self.api_config.newsapi_base}/top-headlines",
                params={'category': 'business', 'language': 'en'},
                headers=headers,
                timeout=st.secrets.get('TIMEOUT', 10)
            )
            data = response.json()
            if 'articles' in data:
                news_data.extend(data['articles'])
        except Exception as e:
            st.warning(f"NewsAPI fetch failed: {str(e)}")
        
        # If no news from NewsAPI, try Marketaux
        if not news_data:
            try:
                self.rate_limiters['marketaux'].wait()
                params = {
                    'api_token': self.api_config.marketaux_key,
                    'limit': 10,
                    'sectors': 'Financial'
                }
                response = requests.get(
                    f"{self.api_config.marketaux_base}/news/all",
                    params=params,
                    timeout=st.secrets.get('TIMEOUT', 10)
                )
                data = response.json()
                if 'data' in data:
                    news_data.extend(data['data'])
            except Exception as e:
                st.warning(f"Marketaux fetch failed: {str(e)}")
        
        return news_data if news_data else None

    def fetch_market_sentiment(self) -> Optional[Dict[str, Any]]:
        """Fetch market sentiment with retry mechanism"""
        try:
            self.rate_limiters['finnhub'].wait()
            headers = {'X-Finnhub-Token': self.api_config.finnhub_key}
            response = requests.get(
                f"{self.api_config.finnhub_base}/news/sentiment",
                headers=headers,
                timeout=st.secrets.get('TIMEOUT', 10)
            )
            return response.json()
        except Exception as e:
            st.warning(f"Finnhub sentiment fetch failed: {str(e)}")
            return None

    def get_market_data(self) -> Optional[Dict[str, Any]]:
        """Get market data using the fetch_market_data function"""
        try:
            return fetch_market_data()
        except Exception as e:
            st.error(f"Error in get_market_data: {str(e)}")
            return None

class DataFetchStatus:
    def __init__(self):
        self.lock = threading.Lock()
        self.fetched = 0
        self.total = 0
        self.failed = []
        self.progress_bar = None
        self.start_time = time.time()
        self.data_queue = queue.Queue()

    def update(self, success=True, symbol=None, data=None):
        with self.lock:
            self.fetched += 1
            if not success and symbol:
                self.failed.append(symbol)
            if data:
                self.data_queue.put(data)
            if self.progress_bar:
                self.progress_bar.progress(self.fetched / self.total)
            
            if time.time() - self.start_time > FETCH_TIMEOUT:
                return True
        return False

def fetch_single_ticker(ticker_symbol, status, category, name, rate_limiter, data_fetcher):
    """Fetch data for a single ticker with retries and rate limiting"""
    for attempt in range(MAX_RETRIES):
        try:
            rate_limiter.wait()
            
            if attempt > 0:
                time.sleep(INITIAL_RETRY_DELAY * (2 ** attempt))
            
            data = data_fetcher.fetch_market_data(ticker_symbol)
            
            if data:
                result = {
                    'category': category,
                    'name': name,
                    'data': data
                }
                
                if status.update(success=True, data=result):
                    return None
                return result
            
            if attempt < MAX_RETRIES - 1:
                continue
                
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                continue
            st.warning(f"Failed to fetch {name} ({ticker_symbol}) after {MAX_RETRIES} attempts: {str(e)}")
    
    status.update(success=False, symbol=ticker_symbol)
    return None

@st.cache_data(ttl=300)
def fetch_market_data():
    """Fetch all market data with retries"""
    try:
        # Define all market indicators
        symbols = {
            'Treasury': {
                '2Y': '^UST2YR',
                '5Y': '^UST5YR',
                '10Y': '^TNX',
                '30Y': '^TYX'
            },
            'TIPS': {
                '5Y': '^T5YIE',  # 5-Year TIPS
                '10Y': '^T10YIE'  # 10-Year TIPS
            },
            'Fed_Funds': {
                'Current': '^FFR',  # Current Fed Funds Rate
                'Next_Meeting': 'FFN=F'  # Fed Funds Futures
            },
            'Commodities': {
                'Gold': 'GC=F',
                'Silver': 'SI=F',
                'Oil': 'CL=F'
            },
            'Currencies': {
                'DXY': 'DX-Y.NYB',  # US Dollar Index
                'EUR/USD': 'EURUSD=X',
                'JPY/USD': 'JPYUSD=X'
            },
            'VIX': '^VIX'
        }
        
        data = {}
        max_retries = 3
        retry_delay = 1
        
        # Fetch data for each category
        for category, category_symbols in symbols.items():
            data[category] = {}
            
            if category == 'VIX':
                # Handle VIX separately
                for attempt in range(max_retries):
                    try:
                        ticker = yf.Ticker(category_symbols)
                        hist = ticker.history(period="2d")
                        if not hist.empty:
                            data[category] = {
                                'current': float(hist['Close'].iloc[-1]),
                                'previous': float(hist['Close'].iloc[0])
                            }
                            break
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                    except Exception as e:
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        st.warning(f"Could not fetch {category} data: {str(e)}")
                continue
            
            # Handle other categories
            for name, symbol in category_symbols.items():
                for attempt in range(max_retries):
                    try:
                        ticker = yf.Ticker(symbol)
                        hist = ticker.history(period="2d")
                        if not hist.empty:
                            data[category][name] = {
                                'current': float(hist['Close'].iloc[-1]),
                                'previous': float(hist['Close'].iloc[0])
                            }
                            break
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                    except Exception as e:
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        st.warning(f"Could not fetch {name} data: {str(e)}")
        
        # Ensure we have at least some data before returning
        if not any(data.values()):
            st.error("Failed to fetch any market data")
            return None
            
        return data
    except Exception as e:
        st.error(f"Error fetching market data: {str(e)}")
        return None

def calculate_real_rates(data):
    """Calculate real interest rates"""
    if not data or 'Treasury' not in data or 'TIPS' not in data:
        return None
    
    real_rates = {}
    
    # Calculate 5Y real rate
    if '5Y' in data['Treasury'] and '5Y' in data['TIPS']:
        nominal_5y = data['Treasury']['5Y']['current']
        tips_5y = data['TIPS']['5Y']['current']
        real_rates['5Y'] = {
            'current': nominal_5y - tips_5y,
            'previous': (data['Treasury']['5Y']['previous'] - data['TIPS']['5Y']['previous'])
        }
    
    # Calculate 10Y real rate
    if '10Y' in data['Treasury'] and '10Y' in data['TIPS']:
        nominal_10y = data['Treasury']['10Y']['current']
        tips_10y = data['TIPS']['10Y']['current']
        real_rates['10Y'] = {
            'current': nominal_10y - tips_10y,
            'previous': (data['Treasury']['10Y']['previous'] - data['TIPS']['10Y']['previous'])
        }
    
    return real_rates

def calculate_implied_rates(data):
    """Calculate implied rates from futures"""
    if not data or 'Futures' not in data:
        return None
    
    implied_rates = {}
    
    # Calculate implied rates from bond futures
    if 'ZB' in data['Futures']:  # 30-Year Bond Futures
        zb_price = data['Futures']['ZB']['current']
        implied_rates['30Y'] = {
            'current': (100 - zb_price),
            'previous': (100 - data['Futures']['ZB']['previous'])
        }
    
    if 'ZN' in data['Futures']:  # 10-Year Note Futures
        zn_price = data['Futures']['ZN']['current']
        implied_rates['10Y'] = {
            'current': (100 - zn_price),
            'previous': (100 - data['Futures']['ZN']['previous'])
        }
    
    if 'ZF' in data['Futures']:  # 5-Year Note Futures
        zf_price = data['Futures']['ZF']['current']
        implied_rates['5Y'] = {
            'current': (100 - zf_price),
            'previous': (100 - data['Futures']['ZF']['previous'])
        }
    
    return implied_rates

def create_enhanced_yield_curve_plot(treasury_data, real_rates=None, implied_rates=None):
    """Create enhanced yield curve visualization with annotations and analysis"""
    if not treasury_data:
        return None
        
    fig = go.Figure()
    
    # Plot current yield curve
    tenors = ['2Y', '5Y', '10Y', '30Y']
    current_rates = [treasury_data[t]['current'] for t in tenors]
    previous_rates = [treasury_data[t]['previous'] for t in tenors]
    
    # Add nominal yield curve with enhanced styling
    fig.add_trace(go.Scatter(
        x=tenors,
        y=current_rates,
        mode='lines+markers+text',
        name='Current Nominal',
        line=dict(color='blue', width=3),
        marker=dict(size=10, symbol='circle'),
        text=[f"{rate:.2f}%" for rate in current_rates],
        textposition="top center"
    ))
    
    fig.add_trace(go.Scatter(
        x=tenors,
        y=previous_rates,
        mode='lines+markers',
        name='Previous Nominal',
        line=dict(color='red', width=2, dash='dash'),
        marker=dict(size=8, symbol='circle')
    ))
    
    # Calculate and display spreads
    spreads = {
        '2s10s': current_rates[2] - current_rates[0],  # 10Y - 2Y
        '5s10s': current_rates[2] - current_rates[1],  # 10Y - 5Y
        '10s30s': current_rates[3] - current_rates[2]  # 30Y - 10Y
    }
    
    # Add spread annotations
    for i, (spread_name, spread_value) in enumerate(spreads.items()):
        fig.add_annotation(
            x=tenors[i],
            y=max(current_rates[i], current_rates[i+1]),
            text=f"{spread_name}: {spread_value:.2f}%",
            showarrow=True,
            arrowhead=1,
            yshift=10
        )
    
    # Add real rates if available
    if real_rates:
        real_tenors = list(real_rates.keys())
        real_current = [real_rates[t]['current'] for t in real_tenors]
        real_previous = [real_rates[t]['previous'] for t in real_tenors]
        
        fig.add_trace(go.Scatter(
            x=real_tenors,
            y=real_current,
            mode='lines+markers',
            name='Current Real',
            line=dict(color='green', width=2),
            marker=dict(size=8, symbol='diamond')
        ))
        
        fig.add_trace(go.Scatter(
            x=real_tenors,
            y=real_previous,
            mode='lines+markers',
            name='Previous Real',
            line=dict(color='orange', width=2, dash='dash'),
            marker=dict(size=8, symbol='diamond')
        ))
    
    # Calculate curve changes and risk signals
    spread_change_2s10s = (treasury_data['10Y']['current'] - treasury_data['2Y']['current']) - \
                         (treasury_data['10Y']['previous'] - treasury_data['2Y']['previous'])
    
    spread_change_5s10s = (treasury_data['10Y']['current'] - treasury_data['5Y']['current']) - \
                         (treasury_data['10Y']['previous'] - treasury_data['5Y']['previous'])
    
    # Add risk signals
    risk_signals = []
    if spread_change_2s10s > 0.05:
        risk_signals.append("Steepening (Risk-On)")
    elif spread_change_2s10s < -0.05:
        risk_signals.append("Flattening (Risk-Off)")
    
    if treasury_data['2Y']['current'] > treasury_data['10Y']['current']:
        risk_signals.append("Inverted (Recession Risk)")
    
    # Update layout with enhanced styling
    fig.update_layout(
        title=dict(
            text=f'Enhanced Yield Curve Analysis<br>2s10s Spread Change: {spread_change_2s10s:.2f}% | 5s10s Spread Change: {spread_change_5s10s:.2f}%<br>Risk Signals: {" | ".join(risk_signals)}',
            x=0.5,
            y=0.95
        ),
        xaxis_title='Tenor',
        yaxis_title='Yield (%)',
        showlegend=True,
        hovermode='x unified',
        template='plotly_white',
        height=600,
        annotations=[
            dict(
                text="Higher Yields = Risk-Off",
                xref="paper",
                yref="paper",
                x=0.02,
                y=0.98,
                showarrow=False,
                font=dict(size=12, color="red")
            ),
            dict(
                text="Lower Yields = Risk-On",
                xref="paper",
                yref="paper",
                x=0.02,
                y=0.95,
                showarrow=False,
                font=dict(size=12, color="green")
            )
        ]
    )
    
    return fig

def determine_market_sentiment(data):
    """Determine market sentiment based on various indicators"""
    if not data:
        return "Unable to determine sentiment"
    
    signals = []
    
    # Treasury yield analysis
    if 'Treasury' in data:
        treasury = data['Treasury']
        if '2Y' in treasury and '10Y' in treasury:
            spread = treasury['10Y']['current'] - treasury['2Y']['current']
            prev_spread = treasury['10Y']['previous'] - treasury['2Y']['previous']
            if spread > prev_spread:
                signals.append("Steepening yield curve")
            else:
                signals.append("Flattening yield curve")
    
    # Real rates analysis
    real_rates = calculate_real_rates(data)
    if real_rates:
        for tenor, rates in real_rates.items():
            real_rate_change = rates['current'] - rates['previous']
            if real_rate_change > 0.1:
                signals.append(f"{tenor} real rates rising (risk-off)")
            elif real_rate_change < -0.1:
                signals.append(f"{tenor} real rates falling (risk-on)")
    
    # Fed Funds analysis
    if 'Fed_Funds' in data:
        if 'Next_Meeting' in data['Fed_Funds']:
            implied_rate = data['Fed_Funds']['Next_Meeting']['current']
            current_rate = data['Fed_Funds']['Current']['current']
            if implied_rate > current_rate:
                signals.append("Market pricing in rate hike")
            elif implied_rate < current_rate:
                signals.append("Market pricing in rate cut")
    
    # VIX analysis
    if 'VIX' in data:
        vix_change = data['VIX']['current'] - data['VIX']['previous']
        if vix_change > 2:
            signals.append("Risk-off (VIX spike)")
        elif vix_change < -2:
            signals.append("Risk-on (VIX drop)")
    
    # Gold analysis
    if 'Commodities' in data and 'Gold' in data['Commodities']:
        gold_change = data['Commodities']['Gold']['current'] - data['Commodities']['Gold']['previous']
        if gold_change > 0:
            signals.append("Gold up (risk-off)")
        else:
            signals.append("Gold down (risk-on)")
    
    # DXY analysis
    if 'Currencies' in data and 'DXY' in data['Currencies']:
        dxy_change = data['Currencies']['DXY']['current'] - data['Currencies']['DXY']['previous']
        if dxy_change > 0:
            signals.append("USD stronger")
        else:
            signals.append("USD weaker")
    
    return " | ".join(signals) if signals else "Neutral"

class DataValidator:
    def __init__(self):
        self.required_fields = {
            'market_data': ['price', 'volume', 'timestamp'],
            'news': ['title', 'content', 'source', 'timestamp'],
            'sentiment': ['score', 'confidence', 'timestamp']
        }
        
    def validate_data(self, data_type: str, data: Dict[str, Any]) -> bool:
        """Validate data structure and content"""
        if data_type not in self.required_fields:
            return False
            
        required = self.required_fields[data_type]
        return all(field in data for field in required)
        
    def sanitize_data(self, data_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize data to ensure consistency"""
        if not self.validate_data(data_type, data):
            return {}
            
        sanitized = {}
        for field in self.required_fields[data_type]:
            if field in data:
                sanitized[field] = data[field]
        return sanitized

class DataQualityMetrics:
    def __init__(self):
        self.metrics = {
            'completeness': {},
            'timeliness': {},
            'consistency': {},
            'accuracy': {}
        }
        self.thresholds = {
            'completeness': 0.95,  # 95% of required fields present
            'timeliness': 300,     # 5 minutes max age
            'consistency': 0.90,   # 90% consistency with historical data
            'accuracy': 0.98       # 98% accuracy threshold
        }
        
    def calculate_metrics(self, data_type: str, data: Dict[str, Any], historical_data: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """Calculate data quality metrics"""
        metrics = {}
        
        # Completeness
        required_fields = len(data.keys())
        present_fields = sum(1 for v in data.values() if v is not None)
        metrics['completeness'] = present_fields / required_fields if required_fields > 0 else 0
        
        # Timeliness
        if 'timestamp' in data:
            age = time.time() - data['timestamp']
            metrics['timeliness'] = 1.0 if age <= self.thresholds['timeliness'] else 0.0
        
        # Consistency
        if historical_data:
            matching_fields = sum(1 for k, v in data.items() 
                                if k in historical_data and abs(v - historical_data[k]) < 0.01)
            metrics['consistency'] = matching_fields / len(data) if data else 0
        
        # Accuracy (based on value ranges and patterns)
        if data_type == 'market_data':
            metrics['accuracy'] = self._validate_market_data_ranges(data)
        elif data_type == 'news':
            metrics['accuracy'] = self._validate_news_content(data)
            
        return metrics
    
    def _validate_market_data_ranges(self, data: Dict[str, Any]) -> float:
        """Validate market data ranges"""
        valid_ranges = {
            'price': (0, 1000000),
            'volume': (0, 1000000000),
            'change': (-100, 100)
        }
        
        valid_count = 0
        total_count = 0
        
        for field, (min_val, max_val) in valid_ranges.items():
            if field in data:
                total_count += 1
                if min_val <= data[field] <= max_val:
                    valid_count += 1
                    
        return valid_count / total_count if total_count > 0 else 0
    
    def _validate_news_content(self, data: Dict[str, Any]) -> float:
        """Validate news content quality"""
        if not data.get('content'):
            return 0.0
            
        # Check content length
        if len(data['content']) < 50:
            return 0.5
            
        # Check for required elements
        required_elements = ['title', 'content', 'source']
        valid_elements = sum(1 for elem in required_elements if elem in data and data[elem])
        
        return valid_elements / len(required_elements)

class EnhancedDataValidator(DataValidator):
    def __init__(self):
        super().__init__()
        self.quality_metrics = DataQualityMetrics()
        self.validation_rules = {
            'market_data': self._validate_market_data,
            'news': self._validate_news,
            'sentiment': self._validate_sentiment
        }
        self.valid_categories = {
            'sentiment': {'positive', 'negative', 'neutral'},
            'market_sectors': {'technology', 'finance', 'healthcare', 'energy', 'consumer', 'industrial'},
            'news_categories': {'business', 'economy', 'markets', 'technology', 'politics'}
        }
        
    def validate_data(self, data_type: str, data: Dict[str, Any], historical_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
        """Enhanced data validation with quality metrics"""
        # Basic validation
        if not super().validate_data(data_type, data):
            return False, {'error': 'Basic validation failed'}
            
        # Type-specific validation
        if data_type in self.validation_rules:
            validation_result = self.validation_rules[data_type](data)
            if not validation_result['valid']:
                return False, validation_result
                
        # Calculate quality metrics
        metrics = self.quality_metrics.calculate_metrics(data_type, data, historical_data)
        
        # Check if metrics meet thresholds
        for metric, value in metrics.items():
            if value < self.quality_metrics.thresholds[metric]:
                return False, {
                    'error': f'Quality threshold not met for {metric}',
                    'metrics': metrics
                }
                
        return True, {'metrics': metrics}
        
    def _validate_market_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate market data specific rules"""
        validation = {'valid': True, 'errors': []}
        
        # Price validation
        if 'price' in data:
            if data['price'] <= 0:
                validation['valid'] = False
                validation['errors'].append('Price must be positive')
            if data['price'] > 1000000:  # Unrealistic price check
                validation['valid'] = False
                validation['errors'].append('Price exceeds realistic threshold')
        
        # Volume validation
        if 'volume' in data:
            if data['volume'] < 0:
                validation['valid'] = False
                validation['errors'].append('Volume cannot be negative')
            if data['volume'] > 1000000000:  # Unrealistic volume check
                validation['valid'] = False
                validation['errors'].append('Volume exceeds realistic threshold')
        
        # Price change validation
        if 'change' in data:
            if not -100 <= data['change'] <= 100:  # Percentage change limits
                validation['valid'] = False
                validation['errors'].append('Price change outside valid range (-100% to 100%)')
        
        # Timestamp validation
        if 'timestamp' in data:
            age = time.time() - data['timestamp']
            if age > 3600:  # 1 hour
                validation['valid'] = False
                validation['errors'].append('Data is too old')
            if age < 0:  # Future timestamp
                validation['valid'] = False
                validation['errors'].append('Invalid future timestamp')
        
        # Market data specific validations
        if 'symbol' in data:
            if not isinstance(data['symbol'], str):
                validation['valid'] = False
                validation['errors'].append('Symbol must be a string')
            if len(data['symbol']) > 10:  # Maximum symbol length
                validation['valid'] = False
                validation['errors'].append('Symbol too long')
        
        if 'exchange' in data:
            valid_exchanges = {'NYSE', 'NASDAQ', 'AMEX', 'OTC'}
            if data['exchange'] not in valid_exchanges:
                validation['valid'] = False
                validation['errors'].append('Invalid exchange')
        
        return validation
        
    def _validate_news(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate news data specific rules"""
        validation = {'valid': True, 'errors': []}
        
        # Content length validation
        if 'content' in data:
            if len(data['content']) < 50:
                validation['valid'] = False
                validation['errors'].append('Content too short (minimum 50 characters)')
            if len(data['content']) > 10000:  # Maximum length check
                validation['valid'] = False
                validation['errors'].append('Content too long (maximum 10000 characters)')
        
        # Title validation
        if 'title' in data:
            if len(data['title']) < 10:
                validation['valid'] = False
                validation['errors'].append('Title too short (minimum 10 characters)')
            if len(data['title']) > 200:  # Maximum title length
                validation['valid'] = False
                validation['errors'].append('Title too long (maximum 200 characters)')
        
        # Source validation
        if 'source' in data:
            if not data['source']:
                validation['valid'] = False
                validation['errors'].append('Invalid source')
            if not isinstance(data['source'], str):
                validation['valid'] = False
                validation['errors'].append('Source must be a string')
        
        # URL validation
        if 'url' in data:
            if not data['url'].startswith(('http://', 'https://')):
                validation['valid'] = False
                validation['errors'].append('Invalid URL format')
        
        # Category validation
        if 'category' in data:
            if data['category'] not in self.valid_categories['news_categories']:
                validation['valid'] = False
                validation['errors'].append('Invalid news category')
        
        # Timestamp validation
        if 'published_at' in data:
            try:
                published_time = datetime.fromisoformat(data['published_at'].replace('Z', '+00:00'))
                if published_time > datetime.now():
                    validation['valid'] = False
                    validation['errors'].append('Future publication date')
            except ValueError:
                validation['valid'] = False
                validation['errors'].append('Invalid publication date format')
        
        return validation
        
    def _validate_sentiment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate sentiment data specific rules"""
        validation = {'valid': True, 'errors': []}
        
        # Sentiment score validation
        if 'score' in data:
            if not -1 <= data['score'] <= 1:
                validation['valid'] = False
                validation['errors'].append('Sentiment score must be between -1 and 1')
            if not isinstance(data['score'], (int, float)):
                validation['valid'] = False
                validation['errors'].append('Sentiment score must be a number')
        
        # Confidence score validation
        if 'confidence' in data:
            if not 0 <= data['confidence'] <= 1:
                validation['valid'] = False
                validation['errors'].append('Confidence score must be between 0 and 1')
            if not isinstance(data['confidence'], (int, float)):
                validation['valid'] = False
                validation['errors'].append('Confidence score must be a number')
        
        # Sentiment categories validation
        if 'categories' in data:
            if not all(cat in self.valid_categories['sentiment'] for cat in data['categories']):
                validation['valid'] = False
                validation['errors'].append('Invalid sentiment category')
        
        # Magnitude validation
        if 'magnitude' in data:
            if not 0 <= data['magnitude'] <= 1:
                validation['valid'] = False
                validation['errors'].append('Magnitude must be between 0 and 1')
        
        # Source validation
        if 'source' in data:
            if not isinstance(data['source'], str):
                validation['valid'] = False
                validation['errors'].append('Source must be a string')
        
        return validation

class DataDistributionManager:
    def __init__(self):
        self.cache = {}
        self.cache_lock = threading.Lock()
        self.data_queue = queue.Queue()
        self.cache_durations = {
            'market_data': 900,     # 15 minutes
            'news': 1800,          # 30 minutes
            'sentiment': 3600,     # 1 hour
            'analysis': 1800,      # 30 minutes
            'yield_curve': 3600,   # 1 hour
            'vix_data': 900,       # 15 minutes
            'gold_data': 1800,     # 30 minutes
            'correlation_data': 3600  # 1 hour
        }
        
    def distribute_data(self, data_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Basic data distribution"""
        with self.cache_lock:
            self.cache[data_type] = {
                'data': data,
                'timestamp': time.time()
            }
            self.data_queue.put((data_type, data))
        return {'success': True}
        
    def get_cached_data(self, data_type: str) -> Optional[Dict[str, Any]]:
        """Basic cached data retrieval"""
        with self.cache_lock:
            if data_type in self.cache:
                cached = self.cache[data_type]
                if time.time() - cached['timestamp'] < self.cache_durations.get(data_type, 300):
                    return cached['data']
        return None

class EnhancedDataDistributionManager(DataDistributionManager):
    def __init__(self):
        super().__init__()
        self.validator = EnhancedDataValidator()
        self.error_counts = {}
        self.retry_strategy = {
            'max_retries': 3,
            'retry_delay': 2,
            'backoff_factor': 2
        }
        
    def distribute_data(self, data_type: str, data: Dict[str, Any], historical_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Enhanced data distribution with validation and retry logic"""
        result = {
            'success': False,
            'error': None,
            'metrics': None
        }
        
        # Validate data
        is_valid, validation_result = self.validator.validate_data(data_type, data, historical_data)
        if not is_valid:
            result['error'] = validation_result.get('error', 'Validation failed')
            result['metrics'] = validation_result.get('metrics')
            return result
            
        # Implement retry logic
        for attempt in range(self.retry_strategy['max_retries']):
            try:
                with self.cache_lock:
                    self.cache[data_type] = {
                        'data': data,
                        'timestamp': time.time(),
                        'metrics': validation_result['metrics']
                    }
                    self.data_queue.put((data_type, data))
                result['success'] = True
                result['metrics'] = validation_result['metrics']
                break
            except Exception as e:
                if attempt == self.retry_strategy['max_retries'] - 1:
                    result['error'] = f'Distribution failed after {self.retry_strategy["max_retries"]} attempts: {str(e)}'
                time.sleep(self.retry_strategy['retry_delay'] * (self.retry_strategy['backoff_factor'] ** attempt))
                
        return result
        
    def get_cached_data(self, data_type: str) -> Optional[Dict[str, Any]]:
        """Enhanced cached data retrieval with quality check"""
        with self.cache_lock:
            if data_type in self.cache:
                cached = self.cache[data_type]
                if time.time() - cached['timestamp'] < self.cache_durations.get(data_type, 300):
                    # Check data quality
                    metrics = cached.get('metrics', {})
                    if all(metrics.get(metric, 0) >= self.validator.quality_metrics.thresholds[metric]
                          for metric in ['completeness', 'timeliness']):
                        return cached['data']
        return None

class DataRefreshProtocol:
    def __init__(self):
        self.last_refresh = {}
        self.refresh_intervals = {
            'market_data': 300,  # 5 minutes
            'news': 1800,       # 30 minutes
            'sentiment': 3600   # 1 hour
        }
    
    def should_refresh(self, data_type: str) -> bool:
        """Check if data should be refreshed based on type and last refresh time"""
        if data_type not in self.last_refresh:
            return True
            
        last_time = self.last_refresh[data_type]
        interval = self.refresh_intervals.get(data_type, 300)
        
        return (time.time() - last_time) > interval
    
    def update_refresh_time(self, data_type: str):
        """Update the last refresh time for a data type"""
        self.last_refresh[data_type] = time.time()

# Initialize data management components
data_fetcher = DataFetcher()
data_validator = EnhancedDataValidator()
data_distributor = EnhancedDataDistributionManager()
refresh_protocol = DataRefreshProtocol()

# Main dashboard
with st.spinner('Fetching market data...'):
    try:
        # Initialize analyzers
        market_analyzer = MarketAnalyzer()
        vix_analyzer = VIXAnalyzer()
        volatility_analyzer = VolatilityAnalyzer()
        gold_analyzer = GoldAnalyzer()
        skew_analyzer = VolatilitySkewAnalyzer()
        
        # Fetch and validate current data
        if refresh_protocol.should_refresh('market_data'):
            current_data = fetch_market_data()
            if current_data:
                # Get historical data for comparison
                historical_data = data_distributor.get_cached_data('market_data')
                
                # Distribute and validate data
                distribution_result = data_distributor.distribute_data(
                    'market_data',
                    current_data,
                    historical_data
                )
                
                if distribution_result['success']:
                    refresh_protocol.update_refresh_time('market_data')
                    # Get cached data for comparison
                    cached_data = data_distributor.get_cached_data('market_data')
                    
                    # Analyze market conditions
                    market_conditions = market_analyzer.analyze_market_conditions(current_data, cached_data)
                    
                    # Calculate expected range
                    expected_range = volatility_analyzer.calculate_expected_range(
                        current_data.get('VIX', {}).get('current', 0),
                        current_data.get('SPY', {}).get('current', 0)
                    )
                    
                    # Analyze gold term structure
                    gold_analysis = gold_analyzer.analyze_gold_term_structure(
                        current_data.get('Commodities', {}).get('Gold', {})
                    )
                    
                    # Analyze volatility skew
                    skew_analysis = skew_analyzer.analyze_volatility_skew(
                        current_data.get('Options', {})
                    )
                    
                    # Create plots
                    yield_curve_plot = create_enhanced_yield_curve_plot(
                        current_data.get('Treasury', {}),
                        market_conditions.get('real_rates'),
                        market_conditions.get('implied_rates')
                    )
                    
                    vix_premium_plot = vix_analyzer.create_vix_premium_plot(
                        current_data.get('VIX', {}),
                        current_data.get('SPY', {})
                    )
                    
                    if expected_range:
                        expected_range_plot = create_expected_range_plot(
                            current_data.get('SPY', {}).get('current', 0),
                            expected_range
                        )
                    
                    if gold_analysis:
                        gold_term_plot = create_gold_term_structure_plot(gold_analysis)
                    
                    if skew_analysis:
                        skew_plot = create_volatility_skew_plot(skew_analysis)
                    
                    # Store in session state
                    st.session_state['market_data'] = current_data
                    st.session_state['market_analysis'] = market_conditions
                    st.session_state['yield_curve_plot'] = yield_curve_plot
                    st.session_state['vix_premium_plot'] = vix_premium_plot
                    st.session_state['expected_range_plot'] = expected_range_plot
                    st.session_state['gold_term_plot'] = gold_term_plot
                    st.session_state['skew_plot'] = skew_plot
                    
                    # Display data quality metrics
                    if distribution_result['metrics']:
                        st.sidebar.write("### Data Quality Metrics")
                        for metric, value in distribution_result['metrics'].items():
                            st.sidebar.metric(
                                metric.capitalize(),
                                f"{value:.2%}",
                                delta=None if value >= data_distributor.validator.quality_metrics.thresholds[metric] else "Below threshold"
                            )
                else:
                    st.error(f"Data distribution failed: {distribution_result['error']}")
        else:
            # Use cached data
            current_data = data_distributor.get_cached_data('market_data')
            if not current_data:
                current_data = st.session_state.get('market_data')
            
            market_conditions = st.session_state.get('market_analysis')
            yield_curve_plot = st.session_state.get('yield_curve_plot')
            vix_premium_plot = st.session_state.get('vix_premium_plot')
            expected_range_plot = st.session_state.get('expected_range_plot')
            gold_term_plot = st.session_state.get('gold_term_plot')
            skew_plot = st.session_state.get('skew_plot')
        
        # Display data
        if current_data:
            display_market_data(current_data)
            
        if market_conditions:
            display_market_analysis(market_conditions)
            
        if yield_curve_plot:
            st.plotly_chart(yield_curve_plot, use_container_width=True)
            
        if vix_premium_plot:
            st.plotly_chart(vix_premium_plot, use_container_width=True)
            
        if expected_range_plot:
            st.plotly_chart(expected_range_plot, use_container_width=True)
            
        if gold_term_plot:
            st.plotly_chart(gold_term_plot, use_container_width=True)
            
        if skew_plot:
            st.plotly_chart(skew_plot, use_container_width=True)
            
    except Exception as e:
        st.error(f"Error updating dashboard: {str(e)}")
        if st.session_state.get('market_data'):
            st.warning("Displaying cached data due to fetch error")
            display_market_data(st.session_state['market_data'])
            if st.session_state.get('market_analysis'):
                display_market_analysis(st.session_state['market_analysis'])
            if st.session_state.get('yield_curve_plot'):
                st.plotly_chart(st.session_state['yield_curve_plot'], use_container_width=True)
            if st.session_state.get('vix_premium_plot'):
                st.plotly_chart(st.session_state['vix_premium_plot'], use_container_width=True)
            if st.session_state.get('expected_range_plot'):
                st.plotly_chart(st.session_state['expected_range_plot'], use_container_width=True)
            if st.session_state.get('gold_term_plot'):
                st.plotly_chart(st.session_state['gold_term_plot'], use_container_width=True)
            if st.session_state.get('skew_plot'):
                st.plotly_chart(st.session_state['skew_plot'], use_container_width=True)

def display_market_data(data: Dict[str, Any]) -> None:
    """Display market data in a structured format"""
    if not data:
        st.warning("No market data available")
        return

    # Create columns for different market segments
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Market Indicators")
        
        # Display VIX
        if 'VIX' in data:
            vix = data['VIX']
            st.metric(
                "VIX",
                f"{vix.get('current', 0):.2f}",
                f"{vix.get('current', 0) - vix.get('previous', 0):.2f}"
            )

        # Display Treasury Yields
        if 'Treasury' in data:
            st.write("### Treasury Yields")
            treasury = data['Treasury']
            for tenor, values in treasury.items():
                st.metric(
                    f"{tenor} Yield",
                    f"{values.get('current', 0):.2f}%",
                    f"{values.get('current', 0) - values.get('previous', 0):.2f}%"
                )

    with col2:
        st.subheader("Commodities & Currencies")
        
        # Display Commodities
        if 'Commodities' in data:
            st.write("### Commodities")
            commodities = data['Commodities']
            for commodity, values in commodities.items():
                st.metric(
                    commodity,
                    f"${values.get('current', 0):.2f}",
                    f"${values.get('current', 0) - values.get('previous', 0):.2f}"
                )

        # Display Currencies
        if 'Currencies' in data:
            st.write("### Currencies")
            currencies = data['Currencies']
            for currency, values in currencies.items():
                st.metric(
                    currency,
                    f"{values.get('current', 0):.4f}",
                    f"{values.get('current', 0) - values.get('previous', 0):.4f}"
                )

    # Display Fed Funds Rate
    if 'Fed_Funds' in data:
        st.subheader("Fed Funds Rate")
        fed_funds = data['Fed_Funds']
        if 'Current' in fed_funds:
            st.metric(
                "Current Rate",
                f"{fed_funds['Current'].get('current', 0):.2f}%",
                f"{fed_funds['Current'].get('current', 0) - fed_funds['Current'].get('previous', 0):.2f}%"
            )
        if 'Next_Meeting' in fed_funds:
            st.metric(
                "Next Meeting Implied Rate",
                f"{fed_funds['Next_Meeting'].get('current', 0):.2f}%",
                f"{fed_funds['Next_Meeting'].get('current', 0) - fed_funds['Next_Meeting'].get('previous', 0):.2f}%"
            )

def display_news_section(news_data):
    if news_data:
        st.subheader("Latest Financial News")
        for article in news_data[:5]:  # Show top 5 news items
            with st.expander(article.get('title', 'No title')):
                st.write(article.get('description', 'No description'))
                st.caption(f"Source: {article.get('source', {}).get('name', 'Unknown')}")

def display_sentiment_section(sentiment_data):
    if sentiment_data:
        st.subheader("Market Sentiment")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Bullish", f"{sentiment_data.get('bullish', 0):.1f}%")
        with col2:
            st.metric("Neutral", f"{sentiment_data.get('neutral', 0):.1f}%")
        with col3:
            st.metric("Bearish", f"{sentiment_data.get('bearish', 0):.1f}%")

def display_market_analysis(analysis: Dict[str, Any]):
    """Display comprehensive market analysis"""
    st.subheader("Market Analysis")
    
    # Risk On/Off Section
    st.write("### Risk Conditions")
    st.write(analysis['risk_on_off'])
    
    # Yield Curve Analysis
    st.write("### Yield Curve Analysis")
    curve = analysis['yield_curve']
    if curve['curve_type']:
        st.write(f"Curve Type: {curve['curve_type']}")
        st.write(f"Change: {curve['change']:.2f}%")
        st.write("Implications:")
        for imp in curve['implications']:
            st.write(f"- {imp}")
            
    # Market Direction
    st.write("### Market Direction")
    direction = analysis['market_direction']
    if direction['trend']:
        st.write(f"Trend: {direction['trend']}")
        st.write(f"Strength: {direction['strength']}")
        st.write("Key Levels:")
        for level in direction['key_levels']:
            st.write(f"- {level}")
            
    # Correlations
    st.write("### Asset Correlations")
    correlations = analysis['correlations']
    for asset_pair, correlation in correlations.items():
        if correlation:
            st.write(f"{asset_pair.replace('_', ' ').title()}: {correlation}")

def create_expected_range_plot(current_price: float, expected_range: Dict[str, Any]) -> go.Figure:
    """Create plot for expected price range based on VIX"""
    fig = go.Figure()
    
    # Add current price line
    fig.add_trace(go.Scatter(
        x=[current_price, current_price],
        y=[0, 1],
        mode='lines',
        name='Current Price',
        line=dict(color='blue', width=2, dash='dash')
    ))
    
    # Add probability zones
    zones = [
        ('1σ', expected_range['daily']['1sigma'], 'green'),
        ('2σ', expected_range['daily']['2sigma'], 'yellow'),
        ('3σ', expected_range['daily']['3sigma'], 'red')
    ]
    
    for zone_name, range_data, color in zones:
        fig.add_trace(go.Scatter(
            x=[range_data['lower'], range_data['upper']],
            y=[0.5, 0.5],
            mode='lines+markers',
            name=f'{zone_name} Range',
            line=dict(color=color, width=3),
            marker=dict(size=10)
        ))
        
    # Update layout
    fig.update_layout(
        title='Expected Price Range (Based on VIX)',
        xaxis_title='Price',
        yaxis_title='Probability',
        showlegend=True,
        height=400
    )
    
    return fig

def create_gold_term_structure_plot(gold_analysis: Dict[str, Any]) -> go.Figure:
    """Create plot for gold term structure analysis"""
    fig = go.Figure()
    
    # Plot term structure
    tenors = list(gold_analysis['term_prices'].keys())
    prices = [gold_analysis['term_prices'][t]['price'] for t in tenors]
    contango = [gold_analysis['term_prices'][t]['contango'] for t in tenors]
    
    # Add price line
    fig.add_trace(go.Scatter(
        x=tenors,
        y=prices,
        mode='lines+markers',
        name='Term Prices',
        line=dict(color='gold', width=3),
        marker=dict(size=10)
    ))
    
    # Add contango/backwardation
    fig.add_trace(go.Scatter(
        x=tenors,
        y=contango,
        mode='lines+markers',
        name='Contango/Backwardation',
        line=dict(color='purple', width=2),
        marker=dict(size=8)
    ))
    
    # Update layout
    fig.update_layout(
        title='Gold Term Structure Analysis',
        xaxis_title='Tenor',
        yaxis_title='Price/Contango',
        showlegend=True,
        height=400
    )
    
    return fig

def create_volatility_skew_plot(skew_analysis: Dict[str, Any]) -> go.Figure:
    """Create plot for volatility skew analysis"""
    fig = go.Figure()
    
    # Plot put skew
    if 'put_skew' in skew_analysis:
        fig.add_trace(go.Scatter(
            x=skew_analysis['put_skew']['strikes'],
            y=skew_analysis['put_skew']['vols'],
            mode='lines+markers',
            name='Put Skew',
            line=dict(color='red', width=2),
            marker=dict(size=8)
        ))
    
    # Plot call skew
    if 'call_skew' in skew_analysis:
        fig.add_trace(go.Scatter(
            x=skew_analysis['call_skew']['strikes'],
            y=skew_analysis['call_skew']['vols'],
            mode='lines+markers',
            name='Call Skew',
            line=dict(color='green', width=2),
            marker=dict(size=8)
        ))
    
    # Update layout
    fig.update_layout(
        title='Volatility Skew Analysis',
        xaxis_title='Strike Price',
        yaxis_title='Implied Volatility',
        showlegend=True,
        height=400
    )
    
    return fig 

def display_data_quality_metrics(metrics: Dict[str, float]) -> None:
    """Display data quality metrics with visual indicators"""
    st.subheader("Data Quality Metrics")
    
    # Create columns for metrics
    cols = st.columns(4)
    
    # Define thresholds and colors
    thresholds = {
        'completeness': 0.95,
        'timeliness': 0.90,
        'consistency': 0.85,
        'accuracy': 0.90
    }
    
    colors = {
        'good': 'green',
        'warning': 'orange',
        'critical': 'red'
    }
    
    # Display each metric
    for i, (metric, value) in enumerate(metrics.items()):
        with cols[i]:
            # Determine status and color
            if value >= thresholds[metric]:
                status = 'good'
            elif value >= thresholds[metric] * 0.8:
                status = 'warning'
            else:
                status = 'critical'
            
            # Create metric display
            st.metric(
                label=metric.capitalize(),
                value=f"{value:.1%}",
                delta=None,
                delta_color=colors[status]
            )
            
            # Add threshold indicator
            st.progress(value)
            st.caption(f"Threshold: {thresholds[metric]:.1%}")

def main():
    st.title("Financial Market Dashboard")
    
    try:
        # Initialize data management components
        data_fetcher = DataFetcher()
        data_validator = EnhancedDataValidator()
        data_distributor = EnhancedDataDistributionManager()
        refresh_protocol = DataRefreshProtocol()
        
        # Initialize analyzers
        market_analyzer = MarketAnalyzer()
        vix_analyzer = VIXAnalyzer()
        volatility_analyzer = VolatilityAnalyzer()
        gold_analyzer = GoldAnalyzer()
        skew_analyzer = VolatilitySkewAnalyzer()
        
        # Fetch market data with spinner
        with st.spinner("Fetching market data..."):
            try:
                market_data = fetch_market_data()
                if not market_data:
                    st.error("Failed to fetch market data. Using cached data if available.")
                    market_data = data_distributor.get_cached_data('market_data')
                    if not market_data:
                        st.error("No cached data available. Please try again later.")
                        return
            except Exception as e:
                st.error(f"Error fetching market data: {str(e)}")
                market_data = data_distributor.get_cached_data('market_data')
                if not market_data:
                    st.error("No cached data available. Please try again later.")
                    return
        
        # Validate and distribute data
        if not data_validator.validate_data('market_data', market_data):
            st.error("Invalid market data received. Using cached data if available.")
            market_data = data_distributor.get_cached_data('market_data')
            if not market_data:
                st.error("No cached data available. Please try again later.")
                return
        
        # Analyze market conditions
        try:
            market_conditions = market_analyzer.analyze_market_conditions(market_data)
            vix_analysis = vix_analyzer.analyze_vix(market_data)
            volatility_analysis = volatility_analyzer.analyze_volatility(market_data)
            gold_analysis = gold_analyzer.analyze_gold_term_structure(market_data)
            skew_analysis = skew_analyzer.analyze_volatility_skew(market_data)
        except Exception as e:
            st.error(f"Error analyzing market data: {str(e)}")
            return
        
        # Display data quality metrics
        try:
            quality_metrics = data_validator.quality_metrics.get_metrics()
            display_data_quality_metrics(quality_metrics)
        except Exception as e:
            st.warning(f"Could not display data quality metrics: {str(e)}")
        
        # Create and display plots
        try:
            # Expected Range Plot
            if 'SPY' in market_data and 'VIX' in market_data:
                current_price = market_data['SPY'].get('current', 0)
                expected_range = volatility_analyzer.calculate_expected_range(
                    market_data['VIX'].get('current', 0),
                    current_price
                )
                if expected_range:
                    fig_range = create_expected_range_plot(current_price, expected_range)
                    st.plotly_chart(fig_range, use_container_width=True)
            
            # Gold Term Structure Plot
            if gold_analysis:
                fig_gold = create_gold_term_structure_plot(gold_analysis)
                st.plotly_chart(fig_gold, use_container_width=True)
            
            # Volatility Skew Plot
            if skew_analysis:
                fig_skew = create_volatility_skew_plot(skew_analysis)
                st.plotly_chart(fig_skew, use_container_width=True)
        except Exception as e:
            st.error(f"Error creating plots: {str(e)}")
        
        # Display market analysis
        try:
            st.subheader("Market Analysis")
            if market_conditions:
                st.write(f"Market Direction: {market_conditions.get('market_direction', {}).get('trend', 'Unknown')}")
                st.write(f"Market Strength: {market_conditions.get('market_direction', {}).get('strength', 'Unknown')}")
                st.write(f"Risk Level: {market_conditions.get('risk_on_off', 'Unknown')}")
            
            st.subheader("Risk Signals")
            if vix_analysis:
                st.write(f"VIX Status: {vix_analysis.get('status', 'Unknown')}")
            if gold_analysis:
                st.write(f"Gold Term Structure: {gold_analysis.get('term_structure', 'Unknown')}")
            if skew_analysis:
                st.write(f"Volatility Skew: {skew_analysis.get('skew_status', 'Unknown')}")
        except Exception as e:
            st.error(f"Error displaying market analysis: {str(e)}")
        
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        st.error("Please try refreshing the page or contact support if the issue persists.")

if __name__ == "__main__":
    main() 