
# コーディングプラクティス

## 原則

### 関数型アプローチ (FP)
- **純粋関数を優先:** 外部状態に依存しない関数を作る  
- **不変データ構造を使用:** 変更不可なオブジェクト（例: `@dataclass(frozen=True)`）を活用する  
- **副作用を分離:** I/O や外部通信は関数の境界に押し出す  
- **型安全性を確保:** 型ヒントをフル活用し、`mypy --strict` を CI で必須にする  

### ドメイン駆動設計 (DDD)
- **値オブジェクトとエンティティを区別:** 不変な値オブジェクト／ID で同一性を判断するエンティティ  
- **集約で整合性を保証:** 一貫性が必要な要素は 1 つの集約ルートに閉じ込める  
- **リポジトリでデータアクセスを抽象化:** DB・API 呼び出しを隠蔽しテスタビリティ向上  
- **境界付けられたコンテキスト:** ドメインごとに独立したモジュールへ分割  

### テスト駆動開発 (TDD)
- **Red-Green-Refactor サイクル:** 失敗するテスト → 実装 → リファクタ  
- **テスト＝仕様:** テストがシステムの期待振る舞いを語る  
- **小さな単位で反復:** 1 つの振る舞いにつき 1 つのテスト  
- **常にリファクタ:** 重複排除と設計改善を継続  

---

## 1. コードスタイル

| ツール | 設定／運用 |
|-------|-----------|
| **black** | 行長 88、`--target-version py313` |
| **ruff**  | flake8 + isort + pep8-naming を統合。CI で必須 |
| **pre-commit** | `pre-commit run --all-files` を Git hook で強制 |

> *議論はツールに委ね、レビューでは本質（設計・命名）に集中する。*

---

## 2. 型ヒント & 静的解析

- **PEP 695** の *新ジェネリック構文* `class Box[T]: ...` が使用可能
- `from __future__ import annotations` は常に最上部に書く  
- エイリアス宣言例  
  ```python
  type JSON = dict[str, "JSON | str | int | bool | None"]
  ```  
- **mypy 設定**  
  ```ini
  [mypy]
  python_version = 3.13
  strict = True
  incremental = True
  warn_unused_ignores = True
  ```

---

## 3. Docstring 規約（Google Style）

```python
def fetch_user(user_id: int) -> User:
    """Retrieve a user domain model.

    Args:
        user_id: Unique identifier.

    Returns:
        Retrieved user.

    Raises:
        UserNotFoundError: If the user does not exist.
    """
```

1 行サマリ → 詳細 → Args → Returns → Raises → Examples の順序を厳守。

---

## 4. ディレクトリ構成（DDD + src レイアウト）

```
project/
├── src/
│   ├── domain/         # エンティティ・値オブジェクト
│   ├── app/            # アプリケーションサービス
│   ├── infra/          # DB / 外部 API (Adapter)
│   ├── presentation/   # CLI / FastAPI / Lambda 等 I/O 層
│   └── settings.py     # Pydantic-Settings
└── tests/
```

---

## 5. 依存性の注入（DI）

```python
class UserRepo(Protocol):
    def save(self, user: User) -> None: ...

class SqlUserRepo(UserRepo):
    ...

class UserService:
    def __init__(self, repo: UserRepo) -> None:
        self._repo = repo
```

- **コンストラクタインジェクション** を第一選択  
- `dependency-injector` などのコンテナを用い、テストでは Stub に差し替え  

---

## 6. エラー処理

- ビジネスエラーは独自例外 (`class DomainError(Exception): ...`)  
- `try / except / else / finally` をフル活用しロールバックを保証  
- 例外メッセージは **検索可能なキーワード＋変数値** を含める  

---

## 7. ロギング

- **structlog + 標準 logging** で JSON 出力  
- レベル基準  
  - DEBUG : 変数・ループ内部  
  - INFO  : 正常フロー  
  - WARNING : リトライ可能  
  - ERROR : 失敗・アラート  

---

## 8. テスト指針

- **pytest ≥ 8**, **pytest-asyncio**  
- **Arrange-Act-Assert** を徹底  
- カバレッジ閾値: 行 95 % / 分岐 90 %（`coverage.py`）  
- テストダブル: `unittest.mock`, `pytest-mock`, `factory-boy`  

---

## 9. デザインパターン実装例

### Strategy

```python
from typing import Protocol

class Discount(Protocol):
    def __call__(self, price: float) -> float: ...

def no_discount(p: float) -> float: return p
def seasonal_discount(p: float) -> float: return p * 0.9

class PriceCalculator:
    def __init__(self, strategy: Discount = no_discount) -> None:
        self._strategy = strategy
    def calc(self, price: float) -> float: return self._strategy(price)
```

### Adapter

```python
class PaymentSDK:  # 外部ライブラリ
    def send(self, payload: dict[str, str]) -> None: ...

class PaymentPort(Protocol):
    def pay(self, amount: int) -> None: ...

class PaymentAdapter(PaymentPort):
    def __init__(self, sdk: PaymentSDK) -> None:
        self._sdk = sdk
    def pay(self, amount: int) -> None:
        self._sdk.send({"amount": str(amount)})
```

### Factory Method

```python
from abc import ABC, abstractmethod

class Exporter(ABC):
    @abstractmethod
    def export(self, data: str) -> None: ...

class JsonExporter(Exporter):
    def export(self, data: str) -> None: print(f"Exporting {data} to JSON")

class CsvExporter(Exporter):
    def export(self, data: str) -> None: print(f"Exporting {data} to CSV")

class ExporterFactory(ABC):
    @abstractmethod
    def create_exporter(self) -> Exporter: ...

class JsonExporterFactory(ExporterFactory):
    def create_exporter(self) -> Exporter: return JsonExporter()

class CsvExporterFactory(ExporterFactory):
    def create_exporter(self) -> Exporter: return CsvExporter()
```

### Observer

```python
from typing import Protocol, List

class Observer(Protocol):
    def update(self, message: str) -> None: ...

class Subject:
    def __init__(self) -> None:
        self._observers: List[Observer] = []

    def attach(self, observer: Observer) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        self._observers.remove(observer)

    def notify(self, message: str) -> None:
        for observer in self._observers:
            observer.update(message)

class EmailNotifier(Observer):
    def update(self, message: str) -> None:
        print(f"Sending email notification: {message}")
```

### Decorator

```python
import time
from typing import Callable, Any

def timing_decorator(func: Callable[..., Any]) -> Callable[..., Any]:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        print(f"{func.__name__} took {end_time - start_time:.4f} seconds")
        return result
    return wrapper

@timing_decorator
def process_data(data: list[int]) -> int:
    time.sleep(0.1) # Simulate work
    return sum(data)
```

---

## 10. 非同期 & 並行処理

| 処理 | 推奨手法 |
|------|-----------|
| I/O バウンド | `asyncio`, `aiohttp`, `asyncpg` |
| CPU バウンド | `concurrent.futures.ProcessPoolExecutor` |
| キャンセル伝搬 | `except asyncio.CancelledError:` で握りつぶさない |

---

## 11. パフォーマンス最適化

- **PEP 703** : GIL なしビルド (実験的) によりスレッド並列化が可能 
- **PEP 744** : JIT 基盤 (試験的) – ボトルネック関数の測定を優先し安易に ON にしない 
- `functools.cache`, `slots=True` dataclass, `heapq`, `bisect` 等を駆使し O 計算量を意識  

---

## 12. セキュリティ

1. **Secrets 管理**: `.env`, HashiCorp Vault, GCP Secret Manager などを経由  
2. **依存脆弱性スキャン**: `pip-audit`, `safety` を CI に  
3. **入力検証**: `pydantic` v3 の `model_validate`  
4. **Web**: SQLi・XSS・CSRF を OWASP ASVS でチェック  


