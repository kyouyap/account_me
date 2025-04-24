"""Downloaderのテスト。"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import urllib3
from urllib3.response import HTTPResponse
from io import BytesIO

from scraper.files.downloader import MoneyForwardDownloader, DownloadError
from scraper.files.file_manager import FileManager


@pytest.fixture
def mock_file_manager():
    """FileManagerのモックを提供。"""
    return MagicMock(spec=FileManager)


@pytest.fixture
def mock_pool_manager():
    """urllib3.PoolManagerのモックを提供。"""
    with patch("urllib3.PoolManager") as mock:
        yield mock


@pytest.fixture
def mock_response():
    """HTTPResponseのモックを提供。"""
    response = MagicMock(spec=HTTPResponse)
    response.status = 200
    response.stream.return_value = [b"test content"]
    return response


@pytest.fixture
def downloader(mock_file_manager):
    """MoneyForwardDownloaderのインスタンスを提供。"""
    return MoneyForwardDownloader(mock_file_manager)


class TestMoneyForwardDownloader:
    """MoneyForwardDownloaderのテストクラス。"""

    def test_prepare_headers_with_cookies(self, downloader):
        """クッキー付きヘッダーの準備テスト。"""
        cookies = {"session": "abc123"}
        headers = downloader._prepare_headers(cookies, None)
        assert "Cookie" in headers
        assert headers["Cookie"] == "session=abc123"

    def test_prepare_headers_with_additional_headers(self, downloader):
        """追加ヘッダーの準備テスト。"""
        additional_headers = {"X-Test": "test"}
        headers = downloader._prepare_headers(None, additional_headers)
        assert headers["X-Test"] == "test"
        assert "User-Agent" in headers  # デフォルトヘッダーが含まれていることを確認

    def test_download_file_success(
        self, downloader, mock_file_manager, mock_pool_manager, mock_response, tmp_path
    ):
        """ファイルダウンロード成功のテスト。"""
        # モックの設定
        mock_response.status = 200  # ステータスを明示的に設定
        mock_pool_manager.return_value.request.return_value = mock_response
        output_path = tmp_path / "test.csv"

        # ダウンロードの実行
        result = downloader.download_file(
            "http://example.com/test.csv", output_path, cookies={"session": "abc123"}
        )

        # 検証
        assert result == output_path
        mock_file_manager.prepare_directory.assert_called_once_with(output_path.parent)
        mock_pool_manager.return_value.request.assert_called_once()
        mock_response.release_conn.assert_called_once()  # finallyブロックで呼ばれることを確認

    def test_download_file_http_error(
        self, downloader, mock_file_manager, mock_pool_manager, tmp_path
    ):
        """HTTPエラー時のテスト。"""
        mock_response = MagicMock(spec=HTTPResponse)
        mock_response.status = 404
        mock_response.release_conn = MagicMock()
        mock_pool_manager.return_value.request.return_value = mock_response

        output_path = tmp_path / "test.csv"

        with pytest.raises(DownloadError) as excinfo:
            downloader.download_file("http://example.com/test.csv", output_path)

        assert "ダウンロードに失敗しました" in str(excinfo.value)
        mock_response.release_conn.assert_called_once()

    def test_download_file_network_error(
        self, downloader, mock_file_manager, mock_pool_manager, tmp_path
    ):
        """ネットワークエラー時のテスト。"""
        mock_pool_manager.return_value.request.side_effect = (
            urllib3.exceptions.HTTPError("Connection failed")
        )
        output_path = tmp_path / "test.csv"

        with pytest.raises(DownloadError) as excinfo:
            downloader.download_file("http://example.com/test.csv", output_path)
        # downloader.py の修正に合わせて期待されるエラーメッセージを修正
        assert "HTTPリクエストエラーが発生しました" in str(excinfo.value)
        # 元の例外が原因として設定されていることを確認
        assert isinstance(excinfo.value.__cause__, urllib3.exceptions.HTTPError)
        assert "Connection failed" in str(excinfo.value.__cause__)

    def test_download_files_success(
        self, downloader, mock_file_manager, mock_pool_manager, mock_response, tmp_path
    ):
        """複数ファイルダウンロード成功のテスト。"""
        mock_response.status = 200  # ステータスを明示的に設定
        mock_response.release_conn = MagicMock()
        mock_pool_manager.return_value.request.return_value = mock_response
        urls = ["http://example.com/1.csv", "http://example.com/2.csv"]

        results = downloader.download_files(urls, tmp_path)

        assert len(results) == 2
        assert all(isinstance(path, Path) for path in results)
        assert mock_pool_manager.return_value.request.call_count == 2
        assert mock_response.release_conn.call_count == 2

    def test_download_files_partial_failure(
        self, downloader, mock_file_manager, mock_pool_manager, tmp_path # mock_response は使わない
    ):
        """一部のファイルダウンロードが失敗するケースのテスト。"""
        # 1つ目は成功、2つ目は失敗するように設定
        success_response = MagicMock(spec=HTTPResponse)
        success_response.status = 200 # 成功レスポンスのステータスを明示的に設定
        success_response.stream.return_value = [b"success content"]
        success_response.release_conn = MagicMock()

        error_response = MagicMock(spec=HTTPResponse)
        error_response.status = 404
        error_response.release_conn = MagicMock()

        # side_effect に独立したモックを設定
        mock_pool_manager.return_value.request.side_effect = [
            success_response,
            error_response,
        ]
        urls = ["http://example.com/1.csv", "http://example.com/2.csv"]

        results = downloader.download_files(urls, tmp_path)

        assert len(results) == 1  # 1つだけ成功
        assert mock_pool_manager.return_value.request.call_count == 2
        success_response.release_conn.assert_called_once() # 成功レスポンスのモックを確認
        error_response.release_conn.assert_called_once()

    def test_download_files_all_failure(
        self, downloader, mock_file_manager, mock_pool_manager, tmp_path
    ):
        """全てのファイルダウンロードが失敗するケースのテスト。"""
        error_response = MagicMock(spec=HTTPResponse)
        error_response.status = 404
        error_response.release_conn = MagicMock()
        mock_pool_manager.return_value.request.return_value = error_response

        urls = ["http://example.com/1.csv", "http://example.com/2.csv"]

        with pytest.raises(DownloadError) as excinfo:
            downloader.download_files(urls, tmp_path)

        assert "全てのダウンロードが失敗しました" in str(excinfo.value)
        assert error_response.release_conn.call_count == 2

    def test_download_files_empty_list(self, downloader, tmp_path):
        """空のURLリストでのテスト。"""
        results = downloader.download_files([], tmp_path)
        assert results == []

    def test_download_file_cleanup_on_error(
        self, downloader, mock_file_manager, mock_pool_manager, tmp_path
    ):
        """エラー時のリソースクリーンアップテスト。"""
        # レスポンスを取得した後にエラーが発生する状況を作成
        mock_response = MagicMock(spec=HTTPResponse)
        mock_response.status = 200
        mock_response.stream.side_effect = Exception("Stream error")
        mock_pool_manager.return_value.request.return_value = mock_response

        output_path = tmp_path / "test.csv"

        with pytest.raises(DownloadError):
            downloader.download_file("http://example.com/test.csv", output_path)

        # レスポンスがクローズされたことを確認
        mock_response.release_conn.assert_called_once()
