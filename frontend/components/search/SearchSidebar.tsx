import type { SourceConfig } from "../../lib/types";
import FormSection from "./FormSection";

const PROVIDER_LABELS: Record<string, string> = {
	azure_openai: "Azure OpenAI",
	openrouter: "OpenRouter",
	gemini: "Google Gemini",
	groq: "Groq",
	openai: "OpenAI",
	anthropic: "Anthropic",
};

const fieldClassName =
	"w-full rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm text-stone-900 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100";

interface SearchSidebarProps {
	configError: string | null;
	providers: string[];
	configSources: SourceConfig[];
	currentYear: number;
	disabled: boolean;
	enabledSources: string[];
	fastMode: boolean;
	loadingConfig: boolean;
	memoryEnabled: boolean;
	model: string;
	provider: string;
	providerModels: string[];
	setEnabledSources: (value: string[]) => void;
	setFastMode: (value: boolean) => void;
	setMemoryEnabled: (value: boolean) => void;
	setModel: (value: string) => void;
	setProvider: (value: string) => void;
	setTemperature: (value: number) => void;
	setYearMax: (value: number) => void;
	setYearMin: (value: number) => void;
	temperature: number;
	toggleSource: (source: SourceConfig) => void;
	yearMax: number;
	yearMin: number;
}

export default function SearchSidebar({
	configError,
	providers,
	configSources,
	currentYear,
	disabled,
	enabledSources,
	fastMode,
	loadingConfig,
	memoryEnabled,
	model,
	provider,
	providerModels,
	setEnabledSources,
	setFastMode,
	setMemoryEnabled,
	setModel,
	setProvider,
	setTemperature,
	setYearMax,
	setYearMin,
	temperature,
	toggleSource,
	yearMax,
	yearMin,
}: SearchSidebarProps) {
	return (
		<div className="space-y-5">
			<section className="rounded-[1.75rem] border border-stone-200 bg-white p-6 shadow-[0_18px_48px_rgba(15,23,42,0.06)]">
				<p className="text-xs font-semibold uppercase tracking-[0.3em] text-stone-500">
					Search setup
				</p>
				<h2 className="mt-3 font-['Trebuchet_MS','Avenir_Next',sans-serif] text-2xl font-semibold tracking-[-0.03em] text-stone-950">
					Build a stronger literature scan
				</h2>
				<p className="mt-2 text-sm leading-7 text-stone-600">
					Choose the model, tune the search window, and define the data sources
					before the research pipeline starts.
				</p>

				{configError ? (
					<div className="mt-5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
						{configError}
					</div>
				) : null}

				<div className="mt-6 space-y-5">
					<FormSection
						title="AI model"
						description="Pick the provider and model that should drive planning and synthesis."
					>
						<div className="grid gap-4">
							<label className="block">
								<span className="mb-2 block text-xs font-semibold uppercase tracking-[0.22em] text-stone-500">
									Provider
								</span>
								<select
									value={provider}
									onChange={(event) => setProvider(event.target.value)}
									className={fieldClassName}
									disabled={disabled || loadingConfig}
								>
									{providers.map((item) => (
										<option key={item} value={item}>
											{PROVIDER_LABELS[item] || item}
										</option>
									))}
								</select>
							</label>

							<label className="block">
								<span className="mb-2 block text-xs font-semibold uppercase tracking-[0.22em] text-stone-500">
									Model
								</span>
								<select
									value={model}
									onChange={(event) => setModel(event.target.value)}
									className={fieldClassName}
									disabled={disabled || loadingConfig}
								>
									{providerModels.length === 0 ? (
										<option value="">Loading models...</option>
									) : null}
									{providerModels.map((item) => (
										<option key={item} value={item}>
											{item}
										</option>
									))}
								</select>
							</label>
						</div>
					</FormSection>

					<FormSection
						title="Research behavior"
						description="Control memory usage, response speed, and model creativity."
					>
						<div className="space-y-4">
							<label className="flex items-start gap-3 rounded-2xl bg-white px-4 py-4">
								<input
									type="checkbox"
									checked={memoryEnabled}
									onChange={(event) => setMemoryEnabled(event.target.checked)}
									disabled={disabled}
									className="mt-1 h-4 w-4 rounded border-stone-300 text-stone-950 focus:ring-sky-400"
								/>
								<span>
									<span className="block font-medium text-stone-900">
										Enable research memory
									</span>
									<span className="mt-1 block text-sm text-stone-600">
										Reuse memory context for longer-lived topic exploration.
									</span>
								</span>
							</label>

							<label className="flex items-start gap-3 rounded-2xl bg-white px-4 py-4">
								<input
									type="checkbox"
									checked={fastMode}
									onChange={(event) => setFastMode(event.target.checked)}
									disabled={disabled}
									className="mt-1 h-4 w-4 rounded border-stone-300 text-stone-950 focus:ring-sky-400"
								/>
								<span>
									<span className="block font-medium text-stone-900">
										{fastMode ? "Fast mode" : "Full mode"}
									</span>
									<span className="mt-1 block text-sm text-stone-600">
										{fastMode
											? "Lower latency with a 12 second timeout."
											: "Deeper retrieval with a 50 second timeout."}
									</span>
								</span>
							</label>

							<div className="rounded-2xl bg-white px-4 py-4">
								<div className="flex items-center justify-between gap-3">
									<span className="text-sm font-medium text-stone-900">
										Temperature
									</span>
									<span className="rounded-full bg-stone-100 px-3 py-1 text-sm font-medium text-stone-700">
										{temperature.toFixed(2)}
									</span>
								</div>
								<input
									type="range"
									min={0}
									max={1}
									step={0.05}
									value={temperature}
									onChange={(event) => setTemperature(Number(event.target.value))}
									disabled={disabled}
									className="mt-4 w-full accent-stone-950"
								/>
							</div>
						</div>
					</FormSection>

					<FormSection
						title="Sources"
						description="Choose which data providers should be queried."
						actions={
							<>
								<button
									type="button"
									onClick={() =>
										setEnabledSources(configSources.map((source) => source.key))
									}
									disabled={disabled || loadingConfig}
									className="rounded-full border border-stone-200 bg-white px-4 py-2 text-sm font-semibold text-stone-700 transition hover:border-sky-300 hover:bg-sky-50 disabled:opacity-50"
								>
									Select all
								</button>
								<button
									type="button"
									onClick={() => setEnabledSources([])}
									disabled={disabled || loadingConfig}
									className="rounded-full border border-stone-200 bg-white px-4 py-2 text-sm font-semibold text-stone-700 transition hover:border-sky-300 hover:bg-sky-50 disabled:opacity-50"
								>
									Clear
								</button>
							</>
						}
					>
						<div className="grid gap-3 sm:grid-cols-2">
							{configSources.map((source) => {
								const active = enabledSources.includes(source.key);
								return (
									<label
										key={source.key}
										className={`flex cursor-pointer items-start gap-3 rounded-2xl border px-4 py-4 transition ${
											active
												? "border-sky-300 bg-white"
												: "border-transparent bg-white/70 hover:border-stone-200"
										}`}
									>
										<input
											type="checkbox"
											checked={active}
											onChange={() => toggleSource(source)}
											disabled={disabled}
											className="mt-1 h-4 w-4 rounded border-stone-300 text-stone-950 focus:ring-sky-400"
										/>
										<span className="font-medium text-stone-800">
											{source.label}
										</span>
									</label>
								);
							})}
						</div>
						{enabledSources.length === 0 ? (
							<p className="text-sm text-amber-700">Select at least one source.</p>
						) : null}
					</FormSection>

					<FormSection
						title="Publication window"
						description="Limit the search to a specific year range."
					>
						<div className="grid gap-4 sm:grid-cols-2">
							<label className="block">
								<span className="mb-2 block text-xs font-semibold uppercase tracking-[0.22em] text-stone-500">
									From
								</span>
								<input
									type="number"
									min={1990}
									max={currentYear}
									value={yearMin}
									onChange={(event) => setYearMin(Number(event.target.value))}
									disabled={disabled}
									className={fieldClassName}
								/>
							</label>
							<label className="block">
								<span className="mb-2 block text-xs font-semibold uppercase tracking-[0.22em] text-stone-500">
									To
								</span>
								<input
									type="number"
									min={1990}
									max={currentYear}
									value={yearMax}
									onChange={(event) => setYearMax(Number(event.target.value))}
									disabled={disabled}
									className={fieldClassName}
								/>
							</label>
						</div>
					</FormSection>
				</div>
			</section>
		</div>
	);
}
