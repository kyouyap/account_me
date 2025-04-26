"""MoneyForwardからのファイルダウンロードを管理するモジュール。

このモジュールは、MoneyForwardからのCSVファイルダウンロードを管理し、
ダウンロードディレクトリの操作やファイルの保存を制御します。urllib3を使用した
HTTPダウンロードとSeleniumを組み合わせて安定したファイル取得を実現します。

主な機能:
    - ダウンロードディレクトリの管理（作成、クリーンアップ）
    - HTTPSを使用したファイルダウンロード
    - 複数リンクからの一括ダウンロード
    - ダウンロード状態の監視と再試行

Note:
    - ダウンロードには適切なセッションクッキーが必要です
    - 一時ファイルは自動的にクリーンアップされます

"""

import logging
import os
import shutil
import time
from pathlib import Path

import urllib3
from exceptions.custom_exceptions import DownloadError
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from config.settings import settings

logger = logging.getLogger(__name__)


class FileDownloader:
    """ファイルダウンロードを管理するクラス。

    このクラスは、MoneyForwardからのファイルダウンロードを管理し、
    ダウンロードディレクトリの操作やファイルの保存を制御します。
    urllib3を使用したHTTPダウンロードとSeleniumを組み合わせて実装されています。

    Attributes:
        download_dir (Path): ダウンロードファイルの保存先ディレクトリ
        http (urllib3.PoolManager): HTTPリクエスト用のコネクションプール

    使用例:
        ```python
        downloader = FileDownloader(Path("/path/to/downloads"))
        downloader.prepare_download_dir()
        downloaded_files = downloader.download_from_links(driver, links)
        ```

    """

    def __init__(self, download_dir: Path) -> None:
        """FileDownloaderを初期化します。

        Args:
            download_dir: ダウンロードディレクトリのパス。
        """
        self.download_dir = download_dir
        self.http = urllib3.PoolManager()

    def prepare_download_dir(self) -> None:
        """ダウンロードディレクトリを作成し、準備します。

        ディレクトリが存在しない場合は作成し、既に存在する場合は
        そのまま使用します。
        """
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def clean_download_dir(self) -> None:
        """ダウンロードディレクトリ内のファイルを全て削除します。

        ディレクトリ内の全てのファイルを削除し、クリーンな状態にします。
        削除したファイル数はログに記録されます。
        """
        try:
            for file in self.download_dir.glob("*"):
                file.unlink()
            files_count = len(list(self.download_dir.glob("*")))
            logger.info(
                "ダウンロードディレクトリをクリーンアップしました: %s"
                "（削除ファイル数: %d）",
                self.download_dir,
                files_count,
            )
        except Exception as e:
            logger.warning(
                "ダウンロードディレクトリのクリーンアップに失敗しました: %s", e
            )

    def get_latest_downloaded_file(self) -> Path | None:
        """ダウンロードディレクトリから最新のダウンロードファイルを取得します。

        ダウンロードディレクトリ内の'download'で始まるファイルの中から、
        最も新しく作成されたファイルを返します。

        Returns:
            Path | None: 最新のファイルパス。ファイルが存在しない場合はNone。
        """
        files = list(self.download_dir.glob("download*"))
        return max(files, key=os.path.getctime) if files else None

    def convert_cookies(self, selenium_cookies: list[dict]) -> dict[str, str]:
        """Seleniumのクッキー形式をurllib3形式に変換します。

        Seleniumで取得したクッキー情報をHTTPリクエストで使用可能な
        形式に変換します。変換されたクッキーは、name-value形式の
        辞書として返されます。

        Args:
            selenium_cookies: Seleniumで取得したクッキー情報のリスト

        Returns:
            dict[str, str]: urllib3で使用可能な形式のクッキー辞書
        """
        return {cookie["name"]: cookie["value"] for cookie in selenium_cookies}

    def download_file(
        self,
        driver: WebDriver,
        download_url: str,
        output_path: Path | None = None,
        wait_time: int = 5,
    ) -> Path | None:
        """指定されたURLからファイルをダウンロードします。

        Seleniumのセッション情報を使用してファイルをダウンロードし、
        指定されたパスに保存します。ダウンロード後、一定時間待機して
        ファイルの書き込みが完了するのを待ちます。

        Args:
            driver: SeleniumのWebDriverインスタンス
            download_url: ダウンロードするファイルのURL
            output_path: 保存先のパス（Noneの場合は一時ファイルとして保存）
            wait_time: ダウンロード完了待機時間（秒）

        Returns:
            Path | None: ダウンロードしたファイルのパス。失敗時はNone。

        Raises:
            DownloadError: 以下の場合に発生:
                - HTTPリクエストが失敗
                - ファイルの書き込みに失敗
                - その他の予期せぬエラー
        """
        try:
            # クッキー情報を取得して変換
            cookies = self.convert_cookies(driver.get_cookies())
            headers = {
                "Cookie": "; ".join(
                    [f"{name}={value}" for name, value in cookies.items()]
                )
            }

            # ファイルをダウンロード
            response = self.http.request("GET", download_url, headers=headers)
            if response.status != 200:
                raise DownloadError(
                    f"ダウンロードに失敗しました。ステータスコード: {response.status}"
                )

            # 一時ファイルとして保存
            temp_path = self.download_dir / "download.csv"
            with open(temp_path, "wb") as f:
                f.write(response.data)

            # 指定された待機時間だけ待機
            time.sleep(wait_time)

            # ファイルの移動（必要な場合）
            if output_path:
                os.makedirs(output_path.parent, exist_ok=True)
                shutil.move(str(temp_path), str(output_path))
                return output_path
            return temp_path

        except urllib3.exceptions.HTTPError as e:
            raise DownloadError(f"HTTPエラーが発生しました: {e}") from e
        except OSError as e:
            raise DownloadError(f"ファイル操作エラーが発生しました: {e}") from e
        except Exception as e:
            raise DownloadError(
                f"ダウンロード中に予期せぬエラーが発生しました: {e}"
            ) from e

    def _download_history_page(
        self, driver: WebDriver, link: str, base_name: str, index: int
    ) -> Path | None:
        """履歴ページからファイルをダウンロードします。

        Args:
            driver: Seleniumのドライバーインスタンス
            link: ダウンロード対象のURL
            base_name: 保存するファイルのベース名
            index: ファイル名に使用するインデックス

        Returns:
            Path | None: ダウンロードしたファイルのパス。失敗時はNone。
        """
        download_url = f"{link}/csv"
        output_path = self.download_dir / f"{base_name}_{index}.csv"
        return self.download_file(driver, download_url, output_path)

    def _download_monthly_data(
        self, driver: WebDriver, base_name: str, index: int, month: int
    ) -> Path | None:
        """指定された月のデータをダウンロードします。

        Args:
            driver: Seleniumのドライバーインスタンス
            base_name: 保存するファイルのベース名
            index: ファイル名に使用するインデックス
            month: ダウンロード対象の月（0が当月）

        Returns:
            Path | None: ダウンロードしたファイルのパス。失敗時はNone。
        """
        try:
            logger.info(
                "過去のデータをダウンロード中: %d/%d（%d月前のデータ）",
                month + 1,
                settings.moneyforward.history.months_to_download,
                month,
            )

            # 「前月」ボタンをクリック
            prev_button = driver.find_element(
                By.CSS_SELECTOR,
                ".btn.fc-button.fc-button-prev.spec-fc-button-click-attached",
            )
            prev_button.click()
            driver.implicitly_wait(settings.moneyforward.selenium.timeout)

            # ダウンロードボタンをクリック
            download_button = driver.find_element(By.PARTIAL_LINK_TEXT, "ダウンロード")
            download_button.click()
            driver.implicitly_wait(settings.moneyforward.selenium.timeout)

            # CSVファイルのリンクを取得
            csv_link = driver.find_element(
                By.PARTIAL_LINK_TEXT, "CSVファイル"
            ).get_attribute("href")

            if not csv_link:
                logger.warning(f"{month}月目のCSVリンクの取得に失敗しました")
                return None

            output_path = self.download_dir / f"{base_name}_{index}_{month}.csv"
            if downloaded_file := self.download_file(driver, csv_link, output_path):
                logger.info(
                    "ファイルのダウンロードが完了しました: %s",
                    downloaded_file.name,
                )
                return downloaded_file

            logger.warning(f"{month}月目のファイルダウンロードに失敗しました")
            return None

        except Exception as month_error:
            logger.error(f"{month}月目のダウンロードでエラーが発生: {month_error!s}")
            return None

    def _download_account_page(
        self, driver: WebDriver, link: str, base_name: str, index: int
    ) -> list[Path]:
        """アカウントページから複数月分のファイルをダウンロードします。

        Args:
            driver: Seleniumのドライバーインスタンス
            link: ダウンロード対象のURL
            base_name: 保存するファイルのベース名
            index: ファイル名に使用するインデックス

        Returns:
            list[Path]: ダウンロードに成功したファイルのパスのリスト

        Raises:
            DownloadError: アカウントページの処理に失敗した場合
        """
        logger.info("アカウントページへアクセス開始: %s", link)
        month_files = []

        try:
            driver.get(link)
            driver.implicitly_wait(settings.moneyforward.selenium.timeout)

            # 「今日」ボタンをクリック
            today_button = driver.find_element(
                By.CSS_SELECTOR,
                ".btn.fc-button.fc-button-today.spec-fc-button-click-attached",
            )
            today_button.click()

            # 設定された月数分のデータをダウンロード
            for month in range(settings.moneyforward.history.months_to_download):
                if downloaded_file := self._download_monthly_data(
                    driver, base_name, index, month
                ):
                    month_files.append(downloaded_file)

            if not month_files:
                logger.error("月次データのダウンロードが全て失敗しました")

            return month_files

        except Exception as e:
            logger.error(f"アカウントページの処理でエラーが発生: {e!s}")
            raise DownloadError(f"アカウントページの処理に失敗: {e!s}") from e

    def download_from_links(
        self, driver: WebDriver, links: list[str], base_name: str = "download"
    ) -> list[Path]:
        """複数のリンクからファイルをダウンロードします。

        MoneyForwardの口座情報ページと履歴ページの両方に対応し、
        各ページタイプに応じた適切なダウンロード処理を実行します。
        履歴ページの場合は指定された月数分のデータを取得します。

        Args:
            driver: Seleniumブラウザのインスタンス
            links: ダウンロード対象のURLリスト
            base_name: 保存するファイルのベース名（デフォルト: "download"）

        Returns:
            List[Path]: ダウンロードに成功したファイルのパスリスト

        Raises:
            DownloadError: 以下の場合に発生:
                - 全てのダウンロードが失敗
                - 最初のダウンロードが失敗
                - ファイルの保存に失敗
        """
        if not links:
            return []

        downloaded_files = []
        history_url = (
            f"{settings.moneyforward.base_url}{settings.moneyforward.endpoints.history}"
        )

        for i, link in enumerate(links):
            try:
                # 履歴ページの場合
                if history_url == link and (
                    downloaded_file := self._download_history_page(
                        driver, link, base_name, i
                    )
                ):
                    downloaded_files.append(downloaded_file)
                    continue

                # アカウントページの場合
                month_files = self._download_account_page(driver, link, base_name, i)
                if month_files:  # リストが空でない場合のみ追加
                    downloaded_files.extend(month_files)

            except Exception as e:
                logger.error(
                    "ファイルのダウンロードに失敗しました - "
                    "リンク: %s, 成功済みファイル数: %d",
                    link,
                    len(downloaded_files),
                )
                # 初回のダウンロードが失敗した場合のみエラーを発生
                if not downloaded_files:
                    raise DownloadError(
                        f"最初のダウンロードに失敗しました: {e!s}"
                    ) from e

        # 全てのダウンロードが失敗した場合
        if not downloaded_files:
            error_msg = (
                "ダウンロードに成功したファイルがありません。"
                "全てのダウンロードが失敗しました。"
            )
            logger.error(
                "ダウンロード処理が完全に失敗しました。ダウンロード試行数: %d",
                len(links),
            )
            raise DownloadError(error_msg)

        # 一部のダウンロードのみ成功した場合
        if len(downloaded_files) < len(links):
            logger.warning(
                "一部のダウンロードのみ成功しました。成功数: %d/%d",
                len(downloaded_files),
                len(links),
            )

        return downloaded_files
