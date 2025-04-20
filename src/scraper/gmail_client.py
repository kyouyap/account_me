"""Gmail APIクライアントモジュール。"""

import base64
import datetime
import logging
import re
from email.mime.text import MIMEText
from typing import Optional, Tuple
import json
import os

import google.auth.exceptions
from config.secrets import update_secret
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from exceptions.custom_exceptions import GmailApiError, VerificationCodeError

logger = logging.getLogger(__name__)

class GmailClient:
    """Gmail APIを使用してメールを操作するクラス。"""

    def __init__(self) -> None:
        """初期化。"""
        self.auth_settings = {
            "sender": "do_not_reply@moneyforward.com",
            "subject": "Thank you for using your Money Forward ID",
            "code_pattern": r"\d{6}",
            "code_timeout_minutes": 10,
        }
        self.service = self._create_gmail_service()

    def _create_gmail_service(self):
        """Gmail APIサービスを作成。

        Returns:
            Resource: Gmail APIサービス

        Raises:
            GmailApiError: サービスの作成に失敗した場合
        """
        try:
            # 認証情報の取得
            creds_json = os.getenv("GMAIL_CREDENTIALS")
            if not creds_json:
                raise GmailApiError("GMAIL_CREDENTIALS環境変数が設定されていません")
            creds_data = json.loads(creds_json)
            creds = Credentials.from_authorized_user_info(creds_data)

            # 認証情報の有効性チェックと更新
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    # 更新された認証情報を保存
                    new_token = creds.to_json()
                    update_secret("gmail-api-token", new_token)
                else:
                    raise GmailApiError("認証情報が無効です")

            return build("gmail", "v1", credentials=creds)
        except Exception as e:
            raise GmailApiError(f"Gmailサービスの作成に失敗: {e}") from e

    def _parse_message(self, message: dict) -> Tuple[str, datetime.datetime]:
        """メッセージから認証コードと有効期限を抽出。

        Args:
            message: メッセージデータ

        Returns:
            Tuple[str, datetime.datetime]: 認証コードと有効期限

        Raises:
            VerificationCodeError: コードの抽出に失敗した場合
        """
        try:
            # メールの本文を取得
            if "parts" in message["payload"]:
                body = ""
                for part in message["payload"]["parts"]:
                    if part["mimeType"] == "text/plain":
                        body = base64.urlsafe_b64decode(part["body"]["data"]).decode()
                        break
            else:
                body = base64.urlsafe_b64decode(
                    message["payload"]["body"]["data"]
                ).decode()

            # 認証コードを抽出
            code_match = re.search(self.auth_settings["code_pattern"], body)
            if not code_match:
                raise VerificationCodeError("認証コードが見つかりません")
            code = code_match.group(0)

            # 有効期限を抽出
            expiry_pattern = r"valid for \d+ mins \((.*?)\)"
            expiry_match = re.search(expiry_pattern, body)
            if not expiry_match:
                raise VerificationCodeError("有効期限が見つかりません")
            expiry_str = expiry_match.group(1)
            expiry = datetime.datetime.strptime(
                expiry_str, "%B %d, %Y %H:%M:%S"
            ).replace(tzinfo=datetime.timezone(datetime.timedelta(hours=9)))

            return code, expiry

        except Exception as e:
            raise VerificationCodeError(f"メッセージの解析に失敗: {e}") from e

    def get_verification_code(self) -> str:
        """最新の認証コードを取得。

        Returns:
            str: 6桁の認証コード

        Raises:
            VerificationCodeError: 認証コードの取得に失敗した場合
        """
        try:
            # 認証メールを検索
            query = (
                f"from:{self.auth_settings['sender']} "
                f"subject:\"{self.auth_settings['subject']}\""
            )
            result = (
                self.service.users()
                .messages()
                .list(userId="me", q=query, maxResults=1)
                .execute()
            )

            messages = result.get("messages", [])
            if not messages:
                raise VerificationCodeError("認証メールが見つかりません")

            # メッセージの詳細を取得
            msg_id = messages[0]["id"]
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )

            # コードと有効期限を抽出
            code, expiry = self._parse_message(message)

            # 有効期限チェック
            now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
            if now > expiry:
                raise VerificationCodeError("認証コードの有効期限が切れています")

            return code

        except HttpError as e:
            raise GmailApiError(f"Gmail APIのリクエストに失敗: {e}") from e
        except Exception as e:
            raise VerificationCodeError(f"認証コードの取得に失敗: {e}") from e
