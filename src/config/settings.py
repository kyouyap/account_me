"""設定管理モジュール。"""

from pathlib import Path
from typing import List

from pydantic import BaseModel
from pydantic_settings import BaseSettings


class SeleniumSettings(BaseModel):
    """Selenium関連の設定。"""

    download_directory: str
    timeout: int
    retry_count: int


class Endpoints(BaseModel):
    """MoneyForwardのエンドポイント設定。"""

    login: str
    accounts: str
    history: str


class SpecialRule(BaseModel):
    """特別なデータ処理ルール。"""

    institution: str
    action: str
    value: float


class MoneyForwardSettings(BaseModel):
    """MoneyForward関連の設定。"""

    base_url: str
    endpoints: Endpoints
    selenium: SeleniumSettings
    special_rules: List[SpecialRule]


class SpreadsheetColumn(BaseModel):
    """スプレッドシートの列設定。"""

    name: str
    col: int


class WorksheetSettings(BaseModel):
    """ワークシート設定。"""

    name: str
    start_row: int
    columns: List[SpreadsheetColumn]


class WorksheetsSettings(BaseModel):
    """全ワークシートの設定。"""

    household_data: WorksheetSettings
    assets_data: WorksheetSettings


class SpreadsheetSettings(BaseModel):
    """スプレッドシート全体の設定。"""

    worksheets: WorksheetsSettings


class AggregatedFilesSettings(BaseModel):
    """集計ファイルのパス設定。"""

    detail: str
    assets: str


class OutputsSettings(BaseModel):
    """出力関連のパス設定。"""

    base: str
    aggregated_files: AggregatedFilesSettings


class PathSettings(BaseModel):
    """パス関連の設定。"""

    outputs: OutputsSettings
    downloads: str
    credentials: str


class Settings(BaseSettings):
    """アプリケーション全体の設定。"""

    moneyforward: MoneyForwardSettings
    spreadsheet: SpreadsheetSettings
    paths: PathSettings

    @classmethod
    def load_from_yaml(cls, yaml_path: Path) -> "Settings":
        """YAMLファイルから設定を読み込む。

        Args:
            yaml_path: 設定ファイルのパス。

        Returns:
            Settings: 設定インスタンス。
        """
        import yaml

        with open(yaml_path, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f)
        return cls(**config_dict)


# シングルトンインスタンス
settings = Settings.load_from_yaml(
    Path(__file__).parent.parent.parent / "config/settings.yaml"
)
