import { useMemo, useState } from "react";
import type { Paper } from "../../lib/types";
import PaperCard from "./PaperCard";

interface PapersTabProps {
	papers: Paper[];
	onFetchMore: () => void;
	isFetchingMore: boolean;
	noMorePapers: boolean;
}

const PAGE_SIZE = 12;

function toggleValue(values: string[] | null, value: string, fallback: string[]) {
	const base = values ?? fallback;
	return base.includes(value)
		? base.filter((item) => item !== value)
		: [...base, value];
}

export default function PapersTab({
	papers,
	onFetchMore,
	isFetchingMore,
	noMorePapers,
}: PapersTabProps) {
	const [selectedSources, setSelectedSources] = useState<string[] | null>(null);
	const [sortBy, setSortBy] = useState<"relevance" | "year" | "citations">(
		"relevance",
	);
	const [yearMinFilter, setYearMinFilter] = useState<number | null>(null);
	const [yearMaxFilter, setYearMaxFilter] = useState<number | null>(null);
	const [page, setPage] = useState(0);
	const [expandedPaper, setExpandedPaper] = useState<string | null>(null);

	const availableSources = useMemo(
		() => Array.from(new Set(papers.map((paper) => paper.source || "Unknown"))).sort(),
		[papers],
	);
	const availableYears = useMemo(
		() =>
			papers
				.map((paper) => paper.year)
				.filter((year): year is number => typeof year === "number")
				.sort((a, b) => a - b),
		[papers],
	);

	const activeSources = selectedSources ?? availableSources;
	const activeYearMin =
		yearMinFilter ?? (availableYears.length ? availableYears[0] : null);
	const activeYearMax =
		yearMaxFilter ??
		(availableYears.length ? availableYears[availableYears.length - 1] : null);

	const filteredPapers = useMemo(() => {
		const filtered = papers.filter((paper) => {
			const source = paper.source || "Unknown";
			const sourceMatch =
				activeSources.length === 0 || activeSources.includes(source);
			const year = paper.year;
			const yearMatch =
				typeof year !== "number" ||
				((activeYearMin === null || year >= activeYearMin) &&
					(activeYearMax === null || year <= activeYearMax));
			return sourceMatch && yearMatch;
		});

		if (sortBy === "year") {
			filtered.sort((a, b) => (b.year || 0) - (a.year || 0));
		} else if (sortBy === "citations") {
			filtered.sort(
				(a, b) => (b.citation_count || 0) - (a.citation_count || 0),
			);
		}

		return filtered;
	}, [papers, activeSources, activeYearMin, activeYearMax, sortBy]);

	const totalPages = Math.max(1, Math.ceil(filteredPapers.length / PAGE_SIZE));
	const clampedPage = Math.min(page, totalPages - 1);
	const pagePapers = filteredPapers.slice(
		clampedPage * PAGE_SIZE,
		clampedPage * PAGE_SIZE + PAGE_SIZE,
	);
	const onLastPage = clampedPage >= totalPages - 1;
	const yearRangeLabel =
		availableYears.length > 0
			? `${availableYears[0]}-${availableYears[availableYears.length - 1]}`
			: "N/A";
	const avgCitations =
		papers.length === 0
			? "N/A"
			: `${Math.round(
					papers.reduce((sum, paper) => sum + (paper.citation_count || 0), 0) /
						papers.length,
				)}`;
	const coverageLabel = `${filteredPapers.length}/${papers.length}`;

	return (
		<div className="space-y-5">
			<div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
				<div className="rounded-[1.5rem] border border-amber-200 bg-amber-50 p-5">
					<p className="text-3xl font-semibold tracking-[-0.04em] text-stone-950">
						{papers.length}
					</p>
					<p className="mt-1 text-xs font-medium uppercase tracking-[0.2em] text-stone-500">
						Paper pool
					</p>
				</div>
				<div className="rounded-[1.5rem] border border-sky-200 bg-sky-50 p-5">
					<p className="text-3xl font-semibold tracking-[-0.04em] text-stone-950">
						{availableSources.length}
					</p>
					<p className="mt-1 text-xs font-medium uppercase tracking-[0.2em] text-stone-500">
						Sources
					</p>
				</div>
				<div className="rounded-[1.5rem] border border-emerald-200 bg-emerald-50 p-5">
					<p className="text-3xl font-semibold tracking-[-0.04em] text-stone-950">
						{yearRangeLabel}
					</p>
					<p className="mt-1 text-xs font-medium uppercase tracking-[0.2em] text-stone-500">
						Coverage
					</p>
				</div>
				<div className="rounded-[1.5rem] border border-rose-200 bg-rose-50 p-5">
					<p className="text-3xl font-semibold tracking-[-0.04em] text-stone-950">
						{avgCitations}
					</p>
					<p className="mt-1 text-xs font-medium uppercase tracking-[0.2em] text-stone-500">
						Avg citations
					</p>
				</div>
			</div>

			<section className="rounded-[1.75rem] border border-stone-200 bg-white p-6 shadow-[0_18px_48px_rgba(15,23,42,0.06)]">
				<div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
					<div>
						<h3 className="text-xl font-semibold tracking-[-0.03em] text-stone-950">
							Paper workspace
						</h3>
						<p className="mt-2 max-w-2xl text-sm leading-6 text-stone-600">
							Refine the result set, then open any paper to inspect its
							synthesis across methodology, contribution, limitations, and next
							steps.
						</p>
					</div>
					<div className="rounded-[1.25rem] bg-stone-50 px-4 py-3">
						<p className="text-2xl font-semibold tracking-[-0.03em] text-stone-950">
							{coverageLabel}
						</p>
						<p className="text-xs uppercase tracking-[0.18em] text-stone-500">
							Visible after filters
						</p>
					</div>
				</div>

				<div className="mt-6 grid gap-5 xl:grid-cols-[2fr_1.05fr_0.95fr]">
					<div>
						<label className="mb-3 block text-xs font-semibold uppercase tracking-[0.22em] text-stone-500">
							Filter by source
						</label>
						<div className="flex flex-wrap gap-2">
							{availableSources.map((source) => {
								const active = activeSources.includes(source);
								return (
									<button
										key={source}
										type="button"
										onClick={() => {
											setSelectedSources((prev) =>
												toggleValue(prev, source, availableSources),
											);
											setPage(0);
										}}
										className={`rounded-full px-4 py-2 text-sm font-medium transition ${
											active
												? "bg-stone-950 text-white"
												: "border border-stone-200 bg-stone-50 text-stone-700 hover:border-sky-300 hover:bg-sky-50"
										}`}
									>
										{source}
									</button>
								);
							})}
						</div>
					</div>

					<div>
						<label className="mb-3 block text-xs font-semibold uppercase tracking-[0.22em] text-stone-500">
							Year range
						</label>
						<div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
							<input
								type="number"
								value={activeYearMin ?? ""}
								onChange={(event) => {
									setYearMinFilter(Number(event.target.value) || null);
									setPage(0);
								}}
								className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm text-stone-900 outline-none transition focus:border-sky-400 focus:bg-white"
							/>
							<input
								type="number"
								value={activeYearMax ?? ""}
								onChange={(event) => {
									setYearMaxFilter(Number(event.target.value) || null);
									setPage(0);
								}}
								className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm text-stone-900 outline-none transition focus:border-sky-400 focus:bg-white"
							/>
						</div>
					</div>

					<div>
						<label className="mb-3 block text-xs font-semibold uppercase tracking-[0.22em] text-stone-500">
							Sort by
						</label>
						<select
							value={sortBy}
							onChange={(event) => {
								setSortBy(
									event.target.value as "relevance" | "year" | "citations",
								);
								setPage(0);
							}}
							className="w-full rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm text-stone-900 outline-none transition focus:border-sky-400 focus:bg-white"
						>
							<option value="relevance">Relevance</option>
							<option value="year">Year (newest)</option>
							<option value="citations">Citations</option>
						</select>
					</div>
				</div>
			</section>

			<div className="space-y-4">
				{pagePapers.map((paper, index) => {
					const rank = clampedPage * PAGE_SIZE + index + 1;
					const paperKey =
						(paper.url || paper.doi || paper.title || `paper-${rank}`) +
						`-${rank}`;

					return (
						<PaperCard
							key={paperKey}
							paper={paper}
							rank={rank}
							isExpanded={expandedPaper === paperKey}
							onToggle={() =>
								setExpandedPaper((prev) => (prev === paperKey ? null : paperKey))
							}
						/>
					);
				})}
			</div>

			<div className="flex flex-col gap-3 rounded-[1.5rem] border border-stone-200 bg-white px-5 py-4 shadow-[0_18px_48px_rgba(15,23,42,0.06)] sm:flex-row sm:items-center sm:justify-between">
				<button
					type="button"
					onClick={() => setPage((value) => Math.max(0, value - 1))}
					disabled={clampedPage === 0}
					className="rounded-full border border-stone-200 bg-stone-50 px-4 py-2.5 text-sm font-semibold text-stone-700 transition hover:border-sky-300 hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-50"
				>
					Previous
				</button>
				<p className="text-sm text-stone-600">
					Page {clampedPage + 1} of {totalPages}
				</p>
				{isFetchingMore ? (
					<p className="text-sm font-medium text-stone-600">
						Fetching more papers...
					</p>
				) : onLastPage ? (
					<button
						type="button"
						onClick={onFetchMore}
						disabled={noMorePapers}
						className="rounded-full bg-stone-950 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-50"
					>
						{noMorePapers ? "All results shown" : "Search more"}
					</button>
				) : (
					<button
						type="button"
						onClick={() => setPage((value) => value + 1)}
						className="rounded-full bg-stone-950 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-stone-800"
					>
						Next
					</button>
				)}
			</div>
		</div>
	);
}
