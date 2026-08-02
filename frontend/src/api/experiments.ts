/** 実験管理画面のエンドポイント。 */
import type {
  DatasetYaml,
  ExperimentsConfig,
  JobAccepted,
  JobStatus,
  RunsResponse,
  TrainRequest,
  TrainResult,
} from '../types';
import { getJson, postJson } from './client';

export const getExperimentsConfig = (): Promise<ExperimentsConfig> =>
  getJson<ExperimentsConfig>('/api/experiments/config');

export const getRuns = (experiment: string): Promise<RunsResponse> =>
  getJson<RunsResponse>(`/api/experiments/runs?experiment=${encodeURIComponent(experiment)}`);

export const startTraining = (body: TrainRequest): Promise<JobAccepted> =>
  postJson<JobAccepted>('/api/experiments/train', body);

export const getTrainingResult = (jobId: string): Promise<JobStatus<TrainResult>> =>
  getJson<JobStatus<TrainResult>>(`/api/experiments/result/${jobId}`);

export const generateDatasetYaml = (name: string, classes: string): Promise<DatasetYaml> =>
  postJson<DatasetYaml>('/api/experiments/dataset-yaml', { name, classes });
