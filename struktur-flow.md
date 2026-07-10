# Struktur & Flow — Multi Agentic AI Workflow (Otomatisasi Media Berita Game)

> Dokumen ini adalah **plan arsitektur** untuk AI coding agent (Claude Code, Cursor, dsb) agar memahami bagaimana kode harus dipecah menjadi modul-modul terpisah per proses, dan bagaimana modul-modul tersebut dirangkai menjadi satu pipeline di `main.ipynb`.

---

## 1. Analisis Workflow (dari diagram)

| # | Node | Input | Output | Sifat |
|---|------|-------|--------|-------|
| 1 | Agent Scraping | Sumber (Gaming News, Reddit, Twitter/X, YouTube, Steam News, dll) | Raw Data | Sequential |
| 2 | Agent Screening | Raw Data | Filtered Data (dedup + quality filter) | Sequential |
| 3a | Agent Caption X | Filtered Data | Caption X (panjang) | Parallel (fork) |
| 3b | Agent Caption IG | Filtered Data | Caption IG (singkat) | Parallel (fork) |
| 4 | Agent Image Generation | Caption IG | Image (IG) | Sequential (tergantung 3b) |
| 5 | Validasi User | Caption X, Caption IG, Image IG | ACC / REJECT | **Human-in-the-loop (mandatory gate)** |
| 6a | Agent Upload X | Caption X (approved) | Post di X | Parallel (join → split) |
| 6b | Agent Upload IG | Caption IG + Image (approved) | Post di IG | Parallel (join → split) |

**Klasifikasi pola arsitektur** (berdasarkan riset — Microsoft Azure AI Agent Design Patterns, Google Cloud Agentic Design Patterns, Google ADK Multi-Agent Patterns):

- Pola utama: **Sequential / Pipeline Orchestration** (a.k.a *prompt chaining*) — setiap agent mengonsumsi output agent sebelumnya, urutan tetap dan dapat diprediksi. Cocok karena tiap tahap punya tanggung jawab tunggal dan ketergantungan linear yang jelas.
- Di tahap 3 terjadi **Fork (Parallel sub-pattern)**: Agent Caption X dan Agent Caption IG berjalan independen dari sumber data yang sama (Filtered Data), tidak saling bergantung → bisa dieksekusi paralel untuk efisiensi.
- Tahap 5 adalah **Mandatory Human-in-the-Loop Gate** (maker–checker loop): pipeline **berhenti (synchronous)** menunggu keputusan manusia sebelum lanjut. Best practice: state pipeline di titik ini harus **di-persist**, supaya tidak perlu mengulang kerja agent 1–4 jika user menutup notebook.
- Tahap 6 adalah **Join lalu Split lagi**: hasil yang sudah di-ACC dipecah ke dua *executor agent* independen (Upload X, Upload IG) yang tidak saling bergantung.
- Setiap agent LLM sebaiknya menghasilkan **structured output (schema-enforced, mis. Pydantic)**, bukan teks bebas — supaya tidak terjadi *tool/data divergence* antar tahap, dan supaya validasi otomatis bisa dilakukan sebelum data diteruskan ke agent berikutnya.

**Prinsip desain yang dipakai untuk struktur folder:**

1. **Single Responsibility per Agent** — satu file = satu agent = satu tanggung jawab (mudah di-debug, mudah diganti model/prompt-nya sendiri-sendiri).
2. **Decoupling Agent dari Tool/Connector** — agent (logic + prompt + LLM call) dipisah dari tool (scraper, API client) supaya tool bisa dipakai ulang tanpa terikat 1 agent.
3. **Contract-based data flow** — schema (Pydantic) mendefinisikan bentuk data di setiap batas antar-tahap (interpretable, dapat divalidasi, dapat di-serialize ke file untuk audit trail / observability).
4. **Orchestrator terpisah dari Agent** — logic "urutan siapa manggil siapa" tidak ditulis campur di dalam agent, tapi di `pipeline/orchestrator.py`. `main.ipynb` hanya memanggil orchestrator (notebook = *entry point*, bukan tempat logic).
5. **State object tunggal mengalir di sepanjang pipeline** (mirip *shared session state* di Google ADK / *common state* di Azure sequential pattern) — memudahkan checkpoint & resume di gate HITL.
6. **Setiap tahap punya persisted intermediate output** (folder `data/`) — membuat pipeline *inherently interpretable* dan mudah di-debug tanpa harus re-run dari awal.

---

## 2. Struktur Folder

```
niki-media-agent/
├── main.ipynb                     # Entry point — merangkai seluruh pipeline jadi satu alur
│
├── config/
│   ├── settings.py                 # Load .env, API keys, model name, konstanta
│   ├── schemas.py                  # Semua Pydantic schema (kontrak data antar-tahap)
│   └── prompts/
│       ├── scraping_prompt.md
│       ├── screening_prompt.md
│       ├── caption_x_prompt.md
│       ├── caption_ig_prompt.md
│       └── image_prompt.md
│
├── agents/                         # 1 file = 1 agent = 1 tanggung jawab
│   ├── __init__.py
│   ├── agent_scraping.py           # Node 1
│   ├── agent_screening.py          # Node 2
│   ├── agent_caption_x.py          # Node 3a
│   ├── agent_caption_ig.py         # Node 3b
│   ├── agent_image_generation.py   # Node 4
│   ├── agent_upload_x.py           # Node 6a
│   └── agent_upload_ig.py          # Node 6b
│
├── tools/                          # Koneksi ke dunia luar — dipanggil OLEH agent, bukan berisi logic LLM
│   ├── __init__.py
│   ├── scrapers/
│   │   ├── reddit_scraper.py
│   │   ├── twitter_scraper.py
│   │   ├── youtube_scraper.py
│   │   ├── steam_news_scraper.py
│   │   └── gaming_site_scraper.py
│   ├── llm_client.py                # Wrapper panggilan LLM (Claude API), structured output enforcement
│   ├── image_gen_client.py          # Wrapper API image generation
│   ├── x_api_client.py              # Wrapper posting ke X (Twitter API v2)
│   └── ig_api_client.py             # Wrapper posting ke Instagram (Graph API)
│
├── pipeline/
│   ├── __init__.py
│   ├── state.py                     # Dataclass PipelineState (state object yang mengalir di semua tahap)
│   └── orchestrator.py              # Fungsi run_stage_1_4(), run_upload(), dst — dipanggil dari main.ipynb
│
├── validation/
│   ├── __init__.py
│   └── human_validation.py          # Fungsi tampilkan hasil + input ACC/REJECT (ipywidgets di notebook)
│
├── data/                            # Intermediate output tiap tahap (audit trail, checkpoint resume)
│   ├── raw/
│   ├── filtered/
│   ├── captions/
│   ├── images/
│   └── checkpoints/                 # State pipeline saat berhenti di gate HITL (agar bisa di-resume)
│
├── logs/
│   └── pipeline.log
│
├── tests/
│   ├── test_agents.py
│   └── test_pipeline.py
│
├── .env.example
├── requirements.txt
└── README.md
```

---

## 3. Kontrak Data Antar-Tahap (`config/schemas.py`)

Semua output agent WAJIB berupa objek Pydantic (schema enforcement) — mencegah *tool/data divergence* dan memudahkan validasi otomatis sebelum lanjut ke tahap berikut.

```python
from pydantic import BaseModel
from typing import Literal
from datetime import datetime

class RawItem(BaseModel):
    source: Literal["gaming_news", "reddit", "twitter", "youtube", "steam", "other"]
    title: str
    content: str
    url: str
    scraped_at: datetime

class RawData(BaseModel):
    items: list[RawItem]

class FilteredItem(BaseModel):
    title: str
    summary: str
    source: str
    url: str
    quality_score: float          # hasil penilaian Agent Screening
    is_duplicate: bool

class FilteredData(BaseModel):
    items: list[FilteredItem]

class CaptionX(BaseModel):
    news_ref_title: str
    caption_long: str             # caption panjang untuk X

class CaptionIG(BaseModel):
    news_ref_title: str
    caption_short: str            # caption singkat untuk IG

class ImageGenResult(BaseModel):
    news_ref_title: str
    image_prompt: str
    image_path: str               # path lokal file gambar hasil generate

class ValidationResult(BaseModel):
    news_ref_title: str
    caption_x_approved: bool
    caption_ig_approved: bool
    image_approved: bool
    status: Literal["ACC", "REJECT"]
    reviewer_note: str | None = None

class UploadResult(BaseModel):
    platform: Literal["x", "instagram"]
    success: bool
    post_url: str | None = None
    error: str | None = None
```

---

## 4. State Object Pipeline (`pipeline/state.py`)

Mengikuti pola *common/shared state* pada sequential orchestration — satu objek yang membawa hasil setiap tahap, sehingga proses bisa di-checkpoint tepat sebelum gate HITL (tahap 5) dan di-resume tanpa mengulang tahap 1–4.

```python
from dataclasses import dataclass, field
from config.schemas import RawData, FilteredData, CaptionX, CaptionIG, ImageGenResult, ValidationResult

@dataclass
class PipelineState:
    raw_data: RawData | None = None
    filtered_data: FilteredData | None = None
    caption_x: CaptionX | None = None
    caption_ig: CaptionIG | None = None
    image_result: ImageGenResult | None = None
    validation: ValidationResult | None = None
    run_id: str = ""
    logs: list[str] = field(default_factory=list)
```

---

## 5. Kontrak Fungsi per Agent

Setiap file di `agents/` mengekspor **satu fungsi utama** dengan signature konsisten: menerima objek schema tahap sebelumnya, mengembalikan objek schema tahap ini. Ini membuat orchestrator bisa memanggil semua agent dengan pola yang sama, dan memudahkan unit test per agent secara terisolasi.

```python
# agents/agent_scraping.py
def run(sources: list[str]) -> RawData: ...

# agents/agent_screening.py
def run(raw_data: RawData) -> FilteredData: ...

# agents/agent_caption_x.py
def run(filtered_data: FilteredData) -> CaptionX: ...

# agents/agent_caption_ig.py
def run(filtered_data: FilteredData) -> CaptionIG: ...

# agents/agent_image_generation.py
def run(caption_ig: CaptionIG) -> ImageGenResult: ...

# agents/agent_upload_x.py
def run(caption_x: CaptionX) -> UploadResult: ...

# agents/agent_upload_ig.py
def run(caption_ig: CaptionIG, image_result: ImageGenResult) -> UploadResult: ...
```

Setiap agent hanya boleh mengimpor dari `config/` dan `tools/` — **tidak boleh** mengimpor agent lain (mencegah coupling silang). Komunikasi antar-agent hanya lewat `pipeline/orchestrator.py`.

---

## 6. Orchestrator (`pipeline/orchestrator.py`)

```python
from concurrent.futures import ThreadPoolExecutor
from agents import (
    agent_scraping, agent_screening,
    agent_caption_x, agent_caption_ig,
    agent_image_generation,
)
from pipeline.state import PipelineState

def run_stage_1_2(state: PipelineState, sources: list[str]) -> PipelineState:
    state.raw_data = agent_scraping.run(sources)
    state.filtered_data = agent_screening.run(state.raw_data)
    return state

def run_stage_3_fork(state: PipelineState) -> PipelineState:
    # Fork: Caption X & Caption IG independen -> jalankan paralel
    with ThreadPoolExecutor(max_workers=2) as ex:
        fx = ex.submit(agent_caption_x.run, state.filtered_data)
        fig = ex.submit(agent_caption_ig.run, state.filtered_data)
        state.caption_x = fx.result()
        state.caption_ig = fig.result()
    return state

def run_stage_4(state: PipelineState) -> PipelineState:
    state.image_result = agent_image_generation.run(state.caption_ig)
    return state
```

`main.ipynb` **tidak** menulis ulang logic ini — ia hanya mengimpor dan memanggil fungsi-fungsi di atas per sel, sehingga setiap sel notebook = satu titik pemeriksaan visual (cocok untuk *human-on-the-loop* review).

---

## 7. Human-in-the-Loop (`validation/human_validation.py`)

Gate ini **wajib synchronous** — pipeline berhenti total sampai user memberi keputusan. State disimpan ke `data/checkpoints/{run_id}.json` sebelum menunggu input, agar sesi notebook yang terputus tetap bisa di-resume.

```python
def request_validation(state: PipelineState) -> ValidationResult: ...
def save_checkpoint(state: PipelineState) -> None: ...
def load_checkpoint(run_id: str) -> PipelineState: ...
```

Di notebook, tahap ini ditampilkan sebagai sel terpisah menggunakan `ipywidgets` (tombol ACC/REJECT) — bukan `input()` biasa, supaya UX di notebook tetap interaktif.

---

## 8. Struktur `main.ipynb`

Notebook dirangkai sebagai *daftar sel = daftar tahap*, tiap sel memanggil satu fungsi orchestrator — **tidak ada logic bisnis ditulis langsung di notebook**:

```
Cell 1  : import & load .env (config.settings)
Cell 2  : inisialisasi PipelineState(run_id=...)
Cell 3  : orchestrator.run_stage_1_2(state, sources)      # Scraping + Screening
Cell 4  : orchestrator.run_stage_3_fork(state)             # Caption X & IG (paralel)
Cell 5  : orchestrator.run_stage_4(state)                  # Image Generation
Cell 6  : human_validation.save_checkpoint(state)
          result = human_validation.request_validation(state)   # <-- STOP, tunggu ACC/REJECT
Cell 7  : if result.status == "ACC": orchestrator.run_stage_6_upload(state)
          else: # loop balik ke agent terkait / log REJECT untuk revisi manual
Cell 8  : cetak ringkasan hasil (post URL X & IG, log run)
```

---

## 9. Error Handling, Retry, & Observability

- Setiap `tools/*_client.py` membungkus pemanggilan API eksternal dengan **retry + exponential backoff** dan **step/attempt budget** (cegah infinite retry loop pada agent yang gagal terus-menerus).
- Semua exception di level agent ditangkap di orchestrator, dicatat ke `logs/pipeline.log`, dan **tidak menghentikan agent paralel lain** yang tidak bergantung padanya (mis. kegagalan Caption X tidak boleh menggagalkan Caption IG).
- Setiap output antar-tahap disimpan sebagai file JSON di `data/` (raw, filtered, captions, images) — menjadikan pipeline dapat diaudit ulang tanpa re-run LLM (hemat biaya token & waktu).
- Gunakan `run_id` (timestamp/UUID) sebagai penanda setiap eksekusi pipeline, dipakai sebagai nama sub-folder di `data/` dan `logs/` supaya antar-run tidak saling menimpa.

---

## 10. Ringkasan Alasan Desain

| Keputusan | Alasan |
|---|---|
| 1 file = 1 agent | Single responsibility, mudah ganti prompt/model per agent tanpa menyentuh agent lain |
| Schema Pydantic di setiap batas | Mencegah data/tool divergence, validasi otomatis, kontrak jelas antar-tahap |
| Orchestrator terpisah dari notebook | Notebook tetap ringkas & jadi entry point, logic dapat di-unit-test di luar notebook |
| Fork paralel di tahap 3 | Caption X & IG tidak saling bergantung → hemat latensi |
| Checkpoint sebelum gate HITL | Pipeline bisa di-resume tanpa mengulang kerja (dan biaya token) tahap 1–4 |
| Tools terpisah dari Agents | Scraper/API client reusable, tidak terikat 1 agent, mudah diuji terpisah |
| Output tiap tahap disimpan sebagai file | Audit trail, interpretable, debug tanpa re-run LLM |

---

## Referensi Teknik yang Digunakan

- Microsoft Azure Architecture Center — *AI Agent Orchestration Patterns* (Sequential Orchestration, Mandatory HITL Gate, state persistence at checkpoints).
- Google Cloud Architecture Center — *Choose a design pattern for your agentic AI system* (Sequential Pattern, Parallel/Fork Pattern, Custom Logic Pattern untuk workflow campuran).
- Google Developers Blog — *Developer's guide to multi-agent patterns in ADK* (SequentialAgent, ParallelAgent, shared session state dengan unique key per agent).
- Pydantic AI Docs — *Multi-Agent Patterns* & *Agents* (programmatic agent hand-off, schema enforcement, durable execution, human-in-the-loop tool approval).
- AppsTek Corp — *Design Patterns for Agentic AI and Multi-Agent Systems* (Schema Enforcement untuk cegah tool divergence, step budget untuk cegah infinite loop).
- Model Workspace Protocol (arXiv 2603.16021) — *folder structure sebagai orkestrasi, setiap output antar-tahap sebagai file yang interpretable*.
