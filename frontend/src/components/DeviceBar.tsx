/**
 * デバイス表示 — Streamlit 版で各画面の上部に出していた
 * `Device / torch / MPS / CUDA`（`describe_device()`）に対応する。
 *
 * Streamlit 版は画面ごとに描いていたが、内容が同じなのでシェル（サイドバー）に集約する。
 * バックエンド未起動のときは、その旨と起動コマンドを出す。
 */
import { useEffect, useState } from 'react';
import type { ReactElement } from 'react';

import { getDeviceInfo } from '../api/client';
import type { DeviceInfo } from '../types';

export function DeviceBar(): ReactElement {
  const [info, setInfo] = useState<DeviceInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDeviceInfo()
      .then((data) => {
        if (!cancelled) setInfo(data);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="device-bar device-bar-error">
        <div className="device-error-title">⚠️ バックエンド未接続</div>
        <div className="device-error-body">{error}</div>
        <code className="device-error-cmd">uvicorn backend.app.main:app --reload --port 8000</code>
      </div>
    );
  }

  if (!info) {
    return <div className="device-bar">デバイス情報を取得中…</div>;
  }

  return (
    <div className="device-bar">
      <div className="device-row">
        <span className="device-label">Device</span>
        <span className="device-value device-value-strong">{info.device.toUpperCase()}</span>
      </div>
      <div className="device-row">
        <span className="device-label">torch</span>
        <span className="device-value">{info.torch ?? '未導入'}</span>
      </div>
      <div className="device-row">
        <span className="device-label">MPS</span>
        <span className="device-value">{info.mps_available ? '✅' : '—'}</span>
      </div>
      <div className="device-row">
        <span className="device-label">CUDA</span>
        <span className="device-value">{info.cuda_available ? '✅' : '—'}</span>
      </div>
    </div>
  );
}
