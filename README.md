# Enhanced Market Dashboard

A comprehensive financial market dashboard built with Streamlit that provides real-time market data, analysis, and visualization.

## Features

- Real-time market data from multiple sources
- Treasury yield curve analysis
- VIX and volatility analysis
- Gold term structure analysis
- Market sentiment analysis
- Data quality metrics
- Interactive visualizations

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd <repository-name>
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up API keys in Streamlit secrets:
Create a `.streamlit/secrets.toml` file with the following structure:
```toml
ALPHA_VANTAGE_KEY = "your_alpha_vantage_key"
FRED_API_KEY = "your_fred_api_key"
FINNHUB_KEY = "your_finnhub_key"
NEWSAPI_KEY = "your_newsapi_key"
MARKETAUX_KEY = "your_marketaux_key"
```

4. Run the application:
```bash
streamlit run streamlite_financial_improved.py
```

## API Keys Required

- Alpha Vantage: For market data
- FRED: For economic indicators
- Finnhub: For market sentiment
- NewsAPI: For financial news
- Marketaux: For additional market data

## Error Handling

The application includes comprehensive error handling for:
- API failures
- Data validation
- Rate limiting
- Network issues
- Data quality issues

## Data Refresh

- Market data refreshes every 5 minutes
- News data refreshes every 30 minutes
- Sentiment data refreshes every hour

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Local Development

1. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements3.txt
```

3. Run the dashboard:
```bash
streamlit run streamlite_financial_improved.py
```

## Deployment

### Local Deployment
Use the provided scripts:
- Original version: `./run_background.sh` (port 8502)
- Improved version: `./run_improved.sh` (port 8503)

### Streamlit Cloud Deployment
1. Push your code to GitHub
2. Sign up for Streamlit Cloud (https://streamlit.io/cloud)
3. Connect your GitHub repository
4. Deploy the `streamlite_financial_improved.py` file

## Data Sources
- Treasury yields and TIPS: Yahoo Finance
- Futures data: Yahoo Finance
- Market indicators: Yahoo Finance

## Notes
- The dashboard uses a robust data fetching system with retries and rate limiting
- Data is cached for 5 minutes to prevent excessive API calls
- Critical data (Treasury, VIX) is required for the dashboard to function
