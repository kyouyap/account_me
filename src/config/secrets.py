"""シークレット管理モジュール。"""

from google.cloud import secretmanager
import os
import subprocess
import logging
from typing import Optional

from exceptions.custom_exceptions import ConfigurationError

logger = logging.getLogger(__name__)

_project_number: Optional[str] = None

def get_project_number() -> str:
    """GCPプロジェクト番号を取得。

    Returns:
        str: GCPプロジェクト番号

    Raises:
        ConfigurationError: プロジェクト番号の取得に失敗した場合
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
                ["gcloud", "projects", "describe", project_id, "--format=value(projectNumber)"],
                capture_output=True,
                text=True,
                check=True,
            )
            _project_number = number_result.stdout.strip()
            if not _project_number:
                raise ConfigurationError("プロジェクト番号の取得に失敗しました")
        except subprocess.CalledProcessError as e:
            raise ConfigurationError(f"プロジェクト番号の取得に失敗: {e}")
    return _project_number

def get_secrets() -> None:
    """Secret Managerから必要な環境変数を設定。

    Raises:
        ConfigurationError: シークレットの取得に失敗した場合
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
        }

        for env_var, secret_name in secrets.items():
            name = f"projects/{project_number}/secrets/{secret_name}/versions/latest"
            print(name)
            try:
                response = client.access_secret_version(request={"name": name})
                os.environ[env_var] = response.payload.data.decode("UTF-8")
                logger.info("シークレット '%s' を環境変数に設定しました", secret_name)
            except Exception as e:
                raise ConfigurationError(f"シークレット '{secret_name}' の取得に失敗: {e}")

    except Exception as e:
        raise ConfigurationError(f"シークレットの取得に失敗: {e}")

def update_secret(secret_name: str, secret_value: str) -> None:
    """Secret Managerのシークレットを更新。

    Args:
        secret_name: シークレット名
        secret_value: 新しい値

    Raises:
        ConfigurationError: シークレットの更新に失敗した場合
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
            raise ConfigurationError(f"シークレット '{secret_name}' の更新に失敗: {e}")

    except Exception as e:
        raise ConfigurationError(f"シークレットの更新に失敗: {e}")

if __name__ == "__main__":
    get_secrets()
