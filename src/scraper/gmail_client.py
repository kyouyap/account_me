"""Gmail APIを使用した認証メール処理モジュール。

このモジュールは、MoneyForwardの2段階認証メールをGmail APIを通じて処理します。
認証メールの検索、認証コードの抽出、有効期限の確認などの機能を提供します。

定数:
    - CODE_PATTERN: 認証コードを抽出するための正規表現パターン
    - EXPIRY_PATTERN: 有効期限を抽出するための正規表現パターン

主な機能:
    - Gmail APIの認証と接続管理
    - 認証メールの検索と取得
    - 認証コードの抽出
    - 認証コードの有効期限確認
    - APIトークンの自動更新と保存

使用するスコープ:
    - gmail.readonly: メールの読み取り
    - gmail.modify: メールの変更（既読マークなど）

Note:
    - 適切なGmail API認証情報が必要です
    - Secret Managerでトークンを管理します
    - 日本時間（UTC+9）で有効期限を処理します

"""

import base64
import datetime
import json
import logging
import os
import re
from typing import TypedDict

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient import discovery
from googleapiclient.errors import HttpError

from config.secrets import update_secret
from exceptions.custom_exceptions import GmailApiError, VerificationCodeError

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

# プリコンパイルされた正規表現パターン
CODE_PATTERN = re.compile(r"\d{6}")
EXPIRY_PATTERN = re.compile(r"valid for \d+ mins \((.*?)\)")


class AuthSettings(TypedDict):
    """認証設定を定義する型。

    Attributes:
        sender (str): 認証メールの送信者アドレス
        subject (str): 認証メールの件名
        code_pattern (str): 認証コードを抽出する正規表現パターン
        code_timeout_minutes (int): 認証コードの有効期限（分）

    """

    sender: str
    subject: str
    code_pattern: str
    code_timeout_minutes: int


class GmailClient:
    """Gmail APIを使用して認証メールを処理するクラス。

    このクラスは、MoneyForwardからの2段階認証メールを処理するための
    機能を提供します。Gmail APIを使用してメールを検索し、認証コードを
    抽出します。

    Attributes:
        auth_settings (AuthSettings): 認証メールの検索と解析に関する設定
        service: Gmail APIサービスのインスタンス

    使用例:
        ```python
        client = GmailClient()
        code = client.get_verification_code()
        print(f"認証コード: {code}")
        ```

    """

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

    def _get_client_config(self) -> dict:
        """クライアント設定を環境変数から取得。

        Returns:
            dict: クライアント設定

        Raises:
            GmailApiError: 設定の取得に失敗した場合

        """
        client_secrets_str = os.getenv("GMAIL_CREDENTIALS")
        if not client_secrets_str:
            logger.error("GMAIL_CREDENTIALS環境変数が設定されていません")
            raise GmailApiError("GMAIL_CREDENTIALS環境変数が設定されていません")

        logger.info("クライアント設定のJSONをパース")
        return json.loads(client_secrets_str)

    def _get_existing_credentials(self) -> Credentials | None:
        """既存のクレデンシャルを取得。

        Returns:
            Credentials | None: 有効なクレデンシャルまたはNone

        """
        token_str = os.getenv("GMAIL_API_TOKEN")
        if not token_str:
            return None

        try:
            logger.info("Secret Managerからトークンを取得")
            token_data = json.loads(token_str)
            creds = Credentials.from_authorized_user_info(token_data, scopes=SCOPES)
            logger.info("Secret Managerからの既存トークンでの認証に成功")
            return creds
        except Exception as e:
            logger.warning("Secret Managerからのトークン取得に失敗: %s", e)
            return None

    def _refresh_credentials(self, creds: Credentials) -> Credentials:
        """クレデンシャルを更新。

        Args:
            creds: 更新するクレデンシャル

        Returns:
            Credentials: 更新されたクレデンシャル

        """
        logger.info("期限切れトークンを更新")
        creds.refresh(Request())
        logger.info("更新されたトークンをSecret Managerに保存")
        update_secret("gmail-api-token", creds.to_json())
        return creds

    def _create_new_credentials(self, client_config: dict) -> Credentials:
        """新規クレデンシャルを作成。

        Args:
            client_config: クライアント設定

        Returns:
            Credentials: 新規作成されたクレデンシャル

        """
        logger.info("新規認証フローを開始")
        flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
        creds = flow.run_local_server(port=0)
        logger.info("新規認証フローが完了")
        logger.info("新規トークンをSecret Managerに保存")
        update_secret("gmail-api-token", creds.to_json())
        return creds

    def _create_gmail_service(self):
        """Gmail APIサービスを作成。

        Returns:
            Resource: Gmail APIサービス

        Raises:
            GmailApiError: サービスの作成に失敗した場合

        """
        try:
            logger.info("Gmail APIサービスの作成を開始")
            client_config = self._get_client_config()
            creds = self._get_existing_credentials()

            if not creds or not creds.valid:
                # 期限切れのクレデンシャルを更新
                if creds and creds.expired and creds.refresh_token:
                    creds = self._refresh_credentials(creds)
                # 新規クレデンシャルを作成
                else:
                    creds = self._create_new_credentials(client_config)

            logger.info("Gmail APIサービスのビルドを開始")
            service = discovery.build("gmail", "v1", credentials=creds)
            logger.info("Gmail APIサービスの作成が完了")
            return service

        except Exception as e:
            logger.error("Gmailサービスの作成中にエラーが発生: %s", e)
            raise GmailApiError(f"Gmailサービスの作成に失敗: {e}") from e

    def _extract_email_body(self, message: dict) -> str:
        """メール本文を抽出。

        Args:
            message: メッセージデータ

        Returns:
            str: メール本文

        Raises:
            VerificationCodeError: 本文の抽出に失敗した場合

        """
        logger.info("メール本文の解析を開始")

        if "parts" in message["payload"]:
            logger.info("マルチパートメールを処理")
            for part in message["payload"]["parts"]:
                if part["mimeType"] == "text/plain":
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode()
                    logger.info("text/plain パートを見つけました")
                    return body
            raise VerificationCodeError("text/plainパートが見つかりません")

        logger.info("シングルパートメールを処理")
        body = base64.urlsafe_b64decode(message["payload"]["body"]["data"]).decode()
        logger.info("メール本文の取得が完了")
        return body

    def _extract_verification_code(self, body: str) -> str:
        """認証コードを抽出。

        Args:
            body: メール本文

        Returns:
            str: 認証コード

        Raises:
            VerificationCodeError: コードの抽出に失敗した場合

        """
        logger.info("認証コードのパターンマッチを試行")
        code_match = CODE_PATTERN.search(body)
        if not code_match:
            logger.error("認証コードのパターンが本文中に見つかりません")
            logger.error("メール本文: %s", body)
            raise VerificationCodeError("認証コードが見つかりません")

        code = code_match.group(0)
        logger.info("認証コードを抽出しました: %s", code)
        return code

    def _extract_expiry_time(self, body: str) -> datetime.datetime:
        """有効期限を抽出。

        Args:
            body: メール本文

        Returns:
            datetime.datetime: 有効期限

        Raises:
            VerificationCodeError: 有効期限の抽出に失敗した場合

        """
        logger.info("有効期限のパターンマッチを試行")
        expiry_match = EXPIRY_PATTERN.search(body)
        if not expiry_match:
            logger.error("有効期限のパターンが本文中に見つかりません")
            logger.error("メール本文: %s", body)
            raise VerificationCodeError("有効期限が見つかりません")

        expiry_str = expiry_match.group(1)
        logger.info("有効期限の文字列を抽出: %s", expiry_str)

        expiry = datetime.datetime.strptime(expiry_str, "%B %d, %Y %H:%M:%S").replace(
            tzinfo=datetime.timezone(datetime.timedelta(hours=9))
        )
        logger.info("有効期限を解析しました: %s", expiry)
        return expiry

    def _parse_message(self, message: dict) -> tuple[str, datetime.datetime]:
        """メッセージから認証コードと有効期限を抽出。

        Args:
            message: メッセージデータ

        Returns:
            Tuple[str, datetime.datetime]: 認証コードと有効期限

        Raises:
            VerificationCodeError: コードの抽出に失敗した場合

        """
        try:
            body = self._extract_email_body(message)
            code = self._extract_verification_code(body)
            expiry = self._extract_expiry_time(body)
            return code, expiry
        except Exception as e:
            logger.error("メッセージの解析中にエラーが発生: %s", e)
            if isinstance(e, VerificationCodeError):
                raise
            raise VerificationCodeError(f"メッセージの解析に失敗: {e}") from e

    def get_verification_email_ids(self, max_results: int = 5) -> list[str]:
        """認証メールのIDリストを取得。

        Args:
            max_results (int): 取得するメールの最大数。デフォルトは5。

        Returns:
            list[str]: メールIDのリスト

        Raises:
            VerificationCodeError: メールの取得に失敗した場合

        """
        query = (
            f"from:{self.auth_settings['sender']} "
            f'subject:"{self.auth_settings["subject"]}"'
        )
        logger.info("メール検索クエリ: %s", query)

        try:
            logger.info("Gmail APIでメールを検索")
            result = (
                self.service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
        except (TimeoutError, HttpError) as e:
            logger.error("Gmail APIのリクエストに失敗: %s", e)
            raise GmailApiError(f"Gmail APIのリクエストに失敗: {e}") from e

        logger.info("メール検索が完了 (最大%d件)", max_results)

        if result is None:
            logger.error("メール検索結果がNoneでした")
            raise VerificationCodeError("認証メールが見つかりません")

        messages = result.get("messages", [])
        logger.info("検索結果のメール数: %d", len(messages))

        if not messages:
            logger.warning("認証メールが見つかりませんでした")
            return []

        return [msg["id"] for msg in messages]

    def get_verification_code_by_id(self, msg_id: str) -> str:
        """指定されたIDのメールから認証コードを取得。

        Args:
            msg_id: メールID

        Returns:
            str: 認証コード

        Raises:
            VerificationCodeError: コードの取得に失敗した場合

        """
        logger.info("メールID: %s の取得を開始", msg_id)

        try:
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
        except (TimeoutError, HttpError) as e:
            logger.error("Gmail APIのリクエストに失敗: %s", e)
            raise GmailApiError(f"Gmail APIのリクエストに失敗: {e}") from e

        logger.info("メールの取得に成功しました")

        if message is None:
            logger.error("メール本文の取得結果がNoneでした")
            raise VerificationCodeError("メッセージの解析に失敗")

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

    def get_verification_code(self) -> str:
        """有効な最新の認証メールから認証コードを取得します。

        直近のメールから順に確認し、有効期限内のコードが見つかった時点で返します。

        Returns:
            str: 6桁の認証コード

        Raises:
            VerificationCodeError: 有効な認証コードが見つからない場合
            GmailApiError: Gmail APIのリクエストに失敗した場合

        """
        logger.info("有効な認証コードの取得処理を開始")

        email_ids = self.get_verification_email_ids()
        if not email_ids:
            logger.error("検索対象の認証メールが見つかりませんでした")
            raise VerificationCodeError("認証メールが見つかりません")

        logger.info("取得したメールIDリスト: %s", email_ids)

        for msg_id in email_ids:
            logger.info("メールID: %s の認証コード取得を試行", msg_id)
            try:
                code = self.get_verification_code_by_id(msg_id)
                logger.info(
                    "有効な認証コードが見つかりました: %s (メールID: %s)",
                    code,
                    msg_id,
                )
                return code
            except VerificationCodeError as e:
                logger.warning(
                    "メールID: %s のコード取得に失敗（次のメールを試行）: %s",
                    msg_id,
                    e,
                )
                continue
            except Exception as e:
                logger.error("認証コードの取得中にエラーが発生: %s", e)
                raise GmailApiError(f"Gmail APIのリクエストに失敗: {e}") from e

        # ループが終了しても有効なコードが見つからなかった場合
        logger.error("試行した全てのメールで有効な認証コードが見つかりませんでした")
        raise VerificationCodeError("有効な認証コードが見つかりませんでした")
