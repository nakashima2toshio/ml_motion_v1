/**
 * アノテーション QA 画面 — Streamlit 版 `app/views/annotation_qa.py` の React 版（R2）。
 *
 * 左: 画像アップロード・プレビュー・提案ラベル・レビュー実行
 * 右: Claude Vision のレビュー結果（Markdown）
 *
 * 受け入れ基準は `docs/manual/05_annotation_qa.md`。
 */
import { useEffect, useState } from 'react';

import { getOptions, reviewAnnotation } from '../api/client';
import { Markdown } from '../components/Markdown';
import type { AnnotationReview, Options } from '../types';

export function AnnotationQaPage(): JSX.Element {
  const [options, setOptions] = useState<Options | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [labelsText, setLabelsText] = useState('person,car');
  const [result, setResult] = useState<AnnotationReview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(false);

  useEffect(() => {
    getOptions()
      .then(setOptions)
      .catch(() => setOptions(null));
  }, []);

  // 選択した画像の Object URL は差し替え・離脱時に解放する。
  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const handleReview = async () => {
    if (!file) return;
    setReviewing(true);
    setError(null);
    setResult(null);
    try {
      setResult(await reviewAnnotation(file, labelsText));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setReviewing(false);
    }
  };

  return (
    <div className="page">
      <h1 className="page-title">🏷 Annotation QA</h1>
      <p className="page-caption">
        アノテーション品質画面 — Claude Vision レビュー
        {options && (
          <>
            {' '}
            ／ モデル: <code>{options.claude_model}</code>（<code>ANTHROPIC_API_KEY</code> が必要）
          </>
        )}
      </p>

      <div className="two-column">
        <section className="panel">
          <h2 className="panel-title">画像</h2>

          <div className="uploader">
            <input
              type="file"
              accept=".jpg,.jpeg,.png,.webp"
              disabled={reviewing}
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setResult(null);
                setError(null);
              }}
            />
          </div>

          {previewUrl && <img className="preview-image" src={previewUrl} alt="レビュー対象のフレーム画像" />}

          <label className="field">
            <span>提案ラベル（カンマ区切り）</span>
            <input
              type="text"
              value={labelsText}
              disabled={reviewing}
              onChange={(e) => setLabelsText(e.target.value)}
            />
          </label>

          <button className="btn btn-primary" disabled={!file || reviewing} onClick={() => void handleReview()}>
            {reviewing ? 'Claude がレビュー中…' : '🔍 Claude でレビュー'}
          </button>
        </section>

        <section className="panel">
          <h2 className="panel-title">検出された問題（Claude Vision）</h2>

          {!file && <p className="hint">🖼 画像をアップロードし、提案ラベルを入れてレビューを実行してください。</p>}
          {error && <div className="alert alert-error">{error}</div>}
          {result && (
            <>
              <p className="hint">
                レビュー対象ラベル: {result.labels.join('、')} ／ モデル: <code>{result.model}</code>
              </p>
              <Markdown source={result.review} />
            </>
          )}
        </section>
      </div>
    </div>
  );
}
