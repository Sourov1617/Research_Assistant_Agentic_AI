import type {
	JobEventEnvelope,
	JobStatusResponse,
	Paper,
	ResearchState,
	StartResearchPayload,
} from "./types";

export const PIPELINE_STEPS = [
	"Understanding research intent",
	"Planning search strategy",
	"Searching databases and web",
	"Ranking and filtering results",
	"Synthesising papers",
	"Generating research insights",
	"Updating memory",
];

export function subscribeSessionStorage(onStoreChange: () => void) {
	if (typeof window === "undefined") {
		return () => {};
	}

	const handleStorage = (event: StorageEvent) => {
		if (event.storageArea === window.sessionStorage) {
			onStoreChange();
		}
	};

	window.addEventListener("storage", handleStorage);
	return () => window.removeEventListener("storage", handleStorage);
}

export function getStoredJobId() {
	if (typeof window === "undefined") return null;
	return window.sessionStorage.getItem("research-job-id");
}

export function getStoredPayload() {
	if (typeof window === "undefined") return null;
	return window.sessionStorage.getItem("research-job-payload");
}

export function clearStoredResearchSession() {
	if (typeof window === "undefined") return;
	window.sessionStorage.removeItem("research-job-id");
	window.sessionStorage.removeItem("research-job-payload");
}

export function dedupePapers(existing: Paper[], incoming: Paper[]) {
	const seen = new Set<string>();
	const combined = [...existing, ...incoming];
	const result: Paper[] = [];

	for (const paper of combined) {
		const key = (paper.url || paper.doi || paper.title || "")
			.trim()
			.toLowerCase();
		if (!key || seen.has(key)) continue;
		seen.add(key);
		result.push(paper);
	}

	return result;
}

export function inferPipelineStep(message: string, memoryEnabled: boolean) {
	const lower = message.toLowerCase();

	if (
		lower.includes("query understood") ||
		lower.includes("analysing research intent") ||
		lower.includes("analyzing research intent")
	) {
		return 1;
	}
	if (lower.includes("search plan") || lower.includes("planning")) {
		return 2;
	}
	if (
		lower.includes("retriev") ||
		lower.includes("searching") ||
		lower.includes("papers fetched")
	) {
		return 3;
	}
	if (lower.includes("rank")) {
		return 4;
	}
	if (lower.includes("synthes")) {
		return 5;
	}
	if (lower.includes("insight")) {
		return 6;
	}
	if (memoryEnabled && lower.includes("memory")) {
		return 7;
	}

	return 0;
}

export function formatTime(value: string) {
	try {
		return new Date(value).toLocaleString();
	} catch {
		return value;
	}
}

export function extractStateFromEvent(
	envelope: JobEventEnvelope,
): ResearchState | null {
	const data = envelope.data;
	const stateCandidate =
		(data.state as ResearchState | undefined) ||
		((data as unknown) as ResearchState);

	if (stateCandidate && typeof stateCandidate === "object") {
		return stateCandidate;
	}

	return null;
}

export function getStatusText(
	status: JobStatusResponse["status"] | "idle",
	state: ResearchState | null,
) {
	return (
		state?.status_message ||
		(status === "running"
			? "Research pipeline is running..."
			: status === "queued"
				? "Job is queued..."
				: status === "complete"
					? "Research completed"
					: status === "error"
						? "Research failed"
						: status === "stopped"
							? "Research stopped"
							: status === "stopping"
								? "Stopping research..."
								: "Ready")
	);
}

export function buildFetchMorePayload(
	payload: StartResearchPayload,
	fetchRound: number,
): StartResearchPayload {
	return {
		...payload,
		memory_enabled: false,
		fetch_round: fetchRound,
	};
}
