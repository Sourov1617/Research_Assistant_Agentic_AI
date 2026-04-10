import { useEffect, useMemo, useState } from "react";
import { getConfig, getModels, startResearch } from "../lib/api";
import type {
	AppConfigResponse,
	SourceConfig,
	StartResearchPayload,
} from "../lib/types";

interface UseSearchFormOptions {
	disabled?: boolean;
	onStarted: (jobId: string, payload: StartResearchPayload) => void;
}

export function useSearchForm({
	disabled = false,
	onStarted,
}: UseSearchFormOptions) {
	const currentYear = new Date().getFullYear();

	const [config, setConfig] = useState<AppConfigResponse | null>(null);
	const [loadingConfig, setLoadingConfig] = useState(true);
	const [query, setQuery] = useState("");
	const [memoryEnabled, setMemoryEnabled] = useState(false);
	const [provider, setProvider] = useState("gemini");
	const [model, setModel] = useState("");
	const [temperature, setTemperature] = useState(0.3);
	const [fastMode, setFastMode] = useState(false);
	const [yearMin, setYearMin] = useState(currentYear - 5);
	const [yearMax, setYearMax] = useState(currentYear);
	const [enabledSources, setEnabledSources] = useState<string[]>([]);
	const [submitting, setSubmitting] = useState(false);
	const [configError, setConfigError] = useState<string | null>(null);

	useEffect(() => {
		let mounted = true;

		getConfig()
			.then((cfg) => {
				if (!mounted) return;
				setConfigError(null);
				setConfig(cfg);
				setMemoryEnabled(cfg.defaults.memory_enabled);
				setProvider(cfg.defaults.llm_provider || "gemini");
				setModel(cfg.defaults.llm_model || "");
				setTemperature(cfg.defaults.llm_temperature ?? 0.3);
				setFastMode(cfg.defaults.fast_mode ?? false);
				const minYear = cfg.defaults.year_min ?? currentYear - 5;
				const maxYear = cfg.defaults.year_max ?? currentYear;
				setYearMin(minYear);
				setYearMax(maxYear);
				setEnabledSources(
					cfg.sources
						.filter((source) => source.enabled_by_default)
						.map((source) => source.key),
				);
			})
			.catch((error) => {
				if (!mounted) return;
				console.error(error);
				setConfigError("Could not load backend configuration.");
			})
			.finally(() => {
				if (mounted) setLoadingConfig(false);
			});

		return () => {
			mounted = false;
		};
	}, [currentYear]);

	const providerModels = useMemo(
		() => config?.models?.[provider] || [],
		[config, provider],
	);

	useEffect(() => {
		if (providerModels.length === 0) {
			getModels(provider).then((models) => {
				if (models.length > 0) setModel(models[0]);
			});
			return;
		}
		if (!providerModels.includes(model)) {
			setModel(providerModels[0]);
		}
	}, [provider, providerModels, model]);

	function toggleSource(source: SourceConfig) {
		setEnabledSources((prev) => {
			if (prev.includes(source.key)) {
				return prev.filter((item) => item !== source.key);
			}
			return [...prev, source.key];
		});
	}

	async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
		event.preventDefault();
		if (!query.trim() || disabled || submitting) return;

		const payload: StartResearchPayload = {
			query: query.trim(),
			llm_provider: provider,
			llm_model: model,
			llm_temperature: temperature,
			memory_enabled: memoryEnabled,
			year_min: Math.min(yearMin, yearMax),
			year_max: Math.max(yearMin, yearMax),
			fast_mode: fastMode,
			enabled_sources: enabledSources,
			fetch_round: 0,
		};

		setSubmitting(true);
		try {
			const data = await startResearch(payload);
			if (data?.job_id) {
				onStarted(data.job_id, payload);
			}
		} finally {
			setSubmitting(false);
		}
	}

	return {
		canSubmit:
			!disabled &&
			!submitting &&
			!loadingConfig &&
			query.trim().length > 0 &&
			enabledSources.length > 0,
		config,
		configError,
		currentYear,
		disabled,
		enabledSources,
		fastMode,
		handleSubmit,
		loadingConfig,
		maxChars: config?.app.max_query_length ?? 5000,
		memoryEnabled,
		model,
		provider,
		providerModels,
		query,
		setEnabledSources,
		setFastMode,
		setMemoryEnabled,
		setModel,
		setProvider,
		setQuery,
		setTemperature,
		setYearMax,
		setYearMin,
		submitting,
		temperature,
		toggleSource,
		yearMax,
		yearMin,
	};
}
