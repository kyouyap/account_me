# MoneyForwardME Plus Readme

## 概要
このプロジェクトは、従来のMoneyForwardMEを使用していた家計簿管理システムを拡張し、同棲や結婚などのライフイベントにより変化した家計状況に適応するためのカスタマイズ版です。

## ディレクトリ構造
プロジェクトの主要なディレクトリ構造は以下の通りです：
- `src/`: メインのコード
  - `main.py`: プロジェクトのエントリーポイント
  - `scraper/`: スクレイピング関連のモジュール
  - `spreadsheet/`: スプレッドシート同期関連のモジュール
  - `exceptions/`: 独自例外定義
  - `config/`: 設定・認証情報・ロギング関連
- `config/`: 設定ファイル（YAML等）
- `test/`: テストコード（config, detail, scraper等のサブディレクトリ含む）
- `outputs/`: 出力データ

## スクリプトの説明
- `src/main.py`:
  - Seleniumを使用してMoneyForwardからデータを取得
  - Googleスプレッドシートと同期
  - ログを活用したエラーハンドリング

## 主な特徴
- 家族カードの支出明細を自動で半分に分け、適切に記帳
- 家賃振込を家賃代として正確に費目計上
- MoneyForward MEの主要機能を維持しつつ、運用コストを最小限に抑える
- DockerとWSLを活用した柔軟な開発環境
- Googleスプレッドシートを使用した直感的なダッシュボードでの可視化

## システム構成
### データ処理システム
- **基盤**: Ubuntu (WSL) 上のDocker
- **サーバー**:
  - Pythonサーバー: 主にデータ処理と管理を担当
  - Seleniumサーバー: MoneyForwardのデータを自動取得するために使用

### ダッシュボードシステム
- **ツール**: Googleスプレッドシート
- **機能**: 取得したデータを基にした視覚的なレポートと分析

## セットアップ手順

---

### セットアップ全体の流れ（概要）

1. 前提条件の準備（WSL/Docker/Terraform/VSCode）
2. GCPプロジェクト作成・API有効化
3. Gmail OAuth認証情報の発行
4. terraform.tfvarsの作成
5. Terraformでクラウドリソース構築
6. Dockerイメージのビルド・起動
7. 初回OAuth認証（src/scraper/gmail_client.pyで自動実行）
8. 定期実行タスクの設定

---

### Step-by-Stepセットアップガイド

#### Step 1: 前提条件の準備

- Windows 10/11 + WSL2（Ubuntu推奨）
- Docker Desktop（WSL2連携有効化）
- Google Cloud SDK（gcloudコマンド）
- Terraform
- VSCode（Remote - WSL拡張推奨）
- GCPアカウント

#### Step 2: GCPプロジェクト作成・API有効化

1. [Google Cloud Console](https://console.cloud.google.com/)で新規プロジェクトを作成
2. 以下のAPIを有効化
   - Secret Manager API
   - Gmail API
   - Google Sheets API
   - BigQuery API
   - Cloud Storage API

#### Step 3: Gmail OAuth認証情報の発行

1. Google Cloud Consoleで「APIとサービス」→「認証情報」→「認証情報を作成」→「OAuthクライアントID」
2. アプリケーションの種類は「デスクトップアプリ」
3. 作成後、JSONファイルをダウンロード
4. 詳細手順は`docs/gmail_api_setup.md`参照

#### Step 4: terraform.tfvarsの作成

`terraform/terraform.tfvars`を以下の例のように作成

```hcl
project_id  = "your-project-id"                # GCPプロジェクトID
region      = "asia-northeast1"                # 利用するGCPリージョン
mf_email    = "your-email@example.com"         # MoneyForwardログイン用メールアドレス
mf_password = "your-password"                  # MoneyForwardログイン用パスワード
spreadsheet_key = "your-spreadsheet-key"       # Googleスプレッドシートのキー
gmail_credentials_file = "./credentials/gmail_oauth_client.json"  # Gmail OAuthクライアント認証情報（手動発行したJSONファイルのパス）
```

- `gmail_credentials_file`には、Step 3でダウンロードしたJSONファイルのパスを指定
- 追加変数が必要な場合は`terraform/variables.tf`も参照

#### Step 5: Terraformでクラウドリソース構築

```sh
cd terraform
terraform init
terraform apply
```

- Secret ManagerやBigQuery、Storageバケット等が自動作成されます

#### Step 6: Dockerイメージのビルド・起動（WSL上で実施）

```sh
docker-compose build
docker-compose up -d
```

- WSL2上でDocker Desktopが連携されていることを確認
- **初回認証は以下のコマンドで一時的なコンテナを起動し、OAuth認証を完了させる**
  ```sh
  docker-compose run --rm app python /app/src/main.py
  ```
  （`--rm`で認証後にコンテナが自動削除されます）

#### Step 7: 初回OAuth認証フロー

- 初回実行時、`src/scraper/gmail_client.py`経由でブラウザ認証が必要
- 認証後、トークンがSecret Managerに保存される
- 以降は自動で認証情報が利用される

#### Step 8: 定期実行タスクの設定

- cron等で定期的に`docker exec`で`python /app/src/main.py`を実行
- 例（WSLのcrontabで12時間ごとに実行）:
  ```
  0 */12 * * * docker exec <container名> python /app/src/main.py
  ```

---

### スプレッドシートの準備

- MoneyForwardの可視化テンプレートを基に、自分用にカスタマイズしたスプレッドシートを作成
  参考用スプレッドシート:
  [https://docs.google.com/spreadsheets/d/1NQOaC2-R-Jfdc0FGjcVpbspu4R5ahDQsXTrKRHe1Arg/edit?gid=0](https://docs.google.com/spreadsheets/d/1NQOaC2-R-Jfdc0FGjcVpbspu4R5ahDQsXTrKRHe1Arg/edit?gid=0)

#### 1. 必要なファイル・記載内容

- `terraform/main.tf` には以下のような内容を記載します（例）:
    - 必要なAPIの有効化（Secret Manager, Gmail, Sheets, BigQuery, Storage等）
    - Spreadsheet用サービスアカウントの作成と鍵のSecret Manager格納
    - MoneyForward認証情報・スプレッドシートキー・Gmail認証情報等のSecret Manager格納
    - BigQueryやStorageバケット等のリソース作成

- `terraform/variables.tf` には各種変数（プロジェクトID、認証情報、リージョン等）を定義します。

- `terraform/terraform.tfvars` で各変数の値を指定します。

##### terraform/terraform.tfvars のセットアップ例

```hcl
project_id  = "your-project-id"                # GCPプロジェクトID
region      = "asia-northeast1"                # 利用するGCPリージョン
mf_email    = "your-email@example.com"         # MoneyForwardログイン用メールアドレス
mf_password = "your-password"                  # MoneyForwardログイン用パスワード
spreadsheet_key = "your-spreadsheet-key"       # Googleスプレッドシートのキー
gmail_credentials_file = "./credentials/gmail_oauth_client.json"  # Gmail OAuthクライアント認証情報（Google Cloud Consoleで手動発行したJSONファイルのパス）
```

- `gmail_credentials_file`には、docs/gmail_api_setup.mdの手順でダウンロードしたJSONファイルのパスを指定してください。
- 追加で必要な変数がある場合は、`terraform/variables.tf`を参照してください。

#### 2. クラウドインフラの立ち上げ手順

1. GCPプロジェクトを作成し、サービスアカウントに必要な権限を付与
2. `terraform` ディレクトリで以下を実行
    ```sh
    cd terraform
    terraform init
    terraform apply
    ```
3. 実行後、Secret ManagerやBigQuery、Storageバケット等が自動で作成されます

#### 3. Gmail認証情報の登録

- Gmail API用OAuth認証情報のみ手動発行が必要です。手順は`docs/gmail_api_setup.md`を参照し、`terraform.tfvars`にJSONを貼り付けてください。

#### 4. 補足

- 認証情報やアプリケーション設定は、Secret Managerからアプリケーションが自動取得します。.envやconfig/settings.yamlでファイルパスを指定する必要はありません。
- Spreadsheet用サービスアカウントと認証情報は**Terraformで自動生成・Secret Managerに格納**されるため、手動作成は不要です。

---

### 実装とテスト
1. Seleniumを利用したMoneyForwardからのデータ取得処理を実装
2. Pythonスクリプトでスプレッドシートの更新処理を実装
3. ローカル環境での手動テストを行い、動作確認

### 定期実行の設定
- Cronジョブ等で、定期的にデータ取得からスプレッドシートの更新までを自動化できます。
- `docker-compose up -d`でコンテナを起動し、必要に応じて`docker exec`で`python /app/src/main.py`を実行してください。

## ダッシュボードの利用
- Googleスプレッドシートに集約されたデータを基に、家計の現状や傾向を視覚的に分析
- スマートフォンからもアクセス可能で、いつでも家計状況をチェックできる

## 今後の展望
- 定期実行の安定性向上とエラーハンドリングの強化
- ダッシュボードの機能拡張とカスタマイズオプションの追加
- ユーザーフィードバックを基にした機能改善と最適化

## 設定ファイル(config/settings.yaml)の編集について
このプロジェクトの設定ファイル(config/settings.yaml)は、プロジェクト全体の各種設定が記述されていますが、以下の項目は特にユーザーの環境に合わせて変更が必要です：

- **special_rules**:
  - 例：`アメリカン・エキスプレスカード` の設定により、取引金額を半分に分割する処理（`divide_amount` と `value: 2`）が定義されています。必要に応じて変更してください。

- **spreadsheet**:
  - ワークシート名（例：`@家計簿データ 貼付` や `@資産推移 貼付`）、開始行、各列の定義は、利用するスプレッドシートの構成に合わせて編集が必要です。

- **paths**:
  - 出力先ディレクトリ、ダウンロードディレクトリ等は、実際のシステム構成に合わせて確認・変更してください。
  - 認証情報ファイルのパス指定は不要です（Secret Managerから自動取得）。
