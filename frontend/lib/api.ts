import axios from "axios";
import type {
	AppConfigResponse,
	JobStatusResponse,
	MemorySessionDetail,
	MemorySessionSummary,
	StartResearchPayload,
	StartResearchResponse,
} from "./types";

export const API_BASE_URL =
	process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const api = axios.create({
	baseURL: API_BASE_URL,
});

export async function startResearch(
	payload: StartResearchPayload,
): Promise<StartResearchResponse> {
	const resp = await api.post<StartResearchResponse>(
		"/research/jobs",
		payload,
	);
	return resp.data;
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
	const resp = await api.get<JobStatusResponse>(`/research/jobs/${jobId}`);
	return resp.data;
}

export async function stopResearch(jobId: string) {
	const resp = await api.post(`/research/jobs/${jobId}/stop`);
	return resp.data;
}

export async function getConfig(): Promise<AppConfigResponse> {
	const resp = await api.get<AppConfigResponse>("/config");
	return resp.data;
}

export async function getProviders(): Promise<string[]> {
	const resp = await api.get<{ providers: string[] }>("/providers");
	return resp.data.providers || [];
}

export async function getModels(provider: string): Promise<string[]> {
	const resp = await api.get<{ models: string[] }>(`/models/${provider}`);
	return resp.data.models || [];
}

export function getJobEventsUrl(jobId: string): string {
	return `${API_BASE_URL}/research/jobs/${jobId}/events`;
}

export async function listMemorySessions(): Promise<MemorySessionSummary[]> {
	const resp = await api.get<{ sessions: MemorySessionSummary[] }>(
		"/memory/sessions",
	);
	return resp.data.sessions || [];
}

export async function getMemorySession(
	sessionId: string,
): Promise<MemorySessionDetail> {
	const resp = await api.get<MemorySessionDetail>(
		`/memory/sessions/${sessionId}`,
	);
	return resp.data;
}

export async function deleteMemorySession(sessionId: string) {
	const resp = await api.delete<{ session_id: string; deleted: boolean }>(
		`/memory/sessions/${sessionId}`,
	);
	return resp.data;
}
