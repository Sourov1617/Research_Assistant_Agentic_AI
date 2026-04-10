import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import {
	deleteMemorySession,
	getConfig,
	getJobEventsUrl,
	getJobStatus,
	getMemorySession,
	listMemorySessions,
	startResearch,
	stopResearch,
} from "../lib/api";
import {
	buildFetchMorePayload,
	clearStoredResearchSession,
	dedupePapers,
	extractStateFromEvent,
	getStatusText,
	getStoredJobId,
	getStoredPayload,
	inferPipelineStep,
	subscribeSessionStorage,
} from "../lib/research";
import type {
	AppConfigResponse,
	JobEventEnvelope,
	JobStatusResponse,
	MemorySessionDetail,
	MemorySessionSummary,
	Paper,
	ResearchState,
	ResearchStatus,
	StartResearchPayload,
} from "../lib/types";

type StreamStatus = "idle" | "connecting" | "connected" | "fallback";

export function useResearchWorkspace() {
	const [config, setConfig] = useState<AppConfigResponse | null>(null);
	const [jobId, setJobId] = useState<string | null>(null);
	const [status, setStatus] = useState<ResearchStatus>("idle");
	const [jobMeta, setJobMeta] = useState<JobStatusResponse | null>(null);
	const [state, setState] = useState<ResearchState | null>(null);
	const [allPapers, setAllPapers] = useState<Paper[]>([]);
	const [lastPayload, setLastPayload] = useState<StartResearchPayload | null>(null);
	const [fetchRound, setFetchRound] = useState(0);
	const [isFetchingMore, setIsFetchingMore] = useState(false);
	const [noMorePapers, setNoMorePapers] = useState(false);
	const [streamConnected, setStreamConnected] = useState(false);
	const [streamFallback, setStreamFallback] = useState(false);
	const [bootError, setBootError] = useState<string | null>(null);
	const [sessions, setSessions] = useState<MemorySessionSummary[]>([]);
	const [sessionDetail, setSessionDetail] = useState<MemorySessionDetail | null>(
		null,
	);
	const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);

	const eventSourceRef = useRef<EventSource | null>(null);
	const storedJobId = useSyncExternalStore(subscribeSessionStorage, getStoredJobId, () => null);
	const storedPayloadRaw = useSyncExternalStore(
		subscribeSessionStorage,
		getStoredPayload,
		() => null,
	);

	const restoredPayload = useMemo(() => {
		if (!storedPayloadRaw) return null;
		try {
			return JSON.parse(storedPayloadRaw) as StartResearchPayload;
		} catch {
			return null;
		}
	}, [storedPayloadRaw]);

	const effectiveJobId = jobId ?? storedJobId;
	const effectiveLastPayload = lastPayload ?? restoredPayload;

	useEffect(() => {
		let alive = true;

		Promise.all([getConfig(), listMemorySessions()])
			.then(([cfg, foundSessions]) => {
				if (!alive) return;
				setConfig(cfg);
				setSessions(foundSessions);
				setBootError(null);
			})
			.catch((error) => {
				if (!alive) return;
				console.error(error);
				setBootError(
					"Frontend could not reach the backend. Start the FastAPI server and try again.",
				);
			});

		return () => {
			alive = false;
		};
	}, []);

	useEffect(() => {
		if (jobId) {
			window.sessionStorage.setItem("research-job-id", jobId);
		} else {
			window.sessionStorage.removeItem("research-job-id");
		}
	}, [jobId]);

	useEffect(() => {
		if (lastPayload) {
			window.sessionStorage.setItem(
				"research-job-payload",
				JSON.stringify(lastPayload),
			);
		} else {
			window.sessionStorage.removeItem("research-job-payload");
		}
	}, [lastPayload]);

	useEffect(() => {
		if (!effectiveJobId) return;

		if (eventSourceRef.current) {
			eventSourceRef.current.close();
		}

		const source = new EventSource(getJobEventsUrl(effectiveJobId));
		eventSourceRef.current = source;

		const applySnapshot = (snapshot: JobStatusResponse) => {
			setJobMeta(snapshot);
			setStatus(snapshot.status);
			if (snapshot.state) {
				setState(snapshot.state);
				const papers =
					snapshot.state.synthesized_papers ||
					snapshot.state.ranked_papers ||
					[];
				if ((snapshot.request.fetch_round || 0) === 0) {
					setAllPapers(papers);
				}
			}
		};

		const handleEnvelope = (envelope: JobEventEnvelope) => {
			if (envelope.event === "snapshot") {
				applySnapshot(envelope.data as unknown as JobStatusResponse);
				return;
			}

			if (envelope.event === "heartbeat") {
				setStreamConnected(true);
				setStreamFallback(false);
				return;
			}

			if (envelope.event === "started") {
				setStatus("running");
				setStreamConnected(true);
				setStreamFallback(false);
				return;
			}

			if (envelope.event === "interim") {
				const statusMessage = envelope.data.status_message;
				if (typeof statusMessage === "string") {
					setState((prev) => ({
						...(prev || {}),
						status_message: statusMessage,
					}));
				}
				setStreamConnected(true);
				setStreamFallback(false);
				return;
			}

			if (envelope.event === "state") {
				const nextState = extractStateFromEvent(envelope);
				if (nextState) {
					setState(nextState);
				}
				setStatus(
					(typeof envelope.data.status === "string"
						? envelope.data.status
						: "running") as ResearchStatus,
				);
				setStreamConnected(true);
				setStreamFallback(false);
				return;
			}

			if (
				envelope.event === "complete" ||
				envelope.event === "error" ||
				envelope.event === "stopped"
			) {
				const nextState = extractStateFromEvent(envelope);
				setStatus(envelope.event as ResearchStatus);

				if (nextState) {
					setState(nextState);
					const incoming =
						nextState.synthesized_papers ||
						nextState.ranked_papers ||
						[];

					if ((effectiveLastPayload?.fetch_round || 0) === 0) {
						setAllPapers(incoming);
						setNoMorePapers(false);
					} else {
						setAllPapers((prev) => {
							const merged = dedupePapers(prev, incoming);
							if (merged.length === prev.length) {
								setNoMorePapers(true);
							}
							return merged;
						});
					}

					if (nextState.session_id) {
						getMemorySession(nextState.session_id)
							.then((detail) => setSessionDetail(detail))
							.catch((error) => console.error(error));
						listMemorySessions()
							.then((items) => setSessions(items))
							.catch((error) => console.error(error));
					}
				}

				setIsFetchingMore(false);
				setStreamConnected(true);
				setStreamFallback(false);

				if (envelope.event !== "complete") {
					window.sessionStorage.removeItem("research-job-id");
				}

				source.close();
			}
		};

		const listener = (event: MessageEvent<string>) => {
			try {
				const envelope = JSON.parse(event.data) as JobEventEnvelope;
				handleEnvelope(envelope);
			} catch (error) {
				console.error("Failed to parse SSE event", error);
			}
		};

		[
			"snapshot",
			"started",
			"interim",
			"state",
			"complete",
			"error",
			"stopped",
			"heartbeat",
		].forEach((eventName) => {
			source.addEventListener(eventName, listener as EventListener);
		});

		source.onerror = async () => {
			setStreamConnected(false);
			setStreamFallback(true);
			try {
				const snapshot = await getJobStatus(effectiveJobId);
				applySnapshot(snapshot);
				if (
					snapshot.status === "complete" ||
					snapshot.status === "error" ||
					snapshot.status === "stopped"
				) {
					source.close();
				}
			} catch (error) {
				console.error("Polling fallback failed", error);
			}
		};

		return () => {
			source.close();
			if (eventSourceRef.current === source) {
				eventSourceRef.current = null;
			}
		};
	}, [effectiveJobId, effectiveLastPayload]);

	function handleStarted(newJobId: string, payload: StartResearchPayload) {
		setJobId(newJobId);
		setLastPayload(payload);
		setJobMeta(null);
		setStatus("queued");
		setStreamConnected(false);
		setStreamFallback(false);

		if ((payload.fetch_round || 0) === 0) {
			setState(null);
			setAllPapers([]);
			setFetchRound(0);
			setNoMorePapers(false);
			setSessionDetail(null);
		}
	}

	async function handleStop() {
		if (!effectiveJobId) return;
		await stopResearch(effectiveJobId);
		setStatus("stopping");
	}

	async function handleFetchMore() {
		if (!effectiveLastPayload || isFetchingMore || status === "running") return;

		const nextRound = fetchRound + 1;
		setFetchRound(nextRound);
		setIsFetchingMore(true);
		setNoMorePapers(false);

		const payload = buildFetchMorePayload(effectiveLastPayload, nextRound);
		const data = await startResearch(payload);

		if (data?.job_id) {
			handleStarted(data.job_id, payload);
		} else {
			setIsFetchingMore(false);
		}
	}

	async function handleSessionSelect(sessionId: string) {
		try {
			const detail = await getMemorySession(sessionId);
			setSessionDetail(detail);
		} catch (error) {
			console.error(error);
		}
	}

	function resetWorkspaceState() {
		if (eventSourceRef.current) {
			eventSourceRef.current.close();
			eventSourceRef.current = null;
		}
		clearStoredResearchSession();
		setJobId(null);
		setLastPayload(null);
		setJobMeta(null);
		setStatus("idle");
		setState(null);
		setAllPapers([]);
		setFetchRound(0);
		setIsFetchingMore(false);
		setNoMorePapers(false);
		setStreamConnected(false);
		setStreamFallback(false);
		setSessionDetail(null);
	}

	function handleClearRecentSession() {
		resetWorkspaceState();
	}

	async function handleDeleteMemorySession(sessionId: string) {
		const confirmed = window.confirm(
			"Delete this saved memory session? This removes its stored messages, papers, and insights.",
		);
		if (!confirmed) return;

		setDeletingSessionId(sessionId);
		try {
			await deleteMemorySession(sessionId);
			setSessions((prev) =>
				prev.filter((session) => session.session_id !== sessionId),
			);
			setSessionDetail((prev) =>
				prev?.session.session_id === sessionId ? null : prev,
			);
			setState((prev) =>
				prev?.session_id === sessionId ? { ...prev, session_id: null } : prev,
			);
			setLastPayload((prev) =>
				prev?.session_id === sessionId ? { ...prev, session_id: null } : prev,
			);
		} catch (error) {
			console.error(error);
		} finally {
			setDeletingSessionId(null);
		}
	}

	const statusText = getStatusText(status, state);
	const memoryEnabled = Boolean(
		state?.memory_enabled || effectiveLastPayload?.memory_enabled,
	);
	const stepIndex = inferPipelineStep(statusText, memoryEnabled);
	const appTitle = config?.app.title || "Research Discovery Backend UI";
	const activePaperCount = allPapers.length;
	const activeSessionTitle = sessionDetail?.session.title || "No session selected";
	const streamStatus: StreamStatus = !effectiveJobId
		? "idle"
		: streamConnected
			? "connected"
			: streamFallback
				? "fallback"
				: "connecting";

	return {
		activePaperCount,
		activeSessionTitle,
		allPapers,
		appTitle,
		bootError,
		config,
		effectiveJobId,
		handleFetchMore,
		handleClearRecentSession,
		handleDeleteMemorySession,
		handleSessionSelect,
		handleStarted,
		handleStop,
		isFetchingMore,
		jobMeta,
		memoryEnabled,
		noMorePapers,
		sessionDetail,
		sessions,
		state,
		status,
		statusText,
		stepIndex,
		streamStatus,
		deletingSessionId,
	};
}
