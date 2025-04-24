"""設定管理の基底モジュール。"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar, cast

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="BaseAppSettings")


class BaseAppModel(BaseModel):
    """アプリケーション設定のベースモデル。"""

    @field_validator("*")
    def validate_path_strings(cls, v: Any) -> Any:
        """パス文字列を検証し、必要に応じてPathオブジェクトに変換。

        Args:
            v: 検証する値。

        Returns:
            Any: 検証・変換後の値。
        """
        if isinstance(v, str) and ("path" in v or "dir" in v):
            path = Path(v).expanduser().resolve()
            if "dir" in v and not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                logger.info("ディレクトリを作成しました: %s", path)
            return path
        return v


class BaseAppSettings(BaseSettings):
    """アプリケーション設定の基底クラス。"""

    config_path: Path = Field(
        default=Path("config/settings.yaml"), description="設定ファイルのパス"
    )
    env_prefix: str = Field(default="APP_", description="環境変数のプレフィックス")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        validate_assignment=True,
    )

    @classmethod
    def load_yaml(cls, yaml_path: Optional[Path] = None) -> Dict[str, Any]:
        """YAMLファイルから設定を読み込む。

        Args:
            yaml_path: 設定ファイルのパス。

        Returns:
            Dict[str, Any]: 読み込んだ設定。

        Raises:
            FileNotFoundError: 設定ファイルが見つからない場合。
            yaml.YAMLError: YAMLの解析に失敗した場合。
        """
        default_path = cls.model_fields["config_path"].default
        yaml_path = yaml_path or default_path
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning("設定ファイルが見つかりません: %s", yaml_path)
            return {}
        except yaml.YAMLError as e:
            logger.error("YAML設定ファイルの解析に失敗: %s", e)
            raise

    @classmethod
    def load(
        cls: Type[T],
        yaml_path: Optional[Path] = None,
        env_file: Optional[str] = None,
        **kwargs,
    ) -> T:
        """環境変数とYAMLファイルから設定をロード。

        Args:
            yaml_path: 設定ファイルのパス。
            env_file: .envファイルのパス。
            **kwargs: その他の設定値。

        Returns:
            T: 設定インスタンス。
        """
        # YAML設定の読み込み
        yaml_config = cls.load_yaml(yaml_path)

        # 環境変数ファイルの設定
        config_dict = SettingsConfigDict(**cls.model_config)
        if env_file:
            config_dict["env_file"] = env_file
        cls.model_config = config_dict

        # インスタンスの作成（優先順位: kwargs > 環境変数 > YAML）
        settings = cls(**{**yaml_config, **kwargs})
        logger.info("設定を読み込みました: %s", settings.__class__.__name__)
        return settings

    def save_yaml(self, yaml_path: Optional[Path] = None) -> None:
        """設定をYAMLファイルに保存。

        Args:
            yaml_path: 保存先のパス。
        """
        yaml_path = yaml_path or self.config_path
        yaml_path.parent.mkdir(parents=True, exist_ok=True)

        # 機密情報を除外（json_schema_extraのsensitiveフラグをチェック）
        config = {}
        for name, field in self.model_fields.items():
            if not (field.json_schema_extra or {}).get("sensitive", False):
                value = getattr(self, name)
                if isinstance(value, Path):
                    value = str(value)
                config[name] = value

        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, allow_unicode=True)
        logger.info("設定を保存しました: %s", yaml_path)

    def update(self, **kwargs: Any) -> None:
        """設定値を更新。

        Args:
            **kwargs: 更新する設定値。
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                logger.info("設定を更新しました: %s = %s", key, value)
            else:
                logger.warning("未定義の設定キー: %s", key)
