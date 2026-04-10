import type { Paper } from "../../lib/types";

const SYNTHESIS_SECTIONS = [
	{ key: "methodology", label: "Methodology", tone: "bg-sky-100 text-sky-700" },
	{ key: "contribution", label: "Key Contribution", tone: "bg-amber-100 text-amber-700" },
	{ key: "limitations", label: "Limitations", tone: "bg-rose-100 text-rose-700" },
	{ key: "future_scope", label: "Future Scope", tone: "bg-emerald-100 text-emerald-700" },
] as const;

interface PaperCardProps {
	paper: Paper;
	rank: number;
	isExpanded: boolean;
	onToggle: () => void;
}

export default function PaperCard({
	paper,
	rank,
	isExpanded,
	onToggle,
}: PaperCardProps) {
	const relevance = Number(paper.relevance_score || paper.similarity_score || 0);
	const relevanceScore = (relevance * 5).toFixed(1);
	const authors = Array.isArray(paper.authors)
		? paper.authors.slice(0, 5).join(", ")
		: paper.authors || "Unknown authors";

	return (
		<article className="rounded-[1.75rem] border border-stone-200 bg-white p-6 shadow-[0_18px_48px_rgba(15,23,42,0.06)]">
			<div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
				<div className="space-y-4">
					<div className="flex flex-wrap items-center gap-2">
						<span className="rounded-full bg-amber-100 px-3 py-1 text-sm font-semibold text-amber-800">
							#{rank}
						</span>
						<span className="rounded-full bg-stone-100 px-3 py-1 text-sm text-stone-700">
							{paper.source || "Unknown source"}
						</span>
						<span className="rounded-full bg-stone-100 px-3 py-1 text-sm text-stone-700">
							{paper.year || "N/A"}
						</span>
						<span className="rounded-full bg-sky-100 px-3 py-1 text-sm font-medium text-sky-800">
							Score {relevanceScore}/5
						</span>
					</div>

					<div className="space-y-3">
						<h4 className="text-2xl font-semibold tracking-[-0.03em] text-stone-950">
							{paper.title || "Untitled paper"}
						</h4>
						<p className="text-sm leading-6 text-stone-500">{authors}</p>
						<p className="text-sm leading-7 text-stone-700">
							{paper.synthesis?.summary || "No summary available."}
						</p>
					</div>
				</div>

				<button
					type="button"
					onClick={onToggle}
					className="rounded-full border border-stone-200 bg-stone-50 px-5 py-3 text-sm font-semibold text-stone-700 transition hover:-translate-y-0.5 hover:border-sky-300 hover:bg-sky-50 hover:text-stone-950"
				>
					{isExpanded ? "Hide synthesis" : "Open synthesis"}
				</button>
			</div>

			<div className="mt-5 flex flex-wrap gap-2 text-sm">
				{paper.url ? (
					<a
						href={paper.url}
						target="_blank"
						rel="noreferrer"
						className="rounded-full border border-stone-200 bg-stone-50 px-3 py-2 text-stone-700 transition hover:border-sky-300 hover:bg-sky-50"
					>
						View
					</a>
				) : null}
				{paper.pdf_url ? (
					<a
						href={paper.pdf_url}
						target="_blank"
						rel="noreferrer"
						className="rounded-full border border-stone-200 bg-stone-50 px-3 py-2 text-stone-700 transition hover:border-sky-300 hover:bg-sky-50"
					>
						PDF
					</a>
				) : null}
				{paper.doi ? (
					<span className="rounded-full border border-stone-200 bg-stone-50 px-3 py-2 text-stone-700">
						DOI: {paper.doi}
					</span>
				) : null}
				{typeof paper.citation_count === "number" ? (
					<span className="rounded-full border border-stone-200 bg-stone-50 px-3 py-2 text-stone-700">
						Citations: {paper.citation_count}
					</span>
				) : null}
			</div>

			{isExpanded ? (
				<div className="mt-6 border-t border-stone-200 pt-6">
					<div className="rounded-[1.5rem] bg-stone-50 p-5">
						<p className="text-xs font-semibold uppercase tracking-[0.24em] text-sky-700">
							Summary
						</p>
						<p className="mt-3 text-sm leading-7 text-stone-700">
							{paper.synthesis?.summary}
						</p>
					</div>
					<div className="mt-4 grid gap-4 md:grid-cols-2">
						{SYNTHESIS_SECTIONS.map((section) => (
							<section
								key={section.key}
								className="rounded-[1.5rem] border border-stone-200 bg-white p-5"
							>
								<span
									className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${section.tone}`}
								>
									{section.label}
								</span>
								<p className="mt-4 text-sm leading-7 text-stone-700">
									{paper.synthesis?.[section.key]}
								</p>
							</section>
						))}
					</div>
				</div>
			) : null}
		</article>
	);
}
