# Fine-tuning Llama-PLLuM-8B-chat — QLoRA

Minimalny pipeline fine-tuningu QLoRA dla **PLLuM** (`Llama-PLLuM-8B-chat`) — polskiego otwartego modelu językowego — uruchamiany na GPU T4 (Kaggle).

---

## Stos technologiczny

| Komponent | Biblioteka / Model |
|---|---|
| Model bazowy | `CYFRAGOVPL/Llama-PLLuM-8B-chat` |
| Kwantyzacja | 4-bitowe QLoRA via [Unsloth](https://github.com/unslothai/unsloth) |
| Trening | `trl` `SFTTrainer` + `SFTConfig` |
| Rank LoRA | r=16, alpha=16, dropout=0.0 |
| Trenowalne parametry | ~42M / 8B (0.52%) |
| Środowisko | Kaggle: GPU T4 x 2  |
| Czas treningu | ~5 min (1 epoka, mały dataset) |

---

## O PLLuM

PLLuM to rodzina dużych modeli językowych wyspecjalizowanych w języku polskim, opracowana przez [konsorcjum HIVE AI](https://pllum.org.pl) oraz Ministerstwo Cyfryzacji.

`Llama-PLLuM-8B-chat` bazuje na **Llama 3.1-8B**, opublikowanym na licencji **Llama 3.1** (otwarta, dozwolony użytek komercyjny), i był dalej pretrenowany na ~30 miliardach tokenów polskiego tekstu.

### Szablon

`Llama-PLLuM-8B-chat` używa **szablonu czatu Llama 3**:

```
# PLLuM / Llama 3:
<|begin_of_text|><|start_header_id|>system<|end_header_id|>

{system}<|eot_id|><|start_header_id|>user<|end_header_id|>

{user}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

{assistant}<|eot_id|>

# ChatML (błędnie dla PLLuM):
<|im_start|>system
{system}<|im_end|>
```

---

## Szybki start

### Kaggle

1. [kaggle.com](https://www.kaggle.com) → **New Notebook**
2. Settings → Accelerator → **GPU T4 x2**
3. Wgrywamy `pllum-8b-finetuning.ipynb`:
  - `File > Import Notebook`
4. **Run All**


---

## Struktura notebooka

| Komórka | Opis |
|---|---|
| 1 | Instalacja zależności |
| 2 | Sprawdzenie GPU (`nvidia-smi`) |
| 3 | Ładowanie modelu + zastosowanie adapterów LoRA |
| 4 | Przygotowanie datasetu (format Llama 3) |
| 5 | Trening z `SFTTrainer` |
| 6 | Test fine-tunowanego modelu |


---

## Wymagania pamięci GPU

| Etap | VRAM |
|---|---|
| Model (4-bit) | ~5.5 GB |
| Adaptery LoRA | ~0.2 GB |
| Narzut treningu | ~1–2 GB |
| **Łącznie** | **~7 GB** |


---

## Licencja

- **Model:** [Licencja społecznościowa Llama 3.1](https://huggingface.co/meta-llama/Llama-3.1-8B/blob/main/LICENSE) — otwarta, dozwolony użytek komercyjny
- **Notebook:** MIT

---

## Źródła

- [PLLuM na HuggingFace](https://huggingface.co/CYFRAGOVPL)
- [Artykuł PLLuM (arXiv:2511.03823)](https://arxiv.org/abs/2511.03823)
- [Unsloth](https://github.com/unslothai/unsloth)
- [Dokumentacja TRL SFTTrainer](https://huggingface.co/docs/trl/sft_trainer)
