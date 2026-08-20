# Document field extraction with source evidence

Three standalone programs demonstrating one mechanism: **proving where every
extracted value came from**, by pointing at the exact region of the scan it was
read from.

Every field gets a bounding box on the source page. When a box cannot be
established, the field goes to a review queue instead of the database.

![result](result_regex.png)

| program | OCR engine | extraction | needs |
|---|---|---|---|
| `01_regex_extraction.py` | Tesseract (local) | regular expressions | nothing |
| `02_llm_extraction.py` | Tesseract (local) | language model | API key |
| `03_azure_ocr.py` | Azure Document Intelligence | regular expressions | Azure resource |

The layout is deliberate: 01→02 changes the extractor, 01→03 changes the OCR
engine. **One variable at a time**, so any difference in output has one possible
cause.

---

## The problem

When processing scanned official documents, reading the text is not enough.
In a regulated environment — banking, insurance, legal — someone will eventually
ask: *how do we know the awarded amount is 47 850,00 PLN?*

"The model said so" is not an acceptable answer. What is needed is a pointer to a
specific region of a specific page.

## The approach: post-hoc grounding

The naive approach is to ask a language model to return the value together with
its coordinates. **This does not work** — the model cannot see page geometry, so
it invents coordinates. They look plausible and point at random places.

The approach used here inverts the order:

```
1. OCR returns WORDS WITH COORDINATES, not flat text
2. The extractor returns a VALUE + a VERBATIM QUOTE  (regex in 01/03, model in 02)
3. The quote is fuzzy-matched against the OCR words
4. The bounding box comes from the words that matched
```

The extractor is never asked where something is. It is asked what it read — and a
quote can be checked against the page.

### The side effect matters more than the main effect

If a quote **cannot be located**, one of two things happened: the value was
fabricated, or OCR mangled that region beyond matching. In both cases the result
is unsafe to auto-approve.

So the audit requirement yields a **hallucination detector for free**.

Measured on the document in this repository:

| quote | match | verdict |
|---|---|---|
| `47 850,00 zl` — real amount, OCR dropped the "ł" | 0.90 | grounded |
| `99 999,00 zl` — invented value | 0.44 | **rejected** |
| `Sad Okregowy w Gdansku` — real span, diacritics stripped | 0.84 | grounded |
| `Sad Rejonowy w Warszawie` — invented span | 0.51 | **rejected** |

Matching **survives OCR errors** but **does not survive fabrication**. That is the
whole mechanism, expressed in four numbers.

---

## Architectural decision: OCR must preserve geometry

A typical Tesseract call returns text:

```
Sygn. akt I C 1284/23
zasądza kwotę 47 850,00 zł
```

Readable and **useless**, because position information is gone for good. All three
programs return words with boxes instead:

```python
{"text": "47", "x": 512, "y": 397, "w": 34, "h": 21, "confidence": 96.4}
```

Flattening to a string here would make source evidence unrecoverable. This is the
first decision in the pipeline, not the last — and the usual place where such a
project goes wrong, because geometry is discarded at the start and needed at the
end.

Both engines are normalised to this shape, confidence included: Azure returns
0–1, Tesseract 0–100. Without normalising, a downstream confidence threshold would
silently mean different things per engine.

---

## Results

### Extractor comparison — regex vs model (programs 01 and 02)

Same document, same OCR engine. The difference is not accuracy, it is what each
approach can distinguish.

| | regex | model |
|---|---|---|
| fields returned | 10 | 6 |
| amounts | 3 × `amount`, undifferentiated | `principal_sum` / `costs_sum`; cost component omitted |
| dates | 4, including a duplicate | 1, the correct one |
| value | raw (`47 850,00 zł`) | normalised (`47850.00`) |
| quote | identical to the value | longer, with context (`kwotę 47 850,00 zł`) |
| grounded | 10/10 | 6/6 |

Regular expressions match **patterns**. They find every amount on the page but
cannot tell the principal sum from the costs of proceedings, and they return the
same date twice because it appears twice.

The model distinguishes **meaning**, because the schema describes each field in
words. It also skipped `5 400,00 zł` — legal representation costs, a component of
the costs already reported rather than a separate award. That judgement is not
expressible as a regular expression.

Note what the model did with `judgment_date`: the value is normalised to
`2024-03-14` while the quote stayed verbatim as `Dnia 14 marca 2024 r.` That split
is what the prompt enforces, and it is why grounding still works — a "corrected"
quote would no longer match the OCR output.

### OCR engine comparison — Tesseract vs Azure (programs 01 and 03)

Same document, same regex extractor:

| | Tesseract (local) | Azure Document Intelligence |
|---|---|---|
| words read | 157 | 158 |
| time | 0.8 s | 2.8 s |
| mean confidence | 95.5% | 98.8% |
| fields grounded | 10/10 | 10/10 |

**On this document the cloud engine buys nothing.** Identical extraction output,
3.5× the latency, plus a per-page cost. The sample is a clean render rather than a
scan, and Tesseract barely errs on clean renders — so there is nothing to improve.

The honest conclusion is that this comparison does not yet answer the question it
was built to answer. Cloud OCR earns its cost on degraded scans, and this
repository has no corpus of real ones. Collecting 15–30 genuine scans and
transcribing a handful by hand is the next step; the numbers above are a
placeholder until then.

### Why the OCR language model matters

CER measured on identical images, changing only Tesseract's language model:

| scan quality | `-l pol` | `-l eng` | diacritics' share of `eng` error |
|---|---|---|---|
| good | 0.000–0.004 | 0.043–0.060 | 48–59% |
| poor | 0.023–0.024 | 0.078–0.095 | 35–45% |

**Between 35% and 62% of the error under a wrong language model is Polish
diacritics alone.** Reported as a single aggregate CER this looks like a scan
quality problem, and leads to optimising image preprocessing instead of changing
one flag. Hence: **always report CER split into diacritic error and the rest.**

---

## Running

System dependencies (not Python packages):

```bash
# macOS
brew install tesseract tesseract-lang poppler

# Ubuntu / Debian / WSL
sudo apt install tesseract-ocr tesseract-ocr-pol poppler-utils
```

Verify the Polish model is installed — `pol` must appear:

```bash
tesseract --list-langs
```

**Program 1** — no key, no cost:

```bash
uv run 01_regex_extraction.py sample.pdf
```

**Program 2** — language model:

```bash
cp .env.example .env      # paste your key from console.anthropic.com
uv run 02_llm_extraction.py sample.pdf
```

**Program 3** — Azure OCR. Create the resource with Terraform:

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # fill in subscription_id
terraform init && terraform apply
terraform output -raw env_file >> ../.env
cd ..
uv run 03_azure_ocr.py sample.pdf
```

`setup_azure.sh` does the same through Azure CLI if you prefer. Tear down when
done — the free tier allows one resource of this kind per subscription:

```bash
cd terraform
NAME=$(terraform output -raw endpoint | sed 's|https://||; s|\..*||')
terraform destroy
az cognitiveservices account purge --name "$NAME" \
    --resource-group rg-ocr-demo --location westeurope
```

`destroy` alone leaves the resource in soft-delete for 48 hours; `purge` frees the
quota immediately.

`uv` resolves Python dependencies from each script's PEP 723 header. `.env`,
`terraform.tfstate` and `terraform.tfvars` are gitignored — the state file holds
the Azure key in plain text.

---

## Scope and limitations

**The document is synthetic.** This demonstrates a mechanism; it does not measure
accuracy. Match scores show the method works — they say nothing about performance
on real archive scans. Every number in the OCR comparison carries this caveat.

**Grounding anchors, it does not validate.** A successful match proves the
extractor looked at the right place; it does not prove the value was transcribed
correctly. A model could quote `kwotę 47 850,00 zł` and return `4785.00` — the
quote would match and the number would be wrong. Checking normalisation is a
separate layer.

**First page only.** Multi-page means looping over `pdftoppm` output and adding a
page number to each word record.

**No document classification.** A full solution puts a classifier before
extraction, selecting the field schema per document type — with a mandatory
`unknown` class, without which the model forces every document into the nearest
category and corrupts everything downstream.

**No table handling.** Tesseract reads tables as ordinary text, losing cell
structure. Azure's `prebuilt-layout` model handles them at roughly 6× the price of
the `prebuilt-read` model used here.

**OCR, grounding and drawing code is duplicated across the three programs.**
Deliberate: each program reads top to bottom without jumping between files. In a
real codebase this would be one shared module.

**Terraform state is local.** Fine for a demo, wrong for production — state
belongs in a remote backend with encryption and locking.

---

## Where this sits in the wider pipeline

| step | description | status |
|---|---|---|
| 1 | sample diagnosis — text layer coverage, splitting merged documents | out of scope |
| 2 | **OCR with geometry** — `(text, page, bbox, confidence)` tokens | **done, two engines** |
| 3 | classification with a mandatory `unknown` class | out of scope |
| 4 | **per-type extraction, `null` allowed** | **done** |
| 5 | **post-hoc grounding + hallucination detection** | **done** |
| 6 | evaluation against a gold set, per-field metrics | **partial** — method built, corpus missing |

The OCR engine is a **swappable component**, which is why swapping it took one
function body and no downstream changes. The choice follows a CER measurement on
the client's own sample rather than preceding it. With sensitive data it usually
turns on a question asked up front: *may the data leave the client's
infrastructure?* If not, cloud engines are out regardless of accuracy — which is
also why the local engine is the default here rather than the fallback.

---

## Code structure

All three programs share the same four-part layout:

| function | role |
|---|---|
| `ocr_with_coordinates*` | engine → words with pixel positions |
| `extract_fields*` | → `{field, value, quote}` records |
| `locate_on_page` | sliding window, fuzzy match → bounding box or `None` |
| `draw_evidence` | boxes and labels rendered onto the page image |

```
.
├── 01_regex_extraction.py     Tesseract + regex
├── 02_llm_extraction.py       Tesseract + language model
├── 03_azure_ocr.py            Azure DI + regex, prints engine comparison
├── sample.pdf                 synthetic court judgment
├── .env.example               API key template
└── terraform/
    ├── main.tf                Document Intelligence resource, F0 tier
    ├── outputs.tf             endpoint + key
    ├── variables.tf           location + subscription_id
    └── terraform.tfvars.example
```
