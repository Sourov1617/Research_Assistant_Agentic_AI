interface AnalysisTabProps {
	query?: string;
	searchPlan?: Record<string, unknown>;
	parsedIntent: Record<string, unknown>;
}

function safeJsonString(data: unknown) {
	try {
		return JSON.stringify(data, null, 2);
	} catch {
		return "{}";
	}
}

export default function AnalysisTab({
	query,
	searchPlan,
	parsedIntent,
}: AnalysisTabProps) {
	if (Object.keys(parsedIntent).length === 0) {
		return (
			<div className="rounded-[1.75rem] border border-dashed border-stone-300 bg-white px-6 py-10 text-center text-stone-500">
				No query analysis available yet.
			</div>
		);
	}

	return (
		<section className="rounded-[1.75rem] border border-stone-200 bg-white p-6 shadow-[0_18px_48px_rgba(15,23,42,0.06)]">
			<div className="space-y-6">
				<div>
					<h4 className="text-lg font-semibold text-stone-950">Original query</h4>
					<p className="mt-3 rounded-[1.25rem] bg-stone-50 px-4 py-4 text-sm leading-7 text-stone-700">
						{query || "-"}
					</p>
				</div>
				{searchPlan ? (
					<div>
						<h4 className="text-lg font-semibold text-stone-950">Search plan</h4>
						<pre className="mt-3 overflow-auto rounded-[1.25rem] bg-stone-950 p-4 text-sm leading-6 text-stone-100">
							{safeJsonString(searchPlan)}
						</pre>
					</div>
				) : null}
				<div>
					<h4 className="text-lg font-semibold text-stone-950">Parsed intent</h4>
					<pre className="mt-3 overflow-auto rounded-[1.25rem] bg-stone-950 p-4 text-sm leading-6 text-stone-100">
						{safeJsonString(parsedIntent)}
					</pre>
				</div>
			</div>
		</section>
	);
}
