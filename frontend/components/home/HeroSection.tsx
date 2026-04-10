interface HeroSectionProps {
	appTitle: string;
	activePaperCount: number;
	sessionCount: number;
}

export default function HeroSection({
	appTitle,
	activePaperCount,
	sessionCount,
}: HeroSectionProps) {
	return (
		<section className="relative overflow-hidden rounded-[2rem] border border-stone-200/80 bg-white/90 p-8 shadow-[0_30px_80px_rgba(15,23,42,0.08)]">
			<div className="absolute inset-x-0 top-0 h-24 bg-[radial-gradient(circle_at_top_left,_rgba(249,115,22,0.16),_transparent_42%),radial-gradient(circle_at_top_right,_rgba(14,165,233,0.16),_transparent_36%)]" />
			<div className="relative flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
				<div className="max-w-3xl space-y-4">
					<p className="text-xs font-semibold uppercase tracking-[0.35em] text-sky-700">
						Research workspace
					</p>
					<div className="space-y-3">
						<h1 className="font-['Trebuchet_MS','Avenir_Next',sans-serif] text-4xl font-semibold tracking-[-0.04em] text-stone-950 sm:text-5xl">
							{appTitle}
						</h1>
						<p className="max-w-2xl text-base leading-7 text-stone-600 sm:text-lg">
							A lighter, calmer dashboard for shaping literature reviews,
							tracking live pipeline progress, and revisiting research memory in
							one place.
						</p>
					</div>
				</div>

				<div className="grid grid-cols-2 gap-3 sm:gap-4">
					<div className="rounded-[1.5rem] border border-amber-200 bg-amber-50 px-5 py-4">
						<p className="text-3xl font-semibold tracking-[-0.04em] text-stone-950">
							{activePaperCount}
						</p>
						<p className="mt-1 text-xs font-medium uppercase tracking-[0.22em] text-stone-500">
							Papers in workspace
						</p>
					</div>
					<div className="rounded-[1.5rem] border border-sky-200 bg-sky-50 px-5 py-4">
						<p className="text-3xl font-semibold tracking-[-0.04em] text-stone-950">
							{sessionCount}
						</p>
						<p className="mt-1 text-xs font-medium uppercase tracking-[0.22em] text-stone-500">
							Memory sessions
						</p>
					</div>
				</div>
			</div>
		</section>
	);
}
