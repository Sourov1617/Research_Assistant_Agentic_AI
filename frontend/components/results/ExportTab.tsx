import type { Paper, ResearchState } from "../../lib/types";

interface ExportTabProps {
	state: ResearchState | null;
	papers: Paper[];
}

function safeJsonString(data: unknown) {
	try {
		return JSON.stringify(data, null, 2);
	} catch {
		return "{}";
	}
}

function download(filename: string, content: string, type: string) {
	const blob = new Blob([content], { type });
	const url = URL.createObjectURL(blob);
	const link = document.createElement("a");
	link.href = url;
	link.download = filename;
	link.click();
	URL.revokeObjectURL(url);
}

export default function ExportTab({ state, papers }: ExportTabProps) {
	return (
		<section className="rounded-[1.75rem] border border-stone-200 bg-white p-6 shadow-[0_18px_48px_rgba(15,23,42,0.06)]">
			<h4 className="text-xl font-semibold tracking-[-0.03em] text-stone-950">
				Export research data
			</h4>
			<div className="mt-5 flex flex-wrap gap-3">
				<button
					type="button"
					onClick={() =>
						download(
							"research_data.json",
							safeJsonString({ state, papers }),
							"application/json",
						)
					}
					className="rounded-full bg-stone-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-stone-800"
				>
					Download JSON
				</button>
				<button
					type="button"
					onClick={() =>
						download(
							"research_report.md",
							`# Research Report\n\n## Query\n${state?.query || ""}\n\n## Papers\n${papers
								.map(
									(paper, index) => `${index + 1}. ${paper.title || "Untitled"}`,
								)
								.join("\n")}`,
							"text/markdown",
						)
					}
					className="rounded-full border border-stone-200 bg-stone-50 px-5 py-3 text-sm font-semibold text-stone-700 transition hover:border-sky-300 hover:bg-sky-50"
				>
					Download Markdown
				</button>
			</div>
			<pre className="mt-5 overflow-auto rounded-[1.25rem] bg-stone-950 p-4 text-sm leading-6 text-stone-100">
				{safeJsonString(state)}
			</pre>
		</section>
	);
}
