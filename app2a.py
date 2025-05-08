import streamlit as st

# Check required packages
required_packages = {
    'pandas': '2.2.1',
    'plotly': '5.13.1',
    'yfinance': '0.2.28'
}

missing_packages = []
for package, version in required_packages.items():
    try:
        __import__(package)
    except ImportError:
        missing_packages.append(f"{package}=={version}")

if missing_packages:
    st.error(f"Missing required packages. Please install: {', '.join(missing_packages)}")
    st.stop()

import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf

# Try to import plotly, but don't fail if it's not available
try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.error("Plotly is not installed. Please check your requirements.txt and make sure plotly is properly installed.")
    st.stop()

# Set page config
st.set_page_config(
    page_title="Market Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize session state
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()

# Title
st.title("Market Dashboard")

# Define date variables
TODAY = datetime.now()
YESTERDAY = TODAY - timedelta(days=1)

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_treasury_data():
    """Fetch treasury data from Yahoo Finance"""
    try:
        symbols = {
            '2Y': '^UST2YR',
            '5Y': '^UST5YR',
            '10Y': '^TNX',
            '30Y': '^TYX'
        }
        
        data = {}
        for tenor, symbol in symbols.items():
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(start=YESTERDAY, end=TODAY)
                if not hist.empty:
                    data[tenor] = {
                        'current': hist['Close'].iloc[-1],
                        'previous': hist['Close'].iloc[0]
                    }
            except Exception as e:
                st.warning(f"Error fetching {tenor} data: {str(e)}")
                continue
        
        return data if data else None
    except Exception as e:
        st.error(f"Error fetching treasury data: {str(e)}")
        return None

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_vix_data():
    """Fetch VIX data"""
    try:
        vix = yf.Ticker("^VIX")
        hist = vix.history(start=YESTERDAY, end=TODAY)
        if not hist.empty:
            return {
                'current': hist['Close'].iloc[-1],
                'previous': hist['Close'].iloc[0]
            }
        return None
    except Exception as e:
        st.error(f"Error fetching VIX data: {str(e)}")
        return None

def create_yield_curve_plot(treasury_data):
    """Create yield curve visualization"""
    if not PLOTLY_AVAILABLE:
        st.error("Cannot create yield curve plot because plotly is not installed")
        return None
    
    if not treasury_data:
        return None
    
    try:
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
            hovermode='x unified',
            template='plotly_white'
        )
        
        return fig
    except Exception as e:
        st.error(f"Error creating yield curve plot: {str(e)}")
        return None

# Main dashboard
try:
    with st.spinner('Fetching market data...'):
        # Fetch data
        treasury_data = fetch_treasury_data()
        vix_data = fetch_vix_data()
        
        # Display last refresh time
        st.caption(f"Last updated: {st.session_state.last_refresh.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        
        if treasury_data:
            with col1:
                st.metric(
                    "2Y Yield",
                    f"{treasury_data['2Y']['current']:.2f}%",
                    f"{treasury_data['2Y']['current'] - treasury_data['2Y']['previous']:.2f}%"
                )
            with col2:
                st.metric(
                    "10Y Yield",
                    f"{treasury_data['10Y']['current']:.2f}%",
                    f"{treasury_data['10Y']['current'] - treasury_data['10Y']['previous']:.2f}%"
                )
            with col3:
                spread = treasury_data['10Y']['current'] - treasury_data['2Y']['current']
                prev_spread = treasury_data['10Y']['previous'] - treasury_data['2Y']['previous']
                st.metric(
                    "2s10s Spread",
                    f"{spread:.2f}%",
                    f"{spread - prev_spread:.2f}%"
                )
        
        if vix_data:
            with col4:
                st.metric(
                    "VIX",
                    f"{vix_data['current']:.2f}",
                    f"{vix_data['current'] - vix_data['previous']:.2f}"
                )
        
        # Display yield curve plot
        if treasury_data:
            fig = create_yield_curve_plot(treasury_data)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        
        # Add refresh button
        if st.button('Refresh Data'):
            st.session_state.last_refresh = datetime.now()
            st.rerun()

except Exception as e:
    st.error(f"An error occurred: {str(e)}")
    st.error("Please try refreshing the page or contact support if the issue persists.") 