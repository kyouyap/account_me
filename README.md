# MoneyForwardME Plus Readme

## 概要
このプロジェクトは、従来のMoneyForwardMEを使用していた家計簿管理システムを拡張し、同棲や結婚などのライフイベントにより変化した家計状況に適応するためのカスタマイズ版です。

## ディレクトリ構造
プロジェクトの主要なディレクトリ構造は以下の通りです：
- `src/`: メインのコード
  - `main.py`: プロジェクトのエントリーポイント
  - `scraper/`: スクレイピング関連のモジュール
  - `spreadsheet/`: スプレッドシート同期関連のモジュール
- `config/`: 設定ファイル
- `test/`: テストコード
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

### WSLとDockerのセットアップ
1. Windows上でWSLを有効化し、Ubuntuをインストール
2. WSL上にDockerをインストールし、必要な設定を行う

### プロジェクト構成の準備
1. 開発環境としてVSCodeのdevcontainer機能を利用し、プロジェクトのベースを作成
2. 必要なディレクトリ構造を設定し、DockerのComposeファイルを作成

### 環境変数の準備
1. `src` 配下に `.env` ファイルを作成し、以下のような内容で環境変数を設定
    ```env
    EMAIL="example@gmail.com"
    PASSWORD="example"
    SPREADSHEET_KEY="hogehoge"
    ```
2. GCPの認証キーのパスも設定ファイル（例：`config/settings.yaml`）や環境変数に記述する

### スプレッドシートの準備
- MoneyForwardの可視化テンプレートを基に、自分用にカスタマイズしたスプレッドシートを作成
  参考用スプレッドシート:
  [https://docs.google.com/spreadsheets/d/1NQOaC2-R-Jfdc0FGjcVpbspu4R5ahDQsXTrKRHe1Arg/edit?gid=0](https://docs.google.com/spreadsheets/d/1NQOaC2-R-Jfdc0FGjcVpbspu4R5ahDQsXTrKRHe1Arg/edit?gid=0)

### GCP認証情報の自動生成・管理手順（Terraformベース最新構成）

このプロジェクトでは、Google Sheets用・Gmail用で用途ごとにサービスアカウントを分けて作成し、それぞれの認証情報（JSON鍵）はTerraformで自動生成・Google Secret Managerに安全に格納します。手動でJSONファイルをダウンロード・配置する必要はありません。

#### 1. 必要なAPIの有効化
- Google Cloud Consoleでプロジェクトを選択し、以下のAPIを有効化してください：
  - Google Sheets API
  - Gmail API
  - Secret Manager API
  - BigQuery API
  - Cloud Storage API

#### 2. 認証情報の準備・管理方針
- **Spreadsheet用**：サービスアカウントをTerraformで自動生成し、その鍵情報（JSON）をSecret Managerに自動格納します。
- **Gmail用**：OAuthクライアントID/シークレット（ユーザー認可型認証情報）はGoogle Cloud Consoleから手動で発行し、そのJSONをTerraformでSecret Managerに格納します。
  - ※GmailのOAuthクライアントID/シークレットは現状Terraform等での自動発行はできません。Google Cloud Consoleの「認証情報」画面から手動で取得してください。

#### 3. デプロイ手順
1. 必要な変数（特に `gmail_credentials_file` には手動発行したOAuthクライアントJSONのパス）を `terraform/terraform.tfvars` で設定
2. 以下のコマンドでTerraformを実行し、インフラと認証情報を構築します：
   ```sh
   cd terraform
   terraform init
   terraform apply
   ```
3. 実行後、Google Secret Managerに以下のようなシークレットが作成されます：
   - `spreadsheet-credential` : Spreadsheet用サービスアカウントの認証情報
   - `gmail-api-credentials` : Gmail用OAuthクライアント認証情報

#### 4. アプリケーションからの認証情報取得
- Pythonアプリ等からは、Secret Manager経由で認証情報を取得し、環境変数や設定で利用します。
- `.env`や`config/settings.yaml`でファイルパスを指定する必要はありません。
- 例：
  - `SPREADSHEET_CREDENTIAL_JSON` 環境変数にSecret Managerから取得したJSONを格納
  - `GMAIL_CREDENTIALS` も同様

#### 5. 注意事項
- Gmail APIのOAuthクライアントID/シークレットは手動発行が必要ですが、一度Secret Managerに格納すれば以降は自動的に安全に運用できます。
- サービスアカウント型はGmail APIの一部機能に非対応のため、ユーザー認可型（OAuthクライアント）を利用しています。

---

これにより、認証情報の手動管理・配置ミスのリスクがなくなり、安全かつ自動的にインフラ・認証基盤が整います。

### 実装とテスト
1. Seleniumを利用したMoneyForwardからのデータ取得処理を実装
2. Pythonスクリプトでスプレッドシートの更新処理を実装
3. ローカル環境での手動テストを行い、動作確認

### 定期実行の設定
- Cronジョブを使用して、定期的にデータ取得からスプレッドシートの更新までを自動化
- `docker-compose up -d`で実行し、crontabで以下のようなコマンドを設定（例）：
    ```cron
    * */12 * * * /usr/bin/docker exec uv-for-seleniarm python /app/src/main.py
    ```

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
  - 出力先ディレクトリ、ダウンロードディレクトリ、認証情報ファイルのパスは、実際のシステム構成に合わせて確認・変更してください。

> ※ 本手順では、Python 3.12およびmypy/pylint等の静的解析ツールを用いて、変数名やコメント、ガード句の使用などGoogleのエンジニアとしてのベストプラクティスに従った設計を意識しています。

