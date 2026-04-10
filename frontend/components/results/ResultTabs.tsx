const TABS = [
	{ id: "papers", label: "Papers" },
	{ id: "insights", label: "Research Insights" },
	{ id: "analysis", label: "Query Analysis" },
	{ id: "export", label: "Export / Raw" },
] as const;

export type ResultsTabId = (typeof TABS)[number]["id"];

interface ResultTabsProps {
	activeTab: ResultsTabId;
	paperCount: number;
	onChange: (tab: ResultsTabId) => void;
}

export default function ResultTabs({
	activeTab,
	paperCount,
	onChange,
}: ResultTabsProps) {
	return (
		<div className="flex flex-wrap gap-3">
			{TABS.map((tab) => {
				const label =
					tab.id === "papers" ? `${tab.label} (${paperCount})` : tab.label;
				const active = tab.id === activeTab;

				return (
					<button
						key={tab.id}
						type="button"
						onClick={() => onChange(tab.id)}
						className={`rounded-full px-5 py-2.5 text-sm font-semibold transition ${
							active
								? "bg-stone-950 text-white shadow-[0_10px_28px_rgba(15,23,42,0.15)]"
								: "border border-stone-200 bg-white text-stone-700 hover:-translate-y-0.5 hover:border-sky-300 hover:text-stone-950"
						}`}
					>
						{label}
					</button>
				);
			})}
		</div>
	);
}
