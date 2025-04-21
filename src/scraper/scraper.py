"""スクレイピング処理を実行するメインモジュール。"""

import datetime
import logging
import os
from pathlib import Path
from typing import List

import pandas as pd

from config.settings import settings
from exceptions.custom_exceptions import MoneyForwardError
from scraper.browser import BrowserManager
from scraper.downloader import FileDownloader

logger = logging.getLogger(__name__)


class MoneyForwardScraper:
    """MoneyForwardのスクレイピングを実行するクラス。"""

    def __init__(self) -> None:
        """スクレイパーの初期化。"""
        self.download_dir = Path(settings.paths.downloads)
        self.browser_manager = BrowserManager()
        self.file_downloader = FileDownloader(self.download_dir)
        
        # シークレットを環境変数に設定
        from config.secrets import get_secrets
        get_secrets()

    def _check_env_variables(self) -> None:
        """必要な環境変数が設定されているか確認します。

        Raises:
            MoneyForwardError: 必要な環境変数が設定されていない場合。
        """
        required_vars = ["EMAIL", "PASSWORD"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise MoneyForwardError(
                f"環境変数が設定されていません: {', '.join(missing_vars)}"
            )

    def _clean_directories(self) -> None:
        """作業ディレクトリをクリーンアップします。"""
        try:
            self.file_downloader.clean_download_dir()
        except OSError as e:
            logger.error(
                "ダウンロードディレクトリのクリーンアップに失敗しました: %s", e
            )

        for directory in [
            Path(settings.paths.outputs.aggregated_files.detail),
            Path(settings.paths.outputs.aggregated_files.assets),
        ]:
            try:
                if directory.exists():
                    for file in directory.glob("*"):
                        try:
                            file.unlink()
                        except OSError as e:
                            logger.error("ファイルの削除に失敗しました %s: %s", file, e)
                else:
                    directory.mkdir(parents=True)
            except OSError as e:
                logger.error("ディレクトリの操作に失敗しました %s: %s", directory, e)

    def _read_csv_with_encoding(self, file_path: Path) -> pd.DataFrame | None:
        """複数のエンコーディングを試行してCSVファイルを読み込みます。

        Args:
            file_path: 読み込むCSVファイルのパス。

        Returns:
            pd.DataFrame | None: 読み込んだデータフレーム。読み込みに失敗した場合はNone。
        """
        # ファイルサイズチェック
        if file_path.stat().st_size == 0:
            logger.warning("CSVファイル '%s' が空のためスキップします", file_path)
            return None

        encodings = ["utf-8", "shift-jis", "cp932"]
        errors = []
        decode_errors = []

        for encoding in encodings:
            try:
                logger.info(
                    "ファイル '%s' をエンコーディング '%s' で読み込み試行中",
                    file_path,
                    encoding,
                )
                df = pd.read_csv(file_path, encoding=encoding)
                if df.empty:
                    logger.warning("CSVファイルにデータがありません")
                    continue

                logger.info(
                    "ファイル '%s' をエンコーディング '%s' で読み込みに成功",
                    file_path,
                    encoding,
                )
                return df
            except UnicodeDecodeError as e:
                logger.warning(
                    "エンコーディング '%s' での読み込みに失敗: %s",
                    encoding,
                    str(e),
                )
                decode_errors.append(f"{encoding}: {str(e)}")
            except Exception as e:
                logger.error(
                    "ファイル '%s' の読み込み中に予期せぬエラーが発生: %s",
                    file_path,
                    str(e),
                )
                errors.append(f"{encoding}: {str(e)}")

        if decode_errors:
            logger.error(
                "CSVファイル '%s' を読み込めませんでした。対応していないエンコーディングの可能性があります。\n詳細:\n%s",
                file_path,
                "\n".join(decode_errors),
            )
        elif errors:
            logger.error(
                "CSVファイル '%s' の読み込みに失敗しました: \n%s",
                file_path,
                "\n".join(errors),
            )
        return None

    def _aggregate_csv_files(self, output_path: Path) -> None:
        """CSVファイルを集約します。

        Args:
            output_path: 出力ファイルのパス。

        Raises:
            MoneyForwardError: CSVファイルの集約に失敗した場合。
        """
        try:
            # CSVファイルを読み込んで結合
            all_dfs: List[pd.DataFrame] = []
            csv_files = list(self.download_dir.glob("*.csv"))
            logger.info("集約対象のCSVファイル数: %d", len(csv_files))

            for file_path in csv_files:
                logger.info("ファイル '%s' の処理を開始", file_path)
                try:
                    df = self._read_csv_with_encoding(file_path)
                    if df is not None:
                        if "金額（円）" in df.columns and "保有金融機関" in df.columns:
                            # 金額カラムを事前に浮動小数点数型に変換
                            df["金額（円）"] = df["金額（円）"].astype(float)
                            # 初期設定ではアメリカン・エキスプレスカードの金額を半額に
                            for rule in settings.moneyforward.special_rules:
                                if rule.action == "divide_amount":
                                    mask = df["保有金融機関"] == rule.institution
                                    df.loc[mask, "金額（円）"] = (
                                        df.loc[mask, "金額（円）"] / rule.value
                                    )
                        all_dfs.append(df)
                except Exception as e:
                    logger.error(f"ファイル '{file_path}' の処理中にエラーが発生しました:", exc_info=True)
                    raise MoneyForwardError(f"CSVファイルの処理に失敗しました: {str(e)}") from e

            if all_dfs:
                # データを結合して重複を削除
                final_df = pd.concat(all_dfs).drop_duplicates().reset_index(drop=True)

                # ディレクトリが存在しない場合は作成
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # CSVファイルとして保存
                final_df.to_csv(output_path, index=False, encoding="utf-8-sig")
                logger.info(
                    "CSVファイルを集約しました: %s（レコード数: %d）",
                    output_path,
                    len(final_df),
                )
            else:
                logger.warning("集約するCSVファイルがありません。")
                return

        except Exception as e:
            logger.error("CSVファイルの集約中にエラーが発生しました:", exc_info=True)
            raise MoneyForwardError(f"CSVファイルの集約に失敗しました: {str(e)}") from e

    def _download_and_aggregate(
        self, browser: BrowserManager, endpoint: str, output_path: Path
    ) -> None:
        """指定されたエンドポイントからデータをダウンロードし集約します。

        Args:
            browser: ブラウザマネージャー
            endpoint: ダウンロード対象のエンドポイント
            output_path: 出力先のパス

        Raises:
            MoneyForwardError: データのダウンロードや集約に失敗した場合
        """
        links = browser.get_links_for_download(endpoint)
        logger.info("ダウンロードリンクを取得しました: %d件", len(links))

        self.file_downloader.download_from_links(browser.driver, links)
        self._aggregate_csv_files(output_path)

    def scrape(self) -> None:
        """スクレイピングを実行します。

        Raises:
            MoneyForwardError: スクレイピング処理に失敗した場合
        """
        try:
            self._check_env_variables()
            self._clean_directories()

            current_date = datetime.datetime.now().strftime("%Y%m%d")
            email = os.getenv("EMAIL")
            password = os.getenv("PASSWORD")

            if not email or not password:
                raise MoneyForwardError("EMAIL/PASSWORDが環境変数に設定されていません。")

            base_url = settings.moneyforward.base_url
            
            with self.browser_manager as browser:
                try:
                    browser.login(email, password)

                    # アカウントページ処理
                    detail_endpoint = f"{base_url}{settings.moneyforward.endpoints.accounts}"
                    detail_output = Path(settings.paths.outputs.aggregated_files.detail) / f"detail_{current_date}.csv"
                    self._download_and_aggregate(browser, detail_endpoint, detail_output)

                    # 履歴ページ処理
                    self.file_downloader.clean_download_dir()
                    history_endpoint = f"{base_url}{settings.moneyforward.endpoints.history}"
                    assets_output = Path(settings.paths.outputs.aggregated_files.assets) / f"assets_{current_date}.csv"
                    self._download_and_aggregate(browser, history_endpoint, assets_output)
                except Exception as e:
                    logger.error("ブラウザ操作中にエラーが発生しました:", exc_info=True)
                    error_message = f"スクレイピングに失敗しました。詳細:\n{e.__class__.__name__}: {str(e)}"
                    raise MoneyForwardError(error_message) from e

            self.file_downloader.clean_download_dir()
            logger.info("スクレイピングが完了しました。")

        except MoneyForwardError:
            raise
        except Exception as e:
            logger.error("スクレイピング中にエラーが発生しました:", exc_info=True)
            self.file_downloader.clean_download_dir()
            error_message = f"予期せぬエラーが発生しました。詳細:\n{e.__class__.__name__}: {str(e)}"
            raise MoneyForwardError(error_message) from e
