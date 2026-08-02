/** 本番化・最適化画面のエンドポイント。 */
import type {
  BatchRequest,
  BatchResult,
  DiscoverResponse,
  ExportResponse,
  JobAccepted,
  JobStatus,
  Quantization,
  RegistryUri,
} from '../types';
import { getJson, postJson } from './client';

export const discoverMedia = (inputDir: string): Promise<DiscoverResponse> =>
  postJson<DiscoverResponse>('/api/production/discover', { input_dir: inputDir });

export const startBatch = (body: BatchRequest): Promise<JobAccepted> =>
  postJson<JobAccepted>('/api/production/batch', body);

export const getBatchResult = (jobId: string): Promise<JobStatus<BatchResult>> =>
  getJson<JobStatus<BatchResult>>(`/api/production/result/${jobId}`);

export const exportModel = (
  weights: string,
  fmt: string,
  quantization: Quantization,
): Promise<ExportResponse> =>
  postJson<ExportResponse>('/api/production/export', { weights, fmt, quantization });

export const getRegistryUri = (name: string, stage: string): Promise<RegistryUri> =>
  getJson<RegistryUri>(
    `/api/production/registry-uri?name=${encodeURIComponent(name)}&stage=${encodeURIComponent(stage)}`,
  );
