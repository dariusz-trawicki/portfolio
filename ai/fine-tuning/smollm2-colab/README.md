# LLM Fine-tuning Demo — SmolLM2-1.7B with QLoRA

Fine-tune a small language model on your own data using QLoRA on a free GPU — no cloud costs required.

## Overview

| | |
|---|---|
| **Model** | SmolLM2-1.7B-Instruct (HuggingFace) |
| **Method** | QLoRA (4-bit quantization + LoRA adapters) |
| **Hardware** | NVIDIA T4 15GB (Google Colab Free) |
| **Training time** | ~5 minutes (3 epochs)|
| **Cost** | $0 |

## Quick Start

1. Open `smollm2_finetuning_colab.ipynb` in Google Colab
2. Set runtime: `Runtime → Change runtime type → T4 GPU`
3. Edit your training data in **Cell 4**
4. Run all cells in order

## Stack

```
Dataset (list of dicts)
    ↓
format_prompt()         — chat template formatting
    ↓
SFTTrainer.train()      — supervised fine-tuning via LoRA adapters
    ↓
model.generate()        — inference test
    ↓
save_pretrained()       — save LoRA adapter or GGUF
```

| Library | Purpose |
|---|---|
| `unsloth` | 2x faster training, VRAM optimization |
| `transformers` | Model loading (HuggingFace) |
| `peft` | LoRA adapter management |
| `trl` | SFTTrainer — training loop |
| `bitsandbytes` | 4-bit quantization |
| `datasets` | Dataset handling |

## Dataset Format

Edit the `data` list in Cell 4. Each example needs three fields:

```python
{
    "instruction": "Answer briefly and clearly.",   # system prompt
    "input":       "What is LoRA?",                 # user question
    "output":      "LoRA is a fine-tuning method…"  # expected answer
}
```

Minimum recommended: **50–100 examples** for meaningful fine-tuning.

## Key Parameters

| Parameter | Default | Notes |
|---|---|---|
| `max_seq_length` | 512 | Max tokens per example |
| `load_in_4bit` | True | QLoRA — uses ~4GB VRAM |
| `r` | 16 | LoRA rank — higher = more params trained |
| `num_train_epochs` | 3 | Passes through dataset |
| `learning_rate` | 2e-4 | Standard for LoRA fine-tuning |
| `per_device_train_batch_size` | 2 | Increase if VRAM allows |
| `gradient_accumulation_steps` | 4 | Effective batch size = 2×4 = 8 |

## Output Options

**LoRA adapter only (~50MB)** — lightweight, requires base model to run:
```python
model.save_pretrained("smollm2-finetuned-lora")
```

**GGUF (merged model)** — ready for mistral.rs or Ollama:
```python
model.save_pretrained_gguf("smollm2-finetuned", tokenizer, quantization_method="q4_k_m")
```

## Notes

- Colab Free sessions disconnect after ~3–4 hours — save your adapter before that
- T4 has 15GB VRAM; QLoRA uses ~4–6GB leaving room for the KV cache
