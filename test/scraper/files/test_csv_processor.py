"""CSVProcessorのテスト。"""

import os
from pathlib import Path
import pandas as pd
import pytest
import tempfile

from scraper.files.csv_processor import MoneyForwardCSVProcessor, CSVProcessingError


@pytest.fixture
def csv_processor():
    """MoneyForwardCSVProcessorのインスタンスを提供。"""
    return MoneyForwardCSVProcessor()


@pytest.fixture
def temp_dir():
    """テスト用の一時ディレクトリを提供。"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_csv(temp_dir):
    """テスト用のサンプルCSVファイルを作成。"""
    content = (
        "日付,保有金融機関,金額（円）\n"
        "2024-01-01,テスト銀行,10000\n"
        "2024-01-02,アメリカン・エキスプレス,20000\n"
    )
    file_path = temp_dir / "sample.csv"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def empty_csv(temp_dir):
    """空のCSVファイルを作成。"""
    file_path = temp_dir / "empty.csv"
    file_path.touch()
    return file_path


@pytest.fixture
def multiple_csv_files(temp_dir):
    """複数のCSVファイルを作成。"""
    files = []

    # 1つ目のファイル
    content1 = "日付,保有金融機関,金額（円）\n2024-01-01,テスト銀行,10000\n"
    file1 = temp_dir / "file1.csv"
    file1.write_text(content1, encoding="utf-8")
    files.append(file1)

    # 2つ目のファイル（重複データを含む）
    content2 = (
        "日付,保有金融機関,金額（円）\n"
        "2024-01-01,テスト銀行,10000\n"  # 重複
        "2024-01-02,アメリカン・エキスプレス,20000\n"
    )
    file2 = temp_dir / "file2.csv"
    file2.write_text(content2, encoding="utf-8")
    files.append(file2)

    return files


class TestMoneyForwardCSVProcessor:
    """MoneyForwardCSVProcessorのテストクラス。"""

    def test_read_csv_success(self, csv_processor, sample_csv):
        """CSVファイルの読み込み成功のテスト。"""
        df = csv_processor.read_csv(sample_csv)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "金額（円）" in df.columns
        assert "保有金融機関" in df.columns

    def test_read_csv_empty_file(self, csv_processor, empty_csv):
        """空のCSVファイルを読み込むテスト。"""
        df = csv_processor.read_csv(empty_csv)
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_read_csv_nonexistent_file(self, csv_processor, temp_dir):
        """存在しないファイルを読み込むテスト。"""
        with pytest.raises(CSVProcessingError, match="CSVファイルが存在しません"):
            csv_processor.read_csv(temp_dir / "nonexistent.csv")

    def test_read_csv_money_forward_rules(self, csv_processor, sample_csv):
        """MoneyForwardのルール適用テスト。"""
        df = csv_processor.read_csv(sample_csv)
        # アメリカン・エキスプレスの金額が半額になっていることを確認
        amex_row = df[df["保有金融機関"] == "アメリカン・エキスプレス"]
        assert amex_row["金額（円）"].iloc[0] == 10000  # 20000の半額

    def test_read_csv_encoding_detection(self, csv_processor, temp_dir):
        """異なるエンコーディングのファイル読み込みテスト。"""
        # UTF-8のファイル
        utf8_content = "日付,保有金融機関,金額（円）\n2024-01-01,テスト銀行,10000"
        utf8_file = temp_dir / "utf8.csv"
        utf8_file.write_text(utf8_content, encoding="utf-8")

        # Shift-JISのファイル
        sjis_content = "日付,保有金融機関,金額（円）\n2024-01-01,テスト銀行,10000"
        sjis_file = temp_dir / "sjis.csv"
        sjis_file.write_text(sjis_content, encoding="shift-jis")

        # 両方のファイルが読み込めることを確認
        assert len(csv_processor.read_csv(utf8_file)) == 1
        assert len(csv_processor.read_csv(sjis_file)) == 1

    def test_aggregate_files_success(self, csv_processor, multiple_csv_files, temp_dir):
        """ファイル集約の成功テスト。"""
        output_path = temp_dir / "output.csv"
        csv_processor.aggregate_files(multiple_csv_files, output_path)

        assert output_path.exists()
        df = pd.read_csv(output_path)
        # 重複が除去されていることを確認
        assert len(df) == 2

    def test_aggregate_files_empty_list(self, csv_processor, temp_dir):
        """空のファイルリストでの集約テスト。"""
        output_path = temp_dir / "output.csv"
        csv_processor.aggregate_files([], output_path)
        assert not output_path.exists()

    def test_aggregate_files_with_errors(
        self, csv_processor, multiple_csv_files, temp_dir
    ):
        """一部のファイルが失敗する場合の集約テスト。"""
        # 無効なファイルを追加
        invalid_file = temp_dir / "invalid.csv"
        invalid_file.write_text("invalid content", encoding="utf-8")
        files = multiple_csv_files + [invalid_file]

        output_path = temp_dir / "output.csv"
        csv_processor.aggregate_files(files, output_path)

        # 有効なファイルのデータは集約されていることを確認
        assert output_path.exists()
        df = pd.read_csv(output_path)
        assert len(df) == 2

    def test_aggregate_files_nested_output_path(
        self, csv_processor, multiple_csv_files, temp_dir
    ):
        """入れ子のディレクトリへの出力テスト。"""
        output_path = temp_dir / "nested" / "dir" / "output.csv"
        csv_processor.aggregate_files(multiple_csv_files, output_path)

        assert output_path.exists()
        df = pd.read_csv(output_path)
        assert len(df) == 2
