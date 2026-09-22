-- Additive workflow service. Version-zero prototype rows retain their old shape/meaning.
-- No privileges or RLS are installed; application authentication is a separate gate.
ALTER TABLE lm_control.steward_task
    ADD COLUMN workflow_schema INTEGER NOT NULL DEFAULT 0 CHECK (workflow_schema IN (0,1)),
    ADD COLUMN domain_version INTEGER,
    ADD COLUMN definition JSONB,
    ADD COLUMN definition_sha256 TEXT,
    ADD COLUMN lease_token UUID,
    ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD CONSTRAINT workflow_task_domain FOREIGN KEY (domain_id,domain_version)
        REFERENCES lm_control.domain_version(domain_id,version),
    ADD CONSTRAINT workflow_task_shape CHECK (
        (workflow_schema=0 AND domain_version IS NULL AND definition IS NULL AND definition_sha256 IS NULL AND lease_token IS NULL)
        OR (workflow_schema=1 AND domain_version IS NOT NULL AND definition IS NOT NULL
            AND jsonb_typeof(definition)='object' AND definition_sha256 IS NOT NULL
            AND definition_sha256 ~ '^[0-9a-f]{64}$'
            AND ((state='claimed')=(lease_token IS NOT NULL))));
CREATE INDEX workflow_task_inbox ON lm_control.steward_task(domain_id,domain_version,priority DESC,task_id)
    WHERE workflow_schema=1;

ALTER TABLE lm_control.operation
    ADD COLUMN workflow_schema INTEGER NOT NULL DEFAULT 0 CHECK (workflow_schema IN (0,1)),
    ADD COLUMN domain_version INTEGER,
    ADD COLUMN kind TEXT,
    ADD COLUMN task_id UUID,
    ADD COLUMN approved_by TEXT,
    ADD COLUMN approval_reason TEXT,
    ADD COLUMN approved_at TIMESTAMPTZ,
    ADD CONSTRAINT workflow_operation_domain FOREIGN KEY (domain_id,domain_version)
        REFERENCES lm_control.domain_version(domain_id,version),
    ADD CONSTRAINT workflow_operation_task FOREIGN KEY (domain_id,task_id)
        REFERENCES lm_control.steward_task(domain_id,task_id),
    ADD CONSTRAINT workflow_operation_shape CHECK (
        (workflow_schema=0 AND domain_version IS NULL AND kind IS NULL AND task_id IS NULL
            AND approved_by IS NULL AND approval_reason IS NULL AND approved_at IS NULL)
        OR (workflow_schema=1 AND domain_version IS NOT NULL AND task_id IS NOT NULL
            AND kind IS NOT NULL AND kind IN ('merge','override','split_new','restore_merge')
            AND state<>'draft' AND (state<>'pending_approval' OR approved_by IS NULL))),
    ADD CONSTRAINT workflow_independent_approval CHECK (workflow_schema=0 OR
        ((approved_by IS NULL AND approval_reason IS NULL AND approved_at IS NULL
            AND state NOT IN ('approved','applying','published')) OR
         (approved_by IS NOT NULL AND length(trim(approved_by))>0 AND approved_by<>caller
            AND approval_reason IS NOT NULL AND length(trim(approval_reason))>0 AND approved_at IS NOT NULL))),
    ADD CONSTRAINT workflow_publication_shape CHECK (workflow_schema=0 OR
        ((state='published')=(publication_id IS NOT NULL)));
CREATE UNIQUE INDEX workflow_operation_per_task ON lm_control.operation(domain_id,task_id)
    WHERE workflow_schema=1;

CREATE TABLE lm_control.workflow_command (
    command_id UUID PRIMARY KEY,
    sequence BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    domain_id TEXT NOT NULL,
    domain_version INTEGER NOT NULL,
    task_id UUID,
    operation_id UUID,
    actor TEXT NOT NULL CHECK (length(trim(actor))>0),
    idempotency_key TEXT NOT NULL CHECK (length(trim(idempotency_key))>0),
    action TEXT NOT NULL CHECK (action IN ('create_task','claim','renew','release','cancel','propose','approve')),
    request_sha256 TEXT NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
    request JSONB NOT NULL CHECK (jsonb_typeof(request)='object'),
    receipt_sha256 TEXT NOT NULL CHECK (receipt_sha256 ~ '^[0-9a-f]{64}$'),
    receipt JSONB NOT NULL CHECK (jsonb_typeof(receipt)='object'),
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (actor,idempotency_key),
    FOREIGN KEY (domain_id,domain_version) REFERENCES lm_control.domain_version(domain_id,version),
    FOREIGN KEY (domain_id,task_id) REFERENCES lm_control.steward_task(domain_id,task_id),
    FOREIGN KEY (domain_id,operation_id) REFERENCES lm_control.operation(domain_id,operation_id)
);
CREATE INDEX workflow_task_history ON lm_control.workflow_command(domain_id,task_id,sequence);
CREATE INDEX workflow_operation_history ON lm_control.workflow_command(domain_id,operation_id,sequence);
CREATE TRIGGER immutable_workflow_command BEFORE UPDATE OR DELETE ON lm_control.workflow_command
    FOR EACH ROW EXECUTE FUNCTION lm_control.immutable_decision();

CREATE FUNCTION lm_control.workflow_task_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        IF OLD.workflow_schema=1 THEN RAISE EXCEPTION 'Workflow tasks cannot be deleted'; END IF;
        RETURN OLD;
    END IF;
    IF OLD.workflow_schema<>NEW.workflow_schema THEN RAISE EXCEPTION 'Workflow schema is immutable'; END IF;
    IF OLD.workflow_schema=0 THEN RETURN NEW; END IF;
    IF (NEW.domain_id,NEW.task_id,NEW.domain_version,NEW.kind,NEW.entity_ids,NEW.definition,
        NEW.definition_sha256,NEW.created_at,NEW.priority) IS DISTINCT FROM
       (OLD.domain_id,OLD.task_id,OLD.domain_version,OLD.kind,OLD.entity_ids,OLD.definition,
        OLD.definition_sha256,OLD.created_at,OLD.priority) OR NEW.revision<>OLD.revision+1 THEN
        RAISE EXCEPTION 'Workflow task definition is immutable; revision must advance once';
    END IF;
    IF NOT ((OLD.state='open' AND NEW.state IN ('claimed','canceled')) OR
            (OLD.state='claimed' AND NEW.state IN ('claimed','open','resolved','canceled'))) THEN
        RAISE EXCEPTION 'Invalid workflow task transition';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER workflow_task_guard BEFORE UPDATE OR DELETE ON lm_control.steward_task
    FOR EACH ROW EXECUTE FUNCTION lm_control.workflow_task_guard();

CREATE FUNCTION lm_control.workflow_operation_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        IF OLD.workflow_schema=1 THEN RAISE EXCEPTION 'Workflow operations cannot be deleted'; END IF;
        RETURN OLD;
    END IF;
    IF OLD.workflow_schema<>NEW.workflow_schema THEN RAISE EXCEPTION 'Workflow schema is immutable'; END IF;
    IF OLD.workflow_schema=0 THEN RETURN NEW; END IF;
    IF (NEW.operation_id,NEW.domain_id,NEW.domain_version,NEW.kind,NEW.task_id,NEW.caller,
        NEW.idempotency_key,NEW.payload_sha256,NEW.expected_versions,NEW.payload,NEW.created_at) IS DISTINCT FROM
       (OLD.operation_id,OLD.domain_id,OLD.domain_version,OLD.kind,OLD.task_id,OLD.caller,
        OLD.idempotency_key,OLD.payload_sha256,OLD.expected_versions,OLD.payload,OLD.created_at)
       OR NEW.revision<>OLD.revision+1 THEN
        RAISE EXCEPTION 'Workflow intent is immutable; revision must advance once';
    END IF;
    IF OLD.approved_by IS NOT NULL AND (NEW.approved_by,NEW.approval_reason,NEW.approved_at) IS DISTINCT FROM
       (OLD.approved_by,OLD.approval_reason,OLD.approved_at) THEN
        RAISE EXCEPTION 'Workflow approval is immutable';
    END IF;
    IF NOT ((OLD.state='pending_approval' AND NEW.state IN ('approved','conflict')) OR
            (OLD.state='approved' AND NEW.state IN ('applying','conflict','failed')) OR
            (OLD.state='applying' AND NEW.state IN ('published','conflict','failed')) OR
            (OLD.state='failed' AND NEW.state='applying')) THEN
        RAISE EXCEPTION 'Invalid workflow operation transition';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER workflow_operation_guard BEFORE UPDATE OR DELETE ON lm_control.operation
    FOR EACH ROW EXECUTE FUNCTION lm_control.workflow_operation_guard();
