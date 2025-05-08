import pandas as pd
import yfinance as yf
from fredapi import Fred
import requests
from typing import Dict, Optional, Tuple, Any, List
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import time
import logging
import json
import random
from pathlib import Path
import concurrent.futures
import aiohttp
import asyncio
from fake_useragent import UserAgent
import backoff
from ratelimit import limits, sleep_and_retry
from collections import defaultdict
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class APIMonitor:
    def __init__(self):
        self.usage = defaultdict(lambda: {'calls': 0, 'errors': 0, 'last_reset': datetime.now()})
        self.lock = threading.Lock()
        self.monitoring_file = Path("cache/api_usage.json")
        self.load_usage()
    
    def load_usage(self):
        """Load API usage from file"""
        try:
            if self.monitoring_file.exists():
                with open(self.monitoring_file, 'r') as f:
                    data = json.load(f)
                    for api, stats in data.items():
                        self.usage[api] = {
                            'calls': stats['calls'],
                            'errors': stats['errors'],
                            'last_reset': datetime.fromisoformat(stats['last_reset'])
                        }
        except Exception as e:
            logger.error(f"Error loading API usage: {str(e)}")
    
    def save_usage(self):
        """Save API usage to file"""
        try:
            with self.lock:
                data = {
                    api: {
                        'calls': stats['calls'],
                        'errors': stats['errors'],
                        'last_reset': stats['last_reset'].isoformat()
                    }
                    for api, stats in self.usage.items()
                }
                with open(self.monitoring_file, 'w') as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving API usage: {str(e)}")
    
    def record_call(self, api_name: str, success: bool = True):
        """Record an API call"""
        with self.lock:
            now = datetime.now()
            if (now - self.usage[api_name]['last_reset']).total_seconds() > 3600:
                # Reset counters after 1 hour
                self.usage[api_name] = {'calls': 0, 'errors': 0, 'last_reset': now}
            
            self.usage[api_name]['calls'] += 1
            if not success:
                self.usage[api_name]['errors'] += 1
            
            self.save_usage()
    
    def get_usage_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get current API usage statistics"""
        with self.lock:
            return {
                api: {
                    'calls': stats['calls'],
                    'errors': stats['errors'],
                    'error_rate': stats['errors'] / stats['calls'] if stats['calls'] > 0 else 0,
                    'last_reset': stats['last_reset'].isoformat()
                }
                for api, stats in self.usage.items()
            }

class RateLimiter:
    def __init__(self):
        self.alpha_vantage_limit = int(os.getenv('ALPHA_VANTAGE_RATE_LIMIT', 5))
        self.fred_limit = int(os.getenv('FRED_RATE_LIMIT', 120))
        self.finnhub_limit = int(os.getenv('FINNHUB_RATE_LIMIT', 60))
        self.newsapi_limit = int(os.getenv('NEWSAPI_RATE_LIMIT', 100))
        self.marketaux_limit = int(os.getenv('MARKETAUX_RATE_LIMIT', 50))

class DataFetcher:
    def __init__(self):
        self.fred = Fred(api_key=os.getenv('FRED_API_KEY'))
        self.cache = {}
        self.cache_duration = timedelta(minutes=5)
    
    def get_treasury_yields(self) -> pd.DataFrame:
        """Fetch Treasury yields from FRED."""
        try:
            # Fetch Treasury yields
            treasury_2y = self.fred.get_series('DGS2')
            treasury_5y = self.fred.get_series('DGS5')
            treasury_10y = self.fred.get_series('DGS10')
            treasury_30y = self.fred.get_series('DGS30')
            
            # Combine into DataFrame
            yield_curve = pd.DataFrame({
                '2Y': treasury_2y,
                '5Y': treasury_5y,
                '10Y': treasury_10y,
                '30Y': treasury_30y
            })
            
            return yield_curve
        except Exception as e:
            print(f"Error fetching Treasury yields: {str(e)}")
            return None
    
    def get_tips_yields(self) -> pd.DataFrame:
        """Fetch TIPS yields from FRED."""
        try:
            # Fetch TIPS yields
            tips_5y = self.fred.get_series('DFII5')
            tips_10y = self.fred.get_series('DFII10')
            tips_30y = self.fred.get_series('DFII30')
            
            # Combine into DataFrame
            tips_curve = pd.DataFrame({
                '5Y': tips_5y,
                '10Y': tips_10y,
                '30Y': tips_30y
            })
            
            return tips_curve
        except Exception as e:
            print(f"Error fetching TIPS yields: {str(e)}")
            return None
    
    def get_inflation_expectations(self) -> pd.Series:
        """Fetch inflation expectations from FRED."""
        try:
            # Fetch 5-year forward inflation expectations
            inflation_expectations = self.fred.get_series('T5YIFR')
            return inflation_expectations
        except Exception as e:
            print(f"Error fetching inflation expectations: {str(e)}")
            return None
    
    def get_fed_funds_futures(self) -> pd.DataFrame:
        """Fetch Fed Funds futures from FRED."""
        try:
            # Fetch Fed Funds futures
            ff_1m = self.fred.get_series('FF1')
            ff_3m = self.fred.get_series('FF3')
            
            # Combine into DataFrame
            fed_funds = pd.DataFrame({
                '1M': ff_1m,
                '3M': ff_3m
            })
            
            return fed_funds
        except Exception as e:
            print(f"Error fetching Fed Funds futures: {str(e)}")
            return None
    
    def get_market_data(self) -> Dict:
        """Fetch market data from Yahoo Finance."""
        try:
            # Fetch VIX
            vix = yf.download('^VIX', period='1d')['Close'].iloc[-1]
            
            # Fetch S&P 500
            spy = yf.download('SPY', period='2d')['Close']
            spy_current = spy.iloc[-1]
            spy_previous = spy.iloc[-2]
            
            # Fetch gold futures
            gold = yf.download('GC=F', period='1d')['Close'].iloc[-1]
            
            # Fetch dollar index
            dxy = yf.download('DX-Y.NYB', period='1d')['Close'].iloc[-1]
            
            return {
                'vix': vix,
                'spy_current': spy_current,
                'spy_previous': spy_previous,
                'gold': gold,
                'dxy': dxy
            }
        except Exception as e:
            print(f"Error fetching market data: {str(e)}")
            return None
    
    def get_all_data(self) -> Dict:
        """Fetch all data sources."""
        return {
            'yield_curve': self.get_treasury_yields(),
            'tips_curve': self.get_tips_yields(),
            'inflation_expectations': self.get_inflation_expectations(),
            'fed_funds': self.get_fed_funds_futures(),
            'market_data': self.get_market_data()
        }
    
    def calculate_real_rates(self, nominal_rates: pd.DataFrame, tips_rates: pd.DataFrame) -> pd.DataFrame:
        """Calculate real rates from nominal and TIPS yields."""
        if nominal_rates is None or tips_rates is None:
            return None
        
        # Align the data
        common_dates = nominal_rates.index.intersection(tips_rates.index)
        nominal_aligned = nominal_rates.loc[common_dates]
        tips_aligned = tips_rates.loc[common_dates]
        
        # Calculate real rates
        real_rates = pd.DataFrame()
        for col in tips_aligned.columns:
            if col in nominal_aligned.columns:
                real_rates[col] = nominal_aligned[col] - tips_aligned[col]
        
        return real_rates

class MarketDataFetcher:
    def __init__(self):
        self.cache_dir = Path("cache")
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "market_data_cache.json"
        self.cache_duration = int(os.getenv('CACHE_DURATION', 3600))
        self.last_fetch_time = None
        self.cached_data = self._load_cache()
        self.proxies = self._load_proxies()
        self.ua = UserAgent()
        self.session = None
        self.api_monitor = APIMonitor()
        self.rate_limiter = RateLimiter()
        
        # Initialize API clients
        self.fred = Fred(api_key=os.getenv('FRED_API_KEY'))
        self.alpha_vantage_key = os.getenv('ALPHA_VANTAGE_KEY')
        self.finnhub_key = os.getenv('FINNHUB_API_KEY')
        self.newsapi_key = os.getenv('NEWSAPI_KEY')
        self.marketaux_key = os.getenv('MARKETAUX_KEY')
        self.tradefilter_key = os.getenv('TRADEFILTER_KEY')
        
        self.symbol_mappings = {
            'SPY': {
                'marketwatch': 'spy',
                'investing': 'spdr-sp-500-etf',
                'tradingview': 'SP:SPY'
            },
            'VIX': {
                'marketwatch': 'vix',
                'investing': 'vix',
                'tradingview': 'CBOE:VIX'
            },
            'DXY': {
                'marketwatch': 'dxy',
                'investing': 'us-dollar-index',
                'tradingview': 'TVC:DXY'
            }
        }

    async def _init_session(self):
        """Initialize aiohttp session if not exists"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def _close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None

    def _load_proxies(self) -> list:
        """Load proxy list from environment or file"""
        proxies = []
        if os.getenv('PROXY_LIST'):
            proxies = os.getenv('PROXY_LIST').split(',')
        return proxies
    
    def _get_random_proxy(self) -> Optional[Dict[str, str]]:
        """Get a random proxy from the list"""
        if not self.proxies:
            return None
        proxy = random.choice(self.proxies)
        return {
            'http': f'http://{proxy}',
            'https': f'https://{proxy}'
        }
    
    def _get_headers(self) -> Dict[str, str]:
        """Get random headers for requests"""
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }

    async def _fetch_from_marketwatch(self, symbol: str) -> Optional[Dict[str, float]]:
        """Fetch data from MarketWatch with enhanced scraping"""
        try:
            await self._init_session()
            symbol_mapping = self.symbol_mappings.get(symbol, {}).get('marketwatch', symbol.lower())
            url = f"https://www.marketwatch.com/investing/stock/{symbol_mapping}"
            
            async with self.session.get(url, headers=self._get_headers(), proxy=self._get_random_proxy()) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'lxml')
                    
                    # Try multiple selectors for price
                    price_element = (
                        soup.find('bg-quote', {'class': 'value'}) or
                        soup.find('span', {'class': 'price'}) or
                        soup.find('div', {'class': 'intraday__price'})
                    )
                    
                    if price_element:
                        current_price = float(price_element.text.strip().replace(',', ''))
                        
                        # Try to get previous close
                        prev_close = None
                        prev_element = (
                            soup.find('td', string='Previous Close') or
                            soup.find('span', string='Previous Close')
                        )
                        if prev_element and prev_element.find_next():
                            prev_close = float(prev_element.find_next().text.strip().replace(',', ''))
                        
                        return {
                            'current': current_price,
                            'previous': prev_close or self.cached_data.get(symbol, {}).get('current', current_price),
                            'timestamp': datetime.now().isoformat(),
                            'source': 'marketwatch'
                        }
            
            self.api_monitor.record_call('marketwatch', False)
        except Exception as e:
            logger.warning(f"Error fetching from MarketWatch: {str(e)}")
            self.api_monitor.record_call('marketwatch', False)
        return None

    async def _fetch_from_investing(self, symbol: str) -> Optional[Dict[str, float]]:
        """Fetch data from Investing.com with enhanced scraping"""
        try:
            await self._init_session()
            symbol_mapping = self.symbol_mappings.get(symbol, {}).get('investing', symbol.lower())
            url = f"https://www.investing.com/equities/{symbol_mapping}"
            
            async with self.session.get(url, headers=self._get_headers(), proxy=self._get_random_proxy()) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'lxml')
                    
                    # Try multiple selectors for price
                    price_element = (
                        soup.find('span', {'data-test': 'instrument-price-last'}) or
                        soup.find('span', {'class': 'last-price'}) or
                        soup.find('div', {'class': 'instrument-price'})
                    )
                    
                    if price_element:
                        current_price = float(price_element.text.strip().replace(',', ''))
                        
                        # Try to get previous close
                        prev_close = None
                        prev_element = (
                            soup.find('td', string='Prev. Close') or
                            soup.find('span', string='Previous Close')
                        )
                        if prev_element and prev_element.find_next():
                            prev_close = float(prev_element.find_next().text.strip().replace(',', ''))
                        
                        return {
                            'current': current_price,
                            'previous': prev_close or self.cached_data.get(symbol, {}).get('current', current_price),
                            'timestamp': datetime.now().isoformat(),
                            'source': 'investing'
                        }
            
            self.api_monitor.record_call('investing', False)
        except Exception as e:
            logger.warning(f"Error fetching from Investing.com: {str(e)}")
            self.api_monitor.record_call('investing', False)
        return None

    async def _fetch_from_yahoo(self, symbol: str) -> Optional[Dict[str, float]]:
        """Fetch data from Yahoo Finance with retry mechanism"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="2d", interval="1d")
                if not hist.empty:
                    return {
                        'current': float(hist['Close'].iloc[-1]),
                        'previous': float(hist['Close'].iloc[0]),
                        'timestamp': datetime.now().isoformat(),
                        'source': 'yahoo'
                    }
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for Yahoo: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        return None

    async def _fetch_from_tradingview(self, symbol: str) -> Optional[Dict[str, float]]:
        """Fetch data from TradingView with enhanced scraping"""
        try:
            await self._init_session()
            symbol_mapping = self.symbol_mappings.get(symbol, {}).get('tradingview', symbol)
            url = f"https://www.tradingview.com/symbols/{symbol_mapping}/"
            
            async with self.session.get(url, headers=self._get_headers(), proxy=self._get_random_proxy()) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'lxml')
                    
                    # Try multiple selectors for price
                    price_element = (
                        soup.find('div', {'class': 'price-value'}) or
                        soup.find('span', {'class': 'tv-symbol-price-quote__value'}) or
                        soup.find('div', {'class': 'tv-symbol-price-quote__value'})
                    )
                    
                    if price_element:
                        current_price = float(price_element.text.strip().replace(',', ''))
                        
                        # Try to get previous close
                        prev_close = None
                        prev_element = (
                            soup.find('div', string='Previous Close') or
                            soup.find('span', string='Previous Close')
                        )
                        if prev_element and prev_element.find_next():
                            prev_close = float(prev_element.find_next().text.strip().replace(',', ''))
                        
                        return {
                            'current': current_price,
                            'previous': prev_close or self.cached_data.get(symbol, {}).get('current', current_price),
                            'timestamp': datetime.now().isoformat(),
                            'source': 'tradingview'
                        }
            
            self.api_monitor.record_call('tradingview', False)
        except Exception as e:
            logger.warning(f"Error fetching from TradingView: {str(e)}")
            self.api_monitor.record_call('tradingview', False)
        return None

    @sleep_and_retry
    @limits(calls=5, period=60)
    async def _fetch_from_alpha_vantage(self, symbol: str) -> Optional[Dict[str, float]]:
        """Fetch data from Alpha Vantage with rate limiting"""
        try:
            await self._init_session()
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={self.alpha_vantage_key}"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'Global Quote' in data:
                        quote = data['Global Quote']
                        return {
                            'current': float(quote['05. price']),
                            'previous': float(quote['08. previous close']),
                            'timestamp': datetime.now().isoformat(),
                            'source': 'alpha_vantage'
                        }
        except Exception as e:
            logger.warning(f"Error fetching from Alpha Vantage: {str(e)}")
        return None

    @sleep_and_retry
    @limits(calls=120, period=60)
    async def _fetch_from_fred(self, series_id: str) -> Optional[Dict[str, float]]:
        """Fetch data from FRED with rate limiting"""
        try:
            data = self.fred.get_series(series_id)
            if not data.empty:
                return {
                    'current': float(data.iloc[-1]),
                    'previous': float(data.iloc[-2]),
                    'timestamp': datetime.now().isoformat(),
                    'source': 'fred'
                }
        except Exception as e:
            logger.warning(f"Error fetching from FRED: {str(e)}")
        return None

    @sleep_and_retry
    @limits(calls=60, period=60)
    async def _fetch_from_finnhub(self, symbol: str) -> Optional[Dict[str, float]]:
        """Fetch data from Finnhub with rate limiting"""
        try:
            await self._init_session()
            url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={self.finnhub_key}"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'current': float(data['c']),
                        'previous': float(data['pc']),
                        'timestamp': datetime.now().isoformat(),
                        'source': 'finnhub'
                    }
        except Exception as e:
            logger.warning(f"Error fetching from Finnhub: {str(e)}")
        return None

    async def _fetch_all_sources(self, symbol: str) -> Optional[Dict[str, float]]:
        """Fetch data from all available sources concurrently"""
        tasks = [
            self._fetch_from_yahoo(symbol),
            self._fetch_from_tradingview(symbol),
            self._fetch_from_marketwatch(symbol),
            self._fetch_from_investing(symbol),
            self._fetch_from_alpha_vantage(symbol),
            self._fetch_from_finnhub(symbol)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid_results = [r for r in results if r is not None and not isinstance(r, Exception)]
        
        if valid_results:
            # Return the result with the most recent timestamp
            return max(valid_results, key=lambda x: x['timestamp'])
        return None

    async def fetch_market_data_async(self) -> Dict[str, Any]:
        """Fetch market data asynchronously with enhanced fallback strategy"""
        if self.cached_data and self.last_fetch_time:
            if time.time() - self.last_fetch_time < self.cache_duration:
                logger.info("Returning cached market data")
                return self.cached_data

        market_data = {}
        symbols = {
            'Treasury': {
                '2Y': '^UST2YR',
                '5Y': '^UST5YR',
                '10Y': '^TNX',
                '30Y': '^TYX'
            },
            'VIX': '^VIX',
            'SPY': 'SPY',
            'Gold': 'GC=F',
            'DXY': 'DX-Y.NYB'
        }

        try:
            await self._init_session()
            
            for category, category_symbols in symbols.items():
                market_data[category] = {}
                
                if isinstance(category_symbols, str):
                    data = await self._fetch_all_sources(category_symbols)
                    if data:
                        market_data[category] = data
                else:
                    tasks = []
                    for name, symbol in category_symbols.items():
                        tasks.append(self._fetch_all_sources(symbol))
                    
                    results = await asyncio.gather(*tasks)
                    for name, data in zip(category_symbols.keys(), results):
                        if data:
                            market_data[category][name] = data
                
                await asyncio.sleep(random.uniform(0.5, 1))

            if market_data:
                self.cached_data = market_data
                self.last_fetch_time = time.time()
                self._save_cache(market_data)
                logger.info("Successfully updated market data cache")
            else:
                logger.warning("Failed to fetch any market data")

        finally:
            await self._close_session()

        return market_data

    def fetch_market_data(self) -> Dict[str, Any]:
        """Synchronous wrapper for async fetch_market_data"""
        return asyncio.run(self.fetch_market_data_async())

    def _save_cache(self, data: Dict[str, Any]):
        """Save data to cache file with atomic write"""
        try:
            cache = {
                'timestamp': time.time(),
                'data': data
            }
            temp_file = self.cache_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(cache, f)
            temp_file.replace(self.cache_file)
            logger.info("Successfully saved market data to cache")
        except Exception as e:
            logger.error(f"Error saving cache: {str(e)}")

    def get_cached_data(self) -> Dict[str, Any]:
        """Get cached market data with timestamp"""
        return {
            'data': self.cached_data,
            'last_updated': datetime.fromtimestamp(self.last_fetch_time).isoformat() if self.last_fetch_time else None
        }

    def get_api_usage_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get API usage statistics"""
        return self.api_monitor.get_usage_stats()

# Create a singleton instance
market_data_fetcher = MarketDataFetcher()

def fetch_market_data() -> Dict[str, Any]:
    """Global function to fetch market data"""
    return market_data_fetcher.fetch_market_data()

def get_api_usage_stats() -> Dict[str, Dict[str, Any]]:
    """Global function to get API usage statistics"""
    return market_data_fetcher.get_api_usage_stats() 