"""CSVファイル処理モジュール。"""

import logging
from pathlib import Path
from typing import List, Optional, Protocol

import pandas as pd

from exceptions.custom_exceptions import CSVProcessingError

logger = logging.getLogger(__name__)


class CSVProcessor(Protocol):
    """CSVファイル処理インターフェース。"""

    def read_csv(self, file_path: Path) -> pd.DataFrame:
        """CSVファイルを読み込む。

        Args:
            file_path: 読み込むCSVファイルのパス。

        Returns:
            pd.DataFrame: 読み込んだデータフレーム。

        Raises:
            CSVProcessingError: CSVファイルの読み込みに失敗した場合。
        """
        ...

    def aggregate_files(self, file_paths: List[Path], output_path: Path) -> None:
        """CSVファイルを集約する。

        Args:
            file_paths: 集約するCSVファイルのパスリスト。
            output_path: 出力先のパス。

        Raises:
            CSVProcessingError: CSVファイルの集約に失敗した場合。
        """
        ...


class MoneyForwardCSVProcessor:
    """MoneyForward用のCSV処理クラス。"""

    def read_csv(self, file_path: Path) -> pd.DataFrame:
        """CSVファイルを読み込む。

        複数のエンコーディングを試行し、適切なエンコーディングで読み込む。
        また、MoneyForwardの特殊ルール（金額の半額化など）も適用する。

        Args:
            file_path: 読み込むCSVファイルのパス。

        Returns:
            pd.DataFrame: 読み込んだデータフレーム。

        Raises:
            CSVProcessingError: CSVファイルの読み込みに失敗した場合。
        """
        if not file_path.exists():
            raise CSVProcessingError(f"CSVファイルが存在しません: {file_path}")

        # ファイルサイズのチェック
        if file_path.stat().st_size == 0:
            logger.warning("CSVファイル '%s' が空のためスキップします", file_path)
            return pd.DataFrame()

        # 複数のエンコーディングを試行
        encodings = ["utf-8", "shift-jis", "cp932"]
        errors = []

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

                # MoneyForward特有の処理（金額の調整など）
                if "金額（円）" in df.columns and "保有金融機関" in df.columns:
                    df = self._apply_money_forward_rules(df)

                return df

            except UnicodeDecodeError as e:
                logger.warning(
                    "エンコーディング '%s' での読み込みに失敗: %s",
                    encoding,
                    str(e),
                )
                errors.append(f"{encoding}: {str(e)}")
            except Exception as e:
                logger.error(
                    "ファイル '%s' の読み込み中に予期せぬエラーが発生: %s",
                    file_path,
                    str(e),
                )
                errors.append(f"{encoding}: {str(e)}")

        error_msg = "\n".join(errors)
        raise CSVProcessingError(
            f"CSVファイル '{file_path}' の読み込みに失敗しました: \n{error_msg}"
        )

    def _apply_money_forward_rules(self, df: pd.DataFrame) -> pd.DataFrame:
        """MoneyForward特有のルールをデータフレームに適用。

        Args:
            df: 処理対象のデータフレーム。

        Returns:
            pd.DataFrame: ルールを適用したデータフレーム。
        """
        try:
            # 金額カラムを数値型に変換
            df["金額（円）"] = df["金額（円）"].astype(float)

            # アメリカン・エキスプレスカードの金額を半額に
            # 将来的にはsettingsから読み込むようにする
            amex_mask = df["保有金融機関"] == "アメリカン・エキスプレス"
            df.loc[amex_mask, "金額（円）"] = df.loc[amex_mask, "金額（円）"] / 2

            return df
        except Exception as e:
            logger.error("MoneyForwardルールの適用中にエラーが発生: %s", e)
            raise CSVProcessingError(f"データの処理に失敗しました: {e}") from e

    def aggregate_files(self, file_paths: List[Path], output_path: Path) -> None:
        """CSVファイルを集約する。

        Args:
            file_paths: 集約するCSVファイルのパスリスト。
            output_path: 出力先のパス。

        Raises:
            CSVProcessingError: CSVファイルの集約に失敗した場合。
        """
        try:
            if not file_paths:
                logger.warning("集約するCSVファイルがありません")
                return

            # 各ファイルを読み込んでリストに追加
            dfs: List[pd.DataFrame] = []
            for file_path in file_paths:
                try:
                    df = self.read_csv(file_path)
                    if not df.empty:
                        dfs.append(df)
                except Exception as e:
                    logger.error("ファイル '%s' の処理中にエラー: %s", file_path, e)
                    continue

            if not dfs:
                logger.warning("有効なデータを含むCSVファイルがありませんでした")
                return

            # データを結合して重複を削除
            final_df = pd.concat(dfs).drop_duplicates().reset_index(drop=True)

            # 出力ディレクトリの作成
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # CSVファイルとして保存
            final_df.to_csv(output_path, index=False, encoding="utf-8-sig")
            logger.info(
                "CSVファイルを集約しました: %s（レコード数: %d）",
                output_path,
                len(final_df),
            )

        except Exception as e:
            logger.error("CSVファイルの集約中にエラーが発生:", exc_info=True)
            raise CSVProcessingError(f"CSVファイルの集約に失敗しました: {e}") from e
