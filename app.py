import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

from data_fetcher import DataFetcher
from risk_calculations import RiskCalculator

# Load environment variables
load_dotenv()

# Initialize components
data_fetcher = DataFetcher()
risk_calculator = RiskCalculator()

# Page config
st.set_page_config(
    page_title="Yield Risk Dashboard",
    page_icon="📈",
    layout="wide"
)

# Title
st.title("Yield Risk Dashboard")

# Sidebar for controls
st.sidebar.header("Controls")

# Main dashboard layout
def main():
    # Fetch all data
    data = data_fetcher.get_all_data()
    
    if data['yield_curve'] is not None:
        # Calculate real rates
        real_rates = data_fetcher.calculate_real_rates(
            data['yield_curve'],
            data['tips_curve']
        )
        
        # Analyze yield curve
        curve_analysis = risk_calculator.analyze_yield_curve(data['yield_curve'])
        
        # Calculate risk score
        risk_score = risk_calculator.calculate_risk_score(
            data['yield_curve'],
            data['market_data']['vix'] if data['market_data'] else None,
            real_rates['10Y'] if real_rates is not None else None,
            data['fed_funds']['1M'] if data['fed_funds'] is not None else None
        )
        
        # Determine risk status
        risk_status = risk_calculator.determine_risk_status(risk_score, curve_analysis)
        
        # Display risk metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Risk Score",
                f"{risk_score:.1f}",
                delta=f"{curve_analysis['spread_change']:.2f}%"
            )
        
        with col2:
            st.metric(
                "2s10s Spread",
                f"{curve_analysis['current_spread']:.2f}%",
                delta=f"{curve_analysis['spread_change']:.2f}%"
            )
        
        with col3:
            st.metric(
                "Curve Status",
                f"{curve_analysis['shape']} ({curve_analysis['movement']})"
            )
        
        # Plot yield curve
        st.subheader("Yield Curve")
        fig = go.Figure()
        
        # Add current yield curve
        fig.add_trace(go.Scatter(
            x=['2Y', '5Y', '10Y', '30Y'],
            y=curve_analysis['latest_yields'],
            name='Current',
            line=dict(color='blue')
        ))
        
        # Add previous yield curve
        fig.add_trace(go.Scatter(
            x=['2Y', '5Y', '10Y', '30Y'],
            y=curve_analysis['previous_yields'],
            name='Previous',
            line=dict(color='gray', dash='dash')
        ))
        
        fig.update_layout(
            title="Treasury Yield Curve",
            xaxis_title="Maturity",
            yaxis_title="Yield (%)",
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Display market data
        if data['market_data']:
            st.subheader("Market Data")
            market_col1, market_col2, market_col3, market_col4 = st.columns(4)
            
            with market_col1:
                st.metric(
                    "VIX",
                    f"{data['market_data']['vix']:.2f}"
                )
            
            with market_col2:
                spy_change = ((data['market_data']['spy_current'] - data['market_data']['spy_previous']) 
                            / data['market_data']['spy_previous'] * 100)
                st.metric(
                    "S&P 500",
                    f"{data['market_data']['spy_current']:.2f}",
                    delta=f"{spy_change:.2f}%"
                )
            
            with market_col3:
                st.metric(
                    "Gold",
                    f"{data['market_data']['gold']:.2f}"
                )
            
            with market_col4:
                st.metric(
                    "Dollar Index",
                    f"{data['market_data']['dxy']:.2f}"
                )
        
        # Display real rates if available
        if real_rates is not None:
            st.subheader("Real Rates")
            real_rates_df = pd.DataFrame({
                'Maturity': ['5Y', '10Y', '30Y'],
                'Real Rate': [real_rates['5Y'].iloc[-1], real_rates['10Y'].iloc[-1], real_rates['30Y'].iloc[-1]]
            })
            st.dataframe(real_rates_df, use_container_width=True)
        
        # Display detailed metrics
        st.subheader("Detailed Metrics")
        metrics_df = pd.DataFrame({
            'Metric': ['2Y Yield', '5Y Yield', '10Y Yield', '30Y Yield'],
            'Current': curve_analysis['latest_yields'],
            'Previous': curve_analysis['previous_yields'],
            'Change': curve_analysis['latest_yields'] - curve_analysis['previous_yields']
        })
        
        st.dataframe(metrics_df, use_container_width=True)
        
        # Display risk assessment
        st.subheader("Risk Assessment")
        risk_col1, risk_col2 = st.columns(2)
        
        with risk_col1:
            st.write("Overall Risk Status:", risk_status)
            st.write("Yield Curve Shape:", curve_analysis['shape'])
            st.write("Curve Movement:", curve_analysis['movement'])
        
        with risk_col2:
            if data['market_data']:
                st.write("Market Volatility (VIX):", f"{data['market_data']['vix']:.2f}")
            if real_rates is not None:
                st.write("Average Real Rate:", f"{real_rates.mean().mean():.2f}%")
            if data['fed_funds'] is not None:
                st.write("Implied Fed Funds Rate:", f"{data['fed_funds']['1M'].iloc[-1]:.2f}%")

if __name__ == "__main__":
    main() 