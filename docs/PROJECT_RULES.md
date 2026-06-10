# Knowledge Management Rules

## Obsidian First Documentation

All project knowledge must be documented in the Obsidian vault.

Code is not considered documentation.

Documentation is a first-class artifact.

---

## What Must Be Saved

The following must always be documented:

### Architectural Decisions

Examples:

- Why a library was chosen
- Why a pattern was adopted
- Why a technology was rejected

Store in:

/docs/decisions/

---

### Research Findings

Examples:

- Paper analysis
- Competitive analysis
- Memory system discoveries

Store in:

/research/

---

### Project Learnings

Examples:

- Unexpected implementation issues
- Performance bottlenecks
- Design discoveries

Store in:

/knowledge/learnings/

---

### System Architecture Changes

Examples:

- New modules
- Pipeline changes
- Data contract modifications

Store in:

/architecture/

---

## What Must NOT Be Saved

Do not save:

- Temporary debugging logs
- Build outputs
- Stack traces
- Generated artifacts
- Repetitive information

---

## Memory Quality Rule

Every note must answer one of:

- What did we learn?
- Why was this decision made?
- What should future contributors know?

If none apply:

Do not create a note.

---

## Agent Responsibility

Before completing significant work:

1. Check if documentation must be updated.

2. Create or update relevant Obsidian notes.

3. Link related notes.

4. Preserve reasoning.