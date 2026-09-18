FROM python:3.10-slim

WORKDIR /app

# Install standard system requirements
COPY requirements.txt .

# Install Python modules directly from your updated requirements file
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "run_backtest.py"]
