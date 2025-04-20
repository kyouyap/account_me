"""カスタム例外モジュール。"""

class GmailApiError(Exception):
    """Gmail API関連のエラー。"""

class VerificationCodeError(GmailApiError):
    """認証コード取得に関するエラー。"""

class MoneyForwardError(Exception):
    """MoneyForwardスクレイピング関連の基底例外クラス。"""

class AuthenticationError(MoneyForwardError):
    """認証関連のエラー。"""

class ScrapingError(MoneyForwardError):
    """スクレイピング処理中のエラー。"""

class DownloadError(MoneyForwardError):
    """ファイルダウンロード関連のエラー。"""

class SpreadsheetError(MoneyForwardError):
    """Google Spreadsheet操作関連のエラー。"""

class ConfigurationError(MoneyForwardError):
    """設定関連のエラー。"""
