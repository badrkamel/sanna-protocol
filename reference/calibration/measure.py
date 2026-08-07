#!/usr/bin/env python3
"""SAN-881 Phase-B execution contract. NEVER executed against the corpus
in Phase A -- Phase A only authors this module and exercises it via toy
fixtures in tests/reference/test_calibration.py. Running this for real
requires reference/calibration/FREEZE-MANIFEST.json to exist with every
bound SHA-256 verified, which does not happen until the staged-
adjudication workflow in README.md completes under separate
authorization.

Pipeline (all transactional):
  1. Refuse to run unless FREEZE-MANIFEST.json validates against its own
     JSON Schema, THEN verifies against its bound hash pins (corpus_inputs,
     labels_frozen, design_metadata, coverage_manifest, evaluation_profile,
     algorithm, tables, adjudication_log) AND its five provenance fields
     (labeling_context_hash, author/reviewer-semantic/reviewer-contract
     commitment hashes, reveal_verification_ledger hash) -- including
     proving every envelope carries the IDENTICAL labeling_context_hash
     and that the reveal-verification ledger shows every declared
     artifact verified.
  2. Validate ALL frozen schemas (corpus, design metadata, labels,
     coverage manifest) and cross-file population invariants (160
     corpus items, 640 labels) BEFORE any harness execution. Requires a
     clean tracked worktree and a resolvable HEAD.
  3. Build the canonical ephemeral 640-record projection: every
     allowlisted corpus input x {C1,C2,C3,C4}, ids "calx:NNN:CN",
     written ONCE as canonical JSON bytes and that SAME file path is
     handed to both harnesses.
  4. ALWAYS rebuild the TypeScript package first (a pre-existing dist/ is
     never trusted), then invoke BOTH harnesses on the exact projected
     bytes. Each harness's stdout must equal the canonical reserialization
     of its own parsed records (attribution closure); every result's
     check_id must match its id's compound check segment; every tuple's
     outcome/outcome_reason/severity/advisory must be internally
     consistent.
  5. Byte-compare the two canonical outputs; any inequality is FATAL and
     is ALSO recorded as the py_ts_byte_equality_640 gate.
  6. Join frozen labels; emit outcomes.json / rates.json /
     RATES-REPORT.md into results/<freeze_manifest_sha256>/ via an
     atomic rename from a fresh sibling temporary directory -- the final
     hash directory must not already exist (refused otherwise). An
     infrastructure failure removes only the temporary directory (any
     prior hash-addressed results directory is untouched and is never
     presented as current). A semantic-gate failure (any of the nine
     hard gates false) still publishes the complete auditable artifact
     set via the same atomic rename, but the process exits nonzero.
"""
from __future__ import annotations

import decimal
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    Draft202012Validator = None

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
SCHEMAS = HERE / "schemas"

# reference.calibration.validate_design is the SINGLE shared source of the
# full locked outcome/outcome_reason matrix (SAN-881 Phase-A correction):
# authored-label validation (validate_design.check_labels) and live
# measurement validation (this module's _validate_tuple_consistency) must
# never drift apart. SAN-881 PASS 2C.1 additionally imports the six
# labeling-context/ledger primitives verify_frozen_bundle below needs --
# BASE_COMMIT_SHA, SCHEMA_FILES, LABELING_CONTEXT_COMPONENT_NAMES,
# build_labeling_context_components, compute_labeling_context_hash_from_disk,
# LEDGER_CANONICAL_ORDER -- direct imports, never mirrored/reimplemented.
# SAN-881 PASS 2C.1-FIX (defect 1) adds two more: Errors and check_labels
# itself -- the labels_frozen cross-referential coherence check below
# projects every merged frozen-label record into check_labels's own
# SEMANTIC/CONTRACT shapes and invokes THE SAME authoritative validator
# authored labels are checked against, over the VERIFIED design_by_id,
# rather than re-deriving a second, parallel implementation of its rules.
# Fix sys.path the same way validate_design.py does -- `python3
# reference/calibration/measure.py` direct invocation puts this file's OWN
# directory on sys.path[0], not the repo root.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from reference.calibration.validate_design import (  # noqa: E402
    REASON_MATRIX,
    BASE_COMMIT_SHA,
    SCHEMA_FILES,
    LABELING_CONTEXT_COMPONENT_NAMES,
    build_labeling_context_components,
    compute_labeling_context_hash_from_disk,
    LEDGER_CANONICAL_ORDER,
    Errors,
    check_labels,
)

CHECK_IDS = ("C1", "C2", "C3", "C4")
_STRATA = (
    "in_domain_nonviolation", "in_domain_violation",
    "determinate_out_of_domain", "indeterminate_or_unsafe",
)
ALLOWED_INPUT_KEYS = {"context", "context_sources", "output"}
SEMANTIC_CORRECTNESS_MAPPING = {
    "NO_VIOLATION": "PASS",
    "VIOLATION": "VIOLATION",
    "INDETERMINATE": "NOT_EVALUATED",
}
CLOSED_OUTCOMES = frozenset(REASON_MATRIX)
CLOSED_SEVERITIES = {"critical", "warning", None}
# Both error-class outcomes fail zero_evaluator_errors -- a bad
# invocation/config is as much a "the evaluator did not produce a
# decided verdict" event as a runtime crash.
ERROR_OUTCOMES = frozenset({"EVALUATOR_ERROR", "CONFIG_ERROR"})

PINNED_GATE_NAMES = (
    "py_ts_byte_equality_640",
    "contract_tuple_agreement_640",
    "zero_evaluator_errors",
    "zero_false_violations",
    "zero_unsafe_violations",
    "zero_in_domain_escapes",
    "in_domain_semantic_accuracy_100",
    "deliberate_abstention_correct_100",
    "zero_envelope_breaches_640",
)

decimal.getcontext().prec = 50


class InfrastructureFailure(RuntimeError):
    """A run-breaking failure (crash, nonzero exit, malformed/duplicate/
    missing result, byte mismatch between harnesses, publication
    precondition violated). Produces NO final result directory -- stale
    success artifacts can never survive a failed run."""


class FreezeGateRefused(RuntimeError):
    """FREEZE-MANIFEST.json is absent, schema-invalid, or a bound hash /
    provenance field does not verify."""


# ---------------------------------------------------------------------
# Freeze gate
# ---------------------------------------------------------------------

def _read_bytes_or_fail(path: Path, label: str, exc_cls: type) -> bytes:
    """SAN-881 PASS 2C.1-FIX (defect 3): fixed-name helper. Reads `path`
    as raw bytes, translating ANY OSError (a directory in place of the
    file, a permission error, ...) into `exc_cls` -- a fixed,
    canonical-artifact-name-only message, never the absolute path, never
    a raw traceback. A directory in place of a file fails the SAME way
    as every other artifact read in this module."""
    try:
        return path.read_bytes()
    except OSError as exc:
        raise exc_cls(f"{label} is unreadable") from exc


def _sha256_or_fail(path: Path, label: str, exc_cls: type) -> str:
    """SAN-881 PASS 2C.1-FIX (defect 3): fixed-name helper. SHA-256 hex
    digest of `path`'s raw bytes, routed through `_read_bytes_or_fail` --
    a directory in place of the file fails the SAME way as every other
    artifact read in this module."""
    return hashlib.sha256(_read_bytes_or_fail(path, label, exc_cls)).hexdigest()


def verify_freeze_manifest(manifest: dict[str, Any], repo_root: Path | None = None, cal_dir: Path | None = None) -> list[str]:
    """SAN-881 PASS 2C.1-FIX (defect 2): reduced to a fixed-name RAW-
    HASH-ONLY helper. Returns a list of raw-hash verification failures
    (empty = every bound hash verifies). Never raises on a mismatch --
    callers decide whether to refuse to run. `repo_root`/`cal_dir`
    default to the current module globals looked up AT CALL TIME (not
    baked in as default-argument values), so tests can monkeypatch
    measure.REPO_ROOT / measure.HERE and this function picks up the
    patched value.

    NEVER parses provenance JSON -- that used to happen here, UNGUARDED,
    before any schema gate, which is exactly how a malformed envelope
    (an author envelope that is `[]`, or `{`, or a directory in place of
    the file) used to leak a raw AttributeError / JSONDecodeError /
    IsADirectoryError straight through the fail-closed boundary. The
    cross-envelope `labeling_context_hash` agreement check and the
    reveal-ledger per-entry `verified` check this function used to
    perform ALSO moved entirely into verify_frozen_bundle, which performs
    them ONLY over documents already proven schema-valid, and via the
    from-disk RECOMPUTED context hash -- a strictly stronger, ground-
    truth check than the pairwise cross-envelope comparison this
    function used to make. Every failure message names the artifact by
    its CANONICAL NAME only (`Path.name`), never an absolute filesystem
    path."""
    if repo_root is None:
        repo_root = REPO_ROOT
    if cal_dir is None:
        cal_dir = HERE
    errors: list[str] = []

    def _check_hash_bindings(bindings: dict[str, Path]) -> None:
        for key, path in bindings.items():
            expected = manifest.get(key)
            if expected is None:
                errors.append(f"FREEZE-MANIFEST.json missing required key {key}")
                continue
            if not path.exists():
                errors.append(f"{key}: bound file {path.name} does not exist")
                continue
            try:
                actual = _sha256_or_fail(path, path.name, FreezeGateRefused)
            except FreezeGateRefused as exc:
                errors.append(f"{key}: {exc}")
                continue
            if actual != expected:
                errors.append(f"{key}: hash mismatch (manifest says {expected}, actual {actual})")

    _check_hash_bindings({
        "corpus_inputs_sha256": cal_dir / "corpus_inputs.json",
        "design_metadata_sha256": cal_dir / "design_metadata.json",
        "coverage_manifest_sha256": cal_dir / "coverage_manifest.json",
        "evaluation_profile_sha256": cal_dir / "evaluation_profile.json",
        "labels_frozen_sha256": cal_dir / "labels_frozen.json",
        "adjudication_log_sha256": cal_dir / "adjudication_log.json",
        "algorithm_sha256": repo_root / "reference" / "spec" / "ALGORITHM-v4-c1c5-reference.md",
        "tables_sha256": repo_root / "reference" / "spec" / "ALGORITHM-v4-tables-v1.json",
    })

    # Provenance bindings: commitment envelopes + reveal ledger. Verified
    # by RAW BYTES hash equality against the manifest's bound values
    # ONLY -- content (parsed JSON) is NEVER inspected here (SAN-881
    # PASS 2C.1-FIX defect 2).
    _check_hash_bindings({
        "author_commitment_sha256": cal_dir / "commitment.json",
        "reviewer_semantic_commitment_sha256": cal_dir / "labels_reviewer_semantic.commitment.json",
        "reviewer_contract_commitment_sha256": cal_dir / "labels_reviewer_contract.commitment.json",
        "reveal_verification_ledger_sha256": cal_dir / "reveal_verification_ledger.json",
    })

    return errors


def _require_clean_tracked_worktree(repo_root: Path) -> str:
    """SAN-881 PASS 2C.2: returns the verified, resolvable HEAD commit
    SHA. Callers capture THIS value once, at gate time, and thread it
    through as the published `runner_git_commit` -- a later, separate
    `git rev-parse HEAD` call at publish time could observe a DIFFERENT
    HEAD than the one this gate actually verified clean, if HEAD moves
    mid-run. `run_pipeline` also calls this function a SECOND time,
    immediately before the atomic rename, to detect exactly that."""
    result = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=no"],
                             cwd=repo_root, capture_output=True, text=True)
    if result.returncode != 0:
        raise InfrastructureFailure(f"git status failed (exit {result.returncode}): {result.stderr.strip()[:500]}")
    if result.stdout.strip():
        raise InfrastructureFailure("clean tracked worktree required before measurement; tracked files have uncommitted changes")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True)
    if head.returncode != 0 or not head.stdout.strip():
        raise InfrastructureFailure("a valid resolvable HEAD is required before measurement")
    return head.stdout.strip()


# ---------------------------------------------------------------------
# SAN-881 PASS 2C.1: the single, shared, centralized frozen-bundle
# verifier. Both measure.run_pipeline and benchmark._rerun_full_freeze_
# verification call ONLY verify_frozen_bundle -- there is no second,
# independent freeze-verification implementation anywhere in this
# project. `load_and_verify_freeze_manifest` and
# `_validate_frozen_schemas_and_population` (the two Phase-A-era
# measure.py-local verifiers this pass retires) no longer exist.
# ---------------------------------------------------------------------

_EVALUATION_PROFILE_ALGORITHM_SHA256 = "49c138595fde5ee517d00d6b41eb815cf1016213a0cb7978ef258560cf5a4c59"
_EVALUATION_PROFILE_TABLES_SHA256 = "0a18dd94bc811bb3166a4f8812e78f2b053a9f8f083b781a21fb0f8371f54ecc"


def _load_json_or_fail(path: Path, label: str, exc_cls: type) -> Any:
    """Reads and JSON-parses `path`, translating "does not exist",
    "unreadable" (any OSError, via `_read_bytes_or_fail` -- including a
    directory in place of the file), "not valid UTF-8"
    (UnicodeDecodeError), and "not valid JSON" (json.JSONDecodeError)
    ALL into `exc_cls` -- never lets a raw OSError / UnicodeDecodeError /
    JSONDecodeError escape verify_frozen_bundle (SAN-881 PASS 2C.1-FIX
    defect 3: the ORIGINAL version here only caught OSError +
    JSONDecodeError, silently missing UnicodeDecodeError), and never
    embeds the absolute `path` itself in the message (artifact-name-only,
    per the fail-closed no-path-leakage contract)."""
    if not path.exists():
        raise exc_cls(f"{label} does not exist")
    raw = _read_bytes_or_fail(path, label, exc_cls)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise exc_cls(f"{label} is unreadable or not valid JSON") from exc


def _named_schema_branch(schema: dict, def_name: str) -> dict:
    """Standalone schema object for schema['$defs'][def_name] (the full
    $defs dict embedded so internal '#/$defs/...' $ref resolution still
    works), WITHOUT the enclosing root oneOf -- the generic JSON-Schema-
    2020-12 $defs-branch construction (mirrors the shape
    validate_design._build_named_schema itself builds, reimplemented
    here as plain schema-composition plumbing -- not one of the six
    approved SAN-881 PASS 2C.1 direct imports, and validate_design.py is
    byte-frozen this pass) so verify_frozen_bundle can pin each
    discriminated envelope to its OWN specific branch (authorEnvelope /
    reviewerSemanticEnvelope / reviewerContractEnvelope /
    mergedFrozenFile) precisely, never relying on root-level `oneOf`
    branch disambiguation to catch a wrong-envelope-kind document."""
    base_id = schema.get("$id") or ""
    return {
        "$schema": schema.get("$schema"),
        "$id": f"{base_id}/{def_name}" if base_id else def_name,
        **schema["$defs"][def_name],
        "$defs": schema["$defs"],
    }


def _schema_validate_or_fail(schema: dict, def_name: str | None, instance: Any, label: str, exc_cls: type) -> None:
    """Whole-instance validation against ONE specific schema shape
    (schema's own root when def_name is None, else the named $defs
    branch). Raises `exc_cls` with a fixed, artifact-name-only message
    on ANY validation error -- never partial/soft acceptance. SAN-881
    PASS 2C.1-FIX (defect 3): a jsonschema ENGINE failure (the validator
    itself raising, rather than yielding validation-error objects --
    e.g. an internal `$ref` resolution failure) is ALSO translated into
    `exc_cls`, never left to escape as a raw exception."""
    target = schema if def_name is None else _named_schema_branch(schema, def_name)
    branch = f" against {def_name}" if def_name else ""
    try:
        errors = sorted(str(e.message) for e in Draft202012Validator(target).iter_errors(instance))
    except Exception as exc:
        raise exc_cls(f"{label} failed schema validation{branch} (schema engine error)") from exc
    if errors:
        raise exc_cls(f"{label} failed schema validation{branch} ({len(errors)} error(s))")


def verify_frozen_bundle(freeze_manifest_path: Path, cal_dir: Path, repo_root: Path) -> dict[str, Any]:
    """THE single, shared frozen-bundle verifier (SAN-881 PASS 2C.1).
    Uses ONLY these three explicit paths -- never a module global (this
    also FIXES a live Phase-A bug: run_pipeline used to verify the
    module-global manifest path regardless of its own `cal_dir`
    argument). Raises ONLY FreezeGateRefused (the FREEZE-MANIFEST.json
    <-> commitment/reviewer envelope <-> reveal-verification-ledger
    cryptographic-provenance chain, and the six schema files
    themselves -- the same artifact grouping verify_freeze_manifest's
    own `provenance_bindings` dict already draws) or InfrastructureFailure
    (a missing jsonschema module; the population/schema/coherence layer
    over corpus_inputs.json, evaluation_profile.json,
    design_metadata.json, labels_frozen.json, coverage_manifest.json,
    adjudication_log.json -- verify_freeze_manifest's own `bindings`
    grouping). Returns the loaded, VERIFIED artifacts run_pipeline
    subsequently consumes: {manifest, corpus_inputs, evaluation_profile,
    design, labels_frozen, coverage_manifest}.

    SAN-881 PASS 2C.1-FIX: labels_frozen.json's cross-referential
    coherence (semantic_truth-vs-contract-outcome, check_id-specific
    severity, advisory-must-be-False, competence-vs-design-stratum) is
    ALSO verified here, via validate_design.check_labels over the
    VERIFIED design_by_id (defect 1); every file read in this function
    is routed through fixed-name helpers that translate OSError
    (including a directory in place of a file), UnicodeDecodeError,
    JSONDecodeError, and jsonschema engine failures into
    FreezeGateRefused/InfrastructureFailure, never a raw traceback
    (defects 2-3); corpus_inputs.json's context/output/context_sources
    fields are type-proven before any string-only operation touches them
    (defect 4).

    Never recomputes a nonce commitment (nonces are intentionally absent
    from every artifact this function reads); never resolves a raw
    committed artifact via an envelope- or ledger-supplied path (only
    the six LEDGER_CANONICAL_ORDER names, resolved against `cal_dir`);
    never embeds an absolute custody path in an error message. Does NOT
    rerun the accepted 2B product predicates or trace machinery (no
    coverage-predicate/product-trace execution over corpus text)."""
    # ---- FREEZE-MANIFEST.json: existence, parse ----
    if not freeze_manifest_path.exists():
        raise FreezeGateRefused(
            "FREEZE-MANIFEST.json does not exist -- refusing to run. This file is produced at the "
            "end of the staged-adjudication workflow (see README.md); Phase A never creates it."
        )
    manifest_raw = _read_bytes_or_fail(freeze_manifest_path, "FREEZE-MANIFEST.json", FreezeGateRefused)
    try:
        manifest = json.loads(manifest_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FreezeGateRefused("FREEZE-MANIFEST.json is unreadable or not valid JSON") from exc

    if Draft202012Validator is None:
        # Fails closed: a missing jsonschema MODULE must never silently
        # skip verification.
        raise InfrastructureFailure(
            "jsonschema module is not installed; verify_frozen_bundle refuses to proceed silently unvalidated"
        )

    # ---- The six schema files: existence, syntactic (check_schema) validity ----
    schemas_dir = cal_dir / "schemas"
    schemas: dict[str, dict] = {}
    for schema_name in SCHEMA_FILES:
        schema_path = schemas_dir / schema_name
        if not schema_path.exists():
            raise FreezeGateRefused(f"required schema {schema_name} does not exist")
        schema_raw = _read_bytes_or_fail(schema_path, schema_name, FreezeGateRefused)
        try:
            schema_obj = json.loads(schema_raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FreezeGateRefused(f"schema {schema_name} is unreadable or not valid JSON") from exc
        try:
            Draft202012Validator.check_schema(schema_obj)
        except Exception as exc:
            raise FreezeGateRefused(f"schema {schema_name} is not a valid Draft 2020-12 schema") from exc
        schemas[schema_name] = schema_obj

    # ---- Manifest: schema-valid at its own root, BEFORE any hash check ----
    _schema_validate_or_fail(schemas["freeze_manifest_schema.json"], None, manifest, "FREEZE-MANIFEST.json", FreezeGateRefused)

    # ---- Bound raw-SHA-256 + provenance verification (unchanged, reused) ----
    hash_errors = verify_freeze_manifest(manifest, repo_root=repo_root, cal_dir=cal_dir)
    if hash_errors:
        raise FreezeGateRefused("FREEZE-MANIFEST.json failed verification:\n" + "\n".join(f"  - {e}" for e in hash_errors))

    # ---- Load + schema-validate the three commitment envelopes + the ledger ----
    commitment = _load_json_or_fail(cal_dir / "commitment.json", "commitment.json", FreezeGateRefused)
    reviewer_semantic = _load_json_or_fail(
        cal_dir / "labels_reviewer_semantic.commitment.json", "labels_reviewer_semantic.commitment.json", FreezeGateRefused)
    reviewer_contract = _load_json_or_fail(
        cal_dir / "labels_reviewer_contract.commitment.json", "labels_reviewer_contract.commitment.json", FreezeGateRefused)
    ledger = _load_json_or_fail(cal_dir / "reveal_verification_ledger.json", "reveal_verification_ledger.json", FreezeGateRefused)

    _schema_validate_or_fail(schemas["commitment_schema.json"], "authorEnvelope", commitment, "commitment.json", FreezeGateRefused)
    _schema_validate_or_fail(
        schemas["commitment_schema.json"], "reviewerSemanticEnvelope", reviewer_semantic,
        "labels_reviewer_semantic.commitment.json", FreezeGateRefused)
    _schema_validate_or_fail(
        schemas["commitment_schema.json"], "reviewerContractEnvelope", reviewer_contract,
        "labels_reviewer_contract.commitment.json", FreezeGateRefused)
    _schema_validate_or_fail(
        schemas["reveal_verification_ledger_schema.json"], None, ledger, "reveal_verification_ledger.json", FreezeGateRefused)

    # ---- From-disk recomputation: COMPLETE component-list equality + context hash ----
    recomputed_components = build_labeling_context_components(cal_dir, repo_root, BASE_COMMIT_SHA)
    if len(recomputed_components) != len(LABELING_CONTEXT_COMPONENT_NAMES):
        raise FreezeGateRefused("recomputed labeling_context_components does not have the pinned eleven-component count")
    if commitment.get("labeling_context_components") != recomputed_components:
        raise FreezeGateRefused(
            "commitment.json: labeling_context_components does not equal the from-disk recomputed component list")

    recomputed_hash_hex = compute_labeling_context_hash_from_disk(cal_dir, repo_root, BASE_COMMIT_SHA).hex()
    for label, doc in (
        ("FREEZE-MANIFEST.json", manifest),
        ("commitment.json", commitment),
        ("labels_reviewer_semantic.commitment.json", reviewer_semantic),
        ("labels_reviewer_contract.commitment.json", reviewer_contract),
        ("reveal_verification_ledger.json", ledger),
    ):
        if doc.get("labeling_context_hash") != recomputed_hash_hex:
            raise FreezeGateRefused(f"{label}: labeling_context_hash does not equal the from-disk recomputed context hash")

    # ---- Ledger: index-by-index cross-check against LEDGER_CANONICAL_ORDER ----
    entries = ledger.get("entries") if isinstance(ledger.get("entries"), list) else []
    envelope_by_key = {
        "author": (commitment, "AUTHOR"),
        "reviewer_semantic": (reviewer_semantic, "REVIEWER_SEMANTIC"),
        "reviewer_contract": (reviewer_contract, "REVIEWER_CONTRACT"),
    }
    for idx, (artifact_name, envelope_key, verified_stage) in enumerate(LEDGER_CANONICAL_ORDER):
        entry = entries[idx] if idx < len(entries) else None
        if not isinstance(entry, dict):
            raise FreezeGateRefused(f"reveal_verification_ledger.json: entry {idx} is missing or malformed")
        if (entry.get("artifact_name"), entry.get("envelope"), entry.get("verified_stage")) != (artifact_name, envelope_key, verified_stage):
            raise FreezeGateRefused(
                f"reveal_verification_ledger.json[{artifact_name}]: entry {idx} does not match the canonical "
                "(artifact_name, envelope, verified_stage) at this position")
        if entry.get("verified") is not True:
            raise FreezeGateRefused(f"reveal_verification_ledger.json[{artifact_name}]: entry is not verified")

        envelope_doc, expected_kind = envelope_by_key[envelope_key]
        if envelope_doc.get("envelope_kind") != expected_kind:
            raise FreezeGateRefused(f"reveal_verification_ledger.json[{artifact_name}]: envelope_kind mismatch against its envelope")
        if envelope_doc.get("corpus_version") != ledger.get("corpus_version"):
            raise FreezeGateRefused(f"reveal_verification_ledger.json[{artifact_name}]: corpus_version mismatch against its envelope")
        if envelope_doc.get("labeling_context_hash") != ledger.get("labeling_context_hash"):
            raise FreezeGateRefused(f"reveal_verification_ledger.json[{artifact_name}]: labeling_context_hash mismatch against its envelope")

        if envelope_key == "author":
            candidates = envelope_doc.get("author_commitments") or []
        else:
            artifact_commitment = envelope_doc.get("artifact_commitment")
            candidates = [artifact_commitment] if isinstance(artifact_commitment, dict) else []
        matching = next((c for c in candidates if isinstance(c, dict) and c.get("artifact_name") == artifact_name), None)
        if matching is None:
            raise FreezeGateRefused(f"reveal_verification_ledger.json[{artifact_name}]: no matching commitment entry in its envelope")
        if matching.get("commitment_hex") != entry.get("commitment_hex"):
            raise FreezeGateRefused(f"reveal_verification_ledger.json[{artifact_name}]: commitment_hex disagrees with its envelope")

        # Canonical-name-only resolution -- NEVER an envelope- or
        # ledger-supplied path. `artifact_name` here is the trusted
        # LEDGER_CANONICAL_ORDER tuple member at this index, never
        # entry.get("artifact_name").
        raw_path = cal_dir / artifact_name
        if not raw_path.exists():
            raise FreezeGateRefused(f"reveal_verification_ledger.json[{artifact_name}]: committed raw artifact does not exist")
        actual_byte_length = len(_read_bytes_or_fail(raw_path, artifact_name, FreezeGateRefused))
        if matching.get("byte_length") != actual_byte_length:
            raise FreezeGateRefused(
                f"reveal_verification_ledger.json[{artifact_name}]: envelope byte_length does not equal the actual raw artifact byte length")
        if entry.get("byte_length") != actual_byte_length:
            raise FreezeGateRefused(
                f"reveal_verification_ledger.json[{artifact_name}]: ledger byte_length does not equal the actual raw artifact byte length")

    # ---- corpus_inputs.json: exact ordered cal:000..cal:159 + coherence ----
    corpus = _load_json_or_fail(cal_dir / "corpus_inputs.json", "corpus_inputs.json", InfrastructureFailure)
    if not isinstance(corpus, list) or len(corpus) != 160:
        got = len(corpus) if isinstance(corpus, list) else "non-list"
        raise InfrastructureFailure(f"corpus_inputs.json: expected 160 items, got {got}")
    seen_corpus_tuples: dict[tuple, int] = {}
    for idx, rec in enumerate(corpus):
        expected_id = f"cal:{idx:03d}"
        if not isinstance(rec, dict) or rec.get("id") != expected_id:
            raise InfrastructureFailure(f"corpus_inputs.json[{idx}]: id does not equal the expected ordinal {expected_id}")
        has_context = "context" in rec
        has_sources = "context_sources" in rec
        if has_context == has_sources:
            raise InfrastructureFailure(f"corpus_inputs.json[{expected_id}]: expected exactly one of context/context_sources")
        if "output" not in rec:
            raise InfrastructureFailure(f"corpus_inputs.json[{expected_id}]: missing output")
        allowed = {"id", "output"} | ({"context"} if has_context else {"context_sources"})
        if set(rec.keys()) != allowed:
            raise InfrastructureFailure(f"corpus_inputs.json[{expected_id}]: disallowed keys present")

        # SAN-881 PASS 2C.1-FIX (defect 4): corpus_inputs.json carries NO
        # JSON Schema (by design), so every field's TYPE must be proven
        # EXPLICITLY here, BEFORE duplicate detection, the
        # context_sources join, or any .encode() call below -- an
        # untyped value (context: [], output: {}, a source's text: [])
        # must never reach a str-only operation and crash with a raw
        # TypeError/AttributeError.
        if has_context and not isinstance(rec.get("context"), str):
            raise InfrastructureFailure(f"corpus_inputs.json[{expected_id}]: context must be a string")
        if not isinstance(rec.get("output"), str):
            raise InfrastructureFailure(f"corpus_inputs.json[{expected_id}]: output must be a string")
        if has_sources and not isinstance(rec.get("context_sources"), list):
            raise InfrastructureFailure(f"corpus_inputs.json[{expected_id}]: context_sources must be a list")

        if has_sources:
            for s_idx, source in enumerate(rec["context_sources"]):
                if not isinstance(source, dict) or set(source.keys()) != {"text", "tier"}:
                    raise InfrastructureFailure(f"corpus_inputs.json[{expected_id}].context_sources[{s_idx}]: malformed source shape")
                if not isinstance(source.get("text"), str):
                    raise InfrastructureFailure(f"corpus_inputs.json[{expected_id}].context_sources[{s_idx}]: text must be a string")
                if source.get("tier") != "tier_1":
                    raise InfrastructureFailure(f"corpus_inputs.json[{expected_id}].context_sources[{s_idx}]: non-tier_1 source")
        ctx_text = rec.get("context") if has_context else " ".join(s.get("text", "") for s in rec.get("context_sources", []))
        out_text = rec.get("output", "")
        tuple_key = (ctx_text, out_text)
        if tuple_key in seen_corpus_tuples:
            raise InfrastructureFailure(
                f"corpus_inputs.json[{expected_id}]: duplicate (context, output) tuple, first seen at index {seen_corpus_tuples[tuple_key]}")
        seen_corpus_tuples[tuple_key] = idx
        if len(out_text.encode("utf-8")) > 1_048_576 or len(ctx_text.encode("utf-8")) > 1_048_576:
            raise InfrastructureFailure(f"corpus_inputs.json[{expected_id}]: field byte cap exceeded")
    corpus_ids = {rec["id"] for rec in corpus}

    # ---- evaluation_profile.json: v2 / scope / spec-pin checks ----
    profile = _load_json_or_fail(cal_dir / "evaluation_profile.json", "evaluation_profile.json", InfrastructureFailure)
    if not isinstance(profile, dict) or profile.get("corpus_version") != 2:
        raise InfrastructureFailure("evaluation_profile.json: corpus_version is not 2")
    if profile.get("scope") != list(CHECK_IDS):
        raise InfrastructureFailure("evaluation_profile.json: scope is not exactly [C1, C2, C3, C4]")
    pins = profile.get("spec_pins") if isinstance(profile.get("spec_pins"), dict) else {}
    if pins.get("algorithm_sha256") != _EVALUATION_PROFILE_ALGORITHM_SHA256:
        raise InfrastructureFailure("evaluation_profile.json: spec_pins.algorithm_sha256 mismatch")
    if pins.get("tables_sha256") != _EVALUATION_PROFILE_TABLES_SHA256:
        raise InfrastructureFailure("evaluation_profile.json: spec_pins.tables_sha256 mismatch")

    # ---- design_metadata.json: schema, exact ordered 160 IDs, corpus membership, 10-per-check/stratum ----
    design = _load_json_or_fail(cal_dir / "design_metadata.json", "design_metadata.json", InfrastructureFailure)
    items = design.get("items") if isinstance(design, dict) else None
    if not isinstance(items, list) or len(items) != 160:
        got = len(items) if isinstance(items, list) else "non-list"
        raise InfrastructureFailure(f"design_metadata.json: expected 160 items, got {got}")
    _schema_validate_or_fail(schemas["design_metadata_schema.json"], None, design, "design_metadata.json", InfrastructureFailure)
    per_check_stratum: dict[tuple, int] = {}
    for idx, it in enumerate(items):
        expected_id = f"cal:{idx:03d}"
        if it.get("item_id") != expected_id:
            raise InfrastructureFailure(f"design_metadata.json[{idx}]: item_id does not equal the expected ordinal {expected_id}")
        if expected_id not in corpus_ids:
            raise InfrastructureFailure(f"design_metadata.json[{expected_id}]: item_id is not a member of corpus_inputs.json")
        stratum_key = (it.get("target_check_id"), it.get("target_stratum"))
        per_check_stratum[stratum_key] = per_check_stratum.get(stratum_key, 0) + 1
    for check_id in CHECK_IDS:
        for stratum in _STRATA:
            count = per_check_stratum.get((check_id, stratum), 0)
            if count != 10:
                raise InfrastructureFailure(f"design_metadata.json[{check_id}/{stratum}]: expected exactly 10 items, got {count}")
    design_by_id = {it["item_id"]: it for it in items}

    # ---- labels_frozen.json: schema, no duplicates, exact ordered 640 (item_id, check_id), tuple consistency ----
    labels_frozen = _load_json_or_fail(cal_dir / "labels_frozen.json", "labels_frozen.json", InfrastructureFailure)
    if not isinstance(labels_frozen, list) or len(labels_frozen) != 640:
        got = len(labels_frozen) if isinstance(labels_frozen, list) else "non-list"
        raise InfrastructureFailure(f"labels_frozen.json: expected 640 records, got {got}")
    _schema_validate_or_fail(schemas["labels_schema.json"], "mergedFrozenFile", labels_frozen, "labels_frozen.json", InfrastructureFailure)
    seen_label_keys: dict[tuple, int] = {}
    for idx, rec in enumerate(labels_frozen):
        key = (rec.get("item_id"), rec.get("check_id"))
        if key in seen_label_keys:
            raise InfrastructureFailure(f"labels_frozen.json[{idx}]: duplicate (item_id, check_id) {key}, first seen at index {seen_label_keys[key]}")
        seen_label_keys[key] = idx
    semantic_records: list[dict] = []
    contract_records: list[dict] = []
    for idx, rec in enumerate(labels_frozen):
        expected_item_id = f"cal:{idx // 4:03d}"
        expected_check_id = CHECK_IDS[idx % 4]
        if (rec.get("item_id"), rec.get("check_id")) != (expected_item_id, expected_check_id):
            raise InfrastructureFailure(
                f"labels_frozen.json[{idx}]: does not match the canonical (item_id, check_id) "
                f"({expected_item_id}, {expected_check_id}) at this position")
        contract_tuple = rec.get("contract_tuple") or {}
        tuple_error = _validate_tuple_consistency({"id": f"{expected_item_id}:{expected_check_id}", **contract_tuple})
        if tuple_error:
            raise InfrastructureFailure(f"labels_frozen.json[{idx}]: {tuple_error}")
        semantic_records.append({
            "item_id": rec.get("item_id"), "check_id": rec.get("check_id"),
            "semantic_truth": rec.get("semantic_truth"), "semantic_rationale": rec.get("semantic_rationale"),
        })
        contract_records.append({
            "item_id": rec.get("item_id"), "check_id": rec.get("check_id"),
            "contract_tuple": rec.get("contract_tuple"), "competence": rec.get("competence"),
            "contract_rationale": rec.get("contract_rationale"), "spec_refs": rec.get("spec_refs"),
        })

    # SAN-881 PASS 2C.1-FIX (defect 1): the position/duplicate/contract-
    # tuple checks above are necessary but NOT sufficient -- they never
    # cross-check semantic_truth against the contract outcome, check_id-
    # specific severity, advisory-must-be-False, or competence against
    # the item's design stratum (previously silently ACCEPTED:
    # semantic_truth=VIOLATION paired with a PASS contract; a C1
    # violation with severity=warning; advisory=true). Project EACH
    # merged frozen-label record into check_labels's own SEMANTIC and
    # CONTRACT shapes and invoke THE SAME authoritative validator
    # authored labels are checked against, over the VERIFIED
    # design_by_id -- ANY diagnostic fails closed.
    label_coherence_errors = Errors()
    check_labels(label_coherence_errors, semantic_records, contract_records, design_by_id)
    if label_coherence_errors:
        raise InfrastructureFailure(
            "labels_frozen.json failed cross-referential coherence check:\n" +
            "\n".join(f"  - {e}" for e in label_coherence_errors))

    # ---- coverage_manifest.json: schema-valid closed 68-key structure, evidence item_id corpus membership ----
    coverage = _load_json_or_fail(cal_dir / "coverage_manifest.json", "coverage_manifest.json", InfrastructureFailure)
    _schema_validate_or_fail(schemas["coverage_manifest_schema.json"], None, coverage, "coverage_manifest.json", InfrastructureFailure)
    for surface_name, evidence in coverage.items():
        for e_idx, evidence_rec in enumerate(evidence):
            if evidence_rec.get("item_id") not in corpus_ids:
                raise InfrastructureFailure(f"coverage_manifest.json[{surface_name}][{e_idx}]: item_id is not a member of corpus_inputs.json")

    # ---- adjudication_log.json: no dedicated schema; parse-only (hash binding already verified above) ----
    _load_json_or_fail(cal_dir / "adjudication_log.json", "adjudication_log.json", InfrastructureFailure)

    return {
        "manifest": manifest,
        "corpus_inputs": corpus,
        "evaluation_profile": profile,
        "design": design,
        "labels_frozen": labels_frozen,
        "coverage_manifest": coverage,
    }


# ---------------------------------------------------------------------
# Canonical projection
# ---------------------------------------------------------------------

def canonical_json_bytes(obj: Any) -> bytes:
    """sorted keys, compact separators, ensure_ascii, single trailing LF."""
    return (json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n").encode("ascii")


def build_projection(corpus_inputs: list[dict]) -> list[dict]:
    """Every allowlisted corpus input x C1-C4, ids EXACTLY "calx:NNN:CN".
    The allowlist is enforced here: only context|context_sources|output
    are read from each source record; any other key (labels, design
    metadata, ids) is NEVER read, so a label leak into the evaluator
    input is structurally impossible."""
    records = []
    for src in corpus_inputs:
        src_id = src["id"]  # "cal:NNN"
        if not (src_id.startswith("cal:") and src_id[4:].isdigit()):
            raise InfrastructureFailure(f"malformed source id {src_id!r}")
        ordinal = src_id[4:]
        ctx_keys = [k for k in ("context", "context_sources") if k in src]
        if len(ctx_keys) != 1:
            raise InfrastructureFailure(f"{src_id}: expected exactly one context shape, got {ctx_keys}")
        if "output" not in src:
            raise InfrastructureFailure(f"{src_id}: missing output")
        extra = set(src.keys()) - ALLOWED_INPUT_KEYS - {"id"}
        if extra:
            raise InfrastructureFailure(f"{src_id}: disallowed keys present in projection source: {extra} (label leak guard)")
        for check_id in CHECK_IDS:
            rec = {"id": f"calx:{ordinal}:{check_id}", "check_id": check_id, "output": src["output"]}
            rec[ctx_keys[0]] = src[ctx_keys[0]]
            records.append(rec)
    if len(records) != len(corpus_inputs) * 4:
        raise InfrastructureFailure(f"projection cardinality fatality: expected {len(corpus_inputs) * 4}, got {len(records)}")
    ids = [r["id"] for r in records]
    if len(set(ids)) != len(ids):
        raise InfrastructureFailure("projection cardinality fatality: duplicate calx ids")
    return records


# ---------------------------------------------------------------------
# Dual-harness invocation
# ---------------------------------------------------------------------

def build_typescript_package(ts_dir: Path) -> None:
    """ALWAYS rebuild; a pre-existing dist/ is never trusted. SAN-881
    PASS 2C.2-FIX (defect 2a/2b): npm dependency installation and the
    build step are subprocess-boundary infrastructure, not evaluator
    logic -- an ordinary toolchain failure (nonzero exit via check=True,
    or npm missing from PATH) previously raised a raw
    CalledProcessError/FileNotFoundError straight through this function.
    Both boundaries now translate subprocess.SubprocessError and OSError
    into a bounded InfrastructureFailure; the existing check=True
    nonzero-exit behavior is unchanged, only wrapped."""
    try:
        subprocess.run(["npm", "ci", "--ignore-scripts"], cwd=ts_dir, check=True)
    except (subprocess.SubprocessError, OSError) as exc:
        raise InfrastructureFailure(f"typescript dependency installation failed: {str(exc)[:500]}") from exc
    try:
        subprocess.run(["npm", "run", "build"], cwd=ts_dir, check=True)
    except (subprocess.SubprocessError, OSError) as exc:
        raise InfrastructureFailure(f"typescript build failed: {str(exc)[:500]}") from exc


def _validate_tuple_consistency(rec: dict) -> str | None:
    """Closed outcome/reason/severity/advisory consistency. Returns an
    error string (None if consistent). outcome_reason validation reuses
    the SAME REASON_MATRIX validate_design.check_labels() uses -- a
    reason must not merely be a well-formed code, it must be a member of
    ITS OWN outcome's allowed set (SAN-881 Phase-A correction)."""
    outcome = rec.get("outcome")
    reason = rec.get("outcome_reason")
    severity = rec.get("severity")
    advisory = rec.get("advisory")
    if outcome not in CLOSED_OUTCOMES:
        return f"result {rec.get('id')}: outcome not in closed set"
    if reason not in REASON_MATRIX[outcome]:
        return f"result {rec.get('id')}: outcome_reason not valid for outcome"
    if outcome == "VIOLATION":
        if severity not in ("critical", "warning"):
            return f"result {rec.get('id')}: severity must be critical|warning when outcome is VIOLATION"
    else:
        if severity is not None:
            return f"result {rec.get('id')}: severity must be null unless outcome is VIOLATION"
    if not isinstance(advisory, bool):
        return f"result {rec.get('id')}: advisory must be a boolean"
    return None


def run_harness(cmd: list[str], projection_path: Path, projection: list[dict], tag: str) -> tuple[bytes, list[dict]]:
    # SAN-881 PASS 2C.2-FIX (defect 2c): the launch itself -- distinct
    # from the EXISTING, PRESERVED nonzero-exit check immediately below
    # (a harness that launched and exited nonzero) -- is now guarded: a
    # harness binary that fails to start at all (missing from PATH, not
    # executable, ...) previously raised a raw FileNotFoundError/OSError
    # straight through this function.
    try:
        result = subprocess.run(cmd + [str(projection_path)], capture_output=True, text=False, cwd=REPO_ROOT)
    except (subprocess.SubprocessError, OSError) as exc:
        raise InfrastructureFailure(f"{tag} harness process launch failed: {str(exc)[:500]}") from exc
    if result.returncode != 0:
        raise InfrastructureFailure(f"{tag} harness exited {result.returncode}: {result.stderr.decode(errors='replace')[:2000]}")
    out_bytes = result.stdout
    try:
        parsed = json.loads(out_bytes)
    except json.JSONDecodeError as exc:
        raise InfrastructureFailure(f"{tag} harness produced malformed JSON: {exc}") from exc
    if not isinstance(parsed, list) or len(parsed) != len(projection):
        raise InfrastructureFailure(f"{tag} harness returned {len(parsed) if isinstance(parsed, list) else 'non-list'} results, expected {len(projection)}")

    # attribution closure: stdout must equal the canonical reserialization
    # of its own parsed records.
    if canonical_json_bytes(parsed) != out_bytes:
        raise InfrastructureFailure(f"{tag} harness stdout is not the canonical reserialization of its parsed records (attribution closure failure)")

    seen_ids = set()
    for rec in parsed:
        required = {"id", "check_id", "outcome", "outcome_reason", "severity", "advisory"}
        if set(rec.keys()) != required:
            raise InfrastructureFailure(f"{tag} harness result has malformed shape")
        if rec["id"] in seen_ids:
            raise InfrastructureFailure(f"{tag} harness duplicate result id")
        seen_ids.add(rec["id"])
        id_parts = rec["id"].split(":")
        if len(id_parts) != 3 or id_parts[2] != rec["check_id"]:
            raise InfrastructureFailure(f"{tag} harness result check_id does not match its projected compound id")
        tuple_error = _validate_tuple_consistency(rec)
        if tuple_error:
            raise InfrastructureFailure(f"{tag} harness: {tuple_error}")
    if seen_ids != {r["id"] for r in projection}:
        raise InfrastructureFailure(f"{tag} harness result id set does not match the projection id set")
    return out_bytes, parsed


def run_dual_harness(projection: list[dict], workdir: Path) -> tuple[bytes, bytes, list[dict], list[dict]]:
    """SAN-881 PASS 2C.2: returns the FOUR raw values -- python_bytes,
    typescript_bytes, python_results, typescript_results -- never a
    single combined hash (that collapsing is exactly what made
    independent per-SDK replay binding impossible). STILL refuses
    (InfrastructureFailure, the py_ts_byte_equality_640 condition) if
    the two canonical byte streams differ; the EQUALITY GATE itself is
    computed downstream, by compute_rates, directly from these same two
    byte strings -- never a boolean this function decides on the gate's
    behalf."""
    ts_dir = REPO_ROOT / "reference" / "ts"
    build_typescript_package(ts_dir)

    # ONE canonical projection file, written once; the SAME path is
    # handed to both harnesses.
    projection_path = workdir / "projection.json"
    projection_path.write_bytes(canonical_json_bytes(projection))

    py_bytes, py_results = run_harness(
        [sys.executable, str(REPO_ROOT / "reference" / "diff_harness.py")], projection_path, projection, "py")
    ts_bytes, ts_results = run_harness(
        ["node", str(ts_dir / "dist" / "src" / "diff_harness.js")], projection_path, projection, "ts")
    if py_bytes != ts_bytes:
        raise InfrastructureFailure("py_ts_byte_equality_640 FAILED: Python and TypeScript harness outputs are not byte-identical")
    return py_bytes, ts_bytes, py_results, ts_results


# ---------------------------------------------------------------------
# Rates / gates
# ---------------------------------------------------------------------

def _ratio(numerator: int, denominator: int) -> dict[str, Any]:
    if denominator == 0:
        return {"numerator": numerator, "denominator": 0, "value": None}
    value = (decimal.Decimal(numerator) / decimal.Decimal(denominator)).quantize(
        decimal.Decimal("0.0001"), rounding=decimal.ROUND_HALF_EVEN)
    return {"numerator": numerator, "denominator": denominator, "value": str(value)}


def join_labels(projection_results: list[dict], labels_frozen: list[dict]) -> list[dict]:
    """Join calx:NNN:CN results against labels_frozen.json {item_id: cal:NNN, check_id}."""
    labels_by_key = {(r["item_id"], r["check_id"]): r for r in labels_frozen}
    joined = []
    for rec in projection_results:
        ordinal, check_id = rec["id"].split(":")[1], rec["id"].split(":")[2]
        item_id = f"cal:{ordinal}"
        label = labels_by_key.get((item_id, check_id))
        if label is None:
            raise InfrastructureFailure(f"no frozen label for {item_id}/{check_id}")
        joined.append({**rec, "item_id": item_id, "label": label})
    return joined


def compute_rates(joined: list[dict], design_by_id: dict[str, dict], *,
                   python_output_bytes: bytes, typescript_output_bytes: bytes) -> dict[str, Any]:
    """Per-check metrics over two populations: primary (the check's own
    40 target items) and secondary (all 160, aggregate only). NEVER
    pooled across checks (640 pooled is explicitly forbidden).

    SAN-881 PASS 2C.2: `python_output_bytes`/`typescript_output_bytes`
    are REQUIRED, keyword-only, raw bytes -- the py_ts_byte_equality_640
    gate is DERIVED directly from their equality, never a caller-
    supplied boolean, never defaulted True."""
    gates: dict[str, bool] = {}

    gates["py_ts_byte_equality_640"] = python_output_bytes == typescript_output_bytes

    envelope_breaches = sum(1 for r in joined if r["outcome_reason"] == "envelope_exceeded")
    gates["zero_envelope_breaches_640"] = envelope_breaches == 0

    contract_agree = sum(
        1 for r in joined
        if (r["outcome"], r["outcome_reason"], r["severity"], r["advisory"]) ==
        (r["label"]["contract_tuple"]["outcome"], r["label"]["contract_tuple"]["outcome_reason"],
         r["label"]["contract_tuple"]["severity"], r["label"]["contract_tuple"]["advisory"])
    )
    gates["contract_tuple_agreement_640"] = contract_agree == len(joined)

    # zero_evaluator_errors keys on OUTCOME (an infrastructure-style
    # evaluator failure marker), NEVER on outcome_reason -- a record can
    # carry outcome_reason == "evaluator_exception" only paired with
    # outcome == "EVALUATOR_ERROR"; outcome is the field this gate reads.
    # BOTH error-class outcomes (EVALUATOR_ERROR: runtime crash;
    # CONFIG_ERROR: bad invocation/configuration) fail this gate (SAN-881
    # Phase-A correction) -- neither is a decided verdict.
    evaluator_errors = sum(1 for r in joined if r["outcome"] in ERROR_OUTCOMES)
    gates["zero_evaluator_errors"] = evaluator_errors == 0

    false_violations = 0
    unsafe_violations = 0
    in_domain_escapes = 0
    deliberate_abstention_correct = True
    in_domain_semantic_accuracy = True

    for r in joined:
        truth = r["label"]["semantic_truth"]
        outcome = r["outcome"]
        design_item = design_by_id.get(r["item_id"], {})
        is_target = design_item.get("target_check_id") == r["check_id"]

        if truth == "NO_VIOLATION" and outcome == "VIOLATION":
            false_violations += 1
        if truth == "INDETERMINATE" and outcome == "VIOLATION":
            unsafe_violations += 1
        # escape = a true VIOLATION that PASSES silently. NOT_EVALUATED on
        # a true VIOLATION is a coverage-loss / recall miss (tracked via
        # coverage_loss_abstention_rate below), never an escape.
        if truth == "VIOLATION" and outcome == "PASS":
            if is_target and design_item.get("target_stratum") == "in_domain_violation":
                in_domain_escapes += 1

        if is_target and design_item.get("target_stratum") in ("in_domain_nonviolation", "in_domain_violation"):
            if outcome != SEMANTIC_CORRECTNESS_MAPPING.get(truth):
                in_domain_semantic_accuracy = False

        if is_target and design_item.get("target_stratum") == "indeterminate_or_unsafe":
            if not (outcome == "NOT_EVALUATED" and r["outcome_reason"] == r["label"]["contract_tuple"]["outcome_reason"]):
                deliberate_abstention_correct = False

    gates["zero_false_violations"] = false_violations == 0
    gates["zero_unsafe_violations"] = unsafe_violations == 0
    gates["zero_in_domain_escapes"] = in_domain_escapes == 0
    gates["in_domain_semantic_accuracy_100"] = in_domain_semantic_accuracy
    gates["deliberate_abstention_correct_100"] = deliberate_abstention_correct

    assert set(gates) == set(PINNED_GATE_NAMES), f"gate set drift: {set(gates) ^ set(PINNED_GATE_NAMES)}"
    gates = {name: gates[name] for name in PINNED_GATE_NAMES}

    def confusion_of(records: list[dict]) -> dict[str, dict[str, int]]:
        confusion: dict[str, dict[str, int]] = {}
        for r in records:
            confusion.setdefault(r["label"]["semantic_truth"], {}).setdefault(r["outcome"], 0)
            confusion[r["label"]["semantic_truth"]][r["outcome"]] += 1
        return confusion

    def pop_metrics(records: list[dict], include_by_stratum: bool = True) -> dict[str, Any]:
        n_violation_truth = sum(1 for r in records if r["label"]["semantic_truth"] == "VIOLATION")
        n_novio_truth = sum(1 for r in records if r["label"]["semantic_truth"] == "NO_VIOLATION")
        n_indet_truth = sum(1 for r in records if r["label"]["semantic_truth"] == "INDETERMINATE")
        n_determinate = n_violation_truth + n_novio_truth
        emitted_violation = [r for r in records if r["outcome"] == "VIOLATION"]
        sem_violation_among_emitted = sum(1 for r in emitted_violation if r["label"]["semantic_truth"] == "VIOLATION")
        detected = sum(1 for r in records if r["label"]["semantic_truth"] == "VIOLATION" and r["outcome"] == "VIOLATION")
        false_v = sum(1 for r in records if r["label"]["semantic_truth"] == "NO_VIOLATION" and r["outcome"] == "VIOLATION")
        unsafe_v = sum(1 for r in records if r["label"]["semantic_truth"] == "INDETERMINATE" and r["outcome"] == "VIOLATION")
        # escape: PASS only (see gate-level fix above)
        esc = sum(1 for r in records if r["label"]["semantic_truth"] == "VIOLATION" and r["outcome"] == "PASS")
        cov_loss = sum(1 for r in records if r["label"]["semantic_truth"] != "INDETERMINATE" and r["outcome"] == "NOT_EVALUATED")
        correct_abstain = sum(1 for r in records if r["label"]["semantic_truth"] == "INDETERMINATE" and r["outcome"] == "NOT_EVALUATED")
        exact_conformance = sum(
            1 for r in records
            if (r["outcome"], r["outcome_reason"], r["severity"], r["advisory"]) ==
            (r["label"]["contract_tuple"]["outcome"], r["label"]["contract_tuple"]["outcome_reason"],
             r["label"]["contract_tuple"]["severity"], r["label"]["contract_tuple"]["advisory"])
        )
        scenario_count = len({design_by_id.get(r["item_id"], {}).get("scenario_id") for r in records})

        result = {
            "item_count": len(records),
            "scenario_count": scenario_count,
            "precision": _ratio(sem_violation_among_emitted, len(emitted_violation)),
            "recall": _ratio(detected, n_violation_truth),
            "false_violation_rate": _ratio(false_v, n_novio_truth),
            "unsafe_violation_rate": _ratio(unsafe_v, n_indet_truth),
            "escape_rate": _ratio(esc, n_violation_truth),
            "coverage_loss_abstention_rate": _ratio(cov_loss, n_determinate),
            "correct_abstention_rate": _ratio(correct_abstain, n_indet_truth),
            "exact_contract_conformance": _ratio(exact_conformance, len(records)),
            "confusion_matrix": confusion_of(records),
        }
        if include_by_stratum:
            # SECONDARY reporting stays aggregate-only (SAN-881 Phase-A
            # correction): the per-target_stratum confusion breakdown is a
            # PRIMARY-population-only view. Secondary (all 160, aggregate)
            # never carries this key.
            by_stratum: dict[str, dict[str, dict[str, int]]] = {}
            for r in records:
                stratum = design_by_id.get(r["item_id"], {}).get("target_stratum", "unknown")
                by_stratum.setdefault(stratum, {}).setdefault(r["label"]["semantic_truth"], {}).setdefault(r["outcome"], 0)
                by_stratum[stratum][r["label"]["semantic_truth"]][r["outcome"]] += 1
            result["confusion_by_stratum"] = by_stratum
        return result

    per_check: dict[str, Any] = {}
    for check_id in CHECK_IDS:
        check_records = [r for r in joined if r["check_id"] == check_id]
        target_records = [r for r in check_records if design_by_id.get(r["item_id"], {}).get("target_check_id") == check_id]
        per_check[check_id] = {
            "primary_target_40": pop_metrics(target_records, include_by_stratum=True),
            "secondary_all_160": pop_metrics(check_records, include_by_stratum=False),
        }

    corpus_impact: dict[str, dict[str, Any]] = {}
    for r in joined:
        design_item = design_by_id.get(r["item_id"], {})
        if design_item.get("target_stratum") != "determinate_out_of_domain":
            continue
        if r["label"].get("competence") != "KNOWN_COVERAGE_GAP":
            continue
        feat = design_item.get("introduced_feature")
        if not feat:
            continue
        # keyed by the COMPLETE introduced_feature object so two distinct
        # features sharing only `kind` (e.g. two different comparator
        # tokens) never collapse into the same ranking bucket.
        feat_key = canonical_json_bytes(feat).decode("ascii")
        key = f"{r['check_id']}:{feat_key}"
        bucket = corpus_impact.setdefault(key, {"check_id": r["check_id"], "introduced_feature": feat, "item_ids": set()})
        bucket["item_ids"].add(r["item_id"])
    ranking = sorted(
        (
            {
                "check_id": v["check_id"],
                "introduced_feature": v["introduced_feature"],
                "supporting_item_count": len(v["item_ids"]),
                "item_ids": sorted(v["item_ids"]),
            }
            for v in corpus_impact.values()
        ),
        key=lambda x: (-x["supporting_item_count"], x["check_id"], json.dumps(x["introduced_feature"], sort_keys=True)),
    )

    return {
        "gates": gates,
        "nine_gates_passed": all(gates.values()),
        "per_check": per_check,
        "corpus_impact_ranking": ranking,
        "record_count": len(joined),
        "caveat": (
            "PURPOSIVE SYNTHETIC DIAGNOSTIC CORPUS. Results are corpus-relative and are NOT "
            "estimates of real-world prevalence, precision, recall, or production performance. "
            "No confidence intervals are reported (no Wilson intervals anywhere): a purposive "
            "synthetic corpus with paired minimal-pair scenarios cannot support statistical "
            "inference over a real-world population."
        ),
    }


def render_report(rates: dict[str, Any]) -> str:
    def pct(v: dict[str, Any]) -> str:
        if v["value"] is None:
            return "null"
        return f"{decimal.Decimal(v['value']) * 100:.2f}%"

    lines = [
        "# SAN-881 Calibration RATES-REPORT",
        "",
        "PURPOSIVE SYNTHETIC DIAGNOSTIC CORPUS. Results are corpus-relative and are NOT",
        "estimates of real-world prevalence, precision, recall, or production performance.",
        "",
        f"Record count: {rates['record_count']}",
        f"Nine hard gates passed: {rates['nine_gates_passed']}",
        "",
        "## Gates",
        "",
    ]
    for name, passed in rates["gates"].items():
        lines.append(f"- {name}: {'PASS' if passed else 'FAIL'}")
    lines.append("")
    lines.append("## Per-check rates")
    for check_id, pops in rates["per_check"].items():
        lines.append(f"### {check_id}")
        for pop_name, pop in pops.items():
            lines.append(f"- {pop_name}: items={pop['item_count']} scenarios={pop['scenario_count']}")
            for metric in ("precision", "recall", "false_violation_rate", "unsafe_violation_rate",
                           "escape_rate", "coverage_loss_abstention_rate", "correct_abstention_rate",
                           "exact_contract_conformance"):
                v = pop[metric]
                lines.append(f"    - {metric}: {pct(v)} ({v['numerator']}/{v['denominator']})")
    lines.append("")
    lines.append("## Corpus-impact ranking (KNOWN_COVERAGE_GAP, deduped by item, keyed by complete introduced_feature)")
    for entry in rates["corpus_impact_ranking"]:
        lines.append(f"- {entry['check_id']}:{entry['introduced_feature']}: {entry['supporting_item_count']} items {entry['item_ids']}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------
# Transactional orchestration
# ---------------------------------------------------------------------

def run_pipeline(cal_dir: Path | None = None) -> int:
    """Returns process exit code. Writes into results/<freeze_hash>/ via
    an atomic rename from a fresh sibling temporary directory. On
    InfrastructureFailure raised before or during the temp-write phase,
    only the temporary directory is removed (a prior hash-addressed
    results directory, if any, is left completely untouched and is never
    presented as current). On a semantic gate failure, the complete
    artifact set IS published via the same atomic rename and the
    function returns nonzero."""
    if cal_dir is None:
        cal_dir = HERE

    # SAN-881 PASS 2C.1: verify_frozen_bundle is invoked with the EXPLICIT
    # path derived from THIS call's own cal_dir argument -- this fixes a
    # live Phase-A bug where the freeze gate verified the module-global
    # FREEZE_MANIFEST_PATH (always HERE / "FREEZE-MANIFEST.json")
    # regardless of the cal_dir this function was actually invoked with.
    freeze_manifest_path = cal_dir / "FREEZE-MANIFEST.json"
    verified = verify_frozen_bundle(freeze_manifest_path, cal_dir, REPO_ROOT)
    manifest = verified["manifest"]

    # SAN-881 PASS 2C.2: the CAPTURED HEAD from this gate -- never a
    # later, fresh, unverified `git rev-parse HEAD` -- is what
    # outcomes.json eventually records as runner_git_commit. This is
    # event 1 of the pinned publication order: harness -> three writes
    # -> git recheck -> rename.
    captured_head = _require_clean_tracked_worktree(REPO_ROOT)

    freeze_bytes = freeze_manifest_path.read_bytes()
    freeze_hash = hashlib.sha256(freeze_bytes).hexdigest()
    final_dir = cal_dir / "results" / freeze_hash
    if final_dir.exists():
        raise InfrastructureFailure(
            f"results directory for freeze {freeze_hash} already exists; refusing to overwrite a "
            "hash-addressed result. Prior results remain but this run publishes nothing."
        )

    corpus_inputs = verified["corpus_inputs"]
    labels_frozen = verified["labels_frozen"]
    design = verified["design"]
    design_by_id = {it["item_id"]: it for it in design["items"]}

    projection = build_projection(corpus_inputs)

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        python_bytes, typescript_bytes, python_results, typescript_results = run_dual_harness(projection, workdir)

    joined = join_labels(python_results, labels_frozen)
    rates = compute_rates(joined, design_by_id, python_output_bytes=python_bytes, typescript_output_bytes=typescript_bytes)

    tmp_result_dir = cal_dir / "results" / f".tmp-{freeze_hash}-{uuid.uuid4().hex}"
    tmp_result_dir.mkdir(parents=True)
    try:
        outcomes = {
            "freeze_manifest_hash": freeze_hash,
            "component_hashes": manifest,
            "record_count": len(joined),
            "python_output_sha256": hashlib.sha256(python_bytes).hexdigest(),
            "typescript_output_sha256": hashlib.sha256(typescript_bytes).hexdigest(),
            "runner_git_commit": captured_head,
            "measure_py_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "outcomes": [{"id": r["id"], "item_id": r["item_id"], "check_id": r["check_id"],
                          "outcome": r["outcome"], "outcome_reason": r["outcome_reason"],
                          "severity": r["severity"], "advisory": r["advisory"]} for r in joined],
        }
        outcomes_bytes = canonical_json_bytes(outcomes)
        (tmp_result_dir / "outcomes.json").write_bytes(outcomes_bytes)

        # rates.json binds freeze_manifest_sha256 + the RAW outcomes.json
        # bytes hash (never a reserialization).
        rates_with_bindings = {
            **rates,
            "freeze_manifest_sha256": freeze_hash,
            "outcomes_sha256": hashlib.sha256(outcomes_bytes).hexdigest(),
        }
        (tmp_result_dir / "rates.json").write_bytes(canonical_json_bytes(rates_with_bindings))
        (tmp_result_dir / "RATES-REPORT.md").write_text(render_report(rates_with_bindings))

        # SAN-881 PASS 2C.2: publication ordering pin. AFTER all three
        # artifact writes, RECHECK cleanliness and HEAD IMMEDIATELY
        # BEFORE the rename -- a SEPARATE, later verification from the
        # captured_head gate above. If a concurrent commit landed (HEAD
        # moved) or a tracked file went dirty WHILE the harness ran, the
        # artifacts just written would misattribute themselves to a
        # HEAD/worktree state that no longer holds; refuse to publish.
        # Bounded to git state only -- no snapshot subsystem.
        recheck_head = _require_clean_tracked_worktree(REPO_ROOT)
        if recheck_head != captured_head:
            raise InfrastructureFailure(
                f"git HEAD changed during measurement (from {captured_head} to {recheck_head}); "
                "refusing to publish results attributed to a HEAD that no longer matches the "
                "current worktree"
            )

        # The atomic rename is INSIDE this try/except (SAN-881 Phase-A
        # correction): a rename failure must clean up the temp directory
        # exactly like a mid-write failure -- no final artifacts may
        # appear, and any OTHER pre-existing freeze-hash results
        # directory is left completely untouched either way.
        tmp_result_dir.rename(final_dir)
    except BaseException as exc:
        shutil.rmtree(tmp_result_dir, ignore_errors=True)
        if isinstance(exc, (InfrastructureFailure, FreezeGateRefused)):
            raise
        raise InfrastructureFailure(f"publication failed mid-write or mid-rename: {exc}") from exc

    return 0 if rates["nine_gates_passed"] else 1


def main(argv: list[str] | None = None) -> int:
    try:
        return run_pipeline(HERE)
    except (FreezeGateRefused, InfrastructureFailure) as exc:
        sys.stderr.write(f"FATAL: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
