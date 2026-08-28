# API
Base `/api/v1`; bearer authentication; OpenAPI `/docs`.

- Health: `/health`, `/readiness`
- Auth: `/auth/login`, `/auth/logout`, `/auth/me`
- Customer: `/conversations`, `/{id}/messages`, `/confirm-action`, `/request-human`; `/customer/orders`, shipping, tickets
- Support: `/agent/queue`, conversation detail/takeover/reply/release, ticket patch/notes
- Admin: `/admin/knowledge/documents` lifecycle; overview/escalation/tool/quality metrics; configuration, errors, agents

Responses use correct status codes and validated structured agent payloads. Production-scale lists should add cursor pagination before importing large datasets.
