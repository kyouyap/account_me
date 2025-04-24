"""ファイル管理クラスモジュール。"""

import logging
from pathlib import Path
from typing import Protocol, List

logger = logging.getLogger(__name__)


class FileManager(Protocol):
    """ファイル管理インターフェース。"""

    def prepare_directory(self, path: Path) -> None:
        """ディレクトリを準備する。

        Args:
            path: 準備するディレクトリのパス。
        """
        ...

    def clean_directory(self, path: Path) -> None:
        """ディレクトリをクリーンアップする。

        Args:
            path: クリーンアップするディレクトリのパス。
        """
        ...

    def list_files(self, path: Path, pattern: str = "*") -> List[Path]:
        """ディレクトリ内のファイルを一覧する。

        Args:
            path: 対象ディレクトリのパス。
            pattern: 検索パターン。

        Returns:
            List[Path]: ファイルパスのリスト。
        """
        ...


class LocalFileManager:
    """ローカルファイルシステムを管理するクラス。"""

    def prepare_directory(self, path: Path) -> None:
        """ディレクトリを準備する。

        存在しない場合は作成し、既に存在する場合は何もしない。

        Args:
            path: 準備するディレクトリのパス。

        Raises:
            OSError: ディレクトリの作成に失敗した場合。
        """
        try:
            path.mkdir(parents=True, exist_ok=True)
            logger.info("ディレクトリを準備しました: %s", path)
        except OSError as e:
            logger.error("ディレクトリの準備に失敗しました: %s", e)
            raise

    def clean_directory(self, path: Path) -> None:
        """ディレクトリをクリーンアップする。

        ディレクトリ内の全ファイルを削除する。

        Args:
            path: クリーンアップするディレクトリのパス。

        Raises:
            OSError: ファイルの削除に失敗した場合。
        """
        try:
            if not path.exists():
                logger.warning(
                    "クリーンアップ対象のディレクトリが存在しません: %s", path
                )
                return

            deleted_count = 0
            for file in path.glob("*"):
                try:
                    file.unlink()
                    deleted_count += 1
                except OSError as e:
                    logger.error("ファイルの削除に失敗しました %s: %s", file, e)
                    raise

            logger.info(
                "ディレクトリをクリーンアップしました: %s（削除ファイル数: %d）",
                path,
                deleted_count,
            )
        except OSError as e:
            logger.error("ディレクトリのクリーンアップに失敗しました: %s", e)
            raise

    def list_files(self, path: Path, pattern: str = "*") -> List[Path]:
        """ディレクトリ内のファイルを一覧する。

        Args:
            path: 対象ディレクトリのパス。
            pattern: 検索パターン。

        Returns:
            List[Path]: ファイルパスのリスト。

        Raises:
            FileNotFoundError: ディレクトリが存在しない場合。
        """
        try:
            if not path.exists():
                raise FileNotFoundError(f"ディレクトリが存在しません: {path}")

            files = list(path.glob(pattern))
            logger.info(
                "ファイル一覧を取得しました - ディレクトリ: %s, パターン: %s（ファイル数: %d）",
                path,
                pattern,
                len(files),
            )
            return files
        except Exception as e:
            logger.error("ファイル一覧の取得に失敗しました: %s", e)
            raise

    def get_latest_file(self, path: Path, pattern: str = "*") -> Path:
        """最新のファイルを取得する。

        Args:
            path: 対象ディレクトリのパス。
            pattern: 検索パターン。

        Returns:
            Path: 最新のファイルパス。

        Raises:
            FileNotFoundError: 該当するファイルが存在しない場合。
        """
        files = self.list_files(path, pattern)
        if not files:
            raise FileNotFoundError(
                f"該当するファイルが存在しません - ディレクトリ: {path}, パターン: {pattern}"
            )

        latest_file = max(files, key=lambda f: f.stat().st_mtime)
        logger.info("最新のファイルを取得しました: %s", latest_file)
        return latest_file
