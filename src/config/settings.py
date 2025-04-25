"""アプリケーション設定管理モジュール。

このモジュールは、MoneyForwardスクレイピングアプリケーションの設定を管理します。
Pydanticを使用して型安全な設定管理を実現し、YAMLファイルから設定を読み込みます。

主な機能:
    - MoneyForward関連設定の管理（エンドポイント、Selenium設定など）
    - スプレッドシート同期設定の管理（ワークシート、列設定など）
    - パス設定の管理（出力ディレクトリ、ダウンロードパスなど）

使用例:
    ```python
    from config.settings import settings

    # MoneyForwardのベースURL取得
    base_url = settings.moneyforward.base_url

    # スプレッドシートの設定取得
    sheet_settings = settings.spreadsheet.worksheets.household_data
    ```

Note:
    設定値は config/settings.yaml から読み込まれ、アプリケーション全体で
    シングルトンインスタンスとして使用されます。
"""

from pathlib import Path
from typing import List

from pydantic import BaseModel
from pydantic_settings import BaseSettings


class SeleniumSettings(BaseModel):
    """Seleniumブラウザ自動化の設定を管理します。

    Attributes:
        download_directory: ダウンロードファイルの保存先ディレクトリ
        timeout: 要素待機のタイムアウト時間（秒）
        retry_count: 操作失敗時のリトライ回数
    """

    download_directory: str
    timeout: int
    retry_count: int


class Endpoints(BaseModel):
    """MoneyForwardの各種エンドポイントURLを管理します。

    Attributes:
        login: ログインページのURL
        accounts: 口座一覧ページのURL
        history: 履歴データページのURL
    """

    login: str
    accounts: str
    history: str


class SpecialRule(BaseModel):
    """特定の金融機関に対する特別な処理ルールを定義します。

    Attributes:
        institution: 金融機関名
        action: 適用するアクション（例: "multiply", "add"など）
        value: アクションで使用する値
    """

    institution: str
    action: str
    value: float


class HistorySettings(BaseModel):
    """履歴データのダウンロード範囲を設定します。

    Attributes:
        months_to_download: ダウンロードする履歴の月数
    """

    months_to_download: int


class MoneyForwardSettings(BaseModel):
    """MoneyForwardサービスに関する全設定をまとめます。

    Attributes:
        base_url: サービスのベースURL
        endpoints: 各種エンドポイント設定
        selenium: ブラウザ自動化の設定
        special_rules: 特別なデータ処理ルールのリスト
        history: 履歴データ取得の設定
    """

    base_url: str
    endpoints: Endpoints
    selenium: SeleniumSettings
    special_rules: List[SpecialRule]
    history: HistorySettings


class SpreadsheetColumn(BaseModel):
    """スプレッドシートの列定義を管理します。

    Attributes:
        name: 列の名前（例: "日付", "金額"など）
        col: 列番号（1始まり）
    """

    name: str
    col: int


class WorksheetSettings(BaseModel):
    """個別のワークシートに関する設定を管理します。

    Attributes:
        name: ワークシート名
        start_row: データ開始行（ヘッダーを除く）
        columns: 列の設定リスト
    """

    name: str
    start_row: int
    columns: List[SpreadsheetColumn]


class WorksheetsSettings(BaseModel):
    """全ワークシートの設定。"""

    household_data: WorksheetSettings
    assets_data: WorksheetSettings


class SpreadsheetSettings(BaseModel):
    """スプレッドシート全体の設定を管理します。

    Attributes:
        worksheets: 家計データと資産データのワークシート設定
    """

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
    chrome_driver: str


class Settings(BaseSettings):
    """アプリケーション全体の設定を管理するメインクラス。

    このクラスは、YAMLファイルから設定を読み込み、型安全な設定オブジェクトを
    提供します。アプリケーション全体でシングルトンとして使用されます。

    Attributes:
        moneyforward: MoneyForward関連の設定
        spreadsheet: スプレッドシート関連の設定
        paths: 各種パス設定
    """

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
