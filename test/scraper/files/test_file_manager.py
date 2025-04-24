"""FileManagerのテスト。"""

import os
from pathlib import Path
import pytest
import tempfile
import shutil

from scraper.files.file_manager import LocalFileManager


@pytest.fixture
def temp_dir():
    """テスト用の一時ディレクトリを提供。"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def file_manager():
    """LocalFileManagerのインスタンスを提供。"""
    return LocalFileManager()


@pytest.fixture
def sample_files(temp_dir):
    """テスト用のサンプルファイルを作成。"""
    files = []
    for i in range(3):
        file_path = temp_dir / f"test_file_{i}.txt"
        file_path.write_text(f"content_{i}")
        files.append(file_path)
    return files


class TestLocalFileManager:
    """LocalFileManagerのテストクラス。"""

    def test_prepare_directory_creates_new(self, file_manager, temp_dir):
        """新規ディレクトリ作成のテスト。"""
        test_dir = temp_dir / "new_dir"
        file_manager.prepare_directory(test_dir)
        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_prepare_directory_existing(self, file_manager, temp_dir):
        """既存ディレクトリの準備テスト。"""
        test_dir = temp_dir / "existing_dir"
        test_dir.mkdir()
        file_manager.prepare_directory(test_dir)
        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_prepare_directory_nested(self, file_manager, temp_dir):
        """入れ子ディレクトリ作成のテスト。"""
        test_dir = temp_dir / "parent" / "child" / "grandchild"
        file_manager.prepare_directory(test_dir)
        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_prepare_directory_permission_error(self, file_manager, temp_dir):
        """権限エラー時のテスト。"""
        if os.name == "nt":  # Windowsの場合はスキップ
            pytest.skip("Windows環境ではスキップします")

        test_dir = temp_dir / "readonly_dir"
        test_dir.mkdir()
        # 実行権限のみを設定（書き込み権限なし）
        os.chmod(test_dir, 0o555)

        with pytest.raises(OSError) as excinfo:
            file_manager.prepare_directory(test_dir / "new_dir")
        assert "Permission denied" in str(excinfo.value)

    def test_clean_directory_empty(self, file_manager, temp_dir):
        """空ディレクトリのクリーンアップテスト。"""
        file_manager.clean_directory(temp_dir)
        assert len(list(temp_dir.glob("*"))) == 0

    def test_clean_directory_with_files(self, file_manager, temp_dir, sample_files):
        """ファイルが存在するディレクトリのクリーンアップテスト。"""
        assert len(list(temp_dir.glob("*"))) > 0
        file_manager.clean_directory(temp_dir)
        assert len(list(temp_dir.glob("*"))) == 0

    def test_clean_directory_nonexistent(self, file_manager, temp_dir):
        """存在しないディレクトリのクリーンアップテスト。"""
        nonexistent_dir = temp_dir / "nonexistent"
        file_manager.clean_directory(nonexistent_dir)  # エラーを発生させない

    def test_clean_directory_permission_error(
        self, file_manager, temp_dir, sample_files
    ):
        """権限エラー時のテスト。"""
        if os.name == "nt":  # Windowsの場合はスキップ
            pytest.skip("Windows環境ではスキップします")

        # ファイルとディレクトリを読み取り専用に設定
        for file in sample_files:
            os.chmod(file, 0o444)
        os.chmod(temp_dir, 0o555)  # ディレクトリも読み取り・実行のみ

        with pytest.raises(OSError) as excinfo:
            file_manager.clean_directory(temp_dir)
        assert "Permission denied" in str(excinfo.value)

    def test_list_files_all(self, file_manager, temp_dir, sample_files):
        """全ファイル一覧取得のテスト。"""
        files = file_manager.list_files(temp_dir)
        assert len(files) == len(sample_files)
        assert all(f.exists() for f in files)

    def test_list_files_pattern(self, file_manager, temp_dir, sample_files):
        """パターンマッチによるファイル一覧取得のテスト。"""
        files = file_manager.list_files(temp_dir, "test_file_1*")
        assert len(files) == 1
        assert files[0].name == "test_file_1.txt"

    def test_list_files_nonexistent_dir(self, file_manager, temp_dir):
        """存在しないディレクトリからのファイル一覧取得テスト。"""
        with pytest.raises(FileNotFoundError):
            file_manager.list_files(temp_dir / "nonexistent")

    def test_get_latest_file(self, file_manager, temp_dir):
        """最新ファイル取得のテスト。"""
        # タイムスタンプの異なるファイルを作成
        for i in range(3):
            file_path = temp_dir / f"test_file_{i}.txt"
            file_path.write_text(f"content_{i}")
            # ファイルのタイムスタンプを設定
            os.utime(
                file_path,
                (os.stat(file_path).st_atime, os.stat(file_path).st_mtime + i),
            )

        latest = file_manager.get_latest_file(temp_dir)
        assert latest.name == "test_file_2.txt"

    def test_get_latest_file_empty_dir(self, file_manager, temp_dir):
        """空ディレクトリからの最新ファイル取得テスト。"""
        with pytest.raises(FileNotFoundError):
            file_manager.get_latest_file(temp_dir)

    def test_get_latest_file_with_pattern(self, file_manager, temp_dir):
        """パターン指定での最新ファイル取得テスト。"""
        # 異なる拡張子のファイルを作成
        txt_file = temp_dir / "test.txt"
        txt_file.write_text("txt content")
        csv_file = temp_dir / "test.csv"
        csv_file.write_text("csv content")

        # タイムスタンプを設定（CSVファイルを新しく）
        os.utime(csv_file, (os.stat(csv_file).st_atime, os.stat(txt_file).st_mtime + 1))

        # txtファイルのみを対象に最新ファイルを取得
        latest = file_manager.get_latest_file(temp_dir, "*.txt")
        assert latest.name == "test.txt"
