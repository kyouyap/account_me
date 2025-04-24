"""ファイルダウンロードモジュール。"""

import logging
from pathlib import Path
from typing import Dict, List, Protocol, Optional

import urllib3
from urllib3.exceptions import HTTPError
from urllib3.response import BaseHTTPResponse, HTTPResponse # HTTPResponse もインポート

from exceptions.custom_exceptions import DownloadError
from scraper.files.file_manager import FileManager

logger = logging.getLogger(__name__)


class Downloader(Protocol):
    """ダウンロード処理インターフェース。"""

    def download_file(
        self,
        url: str,
        output_path: Path,
        cookies: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Path:
        """ファイルをダウンロード。

        Args:
            url: ダウンロードするファイルのURL。
            output_path: 保存先のパス。
            cookies: リクエストに使用するクッキー。
            headers: リクエストヘッダー。

        Returns:
            Path: ダウンロードしたファイルのパス。

        Raises:
            DownloadError: ダウンロードに失敗した場合。
        """
        ...

    def download_files(
        self,
        urls: List[str],
        output_dir: Path,
        cookies: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> List[Path]:
        """複数のファイルをダウンロード。

        Args:
            urls: ダウンロードするファイルのURLリスト。
            output_dir: 保存先ディレクトリ。
            cookies: リクエストに使用するクッキー。
            headers: リクエストヘッダー。

        Returns:
            List[Path]: ダウンロードしたファイルのパスリスト。

        Raises:
            DownloadError: ダウンロードに失敗した場合。
        """
        ...


class MoneyForwardDownloader:
    """MoneyForward用のダウンロード処理クラス。"""

    def __init__(self, file_manager: FileManager) -> None:
        """初期化。

        Args:
            file_manager: ファイル管理インスタンス。
        """
        self._file_manager = file_manager
        self._http = urllib3.PoolManager()
        self._default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }

    def _prepare_headers(
        self, cookies: Optional[Dict[str, str]], headers: Optional[Dict[str, str]]
    ) -> Dict[str, str]:
        """リクエストヘッダーを準備。

        Args:
            cookies: リクエストに使用するクッキー。
            headers: 追加のヘッダー。

        Returns:
            Dict[str, str]: 準備されたヘッダー。
        """
        request_headers = self._default_headers.copy()

        if cookies:
            cookie_string = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            request_headers["Cookie"] = cookie_string

        if headers:
            request_headers.update(headers)

        return request_headers

    def download_file(
        self,
        url: str,
        output_path: Path,
        cookies: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Path:
        """ファイルをダウンロード。

        Args:
            url: ダウンロードするファイルのURL。
            output_path: 保存先のパス。
            cookies: リクエストに使用するクッキー。
            headers: リクエストヘッダー。

        Returns:
            Path: ダウンロードしたファイルのパス。

        Raises:
            DownloadError: ダウンロードに失敗した場合。
        """
        # mypyエラーは無視: 型アノテーションは一旦 BaseHTTPResponse のままにする
        response: Optional[BaseHTTPResponse] = None
        try:
            logger.info("ファイルのダウンロードを開始: %s", url)

            # 保存先ディレクトリの準備
            self._file_manager.prepare_directory(output_path.parent)

            # ヘッダーの準備
            request_headers = self._prepare_headers(cookies, headers)

            # --- HTTPリクエスト実行 ---
            try:
                response = self._http.request(
                    "GET", url, headers=request_headers, preload_content=False
                )
            except HTTPError as e:
                logger.error("HTTPリクエスト中にエラーが発生: %s", e)
                # HTTPError起因のDownloadErrorを生成して送出
                raise DownloadError(f"HTTPリクエストエラーが発生しました: {e}") from e
            # ここでは広範なExceptionは捕捉せず、HTTPErrorのみを対象とする

            # --- レスポンス処理とファイル書き込み ---
                raise DownloadError(f"HTTPリクエスト中に予期せぬエラーが発生しました: {e}") from e

            # --- レスポンス処理とファイル書き込み ---
            # ここまで到達した場合、responseはNoneではないはず
            assert response is not None, "HTTPリクエスト成功後のはずがresponseがNoneです"
            try:
                if response.status != 200:
                    # ステータスコード起因のDownloadErrorはここで発生させる
                    response.release_conn()
                    raise DownloadError(
                        f"HTTPリクエストエラーが発生しました: ステータスコード: {response.status}"
                    )

                # ファイルに保存
                try:
                    with open(output_path, "wb") as f:
                        # stream() で例外が発生する可能性も考慮
                        for chunk in response.stream(32768):
                            f.write(chunk)
                except OSError as e: # ファイル書き込みエラー
                    logger.error("ファイル書き込みエラーが発生: %s", e)
                    raise DownloadError(f"ファイル書き込みエラーが発生しました: {e}") from e
                except Exception as e: # stream() などでの予期せぬエラー
                    logger.error("ファイル保存中に予期せぬエラーが発生: %s", e)
                    raise DownloadError(f"ファイル保存中に予期せぬエラーが発生しました: {e}") from e

                logger.info(
                    "ファイルのダウンロードが完了しました: %s（保存先: %s）",
                    url,
                    output_path,
                )
                return output_path

            except DownloadError: # ステータスコード起因 or ファイル保存中のDownloadErrorを再送出
                raise
            except Exception as e: # レスポンス処理中のその他の予期せぬエラー
                logger.error("レスポンス処理中に予期せぬエラーが発生: %s", e)
                raise DownloadError(f"レスポンス処理中に予期せぬエラーが発生しました: {e}") from e

        finally:
            # レスポンスがあれば必ずクローズする
            if response:
                response.release_conn()

    def download_files(
        self,
        urls: List[str],
        output_dir: Path,
        cookies: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> List[Path]:
        """複数のファイルをダウンロード。

        Args:
            urls: ダウンロードするファイルのURLリスト。
            output_dir: 保存先ディレクトリ。
            cookies: リクエストに使用するクッキー。
            headers: リクエストヘッダー。

        Returns:
            List[Path]: ダウンロードしたファイルのパスリスト。

        Raises:
            DownloadError: 全てのダウンロードが失敗した場合。
        """
        if not urls:
            logger.warning("ダウンロードするURLが指定されていません")
            return []

        downloaded_files: List[Path] = []
        errors: List[str] = []

        for i, url in enumerate(urls):
            try:
                output_path = output_dir / f"download_{i}.csv"
                downloaded_file = self.download_file(url, output_path, cookies, headers)
                downloaded_files.append(downloaded_file)
            except Exception as e:
                logger.error("ファイル '%s' のダウンロードに失敗: %s", url, e)
                errors.append(f"{url}: {str(e)}")
                continue

        if not downloaded_files and errors:
            error_msg = "\n".join(errors)
            raise DownloadError(
                f"全てのダウンロードが失敗しました。エラー:\n{error_msg}"
            )

        return downloaded_files
