interface InsightsTabProps {
	insights: Record<string, unknown>;
	memorySuggestions: string[];
}

export default function InsightsTab({
	insights,
	memorySuggestions,
}: InsightsTabProps) {
	const sections: Array<{ title: string; items?: string[] }> = [
		{ title: "Emerging Trends", items: insights.emerging_trends as string[] | undefined },
		{ title: "Research Gaps", items: insights.research_gaps as string[] | undefined },
		{
			title: "Common Challenges",
			items: insights.common_challenges as string[] | undefined,
		},
		{
			title: "Suggested Directions",
			items: insights.suggested_directions as string[] | undefined,
		},
		{ title: "Memory Suggestions", items: memorySuggestions },
	];

	if (Object.keys(insights).length === 0) {
		return (
			<div className="rounded-[1.75rem] border border-dashed border-stone-300 bg-white px-6 py-10 text-center text-stone-500">
				No insights available yet.
			</div>
		);
	}

	return (
		<section className="space-y-4 rounded-[1.75rem] border border-stone-200 bg-white p-6 shadow-[0_18px_48px_rgba(15,23,42,0.06)]">
			{typeof insights.overview === "string" ? (
				<div className="rounded-[1.5rem] border border-sky-200 bg-sky-50 px-5 py-4 text-sm leading-7 text-stone-700">
					{insights.overview}
				</div>
			) : null}

			<div className="grid gap-4 lg:grid-cols-2">
				{sections.map(({ title, items }) =>
					items && items.length > 0 ? (
						<section
							key={title}
							className="rounded-[1.5rem] border border-stone-200 bg-stone-50 p-5"
						>
							<h4 className="text-lg font-semibold text-stone-950">{title}</h4>
							<ul className="mt-4 space-y-3 text-sm leading-6 text-stone-700">
								{items.map((item) => (
									<li key={item} className="rounded-2xl bg-white px-4 py-3">
										{item}
									</li>
								))}
							</ul>
						</section>
					) : null,
				)}
			</div>
		</section>
	);
}
