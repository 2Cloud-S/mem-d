# Decision Log

Purpose:

Preserve architectural decisions.

Avoid re-discussing solved problems.

---

# ADR-001

Date:
2026-06-10

Decision:

Build CLI before website.

Reason:

Validate value before branding.

Status:

Accepted

---

# ADR-002

Decision:

Local-first architecture.

Reason:

Developer trust.
Privacy.
Lower operating costs.

Status:

Accepted

---

# ADR-003

Decision:

Read-only analysis.

Reason:

Prevent accidental memory corruption.

Status:

Accepted

---

# ADR-004

Decision:

No dashboard in V1.

Reason:

The product is analysis.

Not visualization.

Status:

Accepted

---

# ADR-005

Decision:

Provider-independent architecture.

Reason:

Avoid dependence on OpenAI,
Anthropic,
Gemini,
or any single vendor.

Status:

Accepted

---

# ADR-006

Decision:

Embedding-based duplicate detection.

Reason:

Semantic similarity is core to memory analysis.

Status:

Accepted

---

# ADR-007

Decision:

No vector database.

Reason:

Unnecessary complexity for V1.

Status:

Accepted

---

# ADR-008

Decision:

Use modular pipeline architecture.

Reason:

Future MCP,
SDK,
and Runtime systems can reuse modules.

Status:

Accepted

---

# ADR-009

Decision:

Use deterministic heuristic categorization for V1.

Reason:

Keep the V1 CLI provider-independent,
local-first,
testable,
and explainable while preserving a module boundary for future local model classification.

Status:

Accepted

---

# Future Decisions

Append new decisions.

Never delete old decisions.

If superseded:

Mark as:

Superseded

and link replacement decision.