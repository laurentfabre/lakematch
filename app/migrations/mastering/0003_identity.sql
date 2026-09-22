-- Additive persistent identity foundation. No roles or privileges are granted.
ALTER TABLE lm_control.master_identity
    ADD COLUMN redirect_to UUID,
    ADD CONSTRAINT identity_redirect_fk FOREIGN KEY (domain_id, redirect_to)
        REFERENCES lm_control.master_identity(domain_id, master_id),
    ADD CONSTRAINT identity_redirect_state CHECK ((state = 'merged') = (redirect_to IS NOT NULL)),
    ADD CONSTRAINT identity_no_self_redirect CHECK (redirect_to IS NULL OR redirect_to <> master_id);
CREATE INDEX identity_redirect ON lm_control.master_identity(domain_id, redirect_to)
WHERE redirect_to IS NOT NULL;

CREATE TABLE lm_control.source_identity (
    domain_id TEXT NOT NULL,
    source_id TEXT NOT NULL CHECK (source_id ~ '^[a-z][a-z0-9_]{0,62}$'),
    source_key TEXT NOT NULL CHECK (length(trim(source_key)) > 0 AND octet_length(source_key) <= 2048),
    master_id UUID NOT NULL,
    PRIMARY KEY (domain_id, source_id, source_key),
    FOREIGN KEY (domain_id, master_id) REFERENCES lm_control.master_identity(domain_id, master_id)
);
CREATE INDEX source_identity_master ON lm_control.source_identity(domain_id, master_id);

CREATE TABLE lm_control.identity_alias (
    domain_id TEXT NOT NULL,
    policy_version TEXT NOT NULL CHECK (policy_version = 'spark_min_member_sha256_v1'),
    namespace TEXT NOT NULL CHECK (length(trim(namespace)) > 0 AND octet_length(namespace) <= 1024),
    old_id TEXT NOT NULL CHECK (old_id ~ '^[0-9a-f]{64}$'),
    master_id UUID NOT NULL,
    PRIMARY KEY (domain_id, policy_version, namespace, old_id),
    FOREIGN KEY (domain_id, master_id) REFERENCES lm_control.master_identity(domain_id, master_id)
);
CREATE INDEX identity_alias_master ON lm_control.identity_alias(domain_id, master_id);

CREATE TABLE lm_control.identity_event (
    event_id UUID PRIMARY KEY,
    sequence BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    domain_id TEXT NOT NULL,
    domain_version INTEGER NOT NULL,
    policy_version TEXT NOT NULL CHECK (policy_version = 'persistent_uuid_v1'),
    kind TEXT NOT NULL CHECK (kind IN ('allocate','attach','merge','split_new','restore_merge')),
    actor TEXT NOT NULL CHECK (length(trim(actor)) > 0 AND octet_length(actor) <= 512),
    idempotency_key TEXT NOT NULL CHECK (length(trim(idempotency_key)) > 0 AND octet_length(idempotency_key) <= 512),
    payload_sha256 TEXT NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    request JSONB NOT NULL CHECK (jsonb_typeof(request) = 'object'),
    receipt JSONB NOT NULL CHECK (jsonb_typeof(receipt) = 'object'),
    reverses_event_id UUID UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (actor, idempotency_key),
    UNIQUE (domain_id, event_id),
    FOREIGN KEY (domain_id, domain_version) REFERENCES lm_control.domain_version(domain_id, version),
    FOREIGN KEY (domain_id, reverses_event_id) REFERENCES lm_control.identity_event(domain_id, event_id),
    CHECK ((kind = 'restore_merge') = (reverses_event_id IS NOT NULL))
);
CREATE INDEX identity_history ON lm_control.identity_event(domain_id, sequence);

CREATE FUNCTION lm_control.master_identity_guard() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Persistent identities cannot be deleted';
    END IF;
    IF (NEW.domain_id, NEW.master_id, NEW.created_at) IS DISTINCT FROM
       (OLD.domain_id, OLD.master_id, OLD.created_at) OR NEW.revision <> OLD.revision + 1 THEN
        RAISE EXCEPTION 'Identity key/creation time is immutable; revision must advance once';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER master_identity_guard BEFORE UPDATE OR DELETE ON lm_control.master_identity
FOR EACH ROW EXECUTE FUNCTION lm_control.master_identity_guard();

CREATE FUNCTION lm_control.source_identity_guard() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Source deletion requires a later versioned identity policy';
    END IF;
    IF (NEW.domain_id, NEW.source_id, NEW.source_key) IS DISTINCT FROM
       (OLD.domain_id, OLD.source_id, OLD.source_key) THEN
        RAISE EXCEPTION 'Source reference keys are immutable';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER source_identity_guard BEFORE UPDATE OR DELETE ON lm_control.source_identity
FOR EACH ROW EXECUTE FUNCTION lm_control.source_identity_guard();

CREATE TRIGGER immutable_identity_event BEFORE UPDATE OR DELETE ON lm_control.identity_event
FOR EACH ROW EXECUTE FUNCTION lm_control.immutable_decision();
CREATE TRIGGER immutable_identity_alias BEFORE UPDATE OR DELETE ON lm_control.identity_alias
FOR EACH ROW EXECUTE FUNCTION lm_control.immutable_decision();
