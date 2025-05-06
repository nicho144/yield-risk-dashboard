import pandas as pd
import yfinance as yf
from fredapi import Fred
import requests
from typing import Dict, Optional, Tuple
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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