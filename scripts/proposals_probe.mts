// Sonde de Requirements Intake, lancée par scripts/verify_proposals.py depuis son dépôt :
//   cd <requirements-intake> && npx tsx <llmops>/scripts/proposals_probe.mts <requirements-intake> <enveloppe.json>
// Elle ne modifie aucun dépôt. Elle rejoue, avec le schéma de la suite (`extractedCandidateSchema`, zod), chaque candidate de l'instantané.
import { readFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'

const [riDir, file] = process.argv.slice(2)
const { extractedCandidateSchema } = await import(pathToFileURL(`${riDir}/packages/contracts/src/index.ts`).href)
const envelope = JSON.parse(readFileSync(file, 'utf8'))
const out = envelope.data.candidates.map((candidate: { id: string }) => {
  const parsed = extractedCandidateSchema.safeParse(candidate)
  return {
    id: candidate.id,
    accepted: parsed.success,
    issues: parsed.success ? [] : parsed.error.issues.map((i: { path: (string | number)[]; message: string }) => `${i.path.join('.')}: ${i.message}`),
  }
})
console.log(JSON.stringify(out))
