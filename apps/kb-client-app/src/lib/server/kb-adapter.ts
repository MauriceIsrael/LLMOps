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

	async fetchAnalytics(): Promise<VolumeKpiData> {
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
