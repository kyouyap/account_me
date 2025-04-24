"""ロギング設定管理モジュール。"""

import logging
import logging.config
import os
import sys
from pathlib import Path
import structlog
import yaml
from typing import Any  # 一行ずつimport
from typing import Dict
from typing import List
from typing import TypedDict
from typing import Union
from typing import cast

class FormatterConfig(TypedDict, total=False):
    """Formatterの設定型。"""
    format: str
    datefmt: str
    style: str
    validate: bool
    processor: Any
    foreign_pre_chain: List[Any]

class HandlerConfig(TypedDict, total=False):
    """Handlerの設定型。"""
    level: Union[int, str]
    class_: str
    formatter: str
    filters: List[str]
    filename: str
    maxBytes: int
    backupCount: int
    encoding: str

class LoggerConfig(TypedDict, total=False):
    """Loggerの設定型。"""
    handlers: List[str]
    level: Union[int, str]
    propagate: bool

def setup_shared_processors() -> List[structlog.typing.Processor]:
    """共通のstructlogプロセッサを設定。"""
    return [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

def setup_console_processor() -> structlog.typing.Processor:
    """コンソール出力用のプロセッサを設定。"""
    return structlog.dev.ConsoleRenderer(
        colors=True,
    )

def setup_json_processor() -> structlog.typing.Processor:
    """JSON出力用のプロセッサを設定。"""
    return structlog.processors.JSONRenderer()

def setup_structlog(log_level: int = logging.INFO) -> None:
    """structlogの設定を行う。"""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,  # ログレベルでのフィルタリング
            structlog.stdlib.add_logger_name,  # ロガー名の追加
            structlog.stdlib.add_log_level,  # ログレベルの追加
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        cache_logger_on_first_use=False,  # キャッシュを無効化
    )

def setup_stdlib_logging(log_dir: Path, log_level: int = logging.INFO) -> None:
    """標準ライブラリのloggingの設定を行う。"""
    handlers = {
        "console": {
            "level": log_level,
            "class": "logging.StreamHandler",
            "formatter": "colored",
        },
        "file": {
            "level": log_level,
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(log_dir / "app.log"),
            "maxBytes": 5 * 1024 * 1024,  # 5MB
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "json",
        },
    }

    formatters = {
        "colored": {
            "()": "structlog.stdlib.ProcessorFormatter",
            "processor": setup_console_processor(),
            "foreign_pre_chain": setup_shared_processors(),
        },
        "json": {
            "()": "structlog.stdlib.ProcessorFormatter",
            "processor": setup_json_processor(),
            "foreign_pre_chain": setup_shared_processors(),
        },
    }

    loggers = {
        "": {
            "handlers": ["console", "file"],
            "level": log_level,
            "propagate": True,
        },
    }

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "handlers": handlers,
        "loggers": loggers,
    }

    logging.config.dictConfig(config)

def setup_logging(config_path: Path | None = None) -> None:
    """
    ロギング設定を行う。

    Args:
        config_path: 設定ファイルのパス。指定がない場合はデフォルトの設定を使用。
    """
    base_dir = Path(os.getenv("APP_BASE_DIR", "/app"))
    config_path = config_path or base_dir / "config/logging.yaml"
    log_dir = base_dir / "log"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level = logging.INFO
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            log_level = getattr(logging, config.get("level", "INFO"))

    # 標準ライブラリのロギング設定を先に行う
    setup_stdlib_logging(log_dir, log_level)
    # structlogの設定を後で行う
    setup_structlog(log_level)

def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    ロガーを取得する。

    Args:
        name: ロガー名。指定がない場合は呼び出し元のモジュール名を使用。

    Returns:
        structlog.BoundLogger: 構造化ロガー
    """
    if name is None:
        # 呼び出し元のモジュール名を取得
        frame = sys._getframe(1)
        name = frame.f_globals["__name__"]

    return structlog.get_logger(name)
