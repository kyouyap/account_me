"main関数"

import datetime
import logging
import os
import shutil
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, List, Optional

import gspread
import pandas as pd
import urllib3
from dotenv import load_dotenv
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver


def convert_cookies(selenium_cookies: list[dict]) -> dict[str, str]:
    """
    Seleniumで取得したクッキー情報をurllib3で使用可能な形式に変換します。

    Args:
        selenium_cookies (list[dict]): Seleniumで取得したクッキー情報のリスト。

    Returns:
        dict[str, str]: urllib3で使用するためのクッキー情報。
    """
    cookie_dict = {}
    for cookie in selenium_cookies:
        cookie_dict[cookie["name"]] = cookie["value"]
    return cookie_dict


def selenium_to_urllib3_download(
    driver: WebDriver, download_url: str, save_dir: Path
) -> None:
    """
    SeleniumのWebDriverインスタンスと保存先ディレクトリを指定して、urllib3でファイルをダウンロードします。

    Args:
        driver (WebDriver): SeleniumのWebDriverインスタンス。
        url (str): セッションとクッキーを取得するためのURL。
        download_url (str): ダウンロードするファイルのURL。
        save_dir (str): ダウンロードしたファイルの保存先ディレクトリ。
    """
    # WebDriverを使用してクッキー情報を取得
    cookies = driver.get_cookies()

    # クッキー情報をurllib3用に整形
    cookie_dict = convert_cookies(cookies)

    # urllib3でHTTPリクエストを行う
    http = urllib3.PoolManager()
    headers = {
        "Cookie": "; ".join([f"{name}={value}" for name, value in cookie_dict.items()])
    }
    response = http.request("GET", download_url, headers=headers)

    # ダウンロードしたファイルを指定されたディレクトリに保存
    file_path = os.path.join(save_dir, "download.csv")
    with open(file_path, "wb") as out:
        out.write(response.data)


def configure_logging() -> None:
    """
    ロギングの設定を行う関数です。
    ログフォーマット、ログレベル、ログのローテーションなどをカスタマイズします。
    """
    # ログファイルのパス
    log_file_path = "log.log"

    # ログフォーマットの設定
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # 環境変数からログレベルを取得し、設定する
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level, None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    # ロガーの基本設定
    logging.basicConfig(level=numeric_level, format=log_format)

    # ファイルハンドラーの設定（ローテーションを含む）
    file_handler = RotatingFileHandler(
        log_file_path, maxBytes=1024 * 1024 * 5, backupCount=5
    )
    file_handler.setFormatter(logging.Formatter(log_format))

    # ルートロガーにファイルハンドラーを追加
    logging.getLogger().addHandler(file_handler)


# `configure_logging`関数の呼び出し
configure_logging()

# 使用例
logger = logging.getLogger(__name__)
logger.info("ログの設定が完了しました。")
# 環境変数の読み込み
load_dotenv()


def prepare_download_dir(download_dir: Path) -> None:
    """ダウンロードディレクトリを準備します。存在しない場合は作成します。

    Args:
        download_dir (Path): ダウンロードディレクトリのパス。
    """
    download_dir.mkdir(parents=True, exist_ok=True)


def get_latest_downloaded_filename(download_dir: Path) -> Optional[Path]:
    """ダウンロードディレクトリ内で最も新しいファイルのパスを返します。

    Args:
        download_dir (Path): ダウンロードディレクトリのパス。

    Returns:
        Optional[Path]: 最も新しいファイルのパス。ファイルがない場合はNone。
    """
    files = list(download_dir.glob("download*"))
    if not files:
        return None
    return max(files, key=os.path.getctime)


def configure_chrome_driver() -> webdriver.Remote:
    """Chromeドライバーを設定します。

    Seleniumコンテナ内の`/downloads`にダウンロードディレクトリを設定して、
    名前付きボリューム`downloads`を介してアプリケーションコンテナとファイルを共有します。

    Returns:
        webdriver.Remote: 設定されたChromeドライバー。
    """
    chrome_options = Options()
    prefs = {
        "profile.default_content_settings.popups": 0,
        "download.default_directory": "/app/downloads",  # Seleniumコンテナ内のダウンロードパス
        "safebrowsing.enabled": "false",
    }
    chrome_options.add_experimental_option("prefs", prefs)

    try:
        driver = webdriver.Remote(
            command_executor=os.environ["SELENIUM_URL"], options=chrome_options
        )
    except Exception as e:
        logger.info("WebDriverの初期化中にエラーが発生しました: %s", e)
        raise

    return driver


def login_to_site(driver: Any, url: str, email: str, password: str) -> None:
    """指定したサイトにログインします。

    Args:
        driver (Any): Chromeドライバー。
        url (str): ログインするサイトのURL。
        email (str): ログイン用のメールアドレス。
        password (str): ログイン用のパスワード。
    """
    driver.get(url)
    logger.info("ログインページにアクセスしました。")
    logger.info("url: %s", url)

    driver.implicitly_wait(3)
    driver.find_element(By.NAME, "mfid_user[email]").send_keys(email)
    driver.find_element(By.NAME, "mfid_user[email]").submit()
    driver.implicitly_wait(3)
    driver.find_element(By.NAME, "mfid_user[password]").send_keys(password)
    driver.find_element(By.NAME, "mfid_user[password]").submit()
    driver.implicitly_wait(3)
    logger.info("ログインしました。")


def remove_unnecessary_files(download_dir: Path) -> None:
    """不要なファイルを削除します。

    Args:
        download_dir (Path): ダウンロードディレクトリのパス。
    """
    for file in download_dir.glob("*.crdownload"):
        file.unlink()


def download_files_from_links(
    driver: WebDriver, links: List[str], download_dir: Path
) -> None:
    """リンクリストからファイルをダウンロードし、ダウンロードディレクトリに保存します。

    Args:
        driver (WebDriver): ウェブドライバー。
        links (List[str]): ダウンロードするファイルのリンクリスト。
        download_dir (Path): ダウンロードディレクトリのパス。
    """
    for iter_num, link in enumerate(links):
        try:
            if "https://moneyforward.com/bs/history" == link:
                # driver.get(link + "/csv")
                download_url: Optional[str] = link + "/csv"
                if not download_url:
                    continue
                selenium_to_urllib3_download(driver, download_url, download_dir)
                time.sleep(5)
                latest_file = get_latest_downloaded_filename(download_dir)
                logger.info(latest_file)
                if latest_file:
                    shutil.move(str(latest_file), str(download_dir / f"{iter_num}.csv"))
                del download_url
            elif not link:
                continue
            else:
                logger.info("ダウンロードリンクにアクセス中...")
                logger.info("url: %s", link)
                driver.get(link)
                # btn fc-button fc-button-today spec-fc-button-click-attached
                driver.implicitly_wait(5)
                driver.find_element(
                    By.CSS_SELECTOR,
                    ".btn.fc-button.fc-button-today.spec-fc-button-click-attached",
                ).click()

                for iter_num2 in range(24):
                    logger.info("ダウンロードリンクにアクセス中...: %s", iter_num2)
                    driver.implicitly_wait(5)
                    driver.find_element(
                        By.CSS_SELECTOR,
                        ".btn.fc-button.fc-button-prev.spec-fc-button-click-attached",
                    ).click()
                    driver.implicitly_wait(5)
                    driver.find_element(By.PARTIAL_LINK_TEXT, "ダウンロード").click()
                    driver.implicitly_wait(5)
                    # driver.find_element(
                    #     By.PARTIAL_LINK_TEXT, "CSVファイル").click()
                    download_url = driver.find_element(
                        By.PARTIAL_LINK_TEXT, "CSVファイル"
                    ).get_attribute("href")
                    if download_url is None:
                        continue
                    selenium_to_urllib3_download(driver, download_url, download_dir)
                    latest_file = get_latest_downloaded_filename(download_dir)
                    if latest_file:
                        shutil.move(
                            str(latest_file),
                            str(download_dir / f"{iter_num}_{iter_num2}.csv"),
                        )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error downloading file from %s", link)
            print(f"Error downloading file from {link}: {e}")


def get_links_for_download(driver: WebDriver, page_url: str) -> List[str]:
    """指定されたページからダウンロードリンクを抽出します。

    Args:
        driver (WebDriver): ウェブドライバー。
        page_url (str): ダウンロードリンクを抽出するページのURL。

    Returns:
        List[str]: 抽出されたダウンロードリンクのリスト。
    """
    logger.info("ダウンロードリンクを抽出中...")
    logger.info("url: %s", page_url)
    driver.get(page_url)
    driver.implicitly_wait(5)
    tables = (
        driver.find_element(By.CLASS_NAME, "accounts")
        .find_element(By.CSS_SELECTOR, ".table.table-striped")
        .find_elements(By.TAG_NAME, "tr")
    )

    links = []
    for table in tables[1:]:
        try:
            link = (
                table.find_element(By.TAG_NAME, "td")
                .find_element(By.TAG_NAME, "a")
                .get_attribute("href")
            )
            if link:
                links.append(link)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error extracting link: %s", e)

    return links


def aggregate_and_save_csv(download_dir: Path, output_file: Path) -> None:
    """ダウンロードディレクトリ内のCSVファイルを集約し、指定したファイルパスに保存します。

    Args:
        download_dir (Path): CSVファイルが保存されているダウンロードディレクトリのパス。
        output_file (Path): 集約したデータを保存するファイルのパス。
    """
    all_dfs = []
    os.makedirs(output_file.parent, exist_ok=True)
    for file_path in download_dir.glob("*.csv"):
        df = pd.read_csv(file_path, encoding="shift-jis")
        all_dfs.append(df)

    if all_dfs:
        final_df = pd.concat(all_dfs).drop_duplicates().reset_index(drop=True)
        final_df.to_csv(output_file, index=False, encoding="utf-8-sig")


def clean_download_dir(download_dir: Path) -> None:
    """ダウンロードディレクトリ内の不要なファイルを削除します。

    Args:
        download_dir (Path): クリーンアップするダウンロードディレクトリのパス。
    """
    for file in download_dir.glob("*"):
        file.unlink()


def scrape() -> None:
    """スクレイピングを実行します。"""
    try:
        download_dir = Path("/app/downloads")
        prepare_download_dir(download_dir)

        # Chromeドライバーの設定
        driver = configure_chrome_driver()

        email = os.getenv("EMAIL")
        password = os.getenv("PASSWORD")
        if email is None or password is None:
            raise ValueError("Please set EMAIL and PASSWORD in .env file.")

        login_to_site(driver, "https://moneyforward.com/users/sign_in", email, password)
        logger.info("ログインしました。")
        logger.info("ファイルを削除中...")
        clean_download_dir(download_dir)
        clean_download_dir(Path("../outputs/aggregated_files/detail"))
        logger.info("ファイルを削除しました。")
        # アカウントページからのダウンロード
        account_links = get_links_for_download(
            driver, "https://moneyforward.com/accounts"
        )
        logger.info("ダウンロードリンクを取得しました。")
        logger.info(account_links)
        logger.info("ファイルをダウンロード中...")
        download_files_from_links(driver, account_links, download_dir)
        logger.info("ファイルをダウンロードしました。")
        logger.info("ファイルを集約中...")
        aggregate_and_save_csv(
            download_dir,
            Path.cwd()
            / f"../outputs/aggregated_files/detail/detail_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
        )
        logger.info("ファイルを集約しました。")

        # 履歴ページからのダウンロード
        history_links = ["https://moneyforward.com/bs/history"]
        clean_download_dir(download_dir)
        logger.info("ファイルを削除しました。")
        logger.info("ファイルをダウンロード中...")
        download_files_from_links(driver, history_links, download_dir)
        logger.info("ファイルをダウンロードしました。")
        logger.info("ファイルを集約中...")
        aggregate_and_save_csv(
            download_dir,
            Path.cwd()
            / f"../outputs/aggregated_files/assets/assets_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
        )
        logger.info("ファイルを集約しました。")
        logger.info("ファイルを削除中...")
        clean_download_dir(download_dir)
        logger.info("ファイルを削除しました。")
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Error occurred during scraping: %s", e)
    finally:
        driver.quit()


def update_spreadsheet() -> None:
    """スプレッドシートを更新します。"""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        "../key/spreadsheet_managementkey.json", scope
    )

    gc = gspread.authorize(credentials)

    spreadsheet_key = os.getenv("SPREADSHEET_KEY")
    if spreadsheet_key is None:
        raise ValueError("Please set SPREADSHEET_KEY in .env file.")
    worksheet = gc.open_by_key(spreadsheet_key)
    # 計算対象	日付	内容	金額（円）	保有金融機関	大項目	中項目	メモ	振替	ID
    df_detail = pd.read_csv(
        Path(os.getcwd() + "/../outputs/aggregated_files/detail").resolve()
        / f"detail_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
        encoding="utf-8-sig",
    )
    df_detail["メモ"] = "なし"
    # 保有金融機関が'アメリカン・エキスプレスカード'のものの’金額（円）’だけ半額にする
    df_detail.loc[
        df_detail["保有金融機関"] == "アメリカン・エキスプレスカード", "金額（円）"
    ] = (
        df_detail.loc[
            df_detail["保有金融機関"] == "アメリカン・エキスプレスカード", "金額（円）"
        ]
        / 2
    )
    logger.info(df_detail)
    df_sps = get_as_dataframe(
        worksheet.worksheet("@家計簿データ 貼付"),
        usecols=list(range(2, 12)),
        header=3,
    )[
        [
            "計算対象",
            "日付",
            "内容",
            "金額（円）",
            "保有金融機関",
            "大項目",
            "中項目",
            "メモ",
            "振替",
            "ID",
        ]
    ]
    df_sps.dropna(subset=["ID"], inplace=True)

    df_sps = pd.concat([df_detail, df_sps], ignore_index=True)
    df_sps["日付"] = pd.to_datetime(df_sps["日付"], format="mixed")
    # 日付を2024/1/1の形式に変換
    df_sps["日付"] = df_sps["日付"].dt.strftime("%Y/%m/%d")
    df_sps.sort_values(by="日付", ascending=False, inplace=True)
    df_sps = df_sps.drop_duplicates(subset=["ID"], keep="first")
    set_with_dataframe(
        worksheet.worksheet("@家計簿データ 貼付"),
        df_sps,
        row=4,
        col=3,
        include_index=False,
        include_column_header=True,
        resize=True,
    )
    clean_download_dir(Path("../outputs/aggregated_files/detail"))
    df_assets = pd.read_csv(
        Path(os.getcwd() + "/../outputs/aggregated_files/assets").resolve()
        / f"assets_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
        encoding="utf-8-sig",
    )
    # 日付	合計（円）	預金・現金・仮想通貨（円）	投資信託（円）
    df_sps = get_as_dataframe(
        worksheet.worksheet("@資産推移 貼付"),
        usecols=list(range(4)),
        header=3,
    )[
        [
            "日付",
            "合計（円）",
            "預金・現金・暗号資産（円）",
            "投資信託（円）",
        ]
    ].dropna()
    df_sps = pd.concat([df_sps, df_assets], ignore_index=True).sort_values(
        by="日付", ascending=True
    )
    df_sps["日付"] = pd.to_datetime(df_sps["日付"], format="mixed")
    df_sps["日付"] = df_sps["日付"].dt.strftime("%Y/%m/%d")
    df_sps.sort_values(by="日付", ascending=True, inplace=True)
    df_sps = df_sps.drop_duplicates(subset=["日付"], keep="last")
    logger.info(df_sps)
    set_with_dataframe(
        worksheet.worksheet("@資産推移 貼付"),
        df_sps,
        row=4,
        col=1,
        include_index=False,
        include_column_header=True,
        resize=True,
    )
    clean_download_dir(Path("../outputs/aggregated_files/assets"))


def main() -> None:
    """メイン関数。"""
    time.sleep(10)
    load_dotenv()
    scrape()
    update_spreadsheet()


if __name__ == "__main__":
    main()
