# アプリケーションアーキテクチャ

## モジュール依存関係

```mermaid
flowchart TD
    main[src/main.py] --> scraper[src/scraper/scraper.py]
    main --> sync[src/spreadsheet/sync.py]
    main --> logging_config[src/config/logging_config.py]
    
    scraper --> browser[src/scraper/browser.py]
    scraper --> downloader[src/scraper/downloader.py]
    scraper --> settings[src/config/settings.py]
    scraper --> exceptions[src/exceptions/custom_exceptions.py]
    
    browser --> gmail_client[src/scraper/gmail_client.py]
    browser --> settings
    browser --> exceptions
    
    downloader --> settings
    downloader --> exceptions
    
    gmail_client --> secrets[src/config/secrets.py]
    gmail_client --> exceptions
    
    sync --> settings
    sync --> exceptions
    
    secrets --> exceptions
    
    logging_config --> yaml[yaml]
```

## データフロー

```mermaid
flowchart LR
    subgraph Input
        mf[MoneyForward Website]
        gmail[Gmail API]
    end
    
    subgraph Process
        browser[Browser Manager]
        scraper[Scraper]
        downloader[File Downloader]
        gmail_client[Gmail Client]
    end
    
    subgraph Output
        csv[CSV Files]
        spreadsheet[Google Spreadsheet]
    end
    
    mf --> browser
    browser --> scraper
    scraper --> downloader
    downloader --> csv
    gmail --> gmail_client
    gmail_client --> browser
    csv --> spreadsheet
```

## コンポーネント説明

### メインコンポーネント
- **main.py**: アプリケーションのエントリーポイント。スクレイピング処理と同期処理を制御。
- **scraper.py**: MoneyForwardからのデータ取得を管理。
- **browser.py**: Seleniumを使用したブラウザ操作を制御。
- **downloader.py**: ファイルダウンロードを管理。
- **gmail_client.py**: Gmail APIを使用した2段階認証の処理。

### 設定・ユーティリティ
- **settings.py**: アプリケーション設定の管理。
- **secrets.py**: GCP Secret Managerを使用した機密情報の管理。
- **logging_config.py**: ロギング設定の管理。
- **custom_exceptions.py**: カスタム例外の定義。

### 同期コンポーネント
- **sync.py**: Google Spreadsheetとのデータ同期を管理。
