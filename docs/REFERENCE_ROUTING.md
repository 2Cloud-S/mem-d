# Reference Routing Rules

Version: V1

Status: Active

Purpose:

Determine which references should be consulted for a given implementation task.

References exist to provide patterns, tradeoffs, and design insights.

References must not override:

1. PROJECT_RULES.md
2. PRD.md
3. TRD.md
4. Architecture.md
5. Data_Contracts.md

---

# Core Rule

Before implementing any feature:

Ask:

1. What problem am I solving?
2. Which reference best represents this problem?
3. What principle should be extracted?
4. What unnecessary complexity should be avoided?

---

# Memory Understanding Problems

Use when working on:

* Categorization
* Memory semantics
* Memory types
* Long-term memory concepts
* Importance scoring
* Reflection systems

Consult:

Generative Agents
https://arxiv.org/abs/2304.03442

MemGPT
https://arxiv.org/abs/2310.08560

Letta
https://docs.letta.com/

Mem0
https://docs.mem0.ai/overview

Extract:

* Memory categorization patterns
* Memory importance concepts
* Reflection mechanisms
* Memory lifecycle concepts

Avoid:

* Implementing full memory systems
* Building retrieval frameworks
* Recreating MemGPT

---

# Embedding Problems

Use when working on:

* Semantic similarity
* Duplicate detection
* Vector generation
* Embedding evaluation

Consult:

Sentence Transformers
https://www.sbert.net/

BGE Models
https://huggingface.co/BAAI

Qwen
https://qwenlm.github.io/

Extract:

* Embedding best practices
* Similarity methods
* Local inference patterns

Avoid:

* Vendor lock-in
* External embedding APIs

---

# Similarity Problems

Use when working on:

* Duplicate detection
* Semantic matching
* Cluster generation

Consult:

Sentence Transformers
https://www.sbert.net/

BGE Models
https://huggingface.co/BAAI

Extract:

* Cosine similarity
* Semantic comparison methods
* Similarity thresholds

Avoid:

* Keyword matching approaches
* Rule-only systems

---

# Clustering Problems

Use when working on:

* Duplicate groups
* Cluster creation
* Compression opportunities

Consult:

Scikit-Learn Clustering
https://scikit-learn.org/stable/modules/clustering.html

Sentence Transformers Clustering Examples
https://www.sbert.net/examples/applications/clustering/README.html

Extract:

* DBSCAN
* HDBSCAN
* Agglomerative clustering

Avoid:

* Graph databases
* Distributed systems

---

# Metrics Problems

Use when working on:

* Memory metrics
* Health indicators
* Analysis signals
* Aggregations

Consult:

OpenTelemetry
https://opentelemetry.io/docs/

Datadog Engineering
https://www.datadoghq.com/blog/engineering/

Grafana
https://grafana.com/docs/

Extract:

* Signal design
* Useful metrics
* Aggregation patterns

Avoid:

* Vanity metrics
* Metrics without actionability

---

# Reporting Problems

Use when working on:

* CLI reports
* JSON reports
* Markdown reports
* User-facing outputs

Consult:

Sentry Engineering
https://blog.sentry.io/engineering/

Datadog Engineering
https://www.datadoghq.com/blog/engineering/

PostHog Docs
https://posthog.com/docs

Extract:

* Actionable reporting
* Clear signal presentation
* Noise reduction

Avoid:

* Fancy visualizations
* Dashboard-first thinking

---

# CLI Design Problems

Use when working on:

* Command structure
* Terminal UX
* Tool ergonomics

Consult:

DuckDB
https://duckdb.org/docs/

ripgrep
https://github.com/BurntSushi/ripgrep

uv
https://docs.astral.sh/uv/

Git CLI
https://git-scm.com/docs

Extract:

* Developer-first UX
* Fast workflows
* Simple commands

Avoid:

* Excessive configuration
* Hidden behavior

---

# Documentation Problems

Use when working on:

* Docs structure
* Examples
* Guides

Consult:

DuckDB Docs
https://duckdb.org/docs/

PostHog Docs
https://posthog.com/docs

Grafana Docs
https://grafana.com/docs/

Extract:

* Example-driven docs
* Discoverability
* Clear structure

Avoid:

* Marketing language
* Excessive abstraction

---

# Website Design Problems

Use when working on:

* Landing page
* Product presentation
* Developer trust

Consult:

DuckDB
https://duckdb.org/

Tailscale
https://tailscale.com/

Observable
https://observablehq.com/

PostHog
https://posthog.com/

Extract:

* Infrastructure-product aesthetics
* Product-first presentation
* Technical credibility

Avoid:

* Purple gradients
* Neon AI aesthetics
* Generic SaaS layouts
* Fake dashboards
* AI buzzword marketing

---

# Open Source Strategy Problems

Use when working on:

* Licensing
* Community building
* Open-core strategy

Consult:

Open Core Ventures
https://opencoreventures.com/

PostHog Handbook
https://posthog.com/handbook

Extract:

* Open-core models
* Community growth
* Commercial layering

Avoid:

* Open-sourcing everything
* Closed-source from day one

---

# MCP Problems

Use when working on:

* Tool integrations
* Future MCP server
* Protocol design

Consult:

Model Context Protocol
https://modelcontextprotocol.io/introduction

Extract:

* Protocol contracts
* Resource structures
* Tool definitions

Avoid:

* Creating custom protocols

---

# Future Decay Engine Problems

Use when working on:

* Adaptive decay
* Memory evolution
* Forgetting systems
* Lifecycle management

Consult:

Adaptive Memory Decay Engine
https://arxiv.org/pdf/2606.05405

Memory Lifecycle Research
https://arxiv.org/pdf/2509.19783

Memory Evolution Research
https://arxiv.org/pdf/2511.17332

Extract:

* Decay mechanisms
* Memory strength models
* Lifecycle management

Avoid:

* Time-only expiration
* Simple TTL approaches

---

# Reference Priority

If references conflict:

Priority:

1. PROJECT_RULES.md
2. PRD.md
3. TRD.md
4. Architecture.md
5. Data_Contracts.md
6. External References

External references inform decisions.

Project documents define decisions.

---

# Final Principle

References are used to improve judgment.

References are not implementation instructions.

Always choose the simplest solution that satisfies the current version requirements.
