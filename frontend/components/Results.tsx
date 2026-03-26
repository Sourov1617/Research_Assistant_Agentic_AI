import { useMemo, useState } from "react";
import type { Paper, ResearchState } from "../lib/types";
import AnalysisTab from "./results/AnalysisTab";
import ExportTab from "./results/ExportTab";
import InsightsTab from "./results/InsightsTab";
import PapersTab from "./results/PapersTab";
import ResultTabs, { type ResultsTabId } from "./results/ResultTabs";

interface ResultsProps {
	state: ResearchState | null;
	allPapers: Paper[];
	onFetchMore: () => void;
	isFetchingMore: boolean;
	noMorePapers: boolean;
}

function normalizePaper(paper: Paper): Paper {
	const abstract = paper.abstract?.trim() || "";
	const synthesis = paper.synthesis || {};

	return {
		...paper,
		synthesis: {
			summary: synthesis.summary?.trim() || abstract || "No summary available.",
			methodology:
				synthesis.methodology?.trim() || "Not specified in abstract.",
			contribution:
				synthesis.contribution?.trim() || "Not specified in abstract.",
			limitations:
				synthesis.limitations?.trim() || "Not specified in abstract.",
			future_scope:
				synthesis.future_scope?.trim() || "Not specified in abstract.",
		},
	};
}

export default function Results({
	state,
	allPapers,
	onFetchMore,
	isFetchingMore,
	noMorePapers,
}: ResultsProps) {
	const [activeTab, setActiveTab] = useState<ResultsTabId>("papers");

	const papers = useMemo(
		() => (allPapers || []).map((paper) => normalizePaper(paper)),
		[allPapers],
	);
	const insights = (state?.insights || {}) as Record<string, unknown>;
	const parsedIntent = (state?.parsed_intent || {}) as Record<string, unknown>;
	const memorySuggestions = (state?.memory_suggestions || []) as string[];

	if (!state && papers.length === 0) {
		return (
			<div className="rounded-[1.9rem] border border-dashed border-stone-300 bg-white px-6 py-14 text-center text-stone-500 shadow-[0_18px_48px_rgba(15,23,42,0.04)]">
				Start a research query to see papers, synthesis sections, and insights.
			</div>
		);
	}

	return (
		<div className="space-y-5">
			<ResultTabs
				activeTab={activeTab}
				paperCount={papers.length}
				onChange={setActiveTab}
			/>

			{activeTab === "papers" ? (
				<PapersTab
					papers={papers}
					onFetchMore={onFetchMore}
					isFetchingMore={isFetchingMore}
					noMorePapers={noMorePapers}
				/>
			) : null}

			{activeTab === "insights" ? (
				<InsightsTab
					insights={insights}
					memorySuggestions={memorySuggestions}
				/>
			) : null}

			{activeTab === "analysis" ? (
				<AnalysisTab
					query={state?.query}
					searchPlan={state?.search_plan}
					parsedIntent={parsedIntent}
				/>
			) : null}

			{activeTab === "export" ? (
				<ExportTab
					state={state}
					papers={papers}
				/>
			) : null}
		</div>
	);
}
