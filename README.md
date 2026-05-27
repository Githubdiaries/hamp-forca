# Hamper Forecast

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)](docker-compose.yml)

Forecast monthly **profit** and **revenue** for a gift-hamper business. The stack combines company sales data, [Firecrawl](https://firecrawl.dev) market scraping, a TensorFlow **LSTM** model, and **Grafana** dashboards — all runnable with Docker Compose.

Built for seasonal occasions (Christmas, Easter, corporate gifting) where demand spikes are predictable but hard to plan without both internal history and external market signals.

---

## Table of contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Data flow](#data-flow)
- [Project structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Database schema](#database-schema)
- [Operator workflow](#operator-workflow)
- [Local development](#local-development)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Overview

| Layer | Technology | Role |
|-------|------------|------|
| Ingestion | FastAPI, CSV/JSON | Company monthly sales, revenue, profit |
| Market intel | Firecrawl | Scrape/search competitor and trend pages |
| Storage | PostgreSQL 16 | Time series, documents, forecasts |
| ML | TensorFlow/Keras LSTM | 6-month profit + revenue forecast |
| Viz | Grafana | Actual vs forecast dashboards |

**Key behaviours**

- Monthly grain aligned to retail seasonality
- Multivariate LSTM (sales, revenue, profit + market keyword features)
- Seasonal naive fallback when history is too short (< 18 months by default)
- Scheduled scrape, retrain, and forecast jobs via APScheduler

---

## Architecture

```mermaid
flowchart TB
  subgraph clients [Clients]
    Ops[Operator / CSV upload]
    GFUI[Grafana UI]
  end

  subgraph ingest [Ingestion]
    FC[Firecrawl API]
    CSV[CSV or JSON uploads]
  end

  subgraph app [Python app container]
    API[FastAPI]
    SCH[APScheduler]
    ETL[Market feature builder]
    TRAIN[LSTM training]
    INF[Forecast inference]
  end

  subgraph store [Data layer]
    PG[(PostgreSQL)]
    MV[(Model volume)]
  end

  subgraph viz [Visualization]
    GF[Grafana]
  end

  Ops --> API
  CSV --> API
  API --> PG
  SCH --> FC
  FC --> ETL
  ETL --> PG
  PG --> TRAIN
  TRAIN --> MV
  TRAIN --> PG
  PG --> INF
  MV --> INF
  INF --> PG
  PG --> GF
  GFUI --> GF
```

---

## Data flow

```mermaid
sequenceDiagram
  participant Op as Operator
  participant API as FastAPI
  participant FC as Firecrawl
  participant PG as PostgreSQL
  participant ML as LSTM pipeline
  participant GF as Grafana

  Op->>API: POST /ingest/company-monthly/csv
  API->>PG: Upsert company_monthly

  Op->>API: POST /jobs/scrape-market
  API->>FC: Search + scrape sources
  FC-->>API: Markdown documents
  API->>PG: market_documents + market_features_monthly

  Op->>API: POST /jobs/retrain
  API->>PG: Load time series
  ML->>PG: Save model_run + artifact

  Op->>API: POST /jobs/forecast
  ML->>PG: Write forecasts

  GF->>PG: SQL queries for dashboards
  Op->>GF: View profit vs forecast
```

---

## Project structure

```
.
├── config/
│   └── market_sources.yaml      # Firecrawl queries and seed URLs
├── data/
│   └── sample_company_monthly.csv
├── grafana/provisioning/        # Datasource + dashboard as code
├── ml/                          # Dataset, LSTM model, train/infer
├── sql/migrations/              # Postgres init schema
├── src/
│   ├── main.py                  # FastAPI + scheduler entrypoint
│   ├── routers/                 # Ingest and job endpoints
│   └── services/                # Firecrawl client, feature aggregation
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── LICENSE
```

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose v2)
- Optional: [Firecrawl API key](https://firecrawl.dev) for market scraping
- Ports available: **3000** (Grafana), **8001** (API — mapped from container 8000)

> **Security:** Never commit `.env` or API keys. If a key was exposed, rotate it in the Firecrawl dashboard before use.

---

## Quick start

### 1. Clone and configure

```bash
git clone <your-repo-url>
cd Lstm
cp .env.example .env
```

Edit `.env` and set `FIRECRAWL_API_KEY` (optional for testing without scraping).

### 2. Start the stack

```bash
docker compose up --build -d
```

### 3. Services

| Service | URL | Default credentials |
|---------|-----|---------------------|
| API | http://localhost:8001 | — |
| API docs (Swagger) | http://localhost:8001/docs | — |
| Grafana | http://localhost:3000 | `admin` / `admin` |

Postgres runs on the internal Docker network only (not exposed to the host by default).

### 4. Load sample data and run the pipeline

```bash
curl -X POST "http://localhost:8001/ingest/company-monthly/csv" \
  -F "file=@data/sample_company_monthly.csv"

curl -X POST http://localhost:8001/jobs/retrain
curl -X POST http://localhost:8001/jobs/forecast
```

Optional — refresh market signals (requires Firecrawl key):

```bash
curl -X POST http://localhost:8001/jobs/scrape-market
```

### 5. View dashboards

Open Grafana → folder **Hamper Forecast** → dashboard **Hamper Profit Forecast**.

---

## Configuration

Copy [`.env.example`](.env.example) to `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://hamper:...@postgres:5432/hamper_forecast` | SQLAlchemy connection string |
| `FIRECRAWL_API_KEY` | — | Firecrawl Bearer token |
| `GRAFANA_ADMIN_USER` | `admin` | Grafana login |
| `GRAFANA_ADMIN_PASSWORD` | `admin` | Change in production |
| `MODEL_DIR` | `/models` | Path for saved `.keras` model |
| `LSTM_WINDOW` | `12` | Months of history per training window |
| `FORECAST_HORIZON` | `6` | Months to predict ahead |
| `MIN_TRAINING_ROWS` | `18` | Minimum monthly rows before LSTM (else fallback) |

Market scrape targets live in [`config/market_sources.yaml`](config/market_sources.yaml) (search queries, competitor URLs, keyword list).

---

## API reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/ingest/company-monthly` | JSON batch of monthly rows |
| `POST` | `/ingest/company-monthly/csv` | CSV file upload |
| `POST` | `/ingest/products` | Product lineup metadata |
| `POST` | `/jobs/scrape-market` | Firecrawl scrape + feature aggregation |
| `POST` | `/jobs/aggregate-market-features` | Recompute monthly market features |
| `POST` | `/jobs/retrain` | Train LSTM and record `model_runs` |
| `POST` | `/jobs/forecast` | Write profit/revenue forecasts |

### CSV format

```csv
period,sales_volume,revenue,profit,currency,notes
2024-01-01,440,13200,3300,GBP,January
```

Supported date formats: `YYYY-MM-DD`, `YYYY-MM`, `MM/YYYY`, `DD/MM/YYYY`.

---

## Database schema

```mermaid
erDiagram
  company_monthly {
    date period PK
    numeric sales_volume
    numeric revenue
    numeric profit
    varchar currency
  }

  products {
    int id PK
    varchar name
    varchar category
  }

  market_documents {
    int id PK
    text source_url
    timestamptz scraped_at
    text markdown
    varchar query_tag
  }

  market_features_monthly {
    date period PK
    int doc_count
    numeric avg_keyword_score
    int gift_hits
    int hamper_hits
  }

  model_runs {
    int id PK
    timestamptz started_at
    jsonb metrics
    text artifact_path
  }

  forecasts {
    int id PK
    timestamptz generated_at
    date target_month
    varchar metric
    numeric point_estimate
    int model_run_id FK
  }

  model_runs ||--o{ forecasts : produces
```

---

## Operator workflow

```mermaid
flowchart LR
  A[Upload monthly CSV] --> B{Need market refresh?}
  B -->|Yes| C[POST /jobs/scrape-market]
  B -->|No| D[POST /jobs/retrain]
  C --> D
  D --> E[POST /jobs/forecast]
  E --> F[Review Grafana dashboard]
  F --> G[Adjust market_sources.yaml]
  G --> C
```

### Scheduled jobs (inside app container)

| Schedule | Job |
|----------|-----|
| Daily 02:00 | Market scrape + feature aggregation |
| 1st of month 03:00 | Retrain LSTM + generate forecast |

### Model behaviour

- **Window:** 12 months (`LSTM_WINDOW`)
- **Horizon:** 6 months (`FORECAST_HORIZON`)
- **Fallback:** seasonal naive from last 12 months when data or trained model is unavailable
- **Artifacts:** persisted in Docker volume `modelstore` at `/models`

### Grafana panels

1. Profit — actual vs forecast (time series)
2. Latest forecast table (profit + revenue)
3. Market documents per month
4. Revenue — actual vs forecast

---

## Testing

There was no test suite initially, so `pytest` reported **collected 0 items**. Tests are now organized by marker:

| Marker | Requires | What it covers |
|--------|----------|----------------|
| `unit` | Nothing extra | Date parsing, dataset helpers, Firecrawl error handling |
| `integration` | PostgreSQL on port **5433** | API ingest, jobs, market features |
| `ml` | PostgreSQL + TensorFlow | Full CSV → train → LSTM forecast pipeline |

### Run all tests (recommended — uses Docker)

```bash
docker compose up -d postgres
docker compose --profile test run --rm test
```

Or on Windows:

```powershell
.\scripts\test.ps1
```

### Run unit tests only (no database)

```bash
pip install -r requirements-dev.txt
pytest -m unit
```

### Run integration tests against local Postgres

Start Postgres with the exposed test port, then:

```bash
pip install -r requirements.txt -r requirements-dev.txt
set TEST_DATABASE_URL=postgresql://hamper:hamper_secret@localhost:5433/hamper_forecast_test
pytest -m "integration or ml"
```

> **Note:** ML tests need TensorFlow (included in the Docker image). Local Python 3.13 may not support TensorFlow — use Docker for the full suite.

---

## Local development

Without Docker (Postgres must be reachable separately):

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

# Point at local or containerized Postgres
set DATABASE_URL=postgresql://hamper:hamper_secret@localhost:5432/hamper_forecast   # Windows
export DATABASE_URL=postgresql://hamper:hamper_secret@localhost:5432/hamper_forecast # Unix

python -m src.main
```

Run only database + Grafana via Docker:

```bash
docker compose up postgres grafana -d
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| **`pytest` collects 0 items** | Tests live under `tests/` — run from repo root; use Docker command above for the full suite |
| **`ModuleNotFoundError` locally** | Install deps with Docker, or `pip install -r requirements.txt -r requirements-dev.txt` on Python 3.11 |
| Empty Grafana charts | Ingest data, then `POST /jobs/forecast` |
| LSTM training skipped | Need ≥ 18 monthly rows; sample CSV has 24 |
| Firecrawl errors | Check API key, quota, and URLs in `market_sources.yaml` |
| Port 8001 in use | Change `"8001:8000"` in `docker-compose.yml` |
| Postgres connection failed | Use host `postgres` inside Docker, `localhost` when running app on host |

---

## License

This project is licensed under the [MIT License](LICENSE).
