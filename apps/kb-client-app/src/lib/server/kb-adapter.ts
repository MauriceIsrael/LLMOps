import { GoogleAuth } from 'google-auth-library';
import fs from 'node:fs';
import path from 'node:path';

export interface KBProviderConfig {
	type: 'local' | 'gcp';
	endpoint: string;
	apiKey?: string;
	targetAudience?: string;
}

export interface VolumeKpiData {
	volume_by_type: Array<{ type: string; count: number }>;
	status_breakdown: Array<{ status: string; count: number }>;
	confidence_breakdown: Array<{ confidence: string; count: number }>;
	glossary_count: number;
	relations: {
		REQUIRES: number;
		SUPERSEDES: number;
	};
}

export interface DomainProminenceData {
	domain_volumes: Array<{ domain: string; count: number }>;
	cross_domain_dependencies: Array<{
		source_domain: string;
		target_domain: string;
		weight: number;
	}>;
}

export interface Node3D {
	id: string;
	title: string;
	type: string;
	domain: string;
	status: string;
	confidence: string;
	x: number;
	y: number;
	z: number;
	degree: number;
}

export interface Edge3D {
	id: string;
	source: string;
	target: string;
	type: 'REQUIRES' | 'SUPERSEDES' | 'DEFINES' | 'ABOUT';
	sourceDomain: string;
	targetDomain: string;
}

export interface LayeredGraphPayload {
	domains: string[];
	nodes: Node3D[];
	edges: Edge3D[];
}

export class KBAdapter {
	private config: KBProviderConfig;
	private auth: GoogleAuth | null = null;

	constructor(config: KBProviderConfig) {
		this.config = config;
		if (config.type === 'gcp') {
			this.auth = new GoogleAuth();
		}
	}

	private loadLocalExport(): any {
		try {
			const jsonPath = path.resolve(process.cwd(), '../../data/local_kb_export.json');
			if (fs.existsSync(jsonPath)) {
				const content = fs.readFileSync(jsonPath, 'utf-8');
				return JSON.parse(content);
			}
		} catch {
			// Fallback
		}
		return null;
	}

	private static cachedRemoteSnapshot: any = null;
	private static remoteSnapshotFetchedAt: number = 0;

	private async fetchRemoteSnapshot(): Promise<any> {
		const now = Date.now();
		if (KBAdapter.cachedRemoteSnapshot && now - KBAdapter.remoteSnapshotFetchedAt < 60000) {
			return KBAdapter.cachedRemoteSnapshot;
		}

		try {
			const token = process.env.SERVER_TOKEN || 'llmops-token-2026-sec-98a41f';
			const targetUrl = `${this.config.endpoint.replace(/\/+$/, '')}/snapshot/latest`;
			const res = await fetch(targetUrl, {
				headers: {
					Authorization: `Bearer ${token}`
				}
			});

			if (res.ok) {
				const data = await res.json();
				KBAdapter.cachedRemoteSnapshot = data;
				KBAdapter.remoteSnapshotFetchedAt = now;
				return data;
			} else {
				console.warn(`[KBAdapter] Requête snapshot distant (${res.status}) vers ${targetUrl}`);
			}
		} catch (err) {
			console.error('[KBAdapter] Erreur connexion GCP Cloud Run:', err);
		}
		return null;
	}

	async fetchAnalytics(): Promise<VolumeKpiData> {
		if (this.config.type === 'gcp') {
			const snap = await this.fetchRemoteSnapshot();
			if (snap?.assets && Array.isArray(snap.assets)) {
				const typeCounts: Record<string, number> = {};
				const statusCounts: Record<string, number> = {};
				const confidenceCounts: Record<string, number> = {};

				for (const a of snap.assets) {
					const t = a.type || 'unknown';
					typeCounts[t] = (typeCounts[t] || 0) + 1;
					const s = a.status || 'active';
					statusCounts[s] = (statusCounts[s] || 0) + 1;
					const c = a.confidence || 'verified';
					confidenceCounts[c] = (confidenceCounts[c] || 0) + 1;
				}

				return {
					volume_by_type: Object.entries(typeCounts).map(([type, count]) => ({ type, count })),
					status_breakdown: Object.entries(statusCounts).map(([status, count]) => ({ status, count })),
					confidence_breakdown: Object.entries(confidenceCounts).map(([confidence, count]) => ({ confidence, count })),
					glossary_count: Object.keys(snap.glossary || {}).length,
					relations: {
						REQUIRES: 0,
						SUPERSEDES: 1
					}
				};
			}
		}

		if (this.config.type === 'local') {
			const localData = this.loadLocalExport();
			if (localData?.analytics) {
				return localData.analytics;
			}
		}

		return {
			volume_by_type: [
				{ type: 'decision', count: 13 },
				{ type: 'principle', count: 15 },
				{ type: 'pattern', count: 7 },
				{ type: 'template', count: 5 },
				{ type: 'questionnaire', count: 3 }
			],
			status_breakdown: [
				{ status: 'active', count: 45 },
				{ status: 'superseded', count: 1 }
			],
			confidence_breakdown: [
				{ confidence: 'verified', count: 41 },
				{ confidence: 'assumed', count: 3 },
				{ confidence: 'vendor-stated', count: 2 }
			],
			glossary_count: 10,
			relations: {
				REQUIRES: 0,
				SUPERSEDES: 1
			}
		};
	}

	async fetchDomainProminence(): Promise<DomainProminenceData> {
		if (this.config.type === 'gcp') {
			const snap = await this.fetchRemoteSnapshot();
			if (snap?.assets && Array.isArray(snap.assets)) {
				const domainCounts: Record<string, number> = {};
				for (const a of snap.assets) {
					const d = a.domain || 'general';
					domainCounts[d] = (domainCounts[d] || 0) + 1;
				}
				return {
					domain_volumes: Object.entries(domainCounts).map(([domain, count]) => ({ domain, count })),
					cross_domain_dependencies: []
				};
			}
		}

		if (this.config.type === 'local') {
			const localData = this.loadLocalExport();
			if (localData?.prominence) {
				return localData.prominence;
			}
		}

		return {
			domain_volumes: [
				{ domain: 'network-automation', count: 7 },
				{ domain: 'ai-assistance', count: 4 },
				{ domain: 'mobile-core', count: 4 },
				{ domain: 'delivery', count: 4 },
				{ domain: 'observability', count: 3 }
			],
			cross_domain_dependencies: []
		};
	}

	async fetchLayeredGraph3D(): Promise<LayeredGraphPayload> {
		if (this.config.type === 'gcp') {
			const snap = await this.fetchRemoteSnapshot();
			if (snap?.assets && Array.isArray(snap.assets)) {
				const domainCounts: Record<string, number> = {};
				for (const a of snap.assets) {
					const dom = a.domain || 'general';
					domainCounts[dom] = (domainCounts[dom] || 0) + 1;
				}

				const topDomains = Object.entries(domainCounts)
					.sort((a, b) => b[1] - a[1])
					.slice(0, 6)
					.map(([d]) => d);

				const nodes: Node3D[] = [];

				snap.assets.forEach((a: any, idx: number) => {
					const dom = a.domain || 'general';
					const domainIdx = topDomains.indexOf(dom);
					const y = (domainIdx >= 0 ? domainIdx : topDomains.length) * 6;

					const angle = (idx * 2 * Math.PI) / snap.assets.length;
					const radius = 6 + (idx % 4) * 3;
					const x = Math.round(Math.cos(angle) * radius);
					const z = Math.round(Math.sin(angle) * radius);

					nodes.push({
						id: a.id,
						title: a.title || a.id,
						type: a.type || 'decision',
						domain: dom,
						status: a.status || 'active',
						confidence: a.confidence || 'verified',
						x,
						y,
						z,
						degree: 4 + (idx % 5)
					});
				});

				return {
					domains: topDomains,
					nodes,
					edges: []
				};
			}
		}

		if (this.config.type === 'local') {
			const localData = this.loadLocalExport();
			if (localData?.graph) {
				return localData.graph;
			}
		}

		const domains = [
			'network-automation',
			'cloud-platform',
			'observability',
			'ai-assistance',
			'security'
		];

		const nodes: Node3D[] = [
			{ id: 'ADR-0001', title: 'Git as the source of truth for network and platform configuration', type: 'decision', domain: 'network-automation', status: 'active', confidence: 'verified', x: -8, y: 0, z: -4, degree: 8 },
			{ id: 'ADR-0002', title: 'Network source of truth and compliance engine', type: 'decision', domain: 'network-automation', status: 'active', confidence: 'verified', x: 4, y: 0, z: 2, degree: 6 },
			{ id: 'ADR-0006', title: 'GitOps engine for the container platform', type: 'decision', domain: 'cloud-platform', status: 'active', confidence: 'verified', x: -5, y: 6, z: -2, degree: 7 },
			{ id: 'ADR-0008', title: 'Split observability: service plane and infrastructure plane', type: 'decision', domain: 'observability', status: 'active', confidence: 'verified', x: 0, y: 12, z: 2, degree: 6 },
			{ id: 'ADR-0010', title: 'Inference served by an external endpoint', type: 'decision', domain: 'ai-assistance', status: 'active', confidence: 'verified', x: -3, y: 18, z: -1, degree: 9 },
			{ id: 'ADR-0011', title: 'Inference served locally on general-purpose processors', type: 'decision', domain: 'ai-assistance', status: 'active', confidence: 'verified', x: 4, y: 18, z: 3, degree: 8 }
		];

		return { domains, nodes, edges: [] };
	}
}
