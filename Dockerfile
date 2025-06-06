FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Create .streamlit directory
RUN mkdir -p .streamlit

# Expose the port
EXPOSE 8501

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["streamlit", "run", "streamlite_financial_improved.py", "--server.port=8501", "--server.address=0.0.0.0"] 