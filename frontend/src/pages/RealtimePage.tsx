/**
 * リアルタイム解析画面 — Streamlit 版 `app/views/realtime.py` の React 版（R5）。
 *
 * 2 経路とも Streamlit 版と同じ構成:
 *   1. Continuity Camera（サーバ側 OpenCV）→ MJPEG を `<img>` で表示
 *      （Streamlit 版の `while` ループ + `st.image` 差し替えに相当）
 *   2. ブラウザカメラ → `getUserMedia` + WebSocket で往復
 *      （`streamlit-webrtc` の置き換え。`streamlit-webrtc` / `av` は不要）
 *
 * 受け入れ基準は `docs/manual/02_realtime.md`。
 */
import { useCallback, useEffect, useRef, useState } from 'react';

import { getOptions } from '../api/client';
import { getRealtimeSettings, getRealtimeStats, mjpegUrl, stopRealtime, websocketUrl } from '../api/realtime';
import {
  defaultRealtimeSettings,
  normalizeRealtimeSettings,
  type RealtimeRoute,
  type RealtimeSettings,
  realtimeModels,
  toRealtimeQuery,
} from '../state/realtimeSettings';
import type { Options, RealtimeMessage, RealtimeSettingsResponse } from '../types';

/** ブラウザ経路で送るフレームの JPEG 品質。 */
const JPEG_QUALITY = 0.7;

export function RealtimePage(): JSX.Element {
  const [options, setOptions] = useState<Options | null>(null);
  const [settings, setSettings] = useState<RealtimeSettings>(() => defaultRealtimeSettings(null));
  const [resolved, setResolved] = useState<RealtimeSettingsResponse | null>(null);

  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fps, setFps] = useState(0);
  const [detections, setDetections] = useState(0);
  const [frameIndex, setFrameIndex] = useState(0);

  // 経路2（ブラウザカメラ）用
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const annotatedUrlRef = useRef<string | null>(null);
  const [annotatedUrl, setAnnotatedUrl] = useState<string | null>(null);

  useEffect(() => {
    getOptions()
      .then((data) => {
        setOptions(data);
        setSettings(defaultRealtimeSettings(data));
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  const query = toRealtimeQuery(settings);

  // 設定を変えるたびにサーバへ解決させる（自動切替の注意書きを出すため）。
  useEffect(() => {
    if (!options) return;
    getRealtimeSettings(query)
      .then(setResolved)
      .catch(() => setResolved(null));
  }, [query, options]);

  const update = useCallback(
    (patch: Partial<RealtimeSettings>) => {
      setSettings((current) => normalizeRealtimeSettings({ ...current, ...patch }, options));
    },
    [options],
  );

  // ---- 経路1: サーバ側カメラの統計をポーリング ----
  useEffect(() => {
    if (!running || settings.route !== 'camera') return;
    const timer = window.setInterval(() => {
      void getRealtimeStats()
        .then((stats) => {
          setFps(stats.fps);
          setDetections(stats.n_detections);
          setFrameIndex(stats.frame_index);
        })
        .catch(() => undefined);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [running, settings.route]);

  const stopAll = useCallback(() => {
    socketRef.current?.close();
    socketRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (annotatedUrlRef.current) {
      URL.revokeObjectURL(annotatedUrlRef.current);
      annotatedUrlRef.current = null;
    }
    setAnnotatedUrl(null);
    setRunning(false);
    // サーバ側カメラも解放する（`<img>` を外すだけでは切断が届かない場合の保険）。
    void stopRealtime().catch(() => undefined);
  }, []);

  useEffect(() => () => stopAll(), [stopAll]);

  // ---- 経路2: ブラウザカメラ ----
  const startBrowserCamera = async () => {
    const [width, height] = resolved ? [resolved.width, resolved.height] : [640, 360];
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: width }, height: { ideal: height } },
        audio: false,
      });
    } catch (e) {
      setError(`カメラを利用できません: ${(e as Error).message}（ブラウザの許可を確認してください）`);
      return;
    }
    streamRef.current = stream;

    const video = videoRef.current;
    if (!video) return;
    video.srcObject = stream;
    await video.play();

    const socket = new WebSocket(websocketUrl(query));
    socket.binaryType = 'arraybuffer';
    socketRef.current = socket;

    const sendFrame = () => {
      const canvas = canvasRef.current;
      const current = videoRef.current;
      if (!canvas || !current || socket.readyState !== WebSocket.OPEN) return;
      if (current.videoWidth === 0) {
        window.setTimeout(sendFrame, 100);
        return;
      }
      canvas.width = current.videoWidth;
      canvas.height = current.videoHeight;
      canvas.getContext('2d')?.drawImage(current, 0, 0);
      canvas.toBlob(
        (blob) => {
          if (blob && socket.readyState === WebSocket.OPEN) {
            void blob.arrayBuffer().then((buffer) => socket.send(buffer));
          }
        },
        'image/jpeg',
        JPEG_QUALITY,
      );
    };

    socket.onmessage = (event: MessageEvent<ArrayBuffer | string>) => {
      if (typeof event.data === 'string') {
        const message = JSON.parse(event.data) as RealtimeMessage;
        if (message.type === 'ready') {
          sendFrame(); // 最初の 1 枚
        } else if (message.type === 'stats') {
          setFps(message.fps);
          setDetections(message.n_detections);
          setFrameIndex(message.frame_index);
          // 応答を受け取ってから次を送る（in-flight 1 枚で遅延を溜めない）。
          sendFrame();
        } else if (message.type === 'error') {
          setError(message.message);
        }
        return;
      }
      // 注釈付きフレーム（バイナリ）。前の Object URL は必ず解放する。
      const url = URL.createObjectURL(new Blob([event.data], { type: 'image/jpeg' }));
      if (annotatedUrlRef.current) URL.revokeObjectURL(annotatedUrlRef.current);
      annotatedUrlRef.current = url;
      setAnnotatedUrl(url);
    };

    socket.onopen = () => {
      setRunning(true);
      setError(null);
    };
    socket.onerror = () => setError('WebSocket の接続に失敗しました');
    socket.onclose = () => setRunning(false);
  };

  const handleStart = () => {
    setError(null);
    setFps(0);
    setDetections(0);
    setFrameIndex(0);
    if (settings.route === 'camera') {
      setRunning(true); // `<img>` を出すと MJPEG の取得が始まる
    } else {
      void startBrowserCamera();
    }
  };

  const models = realtimeModels(settings, options);

  return (
    <div className="page">
      <h1 className="page-title">📡 リアルタイム解析</h1>
      <p className="page-caption">iPhone 映像（Continuity Camera / ブラウザ）での準リアルタイム検出</p>

      <div className="analyze-layout realtime-layout">
        {/* ---- 設定 ---- */}
        <section className="panel">
          <h2 className="panel-title">設定</h2>

          <fieldset className="field-group" disabled={running}>
            <legend>取り込み経路</legend>
            {(
              [
                ['camera', 'Continuity Camera (OpenCV)'],
                ['browser', 'ブラウザ (WebSocket)'],
              ] as [RealtimeRoute, string][]
            ).map(([value, label]) => (
              <label key={value} className="check">
                <input
                  type="radio"
                  name="route"
                  checked={settings.route === value}
                  onChange={() => update({ route: value })}
                />
                {label}
              </label>
            ))}
          </fieldset>

          {settings.route === 'camera' && (
            <fieldset className="field-group" disabled={running}>
              <legend>カメラ</legend>
              <label className="field">
                <span>カメラ index（0=内蔵、1〜=外部/iPhone）</span>
                <input
                  type="number"
                  min={0}
                  max={10}
                  value={settings.cameraIndex}
                  onChange={(e) => update({ cameraIndex: Number(e.target.value) })}
                />
              </label>
            </fieldset>
          )}

          <fieldset className="field-group" disabled={running}>
            <legend>タスク</legend>
            <label className="check">
              <input
                type="checkbox"
                checked={settings.enableSeg}
                onChange={(e) => update({ enableSeg: e.target.checked })}
              />
              セグメンテーション
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={settings.enableTrack}
                onChange={(e) => update({ enableTrack: e.target.checked })}
              />
              トラッキング（ByteTrack）
            </label>
          </fieldset>

          <fieldset className="field-group" disabled={running}>
            <legend>モデル</legend>
            <label className="field">
              <span>YOLO11 モデル</span>
              <select value={settings.modelName} onChange={(e) => update({ modelName: e.target.value })}>
                {models.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={settings.autoLight}
                onChange={(e) => update({ autoLight: e.target.checked })}
              />
              リアルタイム用に軽量モデルへ自動切替
            </label>
            {resolved?.notes.map((note) => (
              <p key={note} className="hint">
                {note}
              </p>
            ))}
            <label className="field">
              <span>信頼度しきい値: {settings.conf.toFixed(2)}</span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={settings.conf}
                onChange={(e) => update({ conf: Number(e.target.value) })}
              />
            </label>
          </fieldset>

          <fieldset className="field-group" disabled={running}>
            <legend>スループット最適化</legend>
            <label className="field">
              <span>解像度</span>
              <select value={settings.resolution} onChange={(e) => update({ resolution: e.target.value })}>
                {Object.keys(options?.resolution_presets ?? {}).map((key) => (
                  <option key={key} value={key}>
                    {key}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>フレームスキップ（N フレームに1回推論）: {settings.frameSkip}</span>
              <input
                type="range"
                min={1}
                max={5}
                step={1}
                value={settings.frameSkip}
                onChange={(e) => update({ frameSkip: Number(e.target.value) })}
              />
            </label>
          </fieldset>
        </section>

        {/* ---- 映像 ---- */}
        <section className="panel">
          <h2 className="panel-title">映像</h2>

          {settings.route === 'camera' ? (
            <div className="notice">
              📱 iPhone を Mac の近くに置き、Continuity Camera を有効化してください。OpenCV のカメラ一覧に
              iPhone が現れます（macOS Ventura+ / iPhone XR+）。
              <strong>※ この経路はバックエンドを動かしている Mac のカメラを使います。</strong>
            </div>
          ) : (
            <div className="notice">
              🌐 ブラウザのカメラ許可ダイアログで iPhone/Web カメラを選択してください。
              フレームは WebSocket でサーバへ送られ、注釈付きで返ります。
            </div>
          )}

          <div className="downloads">
            <button className="btn btn-primary" disabled={running} onClick={handleStart}>
              ▶ 開始
            </button>
            <button className="btn" disabled={!running} onClick={stopAll}>
              ⏹ 停止
            </button>
          </div>

          {error && <div className="alert alert-error">{error}</div>}

          {running ? (
            <p className="hint">
              FPS: <strong>{fps.toFixed(1)}</strong> / 検出数: {detections} / frame {frameIndex}
            </p>
          ) : (
            <p className="hint">「開始」を押すと取り込みを開始します。</p>
          )}

          {/* 経路1: MJPEG をそのまま表示 */}
          {running && settings.route === 'camera' && (
            <img className="preview" src={mjpegUrl(query)} alt="リアルタイム映像（サーバ側カメラ）" />
          )}

          {/* 経路2: ローカル映像は canvas 送信用に隠し、注釈付きフレームを表示 */}
          <video ref={videoRef} className="hidden-media" muted playsInline />
          <canvas ref={canvasRef} className="hidden-media" />
          {running && settings.route === 'browser' && annotatedUrl && (
            <img className="preview" src={annotatedUrl} alt="リアルタイム映像（ブラウザカメラ）" />
          )}
        </section>
      </div>
    </div>
  );
}
