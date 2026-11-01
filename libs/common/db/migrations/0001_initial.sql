-- Initial schema. Every table is keyed by tenant_id first: tenants share the
-- database (ADR 0002) and every query filters on tenant_id.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    tenant_id       text        NOT NULL,
    document_id     text        NOT NULL,
    application_id  text        NOT NULL,
    object_key      text        NOT NULL,
    content_type    text        NOT NULL,
    sha256          char(64)    NOT NULL,
    size_bytes      bigint      NOT NULL,
    declared_type   text,
    document_type   text,
    status          text        NOT NULL DEFAULT 'received',
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, document_id),
    -- Re-uploading identical bytes for the same application is a no-op.
    UNIQUE (tenant_id, application_id, sha256)
);

CREATE INDEX IF NOT EXISTS documents_application_idx
    ON documents (tenant_id, application_id);

-- One row per (document, step): reprocessing overwrites, never duplicates.
CREATE TABLE IF NOT EXISTS step_results (
    tenant_id    text        NOT NULL,
    document_id  text        NOT NULL,
    step         text        NOT NULL,
    result       jsonb       NOT NULL,
    confidence   real,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, document_id, step),
    FOREIGN KEY (tenant_id, document_id) REFERENCES documents ON DELETE CASCADE
);

-- Append-only record of every state change.
CREATE TABLE IF NOT EXISTS audit_log (
    id           bigserial   PRIMARY KEY,
    tenant_id    text        NOT NULL,
    document_id  text,
    actor        text        NOT NULL,
    action       text        NOT NULL,
    from_status  text,
    to_status    text,
    details      jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_log_document_idx
    ON audit_log (tenant_id, document_id, created_at);

CREATE TABLE IF NOT EXISTS review_items (
    tenant_id    text        NOT NULL,
    document_id  text        NOT NULL,
    reasons      jsonb       NOT NULL,
    status       text        NOT NULL DEFAULT 'open',
    reviewer     text,
    corrections  jsonb,
    created_at   timestamptz NOT NULL DEFAULT now(),
    resolved_at  timestamptz,
    PRIMARY KEY (tenant_id, document_id),
    FOREIGN KEY (tenant_id, document_id) REFERENCES documents ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS review_items_open_idx
    ON review_items (tenant_id, status, created_at);

-- Staff corrections reused as few-shot examples. 768 dimensions matches
-- the nomic-embed-text embedding model served by Ollama.
CREATE TABLE IF NOT EXISTS tenant_examples (
    id                  bigserial   PRIMARY KEY,
    tenant_id           text        NOT NULL,
    document_type       text        NOT NULL,
    source_document_id  text        NOT NULL,
    ocr_text            text        NOT NULL,
    fields              jsonb       NOT NULL,
    embedding           vector(768) NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, document_type, source_document_id)
);

CREATE INDEX IF NOT EXISTS tenant_examples_embedding_idx
    ON tenant_examples USING hnsw (embedding vector_cosine_ops);

-- Prevents sending the same notification twice when an event is redelivered.
CREATE TABLE IF NOT EXISTS notifications (
    tenant_id    text        NOT NULL,
    document_id  text        NOT NULL,
    event        text        NOT NULL,
    channel      text        NOT NULL,
    language     text        NOT NULL,
    sent_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, document_id, event)
);
