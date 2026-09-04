import { json, type RequestHandler } from '@sveltejs/kit';
import fs from 'node:fs';
import path from 'node:path';

let cachedSnapshot: any = null;
let lastSnapshotFetch = 0;

function getSnapshot(): any {
	const now = Date.now();
	if (cachedSnapshot && now - lastSnapshotFetch < 60000) {
		return cachedSnapshot;
	}
	try {
		const snapPath = path.resolve(process.cwd(), '../../data/snapshots/latest.json');
		if (fs.existsSync(snapPath)) {
			cachedSnapshot = JSON.parse(fs.readFileSync(snapPath, 'utf-8'));
			lastSnapshotFetch = now;
			return cachedSnapshot;
		}
	} catch (e) {
		console.warn('[API Asset] Erreur lecture snapshot local:', e);
	}
	return null;
}

export const GET: RequestHandler = async ({ url }) => {
	const id = url.searchParams.get('id');

	if (!id) {
		return json({ status: 'error', message: 'Asset ID is required' }, { status: 400 });
	}

	const snap = getSnapshot();

	// Try to find the markdown file directly in data/kb/
	const kbDir = path.resolve(process.cwd(), '../../data/kb');
	let matchedFile: string | null = null;

	const targetId = id;
	function findFile(dir: string) {
		if (!fs.existsSync(dir)) return;
		const entries = fs.readdirSync(dir, { withFileTypes: true });
		for (const entry of entries) {
			const fullPath = path.join(dir, entry.name);
			if (entry.isDirectory()) {
				findFile(fullPath);
			} else if (entry.isFile() && (entry.name.includes(targetId) || entry.name === `${targetId}.md`)) {
				matchedFile = fullPath;
				break;
			}
		}
	}

	findFile(kbDir);

	if (matchedFile && fs.existsSync(matchedFile)) {
		const rawContent = fs.readFileSync(matchedFile, 'utf-8');
		
		// Basic Frontmatter Extractor
		let frontmatter: Record<string, any> = {};
		let body = rawContent;

		const match = rawContent.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/);
		if (match) {
			body = match[2];
			const yamlLines = match[1].split('\n');
			for (const line of yamlLines) {
				const colonIdx = line.indexOf(':');
				if (colonIdx > 0) {
					const key = line.slice(0, colonIdx).trim();
					let val: any = line.slice(colonIdx + 1).trim();
					if (val.startsWith('[') && val.endsWith(']')) {
						val = val.slice(1, -1).split(',').map((s: string) => s.trim().replace(/^['"]|['"]$/g, ''));
					}
					frontmatter[key] = val;
				}
			}
		}

		const assetType = frontmatter.type || (id.startsWith('ADR-') ? 'decision' : id.startsWith('P-') ? 'principle' : id.startsWith('PAT-') ? 'pattern' : 'asset');

		// Resolve bidirectional compliance relationships
		let implements_controls: any[] = [];
		let implemented_by: any[] = [];

		if (snap) {
			// If viewing a control: find who implements it
			if (assetType === 'control' || (snap.controls || []).some((c: any) => c.id === id)) {
				const ctrl = (snap.controls || []).find((c: any) => c.id === id);
				const implIds = ctrl?.implemented_by || [];
				implemented_by = implIds.map((aid: string) => {
					const found = (snap.assets || []).find((a: any) => a.id === aid);
					return {
						id: aid,
						type: found?.type || 'pattern',
						title: found?.title || aid
					};
				});
			} else {
				// If viewing an asset: find which controls it implements
				const rawCtrlIds: string[] = Array.isArray(frontmatter.implements_controls)
					? frontmatter.implements_controls
					: [];
				
				// Cross-reference with snap.controls
				for (const c of snap.controls || []) {
					if (Array.isArray(c.implemented_by) && c.implemented_by.includes(id) && !rawCtrlIds.includes(c.id)) {
						rawCtrlIds.push(c.id);
					}
				}

				implements_controls = rawCtrlIds.map((cid: string) => {
					const ctrl = (snap.controls || []).find((c: any) => c.id === cid);
					return {
						id: cid,
						framework: ctrl?.framework || cid.split('-')[0],
						title: ctrl?.title || cid,
						severity: ctrl?.severity || 'mandatory'
					};
				});
			}
		}

		return json({
			status: 'ok',
			data: {
				id: frontmatter.id || id,
				title: frontmatter.title || id,
				type: assetType,
				status: frontmatter.status || 'active',
				confidence: frontmatter.confidence || 'verified',
				domain: frontmatter.domain || frontmatter.framework || 'General',
				owner: frontmatter.owner || 'architecture-team',
				last_reviewed: frontmatter.last_reviewed || '2026-07-25',
				frontmatter,
				body,
				implements_controls,
				implemented_by
			}
		});
	}

	// Fallback : recherche dans le snapshot distant GCP
	try {
		const token = process.env.SERVER_TOKEN || 'llmops-token-2026-sec-98a41f';
		const gcpEndpoint = process.env.GCP_KB_ENDPOINT || 'https://llmops-mcp-server-344571265365.europe-west1.run.app';
		const res = await fetch(`${gcpEndpoint}/snapshot/latest`, {
			headers: { Authorization: `Bearer ${token}` }
		});

		if (res.ok) {
			const remoteSnap = await res.json();
			const asset = (remoteSnap.assets || []).find((a: any) => a.id === id || a.typed_id === id);
			const ctrl = (remoteSnap.controls || []).find((c: any) => c.id === id);
			const item = asset || ctrl;

			if (item) {
				const isControl = Boolean(ctrl);
				const implIds = ctrl?.implemented_by || [];
				const implemented_by = implIds.map((aid: string) => {
					const found = (remoteSnap.assets || []).find((a: any) => a.id === aid);
					return { id: aid, type: found?.type || 'pattern', title: found?.title || aid };
				});

				const rawCtrlIds: string[] = [];
				for (const c of remoteSnap.controls || []) {
					if (Array.isArray(c.implemented_by) && c.implemented_by.includes(id)) {
						rawCtrlIds.push(c.id);
					}
				}
				const implements_controls = rawCtrlIds.map((cid: string) => {
					const foundCtrl = (remoteSnap.controls || []).find((c: any) => c.id === cid);
					return {
						id: cid,
						framework: foundCtrl?.framework || cid.split('-')[0],
						title: foundCtrl?.title || cid,
						severity: foundCtrl?.severity || 'mandatory'
					};
				});

				return json({
					status: 'ok',
					data: {
						id: item.id,
						title: item.title || item.id,
						type: isControl ? 'control' : (item.type || 'decision'),
						status: item.status || 'active',
						confidence: item.confidence || 'verified',
						domain: item.domain || item.framework || 'General',
						owner: item.owner || 'architecture-team',
						last_reviewed: item.last_reviewed || '2026-09-03',
						frontmatter: item,
						body: `# ${item.title}\n\nActif synchronisé depuis l'instance distante GCP Cloud Run.\n\n- **Domaine :** ${item.domain || item.framework}\n- **Statut :** ${item.status}\n- **Confiance :** ${item.confidence}\n- **Propriétaire :** ${item.owner || 'architecture-team'}\n- **Phase :** ${Array.isArray(item.phase) ? item.phase.join(', ') : (item.phase || 'N/A')}`,
						implements_controls,
						implemented_by
					}
				});
			}
		}
	} catch (err) {
		console.warn(`[API Asset] Échec fallback GCP pour ${id}:`, err);
	}

	return json({ status: 'not_found', id }, { status: 404 });
};
