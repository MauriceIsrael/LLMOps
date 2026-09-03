import { json, type RequestHandler } from '@sveltejs/kit';
import fs from 'node:fs';
import path from 'node:path';

export const GET: RequestHandler = async ({ url }) => {
	const domainFilter = url.searchParams.get('domain');
	const skillsDir = path.resolve(process.cwd(), '../../data/kb/skills');

	if (!fs.existsSync(skillsDir)) {
		return json({ status: 'ok', count: 0, data: [] });
	}

	try {
		const files = fs.readdirSync(skillsDir).filter((f) => f.endsWith('.md'));
		const skills: any[] = [];

		for (const file of files) {
			const fullPath = path.join(skillsDir, file);
			const rawContent = fs.readFileSync(fullPath, 'utf-8');

			let frontmatter: Record<string, any> = {};
			const match = rawContent.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/);
			let body = rawContent;
			if (match) {
				body = match[2].trim();
				const lines = match[1].split('\n');
				for (const line of lines) {
					const colonIdx = line.indexOf(':');
					if (colonIdx > 0) {
						const key = line.slice(0, colonIdx).trim();
						let val: any = line.slice(colonIdx + 1).trim();
						if (val.startsWith('[') && val.endsWith(']')) {
							try {
								val = val.slice(1, -1).split(',').map((s: string) => s.trim().replace(/^['"]|['"]$/g, ''));
							} catch {
								// ignore
							}
						}
						frontmatter[key] = val;
					}
				}
			}

			if (domainFilter && frontmatter.domain !== domainFilter) {
				continue;
			}

			skills.push({
				id: frontmatter.id || path.parse(file).name,
				title: frontmatter.title || path.parse(file).name,
				domain: frontmatter.domain || 'general',
				criticality: frontmatter.criticality || 'medium',
				status: frontmatter.status || 'active',
				keywords: Array.isArray(frontmatter.keywords) ? frontmatter.keywords : [],
				description: body.slice(0, 300)
			});
		}

		return json({
			status: 'ok',
			count: skills.length,
			data: skills
		});
	} catch (err) {
		console.error('Erreur API skills:', err);
		return json({ status: 'error', message: 'Impossible de charger les compétences' }, { status: 500 });
	}
};
