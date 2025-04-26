#!/usr/bin/env python3
"""プロンプトファイルとカスタムモード定義を処理するスクリプト

このスクリプトは以下の処理を行います：
1. rules/ ディレクトリ内の Markdown プロンプトファイルを結合して
   .clinerules ファイルを生成
2. roomodes/ ディレクトリ内のカスタムモード定義（Markdown）を読み込んで
   .roomodes ファイルを生成
3. カスタムモードの一覧を .clinerules ファイルの末尾に追加

生成されるファイル:
- .clinerules: AI アシスタント用のプロンプト定義
- .roomodes: カスタムモード設定の JSON ファイル
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# 現在のスクリプトのディレクトリを取得
SCRIPT_DIR = Path(__file__).parent
RULES_DIR = SCRIPT_DIR / "rules"
ROO_MODES_DIR = SCRIPT_DIR / "roomodes"
OUTPUT_FILE = Path.cwd() / ".clinerules"


@dataclass
class RooMode:
    """RooModeの型定義"""

    slug: str
    name: str
    role_definition: str
    groups: list[str]
    source: str
    __filename: str

    def to_dict(self) -> dict[str, Any]:
        """JSONシリアライズ用のディクショナリを返す"""
        return {
            "slug": self.slug,
            "name": self.name,
            "roleDefinition": self.role_definition,
            "groups": self.groups,
            "source": self.source,
            "__filename": self.__filename,
        }


def parse_front_matter(content: str) -> tuple[dict[str, Any], str]:
    """フロントマターを解析する"""
    front_matter_match = re.match(r"^---\n([\s\S]+?)\n---\n", content)
    if not front_matter_match:
        return {}, content

    front_matter = yaml.safe_load(front_matter_match.group(1))
    content_without_front_matter = content.replace(front_matter_match.group(0), "", 1)
    return front_matter, content_without_front_matter


def main() -> None:
    """メイン処理"""
    roomodes: dict[str, list[dict[str, Any]]] = {"customModes": []}

    # roomodesの処理
    if ROO_MODES_DIR.exists():
        for file in ROO_MODES_DIR.glob("*.md"):
            content = file.read_text(encoding="utf-8")
            slug = file.stem
            front_matter, body = parse_front_matter(content)

            mode = {
                **front_matter,
                "slug": slug,
                "roleDefinition": body,
                "__filename": str(file),
            }
            roomodes["customModes"].append(mode)

    try:
        # プロンプトファイルの読み込み
        files = sorted(
            [f for f in RULES_DIR.glob("*.md") if not f.name.startswith("_")]
        )

        # 各ファイルの内容を結合
        contents = []
        for file in files:
            content = file.read_text(encoding="utf-8")
            contents.append(content)

        # .clinerules に書き出し
        result = "\n\n".join(contents)

        if roomodes["customModes"]:
            result += "\nこのプロジェクトには以下のモードが定義されています:"
            for mode in roomodes["customModes"]:
                relative_path = Path(mode["__filename"]).relative_to(Path.cwd())
                result += (
                    f"\n- {mode['slug']} {mode.get('name', '')} at {relative_path}"
                )

        # .roomodes の生成
        roomodes_path = Path.cwd() / ".roomodes"
        roomodes_path.write_text(
            json.dumps(roomodes, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Generated .roomodes from {len(roomodes['customModes'])} mode files")

        # .clinerules の生成
        OUTPUT_FILE.write_text(result, encoding="utf-8")
        print(f"Generated {OUTPUT_FILE} from {len(files)} prompt files")

    except Exception as e:
        print(f"Error: {e!s}")
        raise


if __name__ == "__main__":
    main()
