# Technical Requirements Document

## Project

Mem-D Analyze

Version 1

---

# Architecture

Memory File

↓

Parser

↓

Embedding Engine

↓

Categorization Engine

↓

Duplicate Detection Engine

↓

Report Generator

↓

CLI Output

---

# Component 1

Parser

Inputs:

JSON

TXT

CSV

Output:

Unified Memory Record

{
"id":"",
"content":""
}

---

# Component 2

Embedding Engine

Purpose:

Semantic understanding.

Model:

BGE Small

or

Qwen Embedding

Local inference preferred.

---

# Component 3

Categorization Engine

Categories:

Preference

Fact

Task

Goal

Temporary

Relationship

Unknown

Implementation:

Prompt-based classification.

---

# Component 4

Duplicate Detection

Method:

Embedding similarity

Cosine similarity

Threshold clustering

Output:

Duplicate groups

---

# Component 5

Report Generator

Metrics:

Total Memories

Duplicate Percentage

Category Distribution

Compression Opportunity

---

# Storage

None required.

Analysis performed in memory.

Optional:

Export JSON report.

---

# Interface

CLI only.

Command:

memd analyze memory.json

---

# Dependencies

Python

Typer

Sentence Transformers

Pydantic

NumPy

Scikit-Learn

---

# Non-Goals

No MCP

No SDK

No Dashboard

No Graph Database

No Decay Engine

No Reinforcement Learning

No Memory Storage

No Enterprise Features

---

# Success Definition

Analyze 10,000 memories locally.

Generate useful duplicate clusters.

Produce understandable reports.

Validate demand for memory intelligence.
