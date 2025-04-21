"""シークレット管理モジュールのテスト。"""

import pytest
from unittest.mock import Mock, patch
import os
import subprocess
from exceptions.custom_exceptions import ConfigurationError
from config.secrets import get_project_number, get_secrets, update_secret

@pytest.fixture
def mock_gcloud_success(mocker):
    """正常系のgcloudコマンドをモック化するフィクスチャ。"""
    mock_run = mocker.patch('subprocess.run')
    mock_run.side_effect = [
        Mock(stdout="test-project-id\n", check=True),  # プロジェクトID
        Mock(stdout="123456789\n", check=True)         # プロジェクト番号
    ]
    return mock_run

@pytest.fixture
def mock_secret_manager(mocker):
    """Secret Managerクライアントをモック化するフィクスチャ。"""
    mock_client = Mock()
    mock_client.access_secret_version.return_value = Mock(
        payload=Mock(data=b"test-secret-value")
    )
    mock_client.add_secret_version.return_value = None
    mocker.patch('google.cloud.secretmanager.SecretManagerServiceClient',
                return_value=mock_client)
    return mock_client

class TestGetProjectNumber:
    """get_project_number()のテストクラス。"""

    def test_success(self, mock_gcloud_success):
        """正常系: プロジェクト番号が正しく取得できる。"""
        result = get_project_number()
        assert result == "123456789"
        assert mock_gcloud_success.call_count == 2

    def test_cache(self, mock_gcloud_success, mocker):
        """2回目の呼び出しではキャッシュされた値が返される。"""
        # _project_numberをリセット
        mocker.patch("config.secrets._project_number", None)
        
        get_project_number()
        result = get_project_number()
        assert result == "123456789"
        # 1回目の呼び出しで2回コマンドが実行され、2回目の呼び出しではキャッシュを使用
        assert mock_gcloud_success.call_count == 2

    def test_empty_project_id(self, mocker):
        """異常系: プロジェクトIDが空の場合。"""
        # _project_numberをリセット
        mocker.patch("config.secrets._project_number", None)
        
        mock_run = mocker.patch('subprocess.run')
        mock_run.return_value = Mock(stdout="\n", check=True)
        
        with pytest.raises(ConfigurationError, match="プロジェクトIDが設定されていません"):
            get_project_number()

    def test_empty_project_number(self, mocker):
        """異常系: プロジェクト番号が空の場合。"""
        # _project_numberをリセット
        mocker.patch("config.secrets._project_number", None)
        
        mock_run = mocker.patch('subprocess.run')
        mock_run.side_effect = [
            Mock(stdout="test-project-id\n", check=True),
            Mock(stdout="\n", check=True)
        ]
        
        with pytest.raises(ConfigurationError, match="プロジェクト番号の取得に失敗しました"):
            get_project_number()

    def test_command_error(self, mocker):
        """異常系: gcloudコマンドが失敗する場合。"""
        # _project_numberをリセット
        mocker.patch("config.secrets._project_number", None)
        
        mock_run = mocker.patch('subprocess.run')
        mock_run.side_effect = subprocess.CalledProcessError(1, "command", output="error")
        
        with pytest.raises(ConfigurationError, match="プロジェクト番号の取得に失敗"):
            get_project_number()

class TestGetSecrets:
    """get_secrets()のテストクラス。"""

    def test_success(self, mock_secret_manager, mocker):
        """正常系: 全てのシークレットが正しく取得できる。"""
        mock_environ = mocker.patch.dict('os.environ', {})
        get_secrets()
        
        # 各シークレットについて環境変数が設定されていることを確認
        secrets = ["EMAIL", "PASSWORD", "SPREADSHEET_KEY",
                  "GMAIL_CREDENTIALS", "GMAIL_API_TOKEN"]
        for secret in secrets:
            assert os.environ.get(secret) == "test-secret-value"

    def test_secret_error(self, mock_secret_manager, mocker):
        """異常系: シークレット取得でエラーが発生する場合。"""
        mock_secret_manager.access_secret_version.side_effect = Exception("Secret error")
        
        with pytest.raises(ConfigurationError, match="シークレット 'mf-email' の取得に失敗"):
            get_secrets()

    def test_client_error(self, mocker):
        """異常系: SecretManagerServiceClientの初期化に失敗する場合。"""
        mocker.patch('google.cloud.secretmanager.SecretManagerServiceClient',
                    side_effect=Exception("Client error"))
        
        with pytest.raises(ConfigurationError, match="シークレットの取得に失敗"):
            get_secrets()

class TestUpdateSecret:
    """update_secret()のテストクラス。"""

    def test_success(self, mock_secret_manager):
        """正常系: シークレットが正しく更新できる。"""
        update_secret("test-secret", "new-value")
        mock_secret_manager.add_secret_version.assert_called_once()

    def test_update_error(self, mock_secret_manager):
        """異常系: シークレットの更新に失敗する場合。"""
        mock_secret_manager.add_secret_version.side_effect = Exception("Update error")
        
        with pytest.raises(ConfigurationError, match="シークレット 'test-secret' の更新に失敗"):
            update_secret("test-secret", "new-value")

    def test_client_error(self, mocker):
        """異常系: SecretManagerServiceClientの初期化に失敗する場合。"""
        mocker.patch('google.cloud.secretmanager.SecretManagerServiceClient',
                    side_effect=Exception("Client error"))
        
        with pytest.raises(ConfigurationError, match="シークレットの更新に失敗"):
            update_secret("test-secret", "new-value")
