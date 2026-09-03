import { json, type RequestHandler } from '@sveltejs/kit';
import { exec } from 'node:child_process';
import path from 'node:path';
import util from 'node:util';
import fs from 'node:fs';

const execPromise = util.promisify(exec);

export const POST: RequestHandler = async ({ request }) => {
	const body = await request.json();
	const text = body.text || '';

	if (!text.trim()) {
		return json({ status: 'error', message: 'Texte d\'appel d\'offres vide' }, { status: 400 });
	}

	const repoRoot = path.resolve(process.cwd(), '../..');
	const tempDir = path.join(repoRoot, 'tmp');
	if (!fs.existsSync(tempDir)) {
		fs.mkdirSync(tempDir, { recursive: true });
	}
	const tempFilePath = path.join(tempDir, `rfp_upload_${Date.now()}.txt`);
	fs.writeFileSync(tempFilePath, text, 'utf-8');

	try {
		const { stdout } = await execPromise(`poetry run python scripts/analyze_rfp.py "${tempFilePath}" --output "${tempFilePath}.json"`, {
			cwd: repoRoot
		});

		let resultData: any = null;
		if (fs.existsSync(`${tempFilePath}.json`)) {
			resultData = JSON.parse(fs.readFileSync(`${tempFilePath}.json`, 'utf-8'));
			fs.unlinkSync(`${tempFilePath}.json`);
		}
		if (fs.existsSync(tempFilePath)) {
			fs.unlinkSync(tempFilePath);
		}

		return json({ status: 'ok', data: resultData, stdout });
	} catch (err) {
		console.error('Erreur analyseur RFP:', err);
		if (fs.existsSync(tempFilePath)) {
			fs.unlinkSync(tempFilePath);
		}
		return json({ status: 'error', message: 'Erreur lors de l\'analyse du document' }, { status: 500 });
	}
};
