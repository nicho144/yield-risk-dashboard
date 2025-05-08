import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yfinance as yf
import plotly.graph_objects as go

# Set page config
st.set_page_config(
    page_title="Market Dashboard",
    page_icon="📊",
    layout="wide"
)

# Title
st.title("Market Dashboard")

# Define date variables
TODAY = datetime.now()
YESTERDAY = TODAY - timedelta(days=1)

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
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=YESTERDAY, end=TODAY)
            if not hist.empty:
                data[tenor] = {
                    'current': hist['Close'].iloc[-1],
                    'previous': hist['Close'].iloc[0]
                }
        
        return data if data else None
    except Exception as e:
        st.error(f"Error fetching treasury data: {str(e)}")
        return None

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
with st.spinner('Fetching market data...'):
    # Fetch data
    treasury_data = fetch_treasury_data()
    vix_data = fetch_vix_data()
    
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
        st.plotly_chart(create_yield_curve_plot(treasury_data), use_container_width=True)
    
    # Add refresh button
    if st.button('Refresh Data'):
        st.experimental_rerun() 