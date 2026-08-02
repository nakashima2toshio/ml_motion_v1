/** 解析画面のエンドポイント。 */
import type { AnalyzeResultSummary, DetectionPage, JobStatus } from '../types';
import { getJson } from './client';

/** 結果サマリ（検出レコードは含まれない）。 */
export const fetchAnalyzeResult = (jobId: string): Promise<JobStatus<AnalyzeResultSummary>> =>
  getJson<JobStatus<AnalyzeResultSummary>>(`/api/analyze/result/${jobId}`);

/** 検出結果テーブルの 1 ページ分。 */
export const fetchDetections = (jobId: string, offset: number, limit: number): Promise<DetectionPage> =>
  getJson<DetectionPage>(`/api/analyze/detections/${jobId}?offset=${offset}&limit=${limit}`);
