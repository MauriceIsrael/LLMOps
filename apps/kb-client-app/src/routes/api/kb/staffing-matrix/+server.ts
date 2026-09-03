import { json, type RequestHandler } from '@sveltejs/kit';
import { exec } from 'node:child_process';
import path from 'node:path';
import util from 'node:util';

const execPromise = util.promisify(exec);

export const GET: RequestHandler = async ({ url }) => {
	const engagement = url.searchParams.get('engagement') || 'nordwave-mcx-2027';
	const repoRoot = path.resolve(process.cwd(), '../..');

	try {
		const pythonScript = `
import json, sys
sys.path.insert(0, ".")
from mcp_server.knowledge.tools import get_skills_matrix
res = get_skills_matrix(engagement="${engagement}")
print(json.dumps(res))
`;
		const { stdout } = await execPromise(`poetry run python -c '${pythonScript}'`, {
			cwd: repoRoot
		});

		const result = JSON.parse(stdout.trim());
		return json(result);
	} catch (err) {
		console.error('Erreur calcul matrice staffing:', err);
		return json({ status: 'error', message: 'Erreur lors du calcul de la matrice' }, { status: 500 });
	}
};
