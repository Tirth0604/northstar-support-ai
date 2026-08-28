# Portfolio Content

## Overview and problem
Northstar Support AI demonstrates safe agentic support beyond a chat tutorial: support automation must answer from evidence, use business systems without cross-customer leakage, confirm sensitive writes, and hand difficult cases to humans with useful context.

## Solution and features
A bounded React/FastAPI system separates retrieval from verified tools, enforces RBAC/ownership in code, binds confirmations to actions/arguments, audits decisions, and pauses AI on takeover. It includes customer, support, and admin interfaces; synthetic commerce data; RAG; Docker; migrations; tests; evaluation; CI; and deployment guidance.

## Design challenges
Useful autonomy vs control led to one typed tool per turn. Memory vs truth led to re-reading business state through tools. Safe UX led to expiring confirmations rather than generic “yes.” Local portability led to mock/hash providers with a documented pgvector/Qdrant scale path.

## 60-second pitch
“Northstar Support AI is a support agent that safely works with business systems. It cites policy evidence, checks only the authenticated customer’s orders, confirms cancellation with an action-bound token, and escalates fraud, safety, legal, angry, or explicit-human cases. A support agent receives a structured handoff, transcript, and tool timeline, then takes over while AI pauses. The full React/FastAPI demo runs without a paid key and includes synthetic data, tests, evaluation, Docker, CI, and deployment docs.”

## Two-minute demo
1. Show three synthetic roles. 2. Ask about opened returns and expand citation. 3. Track `NS-100001`. 4. Request cancellation and show confirmation. 5. Report a duplicate charge/request human. 6. Log in as support, review handoff/audit, take over/reply. 7. Log in as admin and show actual metrics/knowledge. 8. End on passing tests/evaluation/build.

## Upwork description
Built a production-minded agentic support POC with grounded RAG, typed commerce tools, RBAC, tenant isolation, action-specific confirmations, deterministic escalation, human takeover, and full auditing. Includes offline mode, synthetic data, tests, evaluation, Docker Compose, CI, and deployment docs.

## GitHub description
Agentic customer support with grounded RAG, controlled tools, expiring confirmations, human takeover, React/FastAPI, and offline demo.

## LinkedIn post
I built Northstar Support AI to explore what matters after the chat bubble: safe business actions. It separates policy evidence from verified state, enforces customer-scoped tools, confirms sensitive actions, and hands risky cases to humans with full context. All data and metrics are explicitly demonstration-only.

## Resume bullets
- Architected bounded tool orchestration, cited RAG, RBAC, tenant isolation, and tamper-evident confirmation flows.
- Implemented deterministic escalation and takeover with structured handoffs, AI pause/release, and tool timelines.
- Delivered a React/FastAPI monorepo with synthetic commerce data, security tests, 34-case evaluation, Docker, CI, and deployment docs.

Topics: `agentic-ai`, `customer-support`, `rag`, `fastapi`, `react`, `human-in-the-loop`, `ai-safety`, `postgresql`, `docker`.

## Screenshot/video checklist
Capture login, cited answer, shipping card, confirmation, escalation, handoff, tool audit/human reply, admin metrics, knowledge lifecycle, OpenAPI, tests, evaluation, and build. Record at 1440×900, hide personal data, label “synthetic demo/local mock,” use the demo sequence above, trim loading only, and never claim clients, production usage, revenue, or efficiency savings.
