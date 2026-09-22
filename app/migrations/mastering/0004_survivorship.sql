-- Additive policy registry. Existing definitions and identity rows are untouched.
CREATE TABLE lm_control.survivorship_version (
    domain_id TEXT NOT NULL,
    policy_id TEXT NOT NULL CHECK (policy_id ~ '^[a-z][a-z0-9_]{0,62}$'),
    version INTEGER NOT NULL CHECK (version > 0),
    domain_version INTEGER NOT NULL,
    definition JSONB NOT NULL CHECK (jsonb_typeof(definition) = 'object'),
    definition_sha256 TEXT NOT NULL CHECK (definition_sha256 ~ '^[0-9a-f]{64}$'),
    state TEXT NOT NULL CHECK (state IN ('draft','approved','retired')),
    revision BIGINT NOT NULL DEFAULT 1 CHECK (revision > 0),
    created_by TEXT NOT NULL CHECK (length(trim(created_by)) > 0),
    approved_by TEXT,
    approval_reason TEXT,
    approved_at TIMESTAMPTZ,
    PRIMARY KEY (domain_id, policy_id, version),
    FOREIGN KEY (domain_id, domain_version) REFERENCES lm_control.domain_version(domain_id, version),
    CHECK ((state = 'draft' AND approved_by IS NULL AND approved_at IS NULL AND approval_reason IS NULL) OR
           (state IN ('approved','retired') AND approved_by IS NOT NULL AND length(trim(approved_by)) > 0
            AND approved_by <> created_by AND approved_at IS NOT NULL
            AND approval_reason IS NOT NULL AND length(trim(approval_reason)) > 0))
);
CREATE TRIGGER survivorship_version_guard BEFORE UPDATE OR DELETE ON lm_control.survivorship_version
FOR EACH ROW EXECUTE FUNCTION lm_control.registry_version_guard();

ALTER TABLE lm_control.registry_event DROP CONSTRAINT registry_event_kind_check;
ALTER TABLE lm_control.registry_event ADD CONSTRAINT registry_event_kind_check
    CHECK (kind IN ('domain','mapping','execution','survivorship'));
