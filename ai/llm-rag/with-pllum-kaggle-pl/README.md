# 🇵🇱 Demo RAG z Llama-PLLuM-8B-chat

Minimalny pipeline Retrieval-Augmented Generation (RAG) oparty na **PLLuM** — polskim otwartym modelu językowym — uruchamiany na GPU T4 (Kaggle).

## Proces

Na podstawie zestawu polskojęzycznych dokumentów pipeline odpowiada na pytania w języku naturalnym, wyszukując najbardziej trafne fragmenty i generując ugruntowaną, cytowaną odpowiedź po polsku.

```
Dokumenty → podział → embeddingi → indeks FAISS
Pytanie   → embedding → wyszukiwanie podobieństwa → top-k fragmentów
                                                          ↓
                                          Szablon promptu PLLuM RAG
                                                          ↓
                                          Llama-PLLuM-8B-chat
                                                          ↓
                                   Odpowiedź z cytatami [0][1]…
```

Jeśli odpowiedź nie zostanie znaleziona w dostarczonych dokumentach, model jawnie odpowiada:
> *„Nie udało mi się odnaleźć odpowiedzi na pytanie."*

---

## Stos technologiczny

| Komponent | Biblioteka / Model |
|---|---|
| LLM | `CYFRAGOVPL/Llama-PLLuM-8B-chat` |
| Kwantyzacja | 4-bitowe QLoRA via [Unsloth](https://github.com/unslothai/unsloth) |
| Embeddingi | `intfloat/multilingual-e5-base` |
| Baza wektorowa | FAISS (lokalna) |
| Ładowanie dokumentów | LangChain + PyPDF |
| Środowisko uruchomieniowe | Kaggle: GPU T4 x 2 |

---

## O PLLuM

PLLuM to rodzina dużych modeli językowych wyspecjalizowanych w języku polskim, opracowana przez [konsorcjum HIVE AI](https://pllum.org.pl) oraz Ministerstwo Cyfryzacji.

`Llama-PLLuM-8B-chat` bazuje na **Llama 3.1-8B**, opublikowanym na licencji **Llama 3.1** (otwarta, dozwolony użytek komercyjny), i był dalej pretrenowany na ~30 miliardach tokenów polskiego tekstu.

> **Uwaga:** Szablon promptu RAG jest celowo utrzymany w języku polskim. PLLuM był fine-tunowany dokładnie na tym szablonie i generuje znacznie lepsze cytaty oraz odmowy, gdy instrukcje pozostają po polsku. Pytania można zadawać po angielsku — model rozumie oba języki.

---

## Szybki start

### Kaggle

1. Przejdź na kaggle.com → **New Notebook**
2. Settings → Accelerator → **GPU T4 x2**
3. Wgrywamy `pllum_rag_pl.ipynb`
  - `File > Import Notebook`
4. **Run All**

---

## Struktura notebooka

| Komórka | Opis |
|---|---|
| 1 | Instalacja zależności |
| 2 | Sprawdzenie GPU (`nvidia-smi`) |
| 3 | Ładowanie i indeksowanie dokumentów |
| 4 | Ładowanie PLLuM (4-bit, ~7 GB VRAM) |
| 5 | Szablon promptu PLLuM RAG |
| 6 | Funkcja pipeline `rag_query()` |
| 7 | Trzy testy + tryb interaktywny |
| 8 | Diagnostyka (VRAM, wyniki wyszukiwania) |


---

## Wymagania pamięci GPU

| Etap | VRAM |
|---|---|
| Model embeddingów (`multilingual-e5-base`) | ~1 GB |
| PLLuM 8B (4-bit) | ~6–7 GB |
| Inferencja (kontekst 4096 tokenów) | ~1–2 GB |
| **Łącznie** | **~9 GB** |

---

## Licencja

- **Model:** [Licencja społecznościowa Llama 3.1](https://huggingface.co/meta-llama/Llama-3.1-8B/blob/main/LICENSE) — otwarta, dozwolony użytek komercyjny
- **Notebook:** MIT

---

## Źródła

- [PLLuM na HuggingFace](https://huggingface.co/CYFRAGOVPL)
- [Artykuł PLLuM (arXiv:2511.03823)](https://arxiv.org/abs/2511.03823)
- [Unsloth](https://github.com/unslothai/unsloth)
- [multilingual-e5-base](https://huggingface.co/intfloat/multilingual-e5-base)
- [FAISS](https://github.com/facebookresearch/faiss)
