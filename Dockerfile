FROM python:3.10-slim

# Install system compilation packages for TA-Lib
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Download and compile TA-Lib using an unrestricted raw tarball mirror to clear exit code blocks
RUN curl -L -O https://googleapis.com && \
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
