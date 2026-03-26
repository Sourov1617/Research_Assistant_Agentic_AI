import { PIPELINE_STEPS } from "../../lib/research";

interface PipelineProgressProps {
	stepIndex: number;
}

export default function PipelineProgress({
	stepIndex,
}: PipelineProgressProps) {
	return (
		<section className="rounded-[1.9rem] border border-stone-200 bg-white p-6 shadow-[0_24px_70px_rgba(15,23,42,0.06)]">
			<div className="mb-5 flex items-center justify-between gap-3">
				<div>
					<p className="text-xs font-semibold uppercase tracking-[0.3em] text-stone-500">
						Pipeline progress
					</p>
					<h3 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-stone-950">
						Research pipeline steps
					</h3>
				</div>
				<div className="rounded-full bg-amber-50 px-4 py-2 text-sm font-medium text-amber-800">
					{stepIndex > 0 ? `${stepIndex}/${PIPELINE_STEPS.length}` : "Waiting"}
				</div>
			</div>

			<div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
				{PIPELINE_STEPS.map((item, index) => {
					const done = index + 1 < stepIndex;
					const active = index + 1 === stepIndex;

					return (
						<div
							key={item}
							className={`rounded-[1.4rem] border px-4 py-4 ${
								active
									? "border-sky-300 bg-sky-50"
									: done
										? "border-emerald-200 bg-emerald-50"
										: "border-stone-200 bg-stone-50"
							}`}
						>
							<div className="mb-3 flex items-center justify-between gap-3">
								<span className="text-sm font-semibold text-stone-900">
									Step {index + 1}
								</span>
								<span
									className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${
										active
											? "bg-sky-100 text-sky-700"
											: done
												? "bg-emerald-100 text-emerald-700"
												: "bg-white text-stone-500"
									}`}
								>
									{active ? "Active" : done ? "Done" : "Waiting"}
								</span>
							</div>
							<p className="text-sm leading-6 text-stone-700">{item}</p>
						</div>
					);
				})}
			</div>
		</section>
	);
}
