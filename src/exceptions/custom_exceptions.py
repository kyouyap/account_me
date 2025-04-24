"""カスタム例外モジュール。"""

from pathlib import Path
from typing import Any, Dict, Optional

from .base import ApplicationError, ExternalServiceError, FileOperationError


# 外部サービス関連の例外
class GmailApiError(ExternalServiceError):
    """Gmail API関連のエラー。"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初期化。"""
        super().__init__(message, "gmail", error_code, details)


class VerificationCodeError(GmailApiError):
    """認証コード取得に関するエラー。"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = "VERIFICATION_CODE_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初期化。"""
        super().__init__(message, error_code, details)


class MoneyForwardError(ExternalServiceError):
    """MoneyForward関連の基底例外クラス。"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初期化。"""
        super().__init__(message, "moneyforward", error_code, details)


class AuthenticationError(MoneyForwardError):
    """認証関連のエラー。"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = "AUTH_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初期化。"""
        super().__init__(message, error_code, details)


class ScrapingError(MoneyForwardError):
    """スクレイピング処理中のエラー。"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = "SCRAPING_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初期化。"""
        super().__init__(message, error_code, details)


class SpreadsheetError(ExternalServiceError):
    """Google Spreadsheet操作関連のエラー。"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初期化。"""
        super().__init__(message, "google_sheets", error_code, details)


# アプリケーション内部の例外
class ConfigurationError(ApplicationError):
    """設定関連のエラー。"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = "CONFIG_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初期化。"""
        super().__init__(message, "config", error_code, details)


class DownloadError(FileOperationError):
    """ファイルダウンロード関連のエラー。"""

    def __init__(
        self,
        message: str,
        file_path: Optional[Path] = None,
        error_code: Optional[str] = "DOWNLOAD_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初期化。"""
        super().__init__(
            message, file_path or Path("unknown"), "download", error_code, details
        )


class CSVProcessingError(FileOperationError):
    """CSV処理関連のエラー。"""

    def __init__(
        self,
        message: str,
        file_path: Optional[Path] = None,
        error_code: Optional[str] = "CSV_PROCESSING_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初期化。"""
        super().__init__(
            message, file_path or Path("unknown"), "csv_processing", error_code, details
        )
