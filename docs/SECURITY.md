# Security
Implemented: signed expiring demo tokens, active-user checks, RBAC, customer ownership filters, internal-note separation, typed tools, mutation/confirmation/frequency policies, tamper-evident action-bound confirmation expiry, prompt-injection refusal, safe logs, request IDs, CORS allowlist, and masked/no payment secrets. Tests cover cross-customer access, admin denial, injection, confirmation, and takeover.

Production requires OIDC, asymmetric token rotation/revocation, Argon2id, TLS/HSTS, malware scanning, object quarantine, row-level security, distributed limits, immutable audit export, KMS secrets, encrypted backups, CSP, retention/deletion workflows, and privacy/legal review. Demo SHA-256 password hashing is not production-grade.
