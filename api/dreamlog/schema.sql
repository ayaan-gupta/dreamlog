CREATE EXTENSION IF NOT EXISTS vector;

-- One row per dream. The transcript is AES-256-GCM ciphertext bound to the id.
CREATE TABLE IF NOT EXISTS entries (
    id          uuid PRIMARY KEY,
    created_at  timestamptz NOT NULL,
    updated_at  timestamptz NOT NULL,
    transcript  bytea NOT NULL,
    mood        text[] NOT NULL DEFAULT '{}',
    embedding   vector(384) NOT NULL,
    image_key   text,
    thumb_key   text,
    audio_key   text,
    duration_s  real,
    source      text NOT NULL,
    engines     jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- The canonical list. embedding is the vector of the canonical name, used for clustering.
CREATE TABLE IF NOT EXISTS symbols (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    canonical   text NOT NULL UNIQUE,
    kind        text NOT NULL,
    embedding   vector(384) NOT NULL,
    glyph       text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Every surface form that has been folded into a canonical symbol.
CREATE TABLE IF NOT EXISTS symbol_aliases (
    alias       text PRIMARY KEY,
    symbol_id   bigint NOT NULL REFERENCES symbols (id) ON DELETE CASCADE,
    kind        text NOT NULL,
    embedding   vector(384) NOT NULL,
    similarity  real NOT NULL
);

CREATE TABLE IF NOT EXISTS entry_symbols (
    entry_id    uuid NOT NULL REFERENCES entries (id) ON DELETE CASCADE,
    symbol_id   bigint NOT NULL REFERENCES symbols (id) ON DELETE CASCADE,
    salience    real NOT NULL,
    surfaces    text[] NOT NULL,
    PRIMARY KEY (entry_id, symbol_id)
);

CREATE INDEX IF NOT EXISTS entries_created_at ON entries (created_at DESC);
CREATE INDEX IF NOT EXISTS entry_symbols_symbol ON entry_symbols (symbol_id);
CREATE INDEX IF NOT EXISTS entries_embedding ON entries USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS symbol_aliases_embedding ON symbol_aliases USING hnsw (embedding vector_cosine_ops);
