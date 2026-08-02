"""MLflow Tracking サーバの疎通確認。

⚠️ MLflow クライアントは接続失敗時に長時間リトライする（実測: サーバ停止時に
`list_runs` が戻るまで約 4 分）。ブラウザからの取得でそれだけ待たされ、その間
ワーカースレッドも占有されるため、**先に短いタイムアウトで疎通を確認**して
落ちていれば即座に 503 を返す。

mlflow に依存しない（標準ライブラリのみ）ので単体テストできる。
"""

from __future__ import annotations

import urllib.error
import urllib.request

# 疎通確認のタイムアウト（秒）。
PROBE_TIMEOUT = 3.0


def is_mlflow_reachable(uri: str, timeout: float = PROBE_TIMEOUT) -> bool:
    """Tracking サーバに短いタイムアウトで疎通確認する。

    http(s) 以外（ローカルの `file:` ストア等）は確認しようがないので True を返し、
    実際の呼び出し結果に判断を委ねる。
    """
    if not uri.startswith(("http://", "https://")):
        return True

    try:
        with urllib.request.urlopen(f"{uri.rstrip('/')}/health", timeout=timeout) as response:
            return 200 <= response.status < 500
    except urllib.error.HTTPError:
        # 応答はあるので「起動はしている」と扱う（認証等は呼び出し側で判断）。
        return True
    except Exception:  # noqa: BLE001 — 接続不可・タイムアウト・名前解決失敗
        return False
