import type { ReactNode } from "react";

interface FormSectionProps {
	title: string;
	description?: string;
	actions?: ReactNode;
	children: ReactNode;
}

export default function FormSection({
	title,
	description,
	actions,
	children,
}: FormSectionProps) {
	return (
		<section className="space-y-4 rounded-[1.5rem] border border-stone-200 bg-stone-50 p-5">
			<div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
				<div>
					<h3 className="text-base font-semibold text-stone-950">{title}</h3>
					{description ? (
						<p className="mt-1 text-sm leading-6 text-stone-600">{description}</p>
					) : null}
				</div>
				{actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
			</div>
			{children}
		</section>
	);
}
