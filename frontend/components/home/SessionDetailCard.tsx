import { formatTime } from "../../lib/research";
import type { MemorySessionDetail } from "../../lib/types";

interface SessionDetailCardProps {
	sessionDetail: MemorySessionDetail;
	title: string;
	onDelete: (sessionId: string) => void;
	isDeleting?: boolean;
}

export default function SessionDetailCard({
	sessionDetail,
	title,
	onDelete,
	isDeleting = false,
}: SessionDetailCardProps) {
	return (
		<section className="rounded-[1.9rem] border border-stone-200 bg-white p-6 shadow-[0_24px_70px_rgba(15,23,42,0.06)]">
			<div className="flex flex-wrap items-center justify-between gap-3">
				<p className="text-xs font-semibold uppercase tracking-[0.3em] text-stone-500">
					Selected memory session
				</p>
				<button
					type="button"
					onClick={() => onDelete(sessionDetail.session.session_id)}
					disabled={isDeleting}
					className="rounded-full border border-rose-200 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-rose-700 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
				>
					{isDeleting ? "Deleting..." : "Delete memory session"}
				</button>
			</div>
			<div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
				<div>
					<h3 className="text-xl font-semibold tracking-[-0.03em] text-stone-950">
						{title}
					</h3>
					<p className="mt-2 text-sm text-stone-600">
						Updated {formatTime(sessionDetail.session.updated_at)}
					</p>
				</div>
				<div className="grid grid-cols-3 gap-3">
					<div className="rounded-2xl bg-stone-50 px-4 py-3 text-center">
						<p className="text-2xl font-semibold text-stone-950">
							{sessionDetail.messages.length}
						</p>
						<p className="text-xs uppercase tracking-[0.18em] text-stone-500">
							Messages
						</p>
					</div>
					<div className="rounded-2xl bg-stone-50 px-4 py-3 text-center">
						<p className="text-2xl font-semibold text-stone-950">
							{sessionDetail.papers.length}
						</p>
						<p className="text-xs uppercase tracking-[0.18em] text-stone-500">
							Papers
						</p>
					</div>
					<div className="rounded-2xl bg-stone-50 px-4 py-3 text-center">
						<p className="text-2xl font-semibold text-stone-950">
							{sessionDetail.insights.length}
						</p>
						<p className="text-xs uppercase tracking-[0.18em] text-stone-500">
							Insights
						</p>
					</div>
				</div>
			</div>
		</section>
	);
}
