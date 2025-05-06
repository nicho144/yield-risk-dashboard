import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import requests
import json

from data_fetcher import DataFetcher
from risk_calculations import RiskCalculator

# Load environment variables
load_dotenv()

# Initialize components
data_fetcher = DataFetcher()
risk_calculator = RiskCalculator()

# Set page config
st.set_page_config(
    page_title="Market Risk Dashboard",
    page_icon="📊",
    layout="wide"
)

# Initialize session state
if 'yield_data' not in st.session_state:
    st.session_state.yield_data = {
        '2Y': 0.0,
        '5Y': 0.0,
        '10Y': 0.0,
        '30Y': 0.0,
        'corporate': 0.0,
        'high_yield_spread': 0.0
    }

# Title and description
st.title("Market Risk Dashboard")
st.markdown("""
This dashboard provides real-time analysis of market risk indicators, including:
- Yield curve analysis
- Risk assessment metrics
- Pre-market indicators
- Market trend analysis
""")

# Create two columns for the layout
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Yield Curve Analysis")
    
    # Yield inputs
    st.write("Current Yields")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.session_state.yield_data['2Y'] = st.number_input("2Y Treasury", value=st.session_state.yield_data['2Y'], format="%.2f")
    with col2:
        st.session_state.yield_data['5Y'] = st.number_input("5Y Treasury", value=st.session_state.yield_data['5Y'], format="%.2f")
    with col3:
        st.session_state.yield_data['10Y'] = st.number_input("10Y Treasury", value=st.session_state.yield_data['10Y'], format="%.2f")
    with col4:
        st.session_state.yield_data['30Y'] = st.number_input("30Y Treasury", value=st.session_state.yield_data['30Y'], format="%.2f")

    # Corporate and High Yield inputs
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.yield_data['corporate'] = st.number_input("Corporate Yield", value=st.session_state.yield_data['corporate'], format="%.2f")
    with col2:
        st.session_state.yield_data['high_yield_spread'] = st.number_input("High Yield Spread", value=st.session_state.yield_data['high_yield_spread'], format="%.2f")

    # Calculate metrics
    def calculate_metrics():
        # Calculate 2s10s spread
        spread_2s10s = st.session_state.yield_data['10Y'] - st.session_state.yield_data['2Y']
        
        # Calculate real rates (assuming 2% inflation for demo)
        real_rates = {
            '2Y': st.session_state.yield_data['2Y'] - 2.0,
            '5Y': st.session_state.yield_data['5Y'] - 2.0,
            '10Y': st.session_state.yield_data['10Y'] - 2.0,
            '30Y': st.session_state.yield_data['30Y'] - 2.0
        }
        
        # Determine risk status
        risk_score = 0
        if spread_2s10s < 0:
            risk_score += 2  # Inverted yield curve
        elif spread_2s10s < 0.5:
            risk_score += 1  # Flat yield curve
            
        if st.session_state.yield_data['high_yield_spread'] > 5:
            risk_score += 2  # High yield spread indicates risk
        elif st.session_state.yield_data['high_yield_spread'] > 3:
            risk_score += 1
            
        risk_status = "Risk Off" if risk_score >= 3 else "Risk On" if risk_score <= 1 else "Neutral"
        
        return {
            'spread_2s10s': spread_2s10s,
            'real_rates': real_rates,
            'risk_score': risk_score,
            'risk_status': risk_status
        }

    # Display metrics
    metrics = calculate_metrics()
    
    # Create yield curve plot
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=['2Y', '5Y', '10Y', '30Y'],
        y=[st.session_state.yield_data['2Y'], 
           st.session_state.yield_data['5Y'],
           st.session_state.yield_data['10Y'],
           st.session_state.yield_data['30Y']],
        mode='lines+markers',
        name='Yield Curve'
    ))
    
    fig.update_layout(
        title='Treasury Yield Curve',
        xaxis_title='Maturity',
        yaxis_title='Yield (%)',
        showlegend=True
    )
    
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Risk Assessment")
    
    # Display risk metrics
    st.metric("2s10s Spread", f"{metrics['spread_2s10s']:.2f}%")
    st.metric("Risk Score", f"{metrics['risk_score']}/4")
    
    # Risk status with color
    risk_color = "red" if metrics['risk_status'] == "Risk Off" else "green" if metrics['risk_status'] == "Risk On" else "orange"
    st.markdown(f"### Risk Status: <span style='color:{risk_color}'>{metrics['risk_status']}</span>", unsafe_allow_html=True)
    
    # Real rates
    st.subheader("Real Rates")
    for maturity, rate in metrics['real_rates'].items():
        st.metric(f"{maturity} Real Rate", f"{rate:.2f}%")

# Pre-market section
st.subheader("Pre-Market Indicators")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Gold Futures", "2,345.67", "+1.2%")
with col2:
    st.metric("10Y Treasury Futures", "98.45", "-0.3%")
with col3:
    st.metric("Dollar Index", "104.32", "+0.1%")

# Add refresh button
if st.button("Refresh Data"):
    st.experimental_rerun() 