"""成果物（注釈付き動画）の配信（`st.video` の置き換え）。

`StaticFiles` をマウントすると配信ディレクトリが **import 時**に固定され、
`ML_MOTION_WORKDIR` を後から変えた場合に食い違う。ここではリクエストごとに
パスを解決し、あわせて run_id / ファイル名を検証する。

`FileResponse` は Range リクエストに応答するので、`<video>` のシークが効く。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.app.core import storage

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/{run_id}/{filename}")
def get_run_file(run_id: str, filename: str) -> FileResponse:
    """解析 1 回分の出力ファイルを返す。"""
    path = storage.resolve_run_file(run_id, filename)
    if path is None:
        raise HTTPException(status_code=404, detail="ファイルが見つかりません")
    return FileResponse(path)
