# Get Started

Generate synthetic data in two steps using Claude Code as your AI assistant.

## Prerequisites

- **Python 3.10+**
- **An LLM API key** (OpenAI, Anthropic, Together AI, Groq, or any of [100+ providers](https://docs.litellm.ai/docs/providers))
- **Claude Code** ([install guide](https://docs.anthropic.com/en/docs/claude-code/overview))

## Step 1: Bootstrap

Run this command to install sdg_hub, set up your workspace, and configure the Claude Code skill -- all automatically:

```bash
export OPENAI_API_KEY="sk-..."  # or ANTHROPIC_API_KEY, TOGETHER_API_KEY, etc.

curl -fsSL https://raw.githubusercontent.com/Red-Hat-AI-Innovation-Team/sdg_hub/main/scripts/bootstrap.sh \
  | claude --dangerously-skip-permissions
```

This installs `sdg-hub`, creates `data/` and `output/` directories, and verifies everything works. No manual steps required.

## Step 2: Generate data

Start a Claude session and describe what you need. Claude handles flow selection, model configuration, validation, and execution:

```bash
claude
```

Then tell Claude what you want:

| What you say | What happens |
|---|---|
| "Generate QA pairs from the documents in ./data/" | Selects a knowledge infusion flow, loads your documents, generates question-answer pairs |
| "Create a red-team evaluation dataset" | Uses the red-team prompt generation flow to produce adversarial test prompts |
| "Build a RAG evaluation dataset from my knowledge base" | Runs the RAG evaluation flow to create ground-truth QA for retrieval testing |
| "Extract structured insights from these articles" | Runs text analysis to produce summaries, keywords, entities, and sentiment |

Claude will:

1. Scan your data directory and load supported formats (CSV, JSON, JSONL, Parquet, text, Markdown)
2. Select the right pipeline from 14+ built-in flows
3. Auto-configure the LLM using your API key from the environment
4. Run a dry run to validate the pipeline
5. Execute the full generation with checkpointing
6. Save results to `./output/` as JSONL and Parquet

## Supported LLM providers

SDG Hub uses [LiteLLM](https://docs.litellm.ai/docs/providers) and works with any provider. Set the corresponding environment variable:

| Provider | Environment variable |
|---|---|
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Together AI | `TOGETHER_API_KEY` |
| Groq | `GROQ_API_KEY` |
| Google Gemini | `GEMINI_API_KEY` |
| Local (vLLM, Ollama) | No key needed -- configure the endpoint URL |

## Available pipelines

| Pipeline | Use case |
|---|---|
| Knowledge Infusion (4 variants) | QA pair generation from documents via extractive summary, detailed summary, key facts, or direct QA |
| Structured Text Insights | Multi-faceted text analysis (summary, keywords, entities, sentiment) |
| Red Team Prompt Generation | Adversarial prompt creation for safety testing |
| RAG Evaluation | Ground-truth QA generation for retrieval-augmented generation evaluation |
| MCP Distillation | Tool-use training data from MCP server interactions |
| Multilingual QA | Spanish and Japanese knowledge infusion variants |

## Want more control?

If you prefer a manual setup or want to build custom pipelines:

- [Installation](installation.md) -- install options, optional dependencies, development setup
- [Quick Start](quickstart.md) -- step-by-step walkthrough of the Python API
- [Core Concepts](concepts.md) -- blocks, flows, registries, and how they connect
- [Built-in Flows](flows/built-in-flows.md) -- detailed reference for all pre-built pipelines
- [Custom Flows](flows/custom-flows.md) -- author your own YAML flow pipelines
