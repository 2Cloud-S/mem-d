---
pretty_name: PERMA Benchmark
language:
- en
license: apache-2.0
tags:
- agent
- personalization
- memory
size_categories:
- 1K<n<10K
---

# PERMA: Benchmarking Personalized Memory Agents

[![GitHub](https://img.shields.io/badge/GitHub-Repository-blue.svg)](https://github.com/PolarisLiu1/PERMA)
[![Paper](https://img.shields.io/badge/arXiv-2603.23231-b31b1b.svg)](https://arxiv.org/abs/2603.23231)

## TL;DR

PERMA is a benchmark for evaluating **personalized memory agents** in long-horizon conversations where user preferences evolve over time.  
Instead of static retrieval, models must track **event-driven preference evolution** and maintain persona consistency under realistic interaction noise.

This dataset supports two complementary evaluation protocols:

- **Multiple-choice evaluation** for granular capability probing (task completion, preference consistency, informational confidence).
- **Interactive evaluation** for multi-turn task success in realistic assistant workflows.

---

## 🚀 Quick Start & Evaluation

If you want to evaluate your own personalized memory agent, we provide full evaluation scripts in our official GitHub repository. 

**Repository:** [https://github.com/PolarisLiu1/PERMA](https://github.com/PolarisLiu1/PERMA)

The repository includes code to run both the Multiple-Choice Question (MCQ) probing and the interactive evaluation. Please refer to the `README.md` in the GitHub repository for specific command-line instructions, environment setup, and baseline implementations.

---

## 🛠️ Extending the Dataset (Data Generation)

PERMA is constructed based on seed datasets, making it highly extensible. If you want to expand the dataset for training purposes, such as generating more dialogue data or using different LLMs (e.g., Gemini, DeepSeek), you can easily do so.

The code and pipelines for generating additional synthetic data are available in our GitHub repository.

---

## Supported Tasks

- Personalized assistant response generation under evolving user preferences.
- Multiple-choice QA over long dialogue history and dynamic persona states.
- Memory retrieval and preference grounding in realistic task environments.

## Dataset Structure

The dataset is organized as:

- `WildChat-1M/`: style source slices used for conversational style alignment.
- `profile/`: user preference profiles and task metadata per user.
- `tasks/`: benchmark task instances with long context dialogues and checkpoints.
- `evaluation/`: evaluation artifacts and meta files for single-domain and multi-domain settings.

## Data Instances

### 1) Profile files

`profile/<user_id>/profile.json` contains structured affinities, for example:

- domain preferences (e.g., Flights, Hotels, Books, Media, Events)
- fine-grained slots (e.g., seat preference, preferred airline, reading format)

### 2) Task files

`tasks/<user_id>/input_data_*.json` includes:

- `task_id`, `task_goal`, `relevant_domain`
- long `context` consisting of temporally ordered user-assistant dialogues
- checkpoints for probing memory and preference consistency

### 3) Evaluation files

`evaluation/<user_id>/meta/overall/*.json` typically includes:

- `question`, `task_description`, `task_goal`
- candidate `options` for MCQ evaluation
- `gold_label`

## Data Splits

The PERMA benchmark is organized by task settings (single-domain / multi-domain, clean / noisy, and temporal checkpoints) rather than a single fixed train/validation/test convention.

Users can construct protocol-specific splits based on:

- task type (SD/MD) - Single-domain/Multi-domain
- temporal stage (`*_1`, `*_2`, `*_3`)
- noise setting

## Dataset Creation

### Curation Rationale

PERMA is built to test whether memory-enabled agents can:

- track evolving user preferences over long timelines,
- remain robust under realistic query noise and context switching,
- preserve persona consistency while completing practical assistant tasks.

### Source Data

- Conversational style alignment is inspired by WildChat slices in `WildChat-1M/`.
- Structured preference profiles and event timelines are used to generate task contexts.
- Evaluation artifacts are produced to support both MCQ probing and interactive success-rate evaluation.

## Considerations for Using the Data

### Intended Use

- Benchmarking memory systems and LLM agents for personalized assistance.
- Research on long-context preference tracking and persona consistency.
- Evaluation of retrieval-memory tradeoffs (quality vs. search cost/time).

## Licensing Information

This dataset is released under the **Apache-2.0** license.

## Citation

```bibtex
@misc{liu2026permabenchmarkingpersonalizedmemory,
  title={PERMA: Benchmarking Personalized Memory Agents via Event-Driven Preference and Realistic Task Environments},
  author={Shuochen Liu and Junyi Zhu and Long Shu and Junda Lin and Yuhao Chen and Haotian Zhang and Chao Zhang and Derong Xu and Jia Li and Bo Tang and Zhiyu Li and Feiyu Xiong and Enhong Chen and Tong Xu},
  year={2026},
  eprint={2603.23231},
  archivePrefix={arXiv},
  primaryClass={cs.AI},
  url={https://arxiv.org/abs/2603.23231}
}
```

## Acknowledgement
We sincerely thank [PersonaLens](https://huggingface.co/datasets/AmazonScience/PersonaLens), [WildChat](https://wildchat.allen.ai) and [MemOS](https://github.com/MemTensor/MemOS) for their valuable work. Their pioneering work has provided important foundations for our research.