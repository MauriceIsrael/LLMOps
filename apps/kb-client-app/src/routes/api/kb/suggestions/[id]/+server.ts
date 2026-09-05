import { json, type RequestHandler } from '@sveltejs/kit';
import fs from 'node:fs';
import path from 'node:path';
import { detectApplicableControls } from '$lib/server/compliance-matcher';

export const POST: RequestHandler = async ({ params, request }) => {
	const { id } = params;
	if (!id) {
		return json({ status: 'error', message: 'ID manquant' }, { status: 400 });
	}

	const suggestionsDir = path.resolve(process.cwd(), '../../data/suggestions');
	const filePath = path.join(suggestionsDir, `${id}.json`);

	if (!fs.existsSync(filePath)) {
		return json({ status: 'error', message: `Suggestion ${id} introuvable` }, { status: 404 });
	}

	try {
		const payload = await request.json();
		const { action, feedback, reviewer = 'Maurice Israel (Lead Architect)' } = payload;

		if (!['approve', 'request_changes', 'reject'].includes(action)) {
			return json({ status: 'error', message: `Action '${action}' non reconnue` }, { status: 400 });
		}

		const raw = fs.readFileSync(filePath, 'utf-8');
		const suggestion = JSON.parse(raw);

		suggestion.status = action === 'approve' ? 'approved' : (action === 'request_changes' ? 'needs_study' : 'rejected');
		suggestion.reviewed_at = new Date().toISOString();
		suggestion.reviewer = reviewer;
		if (feedback) {
			suggestion.review_feedback = feedback;
		}

		let createdAssetId: string | null = null;
		let detectedControls: string[] = [];

		// Si approuvé, on génère le pattern dans data/kb/patterns/
		if (action === 'approve') {
			const patternsDir = path.resolve(process.cwd(), '../../data/kb/patterns');
			if (!fs.existsSync(patternsDir)) {
				fs.mkdirSync(patternsDir, { recursive: true });
			}

			// Détection sémantique continue des contrôles réglementaires (Bottom-Up)
			detectedControls = detectApplicableControls(
				suggestion.title,
				`${suggestion.rationale || ''}\n${suggestion.suggested_change || ''}`,
				['telecom-core', 'security-architecture']
			);

			// Trouver le prochain ID de pattern (PAT-00X)
			const existingFiles = fs.readdirSync(patternsDir).filter(f => f.startsWith('PAT-') && f.endsWith('.md'));
			const nextNum = existingFiles.length + 1;
			createdAssetId = `PAT-${String(nextNum).padStart(3, '0')}`;
			suggestion.promoted_asset_id = createdAssetId;
			suggestion.implemented_controls = detectedControls;

			const newPatternPath = path.join(patternsDir, `${createdAssetId}.md`);
			const controlsYaml = detectedControls.length > 0
				? `\nimplements_controls: [${detectedControls.join(', ')}]`
				: '';

			const patternContent = `---
id: ${createdAssetId}
title: "${suggestion.title.replace(/"/g, '\\"')}"
type: pattern
status: active
confidence: verified
phase: [BUILD, RUN]
domain: [telecom-core, security-architecture]
owner: "${suggestion.author || 'corporate-architecture'}"
last_reviewed: "${new Date().toISOString().slice(0, 10)}"
source_suggestion: "${id}"
source_engagement: "${suggestion.source_engagement || 'global'}"${controlsYaml}
---

# ${suggestion.title}

## Contexte & Justification
${suggestion.rationale}

## Motif Architectural & Recommandation
${suggestion.suggested_change}

## Historique d'Élicitation
Promu automatiquement depuis le projet \`${suggestion.source_engagement || 'global'}\` suite à l'arbitrage du Lead Architect (${reviewer}) le ${new Date().toLocaleDateString('fr-FR')}.
`;
			fs.writeFileSync(newPatternPath, patternContent, 'utf-8');
		}

		// Sauvegarde de la suggestion mise à jour
		fs.writeFileSync(filePath, JSON.stringify(suggestion, null, 2), 'utf-8');

		// Notification Discord automatique de l'arbitrage
		try {
			const webhookUrl = process.env.OWNER_NOTIFICATION_WEBHOOK || process.env.DISCORD_WEBHOOK_URL;
			if (webhookUrl) {
				const colorMap: Record<string, number> = {
					approve: 3066993,      // Vert émeraude
					request_changes: 3447003, // Bleu information
					reject: 15158332,      // Rouge
				};
				const actionTitles: Record<string, string> = {
					approve: `✅ Proposition APPROUVÉE : ${suggestion.title}`,
					request_changes: `🔄 Demande d'Approfondissement : ${suggestion.title}`,
					reject: `❌ Proposition REJETÉE : ${suggestion.title}`,
				};

				const fields: any[] = [
					{ name: "Auteur initial", value: suggestion.author || "Non spécifié", inline: true },
					{ name: "Projet Source", value: suggestion.source_engagement || "Global", inline: true },
					{ name: "Statut Actuel", value: suggestion.status.toUpperCase(), inline: true },
				];

				if (detectedControls.length > 0) {
					fields.push({
						name: "🛡️ Contrôles Couverts (Auto)",
						value: detectedControls.join(", "),
						inline: false
					});
				}

				const discordPayload = {
					username: "Knowledge Hub Governance",
					avatar_url: "https://raw.githubusercontent.com/MauriceIsrael/LLMOps/main/assets/icon.png",
					embeds: [
						{
							title: actionTitles[action],
							description: feedback 
								? `**Retour du Lead Architect (${reviewer}) :**\n> ${feedback}\n\n**Proposition originale :**\n\`\`\`markdown\n${(suggestion.suggested_change || '').slice(0, 400)}\n\`\`\``
								: (action === 'approve' ? `La proposition a été promue dans la base de connaissances sous l'identifiant actif **${createdAssetId}**.` : `La proposition a été clôturée.`),
							color: colorMap[action],
							fields: fields,
							footer: { text: `ID: ${id} • Arbitrage Maurice Israel` },
							timestamp: new Date().toISOString()
						}
					]
				};

				await fetch(webhookUrl, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(discordPayload)
				});
			}
		} catch (webhookErr) {
			console.warn('Échec envoi notification Discord lors de l\'arbitrage:', webhookErr);
		}

		return json({
			status: 'ok',
			message: `Suggestion ${id} mise à jour (${action})`,
			data: suggestion,
			createdAssetId
		});
	} catch (err) {
		console.error(`Erreur action sur suggestion ${id}:`, err);
		return json({ status: 'error', message: 'Erreur lors du traitement de l\'action' }, { status: 500 });
	}
};
