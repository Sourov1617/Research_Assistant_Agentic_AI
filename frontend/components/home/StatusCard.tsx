import type { JobStatusResponse, ResearchState, ResearchStatus } from "../../lib/types";

interface StatusCardProps {
	status: ResearchStatus;
	statusText: string;
	streamConnected: boolean;
	jobMeta: JobStatusResponse | null;
	state: ResearchState | null;
	effectiveJobId: string | null;
	onStop: () => void;
}

export default function StatusCard({
	status,
	statusText,
	streamConnected,
	jobMeta,
	state,
	effectiveJobId,
	onStop,
}: StatusCardProps) {
	return (
		<section className="rounded-[1.9rem] border border-stone-200 bg-white p-6 shadow-[0_24px_70px_rgba(15,23,42,0.06)]">
			<div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
				<div className="space-y-2">
					<p className="text-xs font-semibold uppercase tracking-[0.3em] text-stone-500">
						Pipeline status
					</p>
					<div className="flex items-center gap-3">
						<h2 className="text-2xl font-semibold capitalize tracking-[-0.03em] text-stone-950">
							{status}
						</h2>
						<span
							className={`rounded-full px-3 py-1 text-xs font-semibold ${
								streamConnected
									? "bg-sky-100 text-sky-800"
									: "bg-stone-100 text-stone-700"
							}`}
						>
							{streamConnected ? "Live stream" : "Snapshot mode"}
						</span>
					</div>
					<p className="max-w-3xl text-sm leading-6 text-stone-600">{statusText}</p>
				</div>

				{(status === "running" || status === "stopping") && effectiveJobId ? (
					<button
						type="button"
						onClick={onStop}
						className="rounded-full bg-stone-950 px-5 py-3 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-stone-800"
					>
						Stop research
					</button>
				) : null}
			</div>

			{jobMeta?.error || state?.error ? (
				<div className="mt-5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
					{jobMeta?.error || state?.error}
				</div>
			) : null}
		</section>
	);
}
