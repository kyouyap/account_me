ARG UV_VERSION=latest

FROM ghcr.io/astral-sh/uv:$UV_VERSION AS uv

FROM python:3.13-slim-bullseye


# 環境変数の設定
ENV EMAIL=${EMAIL}
ENV PASSWORD=${PASSWORD}
ENV SPREADSHEET_KEY=${SPREADSHEET_KEY}
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV CHROME_DRIVER_PATH=/usr/bin/chromedriver
ENV CHROME_PATH=/usr/bin/chromium

# ベース依存関係のインストール
RUN apt-get update && apt-get install -y \
    wget=1.21-1+deb11u1 \
    gnupg=2.2.27-2+deb11u2 \
    apt-transport-https ca-certificates \
    xvfb=2:1.20.11-1+deb11u15 \
    libgconf-2-4=3.2.6-7 \
    libnss3=2:3.61-1+deb11u4 \
    libxss1=1:1.2.3-1 \
    libasound2=1.2.4-1.1 \
    fonts-ipafont-gothic=00303-21 \
    fonts-ipafont-mincho=00303-21 \
    git=1:2.30.2-1+deb11u4 \
    && rm -rf /var/lib/apt/lists/*

# Google Cloud SDKインストール
RUN apt-get update && apt-get install -y curl && \
    echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" > /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor | tee /usr/share/keyrings/cloud.google.gpg > /dev/null && \
    apt-get update && \
    apt-get install -y google-cloud-sdk && \
    rm -rf /var/lib/apt/lists/*

# ChromiumとChromeDriverのインストール
# hadolint ignore=DL3008,DL3009,DL3015,DL4006
SHELL ["/bin/bash", "-c"]
RUN apt-get update && \
    apt-get install -y chromium=120.0.6099.224-1~deb11u1 chromium-driver=120.0.6099.224-1~deb11u1; 

# 最初に作業ディレクトリを設定
WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT='/usr/local/'
ENV UV_SYSTEM_PYTHON=1

# 依存関係のインストール用にtemporaryで/optに移動
WORKDIR /opt
COPY --from=uv /uv /bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync

# 作業ディレクトリを/appに戻す
WORKDIR /app

# 出力ディレクトリの作成
RUN mkdir -p /app/downloads \
    && mkdir -p /app/outputs/aggregated_files/detail \
    && mkdir -p /app/outputs/aggregated_files/assets \
    && mkdir -p /app/log \
    && chmod -R 777 /app/downloads \
    && chmod -R 777 /app/outputs \
    && chmod -R 777 /app/log

# Pythonパスの設定
ENV PYTHONPATH=/app/src
