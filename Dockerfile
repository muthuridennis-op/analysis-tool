FROM python:3.10-slim

# Install system compilation packages for TA-Lib
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Download and compile the raw TA-Lib C-library 
RUN wget http://sourceforge.net && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

WORKDIR /app
COPY requirements.txt .

# Install Python modules
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "run_backtest.py"]
