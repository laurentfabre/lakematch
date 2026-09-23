-- Workflow access policy is maintained by a separate trusted operator identity.
-- The application only reads policies; deployments grant explicit privileges separately.
CREATE TABLE lm_control.access_subject (
    domain_id TEXT NOT NULL REFERENCES lm_control.domain(domain_id),
    principal TEXT NOT NULL CHECK (length(trim(principal))>0 AND octet_length(principal)<=512),
    PRIMARY KEY (domain_id,principal)
);
-- A stable row to coordinate readers with grant replacement/revocation.
-- UPDATE permission on the immutable key allows SELECT ... FOR SHARE, without
-- permitting an actual key/row change through the application role.
CREATE TRIGGER immutable_access_subject BEFORE UPDATE OR DELETE ON lm_control.access_subject
    FOR EACH ROW EXECUTE FUNCTION lm_control.immutable_decision();

CREATE TABLE lm_control.access_policy (
    domain_id TEXT NOT NULL,
    principal TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision>0),
    definition JSONB NOT NULL CHECK (jsonb_typeof(definition)='object'),
    definition_sha256 TEXT NOT NULL CHECK (definition_sha256 ~ '^[0-9a-f]{64}$'),
    event_id UUID NOT NULL UNIQUE,
    PRIMARY KEY (domain_id,principal),
    FOREIGN KEY (domain_id,principal) REFERENCES lm_control.access_subject(domain_id,principal)
);

CREATE TABLE lm_control.access_event (
    event_id UUID PRIMARY KEY,
    domain_id TEXT NOT NULL,
    principal TEXT NOT NULL,
    revision BIGINT NOT NULL CHECK (revision>0),
    actor TEXT NOT NULL CHECK (length(trim(actor))>0),
    idempotency_key TEXT NOT NULL CHECK (length(trim(idempotency_key))>0),
    request_sha256 TEXT NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
    request JSONB NOT NULL CHECK (jsonb_typeof(request)='object'),
    receipt_sha256 TEXT NOT NULL CHECK (receipt_sha256 ~ '^[0-9a-f]{64}$'),
    receipt JSONB NOT NULL CHECK (jsonb_typeof(receipt)='object'),
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (actor,idempotency_key),
    UNIQUE (domain_id,principal,revision),
    FOREIGN KEY (domain_id,principal) REFERENCES lm_control.access_subject(domain_id,principal)
);
ALTER TABLE lm_control.access_policy ADD CONSTRAINT access_policy_event
    FOREIGN KEY (event_id) REFERENCES lm_control.access_event(event_id);
CREATE TRIGGER immutable_access_event BEFORE UPDATE OR DELETE ON lm_control.access_event
    FOR EACH ROW EXECUTE FUNCTION lm_control.immutable_decision();

CREATE FUNCTION lm_control.access_policy_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Revoke by appending an empty grant set'; END IF;
    IF (NEW.domain_id,NEW.principal) IS DISTINCT FROM (OLD.domain_id,OLD.principal)
       OR NEW.revision<>OLD.revision+1 OR NEW.event_id=OLD.event_id THEN
        RAISE EXCEPTION 'Access policy key is immutable; advance revision and audit event';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER access_policy_guard BEFORE UPDATE OR DELETE ON lm_control.access_policy
    FOR EACH ROW EXECUTE FUNCTION lm_control.access_policy_guard();
