-- Initial schema for gift hamper forecasting system

CREATE TABLE IF NOT EXISTS company_monthly (
    id SERIAL PRIMARY KEY,
    period DATE NOT NULL UNIQUE,
    sales_volume NUMERIC(14, 2) NOT NULL DEFAULT 0,
    revenue NUMERIC(14, 2) NOT NULL DEFAULT 0,
    profit NUMERIC(14, 2) NOT NULL DEFAULT 0,
    currency VARCHAR(8) NOT NULL DEFAULT 'GBP',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(128),
    active_from DATE,
    active_to DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS market_documents (
    id SERIAL PRIMARY KEY,
    source_url TEXT NOT NULL,
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    title TEXT,
    markdown TEXT,
    query_tag VARCHAR(128),
    status VARCHAR(32) NOT NULL DEFAULT 'ok',
    firecrawl_job_meta JSONB DEFAULT '{}'::jsonb,
    UNIQUE (source_url, scraped_at)
);

CREATE INDEX IF NOT EXISTS idx_market_documents_scraped_at ON market_documents (scraped_at);
CREATE INDEX IF NOT EXISTS idx_market_documents_query_tag ON market_documents (query_tag);

CREATE TABLE IF NOT EXISTS market_features_monthly (
    id SERIAL PRIMARY KEY,
    period DATE NOT NULL UNIQUE,
    doc_count INTEGER NOT NULL DEFAULT 0,
    avg_keyword_score NUMERIC(10, 4) NOT NULL DEFAULT 0,
    gift_hits INTEGER NOT NULL DEFAULT 0,
    hamper_hits INTEGER NOT NULL DEFAULT 0,
    luxury_hits INTEGER NOT NULL DEFAULT 0,
    discount_hits INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS model_runs (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    artifact_path TEXT,
    metrics JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    notes TEXT
);

CREATE TABLE IF NOT EXISTS forecasts (
    id SERIAL PRIMARY KEY,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    horizon_months INTEGER NOT NULL,
    target_month DATE NOT NULL,
    metric VARCHAR(32) NOT NULL,
    point_estimate NUMERIC(14, 2) NOT NULL,
    lower_bound NUMERIC(14, 2),
    upper_bound NUMERIC(14, 2),
    model_run_id INTEGER REFERENCES model_runs (id)
);

CREATE INDEX IF NOT EXISTS idx_forecasts_generated_at ON forecasts (generated_at);
CREATE INDEX IF NOT EXISTS idx_forecasts_metric ON forecasts (metric);
CREATE INDEX IF NOT EXISTS idx_forecasts_target_month ON forecasts (target_month);
