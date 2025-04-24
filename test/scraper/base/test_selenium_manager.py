"""BaseSeleniumManagerのテスト。"""

import os
from unittest.mock import MagicMock, patch
import pytest
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException,
)
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from scraper.base.selenium_manager import BaseSeleniumManager
from exceptions.custom_exceptions import ScrapingError


# 各テストで共通して使用するフィクスチャ
@pytest.fixture
def manager():
    """BaseSeleniumManagerのインスタンスを提供。"""
    return BaseSeleniumManager()


@pytest.fixture
def mock_webdriver():
    """WebDriverのモックを提供。"""
    with patch("selenium.webdriver.Chrome") as mock:
        yield mock


@pytest.fixture
def mock_service():
    """Serviceのモックを提供。"""
    with patch("selenium.webdriver.chrome.service.Service") as mock:
        yield mock


def test_init(manager):
    """初期化のテスト。"""
    assert manager.driver is None
    assert manager.timeout > 0
    assert manager.retry_count > 0


def test_context_manager(manager, mock_webdriver, mock_service):
    """コンテキストマネージャのテスト。"""
    with patch("os.path.exists", return_value=True):
        with manager:
            assert manager.driver is not None
        assert manager.driver is None


def test_setup_driver_success(manager, mock_webdriver, mock_service):
    """setup_driverの成功時のテスト。"""
    with patch("os.path.exists", return_value=True):
        manager.setup_driver()
        assert manager.driver is not None
        mock_webdriver.assert_called_once()


def test_setup_driver_chrome_driver_not_found(manager):
    """ChromeDriverが見つからない場合のテスト。"""
    with patch("os.path.exists", return_value=False):
        with pytest.raises(ScrapingError, match="ChromeDriverが見つかりません"):
            manager.setup_driver()


def test_setup_driver_webdriver_exception(manager, mock_webdriver):
    """WebDriverの初期化に失敗した場合のテスト。"""
    mock_webdriver.side_effect = WebDriverException("Mock WebDriver Error")
    with patch("os.path.exists", return_value=True):
        with pytest.raises(ScrapingError, match="WebDriverの初期化に失敗"):
            manager.setup_driver()


def test_wait_and_find_element_success(manager):
    """wait_and_find_elementの成功時のテスト。"""
    mock_element = MagicMock(spec=WebElement)
    mock_driver = MagicMock(spec=WebDriver)
    mock_wait = MagicMock()
    mock_wait.until.return_value = mock_element

    with patch("selenium.webdriver.support.ui.WebDriverWait", return_value=mock_wait):
        manager.driver = mock_driver
        element = manager.wait_and_find_element(By.ID, "test-id")
        assert element == mock_element


def test_wait_and_find_element_timeout(manager):
    """wait_and_find_elementのタイムアウト時のテスト。"""
    mock_driver = MagicMock(spec=WebDriver)
    mock_wait = MagicMock()
    mock_wait.until.side_effect = TimeoutException("Timeout")

    with patch("selenium.webdriver.support.ui.WebDriverWait", return_value=mock_wait):
        manager.driver = mock_driver
        with pytest.raises(ScrapingError, match="要素が見つかりませんでした"):
            manager.wait_and_find_element(By.ID, "test-id")


def test_retry_operation_success(manager):
    """retry_operationの成功時のテスト。"""
    mock_operation = MagicMock()
    mock_operation.return_value = "success"

    result = manager.retry_operation(mock_operation, "arg1", kwarg1="value1")
    assert result == "success"
    mock_operation.assert_called_once_with("arg1", kwarg1="value1")


def test_retry_operation_retry_and_succeed(manager):
    """retry_operationのリトライ成功時のテスト。"""
    mock_operation = MagicMock()
    mock_operation.side_effect = [NoSuchElementException("Not found"), "success"]

    result = manager.retry_operation(mock_operation)
    assert result == "success"
    assert mock_operation.call_count == 2


def test_retry_operation_all_retries_fail(manager):
    """retry_operationの全リトライ失敗時のテスト。"""
    mock_operation = MagicMock()
    mock_operation.side_effect = NoSuchElementException("Not found")

    with pytest.raises(ScrapingError, match="操作が.*回失敗しました"):
        manager.retry_operation(mock_operation)

    assert mock_operation.call_count == manager.retry_count
