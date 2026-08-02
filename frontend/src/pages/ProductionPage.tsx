/**
 * 本番化・最適化画面 — Streamlit 版 `app/views/production.py` の React 版（R4）。
 *
 * ディレクトリ一括のバッチ推論、モデル変換（ONNX/CoreML/量子化）、
 * レイテンシ計測の案内、Model Registry からの取得を扱う。
 *
 * ⚠️ パスはユーザー入力なので、サーバ側でリポジトリルート配下に限定している
 * （外を指すと 400 が返り、その文言をそのまま表示する）。
 *
 * 受け入れ基準は `docs/manual/04_production.md`。
 */
import { useEffect, useReducer, useRef, useState } from 'react';

import { getOptions, subscribeJob } from '../api/client';
import {
  discoverMedia,
  exportModel,
  getBatchResult,
  getRegistryUri,
  startBatch,
} from '../api/production';
import { DataTable } from '../components/DataTable';
import { Metric } from '../components/Metric';
import { initialJobState, jobReducer, progressLabel } from '../state/jobReducer';
import type { BatchResult, DiscoverResponse, ExportResponse, Options, Quantization } from '../types';

export function ProductionPage(): JSX.Element {
  const [options, setOptions] = useState<Options | null>(null);

  const [inputDir, setInputDir] = useState('data/incoming');
  const [outputDir, setOutputDir] = useState('output_batch');
  const [modelName, setModelName] = useState('yolo11s.pt');
  const [conf, setConf] = useState(0.25);
  const [frameStride, setFrameStride] = useState(2);

  const [discovered, setDiscovered] = useState<DiscoverResponse | null>(null);
  const [batchNotice, setBatchNotice] = useState<string | null>(null);
  const [job, dispatch] = useReducer(jobReducer, initialJobState);
  const [batchResult, setBatchResult] = useState<BatchResult | null>(null);

  const [weights, setWeights] = useState('yolo11s.pt');
  const [fmt, setFmt] = useState('onnx');
  const [quantization, setQuantization] = useState<Quantization>('FP32');
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState<ExportResponse | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const [regName, setRegName] = useState('ml_motion_detector');
  const [regStage, setRegStage] = useState('Staging');
  const [regUri, setRegUri] = useState('');

  const unsubscribeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    getOptions()
      .then((data) => {
        setOptions(data);
        setModelName(data.models[1] ?? 'yolo11s.pt');
        setFmt(data.export_formats[0] ?? 'onnx');
      })
      .catch(() => setOptions(null));
  }, []);

  useEffect(() => () => unsubscribeRef.current?.(), []);

  // Registry URI はサーバ側で組み立てる（ステージ名の正規化を一箇所に保つ）。
  useEffect(() => {
    getRegistryUri(regName, regStage)
      .then((data) => setRegUri(data.uri))
      .catch(() => setRegUri(''));
  }, [regName, regStage]);

  const handleDiscover = async () => {
    setBatchNotice(null);
    try {
      setDiscovered(await discoverMedia(inputDir));
    } catch (e) {
      setDiscovered(null);
      setBatchNotice((e as Error).message);
    }
  };

  const handleBatch = async () => {
    setBatchNotice(null);
    setBatchResult(null);
    try {
      const accepted = await startBatch({
        input_dir: inputDir,
        output_dir: outputDir,
        model_name: modelName,
        conf,
        frame_stride: frameStride,
      });
      dispatch({ type: 'start', jobId: accepted.job_id, message: '処理中…' });
      unsubscribeRef.current?.();
      unsubscribeRef.current = subscribeJob(
        'production',
        accepted.job_id,
        (event) => {
          dispatch({ type: 'event', event });
          if (event.type === 'done') {
            unsubscribeRef.current?.();
            void getBatchResult(accepted.job_id).then((status) => setBatchResult(status.result));
          }
        },
        (message) => dispatch({ type: 'fail', message }),
      );
    } catch (e) {
      setBatchNotice((e as Error).message);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    setExportError(null);
    setExportResult(null);
    try {
      setExportResult(await exportModel(weights, fmt, quantization));
    } catch (e) {
      setExportError((e as Error).message);
    } finally {
      setExporting(false);
    }
  };

  const models = options ? [...options.models, ...options.seg_models] : [];
  const running = job.status === 'running';
  // バッチはファイル単位の進捗（解析画面はフレーム単位）。
  const batchLabel = progressLabel(job, '処理中…', 'ファイル');

  return (
    <div className="page">
      <h1 className="page-title">⚙️ 本番化・最適化</h1>
      <p className="page-caption">バッチ推論 / モデル変換・量子化 / レイテンシ計測</p>

      {/* ---- バッチ推論 ---- */}
      <h2 className="section-title">バッチ推論（ディレクトリ一括）</h2>
      <div className="panel">
        <div className="form-row">
          <label className="field">
            <span>入力ディレクトリ</span>
            <input
              type="text"
              value={inputDir}
              disabled={running}
              onChange={(e) => setInputDir(e.target.value)}
            />
          </label>
          <label className="field">
            <span>出力ディレクトリ</span>
            <input
              type="text"
              value={outputDir}
              disabled={running}
              onChange={(e) => setOutputDir(e.target.value)}
            />
          </label>
        </div>
        <p className="hint">※ パスはリポジトリルート配下のみ指定できます（相対パスはルート基準）。</p>

        <div className="form-row">
          <label className="field">
            <span>モデル</span>
            <select value={modelName} disabled={running} onChange={(e) => setModelName(e.target.value)}>
              {models.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>信頼度: {conf.toFixed(2)}</span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={conf}
              disabled={running}
              onChange={(e) => setConf(Number(e.target.value))}
            />
          </label>
          <label className="field">
            <span>フレーム間引き: {frameStride}</span>
            <input
              type="range"
              min={1}
              max={10}
              step={1}
              value={frameStride}
              disabled={running}
              onChange={(e) => setFrameStride(Number(e.target.value))}
            />
          </label>
        </div>

        <div className="downloads">
          <button className="btn" disabled={running} onClick={() => void handleDiscover()}>
            📁 入力ディレクトリを確認
          </button>
          <button className="btn btn-primary" disabled={running} onClick={() => void handleBatch()}>
            ▶ バッチ実行
          </button>
        </div>

        {batchNotice && <div className="alert alert-error">{batchNotice}</div>}

        {discovered && (
          <>
            <p className="hint">
              {discovered.input_dir}: {discovered.files.length} 件の動画を検出
            </p>
            {discovered.files.length > 0 ? (
              <ul className="feature-list">
                {discovered.files.map((file) => (
                  <li key={file}>{file}</li>
                ))}
              </ul>
            ) : (
              <p className="hint">（動画が見つかりません）</p>
            )}
          </>
        )}

        {running && (
          <div className="progress">
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${(job.progress ?? 0) * 100}%` }} />
            </div>
            <div className="hint">{batchLabel}</div>
          </div>
        )}

        {job.status === 'failed' && <div className="alert alert-error">{job.error}</div>}

        {batchResult && (
          <>
            <div className="alert alert-ok">
              完了: 成功 {batchResult.succeeded} / 失敗 {batchResult.failed} / 総検出{' '}
              {batchResult.total_detections}
            </div>
            <div className="metric-row">
              <Metric label="成功" value={batchResult.succeeded} />
              <Metric label="失敗" value={batchResult.failed} />
              <Metric label="総検出数" value={batchResult.total_detections} />
            </div>
            <DataTable
              columns={[
                { key: 'input', label: 'input' },
                { key: 'output', label: 'output' },
                { key: 'frames', label: 'frames', align: 'right' },
                { key: 'detections', label: 'detections', align: 'right' },
                { key: 'status', label: 'status' },
              ]}
              rows={batchResult.manifest}
            />
          </>
        )}
      </div>

      {/* ---- モデル変換・量子化 ---- */}
      <h2 className="section-title">モデル変換・量子化</h2>
      <div className="panel">
        <div className="form-row">
          <label className="field">
            <span>重みパス</span>
            <input
              type="text"
              value={weights}
              disabled={exporting}
              onChange={(e) => setWeights(e.target.value)}
            />
          </label>
          <label className="field">
            <span>書式</span>
            <select value={fmt} disabled={exporting} onChange={(e) => setFmt(e.target.value)}>
              {(options?.export_formats ?? []).map((format) => (
                <option key={format} value={format}>
                  {format}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>量子化</span>
            <select
              value={quantization}
              disabled={exporting}
              onChange={(e) => setQuantization(e.target.value as Quantization)}
            >
              {(['FP32', 'FP16', 'INT8'] as Quantization[]).map((q) => (
                <option key={q} value={q}>
                  {q}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="hint">
          設定: {fmt} / {quantization}
        </p>
        <button className="btn" disabled={exporting} onClick={() => void handleExport()}>
          {exporting ? '変換中…（初回は時間がかかります）' : '🛠 変換を実行'}
        </button>
        {exportError && <div className="alert alert-error">{exportError}</div>}
        {exportResult && (
          <div className="alert alert-ok">
            変換完了: <code>{exportResult.output_path}</code>（{exportResult.fmt} /{' '}
            {exportResult.quantization}）
          </div>
        )}
      </div>

      {/* ---- レイテンシ計測 ---- */}
      <h2 className="section-title">レイテンシ・スループット計測</h2>
      <div className="panel">
        <p>
          <code>pipeline.benchmark.benchmark_processor()</code> で FrameProcessor を一連フレームに対し実行し、
          mean/p50/p95/fps を計測します（warmup 除外）。MPS/CoreML/ONNX/量子化の前後比較に使用します。
        </p>
        <p className="hint">⏱ 実計測は実機（M2 Mac）で実行してください。</p>
      </div>

      {/* ---- Registry からのモデル取得 ---- */}
      <h2 className="section-title">Model Registry からの取得・差し替え</h2>
      <div className="panel">
        <div className="form-row">
          <label className="field">
            <span>モデル名</span>
            <input type="text" value={regName} onChange={(e) => setRegName(e.target.value)} />
          </label>
          <label className="field">
            <span>ステージ</span>
            <select value={regStage} onChange={(e) => setRegStage(e.target.value)}>
              {(options?.registry_stages ?? []).filter((s) => s !== 'None').map((stage) => (
                <option key={stage} value={stage}>
                  {stage}
                </option>
              ))}
            </select>
          </label>
        </div>
        <pre className="code-block">{regUri || '(取得中…)'}</pre>
        <p className="hint">
          <code>download_model()</code> で上記 URI の成果物を取得し、バッチ/リアルタイムのモデルを差し替えます。
        </p>
      </div>
    </div>
  );
}
