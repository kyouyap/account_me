
# コーディングプラクティス

## 原則

### 関数型アプローチ (FP)
- **純粋関数を優先:** 外部状態に依存しない関数を作る  
- **不変データ構造を使用:** 変更不可なオブジェクト（例: dataclass(frozen=True)）を活用する  
- **副作用を分離:** IO や外部通信は関数の境界に押し出す  
- **型安全性を確保:** 型ヒントや NewType を活用する

### ドメイン駆動設計 (DDD)
- **値オブジェクトとエンティティを区別:** 不変な値オブジェクトと、ID で同一性を判断するエンティティを明確に分ける  
- **集約で整合性を保証:** 関連する値やエンティティを集約し、一貫性を保つ  
- **リポジトリでデータアクセスを抽象化:** データの永続化や取得はインターフェースで抽象化する  
- **境界付けられたコンテキストを意識:** ドメインごとに独立したモジュール・パッケージ設計を行う

### テスト駆動開発 (TDD)
- **Red-Green-Refactor サイクル:** まず失敗するテストを書き、実装してテストを通し、リファクタリングする  
- **テストを仕様として扱う:** テストコード自体が仕様であると捉える  
- **小さな単位で反復:** 単体テストを重ねながら進める  
- **継続的なリファクタリング:** 常にコードを改善する意識を持つ

---

## 実装パターン

### 型定義

Python では、`typing.NewType` を利用してブランデッド型を作ることで、型安全性を高められます。

```python
from typing import NewType

Money = NewType("Money", float)
Email = NewType("Email", str)
```

### 値オブジェクト

値オブジェクトは不変で、値に基づく同一性を持ち、自己検証を行います。以下は、金額（Money）の作成関数の例です。

```python
from typing import Union, TypeVar, Generic

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

def create_money(amount: float) -> Result[Money, Exception]:
    if amount < 0:
        return err(Exception("負の金額不可"))
    return ok(Money(amount))
```

### エンティティ

エンティティは ID に基づく同一性を持ち、内部状態の更新を制御します。Python では `dataclass` を利用して表現します。

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class UserEntity:
    id: str
    name: str
```

### リポジトリ

リポジトリは、ドメインモデルのみを扱い、永続化の詳細を隠蔽します。テスト用のインメモリ実装も用意します。

```python
from abc import ABC, abstractmethod
from typing import Dict

class UserRepository(ABC):
    @abstractmethod
    def get_user(self, user_id: str) -> Result[UserEntity, Exception]:
        pass

class InMemoryUserRepository(UserRepository):
    def __init__(self):
        self.users: Dict[str, UserEntity] = {}

    def add_user(self, user: UserEntity):
        self.users[user.id] = user

    def get_user(self, user_id: str) -> Result[UserEntity, Exception]:
        if user_id in self.users:
            return ok(self.users[user_id])
        return err(Exception("User not found"))
```

### アダプターパターン

外部依存（例えば、外部 API へのアクセス）を抽象化するため、アダプターパターンを利用します。

```python
from abc import ABC, abstractmethod
import requests

class APIAdapter(ABC):
    @abstractmethod
    def fetch_data(self, endpoint: str) -> dict:
        pass

class RealAPIAdapter(APIAdapter):
    def fetch_data(self, endpoint: str) -> dict:
        response = requests.get(endpoint)
        response.raise_for_status()
        return response.json()
```

---

## 実装手順

1. **型設計**  
   - まず型定義（値オブジェクト、エンティティ、Result 型など）を行い、ドメインの言語を型で表現します。

2. **純粋関数から実装**  
   - 外部依存のない純粋関数を先に実装し、テストを先に書きます（TDD）。

3. **副作用を分離**  
   - IO 操作や外部通信は関数の境界に押し出し、必要ならば async/await や同期処理と分離します。

4. **アダプター実装**  
   - 外部サービスやデータベースアクセスはアダプターパターンで抽象化し、テスト用のモック実装を用意します。

---

## プラクティス

- 小さく始め、段階的に拡張する  
- 過度な抽象化は避け、必要な箇所のみ抽象化する  
- コードよりも型定義を重視し、ドメインのルールを型で表現する  
- 複雑さに応じて実装アプローチを調整する

---

## コードスタイル

- **関数優先:** 必要な場合のみクラスを使用（特にエンティティやリポジトリなど）
- **不変更新:** データは可能な限り不変（例: frozen dataclass）にする
- **早期リターン:** 条件分岐は早期リターンでフラットに
- **エラーとユースケースの列挙:** 可能ならエラーや状態を Enum で定義する

---

## テスト戦略

- 純粋関数の単体テストを最優先  
- インメモリ実装を用いたリポジトリのテストを実施  
- テスト可能性を最初から設計に組み込み、アサートファーストで期待結果を記述する
