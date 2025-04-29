"""アプリケーション固有の例外クラスを定義するモジュール。

このモジュールは、MoneyForwardスクレイピングアプリケーションで使用される
カスタム例外クラスを定義します。各例外は特定のエラー状況に対応し、
エラーハンドリングの詳細な制御を可能にします。

例外階層:
    - GmailApiError
        - VerificationCodeError
    - MoneyForwardError (基底クラス)
        - AuthenticationError
        - ScrapingError
        - DownloadError
        - SpreadsheetError
        - ConfigurationError

使用例:
    ```python
    try:
        scraper.login()
    except AuthenticationError as e:
        logger.error("ログインに失敗しました: %s", e)
    except ScrapingError as e:
        logger.error("スクレイピング中にエラーが発生しました: %s", e)
    ```
"""


class GmailApiError(Exception):
    """Gmail APIの操作中に発生するエラーを表します。

    このエラーは以下の状況で発生する可能性があります:
        - API認証の失敗
        - メールの取得失敗
        - APIリクエストの制限超過
    """


class VerificationCodeError(GmailApiError):
    """Gmailからの認証コード取得に失敗した場合のエラーを表します。

    このエラーは以下の状況で発生する可能性があります:
        - 認証メールが届かない
        - メール本文から認証コードを抽出できない
        - 認証コードの形式が不正
    """


class MoneyForwardError(Exception):
    """MoneyForwardスクレイピング関連の基底例外クラスです。

    このクラスは、MoneyForward関連の操作で発生する可能性のある
    すべてのエラーの基底クラスとして機能します。具体的なエラーは
    このクラスを継承した個別の例外クラスで表現されます。
    """


class AuthenticationError(MoneyForwardError):
    """MoneyForwardへの認証処理中のエラーを表します。

    このエラーは以下の状況で発生する可能性があります:
        - ログイン認証情報が無効
        - セッションの有効期限切れ
        - 二段階認証の失敗
    """


class ScrapingError(MoneyForwardError):
    """MoneyForwardのスクレイピング処理中のエラーを表します。

    このエラーは以下の状況で発生する可能性があります:
        - 必要な要素が見つからない
        - ページの構造が変更された
        - ネットワークタイムアウト
    """


class DownloadError(MoneyForwardError):
    """ファイルのダウンロード処理中のエラーを表します。

    このエラーは以下の状況で発生する可能性があります:
        - ダウンロードの開始失敗
        - 不完全なダウンロード
        - ファイルの保存失敗
    """


class SpreadsheetError(MoneyForwardError):
    """Google Spreadsheetの操作中のエラーを表します。

    このエラーは以下の状況で発生する可能性があります:
        - スプレッドシートへのアクセス権限不足
        - シートが存在しない
        - データの更新失敗
    """


class ConfigurationError(MoneyForwardError):
    """アプリケーションの設定に関するエラーを表します。

    このエラーは以下の状況で発生する可能性があります:
        - 必要な設定値の欠落
        - 設定ファイルの読み込み失敗
        - 設定値の型が不正
    """


class BigQueryError(MoneyForwardError):
    """BigQueryの操作中のエラーを表します。

    このエラーは以下の状況で発生する可能性があります:
        - テーブルへのアクセス権限不足
        - テーブルが存在しない
        - データの更新失敗
        - クエリの実行エラー
        - スキーマの不整合
    """
