FROM --platform=linux/amd64 python:3.11-slim-bullseye

# 環境変数の設定
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV CHROME_DRIVER_PATH=/usr/bin/chromedriver
ENV CHROME_PATH=/usr/bin/chromium

# ベース依存関係のインストール
# hadolint ignore=DL3008,DL3015
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    xvfb \
    libgconf-2-4 \
    libnss3 \
    libxss1 \
    libasound2 \
    fonts-ipafont-gothic \
    fonts-ipafont-mincho \
    && rm -rf /var/lib/apt/lists/*

# ChromiumとChromeDriverのインストール
# hadolint ignore=DL3008,DL3009,DL3015,DL4006
SHELL ["/bin/bash", "-c"]
RUN apt-get update && \
    apt-get install -y chromium chromium-driver; 

# 作業ディレクトリの設定
WORKDIR /app

# アプリケーションコードのコピー
COPY . /app

# コンテナ内の仮想環境のパスを設定
ENV UV_PROJECT_ENVIRONMENT='/app/.venv'

# uvのインストール
# hadolint ignore=DL3013
RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -U uv \
    && mkdir -p /app/.venv  # 仮想環境ディレクトリを作成

# Pythonパッケージのインストール
RUN uv sync

# 出力ディレクトリの作成
RUN mkdir -p /app/downloads \
    && mkdir -p /app/outputs/aggregated_files/detail \
    && mkdir -p /app/outputs/aggregated_files/assets \
    && mkdir -p /app/log

# Pythonパスの設定
ENV PYTHONPATH=/app/src

# エントリーポイントの設定（FastAPIアプリケーションの起動）
ENV PORT=8080
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
