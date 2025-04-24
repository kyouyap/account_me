"""例外クラスのテスト。"""

from datetime import datetime
from pathlib import Path
import pytest

from exceptions.base import (
    BaseError,
    ExternalServiceError,
    ApplicationError,
    FileOperationError,
    ValidationError,
)
from exceptions.custom_exceptions import (
    GmailApiError,
    VerificationCodeError,
    MoneyForwardError,
    AuthenticationError,
    ScrapingError,
    SpreadsheetError,
    ConfigurationError,
    DownloadError,
    CSVProcessingError,
)


class TestBaseError:
    """BaseErrorのテスト。"""

    def test_base_error_initialization(self):
        """基本的な初期化のテスト。"""
        error = BaseError("テストエラー")
        assert str(error) == "[BaseError] テストエラー"
        assert error.context.message == "テストエラー"
        assert error.context.error_code == "BaseError"

    def test_base_error_with_custom_code(self):
        """カスタムエラーコードでの初期化テスト。"""
        error = BaseError("テストエラー", "TEST_ERR_001")
        assert str(error) == "[TEST_ERR_001] テストエラー"
        assert error.context.error_code == "TEST_ERR_001"

    def test_base_error_with_details(self):
        """詳細情報付きの初期化テスト。"""
        details = {"key": "value"}
        error = BaseError("テストエラー", details=details)
        assert error.context.details == details

    def test_error_report_creation(self, tmp_path):
        """エラーレポート作成のテスト。"""
        error = BaseError("テストエラー")
        report_path = error.save_error_report(tmp_path / "error_report.log")

        assert report_path.exists()
        content = report_path.read_text()
        assert "テストエラー" in content
        assert "BaseError" in content
        assert "timestamp" in content


class TestExternalServiceError:
    """ExternalServiceErrorのテスト。"""

    def test_external_service_error(self):
        """外部サービスエラーの初期化テスト。"""
        error = ExternalServiceError("API接続エラー", "test_service")
        assert "test_service" in error.context.details["service_name"]


class TestApplicationError:
    """ApplicationErrorのテスト。"""

    def test_application_error(self):
        """アプリケーションエラーの初期化テスト。"""
        error = ApplicationError("内部エラー", "test_module")
        assert "test_module" in error.context.details["module_name"]


class TestFileOperationError:
    """FileOperationErrorのテスト。"""

    def test_file_operation_error(self):
        """ファイル操作エラーの初期化テスト。"""
        path = Path("/test/file.txt")
        error = FileOperationError("ファイルエラー", path, "read")
        assert str(path) == error.context.details["file_path"]
        assert "read" == error.context.details["operation"]


class TestValidationError:
    """ValidationErrorのテスト。"""

    def test_validation_error(self):
        """バリデーションエラーの初期化テスト。"""
        error = ValidationError("不正な値", "test_field", "invalid_value")
        assert "test_field" == error.context.details["field_name"]
        assert "invalid_value" == error.context.details["invalid_value"]


class TestCustomExceptions:
    """カスタム例外クラスのテスト。"""

    def test_gmail_api_error(self):
        """GmailApiErrorのテスト。"""
        error = GmailApiError("Gmail APIエラー")
        assert "gmail" == error.context.details["service_name"]

    def test_verification_code_error(self):
        """VerificationCodeErrorのテスト。"""
        error = VerificationCodeError("認証コードエラー")
        assert "VERIFICATION_CODE_ERROR" == error.context.error_code

    def test_moneyforward_error(self):
        """MoneyForwardErrorのテスト。"""
        error = MoneyForwardError("MoneyForwardエラー")
        assert "moneyforward" == error.context.details["service_name"]

    def test_authentication_error(self):
        """AuthenticationErrorのテスト。"""
        error = AuthenticationError("認証エラー")
        assert "AUTH_ERROR" == error.context.error_code

    def test_scraping_error(self):
        """ScrapingErrorのテスト。"""
        error = ScrapingError("スクレイピングエラー")
        assert "SCRAPING_ERROR" == error.context.error_code

    def test_spreadsheet_error(self):
        """SpreadsheetErrorのテスト。"""
        error = SpreadsheetError("スプレッドシートエラー")
        assert "google_sheets" == error.context.details["service_name"]

    def test_configuration_error(self):
        """ConfigurationErrorのテスト。"""
        error = ConfigurationError("設定エラー")
        assert "CONFIG_ERROR" == error.context.error_code

    def test_download_error(self):
        """DownloadErrorのテスト。"""
        error = DownloadError("ダウンロードエラー")
        assert "DOWNLOAD_ERROR" == error.context.error_code
        assert "download" == error.context.details["operation"]

    def test_csv_processing_error(self):
        """CSVProcessingErrorのテスト。"""
        error = CSVProcessingError("CSV処理エラー")
        assert "CSV_PROCESSING_ERROR" == error.context.error_code
        assert "csv_processing" == error.context.details["operation"]


class TestErrorContextUsage:
    """エラーコンテキストの使用例のテスト。"""

    def test_error_context_in_exception_handling(self):
        """例外処理でのエラーコンテキスト使用テスト。"""
        try:
            raise DownloadError(
                "ファイルのダウンロードに失敗",
                Path("/test/file.csv"),
                details={"url": "http://example.com/file.csv"},
            )
        except DownloadError as e:
            assert "ファイルのダウンロードに失敗" in str(e)
            assert "/test/file.csv" in e.context.details["file_path"]
            assert "http://example.com/file.csv" == e.context.details["url"]

    def test_error_report_contains_all_information(self, tmp_path):
        """エラーレポートの情報完全性テスト。"""
        details = {"url": "http://example.com/file.csv", "status_code": 404}
        error = DownloadError(
            "ファイルのダウンロードに失敗", Path("/test/file.csv"), details=details
        )

        report_path = error.save_error_report(tmp_path / "error_report.log")
        content = report_path.read_text()

        # 全ての重要な情報が含まれていることを確認
        assert "DOWNLOAD_ERROR" in content
        assert "ファイルのダウンロードに失敗" in content
        assert "/test/file.csv" in content
        assert "http://example.com/file.csv" in content
        assert "404" in content
        assert "traceback" in content
