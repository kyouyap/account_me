"""MoneyForwardScraperのテスト。"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from exceptions.custom_exceptions import MoneyForwardError
from scraper.scraper import MoneyForwardScraper


@pytest.fixture
def scraper():
    """テスト用のMoneyForwardScraperインスタンスを生成。"""
    return MoneyForwardScraper()


@pytest.fixture
def mock_env_vars(monkeypatch):
    """環境変数をモック化。"""
    env_vars = {
        "EMAIL": "test@example.com",
        "PASSWORD": "password123",
        "SELENIUM_URL": "http://localhost:4444",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars


def test_init(scraper):
    """初期化のテスト。"""
    assert isinstance(scraper.download_dir, Path)
    assert scraper.browser_manager is not None
    assert scraper.file_downloader is not None


def test_check_env_variables_success(scraper, mock_env_vars):
    """環境変数チェックの成功テスト。"""
    scraper._check_env_variables()


def test_check_env_variables_failure(scraper, monkeypatch):
    """環境変数チェックの失敗テスト。"""
    monkeypatch.delenv("EMAIL", raising=False)
    monkeypatch.delenv("PASSWORD", raising=False)
    monkeypatch.delenv("SELENIUM_URL", raising=False)

    with pytest.raises(MoneyForwardError) as exc_info:
        scraper._check_env_variables()
    assert "環境変数が設定されていません" in str(exc_info.value)


def test_clean_directories(scraper, tmp_path):
    """ディレクトリクリーンアップのテスト。"""
    # テスト用のディレクトリとファイルを作成
    test_dirs = [
        tmp_path / "downloads",
        tmp_path / "outputs/aggregated_files/detail",
        tmp_path / "outputs/aggregated_files/assets",
    ]
    for dir_path in test_dirs:
        dir_path.mkdir(parents=True)
        (dir_path / "test.txt").write_text("test")

    with patch.object(scraper, "download_dir", test_dirs[0]):
        with patch("pathlib.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.glob.return_value = [
                Path(f"{dir_path}/test.txt") for dir_path in test_dirs
            ]

            scraper._clean_directories()


def test_clean_directories_error(scraper, tmp_path):
    """ディレクトリクリーンアップのエラー処理テスト。"""
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    test_file = test_dir / "test.txt"
    test_file.write_text("test")

    with (
        patch.object(scraper, "download_dir", test_dir),
        patch.object(scraper.file_downloader, "clean_download_dir") as mock_clean,
    ):
        mock_clean.side_effect = OSError("削除エラー")
        # エラーがあってもプログラムは続行する（例外は発生させない）
        scraper._clean_directories()


@pytest.mark.parametrize(
    "encoding,content",
    [
        ("utf-8", "名前,金額\nテスト,1000"),
        ("shift-jis", "名前,金額\nテスト,1000"),
        ("cp932", "名前,金額\nテスト,1000"),
    ],
)
def test_read_csv_with_encoding_success(scraper, tmp_path, encoding, content):
    """CSVファイル読み込みの成功テスト。"""
    test_file = tmp_path / "test.csv"
    test_file.write_bytes(content.encode(encoding))

    df = scraper._read_csv_with_encoding(test_file)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0


def test_read_csv_with_encoding_empty_file(scraper, tmp_path):
    """空のCSVファイル読み込みテスト。"""
    test_file = tmp_path / "empty.csv"
    test_file.write_text("")

    result = scraper._read_csv_with_encoding(test_file)
    assert result is None  # 空ファイルの場合はNoneを返す


def test_read_csv_with_encoding_generic_error(scraper, tmp_path):
    """CSVファイル読み込みの一般エラーテスト。"""
    test_file = tmp_path / "test.csv"
    test_file.write_text("test")

    with patch("pandas.read_csv") as mock_read_csv:
        mock_read_csv.side_effect = Exception("予期せぬエラー")
        result = scraper._read_csv_with_encoding(test_file)
        assert result is None  # エラー時はNoneを返す


def test_read_csv_with_encoding_all_encodings_fail(scraper, tmp_path):
    """全エンコーディングでの読み込み失敗テスト。"""
    test_file = tmp_path / "test.csv"
    test_file.write_bytes(b"\xff\xfe")  # 無効なUTF-8バイト列

    result = scraper._read_csv_with_encoding(test_file)
    assert result is None  # すべてのエンコーディングが失敗した場合はNoneを返す


def test_aggregate_csv_files_success(scraper, tmp_path):
    """CSVファイル集約の成功テスト。"""
    # テストデータ作成
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()

    csv_content = """日付,金額（円）,保有金融機関,メモ
2024-03-24,1000,Bank A,Test
2024-03-24,2000,American Express,Test"""

    test_file = download_dir / "test.csv"
    test_file.write_text(csv_content)

    # settingsのモック
    mock_settings = MagicMock()
    mock_settings.moneyforward.special_rules = [
        MagicMock(action="divide_amount", institution="American Express", value=2)
    ]

    with (
        patch.object(scraper, "download_dir", download_dir),
        patch("scraper.scraper.settings", mock_settings),
    ):
        output_path = tmp_path / "output.csv"
        scraper._aggregate_csv_files(output_path)

        assert output_path.exists()
        df = pd.read_csv(output_path)
        assert len(df) == 2
        # American Expressの金額が半額になっていることを確認
        assert (
            df[df["保有金融機関"] == "American Express"]["金額（円）"].iloc[0] == 1000.0
        )


def test_aggregate_csv_files_error(scraper, tmp_path):
    """CSVファイル集約のエラーテスト。"""
    with patch.object(scraper, "download_dir", tmp_path):
        mock_file = tmp_path / "test.csv"
        mock_file.touch()  # ファイルを作成
        result = scraper._aggregate_csv_files(tmp_path / "output.csv")
        assert result is None


def test_aggregate_csv_files_no_files(scraper, tmp_path):
    """CSVファイル集約の失敗テスト（ファイルなし）。"""
    with patch.object(scraper, "download_dir", tmp_path):
        result = scraper._aggregate_csv_files(tmp_path / "output.csv")
        assert result is None


def test_aggregate_csv_files_empty_dataframe(scraper, tmp_path):
    """空のデータフレームを含むCSVファイルの集約テスト。"""
    # テストデータ作成
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()

    # 通常のデータと空のデータを含むCSVファイルを作成
    valid_content = """日付,金額（円）,保有金融機関,メモ
2024-03-24,1000,Bank A,Test"""
    empty_content = """日付,金額（円）,保有金融機関,メモ"""

    (download_dir / "valid.csv").write_text(valid_content)
    (download_dir / "empty.csv").write_text(empty_content)

    with patch.object(scraper, "download_dir", download_dir):
        output_path = tmp_path / "output.csv"
        scraper._aggregate_csv_files(output_path)

        assert output_path.exists()
        df = pd.read_csv(output_path)
        assert len(df) == 1  # 空のデータフレームは無視されるべき


def test_aggregate_csv_files_no_duplicates(scraper, tmp_path):
    """重複データの排除を確認するテスト。"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()

    # 重複するデータを含むCSVファイルを作成
    duplicate_content = """日付,金額（円）,保有金融機関,メモ
2024-03-24,1000,Bank A,Test
2024-03-24,1000,Bank A,Test
2024-03-24,2000,Bank B,Test"""

    (download_dir / "data.csv").write_text(duplicate_content)

    with patch.object(scraper, "download_dir", download_dir):
        output_path = tmp_path / "output.csv"
        scraper._aggregate_csv_files(output_path)

        assert output_path.exists()
        df = pd.read_csv(output_path)
        assert len(df) == 2  # 重複が排除されているべき
        assert df["金額（円）"].sum() == 3000  # 合計金額が正しいことを確認


def test_aggregate_csv_files_encoding(scraper, tmp_path):
    """UTF-8-sigエンコーディングでの出力を確認するテスト。"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()

    content = """日付,金額（円）,保有金融機関,メモ
2024-03-24,1000,テスト銀行,テスト"""

    (download_dir / "data.csv").write_text(content)

    with patch.object(scraper, "download_dir", download_dir):
        output_path = tmp_path / "output.csv"
        scraper._aggregate_csv_files(output_path)

        # ファイルがUTF-8-sigで保存されているか確認
        with open(output_path, "rb") as f:
            assert f.read().startswith(b"\xef\xbb\xbf")  # UTF-8-sig BOM
