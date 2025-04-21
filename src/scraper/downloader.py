"""ファイルダウンロードモジュール。"""

import logging
import os
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional

import urllib3
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from config.settings import settings
from exceptions.custom_exceptions import DownloadError

logger = logging.getLogger(__name__)


class FileDownloader:
    """ファイルダウンロードを管理するクラス。"""

    def __init__(self, download_dir: Path) -> None:
        """
        Args:
            download_dir: ダウンロードディレクトリのパス。
        """
        self.download_dir = download_dir
        self.http = urllib3.PoolManager()

    def prepare_download_dir(self) -> None:
        """ダウンロードディレクトリを準備。"""
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def clean_download_dir(self) -> None:
        """ダウンロードディレクトリをクリーンアップ。"""
        try:
            for file in self.download_dir.glob("*"):
                file.unlink()
            files_count = len(list(self.download_dir.glob("*")))
            logger.info(
                "ダウンロードディレクトリをクリーンアップしました: %s（削除ファイル数: %d）",
                self.download_dir,
                files_count,
            )
        except Exception as e:
            logger.warning(
                "ダウンロードディレクトリのクリーンアップに失敗しました: %s", e
            )

    def get_latest_downloaded_file(self) -> Optional[Path]:
        """最新のダウンロードファイルを取得。

        Returns:
            Optional[Path]: 最新のファイルパス、ファイルがない場合はNone。
        """
        files = list(self.download_dir.glob("download*"))
        return max(files, key=os.path.getctime) if files else None

    def convert_cookies(self, selenium_cookies: List[Dict]) -> Dict[str, str]:
        """Seleniumのクッキーをurllib3形式に変換。

        Args:
            selenium_cookies: Seleniumで取得したクッキー情報。

        Returns:
            Dict[str, str]: urllib3用のクッキー文字列。
        """
        return {cookie["name"]: cookie["value"] for cookie in selenium_cookies}

    def download_file(
        self,
        driver: WebDriver,
        download_url: str,
        output_path: Optional[Path] = None,
        wait_time: int = 5,
    ) -> Optional[Path]:
        """ファイルをダウンロード。

        Args:
            driver: SeleniumのWebDriverインスタンス。
            download_url: ダウンロードするファイルのURL。
            output_path: 保存先のパス（Noneの場合はデフォルトパスを使用）。
            wait_time: ダウンロード待機時間（秒）。

        Returns:
            Optional[Path]: ダウンロードしたファイルのパス。失敗時はNone。

        Raises:
            DownloadError: ダウンロードに失敗した場合。
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

    def download_from_links(
        self, driver: WebDriver, links: List[str], base_name: str = "download"
    ) -> List[Path]:
        """複数のリンクからファイルをダウンロード。

        Args:
            driver: SeleniumのWebDriverインスタンス。
            links: ダウンロードするファイルのURLリスト。
            base_name: 出力ファイルのベース名。

        Returns:
            List[Path]: ダウンロードしたファイルのパスリスト。

        Raises:
            DownloadError: ダウンロードに失敗した場合。
        """
        downloaded_files = []
        for i, link in enumerate(links):
            try:
                if (
                    f"{settings.moneyforward.base_url}{settings.moneyforward.endpoints.history}"
                    == link
                ):
                    # 履歴ページの場合
                    download_url = f"{link}/csv"
                    output_path = self.download_dir / f"{base_name}_{i}.csv"
                    downloaded_file = self.download_file(
                        driver, download_url, output_path
                    )
                    if downloaded_file:
                        downloaded_files.append(downloaded_file)
                else:
                    # アカウントページの場合
                    logger.info("アカウントページへアクセス開始: %s", link)
                    month_files = []  # この月のダウンロードファイル
                    
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
                        months = settings.moneyforward.history.months_to_download
                        for j in range(months):
                            try:
                                logger.info(
                                    "過去のデータをダウンロード中: %d/%d（%d月前のデータ）",
                                    j + 1,
                                    months,
                                    j,
                                )

                                # 「前月」ボタンをクリック
                                prev_button = driver.find_element(
                                    By.CSS_SELECTOR,
                                    ".btn.fc-button.fc-button-prev.spec-fc-button-click-attached",
                                )
                                prev_button.click()
                                driver.implicitly_wait(settings.moneyforward.selenium.timeout)

                                # ダウンロードボタンをクリック
                                download_button = driver.find_element(
                                    By.PARTIAL_LINK_TEXT, "ダウンロード"
                                )
                                download_button.click()
                                driver.implicitly_wait(settings.moneyforward.selenium.timeout)

                                # CSVファイルのリンクを取得
                                csv_link = driver.find_element(
                                    By.PARTIAL_LINK_TEXT, "CSVファイル"
                                ).get_attribute("href")

                                if csv_link:
                                    output_path = self.download_dir / f"{base_name}_{i}_{j}.csv"
                                    downloaded_file = self.download_file(
                                        driver, csv_link, output_path
                                    )
                                    if downloaded_file and downloaded_file.exists():
                                        month_files.append(downloaded_file)
                                        logger.info(
                                            "ファイルのダウンロードが完了しました: %s（サイズ: %.2f KB）",
                                            downloaded_file.name,
                                            downloaded_file.stat().st_size / 1024,
                                        )
                                    else:
                                        logger.warning(f"{j}月目のファイルダウンロードに失敗しました")
                            except Exception as month_error:
                                logger.error(f"{j}月目のダウンロードでエラーが発生: {str(month_error)}")
                                continue
                        
                        # 月次ダウンロードが1件でも成功していれば追加
                        if month_files:
                            downloaded_files.extend(month_files)
                        else:
                            logger.error("月次データのダウンロードが全て失敗しました")
                            
                    except Exception as account_error:
                        logger.error(f"アカウントページの処理でエラーが発生: {str(account_error)}")
                        if not downloaded_files:  # まだ1件もダウンロードできていない場合
                            raise DownloadError(f"アカウントページの処理に失敗: {str(account_error)}")

            except Exception as e:
                error_msg = str(e)
                logger.error(
                    "ファイルのダウンロードに失敗しました - リンク: %s, 成功済みファイル数: %d",
                    link,
                    len(downloaded_files),
                )
                # 一部成功している場合は継続、全て失敗している場合は中断
                if not downloaded_files:
                    raise DownloadError(f"最初のダウンロードに失敗しました: {str(e)}")
                continue

        if not downloaded_files and links:
            error_msg = "ダウンロードに成功したファイルがありません。全てのダウンロードが失敗しました。"
            logger.error(
                "ダウンロード処理が完全に失敗しました。ダウンロード試行数: %d",
                len(links),
            )
            raise DownloadError(error_msg)
        else:
            if links and len(downloaded_files) < len(links):
                logger.warning(
                    "一部のダウンロードのみ成功しました。成功数: %d/%d",
                    len(downloaded_files),
                    len(links),
                )
            return downloaded_files
