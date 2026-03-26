import { formatTime } from "../../lib/research";
import type { MemorySessionSummary } from "../../lib/types";

interface SessionListCardProps {
	sessions: MemorySessionSummary[];
	onSelect: (sessionId: string) => void;
	onDelete: (sessionId: string) => void;
	onClearRecent: () => void;
	activeSessionId?: string | null;
	isDeletingSessionId?: string | null;
}

export default function SessionListCard({
	sessions,
	onSelect,
	onDelete,
	onClearRecent,
	activeSessionId,
	isDeletingSessionId,
}: SessionListCardProps) {
	return (
		<section className="rounded-[1.75rem] border border-stone-200 bg-white p-5 shadow-[0_18px_48px_rgba(15,23,42,0.06)]">
			<div className="flex items-center justify-between gap-3">
				<div>
					<p className="text-xs font-semibold uppercase tracking-[0.28em] text-stone-500">
						Memory sessions
					</p>
					<p className="mt-1 text-xs text-stone-500">
						Clear recent workspace state or delete saved memory sessions.
					</p>
				</div>
				<div className="flex items-center gap-2">
					<span className="rounded-full bg-stone-100 px-3 py-1 text-xs font-medium text-stone-600">
						{sessions.length}
					</span>
					<button
						type="button"
						onClick={onClearRecent}
						className="rounded-full border border-stone-300 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-stone-700 transition hover:bg-stone-50"
					>
						Clear recent
					</button>
				</div>
			</div>
			<div className="mt-4 space-y-3">
				{sessions.length === 0 ? (
					<div className="rounded-2xl border border-dashed border-stone-200 bg-stone-50 px-4 py-5 text-sm text-stone-500">
						No saved sessions yet.
					</div>
				) : (
					sessions.slice(0, 6).map((session) => (
						<div
							key={session.session_id}
							className={`rounded-2xl border px-4 py-3 transition ${
								activeSessionId === session.session_id
									? "border-sky-300 bg-sky-50"
									: "border-stone-200 bg-stone-50"
							}`}
						>
							<div className="flex items-start justify-between gap-3">
								<button
									type="button"
									onClick={() => onSelect(session.session_id)}
									className="min-w-0 flex-1 text-left"
								>
									<p className="font-medium text-stone-950">{session.title}</p>
									<p className="mt-1 text-xs uppercase tracking-[0.18em] text-stone-400">
										Updated
									</p>
									<p className="mt-1 text-sm text-stone-600">
										{formatTime(session.updated_at)}
									</p>
								</button>
								<button
									type="button"
									onClick={() => onDelete(session.session_id)}
									disabled={isDeletingSessionId === session.session_id}
									className="shrink-0 rounded-full border border-rose-200 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-rose-700 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
								>
									{isDeletingSessionId === session.session_id ? "Deleting..." : "Delete"}
								</button>
							</div>
						</div>
					))
				)}
			</div>
		</section>
	);
}
