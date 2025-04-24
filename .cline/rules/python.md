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

| 目的 | 具体策 |
|------|--------|
| **読みやすさ最優先** | *Self-Documenting Code* を目指す。意味のある変数名・関数名、重複排除（DRY）。 |
| **自動整形の徹底** | `black`, `ruff`, `isort` を CI で強制。人間同士のスタイル議論をゼロにする。 |
| **型安全** | 100 %型ヒント＋`mypy --strict`。曖昧さを排除し、保守コストを下げる。 |
| **小さく作り、大きく育てる** | 小さい PR・小さい関数でフィードバックループを短縮。 |
| **実行環境の統一** | `pyproject.toml` でバージョン固定。Docker / dev container 推奨。 |

---

## 2. 実装の選択基準

> JavaScript 規約のテイストを踏襲したシンプルさで整理📝

| 選択肢 | 使う場面 | 主なメリット |
|--------|---------|-------------|
| **関数** | - 単純な計算・純粋関数<br>- 内部状態を保持しない | テスト容易、依存最小、読解負荷が低い |
| **クラス** | - 内部状態を管理したい<br>- リソースのライフサイクルが必要（DBコネクタなど） | 状態と振る舞いをまとめて表現 |
| **データクラス (`@dataclass`)** | - 不変データレコード<br>- 値オブジェクト | ボイラープレート削減、比較/排序が楽 |
| **Enum** | - 限定された定数集合 | マジックナンバー排除、型安全 |
| **Protocol / 抽象基底クラス** | - 実装の交換が前提<br>- テストダブル注入 | DI と相性良し、LSP 準拠 |
| **Adapter** | - 外部 API / DB / SDK の抽象化 | テスト容易、実装差し替え |
| **モジュール単位のシングルトン** | - 設定値やログなど一意リソース | グローバル変数より安全 |
| **スクリプト (`if __name__ == "__main__":`)** | - ワンショット実行ツール | CLI インタフェースを簡易に用意 |

---

## 3. コードスタイル & フォーマッタ

| ツール | ルール |
|-------|--------|
| **black** | 行長 88 桁、--target-version py313 |
| **ruff** | Pylint, flake8, isort, pep8-naming 等を統合。エラーは CI ブロッカー。 |
| **pre-commit** | `pre-commit run --all-files` を Git hook に。 |
| **PEP 8 準拠** | black が自動担保。例外：行長を越える Google style docstring の `Args:` セクションは許可。 |

---

## 4. 型ヒント & 静的解析

1. **原則すべての公開 API に型を付与**。  
2. **`from __future__ import annotations`** を常に先頭に。  
3. **3.13 の機能**  
   - PEP 695: `class Box[T]: ...` の新ジェネリック構文  
   - `Self` 型 & `typing.Sealed`（シールドクラス）  
4. **型エイリアス宣言**  
   ```python
   type JSON = dict[str, "JSON | str | int | bool | None"]  # PEP695
   ```
5. **mypy 設定（抜粋）**
   ```ini
   [mypy]
   python_version = 3.13
   strict = True
   warn_unused_configs = True
   ```

---

## 5. Docstring 規約（Google Style）

```python
def fetch_user(user_id: int) -> User:
    ```python
        """単一のユーザーオブジェクトを取得します。

        Args:
            user_id: ユーザーの一意な識別子。

        Returns:
            User: 取得されたユーザーのドメインモデル。

        Raises:
            UserNotFoundError: ユーザーが存在しない場合。
        """
    ```
```

- セクション順序: **Summary → Args → Returns → Raises → Examples**  
- 1行サマリは動詞から。  
- **例** には `>>>` を使い doctest 可能に。

---

## 6. モジュール / パッケージ構成

```
project/
├── src/
│   ├── app/            # アプリケーションサービス
│   ├── domain/         # エンティティ & 値オブジェクト
│   ├── infra/          # DB / API 実装 (Adapter)
│   ├── presentation/   # CLI / Web Handler
│   └── settings.py     # Pydantic ベース設定
├── tests/
│   └── ...
├── pyproject.toml
└── README.md
```

- **`src/` レイアウト** 推奨。  
- ドメイン駆動設計 (DDD) に合わせて `domain`, `app`, `infra`, `presentation` を分離。  

---

## 7. 依存性の注入（DI）

| 指針 | 例 |
|------|----|
| **コンストラクタインジェクションが第一候補** | ```python class UserService: def __init__(self, repo: UserRepo): ...``` |
| **ファクトリ / Provider パターンを組み合わせる** | `providers.Factory(UserService)` (dependency-injector ライブラリなど) |
| **設定 & 環境変数は Pydantic-Settings で吸収** | `settings.db.url` を注入 |
| **テストでは Stub / Mock 実装に差し替え** | Protocol をキーに DI コンテナでバインド切替 |

---

## 8. エラー処理 & 例外設計

1. **ビジネスエラーは独自例外クラス**（`class DomainError(Exception): ...`）  
2. **Python 組み込み例外を安易に握りつぶさない**  
3. **`try / except / else / finally` ブロックをフル活用**  
4. **例外メッセージはログ・モニタリングで検索可能なキーワードを含める**

---

## 9. ロギング

- `structlog` + 標準 `logging` で JSON 出力。  
- **ログレベル基準**  
  - DEBUG: 変数値  
  - INFO: 正常系ステップ  
  - WARNING: リトライ可能／軽微エラー  
  - ERROR: 失敗 (アラート)  
- **ContextVar** でトレース ID を伝搬。

---

## 10. テスト指針

| 項目 | 推奨 |
|------|------|
| **フレームワーク** | `pytest>=8`, `pytest-asyncio` |
| **AAA パターン** | *Arrange-Act-Assert* を厳守。 |
| **カバレッジ閾値** | 行 95 % / 分岐 90 % 以上を CI で必須。 |
| **テストダブル** | `unittest.mock`, `pytest-mock`, `factory-boy` |
| **フィクスチャ階層** | `conftest.py` をルートに共通化。 |

---

## 11. デザインパターン実装例

> **型ヒント＋Google docstring 付きのミニ実装。**

### 11.1 Strategy

```python
from collections.abc import Callable
from typing import Protocol

class DiscountStrategy(Protocol):
    """Strategy インタフェース。"""

    def __call__(self, price: float) -> float: ...

def no_discount(price: float) -> float:  # 関数も Strategy に
    return price

def seasonal_discount(price: float) -> float:
    return price * 0.9

class PriceCalculator:
    """価格計算クラス (Context)。"""

    def __init__(self, strategy: DiscountStrategy = no_discount) -> None:
        self._strategy = strategy

    def calc(self, price: float) -> float:
        """選択された Strategy で価格を算出。"""
        return self._strategy(price)
```

### 11.2 Adapter

```python
class PaymentGateway:
    """外部 SDK (既存)."""
    def send(self, payload: dict[str, str]) -> None: ...

class PaymentPort(Protocol):
    def pay(self, amount: int) -> None: ...

class PaymentAdapter:
    """SDK をラップし抽象ポートを実装。"""

    def __init__(self, sdk: PaymentGateway) -> None:
        self._sdk = sdk

    def pay(self, amount: int) -> None:
        self._sdk.send({"amount": str(amount)})
```

*Singleton, Factory, Observer, Command* などは付録にコード例を配置（省略）。

---

## 12. 非同期 & 並行処理

1. **`asyncio` を優先しスレッド乱用禁止**  
2. **I/O バウンド処理** → `asyncio`, CPU バウンド → `concurrent.futures.ProcessPoolExecutor`  
3. **Cancellation 伝搬** を忘れず `try/except asyncio.CancelledError`  
4. **非同期コンテキストマネージャ** (`async with`) で接続を安全に管理。

---

## 13. パフォーマンス最適化

| レイヤ | 施策 |
|-------|-----|
| **アルゴリズム** | Big-O を意識。辞書・集合を活用する。 |
| **I/O** | `aiohttp`, `asyncpg` など非同期ライブラリ。 |
| **データ構造** | `array`, `deque`, `bisect`, `heapq` | 
| **メモリ** | `slots=True` dataclass、`functools.cache` で重複計算削減。 |
| **コンパイル** | `python -OO -m py_compile` や Cython / mypyc は最後の手段。 |

---

## 14. セキュリティ / 安全なコード

- **依存ライブラリ脆弱性スキャン**: `pip-audit`, `safety`.  
- **Secrets 管理**: 環境変数 & Secret Manager、ハードコード禁止。  
- **入力値バリデーション**: Pydantic v3 の `model_validate`。  
- **Web 開発**: インジェクション・XSS・CSRF 対策、`werkzeug.security` や OWASP ASVS を参照。  
- **署名付き型アノテーション** で意図しないミューテーションを防ぐ。

---

### 使い方のヒント

1. 本ドキュメントを **社内 Wiki / README** にそのまま貼り付けても OK。  
2. プロジェクト固有の規定（命名プリフィックス、CI /CD など）は追記。  
3. 運用しながら Pull Request で改善案を随時取り込むことで「生きた規約」に。  

