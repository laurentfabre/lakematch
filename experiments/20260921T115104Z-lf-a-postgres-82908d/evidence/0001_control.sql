-- LF-A control-plane prototype. Apply through a transaction/checksummed migration.
-- No privileges are granted here. Application identity/RLS integration is LM-008.
CREATE TABLE lm_control.domain (
    domain_id TEXT PRIMARY KEY CHECK (domain_id ~ '^[a-z][a-z0-9_]{0,62}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE lm_control.domain_version (
    domain_id TEXT NOT NULL REFERENCES lm_control.domain(domain_id),
    version INTEGER NOT NULL CHECK (version > 0),
    definition JSONB NOT NULL CHECK (jsonb_typeof(definition) = 'object'),
    definition_sha256 TEXT NOT NULL CHECK (definition_sha256 ~ '^[0-9a-f]{64}$'),
    state TEXT NOT NULL CHECK (state IN ('draft', 'approved', 'retired')),
    PRIMARY KEY (domain_id, version)
);

CREATE TABLE lm_control.source_mapping_version (
    domain_id TEXT NOT NULL,
    domain_version INTEGER NOT NULL,
    source_id TEXT NOT NULL CHECK (source_id ~ '^[a-z][a-z0-9_]{0,62}$'),
    version INTEGER NOT NULL CHECK (version > 0),
    definition JSONB NOT NULL CHECK (jsonb_typeof(definition) = 'object'),
    definition_sha256 TEXT NOT NULL CHECK (definition_sha256 ~ '^[0-9a-f]{64}$'),
    state TEXT NOT NULL CHECK (state IN ('draft', 'approved', 'retired')),
    PRIMARY KEY (domain_id, source_id, version),
    FOREIGN KEY (domain_id, domain_version) REFERENCES lm_control.domain_version(domain_id, version)
);

CREATE TABLE lm_control.master_identity (
    domain_id TEXT NOT NULL REFERENCES lm_control.domain(domain_id),
    master_id UUID NOT NULL,
    revision BIGINT NOT NULL DEFAULT 1 CHECK (revision > 0),
    state TEXT NOT NULL CHECK (state IN ('active', 'merged', 'retired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (domain_id, master_id)
);

CREATE TABLE lm_control.operation (
    operation_id UUID PRIMARY KEY,
    domain_id TEXT NOT NULL REFERENCES lm_control.domain(domain_id),
    caller TEXT NOT NULL CHECK (length(caller) > 0),
    idempotency_key TEXT NOT NULL CHECK (length(idempotency_key) > 0),
    payload_sha256 TEXT NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    expected_versions JSONB NOT NULL CHECK (jsonb_typeof(expected_versions) = 'object'),
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    state TEXT NOT NULL CHECK (state IN ('draft', 'pending_approval', 'approved', 'applying', 'published', 'conflict', 'failed')),
    revision BIGINT NOT NULL DEFAULT 1 CHECK (revision > 0),
    publication_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (caller, idempotency_key),
    UNIQUE (domain_id, operation_id),
    CHECK (state <> 'published' OR publication_id IS NOT NULL)
);

CREATE TABLE lm_control.steward_task (
    domain_id TEXT NOT NULL REFERENCES lm_control.domain(domain_id),
    task_id UUID NOT NULL,
    kind TEXT NOT NULL CHECK (length(kind) > 0),
    entity_ids JSONB NOT NULL CHECK (jsonb_typeof(entity_ids) = 'array'),
    state TEXT NOT NULL CHECK (state IN ('open', 'claimed', 'resolved', 'canceled')),
    assignee TEXT,
    lease_until TIMESTAMPTZ,
    revision BIGINT NOT NULL DEFAULT 1 CHECK (revision > 0),
    priority INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (domain_id, task_id),
    CHECK ((assignee IS NULL) = (lease_until IS NULL)),
    CHECK ((state = 'claimed') = (assignee IS NOT NULL))
);
CREATE INDEX task_inbox ON lm_control.steward_task(domain_id, state, priority DESC, task_id);

CREATE TABLE lm_control.steward_decision (
    decision_id UUID PRIMARY KEY,
    domain_id TEXT NOT NULL,
    task_id UUID NOT NULL,
    operation_id UUID NOT NULL,
    actor TEXT NOT NULL CHECK (length(actor) > 0),
    action TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    expected_revision BIGINT NOT NULL CHECK (expected_revision > 0),
    supersedes UUID,
    evidence JSONB NOT NULL CHECK (jsonb_typeof(evidence) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (domain_id, decision_id),
    FOREIGN KEY (domain_id, task_id) REFERENCES lm_control.steward_task(domain_id, task_id),
    FOREIGN KEY (domain_id, operation_id) REFERENCES lm_control.operation(domain_id, operation_id),
    FOREIGN KEY (domain_id, supersedes) REFERENCES lm_control.steward_decision(domain_id, decision_id)
);

CREATE TABLE lm_control.outbox_event (
    event_id UUID PRIMARY KEY,
    operation_id UUID NOT NULL REFERENCES lm_control.operation(operation_id),
    kind TEXT NOT NULL,
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    state TEXT NOT NULL CHECK (state IN ('pending', 'delivering', 'delivered', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (operation_id, kind)
);
CREATE INDEX outbox_pending ON lm_control.outbox_event(state, created_at, event_id);

CREATE FUNCTION lm_control.immutable_decision() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Decisions are append-only; append a superseding event';
END
$$;
CREATE TRIGGER immutable_decision BEFORE UPDATE OR DELETE ON lm_control.steward_decision
FOR EACH ROW EXECUTE FUNCTION lm_control.immutable_decision();
