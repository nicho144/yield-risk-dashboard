# Yield Risk Dashboard

A Python-based dashboard for analyzing yield curve risk and market conditions.

## Features

- Real-time yield curve analysis
- Risk assessment based on multiple factors
- Market data monitoring
- Real rates calculation
- Implied rates from Fed Funds futures

## Setup

1. Install Python 3.8 or higher

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
   - Create a `.env` file in the project root
   - Add your FRED API key:
     ```
     FRED_API_KEY=your_fred_api_key_here
     ```
   - Get your FRED API key from: https://fred.stlouisfed.org/docs/api/api_key.html

4. Run the dashboard:
```bash
streamlit run app.py
```

## Project Structure

- `app.py`: Main Streamlit application
- `data_fetcher.py`: Data fetching and processing
- `risk_calculations.py`: Risk assessment calculations
- `requirements.txt`: Python dependencies

## Data Sources

- FRED (Federal Reserve Economic Data)
- Yahoo Finance
- Market Data APIs

## Development

To contribute to this project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License
