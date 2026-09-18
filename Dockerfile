# Use a pre-packaged, ultra-fast micromamba (conda) image
FROM mambaorg/micromamba:1.5-alpine

USER root
RUN apk add --no-cache bash

WORKDIR /app

# Install TA-Lib pre-compiled binaries along with Python dependencies directly from Conda Forge
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

# Set up the environmental path so the system locates python instantly
ENV PATH= "/opt/conda/bin:$PATH"

COPY . .

# Run the app using micromamba's environmental shell execution layer
CMD ["micromamba", "run", "-n", "base", "python", "run_backtest.py"]
