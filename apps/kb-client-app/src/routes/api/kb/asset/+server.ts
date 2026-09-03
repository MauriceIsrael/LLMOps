import { json, type RequestHandler } from '@sveltejs/kit';
import fs from 'node:fs';
import path from 'node:path';

export const GET: RequestHandler = async ({ url }) => {
	const id = url.searchParams.get('id');

	if (!id) {
		return json({ status: 'error', message: 'Asset ID is required' }, { status: 400 });
	}

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
					const val = line.slice(colonIdx + 1).trim();
					frontmatter[key] = val;
				}
			}
		}

		return json({
			status: 'ok',
			data: {
				id: frontmatter.id || id,
				title: frontmatter.title || id,
				type: frontmatter.type || 'decision',
				status: frontmatter.status || 'active',
				confidence: frontmatter.confidence || 'verified',
				domain: frontmatter.domain || 'General',
				owner: frontmatter.owner || 'architecture-team',
				last_reviewed: frontmatter.last_reviewed || '2026-07-25',
				frontmatter,
				body
			}
		});
	}

	return json({ status: 'not_found', id }, { status: 44 });
};
