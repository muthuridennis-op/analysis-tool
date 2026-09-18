# Use a pre-packaged, ultra-fast micromamba (conda) image
FROM mambaorg/micromamba:1.5-alpine

USER root
RUN apk add --no-cache bash

WORKDIR /app

# Install TA-Lib pre-compiled binaries along with base dependencies from Conda Forge
RUN micromamba install -y -n base -c conda-forge \
    python=3.10 \
    ta-lib \
    yfinance \
    pandas \
    numpy=1.26.4 \
    scipy \
    supabase \
    requests \
    && micromamba clean --all --yes

# Set up the environmental path cleanly using standard modern unquoted syntax
ENV PATH=/opt/conda/bin:$PATH

COPY . .

# --- FIXED STEP: Force Python to install the remaining requirements including python-dotenv ---
RUN micromamba run -n base pip install --no-cache-dir -r requirements.txt

# Run the app using micromamba's environmental shell execution layer
CMD ["micromamba", "run", "-n", "base", "python", "run_backtest.py"]
