/**
 * 解析画面 — Streamlit 版 `app/views/analyze.py` の React 版（R1）。
 *
 * 画面構成は Streamlit 版に合わせる:
 *   左: 設定パネル（旧サイドバー）／ 中央: アップロード・実行・動画プレビュー
 *   右: 結果ペイン（メトリクス・クラス別・ダウンロード・NL要約）
 *   下: ゾーン解析・検出結果テーブル
 *
 * 検出結果テーブルは数万行になりうるため 1000 件ずつページングし、
 * 全件は CSV / JSON のダウンロードへ誘導する。
 *
 * 受け入れ基準は `docs/manual/01_analyze.md`。
 */
import { useCallback, useEffect, useReducer, useRef, useState } from 'react';

import { fetchAnalyzeResult, fetchDetections } from '../api/analyze';
import { API_BASE, getOptions, postJson, subscribeJob, uploadVideo } from '../api/client';
import { DataTable } from '../components/DataTable';
import { Metric } from '../components/Metric';
import {
  type AnalyzeSettings,
  availableModels,
  defaultSettings,
  isClassSelectEnabled,
  isTraceLengthEnabled,
  isZoneEnabled,
  normalizeSettings,
  toAnalyzeRequest,
  validateForRun,
} from '../state/analyzeSettings';
import { initialJobState, jobReducer, progressLabel } from '../state/jobReducer';
import type { AnalyzeResultSummary, DetectionPage, JobAccepted, Options, UploadInfo } from '../types';

const PAGE_SIZE = 1000;

export function AnalyzePage(): JSX.Element {
  const [options, setOptions] = useState<Options | null>(null);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [settings, setSettings] = useState<AnalyzeSettings>(() => defaultSettings(null));

  const [upload, setUpload] = useState<UploadInfo | null>(null);
  const [uploading, setUploading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const [job, dispatch] = useReducer(jobReducer, initialJobState);
  const [result, setResult] = useState<AnalyzeResultSummary | null>(null);
  const [detections, setDetections] = useState<DetectionPage | null>(null);
  const [page, setPage] = useState(0);

  const [summary, setSummary] = useState<string | null>(null);
  const [summarizing, setSummarizing] = useState(false);

  const unsubscribeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    getOptions()
      .then((data) => {
        setOptions(data);
        setSettings(defaultSettings(data));
      })
      .catch((e: Error) => setOptionsError(e.message));
  }, []);

  // 画面離脱時に SSE を閉じる。
  useEffect(() => () => unsubscribeRef.current?.(), []);

  const update = useCallback(
    (patch: Partial<AnalyzeSettings>) => {
      setSettings((current) => normalizeSettings({ ...current, ...patch }, options));
    },
    [options],
  );

  const clearResults = () => {
    setResult(null);
    setDetections(null);
    setSummary(null);
  };

  const handleUpload = async (file: File) => {
    setUploading(true);
    setNotice(null);
    try {
      setUpload(await uploadVideo(file));
      dispatch({ type: 'reset' });
      clearResults();
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      setUploading(false);
    }
  };

  const loadResult = useCallback(async (jobId: string) => {
    try {
      const status = await fetchAnalyzeResult(jobId);
      if (status.result) {
        setResult(status.result);
        setPage(0);
        setDetections(await fetchDetections(jobId, 0, PAGE_SIZE));
      }
    } catch (e) {
      setNotice((e as Error).message);
    }
  }, []);

  const handleRun = async () => {
    if (!options || !upload) return;
    const problem = validateForRun(settings, upload.upload_id);
    if (problem) {
      setNotice(problem);
      return;
    }
    setNotice(null);
    clearResults();

    let accepted: JobAccepted;
    try {
      accepted = await postJson<JobAccepted>(
        '/api/analyze/run',
        toAnalyzeRequest(settings, upload.upload_id, options),
      );
    } catch (e) {
      setNotice((e as Error).message);
      return;
    }

    dispatch({ type: 'start', jobId: accepted.job_id, message: '解析中…' });
    unsubscribeRef.current?.();
    unsubscribeRef.current = subscribeJob(
      'analyze',
      accepted.job_id,
      (event) => {
        dispatch({ type: 'event', event });
        if (event.type === 'done') {
          void loadResult(accepted.job_id);
          unsubscribeRef.current?.();
        }
      },
      (message) => dispatch({ type: 'fail', message }),
    );
  };

  const handlePage = async (nextPage: number) => {
    if (!job.jobId) return;
    setPage(nextPage);
    setDetections(await fetchDetections(job.jobId, nextPage * PAGE_SIZE, PAGE_SIZE));
  };

  const handleSummary = async () => {
    if (!job.jobId) return;
    setSummarizing(true);
    setSummary(null);
    try {
      const res = await postJson<{ summary: string }>(`/api/analyze/summary/${job.jobId}`, {});
      setSummary(res.summary);
    } catch (e) {
      setSummary(`⚠️ ${(e as Error).message}`);
    } finally {
      setSummarizing(false);
    }
  };

  const models = availableModels(settings, options);
  const classNames = options ? Object.keys(options.coco_common) : [];
  const running = job.status === 'running';
  const downloadUrl = (kind: string) => `${API_BASE}/api/analyze/download/${job.jobId}/${kind}`;

  return (
    <div className="page analyze">
      <h1 className="page-title">🎥 Video ML Analytics Studio</h1>
      <p className="page-caption">メイン解析画面 — 検出 / セグ / 追跡 / ゾーン</p>

      {optionsError && <div className="alert alert-error">{optionsError}</div>}

      <div className="analyze-layout">
        {/* ---- 設定（旧サイドバー） ---- */}
        <section className="panel settings">
          <h2 className="panel-title">設定</h2>

          <fieldset className="field-group" disabled={running}>
            <legend>タスク</legend>
            <label className="check">
              <input
                type="checkbox"
                checked={settings.enableSeg}
                onChange={(e) => update({ enableSeg: e.target.checked })}
              />
              セグメンテーション（YOLO11-seg）
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={settings.enableTrack}
                onChange={(e) => update({ enableTrack: e.target.checked })}
              />
              トラッキング（ByteTrack / ID付与）
            </label>
            <label className={isZoneEnabled(settings) ? 'check' : 'check check-disabled'}>
              <input
                type="checkbox"
                checked={settings.enableZone}
                disabled={!isZoneEnabled(settings)}
                onChange={(e) => update({ enableZone: e.target.checked })}
              />
              ゾーン解析（滞留・侵入）
            </label>
            {!isZoneEnabled(settings) && <p className="hint">※ ゾーン解析にはトラッキングが必要です</p>}
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
            <legend>対象クラス</legend>
            <label className="check">
              <input
                type="checkbox"
                checked={settings.allClasses}
                onChange={(e) => update({ allClasses: e.target.checked })}
              />
              全クラス（COCO 80）
            </label>
            <div className={isClassSelectEnabled(settings) ? 'class-list' : 'class-list class-list-disabled'}>
              {classNames.map((name) => (
                <label key={name} className="check">
                  <input
                    type="checkbox"
                    disabled={!isClassSelectEnabled(settings)}
                    checked={settings.selectedClasses.includes(name)}
                    onChange={(e) =>
                      update({
                        selectedClasses: e.target.checked
                          ? [...settings.selectedClasses, name]
                          : settings.selectedClasses.filter((n) => n !== name),
                      })
                    }
                  />
                  {name}
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset className="field-group" disabled={running}>
            <legend>処理設定</legend>
            <label className="field">
              <span>フレーム間引き（N フレームに1回）: {settings.frameStride}</span>
              <input
                type="range"
                min={1}
                max={10}
                step={1}
                value={settings.frameStride}
                onChange={(e) => update({ frameStride: Number(e.target.value) })}
              />
            </label>
            <label className={isTraceLengthEnabled(settings) ? 'field' : 'field field-disabled'}>
              <span>軌跡の長さ（フレーム）: {settings.traceLength}</span>
              <input
                type="range"
                min={5}
                max={120}
                step={1}
                disabled={!isTraceLengthEnabled(settings)}
                value={settings.traceLength}
                onChange={(e) => update({ traceLength: Number(e.target.value) })}
              />
            </label>
          </fieldset>

          {settings.enableZone && (
            <fieldset className="field-group" disabled={running}>
              <legend>ゾーン定義（正規化 0〜1 / JSON）</legend>
              <textarea
                className="zone-text"
                rows={9}
                value={settings.zoneText}
                onChange={(e) => update({ zoneText: e.target.value })}
              />
            </fieldset>
          )}
        </section>

        {/* ---- 中央: 入力・実行・プレビュー ---- */}
        <section className="panel center">
          <h2 className="panel-title">映像プレビュー</h2>

          <div className="uploader">
            <input
              type="file"
              accept=".mp4,.mov,.avi"
              disabled={uploading || running}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void handleUpload(file);
              }}
            />
            {uploading && <span className="hint">アップロード中…</span>}
            {upload && !uploading && (
              <span className="hint">
                {upload.filename}（{(upload.size / (1024 * 1024)).toFixed(1)} MB）
              </span>
            )}
          </div>

          <button
            className="btn btn-primary"
            disabled={!upload || running || !options}
            onClick={() => void handleRun()}
          >
            ▶ Run 解析
          </button>

          {notice && <div className="alert alert-warn">{notice}</div>}

          {running && (
            <div className="progress">
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${(job.progress ?? 0) * 100}%` }} />
              </div>
              <div className="hint">{progressLabel(job)}</div>
            </div>
          )}

          {job.status === 'failed' && <div className="alert alert-error">{job.error}</div>}

          {result?.video_url && (
            <>
              <video className="preview" src={`${API_BASE}${result.video_url}`} controls />
              <p className="hint">
                ブラウザで再生できない場合は「⬇ 注釈付き動画」からDLしてください（コーデック依存）。
              </p>
            </>
          )}
        </section>

        {/* ---- 右: 結果ペイン ---- */}
        <section className="panel results">
          <h2 className="panel-title">結果ペイン</h2>
          {!result ? (
            <p className="hint">📤 動画をアップロードして Run すると、統計・ゾーン解析・エクスポートが出ます。</p>
          ) : (
            <>
              <Metric label="総検出数" value={result.total_detections} />
              <Metric label="ユニークID数" value={result.unique_track_ids} />
              <Metric label="処理フレーム" value={`${result.frames_processed} / ${result.frames_total}`} />

              <h3 className="section-title">クラス別（延べ / 最大同時）</h3>
              <DataTable
                empty="検出ゼロ"
                columns={[
                  { key: 'name', label: 'クラス' },
                  { key: 'total', label: '延べ', align: 'right' },
                  { key: 'max_in_frame', label: '最大同時', align: 'right' },
                ]}
                rows={Object.entries(result.stats).map(([name, stat]) => ({ name, ...stat }))}
              />

              <div className="downloads">
                <a className="btn" href={downloadUrl('csv')}>
                  ⬇ CSV
                </a>
                <a className="btn" href={downloadUrl('json')}>
                  ⬇ JSON
                </a>
                {result.video_url && (
                  <a className="btn" href={downloadUrl('video')}>
                    ⬇ 注釈付き動画
                  </a>
                )}
              </div>

              <button className="btn" disabled={summarizing} onClick={() => void handleSummary()}>
                {summarizing ? 'Claude が要約中…' : '📝 NL要約（Claude）'}
              </button>
              {summary && <div className="summary">{summary}</div>}
            </>
          )}
        </section>
      </div>

      {/* ---- 下: ゾーン解析・検出結果テーブル ---- */}
      {result && (
        <div className="analyze-tables">
          {Object.keys(result.zone_summary).length > 0 && (
            <section>
              <h2 className="section-title">ゾーン解析</h2>
              <DataTable
                columns={[
                  { key: 'zone', label: 'ゾーン' },
                  { key: 'unique_tracks', label: '通過ID数', align: 'right' },
                  { key: 'intrusions', label: '侵入回数', align: 'right' },
                  { key: 'max_occupancy', label: '最大同時', align: 'right' },
                  { key: 'total_dwell_sec', label: '合計滞留(s)', align: 'right' },
                  { key: 'max_dwell_sec', label: '最大滞留(s)', align: 'right' },
                ]}
                rows={Object.entries(result.zone_summary).map(([zone, stat]) => ({ zone, ...stat }))}
              />
              {result.per_track_dwell.length > 0 && (
                <>
                  <p className="hint">ID別 滞留時間</p>
                  <DataTable
                    columns={[
                      { key: 'zone', label: 'ゾーン' },
                      { key: 'tracker_id', label: 'ID', align: 'right' },
                      { key: 'dwell_sec', label: '滞留(s)', align: 'right' },
                    ]}
                    rows={result.per_track_dwell}
                  />
                </>
              )}
            </section>
          )}

          <section>
            <h2 className="section-title">検出結果テーブル</h2>
            {detections && (
              <>
                <p className="hint">
                  全 {detections.total} 件中 {detections.total === 0 ? 0 : detections.offset + 1}–
                  {detections.offset + detections.records.length} 件を表示（全件は CSV / JSON をダウンロード）
                </p>
                <DataTable
                  columns={[
                    { key: 'frame', label: 'frame', align: 'right' },
                    { key: 'time_sec', label: 'time_sec', align: 'right' },
                    { key: 'class_name', label: 'class' },
                    { key: 'confidence', label: 'conf', align: 'right' },
                    { key: 'x1', label: 'x1', align: 'right' },
                    { key: 'y1', label: 'y1', align: 'right' },
                    { key: 'x2', label: 'x2', align: 'right' },
                    { key: 'y2', label: 'y2', align: 'right' },
                    { key: 'tracker_id', label: 'tracker_id', align: 'right' },
                  ]}
                  rows={detections.records}
                  empty="検出ゼロ"
                />
                {detections.total > PAGE_SIZE && (
                  <div className="pager">
                    <button className="btn" disabled={page === 0} onClick={() => void handlePage(page - 1)}>
                      ← 前
                    </button>
                    <span className="hint">
                      {page + 1} / {Math.ceil(detections.total / PAGE_SIZE)}
                    </span>
                    <button
                      className="btn"
                      disabled={(page + 1) * PAGE_SIZE >= detections.total}
                      onClick={() => void handlePage(page + 1)}
                    >
                      次 →
                    </button>
                  </div>
                )}
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
