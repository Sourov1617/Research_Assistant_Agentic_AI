const EXAMPLE_QUERIES = [
	"IoT-based sleep monitoring with CNN/LSTM hybrid and PSO/GWO optimizers for wearable edge devices",
	"Lightweight transformer models for real-time object detection on resource-constrained edge devices",
	"Federated learning for privacy-preserving medical imaging diagnosis using MRI and CT scans",
	"Large language models for automated code generation, testing, and bug-fix suggestions",
	"Multimodal deep learning for crop disease detection using drone NDVI imagery and IoT soil sensors",
];

const fieldClassName =
	"w-full rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm text-stone-900 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100";

interface SearchQueryPanelProps {
	canSubmit: boolean;
	disabled: boolean;
	maxChars: number;
	query: string;
	setQuery: (value: string) => void;
	submitting: boolean;
}

export default function SearchQueryPanel({
	canSubmit,
	disabled,
	maxChars,
	query,
	setQuery,
	submitting,
}: SearchQueryPanelProps) {
	return (
		<section className="rounded-[1.9rem] border border-stone-200 bg-white p-6 shadow-[0_24px_70px_rgba(15,23,42,0.06)]">
			<p className="text-xs font-semibold uppercase tracking-[0.3em] text-stone-500">
				Research query
			</p>
			<h3 className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-stone-950">
				Describe what you want to investigate
			</h3>
			<p className="mt-2 text-sm leading-7 text-stone-600">
				Write the topic, problem statement, keywords, or constraints for the
				research run. Example prompts are included below for quick starts.
			</p>

			<div className="mt-6 space-y-5">
				<details className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3">
					<summary className="cursor-pointer text-sm font-semibold text-stone-900">
						Example queries
					</summary>
					<div className="mt-4 flex flex-col gap-2">
						{EXAMPLE_QUERIES.map((item) => (
							<button
								type="button"
								key={item}
								onClick={() => setQuery(item)}
								disabled={disabled}
								className="rounded-2xl border border-stone-200 bg-white px-4 py-3 text-left text-sm leading-6 text-stone-700 transition hover:-translate-y-0.5 hover:border-sky-300 hover:bg-sky-50"
							>
								{item}
							</button>
						))}
					</div>
				</details>

				<div>
					<textarea
						value={query}
						onChange={(event) => setQuery(event.target.value)}
						rows={8}
						maxLength={maxChars}
						disabled={disabled}
						placeholder="Describe your research idea, problem, or keywords"
						className={`${fieldClassName} min-h-[220px] resize-y`}
					/>
					<div className="mt-2 flex items-center justify-end">
						<span className="text-xs font-medium text-stone-500">
							{query.length}/{maxChars}
						</span>
					</div>
				</div>

				<div className="flex justify-end">
					<button
						type="submit"
						disabled={!canSubmit}
						className="w-full rounded-full bg-stone-950 px-5 py-4 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto sm:min-w-56"
					>
						{submitting ? "Starting..." : "Start Research"}
					</button>
				</div>
			</div>
		</section>
	);
}
