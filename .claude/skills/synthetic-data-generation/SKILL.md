---
name: synthetic-data-generation
description: Generate synthetic data using sdg_hub with composable blocks and YAML flows. Use when the user wants to create training datasets, generate QA pairs, run data generation pipelines, build custom flows, produce synthetic data from documents, use agent frameworks for data generation, or distill MCP tool-use traces. Supports pre-built flows, custom Python scripts, and YAML flow authoring with 20+ blocks, agent connectors (Langflow, LangGraph), MCP tool-use, and 100+ LLM providers via LiteLLM.
---

# Synthetic Data Generation with SDG Hub

Generate synthetic data using composable blocks and flows. Blocks are processing units that transform datasets; flows chain blocks into pipelines defined in YAML.

Core concept: `dataset -> Block_1 -> Block_2 -> Block_3 -> enriched_dataset`

## Phase 1: Project Bootstrap

When the user needs to set up sdg_hub from scratch, handle **all** of the following steps autonomously without asking the user for input. The user should not need to make any decisions during bootstrap.

### Step 1: Check Python version

```bash
python3 --version
```

Require Python 3.10+. If not available, tell the user to install it and stop.

### Step 2: Install sdg_hub

```bash
# Prefer uv if available
if command -v uv &>/dev/null; then
    uv pip install sdg-hub
else
    pip install sdg-hub
fi
```

### Step 3: Verify installation

```bash
python3 -c "from sdg_hub import FlowRegistry, BlockRegistry; FlowRegistry.discover_flows(); print('sdg_hub installed successfully'); print(f'{len(FlowRegistry.list_flows())} flows available')"
```

### Step 4: Set up workspace

Create a working directory with a `data/` folder for input documents and an `output/` folder for results:

```bash
mkdir -p data output
```

### Step 5: Check for LLM API keys

Check which API keys are already available in the environment:

```bash
python3 -c "
import os
providers = {
    'OPENAI_API_KEY': 'OpenAI',
    'ANTHROPIC_API_KEY': 'Anthropic',
    'TOGETHER_API_KEY': 'Together AI',
    'GROQ_API_KEY': 'Groq',
    'GEMINI_API_KEY': 'Google Gemini',
}
found = {name: var for var, name in providers.items() if os.environ.get(var)}
if found:
    print('Available LLM providers: ' + ', '.join(found.values()))
else:
    print('No LLM API keys found in environment.')
    print('Set one before generating data, e.g.: export OPENAI_API_KEY=sk-...')
"
```

If no API key is found, inform the user they need to set one before generation can proceed. Do NOT ask them to do it now -- just note it and continue.

After bootstrap, print a summary of what was set up and tell the user they are ready to generate data.

---

## Phase 2: Interactive Data Generation

This is the core workflow. When a user wants to generate synthetic data, follow these steps in order. **You drive the process** -- only ask the user for information that requires their domain knowledge.

### What you need from the user (and ONLY this)

1. **Where are their source documents?** A file path or directory (e.g., `./data/`, `~/docs/report.pdf`). Or a HuggingFace dataset name.
2. **What kind of data do they want?** Described in natural language (e.g., "QA pairs for training", "red-team prompts", "RAG evaluation questions").

Everything else -- flow selection, model configuration, dataset construction, validation, execution, and saving -- you handle autonomously.

### Step 1: Understand the user's goal

Ask the user two questions (combine into a single message):
- Where are the source documents or data?
- What kind of synthetic data should be generated?

If the user already provided this information in their initial message, skip asking and proceed directly.

### Step 2: Detect and load data sources

Scan the location the user provided. Handle these formats automatically:

```python
import pandas as pd
import os

path = "user_provided_path"

if os.path.isdir(path):
    # Scan directory for supported files
    files = []
    for root, dirs, filenames in os.walk(path):
        for f in filenames:
            if f.endswith(('.txt', '.md', '.csv', '.json', '.jsonl', '.parquet', '.pdf')):
                files.append(os.path.join(root, f))
    print(f"Found {len(files)} files")

    # Load based on file type
    if all(f.endswith('.csv') for f in files):
        df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    elif all(f.endswith(('.json', '.jsonl')) for f in files):
        df = pd.concat([pd.read_json(f, lines=f.endswith('.jsonl')) for f in files], ignore_index=True)
    elif all(f.endswith('.parquet') for f in files):
        df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    else:
        # Text files -- read content into a "document" column
        documents = []
        for f in files:
            with open(f) as fh:
                documents.append({"document": fh.read(), "source_file": os.path.basename(f)})
        df = pd.DataFrame(documents)

elif os.path.isfile(path):
    if path.endswith('.csv'):
        df = pd.read_csv(path)
    elif path.endswith('.parquet'):
        df = pd.read_parquet(path)
    elif path.endswith(('.json', '.jsonl')):
        df = pd.read_json(path, lines=path.endswith('.jsonl'))
    else:
        df = pd.DataFrame({"document": [open(path).read()]})
```

For HuggingFace datasets:
```python
from datasets import load_dataset
ds = load_dataset("dataset_name", split="train")
df = ds.to_pandas()
```

Tell the user what you found: number of rows, columns, and a brief preview.

### Step 3: Select the right flow

Match the user's stated goal to a pre-built flow. Use this decision table:

| User wants | Flow to use | Required columns |
|------------|-------------|------------------|
| QA pairs from documents | Knowledge Infusion (extractive summary variant) | `document` |
| Detailed QA with context | Knowledge Infusion (detailed summary variant) | `document` |
| Fact-based QA | Knowledge Infusion (key facts variant) | `document` |
| Direct QA without summarization | Knowledge Infusion (doc direct QA variant) | `document` |
| Text analysis / insights | Structured Text Insights Extraction | `text` |
| Red-team / adversarial prompts | Red Team Prompt Generation | `policy_concept`, `concept_definition`, pool columns |
| RAG evaluation questions | RAG Evaluation Dataset | depends on flow |
| MCP tool-use training data | MCP Server Distillation | `messages` |
| Spanish QA | Spanish Multi-Summary QA variants | `document` |
| Japanese QA | Japanese Multi-Summary QA | `document` |

```python
from sdg_hub import FlowRegistry

# Discover all flows
FlowRegistry.discover_flows()
flows = FlowRegistry.list_flows()

# Search by tag to narrow down
matching = FlowRegistry.search_flows(tag="qa-generation")

# Load the chosen flow
from sdg_hub import Flow
flow_path = FlowRegistry.get_flow_path("flow-name-or-id")
flow = Flow.from_yaml(flow_path)
flow.print_info()
```

If no pre-built flow matches, build a custom flow. See the "Custom Flows" section below.

Tell the user which flow you selected and why. Do NOT ask for confirmation unless the choice is ambiguous (e.g., the user's description could match multiple flows).

### Step 4: Prepare the dataset

Adapt the user's data to match the flow's required schema:

```python
# Check what the flow needs
reqs = flow.get_dataset_requirements()
if reqs:
    required = reqs.required_columns
    print(f"Flow requires: {required}")
    print(f"Dataset has: {list(df.columns)}")

# Rename columns if needed (e.g., user has "text" but flow needs "document")
column_mapping = {}
if "document" in required and "document" not in df.columns:
    # Try common alternatives
    for alt in ["text", "content", "body", "passage"]:
        if alt in df.columns:
            column_mapping[alt] = "document"
            break

if column_mapping:
    df = df.rename(columns=column_mapping)

# Validate
errors = flow.validate_dataset(df)
if errors:
    print(f"Validation issues: {errors}")
```

Handle common mismatches silently. Only ask the user if a required column genuinely cannot be inferred from their data.

### Step 5: Configure the model

```python
import os

# Auto-detect available API keys
if os.environ.get("OPENAI_API_KEY"):
    model = "openai/gpt-4o-mini"
    api_key = os.environ["OPENAI_API_KEY"]
elif os.environ.get("ANTHROPIC_API_KEY"):
    model = "anthropic/claude-sonnet-4-6"
    api_key = os.environ["ANTHROPIC_API_KEY"]
elif os.environ.get("TOGETHER_API_KEY"):
    model = "together_ai/meta-llama/Llama-3-70b-chat-hf"
    api_key = os.environ["TOGETHER_API_KEY"]
elif os.environ.get("GROQ_API_KEY"):
    model = "groq/llama3-70b-8192"
    api_key = os.environ["GROQ_API_KEY"]
elif os.environ.get("GEMINI_API_KEY"):
    model = "gemini/gemini-pro"
    api_key = os.environ["GEMINI_API_KEY"]
else:
    # Check flow's default recommendation
    default = flow.get_default_model()
    print(f"No API key found. Flow recommends: {default}")
    print("Set an API key: export OPENAI_API_KEY=sk-...")
    # STOP and ask user to set an API key

flow.set_model_config(model=model, api_key=api_key)
```

If no API key is available, this is the ONE point where you must stop and ask the user to provide one. Everything else is automated.

### Step 6: Dry run

Always run a dry run before the full generation. Do NOT skip this step.

```python
dry = flow.dry_run(df, sample_size=min(2, len(df)))

if dry["execution_successful"]:
    print("Dry run succeeded!")
    for block in dry["blocks_executed"]:
        print(f"  {block['block_name']}: {block['execution_time_seconds']:.2f}s")
else:
    print("Dry run failed -- investigating...")
    # Check error details and fix
```

If the dry run fails, diagnose and fix the issue (common causes: missing columns, bad model config, template errors). Do NOT ask the user to fix it -- handle it yourself by adjusting the dataset or configuration.

### Step 7: Generate

```python
result = flow.generate(
    df,
    checkpoint_dir="./output/checkpoints",
    save_freq=50,
    max_concurrency=5,
)

print(f"Generated {len(result)} rows")
print(f"Output columns: {list(result.columns)}")
```

### Step 8: Save and present results

Save in multiple formats so the user has options:

```python
# Save as JSONL (most portable)
output_path = "./output/generated_data.jsonl"
result.to_json(output_path, orient="records", lines=True)

# Also save as Parquet (efficient for large datasets)
result.to_parquet("./output/generated_data.parquet")

print(f"Saved {len(result)} rows to {output_path}")
```

Show the user a preview of the generated data (first 3-5 rows) and a summary of what was produced (row count, columns, any quality notes).

---

## Custom Flows

When no pre-built flow matches the user's needs, build one. Follow this process:

### Step 1: Define the data contract

Clarify inputs and outputs before writing any YAML:
- What columns does the input data have?
- What columns should the output contain?
- What transformation needs to happen?

### Step 2: Write the flow YAML

Build incrementally -- start with one block, test, add the next.

```yaml
# flow.yaml
metadata:
  name: "My QA Flow"
  version: "0.1.0"
  author: "Your Name"
  description: "Generate QA pairs from documents"
  dataset_requirements:
    required_columns: ["document"]

blocks:
  - block_type: "PromptBuilderBlock"
    block_config:
      block_name: "build_prompt"
      input_cols: ["document"]
      output_cols: "messages"
      prompt_config_path: "prompts/qa.yaml"

  - block_type: "LLMChatBlock"
    block_config:
      block_name: "generate"
      input_cols: "messages"
      output_cols: "raw_response"
      temperature: 0.7
      async_mode: true

  - block_type: "TagParserBlock"
    block_config:
      block_name: "parse"
      input_cols: "raw_response"
      output_cols: ["question", "response"]
      start_tags: ["<question>", "<answer>"]
      end_tags: ["</question>", "</answer>"]
```

### Step 3: Create prompt templates

```yaml
# prompts/qa.yaml (relative to flow.yaml)
- role: system
  content: |
    You generate question-answer pairs from documents.

- role: user
  content: |
    Generate one question and answer from this document.
    Use <question>...</question> and <answer>...</answer> tags.

    {document}
```

### Step 4: Test and iterate

```python
from sdg_hub import Flow
import pandas as pd

flow = Flow.from_yaml("flow.yaml")
flow.set_model_config(model="openai/gpt-4o-mini", api_key="sk-...")

df = pd.DataFrame({"document": ["Python was created by Guido van Rossum in 1991."]})

dry = flow.dry_run(df, sample_size=1)
if dry['execution_successful']:
    result = flow.generate(df)
    print(result[["document", "question", "response"]])
```

See `references/yaml_schema.md` for the complete YAML structure and `references/flow_patterns.md` for common patterns (quality filtering, parallel paths, multi-step extraction).

---

## Agent and MCP Pipelines

### Agent frameworks (Langflow, LangGraph)

Use `AgentBlock` to call external agent frameworks as pipeline steps:

```python
from sdg_hub.core.blocks.agent import AgentBlock

block = AgentBlock(
    block_name="my_agent",
    agent_framework="langflow",       # or "langgraph"
    agent_url="http://localhost:7860/api/v1/run/my-flow",
    agent_api_key="your-key",
    input_cols=["question"],
    output_cols=["agent_response"],
    extract_response=True
)

result = block.generate(dataset)
```

In YAML flows, configure agent blocks with `set_agent_config()`:

```python
flow = Flow.from_yaml("flow.yaml")
if flow.is_agent_config_required():
    flow.set_agent_config(
        agent_framework="langgraph",
        agent_url="http://localhost:8123",
        agent_api_key="your-key"
    )
```

### MCP tool-use distillation

`MCPAgentBlock` connects an LLM to a remote MCP server for agentic tool-use. The LLM calls tools in a loop, producing full traces for training data:

```yaml
- block_type: "MCPAgentBlock"
  block_config:
    block_name: "mcp_agent"
    input_cols: "messages"
    output_cols: "agent_trace"
    mcp_server_url: "http://localhost:3000/mcp"
    max_iterations: 10
```

See the pre-built `MCP Server Distillation` flow in `references/pre_built_flows.md` for a complete pipeline.

---

## Quick Reference

### Flow methods

```python
flow = Flow.from_yaml("flow.yaml")

# Model configuration
flow.set_model_config(model="...", api_key="...", blocks=["specific_block"])
flow.is_model_config_required()
flow.get_default_model()
flow.get_model_recommendations()

# Agent configuration
flow.set_agent_config(agent_framework="...", agent_url="...", agent_api_key="...")
flow.is_agent_config_required()

# Dataset validation
flow.validate_dataset(df)
flow.get_dataset_requirements()

# Execution
flow.dry_run(df, sample_size=2)
flow.generate(df, checkpoint_dir="./ckpt", save_freq=100, max_concurrency=5)

# Inspection
flow.print_info()
flow.to_yaml("output_flow.yaml")
```

### Block discovery

```python
from sdg_hub.core.blocks import BlockRegistry

BlockRegistry.discover_blocks()                    # Rich table of all blocks
BlockRegistry.list_blocks(category="llm")          # By category
BlockRegistry.list_blocks(grouped=True)            # Grouped by category
BlockRegistry.categories()                         # All categories
```

### Data I/O

```python
import pandas as pd

# Load
df = pd.read_csv("input.csv")
df = pd.read_parquet("input.parquet")
df = pd.read_json("input.jsonl", lines=True)

# From HuggingFace
from datasets import load_dataset
df = load_dataset("your_dataset", split="train").to_pandas()

# Save
result.to_parquet("output.parquet")
result.to_csv("output.csv", index=False)
result.to_json("output.jsonl", orient="records", lines=True)

# Push to HuggingFace Hub
from datasets import Dataset
Dataset.from_pandas(result).push_to_hub("username/dataset")
```

## Common Issues

**"Column X not found"** -- Input data is missing a required column. Run `flow.get_dataset_requirements()` to see what the flow expects, then check your DataFrame columns.

**Empty or null outputs** -- The LLM response didn't match the parser pattern. Check the raw LLM output before parsing, and adjust your prompt template or parser config.

**Rate limit errors** -- Reduce `max_concurrency` in `flow.generate()` or add `timeout` and `num_retries` to `set_model_config()`.

**Slow generation** -- Use `async_mode: true` on LLMChatBlock, increase `max_concurrency`, or use checkpointing to resume interrupted runs.

**Model not responding** -- Verify your model config works with a single-sample test:
```python
from sdg_hub.core.blocks import LLMChatBlock
block = LLMChatBlock(block_name="test", input_cols="messages", output_cols="r", model="...", api_key="...")
block(pd.DataFrame({"messages": [[{"role": "user", "content": "hello"}]]}))
```

## Reference Files

Detailed documentation for specific topics:

- `references/block_reference.md` -- All 20+ blocks with YAML configs and usage examples
- `references/pre_built_flows.md` -- Catalog of pre-built flows with inputs, outputs, and usage
- `references/model_configs.md` -- LLM provider configurations (OpenAI, Anthropic, vLLM, Ollama, etc.)
- `references/yaml_schema.md` -- Complete flow YAML structure and validation rules
- `references/flow_patterns.md` -- Common composition patterns (LLM chain, quality filtering, parallel paths, agent integration)
