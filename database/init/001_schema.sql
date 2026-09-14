CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(60) NOT NULL UNIQUE,
    email VARCHAR(200) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'operator',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS password_resets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(100) NOT NULL,
    price NUMERIC(12,2) NOT NULL CHECK (price > 0),
    status VARCHAR(30) NOT NULL DEFAULT 'on_sale',
    image_url VARCHAR(500) NOT NULL DEFAULT '/images/demo-phone.png',
    summary TEXT NOT NULL DEFAULT '',
    inventory INTEGER NOT NULL DEFAULT 0 CHECK (inventory >= 0),
    warning_threshold INTEGER NOT NULL DEFAULT 20 CHECK (warning_threshold >= 0)
);

CREATE TABLE IF NOT EXISTS competitors (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    price NUMERIC(12,2) NOT NULL,
    highlights JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS ix_competitors_product_id ON competitors(product_id);

CREATE TABLE IF NOT EXISTS content_documents (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    content_type VARCHAR(30) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    revision INTEGER NOT NULL DEFAULT 1,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_content_product_type ON content_documents(product_id, content_type);

CREATE TABLE IF NOT EXISTS generation_tasks (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    kind VARCHAR(30) NOT NULL,
    title VARCHAR(200) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    progress INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    provider_mode VARCHAR(20) NOT NULL DEFAULT 'mock',
    error_message TEXT,
    result_url VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_generation_tasks_product_status ON generation_tasks(product_id, status);

CREATE TABLE IF NOT EXISTS experiments (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'submitted',
    strategy JSONB NOT NULL DEFAULT '{}'::jsonb,
    decision_note TEXT,
    reviewer_id INTEGER REFERENCES users(id),
    reviewed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS metric_records (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    period VARCHAR(50) NOT NULL,
    impressions INTEGER NOT NULL CHECK (impressions >= 0),
    clicks INTEGER NOT NULL CHECK (clicks >= 0 AND clicks <= impressions),
    paid_orders INTEGER NOT NULL CHECK (paid_orders >= 0 AND paid_orders <= clicks),
    gmv NUMERIC(14,2) NOT NULL CHECK (gmv >= 0),
    ad_spend NUMERIC(14,2) NOT NULL CHECK (ad_spend >= 0)
);

