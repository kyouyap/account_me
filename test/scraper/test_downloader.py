"""FileDownloaderのテスト。"""

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import urllib3

from exceptions.custom_exceptions import DownloadError
from scraper.downloader import FileDownloader


@pytest.fixture
def mock_settings():
    """テスト用の設定をモック化。"""
    with patch("scraper.downloader.settings") as mock_settings:
        mock_settings.moneyforward.base_url = "http://example.com"
        mock_settings.moneyforward.endpoints.history = "/history"
        yield mock_settings


@pytest.fixture
def downloader(tmp_path):
    """テスト用のFileDownloaderインスタンスを生成。"""
    return FileDownloader(tmp_path)


@pytest.fixture
def sample_files(tmp_path):
    """テスト用のサンプルファイルを作成。"""
    files = []
    for i in range(3):
        file_path = tmp_path / f"test_file_{i}.txt"
        file_path.write_text(f"Test content {i}")
        files.append(file_path)
    return files


def test_init(tmp_path):
    """初期化のテスト。"""
    downloader = FileDownloader(tmp_path)
    assert downloader.download_dir == tmp_path
    assert isinstance(downloader.http, urllib3.PoolManager)


def test_prepare_download_dir(downloader):
    """ダウンロードディレクトリ準備のテスト。"""
    # ディレクトリが存在しない場合
    shutil.rmtree(downloader.download_dir, ignore_errors=True)
    assert not downloader.download_dir.exists()

    downloader.prepare_download_dir()
    assert downloader.download_dir.exists()
    assert downloader.download_dir.is_dir()

    # ディレクトリが既に存在する場合
    downloader.prepare_download_dir()
    assert downloader.download_dir.exists()


def test_clean_download_dir(downloader, sample_files):
    """ダウンロードディレクトリクリーンアップのテスト。"""
    # クリーンアップ前にファイルが存在することを確認
    assert len(list(downloader.download_dir.glob("*"))) == 3

    downloader.clean_download_dir()

    # クリーンアップ後にファイルが削除されていることを確認
    assert len(list(downloader.download_dir.glob("*"))) == 0


def test_clean_download_dir_error_handling(downloader):
    """クリーンアップのエラーハンドリングテスト。"""
    with patch("pathlib.Path.glob") as mock_glob:
        mock_glob.side_effect = Exception("テストエラー")
        downloader.clean_download_dir()  # エラーをキャッチして処理を継続


def test_get_latest_downloaded_file(downloader, sample_files):
    """最新ダウンロードファイル取得のテスト。"""
    # テスト用のダウンロードファイルを作成
    download_files = []
    for i in range(3):
        file_path = downloader.download_dir / f"download_{i}.csv"
        file_path.write_text(f"Test content {i}")
        download_files.append(file_path)

    latest_file = downloader.get_latest_downloaded_file()
    assert latest_file is not None
    assert latest_file.name == "download_2.csv"


def test_get_latest_downloaded_file_no_files(downloader):
    """ダウンロードファイルが存在しない場合のテスト。"""
    latest_file = downloader.get_latest_downloaded_file()
    assert latest_file is None


def test_convert_cookies(downloader):
    """クッキー変換のテスト。"""
    selenium_cookies = [
        {"name": "cookie1", "value": "value1"},
        {"name": "cookie2", "value": "value2"},
    ]

    converted_cookies = downloader.convert_cookies(selenium_cookies)
    assert converted_cookies == {"cookie1": "value1", "cookie2": "value2"}


def test_download_file_success_with_output_path(downloader):
    """ファイルダウンロード成功とファイル移動のテスト。"""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.data = b"Test content"

    with patch.object(downloader.http, "request") as mock_request:
        mock_request.return_value = mock_response

        driver = MagicMock()
        driver.get_cookies.return_value = [
            {"name": "test_cookie", "value": "test_value"}
        ]

        output_path = downloader.download_dir / "output" / "test.csv"
        result = downloader.download_file(
            driver, "http://example.com/test.csv", output_path=output_path, wait_time=0
        )

        assert result == output_path
        assert result.exists()
        assert result.read_bytes() == b"Test content"
        assert result.parent.exists()


def test_download_file_success(downloader):
    """ファイルダウンロード成功のテスト。"""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.data = b"Test content"

    with patch.object(downloader.http, "request") as mock_request:
        mock_request.return_value = mock_response

        driver = MagicMock()
        driver.get_cookies.return_value = [
            {"name": "test_cookie", "value": "test_value"}
        ]

        result = downloader.download_file(
            driver, "http://example.com/test.csv", wait_time=0
        )

        assert result is not None
        assert result.exists()
        assert result.read_bytes() == b"Test content"


def test_download_file_http_error(downloader):
    """HTTPエラー時のテスト。"""
    with patch.object(downloader.http, "request") as mock_request:
        mock_request.side_effect = urllib3.exceptions.HTTPError("HTTP Error")

        driver = MagicMock()
        with pytest.raises(DownloadError) as exc_info:
            downloader.download_file(driver, "http://example.com/test.csv")
        assert "HTTPエラーが発生しました" in str(exc_info.value)


def test_download_file_non_200_status(downloader):
    """非200ステータスコードのテスト。"""
    mock_response = MagicMock()
    mock_response.status = 404

    with patch.object(downloader.http, "request") as mock_request:
        mock_request.return_value = mock_response

        driver = MagicMock()
        with pytest.raises(DownloadError) as exc_info:
            downloader.download_file(driver, "http://example.com/test.csv")
        assert "ダウンロードに失敗しました" in str(exc_info.value)


def test_download_file_os_error(downloader):
    """ファイル操作エラーのテスト。"""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.data = b"Test content"

    with (
        patch.object(downloader.http, "request") as mock_request,
        patch("builtins.open") as mock_open,
    ):
        mock_request.return_value = mock_response
        mock_open.side_effect = OSError("File error")

        driver = MagicMock()
        with pytest.raises(DownloadError) as exc_info:
            downloader.download_file(driver, "http://example.com/test.csv")
        assert "ファイル操作エラーが発生しました" in str(exc_info.value)


@pytest.mark.parametrize(
    "links,expected_paths",
    [
        (
            ["http://example.com/account"],
            [Path("test1_0_0.csv")],
        ),
        (
            ["http://example.com/history"],
            [Path("test2_0.csv")],
        ),
    ],
)
def test_download_from_links_success(downloader, mock_settings, links, expected_paths):
    """複数リンクからのダウンロード成功テスト。"""
    mock_driver = MagicMock()
    mock_element = MagicMock()
    mock_element.get_attribute.return_value = "http://example.com/csv"
    mock_driver.find_element.return_value = mock_element

    # モック設定
    mock_settings.moneyforward.selenium.timeout = 1

    with (
        patch.object(downloader, "download_file") as mock_download,
        patch("scraper.downloader.settings", mock_settings),
        patch.object(Path, "exists", return_value=True),
    ):
        # アカウントページのダウンロード処理をモック
        if "account" in links[0]:
            mock_download.side_effect = [
                expected_paths[0] for _ in range(12)
            ]  # 12ヶ月分のデータ
        else:
            mock_download.return_value = expected_paths[0]

        downloaded_files = downloader.download_from_links(mock_driver, links)
        assert len(downloaded_files) == len(expected_paths)
        assert all(path.exists() for path in downloaded_files)
        assert downloaded_files == expected_paths


def test_download_from_links_all_fail(downloader):
    """全てのダウンロードが失敗した場合のテスト。"""
    mock_driver = MagicMock()
    links = ["http://example.com/test1", "http://example.com/test2"]

    with patch.object(downloader, "download_file") as mock_download:
        mock_download.side_effect = DownloadError("ダウンロード失敗")

        with pytest.raises(DownloadError) as exc_info:
            downloader.download_from_links(mock_driver, links)
        assert "全てのダウンロードが失敗しました" in str(exc_info.value)


def test_download_from_links_partial_success(downloader, mock_settings):
    """一部のダウンロードのみ成功した場合のテスト。"""
    mock_driver = MagicMock()
    links = ["http://example.com/test1", "http://example.com/test2"]

    mock_settings.moneyforward.selenium.timeout = 1
    mock_settings.moneyforward.base_url = "http://example.com"
    mock_settings.moneyforward.endpoints.history = "/history"

    with (
        patch.object(downloader, "download_file") as mock_download,
        patch("scraper.downloader.settings", mock_settings),
        patch.object(Path, "exists", return_value=True),
    ):
        # 最初のダウンロードは成功、2番目は失敗をシミュレート
        success_path = Path("test1.csv")
        mock_download.side_effect = [success_path, None]

        # 一部のダウンロードが成功した場合は、成功したファイルのリストを返す
        downloaded_files = downloader.download_from_links(mock_driver, links)
        assert len(downloaded_files) == 1
        assert downloaded_files[0] == success_path
