"""シークレット管理モジュール。"""

from google.cloud import secretmanager
import os
import subprocess
import logging
from typing import Optional

from exceptions.custom_exceptions import ConfigurationError

logger = logging.getLogger(__name__)

_project_id: Optional[str] = None

def get_project_id() -> str:
    """GCPプロジェクトIDを取得。

    Returns:
        str: GCPプロジェクトID

    Raises:
        ConfigurationError: プロジェクトIDの取得に失敗した場合
    """
    global _project_id
    if _project_id is None:
        try:
            result = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                capture_output=True,
                text=True,
                check=True,
            )
            _project_id = result.stdout.strip()
            if not _project_id:
                raise ConfigurationError("プロジェクトIDが設定されていません")
        except subprocess.CalledProcessError as e:
            raise ConfigurationError(f"プロジェクトIDの取得に失敗: {e}")
    return _project_id

def get_secrets() -> None:
    """Secret Managerから必要な環境変数を設定。

    Raises:
        ConfigurationError: シークレットの取得に失敗した場合
    """
    try:
        client = secretmanager.SecretManagerServiceClient()
        project_id = get_project_id()

        secrets = {
            "GMAIL_CREDENTIALS": "gmail-api-credentials",
            "GMAIL_TOKEN": "gmail-api-token",
            "EMAIL": "mf-email",
            "PASSWORD": "mf-password",
            "SPREADSHEET_KEY": "spreadsheet-key",
        }

        for env_var, secret_name in secrets.items():
            name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
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
        project_id = get_project_id()
        parent = f"projects/{project_id}/secrets/{secret_name}"

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
