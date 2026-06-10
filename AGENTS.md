# AGENTS.md

## Project

Mem-D

Memory Intelligence for AI Systems

---

## Mission

Help developers understand what exists inside agent memory.

Mem-D analyzes memory.

Mem-D does not manage memory.

---

## Current Version

V1

CLI Only

---

## Product Scope

Supported:

- Parsing
- Categorization
- Embeddings
- Similarity Analysis
- Duplicate Clustering
- Metrics
- Reporting

Not Supported:

- MCP
- SDK
- Dashboard
- Cloud
- Memory Modification

---

## Core Principle

The product answers:

"What is inside memory?"

The product does not answer:

"What should an agent retrieve?"

---

## Architecture

Parser
↓
Normalizer
↓
Categorizer
↓
Embedder
↓
Similarity
↓
Clustering
↓
Metrics
↓
Reporter

---

## Rules

1. Maintain modular architecture.

2. Avoid vendor lock-in.

3. Prefer local inference.

4. Keep functionality explainable.

5. Respect data contracts.

6. Keep V1 small.

---

## Current Goal

Deliver:

memd analyze memory.json

with meaningful memory insights.

Anything outside this goal should be considered out-of-scope.