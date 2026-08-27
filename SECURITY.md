# Security Policy & Public Demonstration Notice

## 🛡️ Public Demonstration Token Notice

The token string published in `README.md`, `README.fr.md`, `docs/user_manual.md`, and `docs/renderer_integration.md` (`demo-public-2026-08`) **is intentionally public**.

- It grants access exclusively to the **read-only Knowledge Plane** (`LLMOPS_PLANE=knowledge`) of the public demonstration deployment on GCP Cloud Run.
- No write, insert, update, or delete operations are exposed or permitted on the public endpoint.
- Do **not** report the published demo token string as a leaked secret or credential exposure issue.

For details on configuring a private, authenticated enterprise deployment with dedicated Secret Manager tokens, see [`docs/deployment.md`](docs/deployment.md).

---

## 🔒 Reporting Security Vulnerabilities

We take the security of LLMOps seriously. If you discover a security vulnerability (such as a bypass of read-only Cypher enforcement or authentication bypass):

1. **Do NOT open a public GitHub issue.**
2. Use [GitHub Private Vulnerability Reporting](https://github.com/MauriceIsrael/LLMOps/security/advisories/new) to submit your report privately to repository maintainers.
3. Include detailed steps to reproduce the issue and any relevant payload logs.
4. We will acknowledge receipt of your report within 48 hours and work with you on a resolution timeline.
