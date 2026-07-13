# 🎮 Glitch Media — Multi-Agentic AI Pipeline

> Otomatisasi media berita game menggunakan pipeline multi-agent AI dengan orchestration, parallel processing, dan human-in-the-loop validation.

## 📋 Deskripsi

Glitch Media adalah pipeline AI yang mengotomatisasi proses pengumpulan, kurasi, dan posting berita gaming ke platform X (Twitter) dan Instagram. Pipeline terdiri dari 7 agent AI yang dirangkai secara sequential dan parallel:

```
[Scraping] → [Screening] → ┬─ [Caption X]  ─┬→ [HITL Gate] → ┬─ [Upload X]
                            └─ [Caption IG] ─┤                └─ [Upload IG]
                                              └─ [Image Gen] ─┘
```

## ✨ Fitur

- **Multi-Source Scraping**: Reddit, Twitter/X, YouTube, Steam News, RSS gaming sites
- **AI-Powered Screening**: Deduplikasi + quality scoring otomatis
- **Parallel Caption Generation**: Caption X (panjang) dan IG (singkat) dihasilkan secara paralel
- **AI Image Generation**: Gambar IG di-generate otomatis berdasarkan caption
- **Human-in-the-Loop Validation**: Gate mandatory dengan UI interaktif di notebook
- **Checkpoint & Resume**: Pipeline bisa di-resume tanpa mengulang tahap sebelumnya
- **Structured Output**: Semua data antar-tahap menggunakan Pydantic schema enforcement
- **Error Isolation**: Kegagalan satu agent tidak menghentikan agent paralel lainnya

## 🏗️ Arsitektur

```
glitch-media/
├── main.ipynb                     # Entry point
├── config/
│   ├── settings.py                # .env loading, constants
│   ├── schemas.py                 # Pydantic schemas (kontrak data)
│   └── prompts/                   # System prompts per agent
├── agents/                        # 1 file = 1 agent
├── tools/                         # API wrappers & scrapers
│   └── scrapers/                  # Per-source scrapers
├── pipeline/
│   ├── state.py                   # PipelineState dataclass
│   └── orchestrator.py            # Stage orchestration
├── validation/
│   └── human_validation.py        # HITL gate (ipywidgets)
├── data/                          # Intermediate outputs
│   ├── raw/
│   ├── filtered/
│   ├── captions/
│   ├── images/
│   └── checkpoints/
├── logs/
└── tests/
```

## 🚀 Setup

### 1. Clone & Install

```bash
# Install dependencies
pip install -r requirements.txt
```

### 2. Konfigurasi API Keys

```bash
# Copy template environment variables
cp .env.example .env

# Edit .env dan isi API keys
```

**API Keys yang dibutuhkan:**

| Service | Key | Cara mendapatkan |
|---------|-----|-----------------|
| Anthropic (Claude) | `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| **9Router (Local AI Router)** | **`NINEROUTER_BASE_URL`** | **[9router.com](https://9router.com) (install locally via npm)** |
| OpenAI (DALL-E) | `IMAGE_GEN_API_KEY` | [platform.openai.com](https://platform.openai.com) |
| Twitter/X | `TWITTER_*` | [developer.twitter.com](https://developer.twitter.com) (Elevated access) |
| Instagram | `INSTAGRAM_*` | [developers.facebook.com](https://developers.facebook.com) (Business account) |
| Reddit | `REDDIT_*` | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) |
| YouTube | `YOUTUBE_API_KEY` | [console.cloud.google.com](https://console.cloud.google.com) |
| Steam | `STEAM_API_KEY` | [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey) |

### 2a. Konfigurasi 9Router (Opsional, untuk mengurangi biaya API)

9Router adalah *local AI router* yang menghubungkan ke 60+ provider AI dengan fallback otomatis (Subscription → Cheap → Free). Ini cara menggunakannya:

1. **Install 9Router globally via npm:**
   ```bash
   npm install -g 9router
   ```

2. **Start 9Router (akan berjalan di localhost:20128):**
   ```bash
   9router
   ```

3. **Konfigurasi API credentials di dashboard:**
   Buka [http://localhost:20128/dashboard](http://localhost:20128/dashboard) dan masukkan API keys provider Anda.

4. **Tambahkan ke `.env`:**
   ```env
   NINEROUTER_BASE_URL=http://localhost:20128/v1
   ```
   **Catatan:** Jika `NINEROUTER_BASE_URL` diisi, pipeline akan menggunakan 9router. Jika kosong, akan langsung ke Anthropic API (biaya lebih tinggi).

### 3. Jalankan

```bash
# Buka notebook
jupyter notebook main.ipynb
```

Lalu jalankan sel-sel notebook secara berurutan.

## 📖 Cara Kerja Pipeline

| Cell | Tahap | Deskripsi |
|------|-------|-----------|
| 1 | Setup | Import & load `.env` |
| 2 | Init | Buat `PipelineState` dengan `run_id` unik |
| 3 | Stage 1-2 | Scraping → Screening (sequential) |
| 4 | Stage 3 | Caption X ∥ Caption IG (parallel fork) |
| 5 | Stage 4 | Image Generation (sequential) |
| 6 | Stage 5 | **HITL Gate** — Checkpoint + ACC/REJECT |
| 7 | Stage 6 | Upload X ∥ Upload IG (parallel, jika ACC) |
| 8 | Summary | Cetak ringkasan hasil |

## 🔄 Resume dari Checkpoint

Jika notebook terputus setelah checkpoint disimpan:

```python
from validation.human_validation import load_checkpoint

state = load_checkpoint("run_id_anda")
# Lanjutkan dari stage 5 (validation)
```

## 🧪 Testing

```bash
python -m pytest tests/ -v
```

## 📐 Design Patterns

- **Sequential / Pipeline Orchestration** (prompt chaining)
- **Parallel Fork** (Captain X ∥ Caption IG)
- **Mandatory Human-in-the-Loop Gate** (maker–checker)
- **Shared State Object** (PipelineState)
- **Schema Enforcement** (Pydantic)
- **Single Responsibility per Agent**
- **Retry + Exponential Backoff** (tools layer)

## 📚 Referensi

- Microsoft Azure — AI Agent Orchestration Patterns
- Google Cloud — Agentic AI Design Patterns
- Google ADK — Multi-Agent Patterns
- Pydantic AI — Multi-Agent Patterns & Schema Enforcement
