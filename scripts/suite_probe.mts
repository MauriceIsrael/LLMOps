// Sonde du Document Engine, lancée par scripts/verify_suite.py depuis le dépôt du Document Engine :
//   cd <document-engine> && npx tsx <llmops>/scripts/suite_probe.mts <document-engine> <kind>=<enveloppe.json>...
// avec <kind> = `conformity` (relue par le lecteur de conformité) ou `engagement` (checksum seulement : pas de lecteur).
// Elle n'écrit rien et ne modifie aucun des deux dépôts. Elle rejoue, avec le CODE du Document Engine, deux choses :
//   1. le checksum de chaque enveloppe (computeSnapshotChecksum) ;
//   2. pour une enveloppe de conformité, le verdict de son lecteur (validateConformitySnapshot), sans rien « corriger ».
import { readFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'

const [deDir, ...specs] = process.argv.slice(2)
const load = (rel: string) => import(pathToFileURL(`${deDir}/${rel}`).href)
const { computeSnapshotChecksum } = await load('src/external/envelope.ts')
const { validateConformitySnapshot } = await load('src/conformity/types.ts')

const out = specs.map((spec) => {
  const [kind, file] = [spec.slice(0, spec.indexOf('=')), spec.slice(spec.indexOf('=') + 1)]
  const envelope = JSON.parse(readFileSync(file, 'utf8'))
  const row: Record<string, unknown> = {
    file,
    kind,
    sourceSystem: envelope.sourceSystem,
    schemaVersion: envelope.schemaVersion,
    checksumRecomputedByDocumentEngine: computeSnapshotChecksum(envelope.data),
    checksumInEnvelope: envelope.checksum,
  }
  if (kind === 'conformity') {
    try {
      validateConformitySnapshot(envelope)
      row.conformityReader = { accepted: true }
    } catch (e) {
      row.conformityReader = { accepted: false, message: (e as Error).message.slice(0, 300) }
    }
  }
  return row
})
console.log(JSON.stringify(out))
