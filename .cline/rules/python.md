# Python のコーディングベストプラクティス

## 方針

- **最初に型とインターフェース（関数のシグネチャ）を考える**  
  Python では、PEP 484 に基づく型ヒントや `typing.NewType`、`Protocol` を活用して、処理対象の型と関数のシグネチャを設計します。

- **ファイル冒頭のコメントで仕様を明記する**  
  各ファイルの冒頭に、そのファイルでどのような仕様を実現するかを docstring やコメントとして記述します。

- **内部状態を持たない場合は関数を優先する**  
  状態が不要な場合は、クラスよりも純粋関数を作成し、テストや再利用がしやすい設計を心がけます。

- **副作用はアダプタパターンで抽象化し、テスト時はインメモリな実装で差し替える**  
  外部依存（IO、DB、外部 API など）はアダプタパターンを用いて抽象化し、テスト時にはモックやスタブに置き換えます。

---

## 型の使用方針

1. **具体的な型を使用する**  
   - Python では `Any` の使用は最小限にとどめ、必要に応じて `Union` や `Optional` で型を絞り込みます。
   - 標準ライブラリの `typing` モジュールや `typing_extensions` の Utility Types を活用します。

2. **型エイリアスの命名**  
   - 意味のある名前を付け、型の意図を明確にします。  
   - 例:
     ```python
     from typing import NewType
     
     UserId = NewType("UserId", str)
     
     # 良い例
     class UserData:
         def __init__(self, id: UserId, created_at: str):
             self.id = id
             self.created_at = created_at
     
     # 悪い例（any の使用）
     Data = object
     ```

---

## エラー処理

### 1. Result 型の使用

Python では、成功と失敗を表すために自作の `Result` クラスを用いることがあります。例えば：

```python
from typing import Generic, TypeVar, Union

T = TypeVar("T")
E = TypeVar("E")

class Result(Generic[T, E]):
    def __init__(self, ok: bool, value: Union[T, None] = None, error: Union[E, None] = None):
        self.ok = ok
        self.value = value
        self.error = error

    def is_ok(self) -> bool:
        return self.ok

    def is_err(self) -> bool:
        return not self.ok

def ok(value: T) -> Result[T, E]:
    return Result(True, value=value)

def err(error: E) -> Result[T, E]:
    return Result(False, error=error)
```

エラー型も、具体的なケースを列挙し、エラーメッセージを含めた実装にします。

### 2. エラー処理の例

```python
import requests
from typing import Any

class ApiError(Exception):
    pass

class NetworkError(ApiError):
    pass

class NotFoundError(ApiError):
    pass

class UnauthorizedError(ApiError):
    pass

async def fetch_user(user_id: str) -> Result[Any, ApiError]:
    try:
        response = requests.get(f"https://api.example.com/users/{user_id}")
        if not response.ok:
            if response.status_code == 404:
                return err(NotFoundError("User not found"))
            elif response.status_code == 401:
                return err(UnauthorizedError("Unauthorized"))
            else:
                return err(NetworkError(f"HTTP error: {response.status_code}"))
        return ok(response.json())
    except Exception as error:
        return err(NetworkError(str(error) if isinstance(error, Exception) else "Unknown error"))
```

---

## 実装パターン

### 1. 関数ベース（状態を持たない場合）

```python
from datetime import datetime

def create_logger():
    def log(message: str) -> None:
        print(f"[{datetime.utcnow().isoformat()}] {message}")
    return log
```

### 2. クラスベース（状態を持つ場合）

```python
from typing import Any, Optional
import time

class TimeBasedCache:
    def __init__(self, ttl: float):
        self.ttl = ttl
        self.items: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        item = self.items.get(key)
        if item and time.time() < item["expire_at"]:
            return item["value"]
        return None

    def set(self, key: str, value: Any) -> None:
        self.items[key] = {
            "value": value,
            "expire_at": time.time() + self.ttl
        }
```

### 3. アダプターパターン（外部依存の抽象化）

```python
from typing import Callable, Dict, TypeVar, Generic
import requests

T = TypeVar("T")

# Fetcher 型の定義（外部依存の抽象化）
Fetcher = Callable[[str], Result[T, ApiError]]

def create_fetcher(headers: Dict[str, str]) -> Fetcher:
    def fetcher(path: str) -> Result[T, ApiError]:
        try:
            response = requests.get(path, headers=headers)
            if not response.ok:
                return err(NetworkError(f"HTTP error: {response.status_code}"))
            return ok(response.json())
        except Exception as error:
            return err(NetworkError(str(error) if isinstance(error, Exception) else "Unknown error"))
    return fetcher

class ApiClient:
    def __init__(self, get_data: Fetcher, base_url: str):
        self.get_data = get_data
        self.base_url = base_url

    def get_user(self, user_id: str) -> Result[Any, ApiError]:
        return self.get_data(f"{self.base_url}/users/{user_id}")
```

---

## 実装の選択基準

1. **関数を選ぶ場合**
   - 単純な操作のみ
   - 内部状態が不要
   - 依存が少なく、テストが容易

2. **クラスを選ぶ場合**
   - 内部状態の管理が必要
   - 設定やリソースの保持、メソッド間での状態共有、ライフサイクル管理が必要

3. **Adapter を選ぶ場合**
   - 外部依存（API や DB など）の抽象化が必要
   - テスト時に容易にモックに置き換えられるようにしたい
   - 実装の詳細を隠蔽し、差し替え可能性を高める

---

## 一般的なルール

1. **依存性の注入**
   - 外部依存はコンストラクタや関数の引数として注入し、グローバルな状態を避ける
   - テスト時にモックに置き換えられるように設計する

2. **インターフェースの設計**
   - 必要最小限のメソッドを定義し、内部実装の詳細は隠蔽する
   - プラットフォーム固有の実装に依存しない抽象的なインターフェースを構築する

3. **テスト容易性**
   - モックの実装を簡潔にし、エッジケースのテストを充実させる
   - テストヘルパーなどを適切に分離し、テストしやすい構造にする

4. **コードの分割**
   - 単一責任の原則 (SRP) に従い、適切な粒度でモジュール化する
   - 循環参照を避け、モジュール間の依存関係を明確に管理する

5. **コード整頓・可読性向上のための指針**
   - **ガード句（Guard Clauses）を活用する**  
     ネストを浅く保つため、条件分岐は早期returnなどでシンプルに。ただし多用しすぎは避ける。
   - **デッドコードはこまめに削除する**  
     不要なコードは都度消し、バージョン管理で安全性を担保する。
   - **対称性を意識してコードを統一する**  
     同じ振る舞いの処理は表現を揃える。
   - **新旧インターフェースの段階的移行を意識する**  
     大規模な一括変更を避け、まず新しいインターフェースを定義して徐々に移行する。
   - **自然な処理順序を意識する**  
     「入力→処理→出力」の流れで関数や処理を並べる。
   - **凝集度を高める**  
     関連する処理や変数は近くにまとめ、カップリングを下げる。
   - **宣言と初期化はまとめて行う**  
     変数宣言と初期化を同時に行い、不要なスコープを作らない。
   - **説明的な変数・定数を使う**  
     マジックナンバーや複雑な式は意味のある名前に置き換える。
   - **明示的なパラメータ設計**  
     関数には必要な要素を明示的に引数として渡す。
   - **長い処理は適切に分割する**  
     ステートメントをチャンク化し、可読性を上げる。
   - **ヘルパー関数を抽出する**  
     再利用性の高い処理は関数やメソッドに切り出す。
   - **細分化しすぎない**  
     クラスや関数を細切れにしすぎず、適切な粒度を保つ。
   - **コメントは「なぜ」を中心に、冗長なものは削除する**  
     「何をしているか」はコード、「なぜそうするか」はコメントで明確に。
   - **ツールを活用し段階的に整頓する**  
     IDEの自動警告や静的解析ツールを活用し、小さな改善を積み重ねる。
