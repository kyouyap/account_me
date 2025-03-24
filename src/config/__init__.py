"""設定管理モジュール。"""

from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv


class ConfigurationError(Exception):
    """設定エラーを表す例外クラス。"""


class Config:
    """アプリケーション設定を管理するクラス。"""

    _instance = None
    _initialized = False

    def __new__(cls):
        """シングルトンパターンの実装。"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """設定の初期化。"""
        if self._initialized:
            return

        self.config_dir = Path("/app/config")
        self._load_settings()
        self._load_env()
        self._initialized = True

    def _load_settings(self) -> None:
        """YAML設定ファイルを読み込む。"""
        settings_path = self.config_dir / "settings.yaml"
        try:
            if not settings_path.exists():
                raise FileNotFoundError(
                    f"設定ファイルが見つかりません: {settings_path}"
                )

            if not settings_path.is_file():
                raise ConfigurationError(
                    f"設定ファイルが正しくありません: {settings_path}"
                )

            with open(settings_path, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip():
                    raise ConfigurationError(f"設定ファイルが空です: {settings_path}")
                self.settings = yaml.safe_load(content)
                if not isinstance(self.settings, dict):
                    raise ConfigurationError(
                        f"設定ファイルの形式が正しくありません: {settings_path}"
                    )
        except FileNotFoundError as e:
            raise ConfigurationError(str(e))
        except (yaml.YAMLError, OSError) as e:
            raise ConfigurationError(
                f"設定ファイルの読み込みに失敗: {settings_path}: {e}"
            )

    def _load_env(self) -> None:
        """環境変数を読み込む。"""
        load_dotenv()

    def get_setting(self, *keys: str) -> Any:
        """
        設定値を取得する。

        Args:
            *keys: 設定値へのパスを表すキーのシーケンス。

        Returns:
            Any: 設定値。

        Raises:
            ConfigurationError: 設定値が見つからない場合。
        """
        value = self.settings
        for key in keys:
            try:
                value = value[key]
            except (KeyError, TypeError):
                raise ConfigurationError(f"設定が見つかりません: {'.'.join(keys)}")
        return value

    @property
    def moneyforward(self) -> Dict[str, Any]:
        """MoneyForward関連の設定を取得する。"""
        return self.get_setting("moneyforward")

    @property
    def spreadsheet(self) -> Dict[str, Any]:
        """スプレッドシート関連の設定を取得する。"""
        return self.get_setting("spreadsheet")

    @property
    def paths(self) -> Dict[str, Any]:
        """パス関連の設定を取得する。"""
        return self.get_setting("paths")


config = Config()

__all__ = ["config"]
