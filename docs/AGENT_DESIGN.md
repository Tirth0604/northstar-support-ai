# Agent Design
State is separated into recent conversation context, verified business state from tools, and a persisted conversation/handoff summary. Earlier AI prose never becomes business truth.

Nodes: input validation → identity → intent → sentiment/risk → retrieval/tool choice → permission/schema check → confirmation → execution → result validation → response contract → escalation → summary/audit. The mock workflow executes at most one business tool per turn.

`AgentResponse` validates informational, clarification, tool, confirmation, action, ticket, escalation, human, refusal, and error payloads. Explicit human, fraud, duplicate charge, legal, safety, anger, permissions, repeated failures, exceptions, disputes, and unresolved cases are escalation candidates. Takeover sets `ai_enabled=false`; release returns control.
