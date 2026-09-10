# vLLM Serving Demo

A minimal, self-contained demo showing how to deploy and serve a local LLM using [vLLM](https://github.com/vllm-project/vllm) — from offline inference to a running OpenAI-compatible API server, on a single free-tier GPU.

## What this demonstrates

- Installing and running vLLM in a resource-constrained environment (single T4 GPU, Google Colab)
- Offline batch inference with vLLM's `LLM` class
- Deploying a local model as an OpenAI-compatible API server (`vllm serve`)
- Continuous batching: handling multiple concurrent requests efficiently
- Token streaming, matching the UX of hosted chat APIs
- Practical constraints and trade-offs of running small open-weight models on limited hardware

## Why this matters

Public-sector and regulated environments often cannot send data to third-party LLM APIs. Self-hosting a model with an efficient serving engine like vLLM offers a way to keep data on-premises, control costs, and tune resource usage — while still exposing a standard, drop-in-compatible API (OpenAI's `/v1/chat/completions` format) that existing tooling can consume without code changes.

## Requirements

- Python 3.10–3.13
- An NVIDIA GPU (demo tested on a Colab T4, 16GB VRAM)
- Internet access (to download model weights from Hugging Face on first run)

## Model used

`Qwen/Qwen2.5-1.5B-Instruct` — a small instruction-tuned model, chosen for fast load times and low VRAM footprint, suitable for demoing the *serving infrastructure* rather than model quality. In a production setting, model choice would depend on task, language, and hardware budget (e.g. a larger model, a quantized variant, or a Polish-language model such as Bielik for Polish-specific use cases).

## Setup

```bash
pip install vllm
```

On Colab, also remove `torchaudio` and restart the runtime — it isn't needed for text-only serving and its bundled version can conflict with the `torch` version vLLM installs (see Troubleshooting):

```bash
pip uninstall -y torchaudio
```

> Restart the runtime after this step. In the first cell after restart, before importing `vllm`, add:
> ```python
> import transformers.utils.import_utils as iu
> iu.is_torchaudio_available = lambda: False
> ```

## Usage

### 1. Offline inference

```python
from vllm import LLM, SamplingParams

llm = LLM(model="Qwen/Qwen2.5-1.5B-Instruct")
params = SamplingParams(temperature=0.3, max_tokens=150)

messages = [{"role": "user", "content": "Explain in two sentences what photosynthesis is."}]
output = llm.chat(messages, params)
print(output[0].outputs[0].text)
```

> In Jupyter/Colab, run this via a script file (`python script.py`) rather than directly in a notebook cell — vLLM's engine expects a real OS-level `stdout`, which notebook kernels don't provide.

### 2. Start the API server

```bash
vllm serve Qwen/Qwen2.5-1.5B-Instruct \
  --port 8000 \
  --gpu-memory-utilization 0.7
```

Wait for the `/health` endpoint to return `200 OK` before sending requests — model loading takes 1–3 minutes.

### 3. Query it like any OpenAI-compatible endpoint

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")

response = client.chat.completions.create(
    model="Qwen/Qwen2.5-1.5B-Instruct",
    messages=[{"role": "user", "content": "Hi, who are you?"}]
)
print(response.choices[0].message.content)
```

### 4. Concurrent requests (continuous batching)

```python
from concurrent.futures import ThreadPoolExecutor

prompts = [
    "What is the capital of Poland?",
    "Name three planets in the Solar System.",
    "What is an algorithm?",
    "Write one sentence about coffee.",
]

def ask(prompt):
    r = client.chat.completions.create(
        model="Qwen/Qwen2.5-1.5B-Instruct",
        messages=[{"role": "user", "content": prompt}]
    )
    return r.choices[0].message.content

with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(ask, prompts))
```

vLLM packs concurrent requests into shared GPU batches instead of processing them strictly one-by-one, improving aggregate throughput on the same hardware.

### 5. Streaming

```python
stream = client.chat.completions.create(
    model="Qwen/Qwen2.5-1.5B-Instruct",
    messages=[{"role": "user", "content": "Tell a short story about a cat."}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

## Key vLLM concepts shown

| Concept | Where it appears |
|---|---|
| **PagedAttention** | Underlying KV-cache memory management (automatic, visible in startup logs) |
| **Continuous batching** | Concurrent request handling (step 4) |
| **OpenAI-compatible serving** | `vllm serve` + `openai` client (steps 2–3) |
| **Resource tuning** | `--gpu-memory-utilization`, model size choice |
| **Chat templates** | `llm.chat()` vs raw `llm.generate()` |

## Known limitations of this demo

- The 1.5B model is small and occasionally produces factually inaccurate output, especially in Polish — this is a model-quality limitation, not an infrastructure issue. A production deployment would use a larger or fine-tuned model matched to the target language and task.
- Single-GPU, single-node setup only; no tensor/pipeline parallelism, quantization, or speculative decoding demonstrated (all supported by vLLM, out of scope for this minimal demo).

## Cleanup

```python
server_process.terminate()
server_process.wait()
```
