<script lang="ts">
	import { onMount } from 'svelte';

	/**
	 * Review of the question trigger rules (K22, Hub contract 1.25).
	 *
	 * A rule says "when these facts are asserted, this question becomes relevant". Rules reach the knowledge base only through
	 * the candidate cycle: a model proposes (llm-derived), a person accepts, amends or rejects, the maintainer promotes and
	 * publishes. Nothing here publishes anything by itself.
	 */
	type Problem = { path: string; code: string; reason: string };
	type Rule = {
		trigger_id: string;
		version: number;
		when: Array<{ key: string; op: string; value: unknown }>;
		question: { fr: string; en: string };
		mandatory: boolean;
		initial_level: string;
		suggested_role: string;
	};
	type AssetRules = { id: string; title: string; rules: Rule[] };
	type VocabKey = { key: string; type: string; values?: string[]; unit?: string; label: { fr: string; en: string } };
	type Candidate = {
		id: string;
		asset_type: 'trigger' | 'fact_key';
		status: string;
		title: string;
		kind: string;
		target_asset_id?: string | null;
		production_mode?: string | null;
		checks: Array<{ name: string; status: string; detail: string }>;
	};

	let assets = $state<AssetRules[]>([]);
	let vocabulary = $state<{ version: number; keys: VocabKey[] }>({ version: 0, keys: [] });
	let candidates = $state<Candidate[]>([]);
	let loading = $state(true);
	let loadError = $state<string | null>(null);

	let selected = $state<{ kind: 'rule' | 'candidate'; id: string } | null>(null);
	let content = $state('');
	let assetType = $state<'trigger' | 'fact_key'>('trigger');
	let targetAssetId = $state<string | null>(null);
	let problems = $state<Problem[]>([]);
	let valid = $state<boolean | null>(null);

	let factsText = $state('{\n  "topology.dc_count": 2,\n  "topology.mode": "active-active"\n}');
	let preview = $state<any | null>(null);
	let previewError = $state<string | null>(null);

	let reviewer = $state('');
	let reason = $state('');
	let message = $state<string | null>(null);
	let mergeInto = $state('');

	async function hub(path: string, method = 'GET', body?: unknown) {
		const res = await fetch(`/api/kb/${path}`, {
			method,
			headers: body ? { 'Content-Type': 'application/json' } : undefined,
			body: body ? JSON.stringify(body) : undefined
		});
		return { ok: res.ok, status: res.status, json: await res.json() };
	}

	async function load() {
		loading = true;
		loadError = null;
		const r = await hub('triggers');
		if (r.ok) {
			assets = r.json.data.assets;
			vocabulary = r.json.data.vocabulary;
			candidates = r.json.data.candidates;
		} else {
			loadError = r.json.reason ?? r.json.message ?? `Hub ${r.status}`;
		}
		loading = false;
	}
	onMount(load);

	function toYaml(rule: Rule): string {
		const q = (s: string) => JSON.stringify(s);
		const when = rule.when.map((c) => `  - {key: ${c.key}, op: ${c.op}, value: ${JSON.stringify(c.value)}}`).join('\n');
		return [
			`trigger_id: ${rule.trigger_id}`,
			`version: ${rule.version}`,
			`when:\n${when}`,
			`question: {fr: ${q(rule.question.fr)}, en: ${q(rule.question.en)}}`,
			`initial_level: ${rule.initial_level}`,
			`suggested_role: ${rule.suggested_role}`,
			`mandatory: ${rule.mandatory}`
		].join('\n');
	}

	async function selectCandidate(c: Candidate) {
		selected = { kind: 'candidate', id: c.id };
		const r = await hub(`candidates/${c.id}`);
		content = r.ok ? r.json.data.proposed_content : '';
		assetType = c.asset_type;
		targetAssetId = c.target_asset_id ?? null;
		message = null;
		await validateNow();
	}

	function selectRule(rule: Rule) {
		selected = { kind: 'rule', id: rule.trigger_id };
		content = toYaml(rule);
		assetType = 'trigger';
		targetAssetId = rule.trigger_id; // an edit of a published rule is an amendment: raise `version`
		message = null;
		validateNow();
	}

	// Live validation: the same validator as the candidate checks and the publication, on the vocabulary of the Hub.
	let timer: ReturnType<typeof setTimeout> | undefined;
	function onEdit() {
		clearTimeout(timer);
		timer = setTimeout(validateNow, 300);
	}
	async function validateNow() {
		if (!content.trim()) {
			valid = null;
			problems = [];
			return;
		}
		const r = await hub('triggers/validate', 'POST', {
			content,
			asset_type: assetType,
			target_asset_id: targetAssetId ?? undefined
		});
		if (r.ok) {
			valid = r.json.data.valid;
			problems = r.json.data.problems;
		}
	}

	// "With these facts, here are the questions that would open": the cascade engine's own evaluation, plus this draft.
	async function runPreview() {
		previewError = null;
		let facts: unknown;
		try {
			facts = JSON.parse(factsText);
		} catch {
			previewError = 'Les faits doivent être un objet JSON {clé: valeur}.';
			return;
		}
		const r = await hub('triggers/preview', 'POST', { facts, rules: content.trim() && assetType === 'trigger' ? [content] : [] });
		if (r.ok) preview = r.json.data;
		else {
			preview = null;
			previewError = `${r.json.code ?? ''} ${r.json.reason ?? r.json.message ?? ''} ${r.json.path ?? ''}`.trim();
		}
	}

	async function review(action: 'accept' | 'amend' | 'reject') {
		if (!selected || selected.kind !== 'candidate') return;
		message = null;
		const body: Record<string, unknown> = { action, reviewer, reason: reason || undefined };
		if (action === 'amend') body.amended_content = content;
		const r = await hub(`candidates/${selected.id}`, 'PATCH', body);
		message = r.ok
			? `Candidat ${selected.id} : ${r.json.data.status}. La publication reste l'acte du mainteneur.`
			: (r.json.reason ?? r.json.message ?? `Hub ${r.status}`);
		if (r.ok) await load();
	}

	async function merge() {
		if (!selected || selected.kind !== 'candidate' || !mergeInto) return;
		const r = await hub(`candidates/${selected.id}/merge-key`, 'POST', { into: mergeInto, reviewer, reason: reason || undefined });
		message = r.ok
			? `Clé fusionnée dans ${mergeInto}. ${r.json.data.affected_rules.length} règle(s) à amender.`
			: (r.json.reason ?? r.json.message ?? `Hub ${r.status}`);
		if (r.ok) await load();
	}

	const selectedCandidate = $derived(selected?.kind === 'candidate' ? candidates.find((c) => c.id === selected!.id) : undefined);
	const statusColor = (s: string) =>
		s === 'checks_failed' ? 'text-rose-400' : s === 'in_review' ? 'text-amber-400' : 'text-emerald-400';
</script>

<svelte:head><title>Règles de déclenchement</title></svelte:head>

<div class="mx-auto grid max-w-7xl gap-4 p-4 lg:grid-cols-[22rem_1fr_22rem]">
	<!-- Rules by carrying element, and the queue of candidates -->
	<section class="space-y-4">
		<h1 class="text-xl font-semibold">Règles de déclenchement</h1>
		{#if loading}
			<p class="text-sm opacity-70">Chargement…</p>
		{:else if loadError}
			<p class="rounded border border-rose-500/40 p-2 text-sm text-rose-400">{loadError}</p>
		{/if}

		<div>
			<h2 class="mb-1 text-sm font-semibold uppercase opacity-70">À relire ({candidates.length})</h2>
			{#each candidates as c (c.id)}
				<button
					class="mb-1 block w-full rounded border p-2 text-left text-sm hover:bg-white/5 {selected?.id === c.id ? 'border-violet-400' : 'border-white/10'}"
					onclick={() => selectCandidate(c)}
				>
					<span class="font-mono text-xs opacity-70">{c.id} · {c.asset_type}</span>
					<span class="block">{c.title}</span>
					<span class="text-xs {statusColor(c.status)}">{c.status}</span>
					{#if c.production_mode === 'llm-derived'}<span class="ml-2 text-xs text-sky-400">llm-derived</span>{/if}
				</button>
			{:else}
				<p class="text-sm opacity-60">Aucun candidat en attente (la file est réservée aux relecteurs).</p>
			{/each}
		</div>

		<div>
			<h2 class="mb-1 text-sm font-semibold uppercase opacity-70">Règles publiées par actif</h2>
			{#each assets as a (a.id)}
				<details class="mb-1 rounded border border-white/10 p-2" open>
					<summary class="cursor-pointer text-sm"><span class="font-mono">{a.id}</span> — {a.title}</summary>
					{#each a.rules as r (r.trigger_id)}
						<button
							class="mt-1 block w-full rounded p-1 text-left text-sm hover:bg-white/5 {selected?.id === r.trigger_id ? 'bg-white/10' : ''}"
							onclick={() => selectRule(r)}
						>
							<span class="font-mono text-xs">{r.trigger_id} v{r.version}</span>
							{#if r.mandatory}<span class="ml-1 rounded bg-rose-500/20 px-1 text-xs text-rose-300">obligatoire</span>{/if}
							<span class="block text-xs opacity-80">{r.question.fr}</span>
						</button>
					{/each}
				</details>
			{/each}
		</div>
	</section>

	<!-- Editor with live validation, and the review actions -->
	<section class="space-y-3">
		<h2 class="text-sm font-semibold uppercase opacity-70">
			Éditeur {assetType === 'fact_key' ? '(clé du vocabulaire)' : '(règle)'}
			{#if targetAssetId}— amendement de {targetAssetId}{/if}
		</h2>
		<textarea
			class="h-80 w-full rounded border border-white/10 bg-black/20 p-2 font-mono text-sm"
			bind:value={content}
			oninput={onEdit}
			spellcheck="false"
			placeholder="Choisir une règle ou un candidat…"
		></textarea>

		<div class="text-sm">
			{#if valid === true}
				<p class="text-emerald-400">✓ Valide pour le vocabulaire (version {vocabulary.version}).</p>
			{:else if valid === false}
				<ul class="space-y-1">
					{#each problems as p}
						<li class="rounded border border-rose-500/30 p-1 text-rose-300">
							<span class="font-mono text-xs">{p.path} [{p.code}]</span> {p.reason}
						</li>
					{/each}
				</ul>
			{/if}
		</div>

		{#if selectedCandidate}
			<div class="space-y-2 rounded border border-white/10 p-3">
				{#each selectedCandidate.checks as chk}
					<p class="text-xs"><span class="font-mono">{chk.name}</span> <span class={chk.status === 'fail' ? 'text-rose-400' : ''}>{chk.status}</span> — {chk.detail}</p>
				{/each}
				<div class="flex flex-wrap items-center gap-2">
					<input class="rounded border border-white/10 bg-black/20 p-1 text-sm" placeholder="@relecteur" bind:value={reviewer} />
					<input class="min-w-48 flex-1 rounded border border-white/10 bg-black/20 p-1 text-sm" placeholder="Motif (obligatoire pour amender ou rejeter)" bind:value={reason} />
				</div>
				<div class="flex flex-wrap gap-2">
					<button class="rounded bg-emerald-600 px-3 py-1 text-sm disabled:opacity-40" disabled={selectedCandidate.status !== 'in_review' || !reviewer} onclick={() => review('accept')}>Accepter</button>
					<button class="rounded bg-amber-600 px-3 py-1 text-sm disabled:opacity-40" disabled={!reviewer || !reason || valid === false} onclick={() => review('amend')}>Amender avec ce contenu</button>
					<button class="rounded bg-rose-600 px-3 py-1 text-sm disabled:opacity-40" disabled={!reviewer || !reason} onclick={() => review('reject')}>Rejeter</button>
				</div>
				{#if selectedCandidate.asset_type === 'fact_key'}
					<div class="flex flex-wrap items-center gap-2 border-t border-white/10 pt-2">
						<select class="rounded border border-white/10 bg-black/20 p-1 text-sm" bind:value={mergeInto}>
							<option value="">Fusionner avec la clé…</option>
							{#each vocabulary.keys as k}<option value={k.key}>{k.key}</option>{/each}
						</select>
						<button class="rounded bg-violet-600 px-3 py-1 text-sm disabled:opacity-40" disabled={!reviewer || !mergeInto} onclick={merge}>Fusionner</button>
					</div>
				{/if}
			</div>
		{/if}
		{#if message}<p class="text-sm text-sky-300">{message}</p>{/if}
	</section>

	<!-- Preview and vocabulary -->
	<section class="space-y-3">
		<h2 class="text-sm font-semibold uppercase opacity-70">Aperçu</h2>
		<textarea class="h-32 w-full rounded border border-white/10 bg-black/20 p-2 font-mono text-sm" bind:value={factsText} spellcheck="false"></textarea>
		<button class="rounded bg-violet-600 px-3 py-1 text-sm" onclick={runPreview}>Avec ces faits, quelles questions s'ouvrent ?</button>
		{#if previewError}<p class="text-sm text-rose-400">{previewError}</p>{/if}
		{#if preview}
			<ul class="space-y-1 text-sm">
				{#each preview.opens as r}
					<li class="rounded border border-emerald-500/30 p-1">
						<span class="font-mono text-xs">{r.trigger_id}{r.scope === 'draft' ? ' (brouillon)' : ''}</span>
						{#if r.mandatory}<span class="ml-1 text-xs text-rose-300">obligatoire</span>{/if}
						<span class="block">{r.question.fr}</span>
					</li>
				{:else}
					<li class="opacity-70">Aucune question ne s'ouvre.</li>
				{/each}
			</ul>
			{#if preview.invalid_drafts.length}<p class="text-xs text-rose-300">Brouillon invalide : voir l'éditeur.</p>{/if}
		{/if}

		<details class="rounded border border-white/10 p-2">
			<summary class="cursor-pointer text-sm">Vocabulaire des faits (v{vocabulary.version})</summary>
			<ul class="mt-1 space-y-1 text-xs">
				{#each vocabulary.keys as k}
					<li><span class="font-mono">{k.key}</span> : {k.type}{k.values ? ` ${JSON.stringify(k.values)}` : ''}{k.unit ? ` (${k.unit})` : ''}</li>
				{/each}
			</ul>
		</details>
	</section>
</div>
