"""GmailClientのテストモジュール。"""

import base64
import datetime
import json
import os
from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

from scraper.gmail_client import (
    SCOPES,
    GmailApiError,
    GmailClient,
    VerificationCodeError,
)


@pytest.fixture
def gmail_client():
    """GmailClientのインスタンスを返すフィクスチャ。認証処理をバイパスします。"""
    with patch.object(GmailClient, "_create_gmail_service", return_value=MagicMock()):
        client = GmailClient()
    return client


@pytest.fixture
def sample_message():
    """テスト用のマルチパートメッセージデータを返すフィクスチャ。期限切れにならない未来の有効期限を設定します。"""
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    future_time = now + datetime.timedelta(minutes=10)
    future_time_str = future_time.strftime("%B %d, %Y %H:%M:%S")
    body = (
        "Test message\n"
        "Your verification code is: 123456 \n"
        f"This code is valid for 10 mins ({future_time_str})"
    )
    encoded_data = base64.b64encode(body.encode("utf-8")).decode("utf-8")
    return {
        "payload": {
            "parts": [{"mimeType": "text/plain", "body": {"data": encoded_data}}]
        }
    }


@pytest.fixture
def expired_message():
    """テスト用の期限切れメッセージデータを返すフィクスチャ。"""
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    past_time = now - datetime.timedelta(minutes=30)  # 30分前
    past_time_str = past_time.strftime("%B %d, %Y %H:%M:%S")
    body = (
        "Test message\n"
        "Your verification code is: 111111 \n"
        f"This code is valid for 10 mins ({past_time_str})"
    )
    encoded_data = base64.b64encode(body.encode("utf-8")).decode("utf-8")
    return {
        "payload": {
            "parts": [{"mimeType": "text/plain", "body": {"data": encoded_data}}]
        }
    }


@pytest.fixture
def valid_message():
    """テスト用の有効なメッセージデータを返すフィクスチャ。"""
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    future_time = now + datetime.timedelta(minutes=5)  # 5分後
    future_time_str = future_time.strftime("%B %d, %Y %H:%M:%S")
    body = (
        "Test message\n"
        "Your verification code is: 222222 \n"
        f"This code is valid for 10 mins ({future_time_str})"
    )
    encoded_data = base64.b64encode(body.encode("utf-8")).decode("utf-8")
    return {
        "payload": {
            "parts": [{"mimeType": "text/plain", "body": {"data": encoded_data}}]
        }
    }


@pytest.fixture
def singlepart_message():
    """テスト用のシングルパートメッセージデータを返すフィクスチャ。"""
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    future_time = now + datetime.timedelta(minutes=10)
    future_time_str = future_time.strftime("%B %d, %Y %H:%M:%S")
    body = (
        "Singlepart message\n"
        "Your verification code is: 789012 \n"
        f"This code is valid for 10 mins ({future_time_str})"
    )
    encoded_data = base64.urlsafe_b64encode(body.encode("utf-8")).decode("utf-8")
    return {"payload": {"body": {"data": encoded_data}}}


@pytest.fixture
def no_expiry_message():
    """テスト用の有効期限パターンがないメッセージデータを返すフィクスチャ。"""
    body = "No expiry message\nYour verification code is: 345678"
    encoded_data = base64.b64encode(body.encode("utf-8")).decode("utf-8")
    return {
        "payload": {
            "parts": [{"mimeType": "text/plain", "body": {"data": encoded_data}}]
        }
    }


@pytest.fixture
def invalid_multipart_message():
    """テスト用の無効なマルチパートメッセージデータを返すフィクスチャ。"""
    body = "Invalid message"
    encoded_data = base64.b64encode(body.encode("utf-8")).decode("utf-8")
    return {
        "payload": {
            "parts": [{"mimeType": "text/html", "body": {"data": encoded_data}}]
        }
    }


def test_get_client_config_success(gmail_client):
    """_get_client_configが正常に動作することを確認する。"""
    expected_config = {"web": {"client_id": "test_id", "client_secret": "test_secret"}}
    with patch.dict(os.environ, {"GMAIL_CREDENTIALS": json.dumps(expected_config)}):
        result = gmail_client._get_client_config()
        assert result == expected_config


def test_get_client_config_missing_env(gmail_client):
    """環境変数が設定されていない場合にGmailApiErrorが発生することを確認する。"""
    with patch.dict(os.environ, clear=True), pytest.raises(
        GmailApiError, match="GMAIL_CREDENTIALS環境変数が設定されていません"
    ):
        gmail_client._get_client_config()


def test_get_existing_credentials_success(gmail_client):
    """_get_existing_credentialsが正常に動作することを確認する。"""
    token_data = {
        "token": "test_token",
        "refresh_token": "test_refresh_token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
    }
    with patch.dict(os.environ, {"GMAIL_API_TOKEN": json.dumps(token_data)}):
        result = gmail_client._get_existing_credentials()
        assert isinstance(result, Credentials)
        assert result.token == "test_token"


def test_get_existing_credentials_missing_env(gmail_client):
    """環境変数が設定されていない場合にNoneが返されることを確認する。"""
    with patch.dict(os.environ, clear=True):
        result = gmail_client._get_existing_credentials()
        assert result is None


def test_get_existing_credentials_invalid_json(gmail_client):
    """トークンデータが不正なJSONの場合にNoneが返されることを確認する。"""
    with patch.dict(os.environ, {"GMAIL_API_TOKEN": "invalid json"}):
        result = gmail_client._get_existing_credentials()
        assert result is None


def test_refresh_credentials_success(gmail_client):
    """_refresh_credentialsが正常に動作することを確認する。"""
    mock_creds = MagicMock(spec=Credentials)
    mock_creds.to_json.return_value = '{"token": "new_token"}'

    with patch("scraper.gmail_client.update_secret") as mock_update:
        result = gmail_client._refresh_credentials(mock_creds)
        assert result == mock_creds
        mock_update.assert_called_once_with("gmail-api-token", '{"token": "new_token"}')


def test_refresh_credentials_error(gmail_client):
    """トークン更新時にエラーが発生した場合の処理を確認する。"""
    mock_creds = MagicMock(spec=Credentials)
    mock_creds.refresh.side_effect = RefreshError("Refresh token error")

    with pytest.raises(RefreshError, match="Refresh token error"):
        gmail_client._refresh_credentials(mock_creds)


def test_create_new_credentials_success(gmail_client):
    """_create_new_credentialsが正常に動作することを確認する。"""
    mock_creds = MagicMock(spec=Credentials)
    mock_creds.to_json.return_value = '{"token": "new_token"}'

    with patch(
        "google_auth_oauthlib.flow.InstalledAppFlow.from_client_config"
    ) as mock_from_client_config:
        mock_from_client_config.return_value.run_local_server.return_value = mock_creds
        with patch("scraper.gmail_client.update_secret") as mock_update:
            result = gmail_client._create_new_credentials({"web": {}})
            assert result == mock_creds
            mock_update.assert_called_once_with(
                "gmail-api-token", '{"token": "new_token"}'
            )


def test_create_new_credentials_error(gmail_client):
    """新規認証フロー実行時にエラーが発生した場合の処理を確認する。"""
    with patch(
        "google_auth_oauthlib.flow.InstalledAppFlow.from_client_config"
    ) as mock_from_client_config:
        mock_from_client_config.return_value.run_local_server.side_effect = Exception(
            "Flow error"
        )
        with pytest.raises(Exception, match="Flow error"):
            gmail_client._create_new_credentials({"web": {}})


def test_create_gmail_service_error_no_config(monkeypatch):
    """クライアント設定が取得できない場合のエラーを確認する。"""
    monkeypatch.delenv("GMAIL_CREDENTIALS", raising=False)

    with pytest.raises(
        GmailApiError, match="GMAIL_CREDENTIALS環境変数が設定されていません"
    ):
        GmailClient()


def test_create_gmail_service_with_valid_credentials(monkeypatch):
    """有効なクレデンシャルでサービスが正常に作成されることを確認。"""
    mock_service = MagicMock()
    mock_creds = MagicMock(spec=Credentials)
    mock_creds.valid = True
    mock_creds.expired = False

    # 環境変数の設定
    client_config = {"web": {"client_id": "test_id", "client_secret": "test_secret"}}
    token_data = {
        "token": "test_token",
        "refresh_token": "test_refresh_token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
    }
    with patch.dict(
        os.environ,
        {
            "GMAIL_CREDENTIALS": json.dumps(client_config),
            "GMAIL_API_TOKEN": json.dumps(token_data),
        },
    ), patch(
        "googleapiclient.discovery.build", return_value=mock_service
    ) as mock_build, patch.object(
        Credentials, "from_authorized_user_info", return_value=mock_creds
    ):
        client = GmailClient()
        mock_build.assert_called_once_with("gmail", "v1", credentials=mock_creds)
        assert client.service is mock_service


def test_create_gmail_service_with_expired_credentials(monkeypatch):
    """期限切れクレデンシャルが正常に更新されることを確認。"""
    mock_service = MagicMock()
    mock_creds = MagicMock(spec=Credentials)
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = True
    mock_creds.to_json.return_value = '{"token": "refreshed_token"}'

    # 環境変数の設定
    client_config = {"web": {"client_id": "test_id", "client_secret": "test_secret"}}
    token_data = {
        "token": "test_token",
        "refresh_token": "test_refresh_token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
    }
    with patch.dict(
        os.environ,
        {
            "GMAIL_CREDENTIALS": json.dumps(client_config),
            "GMAIL_API_TOKEN": json.dumps(token_data),
        },
    ), patch(
        "googleapiclient.discovery.build", return_value=mock_service
    ) as mock_build, patch.object(
        Credentials, "from_authorized_user_info", return_value=mock_creds
    ), patch("scraper.gmail_client.update_secret") as mock_update:
        client = GmailClient()
        mock_build.assert_called_once_with("gmail", "v1", credentials=mock_creds)
        mock_creds.refresh.assert_called_once()
        mock_update.assert_called_once_with(
            "gmail-api-token", '{"token": "refreshed_token"}'
        )
        assert client.service is mock_service


def test_create_gmail_service_create_new_credentials(monkeypatch):
    """新規クレデンシャルが正常に作成されることを確認。"""
    mock_service = MagicMock()
    mock_creds = MagicMock(spec=Credentials)
    mock_creds.valid = False
    mock_creds.expired = False
    mock_creds.to_json.return_value = '{"token": "new_token"}'

    # 環境変数の設定
    client_config = {"web": {"client_id": "test_id", "client_secret": "test_secret"}}
    with patch.dict(
        os.environ,
        {
            "GMAIL_CREDENTIALS": json.dumps(client_config),
        },
    ), patch(
        "googleapiclient.discovery.build", return_value=mock_service
    ) as mock_build, patch(
        "google_auth_oauthlib.flow.InstalledAppFlow.from_client_config"
    ) as mock_flow:
        mock_flow.return_value.run_local_server.return_value = mock_creds
        with patch("scraper.gmail_client.update_secret") as mock_update:
            client = GmailClient()
            mock_build.assert_called_once_with("gmail", "v1", credentials=mock_creds)
            mock_flow.assert_called_once_with(client_config, scopes=SCOPES)
            mock_update.assert_called_once_with(
                "gmail-api-token", '{"token": "new_token"}'
            )
            assert client.service is mock_service


def test_create_gmail_service_error_build(monkeypatch):
    """サービスビルド時のエラーを確認する。"""
    # 環境変数の設定
    client_config = {"web": {"client_id": "test_id", "client_secret": "test_secret"}}
    token_data = {
        "token": "test_token",
        "refresh_token": "test_refresh_token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
    }
    mock_creds = MagicMock(spec=Credentials)
    mock_creds.valid = True

    with patch.dict(
        os.environ,
        {
            "GMAIL_CREDENTIALS": json.dumps(client_config),
            "GMAIL_API_TOKEN": json.dumps(token_data),
        },
    ), patch("googleapiclient.discovery.build") as mock_build, patch.object(
        Credentials, "from_authorized_user_info", return_value=mock_creds
    ):
        mock_build.side_effect = Exception("Build error")
        with pytest.raises(GmailApiError, match="Gmailサービスの作成に失敗"):
            GmailClient()


def test_extract_email_body_singlepart_success(gmail_client, singlepart_message):
    """シングルパートメールの本文抽出が正常に動作することを確認。"""
    result = gmail_client._extract_email_body(singlepart_message)
    assert "Singlepart message" in result
    assert "789012" in result


def test_extract_email_body_invalid_multipart(gmail_client, invalid_multipart_message):
    """text/plainパートがないマルチパートメッセージでVerificationCodeErrorが発生することを確認する。"""
    with pytest.raises(VerificationCodeError, match="text/plainパートが見つかりません"):
        gmail_client._extract_email_body(invalid_multipart_message)


def test_get_verification_email_ids_none_result(gmail_client):
    """メール検索結果がNoneの場合のエラー処理を確認。"""
    mock_service = gmail_client.service
    mock_service.users().messages().list().execute.return_value = None

    with pytest.raises(VerificationCodeError, match="認証メールが見つかりません"):
        gmail_client.get_verification_email_ids()


def test_get_verification_code_by_id_none_message(gmail_client):
    """メッセージ取得結果がNoneの場合のエラー処理を確認。"""
    mock_service = gmail_client.service
    mock_service.users().messages().get().execute.return_value = None

    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client.get_verification_code_by_id("test_id")


def test_gmail_api_request_error(gmail_client):
    """Gmail APIリクエストエラー時の例外処理を確認。"""
    mock_service = gmail_client.service
    mock_service.users().messages().list().execute.side_effect = HttpError(
        MagicMock(status=500), b"API error"
    )

    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code()


def test_verification_code_not_found(gmail_client):
    """認証コードが見つからない場合のエラー処理を確認。"""
    message = {
        "payload": {
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {
                        "data": base64.b64encode(b"No verification code here").decode()
                    },
                }
            ]
        }
    }
    with pytest.raises(VerificationCodeError, match="認証コードが見つかりません"):
        gmail_client._parse_message(message)


def test_expiry_time_invalid_format(gmail_client):
    """有効期限の形式が不正な場合のエラー処理を確認。"""
    message = {
        "payload": {
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {
                        "data": base64.b64encode(
                            b"Your verification code is: 123456\n"
                            b"This code is valid for 10 mins (invalid date)"
                        ).decode()
                    },
                }
            ]
        }
    }
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client._parse_message(message)


def test_get_verification_email_ids_success(gmail_client):
    """get_verification_email_idsが正常に動作することを確認する。"""
    mock_response = {"messages": [{"id": "1"}, {"id": "2"}]}
    mock_service = gmail_client.service
    mock_service.users().messages().list().execute.return_value = mock_response

    result = gmail_client.get_verification_email_ids()
    assert result == ["1", "2"]

    # APIの呼び出しパラメータを確認
    mock_service.users().messages().list.assert_called_with(
        userId="me",
        q=(
            "from:do_not_reply@moneyforward.com "
            'subject:"Money Forward ID Additional Authentication via Email"'
        ),
        maxResults=5,
    )


def test_get_verification_email_ids_no_results(gmail_client):
    """メールが見つからない場合に空リストが返されることを確認する。"""
    mock_response = {"messages": []}
    mock_service = gmail_client.service
    mock_service.users().messages().list().execute.return_value = mock_response

    result = gmail_client.get_verification_email_ids()
    assert result == []


def test_get_verification_email_ids_api_error(gmail_client):
    """API呼び出しでエラーが発生した場合にGmailApiErrorが発生することを確認する。"""
    mock_service = gmail_client.service
    mock_service.users().messages().list().execute.side_effect = HttpError(
        MagicMock(status=500), b"API error"
    )

    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_email_ids()


def test_get_verification_code_by_id_success(gmail_client, sample_message):
    """get_verification_code_by_idが正常に動作することを確認する。"""
    mock_service = gmail_client.service
    mock_service.users().messages().get().execute.return_value = sample_message

    result = gmail_client.get_verification_code_by_id("test_id")
    assert result == "123456"


def test_get_verification_code_by_id_expired(gmail_client, expired_message):
    """期限切れのコードでVerificationCodeErrorが発生することを確認する。"""
    mock_service = gmail_client.service
    mock_service.users().messages().get().execute.return_value = expired_message

    with pytest.raises(
        VerificationCodeError, match="認証コードの有効期限が切れています"
    ):
        gmail_client.get_verification_code_by_id("test_id")


def test_get_verification_code_by_id_api_error(gmail_client):
    """API呼び出しでエラーが発生した場合にGmailApiErrorが発生することを確認する。"""
    mock_service = gmail_client.service
    mock_service.users().messages().get().execute.side_effect = HttpError(
        MagicMock(status=500), b"API error"
    )

    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code_by_id("test_id")


def test_get_verification_code_success(gmail_client, valid_message):
    """get_verification_codeが正常に動作することを確認する。"""
    # メールIDのリストを返すようにモック設定
    mock_service = gmail_client.service
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "1"}]
    }
    # メッセージの取得をモック設定
    mock_service.users().messages().get().execute.return_value = valid_message

    result = gmail_client.get_verification_code()
    assert result == "222222"


def test_get_verification_code_no_valid_codes(gmail_client, expired_message):
    """有効なコードが見つからない場合にVerificationCodeErrorが発生することを確認する。"""
    # メールIDのリストを返すようにモック設定
    mock_service = gmail_client.service
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "1"}, {"id": "2"}]
    }
    # 全てのメッセージを期限切れに設定
    mock_service.users().messages().get().execute.return_value = expired_message

    with pytest.raises(
        VerificationCodeError, match="有効な認証コードが見つかりませんでした"
    ):
        gmail_client.get_verification_code()


def test_get_verification_code_no_messages(gmail_client):
    """メールが見つからない場合にVerificationCodeErrorが発生することを確認する。"""
    # メールが見つからないようにモック設定
    mock_service = gmail_client.service
    mock_service.users().messages().list().execute.return_value = {"messages": []}

    with pytest.raises(VerificationCodeError, match="認証メールが見つかりません"):
        gmail_client.get_verification_code()


def test_get_verification_code_socket_timeout(gmail_client):
    """ソケットタイムアウトが発生した場合のエラー処理を確認する。"""
    mock_service = gmail_client.service
    mock_service.users().messages().list().execute.side_effect = TimeoutError(
        "Connection timed out"
    )

    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code()


def test_extract_verification_code_error(gmail_client):
    """認証コードが見つからない場合のエラー処理を確認する。"""
    message = {
        "payload": {
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {
                        "data": base64.b64encode(b"No verification code here").decode()
                    },
                }
            ]
        }
    }
    with pytest.raises(VerificationCodeError, match="認証コードが見つかりません"):
        gmail_client._parse_message(message)


def test_extract_expiry_time_missing_pattern():
    client = GmailClient.__new__(GmailClient)
    with pytest.raises(VerificationCodeError, match="有効期限が見つかりません"):
        client._extract_expiry_time("no expiry here")


def test_get_verification_code_generic_error(monkeypatch):
    client = GmailClient.__new__(GmailClient)
    monkeypatch.setattr(client, "get_verification_email_ids", lambda: ["msg1"])

    def raise_err(msg_id):
        raise Exception("err")

    monkeypatch.setattr(client, "get_verification_code_by_id", raise_err)
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗: err"):
        client.get_verification_code()


def test_extract_verification_code_invalid_expiry(gmail_client):
    """有効期限の形式が不正な場合のエラー処理を確認する。"""
    message = {
        "payload": {
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {
                        "data": base64.b64encode(
                            b"Your verification code is: 123456\n"
                            b"This code is valid for 10 mins (invalid date)"
                        ).decode()
                    },
                }
            ]
        }
    }
    expected_error = (
        "メッセージの解析に失敗: time data 'invalid date' does not match format "
        "'%B %d, %Y %H:%M:%S'"
    )
    with pytest.raises(VerificationCodeError, match=expected_error):
        gmail_client._parse_message(message)
