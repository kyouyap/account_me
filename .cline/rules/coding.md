# コーディングプラクティス

---

## 原則

### 関数型アプローチ (FP)
- **純粋関数を優先:** 外部状態に依存しない関数を作る  
- **不変データ構造を使用:** 変更不可なオブジェクト（例: `@dataclass(frozen=True)`）を活用する  
- **副作用を分離:** I/O や外部通信は関数の境界に押し出す  
- **型安全性を確保:** 型ヒントをフル活用し、`mypy --strict` を CI で必須にする  

### テスト駆動開発 (TDD)
- **Red-Green-Refactor サイクル:** 失敗するテスト → 実装 → リファクタ  
- **テスト＝仕様:** テストがシステムの期待振る舞いを語る  
- **小さな単位で反復:** 1 つの振る舞いにつき 1 つのテスト  
- **常にリファクタ:** 重複排除と設計改善を継続  

---

## 1. コードスタイル

| ツール           | 設定／運用                                            |
|------------------|-------------------------------------------------------|
| **black**        | 行長 88、`--target-version py313`                     |
| **ruff**         | flake8 + isort + pep8-naming を統合。CI で必須       |
| **pre-commit**   | `pre-commit run --all-files` を Git hook で強制       |

> *スタイル議論はツールに委ね、コードレビューでは設計・命名の本質に集中する。*

---

## 2. 型ヒント & 静的解析

- **PEP 695** の新ジェネリック構文（`class Box[T]: ...`）を活用  
- ファイル先頭に必ず `from __future__ import annotations` を記述  
- 型エイリアス例:  
  ```python
  type JSON = dict[str, "JSON | str | int | bool | None"]
  ```  
- **mypy 設定** (`pyproject.toml` 抜粋)  
  ```ini
  [tool.mypy]
  python_version = "3.13"
  strict = true
  incremental = true
  warn_unused_ignores = true
  ```

---

## 3. Docstring 規約（Google Style）

```python
def fetch_user(user_id: int) -> User:
    """Retrieve a user record.

    Args:
        user_id: Unique identifier of the user.

    Returns:
        User: Retrieved user object.

    Raises:
        UserNotFoundError: If the user does not exist.

    Examples:
        >>> user = fetch_user(42)
        >>> assert user.id == 42
    """
```
- サマリ → 詳細 → Args → Returns → Raises → Examples の順序を厳守  
- 1行サマリは動詞から始める  
- Examples には `>>>` 形式で記述し、doctest 可能に

---

## 4. ディレクトリ構成（src レイアウト）

```
project/
├── docs/                     # ドキュメント
├── src/
│   └── my_package/           # アプリケーションコード
│       ├── models/           # データ構造・スキーマ定義
│       ├── services/         # ビジネスロジック
│       ├── adapters/         # 外部連携（DB, API など）
│       ├── cli/              # CLI エントリポイント
│       ├── utils/            # 汎用ユーティリティ
│       └── settings.py       # 設定管理（Pydantic など）
├── tests/                    # テストコード
├── pyproject.toml
└── README.md
```
- `src/` 以下は機能ごとに明確に分割  
- プロジェクト固有の追加構造は都度追記

---

## 5. 依存性の注入（DI）

```python
from typing import Protocol

class UserRepo(Protocol):
    def save(self, user: User) -> None: ...

class SqlUserRepo:
    def save(self, user: User) -> None:
        # 実際の DB 保存処理
        ...

class UserService:
    def __init__(self, repo: UserRepo) -> None:
        self._repo = repo

    def register(self, user: User) -> None:
        self._repo.save(user)
```
- **コンストラクタインジェクション** を第一選択  
- `dependency-injector` 等のコンテナ導入で設定と実実装を切り分け、テスト時は Stub / Mock に差し替え

---

## 6. エラー処理

- **ビジネスエラー用** にカスタム例外を定義  
  ```python
  class BusinessError(Exception):
      """ビジネス要件に起因するエラー。"""
  ```
- 組み込み例外をむやみに握りつぶさない  
- `try / except / else / finally` を適切に使い分け、必要に応じてロールバック処理を組み込む  
- 例外メッセージには検索可能なキーワードと変数値を含める

---

## 7. ロギング

- `structlog` + 標準 `logging` で JSON フォーマット出力  
- **ログレベル基準**  
  - DEBUG: 詳細な変数内容やループ内部  
  - INFO: 正常処理の通過点  
  - WARNING: リトライ可能な軽微エラー  
  - ERROR: 回復不能な致命エラー（アラート）  
- ContextVar でトレース ID を伝搬し、一貫したログ追跡を実現

---

## 8. テスト指針

| 項目               | 推奨                                      |
|--------------------|-------------------------------------------|
| **フレームワーク** | `pytest>=8`, `pytest-asyncio`             |
| **パターン**       | Arrange–Act–Assert を徹底                 |
| **カバレッジ**     | 行 95% / 分岐 90% 以上を CI で必須          |
| **テストダブル**   | `unittest.mock`, `pytest-mock`, `factory-boy` |
| **フィクスチャ管理**| `conftest.py` で共通設定をまとめる        |

---

## 9. デザインパターン実装例

### Strategy

```python
from typing import Protocol

class Discount(Protocol):
    def __call__(self, price: float) -> float: ...

def no_discount(p: float) -> float:
    return p

def seasonal_discount(p: float) -> float:
    return p * 0.9

class PriceCalculator:
    def __init__(self, strategy: Discount = no_discount) -> None:
        self._strategy = strategy

    def calc(self, price: float) -> float:
        return self._strategy(price)
```

### Adapter

```python
class PaymentSDK:
    def send(self, payload: dict[str, str]) -> None: ...

class PaymentPort(Protocol):
    def pay(self, amount: int) -> None: ...

class PaymentAdapter:
    def __init__(self, sdk: PaymentSDK) -> None:
        self._sdk = sdk

    def pay(self, amount: int) -> None:
        self._sdk.send({"amount": str(amount)})
```

*(Factory, Observer, Decorator などは付録に追加推奨)*

---

## 10. 非同期 & 並行処理

| 処理           | 推奨手法                                             |
|----------------|------------------------------------------------------|
| I/O バウンド   | `asyncio`, `aiohttp`, `asyncpg`                     |
| CPU バウンド   | `concurrent.futures.ProcessPoolExecutor`            |
| キャンセル制御 | `except asyncio.CancelledError:` は握りつぶさず再送出 |

---

## 11. パフォーマンス最適化

- `functools.cache`, `slots=True` dataclass でメモリ最適化  
- `heapq`, `bisect` など組み込みデータ構造を活用  
- アルゴリズムは Big-O を意識し、適切なデータ構造を選択  
- 必要に応じて Cython や mypyc でコンパイル検討

---

## 12. セキュリティ

1. **Secrets 管理:** `.env`, Vault, Secret Manager を利用しコードに埋め込まない  
2. **脆弱性スキャン:** `pip-audit`, `safety` を CI に組み込む  
3. **入力検証:** Pydantic や `validators` で堅牢に  
4. **Web セキュリティ:** SQLi, XSS, CSRF 対策は OWASP ASVS を参照

