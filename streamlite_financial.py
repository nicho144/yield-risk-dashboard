import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf
import plotly.graph_objects as go
import time

# Set page config
st.set_page_config(
    page_title="Pre-Market Dashboard",
    page_icon="📊",
    layout="wide"
)

# Title
st.title("Pre-Market Dashboard")

# Define date variables
TODAY = datetime.now()
YESTERDAY = TODAY - timedelta(days=1)

def is_market_open():
    """Check if US market is open"""
    now = datetime.now()
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close

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
        retry_delay = 1  # seconds
        
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
                                'current': hist['Close'].iloc[-1],
                                'previous': hist['Close'].iloc[0]
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
                                'current': hist['Close'].iloc[-1],
                                'previous': hist['Close'].iloc[0]
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

def create_yield_curve_plot(treasury_data):
    """Create yield curve visualization"""
    if not treasury_data:
        return None
        
    fig = go.Figure()
    
    # Plot current yield curve
    tenors = ['2Y', '5Y', '10Y', '30Y']
    current_rates = [treasury_data[t]['current'] for t in tenors]
    previous_rates = [treasury_data[t]['previous'] for t in tenors]
    
    fig.add_trace(go.Scatter(
        x=tenors,
        y=current_rates,
        mode='lines+markers',
        name='Current',
        line=dict(color='blue', width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=tenors,
        y=previous_rates,
        mode='lines+markers',
        name='Previous',
        line=dict(color='red', width=2, dash='dash')
    ))
    
    # Calculate curve changes
    spread_change = (treasury_data['10Y']['current'] - treasury_data['2Y']['current']) - \
                   (treasury_data['10Y']['previous'] - treasury_data['2Y']['previous'])
    
    fig.update_layout(
        title=f'Yield Curve Analysis (2s10s Spread Change: {spread_change:.2f}%)',
        xaxis_title='Tenor',
        yaxis_title='Yield (%)',
        showlegend=True,
        hovermode='x unified'
    )
    
    return fig

# Main dashboard
with st.spinner('Fetching pre-market data...'):
    # Fetch data
    market_data = fetch_market_data()
    
    if market_data:
        # Display market status
        st.subheader(f"Market Status: {'Open' if is_market_open() else 'Pre-Market'}")
        
        # Display market sentiment
        sentiment = determine_market_sentiment(market_data)
        st.subheader(f"Market Sentiment: {sentiment}")
        
        # Display metrics in columns
        col1, col2, col3, col4 = st.columns(4)
        
        # Treasury metrics
        if 'Treasury' in market_data:
            with col1:
                st.subheader("Treasury Yields")
                for tenor, data in market_data['Treasury'].items():
                    st.metric(
                        f"{tenor} Yield",
                        f"{data['current']:.2f}%",
                        f"{data['current'] - data['previous']:.2f}%"
                    )
        
        # Real rates
        real_rates = calculate_real_rates(market_data)
        if real_rates:
            with col2:
                st.subheader("Real Interest Rates")
                for tenor, rates in real_rates.items():
                    st.metric(
                        f"{tenor} Real Rate",
                        f"{rates['current']:.2f}%",
                        f"{rates['current'] - rates['previous']:.2f}%"
                    )
        
        # Fed Funds
        if 'Fed_Funds' in market_data:
            with col3:
                st.subheader("Fed Funds")
                for name, data in market_data['Fed_Funds'].items():
                    st.metric(
                        name.replace('_', ' '),
                        f"{data['current']:.2f}%",
                        f"{data['current'] - data['previous']:.2f}%"
                    )
        
        # VIX and Commodities
        if 'VIX' in market_data or 'Commodities' in market_data:
            with col4:
                if 'VIX' in market_data:
                    st.metric(
                        "VIX",
                        f"{market_data['VIX']['current']:.2f}",
                        f"{market_data['VIX']['current'] - market_data['VIX']['previous']:.2f}"
                    )
                if 'Commodities' in market_data:
                    st.subheader("Commodities")
                    for name, data in market_data['Commodities'].items():
                        st.metric(
                            name,
                            f"{data['current']:.2f}",
                            f"{data['current'] - data['previous']:.2f}"
                        )
        
        # Display yield curve plot
        if 'Treasury' in market_data:
            st.plotly_chart(create_yield_curve_plot(market_data['Treasury']), use_container_width=True)
    
    # Add refresh button
    if st.button('Refresh Data'):
        st.rerun() 