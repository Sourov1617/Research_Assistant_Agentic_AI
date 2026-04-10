interface ConnectionCardProps {
	streamStatus: "idle" | "connecting" | "connected" | "fallback";
	jobId: string | null;
	sessionId?: string | null;
}

export default function ConnectionCard({
	streamStatus,
	jobId,
	sessionId,
}: ConnectionCardProps) {
	const streamBadge =
		streamStatus === "connected"
			? { label: "Connected", className: "bg-emerald-100 text-emerald-800" }
			: streamStatus === "connecting"
				? { label: "Connecting", className: "bg-sky-100 text-sky-800" }
				: streamStatus === "fallback"
					? { label: "Fallback mode", className: "bg-amber-100 text-amber-800" }
					: { label: "Idle", className: "bg-stone-200 text-stone-700" };

	return (
		<section className="rounded-[1.75rem] border border-stone-200 bg-white p-5 shadow-[0_18px_48px_rgba(15,23,42,0.06)]">
			<p className="text-xs font-semibold uppercase tracking-[0.28em] text-stone-500">
				Connection
			</p>
			<div className="mt-4 space-y-3 text-sm text-stone-600">
				<div className="flex items-center justify-between gap-3 rounded-2xl bg-stone-50 px-4 py-3">
					<span>Backend stream</span>
					<span
						className={`rounded-full px-3 py-1 text-xs font-semibold ${streamBadge.className}`}
					>
						{streamBadge.label}
					</span>
				</div>
				<div className="rounded-2xl bg-stone-50 px-4 py-3">
					<p className="text-xs uppercase tracking-[0.18em] text-stone-400">
						Current job
					</p>
					<p className="mt-1 break-all font-medium text-stone-900">
						{jobId || "None"}
					</p>
				</div>
				{sessionId ? (
					<div className="rounded-2xl bg-stone-50 px-4 py-3">
						<p className="text-xs uppercase tracking-[0.18em] text-stone-400">
							Memory session
						</p>
						<p className="mt-1 break-all font-medium text-stone-900">
							{sessionId}
						</p>
					</div>
				) : null}
			</div>
		</section>
	);
}
