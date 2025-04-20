---
name: uv-script Python
groups:
  - read
  - edit
  - command
  - mcp
source: "project"
---

## 実装モード: スクリプトモード

- 外部依存を可能な限り減らし、一つのファイル内に全ての処理（実装＋テスト）を完結させる。
- テストコードも同じファイルに記述する。
- スクリプトモードは、ファイル冒頭に `# @script` というコメントが含まれている場合、または `scripts/` や `script/` 以下のファイルが対象となる。

スクリプトモードの例

```python
# @script
"""
足し算を行うモジュール
"""

def add(a: int, b: int) -> int:
  return a + b

# メイン実行部：直接実行時のエントリーポイント
if __name__ == "__main__":
  print(add(1, 2))

# --- テストコード ---
import pytest

def test_add():
  assert add(1, 2) == 3, "1 + 2 は 3 であるべき"

# 'test' 引数を付与して実行するとテストが動作するようにする（例: python script.py test）
if __name__ == "__main__" and 'test' in sys.argv:
  pytest.main()
```

CLINE/Roo のようなコーディングエージェントは、まず `python script.py` で実行して動作確認を行い、要求に応じてテストコードを充実させ、後に必要に応じてモジュールモードに移行していきます。

### 依存関係について

- スクリプトモードでは、曖昧な import（たとえば標準ライブラリ以外のライブラリの利用）は許容されるものの、可能な限り安定したバージョンを利用してください。  
- 具体的には、必要な外部ライブラリは事前に `requirements.txt` や `pyproject.toml` で管理し、pip などでインストール済みであることを前提とします。

**優先順の例**

- 可能であれば、特定バージョンのライブラリは管理ファイル（pyproject.toml など）で固定する  
- 標準ライブラリを優先する  
- 外部ライブラリの利用は必要最小限に留める

```python
# OKな例
import requests  # pip install requests でインストール済み

```

最初はスクリプトモードで検証を行い、必要に応じてモジュールモード（複数ファイル構成）に移行してください。


