"""BigQueryへのデータロード処理を行うモジュール。"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from google.cloud import bigquery, storage

logger = logging.getLogger(__name__)


class BigQueryLoader:
    """BigQueryへのデータロード処理を行うクラス。"""

    def __init__(self) -> None:
        """BigQueryローダーの初期化。"""
        self.client = bigquery.Client()
        self.storage_client = storage.Client()
        self.dataset_id = "moneyforward"
        self.bucket_name = f"mf-raw-data-{self.client.project}"

    def _upload_to_gcs(self, file_path: Path) -> Optional[str]:
        """ファイルをCloud Storageにアップロードする。

        Args:
            file_path: アップロードするファイルのパス

        Returns:
            Optional[str]: アップロードしたファイルのGCSパス
        """
        try:
            bucket = self.storage_client.bucket(self.bucket_name)
            date_prefix = datetime.now().strftime("%Y/%m/%d")
            blob_name = f"{date_prefix}/{file_path.name}"
            blob = bucket.blob(blob_name)

            blob.upload_from_filename(str(file_path))
            return f"gs://{self.bucket_name}/{blob_name}"

        except Exception as e:
            logger.error("Cloud Storageへのアップロードに失敗しました: %s", e)
            return None

    def _load_to_bigquery(
        self, gcs_path: str, table_id: str, schema: list[dict]
    ) -> bool:
        """Cloud StorageからBigQueryにデータをロードする。

        Args:
            gcs_path: Cloud StorageのパスURL
            table_id: ロード先のテーブルID
            schema: BigQueryのテーブルスキーマ

        Returns:
            bool: ロードが成功したかどうか
        """
        try:
            dataset_ref = self.client.dataset(self.dataset_id)
            table_ref = dataset_ref.table(table_id)

            job_config = bigquery.LoadJobConfig()
            job_config.source_format = bigquery.SourceFormat.CSV
            job_config.schema = [bigquery.SchemaField(**field) for field in schema]
            job_config.write_disposition = bigquery.WriteDisposition.WRITE_APPEND
            job_config.encoding = "UTF-8"
            job_config.skip_leading_rows = 1

            load_job = self.client.load_table_from_uri(
                gcs_path, table_ref, job_config=job_config
            )
            load_job.result()  # ジョブの完了を待機

            logger.info(
                "テーブル %s.%s にデータをロードしました: %s rows",
                self.dataset_id,
                table_id,
                load_job.output_rows,
            )
            return True

        except Exception as e:
            logger.error("BigQueryへのロードに失敗しました: %s", e)
            return False

    def load_transactions(self, file_path: Path) -> bool:
        """取引データをBigQueryにロードする。

        Args:
            file_path: 取引データファイルのパス

        Returns:
            bool: ロードが成功したかどうか
        """
        schema = [
            {"name": "transaction_date", "type": "DATE", "mode": "REQUIRED"},
            {"name": "category", "type": "STRING", "mode": "REQUIRED"},
            {"name": "sub_category", "type": "STRING", "mode": "NULLABLE"},
            {"name": "amount", "type": "NUMERIC", "mode": "REQUIRED"},
            {"name": "institution", "type": "STRING", "mode": "REQUIRED"},
            {"name": "memo", "type": "STRING", "mode": "NULLABLE"},
            {"name": "created_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
        ]

        gcs_path = self._upload_to_gcs(file_path)
        if not gcs_path:
            return False

        return self._load_to_bigquery(gcs_path, "raw_transactions", schema)

    def load_assets(self, file_path: Path) -> bool:
        """資産データをBigQueryにロードする。

        Args:
            file_path: 資産データファイルのパス

        Returns:
            bool: ロードが成功したかどうか
        """
        schema = [
            {"name": "asset_date", "type": "DATE", "mode": "REQUIRED"},
            {"name": "institution", "type": "STRING", "mode": "REQUIRED"},
            {"name": "asset_type", "type": "STRING", "mode": "REQUIRED"},
            {"name": "amount", "type": "NUMERIC", "mode": "REQUIRED"},
            {"name": "created_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
        ]

        gcs_path = self._upload_to_gcs(file_path)
        if not gcs_path:
            return False

        return self._load_to_bigquery(gcs_path, "raw_assets", schema)
