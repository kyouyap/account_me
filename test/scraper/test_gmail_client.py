"""GmailClientのテストモジュール。"""
from unittest.mock import MagicMock, patch
import base64
import datetime
import json
import socket
import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from scraper.gmail_client import GmailClient, GmailApiError, VerificationCodeError

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
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": encoded_data}
                }
            ]
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
    return {
        "payload": {
            "body": {"data": encoded_data}
        }
    }

@pytest.fixture
def no_expiry_message():
    """テスト用の有効期限パターンがないメッセージデータを返すフィクスチャ。"""
    body = (
        "No expiry message\n"
        "Your verification code is: 345678"
    )
    encoded_data = base64.b64encode(body.encode("utf-8")).decode("utf-8")
    return {
        "payload": {
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": encoded_data}
                }
            ]
        }
    }

# --- 既存テスト ---

def test_create_gmail_service_success(monkeypatch):
    """Gmail APIサービスの作成が成功するケースのテスト。"""
    monkeypatch.setenv(
        "GMAIL_CREDENTIALS",
        json.dumps({
            "installed": {
                "client_id": "test",
                "project_id": "test",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_secret": "secret",
                "redirect_uris": ["http://localhost"]
            }
        })
    )
    monkeypatch.setenv(
        "GMAIL_API_TOKEN",
        json.dumps({"token": "test", "refresh_token": "r", "client_id": "test"})
    )
    mock_creds = MagicMock()
    mock_creds.valid = True
    with patch("scraper.gmail_client.Credentials") as mock_credentials:
        mock_credentials.from_authorized_user_info.return_value = mock_creds
        with patch("scraper.gmail_client.build") as mock_build:
            client = GmailClient()
            assert client.service is not None
            mock_build.assert_called_once_with("gmail", "v1", credentials=mock_creds)


def test_create_gmail_service_no_credentials(monkeypatch):
    """認証情報が設定されていない場合のテスト。"""
    monkeypatch.delenv("GMAIL_CREDENTIALS", raising=False)
    with pytest.raises(GmailApiError, match="GMAIL_CREDENTIALS環境変数が設定されていません"):
        GmailClient()

def test_create_gmail_service_invalid_credentials_json(monkeypatch):
    """不正なJSON形式の認証情報が設定されている場合のテスト。"""
    monkeypatch.setenv("GMAIL_CREDENTIALS", "invalid-json")
    with pytest.raises(GmailApiError, match="認証処理に失敗"):
        GmailClient()

def test_create_gmail_service_missing_token(monkeypatch):
    """トークンが設定されていない場合のテスト。"""
    monkeypatch.setenv(
        "GMAIL_CREDENTIALS",
        json.dumps({"installed": {"client_id": "test"}})
    )
    monkeypatch.delenv("GMAIL_API_TOKEN", raising=False)
    
    new_creds = MagicMock()
    new_creds.valid = True
    new_creds.to_json.return_value = "new_token_json"
    fake_flow = MagicMock(run_local_server=MagicMock(return_value=new_creds))
    
    with patch("scraper.gmail_client.InstalledAppFlow.from_client_config", return_value=fake_flow):
        with patch("scraper.gmail_client.build"):
            with patch("scraper.gmail_client.update_secret") as mock_update:
                client = GmailClient()
                mock_update.assert_called_once_with("gmail-api-token", "new_token_json")

def test_create_gmail_service_refresh_failure(monkeypatch):
    """トークンの更新に失敗する場合のテスト。"""
    monkeypatch.setenv(
        "GMAIL_CREDENTIALS",
        json.dumps({"installed": {"client_id": "test"}})
    )
    monkeypatch.setenv("GMAIL_API_TOKEN", json.dumps({"token": "test"}))
    
    old_creds = MagicMock()
    old_creds.valid = False
    old_creds.expired = True
    old_creds.refresh_token = True
    old_creds.refresh.side_effect = RefreshError("refresh failed")
    
    with patch("scraper.gmail_client.Credentials") as mock_credentials:
        mock_credentials.from_authorized_user_info.return_value = old_creds
        with pytest.raises(GmailApiError, match="認証処理に失敗"):
            GmailClient()

def test_create_gmail_service_secret_update_failure(monkeypatch):
    """Secret Managerの更新に失敗する場合のテスト。"""
    monkeypatch.setenv(
        "GMAIL_CREDENTIALS",
        json.dumps({"installed": {"client_id": "test"}})
    )
    monkeypatch.setenv("GMAIL_API_TOKEN", json.dumps({"token": "test"}))
    
    old_creds = MagicMock()
    old_creds.valid = False
    old_creds.expired = True
    old_creds.refresh_token = True
    old_creds.to_json.return_value = "refreshed_json"
    
    with patch("scraper.gmail_client.Credentials") as mock_credentials:
        mock_credentials.from_authorized_user_info.return_value = old_creds
        with patch("scraper.gmail_client.update_secret", side_effect=Exception("update failed")):
            with patch("scraper.gmail_client.build"):
                with pytest.raises(GmailApiError, match="認証処理に失敗"):
                    GmailClient()

# --- メッセージ解析関連テスト ---

def test_create_gmail_service_refresh_token(monkeypatch):
    """期限切れかつリフレッシュトークンがある場合、更新処理が行われるテスト。"""
    # 環境変数設定
    monkeypatch.setenv(
        "GMAIL_CREDENTIALS",
        json.dumps({
            "installed": {"client_id": "test", "project_id": "test", "auth_uri": "https://", "token_uri": "https://", "client_secret": "sec", "redirect_uris": ["http://localhost"]}
        })
    )
    monkeypatch.setenv("GMAIL_API_TOKEN", json.dumps({"dummy": "value"}))
    # 古い資格情報をモック
    old_creds = MagicMock()
    old_creds.valid = False
    old_creds.expired = True
    old_creds.refresh_token = True
    old_creds.to_json.return_value = "refreshed_json"
    # モック設定
    with patch("scraper.gmail_client.Credentials") as mock_credentials:
        mock_credentials.from_authorized_user_info.return_value = old_creds
        with patch("scraper.gmail_client.Request"):
            with patch("scraper.gmail_client.update_secret") as mock_update:
                with patch("scraper.gmail_client.build") as mock_build:
                    client = GmailClient()
                    old_creds.refresh.assert_called_once()
                    mock_update.assert_called_once_with("gmail-api-token", "refreshed_json")
                    mock_build.assert_called_once_with("gmail", "v1", credentials=old_creds)


def test_create_gmail_service_new_auth_flow(monkeypatch):
    """トークンが解析できない場合に新規認証フローが開始されるテスト。"""
    monkeypatch.setenv(
        "GMAIL_CREDENTIALS",
        json.dumps({"installed": {"client_id":"a","project_id":"b","auth_uri":"x","token_uri":"y","client_secret":"z","redirect_uris":["u"]}})
    )
    # トークン文字列が不正でinner tryが例外となりcreds=Noneとなる
    monkeypatch.setenv("GMAIL_API_TOKEN", "invalid_json")
    new_creds = MagicMock()
    new_creds.valid = True
    new_creds.to_json.return_value = "newflow_json"
    fake_flow = MagicMock(run_local_server=MagicMock(return_value=new_creds))
    with patch("scraper.gmail_client.Credentials") as mock_credentials:
        # from_authorized_user_info 呼ばれないまたは例外後creds=None
        mock_credentials.from_authorized_user_info.side_effect = ValueError("bad")
        with patch("scraper.gmail_client.InstalledAppFlow.from_client_config", return_value=fake_flow) as mock_flow_cls:
            with patch("scraper.gmail_client.update_secret") as mock_update:
                with patch("scraper.gmail_client.build") as mock_build:
                    client = GmailClient()
                    mock_flow_cls.assert_called_once()
                    fake_flow.run_local_server.assert_called_once()
                    mock_update.assert_called_once_with("gmail-api-token", "newflow_json")
                    mock_build.assert_called_once_with("gmail", "v1", credentials=new_creds)

# --- パース関連追加テスト ---

def test_parse_message_singlepart_success(gmail_client, singlepart_message):
    """シングルパートメールが正しく解析されるテスト。"""
    code, expiry = gmail_client._parse_message(singlepart_message)
    assert code == "789012"
    assert isinstance(expiry, datetime.datetime)


def test_parse_message_no_expiry(no_expiry_message, gmail_client):
    """有効期限パターンがない場合、VerificationCodeErrorが発生するテスト。"""
    with pytest.raises(VerificationCodeError, match="有効期限が見つかりません"):
        gmail_client._parse_message(no_expiry_message)

# --- APIエラー・メッセージなし分岐テスト ---

def test_parse_message_invalid_base64(gmail_client):
    """不正なBase64エンコードの場合のテスト。"""
    msg = {"payload": {"parts": [{"mimeType": "text/plain", "body": {"data": "invalid-base64"}}]}}
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client._parse_message(msg)

def test_parse_message_no_body(gmail_client):
    """本文が見つからない場合のテスト。"""
    msg = {"payload": {"parts": [{"mimeType": "text/plain", "body": {}}]}}
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client._parse_message(msg)

def test_parse_message_invalid_date_format(gmail_client):
    """不正な日付フォーマットの場合のテスト。"""
    body = "Test msg\nYour verification code is: 123456 \nThis code is valid for 10 mins (Invalid Date)"
    encoded = base64.b64encode(body.encode()).decode()
    msg = {"payload": {"parts": [{"mimeType": "text/plain", "body": {"data": encoded}}]}}
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client._parse_message(msg)

# --- APIエラー関連テスト ---

def test_get_latest_verification_email_id_network_error(gmail_client):
    """ネットワークエラーの場合のテスト。"""
    gmail_client.service.users.return_value.messages.return_value.list.side_effect = socket.timeout("timeout")
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_latest_verification_email_id()

def test_get_latest_verification_email_id_api_error(gmail_client):
    """get_latest_verification_email_idでHttpError発生時にGmailApiErrorが送出されるテスト。"""
    gmail_client.service.users.return_value.messages.return_value.list.side_effect = HttpError(MagicMock(), b"err")
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_latest_verification_email_id()


def test_get_verification_code_by_id_api_error(gmail_client):
    """get_verification_code_by_idでHttpError発生時にGmailApiErrorが送出されるテスト。"""
    gmail_client.service.users.return_value.messages.return_value.get.side_effect = HttpError(MagicMock(), b"err")
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code_by_id("id")


def test_get_verification_code_no_messages(gmail_client):
    """get_verification_codeでメッセージが見つからない場合、VerificationCodeErrorが発生するテスト。"""
    gmail_client.service.users.return_value.messages.return_value.list.return_value.execute.return_value = {"messages": []}
    with pytest.raises(VerificationCodeError, match="認証メールが見つかりません"):
        gmail_client.get_verification_code()

# --- 既存残りのテスト ---

def test_parse_message_success(gmail_client, sample_message):
    """メッセージの解析が成功するケースのテスト。"""
    code, expiry = gmail_client._parse_message(sample_message)
    assert code == "123456"
    assert isinstance(expiry, datetime.datetime)
    assert expiry.tzinfo is not None  # タイムゾーン情報が設定されていることを確認


def test_parse_message_no_code(gmail_client):
    """認証コードが見つからない場合のテスト。"""
    msg = {"payload": {"parts": [{"mimeType": "text/plain", "body": {"data": "VGVzdCBtZXNzYWdlCk5vIGNvZGUgaGVyZQ=="}}]}}
    with pytest.raises(VerificationCodeError, match="認証コードが見つかりません"):
        gmail_client._parse_message(msg)


def test_get_verification_code_by_id_expired(gmail_client):
    """有効期限切れの認証コードの場合のテスト。"""
    past = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))) - datetime.timedelta(hours=1)
    past_str = past.strftime("%B %d, %Y %H:%M:%S")
    body = (f"Test msg\nYour verification code is: 000000 \nThis code is valid for 10 mins ({past_str})")
    encoded = base64.b64encode(body.encode()).decode()
    msg = {"payload": {"parts": [{"mimeType": "text/plain", "body": {"data": encoded}}]}}
    gmail_client.service.users.return_value.messages.return_value.get.return_value.execute.return_value = msg
    with pytest.raises(VerificationCodeError, match="認証コードの有効期限が切れています"):
        gmail_client.get_verification_code_by_id("id")


def test_get_verification_code_malformed_response(gmail_client):
    """APIからの不正なレスポンス形式の場合のテスト。"""
    gmail_client.service.users.return_value.messages.return_value.list.return_value.execute.return_value = {"invalid": "response"}
    with pytest.raises(VerificationCodeError, match="認証メールが見つかりません"):
        gmail_client.get_verification_code()

def test_get_verification_code_api_error(gmail_client):
    """Gmail APIのエラーが発生した場合のテスト。"""
    gmail_client.service.users.return_value.messages.return_value.list.side_effect = HttpError(MagicMock(), b"API Error")
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code()

def test_get_verification_code_network_timeout(gmail_client):
    """ネットワークタイムアウトの場合のテスト。"""
    gmail_client.service.users.return_value.messages.return_value.list.side_effect = socket.timeout("Network timeout")
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code()

# --- Secret Manager関連の追加テスト ---

def test_create_gmail_service_token_parse_error(monkeypatch):
    """Secret Managerからのトークンが不正なJSONの場合のテスト。"""
    monkeypatch.setenv(
        "GMAIL_CREDENTIALS",
        json.dumps({"installed": {"client_id": "test"}})
    )
    monkeypatch.setenv("GMAIL_API_TOKEN", "invalid-json")
    
    new_creds = MagicMock()
    new_creds.valid = True
    new_creds.to_json.return_value = "new_token_json"
    fake_flow = MagicMock(run_local_server=MagicMock(return_value=new_creds))
    
    with patch("scraper.gmail_client.InstalledAppFlow.from_client_config", return_value=fake_flow):
        with patch("scraper.gmail_client.build"):
            with patch("scraper.gmail_client.update_secret") as mock_update:
                client = GmailClient()
                mock_update.assert_called_once_with("gmail-api-token", "new_token_json")

def test_create_gmail_service_token_invalid_format(monkeypatch):
    """Secret Managerからのトークンが不正な形式の場合のテスト。"""
    monkeypatch.setenv(
        "GMAIL_CREDENTIALS",
        json.dumps({"installed": {"client_id": "test"}})
    )
    monkeypatch.setenv("GMAIL_API_TOKEN", json.dumps({"invalid": "format"}))
    
    new_creds = MagicMock()
    new_creds.valid = True
    new_creds.to_json.return_value = "new_token_json"
    fake_flow = MagicMock(run_local_server=MagicMock(return_value=new_creds))
    
    with patch("scraper.gmail_client.InstalledAppFlow.from_client_config", return_value=fake_flow):
        with patch("scraper.gmail_client.build"):
            with patch("scraper.gmail_client.update_secret") as mock_update:
                client = GmailClient()
                mock_update.assert_called_once_with("gmail-api-token", "new_token_json")

def test_create_gmail_service_update_secret_error(monkeypatch):
    """Secret Managerの更新時にエラーが発生する場合のテスト。"""
    monkeypatch.setenv(
        "GMAIL_CREDENTIALS",
        json.dumps({"installed": {"client_id": "test"}})
    )
    monkeypatch.setenv("GMAIL_API_TOKEN", json.dumps({"token": "test"}))
    
    old_creds = MagicMock()
    old_creds.valid = False
    old_creds.expired = True
    old_creds.refresh_token = True
    old_creds.refresh.side_effect = Exception("update secret failed")
    
    with patch("scraper.gmail_client.Credentials") as mock_credentials:
        mock_credentials.from_authorized_user_info.return_value = old_creds
        with pytest.raises(GmailApiError, match="認証処理に失敗"):
            GmailClient()

# --- メッセージ形式関連の追加テスト ---

def test_parse_message_different_mimetype(gmail_client):
    """text/plain以外のMIMETypeの場合のテスト。"""
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    future_time = now + datetime.timedelta(minutes=10)
    future_time_str = future_time.strftime("%B %d, %Y %H:%M:%S")
    body = (
        "HTML message\n"
        "Your verification code is: 123456 \n"
        f"This code is valid for 10 mins ({future_time_str})"
    )
    encoded_data = base64.b64encode(body.encode()).decode()
    msg = {
        "payload": {
            "parts": [
                {
                    "mimeType": "text/html",
                    "body": {"data": encoded_data}
                }
            ]
        }
    }
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client._parse_message(msg)

def test_parse_message_empty_parts(gmail_client):
    """partsが空の場合のテスト。"""
    msg = {"payload": {"parts": []}}
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client._parse_message(msg)

def test_parse_message_missing_payload(gmail_client):
    """payloadが存在しない場合のテスト。"""
    msg = {}
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client._parse_message(msg)

def test_parse_message_empty_message(gmail_client):
    """メッセージが空の場合のテスト。"""
    msg = {"payload": {"parts": [{"mimeType": "text/plain", "body": {"data": ""}}]}}
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client._parse_message(msg)

def test_parse_message_body_none(gmail_client):
    """bodyがNoneの場合のテスト。"""
    msg = {"payload": {"parts": [{"mimeType": "text/plain", "body": None}]}}
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client._parse_message(msg)

def test_get_verification_code_empty_response(gmail_client):
    """APIからの空のレスポンスの場合のテスト。"""
    gmail_client.service.users.return_value.messages.return_value.list.return_value.execute.return_value = {}
    with pytest.raises(VerificationCodeError, match="認証メールが見つかりません"):
        gmail_client.get_verification_code()

# --- 追加のAPIエラーテスト ---

def test_get_latest_verification_email_id_unknown_error(gmail_client):
    """未知のエラーが発生した場合のテスト。"""
    gmail_client.service.users.return_value.messages.return_value.list.side_effect = Exception("unknown error")
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_latest_verification_email_id()

def test_get_verification_code_by_id_unknown_error(gmail_client):
    """get_verification_code_by_idで未知のエラーが発生した場合のテスト。"""
    gmail_client.service.users.return_value.messages.return_value.get.side_effect = Exception("unknown error")
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code_by_id("id")

def test_get_verification_code_execution_error(gmail_client):
    """executeメソッドでエラーが発生した場合のテスト。"""
    gmail_client.service.users.return_value.messages.return_value.list.return_value.execute.side_effect = Exception("execution error")
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code()

def test_get_verification_code_by_id_invalid_message(gmail_client):
    """メッセージの形式が不正な場合のテスト。"""
    gmail_client.service.users.return_value.messages.return_value.get.return_value.execute.return_value = {"invalid": "format"}
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client.get_verification_code_by_id("id")

def test_get_verification_code_chain_error(gmail_client):
    """チェーンメソッドの途中でエラーが発生した場合のテスト。"""
    gmail_client.service.users.return_value.messages.return_value.list.return_value = None
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code()

def test_get_verification_code_none_response(gmail_client):
    """APIからのレスポンスがNoneの場合のテスト。"""
    gmail_client.service.users.return_value.messages.return_value.list.return_value.execute.return_value = None
    with pytest.raises(VerificationCodeError, match="認証メールが見つかりません"):
        gmail_client.get_verification_code()

def test_get_verification_code_by_id_none_response(gmail_client):
    """get_verification_code_by_idでレスポンスがNoneの場合のテスト。"""
    gmail_client.service.users.return_value.messages.return_value.get.return_value.execute.return_value = None
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client.get_verification_code_by_id("id")

def test_get_verification_code_execution_none(gmail_client):
    """executeメソッドの戻り値がNoneの場合のテスト。"""
    gmail_client.service.users.return_value.messages.return_value.get.return_value.execute.return_value = None
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client.get_verification_code_by_id("id")

def test_parse_message_none_payload(gmail_client):
    """payloadがNoneの場合のテスト。"""
    msg = {"payload": None}
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client._parse_message(msg)

def test_parse_message_key_error(gmail_client):
    """必要なキーが存在しない場合のテスト。"""
    msg = {"payload": {"parts": [{"mimeType": "text/plain"}]}}
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client._parse_message(msg)

def test_parse_message_decode_error(gmail_client):
    """データのデコードに失敗する場合のテスト。"""
    msg = {"payload": {"body": {"data": None}}}
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client._parse_message(msg)

def test_get_verification_code_message_error(gmail_client):
    """メッセージの取得に失敗する場合のテスト。"""
    gmail_client.service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "test_id"}]
    }
    gmail_client.service.users.return_value.messages.return_value.get.side_effect = Exception("message error")
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code()

def test_get_verification_code_general_error(gmail_client):
    """予期せぬエラーが発生した場合のテスト。"""
    gmail_client.service.users.return_value.messages.return_value.list.return_value.execute.side_effect = Exception("unexpected error")
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code()

def test_get_verification_code_by_id_payload_error(gmail_client):
    """ペイロードの取得に失敗する場合のテスト。"""
    gmail_client.service.users.return_value.messages.return_value.get.return_value.execute.return_value = {"wrong_key": {}}
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client.get_verification_code_by_id("test_id")

def test_get_verification_code_by_id_parse_error(gmail_client):
    """メッセージのパースに失敗する場合のテスト。"""
    msg = {"payload": {"body": {"data": "invalid_data"}}}
    gmail_client.service.users.return_value.messages.return_value.get.return_value.execute.return_value = msg
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client.get_verification_code_by_id("test_id")

def test_parse_message_no_data(gmail_client):
    """データキーが存在しない場合のテスト。"""
    msg = {"payload": {"parts": [{"mimeType": "text/plain", "body": {}}]}}
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client._parse_message(msg)

def test_get_verification_code_message_id_error(gmail_client):
    """メッセージIDの取得に失敗する場合のテスト。"""
    gmail_client.service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{}]  # idキーが存在しない
    }
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code()

def test_get_verification_code_nested_error(gmail_client):
    """ネストされた例外が発生する場合のテスト。"""
    def raise_nested():
        try:
            raise ValueError("inner error")
        except ValueError as e:
            raise Exception("outer error") from e
    
    gmail_client.service.users.return_value.messages.return_value.list.side_effect = raise_nested
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code()

def test_parse_message_chain_error(gmail_client):
    """パース処理でチェーンエラーが発生する場合のテスト。"""
    msg = {"payload": {"parts": [{"mimeType": "text/plain", "body": {"data": None}}]}}
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client._parse_message(msg)

def test_get_verification_code_concurrent_error(gmail_client):
    """並行処理で例外が発生する場合のテスト。"""
    # メッセージ一覧の取得をモック
    gmail_client.service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "test_id"}]
    }
    
    # メッセージ本文の取得でエラーを発生させる
    gmail_client.service.users.return_value.messages.return_value.get.return_value.execute.side_effect = Exception("concurrent error")
    
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code()

def test_parse_message_recursive_error(gmail_client):
    """再帰的な例外が発生する場合のテスト。"""
    def raise_recursive():
        raise RecursionError("recursive error")
    
    msg = {"payload": {"parts": [{"mimeType": "text/plain", "body": {"data": "invalid"}}]}}
    with patch("base64.urlsafe_b64decode", side_effect=raise_recursive):
        with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
            gmail_client._parse_message(msg)

def test_parse_message_complex_error(gmail_client):
    """複雑な例外チェーンが発生する場合のテスト。"""
    def raise_complex():
        try:
            raise KeyError("inner")
        except KeyError as e:
            try:
                raise ValueError("middle") from e
            except ValueError as ve:
                raise RuntimeError("outer") from ve
    
    msg = {"payload": {"parts": [{"mimeType": "text/plain", "body": {"data": "test"}}]}}
    with patch("base64.urlsafe_b64decode", side_effect=raise_complex):
        with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
            gmail_client._parse_message(msg)

def test_get_verification_code_message_chain_error(gmail_client):
    """メッセージ取得のチェーンで例外が発生する場合のテスト。"""
    def raise_chain_error(*args, **kwargs):
        try:
            raise ConnectionError("connection failed")
        except ConnectionError as e:
            raise HttpError(MagicMock(), b"chain error") from e
    
    gmail_client.service.users.return_value.messages.return_value.get.return_value.execute.side_effect = raise_chain_error
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code()

def test_get_verification_code_payload_missing(gmail_client):
    """ペイロードキーが存在しない場合のテスト。"""
    invalid_message = {"id": "test_id", "threadId": "test_thread"}
    gmail_client.service.users.return_value.messages.return_value.get.return_value.execute.return_value = invalid_message
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client.get_verification_code()

def test_parse_message_deeply_nested_error(gmail_client):
    """深くネストされたエラーハンドリングのテスト。"""
    def raise_nested_error():
        try:
            try:
                raise ValueError("level 1")
            except ValueError as e1:
                raise KeyError("level 2") from e1
        except KeyError as e2:
            raise RuntimeError("level 3") from e2
    
    msg = {"payload": {"parts": [{"mimeType": "text/plain", "body": {"data": "test"}}]}}
    with patch("base64.urlsafe_b64decode", side_effect=raise_nested_error):
        with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
            gmail_client._parse_message(msg)

def test_create_gmail_service_token_update_error(monkeypatch):
    """トークン更新時にエラーが発生する場合のテスト。"""
    monkeypatch.setenv(
        "GMAIL_CREDENTIALS",
        json.dumps({"installed": {"client_id": "test"}})
    )
    monkeypatch.setenv("GMAIL_API_TOKEN", json.dumps({"token": "test"}))
    
    old_creds = MagicMock()
    old_creds.valid = False
    old_creds.expired = True
    old_creds.refresh_token = True
    old_creds.to_json.return_value = "updated_token"
    old_creds.refresh.side_effect = lambda x: exec('raise Exception("update failed")')
    
    with patch("scraper.gmail_client.Credentials") as mock_credentials:
        mock_credentials.from_authorized_user_info.return_value = old_creds
        with pytest.raises(GmailApiError, match="認証処理に失敗"):
            GmailClient()

def test_create_gmail_service_refresh_complex_error(monkeypatch):
    """トークン更新時に複雑なエラーチェーンが発生する場合のテスト。"""
    monkeypatch.setenv(
        "GMAIL_CREDENTIALS",
        json.dumps({"installed": {"client_id": "test"}})
    )
    monkeypatch.setenv("GMAIL_API_TOKEN", json.dumps({"token": "test"}))
    
    def raise_complex():
        try:
            raise ConnectionError("network error")
        except ConnectionError as e:
            try:
                raise TimeoutError("timeout") from e
            except TimeoutError as te:
                raise RefreshError("refresh failed") from te
    
    old_creds = MagicMock()
    old_creds.valid = False
    old_creds.expired = True
    old_creds.refresh_token = True
    old_creds.refresh.side_effect = raise_complex
    
    with patch("scraper.gmail_client.Credentials") as mock_credentials:
        mock_credentials.from_authorized_user_info.return_value = old_creds
        with pytest.raises(GmailApiError, match="認証処理に失敗"):
            GmailClient()

def test_parse_message_malformed_expiry(gmail_client):
    """不正な有効期限フォーマットの場合のテスト。"""
    body = (
        "Test message\n"
        "Your verification code is: 123456 \n"
        "This code is valid for 10 mins (Invalid Date Format)"
    )
    encoded_data = base64.urlsafe_b64encode(body.encode()).decode()
    msg = {
        "payload": {
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": encoded_data}
                }
            ]
        }
    }
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client._parse_message(msg)

def test_parse_message_invalid_timezone(gmail_client):
    """不正なタイムゾーン情報の場合のテスト。"""
    now = datetime.datetime.now()
    body = (
        "Test message\n"
        "Your verification code is: 123456 \n"
        f"This code is valid for 10 mins ({now.strftime('%B %d, %Y %H:%M:%S')} XXX)"
    )
    encoded_data = base64.urlsafe_b64encode(body.encode()).decode()
    msg = {
        "payload": {
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": encoded_data}
                }
            ]
        }
    }
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client._parse_message(msg)

def test_get_verification_code_timeout_chain(gmail_client):
    """タイムアウトが連鎖的に発生する場合のテスト。"""
    def raise_timeout_chain():
        try:
            raise socket.timeout("connection timeout")
        except socket.timeout as e:
            raise HttpError(MagicMock(), b"timeout occurred") from e
    
    gmail_client.service.users.return_value.messages.return_value.list.side_effect = raise_timeout_chain
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code()

def test_get_verification_code_socket_error(gmail_client):
    """ソケットエラーが発生する場合のテスト。"""
    gmail_client.service.users.return_value.messages.return_value.list.side_effect = socket.error("connection failed")
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code()

def test_parse_message_corrupted_data(gmail_client):
    """破損したデータの場合のテスト。"""
    msg = {
        "payload": {
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": "corrupted-base64-data"}
                }
            ]
        }
    }
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client._parse_message(msg)

def test_parse_message_invalid_structure(gmail_client):
    """不正なメッセージ構造の場合のテスト。"""
    msg = {
        "payload": {
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"wrong_key": "data"}
                }
            ]
        }
    }
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client._parse_message(msg)
# --- _create_gmail_service の build() エラー分岐 ---
def test_create_gmail_service_build_error(monkeypatch):
    """build() が例外を投げたとき、Gmailサービス作成失敗エラーになることをテスト"""
    # 正常な認証情報とトークン
    monkeypatch.setenv("GMAIL_CREDENTIALS", '{"installed":{"client_id":"a","project_id":"b","auth_uri":"x","token_uri":"y","client_secret":"z","redirect_uris":["u"]}}')
    monkeypatch.setenv("GMAIL_API_TOKEN", '{"token":"t","refresh_token":"r","client_id":"a"}')
    # モック資格情報
    fake_creds = MagicMock(valid=True)
    with patch("scraper.gmail_client.Credentials") as mock_creds_cls:
        mock_creds_cls.from_authorized_user_info.return_value = fake_creds
        # build() 側で例外を発生
        with patch("scraper.gmail_client.build", side_effect=Exception("build failed")):
            with pytest.raises(GmailApiError, match="Gmailサービスの作成に失敗"):
                GmailClient()

# --- get_latest_verification_email_id の None / 空リスト / id 欠如 分岐 ---
@pytest.mark.parametrize("result,exc_type,match", [
    (None, VerificationCodeError, "認証メールが見つかりません"),           # execute() が None
    ({"messages":[]}, VerificationCodeError, "認証メールが見つかりません"),  # 空リスト
    ({"messages":[{}]}, GmailApiError,        "Gmail APIのリクエストに失敗"), # id キーなし
])
def test_get_latest_verification_email_id_missing_branches(gmail_client, result, exc_type, match):
    svc = gmail_client.service.users.return_value.messages.return_value.list.return_value
    svc.execute.return_value = result
    with pytest.raises(exc_type, match=match):
        gmail_client.get_latest_verification_email_id()

# --- get_verification_code_by_id の socket.timeout 分岐 ---
def test_get_verification_code_by_id_timeout(gmail_client):
    """get_verification_code_by_id で socket.timeout が起きるパスをテスト"""
    gmail_client.service.users.return_value.messages.return_value.get.side_effect = socket.timeout("timeout")
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code_by_id("any-id")

# --- get_verification_code_by_id の None レスポンス分岐（明示的） ---
def test_get_verification_code_by_id_none_response(gmail_client):
    """get_verification_code_by_id で execute() が None を返すパスをテスト"""
    get_msg = gmail_client.service.users.return_value.messages.return_value.get.return_value
    get_msg.execute.return_value = None
    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client.get_verification_code_by_id("id")

# --- get_verification_code の socket.error 分岐 ---
def test_get_verification_code_socket_error(gmail_client):
    """get_verification_code で socket.error が起きるパスをテスト"""
    list_call = gmail_client.service.users.return_value.messages.return_value.list
    list_call.side_effect = socket.error("network down")
    with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
        gmail_client.get_verification_code()


import base64
import datetime
import socket
from unittest.mock import patch
import pytest
from googleapiclient.errors import HttpError
from scraper.gmail_client import GmailClient, GmailApiError, VerificationCodeError

# --- get_verification_code の message=None 分岐 ---
def test_get_verification_code_message_none(gmail_client):
    """get_verification_code で get(...).execute() が None を返すと VerificationCodeError になることをテスト"""
    # list() は正常に ID を返す
    list_call = gmail_client.service.users.return_value.messages.return_value.list.return_value
    list_call.execute.return_value = {"messages": [{"id": "any-id"}]}

    # get().execute() が None
    get_call = gmail_client.service.users.return_value.messages.return_value.get.return_value
    get_call.execute.return_value = None

    with pytest.raises(VerificationCodeError, match="メッセージの解析に失敗"):
        gmail_client.get_verification_code()


# --- get_verification_code の期限切れコード分岐 ---
def test_get_verification_code_expired(gmail_client):
    """get_verification_code で過去期限のコードが返ると VerificationCodeError になることをテスト"""
    # list() は正常に ID を返す
    list_call = gmail_client.service.users.return_value.messages.return_value.list.return_value
    list_call.execute.return_value = {"messages": [{"id": "any-id"}]}

    # get() は過去 expiry のメッセージを返す
    past = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))) - datetime.timedelta(minutes=5)
    past_str = past.strftime("%B %d, %Y %H:%M:%S")
    body = f"Your verification code is: 654321\nThis code is valid for 10 mins ({past_str})"
    encoded = base64.urlsafe_b64encode(body.encode()).decode()
    msg = {"payload": {"body": {"data": encoded}}}

    get_call = gmail_client.service.users.return_value.messages.return_value.get.return_value
    get_call.execute.return_value = msg

    with pytest.raises(VerificationCodeError, match="認証コードの有効期限が切れています"):
        gmail_client.get_verification_code()


# --- get_verification_code の _parse_message で ValueError を投げたときの汎用例外分岐 ---
def test_get_verification_code_parse_generic_error(gmail_client):
    """get_verification_code で _parse_message が ValueError を投げると GmailApiError にラップされることをテスト"""
    # list()/get() は最低限の構造を返す
    list_call = gmail_client.service.users.return_value.messages.return_value.list.return_value
    list_call.execute.return_value = {"messages": [{"id": "any-id"}]}
    get_call = gmail_client.service.users.return_value.messages.return_value.get.return_value
    # _parse_message を強制的に ValueError にする
    with patch.object(GmailClient, "_parse_message", side_effect=ValueError("boom")):
        get_call.execute.return_value = {"payload": {"body": {"data": "dummy"}}}
        with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
            gmail_client.get_verification_code()


# --- get_verification_code_by_id の _parse_message で ValueError を投げたときの汎用例外分岐 ---
def test_get_verification_code_by_id_parse_generic_error(gmail_client):
    """get_verification_code_by_id で _parse_message が ValueError を投げると GmailApiError にラップされることをテスト"""
    # service.get().execute() はダミーのメッセージを返す
    dummy_msg = {
        "payload": {"body": {"data": base64.urlsafe_b64encode(b"dummy").decode()}}
    }
    get_call = gmail_client.service.users.return_value.messages.return_value.get.return_value
    get_call.execute.return_value = dummy_msg

    with patch.object(GmailClient, "_parse_message", side_effect=ValueError("boom")):
        with pytest.raises(GmailApiError, match="Gmail APIのリクエストに失敗"):
            gmail_client.get_verification_code_by_id("any-id")


def test_get_verification_code_by_id_success(gmail_client, sample_message):
    """get_verification_code_by_id 正常系: コードが返ることをテスト"""
    # get().execute() が sample_message を返すように設定
    gmail_client.service.users() \
        .messages() \
        .get(return_value=MagicMock(execute=MagicMock(return_value=sample_message))) \
        .execute.return_value = sample_message

    code = gmail_client.get_verification_code_by_id("any-id")
    assert code == "123456"


def test_get_verification_code_success(gmail_client, sample_message):
    """get_verification_code 正常系: 最新メールからコードが返ることをテスト"""
    # list().execute() がメッセージIDを返す
    gmail_client.service.users() \
        .messages() \
        .list(return_value=MagicMock(execute=MagicMock(return_value={"messages": [{"id": "any-id"}]}))) \
        .execute.return_value = {"messages": [{"id": "any-id"}]}

    # get().execute() が sample_message を返す
    gmail_client.service.users() \
        .messages() \
        .get(return_value=MagicMock(execute=MagicMock(return_value=sample_message))) \
        .execute.return_value = sample_message

    code = gmail_client.get_verification_code()
    assert code == "123456"