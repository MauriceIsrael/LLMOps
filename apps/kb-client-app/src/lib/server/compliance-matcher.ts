import fs from 'node:fs';
import path from 'node:path';

export interface RegulatoryControlInfo {
	id: string;
	framework: string;
	title: string;
	domain: string[];
	terms: string[];
}

let cachedControls: RegulatoryControlInfo[] | null = null;

export function loadControls(): RegulatoryControlInfo[] {
	if (cachedControls) return cachedControls;

	const controlsDir = path.resolve(process.cwd(), '../../data/kb/controls');
	if (!fs.existsSync(controlsDir)) {
		return [];
	}

	const results: RegulatoryControlInfo[] = [];

	function scanDir(dir: string) {
		const entries = fs.readdirSync(dir, { withFileTypes: true });
		for (const entry of entries) {
			const full = path.join(dir, entry.name);
			if (entry.isDirectory()) {
				scanDir(full);
			} else if (entry.isFile() && entry.name.endsWith('.md') && !entry.name.startsWith('_') && entry.name.toLowerCase() !== 'readme.md') {
				try {
					const content = fs.readFileSync(full, 'utf-8');
					const fmMatch = content.match(/^---\s*\n([\s\S]*?)\n---/);
					if (!fmMatch) continue;

					const fmLines = fmMatch[1].split('\n');
					let id = '';
					let framework = '';
					let title = '';
					const domain: string[] = [];
					const terms: string[] = [];

					for (const line of fmLines) {
						const trimmed = line.trim();
						if (trimmed.startsWith('id:')) id = trimmed.replace('id:', '').trim();
						if (trimmed.startsWith('framework:')) framework = trimmed.replace('framework:', '').trim();
						if (trimmed.startsWith('title:')) title = trimmed.replace('title:', '').trim().replace(/^["']|["']$/g, '');
						if (trimmed.startsWith('domain:')) {
							const raw = trimmed.replace('domain:', '').trim();
							if (raw.startsWith('[') && raw.endsWith(']')) {
								domain.push(...raw.slice(1, -1).split(',').map((s) => s.trim().toLowerCase()));
							}
						}
						if (trimmed.startsWith('terms:')) {
							const raw = trimmed.replace('terms:', '').trim();
							if (raw.startsWith('[') && raw.endsWith(']')) {
								terms.push(...raw.slice(1, -1).split(',').map((s) => s.trim().toLowerCase()));
							}
						}
					}

					if (id) {
						results.push({ id, framework, title, domain, terms });
					}
				} catch {
					// Ignorer erreurs de lecture de fichier
				}
			}
		}
	}

	scanDir(controlsDir);
	cachedControls = results;
	return results;
}

const SPECIFIC_KEYWORDS: Record<string, string[]> = {
	'SNC-REQ-01': ['extraterritorial', 'souverain', 'cloud act', 'on-premise', 'trust boundary', 'local inference', 'sovereignty'],
	'SNC-REQ-02': ['bastion', 'management cluster', 'mtls', 'segregation', 'administration network'],
	'SNC-REQ-03': ['hsm', 'envelope encryption', 'kms', 'key management', 'root of trust'],
	'SNC-REQ-04': ['container', 'hardened', 'hypervisor', 'rootless', 'network policy', 'kubernetes'],
	'SNC-REQ-05': ['audit log', 'siem', 'soc', 'immutable', 'telemetry', 'observability', 'tamper'],
	'SNC-REQ-06': ['disaster recovery', 'bcp', 'drp', 'pra', 'pca', 'multi-site', 'fallback', 'failover'],
	'ISO-27001-A5-15': ['supplier', 'vendor', 'sbom', 'supply chain', 'third-party'],
	'ISO-27001-A8-01': ['endpoint', 'fleet', 'remote wipe', 'device', 'terminal'],
	'ISO-27001-A8-08': ['vulnerability', 'scanner', 'patch', 'shadow validation', 'devsecops'],
	'ISO-27001-A8-09': ['gitops', 'source of truth', 'drift', 'configuration management', 'declarative'],
	'ISO-27001-A8-24': ['cryptography', 'ciphers', 'key lifecycle', 'encryption'],
	'ISO-27001-A8-28': ['log', 'logging', 'tamper-resistant', 'retention', 'non-repudiation'],
	'3GPP-TS33501-SBI': ['sba', 'token', 'nrf', 'service-based', 'oauth'],
	'3GPP-TS33501-SEPP': ['sepp', 'inter-plmn', 'roaming', 'n32', 'boundary'],
	'3GPP-TS33179-ISOLATED': ['isolated', 'iops', 'local site', 'autonomous'],
	'3GPP-TS33179-KMS': ['kms', 'group key', 'gtk', 'gmk', 'media encryption'],
	'3GPP-TS33179-AFFILIATION': ['affiliation', 'talkgroup', 'mutual auth']
};

export function detectApplicableControls(
	title: string,
	content: string,
	domain: string[] = []
): string[] {
	const controls = loadControls();
	const fullText = `${title}\n${content}`.toLowerCase();
	const matched: { id: string; score: number }[] = [];

	for (const ctrl of controls) {
		let score = 0;

		// 1. Termes normalisés
		for (const term of ctrl.terms) {
			const clean = term.replace(/-/g, ' ');
			if (fullText.includes(term) || fullText.includes(clean)) {
				score += 0.45;
			}
		}

		// 2. Domaines partagés
		for (const d of ctrl.domain) {
			if (domain.some((dom) => dom.toLowerCase() === d || d.includes(dom.toLowerCase()))) {
				score += 0.2;
			}
		}

		// 3. Mots clés ciblés
		const kws = SPECIFIC_KEYWORDS[ctrl.id];
		if (kws) {
			for (const kw of kws) {
				if (fullText.includes(kw)) {
					score += 0.2;
				}
			}
		}

		if (score >= 0.35) {
			matched.push({ id: ctrl.id, score });
		}
	}

	matched.sort((a, b) => b.score - a.score);
	return matched.map((m) => m.id);
}
