"""例外の基底クラスモジュール。"""

import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ErrorContext:
    """エラーに関する追加情報を保持するクラス。"""

    timestamp: datetime = field(default_factory=datetime.now)
    error_code: str = ""
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    traceback: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """エラーコンテキストを辞書形式で返す。"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "traceback": self.traceback,
        }


class BaseError(Exception):
    """カスタム例外の基底クラス。

    全てのカスタム例外の基底となるクラス。
    エラーコード、メッセージ、コンテキスト情報を保持する。
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初期化。

        Args:
            message: エラーメッセージ。
            error_code: エラーコード。指定しない場合はクラス名が使用される。
            details: エラーの詳細情報。
        """
        super().__init__(message)
        self.context = ErrorContext(
            error_code=error_code or self.__class__.__name__,
            message=message,
            details=details or {},
            traceback="".join(traceback.format_stack()),
        )

    def __str__(self) -> str:
        """エラーメッセージを文字列として返す。

        Returns:
            str: フォーマットされたエラーメッセージ。
        """
        return f"[{self.context.error_code}] {self.context.message}"

    def save_error_report(self, filepath: Optional[Path] = None) -> Path:
        """エラー情報をファイルに保存。

        Args:
            filepath: 保存先のパス。指定しない場合は自動生成。

        Returns:
            Path: 保存したファイルのパス。
        """
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = Path(f"error_report_{timestamp}.log")

        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                error_info = self.context.to_dict()
                for key, value in error_info.items():
                    f.write(f"{key}:\n{value}\n\n")
            logger.info("エラーレポートを保存しました: %s", filepath)
            return filepath
        except Exception as e:
            logger.error("エラーレポートの保存に失敗しました: %s", e)
            raise


class ExternalServiceError(BaseError):
    """外部サービス関連の基底例外クラス。"""

    def __init__(
        self,
        message: str,
        service_name: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初期化。

        Args:
            message: エラーメッセージ。
            service_name: 外部サービス名。
            error_code: エラーコード。
            details: エラーの詳細情報。
        """
        details = details or {}
        details["service_name"] = service_name
        super().__init__(message, error_code, details)


class ApplicationError(BaseError):
    """アプリケーション内部の基底例外クラス。"""

    def __init__(
        self,
        message: str,
        module_name: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初期化。

        Args:
            message: エラーメッセージ。
            module_name: エラーが発生したモジュール名。
            error_code: エラーコード。
            details: エラーの詳細情報。
        """
        details = details or {}
        details["module_name"] = module_name
        super().__init__(message, error_code, details)


class FileOperationError(ApplicationError):
    """ファイル操作関連の基底例外クラス。"""

    def __init__(
        self,
        message: str,
        file_path: Path,
        operation: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初期化。

        Args:
            message: エラーメッセージ。
            file_path: 対象ファイルのパス。
            operation: 実行しようとした操作。
            error_code: エラーコード。
            details: エラーの詳細情報。
        """
        details = details or {}
        details.update(
            {
                "file_path": str(file_path),
                "operation": operation,
            }
        )
        super().__init__(message, "file_operations", error_code, details)


class ValidationError(ApplicationError):
    """入力値検証関連の基底例外クラス。"""

    def __init__(
        self,
        message: str,
        field_name: str,
        invalid_value: Any,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """初期化。

        Args:
            message: エラーメッセージ。
            field_name: 検証に失敗したフィールド名。
            invalid_value: 不正な値。
            error_code: エラーコード。
            details: エラーの詳細情報。
        """
        details = details or {}
        details.update(
            {
                "field_name": field_name,
                "invalid_value": str(invalid_value),
            }
        )
        super().__init__(message, "validation", error_code, details)
