import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

import config.secrets as secrets_mod
import scraper.scraper as scraper_module
from exceptions.custom_exceptions import MoneyForwardError
from scraper.scraper import MoneyForwardScraper


@pytest.fixture(autouse=True)
def patch_get_secrets(monkeypatch):
    """
    MoneyForwardScraper.__init__ 内で呼ばれる get_secrets() を
    no-op に置き換えて SecretManager 呼び出しを抑制。
    """
    monkeypatch.setattr(secrets_mod, "get_secrets", lambda: None)


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    """各テスト前後に EMAIL/PASSWORD 環境変数をクリア。"""
    monkeypatch.delenv("EMAIL", raising=False)
    monkeypatch.delenv("PASSWORD", raising=False)
    yield
    monkeypatch.delenv("EMAIL", raising=False)
    monkeypatch.delenv("PASSWORD", raising=False)


@pytest.fixture
def scraper():
    """パッチ済み get_secrets() 付きのスクレイパーを生成。"""
    return MoneyForwardScraper()


@pytest.fixture
def mock_env(monkeypatch):
    """テスト用の環境変数を設定。"""
    monkeypatch.setenv("EMAIL", "user@example.com")
    monkeypatch.setenv("PASSWORD", "pass123")
    return {"EMAIL": "user@example.com", "PASSWORD": "pass123"}


def test_init_calls_get_secrets(monkeypatch):
    called = {"flag": False}

    def fake_get_secrets():
        called["flag"] = True

    monkeypatch.setattr(secrets_mod, "get_secrets", fake_get_secrets)
    scraper = MoneyForwardScraper()
    assert called["flag"], "get_secrets() が呼ばれていません"
    assert isinstance(scraper.download_dir, Path)
    assert scraper.browser_manager is not None
    assert scraper.file_downloader is not None


def test_check_env_variables_success(scraper, mock_env):
    scraper._check_env_variables()


def test_check_env_variables_failure(scraper):
    with pytest.raises(MoneyForwardError) as exc:
        scraper._check_env_variables()
    assert "環境変数が設定されていません" in str(exc.value)


def test_clean_directories_success(tmp_path, scraper, monkeypatch):
    detail = tmp_path / "d1"
    assets = tmp_path / "d2"
    detail.mkdir()
    assets.mkdir()
    (detail / "a.txt").write_text("x")
    (assets / "b.txt").write_text("y")
    fake_settings = MagicMock()
    fake_settings.paths.outputs.aggregated_files.detail = str(detail)
    fake_settings.paths.outputs.aggregated_files.assets = str(assets)
    monkeypatch.setattr(scraper_module, "settings", fake_settings)
    cleaned = {"ok": False}
    scraper.file_downloader.clean_download_dir = lambda: cleaned.update(ok=True)
    scraper._clean_directories()
    assert cleaned["ok"], "download_dir のクリーンが呼ばれていません"
    assert list(detail.iterdir()) == []
    assert list(assets.iterdir()) == []


def test_clean_directories_make_dirs(tmp_path, scraper, monkeypatch):
    d1 = tmp_path / "nd1"
    d2 = tmp_path / "nd2"
    fake_settings = MagicMock()
    fake_settings.paths.outputs.aggregated_files.detail = str(d1)
    fake_settings.paths.outputs.aggregated_files.assets = str(d2)
    monkeypatch.setattr(scraper_module, "settings", fake_settings)
    scraper.file_downloader.clean_download_dir = lambda: None
    scraper._clean_directories()
    assert d1.exists() and d2.exists(), "ディレクトリが作成されていません"


def test_clean_directories_download_error(scraper):
    scraper.file_downloader.clean_download_dir = lambda: (_ for _ in ()).throw(
        OSError("fail")
    )
    scraper._clean_directories()  # 例外なし


def test_clean_directories_file_removal_error(scraper, monkeypatch):
    fake_settings = MagicMock()
    fake_settings.paths.outputs.aggregated_files.detail = "dummy"
    fake_settings.paths.outputs.aggregated_files.assets = "dummy"
    monkeypatch.setattr(scraper_module, "settings", fake_settings)
    scraper.file_downloader.clean_download_dir = lambda: None

    class FakeFile:
        def unlink(self):
            raise OSError("unlink fail")

    class FakePath:
        def __init__(self, *args, **kw):
            pass

        def exists(self):
            return True

        def glob(self, pattern):
            return [FakeFile()]

        def mkdir(self, parents):
            pass

    monkeypatch.setattr(scraper_module, "Path", FakePath)
    scraper._clean_directories()


def test_clean_directories_dir_op_error(scraper, monkeypatch):
    fake_settings = MagicMock()
    fake_settings.paths.outputs.aggregated_files.detail = "x"
    fake_settings.paths.outputs.aggregated_files.assets = "x"
    monkeypatch.setattr(scraper_module, "settings", fake_settings)
    scraper.file_downloader.clean_download_dir = lambda: None

    class FakePath:
        def __init__(self, *args, **kw):
            pass

        def exists(self):
            raise OSError("op fail")

        def glob(self, pattern):
            return []

        def mkdir(self, parents):
            pass

    monkeypatch.setattr(scraper_module, "Path", FakePath)
    scraper._clean_directories()


@pytest.mark.parametrize(
    "encoding,data",
    [
        ("utf-8", "c1,c2\nx,1"),
        ("shift-jis", "a,b\nあ,2"),
        ("cp932", "d,e\nい,3"),
    ],
)
def test_read_csv_with_encoding_success(scraper, tmp_path, encoding, data):
    fp = tmp_path / "f.csv"
    fp.write_bytes(data.encode(encoding))
    df = scraper._read_csv_with_encoding(fp)
    assert isinstance(df, pd.DataFrame)


def test_read_csv_with_encoding_empty(scraper, tmp_path):
    fp = tmp_path / "e.csv"
    fp.write_text("")
    assert scraper._read_csv_with_encoding(fp) is None


def test_read_csv_with_encoding_errors(scraper, tmp_path):
    fp = tmp_path / "f.csv"
    fp.write_text("x")
    err = UnicodeDecodeError("utf-8", b"", 0, 1, "reason")
    with patch("pandas.read_csv", side_effect=err):
        assert scraper._read_csv_with_encoding(fp) is None
    with patch("pandas.read_csv", side_effect=Exception("boom")):
        assert scraper._read_csv_with_encoding(fp) is None


def test_read_csv_with_encoding_header_only(scraper, tmp_path):
    fp = tmp_path / "header_only.csv"
    fp.write_text("col1,col2\n")
    assert scraper._read_csv_with_encoding(fp) is None


def test_aggregate_csv_files_no_files(scraper, tmp_path):
    scraper.download_dir = tmp_path
    assert scraper._aggregate_csv_files(tmp_path / "o.csv") is None


def test_aggregate_csv_files_success(tmp_path, scraper, monkeypatch):
    dl = tmp_path / "dl"
    dl.mkdir()
    (dl / "t.csv").write_text("c,金額（円）,保有金融機関\nx,100,A\n")
    scraper.download_dir = dl
    fake_settings = MagicMock()
    fake_settings.moneyforward.special_rules = [
        MagicMock(action="divide_amount", institution="A", value=2)
    ]
    monkeypatch.setattr(scraper_module, "settings", fake_settings)
    out = tmp_path / "o.csv"
    scraper._aggregate_csv_files(out)
    df = pd.read_csv(out, encoding="utf-8-sig")
    assert df["金額（円）"].iloc[0] == 50.0


def test_aggregate_csv_files_no_transform(tmp_path, scraper, monkeypatch):
    dl = tmp_path / "dl"
    dl.mkdir()
    (dl / "t.csv").write_text("c1,c2\n1,2\n")
    scraper.download_dir = dl
    fake_settings = MagicMock()
    fake_settings.moneyforward.special_rules = [
        MagicMock(action="divide_amount", institution="X", value=10)
    ]
    monkeypatch.setattr(scraper_module, "settings", fake_settings)
    out = tmp_path / "o2.csv"
    scraper._aggregate_csv_files(out)
    df = pd.read_csv(out)
    assert df["c2"].iloc[0] == 2


def test_aggregate_csv_files_malformed(scraper, tmp_path, monkeypatch):
    dl = tmp_path / "dl"
    dl.mkdir()
    (dl / "t.csv").write_text("bad")
    scraper.download_dir = dl
    monkeypatch.setattr(
        scraper,
        "_read_csv_with_encoding",
        lambda p: (_ for _ in ()).throw(Exception("fail")),
    )
    with pytest.raises(MoneyForwardError):
        scraper._aggregate_csv_files(tmp_path / "o.csv")


def test_aggregate_csv_files_empty_df(tmp_path, scraper):
    dl = tmp_path / "dl"
    dl.mkdir()
    (dl / "t.csv").write_text("c,金額（円）,保有金融機関\n")
    scraper.download_dir = dl
    scraper._aggregate_csv_files(tmp_path / "o.csv")
    assert not (tmp_path / "o.csv").exists()


def test_download_and_aggregate(scraper):
    browser = MagicMock()
    browser.get_links_for_download.return_value = ["l1", "l2"]
    browser.driver = "drv"
    calls = []
    scraper.file_downloader.download_from_links = lambda drv, links: calls.append(
        ("down", drv, links)
    )
    scraper._aggregate_csv_files = lambda out: calls.append(("agg", out))
    scraper._download_and_aggregate(browser, "endpoint", Path("o"))
    assert calls == [("down", "drv", ["l1", "l2"]), ("agg", Path("o"))]


def test_scrape_missing_credentials_branch(scraper, monkeypatch):
    monkeypatch.setenv("EMAIL", "u@example.com")
    monkeypatch.delenv("PASSWORD", raising=False)
    scraper._check_env_variables = lambda: None
    scraper._clean_directories = lambda: None
    with pytest.raises(MoneyForwardError) as exc:
        scraper.scrape()
    assert "EMAIL/PASSWORDが環境変数に設定されていません" in str(exc.value)


def test_scrape_raises_mf_error_from_check_env(scraper, mock_env):
    calls = []
    scraper.file_downloader.clean_download_dir = lambda: calls.append(True)
    scraper._check_env_variables = lambda: (_ for _ in ()).throw(
        MoneyForwardError("env missing")
    )
    with pytest.raises(MoneyForwardError):
        scraper.scrape()
    assert calls == []


def test_scrape_success_final_cleanup(scraper, mock_env, monkeypatch):
    scraper._check_env_variables = lambda: None
    scraper._clean_directories = lambda: None
    calls = []
    scraper._download_and_aggregate = lambda b, e, o: calls.append(("agg", e))
    scraper.file_downloader.clean_download_dir = lambda: calls.append(("clean", None))
    browser = MagicMock()
    browser.__enter__.return_value = browser
    browser.login = lambda e, p: None
    monkeypatch.setattr(scraper, "browser_manager", browser)
    scraper.scrape()
    agg_count = len([c for c in calls if c[0] == "agg"])
    clean_count = len([c for c in calls if c[0] == "clean"])
    assert agg_count == 2
    assert clean_count == 2


def test_scrape_download_error(scraper, mock_env, monkeypatch):
    scraper._check_env_variables = lambda: None
    scraper._clean_directories = lambda: None
    browser = MagicMock()
    browser.__enter__.return_value = browser
    browser.login = lambda e, p: None
    monkeypatch.setattr(scraper, "browser_manager", browser)
    scraper._download_and_aggregate = lambda b, e, o: (_ for _ in ()).throw(
        KeyError("bad")
    )
    scraper.file_downloader.clean_download_dir = lambda: None
    with pytest.raises(MoneyForwardError) as exc:
        scraper.scrape()
    msg = str(exc.value)
    assert "スクレイピングに失敗しました" in msg
    assert "KeyError" in msg


def test_scrape_browser_enter_error(scraper, mock_env, monkeypatch):
    scraper._check_env_variables = lambda: None
    scraper._clean_directories = lambda: None
    calls = []
    scraper.file_downloader.clean_download_dir = lambda: calls.append(True)
    fake_mgr = MagicMock()
    fake_mgr.__enter__.side_effect = ValueError("enter fail")
    monkeypatch.setattr(scraper, "browser_manager", fake_mgr)
    with pytest.raises(MoneyForwardError) as exc:
        scraper.scrape()
    msg = str(exc.value)
    assert "予期せぬエラー" in msg
    assert "ValueError" in msg
    assert calls == [True]


def test_scrape_success_flow(scraper, mock_env, monkeypatch):
    fake = datetime.datetime(2025, 4, 21)

    class FakeDate(datetime.datetime):
        @classmethod
        def now(cls):
            return fake

    monkeypatch.setattr(scraper_module.datetime, "datetime", FakeDate)
    scraper._check_env_variables = lambda: None
    scraper._clean_directories = lambda: None
    calls = []
    scraper._download_and_aggregate = lambda b, e, o: calls.append((e, o))
    browser = MagicMock()
    browser.__enter__.return_value = browser
    browser.login = lambda e, p: None
    monkeypatch.setattr(scraper, "browser_manager", browser)
    scraper.scrape()
    assert len(calls) == 2
