# GCPセットアップ手順

## 1. プロジェクト作成
1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. 新規プロジェクトを作成
   - プロジェクト名: `moneyforward-etl`
   - 組織: 任意
   - 場所: 任意

## 2. APIの有効化
以下のAPIを有効化:
- Cloud Run API
- Cloud Storage API
- BigQuery API
- Cloud Scheduler API
- Secret Manager API
- Artifact Registry API

## 3. サービスアカウント作成
1. IAM & 管理 > サービスアカウントに移動
2. 新しいサービスアカウントを作成
   ```
   名前: moneyforward-etl-sa
   説明: MoneyForward ETL Pipeline Service Account
   ```
3. 以下のロールを付与:
   - Cloud Run 起動元
   - Storage オブジェクト作成者
   - BigQuery データ編集者
   - Secret Manager シークレットアクセサー

## 4. 環境変数の設定
以下の環境変数をSecret Managerに登録:
```
MF_EMAIL: MoneyForwardのログインメール
MF_PASSWORD: MoneyForwardのログインパスワード
```

## 5. ストレージの作成
1. Cloud Storageバケットの作成
   ```
   名前: mf-raw-data-[YOUR_PROJECT_ID]
   リージョン: asia-northeast1
   保存クラス: Standard
   ```

2. BigQueryデータセットの作成
   ```
   データセットID: moneyforward
   リージョン: asia-northeast1
   ```

## 6. Docker設定
1. Artifact Registryリポジトリの作成:
   ```
   名前: moneyforward-etl
   形式: Docker
   リージョン: asia-northeast1
   ```

## 7. デプロイ用gcloudコマンド
```bash
# Dockerビルド＆プッシュ
docker build -t asia-northeast1-docker.pkg.dev/[PROJECT_ID]/moneyforward-etl/scraper:v1 .
docker push asia-northeast1-docker.pkg.dev/[PROJECT_ID]/moneyforward-etl/scraper:v1

# Cloud Runデプロイ
gcloud run deploy moneyforward-etl \
  --image asia-northeast1-docker.pkg.dev/[PROJECT_ID]/moneyforward-etl/scraper:v1 \
  --region asia-northeast1 \
  --service-account moneyforward-etl-sa \
  --set-secrets=EMAIL=mf-email:latest,PASSWORD=mf-password:latest \
  --memory 2Gi \
  --timeout 1800s \
  --no-cpu-throttling
```

## 8. スケジューラー設定
Cloud Schedulerジョブの作成:
```
名前: moneyforward-etl-daily
説明: Daily MoneyForward ETL Pipeline
頻度: 0 1 * * * (毎日午前1時)
タイムゾーン: Asia/Tokyo
ターゲット: Cloud Run
サービス: moneyforward-etl
