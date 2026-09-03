import { json, type RequestHandler } from '@sveltejs/kit';
import fs from 'node:fs';
import path from 'node:path';

export const GET: RequestHandler = async ({ url }) => {
	const statusFilter = url.searchParams.get('status');
	const suggestionsDir = path.resolve(process.cwd(), '../../data/suggestions');

	if (!fs.existsSync(suggestionsDir)) {
		return json({ status: 'ok', count: 0, data: [] });
	}

	try {
		const files = fs.readdirSync(suggestionsDir).filter((f) => f.endsWith('.json'));
		const suggestions: any[] = [];

		for (const file of files) {
			const fullPath = path.join(suggestionsDir, file);
			try {
				const content = fs.readFileSync(fullPath, 'utf-8');
				const data = JSON.parse(content);

				// Default status to 'pending_review' if not set
				if (!data.status) {
					data.status = 'pending_review';
				}

				if (!statusFilter || data.status === statusFilter) {
					suggestions.push(data);
				}
			} catch (err) {
				console.error(`Erreur lecture suggestion ${file}:`, err);
			}
		}

		// Trier par date décroissante
		suggestions.sort((a, b) => {
			const dateA = new Date(a.timestamp || 0).getTime();
			const dateB = new Date(b.timestamp || 0).getTime();
			return dateB - dateA;
		});

		return json({
			status: 'ok',
			count: suggestions.length,
			data: suggestions
		});
	} catch (err) {
		console.error('Erreur API suggestions:', err);
		return json({ status: 'error', message: 'Impossible de lire les suggestions' }, { status: 500 });
	}
};
