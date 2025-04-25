# 技術コンテキスト

## 開発環境

### 1. 基盤システム
- **OS**: Ubuntu on WSL2
- **コンテナ化**: Docker + docker-compose
- **バージョン管理**: Git

### 2. 開発ツール
- **IDE**: VSCode
  - Remote - WSL拡張
  - Python拡張
  - Docker拡張
- **パッケージ管理**: uv
- **フォーマッター/リンター**: 
  - ruff
  - mypy
  - pre-commit

## 技術スタック

### 1. コア言語・フレームワーク
```toml
[dependencies]
python = ">=3.11"
selenium = ">=4.30.0"
gspread-dataframe = ">=4.0.0"
pydantic = ">=2.10.6"
fastapi = ">=0.104.0"
```

### 2. GCPサービス連携
```toml
[dependencies]
google-api-python-client = ">=2.88.0"
google-auth-oauthlib = ">=1.0.0"
google-auth-httplib2 = ">=0.1.0"
google-cloud-secret-manager = ">=2.16.0"
```

### 3. 開発支援ツール
```toml
[tool.uv.dev-dependencies]
pytest = ">=8.3.2"
pre-commit = ">=3.8.0"
ruff = ">=0.6.3"
mypy = ">=1.15.0"
pytest-cov = ">=6.0.0"
```

## インフラストラクチャ

### 1. ローカル開発環境
```yaml
version: '3'
services:
  app:
    build: .
    volumes:
      - .:/app
    environment:
      - PYTHONPATH=/app/src
```

### 2. クラウドリソース
- **GCP**:
  - Secret Manager: 認証情報管理
  - Gmail API: メール連携
  - Sheets API: スプレッドシート操作
  - Storage: データバックアップ

### 3. CI/CD環境
```yaml
pre-commit:
  repos:
    - repo: https://github.com/astral-sh/ruff-pre-commit
    - repo: https://github.com/pre-commit/mirrors-mypy
```

## テスト戦略

### 1. ユニットテスト
```python
# テストの基本構造
def test_something():
    # Arrange
    expected = ...
    
    # Act
    actual = ...
    
    # Assert
    assert actual == expected
```

### 2. 統合テスト
- Seleniumテスト
- APIテスト
- スプレッドシート連携テスト

### 3. カバレッジ目標
```toml
[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if __name__ == .__main__.:"
]
omit = ["src/main.py"]
```

## セキュリティ考慮事項

### 1. 認証情報管理
- Secret Managerによる集中管理
- 環境変数経由でのアクセス
- トークンの安全な保存

### 2. アクセス制御
- 最小権限の原則
- APIキーのローテーション
- セッション管理

### 3. データ保護
- 機密情報の暗号化
- ログからの機密情報除去
- バックアップ戦略

## 運用管理

### 1. ログ管理
```yaml
logging:
  version: 1
  handlers:
    console:
      class: logging.StreamHandler
      level: INFO
    file:
      class: logging.FileHandler
      filename: log/app.log
      level: DEBUG
```

### 2. モニタリング
- 実行状態の監視
- エラー検知
- パフォーマンス追跡

### 3. メンテナンス
- 依存パッケージの更新
- セキュリティパッチの適用
- バックアップの確認
