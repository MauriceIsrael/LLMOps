<script lang="ts">
	import { onMount } from 'svelte';
	import RefreshCw from 'lucide-svelte/icons/refresh-cw';
	import Inbox from 'lucide-svelte/icons/inbox';
	import Check from 'lucide-svelte/icons/check';
	import PenLine from 'lucide-svelte/icons/pen-line';
	import XCircle from 'lucide-svelte/icons/x-circle';
	import { lineDiff, type DiffLine } from '$lib/line-diff';

	/** KB candidate (schemas/kb_candidate.schema.json). */
	interface CandidateCheck {
		name: string;
		status: 'pass' | 'fail' | 'warn';
		detail: string;
	}
	interface CandidateReview {
		reviewer: string;
		action: 'accept' | 'amend' | 'reject';
		reason: string | null;
		at: string;
	}
	interface Candidate {
		id: string;
		kind: 'new_asset' | 'amendment' | 'rex' | 'framework_ingestion';
		target_asset_id: string | null;
		asset_type: string | null;
		domain: string[];
		title: string;
		rationale: string;
		proposed_content: string;
		source: { system: string; engagement?: string | null; author?: string | null; production_mode: string };
		evidence: Array<{ kind: string; ref: string }>;
		status: 'proposed' | 'checks_failed' | 'in_review' | 'accepted' | 'rejected' | 'published';
		checks: CandidateCheck[];
		review: CandidateReview | null;
		second_review_required: boolean;
		second_review: CandidateReview | null;
		assigned_owner: string | null;
		history: Array<{ at: string; actor: string; event: string }>;
		created_at: string;
		updated_at: string;
	}

	let { data } = $props();

	const STATUSES = ['in_review', 'checks_failed', 'accepted', 'published', 'rejected'] as const;
	const STATUS_LABELS: Record<string, string> = {
		proposed: 'Proposé',
		in_review: 'En revue',
		checks_failed: 'Contrôles échoués',
		accepted: 'Accepté',
		published: 'Publié',
		rejected: 'Rejeté'
	};
	const STATUS_STYLES: Record<string, string> = {
		in_review: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
		checks_failed: 'bg-red-500/15 text-red-300 border-red-500/30',
		accepted: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
		published: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
		rejected: 'bg-slate-700/40 text-slate-400 border-slate-600/40',
		proposed: 'bg-slate-700/40 text-slate-300 border-slate-600/40'
	};
	const CHECK_STYLES: Record<string, string> = {
		pass: 'text-emerald-400',
		warn: 'text-amber-400',
		fail: 'text-red-400'
	};

	let candidates = $state<Candidate[]>([]);
	let loading = $state(true);
	let loadError = $state<string | null>(null);
	let statusFilter = $state<string>('in_review');
	let sourceFilter = $state<string>('');
	let domainFilter = $state<string>('');
	let selectedId = $state<string | null>(null);
	let targetContent = $state<string | null>(null);

	let reviewer = $state<string>((data?.session?.user?.attributes?.kb_owner_handle as string) || '');
	let reason = $state('');
	let amendedContent = $state('');
	let showAmend = $state(false);
	let actionInProgress = $state(false);
	let actionMessage = $state<{ ok: boolean; text: string } | null>(null);

	const selected = $derived(candidates.find((c) => c.id === selectedId) || null);
	const canReview = $derived(
		!!selected && (selected.status === 'in_review' || selected.status === 'checks_failed')
	);
	const diff = $derived<DiffLine[]>(
		selected && selected.kind === 'amendment' && targetContent !== null
			? lineDiff(targetContent, selected.proposed_content)
			: []
	);

	async function loadCandidates() {
		loading = true;
		loadError = null;
		try {
			const params = new URLSearchParams();
			if (statusFilter) params.set('status', statusFilter);
			if (sourceFilter) params.set('source', sourceFilter);
			if (domainFilter.trim()) params.set('domain', domainFilter.trim());
			const res = await fetch(`/api/kb/candidates?${params.toString()}`);
			const json = await res.json();
			if (!res.ok || json.status !== 'ok') {
				loadError = json.reason || `Erreur ${res.status}`;
				candidates = [];
				return;
			}
			candidates = json.data || [];
			if (!candidates.some((c) => c.id === selectedId)) {
				selectedId = candidates[0]?.id ?? null;
			}
		} catch (e: any) {
			loadError = e?.message || String(e);
		} finally {
			loading = false;
		}
	}

	async function loadTarget(candidate: Candidate | null) {
		targetContent = null;
		if (!candidate || candidate.kind !== 'amendment' || !candidate.target_asset_id) return;
		try {
			const res = await fetch(`/api/kb/asset?id=${encodeURIComponent(candidate.target_asset_id)}`);
			if (res.ok) {
				const json = await res.json();
				const fm = json.data?.frontmatter;
				const body = json.data?.body ?? '';
				targetContent = fm ? `---\n${toYaml(fm)}---\n\n${body}` : body;
			}
		} catch {
			targetContent = null;
		}
	}

	function toYaml(fm: Record<string, unknown>): string {
		return Object.entries(fm)
			.map(([k, v]) => `${k}: ${Array.isArray(v) ? `[${v.join(', ')}]` : typeof v === 'object' ? JSON.stringify(v) : v}`)
			.join('\n') + '\n';
	}

	function select(id: string) {
		selectedId = id;
		actionMessage = null;
		reason = '';
		showAmend = false;
		const c = candidates.find((x) => x.id === id) || null;
		amendedContent = c?.proposed_content ?? '';
		loadTarget(c);
	}

	async function review(action: 'accept' | 'amend' | 'reject') {
		if (!selected) return;
		if (!reviewer.trim()) {
			actionMessage = { ok: false, text: 'Indiquez votre handle de propriétaire (ex. @core-owner-architecture).' };
			return;
		}
		if (!reason.trim()) {
			actionMessage = { ok: false, text: 'Le motif est obligatoire.' };
			return;
		}
		actionInProgress = true;
		actionMessage = null;
		try {
			const res = await fetch(`/api/kb/candidates/${encodeURIComponent(selected.id)}`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					action,
					reviewer: reviewer.trim(),
					reason: reason.trim(),
					amended_content: action === 'amend' ? amendedContent : undefined
				})
			});
			const json = await res.json();
			if (res.ok && json.status === 'ok') {
				const updated: Candidate = json.data;
				candidates = candidates.map((c) => (c.id === updated.id ? updated : c));
				actionMessage = { ok: true, text: `${updated.id} : ${STATUS_LABELS[updated.status] ?? updated.status}.` };
				reason = '';
				showAmend = false;
			} else {
				actionMessage = { ok: false, text: json.reason || `Erreur ${res.status}` };
			}
		} catch (e: any) {
			actionMessage = { ok: false, text: e?.message || String(e) };
		} finally {
			actionInProgress = false;
		}
	}

	onMount(async () => {
		await loadCandidates();
		if (selectedId) select(selectedId);
	});
</script>

<div class="min-h-screen bg-slate-950 text-slate-100 p-6 flex flex-col gap-6 font-sans">
	<div class="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
		<div>
			<div class="flex items-center gap-3">
				<div class="p-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
					<Inbox class="w-6 h-6" />
				</div>
				<h1 class="text-2xl font-bold tracking-tight text-white">Candidats d'enrichissement de la base</h1>
			</div>
			<p class="text-sm text-slate-400 mt-1">
				File de revue : contrôles automatiques, décision du propriétaire du domaine (seconde revue pour un principe
				ou un <code>supersedes</code>), puis promotion et publication par <code>kb promote</code> / <code>kb publish</code>.
			</p>
		</div>
		<button
			onclick={loadCandidates}
			class="flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
			disabled={loading}
		>
			<RefreshCw class="w-3.5 h-3.5 {loading ? 'animate-spin' : ''}" />
			Actualiser
		</button>
	</div>

	<!-- Filters -->
	<div class="flex flex-wrap items-end gap-3 text-sm">
		<div class="flex flex-wrap gap-2">
			<button
				onclick={() => { statusFilter = ''; loadCandidates(); }}
				class="px-3 py-1.5 rounded-lg font-medium border {statusFilter === '' ? 'bg-slate-800 text-white border-slate-700' : 'text-slate-400 border-transparent hover:text-slate-200'}"
			>Tous</button>
			{#each STATUSES as s (s)}
				<button
					onclick={() => { statusFilter = s; loadCandidates(); }}
					class="px-3 py-1.5 rounded-lg font-medium border {statusFilter === s ? STATUS_STYLES[s] : 'text-slate-400 border-transparent hover:text-slate-200'}"
				>{STATUS_LABELS[s]}</button>
			{/each}
		</div>
		<label class="flex flex-col gap-1 text-xs text-slate-400">
			Source
			<select bind:value={sourceFilter} onchange={loadCandidates} class="bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-slate-200">
				<option value="">Toutes</option>
				<option value="archinex">archinex</option>
				<option value="document-studio">document-studio</option>
				<option value="mcp">mcp</option>
				<option value="cli-ingestion">cli-ingestion</option>
			</select>
		</label>
		<label class="flex flex-col gap-1 text-xs text-slate-400">
			Domaine
			<input
				bind:value={domainFilter}
				onchange={loadCandidates}
				placeholder="ex. network-automation"
				class="bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-slate-200"
			/>
		</label>
	</div>

	{#if loadError}
		<div class="p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-red-300 text-sm">{loadError}</div>
	{/if}

	<div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
		<!-- List -->
		<div class="lg:col-span-4 flex flex-col gap-2">
			{#if !loading && candidates.length === 0}
				<p class="text-sm text-slate-500 p-4 border border-dashed border-slate-800 rounded-xl">Aucun candidat.</p>
			{/if}
			{#each candidates as c (c.id)}
				<button
					onclick={() => select(c.id)}
					class="text-left p-3 rounded-xl border transition {selectedId === c.id ? 'bg-slate-800/80 border-slate-600' : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'}"
				>
					<div class="flex items-center justify-between gap-2">
						<span class="font-mono text-xs text-slate-400">{c.id}</span>
						<span class="text-[11px] px-2 py-0.5 rounded-full border {STATUS_STYLES[c.status]}">{STATUS_LABELS[c.status]}</span>
					</div>
					<div class="mt-1 font-medium text-slate-100">{c.title}</div>
					<div class="mt-1 text-xs text-slate-400">
						{c.kind}{c.asset_type ? ` · ${c.asset_type}` : ''}{c.target_asset_id ? ` → ${c.target_asset_id}` : ''}
						· {c.assigned_owner ?? 'non assigné'}
					</div>
				</button>
			{/each}
		</div>

		<!-- Detail -->
		<div class="lg:col-span-8 flex flex-col gap-4">
			{#if selected}
				<div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col gap-2">
					<div class="flex flex-wrap items-center gap-2">
						<h2 class="text-lg font-semibold text-white">{selected.title}</h2>
						<span class="text-[11px] px-2 py-0.5 rounded-full border {STATUS_STYLES[selected.status]}">{STATUS_LABELS[selected.status]}</span>
						{#if selected.second_review_required}
							<span class="text-[11px] px-2 py-0.5 rounded-full border border-violet-500/30 bg-violet-500/10 text-violet-300">Seconde revue requise</span>
						{/if}
					</div>
					<dl class="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs text-slate-400">
						<div><dt>Type</dt><dd class="text-slate-200">{selected.kind} · {selected.asset_type ?? 'n/a'}</dd></div>
						<div><dt>Domaines</dt><dd class="text-slate-200">{selected.domain.join(', ') || 'n/a'}</dd></div>
						<div><dt>Source</dt><dd class="text-slate-200">{selected.source.system}{selected.source.engagement ? ` · ${selected.source.engagement}` : ''}</dd></div>
						<div><dt>Production</dt><dd class="text-slate-200">{selected.source.production_mode}</dd></div>
						<div><dt>Propriétaire</dt><dd class="text-slate-200">{selected.assigned_owner ?? 'n/a'}</dd></div>
						<div><dt>Preuves</dt><dd class="text-slate-200">{selected.evidence.map((e) => `${e.kind}:${e.ref}`).join(', ') || 'aucune'}</dd></div>
						<div><dt>Revue</dt><dd class="text-slate-200">{selected.review ? `${selected.review.action} par ${selected.review.reviewer}` : '—'}</dd></div>
						<div><dt>Seconde revue</dt><dd class="text-slate-200">{selected.second_review ? `${selected.second_review.action} par ${selected.second_review.reviewer}` : '—'}</dd></div>
					</dl>
					{#if selected.rationale}
						<p class="text-sm text-slate-300 whitespace-pre-wrap">{selected.rationale}</p>
					{/if}
				</div>

				<!-- Checks -->
				<div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
					<h3 class="text-sm font-semibold text-slate-200 mb-2">Contrôles automatiques</h3>
					<table class="w-full text-xs">
						<tbody>
							{#each selected.checks as check (check.name)}
								<tr class="border-t border-slate-800">
									<td class="py-1.5 pr-3 font-mono text-slate-300">{check.name}</td>
									<td class="py-1.5 pr-3 font-semibold uppercase {CHECK_STYLES[check.status]}">{check.status}</td>
									<td class="py-1.5 text-slate-400">{check.detail}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

				<!-- Content or diff -->
				<div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
					<h3 class="text-sm font-semibold text-slate-200 mb-2">
						{selected.kind === 'amendment' && diff.length ? `Différences avec ${selected.target_asset_id}` : 'Contenu proposé'}
					</h3>
					{#if selected.kind === 'amendment' && diff.length}
						<pre class="text-xs overflow-x-auto leading-5">{#each diff as line, i (i)}<span class="block {line.kind === 'added' ? 'bg-emerald-500/10 text-emerald-300' : line.kind === 'removed' ? 'bg-red-500/10 text-red-300 line-through' : 'text-slate-400'}">{line.kind === 'added' ? '+ ' : line.kind === 'removed' ? '- ' : '  '}{line.text}</span>{/each}</pre>
					{:else}
						<pre class="text-xs text-slate-300 whitespace-pre-wrap">{selected.proposed_content}</pre>
					{/if}
				</div>

				<!-- Review -->
				{#if canReview}
					<div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col gap-3">
						<h3 class="text-sm font-semibold text-slate-200">Revue</h3>
						<div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs text-slate-400">
							<label class="flex flex-col gap-1">
								Relecteur (handle déclaré dans owners.yaml)
								<input bind:value={reviewer} placeholder="@core-owner-architecture" class="bg-slate-950 border border-slate-700 rounded-lg px-2 py-1.5 text-slate-200" />
							</label>
							<label class="flex flex-col gap-1 md:col-span-2">
								Motif (obligatoire)
								<input bind:value={reason} placeholder="Motif de la décision ou exception motivée" class="bg-slate-950 border border-slate-700 rounded-lg px-2 py-1.5 text-slate-200" />
							</label>
						</div>
						{#if showAmend}
							<label class="flex flex-col gap-1 text-xs text-slate-400">
								Contenu amendé (front-matter + Markdown)
								<textarea bind:value={amendedContent} rows="14" class="font-mono bg-slate-950 border border-slate-700 rounded-lg p-2 text-slate-200"></textarea>
							</label>
						{/if}
						<div class="flex flex-wrap gap-2">
							{#if selected.status === 'in_review'}
								<button onclick={() => review('accept')} disabled={actionInProgress} class="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50">
									<Check class="w-3.5 h-3.5" /> Accepter
								</button>
							{/if}
							{#if !showAmend}
								<button onclick={() => (showAmend = true)} class="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-slate-700 hover:bg-slate-600 text-white">
									<PenLine class="w-3.5 h-3.5" /> Amender…
								</button>
							{:else}
								<button onclick={() => review('amend')} disabled={actionInProgress} class="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50">
									<PenLine class="w-3.5 h-3.5" /> Accepter le contenu amendé
								</button>
							{/if}
							<button onclick={() => review('reject')} disabled={actionInProgress} class="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-red-600/80 hover:bg-red-500 text-white disabled:opacity-50">
								<XCircle class="w-3.5 h-3.5" /> Rejeter
							</button>
						</div>
						{#if actionMessage}
							<p class="text-xs {actionMessage.ok ? 'text-emerald-300' : 'text-red-300'}">{actionMessage.text}</p>
						{/if}
					</div>
				{/if}

				<!-- History -->
				<div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
					<h3 class="text-sm font-semibold text-slate-200 mb-2">Historique</h3>
					<ul class="text-xs text-slate-400 flex flex-col gap-1">
						{#each selected.history as h, i (i)}
							<li><span class="font-mono text-slate-500">{h.at}</span> · {h.event} · {h.actor}</li>
						{/each}
					</ul>
				</div>
			{:else if !loading}
				<p class="text-sm text-slate-500">Sélectionnez un candidat.</p>
			{/if}
		</div>
	</div>
</div>
