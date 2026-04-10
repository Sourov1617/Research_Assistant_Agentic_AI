import ConnectionCard from "../components/home/ConnectionCard";
import HeroSection from "../components/home/HeroSection";
import PipelineProgress from "../components/home/PipelineProgress";
import SessionDetailCard from "../components/home/SessionDetailCard";
import SessionListCard from "../components/home/SessionListCard";
import StatusCard from "../components/home/StatusCard";
import Results from "../components/Results";
import SearchQueryPanel from "../components/search/SearchQueryPanel";
import SearchSidebar from "../components/search/SearchSidebar";
import { useSearchForm } from "../hooks/useSearchForm";
import { useResearchWorkspace } from "../hooks/useResearchWorkspace";

export default function Home() {
	const {
		activePaperCount,
		activeSessionTitle,
		allPapers,
		appTitle,
		bootError,
		effectiveJobId,
		handleFetchMore,
		handleClearRecentSession,
		handleDeleteMemorySession,
		handleSessionSelect,
		handleStarted,
		handleStop,
		isFetchingMore,
		jobMeta,
		noMorePapers,
		sessionDetail,
		sessions,
		state,
		status,
		statusText,
		stepIndex,
		streamStatus,
		deletingSessionId,
	} = useResearchWorkspace();
	const searchDisabled = status === "running" || status === "stopping";
	const searchForm = useSearchForm({
		disabled: searchDisabled,
		onStarted: handleStarted,
	});

	return (
		<div className="min-h-screen bg-[linear-gradient(180deg,#fcfcfb_0%,#f7f1e8_45%,#eef6fb_100%)] text-stone-950">
			<div className="mx-auto flex max-w-[1500px] flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
				<HeroSection
					appTitle={appTitle}
					activePaperCount={activePaperCount}
					sessionCount={sessions.length}
				/>

				{bootError ? (
					<div className="rounded-[1.75rem] border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700 shadow-[0_18px_48px_rgba(15,23,42,0.05)]">
						{bootError}
					</div>
				) : null}

				<form
					onSubmit={searchForm.handleSubmit}
					className="grid gap-6 xl:grid-cols-[390px_minmax(0,1fr)]"
				>
					<aside className="space-y-5 xl:sticky xl:top-6 xl:self-start">
						<SearchSidebar
							configError={searchForm.configError}
							providers={searchForm.config?.providers || ["openrouter", "gemini", "groq"]}
							configSources={searchForm.config?.sources || []}
							currentYear={searchForm.currentYear}
							disabled={searchForm.disabled}
							enabledSources={searchForm.enabledSources}
							fastMode={searchForm.fastMode}
							loadingConfig={searchForm.loadingConfig}
							memoryEnabled={searchForm.memoryEnabled}
							model={searchForm.model}
							provider={searchForm.provider}
							providerModels={searchForm.providerModels}
							setEnabledSources={searchForm.setEnabledSources}
							setFastMode={searchForm.setFastMode}
							setMemoryEnabled={searchForm.setMemoryEnabled}
							setModel={searchForm.setModel}
							setProvider={searchForm.setProvider}
							setTemperature={searchForm.setTemperature}
							setYearMax={searchForm.setYearMax}
							setYearMin={searchForm.setYearMin}
							temperature={searchForm.temperature}
							toggleSource={searchForm.toggleSource}
							yearMax={searchForm.yearMax}
							yearMin={searchForm.yearMin}
						/>
						<ConnectionCard
							streamStatus={streamStatus}
							jobId={effectiveJobId}
							sessionId={state?.session_id}
						/>

						<SessionListCard
							sessions={sessions}
							onSelect={handleSessionSelect}
							onDelete={handleDeleteMemorySession}
							onClearRecent={handleClearRecentSession}
							activeSessionId={sessionDetail?.session.session_id}
							isDeletingSessionId={deletingSessionId}
						/>
					</aside>

					<main className="space-y-5">
						<StatusCard
							status={status}
							statusText={statusText}
							streamConnected={streamStatus === "connected"}
							jobMeta={jobMeta}
							state={state}
							effectiveJobId={effectiveJobId}
							onStop={handleStop}
						/>

						{status !== "idle" ? <PipelineProgress stepIndex={stepIndex} /> : null}

						{sessionDetail ? (
							<SessionDetailCard
								sessionDetail={sessionDetail}
								title={activeSessionTitle}
								onDelete={handleDeleteMemorySession}
								isDeleting={deletingSessionId === sessionDetail.session.session_id}
							/>
						) : null}

						<SearchQueryPanel
							canSubmit={searchForm.canSubmit}
							disabled={searchForm.disabled}
							maxChars={searchForm.maxChars}
							query={searchForm.query}
							setQuery={searchForm.setQuery}
							submitting={searchForm.submitting}
						/>

						<Results
							state={state}
							allPapers={allPapers}
							onFetchMore={handleFetchMore}
							isFetchingMore={isFetchingMore}
							noMorePapers={noMorePapers}
						/>
					</main>
				</form>
			</div>
		</div>
	);
}
