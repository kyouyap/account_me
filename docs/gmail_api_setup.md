# Gmail API セットアップマニュアル

## 1. Google Cloud Consoleでの設定

### 1.1 Gmail APIの有効化

1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. プロジェクトを選択
3. 左側メニューから「APIとサービス」>「ライブラリ」を選択
4. 検索バーで「Gmail API」を検索
5. Gmail APIを選択し、「有効にする」をクリック

### 1.2 認証情報の作成

1. 左側メニューから「APIとサービス」>「認証情報」を選択
2. 「認証情報を作成」>「OAuthクライアントID」をクリック
3. アプリケーションの種類で「デスクトップアプリ」を選択
4. 名前を入力（例：「MoneyForward Automation」）
5. 「作成」をクリック
6. クライアントIDとクライアントシークレットが表示されるので、JSONファイルをダウンロード

### 1.3 OAuth同意画面の設定

1. 左側メニューから「APIとサービス」>「OAuth同意画面」を選択
2. User Typeで「内部」を選択（組織内のみ）
3. 必須項目を入力：
   - アプリ名：「MoneyForward Automation」
   - サポートメール：あなたのメールアドレス
   - デベロッパーの連絡先情報：あなたのメールアドレス
4. 保存

### 1.4 スコープの設定

1. OAuth同意画面の「スコープ」セクションで「スコープを追加または削除」をクリック
2. 以下のスコープを追加：
   - `https://www.googleapis.com/auth/gmail.readonly`
3. 保存

## 2. Secret Managerへの認証情報の保存

### 2.1 認証情報の準備

1. ダウンロードしたJSONファイルを開き、内容を確認
2. ファイルには以下の情報が含まれています：
   - client_id
   - client_secret
   - redirect_uris
   - auth_uri
   - token_uri

### 2.2 Terraformによる設定

1. main.tfに以下を追加：
```hcl
# Gmail API 認証情報
resource "google_secret_manager_secret" "gmail_credentials" {
  secret_id = "gmail-api-credentials"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "gmail_credentials" {
  secret      = google_secret_manager_secret.gmail_credentials.id
  secret_data = var.gmail_credentials_json
}

# Gmail API トークン
resource "google_secret_manager_secret" "gmail_token" {
  secret_id = "gmail-api-token"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}
```

2. variables.tfに以下を追加：
```hcl
variable "gmail_credentials_json" {
  description = "Gmail API認証情報のJSON"
  type        = string
  sensitive   = true
}

variable "gmail_token_json" {
  description = "Gmail APIアクセストークンのJSON"
  type        = string
  sensitive   = true
}
```

3. 必要なAPIを有効化：
```hcl
locals {
  required_apis = [
    "gmail.googleapis.com",
    # 他の既存のAPI...
  ]
}
```

### 2.3 認証情報の適用

1. terraform.tfvarsに認証情報を追加：
```hcl
gmail_credentials_json = <<EOT
{
  // ダウンロードしたJSONファイルの内容をここにペースト
}
EOT
```

2. Terraformを適用：
```bash
terraform apply
```

## 3. 環境変数の設定

以下の環境変数を設定：

```bash
PROJECT_ID="your-project-id"  # GCPプロジェクトID
```

## 4. 依存パッケージのインストール

必要なPythonパッケージをインストール：

```bash
uv pip install -e .
```

## 5. 注意事項

- 認証情報は絶対にGitにコミットしないでください
- 初回実行時にブラウザで認証が必要になる場合があります
- トークンの有効期限が切れた場合は自動的に更新されます
- Secret Managerのシークレットにはバージョン管理があるため、古いバージョンは適宜クリーンアップしてください
