/**
 * 実験管理・モデル管理画面 — Streamlit 版 `app/views/experiments.py` の React 版（R3）。
 *
 * MLflow から Run 一覧・メトリクス比較を取得し、転移学習ジョブの起動と
 * data.yaml の生成を行う。**MLflow 未起動でも画面は表示する**（Streamlit 版と同じ）。
 *
 * 受け入れ基準は `docs/manual/03_experiments.md`。
 */
import { useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';

import {
  generateDatasetYaml,
  getExperimentsConfig,
  getRuns,
  getTrainingResult,
  startTraining,
} from '../api/experiments';
import { getOptions, subscribeJob } from '../api/client';
import { DataTable } from '../components/DataTable';
import {
  defaultTrainForm,
  parseClasses,
  type TrainForm,
  toTrainRequest,
  validateTrainForm,
} from '../state/experiments';
import type { DatasetYaml, ExperimentsConfig, Options, RunsResponse, TrainResult } from '../types';

export function ExperimentsPage(): ReactElement {
  const [config, setConfig] = useState<ExperimentsConfig | null>(null);
  const [options, setOptions] = useState<Options | null>(null);
  const [experiment, setExperiment] = useState('');

  const [runs, setRuns] = useState<RunsResponse | null>(null);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [loadingRuns, setLoadingRuns] = useState(false);

  const [form, setForm] = useState<TrainForm>(() => defaultTrainForm('yolo11s.pt'));
  const [trainNotice, setTrainNotice] = useState<string | null>(null);
  const [trainStatus, setTrainStatus] = useState<'idle' | 'running' | 'completed' | 'failed'>('idle');
  const [trainResult, setTrainResult] = useState<TrainResult | null>(null);
  const [trainError, setTrainError] = useState<string | null>(null);

  const [datasetName, setDatasetName] = useState('custom');
  const [datasetClasses, setDatasetClasses] = useState('person,car,truck,bus,bicycle,motorcycle');
  const [datasetYaml, setDatasetYaml] = useState<DatasetYaml | null>(null);
  const [datasetError, setDatasetError] = useState<string | null>(null);

  const unsubscribeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    getExperimentsConfig()
      .then((data) => {
        setConfig(data);
        setExperiment(data.default_experiment);
      })
      .catch((e: Error) => setRunsError(e.message));
    getOptions()
      .then((data) => {
        setOptions(data);
        setForm(defaultTrainForm(data.models[1] ?? 'yolo11s.pt'));
      })
      .catch(() => setOptions(null));
  }, []);

  useEffect(() => () => unsubscribeRef.current?.(), []);

  const handleLoadRuns = async () => {
    setLoadingRuns(true);
    setRunsError(null);
    try {
      setRuns(await getRuns(experiment));
    } catch (e) {
      setRuns(null);
      setRunsError((e as Error).message);
    } finally {
      setLoadingRuns(false);
    }
  };

  const handleTrain = async () => {
    const problem = validateTrainForm(form);
    if (problem) {
      setTrainNotice(problem);
      return;
    }
    setTrainNotice(null);
    setTrainResult(null);
    setTrainError(null);

    try {
      const accepted = await startTraining(toTrainRequest(form, experiment));
      setTrainStatus('running');
      unsubscribeRef.current?.();
      unsubscribeRef.current = subscribeJob(
        'experiments',
        accepted.job_id,
        (event) => {
          if (event.type === 'error') {
            setTrainStatus('failed');
            setTrainError(event.message);
            unsubscribeRef.current?.();
          }
          if (event.type === 'done') {
            unsubscribeRef.current?.();
            void getTrainingResult(accepted.job_id).then((status) => {
              setTrainStatus(status.status === 'completed' ? 'completed' : 'failed');
              setTrainResult(status.result);
              setTrainError(status.error);
            });
          }
        },
        (message) => {
          setTrainStatus('failed');
          setTrainError(message);
        },
      );
    } catch (e) {
      setTrainNotice((e as Error).message);
    }
  };

  const handleDatasetYaml = async () => {
    setDatasetError(null);
    try {
      setDatasetYaml(await generateDatasetYaml(datasetName, datasetClasses));
    } catch (e) {
      setDatasetYaml(null);
      setDatasetError((e as Error).message);
    }
  };

  const models = options ? [...options.models, ...options.seg_models] : [];
  const training = trainStatus === 'running';

  return (
    <div className="page">
      <h1 className="page-title">📊 Experiments &amp; Models</h1>
      <p className="page-caption">実験管理・モデル管理画面 — MLflow / Model Registry</p>

      <p className="hint">
        MLflow Tracking URI: <code>{config?.tracking_uri ?? '取得中…'}</code>
      </p>

      <label className="field field-inline">
        <span>実験名</span>
        <input type="text" value={experiment} onChange={(e) => setExperiment(e.target.value)} />
      </label>

      {/* ---- Run 一覧・比較 ---- */}
      <h2 className="section-title">Run 一覧・比較</h2>
      <button className="btn btn-primary" disabled={loadingRuns} onClick={() => void handleLoadRuns()}>
        {loadingRuns ? '取得中…' : '🔄 MLflow から取得'}
      </button>

      {runsError && <div className="alert alert-error">{runsError}</div>}

      {!runs && !runsError && <p className="hint">📡「MLflow から取得」を押すと Run 一覧を表示します。</p>}

      {runs && runs.rows.length === 0 && (
        <div className="alert alert-warn">
          実験 &apos;{runs.experiment}&apos; に Run がありません。学習ジョブを実行してください。
        </div>
      )}

      {runs && runs.rows.length > 0 && (
        <>
          <DataTable
            columns={[
              { key: 'run', label: 'run' },
              { key: 'status', label: 'status' },
              { key: 'mAP50', label: 'mAP50', align: 'right' },
              { key: 'mAP50-95', label: 'mAP50-95', align: 'right' },
            ]}
            rows={runs.rows}
          />
          {runs.best_run_name && (
            <div className="alert alert-ok">
              最良 Run: <strong>{runs.best_run_name}</strong>（mAP50-95 = {runs.best_metric?.toFixed(4)}）
            </div>
          )}
        </>
      )}

      {/* ---- 転移学習ジョブ ---- */}
      <h2 className="section-title">新規学習ジョブ（転移学習 / Fine-tuning）</h2>
      <div className="panel">
        <div className="form-row">
          <label className="field">
            <span>data.yaml パス</span>
            <input
              type="text"
              value={form.dataYaml}
              disabled={training}
              onChange={(e) => setForm({ ...form, dataYaml: e.target.value })}
            />
          </label>
          <label className="field">
            <span>ベースモデル</span>
            <select
              value={form.baseModel}
              disabled={training}
              onChange={(e) => setForm({ ...form, baseModel: e.target.value })}
            >
              {models.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>epochs</span>
            <input
              type="number"
              min={1}
              max={1000}
              value={form.epochs}
              disabled={training}
              onChange={(e) => setForm({ ...form, epochs: Number(e.target.value) })}
            />
          </label>
        </div>
        <label className="field">
          <span>Run 名（任意）</span>
          <input
            type="text"
            value={form.runName}
            disabled={training}
            onChange={(e) => setForm({ ...form, runName: e.target.value })}
          />
        </label>

        <button className="btn btn-primary" disabled={training} onClick={() => void handleTrain()}>
          {training ? '学習中…' : '▶ 学習を開始'}
        </button>

        {trainNotice && <div className="alert alert-warn">{trainNotice}</div>}

        {training && (
          <div className="alert alert-warn">
            ⚙️ 学習は ultralytics + MLflow を要し、長時間かつ高負荷です。M2 Mac では軽量・短時間に留め、
            本格学習はクラウド GPU を推奨します。進捗は MLflow UI / コンソールで確認してください。
          </div>
        )}
        {trainError && <div className="alert alert-error">{trainError}</div>}
        {trainResult && (
          <>
            <div className="alert alert-ok">
              学習完了: run_id=<code>{trainResult.run_id}</code>
            </div>
            <pre className="code-block">{JSON.stringify(trainResult.metrics, null, 2)}</pre>
          </>
        )}
      </div>

      {/* ---- データセット雛形生成 ---- */}
      <h2 className="section-title">データセット data.yaml 生成</h2>
      <div className="panel">
        <div className="form-row">
          <label className="field">
            <span>データセット名</span>
            <input type="text" value={datasetName} onChange={(e) => setDatasetName(e.target.value)} />
          </label>
          <label className="field">
            <span>クラス（カンマ区切り / 並び順がクラス ID）</span>
            <input type="text" value={datasetClasses} onChange={(e) => setDatasetClasses(e.target.value)} />
          </label>
        </div>
        <p className="hint">クラス: {parseClasses(datasetClasses).join(' / ') || '（未入力）'}</p>
        <button className="btn" onClick={() => void handleDatasetYaml()}>
          data.yaml を生成
        </button>
        {datasetError && <div className="alert alert-error">{datasetError}</div>}
        {datasetYaml && <pre className="code-block">{datasetYaml.yaml}</pre>}
      </div>

      {/* ---- Model Registry ---- */}
      <h2 className="section-title">Model Registry</h2>
      <div className="panel">
        <p className="hint">ステージ: {options?.registry_stages.join(' / ') ?? '取得中…'}</p>
        <p>
          学習済みベスト重みを <code>register_model()</code> で登録し、<code>transition_stage()</code> で
          Staging→Production→Archived を管理します（仕様書 §4.2）。
        </p>
        <button className="btn" disabled>
          Claude自動レビュー（P6）
        </button>
      </div>
    </div>
  );
}
