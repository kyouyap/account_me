"""設定管理モジュール。"""

import re
from pathlib import Path
from typing import List, Optional

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic.types import PositiveInt

from .base import BaseAppModel, BaseAppSettings


class AuthSettings(BaseAppModel):
    """認証関連の設定。"""

    email: str = Field(
        ...,
        description="ログインメールアドレス",
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
    )
    password: SecretStr = Field(
        ..., description="ログインパスワード", json_schema_extra={"sensitive": True}
    )
    two_factor_enabled: bool = Field(default=False, description="二要素認証の有効/無効")


class SeleniumSettings(BaseAppModel):
    """Selenium関連の設定。"""

    download_directory: Path = Field(..., description="ダウンロードディレクトリのパス")
    timeout: PositiveInt = Field(
        default=30, description="要素待機のタイムアウト時間（秒）"
    )
    retry_count: PositiveInt = Field(default=3, description="操作失敗時の再試行回数")


class Endpoints(BaseAppModel):
    """MoneyForwardのエンドポイント設定。"""

    login: str = Field(
        ..., description="ログインページのパス", pattern="^/[a-zA-Z0-9/_-]*$"
    )
    accounts: str = Field(
        ..., description="アカウントページのパス", pattern="^/[a-zA-Z0-9/_-]*$"
    )
    history: str = Field(
        ..., description="履歴ページのパス", pattern="^/[a-zA-Z0-9/_-]*$"
    )


class SpecialRule(BaseAppModel):
    """特別なデータ処理ルール。"""

    institution: str = Field(..., description="金融機関名", min_length=1)
    action: str = Field(
        ..., description="処理内容", pattern="^(multiply|divide|add|subtract)$"
    )
    value: float = Field(..., description="処理に使用する値", gt=0)


class HistorySettings(BaseAppModel):
    """履歴データ取得の設定。"""

    months_to_download: PositiveInt = Field(
        default=3, description="ダウンロードする月数", le=12
    )


class MoneyForwardSettings(BaseAppModel):
    """MoneyForward関連の設定。"""

    base_url: str = Field(
        ...,
        description="MoneyForwardのベースURL",
        pattern="^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    )
    auth: AuthSettings = Field(..., description="認証設定")
    endpoints: Endpoints = Field(..., description="各種エンドポイント設定")
    selenium: SeleniumSettings = Field(..., description="Selenium関連の設定")
    special_rules: List[SpecialRule] = Field(
        default_factory=list, description="特別な処理ルール"
    )
    history: HistorySettings = Field(
        default_factory=HistorySettings, description="履歴データ取得設定"
    )

    @field_validator("base_url")
    def validate_base_url(cls, v: str) -> str:
        """ベースURLのバリデーション。"""
        if not v.endswith("/"):
            v += "/"
        return v


class SpreadsheetColumn(BaseAppModel):
    """スプレッドシートの列設定。"""

    name: str = Field(..., description="列名", min_length=1)
    col: PositiveInt = Field(..., description="列番号（1始まり）")


class WorksheetSettings(BaseAppModel):
    """ワークシート設定。"""

    name: str = Field(..., description="ワークシート名", min_length=1)
    start_row: PositiveInt = Field(default=2, description="データ開始行（1始まり）")
    columns: List[SpreadsheetColumn]

    @model_validator(mode="after")
    def validate_columns(self) -> "WorksheetSettings":
        """列設定のバリデーション。"""
        # 列番号の重複チェック
        cols = [col.col for col in self.columns]
        if len(cols) != len(set(cols)):
            raise ValueError("列番号が重複しています")
        return self


class WorksheetsSettings(BaseAppModel):
    """全ワークシートの設定。"""

    household_data: WorksheetSettings
    assets_data: WorksheetSettings


class SpreadsheetSettings(BaseAppModel):
    """スプレッドシート全体の設定。"""

    worksheets: WorksheetsSettings


class AggregatedFilesSettings(BaseAppModel):
    """集計ファイルのパス設定。"""

    detail: Path = Field(..., description="明細データの出力先")
    assets: Path = Field(..., description="資産データの出力先")


class OutputsSettings(BaseAppModel):
    """出力関連のパス設定。"""

    base: Path = Field(..., description="出力のベースディレクトリ")
    aggregated_files: AggregatedFilesSettings


class PathSettings(BaseAppModel):
    """パス関連の設定。"""

    outputs: OutputsSettings
    downloads: Path = Field(..., description="ダウンロードディレクトリ")
    chrome_driver: Path = Field(..., description="ChromeDriverのパス")

    @model_validator(mode="after")
    def ensure_directories(self) -> "PathSettings":
        """ディレクトリの存在確認と作成。"""
        self.outputs.base.mkdir(parents=True, exist_ok=True)
        self.downloads.mkdir(parents=True, exist_ok=True)
        return self


class AppSettings(BaseAppSettings):
    """アプリケーション全体の設定。"""

    moneyforward: MoneyForwardSettings
    spreadsheet: SpreadsheetSettings
    paths: PathSettings

    @model_validator(mode="after")
    def setup_dependencies(self) -> "AppSettings":
        """設定間の依存関係を解決。"""
        # SeleniumのダウンロードディレクトリをPathSettingsと同期
        self.moneyforward.selenium.download_directory = self.paths.downloads
        return self


# シングルトンインスタンス
settings = AppSettings.load(
    yaml_path=Path(__file__).parent.parent.parent / "config/settings.yaml"
)
