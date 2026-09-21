-- Additive migration. Keep 0001 and every applied migration immutable.
-- Previously approved prototype rows without attribution deliberately fail the
-- new checks; review/export them before upgrading, rather than inventing actors.
ALTER TABLE lm_control.domain_version
    ADD COLUMN revision BIGINT NOT NULL DEFAULT 1 CHECK (revision > 0),
    ADD COLUMN created_by TEXT NOT NULL DEFAULT 'legacy-unattributed' CHECK (length(trim(created_by)) > 0),
    ADD COLUMN approved_by TEXT,
    ADD COLUMN approval_reason TEXT,
    ADD COLUMN approved_at TIMESTAMPTZ,
    ADD CONSTRAINT domain_approval_attribution CHECK (
        (state = 'draft' AND approved_by IS NULL AND approved_at IS NULL AND approval_reason IS NULL) OR
        (state IN ('approved','retired') AND approved_by IS NOT NULL AND length(trim(approved_by)) > 0
         AND approved_by <> created_by AND approved_at IS NOT NULL
         AND approval_reason IS NOT NULL AND length(trim(approval_reason)) > 0));

ALTER TABLE lm_control.source_mapping_version
    ADD COLUMN revision BIGINT NOT NULL DEFAULT 1 CHECK (revision > 0),
    ADD COLUMN created_by TEXT NOT NULL DEFAULT 'legacy-unattributed' CHECK (length(trim(created_by)) > 0),
    ADD COLUMN approved_by TEXT,
    ADD COLUMN approval_reason TEXT,
    ADD COLUMN approved_at TIMESTAMPTZ,
    ADD CONSTRAINT mapping_approval_attribution CHECK (
        (state = 'draft' AND approved_by IS NULL AND approved_at IS NULL AND approval_reason IS NULL) OR
        (state IN ('approved','retired') AND approved_by IS NOT NULL AND length(trim(approved_by)) > 0
         AND approved_by <> created_by AND approved_at IS NOT NULL
         AND approval_reason IS NOT NULL AND length(trim(approval_reason)) > 0));

CREATE TABLE lm_control.execution_version (
    domain_id TEXT NOT NULL,
    execution_id TEXT NOT NULL CHECK (execution_id ~ '^[a-z][a-z0-9_]{0,62}$'),
    version INTEGER NOT NULL CHECK (version > 0),
    domain_version INTEGER NOT NULL,
    left_source_id TEXT NOT NULL,
    left_mapping_version INTEGER NOT NULL,
    right_source_id TEXT NOT NULL,
    right_mapping_version INTEGER NOT NULL,
    definition JSONB NOT NULL CHECK (jsonb_typeof(definition) = 'object'),
    definition_sha256 TEXT NOT NULL CHECK (definition_sha256 ~ '^[0-9a-f]{64}$'),
    state TEXT NOT NULL CHECK (state IN ('draft','approved','retired')),
    revision BIGINT NOT NULL DEFAULT 1 CHECK (revision > 0),
    created_by TEXT NOT NULL CHECK (length(trim(created_by)) > 0),
    approved_by TEXT,
    approval_reason TEXT,
    approved_at TIMESTAMPTZ,
    PRIMARY KEY (domain_id, execution_id, version),
    FOREIGN KEY (domain_id, domain_version) REFERENCES lm_control.domain_version(domain_id, version),
    FOREIGN KEY (domain_id, left_source_id, left_mapping_version)
        REFERENCES lm_control.source_mapping_version(domain_id, source_id, version),
    FOREIGN KEY (domain_id, right_source_id, right_mapping_version)
        REFERENCES lm_control.source_mapping_version(domain_id, source_id, version),
    CHECK (left_source_id <> right_source_id),
    CHECK ((state = 'draft' AND approved_by IS NULL AND approved_at IS NULL AND approval_reason IS NULL) OR
           (state IN ('approved','retired') AND approved_by IS NOT NULL AND length(trim(approved_by)) > 0
            AND approved_by <> created_by AND approved_at IS NOT NULL
            AND approval_reason IS NOT NULL AND length(trim(approval_reason)) > 0))
);

CREATE TABLE lm_control.registry_event (
    event_id UUID PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('domain','mapping','execution')),
    domain_id TEXT NOT NULL REFERENCES lm_control.domain(domain_id),
    object_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    revision BIGINT NOT NULL CHECK (revision > 0),
    action TEXT NOT NULL CHECK (action IN ('draft','approved','retired')),
    actor TEXT NOT NULL CHECK (length(trim(actor)) > 0),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    definition_sha256 TEXT NOT NULL CHECK (definition_sha256 ~ '^[0-9a-f]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (kind, domain_id, object_id, version, revision)
);

CREATE FUNCTION lm_control.registry_version_guard() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Registry versions are immutable; retire the version';
    END IF;
    IF (to_jsonb(NEW) - ARRAY['state','revision','approved_by','approved_at','approval_reason'])
        IS DISTINCT FROM
       (to_jsonb(OLD) - ARRAY['state','revision','approved_by','approved_at','approval_reason']) THEN
        RAISE EXCEPTION 'Registry definitions are immutable; create a new version';
    END IF;
    IF NEW.revision <> OLD.revision + 1 OR NOT
       ((OLD.state = 'draft' AND NEW.state = 'approved') OR
        (OLD.state = 'approved' AND NEW.state = 'retired')) THEN
        RAISE EXCEPTION 'Invalid registry state/revision transition';
    END IF;
    IF OLD.state = 'approved' AND
       (NEW.approved_by, NEW.approved_at, NEW.approval_reason) IS DISTINCT FROM
       (OLD.approved_by, OLD.approved_at, OLD.approval_reason) THEN
        RAISE EXCEPTION 'Approval attribution is immutable';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER domain_version_guard BEFORE UPDATE OR DELETE ON lm_control.domain_version
FOR EACH ROW EXECUTE FUNCTION lm_control.registry_version_guard();
CREATE TRIGGER mapping_version_guard BEFORE UPDATE OR DELETE ON lm_control.source_mapping_version
FOR EACH ROW EXECUTE FUNCTION lm_control.registry_version_guard();
CREATE TRIGGER execution_version_guard BEFORE UPDATE OR DELETE ON lm_control.execution_version
FOR EACH ROW EXECUTE FUNCTION lm_control.registry_version_guard();
CREATE TRIGGER immutable_registry_event BEFORE UPDATE OR DELETE ON lm_control.registry_event
FOR EACH ROW EXECUTE FUNCTION lm_control.immutable_decision();
