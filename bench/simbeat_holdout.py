"""Release staged TEST outcomes after frozen VALID selection; no model execution."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import simbeat_inputs as inputs
from simbeat_audit import audit_selection, digest, model_check, read, require


def verify_release(envelope, corpus, lock, manifest):
    expected = manifest['input_bundle']['corpora'][corpus]['heldout_sha256']
    require(envelope['selection_sha256'] == digest(lock) and
            envelope['manifest_sha256'] == digest(manifest) and envelope['corpus'] == corpus and
            envelope['source_sha256'] == expected, 'Held-out release identity mismatch')
    require(hashlib.sha256(envelope['source_text'].encode('utf-8')).hexdigest() == expected,
            'Held-out release content mismatch')
    payload = json.loads(envelope['source_text'])
    try:
        inputs.validate_payload(payload, manifest['input_bundle']['corpora'][corpus]['kind'], heldout=True)
    except inputs.InputError as exc:
        require(False, f'Invalid held-out payload: {exc}')
    return payload


def release_labels(work, corpus, lock, manifest, valid, *, root=None):
    """The sole fresh-run TEST label reader. Resume reuses the bound release.

    Provisioning is separate from experiment execution. The source payload is
    read once and committed atomically; a crash before commit may retry the read.
    """
    work = Path(work)
    require(manifest['protocol'] == 'simbeat-v2', 'Held-out release requires v2 inputs')
    require(read(work / 'selection.json') == lock and read(work / 'manifest.json') == manifest,
            'Frozen selection/manifest mismatch')
    audit_selection(manifest, lock, valid)
    require(inputs.public_manifest(root) == manifest['input_bundle'], 'Staged input manifest changed')
    # Verify selected serialized models before exposing any outcome.
    for label in ('chosen', 'jaro_winkler'):
        variant = lock['chosen_variant'] if label == 'chosen' else label
        model_check(work / corpus / 'models' / hashlib.sha256(variant.encode()).hexdigest()[:16],
                    valid[variant][corpus])
    path = work / corpus / 'heldout_release.json'
    if path.exists():
        return verify_release(read(path), corpus, lock, manifest)
    root = Path(root) if root is not None else inputs.DEFAULT_INPUTS
    raw = (root / corpus / 'heldout.json').read_bytes()
    envelope = {'selection_sha256': digest(lock), 'manifest_sha256': digest(manifest), 'corpus': corpus,
                'source_sha256': manifest['input_bundle']['corpora'][corpus]['heldout_sha256'],
                'source_text': raw.decode('utf-8')}
    payload = verify_release(envelope, corpus, lock, manifest)
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(envelope, sort_keys=True, allow_nan=False) + '\n')
    tmp.replace(path)
    return payload
