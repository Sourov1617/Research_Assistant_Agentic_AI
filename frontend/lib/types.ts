export type ResearchStatus =
	| "idle"
	| "queued"
	| "running"
	| "stopping"
	| "stopped"
	| "complete"
	| "error";

export interface SourceConfig {
	key: string;
	label: string;
	enabled_by_default: boolean;
}

export interface AppConfigResponse {
	app: {
		title: string;
		theme: string;
		max_query_length: number;
	};
	defaults: {
		llm_provider: string;
		llm_model: string;
		llm_temperature: number;
		memory_enabled: boolean;
		fast_mode: boolean;
		year_min: number | null;
		year_max: number | null;
	};
	providers: string[];
	models: Record<string, string[]>;
	sources: SourceConfig[];
	streaming: {
		sse_endpoint_template: string;
		polling_endpoint_template: string;
	};
	memory: {
		enabled_default: boolean;
		backend: string;
	};
	kafka: {
		enabled: boolean;
		topic_prefix: string;
	};
}

export interface StartResearchPayload {
	query: string;
	llm_provider?: string;
	llm_model?: string;
	llm_temperature?: number;
	memory_enabled?: boolean;
	session_id?: string | null;
	year_min?: number | null;
	year_max?: number | null;
	fast_mode?: boolean;
	enabled_sources?: string[];
	fetch_round?: number;
}

export interface StartResearchResponse {
	job_id: string;
	status: ResearchStatus;
}

export interface Paper {
	title?: string;
	source?: string;
	year?: number;
	citation_count?: number;
	relevance_score?: number;
	similarity_score?: number;
	authors?: string[] | string;
	abstract?: string;
	url?: string;
	pdf_url?: string;
	doi?: string;
	synthesis?: {
		summary?: string;
		methodology?: string;
		contribution?: string;
		limitations?: string;
		future_scope?: string;
	};
}

export interface ResearchState {
	query?: string;
	session_id?: string | null;
	memory_enabled?: boolean;
	status_message?: string;
	parsed_intent?: Record<string, unknown>;
	search_plan?: Record<string, unknown>;
	insights?: Record<string, unknown>;
	papers?: Paper[];
	synthesized_papers?: Paper[];
	ranked_papers?: Paper[];
	memory_suggestions?: string[];
	final_output?: string | null;
	error?: string;
}

export interface JobStatusResponse {
	id: string;
	status: ResearchStatus;
	state: ResearchState | null;
	error: string | null;
	request: StartResearchPayload;
	created_at: string;
	updated_at: string;
}

export interface JobEventEnvelope {
	job_id: string;
	event:
		| "snapshot"
		| "started"
		| "interim"
		| "state"
		| "complete"
		| "error"
		| "stopped"
		| "heartbeat"
		| string;
	timestamp: string;
	data: Record<string, unknown>;
}

export interface MemorySessionSummary {
	session_id: string;
	created_at: string;
	updated_at: string;
	title: string;
	meta_json: string;
}

export interface MemorySessionDetail {
	session: MemorySessionSummary;
	messages: Array<{
		role: string;
		content: string;
		created_at: string;
	}>;
	papers: Paper[];
	insights: Array<Record<string, unknown>>;
}
