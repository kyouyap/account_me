# Python のベストプラクティス

---

## 目次

1. 全体方針  
2. 実装の選択基準  
3. コードスタイル & フォーマッタ  
4. 型ヒント & 静的解析  
5. Docstring 規約（Google Style）  
6. モジュール / パッケージ構成  
7. 依存性の注入（DI）  
8. エラー処理 & 例外設計  
9. ロギング  
10. テスト指針  
11. デザインパターン実装例  
12. 非同期 & 並行処理  
13. パフォーマンス最適化  
14. セキュリティ / 安全なコード  
15. 参考資料  

---

## 1. 全体方針

| 目的                       | 具体策                                    |
|----------------------------|-------------------------------------------|
| **読みやすさ最優先**       | Self-Documenting Code を目指す。意味のある変数名・関数名、重複排除（DRY）。 |
| **自動整形の徹底**         | `black`, `ruff`, `isort` を CI で強制。    |
| **型安全**                 | 100% 型ヒント + `mypy --strict`。        |
| **小さく作り、大きく育てる** | 小さい PR・小さい関数でフィードバックループを短縮。        |
| **実行環境の統一**         | `pyproject.toml` でバージョン固定。Docker / dev container 推奨。 |

---

## 2. 実装の選択基準

> JavaScript 規約のテイストを踏襲したシンプルさ📝

| 選択肢                      | 使う場面                                                      | 主なメリット                         |
|-----------------------------|---------------------------------------------------------------|--------------------------------------|
| **関数**                    | - 単純な計算・純粋関数<br>- 内部状態を保持しない             | テスト容易、依存最小、読解負荷が低い |
| **クラス**                  | - 内部状態を管理したい<br>- リソースのライフサイクルが必要   | 状態と振る舞いをまとめて表現         |
| **データクラス (`@dataclass`)** | - 単なるデータレコード<br>- イミュータブルな構造を作りたい | ボイラープレート削減、比較/排序が楽   |
| **Enum**                    | - 限定された定数集合を扱いたい                               | マジックナンバー排除、型安全         |
| **Protocol / 抽象基底クラス** | - 実装を差し替え可能に<br>- テストダブル注入                 | DI と相性良し、LSP に沿った設計      |
| **Adapter**                 | - 外部 API / DB / SDK の抽象化                              | テスト容易、実装差し替え可能         |
| **モジュール単位のシングルトン** | - 設定値やログなど唯一のリソース                         | グローバル変数より安全               |
| **スクリプト (`if __name__ == "__main__":`)** | - ワンショット実行ツール                              | シンプルな CLI インタフェース        |

---

## 3. コードスタイル & フォーマッタ

| ツール           | ルール                                         |
|------------------|------------------------------------------------|
| **black**        | 行長 88 文字、`--target-version py313`         |
| **ruff**         | Pylint, flake8, isort, pep8-naming 等を統合。CI ブロッカー。 |
| **pre-commit**   | `pre-commit run --all-files` を Git hook に設定。 |
| **PEP 8 準拠**   | black で自動担保。例外：docstring の Args セクションは多少超えて可。 |

---

## 4. 型ヒント & 静的解析

1. **公開 API には必ず型注釈**  
2. **`from __future__ import annotations`** を常に先頭に記述。  
3. **Python 3.13 の新機能**  
   - PEP 695: 新ジェネリック構文 (`class Box[T]: ...`)  
   - `Self` 型、`typing.Sealed`  
4. **型エイリアス**  
   ```python
   type JSON = dict[str, "JSON | str | int | bool | None"]
   ```
5. **mypy 設定例** (`pyproject.toml` 抜粋)  
   ```ini
   [tool.mypy]
   python_version = "3.13"
   strict = true
   warn_unused_configs = true
   ```

---

## 5. Docstring 規約（Google Style）

```python
def fetch_user(user_id: int) -> User:
    """単一のユーザー情報を取得します。

    Args:
        user_id: ユーザーの一意な識別子。

    Returns:
        User: 取得されたユーザー情報オブジェクト。

    Raises:
        UserNotFoundError: ユーザーが存在しない場合。

    Examples:
        >>> user = fetch_user(123)
        >>> assert user.id == 123
    """
```

- **セクション順序**: Summary → Args → Returns → Raises → Examples  
- **1行サマリ** は動詞から始める。  
- **Examples** には `>>>` を使い doctest 可能に。

---

## 6. モジュール / パッケージ構成

```text
project/
├── docs/                   # ドキュメント
├── src/
│   └── my_package/         # アプリケーションコード
│       ├── models/         # データ構造・スキーマ定義
│       ├── services/       # ビジネスロジック
│       ├── adapters/       # 外部連携（DB, API など）
│       ├── cli/            # CLI エントリポイント
│       ├── utils/          # 汎用ユーティリティ
│       └── settings.py     # 設定管理（Pydantic など）
├── tests/                  # テストコード
├── pyproject.toml
└── README.md
```

- **トップレベル** に `src/`, `tests/`, `docs/` を配置。  
- `my_package` 直下は役割ごとに分割して整理。  
- プロジェクト固有の命名や追加構造は適宜追記。

---

## 7. 依存性の注入（DI）

| 指針                          | 備考                                                   |
|-------------------------------|------------------------------------------------------|
| **コンストラクタインジェクション優先** | 依存性をコンストラクタで受け取る。下記コード例参照。 |
| **Factory / Provider パターン活用**  | `providers.Factory(UserService)` （dependency-injector など） |
| **設定 & 環境変数** は Pydantic-Settings で一元管理。 |                                                      |
| **テスト** では Stub / Mock 実装に差し替え。      |                                                      |

**コンストラクタインジェクションの例:**
```python
class UserService:
    def __init__(self, repo: UserRepo) -> None:
        self._repo = repo
        # ...
```

---

## 8. エラー処理 & 例外設計

1.  **ビジネスエラー用にカスタム例外クラスを作成**
    -   ビジネス要件に起因するエラーを表す独自の例外クラスを定義します。下記コード例参照。
2.  **組み込み例外をむやみに握りつぶさない**
3.  **`try / except / else / finally` を適切に使い分ける**
4.  **例外メッセージ** はログやモニタリングで検索しやすいキーワードを含める

**カスタム例外クラスの例:**
```python
class BusinessError(Exception):
    """ビジネス要件に起因するエラーを表す例外。"""
    pass

class UserNotFoundError(BusinessError):
    """指定されたユーザーが見つからない場合に発生するエラー。"""
    def __init__(self, user_id: int) -> None:
        super().__init__(f"User with ID {user_id} not found.")
        self.user_id = user_id
```

---

## 9. ロギング

- `structlog` + 標準 `logging` で JSON 出力。  
- **ログレベル基準**  
  - DEBUG: 詳細な変数値  
  - INFO: 正常系ステップ  
  - WARNING: リトライ可能な軽微エラー  
  - ERROR: 回復不能な失敗（アラート）  
- **ContextVar** でトレース ID を伝搬。

---

## 10. テスト指針

| 項目               | 推奨                                     |
|--------------------|------------------------------------------|
| **フレームワーク** | `pytest>=8`, `pytest-asyncio`            |
| **パターン**       | Arrange–Act–Assert を厳守                |
| **カバレッジ**     | 行 95% / 分岐 90% 以上を CI で必須         |
| **ダブル**         | `unittest.mock`, `pytest-mock`, `factory-boy` |
| **フィクスチャ**   | `conftest.py` で共通設定をまとめる        |

---

## 11. デザインパターン実装例

> 型ヒント＋Google docstring 付きのミニ実装

### 11.1 Strategy

```python
from collections.abc import Callable

class DiscountStrategy(Protocol):
    """価格割引のための Strategy インターフェース。"""

    def __call__(self, price: float) -> float: ...
```

```python
def no_discount(price: float) -> float:
    """割引なし。"""
    return price

def seasonal_discount(price: float) -> float:
    """10% 割引。"""
    return price * 0.9

class PriceCalculator:
    """価格計算クラス（Context）。"""

    def __init__(self, strategy: DiscountStrategy = no_discount) -> None:
        self._strategy = strategy

    def calc(self, price: float) -> float:
        """選択された Strategy で価格を算出。"""
        return self._strategy(price)
```

### 11.2 Adapter

```python
class PaymentGateway:
    """外部 SDK クラス。"""
    def send(self, payload: dict[str, str]) -> None: ...
```

```python
class PaymentPort(Protocol):
    """アプリ側抽象インターフェース。"""
    def pay(self, amount: int) -> None: ...
```

```python
class PaymentAdapter:
    """SDK をラップして抽象 Port を実装。"""

    def __init__(self, sdk: PaymentGateway) -> None:
        self._sdk = sdk

    def pay(self, amount: int) -> None:
        self._sdk.send({"amount": str(amount)})
```

*(Singleton, Factory, Observer, Command などは付録にコード例を追加するとよい)*

---

## 12. 非同期 & 並行処理

1. **`asyncio` を優先**（スレッド乱用禁止）  
2. **I/O バウンド** → `asyncio`／`aiohttp`／`asyncpg`  
   **CPU バウンド** → `concurrent.futures.ProcessPoolExecutor`  
3. **キャンセル伝搬** を忘れず `except asyncio.CancelledError`  
4. **非同期コンテキストマネージャ** (`async with`) で安全に管理

---

## 13. パフォーマンス最適化

| レイヤ      | 施策                                                  |
|-------------|-------------------------------------------------------|
| **アルゴリズム** | Big-O を意識。辞書・集合を活用。                       |
| **I/O**        | 非同期ライブラリを活用 (`aiohttp`, `asyncpg`)        |
| **データ構造** | `array`, `deque`, `bisect`, `heapq`                  |
| **メモリ**     | `slots=True` dataclass、`functools.cache`            |
| **コンパイル** | `python -OO -m py_compile`、Cython / mypyc は最後の手段 |

---

## 14. セキュリティ / 安全なコード

- **脆弱性スキャン**: `pip-audit`, `safety`  
- **Secrets 管理**: 環境変数 & Secret Manager、ハードコード禁止  
- **入力バリデーション**: Pydantic v3 の `model_validate`  
- **Web 脆弱性対策**: インジェクション・XSS・CSRF 対策、OWASP ASVS 参照  
- **イミュータブル型アノテーション** で不意のミューテーションを防止

---

### 使い方のヒント

1. 本ドキュメントを **社内 Wiki / README** にそのまま貼り付け。  
2. プロジェクト固有のルール（命名規則、CI/CD フローなど）は適宜追記。  
3. 運用しながら Pull Request で改善案を取り込み、「生きた規約」に仕上げる。  

