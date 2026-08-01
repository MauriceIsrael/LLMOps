export interface KBEnvironment {
	id: string;
	name: string;
	type: 'local' | 'gcp';
	endpoint: string;
	status: 'connected' | 'offline';
}

class KBConfigStore {
	environments = $state<KBEnvironment[]>([
		{
			id: 'local-dev',
			name: 'Local KB (FastMCP)',
			type: 'local',
			endpoint: 'http://localhost:8000',
			status: 'connected'
		},
		{
			id: 'gcp-staging',
			name: 'GCP Staging (Cloud Run)',
			type: 'gcp',
			endpoint: 'https://kb-staging-mcp-run.a.run.app',
			status: 'connected'
		},
		{
			id: 'gcp-prod',
			name: 'GCP Production (Cloud Run)',
			type: 'gcp',
			endpoint: 'https://kb-prod-mcp-run.a.run.app',
			status: 'connected'
		}
	]);

	activeEnvId = $state<string>('local-dev');
	selectedDomain = $state<string | null>(null);
	selectedNodeId = $state<string | null>(null);

	get activeEnv(): KBEnvironment {
		return (
			this.environments.find((e) => e.id === this.activeEnvId) || this.environments[0]
		);
	}

	setEnvironment(id: string) {
		this.activeEnvId = id;
	}

	setSelectedDomain(domain: string | null) {
		this.selectedDomain = domain;
	}

	setSelectedNodeId(id: string | null) {
		this.selectedNodeId = id;
	}
}

export const kbConfig = new KBConfigStore();
