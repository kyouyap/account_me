"""GCP Secret Managerを使用したシークレット管理モジュール。

このモジュールは、アプリケーションで使用する機密情報を
Google Cloud Platform (GCP) Secret Managerを通じて安全に管理します。

主な機能:
    - MoneyForward認証情報の取得
    - Google Spreadsheet APIの認証情報の取得
    - Gmail APIの認証情報の取得
    - シークレットの環境変数への設定
    - シークレットの更新

Note:
    実行には適切なGCPプロジェクト設定とSecret Managerへのアクセス権限が必要です。

"""

import logging
import os
import subprocess

from google.cloud import secretmanager

from exceptions.custom_exceptions import ConfigurationError

logger = logging.getLogger(__name__)

_project_number: str | None = None


def get_project_number() -> str:
    """GCPプロジェクト番号を取得します。

    gcloudコマンドを使用してプロジェクトIDを取得し、そこからプロジェクト番号を
    取得します。結果はキャッシュされ、2回目以降の呼び出しでは保存された値が
    返されます。

    Returns:
        str: GCPプロジェクト番号

    Raises:
        ConfigurationError: プロジェクトIDまたはプロジェクト番号の取得に失敗した場合

    """
    global _project_number
    if _project_number is None:
        try:
            # まずプロジェクトIDを取得
            id_result = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                capture_output=True,
                text=True,
                check=True,
            )
            project_id = id_result.stdout.strip()
            if not project_id:
                raise ConfigurationError("プロジェクトIDが設定されていません")

            # プロジェクトIDを使用してプロジェクト番号を取得
            number_result = subprocess.run(
                [
                    "gcloud",
                    "projects",
                    "describe",
                    project_id,
                    "--format=value(projectNumber)",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            _project_number = number_result.stdout.strip()
            if not _project_number:
                raise ConfigurationError("プロジェクト番号の取得に失敗しました")
        except subprocess.CalledProcessError as e:
            raise ConfigurationError(f"プロジェクト番号の取得に失敗: {e}") from e
    return _project_number


def get_secrets() -> None:
    """Secret Managerから必要なシークレットを取得し、環境変数として設定します。

    以下のシークレットを環境変数として設定します:
        - EMAIL: MoneyForwardログイン用メールアドレス
        - PASSWORD: MoneyForwardログインパスワード
        - SPREADSHEET_KEY: 同期先のスプレッドシートキー
        - GMAIL_CREDENTIALS: Gmail API用クライアント認証情報
        - GMAIL_API_TOKEN: Gmail APIアクセストークン
        - SPREADSHEET_CREDENTIAL_JSON: Spreadsheet API用サービスアカウント認証情報

    Raises:
        ConfigurationError: シークレットの取得または環境変数の設定に失敗した場合

    """
    try:
        client = secretmanager.SecretManagerServiceClient()
        project_number = get_project_number()

        secrets = {
            "EMAIL": "mf-email",
            "PASSWORD": "mf-password",
            "SPREADSHEET_KEY": "spreadsheet-key",
            "GMAIL_CREDENTIALS": "gmail-api-credentials",
            "GMAIL_API_TOKEN": "gmail-api-token",
            "SPREADSHEET_CREDENTIAL_JSON": "spreadsheet-credential",
        }

        for env_var, secret_name in secrets.items():
            name = f"projects/{project_number}/secrets/{secret_name}/versions/latest"
            print(name)
            try:
                response = client.access_secret_version(request={"name": name})
                os.environ[env_var] = response.payload.data.decode("UTF-8")
                logger.info("シークレット '%s' を環境変数に設定しました", secret_name)
            except Exception as e:
                raise ConfigurationError(
                    f"シークレット '{secret_name}' の取得に失敗: {e}"
                ) from e

    except Exception as e:
        raise ConfigurationError(f"シークレットの取得に失敗: {e}") from e


def update_secret(secret_name: str, secret_value: str) -> None:
    """Secret Managerの特定のシークレットを更新します。

    Args:
        secret_name: 更新対象のシークレット名
            (例: "mf-email", "spreadsheet-key" など)
        secret_value: シークレットの新しい値

    Raises:
        ConfigurationError: シークレットの更新に失敗した場合
            - シークレットが存在しない
            - 更新権限がない
            - その他のAPI関連エラー

    """
    try:
        client = secretmanager.SecretManagerServiceClient()
        project_number = get_project_number()
        parent = f"projects/{project_number}/secrets/{secret_name}"

        try:
            payload = secret_value.encode("UTF-8")
            client.add_secret_version(
                request={
                    "parent": parent,
                    "payload": {"data": payload},
                }
            )
            logger.info("シークレット '%s' を更新しました", secret_name)
        except Exception as e:
            raise ConfigurationError(
                f"シークレット '{secret_name}' の更新に失敗: {e}"
            ) from e

    except Exception as e:
        raise ConfigurationError(f"シークレットの更新に失敗: {e}") from e


if __name__ == "__main__":
    get_secrets()
