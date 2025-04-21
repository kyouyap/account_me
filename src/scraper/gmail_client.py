"""Gmail APIクライアントモジュール。"""

import base64
import datetime
import logging
import re
import socket
from typing import Tuple, TypedDict
import json
import os

from config.secrets import update_secret
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from exceptions.custom_exceptions import GmailApiError, VerificationCodeError

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


class AuthSettings(TypedDict):
    """認証設定の型定義。"""

    sender: str
    subject: str
    code_pattern: str
    code_timeout_minutes: int


class GmailClient:
    """Gmail APIを使用してメールを操作するクラス。"""

    auth_settings: AuthSettings

    def __init__(self) -> None:
        """初期化。"""
        self.auth_settings: AuthSettings = {
            "sender": "do_not_reply@moneyforward.com",
            "subject": "Money Forward ID Additional Authentication via Email",
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
            logger.info("Gmail APIサービスの作成を開始")

            try:
                # クライアントシークレットの取得
                client_secrets_str = os.getenv("GMAIL_CREDENTIALS")
                if not client_secrets_str:
                    logger.error("GMAIL_CREDENTIALS環境変数が設定されていません")
                    raise GmailApiError("GMAIL_CREDENTIALS環境変数が設定されていません")

                logger.info("クライアント設定のJSONをパース")
                client_config = json.loads(client_secrets_str)

                # Secret Managerからトークンを取得
                creds = None
                token_str = os.getenv("GMAIL_API_TOKEN")
                if token_str:
                    try:
                        logger.info("Secret Managerからトークンを取得")
                        token_data = json.loads(token_str)
                        creds = Credentials.from_authorized_user_info(
                            token_data, scopes=SCOPES
                        )
                        logger.info("Secret Managerからの既存トークンでの認証に成功")
                    except Exception as e:
                        logger.warning("Secret Managerからのトークン取得に失敗: %s", e)

                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        logger.info("期限切れトークンを更新")
                        creds.refresh(Request())
                        # 更新されたトークンを保存
                        logger.info("更新されたトークンをSecret Managerに保存")
                        update_secret("gmail-api-token", creds.to_json())
                    else:
                        logger.info("新規認証フローを開始")
                        flow = InstalledAppFlow.from_client_config(
                            client_config, scopes=SCOPES
                        )
                        creds = flow.run_local_server(port=0)
                        logger.info("新規認証フローが完了")

                        # 新規トークンをSecret Managerに保存
                        logger.info("新規トークンをSecret Managerに保存")
                        update_secret("gmail-api-token", creds.to_json())

                logger.info("Gmail APIサービスのビルドを開始")
                service = build("gmail", "v1", credentials=creds)
                logger.info("Gmail APIサービスの作成が完了")
                return service

            except Exception as e:
                logger.error("認証処理中にエラーが発生: %s", e)
                raise GmailApiError(f"認証処理に失敗: {e}") from e
        except Exception as e:
            logger.error("Gmailサービスの作成中にエラーが発生: %s", e)
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
            logger.info("メール本文の解析を開始")
            body = ""
            if "parts" in message["payload"]:
                logger.info("マルチパートメールを処理")
                for part in message["payload"]["parts"]:
                    if part["mimeType"] == "text/plain":
                        body = base64.urlsafe_b64decode(part["body"]["data"]).decode()
                        logger.info("text/plain パートを見つけました")
                        break
            else:
                logger.info("シングルパートメールを処理")
                body = base64.urlsafe_b64decode(
                    message["payload"]["body"]["data"]
                ).decode()

            logger.info("メール本文の取得が完了")

            # 認証コードを抽出
            logger.info(
                "認証コードのパターンマッチを試行: %s",
                self.auth_settings["code_pattern"],
            )
            code_match = re.search(self.auth_settings["code_pattern"], body)
            if not code_match:
                logger.error("認証コードのパターンが本文中に見つかりません")
                logger.error("メール本文: %s", body)
                raise VerificationCodeError("認証コードが見つかりません")
            code = code_match.group(0)
            logger.info("認証コードを抽出しました: %s", code)

            # 有効期限を抽出
            logger.info("有効期限のパターンマッチを試行")
            expiry_pattern = r"valid for \d+ mins \((.*?)\)"
            expiry_match = re.search(expiry_pattern, body)
            if not expiry_match:
                logger.error("有効期限のパターンが本文中に見つかりません")
                logger.error("メール本文: %s", body)
                raise VerificationCodeError("有効期限が見つかりません")
            expiry_str = expiry_match.group(1)
            logger.info("有効期限の文字列を抽出: %s", expiry_str)

            expiry = datetime.datetime.strptime(
                expiry_str, "%B %d, %Y %H:%M:%S"
            ).replace(tzinfo=datetime.timezone(datetime.timedelta(hours=9)))
            logger.info("有効期限を解析しました: %s", expiry)

            return code, expiry

        except Exception as e:
            logger.error("メッセージの解析中にエラーが発生: %s", e)
            raise VerificationCodeError(f"メッセージの解析に失敗: {e}") from e

    def get_latest_verification_email_id(self) -> str:
        """最新の認証メールのIDを取得。

        Returns:
            str: メールID

        Raises:
            VerificationCodeError: メールの取得に失敗した場合
        """
        try:
            # 認証メールを検索
            query = (
                f"from:{self.auth_settings['sender']} "
                f'subject:"{self.auth_settings["subject"]}"'
            )

            logger.info("メール検索クエリ: %s", query)

            logger.info("Gmail APIでメールを検索")
            result = (
                self.service.users()
                .messages()
                .list(userId="me", q=query, maxResults=1)
                .execute()
            )
            logger.info("メール検索が完了")

            if result is None:
                logger.error("メール検索結果がNoneでした")
                raise VerificationCodeError("認証メールが見つかりません")

            messages = result.get("messages", [])
            logger.info("検索結果のメール数: %d", len(messages))
            if not messages:
                logger.error("認証メールが見つかりませんでした")
                raise VerificationCodeError("認証メールが見つかりません")

            return messages[0]["id"]

        except (HttpError, socket.timeout) as e:
            logger.error("Gmail APIのリクエストに失敗: %s", e)
            raise GmailApiError(f"Gmail APIのリクエストに失敗: {e}") from e
        except VerificationCodeError:
            raise
        except Exception as e:
            logger.error("認証メールの取得に失敗: %s", e)
            raise GmailApiError(f"Gmail APIのリクエストに失敗: {e}") from e

    def get_verification_code_by_id(self, msg_id: str) -> str:
        """指定されたIDのメールから認証コードを取得。

        Args:
            msg_id: メールID

        Returns:
            str: 認証コード

        Raises:
            VerificationCodeError: コードの取得に失敗した場合
        """
        try:
            # メッセージの詳細を取得
            logger.info("メールID: %s の取得を開始", msg_id)
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
            logger.info("メールの取得に成功しました")

            if message is None:
                logger.error("メール本文の取得結果がNoneでした")
                raise VerificationCodeError("メッセージの解析に失敗")

            # コードと有効期限を抽出
            logger.info("メールの内容を解析します")
            code, expiry = self._parse_message(message)
            logger.info("認証コード: %s, 有効期限: %s を抽出しました", code, expiry)

            # 有効期限チェック
            now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
            logger.info("現在時刻: %s", now)
            if now > expiry:
                raise VerificationCodeError("認証コードの有効期限が切れています")

            logger.info("認証コードの取得に成功しました")
            return code

        except (HttpError, socket.timeout) as e:
            logger.error("Gmail APIのリクエストに失敗: %s", e)
            raise GmailApiError(f"Gmail APIのリクエストに失敗: {e}") from e
        except VerificationCodeError:
            raise
        except Exception as e:
            logger.error("認証コードの取得に失敗: %s", e)
            raise GmailApiError(f"Gmail APIのリクエストに失敗: {e}") from e

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
                f'subject:"{self.auth_settings["subject"]}"'
            )

            logger.info("メール検索クエリ: %s", query)

            logger.info("Gmail APIでメールを検索")
            result = (
                self.service.users()
                .messages()
                .list(userId="me", q=query, maxResults=1)
                .execute()
            )
            logger.info("メール検索が完了")

            if result is None:
                logger.error("メール検索結果がNoneでした")
                raise VerificationCodeError("認証メールが見つかりません")

            messages = result.get("messages", [])
            logger.info("検索結果のメール数: %d", len(messages))
            if not messages:
                logger.error("認証メールが見つかりませんでした")
                raise VerificationCodeError("認証メールが見つかりません")

            # メッセージの詳細を取得
            msg_id = messages[0]["id"]
            logger.info("最新のメールID: %s を取得します", msg_id)
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
            logger.info("メールの取得に成功しました")

            if message is None:
                logger.error("メール本文の取得結果がNoneでした")
                raise VerificationCodeError("メッセージの解析に失敗")

            # コードと有効期限を抽出
            logger.info("メールの内容を解析します")
            code, expiry = self._parse_message(message)
            logger.info("認証コード: %s, 有効期限: %s を抽出しました", code, expiry)

            # 有効期限チェック
            now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
            logger.info("現在時刻: %s", now)
            if now > expiry:
                raise VerificationCodeError("認証コードの有効期限が切れています")

            logger.info("認証コードの取得に成功しました")
            return code

        except (HttpError, socket.timeout) as e:
            logger.error("Gmail APIのリクエストに失敗: %s", e)
            raise GmailApiError(f"Gmail APIのリクエストに失敗: {e}") from e
        except VerificationCodeError:
            raise
        except Exception as e:
            logger.error("認証コードの取得に失敗: %s", e)
            raise GmailApiError(f"Gmail APIのリクエストに失敗: {e}") from e
