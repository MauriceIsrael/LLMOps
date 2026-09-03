<script lang="ts">
	import { onMount } from 'svelte';
	import Check from 'lucide-svelte/icons/check';
	import AlertCircle from 'lucide-svelte/icons/alert-circle';
	import RefreshCw from 'lucide-svelte/icons/refresh-cw';
	import XCircle from 'lucide-svelte/icons/x-circle';
	import Sparkles from 'lucide-svelte/icons/sparkles';
	import MessageSquare from 'lucide-svelte/icons/message-square';
	import User from 'lucide-svelte/icons/user';
	import Building from 'lucide-svelte/icons/building';
	import Clock from 'lucide-svelte/icons/clock';
	import Send from 'lucide-svelte/icons/send';
	import ExternalLink from 'lucide-svelte/icons/external-link';

	interface Suggestion {
		id: string;
		timestamp: string;
		title: string;
		rationale: string;
		suggested_change: string;
		author: string;
		contact?: string;
		source_engagement?: string;
		status: 'pending_review' | 'needs_study' | 'approved' | 'rejected';
		reviewer?: string;
		reviewed_at?: string;
		review_feedback?: string;
		promoted_asset_id?: string;
	}

	let suggestions = $state<Suggestion[]>([]);
	let loading = $state(true);
	let selectedId = $state<string | null>(null);
	let activeFilter = $state<string>('all');
	let feedbackText = $state('');
	let showFeedbackInput = $state(false);
	let actionInProgress = $state(false);
	let actionMessage = $state<string | null>(null);

	async function loadSuggestions() {
		loading = true;
		try {
			const res = await fetch('/api/kb/suggestions');
			if (res.ok) {
				const json = await res.json();
				suggestions = json.data || [];
				if (suggestions.length > 0 && !selectedId) {
					selectedId = suggestions[0].id;
				}
			}
		} catch (e) {
			console.error('Erreur chargement suggestions:', e);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		loadSuggestions();
	});

	const filteredSuggestions = $derived(
		suggestions.filter((s) => {
			if (activeFilter === 'all') return true;
			return s.status === activeFilter;
		})
	);

	const activeSuggestion = $derived(
		suggestions.find((s) => s.id === selectedId) || null
	);

	const counts = $derived({
		total: suggestions.length,
		pending: suggestions.filter((s) => s.status === 'pending_review').length,
		needs_study: suggestions.filter((s) => s.status === 'needs_study').length,
		approved: suggestions.filter((s) => s.status === 'approved').length,
		rejected: suggestions.filter((s) => s.status === 'rejected').length
	});

	async function performAction(action: 'approve' | 'request_changes' | 'reject') {
		if (!selectedId) return;
		actionInProgress = true;
		actionMessage = null;

		try {
			const res = await fetch(`/api/kb/suggestions/${encodeURIComponent(selectedId)}`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					action,
					feedback: feedbackText.trim() || undefined,
					reviewer: 'Maurice Israel (Lead Architect)'
				})
			});

			if (res.ok) {
				const result = await res.json();
				actionMessage = action === 'approve'
					? `✅ Proposition approuvée avec succès ! Actif créé : ${result.createdAssetId}`
					: (action === 'request_changes' ? '🔄 Demande de réétude transmise sur Discord.' : 'Proposition rejetée.');
				feedbackText = '';
				showFeedbackInput = false;
				await loadSuggestions();
			}
		} catch (e) {
			console.error('Erreur action:', e);
			actionMessage = 'Erreur lors de l\'enregistrement de l\'action.';
		} finally {
			actionInProgress = false;
		}
	}
</script>

<div class="min-h-screen bg-slate-950 text-slate-100 p-6 flex flex-col gap-6 font-sans">
	<!-- Page Header -->
	<div class="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
		<div>
			<div class="flex items-center gap-3">
				<div class="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
					<Sparkles class="w-6 h-6" />
				</div>
				<h1 class="text-2xl font-bold tracking-tight text-white">Gouvernance REX & Suggestions d'Amélioration</h1>
			</div>
			<p class="text-sm text-slate-400 mt-1">
				Console d'arbitrage de Maurice Israel — Examinez, promouvez dans la KB globale ou demandez d'approfondir les motifs issus des projets.
			</p>
		</div>

		<!-- Counters Header -->
		<div class="flex items-center gap-2">
			<button 
				onclick={loadSuggestions} 
				class="flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
				disabled={loading}
			>
				<RefreshCw class="w-3.5 h-3.5 {loading ? 'animate-spin' : ''}" />
				Actualiser
			</button>
		</div>
	</div>

	<!-- Stats Badges -->
	<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
		<div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col">
			<span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Total Proposé</span>
			<span class="text-2xl font-bold text-white mt-1">{counts.total}</span>
		</div>
		<div class="p-4 rounded-xl bg-amber-500/5 border border-amber-500/20 flex flex-col">
			<span class="text-xs font-semibold uppercase tracking-wider text-amber-400">En attente d'arbitrage</span>
			<span class="text-2xl font-bold text-amber-300 mt-1">{counts.pending}</span>
		</div>
		<div class="p-4 rounded-xl bg-blue-500/5 border border-blue-500/20 flex flex-col">
			<span class="text-xs font-semibold uppercase tracking-wider text-blue-400">À approfondir</span>
			<span class="text-2xl font-bold text-blue-300 mt-1">{counts.needs_study}</span>
		</div>
		<div class="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20 flex flex-col">
			<span class="text-xs font-semibold uppercase tracking-wider text-emerald-400">Approuvées & Promues</span>
			<span class="text-2xl font-bold text-emerald-300 mt-1">{counts.approved}</span>
		</div>
	</div>

	<!-- Filter Tabs -->
	<div class="flex items-center gap-2 border-b border-slate-800/80 pb-2 overflow-x-auto text-sm">
		<button 
			onclick={() => activeFilter = 'all'} 
			class="px-3 py-1.5 rounded-lg font-medium transition {activeFilter === 'all' ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-slate-200'}"
		>
			Toutes ({counts.total})
		</button>
		<button 
			onclick={() => activeFilter = 'pending_review'} 
			class="px-3 py-1.5 rounded-lg font-medium transition {activeFilter === 'pending_review' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'text-slate-400 hover:text-slate-200'}"
		>
			En attente ({counts.pending})
		</button>
		<button 
			onclick={() => activeFilter = 'needs_study'} 
			class="px-3 py-1.5 rounded-lg font-medium transition {activeFilter === 'needs_study' ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' : 'text-slate-400 hover:text-slate-200'}"
		>
			À approfondir ({counts.needs_study})
		</button>
		<button 
			onclick={() => activeFilter = 'approved'} 
			class="px-3 py-1.5 rounded-lg font-medium transition {activeFilter === 'approved' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'text-slate-400 hover:text-slate-200'}"
		>
			Approuvées ({counts.approved})
		</button>
		<button 
			onclick={() => activeFilter = 'rejected'} 
			class="px-3 py-1.5 rounded-lg font-medium transition {activeFilter === 'rejected' ? 'bg-red-500/20 text-red-300 border border-red-500/30' : 'text-slate-400 hover:text-slate-200'}"
		>
			Rejetées ({counts.rejected})
		</button>
	</div>

	<!-- Main 2-Column Workspace -->
	<div class="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 items-start">
		<!-- Left: Suggestions List (5 cols) -->
		<div class="lg:col-span-5 flex flex-col gap-3">
			{#if loading}
				<div class="p-8 text-center text-slate-500 text-sm">Chargement des suggestions...</div>
			{:else if filteredSuggestions.length === 0}
				<div class="p-8 text-center bg-slate-900/40 rounded-xl border border-slate-800 text-slate-400 text-sm">
					Aucune suggestion ne correspond à ce filtre.
				</div>
			{:else}
				{#each filteredSuggestions as s (s.id)}
					<button
						onclick={() => selectedId = s.id}
						class="w-full text-left p-4 rounded-xl border transition flex flex-col gap-2 {selectedId === s.id ? 'bg-slate-900 border-emerald-500/50 shadow-lg shadow-emerald-950/20' : 'bg-slate-900/40 border-slate-800/80 hover:bg-slate-900/70 hover:border-slate-700'}"
					>
						<div class="flex items-center justify-between gap-2">
							<span class="text-xs font-mono text-slate-400">{s.id}</span>
							{#if s.status === 'pending_review'}
								<span class="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">En attente</span>
							{:else if s.status === 'needs_study'}
								<span class="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">À approfondir</span>
							{:else if s.status === 'approved'}
								<span class="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Approuvée</span>
							{:else}
								<span class="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-red-500/10 text-red-400 border border-red-500/20">Rejetée</span>
							{/if}
						</div>

						<h3 class="text-sm font-semibold text-white line-clamp-1">{s.title}</h3>
						<p class="text-xs text-slate-400 line-clamp-2">{s.rationale}</p>

						<div class="flex items-center gap-3 text-[11px] text-slate-500 mt-1">
							<span class="flex items-center gap-1"><User class="w-3 h-3" /> {s.author}</span>
							<span class="flex items-center gap-1"><Building class="w-3 h-3" /> {s.source_engagement || 'Global'}</span>
						</div>
					</button>
				{/each}
			{/if}
		</div>

		<!-- Right: Details & Action Drawer (7 cols) -->
		<div class="lg:col-span-7 bg-slate-900/60 rounded-xl border border-slate-800 p-6 flex flex-col gap-6 sticky top-24">
			{#if activeSuggestion}
				<!-- Header of Active Suggestion -->
				<div class="flex flex-col gap-2 border-b border-slate-800 pb-4">
					<div class="flex items-center justify-between">
						<span class="text-xs font-mono text-emerald-400 font-semibold">{activeSuggestion.id}</span>
						<span class="text-xs text-slate-400 flex items-center gap-1">
							<Clock class="w-3.5 h-3.5" />
							{new Date(activeSuggestion.timestamp).toLocaleString('fr-FR')}
						</span>
					</div>
					<h2 class="text-xl font-bold text-white">{activeSuggestion.title}</h2>
					<div class="flex flex-wrap items-center gap-4 text-xs text-slate-400 mt-1">
						<span>Auteur : <strong class="text-slate-200">{activeSuggestion.author}</strong></span>
						<span>Contact : <strong class="text-slate-200">{activeSuggestion.contact || 'N/A'}</strong></span>
						<span>Engagement : <strong class="text-slate-200">{activeSuggestion.source_engagement || 'Global'}</strong></span>
					</div>
				</div>

				{#if actionMessage}
					<div class="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs font-medium">
						{actionMessage}
					</div>
				{/if}

				<!-- Rationale -->
				<div class="flex flex-col gap-2">
					<h4 class="text-xs font-semibold uppercase tracking-wider text-slate-400">Raison & Valeur Architecturale</h4>
					<div class="p-3.5 rounded-lg bg-slate-950/60 border border-slate-800/80 text-sm text-slate-300">
						{activeSuggestion.rationale}
					</div>
				</div>

				<!-- Proposal Body -->
				<div class="flex flex-col gap-2">
					<h4 class="text-xs font-semibold uppercase tracking-wider text-slate-400">Proposition Technique Détaillée</h4>
					<div class="p-4 rounded-lg bg-slate-950 border border-slate-800 font-mono text-xs text-emerald-300 overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-72">
						{activeSuggestion.suggested_change}
					</div>
				</div>

				<!-- Review Feedback Trail if exists -->
				{#if activeSuggestion.review_feedback}
					<div class="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20 text-xs flex flex-col gap-1">
						<span class="font-semibold text-blue-400">Retour d'arbitrage ({activeSuggestion.reviewer || 'Maurice Israel'}) :</span>
						<p class="text-blue-200 italic">"{activeSuggestion.review_feedback}"</p>
					</div>
				{/if}

				{#if activeSuggestion.promoted_asset_id}
					<div class="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs flex items-center justify-between">
						<span class="text-emerald-300">Actif créé dans le patrimoine : <strong>{activeSuggestion.promoted_asset_id}</strong></span>
						<a href="/assets?id={activeSuggestion.promoted_asset_id}" class="text-emerald-400 hover:underline flex items-center gap-1">
							Voir dans les Actifs <ExternalLink class="w-3 h-3" />
						</a>
					</div>
				{/if}

				<!-- Action Controls for Maurice -->
				<div class="flex flex-col gap-3 border-t border-slate-800 pt-4">
					<span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Arbitrage Lead Architect</span>

					{#if showFeedbackInput}
						<div class="flex flex-col gap-2 p-3 rounded-lg bg-slate-950 border border-slate-800">
							<label for="feedback" class="text-xs text-slate-300 font-medium">Consignes techniques pour l'auteur (notifié sur Discord) :</label>
							<textarea 
								id="feedback"
								bind:value={feedbackText} 
								rows="3" 
								placeholder="Ex: Merci de préciser le benchmark de performance ou le dimensionnement mémoire..."
								class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-blue-500"
							></textarea>
							<div class="flex justify-end gap-2 mt-1">
								<button 
									onclick={() => showFeedbackInput = false} 
									class="px-3 py-1.5 text-xs text-slate-400 hover:text-white"
								>
									Annuler
								</button>
								<button 
									onclick={() => performAction('request_changes')} 
									class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-500 text-white"
									disabled={actionInProgress || !feedbackText.trim()}
								>
									<Send class="w-3 h-3" />
									Transmettre la consigne
								</button>
							</div>
						</div>
					{:else}
						<div class="flex flex-wrap items-center gap-3">
							<button 
								onclick={() => performAction('approve')} 
								class="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-950/40 transition"
								disabled={actionInProgress}
							>
								<Check class="w-4 h-4" />
								Approuver & Promouvoir (PAT)
							</button>

							<button 
								onclick={() => showFeedbackInput = true} 
								class="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 text-xs font-semibold transition"
								disabled={actionInProgress}
							>
								<MessageSquare class="w-4 h-4" />
								Demander d'approfondir
							</button>

							<button 
								onclick={() => performAction('reject')} 
								class="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 text-xs font-semibold transition"
								disabled={actionInProgress}
							>
								<XCircle class="w-4 h-4" />
								Rejeter
							</button>
						</div>
					{/if}
				</div>
			{:else}
				<div class="p-12 text-center text-slate-500 text-sm">
					Sélectionnez une suggestion pour afficher son contenu et l'arbitrer.
				</div>
			{/if}
		</div>
	</div>
</div>
