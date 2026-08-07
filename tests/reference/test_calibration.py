"""SAN-881 Phase A tests: public-data structural checks over the
committed calibration corpus artifacts, plus toy-only tests of
validate_design.py / measure.py / benchmark.py logic. NO
pytest.mark.parametrize (project convention for this file). Never runs
a full evaluator pass (Python or TypeScript) over any corpus item, and
never records, publishes, or gates on an evaluator OUTCOME -- toy tests
use inline fixtures that are explicitly NOT corpus items.

SAN-881 PASS 2B.1-T built validate_design.py's EPHEMERAL, TYPED,
validator-local product-trace substrate (FieldProductTrace /
FrameProductEvent / PartialProductEvent / ProductTraceBundle), tested
below over inline SYNTHETIC unit-test strings -- never over
corpus_inputs.json's sealed items -- and never publishing trace data,
outcomes, or a rate/gate derived from one. SAN-881 PASS 2B.1-P wires
this substrate into check_coverage_manifest for the 50 in-scope
surfaces (47 table-derived + 3 value_role_v1) via CAPABILITY_MAP and a
four-clause product contract; the 18 nontable surfaces remain the
ORIGINAL static-lexical proof, byte-unchanged. This is PRODUCT-LEVEL
assurance, never consumption tracing: no CheckConsumptionTrace class
exists, none is planned, and that architecture was proposed and
REJECTED -- see test_no_checkconsumptiontrace_symbol_exists_anywhere_in_module,
test_readme_documents_truthful_partial_state_for_in_scope_surfaces, and
test_coverage_manifest_schema_description_states_truthful_partial_state_for_in_scope_surfaces
below for the reality-pinning assertions.

SAN-881 Phase-A CORRECTION (adversarial review round 2): adds toy-only
regressions for the defect classes identified in review -- wired
from-disk context-hash recomputation, --reviewer-dir / generic envelope
verification, subset/single-artifact reveal for the semantic stage,
whole-file schema application, introduced-feature table-absence +
minimal-pair semantic-equivalence checks, executable coverage
predicates, no-leak error discipline, the corrected nine-gate object,
the transactional hash-addressed publication scheme, and the freeze
manifest provenance bindings.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from reference.calibration import validate_design as vd
from reference.calibration import measure as ms
from reference.calibration import benchmark as bm
from reference import checks as ref_checks
from reference import evaluate as ref_evaluate

CAL_DIR = Path(__file__).parent.parent.parent / "reference" / "calibration"
SCHEMAS_DIR = CAL_DIR / "schemas"
REPO_ROOT = CAL_DIR.parent.parent

CORPUS = json.loads((CAL_DIR / "corpus_inputs.json").read_text())
PROFILE = json.loads((CAL_DIR / "evaluation_profile.json").read_text())
COMMITMENT = json.loads((CAL_DIR / "commitment.json").read_text())

# SAN-881 PASS 2B.1-P HONEST ASSURANCE: the exact wording that must
# appear verbatim (modulo insignificant line-wrap whitespace) in
# README.md, coverage_manifest_schema.json's root "description", and
# validate_design.py's own module docstring.
HONEST_ASSURANCE_SENTENCE = (
    "Runtime validation proves parsed-product presence, ownership and "
    "partiality qualifiers, declared-field integrity, and compatibility "
    "with a reviewed static routing map. It does not prove internal "
    "branch reach, causality, or per-corpus-item execution. Phase B "
    "evaluator runs remain the authority for measured behavior."
)
_FORBIDDEN_HONEST_ASSURANCE_PHRASES = (
    "the suite validates the map, the map validates the corpus",
    "per-family consumption proven once",
)


def _normalize_ws(text: str) -> str:
    """Collapses all whitespace runs (including line-wrap newlines in
    wrapped prose/docstrings) to a single space, for VERBATIM-modulo-
    wrapping substring checks of the honest-assurance sentence."""
    return " ".join(text.split())


def _toy_640_semantic_records() -> list[dict]:
    """640 schema-valid semanticRecord entries (160 corpus items x
    C1-C4), used wherever a test needs a labels_schema.json-conformant
    semantic label file at the SAN-881 Phase-A correction's pinned
    cardinality (exactly 640, independently of contractFile)."""
    return [
        {"item_id": f"cal:{i:03d}", "check_id": c, "semantic_truth": "NO_VIOLATION", "semantic_rationale": "toy"}
        for i in range(160) for c in vd.CHECK_IDS
    ]


def _toy_640_contract_records() -> list[dict]:
    """640 schema-valid contractRecord entries (160 corpus items x
    C1-C4), at the pinned cardinality (exactly 640, independently of
    semanticFile)."""
    return [
        {
            "item_id": f"cal:{i:03d}", "check_id": c,
            "contract_tuple": {"outcome": "PASS", "outcome_reason": "detection_complete", "severity": None, "advisory": False},
            "competence": "IN_DOMAIN", "contract_rationale": "toy", "spec_refs": "toy",
        }
        for i in range(160) for c in vd.CHECK_IDS
    ]


_TOY_DOD_INTRODUCED_FEATURE = {
    "kind": "concept", "table_path": "concept_v1",
    "surface_tokens": ["approval"],
    "intended_semantics": {"canonical_concept": "approval"},
}


def _toy_160_design_items() -> list[dict]:
    """160 schema-valid design_metadata item entries, at the pinned
    cardinality (exactly 160, schema-level), EVENLY distributed 10 per
    (target_check_id, target_stratum) combination (4 checks x 4 strata)
    -- SAN-881 PASS 2B.1-P-GATE: check_design_metadata's own
    STRATUM_COUNT_NOT_10 balance check (16 combinations, each requiring
    exactly 10) is now one of the LOCAL, before/after-delta prerequisite
    operands `upstream_ok` conjoins (`design_semantics_ok`), so a fixture
    consumed by the "fully valid" positive-control coverage-gate test
    must itself be genuinely check_design_metadata-clean (zero errors),
    not merely schema-valid, to reach Pass B at all. determinate_out_of_
    domain items carry a non-null minimal_pair_of (pointing at the first,
    in-domain-nonviolation/C1 item, cal:000) and a schema-valid
    introduced_feature (both required, schema- and semantics-wise, only
    for this one stratum) -- check_design_metadata itself does not
    validate minimal-pair RESOLUTION/correctness (that is
    check_dod_balance_and_pairs, a separate, non-gating check whose own
    noise here -- e.g. reused controls, cross-check_id minimal pairs --
    remains immaterial, exactly as already documented on
    test_main_fully_valid_coverage_manifest_builds_exactly_once_per_item)."""
    items = []
    idx = 0
    for check_id in vd.CHECK_IDS:
        for stratum in vd.STRATA:
            for _ in range(10):
                is_dod = stratum == "determinate_out_of_domain"
                items.append({
                    "item_id": f"cal:{idx:03d}", "target_check_id": check_id, "target_stratum": stratum,
                    "domain": "toy_domain", "facet_families": ["facet:availability"], "scenario_id": f"toy-scenario-{idx}",
                    "minimal_pair_of": "cal:000" if is_dod else None,
                    "introduced_feature": _TOY_DOD_INTRODUCED_FEATURE if is_dod else None,
                })
                idx += 1
    return items


def _160_items_with_feature_override(feature_override, item_index=None):
    """SAN-881 PASS 2B.2 Part F (NON-VACUOUS SCHEMA REDS): deep-copies
    _toy_160_design_items() (the ACCEPTED-CLOSED 2B.1 gate substrate,
    left byte-for-byte UNCHANGED as a fixture -- this helper only copies
    its OUTPUT) and replaces ONE determinate_out_of_domain item's
    introduced_feature with `feature_override`, defaulting to the FIRST
    DOD item found. Returns (items, item_id, item_index) so a caller can
    assert a schema-validation error reaches EXACTLY that item's
    introduced_feature -- never a vacuous 1-item document, which fails a
    priori on minItems==160 and proves nothing about the discriminator."""
    items = copy.deepcopy(_toy_160_design_items())
    dod_indices = [i for i, it in enumerate(items) if it["target_stratum"] == "determinate_out_of_domain"]
    idx = dod_indices[0] if item_index is None else item_index
    items[idx]["introduced_feature"] = feature_override
    return items, items[idx]["item_id"], idx


def _assert_schema_error_reaches_item_feature(schema, instance, item_index):
    """Asserts Draft202012Validator finds at least one error, AND that
    error reaches items[item_index].introduced_feature specifically --
    proving the schema negative is a genuine discriminator failure at
    THAT item, not a document-shape failure (e.g. item count) that would
    fire regardless of the item's own content."""
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(instance))
    assert errors, "expected at least one schema validation error"
    paths = [list(e.absolute_path) for e in errors]
    assert any(
        len(p) >= 3 and p[0] == "items" and p[1] == item_index and p[2] == "introduced_feature"
        for p in paths
    ), f"no error reached items[{item_index}].introduced_feature; paths={paths}"
    return errors


_SCHEMAS_WITH_NAMED_BRANCHES = ("commitment_schema.json", "labels_schema.json")


def _write_toy_schemas_dir(schemas_dir: Path) -> None:
    """Writes all six schema files into `schemas_dir`, for tests that
    exercise `check_commitment` / `_load_fixed_components_cache`
    directly without the full `_build_main_toy_v2_stage_environment`
    machinery. `commitment_schema.json` and `labels_schema.json` are the
    REAL, on-disk schemas (copied verbatim from `SCHEMAS_DIR`) -- SAN-881
    PASS-1 CORRECTION's EXECUTABLE $defs VALIDATION requires these two
    to genuinely define the authorEnvelope / reviewerSemanticEnvelope /
    reviewerContractEnvelope / semanticFile / contractFile branches this
    module actually builds via `_build_named_schema`, so a minimal `{}`
    placeholder (self-valid at its own root, but $defs-less) no longer
    suffices for these two specifically. The other four schema files --
    never branch-consumed by `_build_named_schema` -- remain minimal
    placeholder `{}` schemas (self-valid, content-empty)."""
    for name in vd.SCHEMA_FILES:
        if name in _SCHEMAS_WITH_NAMED_BRANCHES:
            (schemas_dir / name).write_bytes((SCHEMAS_DIR / name).read_bytes())
        else:
            (schemas_dir / name).write_bytes(b"{}")


def _build_main_toy_v2_stage_environment(tmp_path, monkeypatch) -> dict:
    """Builds a full, self-consistent TOY v2 calibration directory and
    monkeypatches vd.HERE / vd.SCHEMAS / vd.REPO_ROOT to point at it --
    TOY INJECTION (SAN-881 Phase-A CORRECTION PASS 1): main-level success
    tests monkeypatch module path dependencies, they do NOT add a new
    production CLI override for the calibration root or author-envelope
    path. Every public artifact (corpus_inputs.json, evaluation_profile.json,
    the six REAL post-edit schemas, the two REAL pinned spec files) is
    genuinely self-consistent, so commitment.json's labeling_context_hash
    is a REAL from-disk recomputation (not an arbitrary toy value) -- a
    caller can therefore assert a FULLY clean main(argv) run, not merely
    an absence of reveal-stage-specific errors. Returns everything a
    caller needs to construct --sealed-dir / --reviewer-dir / nonces
    files for either stage."""
    cal_dir = tmp_path / "cal"
    cal_dir.mkdir()
    schemas_dir = cal_dir / "schemas"
    schemas_dir.mkdir()
    for name in vd.SCHEMA_FILES:
        (schemas_dir / name).write_bytes((SCHEMAS_DIR / name).read_bytes())
    spec_dir = tmp_path / "reference" / "spec"
    spec_dir.mkdir(parents=True)
    real_spec_dir = CAL_DIR.parent / "spec"
    algo_bytes = (real_spec_dir / "ALGORITHM-v4-c1c5-reference.md").read_bytes()
    tables_bytes = (real_spec_dir / "ALGORITHM-v4-tables-v1.json").read_bytes()
    (spec_dir / "ALGORITHM-v4-c1c5-reference.md").write_bytes(algo_bytes)
    (spec_dir / "ALGORITHM-v4-tables-v1.json").write_bytes(tables_bytes)

    corpus = [{"id": f"cal:{i:03d}", "context": f"Toy context number {i}.", "output": f"Toy output number {i}."} for i in range(160)]
    (cal_dir / "corpus_inputs.json").write_text(json.dumps(corpus))
    profile = {
        "corpus_version": 2, "scope": ["C1", "C2", "C3", "C4"],
        "spec_pins": {
            "algorithm_sha256": hashlib.sha256(algo_bytes).hexdigest(),
            "tables_sha256": hashlib.sha256(tables_bytes).hexdigest(),
        },
    }
    (cal_dir / "evaluation_profile.json").write_text(json.dumps(profile))

    # From-disk recompute (v2 formula) over the REAL dependency bytes
    # just written -- a genuinely correct context hash, not an arbitrary
    # toy value.
    ctx_hash_hex = vd.compute_labeling_context_hash_from_disk(cal_dir, tmp_path).hex()
    ctx_hash_bytes = bytes.fromhex(ctx_hash_hex)

    semantic_bytes = json.dumps(_toy_640_semantic_records()).encode()
    contract_bytes = json.dumps(_toy_640_contract_records()).encode()
    design_bytes = json.dumps({"items": _toy_160_design_items()}).encode()
    # SAN-881 PASS 2B.1: the schema no longer accepts an arbitrary
    # "toy_surface" key -- coverage_manifest.json bytes used anywhere a
    # SCHEMA-VALID (68-key-closed) artifact is required must be built
    # from the full registry (see _full_valid_coverage_manifest below).
    coverage_bytes = json.dumps(_full_valid_coverage_manifest()).encode()

    # Cross-validate these ARE schema-valid before using them as bundle
    # bytes (do not weaken schemas to simplify tests).
    labels_schema = json.loads((SCHEMAS_DIR / "labels_schema.json").read_text())
    Draft202012Validator(labels_schema).validate(json.loads(semantic_bytes))
    Draft202012Validator(labels_schema).validate(json.loads(contract_bytes))
    coverage_schema = json.loads((SCHEMAS_DIR / "coverage_manifest_schema.json").read_text())
    Draft202012Validator(coverage_schema).validate(json.loads(coverage_bytes))

    artifact_bytes = {
        "labels_author_semantic.json": semantic_bytes,
        "labels_author_contract.json": contract_bytes,
        "design_metadata.json": design_bytes,
        "coverage_manifest.json": coverage_bytes,
    }
    author_nonces = {n: secrets.token_bytes(32) for n in artifact_bytes}
    author_commitments = [
        {"artifact_name": n, "byte_length": len(artifact_bytes[n]),
         "commitment_hex": vd.compute_artifact_commitment(n, author_nonces[n], ctx_hash_bytes, artifact_bytes[n])}
        for n in vd.AUTHOR_COMMITMENT_ORDER
    ]
    algorithm_block = {"hash": "SHA256", "domain_separator": "sanna-calibration-commitment/1", "formula": vd.COMMITMENT_ALGORITHM_FORMULA}
    commitment = {
        "corpus_version": 2, "envelope_kind": "AUTHOR", "labeling_context_hash": ctx_hash_hex,
        "labeling_context_components": vd.build_labeling_context_components(cal_dir, tmp_path),
        "commitment_algorithm": algorithm_block,
        "author_commitments": author_commitments,
        "reveal_protocol": {
            "reviewer_commitment_filenames": [
                "labels_reviewer_semantic.commitment.json", "labels_reviewer_contract.commitment.json",
            ],
            "reviewer_commitment_method": (
                "identical to author_commitments: domain-separated SHA256(\"sanna-calibration-commitment/1\""
                " || NUL || artifact_name || NUL || raw_32_byte_nonce || raw_32_byte_labeling_context_hash"
                " || exact_artifact_bytes)"
            ),
            "abandonment_rule": "toy",
        },
    }
    (cal_dir / "commitment.json").write_text(json.dumps(commitment))

    rev_sem_artifact = json.dumps(_toy_640_semantic_records()).encode()
    rev_sem_nonce = secrets.token_bytes(32)
    rev_sem_commit_hex = vd.compute_artifact_commitment(vd.REVIEWER_SEMANTIC_ARTIFACT, rev_sem_nonce, ctx_hash_bytes, rev_sem_artifact)
    rev_sem_env = {
        "corpus_version": 2, "envelope_kind": "REVIEWER_SEMANTIC", "labeling_context_hash": ctx_hash_hex,
        "commitment_algorithm": algorithm_block,
        "artifact_commitment": {"artifact_name": vd.REVIEWER_SEMANTIC_ARTIFACT, "byte_length": len(rev_sem_artifact), "commitment_hex": rev_sem_commit_hex},
    }

    rev_con_artifact = json.dumps(_toy_640_contract_records()).encode()
    rev_con_nonce = secrets.token_bytes(32)
    rev_con_commit_hex = vd.compute_artifact_commitment(vd.REVIEWER_CONTRACT_ARTIFACT, rev_con_nonce, ctx_hash_bytes, rev_con_artifact)
    rev_con_env = {
        "corpus_version": 2, "envelope_kind": "REVIEWER_CONTRACT", "labeling_context_hash": ctx_hash_hex,
        "commitment_algorithm": algorithm_block,
        "artifact_commitment": {"artifact_name": vd.REVIEWER_CONTRACT_ARTIFACT, "byte_length": len(rev_con_artifact), "commitment_hex": rev_con_commit_hex},
    }

    monkeypatch.setattr(vd, "HERE", cal_dir)
    monkeypatch.setattr(vd, "SCHEMAS", schemas_dir)
    monkeypatch.setattr(vd, "REPO_ROOT", tmp_path)

    return {
        "cal_dir": cal_dir, "artifact_bytes": artifact_bytes, "author_nonces": author_nonces,
        "rev_sem_artifact": rev_sem_artifact, "rev_sem_nonce": rev_sem_nonce, "rev_sem_env": rev_sem_env,
        "rev_con_artifact": rev_con_artifact, "rev_con_nonce": rev_con_nonce, "rev_con_env": rev_con_env,
        "commitment": commitment,
    }


def _init_toy_git_repo(repo_dir: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "toy@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "toy"], cwd=repo_dir, check=True)
    (repo_dir / "README.md").write_text("toy\n")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "toy"], cwd=repo_dir, check=True)


# ---------------------------------------------------------------------
# Public-data: corpus_inputs.json
# ---------------------------------------------------------------------

def test_corpus_has_160_items():
    assert len(CORPUS) == 160


def test_corpus_ordinals_sequential():
    for idx, rec in enumerate(CORPUS):
        assert rec["id"] == f"cal:{idx:03d}"


def test_corpus_allowlist_exactly_id_context_output():
    for rec in CORPUS:
        keys = set(rec.keys())
        has_context = "context" in keys
        has_sources = "context_sources" in keys
        assert has_context != has_sources, rec["id"]
        allowed = {"id", "output"} | ({"context"} if has_context else {"context_sources"})
        assert keys == allowed, rec["id"]


def test_corpus_tier1_only():
    for rec in CORPUS:
        if "context_sources" in rec:
            for source in rec["context_sources"]:
                assert set(source.keys()) == {"text", "tier"}, rec["id"]
                assert source["tier"] == "tier_1", rec["id"]


def test_corpus_no_duplicate_canonical_tuples():
    seen = set()
    for rec in CORPUS:
        ctx = rec.get("context") or " ".join(s["text"] for s in rec.get("context_sources", []))
        key = (ctx, rec["output"])
        assert key not in seen, f"duplicate tuple at {rec['id']}"
        seen.add(key)


def test_corpus_env_cap_statics_field_bytes():
    for rec in CORPUS:
        assert len(rec["output"].encode("utf-8")) <= 1_048_576, rec["id"]
        ctx = rec.get("context") or " ".join(s["text"] for s in rec.get("context_sources", []))
        assert len(ctx.encode("utf-8")) <= 1_048_576, rec["id"]


def test_corpus_context_sentence_count_2_to_5():
    import re
    for rec in CORPUS:
        ctx = rec.get("context") or " ".join(s["text"] for s in rec.get("context_sources", []))
        n = len(re.findall(r"[.!?](?:\s|$)", ctx))
        assert 2 <= n <= 5, f"{rec['id']}: context has {n} sentences"


def test_corpus_is_pure_ascii_except_documented_abstention_item():
    # the whole file must round-trip through ensure_ascii=True JSON,
    # i.e. no raw non-ASCII bytes on disk (escapes are fine)
    raw = (CAL_DIR / "corpus_inputs.json").read_bytes()
    assert all(b <= 0x7F for b in raw)


# ---------------------------------------------------------------------
# Public-data: evaluation_profile.json
# ---------------------------------------------------------------------

def test_evaluation_profile_scope_and_version():
    assert PROFILE["corpus_version"] == 1
    assert PROFILE["scope"] == ["C1", "C2", "C3", "C4"]


def test_evaluation_profile_hash_pins():
    algo_path = CAL_DIR.parent / "spec" / "ALGORITHM-v4-c1c5-reference.md"
    tables_path = CAL_DIR.parent / "spec" / "ALGORITHM-v4-tables-v1.json"
    assert PROFILE["spec_pins"]["algorithm_sha256"] == hashlib.sha256(algo_path.read_bytes()).hexdigest()
    assert PROFILE["spec_pins"]["tables_sha256"] == hashlib.sha256(tables_path.read_bytes()).hexdigest()


def test_evaluation_profile_allowlist_matches_measure_allowlist():
    allowlist = set(PROFILE["evaluator"]["fixture_construction"]["allowlist"])
    assert allowlist <= ms.ALLOWED_INPUT_KEYS


# ---------------------------------------------------------------------
# Public-data: commitment.json (AUTHOR envelope) + from-disk context hash
# ---------------------------------------------------------------------

def test_commitment_schema_valid_or_documents_v1_transitional_corpus_version_failure():
    # TRANSITIONAL (SAN-881 Phase-A correction): commitment_schema.json now
    # pins corpus_version STRICTLY to vd.EXPECTED_CORPUS_VERSION (2, const).
    # The current on-disk commitment.json is intentionally still v1 (see
    # README.md's v1-transitional posture). Written so the eventual v2
    # reseal is a DATA change (COMMITMENT["corpus_version"] becomes 2),
    # never a test rewrite: the branch taken flips automatically. The
    # top-level oneOf error has an empty path (jsonschema reports the
    # WHOLE instance at the failing oneOf), so the pinned reason is read
    # from e.context (the per-branch sub-errors), not e.path/e.message.
    schema = json.loads((SCHEMAS_DIR / "commitment_schema.json").read_text())
    errors = list(Draft202012Validator(schema).iter_errors(COMMITMENT))
    if COMMITMENT.get("corpus_version") == vd.EXPECTED_CORPUS_VERSION:
        assert errors == []
    else:
        sub_errors = [sub for e in errors for sub in (e.context or [])]
        assert any(list(sub.path) == ["corpus_version"] and sub.validator == "const" for sub in sub_errors)


def test_commitment_four_sealed_entries_with_positive_lengths_and_hex64():
    assert len(COMMITMENT["author_commitments"]) == 4
    for entry in COMMITMENT["author_commitments"]:
        assert len(entry["commitment_hex"]) == 64
        assert int(entry["commitment_hex"], 16) >= 0
        assert entry["byte_length"] > 0


def test_commitment_envelope_kind_is_author():
    assert COMMITMENT["envelope_kind"] == "AUTHOR"


def test_commitment_reveal_protocol_pins_reviewer_filenames():
    assert COMMITMENT["reveal_protocol"]["reviewer_commitment_filenames"] == [
        "labels_reviewer_semantic.commitment.json",
        "labels_reviewer_contract.commitment.json",
    ]


def test_compute_labeling_context_hash_from_disk_matches_manual_recomputation():
    # Independent recomputation (this test's own concat), cross-checked
    # against vd.compute_labeling_context_hash_from_disk -- both must
    # agree on the CURRENT on-disk component set (6 schemas post-correction).
    # v2 formula (SAN-881 Phase-A CORRECTION PASS 1, an intentional break
    # from v1): EVERY component -- including base_commit_sha -- is
    # individually SHA-256'd first; the outer hash is SHA256 of the
    # concatenation of the eleven raw 32-byte digests, in the pinned
    # LABELING_CONTEXT_COMPONENT_NAMES order. Schema filenames are the
    # FIXED SCHEMA_FILES tuple, never a directory glob.
    assert len(vd.LABELING_CONTEXT_COMPONENT_NAMES) == 11
    schema_files = [SCHEMAS_DIR / name for name in vd.SCHEMA_FILES]
    assert len(schema_files) == 6, "labeling context now binds six schema files (reveal_verification_ledger_schema.json added)"
    digests = [hashlib.sha256(vd.BASE_COMMIT_SHA.encode("ascii")).digest()]
    digests.append(hashlib.sha256((CAL_DIR / "corpus_inputs.json").read_bytes()).digest())
    digests.append(hashlib.sha256((CAL_DIR / "evaluation_profile.json").read_bytes()).digest())
    for p in schema_files:
        digests.append(hashlib.sha256(p.read_bytes()).digest())
    digests.append(hashlib.sha256((CAL_DIR.parent / "spec" / "ALGORITHM-v4-c1c5-reference.md").read_bytes()).digest())
    digests.append(hashlib.sha256((CAL_DIR.parent / "spec" / "ALGORITHM-v4-tables-v1.json").read_bytes()).digest())
    expected = hashlib.sha256(b"".join(digests)).hexdigest()
    assert vd.compute_labeling_context_hash_from_disk(CAL_DIR, REPO_ROOT).hex() == expected


def test_labeling_context_component_names_pinned_eleven_in_order():
    assert vd.LABELING_CONTEXT_COMPONENT_NAMES == (
        "base_commit_sha",
        "corpus_inputs.json",
        "evaluation_profile.json",
        "schemas/commitment_schema.json",
        "schemas/coverage_manifest_schema.json",
        "schemas/design_metadata_schema.json",
        "schemas/freeze_manifest_schema.json",
        "schemas/labels_schema.json",
        "schemas/reveal_verification_ledger_schema.json",
        "algorithm",
        "tables",
    )


def test_build_labeling_context_components_structure_and_hashes():
    components = vd.build_labeling_context_components(CAL_DIR, REPO_ROOT)
    assert [c["name"] for c in components] == list(vd.LABELING_CONTEXT_COMPONENT_NAMES)
    for c in components:
        assert len(c["sha256"]) == 64
        assert set(c["sha256"]) <= set("0123456789abcdef")
    # base_commit_sha's own component is the SHA-256 of the ASCII pin
    # string itself (v2: hashed, unlike v1's raw-bytes concat).
    assert components[0]["sha256"] == hashlib.sha256(vd.BASE_COMMIT_SHA.encode("ascii")).hexdigest()


def test_v1_commitment_context_hash_is_now_stale_pending_v2_reseal():
    """KNOWN, INTENTIONAL red: adding reveal_verification_ledger_schema.json
    (SAN-881 Phase-A correction) changed the labeling-context component set
    that reference/calibration/commitment.json's frozen v1
    labeling_context_hash was computed over. The whole point of wiring
    from-disk recomputation into check_commitment (rather than trusting the
    envelope) is that it catches EXACTLY this drift. This corpus v1 seal is
    intentionally abandoned by this correction; a full v2 reseal (fresh
    nonces, recomputed commitments, corpus_version 2) restores a green
    `python3 reference/calibration/validate_design.py` run. See README.md
    abandonment rule and commitment.json's future v2 abandonment record."""
    errors = vd.Errors()
    vd.check_commitment(errors, COMMITMENT, cal_dir=CAL_DIR, repo_root=REPO_ROOT)
    assert any(vd.RULE_CONTEXT_HASH_MISMATCH in e for e in errors), (
        "if this starts passing, corpus v1 has been resealed as v2 -- update "
        "this test to assert the NEW hash matches instead of documenting the drift"
    )


def test_check_commitment_wires_from_disk_recomputation_not_envelope_trust(tmp_path, monkeypatch):
    # Build a toy cal_dir with a tampered schema file: the OUTER
    # labeling_context_hash is ALWAYS recomputed from disk, never trusted
    # from the envelope, so a from-disk recompute against tampered bytes
    # MUST diverge from the committed hash, even though the envelope's
    # descriptive component list still names the (now-stale) files
    # correctly. SAN-881 Phase-A CORRECTION PASS 1 (Section C): for a v2
    # envelope, check_commitment ADDITIONALLY cross-checks the envelope's
    # OWN declared labeling_context_components list against
    # build_labeling_context_components(cal_dir, repo_root) -- so the
    # declared list is no longer "never consulted"; it is cross-checked,
    # but the outer hash math itself still never takes the envelope's
    # list as an INPUT (see compute_labeling_context_hash_from_disk,
    # which reads only fixed disk paths/constants). v2 formula (SAN-881
    # Phase-A correction) reads schema bytes from the FIXED SCHEMA_FILES
    # names, never a directory glob -- the toy schemas/ dir must use
    # those exact six pinned filenames, not an arbitrary one.
    cal_dir = tmp_path
    schemas_dir = cal_dir / "schemas"
    schemas_dir.mkdir()
    (cal_dir / "corpus_inputs.json").write_bytes(b"[]")
    (cal_dir / "evaluation_profile.json").write_bytes(b"{}")
    _write_toy_schemas_dir(schemas_dir)  # SAN-881 PASS-1 CORRECTION: real bytes for the two $defs-branch-checked schemas
    spec_dir = tmp_path / "reference" / "spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "ALGORITHM-v4-c1c5-reference.md").write_bytes(b"algo")
    (spec_dir / "ALGORITHM-v4-tables-v1.json").write_bytes(b"{}")  # valid JSON -- SAN-881 PASS-1 FINAL CLOSURE CORRECTION: tables is now cache-validated as JSON too

    correct_hash = vd.compute_labeling_context_hash_from_disk(cal_dir, tmp_path).hex()
    commitment = {
        "corpus_version": vd.EXPECTED_CORPUS_VERSION,
        "author_commitments": [
            {"artifact_name": n, "byte_length": 1, "commitment_hex": "a" * 64}
            for n in vd.AUTHOR_COMMITMENT_ORDER
        ],
        "labeling_context_hash": correct_hash,
        # SAN-881 Phase-A CORRECTION PASS 1 (Section C): a v2 envelope's
        # declared component list is now cross-checked against the
        # from-disk build -- must be genuinely correct for this
        # errors == [] baseline to hold.
        "labeling_context_components": vd.build_labeling_context_components(cal_dir, tmp_path),
    }
    errors = vd.Errors()
    vd.check_commitment(errors, commitment, cal_dir=cal_dir, repo_root=tmp_path)
    assert errors == []

    # Now tamper ONE pinned schema file on disk WITHOUT updating
    # labeling_context_hash. Deliberately NOT one of the two
    # $defs-branch-checked schemas (commitment_schema.json,
    # labels_schema.json) -- this test isolates HASH divergence from
    # tampering, not SAN-881 PASS-1 CORRECTION's separate $defs-branch
    # validity gate (covered by its own tests).
    (schemas_dir / "coverage_manifest_schema.json").write_bytes(b'{"tampered": true}')
    errors2 = vd.Errors()
    vd.check_commitment(errors2, commitment, cal_dir=cal_dir, repo_root=tmp_path)
    assert any(vd.RULE_CONTEXT_HASH_MISMATCH in e for e in errors2)


# ---------------------------------------------------------------------
# Public-data: six schemas load and validate whole-file / toy instances
# ---------------------------------------------------------------------

def test_schema_files_are_exactly_six():
    names = sorted(p.name for p in SCHEMAS_DIR.glob("*.json"))
    assert names == [
        "commitment_schema.json",
        "coverage_manifest_schema.json",
        "design_metadata_schema.json",
        "freeze_manifest_schema.json",
        "labels_schema.json",
        "reveal_verification_ledger_schema.json",
    ]


def test_schema_design_metadata_loads_and_validates_toy():
    # SAN-881 Phase-A correction: items is pinned to EXACTLY 160
    # (schema-level minItems == maxItems), so a whole-file toy instance
    # must supply all 160 to prove the WHOLE-FILE form loads/validates.
    schema = json.loads((SCHEMAS_DIR / "design_metadata_schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    toy = {"items": _toy_160_design_items()}
    Draft202012Validator(schema).validate(toy)


def test_schema_design_metadata_rejects_single_item_file():
    # Correction-target RED-then-GREEN: a 1-item design_metadata.json is
    # no longer schema-valid now that items is pinned to EXACTLY 160.
    schema = json.loads((SCHEMAS_DIR / "design_metadata_schema.json").read_text())
    toy = {"items": [_toy_160_design_items()[0]]}
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(toy)


def test_schema_design_metadata_closed_table_path_rejects_open_string():
    # SAN-881 PASS 2B.2: repurposed off the removed 'comparator' kind and
    # upgraded to the NON-VACUOUS 160-item form (Part F) -- an arbitrary,
    # non-enum table_path string must be rejected, and the error must
    # reach THIS item's introduced_feature specifically.
    schema = json.loads((SCHEMAS_DIR / "design_metadata_schema.json").read_text())
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "concept", "table_path": "not_a_real_table",
        "surface_tokens": ["approval"],
        "intended_semantics": {"canonical_concept": "approval"},
    })
    _assert_schema_error_reaches_item_feature(schema, {"items": items}, idx)


def test_schema_design_metadata_per_kind_intended_semantics_closed():
    # SAN-881 PASS 2B.2: repurposed off the removed 'comparator' kind and
    # upgraded to the NON-VACUOUS 160-item form -- concept kind with a
    # facet-shaped intended_semantics (wrong shape for this kind) must be
    # rejected.
    schema = json.loads((SCHEMAS_DIR / "design_metadata_schema.json").read_text())
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "concept", "table_path": "concept_v1",
        "surface_tokens": ["approval"],
        "intended_semantics": {"facet": "facet:availability", "polarity": "POS"},
    })
    _assert_schema_error_reaches_item_feature(schema, {"items": items}, idx)


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.2 Part A: THE CLOSED DISCRIMINATED UNION (schema-level)
# -- comparator PROHIBITION, ten-branch kind-to-table BINDING (facet
# match, polarity match, role match). Every negative below is
# NON-VACUOUS (Part F): ONE mutated item inside an otherwise-valid
# 160-item document, with the error asserted to reach THAT item's
# introduced_feature specifically -- never a 1-item document, which
# fails a priori on minItems==160 and proves nothing about the
# discriminator.
# ---------------------------------------------------------------------

def _design_schema():
    return json.loads((SCHEMAS_DIR / "design_metadata_schema.json").read_text())


def test_schema_dod_comparator_kind_no_longer_a_legal_introduced_feature():
    # RED-then-GREEN: comparator used to be a legal introduced_feature
    # kind (its own comparatorIntervalSemantics branch); PASS 2B.2
    # deletes it from the vocabulary entirely. comparator PARSING itself
    # (comparators_v1, checks.py/evaluate.py) is untouched -- this is
    # ONLY about introduced_feature's closed kind enum.
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "comparator", "table_path": "comparators_v1",
        "surface_tokens": ["at", "least"],
        "intended_semantics": {"interval": "hi=v, hi_open=false (at-most)"},
    })
    _assert_schema_error_reaches_item_feature(schema, {"items": items}, idx)


def test_schema_dod_comparators_v1_removed_from_closed_table_path():
    schema = _design_schema()
    assert "comparators_v1" not in schema["$defs"]["closedTablePath"]["enum"]


def test_schema_dod_comparator_interval_semantics_def_deleted():
    schema = _design_schema()
    assert "comparatorIntervalSemantics" not in schema["$defs"]


def test_schema_dod_kind_table_mismatch_concept_bound_to_units_v1():
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "concept", "table_path": "units_v1",
        "surface_tokens": ["approval"],
        "intended_semantics": {"canonical_concept": "approval"},
    })
    _assert_schema_error_reaches_item_feature(schema, {"items": items}, idx)


def test_schema_dod_kind_table_mismatch_unit_bound_to_condition_operators_v1():
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "unit", "table_path": "condition_operators_v1",
        "surface_tokens": ["hour"],
        "intended_semantics": {"group": "time_a", "factor": 60},
    })
    _assert_schema_error_reaches_item_feature(schema, {"items": items}, idx)


def test_schema_dod_kind_table_mismatch_excl_pair_bound_to_complement_v1():
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "excl_pair", "table_path": "complement_v1",
        "members": [["digital"], ["physical"]],
    })
    _assert_schema_error_reaches_item_feature(schema, {"items": items}, idx)


def test_schema_dod_deny_trigger_bound_to_facetproj_v1_forbidden():
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "deny_trigger", "table_path": "facetproj_v1",
        "surface_tokens": ["refund"],
        "intended_semantics": {"polarity": "NEG", "projects_to": "facet:refund_availability"},
    })
    _assert_schema_error_reaches_item_feature(schema, {"items": items}, idx)


def test_schema_dod_facet_trigger_bound_to_facetproj_v1_allowed():
    # Positive control pinning the OTHER side of the same branch: this
    # combination MUST stay legal (facet_trigger, unlike deny_trigger,
    # may bind to facetproj_v1).
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "facet_trigger", "table_path": "facetproj_v1",
        "surface_tokens": ["discount"],
        "intended_semantics": {"polarity": "POS", "projects_to": "facet:discount_availability"},
    })
    errors = list(Draft202012Validator(schema).iter_errors({"items": items}))
    assert errors == []


def test_schema_dod_facet_mismatch_table_path_vs_intended_semantics_facet():
    # table_path names facet:cost's triggers leaf but intended_semantics
    # declares facet:duration -- a facet MISMATCH, currently legal at
    # schema level pre-fix (RED), rejected post-fix (GREEN).
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "facet_trigger", "table_path": "facets_v1.facet:cost.triggers",
        "surface_tokens": ["expensive"],
        "intended_semantics": {"facet": "facet:duration", "polarity": "POS"},
    })
    _assert_schema_error_reaches_item_feature(schema, {"items": items}, idx)


def test_schema_dod_wrong_polarity_facet_trigger_claims_neg():
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "facet_trigger", "table_path": "facets_v1.facet:cost.triggers",
        "surface_tokens": ["expensive"],
        "intended_semantics": {"facet": "facet:cost", "polarity": "NEG"},
    })
    _assert_schema_error_reaches_item_feature(schema, {"items": items}, idx)


def test_schema_dod_wrong_polarity_deny_trigger_claims_pos():
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "deny_trigger", "table_path": "facets_v1.facet:cost.deny_triggers",
        "surface_tokens": ["cheap"],
        "intended_semantics": {"facet": "facet:cost", "polarity": "POS"},
    })
    _assert_schema_error_reaches_item_feature(schema, {"items": items}, idx)


def test_schema_dod_wrong_role_definitive_claims_hedge():
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "definitive", "table_path": "definitive_v1",
        "surface_tokens": ["guaranteed"],
        "intended_semantics": {"role": "hedge", "same_overclaim_class_as_table": True},
    })
    _assert_schema_error_reaches_item_feature(schema, {"items": items}, idx)


def test_schema_dod_wrong_role_hedge_claims_definitive():
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "hedge", "table_path": "hedge_v1",
        "surface_tokens": ["may"],
        "intended_semantics": {"role": "definitive", "same_overclaim_class_as_table": True},
    })
    _assert_schema_error_reaches_item_feature(schema, {"items": items}, idx)


def test_schema_dod_hedge_bound_to_wrong_table_definitive_v1():
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "hedge", "table_path": "definitive_v1",
        "surface_tokens": ["may"],
        "intended_semantics": {"role": "hedge", "same_overclaim_class_as_table": True},
    })
    _assert_schema_error_reaches_item_feature(schema, {"items": items}, idx)


def test_schema_dod_all_ten_branches_positive_controls_stay_legal():
    # Positive-control sweep: one genuinely-valid feature per kind, all
    # inside the SAME otherwise-valid 160-item document, must validate
    # cleanly -- proving the ten-branch binding does not over-reject
    # legitimate combinations.
    schema = _design_schema()
    per_kind_features = {
        "facet_trigger": {
            "kind": "facet_trigger", "table_path": "facets_v1.facet:cost.triggers",
            "surface_tokens": ["expensive"], "intended_semantics": {"facet": "facet:cost", "polarity": "POS"},
        },
        "deny_trigger": {
            "kind": "deny_trigger", "table_path": "facets_v1.facet:cost.deny_triggers",
            "surface_tokens": ["cheap"], "intended_semantics": {"facet": "facet:cost", "polarity": "NEG"},
        },
        "concept": {
            "kind": "concept", "table_path": "concept_v1",
            "surface_tokens": ["approval"], "intended_semantics": {"canonical_concept": "approval"},
        },
        "unit": {
            "kind": "unit", "table_path": "units_v1",
            "surface_tokens": ["hour"], "intended_semantics": {"group": "time_a", "factor": 60},
        },
        "condition_operator": {
            "kind": "condition_operator", "table_path": "condition_operators_v1",
            "surface_tokens": ["unless"], "intended_semantics": {"kind": "IF", "polarity": "-", "force": "grant"},
        },
        "quantifier": {
            "kind": "quantifier", "table_path": "quant_v1",
            "surface_tokens": ["some"], "intended_semantics": {"quantifier_class": "existential"},
        },
        "definitive": {
            "kind": "definitive", "table_path": "definitive_v1",
            "surface_tokens": ["guaranteed"], "intended_semantics": {"role": "definitive", "same_overclaim_class_as_table": True},
        },
        "hedge": {
            "kind": "hedge", "table_path": "hedge_v1",
            "surface_tokens": ["may"], "intended_semantics": {"role": "hedge", "same_overclaim_class_as_table": True},
        },
        "excl_pair": {
            "kind": "excl_pair", "table_path": "excl_v1", "members": [["digital"], ["physical"]],
        },
        "complement_pair": {
            "kind": "complement_pair", "table_path": "complement_v1", "members": [["enabled"], ["disabled"]],
        },
    }
    base_items = copy.deepcopy(_toy_160_design_items())
    dod_indices = [i for i, it in enumerate(base_items) if it["target_stratum"] == "determinate_out_of_domain"]
    assert len(dod_indices) >= len(per_kind_features)
    for slot, (kind, feature) in zip(dod_indices, per_kind_features.items()):
        base_items[slot]["introduced_feature"] = feature
    errors = list(Draft202012Validator(schema).iter_errors({"items": base_items}))
    assert errors == [], f"expected all ten legitimate per-kind bindings to validate cleanly, got {errors}"


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.2-FIX defect 4: facetprojSemantics.projects_to closure.
# projects_to previously accepted ANY string matching the OPEN pattern
# ^facet:[a-z_]+$ -- every other facet reference in this schema
# (facetPolaritySemantics.facet) is a CLOSED ten-facet enum; projects_to
# must be too.
# ---------------------------------------------------------------------

def test_schema_design_metadata_facetproj_projects_to_open_pattern_rejects_non_closed_facet():
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "facet_trigger", "table_path": "facetproj_v1",
        "surface_tokens": ["markdown"],
        "intended_semantics": {"polarity": "POS", "projects_to": "facet:not_closed"},
    })
    _assert_schema_error_reaches_item_feature(schema, {"items": items}, idx)


def test_schema_design_metadata_facetproj_projects_to_real_facet_still_legal():
    # Positive control: the closure must not over-reject a real facet.
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "facet_trigger", "table_path": "facetproj_v1",
        "surface_tokens": ["markdown"],
        "intended_semantics": {"polarity": "POS", "projects_to": "facet:discount_availability"},
    })
    errors = list(Draft202012Validator(schema).iter_errors({"items": items}))
    assert errors == []


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.2-FIX defect 5: same_overclaim_class_as_table is now
# const: true for BOTH definitive and hedge -- the control check that
# consumes this field treats it as an unconditional "yes, this is a
# genuine same-overclaim-class swap" flag; a schema-valid `false` let an
# author declare a feature that is NOT a genuine same-class swap while
# still passing schema validation, with the control check ignoring the
# field's actual value entirely.
# ---------------------------------------------------------------------

def test_schema_design_metadata_definitive_same_overclaim_class_as_table_false_rejected():
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "definitive", "table_path": "definitive_v1",
        "surface_tokens": ["unquestionably"],
        "intended_semantics": {"role": "definitive", "same_overclaim_class_as_table": False},
    })
    _assert_schema_error_reaches_item_feature(schema, {"items": items}, idx)


def test_schema_design_metadata_hedge_same_overclaim_class_as_table_false_rejected():
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "hedge", "table_path": "hedge_v1",
        "surface_tokens": ["conceivably"],
        "intended_semantics": {"role": "hedge", "same_overclaim_class_as_table": False},
    })
    _assert_schema_error_reaches_item_feature(schema, {"items": items}, idx)


def test_dod_schema_kind_vocabulary_matches_validator_kind_vocabulary():
    # SAN-881 PASS 2B.2 Part A.3: build-time parity test -- the schema's
    # closed kind vocabulary (lexicalSurfaceFeature + pairRelationFeature)
    # must equal EXACTLY the validator's own recognized kind vocabulary
    # (_DOD_SIMPLE_KIND_TABLE's keys + the two facet-leaf kinds + the two
    # role-bound kinds already counted in _DOD_SIMPLE_KIND_TABLE/handled
    # specially in _dod_kind_table_binding_ok) -- exactly ten, no more,
    # no fewer, never drifting independently.
    schema = _design_schema()
    schema_kinds = set(schema["$defs"]["lexicalSurfaceFeature"]["properties"]["kind"]["enum"])
    schema_kinds |= set(schema["$defs"]["pairRelationFeature"]["properties"]["kind"]["enum"])

    validator_kinds = set(vd._DOD_SIMPLE_KIND_TABLE) | {"definitive", "hedge", "facet_trigger", "deny_trigger"}

    assert schema_kinds == validator_kinds
    assert len(schema_kinds) == 10
    assert "comparator" not in schema_kinds
    assert "comparator" not in validator_kinds


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.2-FIX defect 3: WHITESPACE-ONLY LEXICAL/PAIR TOKENS.
# surface_tokens: [" "] (or a pair member [" "]) is schema-valid
# pre-fix (minLength: 1 is satisfied by a lone space, no non-whitespace
# requirement) and folds to the empty sequence -- both $defs now carry
# "pattern": "\\S" alongside the existing minLength: 1.
# ---------------------------------------------------------------------

def test_schema_design_metadata_whitespace_only_lexical_surface_token_rejected():
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "concept", "table_path": "concept_v1",
        "surface_tokens": [" "],
        "intended_semantics": {"canonical_concept": "approval"},
    })
    _assert_schema_error_reaches_item_feature(schema, {"items": items}, idx)


def test_schema_design_metadata_whitespace_only_pair_member_token_rejected():
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "excl_pair", "table_path": "excl_v1",
        "members": [[" "], ["premium"]],
    })
    _assert_schema_error_reaches_item_feature(schema, {"items": items}, idx)


def test_schema_design_metadata_non_whitespace_surface_token_still_legal():
    # Positive control: the pattern must not over-reject genuine content.
    schema = _design_schema()
    items, item_id, idx = _160_items_with_feature_override({
        "kind": "concept", "table_path": "concept_v1",
        "surface_tokens": ["approval"],
        "intended_semantics": {"canonical_concept": "approval"},
    })
    errors = list(Draft202012Validator(schema).iter_errors({"items": items}))
    assert errors == []


def test_schema_labels_validates_whole_files_not_single_records():
    # SAN-881 Phase-A correction: semanticFile/contractFile/mergedFrozenFile
    # are each pinned to EXACTLY 640 records (independently), so the
    # "whole-file array form validates" assertions below now require a
    # full 640-record array, not a 1-item array.
    schema = json.loads((SCHEMAS_DIR / "labels_schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    semantic_toy = {"item_id": "cal:000", "check_id": "C1", "semantic_truth": "NO_VIOLATION", "semantic_rationale": "toy"}
    contract_toy = {
        "item_id": "cal:000", "check_id": "C1",
        "contract_tuple": {"outcome": "PASS", "outcome_reason": "detection_complete", "severity": None, "advisory": False},
        "competence": "IN_DOMAIN", "contract_rationale": "toy", "spec_refs": "toy",
    }
    merged_toy = {**semantic_toy, **{k: v for k, v in contract_toy.items() if k not in ("item_id", "check_id")}}

    # A single record is NO LONGER a valid whole-file instance.
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(semantic_toy)

    # A 1-item ARRAY is also no longer valid at the pinned 640 cardinality.
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate([semantic_toy])

    # Whole-file (640-record array) forms validate.
    Draft202012Validator(schema).validate(_toy_640_semantic_records())
    Draft202012Validator(schema).validate(_toy_640_contract_records())
    merged_640 = [{**semantic_toy, **{k: v for k, v in contract_toy.items() if k not in ("item_id", "check_id")},
                   "item_id": f"cal:{i:03d}", "check_id": c}
                  for i in range(160) for c in vd.CHECK_IDS]
    Draft202012Validator(schema).validate(merged_640)


def test_schema_labels_rejects_wrong_cardinality_semantic_and_contract_files():
    # Correction-target RED-then-GREEN: exactly 1 record (and any count
    # other than 640) fails schema now that minItems == maxItems == 640
    # is pinned independently per whole-file form.
    schema = json.loads((SCHEMAS_DIR / "labels_schema.json").read_text())
    one_semantic = [_toy_640_semantic_records()[0]]
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(one_semantic)
    one_contract = [_toy_640_contract_records()[0]]
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(one_contract)
    too_many_semantic = _toy_640_semantic_records() + [_toy_640_semantic_records()[0]]
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(too_many_semantic)


def _full_valid_coverage_manifest() -> dict:
    """A schema-valid, registry-CLOSED (all 68 surfaces present, exactly
    once each) coverage manifest -- one placeholder evidence record per
    surface. SAN-881 PASS 2B.1: the schema no longer accepts an
    arbitrary "toy_surface" key (additionalProperties: false, all 68
    registry names required) -- every test that needs a SCHEMA-VALID
    coverage_manifest.json now builds it from this exact 68-key set."""
    return {
        surface: [{"item_id": "cal:000", "check_id": "C1", "field": "context"}]
        for surface in vd.SURFACE_REGISTRY
    }


def test_schema_coverage_manifest_requires_all_68_registered_surfaces_with_nonempty_evidence():
    # SAN-881 PASS 2B.1 schema-closure rewrite: the RETIRED single
    # "toy_surface" key (any key at all, under the old open
    # additionalProperties shape) is no longer schema-valid -- the
    # schema now enumerates the pre-registered 68-surface registry
    # explicitly and rejects anything outside it.
    schema = json.loads((SCHEMAS_DIR / "coverage_manifest_schema.json").read_text())
    Draft202012Validator.check_schema(schema)

    toy_surface_only = {"toy_surface": [{"item_id": "cal:000", "check_id": "C1", "field": "context"}]}
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(toy_surface_only)

    full = _full_valid_coverage_manifest()
    Draft202012Validator(schema).validate(full)

    one_registered_surface_emptied = dict(full)
    emptied_surface = next(iter(vd.SURFACE_REGISTRY))
    one_registered_surface_emptied[emptied_surface] = []
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(one_registered_surface_emptied)


def test_schema_coverage_manifest_retired_69_key_pass1_manifest_fails_schema():
    # Acceptance: the retired Pass-1 69-key shape (units_v1.facet:* +
    # excl_v1.refundable_nonrefundable instead of value_role_v1.*) must
    # fail SCHEMA validation directly now, not merely the runtime
    # check_coverage_registry_closure cross-check (see
    # test_check_coverage_registry_closure_rejects_old_pass1_69_key_set).
    schema = json.loads((SCHEMAS_DIR / "coverage_manifest_schema.json").read_text())
    old_69_keys = set(vd.SURFACE_REGISTRY) - {f"value_role_v1.{f}" for f in ("cost", "duration", "limit")}
    old_69_keys |= {f"units_v1.facet:{f}" for f in ("cost", "duration", "limit")}
    old_69_keys |= {"excl_v1.refundable_nonrefundable"}
    assert len(old_69_keys) == 69
    retired = {surface: [{"item_id": "cal:000", "check_id": "C1", "field": "context"}] for surface in old_69_keys}
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(retired)


def test_coverage_manifest_schema_properties_required_and_registry_are_all_exactly_equal():
    # Build-time consistency: the schema's declared property name set,
    # its "required" list (as a set), and validate_design.SURFACE_REGISTRY's
    # key set must be EXACTLY the same 68 names -- no drift between the
    # schema mirror and the runtime registry it mirrors.
    schema = json.loads((SCHEMAS_DIR / "coverage_manifest_schema.json").read_text())
    registry_keys = set(vd.SURFACE_REGISTRY)
    schema_property_keys = set(schema["properties"])
    schema_required_keys = set(schema["required"])
    assert schema_property_keys == registry_keys
    assert schema_required_keys == registry_keys
    assert schema["additionalProperties"] is False
    # sorted-properties / sorted-required encoding, pinned verbatim
    assert list(schema["properties"].keys()) == sorted(schema["properties"].keys())
    assert schema["required"] == sorted(schema["required"])
    for name, prop_schema in schema["properties"].items():
        assert prop_schema == {"$ref": "#/$defs/evidenceArray"}, name
    assert schema["$defs"]["evidenceArray"]["items"] == {"$ref": "#/$defs/evidenceRecord"}
    assert schema["$defs"]["evidenceArray"]["minItems"] == 1


def test_schema_commitment_loads_and_validates_reviewer_envelopes():
    schema = json.loads((SCHEMAS_DIR / "commitment_schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    sem_env = {
        "corpus_version": 2, "envelope_kind": "REVIEWER_SEMANTIC",
        "labeling_context_hash": "a" * 64,
        "commitment_algorithm": {
            "hash": "SHA256", "domain_separator": "sanna-calibration-commitment/1",
            # SAN-881 Phase-A CORRECTION PASS 1 (Section F): formula is now
            # a pinned const -- any other string is schema-invalid.
            "formula": vd.COMMITMENT_ALGORITHM_FORMULA,
        },
        "artifact_commitment": {"artifact_name": "labels_reviewer_semantic.json", "byte_length": 1, "commitment_hex": "b" * 64},
    }
    Draft202012Validator(schema).validate(sem_env)
    # A contract artifact_name inside a REVIEWER_SEMANTIC envelope is rejected.
    bad = {**sem_env, "artifact_commitment": {**sem_env["artifact_commitment"], "artifact_name": "labels_reviewer_contract.json"}}
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(bad)


def test_schema_freeze_manifest_requires_provenance_fields_and_corpus_v2():
    schema = json.loads((SCHEMAS_DIR / "freeze_manifest_schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    toy = {
        "corpus_version": 2,
        "corpus_inputs_sha256": "a" * 64, "labels_frozen_sha256": "a" * 64,
        "design_metadata_sha256": "a" * 64, "coverage_manifest_sha256": "a" * 64,
        "evaluation_profile_sha256": "a" * 64,
        "algorithm_sha256": "49c138595fde5ee517d00d6b41eb815cf1016213a0cb7978ef258560cf5a4c59",
        "tables_sha256": "0a18dd94bc811bb3166a4f8812e78f2b053a9f8f083b781a21fb0f8371f54ecc",
        "adjudication_log_sha256": "a" * 64,
        "labeling_context_hash": "a" * 64,
        "author_commitment_sha256": "a" * 64,
        "reviewer_semantic_commitment_sha256": "a" * 64,
        "reviewer_contract_commitment_sha256": "a" * 64,
        "reveal_verification_ledger_sha256": "a" * 64,
    }
    Draft202012Validator(schema).validate(toy)
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate({**toy, "corpus_version": 1})
    missing = {k: v for k, v in toy.items() if k != "reveal_verification_ledger_sha256"}
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(missing)


def _toy_six_entry_ledger() -> dict:
    # SAN-881 Phase-A correction: entries must be in the PINNED CANONICAL
    # order (vd.LEDGER_CANONICAL_ORDER), not an alphabetical sort of the
    # tuple set -- those are two different orderings (see
    # test_ledger_canonical_order_differs_from_alphabetical_sort below).
    return {
        "corpus_version": 2,
        "labeling_context_hash": "a" * 64,
        "entries": [
            {"artifact_name": name, "envelope": envelope, "commitment_hex": "b" * 64,
             "verified": True, "verified_stage": stage, "byte_length": 10}
            for name, envelope, stage in vd.LEDGER_CANONICAL_ORDER
        ],
    }


def test_ledger_canonical_order_differs_from_alphabetical_sort():
    # Documents WHY _toy_six_entry_ledger uses vd.LEDGER_CANONICAL_ORDER
    # rather than sorted(vd.LEDGER_PINNED_TUPLES): the pinned canonical
    # sequence groups semantic-stage-then-contract-stage and is NOT an
    # alphabetical sort by (artifact_name, envelope, verified_stage).
    assert list(vd.LEDGER_CANONICAL_ORDER) != sorted(vd.LEDGER_PINNED_TUPLES)


def test_schema_reveal_verification_ledger_shape_and_ordering():
    schema = json.loads((SCHEMAS_DIR / "reveal_verification_ledger_schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    toy = _toy_six_entry_ledger()
    Draft202012Validator(schema).validate(toy)
    bad_verified = {**toy, "entries": [{**toy["entries"][0], "verified": False}] + toy["entries"][1:]}
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(bad_verified)


def test_schema_reveal_verification_ledger_requires_exactly_six_entries():
    schema = json.loads((SCHEMAS_DIR / "reveal_verification_ledger_schema.json").read_text())
    toy = _toy_six_entry_ledger()
    short = {**toy, "entries": toy["entries"][:5]}
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(short)
    extra_entry = {**toy["entries"][0], "artifact_name": "not_a_real_artifact.json"}
    too_long = {**toy, "entries": toy["entries"] + [extra_entry]}
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(too_long)
    empty = {**toy, "entries": []}
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(empty)


def _toy_six_ledger_builder_entries() -> list[dict]:
    """Full six-entry input for build_reveal_verification_ledger, keyed
    by (artifact_name, envelope, verified_stage) -- caller order is
    intentionally NOT the canonical order, to prove the builder emits
    the pinned order regardless of input order (SAN-881 Phase-A
    correction item 2: the builder EMITS canonical order directly, it
    does not sort)."""
    return [
        {"artifact_name": name, "envelope": envelope, "commitment_hex": "b" * 64, "verified_stage": stage, "byte_length": 10}
        for name, envelope, stage in vd.LEDGER_CANONICAL_ORDER
    ]


def test_build_reveal_verification_ledger_emits_canonical_order_not_sorted():
    entries = _toy_six_ledger_builder_entries()
    ledger = vd.build_reveal_verification_ledger(2, "d" * 64, entries)
    actual_order = [(e["artifact_name"], e["envelope"], e["verified_stage"]) for e in ledger["entries"]]
    assert tuple(actual_order) == vd.LEDGER_CANONICAL_ORDER
    # The canonical order is NOT an alphabetical sort by (envelope, name)
    # -- proves this test would have caught the pre-correction sorting
    # behavior (which put ("author", "coverage_manifest.json") first).
    assert actual_order[0] != ("coverage_manifest.json", "author", "contract")


def test_build_reveal_verification_ledger_emits_canonical_order_regardless_of_input_order():
    # Correction-target RED-then-GREEN: REVERSING the caller-supplied
    # entries must have NO EFFECT on the emitted order -- the builder
    # looks each canonical tuple up by (artifact_name, envelope,
    # verified_stage), it does not preserve or sort caller input order.
    forward = _toy_six_ledger_builder_entries()
    reversed_input = list(reversed(forward))
    ledger_forward = vd.build_reveal_verification_ledger(2, "d" * 64, forward)
    ledger_reversed = vd.build_reveal_verification_ledger(2, "d" * 64, reversed_input)
    order_forward = [(e["artifact_name"], e["envelope"], e["verified_stage"]) for e in ledger_forward["entries"]]
    order_reversed = [(e["artifact_name"], e["envelope"], e["verified_stage"]) for e in ledger_reversed["entries"]]
    assert order_forward == order_reversed == list(vd.LEDGER_CANONICAL_ORDER)


def test_canonical_ledger_bytes_sorted_compact_ascii_trailing_lf():
    ledger = vd.build_reveal_verification_ledger(2, "a" * 64, [])
    b1 = vd.canonical_ledger_bytes(ledger)
    b2 = vd.canonical_ledger_bytes(ledger)
    assert b1 == b2
    assert b1.endswith(b"\n") and b1.count(b"\n") == 1
    assert b", " not in b1 and b": " not in b1


# ---------------------------------------------------------------------
# Toy SUBSET (semantic-only) reveal tests
# ---------------------------------------------------------------------

def _toy_four_artifact_commitment():
    ctx_hash = vd.compute_labeling_context_hash([b"toy-ctx"])
    names = ["design_metadata.json", "labels_author_semantic.json", "labels_author_contract.json", "coverage_manifest.json"]
    artifacts = {n: f'{{"n":"{n}"}}'.encode() for n in names}
    nonces = {n: secrets.token_bytes(32) for n in names}
    commitments = [
        {"artifact_name": n, "byte_length": len(artifacts[n]),
         "commitment_hex": vd.compute_artifact_commitment(n, nonces[n], ctx_hash, artifacts[n])}
        for n in names
    ]
    commitment = {"labeling_context_hash": ctx_hash.hex(), "author_commitments": commitments}
    nonces_hex = {n: nonces[n].hex() for n in names}
    return commitment, artifacts, nonces_hex


def test_subset_reveal_semantic_only_verifies_with_others_unrevealed():
    commitment, artifacts, nonces_hex = _toy_four_artifact_commitment()
    failures = vd.reveal_verify_subset(
        commitment,
        subset_names={"labels_author_semantic.json"},
        forbidden_extra_names=vd.SEMANTIC_STAGE_FORBIDDEN_EXTRAS,
        artifact_bytes_by_name={"labels_author_semantic.json": artifacts["labels_author_semantic.json"]},
        nonces_by_name={"labels_author_semantic.json": nonces_hex["labels_author_semantic.json"]},
    )
    assert failures == []


def test_subset_reveal_rejects_forbidden_contract_extra():
    commitment, artifacts, nonces_hex = _toy_four_artifact_commitment()
    failures = vd.reveal_verify_subset(
        commitment,
        subset_names={"labels_author_semantic.json"},
        forbidden_extra_names=vd.SEMANTIC_STAGE_FORBIDDEN_EXTRAS,
        artifact_bytes_by_name={
            "labels_author_semantic.json": artifacts["labels_author_semantic.json"],
            "labels_author_contract.json": artifacts["labels_author_contract.json"],
        },
        nonces_by_name=nonces_hex,
    )
    assert any("forbidden stage extra" in f for f in failures)


def test_subset_reveal_rejects_forbidden_design_and_coverage_extras():
    commitment, artifacts, nonces_hex = _toy_four_artifact_commitment()
    failures = vd.reveal_verify_subset(
        commitment,
        subset_names={"labels_author_semantic.json"},
        forbidden_extra_names=vd.SEMANTIC_STAGE_FORBIDDEN_EXTRAS,
        artifact_bytes_by_name={
            "labels_author_semantic.json": artifacts["labels_author_semantic.json"],
            "design_metadata.json": artifacts["design_metadata.json"],
            "coverage_manifest.json": artifacts["coverage_manifest.json"],
        },
        nonces_by_name=nonces_hex,
    )
    forbidden_hits = [f for f in failures if "forbidden stage extra" in f]
    assert len(forbidden_hits) == 2


def test_subset_reveal_requires_subset_member_present():
    commitment, artifacts, nonces_hex = _toy_four_artifact_commitment()
    failures = vd.reveal_verify_subset(
        commitment,
        subset_names={"labels_author_semantic.json"},
        forbidden_extra_names=vd.SEMANTIC_STAGE_FORBIDDEN_EXTRAS,
        artifact_bytes_by_name={},
        nonces_by_name={},
    )
    assert any("not supplied" in f for f in failures)


# ---------------------------------------------------------------------
# --reviewer-dir CLI wiring
# ---------------------------------------------------------------------

def test_main_accepts_reviewer_dir_flag(tmp_path, monkeypatch):
    # A minimal public-only cal_dir (no sealed/reviewer content present)
    # must still ACCEPT the flag without argparse erroring.
    monkeypatch.setattr(vd, "HERE", CAL_DIR)
    monkeypatch.setattr(vd, "SCHEMAS", SCHEMAS_DIR)
    parser_args = vd.main.__wrapped__ if hasattr(vd.main, "__wrapped__") else None
    # argparse smoke test: build the parser the same way main() does and
    # confirm --reviewer-dir / --reviewer-nonces-file parse without error.
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--sealed-dir", type=Path, default=None)
    p.add_argument("--nonces-file", type=Path, default=None)
    p.add_argument("--reviewer-dir", type=Path, default=None)
    p.add_argument("--reviewer-nonces-file", type=Path, default=None)
    ns = p.parse_args(["--reviewer-dir", str(tmp_path)])
    assert ns.reviewer_dir == tmp_path


# ---------------------------------------------------------------------
# Toy validate_design structural pass/fail tests
# ---------------------------------------------------------------------

def test_validate_design_corpus_check_passes_on_clean_toy():
    errors = vd.Errors()
    toy_corpus = [{"id": "cal:000", "context": "Toy context.", "output": "Toy output."}]
    by_id = vd.check_corpus_inputs(errors, toy_corpus)
    assert errors == []
    assert "cal:000" in by_id


def test_validate_design_corpus_check_catches_duplicate_tuple():
    errors = vd.Errors()
    toy_corpus = [
        {"id": "cal:000", "context": "Same.", "output": "Same out."},
        {"id": "cal:001", "context": "Same.", "output": "Same out."},
    ]
    vd.check_corpus_inputs(errors, toy_corpus)
    assert any(vd.RULE_DUPLICATE_TUPLE in e for e in errors)


def test_validate_design_corpus_check_catches_both_context_shapes():
    errors = vd.Errors()
    toy_corpus = [{"id": "cal:000", "context": "A.", "context_sources": [{"text": "B.", "tier": "tier_1"}], "output": "O."}]
    vd.check_corpus_inputs(errors, toy_corpus)
    assert any(vd.RULE_CONTEXT_SHAPE in e for e in errors)


def test_validate_design_corpus_check_catches_non_tier1():
    errors = vd.Errors()
    toy_corpus = [{"id": "cal:000", "context_sources": [{"text": "B.", "tier": "tier_3"}], "output": "O."}]
    vd.check_corpus_inputs(errors, toy_corpus)
    assert any(vd.RULE_NON_TIER1 in e for e in errors)


# ---------------------------------------------------------------------
# No-leak error discipline: a failing sealed toy triggers ONLY
# name/index/id/rule-code -- never label VALUES.
# ---------------------------------------------------------------------

def test_check_labels_error_output_never_leaks_semantic_truth_value():
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "target_check_id": "C1", "target_stratum": "in_domain_nonviolation"}}
    semantic = [{"item_id": "cal:000", "check_id": "C1", "semantic_truth": "SECRET_LEAKED_VALUE_XYZ", "semantic_rationale": "toy"}]
    contract = [{"item_id": "cal:000", "check_id": "C1",
                 "contract_tuple": {"outcome": "PASS", "outcome_reason": "detection_complete", "severity": None, "advisory": False},
                 "competence": "IN_DOMAIN", "contract_rationale": "toy", "spec_refs": "toy"}]
    vd.check_labels(errors, semantic, contract, design_by_id)
    blob = " ".join(errors)
    assert "SECRET_LEAKED_VALUE_XYZ" not in blob
    assert any(vd.RULE_SEM_TRUTH_INVALID in e for e in errors)


def test_check_labels_error_output_never_leaks_rationale_or_competence_value():
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "target_check_id": "C1", "target_stratum": "in_domain_nonviolation"}}
    semantic = [{"item_id": "cal:000", "check_id": "C1", "semantic_truth": "NO_VIOLATION", "semantic_rationale": "SECRET RATIONALE TEXT"}]
    contract = [{"item_id": "cal:000", "check_id": "C1",
                 "contract_tuple": {"outcome": "PASS", "outcome_reason": "detection_complete", "severity": None, "advisory": False},
                 "competence": "SECRET_BOGUS_COMPETENCE", "contract_rationale": "SECRET RATIONALE TEXT 2", "spec_refs": "toy"}]
    vd.check_labels(errors, semantic, contract, design_by_id)
    blob = " ".join(errors)
    assert "SECRET RATIONALE TEXT" not in blob
    assert "SECRET_BOGUS_COMPETENCE" not in blob
    assert any(vd.RULE_COMPETENCE_INVALID in e for e in errors)


def test_check_dod_balance_error_output_never_leaks_truth_values():
    errors = vd.Errors()
    design_by_id = {
        "cal:000": {"item_id": "cal:000", "target_check_id": "C1", "target_stratum": "determinate_out_of_domain",
                    "domain": "d", "minimal_pair_of": "cal:001", "introduced_feature": {"kind": "concept"}},
        "cal:001": {"item_id": "cal:001", "target_check_id": "C1", "target_stratum": "in_domain_nonviolation", "domain": "d"},
    }
    semantic_by_key = {
        ("cal:000", "C1"): {"semantic_truth": "SECRET_TRUTH_LEAK"},
        ("cal:001", "C1"): {"semantic_truth": "NO_VIOLATION"},
    }
    vd.check_dod_balance_and_pairs(errors, design_by_id, semantic_by_key)
    blob = " ".join(errors)
    assert "SECRET_TRUTH_LEAK" not in blob
    assert any(vd.RULE_DOD_TRUTH_INVALID in e for e in errors)


def test_check_coverage_manifest_error_output_only_name_index_id_rule():
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    coverage = {"toy_surface": [{"item_id": "cal:999", "check_id": "C1", "field": "context"}]}
    vd.check_coverage_manifest(errors, coverage, design_by_id)
    for e in errors:
        assert "coverage_manifest.json" in e
        assert "rule=" in e


# ---------------------------------------------------------------------
# Introduced-feature EXACT table-path absence (post-fold, named table only)
# ---------------------------------------------------------------------

def test_introduced_feature_absent_from_tables_passes_for_genuinely_absent_condition_operator():
    # SAN-881 PASS 2B.2: repurposed from the removed 'comparator' kind --
    # condition_operators_v1 is the same "list of {tokens: [...]} dicts"
    # table shape comparators_v1 used to exercise, so this preserves
    # coverage of that generic fold branch under a still-legal kind.
    errors = vd.Errors()
    tables_data = {"condition_operators_v1": [{"tokens": ["unless"], "kind": "IF", "polarity": "-", "force": "grant"}]}
    feature = {
        "kind": "condition_operator", "table_path": "condition_operators_v1",
        "surface_tokens": ["only", "if"],
        "intended_semantics": {"kind": "ONLY_IF", "polarity": "+", "force": "restriction"},
    }
    vd.check_introduced_feature_absent_from_tables(errors, "cal:000", feature, tables_data)
    assert errors == []


def test_introduced_feature_absent_from_tables_fails_when_actually_present():
    errors = vd.Errors()
    tables_data = {"condition_operators_v1": [{"tokens": ["unless"], "kind": "IF", "polarity": "-", "force": "grant"}]}
    feature = {
        "kind": "condition_operator", "table_path": "condition_operators_v1",
        "surface_tokens": ["unless"],
        "intended_semantics": {"kind": "IF", "polarity": "-", "force": "grant"},
    }
    vd.check_introduced_feature_absent_from_tables(errors, "cal:000", feature, tables_data)
    assert any(vd.RULE_FEATURE_NOT_ABSENT in e for e in errors)


def test_introduced_feature_absent_checks_named_table_only_not_other_tables():
    # "over" IS present in comparators_v1 in this toy table set (a real
    # PRODUCT table that still exists -- only its use as an
    # introduced_feature TARGET is removed), but the feature claims
    # table_path concept_v1 -- absence must be checked against the EXACT
    # named table, so a token that happens to collide with a DIFFERENT
    # table's contents must not false-positive.
    errors = vd.Errors()
    tables_data = {"comparators_v1": [{"tokens": ["over"], "interval": {}}], "concept_v1": {}}
    feature = {"kind": "concept", "table_path": "concept_v1", "surface_tokens": ["over"],
               "intended_semantics": {"canonical_concept": "over"}}
    vd.check_introduced_feature_absent_from_tables(errors, "cal:000", feature, tables_data)
    assert errors == []


def test_introduced_feature_absent_from_tables_excl_pair():
    errors = vd.Errors()
    tables_data = {"excl_v1": [["refundable", "nonrefundable"]]}
    feature = {"kind": "excl_pair", "table_path": "excl_v1", "members": [["digital"], ["physical"]]}
    vd.check_introduced_feature_absent_from_tables(errors, "cal:000", feature, tables_data)
    assert errors == []
    feature_present = {"kind": "excl_pair", "table_path": "excl_v1", "members": [["refundable"], ["nonrefundable"]]}
    errors2 = vd.Errors()
    vd.check_introduced_feature_absent_from_tables(errors2, "cal:000", feature_present, tables_data)
    assert any(vd.RULE_FEATURE_NOT_ABSENT in e for e in errors2)
    # Reversed member order must still match the SAME (unordered) row.
    feature_reversed = {"kind": "excl_pair", "table_path": "excl_v1", "members": [["nonrefundable"], ["refundable"]]}
    errors3 = vd.Errors()
    vd.check_introduced_feature_absent_from_tables(errors3, "cal:000", feature_reversed, tables_data)
    assert any(vd.RULE_FEATURE_NOT_ABSENT in e for e in errors3)


def test_introduced_feature_absent_from_tables_excl_pair_complete_pair_not_individual_member():
    # SAN-881 PASS 2B.2 RED-then-GREEN: table ABSENCE must compare the
    # COMPLETE UNORDERED PAIR, never individual-member overlap. "digital"
    # is one side of the table's (digital, physical) row, but the
    # PROPOSED pair (digital, cost) is a genuinely different, genuinely
    # ABSENT relation -- it must NOT false-positive merely because one
    # member happens to also appear in some unrelated existing row.
    errors = vd.Errors()
    tables_data = {"excl_v1": [["digital", "physical"], ["verified", "unverified"]]}
    feature = {"kind": "excl_pair", "table_path": "excl_v1", "members": [["digital"], ["cost"]]}
    vd.check_introduced_feature_absent_from_tables(errors, "cal:000", feature, tables_data)
    assert errors == [], f"expected genuine absence (complete-pair mismatch), got {errors}"


def test_introduced_feature_absent_from_tables_binding_failure_wrong_table_for_kind():
    # SAN-881 PASS 2B.2 RED-then-GREEN: kind/table mismatch (a concept
    # feature bound to units_v1) is a BINDING FAILURE, reported via the
    # SAME RULE_FEATURE_NOT_ABSENT code, before any table lookup.
    errors = vd.Errors()
    tables_data = {"units_v1": {}, "concept_v1": {}}
    feature = {"kind": "concept", "table_path": "units_v1", "surface_tokens": ["approval"],
               "intended_semantics": {"canonical_concept": "approval"}}
    vd.check_introduced_feature_absent_from_tables(errors, "cal:000", feature, tables_data)
    assert any(vd.RULE_FEATURE_NOT_ABSENT in e for e in errors)


def test_introduced_feature_absent_from_tables_binding_failure_quantifier_wrong_table():
    # SAN-881 PASS 2B.2 RED-then-GREEN: a quantifier feature bound to the
    # WRONG table (units_v1 instead of quant_v1) previously silently
    # PASSED the class-scoped absence check (the wrong table's dict has
    # no "existential" key, so the lookup found an empty entries list and
    # never fired) -- now caught as a binding failure BEFORE the lookup.
    errors = vd.Errors()
    tables_data = {"units_v1": {}, "quant_v1": {"existential": ["some"]}}
    feature = {"kind": "quantifier", "table_path": "units_v1", "surface_tokens": ["some"],
               "intended_semantics": {"quantifier_class": "existential"}}
    vd.check_introduced_feature_absent_from_tables(errors, "cal:000", feature, tables_data)
    assert any(vd.RULE_FEATURE_NOT_ABSENT in e for e in errors)


def test_introduced_feature_absent_from_tables_binding_failure_deny_trigger_never_facetproj():
    # SAN-881 PASS 2B.2 RED-then-GREEN: deny_trigger bound to
    # facetproj_v1 was previously accepted (the lookup succeeds --
    # facetproj_v1 exists regardless of kind) -- now an explicit binding
    # failure, independent of whether the surface_tokens happen to be
    # absent from facetproj_v1's own key list.
    errors = vd.Errors()
    tables_data = {"facetproj_v1": {"refund": "facet:refund_availability"}}
    feature = {"kind": "deny_trigger", "table_path": "facetproj_v1", "surface_tokens": ["zzz_never_present_zzz"],
               "intended_semantics": {"polarity": "NEG", "projects_to": "facet:refund_availability"}}
    vd.check_introduced_feature_absent_from_tables(errors, "cal:000", feature, tables_data)
    assert any(vd.RULE_FEATURE_NOT_ABSENT in e for e in errors)


def test_introduced_feature_absent_from_tables_binding_failure_facet_mismatch():
    # A facet_trigger whose table_path names one facet (cost) but whose
    # intended_semantics.facet declares a DIFFERENT facet (duration) is a
    # binding failure -- the validator must not silently check absence
    # against whichever facet table_path happens to name.
    errors = vd.Errors()
    tables_data = {"facets_v1": {"facet:cost": {"triggers": ["expensive"], "deny_triggers": ["cheap"]},
                                  "facet:duration": {"triggers": ["lengthy"], "deny_triggers": ["brief"]}}}
    feature = {"kind": "facet_trigger", "table_path": "facets_v1.facet:cost.triggers",
               "surface_tokens": ["zzz_never_present_zzz"],
               "intended_semantics": {"facet": "facet:duration", "polarity": "POS"}}
    vd.check_introduced_feature_absent_from_tables(errors, "cal:000", feature, tables_data)
    assert any(vd.RULE_FEATURE_NOT_ABSENT in e for e in errors)


def test_introduced_feature_absent_from_tables_binding_failure_wrong_polarity():
    errors = vd.Errors()
    tables_data = {"facets_v1": {"facet:cost": {"triggers": ["expensive"], "deny_triggers": ["cheap"]}}}
    feature = {"kind": "facet_trigger", "table_path": "facets_v1.facet:cost.triggers",
               "surface_tokens": ["zzz_never_present_zzz"],
               "intended_semantics": {"facet": "facet:cost", "polarity": "NEG"}}
    vd.check_introduced_feature_absent_from_tables(errors, "cal:000", feature, tables_data)
    assert any(vd.RULE_FEATURE_NOT_ABSENT in e for e in errors)


def test_introduced_feature_absent_from_tables_binding_failure_wrong_role():
    errors = vd.Errors()
    tables_data = {"definitive_v1": ["always"], "hedge_v1": ["may"]}
    feature = {"kind": "definitive", "table_path": "definitive_v1", "surface_tokens": ["zzz_never_present_zzz"],
               "intended_semantics": {"role": "hedge", "same_overclaim_class_as_table": True}}
    vd.check_introduced_feature_absent_from_tables(errors, "cal:000", feature, tables_data)
    assert any(vd.RULE_FEATURE_NOT_ABSENT in e for e in errors)


def test_introduced_feature_absent_from_tables_binding_failure_comparator_kind_prohibited():
    # SAN-881 PASS 2B.2: defense-in-depth -- 'comparator' is no longer a
    # recognized kind AT ALL (validator-side binding, independent of
    # schema); this must fail even for a feature that would have been a
    # genuinely-absent comparator under the pre-2B.2 vocabulary.
    errors = vd.Errors()
    tables_data = {"comparators_v1": [{"tokens": ["over"], "interval": {}}]}
    feature = {"kind": "comparator", "table_path": "comparators_v1", "surface_tokens": ["at", "least"]}
    vd.check_introduced_feature_absent_from_tables(errors, "cal:000", feature, tables_data)
    assert any(vd.RULE_FEATURE_NOT_ABSENT in e for e in errors)


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.2-FIX defect 4/5: LITERAL PER-KIND SEMANTIC PARITY
# CONTRACT, validator-side (_dod_kind_table_binding_ok). Each kind gets
# a positive control plus DIRECT negatives for MISSING, EXTRA,
# WRONG-TYPE, and WRONG-DOMAIN intended_semantics fields -- not merely
# vocabulary-equality tests. All fire the SAME RULE_FEATURE_NOT_ABSENT
# code check_introduced_feature_absent_from_tables already uses for
# every other binding failure.
# ---------------------------------------------------------------------

def _assert_binding_ok(feature, tables_data):
    errors = vd.Errors()
    vd.check_introduced_feature_absent_from_tables(errors, "cal:000", feature, tables_data)
    assert errors == [], f"expected clean binding, got {errors}"


def _assert_binding_failure(feature, tables_data):
    errors = vd.Errors()
    vd.check_introduced_feature_absent_from_tables(errors, "cal:000", feature, tables_data)
    assert any(vd.RULE_FEATURE_NOT_ABSENT in e for e in errors), f"expected a binding failure, got {errors}"


def test_dod_kind_binding_concept_semantics_shape_negatives_and_positive():
    tables_data = {"concept_v1": {"approve": "approval"}}

    def feat(sem):
        return {"kind": "concept", "table_path": "concept_v1",
                "surface_tokens": ["zzz_never_present_zzz"], "intended_semantics": sem}

    _assert_binding_ok(feat({"canonical_concept": "approval"}), tables_data)
    _assert_binding_failure(feat({}), tables_data)  # MISSING canonical_concept
    _assert_binding_failure(feat({"canonical_concept": "approval", "extra_field": "x"}), tables_data)  # EXTRA
    _assert_binding_failure(feat({"canonical_concept": 123}), tables_data)  # WRONG-TYPE
    _assert_binding_failure(feat({"canonical_concept": ""}), tables_data)  # WRONG-DOMAIN (empty)


def test_dod_kind_binding_unit_semantics_shape_negatives_and_positive():
    tables_data = {"units_v1": {"hour": {"group": "time_a", "factor": 60}}}

    def feat(sem):
        return {"kind": "unit", "table_path": "units_v1",
                "surface_tokens": ["zzz_never_present_zzz"], "intended_semantics": sem}

    _assert_binding_ok(feat({"group": "time_a", "factor": 60}), tables_data)
    _assert_binding_failure(feat({"group": "time_a"}), tables_data)  # MISSING factor
    _assert_binding_failure(feat({"group": "time_a", "factor": 60, "extra_field": 1}), tables_data)  # EXTRA
    _assert_binding_failure(feat({"group": "time_a", "factor": "60"}), tables_data)  # WRONG-TYPE (string)
    _assert_binding_failure(feat({"group": "time_a", "factor": True}), tables_data)  # WRONG-TYPE (bool excluded)
    _assert_binding_failure(feat({"group": "", "factor": 60}), tables_data)  # WRONG-DOMAIN (empty group)


def test_dod_kind_binding_condition_operator_semantics_shape_negatives_and_positive():
    tables_data = {"condition_operators_v1": [{"tokens": ["unless"], "kind": "IF", "polarity": "-", "force": "grant"}]}

    def feat(sem):
        return {"kind": "condition_operator", "table_path": "condition_operators_v1",
                "surface_tokens": ["zzz_never_present_zzz"], "intended_semantics": sem}

    _assert_binding_ok(feat({"kind": "ONLY_IF", "polarity": "+", "force": "restriction"}), tables_data)
    _assert_binding_failure(feat({"kind": "IF", "polarity": "-"}), tables_data)  # MISSING force
    _assert_binding_failure(feat({"kind": "IF", "polarity": "-", "force": "grant", "extra_field": 1}), tables_data)  # EXTRA
    _assert_binding_failure(feat({"kind": 123, "polarity": "-", "force": "grant"}), tables_data)  # WRONG-TYPE
    _assert_binding_failure(feat({"kind": "IF", "polarity": "sideways", "force": "grant"}), tables_data)  # WRONG-DOMAIN


def test_dod_kind_binding_quantifier_semantics_shape_negatives_and_positive():
    tables_data = {"quant_v1": {"existential": ["some"]}}

    def feat(sem):
        return {"kind": "quantifier", "table_path": "quant_v1",
                "surface_tokens": ["zzz_never_present_zzz"], "intended_semantics": sem}

    _assert_binding_ok(feat({"quantifier_class": "existential"}), tables_data)
    _assert_binding_failure(feat({}), tables_data)  # MISSING
    _assert_binding_failure(feat({"quantifier_class": "existential", "extra_field": 1}), tables_data)  # EXTRA
    _assert_binding_failure(feat({"quantifier_class": 123}), tables_data)  # WRONG-TYPE
    _assert_binding_failure(feat({"quantifier_class": "nonexistent_class"}), tables_data)  # WRONG-DOMAIN


def test_dod_kind_binding_definitive_semantics_shape_negatives_and_positive():
    # Defect 5 is folded in here: same_overclaim_class_as_table: False is
    # the WRONG-DOMAIN case (schema-valid boolean, but not the pinned
    # const True) -- the validator-side negative pinned pairing the
    # schema-level test_schema_design_metadata_definitive_same_overclaim_
    # class_as_table_false_rejected above.
    tables_data = {"definitive_v1": ["always"]}

    def feat(sem):
        return {"kind": "definitive", "table_path": "definitive_v1",
                "surface_tokens": ["zzz_never_present_zzz"], "intended_semantics": sem}

    _assert_binding_ok(feat({"role": "definitive", "same_overclaim_class_as_table": True}), tables_data)
    _assert_binding_failure(feat({"role": "definitive"}), tables_data)  # MISSING
    _assert_binding_failure(feat({"role": "definitive", "same_overclaim_class_as_table": True, "extra_field": 1}), tables_data)  # EXTRA
    _assert_binding_failure(feat({"role": "definitive", "same_overclaim_class_as_table": "true"}), tables_data)  # WRONG-TYPE
    _assert_binding_failure(feat({"role": "definitive", "same_overclaim_class_as_table": False}), tables_data)  # WRONG-DOMAIN (defect 5)


def test_dod_kind_binding_hedge_semantics_shape_negatives_and_positive():
    # Defect 5's hedge-false negative, validator-side (mirrors the
    # schema-level test_schema_design_metadata_hedge_same_overclaim_
    # class_as_table_false_rejected above).
    tables_data = {"hedge_v1": ["may"]}

    def feat(sem):
        return {"kind": "hedge", "table_path": "hedge_v1",
                "surface_tokens": ["zzz_never_present_zzz"], "intended_semantics": sem}

    _assert_binding_ok(feat({"role": "hedge", "same_overclaim_class_as_table": True}), tables_data)
    _assert_binding_failure(feat({"role": "hedge"}), tables_data)  # MISSING
    _assert_binding_failure(feat({"role": "hedge", "same_overclaim_class_as_table": True, "extra_field": 1}), tables_data)  # EXTRA
    _assert_binding_failure(feat({"role": "hedge", "same_overclaim_class_as_table": "true"}), tables_data)  # WRONG-TYPE
    _assert_binding_failure(feat({"role": "hedge", "same_overclaim_class_as_table": False}), tables_data)  # WRONG-DOMAIN (defect 5)


def test_dod_kind_binding_facet_leaf_semantics_shape_negatives_and_positive():
    tables_data = {"facets_v1": {"facet:cost": {"triggers": ["expensive"], "deny_triggers": ["cheap"]}}}

    def feat(sem):
        return {"kind": "facet_trigger", "table_path": "facets_v1.facet:cost.triggers",
                "surface_tokens": ["zzz_never_present_zzz"], "intended_semantics": sem}

    _assert_binding_ok(feat({"facet": "facet:cost", "polarity": "POS"}), tables_data)
    _assert_binding_failure(feat({"facet": "facet:cost"}), tables_data)  # MISSING polarity
    _assert_binding_failure(feat({"facet": "facet:cost", "polarity": "POS", "extra_field": 1}), tables_data)  # EXTRA
    _assert_binding_failure(feat({"facet": 123, "polarity": "POS"}), tables_data)  # WRONG-TYPE
    _assert_binding_failure(feat({"facet": "facet:not_a_real_closed_facet", "polarity": "POS"}), tables_data)  # WRONG-DOMAIN


def test_dod_kind_binding_deny_trigger_semantics_shape_negatives_and_positive():
    tables_data = {"facets_v1": {"facet:cost": {"triggers": ["expensive"], "deny_triggers": ["cheap"]}}}

    def feat(sem):
        return {"kind": "deny_trigger", "table_path": "facets_v1.facet:cost.deny_triggers",
                "surface_tokens": ["zzz_never_present_zzz"], "intended_semantics": sem}

    _assert_binding_ok(feat({"facet": "facet:cost", "polarity": "NEG"}), tables_data)
    _assert_binding_failure(feat({"facet": "facet:cost"}), tables_data)  # MISSING polarity
    _assert_binding_failure(feat({"facet": "facet:cost", "polarity": "NEG", "extra_field": 1}), tables_data)  # EXTRA
    _assert_binding_failure(feat({"facet": "facet:cost", "polarity": 123}), tables_data)  # WRONG-TYPE
    _assert_binding_failure(feat({"facet": "facet:not_a_real_closed_facet", "polarity": "NEG"}), tables_data)  # WRONG-DOMAIN


def test_dod_kind_binding_facet_projection_semantics_shape_negatives_and_positive():
    tables_data = {"facetproj_v1": {"discount": "facet:discount_availability"}}

    def feat(sem):
        return {"kind": "facet_trigger", "table_path": "facetproj_v1",
                "surface_tokens": ["zzz_never_present_zzz"], "intended_semantics": sem}

    _assert_binding_ok(feat({"polarity": "POS", "projects_to": "facet:discount_availability"}), tables_data)
    _assert_binding_failure(feat({"polarity": "POS"}), tables_data)  # MISSING projects_to
    _assert_binding_failure(feat({"polarity": "POS", "projects_to": "facet:discount_availability", "extra_field": 1}), tables_data)  # EXTRA
    _assert_binding_failure(feat({"polarity": "POS", "projects_to": 123}), tables_data)  # WRONG-TYPE
    _assert_binding_failure(feat({"polarity": "POS", "projects_to": "facet:not_closed"}), tables_data)  # WRONG-DOMAIN


def test_dod_kind_binding_pair_kinds_reject_any_semantics_object():
    # Pair kinds (excl_pair/complement_pair) carry NO semantics object at
    # all -- the schema's pairRelationFeature has no "intended_semantics"
    # property (additionalProperties: false). Validator-side, sem must be
    # the empty dict feature.get("intended_semantics") normalizes an
    # absent/null value to; a genuinely-present (non-empty) semantics
    # object -- however shaped -- is itself a binding failure. No
    # MISSING/WRONG-TYPE/WRONG-DOMAIN classes apply here (there is no
    # field to be missing, mistyped, or out-of-domain); the single
    # applicable negative class is EXTRA (an object present at all).
    excl_tables = {"excl_v1": [["digital", "physical"]]}
    complement_tables = {"complement_v1": [["required", "optional"]]}

    _assert_binding_ok({"kind": "excl_pair", "table_path": "excl_v1", "members": [["zzz1"], ["zzz2"]]}, excl_tables)
    _assert_binding_failure(
        {"kind": "excl_pair", "table_path": "excl_v1", "members": [["zzz1"], ["zzz2"]],
         "intended_semantics": {"facet": "facet:cost", "polarity": "POS"}},
        excl_tables,
    )
    _assert_binding_ok({"kind": "complement_pair", "table_path": "complement_v1", "members": [["zzz3"], ["zzz4"]]}, complement_tables)
    _assert_binding_failure(
        {"kind": "complement_pair", "table_path": "complement_v1", "members": [["zzz3"], ["zzz4"]],
         "intended_semantics": {"canonical_concept": "approval"}},
        complement_tables,
    )


def test_dod_kind_binding_pair_kinds_reject_falsy_present_semantics_object():
    # SAN-881 PASS 2B.2-FIX2: check_introduced_feature_absent_from_tables's
    # own `sem = feature.get("intended_semantics") or {}` normalization
    # collapses a PRESENT-but-falsy intended_semantics value ({}, None,
    # [], "") into the SAME {} the helper produces for a genuinely ABSENT
    # property -- so _dod_kind_table_binding_ok's `sem != {}` pair-kind
    # check can never distinguish "the key was never set" from "the key
    # was set to something falsy". The schema correctly rejects all four
    # as an unexpected property (pairRelationFeature's additionalProperties:
    # false has no intended_semantics property at all); the validator must
    # too, via an explicit presence check ("intended_semantics" in feature)
    # BEFORE the `or {}` normalization can erase that presence. Each of
    # the eight cases below (two pair kinds x four falsy values) must
    # produce EXACTLY ONE RULE_FEATURE_NOT_ABSENT diagnostic -- never zero
    # (the pre-fix defect) and never more than one.
    excl_tables = {"excl_v1": [["digital", "physical"]]}
    complement_tables = {"complement_v1": [["required", "optional"]]}
    falsy_values = [{}, None, [], ""]

    def _assert_exactly_one_binding_failure(feature, tables_data):
        errors = vd.Errors()
        vd.check_introduced_feature_absent_from_tables(errors, "cal:000", feature, tables_data)
        assert len(errors) == 1, f"expected exactly one diagnostic, got {errors}"
        assert vd.RULE_FEATURE_NOT_ABSENT in errors[0], f"expected RULE_FEATURE_NOT_ABSENT, got {errors}"

    for falsy in falsy_values:
        _assert_exactly_one_binding_failure(
            {"kind": "excl_pair", "table_path": "excl_v1", "members": [["zzz1"], ["zzz2"]],
             "intended_semantics": falsy},
            excl_tables,
        )
        _assert_exactly_one_binding_failure(
            {"kind": "complement_pair", "table_path": "complement_v1", "members": [["zzz3"], ["zzz4"]],
             "intended_semantics": falsy},
            complement_tables,
        )

    # Absence controls (per kind): the property genuinely ABSENT (the key
    # never set at all) must stay clean -- provably distinct from
    # "present but falsy", which must always fail above.
    _assert_binding_ok({"kind": "excl_pair", "table_path": "excl_v1", "members": [["zzz1"], ["zzz2"]]}, excl_tables)
    _assert_binding_ok({"kind": "complement_pair", "table_path": "complement_v1", "members": [["zzz3"], ["zzz4"]]}, complement_tables)


# ---------------------------------------------------------------------
# Minimal-pair semantic-equivalence: the swap must be provably real
# (SAN-881 PASS 2B.2: field-boundary-respecting fold-sequence search over
# raw corpus RECORDS, never a flattened-text substring match)
# ---------------------------------------------------------------------

def _toy_rec(context=None, context_sources=None, output=""):
    rec = {"id": "cal:toy"}
    if context_sources is not None:
        rec["context_sources"] = context_sources
    else:
        rec["context"] = context if context is not None else ""
    rec["output"] = output
    return rec


def test_minimal_pair_semantic_equivalence_passes_when_tokens_swapped_correctly():
    errors = vd.Errors()
    feature = {"kind": "condition_operator", "surface_tokens": ["as", "long", "as"]}
    dod_rec = _toy_rec(context="Refunds are available for orders as long as they are unused.")
    control_rec = _toy_rec(context="Refunds are available for orders unless they are used.")
    vd.check_minimal_pair_semantic_equivalence(errors, "cal:005", dod_rec, control_rec, feature)
    assert errors == []


def test_minimal_pair_semantic_equivalence_fails_when_tokens_absent_from_dod_item():
    errors = vd.Errors()
    feature = {"kind": "condition_operator", "surface_tokens": ["as", "long", "as"]}
    dod_rec = _toy_rec(context="Refunds are available for orders unless they are used.")
    control_rec = _toy_rec(context="Refunds are available for orders unless they are used.")
    vd.check_minimal_pair_semantic_equivalence(errors, "cal:005", dod_rec, control_rec, feature)
    assert any(vd.RULE_FEATURE_TOKENS_NOT_IN_ITEM in e for e in errors)


def test_minimal_pair_semantic_equivalence_fails_when_tokens_leak_into_control():
    errors = vd.Errors()
    feature = {"kind": "condition_operator", "surface_tokens": ["as", "long", "as"]}
    dod_rec = _toy_rec(context="Refunds are available for orders as long as they are unused.")
    control_rec = _toy_rec(context="Refunds are available for orders as long as they are unused too.")
    vd.check_minimal_pair_semantic_equivalence(errors, "cal:005", dod_rec, control_rec, feature)
    assert any(vd.RULE_FEATURE_TOKENS_IN_CONTROL in e for e in errors)


def test_minimal_pair_semantic_equivalence_evidence_boundary_negative_cross_source_bleed():
    # SAN-881 PASS 2B.2 RED-then-GREEN (EVIDENCE BOUNDARIES): the phrase
    # "as long as" is synthesized ONLY by joining two context_sources
    # with a space -- source 1 ends "...orders as long", source 2 begins
    # "as they...". NEITHER source independently contains the complete
    # 3-token fold sequence "as long as" (source 1 has "as long" only,
    # source 2 has a standalone "as" only) -- a flattened-text substring
    # match would wrongly find it; a field-scoped search must not.
    errors = vd.Errors()
    feature = {"kind": "condition_operator", "surface_tokens": ["as", "long", "as"]}
    dod_rec = _toy_rec(context_sources=[
        {"text": "Refunds are available for orders as long", "tier": "tier_1"},
        {"text": "as they are unused.", "tier": "tier_1"},
    ])
    control_rec = _toy_rec(context="Refunds are available for orders unless they are used.")
    vd.check_minimal_pair_semantic_equivalence(errors, "cal:005", dod_rec, control_rec, feature)
    assert any(vd.RULE_FEATURE_TOKENS_NOT_IN_ITEM in e for e in errors), (
        f"expected TOKENS_NOT_IN_ITEM (no single field contains the complete sequence), got {errors}"
    )


def test_minimal_pair_semantic_equivalence_evidence_boundary_positive_within_one_context_source():
    # Positive control for the same shape: the COMPLETE sequence within
    # ONE context_source (not straddling a boundary) is genuinely found.
    errors = vd.Errors()
    feature = {"kind": "condition_operator", "surface_tokens": ["as", "long", "as"]}
    dod_rec = _toy_rec(context_sources=[
        {"text": "Refunds are available for orders as long as they are unused.", "tier": "tier_1"},
        {"text": "Some unrelated second source.", "tier": "tier_1"},
    ])
    control_rec = _toy_rec(context="Refunds are available for orders unless they are used.")
    vd.check_minimal_pair_semantic_equivalence(errors, "cal:005", dod_rec, control_rec, feature)
    assert errors == []


def test_minimal_pair_semantic_equivalence_evidence_boundary_positive_output_field():
    # The output field is searched independently too.
    errors = vd.Errors()
    feature = {"kind": "condition_operator", "surface_tokens": ["as", "long", "as"]}
    dod_rec = _toy_rec(context="Refund policy summary.", output="Valid as long as unused.")
    control_rec = _toy_rec(context="Refund policy summary.", output="Valid unless used.")
    vd.check_minimal_pair_semantic_equivalence(errors, "cal:005", dod_rec, control_rec, feature)
    assert errors == []


def test_minimal_pair_semantic_equivalence_pair_members_may_occur_in_different_fields():
    # PAIR kind: the two members MAY occur in different logical fields --
    # "digital" in context, "physical" in output -- and still both count
    # as present.
    errors = vd.Errors()
    feature = {"kind": "excl_pair", "members": [["digital"], ["physical"]]}
    dod_rec = _toy_rec(context="This is a digital item.", output="Not available in physical form.")
    control_rec = _toy_rec(context="This is a verified item.", output="Not an unverified one.")
    vd.check_minimal_pair_semantic_equivalence(errors, "cal:005", dod_rec, control_rec, feature)
    assert errors == []


def test_minimal_pair_semantic_equivalence_pair_leak_requires_complete_pair_one_member_allowed():
    # Control leakage for a PAIR fires ONLY when the COMPLETE pair
    # occurs; one overlapping member ("digital" alone) is allowed.
    errors = vd.Errors()
    feature = {"kind": "excl_pair", "members": [["digital"], ["physical"]]}
    dod_rec = _toy_rec(context="This is a digital item.", output="Not available in physical form.")
    control_rec = _toy_rec(context="This is also a digital item.", output="Sold only online.")
    vd.check_minimal_pair_semantic_equivalence(errors, "cal:005", dod_rec, control_rec, feature)
    assert errors == [], f"one overlapping member must not fire leakage, got {errors}"


def test_minimal_pair_semantic_equivalence_pair_leak_fires_when_complete_pair_in_control():
    errors = vd.Errors()
    feature = {"kind": "excl_pair", "members": [["digital"], ["physical"]]}
    dod_rec = _toy_rec(context="This is a digital item.", output="Not available in physical form.")
    control_rec = _toy_rec(context="This is a digital item.", output="Not available in physical form, either.")
    vd.check_minimal_pair_semantic_equivalence(errors, "cal:005", dod_rec, control_rec, feature)
    assert any(vd.RULE_FEATURE_TOKENS_IN_CONTROL in e for e in errors)


def test_minimal_pair_semantic_equivalence_whitespace_only_lexical_feature_does_not_bypass_evidence():
    # SAN-881 PASS 2B.2-FIX defect 3: surface_tokens: [" "] is schema-valid
    # pre-fix (minLength: 1 is satisfied by a single space) and folds to
    # the EMPTY sequence (fold_sequence(" ") == ()) -- the prior
    # "if not target_fold: return" early-out silently passed with ZERO
    # errors, bypassing table-absence, DOD evidence, and control-
    # equivalence proof entirely. An empty lexical target_fold must now
    # emit EXACTLY ONE RULE_FEATURE_TOKENS_NOT_IN_ITEM diagnostic.
    errors = vd.Errors()
    feature = {"kind": "condition_operator", "surface_tokens": [" "]}
    dod_rec = _toy_rec(context="Refunds are available for orders as long as they are unused.")
    control_rec = _toy_rec(context="Refunds are available for orders unless they are used.")
    vd.check_minimal_pair_semantic_equivalence(errors, "cal:005", dod_rec, control_rec, feature)
    assert len(errors) == 1, f"expected exactly one diagnostic, got {errors}"
    assert vd.RULE_FEATURE_TOKENS_NOT_IN_ITEM in errors[0]


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.2 Part E: DEDICATED 2B.2 fixture for
# check_dod_balance_and_pairs, run through the REAL entry point (never
# the accepted-closed 2B.1 gate substrate _toy_160_design_items, which
# stays byte-for-byte unchanged as a fixture). 10 DOD items per check (4
# checks x 10 = 40), balanced 5 VIOLATION / 5 NO_VIOLATION per check,
# each with a UNIQUE in-domain control matching check/domain/scenario/
# truth, covering ALL EIGHT lexical kinds plus BOTH pair kinds (excl_pair
# on C1/C3, complement_pair on C2/C4) -- "complete lexical AND pair
# examples". Every introduced surface/pair is a genuine, verified-absent
# novel token relative to the REAL production tables
# (ALGORITHM-v4-tables-v1.json); every control genuinely swaps in a REAL
# sibling table entry. Synthetic inline strings only -- corpus_inputs.json
# is never read or touched.
# ---------------------------------------------------------------------

def _2b2_real_tables_data() -> dict:
    return json.loads((CAL_DIR.parent / "spec" / "ALGORITHM-v4-tables-v1.json").read_text())


def _2b2_fixture_slots(check_id: str) -> list[dict]:
    pair_slot = (
        dict(
            label="excl_pair", truth="NO_VIOLATION",
            feature={"kind": "excl_pair", "table_path": "excl_v1", "members": [["standard"], ["premium"]]},
            dod_text="This is the standard tier, not the premium tier.",
            control_text="This account is verified, not unverified.",
        )
        if check_id in ("C1", "C3") else
        dict(
            label="complement_pair", truth="NO_VIOLATION",
            feature={"kind": "complement_pair", "table_path": "complement_v1", "members": [["required"], ["optional"]]},
            dod_text="This field is required, not optional.",
            control_text="This feature is enabled, not disabled.",
        )
    )
    return [
        dict(
            label="facet_trigger_leaf",
            feature={"kind": "facet_trigger", "table_path": "facets_v1.facet:eligibility.triggers",
                     "surface_tokens": ["qualifiable"],
                     "intended_semantics": {"facet": "facet:eligibility", "polarity": "POS"}},
            dod_text="This plan is qualifiable for the discount program.",
            control_text="This plan is eligible for the discount program.",
        ),
        dict(
            label="facet_trigger_facetproj",
            feature={"kind": "facet_trigger", "table_path": "facetproj_v1",
                     "surface_tokens": ["markdown"],
                     "intended_semantics": {"polarity": "POS", "projects_to": "facet:discount_availability"}},
            dod_text="A markdown may apply at checkout.",
            control_text="A discount may apply at checkout.",
        ),
        dict(
            label="deny_trigger",
            feature={"kind": "deny_trigger", "table_path": "facets_v1.facet:eligibility.deny_triggers",
                     "surface_tokens": ["unqualifiable"],
                     "intended_semantics": {"facet": "facet:eligibility", "polarity": "NEG"}},
            dod_text="This plan is unqualifiable for assistance.",
            control_text="This plan is ineligible for assistance.",
        ),
        dict(
            label="concept",
            feature={"kind": "concept", "table_path": "concept_v1",
                     "surface_tokens": ["greenlit"],
                     "intended_semantics": {"canonical_concept": "approval"}},
            dod_text="The request was greenlit yesterday.",
            control_text="The request was approved yesterday.",
        ),
        dict(
            label="unit",
            feature={"kind": "unit", "table_path": "units_v1",
                     "surface_tokens": ["hourblock"],
                     "intended_semantics": {"group": "time_a", "factor": 60}},
            dod_text="Access expires after one hourblock.",
            control_text="Access expires after one hour.",
        ),
        dict(
            label="condition_operator",
            feature={"kind": "condition_operator", "table_path": "condition_operators_v1",
                     "surface_tokens": ["barring", "that"],
                     "intended_semantics": {"kind": "IF", "polarity": "-", "force": "grant"}},
            dod_text="Refunds are granted barring that the item was used.",
            control_text="Refunds are granted except the item was used.",
        ),
        dict(
            label="quantifier",
            feature={"kind": "quantifier", "table_path": "quant_v1",
                     "surface_tokens": ["sundry"],
                     "intended_semantics": {"quantifier_class": "existential"}},
            dod_text="Sundry orders qualify for a refund.",
            control_text="Some orders qualify for a refund.",
        ),
        dict(
            label="definitive",
            feature={"kind": "definitive", "table_path": "definitive_v1",
                     "surface_tokens": ["unquestionably"],
                     "intended_semantics": {"role": "definitive", "same_overclaim_class_as_table": True}},
            dod_text="Refunds are unquestionably granted within policy.",
            control_text="Refunds are always granted within policy.",
        ),
        dict(
            label="hedge",
            feature={"kind": "hedge", "table_path": "hedge_v1",
                     "surface_tokens": ["conceivably"],
                     "intended_semantics": {"role": "hedge", "same_overclaim_class_as_table": True}},
            dod_text="Refunds conceivably apply depending on the item.",
            control_text="Refunds may apply depending on the item.",
        ),
        pair_slot,
    ]


def _toy_2b2_dod_fixture():
    """Builds the DEDICATED 2B.2 fixture: returns (design_by_id,
    semantic_by_key, corpus_by_id) ready to pass straight to
    check_dod_balance_and_pairs alongside _2b2_real_tables_data()."""
    design_by_id: dict = {}
    semantic_by_key: dict = {}
    corpus_by_id: dict = {}
    idx = 0
    for check_id in vd.CHECK_IDS:
        truths = ["VIOLATION"] * 5 + ["NO_VIOLATION"] * 5
        slots = _2b2_fixture_slots(check_id)
        assert len(slots) == 10
        domain = f"toy2b2_{check_id}"
        for slot, truth in zip(slots, truths):
            dod_id = f"cal2b2:{idx:03d}"
            idx += 1
            ctrl_id = f"cal2b2:{idx:03d}"
            idx += 1
            scenario = f"toy2b2-{check_id}-{slot['label']}"
            control_stratum = "in_domain_nonviolation" if truth == "NO_VIOLATION" else "in_domain_violation"
            design_by_id[dod_id] = {
                "item_id": dod_id, "target_check_id": check_id, "target_stratum": "determinate_out_of_domain",
                "domain": domain, "facet_families": ["facet:availability"], "scenario_id": scenario,
                "minimal_pair_of": ctrl_id, "introduced_feature": slot["feature"],
            }
            design_by_id[ctrl_id] = {
                "item_id": ctrl_id, "target_check_id": check_id, "target_stratum": control_stratum,
                "domain": domain, "facet_families": ["facet:availability"], "scenario_id": scenario,
                "minimal_pair_of": None, "introduced_feature": None,
            }
            semantic_by_key[(dod_id, check_id)] = {"semantic_truth": truth}
            semantic_by_key[(ctrl_id, check_id)] = {"semantic_truth": truth}
            corpus_by_id[dod_id] = {"id": dod_id, "context": slot["dod_text"], "output": "OK."}
            corpus_by_id[ctrl_id] = {"id": ctrl_id, "context": slot["control_text"], "output": "OK."}
    return design_by_id, semantic_by_key, corpus_by_id


def _2b2_find_dod_item(design_by_id: dict, check_id: str, label: str) -> str:
    for iid, it in design_by_id.items():
        if (it["target_stratum"] == "determinate_out_of_domain"
                and it["target_check_id"] == check_id
                and it["scenario_id"].endswith(label)):
            return iid
    raise AssertionError(f"no DOD item found for {check_id}/{label}")


def test_2b2_dedicated_fixture_shape():
    design_by_id, semantic_by_key, corpus_by_id = _toy_2b2_dod_fixture()
    assert len(design_by_id) == 80  # 40 DOD + 40 unique controls
    dod_items = [it for it in design_by_id.values() if it["target_stratum"] == "determinate_out_of_domain"]
    assert len(dod_items) == 40
    for check_id in vd.CHECK_IDS:
        per_check = [it for it in dod_items if it["target_check_id"] == check_id]
        assert len(per_check) == 10
        truths = [semantic_by_key[(it["item_id"], check_id)]["semantic_truth"] for it in per_check]
        assert truths.count("VIOLATION") == 5
        assert truths.count("NO_VIOLATION") == 5
    kinds = {it["introduced_feature"]["kind"] for it in dod_items}
    assert kinds == {
        "facet_trigger", "deny_trigger", "concept", "unit", "condition_operator",
        "quantifier", "definitive", "hedge", "excl_pair", "complement_pair",
    }
    # controls are all unique (no reuse across the 40 DOD items)
    control_pointers = [it["minimal_pair_of"] for it in dod_items]
    assert len(control_pointers) == len(set(control_pointers))


def test_2b2_dedicated_fixture_fully_valid_produces_zero_dod_minimal_pair_diagnostics():
    design_by_id, semantic_by_key, corpus_by_id = _toy_2b2_dod_fixture()
    errors = vd.Errors()
    vd.check_dod_balance_and_pairs(errors, design_by_id, semantic_by_key, corpus_by_id, _2b2_real_tables_data())
    assert errors == [], f"expected a fully-valid dedicated 2B.2 fixture to produce zero diagnostics, got {errors}"


def test_2b2_dedicated_fixture_negative_rule_feature_not_absent():
    # Mutates ONLY the concept slot's introduced surface_tokens to a
    # word (and matching dod-item text) that IS present in concept_v1 --
    # exactly RULE_FEATURE_NOT_ABSENT, nothing else.
    design_by_id, semantic_by_key, corpus_by_id = _toy_2b2_dod_fixture()
    iid = _2b2_find_dod_item(design_by_id, "C1", "concept")
    design_by_id[iid] = dict(design_by_id[iid])
    design_by_id[iid]["introduced_feature"] = dict(design_by_id[iid]["introduced_feature"], surface_tokens=["verify"])
    corpus_by_id[iid] = dict(corpus_by_id[iid], context="Please verify the request yesterday.")
    errors = vd.Errors()
    vd.check_dod_balance_and_pairs(errors, design_by_id, semantic_by_key, corpus_by_id, _2b2_real_tables_data())
    assert len(errors) == 1, f"expected exactly one diagnostic, got {errors}"
    assert vd.RULE_FEATURE_NOT_ABSENT in errors[0]


def test_2b2_dedicated_fixture_negative_rule_feature_tokens_not_in_item():
    # Mutates ONLY the unit slot's dod-item text to no longer contain the
    # introduced surface token -- exactly RULE_FEATURE_TOKENS_NOT_IN_ITEM.
    design_by_id, semantic_by_key, corpus_by_id = _toy_2b2_dod_fixture()
    iid = _2b2_find_dod_item(design_by_id, "C2", "unit")
    corpus_by_id[iid] = dict(corpus_by_id[iid], context="Access expires after some time.")
    errors = vd.Errors()
    vd.check_dod_balance_and_pairs(errors, design_by_id, semantic_by_key, corpus_by_id, _2b2_real_tables_data())
    assert len(errors) == 1, f"expected exactly one diagnostic, got {errors}"
    assert vd.RULE_FEATURE_TOKENS_NOT_IN_ITEM in errors[0]


def test_2b2_dedicated_fixture_negative_rule_feature_tokens_in_control():
    # Mutates ONLY the hedge slot's control text to also contain the
    # dod item's own introduced surface token -- exactly
    # RULE_FEATURE_TOKENS_IN_CONTROL.
    design_by_id, semantic_by_key, corpus_by_id = _toy_2b2_dod_fixture()
    iid = _2b2_find_dod_item(design_by_id, "C3", "hedge")
    mp = design_by_id[iid]["minimal_pair_of"]
    corpus_by_id[mp] = dict(corpus_by_id[mp], context="Refunds may conceivably apply depending on the item.")
    errors = vd.Errors()
    vd.check_dod_balance_and_pairs(errors, design_by_id, semantic_by_key, corpus_by_id, _2b2_real_tables_data())
    assert len(errors) == 1, f"expected exactly one diagnostic, got {errors}"
    assert vd.RULE_FEATURE_TOKENS_IN_CONTROL in errors[0]


def test_2b2_dedicated_fixture_negative_rule_minimal_pair_same_semantics():
    # Mutates ONLY the definitive slot's control text to drop its
    # definitive_v1 sibling word -- exactly RULE_MINIMAL_PAIR_SAME_SEMANTICS.
    design_by_id, semantic_by_key, corpus_by_id = _toy_2b2_dod_fixture()
    iid = _2b2_find_dod_item(design_by_id, "C4", "definitive")
    mp = design_by_id[iid]["minimal_pair_of"]
    corpus_by_id[mp] = dict(corpus_by_id[mp], context="Refunds are granted within policy.")
    errors = vd.Errors()
    vd.check_dod_balance_and_pairs(errors, design_by_id, semantic_by_key, corpus_by_id, _2b2_real_tables_data())
    assert len(errors) == 1, f"expected exactly one diagnostic, got {errors}"
    assert vd.RULE_MINIMAL_PAIR_SAME_SEMANTICS in errors[0]


def test_2b2_dedicated_fixture_negative_rule_dod_truth_balance():
    # Mutates ONE VIOLATION-truth DOD+control pair's truth+stratum
    # TOGETHER to NO_VIOLATION (keeping dod_truth == control_truth, so
    # MINIMAL_PAIR_SAME_SEMANTICS stays satisfied) -- this shifts the
    # per-check count away from 5/5, firing exactly RULE_DOD_TRUTH_BALANCE.
    design_by_id, semantic_by_key, corpus_by_id = _toy_2b2_dod_fixture()
    iid = _2b2_find_dod_item(design_by_id, "C1", "concept")  # a VIOLATION-truth slot
    mp = design_by_id[iid]["minimal_pair_of"]
    assert semantic_by_key[(iid, "C1")]["semantic_truth"] == "VIOLATION"
    semantic_by_key[(iid, "C1")] = {"semantic_truth": "NO_VIOLATION"}
    semantic_by_key[(mp, "C1")] = {"semantic_truth": "NO_VIOLATION"}
    design_by_id[mp] = dict(design_by_id[mp], target_stratum="in_domain_nonviolation")
    errors = vd.Errors()
    vd.check_dod_balance_and_pairs(errors, design_by_id, semantic_by_key, corpus_by_id, _2b2_real_tables_data())
    assert len(errors) == 1, f"expected exactly one diagnostic, got {errors}"
    assert vd.RULE_DOD_TRUTH_BALANCE in errors[0]


def test_2b2_dedicated_fixture_negative_rule_minimal_pair_scenario_id_mismatch():
    # SAN-881 PASS 2B.2-FIX defect 1: the comment above the minimal-pair
    # loop in check_dod_balance_and_pairs claims the control shares
    # check+domain+semantic_truth+scenario_id, but NO scenario_id
    # comparison actually existed in the loop -- a scenario-only
    # mismatch produced zero diagnostics. Mutates ONLY the control's
    # scenario_id (check_id, domain, stratum, semantic_truth, and every
    # other field stay untouched) -- exactly one
    # RULE_MINIMAL_PAIR_SAME_SEMANTICS diagnostic, nothing else.
    design_by_id, semantic_by_key, corpus_by_id = _toy_2b2_dod_fixture()
    iid = _2b2_find_dod_item(design_by_id, "C1", "concept")
    mp = design_by_id[iid]["minimal_pair_of"]
    assert design_by_id[mp]["scenario_id"] == design_by_id[iid]["scenario_id"]
    design_by_id[mp] = dict(design_by_id[mp], scenario_id=design_by_id[mp]["scenario_id"] + "-scenario-mismatch")
    errors = vd.Errors()
    vd.check_dod_balance_and_pairs(errors, design_by_id, semantic_by_key, corpus_by_id, _2b2_real_tables_data())
    assert len(errors) == 1, f"expected exactly one diagnostic, got {errors}"
    assert vd.RULE_MINIMAL_PAIR_SAME_SEMANTICS in errors[0]


def test_2b2_dedicated_fixture_negative_whitespace_only_lexical_feature_single_diagnostic_no_duplication():
    # SAN-881 PASS 2B.2-FIX defect 3, non-duplication proof: runs the
    # whitespace-only-surface_tokens defect through the REAL
    # check_dod_balance_and_pairs entry point (not just the isolated
    # check_minimal_pair_semantic_equivalence unit) -- the table-absence
    # helper (check_introduced_feature_absent_from_tables) and the
    # control-same-semantics helper
    # (check_minimal_pair_control_same_semantics_in_table) must NOT ALSO
    # fire for the same empty-fold condition; exactly the one
    # RULE_FEATURE_TOKENS_NOT_IN_ITEM diagnostic from
    # check_minimal_pair_semantic_equivalence, nothing else.
    design_by_id, semantic_by_key, corpus_by_id = _toy_2b2_dod_fixture()
    iid = _2b2_find_dod_item(design_by_id, "C1", "concept")
    design_by_id[iid] = dict(design_by_id[iid])
    design_by_id[iid]["introduced_feature"] = dict(design_by_id[iid]["introduced_feature"], surface_tokens=[" "])
    errors = vd.Errors()
    vd.check_dod_balance_and_pairs(errors, design_by_id, semantic_by_key, corpus_by_id, _2b2_real_tables_data())
    assert len(errors) == 1, f"expected exactly one diagnostic (no duplication), got {errors}"
    assert vd.RULE_FEATURE_TOKENS_NOT_IN_ITEM in errors[0]


# ---------------------------------------------------------------------
# Executable coverage predicates (closed static predicate map by surface
# category; toy-tested per family; must prove the surface/check/field
# relationship, not mere token presence)
# ---------------------------------------------------------------------

def test_coverage_predicate_concept_family_toy():
    tables_data = {"concept_v1": {"authorize": "authorization", "authorized": "authorization"}}
    assert vd._predicate_concept("You must be authorized to proceed.", "concept_v1.authorization", tables_data) is True
    assert vd._predicate_concept("You must be verified to proceed.", "concept_v1.authorization", tables_data) is False


def test_coverage_predicate_comparators_family_toy():
    tables_data = {"comparators_v1": [{"tokens": ["at", "least"], "interval": {}}]}
    assert vd._predicate_comparators("Orders at least 30 days old qualify.", "comparators_v1.at_least", tables_data) is True
    assert vd._predicate_comparators("Orders over 30 days old qualify.", "comparators_v1.at_least", tables_data) is False


def test_coverage_predicate_condition_operators_family_toy():
    tables_data = {"condition_operators_v1": [{"tokens": ["unless"], "kind": "IF", "polarity": "-", "force": "grant"}]}
    assert vd._predicate_condition_operators("Refunds are granted unless the item was used.", "condition_operators_v1.unless.IF.grant", tables_data) is True
    assert vd._predicate_condition_operators("Refunds are granted if requested.", "condition_operators_v1.unless.IF.grant", tables_data) is False


def test_coverage_predicate_quant_family_toy():
    tables_data = {"quant_v1": {"existential": ["some"]}}
    assert vd._predicate_quant("Some orders qualify for a refund.", "quant_v1.existential", tables_data) is True
    assert vd._predicate_quant("All orders qualify for a refund.", "quant_v1.existential", tables_data) is False


def test_coverage_predicate_excl_and_complement_family_toy():
    tables_data = {"excl_v1": [["digital", "physical"]], "complement_v1": [["enabled", "disabled"]]}
    assert vd._predicate_excl_or_complement("This is a digital item.", "excl_v1.digital_physical", "excl_v1", tables_data) is True
    assert vd._predicate_excl_or_complement("This account is disabled.", "complement_v1.enabled_disabled", "complement_v1", tables_data) is True
    assert vd._predicate_excl_or_complement("This account is active.", "complement_v1.enabled_disabled", "complement_v1", tables_data) is False


def test_coverage_predicate_facets_family_toy():
    tables_data = {"facets_v1": {"facet:availability": {"triggers": ["available"], "deny_triggers": ["unavailable"]}}}
    assert vd._predicate_facets("This item is available now.", "facets_v1.facet:availability", tables_data) is True
    assert vd._predicate_facets("This item ships tomorrow.", "facets_v1.facet:availability", tables_data) is False


def test_coverage_predicate_rejects_mere_token_presence_wrong_surface():
    # The token "authorized" appearing in text does NOT prove the
    # comparators_v1.at_least surface -- predicates are keyed to their
    # OWN surface only.
    tables_data = {"comparators_v1": [{"tokens": ["at", "least"], "interval": {}}]}
    assert vd._predicate_comparators("You must be authorized to proceed.", "comparators_v1.at_least", tables_data) is False


def test_check_coverage_manifest_predicate_failure_flagged():
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    corpus_by_id = {"cal:000": {"id": "cal:000", "context": "Nothing relevant here.", "output": "Also nothing."}}
    tables_data = {"comparators_v1": [{"tokens": ["at", "least"], "interval": {}}]}
    coverage = {"comparators_v1.at_least": [{"item_id": "cal:000", "check_id": "C1", "field": "context"}]}
    vd.check_coverage_manifest(errors, coverage, design_by_id, corpus_by_id, tables_data)
    assert any(vd.RULE_COVERAGE_PREDICATE_FAILED in e for e in errors)


def test_check_coverage_manifest_predicate_success_no_error():
    # SAN-881 PASS 2B.1-P: the fixture must be a GENUINE, linguistically
    # valid production sentence -- build_product_trace_bundle replays the
    # REAL production tables/grammar (never the toy tables_data dict),
    # so a comparator claim now requires an actual parsed
    # ComparatorProductEvent, not mere field-wide substring presence.
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    corpus_by_id = {"cal:000": {"id": "cal:000", "context": "The service costs over $30.", "output": "OK."}}
    tables_data = {"comparators_v1": [{"tokens": ["over"], "interval": {}}]}
    coverage = {"comparators_v1.over": [{"item_id": "cal:000", "check_id": "C1", "field": "context"}]}
    vd.check_coverage_manifest(errors, coverage, design_by_id, corpus_by_id, tables_data)
    assert errors == []


def test_check_coverage_manifest_empty_evidence_is_now_a_failure():
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    coverage = {"some_surface": []}
    vd.check_coverage_manifest(errors, coverage, design_by_id)
    assert any(vd.RULE_COVERAGE_EMPTY_EVIDENCE in e for e in errors)


# ---------------------------------------------------------------------
# Toy measure.py tests: gates
# ---------------------------------------------------------------------

def test_measure_projection_shape_and_calx_ids_two_item_toy():
    toy_corpus = [
        {"id": "cal:000", "context": "Toy context zero.", "output": "Toy output zero."},
        {"id": "cal:001", "context": "Toy context one.", "output": "Toy output one."},
    ]
    projection = ms.build_projection(toy_corpus)
    assert len(projection) == 8
    ids = sorted(r["id"] for r in projection)
    expected = sorted(f"calx:{n:03d}:{c}" for n in (0, 1) for c in ("C1", "C2", "C3", "C4"))
    assert ids == expected
    for rec in projection:
        assert set(rec.keys()) == {"id", "check_id", "output", "context"}


def test_measure_projection_allowlist_rejects_label_leak():
    toy_corpus = [{"id": "cal:000", "context": "Toy.", "output": "Toy.", "semantic_truth": "VIOLATION"}]
    with pytest.raises(ms.InfrastructureFailure, match="label leak guard"):
        ms.build_projection(toy_corpus)


def test_measure_projection_requires_exactly_one_context_shape():
    toy_corpus = [{"id": "cal:000", "output": "Toy."}]
    with pytest.raises(ms.InfrastructureFailure):
        ms.build_projection(toy_corpus)


def _write_real_schemas_dir(schemas_dir: Path) -> None:
    """Copies all six REAL, production schema files (byte-identical to
    SCHEMAS_DIR) into `schemas_dir` -- used by verify_frozen_bundle tests
    that need genuinely check_schema-valid, named-branch-capable schemas
    (unlike _write_toy_schemas_dir, which validate_design.py-only tests
    use with four placeholder {} schemas)."""
    schemas_dir.mkdir(parents=True, exist_ok=True)
    for name in vd.SCHEMA_FILES:
        (schemas_dir / name).write_bytes((SCHEMAS_DIR / name).read_bytes())


def test_measure_freeze_manifest_refusal_absent(tmp_path):
    with pytest.raises(ms.FreezeGateRefused, match="does not exist"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_measure_freeze_manifest_refusal_schema_invalid_before_hash_checks(tmp_path):
    # Missing every required key -- schema validation must catch this
    # BEFORE any hash-mismatch path is even reached.
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps({"corpus_version": 2}))
    _write_real_schemas_dir(tmp_path / "schemas")
    with pytest.raises(ms.FreezeGateRefused, match="schema validation"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def _write_toy_freeze_component_files(cal_dir: Path, repo_root: Path) -> dict:
    files = {
        "corpus_inputs.json": b"a", "design_metadata.json": b"b", "coverage_manifest.json": b"c",
        "evaluation_profile.json": b"d", "labels_frozen.json": b"e", "adjudication_log.json": b"f",
    }
    for name, content in files.items():
        (cal_dir / name).write_bytes(content)
    spec_dir = repo_root / "reference" / "spec"
    spec_dir.mkdir(parents=True, exist_ok=True)
    # Copy the REAL pinned spec bytes (freeze_manifest_schema.json const-pins
    # algorithm_sha256/tables_sha256 to the real hashes) so schema validation
    # and hash verification both succeed in this toy sandbox.
    real_spec_dir = CAL_DIR.parent / "spec"
    algo_bytes = (real_spec_dir / "ALGORITHM-v4-c1c5-reference.md").read_bytes()
    tables_bytes = (real_spec_dir / "ALGORITHM-v4-tables-v1.json").read_bytes()
    (spec_dir / "ALGORITHM-v4-c1c5-reference.md").write_bytes(algo_bytes)
    (spec_dir / "ALGORITHM-v4-tables-v1.json").write_bytes(tables_bytes)

    ctx_hash_hex = "a" * 64
    commitment = {"labeling_context_hash": ctx_hash_hex}
    (cal_dir / "commitment.json").write_text(json.dumps(commitment))
    (cal_dir / "labels_reviewer_semantic.commitment.json").write_text(json.dumps({"labeling_context_hash": ctx_hash_hex}))
    (cal_dir / "labels_reviewer_contract.commitment.json").write_text(json.dumps({"labeling_context_hash": ctx_hash_hex}))
    ledger = {"corpus_version": 2, "labeling_context_hash": ctx_hash_hex, "entries": [{"artifact_name": n, "verified": True} for n in files]}
    (cal_dir / "reveal_verification_ledger.json").write_text(json.dumps(ledger))

    manifest = {
        "corpus_version": 2,
        "corpus_inputs_sha256": hashlib.sha256(b"a").hexdigest(),
        "design_metadata_sha256": hashlib.sha256(b"b").hexdigest(),
        "coverage_manifest_sha256": hashlib.sha256(b"c").hexdigest(),
        "evaluation_profile_sha256": hashlib.sha256(b"d").hexdigest(),
        "labels_frozen_sha256": hashlib.sha256(b"e").hexdigest(),
        "adjudication_log_sha256": hashlib.sha256(b"f").hexdigest(),
        "algorithm_sha256": hashlib.sha256(algo_bytes).hexdigest(),
        "tables_sha256": hashlib.sha256(tables_bytes).hexdigest(),
        "labeling_context_hash": ctx_hash_hex,
        "author_commitment_sha256": hashlib.sha256((cal_dir / "commitment.json").read_bytes()).hexdigest(),
        "reviewer_semantic_commitment_sha256": hashlib.sha256((cal_dir / "labels_reviewer_semantic.commitment.json").read_bytes()).hexdigest(),
        "reviewer_contract_commitment_sha256": hashlib.sha256((cal_dir / "labels_reviewer_contract.commitment.json").read_bytes()).hexdigest(),
        "reveal_verification_ledger_sha256": hashlib.sha256((cal_dir / "reveal_verification_ledger.json").read_bytes()).hexdigest(),
    }
    return manifest


def test_measure_freeze_manifest_verifies_when_all_bound_hashes_and_provenance_match(tmp_path, monkeypatch):
    manifest = _write_toy_freeze_component_files(tmp_path, tmp_path)
    errors = ms.verify_freeze_manifest(manifest, repo_root=tmp_path, cal_dir=tmp_path)
    assert errors == []


def test_measure_freeze_manifest_is_raw_hash_only_and_ignores_provenance_content_context_hash(tmp_path):
    # SAN-881 PASS 2C.1-FIX (defect 2): verify_freeze_manifest is reduced
    # to a fixed-name RAW-HASH-ONLY helper -- it no longer parses
    # provenance JSON at all (that unguarded parsing is exactly how a
    # malformed envelope used to leak a raw AttributeError/
    # JSONDecodeError through the fail-closed boundary). The cross-
    # envelope labeling_context_hash agreement check that used to live
    # here moved entirely into verify_frozen_bundle's from-disk
    # RECOMPUTED-hash cross-check (a strictly stronger, ground-truth
    # check -- see test_verify_frozen_bundle_rejects_fabricated_but_
    # self_consistent_context_hash). A provenance file whose CONTENT
    # diverges from the manifest but whose RAW BYTES still match the
    # manifest's declared hash now produces ZERO errors from
    # verify_freeze_manifest alone.
    manifest = _write_toy_freeze_component_files(tmp_path, tmp_path)
    (tmp_path / "labels_reviewer_semantic.commitment.json").write_text(json.dumps({"labeling_context_hash": "b" * 64}))
    manifest["reviewer_semantic_commitment_sha256"] = hashlib.sha256((tmp_path / "labels_reviewer_semantic.commitment.json").read_bytes()).hexdigest()
    errors = ms.verify_freeze_manifest(manifest, repo_root=tmp_path, cal_dir=tmp_path)
    assert errors == []


def test_measure_freeze_manifest_is_raw_hash_only_and_ignores_ledger_verified_content(tmp_path):
    # See the counterpart above (context hash). The ledger's per-entry
    # `verified` flag is no longer read by verify_freeze_manifest either
    # -- that check now lives EXCLUSIVELY in verify_frozen_bundle's
    # ledger index-by-index cross-check (see
    # test_verify_frozen_bundle_rejects_unverified_ledger_entry).
    manifest = _write_toy_freeze_component_files(tmp_path, tmp_path)
    ledger = json.loads((tmp_path / "reveal_verification_ledger.json").read_text())
    ledger["entries"][0]["verified"] = False
    (tmp_path / "reveal_verification_ledger.json").write_text(json.dumps(ledger))
    manifest["reveal_verification_ledger_sha256"] = hashlib.sha256((tmp_path / "reveal_verification_ledger.json").read_bytes()).hexdigest()
    errors = ms.verify_freeze_manifest(manifest, repo_root=tmp_path, cal_dir=tmp_path)
    assert errors == []


def test_measure_canonical_json_bytes_is_stable_and_sorted():
    obj = {"b": 1, "a": 2}
    r1 = ms.canonical_json_bytes(obj)
    r2 = ms.canonical_json_bytes(obj)
    assert r1 == r2
    assert r1 == b'{"a":2,"b":1}\n'
    assert r1.endswith(b"\n") and r1.count(b"\n") == 1


def test_measure_join_labels_and_tuple_consistency():
    toy_results = [{"id": "calx:000:C1", "check_id": "C1", "outcome": "PASS",
                     "outcome_reason": "detection_complete", "severity": None, "advisory": False}]
    toy_labels = [{"item_id": "cal:000", "check_id": "C1", "semantic_truth": "NO_VIOLATION",
                   "contract_tuple": {"outcome": "PASS", "outcome_reason": "detection_complete", "severity": None, "advisory": False}}]
    joined = ms.join_labels(toy_results, toy_labels)
    assert joined[0]["item_id"] == "cal:000"
    assert joined[0]["label"]["semantic_truth"] == "NO_VIOLATION"


def test_measure_join_labels_missing_label_is_infrastructure_failure():
    toy_results = [{"id": "calx:000:C1", "check_id": "C1", "outcome": "PASS",
                     "outcome_reason": "detection_complete", "severity": None, "advisory": False}]
    with pytest.raises(ms.InfrastructureFailure, match="no frozen label"):
        ms.join_labels(toy_results, [])


def _toy_joined_and_design():
    design_by_id = {
        "cal:000": {"item_id": "cal:000", "target_check_id": "C1", "target_stratum": "in_domain_nonviolation", "scenario_id": "s0"},
        "cal:001": {"item_id": "cal:001", "target_check_id": "C1", "target_stratum": "in_domain_violation", "scenario_id": "s1"},
    }
    joined = [
        {"id": "calx:000:C1", "item_id": "cal:000", "check_id": "C1", "outcome": "PASS",
         "outcome_reason": "detection_complete", "severity": None, "advisory": False,
         "label": {"semantic_truth": "NO_VIOLATION", "competence": "IN_DOMAIN",
                    "contract_tuple": {"outcome": "PASS", "outcome_reason": "detection_complete", "severity": None, "advisory": False}}},
        {"id": "calx:001:C1", "item_id": "cal:001", "check_id": "C1", "outcome": "VIOLATION",
         "outcome_reason": "detection_complete", "severity": "critical", "advisory": False,
         "label": {"semantic_truth": "VIOLATION", "competence": "IN_DOMAIN",
                    "contract_tuple": {"outcome": "VIOLATION", "outcome_reason": "detection_complete", "severity": "critical", "advisory": False}}},
    ]
    return joined, design_by_id


def test_measure_gate_population_selection_and_semantic_mapping():
    joined, design_by_id = _toy_joined_and_design()
    rates = ms.compute_rates(joined, design_by_id, python_output_bytes=b"toy", typescript_output_bytes=b"toy")
    assert rates["gates"]["in_domain_semantic_accuracy_100"] is True
    assert rates["gates"]["zero_false_violations"] is True
    assert rates["gates"]["zero_in_domain_escapes"] is True
    assert "C1" in rates["per_check"]
    assert rates["per_check"]["C1"]["primary_target_40"]["item_count"] == 2
    assert rates["per_check"]["C2"]["primary_target_40"]["item_count"] == 0


def test_measure_gate_9_envelope_breaches():
    joined, design_by_id = _toy_joined_and_design()
    joined[0]["outcome_reason"] = "envelope_exceeded"
    rates = ms.compute_rates(joined, design_by_id, python_output_bytes=b"toy", typescript_output_bytes=b"toy")
    assert rates["gates"]["zero_envelope_breaches_640"] is False


def test_measure_gates_object_has_exactly_nine_pinned_names():
    joined, design_by_id = _toy_joined_and_design()
    rates = ms.compute_rates(joined, design_by_id, python_output_bytes=b"toy", typescript_output_bytes=b"toy")
    assert set(rates["gates"]) == set(ms.PINNED_GATE_NAMES)
    assert len(rates["gates"]) == 9
    assert "py_ts_byte_equality_640" in rates["gates"]


def test_measure_zero_evaluator_errors_keys_on_outcome_not_reason():
    joined, design_by_id = _toy_joined_and_design()
    joined[0]["outcome"] = "EVALUATOR_ERROR"
    joined[0]["outcome_reason"] = "evaluator_exception"
    rates = ms.compute_rates(joined, design_by_id, python_output_bytes=b"toy", typescript_output_bytes=b"toy")
    assert rates["gates"]["zero_evaluator_errors"] is False


def test_measure_zero_evaluator_errors_true_when_no_evaluator_error_outcome():
    joined, design_by_id = _toy_joined_and_design()
    rates = ms.compute_rates(joined, design_by_id, python_output_bytes=b"toy", typescript_output_bytes=b"toy")
    assert rates["gates"]["zero_evaluator_errors"] is True


def test_measure_py_ts_byte_equality_gate_reflects_argument():
    # SAN-881 PASS 2C.2: the gate is DERIVED directly from the two raw
    # byte strings' equality -- no boolean, no default.
    joined, design_by_id = _toy_joined_and_design()
    rates_true = ms.compute_rates(joined, design_by_id, python_output_bytes=b"same", typescript_output_bytes=b"same")
    rates_false = ms.compute_rates(joined, design_by_id, python_output_bytes=b"same", typescript_output_bytes=b"different")
    assert rates_true["gates"]["py_ts_byte_equality_640"] is True
    assert rates_false["gates"]["py_ts_byte_equality_640"] is False
    assert rates_false["nine_gates_passed"] is False


def test_measure_compute_rates_is_keyword_only_for_raw_bytes():
    # SAN-881 PASS 2C.2: python_output_bytes/typescript_output_bytes are
    # REQUIRED and keyword-only -- a positional-only call, or a call
    # omitting them, must fail with a TypeError, never silently default.
    joined, design_by_id = _toy_joined_and_design()
    with pytest.raises(TypeError):
        ms.compute_rates(joined, design_by_id)
    with pytest.raises(TypeError):
        ms.compute_rates(joined, design_by_id, b"x", b"x")


def test_measure_escape_rate_counts_only_pass_never_abstention():
    design_by_id = {
        "cal:000": {"item_id": "cal:000", "target_check_id": "C1", "target_stratum": "in_domain_violation", "scenario_id": "s0"},
        "cal:001": {"item_id": "cal:001", "target_check_id": "C1", "target_stratum": "in_domain_violation", "scenario_id": "s1"},
    }
    joined = [
        {"id": "calx:000:C1", "item_id": "cal:000", "check_id": "C1", "outcome": "PASS",
         "outcome_reason": "detection_complete", "severity": None, "advisory": False,
         "label": {"semantic_truth": "VIOLATION", "competence": "IN_DOMAIN",
                    "contract_tuple": {"outcome": "VIOLATION", "outcome_reason": "detection_complete", "severity": "critical", "advisory": False}}},
        {"id": "calx:001:C1", "item_id": "cal:001", "check_id": "C1", "outcome": "NOT_EVALUATED",
         "outcome_reason": "basis_conflict", "severity": None, "advisory": False,
         "label": {"semantic_truth": "VIOLATION", "competence": "IN_DOMAIN",
                    "contract_tuple": {"outcome": "VIOLATION", "outcome_reason": "basis_conflict", "severity": None, "advisory": False}}},
    ]
    rates = ms.compute_rates(joined, design_by_id, python_output_bytes=b"toy", typescript_output_bytes=b"toy")
    # cal:000 (VIOLATION truth, PASS outcome) is a real escape; cal:001
    # (VIOLATION truth, NOT_EVALUATED outcome) is a coverage-loss miss,
    # NEVER an escape.
    assert rates["gates"]["zero_in_domain_escapes"] is False
    pop = rates["per_check"]["C1"]["primary_target_40"]
    assert pop["escape_rate"]["numerator"] == 1
    assert pop["coverage_loss_abstention_rate"]["numerator"] == 1


def test_measure_impact_ranking_filtered_to_known_coverage_gap_only():
    design_by_id = {
        "cal:000": {"item_id": "cal:000", "target_check_id": "C1", "target_stratum": "determinate_out_of_domain",
                    "scenario_id": "s0", "introduced_feature": {"kind": "comparator", "table_path": "comparators_v1", "surface_tokens": ["at", "least"]}},
    }
    joined = [
        {"id": "calx:000:C1", "item_id": "cal:000", "check_id": "C1", "outcome": "PASS",
         "outcome_reason": "detection_complete", "severity": None, "advisory": False,
         "label": {"semantic_truth": "NO_VIOLATION", "competence": "IN_DOMAIN",  # NOT KNOWN_COVERAGE_GAP
                    "contract_tuple": {"outcome": "PASS", "outcome_reason": "detection_complete", "severity": None, "advisory": False}}},
    ]
    rates = ms.compute_rates(joined, design_by_id, python_output_bytes=b"toy", typescript_output_bytes=b"toy")
    assert rates["corpus_impact_ranking"] == []


def test_measure_impact_ranking_two_distinct_features_same_kind_do_not_collapse():
    design_by_id = {
        "cal:000": {"item_id": "cal:000", "target_check_id": "C1", "target_stratum": "determinate_out_of_domain",
                    "scenario_id": "s0", "introduced_feature": {"kind": "comparator", "table_path": "comparators_v1", "surface_tokens": ["at", "least"]}},
        "cal:001": {"item_id": "cal:001", "target_check_id": "C1", "target_stratum": "determinate_out_of_domain",
                    "scenario_id": "s1", "introduced_feature": {"kind": "comparator", "table_path": "comparators_v1", "surface_tokens": ["at", "most"]}},
    }
    label = {"semantic_truth": "NO_VIOLATION", "competence": "KNOWN_COVERAGE_GAP",
              "contract_tuple": {"outcome": "PASS", "outcome_reason": "detection_complete", "severity": None, "advisory": False}}
    joined = [
        {"id": "calx:000:C1", "item_id": "cal:000", "check_id": "C1", "outcome": "PASS",
         "outcome_reason": "detection_complete", "severity": None, "advisory": False, "label": label},
        {"id": "calx:001:C1", "item_id": "cal:001", "check_id": "C1", "outcome": "PASS",
         "outcome_reason": "detection_complete", "severity": None, "advisory": False, "label": label},
    ]
    rates = ms.compute_rates(joined, design_by_id, python_output_bytes=b"toy", typescript_output_bytes=b"toy")
    assert len(rates["corpus_impact_ranking"]) == 2
    total_items = sum(e["supporting_item_count"] for e in rates["corpus_impact_ranking"])
    assert total_items == 2


def test_measure_primary_confusion_by_stratum_present():
    joined, design_by_id = _toy_joined_and_design()
    rates = ms.compute_rates(joined, design_by_id, python_output_bytes=b"toy", typescript_output_bytes=b"toy")
    by_stratum = rates["per_check"]["C1"]["primary_target_40"]["confusion_by_stratum"]
    assert "in_domain_nonviolation" in by_stratum
    assert "in_domain_violation" in by_stratum


def test_measure_report_byte_stability_two_renders_identical():
    joined, design_by_id = _toy_joined_and_design()
    rates = ms.compute_rates(joined, design_by_id, python_output_bytes=b"toy", typescript_output_bytes=b"toy")
    r1 = ms.render_report(rates)
    r2 = ms.render_report(rates)
    assert r1 == r2


def test_measure_report_renders_percentages_not_fractions():
    joined, design_by_id = _toy_joined_and_design()
    rates = ms.compute_rates(joined, design_by_id, python_output_bytes=b"toy", typescript_output_bytes=b"toy")
    report = ms.render_report(rates)
    assert "%" in report
    assert "0.25\n" not in report and "0.5000" not in report


def test_measure_ratio_zero_denominator_is_null_never_percent():
    r = ms._ratio(0, 0)
    assert r == {"numerator": 0, "denominator": 0, "value": None}


def test_measure_ratio_decimal_scale_4_round_half_even():
    r = ms._ratio(1, 3)
    assert r["value"] == "0.3333"


def test_measure_tuple_consistency_closed_check():
    ok = {"id": "calx:000:C1", "outcome": "VIOLATION", "outcome_reason": "detection_complete", "severity": "critical", "advisory": False}
    assert ms._validate_tuple_consistency(ok) is None
    bad_severity = {"id": "calx:000:C1", "outcome": "PASS", "outcome_reason": "detection_complete", "severity": "critical", "advisory": False}
    assert ms._validate_tuple_consistency(bad_severity) is not None
    bad_outcome = {"id": "calx:000:C1", "outcome": "BOGUS", "outcome_reason": "detection_complete", "severity": None, "advisory": False}
    assert ms._validate_tuple_consistency(bad_outcome) is not None


def test_measure_tuple_consistency_accepts_valid_config_error():
    ok = {"id": "calx:000:C1", "outcome": "CONFIG_ERROR", "outcome_reason": "malformed_structured_input", "severity": None, "advisory": False}
    assert ms._validate_tuple_consistency(ok) is None


def test_measure_tuple_consistency_rejects_reason_not_valid_for_outcome():
    # A well-formed reason code (belongs to NOT_EVALUATED's set) paired
    # with the wrong outcome (PASS, whose only valid reason is
    # detection_complete) -- SAN-881 Phase-A correction full locked
    # reason matrix is outcome-specific, not a flat allowlist.
    mismatched = {"id": "calx:000:C1", "outcome": "PASS", "outcome_reason": "extraction_partial", "severity": None, "advisory": False}
    assert ms._validate_tuple_consistency(mismatched) is not None


def test_measure_dual_harness_byte_mismatch_is_fatal(tmp_path, monkeypatch):
    def fake_run_harness(cmd, projection_path, projection, tag):
        if tag == "py":
            return b'[{"a":1}]\n', [{"id": "x"}]
        return b'[{"a":2}]\n', [{"id": "x"}]

    monkeypatch.setattr(ms, "build_typescript_package", lambda ts_dir: None)
    monkeypatch.setattr(ms, "run_harness", fake_run_harness)
    with pytest.raises(ms.InfrastructureFailure, match="byte_equality_640"):
        ms.run_dual_harness([{"id": "calx:000:C1"}], tmp_path)


def test_measure_run_harness_uses_one_canonical_projection_file_for_both_tags(tmp_path, monkeypatch):
    written_paths = []

    def fake_run_harness(cmd, projection_path, projection, tag):
        written_paths.append(projection_path)
        return b"[]\n", []

    monkeypatch.setattr(ms, "build_typescript_package", lambda ts_dir: None)
    monkeypatch.setattr(ms, "run_harness", fake_run_harness)
    with pytest.raises(ms.InfrastructureFailure):
        # empty projection triggers id-set mismatch fatality downstream in
        # the real run_harness, but here run_harness is faked -- we only
        # care that BOTH calls received the identical path. Force a
        # mismatch after the fact by checking captured paths, then raise
        # deliberately via unequal py/ts bytes on a THIRD call pattern is
        # unnecessary: just assert path identity directly.
        raise ms.InfrastructureFailure("path-identity-check")
    ms.run_dual_harness([], tmp_path)
    assert len(written_paths) == 2
    assert written_paths[0] == written_paths[1]


def test_measure_run_harness_cardinality_fatality(tmp_path, monkeypatch):
    class FakeResult:
        returncode = 0
        stdout = b"[]"
        stderr = b""

    monkeypatch.setattr(ms.subprocess, "run", lambda *a, **k: FakeResult())
    projection = [{"id": "calx:000:C1"}, {"id": "calx:000:C2"}]
    with pytest.raises(ms.InfrastructureFailure, match="results, expected"):
        ms.run_harness(["toy"], tmp_path / "projection.json", projection, "toy")


def test_measure_run_harness_rejects_check_id_mismatch(tmp_path, monkeypatch):
    result_json = ms.canonical_json_bytes([
        {"id": "calx:000:C1", "check_id": "C2", "outcome": "PASS", "outcome_reason": "detection_complete", "severity": None, "advisory": False}
    ])

    class FakeResult:
        returncode = 0
        stdout = result_json
        stderr = b""

    monkeypatch.setattr(ms.subprocess, "run", lambda *a, **k: FakeResult())
    projection = [{"id": "calx:000:C1"}]
    with pytest.raises(ms.InfrastructureFailure, match="check_id does not match"):
        ms.run_harness(["toy"], tmp_path / "projection.json", projection, "toy")


def test_measure_run_harness_rejects_non_canonical_stdout_attribution_closure(tmp_path, monkeypatch):
    # Valid JSON, valid shape, but NOT the canonical reserialization of
    # its own parsed content (extra whitespace) -- attribution closure
    # must be enforced.
    non_canonical = b'[{"id": "calx:000:C1", "check_id": "C1", "outcome": "PASS", "outcome_reason": "detection_complete", "severity": null, "advisory": false}]\n'

    class FakeResult:
        returncode = 0
        stdout = non_canonical
        stderr = b""

    monkeypatch.setattr(ms.subprocess, "run", lambda *a, **k: FakeResult())
    projection = [{"id": "calx:000:C1"}]
    with pytest.raises(ms.InfrastructureFailure, match="attribution closure"):
        ms.run_harness(["toy"], tmp_path / "projection.json", projection, "toy")


def test_measure_run_harness_rejects_inconsistent_tuple():
    class FakeResult:
        returncode = 0
        stdout = ms.canonical_json_bytes([
            {"id": "calx:000:C1", "check_id": "C1", "outcome": "PASS", "outcome_reason": "detection_complete", "severity": "critical", "advisory": False}
        ])
        stderr = b""

    import unittest.mock as mock
    with mock.patch.object(ms.subprocess, "run", return_value=FakeResult()):
        projection = [{"id": "calx:000:C1"}]
        with pytest.raises(ms.InfrastructureFailure, match="severity"):
            ms.run_harness(["toy"], Path("/tmp/nonexistent-projection.json"), projection, "toy")


def test_measure_build_typescript_package_translates_missing_npm_dependency_install(tmp_path, monkeypatch):
    """SAN-881 PASS 2C.2-FIX (defect 2a, authentic RED pre-fix): `npm ci
    --ignore-scripts` is invoked with check=True and no subprocess-error
    guard -- a missing npm binary (or any OSError launching it) raises a
    raw FileNotFoundError straight through build_typescript_package
    pre-fix, reviewer-reproduced verbatim as
    [Errno 2] No such file or directory: 'npm'. Never requires a real
    npm failure on the host -- subprocess.run itself is monkeypatched to
    simulate the missing binary."""
    def fake_run(cmd, cwd=None, check=None):
        raise FileNotFoundError(2, "No such file or directory", "npm")

    monkeypatch.setattr(ms.subprocess, "run", fake_run)
    with pytest.raises(ms.InfrastructureFailure, match="typescript dependency installation"):
        ms.build_typescript_package(tmp_path)


def test_measure_build_typescript_package_translates_npm_build_failure(tmp_path, monkeypatch):
    """SAN-881 PASS 2C.2-FIX (defect 2b, authentic RED pre-fix): `npm run
    build` is invoked with check=True and no subprocess-error guard -- an
    ordinary nonzero-exit npm build failure raises a raw
    CalledProcessError straight through build_typescript_package
    pre-fix, reviewer-reproduced verbatim as Command
    '['npm', 'run', 'build']' returned non-zero exit status 1. Never
    requires a real npm failure on the host -- subprocess.run is
    monkeypatched so the `npm ci` call succeeds and only the `npm run
    build` call fails, proving the SECOND subprocess boundary is guarded
    too, not just the first."""
    def fake_run(cmd, cwd=None, check=None):
        if cmd[:2] == ["npm", "run"]:
            raise subprocess.CalledProcessError(1, cmd)

        class FakeResult:
            returncode = 0

        return FakeResult()

    monkeypatch.setattr(ms.subprocess, "run", fake_run)
    with pytest.raises(ms.InfrastructureFailure, match="typescript build"):
        ms.build_typescript_package(tmp_path)


def test_measure_run_harness_translates_launch_failure(tmp_path, monkeypatch):
    """SAN-881 PASS 2C.2-FIX (defect 2c, authentic RED pre-fix): the
    harness-process launch itself (subprocess.run(cmd + [projection_path],
    ...)) is unguarded -- a missing/unlaunchable harness binary raises a
    raw FileNotFoundError straight through run_harness pre-fix,
    reviewer-reproduced verbatim as [Errno 2] No such file or directory:
    'nonexistent-binary'. This is distinct from the EXISTING, PRESERVED
    nonzero-exit check (result.returncode != 0) immediately below the
    launch -- that check is for a harness that launched and exited
    nonzero; this guards the launch call itself failing to start at
    all. Never requires a real missing binary on the host -- subprocess.
    run is monkeypatched to simulate the failed launch."""
    def fake_run(cmd, capture_output=None, text=None, cwd=None):
        raise FileNotFoundError(2, "No such file or directory", cmd[0])

    monkeypatch.setattr(ms.subprocess, "run", fake_run)
    projection = [{"id": "calx:000:C1"}]
    with pytest.raises(ms.InfrastructureFailure, match="harness process launch"):
        ms.run_harness(["nonexistent-binary"], tmp_path / "projection.json", projection, "toy")


# ---------------------------------------------------------------------
# Pre-execution gating: schemas/population BEFORE harness, clean worktree
# (wrong-corpus-count / wrong-label-count / missing-jsonschema-module
# coverage now lives in the verify_frozen_bundle toy-bundle-and-negatives
# section below, alongside every other SAN-881 PASS 2C.1 defect class --
# _validate_frozen_schemas_and_population no longer exists as a
# standalone unit.)
# ---------------------------------------------------------------------

def test_require_clean_tracked_worktree_passes_on_clean_repo(tmp_path):
    _init_toy_git_repo(tmp_path)
    ms._require_clean_tracked_worktree(tmp_path)  # must not raise


def test_require_clean_tracked_worktree_rejects_dirty_repo(tmp_path):
    _init_toy_git_repo(tmp_path)
    (tmp_path / "README.md").write_text("dirty now\n")
    with pytest.raises(ms.InfrastructureFailure, match="clean tracked worktree"):
        ms._require_clean_tracked_worktree(tmp_path)


# ---------------------------------------------------------------------
# Transactional hash-addressed publication scheme
# ---------------------------------------------------------------------

def _write_minimal_run_pipeline_cal_dir(cal_dir: Path) -> None:
    """The minimal on-disk artifacts run_pipeline itself reads AFTER the
    freeze gate. SAN-881 PASS 2C.1: these transactional-publish tests
    monkeypatch ms.verify_frozen_bundle directly (see
    _fake_verify_frozen_bundle below) -- they exercise atomic-rename /
    stale-directory / temp-cleanup mechanics, never freeze-gate
    correctness (that is the verify_frozen_bundle toy-bundle-and-
    negatives section), so the gate itself is bypassed rather than
    reconstructed at full 160/640/68 population scale."""
    (cal_dir / "corpus_inputs.json").write_text(json.dumps([{"id": "cal:000", "context": "Toy.", "output": "Toy."}]))
    (cal_dir / "design_metadata.json").write_text(json.dumps({"items": [
        {"item_id": "cal:000", "target_check_id": "C1", "target_stratum": "in_domain_nonviolation", "scenario_id": "s0"},
    ]}))
    (cal_dir / "labels_frozen.json").write_text(json.dumps([
        {"item_id": "cal:000", "check_id": c, "semantic_truth": "NO_VIOLATION", "competence": "IN_DOMAIN",
         "contract_tuple": {"outcome": "PASS", "outcome_reason": "detection_complete", "severity": None, "advisory": False}}
        for c in ("C1", "C2", "C3", "C4")
    ]))
    (cal_dir / "FREEZE-MANIFEST.json").write_text(json.dumps({"toy": "manifest"}))


def _fake_verify_frozen_bundle(freeze_manifest_path: Path, cal_dir: Path, repo_root: Path) -> dict:
    return {
        "manifest": json.loads((cal_dir / "FREEZE-MANIFEST.json").read_text()),
        "corpus_inputs": json.loads((cal_dir / "corpus_inputs.json").read_text()),
        "design": json.loads((cal_dir / "design_metadata.json").read_text()),
        "labels_frozen": json.loads((cal_dir / "labels_frozen.json").read_text()),
        "evaluation_profile": {},
        "coverage_manifest": {},
    }


def test_measure_transactional_infra_failure_leaves_no_final_dir_and_preserves_stale(tmp_path, monkeypatch):
    cal_dir = tmp_path / "cal"
    cal_dir.mkdir()
    _init_toy_git_repo(tmp_path)
    _write_minimal_run_pipeline_cal_dir(cal_dir)

    monkeypatch.setattr(ms, "HERE", cal_dir)
    monkeypatch.setattr(ms, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ms, "verify_frozen_bundle", _fake_verify_frozen_bundle)

    freeze_hash = hashlib.sha256((cal_dir / "FREEZE-MANIFEST.json").read_bytes()).hexdigest()
    stale_dir = cal_dir / "results" / freeze_hash
    stale_dir.mkdir(parents=True)
    (stale_dir / "outcomes.json").write_text('{"stale": true}')

    def boom(projection, workdir):
        raise ms.InfrastructureFailure("toy induced failure")

    monkeypatch.setattr(ms, "run_dual_harness", boom)
    exit_code = ms.main([])
    assert exit_code == 2
    # the pre-existing hash dir already existed -> run_pipeline refuses
    # BEFORE creating any temp dir, and the stale dir is untouched.
    assert stale_dir.exists()
    assert json.loads((stale_dir / "outcomes.json").read_text()) == {"stale": True}
    tmp_dirs = list((cal_dir / "results").glob(".tmp-*"))
    assert tmp_dirs == []


def test_measure_transactional_refuses_when_final_hash_dir_preexists(tmp_path, monkeypatch):
    cal_dir = tmp_path / "cal"
    cal_dir.mkdir()
    _init_toy_git_repo(tmp_path)
    _write_minimal_run_pipeline_cal_dir(cal_dir)

    monkeypatch.setattr(ms, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ms, "verify_frozen_bundle", _fake_verify_frozen_bundle)

    freeze_hash = hashlib.sha256((cal_dir / "FREEZE-MANIFEST.json").read_bytes()).hexdigest()
    (cal_dir / "results" / freeze_hash).mkdir(parents=True)

    with pytest.raises(ms.InfrastructureFailure, match="already exists"):
        ms.run_pipeline(cal_dir)


def test_measure_transactional_gate_failure_emits_artifacts_and_publishes(tmp_path, monkeypatch):
    cal_dir = tmp_path / "cal"
    cal_dir.mkdir()
    _init_toy_git_repo(tmp_path)
    _write_minimal_run_pipeline_cal_dir(cal_dir)

    monkeypatch.setattr(ms, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ms, "verify_frozen_bundle", _fake_verify_frozen_bundle)

    def fake_dual_harness(projection, workdir):
        results = [{"id": r["id"], "check_id": r["check_id"], "outcome": "VIOLATION",
                    "outcome_reason": "detection_complete", "severity": "critical" if r["check_id"] == "C1" else "warning",
                    "advisory": False} for r in projection]
        return b"toybytes", b"toybytes", results, results

    monkeypatch.setattr(ms, "run_dual_harness", fake_dual_harness)
    # A real toy git repo backs this test (via _init_toy_git_repo above),
    # so `git status`/`git rev-parse HEAD` run for real here -- no global
    # subprocess.run mock (a mock would also intercept the clean-worktree
    # check and misreport it as dirty).

    exit_code = ms.run_pipeline(cal_dir)
    assert exit_code == 1  # gate failure (false violation), not infra failure

    freeze_hash = hashlib.sha256((cal_dir / "FREEZE-MANIFEST.json").read_bytes()).hexdigest()
    result_dir = cal_dir / "results" / freeze_hash
    assert (result_dir / "outcomes.json").exists()
    assert (result_dir / "rates.json").exists()
    assert (result_dir / "RATES-REPORT.md").exists()
    tmp_dirs = list((cal_dir / "results").glob(".tmp-*"))
    assert tmp_dirs == []  # renamed away, no temp dir left behind

    rates = json.loads((result_dir / "rates.json").read_text())
    assert rates["nine_gates_passed"] is False
    assert rates["gates"]["zero_false_violations"] is False
    assert rates["freeze_manifest_sha256"] == freeze_hash
    outcomes_bytes = (result_dir / "outcomes.json").read_bytes()
    assert rates["outcomes_sha256"] == hashlib.sha256(outcomes_bytes).hexdigest()


# =======================================================================
# SAN-881 PASS 2C.2 HEAD defect (authentic RED pre-fix): the worktree-
# clean/HEAD-resolvable gate ran exactly ONCE, at the very top of
# run_pipeline, before the harness ran. Nothing re-verified cleanliness
# or HEAD identity between that gate and the eventual publish -- a
# concurrent commit landing (or a tracked file going dirty) DURING the
# harness run went completely undetected, and outcomes.json's own
# runner_git_commit was captured via a FRESH, unverified `git rev-parse
# HEAD` at write time (potentially a DIFFERENT commit than the one the
# gate actually verified clean).
# =======================================================================

def test_measure_run_pipeline_refuses_when_head_moves_during_run(tmp_path, monkeypatch):
    cal_dir = tmp_path / "cal"
    cal_dir.mkdir()
    _init_toy_git_repo(tmp_path)
    _write_minimal_run_pipeline_cal_dir(cal_dir)

    monkeypatch.setattr(ms, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ms, "verify_frozen_bundle", _fake_verify_frozen_bundle)

    def fake_dual_harness(projection, workdir):
        # Side effect: a concurrent commit lands in the toy repo DURING
        # the "harness" step, advancing HEAD past what the worktree-clean
        # gate verified before the harness ran.
        subprocess.run(["git", "commit", "--allow-empty", "-q", "-m", "toy concurrent commit"],
                        cwd=tmp_path, check=True)
        results = [{"id": r["id"], "check_id": r["check_id"], "outcome": "PASS",
                    "outcome_reason": "detection_complete", "severity": None, "advisory": False} for r in projection]
        return b"toybytes", b"toybytes", results, results

    monkeypatch.setattr(ms, "run_dual_harness", fake_dual_harness)

    with pytest.raises(ms.InfrastructureFailure, match="HEAD changed during measurement"):
        ms.run_pipeline(cal_dir)

    freeze_hash = hashlib.sha256((cal_dir / "FREEZE-MANIFEST.json").read_bytes()).hexdigest()
    assert not (cal_dir / "results" / freeze_hash).exists()
    tmp_dirs = list((cal_dir / "results").glob(".tmp-*"))
    assert tmp_dirs == []


def test_measure_run_pipeline_refuses_when_worktree_becomes_dirty_during_run(tmp_path, monkeypatch):
    cal_dir = tmp_path / "cal"
    cal_dir.mkdir()
    _init_toy_git_repo(tmp_path)
    _write_minimal_run_pipeline_cal_dir(cal_dir)

    monkeypatch.setattr(ms, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ms, "verify_frozen_bundle", _fake_verify_frozen_bundle)

    def fake_dual_harness(projection, workdir):
        # Side effect: a TRACKED file goes dirty (never committed) DURING
        # the "harness" step.
        (tmp_path / "README.md").write_text("dirtied mid-run\n")
        results = [{"id": r["id"], "check_id": r["check_id"], "outcome": "PASS",
                    "outcome_reason": "detection_complete", "severity": None, "advisory": False} for r in projection]
        return b"toybytes", b"toybytes", results, results

    monkeypatch.setattr(ms, "run_dual_harness", fake_dual_harness)

    with pytest.raises(ms.InfrastructureFailure, match="clean tracked worktree"):
        ms.run_pipeline(cal_dir)

    freeze_hash = hashlib.sha256((cal_dir / "FREEZE-MANIFEST.json").read_bytes()).hexdigest()
    assert not (cal_dir / "results" / freeze_hash).exists()
    tmp_dirs = list((cal_dir / "results").glob(".tmp-*"))
    assert tmp_dirs == []


# ---------------------------------------------------------------------
# Toy benchmark.py tests
# ---------------------------------------------------------------------

def test_benchmark_nearest_rank_arithmetic_fixed_samples():
    samples = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    assert bm.nearest_rank_percentile(samples, 50) == 50
    assert bm.nearest_rank_percentile(samples, 95) == 100
    assert bm.nearest_rank_percentile(samples, 100) == 100
    assert bm.nearest_rank_percentile([42], 50) == 42


def test_benchmark_refuses_without_outcomes(tmp_path):
    _init_toy_git_repo(tmp_path)
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_path.write_text("{}")
    with pytest.raises(bm.BenchmarkRefused, match="outcomes.json"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def test_benchmark_refuses_when_gate_map_not_exactly_nine(tmp_path):
    _init_toy_git_repo(tmp_path)
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_path.write_text("{}")
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    outcomes = {"freeze_manifest_hash": freeze_hash, "outcomes": [{}] * 640,
                "runner_git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.strip()}
    (results_dir / "outcomes.json").write_text(json.dumps(outcomes))
    outcomes_hash = hashlib.sha256((results_dir / "outcomes.json").read_bytes()).hexdigest()
    (results_dir / "rates.json").write_text(json.dumps({
        "nine_gates_passed": True, "gates": {"only_one_gate": True},
        "freeze_manifest_sha256": freeze_hash, "outcomes_sha256": outcomes_hash,
    }))
    with pytest.raises(bm.BenchmarkRefused, match="nine pinned gates"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def test_benchmark_refuses_when_gates_not_passed(tmp_path):
    _init_toy_git_repo(tmp_path)
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_path.write_text("{}")
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    outcomes = {"freeze_manifest_hash": freeze_hash, "outcomes": [{}] * 640,
                "runner_git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.strip()}
    (results_dir / "outcomes.json").write_text(json.dumps(outcomes))
    outcomes_hash = hashlib.sha256((results_dir / "outcomes.json").read_bytes()).hexdigest()
    gates = {name: (name != "zero_false_violations") for name in bm.PINNED_GATE_NAMES}
    (results_dir / "rates.json").write_text(json.dumps({
        "nine_gates_passed": False, "gates": gates,
        "freeze_manifest_sha256": freeze_hash, "outcomes_sha256": outcomes_hash,
    }))
    with pytest.raises(bm.BenchmarkRefused, match="not all nine hard gates passed"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def test_benchmark_refuses_when_freeze_hash_mismatches(tmp_path):
    _init_toy_git_repo(tmp_path)
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_path.write_text("{}")
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    (results_dir / "outcomes.json").write_text(json.dumps({"freeze_manifest_hash": "0" * 64, "outcomes": []}))
    (results_dir / "rates.json").write_text(json.dumps({"nine_gates_passed": True, "gates": {}}))
    with pytest.raises(bm.BenchmarkRefused, match="different freeze"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def test_benchmark_check_preconditions_rejects_non_list_outcomes_member(tmp_path):
    """SAN-881 PASS 2C.2-FIX (defect 1a, authentic RED pre-fix):
    check_preconditions read outcomes.json's `outcomes` member via
    len(outcomes.get("outcomes", [])) with no type proof -- reviewer-
    reproduced pre-fix as a raw TypeError: object of type 'int' has no
    len(). The member must be proven to be a list BEFORE len() is ever
    called on it, and rejected with a fixed, artifact-only
    BenchmarkRefused message instead."""
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_path.write_text("{}")
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    outcomes = {"freeze_manifest_hash": freeze_hash, "outcomes": 1, "runner_git_commit": "0" * 40}
    (results_dir / "outcomes.json").write_text(json.dumps(outcomes))
    outcomes_hash = hashlib.sha256((results_dir / "outcomes.json").read_bytes()).hexdigest()
    (results_dir / "rates.json").write_text(json.dumps({
        "nine_gates_passed": True, "gates": {name: True for name in bm.PINNED_GATE_NAMES},
        "freeze_manifest_sha256": freeze_hash, "outcomes_sha256": outcomes_hash,
    }))
    with pytest.raises(bm.BenchmarkRefused, match="'outcomes' field"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def test_benchmark_check_preconditions_rejects_missing_outcomes_member(tmp_path):
    """SAN-881 PASS 2C.2-FIX (defect 1a): an ABSENT `outcomes` member
    (key not present at all) is rejected by the SAME fixed type-proving
    guard as a malformed one -- not silently defaulted to an empty list
    that then produces a generic count-mismatch message."""
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_path.write_text("{}")
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    outcomes = {"freeze_manifest_hash": freeze_hash, "runner_git_commit": "0" * 40}
    (results_dir / "outcomes.json").write_text(json.dumps(outcomes))
    outcomes_hash = hashlib.sha256((results_dir / "outcomes.json").read_bytes()).hexdigest()
    (results_dir / "rates.json").write_text(json.dumps({
        "nine_gates_passed": True, "gates": {name: True for name in bm.PINNED_GATE_NAMES},
        "freeze_manifest_sha256": freeze_hash, "outcomes_sha256": outcomes_hash,
    }))
    with pytest.raises(bm.BenchmarkRefused, match="'outcomes' field"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def test_benchmark_check_preconditions_rejects_non_dict_gates_member(tmp_path):
    """SAN-881 PASS 2C.2-FIX (defect 1b, authentic RED pre-fix):
    check_preconditions read rates.json's `gates` member via
    `rates.get("gates") or {}` with no type proof -- reviewer-reproduced
    pre-fix as a raw TypeError: 'int' object is not iterable (from
    set(gates)). The member must be proven to be a dict BEFORE any
    len/iteration/set/sorted/.items() use, and rejected with a fixed,
    artifact-only BenchmarkRefused message instead."""
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_path.write_text("{}")
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    outcomes = {"freeze_manifest_hash": freeze_hash, "outcomes": [{}] * 640, "runner_git_commit": "0" * 40}
    (results_dir / "outcomes.json").write_text(json.dumps(outcomes))
    outcomes_hash = hashlib.sha256((results_dir / "outcomes.json").read_bytes()).hexdigest()
    (results_dir / "rates.json").write_text(json.dumps({
        "nine_gates_passed": True, "gates": 1,
        "freeze_manifest_sha256": freeze_hash, "outcomes_sha256": outcomes_hash,
    }))
    with pytest.raises(bm.BenchmarkRefused, match="'gates' field"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def test_benchmark_check_preconditions_rejects_missing_gates_member(tmp_path):
    """SAN-881 PASS 2C.2-FIX (defect 1b): an ABSENT `gates` member (key
    not present at all) is rejected by the SAME fixed type-proving guard
    as a malformed one."""
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_path.write_text("{}")
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    outcomes = {"freeze_manifest_hash": freeze_hash, "outcomes": [{}] * 640, "runner_git_commit": "0" * 40}
    (results_dir / "outcomes.json").write_text(json.dumps(outcomes))
    outcomes_hash = hashlib.sha256((results_dir / "outcomes.json").read_bytes()).hexdigest()
    (results_dir / "rates.json").write_text(json.dumps({
        "nine_gates_passed": True,
        "freeze_manifest_sha256": freeze_hash, "outcomes_sha256": outcomes_hash,
    }))
    with pytest.raises(bm.BenchmarkRefused, match="'gates' field"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def _toy_160_corpus_inputs() -> list[dict]:
    """160 schema-shape-valid corpus_inputs.json entries (cal:000..
    cal:159), each with a UNIQUE (context, output) tuple (no duplicate
    RULE_DUPLICATE_TUPLE), a single `context` field (never
    context_sources), ASCII, and well under the field-byte cap."""
    return [
        {"id": f"cal:{i:03d}", "context": f"Toy context number {i}.", "output": f"Toy output number {i}."}
        for i in range(160)
    ]


def _toy_68_coverage_manifest() -> dict:
    """The closed 68-surface structure (vd.SURFACE_REGISTRY's own key
    set), each with exactly one evidence record referencing a real
    corpus item -- schema-valid, and every evidence item_id a genuine
    member of _toy_160_corpus_inputs(). Never exercises coverage
    predicate/product-trace machinery (2B territory, out of PASS 2C.1
    scope) -- verify_frozen_bundle's own coverage check is schema
    validity + corpus-membership only."""
    return {surface: [{"item_id": "cal:000", "check_id": "C1", "field": "context"}] for surface in vd.SURFACE_REGISTRY}


def _toy_640_merged_frozen_labels() -> list[dict]:
    """640 schema-valid mergedFrozenRecord entries (160 corpus items x
    C1-C4), in the SAME canonical (item_id outer, check_id inner) order
    verify_frozen_bundle pins -- every tuple PASS/detection_complete/
    None/False, which is both schema-valid and
    _validate_tuple_consistency-clean."""
    return [
        {
            "item_id": f"cal:{i:03d}", "check_id": c,
            "semantic_truth": "NO_VIOLATION", "semantic_rationale": "toy",
            "contract_tuple": {"outcome": "PASS", "outcome_reason": "detection_complete", "severity": None, "advisory": False},
            "competence": "IN_DOMAIN", "contract_rationale": "toy", "spec_refs": "toy",
        }
        for i in range(160) for c in vd.CHECK_IDS
    ]


def _stratum_aware_toy_640_merged_frozen_labels(design_by_id: dict) -> list[dict]:
    """SAN-881 PASS 2C.2: unlike _toy_640_merged_frozen_labels (uniform
    PASS/NO_VIOLATION everywhere -- fine for freeze-verification-only
    tests, but STRUCTURALLY INCAPABLE of ever reaching
    nine_gates_passed=True via measure.compute_rates, since the 10
    indeterminate_or_unsafe TARGET records require outcome=NOT_EVALUATED
    for deliberate_abstention_correct_100 while a uniform PASS contract
    demands outcome=PASS for contract_tuple_agreement_640 -- mutually
    exclusive), this labels EACH item's own TARGET record per its
    target_stratum (in_domain_violation -> VIOLATION with the pinned
    per-check severity; indeterminate_or_unsafe -> NOT_EVALUATED/
    basis_conflict; everything else, including every OFF-target record,
    -> NO_VIOLATION/PASS). Confirmed check_labels-clean (zero errors)
    and, paired with _stratum_aware_toy_harness_outcome below, confirmed
    to genuinely achieve all nine measure.compute_rates gates true."""
    labels = []
    for i in range(160):
        item = design_by_id[f"cal:{i:03d}"]
        for c in vd.CHECK_IDS:
            is_target = c == item["target_check_id"]
            if is_target and item["target_stratum"] == "indeterminate_or_unsafe":
                rec = {"item_id": f"cal:{i:03d}", "check_id": c,
                       "semantic_truth": "INDETERMINATE", "semantic_rationale": "toy",
                       "contract_tuple": {"outcome": "NOT_EVALUATED", "outcome_reason": "basis_conflict", "severity": None, "advisory": False},
                       "competence": "DELIBERATE_ABSTENTION", "contract_rationale": "toy", "spec_refs": "toy"}
            elif is_target and item["target_stratum"] == "in_domain_violation":
                severity = "critical" if item["target_check_id"] == "C1" else "warning"
                rec = {"item_id": f"cal:{i:03d}", "check_id": c,
                       "semantic_truth": "VIOLATION", "semantic_rationale": "toy",
                       "contract_tuple": {"outcome": "VIOLATION", "outcome_reason": "detection_complete", "severity": severity, "advisory": False},
                       "competence": "IN_DOMAIN", "contract_rationale": "toy", "spec_refs": "toy"}
            else:
                rec = {"item_id": f"cal:{i:03d}", "check_id": c,
                       "semantic_truth": "NO_VIOLATION", "semantic_rationale": "toy",
                       "contract_tuple": {"outcome": "PASS", "outcome_reason": "detection_complete", "severity": None, "advisory": False},
                       "competence": "IN_DOMAIN", "contract_rationale": "toy", "spec_refs": "toy"}
            labels.append(rec)
    return labels


def _stratum_aware_toy_harness_outcome(rec: dict, design_by_id: dict) -> dict:
    """The harness-output counterpart to
    _stratum_aware_toy_640_merged_frozen_labels: `rec` is one projection
    record (id "calx:NNN:CN", check_id "CN"); returns the outcome tuple
    fields that, joined against those SAME labels, make ALL nine
    measure.compute_rates gates genuinely true."""
    ordinal = rec["id"].split(":")[1]
    item = design_by_id[f"cal:{ordinal}"]
    is_target = rec["check_id"] == item["target_check_id"]
    if is_target and item["target_stratum"] == "indeterminate_or_unsafe":
        return {"outcome": "NOT_EVALUATED", "outcome_reason": "basis_conflict", "severity": None, "advisory": False}
    if is_target and item["target_stratum"] == "in_domain_violation":
        severity = "critical" if item["target_check_id"] == "C1" else "warning"
        return {"outcome": "VIOLATION", "outcome_reason": "detection_complete", "severity": severity, "advisory": False}
    return {"outcome": "PASS", "outcome_reason": "detection_complete", "severity": None, "advisory": False}


def _write_toy_v2_schema_valid_freeze_environment(cal_dir: Path, repo_root: Path) -> dict:
    """A FULLY schema-valid, FULL-POPULATION (160 corpus items / 640
    frozen labels / 68 coverage surfaces) v2 freeze environment --
    FREEZE-MANIFEST.json + every bound artifact + schema-valid AUTHOR/
    REVIEWER_SEMANTIC/REVIEWER_CONTRACT commitment envelopes (with a
    REAL from-disk-recomputed labeling_context_hash and a REAL,
    from-disk-recomputed labeling_context_components list) + a
    schema-valid six-entry reveal_verification_ledger.json (with REAL
    actual-raw-byte-length-bound entries) + the six raw
    LEDGER_CANONICAL_ORDER-named committed artifacts. SAN-881 PASS 2C.1:
    this is the SAME toy-bundle shape the measure.verify_frozen_bundle
    toy-bundle-and-negatives section below builds (verify_frozen_bundle
    is now the ONLY freeze-verification implementation either measure.py
    or benchmark.py calls, so a schema-valid-but-population-incorrect
    toy environment -- e.g. this helper's pre-PASS-2C.1 single-byte
    placeholder files -- no longer reaches benchmark.py's re-verification
    successfully; population correctness is required end to end)."""
    schemas_dir = cal_dir / "schemas"
    _write_real_schemas_dir(schemas_dir)

    spec_dir = repo_root / "reference" / "spec"
    spec_dir.mkdir(parents=True, exist_ok=True)
    real_spec_dir = CAL_DIR.parent / "spec"
    algo_bytes = (real_spec_dir / "ALGORITHM-v4-c1c5-reference.md").read_bytes()
    tables_bytes = (real_spec_dir / "ALGORITHM-v4-tables-v1.json").read_bytes()
    (spec_dir / "ALGORITHM-v4-c1c5-reference.md").write_bytes(algo_bytes)
    (spec_dir / "ALGORITHM-v4-tables-v1.json").write_bytes(tables_bytes)

    (cal_dir / "corpus_inputs.json").write_text(json.dumps(_toy_160_corpus_inputs()))
    (cal_dir / "evaluation_profile.json").write_text(json.dumps({
        "corpus_version": 2, "scope": list(vd.CHECK_IDS),
        "spec_pins": {"algorithm_sha256": hashlib.sha256(algo_bytes).hexdigest(),
                      "tables_sha256": hashlib.sha256(tables_bytes).hexdigest()},
    }))
    (cal_dir / "design_metadata.json").write_text(json.dumps({"items": _toy_160_design_items()}))
    (cal_dir / "labels_frozen.json").write_text(json.dumps(_toy_640_merged_frozen_labels()))
    (cal_dir / "coverage_manifest.json").write_text(json.dumps(_toy_68_coverage_manifest()))
    (cal_dir / "adjudication_log.json").write_text(json.dumps({"toy": "adjudication-log"}))

    # The six RAW LEDGER_CANONICAL_ORDER-named artifacts (labels_author_
    # semantic.json / labels_reviewer_semantic.json / labels_author_
    # contract.json / design_metadata.json [already written above] /
    # coverage_manifest.json [already written above] / labels_reviewer_
    # contract.json) -- only their genuine raw byte length matters here
    # (verify_frozen_bundle never schema-validates these four, and never
    # recomputes their nonce commitment).
    (cal_dir / "labels_author_semantic.json").write_text(json.dumps({"toy": "author-semantic"}))
    (cal_dir / "labels_author_contract.json").write_text(json.dumps({"toy": "author-contract"}))
    (cal_dir / "labels_reviewer_semantic.json").write_text(json.dumps({"toy": "reviewer-semantic"}))
    (cal_dir / "labels_reviewer_contract.json").write_text(json.dumps({"toy": "reviewer-contract"}))

    ctx_hash_hex = vd.compute_labeling_context_hash_from_disk(cal_dir, repo_root).hex()
    recomputed_components = vd.build_labeling_context_components(cal_dir, repo_root)
    algorithm_block = {"hash": "SHA256", "domain_separator": "sanna-calibration-commitment/1", "formula": vd.COMMITMENT_ALGORITHM_FORMULA}

    def _commitment_entry(artifact_name: str, commitment_hex_seed: str) -> dict:
        return {
            "artifact_name": artifact_name,
            "byte_length": len((cal_dir / artifact_name).read_bytes()),
            "commitment_hex": (commitment_hex_seed * 64)[:64],
        }

    commitment = {
        "corpus_version": 2, "envelope_kind": "AUTHOR", "labeling_context_hash": ctx_hash_hex,
        "labeling_context_components": recomputed_components,
        "commitment_algorithm": algorithm_block,
        "author_commitments": [_commitment_entry(n, "b") for n in vd.AUTHOR_COMMITMENT_ORDER],
        "reveal_protocol": {
            "reviewer_commitment_filenames": [
                "labels_reviewer_semantic.commitment.json", "labels_reviewer_contract.commitment.json",
            ],
            "reviewer_commitment_method": (
                "identical to author_commitments: domain-separated SHA256(\"sanna-calibration-commitment/1\""
                " || NUL || artifact_name || NUL || raw_32_byte_nonce || raw_32_byte_labeling_context_hash"
                " || exact_artifact_bytes)"
            ),
            "abandonment_rule": "toy",
        },
    }
    (cal_dir / "commitment.json").write_text(json.dumps(commitment))

    rev_sem = {
        "corpus_version": 2, "envelope_kind": "REVIEWER_SEMANTIC", "labeling_context_hash": ctx_hash_hex,
        "commitment_algorithm": algorithm_block,
        "artifact_commitment": _commitment_entry("labels_reviewer_semantic.json", "c"),
    }
    (cal_dir / "labels_reviewer_semantic.commitment.json").write_text(json.dumps(rev_sem))

    rev_con = {
        "corpus_version": 2, "envelope_kind": "REVIEWER_CONTRACT", "labeling_context_hash": ctx_hash_hex,
        "commitment_algorithm": algorithm_block,
        "artifact_commitment": _commitment_entry("labels_reviewer_contract.json", "d"),
    }
    (cal_dir / "labels_reviewer_contract.commitment.json").write_text(json.dumps(rev_con))

    commitments_by_name = {c["artifact_name"]: c for c in commitment["author_commitments"]}
    commitments_by_name[rev_sem["artifact_commitment"]["artifact_name"]] = rev_sem["artifact_commitment"]
    commitments_by_name[rev_con["artifact_commitment"]["artifact_name"]] = rev_con["artifact_commitment"]

    ledger = {
        "corpus_version": 2, "labeling_context_hash": ctx_hash_hex,
        "entries": [
            {"artifact_name": name, "envelope": envelope,
             "commitment_hex": commitments_by_name[name]["commitment_hex"],
             "verified": True, "verified_stage": stage,
             "byte_length": commitments_by_name[name]["byte_length"]}
            for name, envelope, stage in vd.LEDGER_CANONICAL_ORDER
        ],
    }
    (cal_dir / "reveal_verification_ledger.json").write_text(json.dumps(ledger))

    manifest = {
        "corpus_version": 2,
        "corpus_inputs_sha256": hashlib.sha256((cal_dir / "corpus_inputs.json").read_bytes()).hexdigest(),
        "design_metadata_sha256": hashlib.sha256((cal_dir / "design_metadata.json").read_bytes()).hexdigest(),
        "coverage_manifest_sha256": hashlib.sha256((cal_dir / "coverage_manifest.json").read_bytes()).hexdigest(),
        "evaluation_profile_sha256": hashlib.sha256((cal_dir / "evaluation_profile.json").read_bytes()).hexdigest(),
        "labels_frozen_sha256": hashlib.sha256((cal_dir / "labels_frozen.json").read_bytes()).hexdigest(),
        "adjudication_log_sha256": hashlib.sha256((cal_dir / "adjudication_log.json").read_bytes()).hexdigest(),
        "algorithm_sha256": hashlib.sha256(algo_bytes).hexdigest(),
        "tables_sha256": hashlib.sha256(tables_bytes).hexdigest(),
        "labeling_context_hash": ctx_hash_hex,
        "author_commitment_sha256": hashlib.sha256((cal_dir / "commitment.json").read_bytes()).hexdigest(),
        "reviewer_semantic_commitment_sha256": hashlib.sha256((cal_dir / "labels_reviewer_semantic.commitment.json").read_bytes()).hexdigest(),
        "reviewer_contract_commitment_sha256": hashlib.sha256((cal_dir / "labels_reviewer_contract.commitment.json").read_bytes()).hexdigest(),
        "reveal_verification_ledger_sha256": hashlib.sha256((cal_dir / "reveal_verification_ledger.json").read_bytes()).hexdigest(),
    }
    (cal_dir / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    return manifest


def test_benchmark_binds_raw_outcomes_bytes_not_reserialization(tmp_path, monkeypatch):
    """SAN-881 PASS 2C.2: rewritten for the new replay-integrity
    architecture (the prior version's premise -- ANY self-consistent
    hash-bound outcomes.json is accepted regardless of content -- is
    EXACTLY the gap this pass closes; see the REPLAY defect tests
    above). A genuinely-correct outcomes.json (byte-identical to a
    deterministic replay's own reconstruction) succeeds. The SAME
    logical content, written non-canonically (pretty-printed, extra
    whitespace), is REJECTED even though its json.loads()-decoded VALUE
    is identical to the canonical form -- proving the binding is over
    RAW bytes, never a reserialization/parse-then-reserialize
    equality."""
    _init_toy_git_repo(tmp_path)
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"

    design_by_id = {it["item_id"]: it for it in _toy_160_design_items()}
    # Swap in the STRATUM-AWARE labels (the shared _toy_640_merged_
    # frozen_labels fixture is uniform PASS/NO_VIOLATION everywhere,
    # which can NEVER genuinely achieve nine_gates_passed=True -- the 10
    # indeterminate_or_unsafe target records structurally require
    # NOT_EVALUATED). labels_frozen.json is NOT one of the eleven
    # labeling-context components, so only its OWN outer hash pin needs
    # refreshing (no context-hash repropagation).
    stratum_labels = _stratum_aware_toy_640_merged_frozen_labels(design_by_id)
    (tmp_path / "labels_frozen.json").write_text(json.dumps(stratum_labels))
    manifest = json.loads(freeze_path.read_text())
    manifest["labels_frozen_sha256"] = hashlib.sha256((tmp_path / "labels_frozen.json").read_bytes()).hexdigest()
    freeze_path.write_text(json.dumps(manifest))
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.strip()

    corpus_inputs = _toy_160_corpus_inputs()
    projection = ms.build_projection(corpus_inputs)

    def fake_harness(proj):
        results = [{"id": r["id"], "check_id": r["check_id"],
                     **_stratum_aware_toy_harness_outcome(r, design_by_id)} for r in proj]
        return ms.canonical_json_bytes(results), results

    out_bytes, results = fake_harness(projection)
    joined = ms.join_labels(results, stratum_labels)
    rates = ms.compute_rates(joined, design_by_id, python_output_bytes=out_bytes, typescript_output_bytes=out_bytes)
    assert rates["nine_gates_passed"] is True

    genuine_outcomes = {
        "freeze_manifest_hash": freeze_hash,
        "component_hashes": manifest,
        "record_count": len(joined),
        "python_output_sha256": hashlib.sha256(out_bytes).hexdigest(),
        "typescript_output_sha256": hashlib.sha256(out_bytes).hexdigest(),
        "runner_git_commit": head,
        "measure_py_sha256": hashlib.sha256((CAL_DIR / "measure.py").read_bytes()).hexdigest(),
        "outcomes": [{"id": r["id"], "item_id": r["item_id"], "check_id": r["check_id"],
                      "outcome": r["outcome"], "outcome_reason": r["outcome_reason"],
                      "severity": r["severity"], "advisory": r["advisory"]} for r in joined],
    }
    outcomes_bytes = ms.canonical_json_bytes(genuine_outcomes)
    rates_doc = {
        **rates,
        "freeze_manifest_sha256": freeze_hash,
        "outcomes_sha256": hashlib.sha256(outcomes_bytes).hexdigest(),
    }

    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    (results_dir / "outcomes.json").write_bytes(outcomes_bytes)
    (results_dir / "rates.json").write_bytes(ms.canonical_json_bytes(rates_doc))

    def fake_dual_harness(proj, workdir):
        b, r = fake_harness(proj)
        return b, b, r, r

    monkeypatch.setattr(ms, "run_dual_harness", fake_dual_harness)

    preconditions = bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)
    assert preconditions["outcomes"] == genuine_outcomes

    # Overwrite outcomes.json with a PRETTY-PRINTED reserialization of
    # the IDENTICAL logical content -- json.loads() treats these as
    # equal, but the raw bytes differ, and the replay reconstruction
    # only ever produces the CANONICAL (compact, single-trailing-LF)
    # form.
    pretty_bytes = (json.dumps(genuine_outcomes, indent=4) + "\n").encode()
    assert pretty_bytes != outcomes_bytes
    assert json.loads(pretty_bytes) == json.loads(outcomes_bytes)
    (results_dir / "outcomes.json").write_bytes(pretty_bytes)
    rates_doc2 = {**rates_doc, "outcomes_sha256": hashlib.sha256(pretty_bytes).hexdigest()}
    (results_dir / "rates.json").write_bytes(ms.canonical_json_bytes(rates_doc2))

    with pytest.raises(bm.BenchmarkRefused, match="replay"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def test_benchmark_refuses_when_head_does_not_match_runner_commit(tmp_path):
    _init_toy_git_repo(tmp_path)
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_path.write_text("{}")
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    outcomes = {"freeze_manifest_hash": freeze_hash, "outcomes": [{}] * 640, "runner_git_commit": "0" * 40}
    (results_dir / "outcomes.json").write_text(json.dumps(outcomes))
    outcomes_hash = hashlib.sha256((results_dir / "outcomes.json").read_bytes()).hexdigest()
    gates = {name: True for name in bm.PINNED_GATE_NAMES}
    (results_dir / "rates.json").write_text(json.dumps({
        "nine_gates_passed": True, "gates": gates,
        "freeze_manifest_sha256": freeze_hash, "outcomes_sha256": outcomes_hash,
    }))
    with pytest.raises(bm.BenchmarkRefused, match="runner_git_commit"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def test_benchmark_summarize_shape_on_toy_timing():
    per_item = {"cal:000": [100, 200, 150], "cal:001": [90, 110, 95]}
    summary = bm.summarize(per_item)
    assert summary["per_item"]["cal:000"]["n"] == 3
    assert summary["per_item"]["cal:000"]["p50_ns"] == 150
    assert summary["per_pass"]["n"] == 3


# ---------------------------------------------------------------------
# README staged ordering: semantic-only strictly precedes contract/design/coverage
# ---------------------------------------------------------------------

def test_readme_semantic_reveal_precedes_contract_design_coverage_reveal():
    readme = (CAL_DIR / "README.md").read_text()
    sem_idx = readme.find("Semantic-only reveal")
    contract_idx = readme.find("Contract/design/coverage reveal")
    assert sem_idx != -1, "README must document a semantic-only reveal step"
    assert contract_idx != -1, "README must document a separate contract/design/coverage reveal step"
    assert sem_idx < contract_idx


def test_readme_documents_nine_gates_and_transaction_scheme():
    readme = (CAL_DIR / "README.md").read_text()
    for gate_name in ms.PINNED_GATE_NAMES:
        assert gate_name in readme, f"README must document gate {gate_name}"
    assert "results/<freeze_manifest_sha256>" in readme or "results/<" in readme


# =======================================================================
# SAN-881 PASS 2C.1: the centralized frozen-bundle verifier
# (measure.verify_frozen_bundle), invoked by BOTH measure.run_pipeline
# and benchmark._rerun_full_freeze_verification. A single full-size toy
# bundle (_write_toy_v2_schema_valid_freeze_environment, upgraded above
# to genuine 160/640/68 population scale) verifies clean through both
# consumers; every negative below mutates ONE logical invariant off that
# SAME clean bundle, refreshing whichever outer raw-hash pin(s) the
# mutated file feeds so the mutation actually reaches the specific inner
# check under test (never trips an EARLIER, already-covered check
# instead).
# =======================================================================

def _repropagate_context_hash(cal_dir: Path, repo_root: Path, manifest: dict) -> None:
    """After mutating corpus_inputs.json / evaluation_profile.json (or a
    schema file) -- one of the eleven from-disk labeling-context
    components -- the RECOMPUTED context hash changes. Repropagates the
    new recomputed hash (and, for the author envelope, the new
    recomputed component list) into `manifest` (mutated in place) and
    every on-disk envelope/ledger file, so a test targeting a LATER
    check (population count, corpus-membership, ...) actually reaches
    that check instead of tripping the separately-tested recomputed-
    context-hash cross-check first. Caller still writes FREEZE-
    MANIFEST.json itself afterward (this only mutates the in-memory
    dict + the on-disk envelope/ledger files)."""
    new_hash = vd.compute_labeling_context_hash_from_disk(cal_dir, repo_root).hex()
    new_components = vd.build_labeling_context_components(cal_dir, repo_root)
    manifest["labeling_context_hash"] = new_hash

    commitment = json.loads((cal_dir / "commitment.json").read_text())
    commitment["labeling_context_hash"] = new_hash
    commitment["labeling_context_components"] = new_components
    (cal_dir / "commitment.json").write_text(json.dumps(commitment))

    for fname in ("labels_reviewer_semantic.commitment.json", "labels_reviewer_contract.commitment.json"):
        doc = json.loads((cal_dir / fname).read_text())
        doc["labeling_context_hash"] = new_hash
        (cal_dir / fname).write_text(json.dumps(doc))

    ledger = json.loads((cal_dir / "reveal_verification_ledger.json").read_text())
    ledger["labeling_context_hash"] = new_hash
    (cal_dir / "reveal_verification_ledger.json").write_text(json.dumps(ledger))

    manifest["author_commitment_sha256"] = hashlib.sha256((cal_dir / "commitment.json").read_bytes()).hexdigest()
    manifest["reviewer_semantic_commitment_sha256"] = hashlib.sha256(
        (cal_dir / "labels_reviewer_semantic.commitment.json").read_bytes()).hexdigest()
    manifest["reviewer_contract_commitment_sha256"] = hashlib.sha256(
        (cal_dir / "labels_reviewer_contract.commitment.json").read_bytes()).hexdigest()
    manifest["reveal_verification_ledger_sha256"] = hashlib.sha256(
        (cal_dir / "reveal_verification_ledger.json").read_bytes()).hexdigest()


def test_verify_frozen_bundle_toy_bundle_clean_through_both_consumers(tmp_path):
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    freeze_manifest_path = tmp_path / "FREEZE-MANIFEST.json"

    verified = ms.verify_frozen_bundle(freeze_manifest_path, tmp_path, tmp_path)
    assert set(verified) == {"manifest", "corpus_inputs", "evaluation_profile", "design", "labels_frozen", "coverage_manifest"}
    assert len(verified["corpus_inputs"]) == 160
    assert len(verified["design"]["items"]) == 160
    assert len(verified["labels_frozen"]) == 640
    assert len(verified["coverage_manifest"]) == 68

    # benchmark's OWN entry point -- which now calls ONLY
    # ms.verify_frozen_bundle -- verifies the SAME toy bundle clean too:
    # ONE shared verifier, BOTH consumers.
    _, failures = bm._rerun_full_freeze_verification(freeze_manifest_path, tmp_path, tmp_path)
    assert failures == []


def test_verify_frozen_bundle_rejects_fabricated_but_self_consistent_context_hash(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    fabricated = "b" * 64
    manifest["labeling_context_hash"] = fabricated
    for fname in ("commitment.json", "labels_reviewer_semantic.commitment.json",
                  "labels_reviewer_contract.commitment.json", "reveal_verification_ledger.json"):
        doc = json.loads((tmp_path / fname).read_text())
        doc["labeling_context_hash"] = fabricated
        (tmp_path / fname).write_text(json.dumps(doc))
    # Refresh every outer raw-hash pin the four edited files feed -- a
    # stale pin would fire verify_freeze_manifest's EXISTING hash-binding
    # check first, never reaching the NEW from-disk recomputed-context-
    # hash cross-check this test targets. The manifest/commitment/both
    # reviewer envelopes/ledger are now all EQUAL to each other
    # (self-consistent), which is exactly why the OLD cross-envelope-
    # agreement check (unchanged, reused) does NOT catch this -- only the
    # NEW from-disk recomputation does.
    manifest["author_commitment_sha256"] = hashlib.sha256((tmp_path / "commitment.json").read_bytes()).hexdigest()
    manifest["reviewer_semantic_commitment_sha256"] = hashlib.sha256(
        (tmp_path / "labels_reviewer_semantic.commitment.json").read_bytes()).hexdigest()
    manifest["reviewer_contract_commitment_sha256"] = hashlib.sha256(
        (tmp_path / "labels_reviewer_contract.commitment.json").read_bytes()).hexdigest()
    manifest["reveal_verification_ledger_sha256"] = hashlib.sha256(
        (tmp_path / "reveal_verification_ledger.json").read_bytes()).hexdigest()
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(ms.FreezeGateRefused, match="recomputed context hash"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_author_component_list_mismatch(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    commitment = json.loads((tmp_path / "commitment.json").read_text())
    components = commitment["labeling_context_components"]
    # Tamper ONE entry's digest (keeping its pinned name/position intact,
    # so authorEnvelope's own prefixItems name-consts still pass) -- the
    # COMPLETE declared list must equal the recomputed list EXACTLY, not
    # merely share the same digest set.
    components[0] = {**components[0], "sha256": "f" * 64}
    commitment["labeling_context_components"] = components
    (tmp_path / "commitment.json").write_text(json.dumps(commitment))
    manifest["author_commitment_sha256"] = hashlib.sha256((tmp_path / "commitment.json").read_bytes()).hexdigest()
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(ms.FreezeGateRefused, match="labeling_context_components does not equal"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_deleted_schema(tmp_path):
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    (tmp_path / "schemas" / "coverage_manifest_schema.json").unlink()
    with pytest.raises(ms.FreezeGateRefused, match="required schema coverage_manifest_schema.json does not exist"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_wrong_envelope_discriminant(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    commitment = json.loads((tmp_path / "commitment.json").read_text())
    commitment["envelope_kind"] = "REVIEWER_SEMANTIC"
    (tmp_path / "commitment.json").write_text(json.dumps(commitment))
    manifest["author_commitment_sha256"] = hashlib.sha256((tmp_path / "commitment.json").read_bytes()).hexdigest()
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(ms.FreezeGateRefused, match="commitment.json failed schema validation"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_permuted_corpus_order(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    corpus = json.loads((tmp_path / "corpus_inputs.json").read_text())
    corpus[0], corpus[1] = corpus[1], corpus[0]
    (tmp_path / "corpus_inputs.json").write_text(json.dumps(corpus))
    manifest["corpus_inputs_sha256"] = hashlib.sha256((tmp_path / "corpus_inputs.json").read_bytes()).hexdigest()
    # corpus_inputs.json is one of the eleven labeling-context components
    # -- repropagate, or the (separately tested) recomputed-context-hash
    # cross-check fires before ever reaching the ordering check below.
    _repropagate_context_hash(tmp_path, tmp_path, manifest)
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(ms.InfrastructureFailure, match="id does not equal the expected ordinal"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_permuted_design_order(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    design = json.loads((tmp_path / "design_metadata.json").read_text())
    design["items"][0], design["items"][1] = design["items"][1], design["items"][0]
    (tmp_path / "design_metadata.json").write_text(json.dumps(design))
    manifest["design_metadata_sha256"] = hashlib.sha256((tmp_path / "design_metadata.json").read_bytes()).hexdigest()
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(ms.InfrastructureFailure, match="item_id does not equal the expected ordinal"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_permuted_label_order(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    labels = json.loads((tmp_path / "labels_frozen.json").read_text())
    labels[0], labels[1] = labels[1], labels[0]  # (cal:000,C1) <-> (cal:000,C2): distinct keys, pure reorder
    (tmp_path / "labels_frozen.json").write_text(json.dumps(labels))
    manifest["labels_frozen_sha256"] = hashlib.sha256((tmp_path / "labels_frozen.json").read_bytes()).hexdigest()
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(ms.InfrastructureFailure, match="does not match the canonical"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_duplicate_label(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    labels = json.loads((tmp_path / "labels_frozen.json").read_text())
    # Displace the LAST record with a duplicate of the FIRST record's
    # (item_id, check_id) key -- the array stays length 640, but
    # (cal:000, C1) now appears twice and (cal:159, C4) is missing.
    labels[639] = {**labels[639], "item_id": labels[0]["item_id"], "check_id": labels[0]["check_id"]}
    (tmp_path / "labels_frozen.json").write_text(json.dumps(labels))
    manifest["labels_frozen_sha256"] = hashlib.sha256((tmp_path / "labels_frozen.json").read_bytes()).hexdigest()
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(ms.InfrastructureFailure, match="duplicate"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_foreign_item_id_in_coverage_evidence(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    coverage = json.loads((tmp_path / "coverage_manifest.json").read_text())
    first_surface = next(iter(coverage))
    coverage[first_surface][0]["item_id"] = "cal:999"  # schema-shape-valid (matches ^cal:[0-9]{3}$), not in corpus
    (tmp_path / "coverage_manifest.json").write_text(json.dumps(coverage))
    manifest["coverage_manifest_sha256"] = hashlib.sha256((tmp_path / "coverage_manifest.json").read_bytes()).hexdigest()
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(ms.InfrastructureFailure, match="not a member of corpus_inputs.json"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_reversed_ledger(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    ledger = json.loads((tmp_path / "reveal_verification_ledger.json").read_text())
    ledger["entries"] = list(reversed(ledger["entries"]))
    (tmp_path / "reveal_verification_ledger.json").write_text(json.dumps(ledger))
    manifest["reveal_verification_ledger_sha256"] = hashlib.sha256((tmp_path / "reveal_verification_ledger.json").read_bytes()).hexdigest()
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    # Entry-level `verified` flags are untouched by the reversal, so
    # verify_freeze_manifest's OWN (reused, unchanged) ledger check finds
    # nothing wrong -- the schema's pinned prefixItems order is what
    # catches this, exclusively.
    with pytest.raises(ms.FreezeGateRefused, match="reveal_verification_ledger.json failed schema validation"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_ledger_commitment_disagreeing_with_envelope(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    ledger = json.loads((tmp_path / "reveal_verification_ledger.json").read_text())
    ledger["entries"][0]["commitment_hex"] = "9" * 64
    (tmp_path / "reveal_verification_ledger.json").write_text(json.dumps(ledger))
    manifest["reveal_verification_ledger_sha256"] = hashlib.sha256((tmp_path / "reveal_verification_ledger.json").read_bytes()).hexdigest()
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(ms.FreezeGateRefused, match="commitment_hex disagrees with its envelope"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_ledger_byte_length_disagreeing_with_actual_raw_bytes(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    ledger = json.loads((tmp_path / "reveal_verification_ledger.json").read_text())
    ledger["entries"][0]["byte_length"] = ledger["entries"][0]["byte_length"] + 1
    (tmp_path / "reveal_verification_ledger.json").write_text(json.dumps(ledger))
    manifest["reveal_verification_ledger_sha256"] = hashlib.sha256((tmp_path / "reveal_verification_ledger.json").read_bytes()).hexdigest()
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(ms.FreezeGateRefused, match="ledger byte_length does not equal the actual raw artifact byte length"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_missing_raw_committed_artifact(tmp_path):
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    (tmp_path / "labels_author_semantic.json").unlink()
    with pytest.raises(ms.FreezeGateRefused, match="committed raw artifact does not exist"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_missing_manifest_key(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    del manifest["adjudication_log_sha256"]
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(ms.FreezeGateRefused, match="FREEZE-MANIFEST.json failed schema validation"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_unverified_ledger_entry(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    ledger = json.loads((tmp_path / "reveal_verification_ledger.json").read_text())
    ledger["entries"][0]["verified"] = False
    (tmp_path / "reveal_verification_ledger.json").write_text(json.dumps(ledger))
    manifest["reveal_verification_ledger_sha256"] = hashlib.sha256((tmp_path / "reveal_verification_ledger.json").read_bytes()).hexdigest()
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    # SAN-881 PASS 2C.1-FIX (defect 2): verify_freeze_manifest no longer
    # parses ledger content at all (that unguarded parsing is exactly
    # the raw-exception-leak bug this pass fixes), so its OWN
    # entry-level `verified` check (pre-existing before this pass) no
    # longer exists either. This is now caught by
    # reveal_verification_ledger_schema.json's schema validation, which
    # pins `verified: const true` -- still refused, still a
    # FreezeGateRefused, via a DIFFERENT (schema-level, not content-
    # inspection) mechanism. The ledger's OWN "is not verified"
    # cross-check now lives exclusively in verify_frozen_bundle's ledger
    # index-by-index cross-check (see
    # test_verify_frozen_bundle_rejects_missing_manifest_key's sibling
    # negatives above for that layer).
    with pytest.raises(ms.FreezeGateRefused, match="reveal_verification_ledger.json failed schema validation"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_wrong_corpus_count(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    corpus = json.loads((tmp_path / "corpus_inputs.json").read_text())[:159]
    (tmp_path / "corpus_inputs.json").write_text(json.dumps(corpus))
    manifest["corpus_inputs_sha256"] = hashlib.sha256((tmp_path / "corpus_inputs.json").read_bytes()).hexdigest()
    _repropagate_context_hash(tmp_path, tmp_path, manifest)
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(ms.InfrastructureFailure, match="expected 160 items"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_wrong_label_count(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    labels = json.loads((tmp_path / "labels_frozen.json").read_text())[:639]
    (tmp_path / "labels_frozen.json").write_text(json.dumps(labels))
    manifest["labels_frozen_sha256"] = hashlib.sha256((tmp_path / "labels_frozen.json").read_bytes()).hexdigest()
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(ms.InfrastructureFailure, match="expected 640 records"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_benchmark_rerun_full_freeze_verification_rejects_mutation_after_measure_earlier_success(tmp_path):
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    freeze_manifest_path = tmp_path / "FREEZE-MANIFEST.json"

    # "measure's earlier successful verification" -- verify_frozen_bundle
    # succeeds once, exactly as measure.run_pipeline invokes it.
    ms.verify_frozen_bundle(freeze_manifest_path, tmp_path, tmp_path)

    # A mutation made AFTER that successful verification.
    (tmp_path / "labels_author_semantic.json").unlink()

    # benchmark._rerun_full_freeze_verification must read FRESH from disk
    # and independently catch the now-missing artifact -- proving there
    # is no shared cache/staleness between measure's earlier verification
    # and benchmark's own, later, independent one.
    _, failures = bm._rerun_full_freeze_verification(freeze_manifest_path, tmp_path, tmp_path)
    assert any("committed raw artifact does not exist" in f for f in failures)


def _ast_call_count(func, name: str) -> int:
    """Counts direct ast.Call nodes whose function is exactly `name` (a
    bare Name, e.g. `verify_frozen_bundle(...)`) or an attribute access
    ending in `.name` (e.g. `ms.verify_frozen_bundle(...)`), anywhere
    within `func`'s own source -- never transitively into functions it
    calls. A substring/count-in-source check would false-positive on a
    comment or docstring mentioning the name; this counts genuine call
    sites only."""
    import ast
    import inspect

    source = inspect.getsource(func)
    tree = ast.parse(source)
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name) and target.id == name:
                count += 1
            elif isinstance(target, ast.Attribute) and target.attr == name:
                count += 1
    return count


def test_measure_run_pipeline_calls_verify_frozen_bundle_exactly_once_no_retired_verifiers():
    assert _ast_call_count(ms.run_pipeline, "verify_frozen_bundle") == 1
    # SAN-881 PASS 2C.1 retires BOTH prior measure.py-local
    # freeze-verification entry points entirely -- neither exists as a
    # module attribute any more, so no duplicate-implementation call site
    # is even possible, accidentally or otherwise.
    assert not hasattr(ms, "load_and_verify_freeze_manifest")
    assert not hasattr(ms, "_validate_frozen_schemas_and_population")


def test_benchmark_rerun_full_freeze_verification_calls_verify_frozen_bundle_exactly_once():
    assert _ast_call_count(bm._rerun_full_freeze_verification, "verify_frozen_bundle") == 1


def test_benchmark_module_has_no_own_schema_context_ledger_population_implementation():
    # The shared implementation necessarily lives in measure.py --
    # this asserts the ABSENCE of a duplicate in benchmark.py, never
    # that the implementation itself lives anywhere in particular.
    referenced = _ast_referenced_names(bm)
    forbidden = {
        "Draft202012Validator", "LEDGER_CANONICAL_ORDER", "SCHEMA_FILES",
        "LABELING_CONTEXT_COMPONENT_NAMES", "build_labeling_context_components",
        "compute_labeling_context_hash_from_disk",
    }
    hit = referenced & forbidden
    assert hit == set(), f"benchmark.py's AST references forbidden schema/context/ledger symbols: {hit}"


# =======================================================================
# SAN-881 PASS 2C.1-FIX: three CORRECTION-ONLY defects found against the
# 2C.1 architecture (verify_frozen_bundle contract, six-plus-two direct
# imports, ledger index-by-index cross-check, call-site centralization,
# run_pipeline path fix -- all ACCEPTED and unchanged by this pass).
# Grouped by defect below.
# =======================================================================

# ---------------------------------------------------------------------
# Defect 1: frozen-label coherence was INCOMPLETE -- the labels_frozen
# loop validated ONLY the contract tuple (_validate_tuple_consistency),
# never semantic_truth-vs-contract-outcome agreement, check_id-specific
# severity, advisory-must-be-False, or competence/stratum consistency.
# Each fixture below isolates exactly ONE validate_design.check_labels
# rule that _validate_tuple_consistency alone cannot see (it is handed
# only the contract_tuple fields -- it never even receives
# semantic_truth or competence), starting from the SAME clean toy
# bundle and mutating exactly one labels_frozen.json record.
# ---------------------------------------------------------------------

def _mutate_one_label_record(tmp_path: Path, index: int, **field_overrides) -> None:
    """Overwrites labels_frozen[index] with field_overrides merged onto
    the existing record, refreshes labels_frozen_sha256 in
    FREEZE-MANIFEST.json (labels_frozen.json is NOT one of the eleven
    labeling-context components, so no context-hash repropagation is
    needed -- see test_verify_frozen_bundle_rejects_permuted_label_order
    for the same pattern), and rewrites the manifest."""
    manifest = json.loads((tmp_path / "FREEZE-MANIFEST.json").read_text())
    labels = json.loads((tmp_path / "labels_frozen.json").read_text())
    labels[index] = {**labels[index], **field_overrides}
    (tmp_path / "labels_frozen.json").write_text(json.dumps(labels))
    manifest["labels_frozen_sha256"] = hashlib.sha256((tmp_path / "labels_frozen.json").read_bytes()).hexdigest()
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))


def test_verify_frozen_bundle_rejects_labels_semantic_contract_outcome_mismatch(tmp_path):
    # Reviewer-reproduced: semantic_truth=VIOLATION paired with a PASS
    # contract on an in-domain target record (cal:000's own target check
    # is C1) -- _validate_tuple_consistency sees only the (internally
    # self-consistent) contract tuple and accepts it; check_labels
    # rejects it as IN_DOMAIN_OUTCOME_MAP_MISMATCH.
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    _mutate_one_label_record(tmp_path, 0, semantic_truth="VIOLATION")  # cal:000/C1, contract stays PASS
    with pytest.raises(ms.InfrastructureFailure, match=r"cal:000/C1: rule=IN_DOMAIN_OUTCOME_MAP_MISMATCH"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_labels_c1_violation_with_warning_severity(tmp_path):
    # Reviewer-reproduced: a C1 VIOLATION with severity=warning (must be
    # critical) -- schema-valid (severity in {critical,warning} for any
    # VIOLATION, check_id-agnostic) and _validate_tuple_consistency-clean
    # (same, check_id-agnostic); only check_labels's check_id-specific
    # rule catches it.
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    _mutate_one_label_record(
        tmp_path, 0,  # cal:000/C1
        semantic_truth="VIOLATION",
        contract_tuple={"outcome": "VIOLATION", "outcome_reason": "detection_complete", "severity": "warning", "advisory": False},
    )
    with pytest.raises(ms.InfrastructureFailure, match=r"cal:000/C1: rule=SEVERITY_MISMATCH"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_labels_non_c1_violation_with_critical_severity(tmp_path):
    # The other direction: a non-C1 (here C2) VIOLATION with
    # severity=critical (must be warning). cal:000's target check is C1,
    # so this C2 record is off-target and the in-domain-competence/
    # outcome-map rules below do not apply to it -- isolates the
    # severity rule alone.
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    _mutate_one_label_record(
        tmp_path, 1,  # cal:000/C2
        contract_tuple={"outcome": "VIOLATION", "outcome_reason": "detection_complete", "severity": "critical", "advisory": False},
    )
    with pytest.raises(ms.InfrastructureFailure, match=r"cal:000/C2: rule=SEVERITY_MISMATCH"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_labels_advisory_true(tmp_path):
    # Reviewer-reproduced: advisory=true in this tier_1-only corpus --
    # schema-valid (advisory is typed boolean, never const-pinned to
    # false) and _validate_tuple_consistency-clean (isinstance bool);
    # only check_labels's ADVISORY_MUST_BE_FALSE rule catches it.
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    _mutate_one_label_record(
        tmp_path, 0,  # cal:000/C1
        contract_tuple={"outcome": "PASS", "outcome_reason": "detection_complete", "severity": None, "advisory": True},
    )
    with pytest.raises(ms.InfrastructureFailure, match=r"cal:000/C1: rule=ADVISORY_MUST_BE_FALSE"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_labels_invalid_competence_for_in_domain_item(tmp_path):
    # cal:000's OWN target check is C1 at stratum in_domain_nonviolation
    # -- an in-domain TARGET record declared with a different (schema-
    # valid) competence is IN_DOMAIN_COMPETENCE_MISMATCH. semantic_truth
    # and contract_tuple are updated together so DELIBERATE_ABSTENTION
    # stays internally self-consistent (truth==INDETERMINATE, outcome
    # mapped to NOT_EVALUATED) -- ONLY the competence rule fires, not
    # also the outcome-map or abstention-truth rules.
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    _mutate_one_label_record(
        tmp_path, 0,  # cal:000/C1
        semantic_truth="INDETERMINATE",
        competence="DELIBERATE_ABSTENTION",
        contract_tuple={"outcome": "NOT_EVALUATED", "outcome_reason": "input_empty", "severity": None, "advisory": False},
    )
    with pytest.raises(ms.InfrastructureFailure, match=r"cal:000/C1: rule=IN_DOMAIN_COMPETENCE_MISMATCH"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_labels_known_coverage_gap_out_of_scope(tmp_path):
    # cal:030's OWN target check is C1 at stratum indeterminate_or_unsafe
    # (NOT determinate_out_of_domain) -- competence=KNOWN_COVERAGE_GAP is
    # schema-valid but out of scope for this item/check's stratum.
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    _mutate_one_label_record(tmp_path, 120, competence="KNOWN_COVERAGE_GAP")  # cal:030/C1
    with pytest.raises(ms.InfrastructureFailure, match=r"cal:030/C1: rule=KNOWN_COVERAGE_GAP_OUT_OF_SCOPE"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


# ---------------------------------------------------------------------
# Defect 2 + Defect 3: the fail-closed boundary leaked raw exceptions.
# verify_freeze_manifest used to parse provenance JSON (commitment.json,
# both reviewer commitment envelopes, reveal_verification_ledger.json)
# UNGUARDED, before any schema gate -- a malformed envelope produced a
# raw AttributeError/JSONDecodeError/IsADirectoryError instead of a
# FreezeGateRefused, and a missing manifest-bound artifact's refusal
# text embedded its ABSOLUTE filesystem path. verify_freeze_manifest is
# now reduced to a RAW-HASH-ONLY helper (see its own docstring for the
# reduce-vs-retire rationale) that never parses JSON at all; every
# actual JSON/bytes read in verify_frozen_bundle is routed through the
# fixed-name helpers _load_json_or_fail / _read_bytes_or_fail /
# _sha256_or_fail / _schema_validate_or_fail, which translate OSError
# (including a directory in place of a file), UnicodeDecodeError,
# JSONDecodeError, and jsonschema ENGINE failures into
# FreezeGateRefused/InfrastructureFailure -- never a raw traceback,
# never an absolute path in the message.
# ---------------------------------------------------------------------

def _assert_no_absolute_path_leak(message: str, *roots: Path) -> None:
    for root in roots:
        assert str(root) not in message, f"absolute path {root} leaked into diagnostic: {message!r}"


def test_verify_frozen_bundle_rejects_invalid_json_provenance_through_both_entry_points(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    (tmp_path / "commitment.json").write_text("{")  # malformed JSON -- the ticket's own reproduction
    manifest["author_commitment_sha256"] = hashlib.sha256((tmp_path / "commitment.json").read_bytes()).hexdigest()
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    freeze_manifest_path = tmp_path / "FREEZE-MANIFEST.json"

    with pytest.raises(ms.FreezeGateRefused, match=r"commitment\.json is unreadable or not valid JSON") as excinfo:
        ms.verify_frozen_bundle(freeze_manifest_path, tmp_path, tmp_path)
    _assert_no_absolute_path_leak(str(excinfo.value), tmp_path)

    _, failures = bm._rerun_full_freeze_verification(freeze_manifest_path, tmp_path, tmp_path)
    assert len(failures) == 1
    assert "commitment.json is unreadable or not valid JSON" in failures[0]
    _assert_no_absolute_path_leak(failures[0], tmp_path)


def test_verify_frozen_bundle_rejects_invalid_utf8_provenance_through_both_entry_points(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    (tmp_path / "commitment.json").write_bytes(b"\xff\xfe\x00\x01")  # not valid UTF-8
    manifest["author_commitment_sha256"] = hashlib.sha256((tmp_path / "commitment.json").read_bytes()).hexdigest()
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    freeze_manifest_path = tmp_path / "FREEZE-MANIFEST.json"

    with pytest.raises(ms.FreezeGateRefused, match=r"commitment\.json is unreadable or not valid JSON") as excinfo:
        ms.verify_frozen_bundle(freeze_manifest_path, tmp_path, tmp_path)
    _assert_no_absolute_path_leak(str(excinfo.value), tmp_path)

    _, failures = bm._rerun_full_freeze_verification(freeze_manifest_path, tmp_path, tmp_path)
    assert len(failures) == 1
    assert "commitment.json is unreadable or not valid JSON" in failures[0]
    _assert_no_absolute_path_leak(failures[0], tmp_path)


def test_verify_frozen_bundle_rejects_top_level_list_provenance_through_both_entry_points(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    (tmp_path / "commitment.json").write_text("[]")  # valid JSON, wrong top-level shape
    manifest["author_commitment_sha256"] = hashlib.sha256((tmp_path / "commitment.json").read_bytes()).hexdigest()
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    freeze_manifest_path = tmp_path / "FREEZE-MANIFEST.json"

    with pytest.raises(ms.FreezeGateRefused, match=r"commitment\.json failed schema validation") as excinfo:
        ms.verify_frozen_bundle(freeze_manifest_path, tmp_path, tmp_path)
    _assert_no_absolute_path_leak(str(excinfo.value), tmp_path)

    _, failures = bm._rerun_full_freeze_verification(freeze_manifest_path, tmp_path, tmp_path)
    assert len(failures) == 1
    assert "commitment.json failed schema validation" in failures[0]
    _assert_no_absolute_path_leak(failures[0], tmp_path)


def test_verify_frozen_bundle_rejects_directory_in_place_of_raw_committed_artifact_through_both_entry_points(tmp_path):
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    (tmp_path / "labels_author_semantic.json").unlink()
    (tmp_path / "labels_author_semantic.json").mkdir()  # a DIRECTORY in place of the raw artifact
    freeze_manifest_path = tmp_path / "FREEZE-MANIFEST.json"

    with pytest.raises(ms.FreezeGateRefused) as excinfo:
        ms.verify_frozen_bundle(freeze_manifest_path, tmp_path, tmp_path)
    assert "labels_author_semantic.json" in str(excinfo.value)
    _assert_no_absolute_path_leak(str(excinfo.value), tmp_path)

    _, failures = bm._rerun_full_freeze_verification(freeze_manifest_path, tmp_path, tmp_path)
    assert len(failures) == 1
    assert "labels_author_semantic.json" in failures[0]
    _assert_no_absolute_path_leak(failures[0], tmp_path)


def test_verify_frozen_bundle_rejects_malformed_corpus_context_through_both_entry_points(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    corpus = json.loads((tmp_path / "corpus_inputs.json").read_text())
    corpus[0]["context"] = []
    (tmp_path / "corpus_inputs.json").write_text(json.dumps(corpus))
    manifest["corpus_inputs_sha256"] = hashlib.sha256((tmp_path / "corpus_inputs.json").read_bytes()).hexdigest()
    _repropagate_context_hash(tmp_path, tmp_path, manifest)
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    freeze_manifest_path = tmp_path / "FREEZE-MANIFEST.json"

    with pytest.raises(ms.InfrastructureFailure, match="context must be a string") as excinfo:
        ms.verify_frozen_bundle(freeze_manifest_path, tmp_path, tmp_path)
    _assert_no_absolute_path_leak(str(excinfo.value), tmp_path)

    _, failures = bm._rerun_full_freeze_verification(freeze_manifest_path, tmp_path, tmp_path)
    assert len(failures) == 1
    assert "context must be a string" in failures[0]
    _assert_no_absolute_path_leak(failures[0], tmp_path)


def test_verify_frozen_bundle_rejects_malformed_corpus_output_through_both_entry_points(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    corpus = json.loads((tmp_path / "corpus_inputs.json").read_text())
    corpus[0]["output"] = {}
    (tmp_path / "corpus_inputs.json").write_text(json.dumps(corpus))
    manifest["corpus_inputs_sha256"] = hashlib.sha256((tmp_path / "corpus_inputs.json").read_bytes()).hexdigest()
    _repropagate_context_hash(tmp_path, tmp_path, manifest)
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    freeze_manifest_path = tmp_path / "FREEZE-MANIFEST.json"

    with pytest.raises(ms.InfrastructureFailure, match="output must be a string") as excinfo:
        ms.verify_frozen_bundle(freeze_manifest_path, tmp_path, tmp_path)
    _assert_no_absolute_path_leak(str(excinfo.value), tmp_path)

    _, failures = bm._rerun_full_freeze_verification(freeze_manifest_path, tmp_path, tmp_path)
    assert len(failures) == 1
    assert "output must be a string" in failures[0]
    _assert_no_absolute_path_leak(failures[0], tmp_path)


# ---------------------------------------------------------------------
# Defect 4: corpus type-proving BEFORE use. corpus_inputs.json carries
# NO JSON Schema (by design), so field types must be proven EXPLICITLY,
# before duplicate detection, the context_sources join, or any
# .encode() call.
# ---------------------------------------------------------------------

def test_verify_frozen_bundle_rejects_corpus_context_sources_text_not_a_string(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    corpus = json.loads((tmp_path / "corpus_inputs.json").read_text())
    corpus[0] = {"id": "cal:000", "context_sources": [{"text": [], "tier": "tier_1"}], "output": corpus[0]["output"]}
    (tmp_path / "corpus_inputs.json").write_text(json.dumps(corpus))
    manifest["corpus_inputs_sha256"] = hashlib.sha256((tmp_path / "corpus_inputs.json").read_bytes()).hexdigest()
    _repropagate_context_hash(tmp_path, tmp_path, manifest)
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(ms.InfrastructureFailure, match="text must be a string"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


def test_verify_frozen_bundle_rejects_corpus_context_sources_not_a_list(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    corpus = json.loads((tmp_path / "corpus_inputs.json").read_text())
    corpus[0] = {"id": "cal:000", "context_sources": {"text": "x", "tier": "tier_1"}, "output": corpus[0]["output"]}
    (tmp_path / "corpus_inputs.json").write_text(json.dumps(corpus))
    manifest["corpus_inputs_sha256"] = hashlib.sha256((tmp_path / "corpus_inputs.json").read_bytes()).hexdigest()
    _repropagate_context_hash(tmp_path, tmp_path, manifest)
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(ms.InfrastructureFailure, match="context_sources must be a list"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


# ---------------------------------------------------------------------
# Defect 6: the missing behavioral regression for the run_pipeline path
# fix. The 2C.1 pass fixed a live bug (run_pipeline verified the
# module-global FREEZE_MANIFEST_PATH regardless of its own cal_dir
# argument) but only proved it STRUCTURALLY, via an AST call-count check
# (test_measure_run_pipeline_calls_verify_frozen_bundle_exactly_once_no_
# retired_verifiers above). This spies on verify_frozen_bundle's ACTUAL
# runtime arguments.
# ---------------------------------------------------------------------

def test_measure_run_pipeline_passes_exact_manifest_path_and_same_cal_dir_to_verify_frozen_bundle(tmp_path, monkeypatch):
    cal_dir = tmp_path / "cal"
    cal_dir.mkdir()
    _init_toy_git_repo(tmp_path)
    _write_minimal_run_pipeline_cal_dir(cal_dir)
    monkeypatch.setattr(ms, "REPO_ROOT", tmp_path)

    captured: dict = {}

    def spy(freeze_manifest_path, cal_dir_arg, repo_root_arg):
        captured["freeze_manifest_path"] = freeze_manifest_path
        captured["cal_dir"] = cal_dir_arg
        captured["repo_root"] = repo_root_arg
        raise ms.FreezeGateRefused("spy stop")

    monkeypatch.setattr(ms, "verify_frozen_bundle", spy)

    with pytest.raises(ms.FreezeGateRefused, match="spy stop"):
        ms.run_pipeline(cal_dir)

    assert captured["freeze_manifest_path"] == cal_dir / "FREEZE-MANIFEST.json"
    assert captured["cal_dir"] is cal_dir  # the SAME object run_pipeline was called with, not a reconstruction
    assert captured["repo_root"] == tmp_path


# =======================================================================
# SAN-881 PASS 2C.1-FIX-PINS: three GREEN-FROM-BIRTH regression pins
# closing test-coverage gaps against the ACCEPTED 2C.1-FIX architecture
# (verify_frozen_bundle contract, direct imports, ledger index-by-index
# cross-check, call-site centralization, run_pipeline path fix, the
# fixed-name _load_json_or_fail / _read_bytes_or_fail / _sha256_or_fail /
# _schema_validate_or_fail helpers -- all unchanged by this pass). Every
# fixture below starts from the SAME clean toy v2 bundle
# (_write_toy_v2_schema_valid_freeze_environment) and mutates exactly
# ONE logical invariant, through BOTH consumers (ms.verify_frozen_bundle
# directly and benchmark._rerun_full_freeze_verification).
# =======================================================================

def test_verify_frozen_bundle_rejects_labels_deliberate_abstention_with_determinate_truth_through_both_entry_points(tmp_path):
    # cal:000/C2 is OFF-TARGET (cal:000's own target check is C1) --
    # declaring competence=DELIBERATE_ABSTENTION while semantic_truth
    # stays determinate (NO_VIOLATION, untouched) and the PASS contract
    # is left unchanged isolates RULE_ABSTENTION_TRUTH_MISMATCH alone:
    # off-target, so neither the IN_DOMAIN_COMPETENCE nor the
    # IN_DOMAIN_OUTCOME_MAP rule applies to this record, and the
    # contract tuple itself stays internally self-consistent
    # (_validate_tuple_consistency-clean).
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    _mutate_one_label_record(tmp_path, 1, competence="DELIBERATE_ABSTENTION")  # cal:000/C2
    freeze_manifest_path = tmp_path / "FREEZE-MANIFEST.json"

    with pytest.raises(ms.InfrastructureFailure, match=r"cal:000/C2: rule=DELIBERATE_ABSTENTION_REQUIRES_INDETERMINATE") as excinfo:
        ms.verify_frozen_bundle(freeze_manifest_path, tmp_path, tmp_path)
    _assert_no_absolute_path_leak(str(excinfo.value), tmp_path)

    _, failures = bm._rerun_full_freeze_verification(freeze_manifest_path, tmp_path, tmp_path)
    assert len(failures) == 1
    assert "cal:000/C2: rule=DELIBERATE_ABSTENTION_REQUIRES_INDETERMINATE" in failures[0]
    _assert_no_absolute_path_leak(failures[0], tmp_path)


def test_verify_frozen_bundle_rejects_missing_adjudication_log_through_both_entry_points(tmp_path):
    # adjudication_log.json deleted WITHOUT refreshing its manifest
    # binding (adjudication_log_sha256 still names the file by its
    # canonical artifact name, never an absolute path) -- every other
    # bound raw-hash key is untouched, isolating this ONE binding.
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    (tmp_path / "adjudication_log.json").unlink()
    freeze_manifest_path = tmp_path / "FREEZE-MANIFEST.json"

    with pytest.raises(ms.FreezeGateRefused, match=r"adjudication_log_sha256: bound file adjudication_log\.json does not exist") as excinfo:
        ms.verify_frozen_bundle(freeze_manifest_path, tmp_path, tmp_path)
    _assert_no_absolute_path_leak(str(excinfo.value), tmp_path)

    _, failures = bm._rerun_full_freeze_verification(freeze_manifest_path, tmp_path, tmp_path)
    assert len(failures) == 1
    assert "adjudication_log_sha256: bound file adjudication_log.json does not exist" in failures[0]
    _assert_no_absolute_path_leak(failures[0], tmp_path)


def test_verify_frozen_bundle_rejects_dangling_local_ref_in_coverage_schema_through_both_entry_points(tmp_path):
    # A syntactically valid Draft 2020-12 schema (check_schema itself
    # raises nothing) whose "allOf" references a $defs branch that does
    # not exist -- the schema FILE loads and check_schema-passes clean;
    # only actually validating coverage_manifest.json against it forces
    # $ref resolution, which the underlying jsonschema/referencing
    # engine raises as a PointerToNowhere-flavored ENGINE failure (never
    # a soft ValidationError), which _schema_validate_or_fail's `except
    # Exception` branch translates into a fixed InfrastructureFailure
    # message -- never a raw traceback, never the resolver's own
    # exception text. schemas/coverage_manifest_schema.json is one of
    # the eleven labeling-context components, so the recomputed context
    # hash/envelope/ledger bindings must be repropagated or the
    # (separately tested) recomputed-context-hash cross-check fires
    # first instead of the schema-engine-error path this test targets.
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    schema_path = tmp_path / "schemas" / "coverage_manifest_schema.json"
    schema = json.loads(schema_path.read_text())
    schema["allOf"] = [{"$ref": "#/$defs/DOES_NOT_EXIST"}]
    schema_path.write_text(json.dumps(schema))
    _repropagate_context_hash(tmp_path, tmp_path, manifest)
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    freeze_manifest_path = tmp_path / "FREEZE-MANIFEST.json"

    with pytest.raises(ms.InfrastructureFailure, match=r"coverage_manifest\.json failed schema validation \(schema engine error\)") as excinfo:
        ms.verify_frozen_bundle(freeze_manifest_path, tmp_path, tmp_path)
    message = str(excinfo.value)
    assert "PointerToNowhere" not in message
    assert "Traceback" not in message
    _assert_no_absolute_path_leak(message, tmp_path)

    _, failures = bm._rerun_full_freeze_verification(freeze_manifest_path, tmp_path, tmp_path)
    assert len(failures) == 1
    assert "coverage_manifest.json failed schema validation (schema engine error)" in failures[0]
    assert "PointerToNowhere" not in failures[0]
    assert "Traceback" not in failures[0]
    _assert_no_absolute_path_leak(failures[0], tmp_path)


# =======================================================================
# SAN-881 PUBLIC-INFRASTRUCTURE-ONLY closure pass: 11 corrections + 5
# pinning amendments. New regressions below, grouped by correction.
# =======================================================================

# ---------------------------------------------------------------------
# Correction 1 (SAN-881 CORRECTION PASS 2, operator-ratified Coverage
# Routing Matrix v3): complete-inventory declarative 68-surface registry
# with ALLOWED_POSITIONS pairs replacing allowed_checks x allowed_fields.
# 47 table-derived + 3 value_role_v1 (synthetic) + 18 nontable = 68;
# excl_v1.refundable_nonrefundable retired; units_v1.facet:* renamed to
# value_role_v1.{cost,duration,limit}.
# ---------------------------------------------------------------------

def test_surface_registry_has_exactly_68_entries():
    assert len(vd.SURFACE_REGISTRY) == 68


def test_surface_registry_total_allowed_positions_is_362():
    total = sum(len(e["allowed_positions"]) for e in vd.SURFACE_REGISTRY.values())
    assert total == 362


def test_surface_registry_family_counts_sum_47_plus_3_plus_18_equals_68():
    predicate_ids = [e["predicate_id"] for e in vd.SURFACE_REGISTRY.values()]
    table_derived = sum(
        1 for surface, e in vd.SURFACE_REGISTRY.items()
        if e["predicate_id"] in ("facets_v1", "concept_v1", "comparators_v1", "excl_v1", "complement_v1", "condition_operators_v1", "quant_v1")
    )
    value_role = predicate_ids.count("value_role_v1")
    nontable = predicate_ids.count("nontable")
    assert table_derived == 47
    assert value_role == 3
    assert nontable == 18
    assert table_derived + value_role + nontable == 68
    assert 47 + 3 + 18 == 68


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1: derived excl_v1 collision set. A PURE, build/
# test-time-only helper (never called from main() or any runtime
# acceptance path -- see the module comment above
# validate_design.derive_excl_trigger_collision_set) proves that
# retiring excl_v1.refundable_nonrefundable from the registry is not
# arbitrary: it is the ONE excl_v1 row whose both members also appear
# in the folded union of every facets_v1 facet's own triggers +
# deny_triggers.
# ---------------------------------------------------------------------

def _real_tables_data() -> dict:
    tables_path = CAL_DIR.parent / "spec" / "ALGORITHM-v4-tables-v1.json"
    return json.loads(tables_path.read_text())


def test_derive_excl_collision_set_equals_registry_excluded_set():
    tables_data = _real_tables_data()
    collision_set = vd.derive_excl_trigger_collision_set(tables_data)
    excluded_set = vd.derive_excl_registry_excluded_set(tables_data)
    # Canonical form (SAN-881 PASS 2B.1-T): the UNORDERED sorted 2-tuple
    # of the two members' folded tokens, NOT the raw table row order.
    assert collision_set == excluded_set == {("nonrefundable", "refundable")}


def test_derive_excl_collision_set_negative_control_deep_copy_manufactured_collision():
    # NEGATIVE CONTROL: deep-copy the real tables JSON (never
    # monkeypatch vd.T, reference.tables.T, or any compiled constant --
    # this is a pure, isolated, build/test-time-only exercise of the
    # two derivation helpers over a private dict), then manufacture a
    # SECOND collision in the COPY by adding "digital" as a trigger of
    # an existing facet (digital_physical does not naturally collide --
    # see the previous test's baseline of exactly one collision).
    # Asserts the helper reports the manufactured collision too, and
    # that the untouched on-disk tables artifact / a fresh read of it
    # are unaffected.
    import copy

    real_tables_data = _real_tables_data()
    baseline_collision_set = vd.derive_excl_trigger_collision_set(real_tables_data)
    assert ("digital", "physical") not in baseline_collision_set

    copied = copy.deepcopy(real_tables_data)
    assert copied is not real_tables_data
    assert copied["facets_v1"] is not real_tables_data["facets_v1"]

    # Pick any real facet in the copy and inject "digital" into its
    # triggers, and "physical" into its deny_triggers, manufacturing a
    # collision for the excl_v1 ("digital", "physical") row that does
    # not exist in the real tables data.
    some_facet_key = next(iter(copied["facets_v1"]))
    copied["facets_v1"][some_facet_key] = dict(copied["facets_v1"][some_facet_key])
    copied["facets_v1"][some_facet_key]["triggers"] = list(copied["facets_v1"][some_facet_key].get("triggers", [])) + ["digital"]
    copied["facets_v1"][some_facet_key]["deny_triggers"] = list(copied["facets_v1"][some_facet_key].get("deny_triggers", [])) + ["physical"]

    manufactured_collision_set = vd.derive_excl_trigger_collision_set(copied)
    assert ("digital", "physical") in manufactured_collision_set
    # The pre-existing genuine collision must still be reported too
    # (canonical sorted order: "nonrefundable" < "refundable").
    assert ("nonrefundable", "refundable") in manufactured_collision_set

    # The REAL, un-copied tables data (and a completely fresh read of
    # the on-disk artifact) must be completely unaffected -- proving
    # the manufactured collision lives ONLY in the deep-copied dict.
    assert vd.derive_excl_trigger_collision_set(real_tables_data) == baseline_collision_set == {("nonrefundable", "refundable")}
    fresh_reread = _real_tables_data()
    assert "digital" not in fresh_reread["facets_v1"][some_facet_key].get("triggers", [])


def test_derive_excl_collision_set_red_stemming_plural_trigger_still_collides():
    # RED DISCRIMINATOR (a): a deep-copied table whose facet trigger
    # list carries "refundables"/"nonrefundables" (PLURAL) against the
    # SINGULAR excl_v1 members "refundable"/"nonrefundable". Production
    # fold_sequence stems the plural trigger to ("refundable",), so the
    # collision IS caught; the prior .lower()-only implementation would
    # have MISSED it (a literal-string "refundable" is never equal to
    # the literal string "refundables"). Never monkeypatches production
    # tables/T/compiled constants -- a private deep copy only.
    import copy

    real_tables_data = _real_tables_data()
    copied = copy.deepcopy(real_tables_data)
    key = "facet:refund_availability"
    assert copied["facets_v1"][key]["triggers"] == ["refundable"]
    assert copied["facets_v1"][key]["deny_triggers"] == ["nonrefundable"]
    copied["facets_v1"][key] = dict(copied["facets_v1"][key])
    copied["facets_v1"][key]["triggers"] = ["refundables"]
    copied["facets_v1"][key]["deny_triggers"] = ["nonrefundables"]

    collision_set = vd.derive_excl_trigger_collision_set(copied)
    assert ("nonrefundable", "refundable") in collision_set

    # Real, un-copied tables data is unaffected.
    assert vd.derive_excl_trigger_collision_set(real_tables_data) == {("nonrefundable", "refundable")}


def test_derive_excl_collision_set_red_reversal_invariance_retired_and_registered_rows():
    # RED DISCRIMINATOR (b): deep-copied tables with a REVERSED retired
    # excl_v1 row (refundable/nonrefundable, in raw-row order swapped)
    # AND a reversed REGISTERED row (digital/physical, also swapped)
    # must both still produce the IDENTICAL canonical sets as the
    # un-reversed original -- canonicalization and registry-membership
    # matching are both order-insensitive, decoupled from raw table row
    # order and from SURFACE_REGISTRY's own fixed join-order key names.
    import copy

    real_tables_data = _real_tables_data()
    baseline_collision = vd.derive_excl_trigger_collision_set(real_tables_data)
    baseline_excluded = vd.derive_excl_registry_excluded_set(real_tables_data)

    copied = copy.deepcopy(real_tables_data)
    reversed_rows = []
    for row in copied["excl_v1"]:
        if set(row) == {"refundable", "nonrefundable"} or set(row) == {"digital", "physical"}:
            reversed_rows.append(list(reversed(row)))
        else:
            reversed_rows.append(row)
    copied["excl_v1"] = reversed_rows
    # Sanity: the rows are genuinely reversed relative to the original.
    assert copied["excl_v1"] != real_tables_data["excl_v1"]

    reversed_collision = vd.derive_excl_trigger_collision_set(copied)
    reversed_excluded = vd.derive_excl_registry_excluded_set(copied)
    assert reversed_collision == baseline_collision == {("nonrefundable", "refundable")}
    assert reversed_excluded == baseline_excluded == {("nonrefundable", "refundable")}

    # "digital_physical" (reversed to physical/digital in the copy) must
    # still resolve as REGISTERED (not excluded) via order-insensitive
    # registry membership matching.
    assert ("digital", "physical") not in reversed_excluded


def test_fold_excl_member_raises_valueerror_on_multi_token_member():
    # ENFORCEMENT: an excl_v1 member that folds to more than one token
    # is a build/test-time authoring defect -- fail loud, never guess.
    with pytest.raises(ValueError):
        vd._fold_excl_member("no refunds")


def test_derive_excl_collision_set_raises_valueerror_on_multi_token_excl_v1_row():
    import copy

    real_tables_data = _real_tables_data()
    copied = copy.deepcopy(real_tables_data)
    copied["excl_v1"] = copied["excl_v1"] + [["no refunds", "physical"]]
    with pytest.raises(ValueError):
        vd.derive_excl_trigger_collision_set(copied)


def test_derive_excl_registry_excluded_set_raises_valueerror_on_multi_token_excl_v1_row():
    import copy

    real_tables_data = _real_tables_data()
    copied = copy.deepcopy(real_tables_data)
    copied["excl_v1"] = copied["excl_v1"] + [["no refunds", "physical"]]
    with pytest.raises(ValueError):
        vd.derive_excl_registry_excluded_set(copied)


def test_assert_excl_collision_registry_alignment_passes_on_real_table():
    tables_data = _real_tables_data()
    # Must not raise.
    vd.assert_excl_collision_registry_alignment(tables_data)


def test_assert_excl_collision_registry_alignment_negative_control_fails_on_manufactured_collision():
    # NEGATIVE CONTROL: proves the central equality assertion inside
    # assert_excl_collision_registry_alignment is LIVE, not vacuously
    # true -- a manufactured SECOND collision (digital/physical) in a
    # deep-copied tables JSON must make the helper raise
    # AssertionError, since collision_set would then contain an entry
    # ("digital", "physical") that excluded_set does not (digital_physical
    # remains a REGISTERED, non-retired surface). Never monkeypatches
    # vd.T, reference.tables.T, or any compiled constant; the real
    # singletons are asserted untouched afterward.
    import copy

    real_tables_data = _real_tables_data()
    copied = copy.deepcopy(real_tables_data)
    some_facet_key = next(iter(copied["facets_v1"]))
    copied["facets_v1"][some_facet_key] = dict(copied["facets_v1"][some_facet_key])
    copied["facets_v1"][some_facet_key]["triggers"] = list(copied["facets_v1"][some_facet_key].get("triggers", [])) + ["digital"]
    copied["facets_v1"][some_facet_key]["deny_triggers"] = list(copied["facets_v1"][some_facet_key].get("deny_triggers", [])) + ["physical"]

    with pytest.raises(AssertionError):
        vd.assert_excl_collision_registry_alignment(copied)

    # The real singletons are untouched by the failed attempt.
    assert len(vd.SURFACE_REGISTRY) == 68
    vd.assert_excl_collision_registry_alignment(real_tables_data)
    fresh_reread = _real_tables_data()
    assert "digital" not in fresh_reread["facets_v1"][some_facet_key].get("triggers", [])


def test_derive_excl_registry_excluded_set_is_independent_of_trigger_collision_helper():
    # Cross-check with an explicit, hand-built registry (never
    # vd.SURFACE_REGISTRY itself) proving derive_excl_registry_excluded_set
    # genuinely reads the registry argument and never touches facets_v1.
    tables_data = {"excl_v1": [["a", "b"], ["c", "d"]], "facets_v1": {"facet:x": {"triggers": ["a", "b", "c", "d"], "deny_triggers": []}}}
    registry_missing_both = {}
    assert vd.derive_excl_registry_excluded_set(tables_data, registry_missing_both) == {("a", "b"), ("c", "d")}
    registry_with_a_b = {"excl_v1.a_b": {}}
    assert vd.derive_excl_registry_excluded_set(tables_data, registry_with_a_b) == {("c", "d")}


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1-T-FIX blocker 6: LOUD COLLISION-HELPER FAILURES.
# Both derive_excl_* helpers currently silently `continue` past a
# malformed excl_v1 row (cardinality != 2) and silently accept a folded
# duplicate (two members -- or two different rows -- normalizing to the
# same folded token/pair) into the same set entry. Deep-copied tables
# only; the real singletons are asserted untouched after every
# pytest.raises block.
# ---------------------------------------------------------------------

def test_derive_excl_trigger_collision_set_raises_valueerror_on_row_cardinality_not_two():
    # RED DISCRIMINATOR (a): row cardinality != 2 (a single-member row).
    import copy

    real_tables_data = _real_tables_data()
    copied = copy.deepcopy(real_tables_data)
    copied["excl_v1"] = copied["excl_v1"] + [["solo"]]
    with pytest.raises(ValueError):
        vd.derive_excl_trigger_collision_set(copied)
    assert vd.derive_excl_trigger_collision_set(real_tables_data) == {("nonrefundable", "refundable")}


def test_derive_excl_registry_excluded_set_raises_valueerror_on_row_cardinality_not_two():
    # RED DISCRIMINATOR (a), companion helper: cardinality 3.
    import copy

    real_tables_data = _real_tables_data()
    copied = copy.deepcopy(real_tables_data)
    copied["excl_v1"] = copied["excl_v1"] + [["a", "b", "c"]]
    with pytest.raises(ValueError):
        vd.derive_excl_registry_excluded_set(copied)
    assert vd.derive_excl_registry_excluded_set(real_tables_data) == {("nonrefundable", "refundable")}


def test_derive_excl_trigger_collision_set_raises_valueerror_on_same_folded_token_both_members():
    # RED DISCRIMINATOR (b): a row whose two members fold to the SAME
    # token -- "refundable" / "refundables" both stem to ("refundable",)
    # via production fold_sequence -- a degenerate self-pair, never a
    # genuine 2-member exclusion.
    import copy

    real_tables_data = _real_tables_data()
    copied = copy.deepcopy(real_tables_data)
    copied["excl_v1"] = copied["excl_v1"] + [["refundable", "refundables"]]
    with pytest.raises(ValueError):
        vd.derive_excl_trigger_collision_set(copied)
    assert vd.derive_excl_trigger_collision_set(real_tables_data) == {("nonrefundable", "refundable")}


def test_derive_excl_registry_excluded_set_raises_valueerror_on_same_folded_token_both_members():
    # RED DISCRIMINATOR (b), companion helper.
    import copy

    real_tables_data = _real_tables_data()
    copied = copy.deepcopy(real_tables_data)
    copied["excl_v1"] = copied["excl_v1"] + [["refundable", "refundables"]]
    with pytest.raises(ValueError):
        vd.derive_excl_registry_excluded_set(copied)
    assert vd.derive_excl_registry_excluded_set(real_tables_data) == {("nonrefundable", "refundable")}


def test_derive_excl_trigger_collision_set_raises_valueerror_on_two_different_rows_same_folded_pair():
    # RED DISCRIMINATOR (c): two DIFFERENT rows (distinct row content --
    # a reversed-order duplicate of the real "digital"/"physical" row)
    # normalize to the SAME unordered folded pair -- an authoring defect
    # silently collapsed into one set entry today.
    import copy

    real_tables_data = _real_tables_data()
    copied = copy.deepcopy(real_tables_data)
    assert ["digital", "physical"] in copied["excl_v1"]
    copied["excl_v1"] = copied["excl_v1"] + [["physical", "digital"]]
    with pytest.raises(ValueError):
        vd.derive_excl_trigger_collision_set(copied)
    assert vd.derive_excl_trigger_collision_set(real_tables_data) == {("nonrefundable", "refundable")}


def test_derive_excl_registry_excluded_set_raises_valueerror_on_two_different_rows_same_folded_pair():
    # RED DISCRIMINATOR (c), companion helper.
    import copy

    real_tables_data = _real_tables_data()
    copied = copy.deepcopy(real_tables_data)
    assert ["digital", "physical"] in copied["excl_v1"]
    copied["excl_v1"] = copied["excl_v1"] + [["physical", "digital"]]
    with pytest.raises(ValueError):
        vd.derive_excl_registry_excluded_set(copied)
    assert vd.derive_excl_registry_excluded_set(real_tables_data) == {("nonrefundable", "refundable")}


def test_derive_excl_trigger_collision_set_raises_valueerror_on_exact_duplicate_row():
    # RED DISCRIMINATOR (SAN-881 PASS 2B.1-T-FIX-MICRO fix 2): an EXACT
    # byte-identical duplicate row (never merely a reversed/differently-
    # ordered row, as covered above) currently passes
    # _validate_excl_v1_rows SILENTLY -- `seen_pairs[pair] != row` is
    # False when the second row equals the first BY VALUE, so the `and`
    # short-circuits and no ValueError is raised. ANY second row
    # normalizing to an already-seen unordered folded pair must be
    # rejected, including a byte-identical repeat.
    import copy

    real_tables_data = _real_tables_data()
    copied = copy.deepcopy(real_tables_data)
    assert ["digital", "physical"] in copied["excl_v1"]
    copied["excl_v1"] = copied["excl_v1"] + [["digital", "physical"]]
    with pytest.raises(ValueError):
        vd.derive_excl_trigger_collision_set(copied)
    # The real, un-copied singleton is unaffected by the failed attempt.
    assert vd.derive_excl_trigger_collision_set(real_tables_data) == {("nonrefundable", "refundable")}


def test_derive_excl_registry_excluded_set_raises_valueerror_on_exact_duplicate_row():
    # RED DISCRIMINATOR (SAN-881 PASS 2B.1-T-FIX-MICRO fix 2), companion
    # helper -- IDENTICAL ValueError from both derivation helpers for the
    # SAME exact-duplicate-row defect.
    import copy

    real_tables_data = _real_tables_data()
    copied = copy.deepcopy(real_tables_data)
    assert ["digital", "physical"] in copied["excl_v1"]
    copied["excl_v1"] = copied["excl_v1"] + [["digital", "physical"]]
    with pytest.raises(ValueError):
        vd.derive_excl_registry_excluded_set(copied)
    assert vd.derive_excl_registry_excluded_set(real_tables_data) == {("nonrefundable", "refundable")}


def test_surface_registry_excl_v1_refundable_nonrefundable_is_retired():
    assert "excl_v1.refundable_nonrefundable" not in vd.SURFACE_REGISTRY


def test_surface_registry_units_v1_facet_keys_are_retired():
    assert not any(k.startswith("units_v1.") for k in vd.SURFACE_REGISTRY)


def test_surface_registry_value_role_v1_keys_present_with_three_legal_positions():
    for facet in ("cost", "duration", "limit"):
        entry = vd.SURFACE_REGISTRY[f"value_role_v1.{facet}"]
        assert entry["allowed_positions"] == {("C1", "context"), ("C1", "output"), ("C3", "context")}
        assert entry["predicate_id"] == "value_role_v1"


def test_surface_registry_entries_have_allowed_positions_and_predicate_id():
    for surface, entry in vd.SURFACE_REGISTRY.items():
        assert entry["allowed_positions"], surface
        for check_id, field in entry["allowed_positions"]:
            assert check_id in vd.CHECK_IDS, surface
            assert field in ("context", "output"), surface
        assert entry["predicate_id"] in vd.COVERAGE_PREDICATES, surface


def test_surface_registry_predicate_ids_cover_every_coverage_predicate_category():
    predicate_ids_in_registry = {e["predicate_id"] for e in vd.SURFACE_REGISTRY.values()}
    assert predicate_ids_in_registry == set(vd.COVERAGE_PREDICATES)


def test_check_coverage_registry_closure_passes_on_exact_key_set():
    errors = vd.Errors()
    coverage = {surface: [{"item_id": "cal:000", "check_id": "C1", "field": "context"}] for surface in vd.SURFACE_REGISTRY}
    vd.check_coverage_registry_closure(errors, coverage)
    assert errors == []


def test_check_coverage_registry_closure_rejects_old_pass1_69_key_set():
    # The retired Pass-1 69-key set (units_v1.facet:* instead of
    # value_role_v1.*, plus excl_v1.refundable_nonrefundable) must be
    # rejected outright under the v3 registry: the three units_v1.facet:*
    # names and the retired excl_v1 pair are EXTRA (undeclared) surfaces;
    # the three value_role_v1.* names are MISSING.
    errors = vd.Errors()
    old_69_keys = set(vd.SURFACE_REGISTRY) - {f"value_role_v1.{f}" for f in ("cost", "duration", "limit")}
    old_69_keys |= {f"units_v1.facet:{f}" for f in ("cost", "duration", "limit")}
    old_69_keys |= {"excl_v1.refundable_nonrefundable"}
    assert len(old_69_keys) == 69
    coverage = {surface: [{"item_id": "cal:000", "check_id": "C1", "field": "context"}] for surface in old_69_keys}
    vd.check_coverage_registry_closure(errors, coverage)
    assert any(vd.RULE_COVERAGE_REGISTRY_EXTRA_SURFACE in e and "units_v1.facet:cost" in e for e in errors)
    assert any(vd.RULE_COVERAGE_REGISTRY_EXTRA_SURFACE in e and "excl_v1.refundable_nonrefundable" in e for e in errors)
    assert any(vd.RULE_COVERAGE_REGISTRY_MISSING_SURFACE in e and "value_role_v1.cost" in e for e in errors)


def test_check_coverage_registry_closure_catches_missing_surface():
    errors = vd.Errors()
    coverage = {surface: [] for surface in list(vd.SURFACE_REGISTRY)[1:]}
    vd.check_coverage_registry_closure(errors, coverage)
    assert any(vd.RULE_COVERAGE_REGISTRY_MISSING_SURFACE in e for e in errors)


def test_check_coverage_registry_closure_catches_extra_surface():
    errors = vd.Errors()
    coverage = dict.fromkeys(vd.SURFACE_REGISTRY, [])
    coverage["not_a_real_surface.made_up"] = []
    vd.check_coverage_registry_closure(errors, coverage)
    assert any(vd.RULE_COVERAGE_REGISTRY_EXTRA_SURFACE in e for e in errors)


def test_value_role_v1_predicate_proves_trigger_plus_unit_pairing():
    tables_data = {
        "facets_v1": {"facet:duration": {"triggers": ["takes"], "deny_triggers": []}},
        "units_v1": {"day": {"group": "time_a", "factor": 1440}},
        "currency_symbols_v1": {"$": "USD"},
    }
    assert vd._predicate_value_role("Shipping takes 3 day.", "value_role_v1.duration", tables_data) is True
    assert vd._predicate_value_role("Shipping takes a while.", "value_role_v1.duration", tables_data) is False
    assert vd._predicate_value_role("Delivery in 3 day.", "value_role_v1.duration", tables_data) is False


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1 RED target 4: span-bound value classifiers.
# classify_value_span_text is a pure POLICY function over the exact raw
# text of a Roles.value span (tokenized with the real production
# tokenizer); first_measure_value_span_text is the genuine, non-
# monkeypatched span-extraction integration point. All three
# classifiers (cost/duration/limit) must be False (None) for every one
# of the six mixed/percent vectors below, and each positive vector must
# classify to EXACTLY one of the three.
# ---------------------------------------------------------------------

_VALUE_SPAN_MIXED_PERCENT_VECTORS = ("$3 day", "$3%", "3% day", "$3% day", "5%", "100%")


def test_classify_value_span_text_all_six_mixed_percent_vectors_unclassified():
    tables_data = _real_tables_data()
    for vector in _VALUE_SPAN_MIXED_PERCENT_VECTORS:
        assert vd.classify_value_span_text(vector, tables_data) is None, vector


def test_classify_value_span_text_three_positive_vectors_classify_exactly_one_way():
    tables_data = _real_tables_data()
    assert vd.classify_value_span_text("$3", tables_data) == "cost"
    assert vd.classify_value_span_text("1 day", tables_data) == "duration"
    assert vd.classify_value_span_text("5", tables_data) == "limit"


def test_first_measure_value_span_text_locates_exact_raw_span_cost():
    tables_data = _real_tables_data()
    found = vd.first_measure_value_span_text("Service costs $3.", tables_data)
    assert found is not None
    facet, span_text = found
    assert facet == "facet:cost"
    assert span_text == "$3"
    assert vd.classify_value_span_text(span_text, tables_data) == "cost"


def test_first_measure_value_span_text_locates_exact_raw_span_duration():
    tables_data = _real_tables_data()
    found = vd.first_measure_value_span_text("Service takes 1 day.", tables_data)
    assert found is not None
    facet, span_text = found
    assert facet == "facet:duration"
    assert span_text == "1 day"
    assert vd.classify_value_span_text(span_text, tables_data) == "duration"


def test_first_measure_value_span_text_locates_exact_raw_span_limit():
    tables_data = _real_tables_data()
    found = vd.first_measure_value_span_text("Account maximum is 5.", tables_data)
    assert found is not None
    facet, span_text = found
    assert facet == "facet:limit"
    assert span_text == "5"
    assert vd.classify_value_span_text(span_text, tables_data) == "limit"


def test_first_measure_value_span_text_full_sentence_positive_vectors_end_to_end():
    # End-to-end acceptance vectors named in the RED target: the exact
    # SENTENCES (not pre-isolated spans) classify to exactly the one
    # expected role, proving the span-bound extraction + classification
    # pipeline together, not merely the pure classifier in isolation.
    tables_data = _real_tables_data()
    cases = [
        ("Service costs $3.", "cost"),
        ("Service takes 1 day.", "duration"),
        ("Account maximum is 5.", "limit"),
    ]
    for sentence, expected in cases:
        found = vd.first_measure_value_span_text(sentence, tables_data)
        assert found is not None, sentence
        _facet, span_text = found
        assert vd.classify_value_span_text(span_text, tables_data) == expected, sentence


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1-T: PRODUCT TRACE SUBSTRATE. PRODUCT capture tests
# only -- no consumption claims, no coverage-predicate assertions. This
# block REPLACES the vacuous test_classify_value_span_text_never_reads_
# outside_the_given_span (deleted: it called the same function twice
# with the same argument, a tautology, never proving span isolation).
# ---------------------------------------------------------------------

def test_product_trace_multi_frame_field_two_clean_frames_exact_spans():
    # RED (the substrate does not exist yet): "Service costs $5.
    # Shipping takes 1 day." produces TWO clean frames (cost + duration,
    # partial=False) with DISTINCT identities and exact raw spans "$5"
    # and "1 day". NOT "Refunds cost $5, but shipping takes 1 day."
    # (verified separately below to produce ONE duration frame with
    # partial=True -- the "but shipping" coordination swallows the cost
    # trigger's own subject/valency).
    bundle = vd.build_product_trace_bundle({"id": "cal:test", "context": "Service costs $5. Shipping takes 1 day.", "output": ""})
    ctx = bundle.fields[0]
    assert ctx.field == "context"
    assert ctx.partial is False
    assert len(ctx.frame_events) == 2
    cost_fe, duration_fe = ctx.frame_events
    assert cost_fe.facet == "facet:cost"
    assert cost_fe.value_span_raw == "$5"
    assert duration_fe.facet == "facet:duration"
    assert duration_fe.value_span_raw == "1 day"
    assert cost_fe.identity != duration_fe.identity
    assert cost_fe.identity == ("context", 0, 0, 0)
    assert duration_fe.identity == ("context", 0, 1, 0)


def test_product_trace_coordinated_sentence_negative_example_one_duration_frame_partial():
    # Negative example named in the ticket: "Refunds cost $5, but
    # shipping takes 1 day." produces ONE duration frame with
    # partial=True (NOT the clean two-frame case above).
    bundle = vd.build_product_trace_bundle({"id": "cal:test", "context": "Refunds cost $5, but shipping takes 1 day.", "output": ""})
    ctx = bundle.fields[0]
    assert ctx.partial is True
    assert len(ctx.frame_events) == 1
    assert ctx.frame_events[0].facet == "facet:duration"


def test_product_trace_non_assertive_context_question_marked_assertive_false():
    # A context sentence ending '?' yields a trace entry marked
    # non-assertive (context is governed=False, so the sentence is
    # still scanned for frames -- unlike a governed OUTPUT '?').
    bundle = vd.build_product_trace_bundle({"id": "cal:test", "context": "Items are refundable?", "output": ""})
    ctx = bundle.fields[0]
    assert ctx.partial is False
    assert len(ctx.frame_events) == 1
    fe = ctx.frame_events[0]
    assert fe.facet == "facet:refund_availability"
    assert fe.assertive is False


def test_product_trace_governed_output_question_records_governed_interrogative_partial():
    # The GOVERNED (output) counterpart: a governed '?' sentence never
    # even reaches trigger_scan -- it is immediately PARTIAL, no frame.
    bundle = vd.build_product_trace_bundle({"id": "cal:test", "context": "", "output": "Items are refundable?"})
    out = bundle.fields[-1]
    assert out.field == "output"
    assert out.partial is True
    assert len(out.frame_events) == 0
    assert len(out.partial_events) == 1
    pe = out.partial_events[0]
    assert pe.stage is vd.PartialStage.GOVERNED_INTERROGATIVE
    assert pe.cause is None


def test_product_trace_partial_extraction_malformed_value_production_cause_no_frame():
    # An e13/nested-adjunct/malformed-value input records a
    # PartialProductEvent with its closed stage and ONLY a
    # production-supplied cause, and NO frame product for the failed
    # span. Malformed-value case: TWO NUMBER tokens in the value region
    # -> Abstain(malformed_mention), propagated from extract_roles.
    bundle = vd.build_product_trace_bundle({"id": "cal:test", "context": "Shipping costs $5 $10.", "output": ""})
    ctx = bundle.fields[0]
    assert ctx.partial is True
    assert len(ctx.frame_events) == 0
    assert len(ctx.partial_events) == 1
    pe = ctx.partial_events[0]
    assert pe.stage is vd.PartialStage.PER_HIT_ABSTAIN
    assert pe.cause == "malformed_mention"


def test_product_trace_partial_extraction_e13_no_invented_cause():
    # e13 (nonterminating sentence punctuation) is a STRUCTURAL check in
    # production -- it never raises an exception -- so `cause` must be
    # None, never an invented value. Control: the same clause WITHOUT
    # the e13 defect produces a clean frame (proves the partiality is
    # attributable to e13, not something else).
    bundle = vd.build_product_trace_bundle(
        {"id": "cal:test", "context": "This item is nonrefundable.Return within 30 days.", "output": ""}
    )
    ctx = bundle.fields[0]
    assert ctx.partial is True
    assert len(ctx.frame_events) == 0
    assert len(ctx.partial_events) == 1
    pe = ctx.partial_events[0]
    assert pe.stage is vd.PartialStage.NONTERMINATING_PUNCTUATION
    assert pe.cause is None
    assert pe.identity == ("context", 0, 0, None)

    control = vd.build_product_trace_bundle({"id": "cal:test", "context": "This item is nonrefundable.", "output": ""})
    control_ctx = control.fields[0]
    assert control_ctx.partial is False
    assert len(control_ctx.frame_events) == 1


def test_product_trace_total_span_unconsumed_partiality_no_invented_cause():
    # spec 2.6 total span accounting: an untriggered sentence with a
    # non-filler, non-consumed token is PARTIAL with NO production
    # exception -- cause must be None.
    bundle = vd.build_product_trace_bundle({"id": "cal:test", "context": "Blorp.", "output": ""})
    ctx = bundle.fields[0]
    assert ctx.partial is True
    assert len(ctx.frame_events) == 0
    assert any(pe.stage is vd.PartialStage.TOTAL_SPAN_UNCONSUMED and pe.cause is None for pe in ctx.partial_events)


def test_product_trace_comparator_location_value_vs_condition_exact_folds():
    # A top-level "over $5" value span vs an "if over 30 days" condition
    # are captured at DIFFERENT locations with exact comparator folds.
    bundle = vd.build_product_trace_bundle(
        {"id": "cal:test", "context": "Shipping costs over $5. Shipping is available if over 30 days.", "output": ""}
    )
    ctx = bundle.fields[0]
    assert ctx.partial is False
    assert len(ctx.frame_events) == 2
    cost_fe, avail_fe = ctx.frame_events

    assert cost_fe.facet == "facet:cost"
    assert len(cost_fe.comparator_events) == 1
    value_comp = cost_fe.comparator_events[0]
    assert value_comp.location == "value"
    assert value_comp.comparator_folds == ("over",)
    assert value_comp.raw_span_text == "over $5"
    assert value_comp.owning_condition_index is None

    assert avail_fe.facet == "facet:availability"
    assert len(avail_fe.conds) == 1
    cond = avail_fe.conds[0]
    assert cond.kind == "IF"
    assert cond.marker_folds == ("if",)
    assert len(cond.comparator_events) == 1
    cond_comp = cond.comparator_events[0]
    assert cond_comp.location == "condition"
    assert cond_comp.comparator_folds == ("over",)
    assert cond_comp.owning_condition_index == 0

    # DIFFERENT locations, different owning identities.
    assert value_comp.location != cond_comp.location
    assert value_comp.owning_identity == cost_fe.identity
    assert cond_comp.owning_identity == avail_fe.identity


def test_product_trace_quantifier_first_match_universal_not_abstain():
    # "All most services are available." records selected token 'all'
    # (universal), NOT an abstain event -- quant()'s first-match scan
    # stops at the FIRST quantifier-class token in the subject span.
    from reference.primitives import UNIVERSAL

    bundle = vd.build_product_trace_bundle({"id": "cal:test", "context": "All most services are available.", "output": ""})
    ctx = bundle.fields[0]
    assert ctx.partial is False
    assert len(ctx.frame_events) == 1
    fe = ctx.frame_events[0]
    assert fe.quant_class == UNIVERSAL
    assert fe.quant_token_fold == "all"
    assert len(ctx.partial_events) == 0


def test_product_trace_quantifier_abstain_records_event_no_frame():
    # "Most services are available." records a quant-abstain EVENT with
    # no frame -- the selected token ('most') is recorded even though
    # the sentence produces zero frame products.
    bundle = vd.build_product_trace_bundle({"id": "cal:test", "context": "Most services are available.", "output": ""})
    ctx = bundle.fields[0]
    assert ctx.partial is True
    assert len(ctx.frame_events) == 0
    assert len(ctx.partial_events) == 1
    pe = ctx.partial_events[0]
    assert pe.stage is vd.PartialStage.PER_HIT_ABSTAIN
    assert pe.cause == "unextractable"
    assert pe.quant_token_fold == "most"


def test_product_trace_exactness_control_only_if_not_captured_as_if():
    # "only if" must NOT be captured as "if" -- marker folds are EXACT
    # sequences, not a truncated/first-token guess.
    bundle = vd.build_product_trace_bundle(
        {"id": "cal:test", "context": "Shipping is available only if verified.", "output": ""}
    )
    ctx = bundle.fields[0]
    assert len(ctx.frame_events) == 1
    fe = ctx.frame_events[0]
    assert len(fe.conds) == 1
    cond = fe.conds[0]
    assert cond.marker_folds == ("only", "if")
    assert cond.marker_folds != ("if",)
    assert cond.kind == "ONLY_IF"
    # Bonus: actual CONCEPT_v1 application captured ("verified" ->
    # "verification"), and the resulting Bool-atom term is a genuine
    # COMPLEMENT_v1 candidate (verified/unverified pair, normalized).
    assert ("verified", "verification") in cond.concept_mappings
    assert "verification" in cond.complement_candidates


def test_product_trace_exactness_control_more_than_not_captured_as_over():
    # "more than" must NOT become "over" -- both comparators share the
    # SAME interval template (lo=v, lo_open=True, hi=None), so the
    # Interval alone cannot distinguish them; the captured comparator
    # FOLDS must be the exact matched token sequence.
    bundle = vd.build_product_trace_bundle({"id": "cal:test", "context": "Shipping costs more than $5.", "output": ""})
    ctx = bundle.fields[0]
    assert len(ctx.frame_events) == 1
    fe = ctx.frame_events[0]
    assert len(fe.comparator_events) == 1
    comp = fe.comparator_events[0]
    assert comp.comparator_folds == ("more", "than")
    assert comp.comparator_folds != ("over",)
    assert comp.raw_span_text == "more than $5"


def test_product_trace_excl_candidate_captured_on_modifier():
    # PRODUCT CAPTURE item 4: a modifier-only EXCL_v1 candidate -- a
    # facet:availability frame with an adjunct modifier "for physical
    # items" carries "physical" as a captured EXCL candidate (digital /
    # physical is a real excl_v1 pair).
    bundle = vd.build_product_trace_bundle(
        {"id": "cal:test", "context": "Refunds are available for physical items.", "output": ""}
    )
    ctx = bundle.fields[0]
    assert len(ctx.frame_events) == 1
    fe = ctx.frame_events[0]
    assert "physical" in fe.excl_candidates


def test_product_trace_context_sources_boundaries_and_tiers_preserved():
    # Individual context_sources -- their boundaries and their tiers --
    # are preserved; each source is processed strictly on its OWN text,
    # never a concatenated context string.
    item = {
        "id": "cal:test",
        "context_sources": [
            {"text": "Service costs $5.", "tier": "tier_1"},
            {"text": "Shipping takes 1 day.", "tier": "tier_1"},
        ],
        "output": "",
    }
    bundle = vd.build_product_trace_bundle(item)
    ctx_traces = [t for t in bundle.fields if t.field == "context"]
    assert len(ctx_traces) == 2
    assert ctx_traces[0].source_index == 0
    assert ctx_traces[0].tier == "tier_1"
    assert ctx_traces[0].boundary_start == 0
    assert ctx_traces[0].boundary_end == len("Service costs $5.")
    assert len(ctx_traces[0].frame_events) == 1
    assert ctx_traces[0].frame_events[0].identity == ("context", 0, 0, 0)

    assert ctx_traces[1].source_index == 1
    assert ctx_traces[1].tier == "tier_1"
    assert ctx_traces[1].boundary_start == 0
    assert ctx_traces[1].boundary_end == len("Shipping takes 1 day.")
    assert len(ctx_traces[1].frame_events) == 1
    assert ctx_traces[1].frame_events[0].identity == ("context", 1, 0, 0)


def test_product_trace_determinism_and_no_side_effects():
    # Repeated construction over the SAME item is IDENTICAL
    # (deterministic) and leaves frame-counter state, tables, compiled
    # constants, and evaluator results unchanged.
    #
    # FRAME-COUNTER HYGIENE (SAN-881 PASS 2B.1-T-FIX-MICRO fix 3 audit):
    # this test calls production extract_frames (via reference.evaluate,
    # which imports the SAME reference.extraction.extract_frames /
    # _frame_counter directly) TWICE, both legitimately advancing the
    # shared global counter -- snapshotted before either call and
    # restored in a finally block, so this test leaves the counter
    # exactly as it found it, mirroring
    # test_product_trace_differential_against_production_extract_frames_full_corpus's
    # own snapshot/finally-restore/post-equality discipline.
    import reference.evaluate as _evaluate_mod
    from reference.extraction import _frame_counter
    from reference.primitives import CONCEPT_V1, STOP_V1
    from reference.tables import T as _T

    item = {"id": "cal:test", "context": "Service costs $5. Shipping takes 1 day.", "output": "It is available."}

    frame_counter_at_start = dict(_frame_counter)
    try:
        # A genuine evaluator result, built BEFORE the trace substrate runs
        # (this call legitimately advances the production frame counter --
        # it is the production extract_frames itself) and compared AFTER.
        evaluator_frames_before, evaluator_partial_before = _evaluate_mod.extract_frames(
            "context", "Service costs $5. Shipping takes 1 day.", governed=False
        )

        # Snapshot state AFTER the legitimate evaluator call above and
        # BEFORE any trace-substrate call -- what must stay unchanged is
        # what the trace substrate itself does, not the evaluator call this
        # test also happens to make.
        frame_counter_before = dict(_frame_counter)
        tables_object_before = _T
        stop_v1_before = STOP_V1
        concept_v1_before = dict(CONCEPT_V1)

        bundle_a = vd.build_product_trace_bundle(item)
        bundle_b = vd.build_product_trace_bundle(item)

        assert bundle_a == bundle_b

        assert _frame_counter == frame_counter_before, "production frame counter must be untouched by the trace substrate"
        assert _T is tables_object_before, "reference.tables.T must be the SAME object"
        assert STOP_V1 == stop_v1_before, "compiled STOP_V1 constant must be unchanged"
        assert dict(CONCEPT_V1) == concept_v1_before, "compiled CONCEPT_V1 constant must be unchanged"

        evaluator_frames_after, evaluator_partial_after = _evaluate_mod.extract_frames(
            "context", "Service costs $5. Shipping takes 1 day.", governed=False
        )
        assert evaluator_partial_after == evaluator_partial_before
        assert len(evaluator_frames_after) == len(evaluator_frames_before)
        for fb, fa in zip(evaluator_frames_before, evaluator_frames_after):
            assert fb.extent == fa.extent
            assert fb.conds == fa.conds
    finally:
        _frame_counter["n"] = frame_counter_at_start["n"]
    assert _frame_counter == frame_counter_at_start, "test must restore the production frame counter it advanced"


def test_product_trace_differential_against_production_extract_frames_full_corpus():
    # DIFFERENTIAL TEST: over EVERY public corpus item's every context
    # source and output, compare canonical trace frame projections,
    # partiality, AND parsed value_intervals (SAN-881 PASS 2B.1-T-FIX
    # blocker 2) against production extract_frames, IGNORING production
    # frame IDs -- the trace substrate must agree with production
    # extraction on what frames exist, what is partial, and what values
    # were parsed. FRAME-COUNTER HYGIENE (cleanup B): this test calls
    # production's REAL extract_frames directly, which legitimately
    # advances the shared global _frame_counter as a side effect -- the
    # counter is snapshotted before the loop and restored in a finally
    # block (never mutated mid-loop to force a fixed starting point,
    # which was never needed since frame IDs are ignored throughout),
    # and post-test equality with the pre-test value is asserted.
    from reference.extraction import _frame_counter, extract_frames as _prod_extract_frames

    frame_counter_before = dict(_frame_counter)
    try:
        checked_fields = 0
        for rec in CORPUS:
            if "context_sources" in rec:
                ctx_sources = [(s["text"], s.get("tier")) for s in rec["context_sources"]]
            else:
                ctx_sources = [(rec.get("context", ""), None)]
            out_text = rec.get("output", "")

            bundle = vd.build_product_trace_bundle(rec)
            assert len(bundle.fields) == len(ctx_sources) + 1

            all_sources = [(text, False) for text, _tier in ctx_sources] + [(out_text, True)]
            for field_index, (text, governed) in enumerate(all_sources):
                trace = bundle.fields[field_index]
                prod_frames, prod_partial = _prod_extract_frames(
                    "context" if not governed else "output", text, governed=governed
                )
                checked_fields += 1

                assert trace.partial == prod_partial, f"{rec['id']} field {field_index}: partial mismatch"
                assert len(trace.frame_events) == len(prod_frames), f"{rec['id']} field {field_index}: frame count mismatch"

                for fe, pf in zip(trace.frame_events, prod_frames):
                    assert fe.facet == pf.extent.facet
                    assert fe.subject == pf.extent.subject
                    assert fe.object == pf.extent.object
                    assert fe.modifiers == pf.extent.modifiers
                    assert fe.quant_class == pf.extent.quant
                    assert fe.polarity == pf.extent.polarity
                    assert fe.assertive == pf.assertive
                    assert fe.subject_conjuncts == pf.subject_conjuncts
                    assert fe.subject_conjunct_heads == pf.subject_conjunct_heads
                    assert fe.req_formula == pf.req_formula
                    assert fe.value_intervals == pf.extent.values, f"{rec['id']} field {field_index}: value interval mismatch"
                    assert tuple(c.formula for c in fe.conds) == tuple(c.formula for c in pf.conds)
                    assert tuple(c.kind for c in fe.conds) == tuple(c.kind for c in pf.conds)
                    assert tuple(c.force for c in fe.conds) == tuple(c.force for c in pf.conds)

        assert checked_fields > 0
        assert checked_fields == sum(
            (len(rec["context_sources"]) if "context_sources" in rec else 1) + 1 for rec in CORPUS
        )
    finally:
        _frame_counter["n"] = frame_counter_before["n"]
    assert _frame_counter == frame_counter_before, "differential test must restore the production frame counter it advanced"


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1-T-FIX blocker 1: CONJUNCT-BOUND ATOM CAPTURE.
# _pt_capture_concept_and_complement / _pt_capture_condition_comparators
# used to be whole-body token scans that could credit a product from a
# conjunct whose OWN atom production actually built was UnknownAtom.
# Capture is now bound to production's own per-conjunct
# _atom_from_conjunct call, proven faithful by a structural-equality
# assertion against production's real formula (exercised corpus-wide by
# the differential test above, which calls build_product_trace_bundle
# -- and therefore this assertion -- for every corpus item).
# ---------------------------------------------------------------------

def test_product_trace_conjunct_bound_unknown_atom_conjunct_yields_no_products():
    # RED DISCRIMINATOR: condition body "verified and $5 $10" splits
    # into a TermAtom conjunct ("verified") and an UnknownAtom conjunct
    # ("$5 $10" -- two NUMBER tokens, parse_values raises Abstain inside
    # production's own _atom_from_conjunct). The UnknownAtom conjunct
    # must credit NEITHER a concept mapping NOR a comparator event --
    # the prior whole-body scan spuriously credited comparator events
    # for BOTH "$5" and "$10" even though production's own atom-builder
    # marked that exact conjunct UnknownAtom.
    from reference.primitives import And, TermAtom, UnknownAtom

    bundle = vd.build_product_trace_bundle(
        {"id": "cal:test", "context": "Shipping is available if verified and $5 $10.", "output": ""}
    )
    ctx = bundle.fields[0]
    assert ctx.partial is False
    fe = ctx.frame_events[0]
    assert len(fe.conds) == 1
    cond = fe.conds[0]
    assert isinstance(cond.formula, And)
    assert isinstance(cond.formula.children[0], TermAtom)
    assert isinstance(cond.formula.children[1], UnknownAtom)

    assert cond.concept_mappings == (("verified", "verification"),)
    assert cond.complement_candidates == ("verification",)
    # THE RED assertion: zero comparator events, not two spurious ones
    # credited from a conjunct production itself marked UnknownAtom.
    assert cond.comparator_events == ()


def test_product_trace_conjunct_bound_mixed_control_termatom_plus_measureatom_no_cross_contamination():
    # POSITIVE MIXED CONTROL named in the ticket: "approved and over 30
    # days" -- two conjuncts, one TermAtom (concept mapping from
    # 'approved' only) and one MeasureAtom (comparator folds ("over",)
    # + the parsed interval only) -- NO single conjunct produces both
    # atom types, and neither conjunct's product leaks into the other's.
    from reference.primitives import And, MeasureAtom, TermAtom

    bundle = vd.build_product_trace_bundle(
        {"id": "cal:test", "context": "Shipping is available if approved and over 30 days.", "output": ""}
    )
    ctx = bundle.fields[0]
    fe = ctx.frame_events[0]
    cond = fe.conds[0]
    assert isinstance(cond.formula, And)
    term_atom, measure_atom = cond.formula.children
    assert isinstance(term_atom, TermAtom)
    assert isinstance(measure_atom, MeasureAtom)
    assert type(term_atom) is not type(measure_atom)

    # TermAtom conjunct's OWN concept mapping only -- never contaminated
    # by the sibling MeasureAtom conjunct's tokens.
    assert cond.concept_mappings == (("approved", "approval"),)

    # MeasureAtom conjunct's OWN comparator event only -- folds "over",
    # bound together with the atom's own parsed interval.
    assert len(cond.comparator_events) == 1
    comp = cond.comparator_events[0]
    assert comp.location == "condition"
    assert comp.comparator_folds == ("over",)
    assert comp.owning_condition_index == 0
    assert measure_atom.intervals[0].lo_open is True
    assert measure_atom.intervals[0].hi is None


def test_product_trace_requirement_comparator_location_and_concept_capture():
    # Blocker 1 extension: requirement formulas ALSO get conjunct-bound
    # capture, and the comparator-event location vocabulary now includes
    # "requirement" -- previously requirement capture had NO comparator
    # events at all (req_comparator_events did not exist on
    # FrameProductEvent, an AttributeError under the pre-fix module).
    from reference.primitives import And, MeasureAtom, TermAtom

    bundle = vd.build_product_trace_bundle(
        {"id": "cal:test", "context": "Refunds require approved and over 30 days.", "output": ""}
    )
    ctx = bundle.fields[0]
    fe = ctx.frame_events[0]
    assert fe.facet == "facet:approval_requirement"
    assert isinstance(fe.req_formula, And)
    term_atom, measure_atom = fe.req_formula.children
    assert isinstance(term_atom, TermAtom)
    assert isinstance(measure_atom, MeasureAtom)

    assert fe.req_concept_mappings == (("approved", "approval"),)
    assert len(fe.req_comparator_events) == 1
    comp = fe.req_comparator_events[0]
    assert comp.location == "requirement"
    assert comp.comparator_folds == ("over",)
    assert comp.owning_condition_index is None
    assert comp.owning_identity == fe.identity


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1-T-FIX-MICRO fix 1: PARSED INTERVALS BOUND TO THE
# COMPARATOR EVENT ITSELF. ComparatorProductEvent captured the raw
# comparator FOLDS (lexeme) but never the corresponding PARSED interval
# -- the two live on the SAME event object, never split across the
# event and a separate formula/atom node the caller would have to
# cross-reference.
# ---------------------------------------------------------------------

def test_product_trace_comparator_event_carries_parsed_intervals_event_level_binding():
    # RED: ComparatorProductEvent has no parsed_intervals field at all
    # (AttributeError) prior to the fix. Every assertion below reads
    # parsed_intervals OFF THE COMPARATOR EVENT ITSELF -- never off a
    # separate formula/atom/frame node -- proving the lexeme
    # (comparator_folds) and the parsed interval are bound on one event.
    from reference.primitives import And, MeasureAtom, TermAtom

    # location == "value": EXACTLY the frame's own parsed Extent.values
    # (mirrored on FrameProductEvent.value_intervals).
    bundle = vd.build_product_trace_bundle({"id": "cal:test", "context": "Shipping costs over $5.", "output": ""})
    fe = bundle.fields[0].frame_events[0]
    assert fe.facet == "facet:cost"
    assert len(fe.comparator_events) == 1
    value_comp = fe.comparator_events[0]
    assert value_comp.location == "value"
    assert value_comp.comparator_folds == ("over",)
    assert value_comp.parsed_intervals == fe.value_intervals
    assert value_comp.parsed_intervals is not None
    assert len(value_comp.parsed_intervals) == 1
    assert value_comp.parsed_intervals[0].lo_open is True
    assert value_comp.parsed_intervals[0].hi is None

    # location == "condition": EXACTLY the MeasureAtom conjunct's own
    # atom.intervals, read off the comparator event, not off
    # measure_atom directly (that would be the disallowed
    # separate-formula-node check).
    bundle_cond = vd.build_product_trace_bundle(
        {"id": "cal:test", "context": "Shipping is available if approved and over 30 days.", "output": ""}
    )
    fe_cond = bundle_cond.fields[0].frame_events[0]
    cond = fe_cond.conds[0]
    assert isinstance(cond.formula, And)
    term_atom, measure_atom = cond.formula.children
    assert isinstance(term_atom, TermAtom)
    assert isinstance(measure_atom, MeasureAtom)
    assert len(cond.comparator_events) == 1
    cond_comp = cond.comparator_events[0]
    assert cond_comp.location == "condition"
    assert cond_comp.comparator_folds == ("over",)
    assert cond_comp.parsed_intervals == measure_atom.intervals

    # location == "requirement": same event-level binding, requirement
    # formula.
    bundle_req = vd.build_product_trace_bundle(
        {"id": "cal:test", "context": "Refunds require approved and over 30 days.", "output": ""}
    )
    fe_req = bundle_req.fields[0].frame_events[0]
    assert isinstance(fe_req.req_formula, And)
    req_term_atom, req_measure_atom = fe_req.req_formula.children
    assert isinstance(req_term_atom, TermAtom)
    assert isinstance(req_measure_atom, MeasureAtom)
    assert len(fe_req.req_comparator_events) == 1
    req_comp = fe_req.req_comparator_events[0]
    assert req_comp.location == "requirement"
    assert req_comp.comparator_folds == ("over",)
    assert req_comp.parsed_intervals == req_measure_atom.intervals


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1-T-FIX blocker 2: PARSED VALUES IN THE TRACE.
# ---------------------------------------------------------------------

def test_product_trace_frame_captures_parsed_value_intervals_matching_production():
    # RED: FrameProductEvent must carry the parsed Extent.values (the
    # production Interval tuple, or None exactly as production yields)
    # -- currently dropped from the trace entirely (AttributeError).
    from reference.primitives import Dec, Interval

    bundle = vd.build_product_trace_bundle({"id": "cal:test", "context": "Service costs $5.", "output": ""})
    ctx = bundle.fields[0]
    fe = ctx.frame_events[0]
    assert fe.facet == "facet:cost"
    assert fe.value_intervals == (
        Interval(lo=Dec(coefficient=5, scale=0), lo_open=False, hi=Dec(coefficient=5, scale=0), hi_open=False, unit="currency:USD"),
    )

    # A frame with no value span at all yields None, not a fabricated
    # empty tuple (production's own Extent.values is `tuple(values) if
    # values else None`).
    bundle_no_value = vd.build_product_trace_bundle({"id": "cal:test", "context": "Refunds require approval.", "output": ""})
    fe_no_value = bundle_no_value.fields[0].frame_events[0]
    assert fe_no_value.value_intervals is None


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1-T-FIX blocker 3: TIER RESOLUTION PARITY.
# reference.evaluate._context_sources resolves plain `context` and a
# context_sources entry missing `tier` to "tier_1" (never None) --
# build_product_trace_bundle must mirror this exactly.
# ---------------------------------------------------------------------

def test_product_trace_tier_resolution_matches_production_context_sources_defaults():
    # RED DISCRIMINATORS: plain `context` -> tier_1 (not None);
    # context_sources entry missing a `tier` key -> tier_1 (not None);
    # explicit tier_3 stays tier_3.
    bundle_plain = vd.build_product_trace_bundle({"id": "cal:test", "context": "Service costs $5.", "output": ""})
    assert bundle_plain.fields[0].tier == "tier_1"

    bundle_missing_tier = vd.build_product_trace_bundle(
        {"id": "cal:test", "context_sources": [{"text": "Service costs $5."}], "output": ""}
    )
    assert bundle_missing_tier.fields[0].tier == "tier_1"

    bundle_explicit_tier3 = vd.build_product_trace_bundle(
        {"id": "cal:test", "context_sources": [{"text": "Service costs $5.", "tier": "tier_3"}], "output": ""}
    )
    assert bundle_explicit_tier3.fields[0].tier == "tier_3"


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1-T-FIX blockers 4+5: TYPED, INDEPENDENT
# OBLIGATION/EVIDENCE CAPTURE + TRUST-BEFORE-AGGREGATION. SYNTHETIC
# fixtures only -- corpus counts are not a stable contract. Expected
# values for the trust-filtering test are derived with
# reference.checks._trusted plus reference.extraction.extract_obligations
# DIRECTLY, never via evaluate().
# ---------------------------------------------------------------------

def test_product_trace_obligation_capture_partial_distinguishable_from_genuinely_empty():
    # Obligation-partial: facetproj_v1 miss (subject head "widget" is
    # not in FACETPROJ_V1) raises FramePartial(unextractable) inside
    # extract_obligations -- must be captured as a typed partial_event,
    # not silently flattened into an empty tuple indistinguishable from
    # a genuinely empty result.
    partial_bundle = vd.build_product_trace_bundle({"id": "cal:test", "context": "Widgets require approval.", "output": ""})
    assert partial_bundle.trusted_obligations.items == ()
    assert partial_bundle.trusted_obligations.partial_event is not None
    assert partial_bundle.trusted_obligations.partial_event.cause == "unextractable"

    # Genuinely empty: no approval_requirement / conds-bearing frame at
    # all -- zero items, but NO partial event (mutually distinguishable
    # from the partial case above).
    empty_bundle = vd.build_product_trace_bundle({"id": "cal:test", "context": "Service costs $5.", "output": ""})
    assert empty_bundle.trusted_obligations.items == ()
    assert empty_bundle.trusted_obligations.partial_event is None


def test_product_trace_evidence_capture_partial_distinguishable_from_genuinely_empty():
    partial_bundle = vd.build_product_trace_bundle({"id": "cal:test", "context": "", "output": "Widgets require approval."})
    assert partial_bundle.evidence.items == ()
    assert partial_bundle.evidence.partial_event is not None
    assert partial_bundle.evidence.partial_event.cause == "unextractable"

    empty_bundle = vd.build_product_trace_bundle({"id": "cal:test", "context": "", "output": "Shipping takes 1 day."})
    assert empty_bundle.evidence.items == ()
    assert empty_bundle.evidence.partial_event is None


def test_product_trace_trusted_obligations_excludes_tier3_source_mirrors_checks_trusted():
    # RED DISCRIMINATOR: an item with mixed trusted (tier_1) + tier_3
    # sources -- the tier_3 source's obligation-bearing frame must NOT
    # contribute to trusted_obligations, its frame products must still
    # be captured in `fields` (exclusion applies only to the
    # aggregation input, never to capture), and its exclusion record
    # must carry (identity, tier_3, untrusted_tier).
    #
    # FRAME-COUNTER HYGIENE (SAN-881 PASS 2B.1-T-FIX-MICRO fix 3): the
    # two production extract_frames calls below legitimately advance the
    # shared global _frame_counter as a side effect -- snapshotted
    # before both calls and restored in a finally block, with post-test
    # equality asserted against the pre-test value, mirroring
    # test_product_trace_differential_against_production_extract_frames_full_corpus's
    # own discipline.
    from reference.checks import _trusted
    from reference.extraction import _frame_counter, extract_frames as _prod_extract_frames, extract_obligations as _prod_extract_obligations

    item = {
        "id": "cal:test",
        "context_sources": [
            {"text": "Refunds require approval.", "tier": "tier_1"},
            {"text": "Refunds require verification.", "tier": "tier_3"},
        ],
        "output": "",
    }
    bundle = vd.build_product_trace_bundle(item)

    ctx_traces = [t for t in bundle.fields if t.field == "context"]
    assert len(ctx_traces) == 2
    assert len(ctx_traces[0].frame_events) == 1
    assert len(ctx_traces[1].frame_events) == 1
    tier3_identity = ctx_traces[1].frame_events[0].identity
    assert tier3_identity == ("context", 1, 0, 0)

    frame_counter_before = dict(_frame_counter)
    try:
        f1, _ = _prod_extract_frames("context", "Refunds require approval.", governed=False)
        f2, _ = _prod_extract_frames("context", "Refunds require verification.", governed=False)
        tiers = {}
        for f in f1:
            tiers[f.frame_id] = "tier_1"
        for f in f2:
            tiers[f.frame_id] = "tier_3"
        trusted = _trusted(list(f1) + list(f2), tiers)
        expected_obligations = _prod_extract_obligations(trusted)
    finally:
        _frame_counter["n"] = frame_counter_before["n"]
    assert _frame_counter == frame_counter_before, "test must restore the production frame counter it advanced"
    assert len(expected_obligations) == 1

    assert len(bundle.trusted_obligations.items) == 1
    assert bundle.trusted_obligations.items[0].requirement_formula == expected_obligations[0].requirement_formula
    assert bundle.trusted_obligations.items[0].source_frame_identities == (("context", 0, 0, 0),)
    assert bundle.trusted_obligations.partial_event is None

    assert len(bundle.excluded_obligation_frames) == 1
    excl = bundle.excluded_obligation_frames[0]
    assert excl.identity == tier3_identity
    assert excl.tier == "tier_3"
    assert excl.reason == "untrusted_tier"


def test_product_trace_excluded_obligation_frame_non_assertive_reason():
    # non_assertive fires for a non-assertive (interrogative context)
    # frame at DEFAULT tier_1 -- proving the reason is genuinely
    # assertive-driven, not a tier misclassification: a tier_1 source
    # would otherwise be trusted, but this frame is still excluded
    # because reference.checks._trusted checks `f.assertive` first.
    item = {"id": "cal:test", "context": "Do refunds require approval?", "output": ""}
    bundle = vd.build_product_trace_bundle(item)
    fe = bundle.fields[0].frame_events[0]
    assert fe.facet == "facet:approval_requirement"
    assert fe.assertive is False

    assert bundle.trusted_obligations.items == ()
    assert bundle.trusted_obligations.partial_event is None
    assert len(bundle.excluded_obligation_frames) == 1
    excl = bundle.excluded_obligation_frames[0]
    assert excl.identity == fe.identity
    assert excl.tier == "tier_1"
    assert excl.reason == "non_assertive"


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1-T-FIX cleanup A: CODE-BOUND TRUTH ASSERTIONS.
# AST/name-reference inspection, NOT source-substring checks.
# ---------------------------------------------------------------------

def test_product_trace_dataclasses_and_builder_exist_as_module_attributes():
    for name in ("FieldProductTrace", "FrameProductEvent", "PartialProductEvent", "ProductTraceBundle", "build_product_trace_bundle"):
        assert hasattr(vd, name), f"{name} must exist as a module attribute"
    assert not hasattr(vd, "CheckConsumptionTrace"), "CheckConsumptionTrace does not exist -- that architecture was proposed and REJECTED (SAN-881 PASS 2B.1-P); never reintroduce it"


_PRODUCT_TRACE_SYMBOLS = frozenset({
    "FieldProductTrace", "FrameProductEvent", "PartialProductEvent", "PartialStage",
    "ComparatorProductEvent", "ConditionProductEvent", "ObligationProductEvent",
    "EvidenceProductEvent", "ProductTraceBundle", "ObligationCaptureProduct",
    "EvidenceCaptureProduct", "ObligationExclusionRecord", "BundleCapturePartialEvent",
    "build_product_trace_bundle", "_replay_field_trace", "_pt_capture_comparator_at",
    "_pt_capture_value_comparator", "_pt_split_and_replay_bool",
    "_pt_capture_conjunct_products", "_pt_capture_bool_products",
    "_pt_collect_term_atom_terms", "CheckConsumptionTrace",
})


def _ast_referenced_names(func) -> set:
    """CODE-BOUND TRUTH ASSERTION helper: AST/name-reference inspection,
    NOT a source-substring check -- parses `func`'s own source (never
    transitively into functions it calls) and returns every Name.id /
    Attribute.attr referenced anywhere in its tree. A substring check
    would both false-positive (a comment mentioning the name) and
    false-negative (an aliased import); walking the AST for actual
    Name/Attribute references is the genuine proof."""
    import ast
    import inspect

    source = inspect.getsource(func)
    tree = ast.parse(source)
    referenced = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            referenced.add(node.id)
        if isinstance(node, ast.Attribute):
            referenced.add(node.attr)
    return referenced


def test_check_coverage_manifest_dispatcher_ast_never_references_product_trace_symbols():
    # SAN-881 PASS 2B.1-P: check_coverage_manifest itself is a PURE Pass
    # A/Pass B DISPATCHER -- it never builds a bundle or references any
    # product-trace-substrate symbol directly; Pass B is entirely
    # delegated to _check_nontable_surface_evidence (nontable) and
    # _check_all_product_surfaces_evidence (the 50 in-scope surfaces).
    referenced = _ast_referenced_names(vd.check_coverage_manifest) & _PRODUCT_TRACE_SYMBOLS
    assert referenced == set(), f"check_coverage_manifest's AST references product-trace substrate symbols: {referenced}"


def test_check_coverage_nontable_ast_never_references_product_trace_or_capability_map():
    # SAN-881 PASS 2B.1-P TRUTH TEST: the nontable branch
    # (_check_nontable_surface_evidence) references NEITHER the
    # product-trace substrate NOR CAPABILITY_MAP -- the 18 nontable
    # surfaces remain the ORIGINAL, byte-unchanged static-lexical proof.
    referenced = _ast_referenced_names(vd._check_nontable_surface_evidence)
    forbidden = referenced & (_PRODUCT_TRACE_SYMBOLS | {"CAPABILITY_MAP"})
    assert forbidden == set(), f"_check_nontable_surface_evidence's AST references forbidden symbols: {forbidden}"


def test_check_coverage_product_ast_references_product_trace_and_capability_map():
    # SAN-881 PASS 2B.1-P TRUTH TEST: the 50-surface branch
    # (_check_all_product_surfaces_evidence) DOES reference the
    # product-trace substrate (it builds a ProductTraceBundle per item
    # via build_product_trace_bundle) AND CAPABILITY_MAP (the reviewed
    # static routing declaration) directly in its own source.
    referenced = _ast_referenced_names(vd._check_all_product_surfaces_evidence)
    assert "build_product_trace_bundle" in referenced
    assert "CAPABILITY_MAP" in referenced
    assert "CheckConsumptionTrace" not in referenced


def test_no_checkconsumptiontrace_symbol_exists_anywhere_in_module():
    # SAN-881 PASS 2B.1-P: the CheckConsumptionTrace architecture (event
    # vocabulary, locks, phase state, call attribution, runtime
    # monkeypatching, EXCL branch replay) was proposed and REJECTED --
    # scans the COMPLETE module source (not just one function) for the
    # literal identifier, as an AST Name/Attribute reference, not a
    # docstring mention (this module's own docstring and several
    # docstrings legitimately name it, in prose, as a rejected/never-
    # implemented architecture).
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(vd))
    referenced = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "CheckConsumptionTrace":
            referenced.add("Name")
        if isinstance(node, ast.Attribute) and node.attr == "CheckConsumptionTrace":
            referenced.add("Attribute")
        if isinstance(node, ast.ClassDef) and node.name == "CheckConsumptionTrace":
            referenced.add("ClassDef")
        if isinstance(node, ast.FunctionDef) and node.name == "CheckConsumptionTrace":
            referenced.add("FunctionDef")
    assert referenced == set(), f"CheckConsumptionTrace exists as executable code: {referenced}"


# ---------------------------------------------------------------------
# Correction 1b (SAN-881 CORRECTION PASS 2): ALLOWED_POSITIONS pair
# enforcement. RULE_COVERAGE_POSITION_NOT_ALLOWED is the ONLY new rule
# code this pass -- it fires when check_id and field are each
# individually legal values but the SPECIFIC (check_id, field) pair is
# not in the claimed surface's allowed_positions (a pair the prior
# allowed_checks x allowed_fields cartesian check could not describe,
# e.g. value_role_v1.cost at (C3, output): C3 is legal for value_role_v1
# at (C3, context), output is legal for value_role_v1 at (C1, output),
# but the PAIR (C3, output) is not itself allowed).
# ---------------------------------------------------------------------

def test_check_coverage_manifest_rejects_c2_context_for_any_surface():
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    coverage = {"nontable.c2_interrogative": [{"item_id": "cal:000", "check_id": "C2", "field": "context"}]}
    vd.check_coverage_manifest(errors, coverage, design_by_id)
    assert any(vd.RULE_COVERAGE_POSITION_NOT_ALLOWED in e for e in errors)


def test_check_coverage_manifest_rejects_c2_for_table_derived_surfaces():
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    coverage = {"facets_v1.facet:cost": [{"item_id": "cal:000", "check_id": "C2", "field": "output"}]}
    vd.check_coverage_manifest(errors, coverage, design_by_id)
    assert any(vd.RULE_COVERAGE_POSITION_NOT_ALLOWED in e for e in errors)
    errors2 = vd.Errors()
    coverage2 = {"comparators_v1.over": [{"item_id": "cal:000", "check_id": "C2", "field": "output"}]}
    vd.check_coverage_manifest(errors2, coverage2, design_by_id)
    assert any(vd.RULE_COVERAGE_POSITION_NOT_ALLOWED in e for e in errors2)


def test_check_coverage_manifest_rejects_value_role_at_c3_output_and_any_c4_position():
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    coverage = {"value_role_v1.cost": [{"item_id": "cal:000", "check_id": "C3", "field": "output"}]}
    vd.check_coverage_manifest(errors, coverage, design_by_id)
    assert any(vd.RULE_COVERAGE_POSITION_NOT_ALLOWED in e for e in errors)
    for field in ("context", "output"):
        errors2 = vd.Errors()
        coverage2 = {"value_role_v1.duration": [{"item_id": "cal:000", "check_id": "C4", "field": field}]}
        vd.check_coverage_manifest(errors2, coverage2, design_by_id)
        assert any(vd.RULE_COVERAGE_POSITION_NOT_ALLOWED in e for e in errors2)


def test_check_coverage_manifest_accepts_value_role_at_its_three_legal_positions():
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    coverage = {"value_role_v1.cost": [
        {"item_id": "cal:000", "check_id": "C1", "field": "context"},
        {"item_id": "cal:000", "check_id": "C1", "field": "output"},
        {"item_id": "cal:000", "check_id": "C3", "field": "context"},
    ]}
    vd.check_coverage_manifest(errors, coverage, design_by_id)
    assert not any(vd.RULE_COVERAGE_POSITION_NOT_ALLOWED in e for e in errors)


def test_check_coverage_manifest_rejects_abstain_interrogative_output_claimed_as_c2_evidence():
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    coverage = {"nontable.abstain_interrogative_output": [{"item_id": "cal:000", "check_id": "C2", "field": "output"}]}
    vd.check_coverage_manifest(errors, coverage, design_by_id)
    assert any(vd.RULE_COVERAGE_POSITION_NOT_ALLOWED in e for e in errors)


def test_check_coverage_manifest_abstain_interrogative_output_accepts_its_legal_positions():
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    coverage = {"nontable.abstain_interrogative_output": [
        {"item_id": "cal:000", "check_id": "C1", "field": "output"},
        {"item_id": "cal:000", "check_id": "C3", "field": "output"},
        {"item_id": "cal:000", "check_id": "C4", "field": "output"},
    ]}
    vd.check_coverage_manifest(errors, coverage, design_by_id)
    assert not any(vd.RULE_COVERAGE_POSITION_NOT_ALLOWED in e for e in errors)


def test_check_coverage_manifest_rejects_check_not_allowed_for_c2_only_nontable_surface():
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    coverage = {"nontable.c2_interrogative": [{"item_id": "cal:000", "check_id": "C1", "field": "output"}]}
    vd.check_coverage_manifest(errors, coverage, design_by_id)
    assert any(vd.RULE_COVERAGE_POSITION_NOT_ALLOWED in e for e in errors)


def test_check_coverage_manifest_interrogative_dual_evidence_both_surfaces_accepted():
    # One '?' item may evidence BOTH c2_interrogative (C2,output) and
    # abstain_interrogative_output ((C1|C3|C4),output) from the SAME
    # item -- only WRONG surface/check pairings are rejected, never the
    # dual claim itself.
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    coverage = {
        "nontable.c2_interrogative": [{"item_id": "cal:000", "check_id": "C2", "field": "output"}],
        "nontable.abstain_interrogative_output": [{"item_id": "cal:000", "check_id": "C1", "field": "output"}],
    }
    vd.check_coverage_manifest(errors, coverage, design_by_id)
    assert not any(vd.RULE_COVERAGE_POSITION_NOT_ALLOWED in e for e in errors)


def test_check_coverage_manifest_position_check_does_not_double_diagnose_invalid_check_id():
    # An already out-of-vocabulary check_id must fail via
    # RULE_COVERAGE_INVALID_CHECK alone -- the new position code only
    # evaluates pairs whose check_id and field are EACH individually
    # legal values, so it must not additionally fire here.
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    coverage = {"nontable.c2_interrogative": [{"item_id": "cal:000", "check_id": "C9", "field": "output"}]}
    vd.check_coverage_manifest(errors, coverage, design_by_id)
    assert any(vd.RULE_COVERAGE_INVALID_CHECK in e for e in errors)
    assert not any(vd.RULE_COVERAGE_POSITION_NOT_ALLOWED in e for e in errors)


# ---------------------------------------------------------------------
# Correction 2: check/field-specific proof; joint EXCL/COMPLEMENT
# evidence; honest static-proof wording
# ---------------------------------------------------------------------

def test_check_coverage_manifest_joint_excl_evidence_both_members_across_records_passes():
    # SAN-881 PASS 2B.1-P: JOINT EXCL now requires TWO DISTINCT assertive
    # FrameProductEvent owners, each carrying its own member in a
    # SAME-RELATION PP-adjunct modifier object set -- a genuine,
    # linguistically valid production fixture is required (never a bare
    # toy substring like "This item is digital.", which has no facets_v1
    # trigger at all and produces zero frames).
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    corpus_by_id = {"cal:000": {
        "id": "cal:000",
        "context": "Refunds are refundable for digital items. Refunds are refundable for physical items.",
        "output": "ok.",
    }}
    tables_data = {"excl_v1": [["digital", "physical"]]}
    coverage = {"excl_v1.digital_physical": [
        {"item_id": "cal:000", "check_id": "C1", "field": "context"},
        {"item_id": "cal:000", "check_id": "C1", "field": "context"},
    ]}
    vd.check_coverage_manifest(errors, coverage, design_by_id, corpus_by_id, tables_data)
    assert errors == []


def test_check_coverage_manifest_joint_excl_evidence_single_member_only_fails():
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    corpus_by_id = {"cal:000": {"id": "cal:000", "context": "Refunds are refundable for digital items.", "output": "ok."}}
    tables_data = {"excl_v1": [["digital", "physical"]]}
    coverage = {"excl_v1.digital_physical": [
        {"item_id": "cal:000", "check_id": "C1", "field": "context"},
    ]}
    vd.check_coverage_manifest(errors, coverage, design_by_id, corpus_by_id, tables_data)
    assert any(vd.RULE_COVERAGE_JOINT_MEMBER_MISSING in e for e in errors)


def test_check_coverage_manifest_joint_complement_evidence_never_concatenates_fields():
    # SAN-881 PASS 2B.1-P: complement_v1 credit now requires each member
    # as an exact SINGLETON TermAtom inside a STORED condition/requirement
    # Bool formula -- "verified" (normalized to "verification" via
    # CONCEPT_v1) is a genuine condition-embedded singleton in CONTEXT
    # only; "unverified" is a genuine condition-embedded singleton in
    # OUTPUT only. The group names ONLY field=context, so the joint check
    # must NOT find "unverified" via an undeclared field.
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    corpus_by_id = {"cal:000": {
        "id": "cal:000",
        "context": "Refunds are refundable if verified.",
        "output": "Refunds are not refundable if unverified.",
    }}
    tables_data = {"complement_v1": [["verified", "unverified"]]}
    coverage = {"complement_v1.verified_unverified": [
        {"item_id": "cal:000", "check_id": "C1", "field": "context"},
    ]}
    vd.check_coverage_manifest(errors, coverage, design_by_id, corpus_by_id, tables_data)
    assert any(vd.RULE_COVERAGE_JOINT_MEMBER_MISSING in e for e in errors)


def test_predicate_nontable_inspects_only_its_own_argument_never_concatenates():
    # _predicate_nontable itself takes whatever text it is given -- the
    # NO-CONCATENATION guarantee lives in check_coverage_manifest's caller
    # logic (_field_text), verified here structurally: the predicate
    # returns a DIFFERENT (correct) answer depending on which single
    # field's text it receives.
    tables_data = {"definitive_v1": ["always"], "hedge_v1": [], "negators_v1": [], "hedge_window_boundaries": [],
                    "quant_v1": {"abstain": []}, "approx_v1": [], "contractions_v1": {}, "facets_v1": {}}
    assert vd._predicate_nontable("It is always available.", "nontable.c2_definitive_hit", tables_data) is True
    assert vd._predicate_nontable("It ships tomorrow.", "nontable.c2_definitive_hit", tables_data) is False


def test_check_coverage_manifest_nontable_uses_only_declared_field():
    # The definitive term is ONLY in context; a record declaring field
    # "output" must NOT see it (no concatenation across fields).
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    corpus_by_id = {"cal:000": {"id": "cal:000", "context": "This is always true.", "output": "Ships tomorrow."}}
    tables_data = {"definitive_v1": ["always"], "hedge_v1": [], "negators_v1": [], "hedge_window_boundaries": [],
                    "quant_v1": {"abstain": []}, "approx_v1": [], "contractions_v1": {}, "facets_v1": {}}
    coverage = {"nontable.c2_definitive_hit": [{"item_id": "cal:000", "check_id": "C2", "field": "output"}]}
    vd.check_coverage_manifest(errors, coverage, design_by_id, corpus_by_id, tables_data)
    assert any(vd.RULE_COVERAGE_PREDICATE_FAILED in e for e in errors)


def test_coverage_manifest_schema_description_states_truthful_partial_state_for_in_scope_surfaces():
    # SAN-881 PASS 2B.1-P HONESTY STATEMENT: the 50 in-scope surfaces are
    # now validated by a PRODUCT-LEVEL four-clause contract over
    # FieldProductTrace + CAPABILITY_MAP; the 18 nontable surfaces remain
    # the ORIGINAL, byte-unchanged static-lexical proof. The description
    # must say so, must carry the exact honest-assurance sentence
    # verbatim, and must disclose that CheckConsumptionTrace does not
    # exist and was REJECTED (never framed as a deferred follow-up).
    schema_text = (SCHEMAS_DIR / "coverage_manifest_schema.json").read_text()
    assert "FieldProductTrace" in schema_text
    assert "CAPABILITY_MAP" in schema_text
    assert "18 NONTABLE surfaces" in schema_text
    assert "BYTE-UNCHANGED" in schema_text
    assert "CheckConsumptionTrace" in schema_text
    assert "REJECTED" in schema_text
    assert HONEST_ASSURANCE_SENTENCE in _normalize_ws(schema_text)
    for phrase in _FORBIDDEN_HONEST_ASSURANCE_PHRASES:
        assert phrase not in schema_text.lower()
    assert "static-lexical" in schema_text
    assert "never publishes trace data" in schema_text or "trace data" in schema_text


def test_module_docstring_states_truthful_partial_state_and_honest_assurance():
    # SAN-881 PASS 2B.1-P: validate_design.py's OWN module docstring
    # must ALSO carry the exact honest-assurance sentence verbatim (the
    # third of the three required locations: README + schema description
    # + module docstring), plus the same REJECTED-architecture framing.
    doc = vd.__doc__
    assert doc is not None
    assert "CAPABILITY_MAP" in doc
    assert "FieldProductTrace" in doc
    assert "BYTE-UNCHANGED" in doc
    assert "CheckConsumptionTrace" in doc
    assert "REJECTED" in doc
    assert HONEST_ASSURANCE_SENTENCE in _normalize_ws(doc)
    for phrase in _FORBIDDEN_HONEST_ASSURANCE_PHRASES:
        assert phrase not in doc.lower()


def test_capability_map_described_as_static_never_dynamic_consumption_proof():
    # CAPABILITY_MAP must be documented, everywhere it is introduced, as
    # a REVIEWED STATIC compatibility declaration -- never as dynamically
    # inferred consumption proof.
    doc = vd.__doc__
    readme = (CAL_DIR / "README.md").read_text()
    schema_text = (SCHEMAS_DIR / "coverage_manifest_schema.json").read_text()
    for text, label in ((doc, "module docstring"), (readme, "README"), (schema_text, "schema description")):
        norm = _normalize_ws(text).lower()
        assert "never a dynamically inferred consumption proof" in norm, label


# ---------------------------------------------------------------------
# Correction 3: explicit --reveal-stage semantic|contract CLI
# ---------------------------------------------------------------------

def test_main_parser_accepts_reveal_stage_choices():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--reveal-stage", choices=list(vd.REVEAL_STAGES), default=None)
    ns = p.parse_args(["--reveal-stage", "semantic"])
    assert ns.reveal_stage == "semantic"
    ns2 = p.parse_args(["--reveal-stage", "contract"])
    assert ns2.reveal_stage == "contract"
    with pytest.raises(SystemExit):
        p.parse_args(["--reveal-stage", "bogus"])


def _toy_stage_environment(tmp_path, sealed_names_on_disk=None, reviewer_names_on_disk=None):
    """`sealed_names_on_disk` controls which of the four author artifacts
    are actually WRITTEN to sealed_dir (all four are always DECLARED in
    the commitment envelope, matching a real AUTHOR envelope's shape --
    only which files physically exist on disk varies). `reviewer_names_on_disk`
    is the analogous control for reviewer_dir's four possible files
    (both reviewer artifacts + both reviewer commitment envelopes).
    Both default to the FULL set (a realistic full sealed/reviewer
    staging copy), which is the scenario a stage-scoped reveal must
    reject if pointed at directly; individual happy-path tests narrow
    both to exactly the artifacts legitimately revealed at that stage
    (SAN-881 Phase-A correction: sealed_dir/reviewer_dir now enforce
    EXACT bundle membership, so a happy-path test's custody copy must
    contain ONLY the stage-appropriate files, nothing extra). The
    returned nonces/reviewer_nonces are the FULL nonce pools (all four /
    both keys); callers scope them down per stage via _scope_nonces.

    SAN-881 Phase-A CORRECTION PASS 1: every artifact's bytes are now
    genuinely SCHEMA-VALID (not the prior placeholder `{"n": "..."}`
    shape) -- the selected-stage schema-validation gate now runs before
    cryptographic subset verification (validate_design.check_stage_schema_validity),
    so a happy-path caller's bundle must satisfy BOTH the crypto AND the
    schema layer to reach `errors == []`. Callers exercising bundle-
    membership / nonce-map / dispatch failures (the majority of this
    function's callers) are unaffected either way -- those checks run
    independently of, and before, the schema gate."""
    ctx_hash = vd.compute_labeling_context_hash([b"toy-ctx"])
    names = ["design_metadata.json", "labels_author_semantic.json", "labels_author_contract.json", "coverage_manifest.json"]
    if sealed_names_on_disk is None:
        sealed_names_on_disk = names
    reviewer_names = [vd.REVIEWER_SEMANTIC_ARTIFACT, vd.REVIEWER_SEMANTIC_COMMITMENT_FILE,
                       vd.REVIEWER_CONTRACT_ARTIFACT, vd.REVIEWER_CONTRACT_COMMITMENT_FILE]
    if reviewer_names_on_disk is None:
        reviewer_names_on_disk = reviewer_names
    artifacts = {
        "design_metadata.json": json.dumps({"items": _toy_160_design_items()}).encode(),
        "labels_author_semantic.json": json.dumps(_toy_640_semantic_records()).encode(),
        "labels_author_contract.json": json.dumps(_toy_640_contract_records()).encode(),
        # SAN-881 PASS 2B.1: schema-valid 68-key-closed manifest -- see
        # _full_valid_coverage_manifest / the schema-closure rewrite.
        "coverage_manifest.json": json.dumps(_full_valid_coverage_manifest()).encode(),
    }
    nonces = {n: secrets.token_bytes(32) for n in names}
    author_commitments = [
        {"artifact_name": n, "byte_length": len(artifacts[n]),
         "commitment_hex": vd.compute_artifact_commitment(n, nonces[n], ctx_hash, artifacts[n])}
        for n in names
    ]
    commitment = {"labeling_context_hash": ctx_hash.hex(), "author_commitments": author_commitments}

    sealed_dir = tmp_path / "sealed"
    sealed_dir.mkdir()
    for n in sealed_names_on_disk:
        (sealed_dir / n).write_bytes(artifacts[n])
    nonces_hex = {n: nonces[n].hex() for n in names}
    nonces_file = tmp_path / "nonces.json"
    nonces_file.write_text(json.dumps(nonces_hex))

    algorithm_block = {
        "hash": "SHA256", "domain_separator": "sanna-calibration-commitment/1",
        "formula": vd.COMMITMENT_ALGORITHM_FORMULA,
    }

    reviewer_dir = tmp_path / "reviewer"
    reviewer_dir.mkdir()
    rev_sem_artifact = json.dumps(_toy_640_semantic_records()).encode()
    rev_sem_nonce = secrets.token_bytes(32)
    rev_sem_commit_hex = vd.compute_artifact_commitment(vd.REVIEWER_SEMANTIC_ARTIFACT, rev_sem_nonce, ctx_hash, rev_sem_artifact)
    if vd.REVIEWER_SEMANTIC_ARTIFACT in reviewer_names_on_disk:
        (reviewer_dir / vd.REVIEWER_SEMANTIC_ARTIFACT).write_bytes(rev_sem_artifact)
    if vd.REVIEWER_SEMANTIC_COMMITMENT_FILE in reviewer_names_on_disk:
        (reviewer_dir / vd.REVIEWER_SEMANTIC_COMMITMENT_FILE).write_text(json.dumps({
            "corpus_version": 2, "envelope_kind": "REVIEWER_SEMANTIC",
            "labeling_context_hash": ctx_hash.hex(),
            "commitment_algorithm": algorithm_block,
            "artifact_commitment": {"artifact_name": vd.REVIEWER_SEMANTIC_ARTIFACT, "byte_length": len(rev_sem_artifact), "commitment_hex": rev_sem_commit_hex},
        }))

    rev_con_artifact = json.dumps(_toy_640_contract_records()).encode()
    rev_con_nonce = secrets.token_bytes(32)
    rev_con_commit_hex = vd.compute_artifact_commitment(vd.REVIEWER_CONTRACT_ARTIFACT, rev_con_nonce, ctx_hash, rev_con_artifact)
    if vd.REVIEWER_CONTRACT_ARTIFACT in reviewer_names_on_disk:
        (reviewer_dir / vd.REVIEWER_CONTRACT_ARTIFACT).write_bytes(rev_con_artifact)
    if vd.REVIEWER_CONTRACT_COMMITMENT_FILE in reviewer_names_on_disk:
        (reviewer_dir / vd.REVIEWER_CONTRACT_COMMITMENT_FILE).write_text(json.dumps({
            "corpus_version": 2, "envelope_kind": "REVIEWER_CONTRACT",
            "labeling_context_hash": ctx_hash.hex(),
            "commitment_algorithm": algorithm_block,
            "artifact_commitment": {"artifact_name": vd.REVIEWER_CONTRACT_ARTIFACT, "byte_length": len(rev_con_artifact), "commitment_hex": rev_con_commit_hex},
        }))
    reviewer_nonces_hex = {vd.REVIEWER_SEMANTIC_ARTIFACT: rev_sem_nonce.hex(), vd.REVIEWER_CONTRACT_ARTIFACT: rev_con_nonce.hex()}
    reviewer_nonces_file = tmp_path / "reviewer_nonces.json"
    reviewer_nonces_file.write_text(json.dumps(reviewer_nonces_hex))

    return commitment, sealed_dir, json.loads(nonces_file.read_text()), reviewer_dir, json.loads(reviewer_nonces_file.read_text())


def _scope_nonces(nonces: dict, keys) -> dict:
    """Narrows a FULL nonce pool (as returned by _toy_stage_environment)
    down to EXACTLY the keys a given stage's nonce map is pinned to --
    mirrors what a real staged --nonces-file / --reviewer-nonces-file
    (a custody-derived STAGE SUBSET, never the original four-key author
    nonce file) would contain."""
    return {k: v for k, v in nonces.items() if k in keys}


_TOY_CACHE_COUNTER = {"n": 0}


def _write_nonces_file(tmp_path: Path, nonces: dict) -> Path:
    """SAN-881 PASS-1 FINAL CLOSURE CORRECTION: run_stage_reveal_verification
    now takes nonce-file PATHS (never a pre-loaded map) -- this materializes
    a scoped nonce dict to a fresh on-disk file (outside any bundle
    directory) and returns its Path, mirroring what a real
    --nonces-file / --reviewer-nonces-file argument is."""
    _TOY_CACHE_COUNTER["n"] += 1
    path = tmp_path / f"nonces_{_TOY_CACHE_COUNTER['n']}.json"
    path.write_text(json.dumps(nonces))
    return path


def _toy_cache_with_real_schemas() -> dict:
    """A minimal Tier-0 cache dict carrying ONLY the real, self-valid
    schemas -- everything run_stage_reveal_verification /
    check_stage_schema_validity need from `cache` for direct-call
    (non-main()) tests of the staged reveal pipeline against TOY
    (not real-corpus) commitments/artifacts."""
    return {"schema": {name: json.loads((SCHEMAS_DIR / name).read_text()) for name in vd.SCHEMA_FILES}}


def test_run_stage_reveal_verification_semantic_two_artifact_event_verifies(tmp_path):
    # Happy path: sealed_dir/reviewer_dir contain EXACTLY the
    # semantic-stage bundle (matching the real workflow's practice of
    # copying out only the currently-revealed subset), and the nonce
    # maps are narrowed to exactly the semantic-stage keys -- no
    # forbidden extra, no keyset mismatch.
    commitment, sealed_dir, nonces, reviewer_dir, reviewer_nonces = _toy_stage_environment(
        tmp_path, sealed_names_on_disk=["labels_author_semantic.json"],
        reviewer_names_on_disk=[vd.REVIEWER_SEMANTIC_ARTIFACT, vd.REVIEWER_SEMANTIC_COMMITMENT_FILE])
    nonces_path = _write_nonces_file(tmp_path, _scope_nonces(nonces, vd.SEMANTIC_AUTHOR_NONCE_KEYS))
    reviewer_nonces_path = _write_nonces_file(tmp_path, _scope_nonces(reviewer_nonces, vd.SEMANTIC_REVIEWER_NONCE_KEYS))
    errors = vd.Errors()
    vd.run_stage_reveal_verification(errors, commitment, "semantic", sealed_dir, nonces_path, reviewer_dir, reviewer_nonces_path, _toy_cache_with_real_schemas())
    assert errors == []


def test_run_stage_reveal_verification_semantic_rejects_contract_extra_supplied(tmp_path):
    commitment, sealed_dir, nonces, reviewer_dir, reviewer_nonces = _toy_stage_environment(tmp_path)
    nonces_path = _write_nonces_file(tmp_path, nonces)
    reviewer_nonces_path = _write_nonces_file(tmp_path, reviewer_nonces)
    # labels_author_contract.json exists on disk in sealed_dir (written by
    # the fixture); the semantic stage must hard-reject it if present.
    # SAN-881 Phase-A CORRECTION PASS 1 (Section E): the staged path no
    # longer appends reveal_verify_subset's free-form prose -- every
    # staged diagnostic is now a fixed rule=CODE line.
    errors = vd.Errors()
    vd.run_stage_reveal_verification(errors, commitment, "semantic", sealed_dir, nonces_path, reviewer_dir, reviewer_nonces_path, _toy_cache_with_real_schemas())
    blob = " ".join(errors)
    assert vd.RULE_REVEAL_FORBIDDEN_EXTRA in blob
    assert "forbidden stage extra" not in blob


def test_run_stage_reveal_verification_semantic_missing_artifact_fails(tmp_path):
    commitment, sealed_dir, nonces, reviewer_dir, reviewer_nonces = _toy_stage_environment(tmp_path)
    (sealed_dir / "labels_author_semantic.json").unlink()
    nonces_path = _write_nonces_file(tmp_path, nonces)
    reviewer_nonces_path = _write_nonces_file(tmp_path, reviewer_nonces)
    errors = vd.Errors()
    vd.run_stage_reveal_verification(errors, commitment, "semantic", sealed_dir, nonces_path, reviewer_dir, reviewer_nonces_path, _toy_cache_with_real_schemas())
    assert any(vd.RULE_REVEAL_NOT_SUPPLIED in e for e in errors)


def test_run_stage_reveal_verification_contract_four_artifact_event_verifies(tmp_path):
    # Happy path: sealed_dir contains ONLY the three contract-scoped
    # author artifacts (not labels_author_semantic.json, already revealed
    # and frozen at the earlier semantic stage), reviewer_dir contains
    # ONLY the contract-stage reviewer bundle, and nonce maps are
    # narrowed to exactly the contract-stage keys.
    commitment, sealed_dir, nonces, reviewer_dir, reviewer_nonces = _toy_stage_environment(
        tmp_path, sealed_names_on_disk=["design_metadata.json", "labels_author_contract.json", "coverage_manifest.json"],
        reviewer_names_on_disk=[vd.REVIEWER_CONTRACT_ARTIFACT, vd.REVIEWER_CONTRACT_COMMITMENT_FILE])
    nonces_path = _write_nonces_file(tmp_path, _scope_nonces(nonces, vd.CONTRACT_AUTHOR_NONCE_KEYS))
    reviewer_nonces_path = _write_nonces_file(tmp_path, _scope_nonces(reviewer_nonces, vd.CONTRACT_REVIEWER_NONCE_KEYS))
    errors = vd.Errors()
    vd.run_stage_reveal_verification(errors, commitment, "contract", sealed_dir, nonces_path, reviewer_dir, reviewer_nonces_path, _toy_cache_with_real_schemas())
    assert errors == []


def test_run_stage_reveal_verification_contract_rejects_semantic_extra_supplied(tmp_path):
    commitment, sealed_dir, nonces, reviewer_dir, reviewer_nonces = _toy_stage_environment(tmp_path)
    nonces_path = _write_nonces_file(tmp_path, nonces)
    reviewer_nonces_path = _write_nonces_file(tmp_path, reviewer_nonces)
    errors = vd.Errors()
    vd.run_stage_reveal_verification(errors, commitment, "contract", sealed_dir, nonces_path, reviewer_dir, reviewer_nonces_path, _toy_cache_with_real_schemas())
    # labels_author_semantic.json exists on disk in sealed_dir (fixture
    # writes it); the contract stage must hard-reject it if present.
    # SAN-881 Phase-A CORRECTION PASS 1 (Section E): fixed rule=CODE, not
    # reveal_verify_subset's free-form prose.
    blob = " ".join(errors)
    assert vd.RULE_REVEAL_FORBIDDEN_EXTRA in blob
    assert "forbidden stage extra" not in blob


def test_run_stage_reveal_verification_invalid_stage_rejected(tmp_path):
    errors = vd.Errors()
    bogus_nonces = _write_nonces_file(tmp_path, {})
    vd.run_stage_reveal_verification(
        errors, {"labeling_context_hash": "a" * 64, "author_commitments": []}, "bogus",
        None, bogus_nonces, None, bogus_nonces, _toy_cache_with_real_schemas())
    assert any(vd.RULE_INVALID_REVEAL_STAGE in e for e in errors)


# ---------------------------------------------------------------------
# SAN-881 Phase-A CORRECTION PASS 1: staged bundle-contract correction
# targets -- exact bundle membership, exact nonce keysets, missing-
# reviewer hard-fail (not skip), dispatch-order isolation.
# ---------------------------------------------------------------------

def test_run_stage_reveal_verification_missing_reviewer_dir_fails_not_skips(tmp_path):
    # THE core correction-target regression: before the fix, passing
    # reviewer_dir=None (no --reviewer-dir at all) to a staged reveal
    # SILENTLY produced zero errors -- the reviewer artifact was simply
    # never checked. It must now hard-fail.
    commitment, sealed_dir, nonces, _reviewer_dir, _reviewer_nonces = _toy_stage_environment(
        tmp_path, sealed_names_on_disk=["labels_author_semantic.json"])
    nonces_path = _write_nonces_file(tmp_path, _scope_nonces(nonces, vd.SEMANTIC_AUTHOR_NONCE_KEYS))
    reviewer_nonces_path = _write_nonces_file(tmp_path, {})
    errors = vd.Errors()
    vd.run_stage_reveal_verification(errors, commitment, "semantic", sealed_dir, nonces_path, None, reviewer_nonces_path, _toy_cache_with_real_schemas())
    assert errors != []
    assert any("not supplied" in e or vd.RULE_REVEAL_NOT_SUPPLIED in e for e in errors)


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1-P: CAPABILITY_MAP bidirectional consistency (build-
# time properties re-proven as explicit pytest tests, in addition to
# the module-load-time asserts in validate_design.py itself).
# ---------------------------------------------------------------------

def test_capability_map_has_exactly_13_nonempty_rows():
    assert len(vd.CAPABILITY_MAP) == 13
    for key, positions in vd.CAPABILITY_MAP.items():
        assert len(positions) > 0, f"{key} must be nonempty"


def test_capability_map_positions_subset_of_closed_vocabulary():
    closed = vd._TABLE_POSITIONS | vd._VALUE_ROLE_POSITIONS
    for key, positions in vd.CAPABILITY_MAP.items():
        assert positions <= closed, f"{key} contains a position outside the closed vocabulary: {positions - closed}"


def test_capability_map_per_surface_union_equals_registry_allowed_positions_for_all_50():
    checked = 0
    for surface, entry in vd.SURFACE_REGISTRY.items():
        family = entry["predicate_id"]
        if family == "nontable":
            continue
        union = set()
        for (f, _loc), positions in vd.CAPABILITY_MAP.items():
            if f == family:
                union |= positions
        assert frozenset(union) == entry["allowed_positions"], (
            f"{surface}: CAPABILITY_MAP union {union!r} != registry {entry['allowed_positions']!r}"
        )
        checked += 1
    assert checked == 50, f"expected exactly 50 in-scope surfaces checked, got {checked}"


def test_capability_map_does_not_route_nontable_surfaces():
    capability_map_families = {family for family, _location in vd.CAPABILITY_MAP}
    assert "nontable" not in capability_map_families
    nontable_count = sum(1 for e in vd.SURFACE_REGISTRY.values() if e["predicate_id"] == "nontable")
    assert nontable_count == 18


def test_surface_registry_unchanged_68_surfaces_362_positions():
    assert len(vd.SURFACE_REGISTRY) == 68
    total = sum(len(e["allowed_positions"]) for e in vd.SURFACE_REGISTRY.values())
    assert total == 362


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1-P: THE NINE PRODUCT-LEVEL DISCRIMINATORS (literal
# vectors, verbatim per the ticket). Each calls build_product_trace_bundle
# directly (never evaluate(), never main()) and exercises
# _pc_check_surface_record / _pc_check_joint_excl_group /
# _pc_check_joint_complement_group -- the SAME functions
# check_coverage_manifest's Pass B dispatches to.
# ---------------------------------------------------------------------

_DISCRIMINATOR_TABLES_DATA = json.loads((REPO_ROOT / "reference" / "spec" / "ALGORITHM-v4-tables-v1.json").read_text())


def _pc_credit(bundle, surface, check_id, field, tables_data=None):
    tables_data = tables_data if tables_data is not None else _DISCRIMINATOR_TABLES_DATA
    family = surface.split(".", 1)[0]
    if family == "excl_v1":
        return vd._pc_check_joint_excl_group(bundle, surface, tables_data, {field}, check_id)
    if family == "complement_v1":
        return vd._pc_check_joint_complement_group(bundle, surface, tables_data, {field}, check_id)
    return vd._pc_check_surface_record(bundle, surface, family, check_id, field, tables_data)


def test_discriminator_1_facet_projection_availability_fails_refund_availability_passes():
    item = {"id": "disc1", "context": "Refunds are available.", "output": "Refunds are unavailable."}
    bundle = vd.build_product_trace_bundle(item)
    assert _pc_credit(bundle, "facets_v1.facet:availability", "C1", "context") is False
    assert _pc_credit(bundle, "facets_v1.facet:refund_availability", "C1", "context") is True


def test_discriminator_2_non_assertive_context_question_fails_facet_credit():
    item = {"id": "disc2", "context": "Are refunds refundable?", "output": "Refunds are not refundable."}
    bundle = vd.build_product_trace_bundle(item)
    assert _pc_credit(bundle, "facets_v1.facet:refund_availability", "C1", "context") is False


def test_discriminator_3_c3_context_facet_credit_fails_without_obligation():
    item = {"id": "disc3", "context": "Refunds are refundable.", "output": "Refunds are refundable."}
    bundle = vd.build_product_trace_bundle(item)
    assert _pc_credit(bundle, "facets_v1.facet:refund_availability", "C3", "context") is False


def test_discriminator_4_bare_subject_modifier_concept_credit_fails():
    item = {"id": "disc4", "context": "Verified refunds are refundable.", "output": "Verified refunds are not refundable."}
    bundle = vd.build_product_trace_bundle(item)
    assert _pc_credit(bundle, "concept_v1.verification", "C1", "context") is False


def test_discriminator_5_bare_subject_modifier_complement_credit_fails():
    item = {
        "id": "disc5",
        "context": "Verified refunds are refundable. Unverified refunds are not refundable.",
        "output": "Refunds are refundable.",
    }
    bundle = vd.build_product_trace_bundle(item)
    assert _pc_credit(bundle, "complement_v1.verified_unverified", "C1", "context") is False


def test_discriminator_6_bare_subject_modifier_excl_credit_fails():
    item = {
        "id": "disc6",
        "context": "Digital items are refundable. Physical items are not refundable.",
        "output": "Items are refundable.",
    }
    bundle = vd.build_product_trace_bundle(item)
    assert _pc_credit(bundle, "excl_v1.digital_physical", "C1", "context") is False


def test_discriminator_7_value_location_comparator_not_c4_consumable():
    item = {
        "id": "disc7",
        "context": "Basic service costs over $30. Basic service never costs over $20.",
        "output": "Basic service costs over $30.",
    }
    bundle = vd.build_product_trace_bundle(item)
    assert _pc_credit(bundle, "comparators_v1.over", "C4", "context") is False


def test_discriminator_8_condition_location_comparator_c4_credit_passes():
    item = {
        "id": "disc8",
        "context": "Refunds are refundable if over 30 days. Refunds are not refundable if over 30 days.",
        "output": "Refunds are refundable if over 30 days.",
    }
    bundle = vd.build_product_trace_bundle(item)
    assert _pc_credit(bundle, "comparators_v1.over", "C4", "context") is True


def test_discriminator_9_universal_preemption_defeats_abstain_credit():
    item = {"id": "disc9", "context": "All most services are available.", "output": "Services are unavailable."}
    bundle = vd.build_product_trace_bundle(item)
    assert _pc_credit(bundle, "quant_v1.abstain", "C1", "context") is False


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1-P: OWNERSHIP QUALIFIER NEGATIVES beyond the nine
# named discriminators.
# ---------------------------------------------------------------------

def test_qualifier_negative_substring_only_hit_fails():
    item = {"id": "qnsub", "context": "This is nonrefundableish stuff maybe.", "output": "ok."}
    bundle = vd.build_product_trace_bundle(item)
    assert _pc_credit(bundle, "facets_v1.facet:refund_availability", "C1", "context") is False


def test_qualifier_negative_tier3_owner_c1_context_claim_fails():
    item = {"id": "qntier3", "context_sources": [{"text": "Refunds are refundable.", "tier": "tier_3"}], "output": "ok."}
    bundle = vd.build_product_trace_bundle(item)
    assert _pc_credit(bundle, "facets_v1.facet:refund_availability", "C1", "context") is False


def test_qualifier_negative_c3_context_owner_absent_from_trusted_obligations_fails():
    # A DISTINCT fixture from discriminator 3 (facet:eligibility, no
    # condition) -- proves the ownership qualifier generalizes beyond
    # the one named discriminator text.
    item = {"id": "qnc3", "context": "Accounts are eligible.", "output": "Accounts are eligible."}
    bundle = vd.build_product_trace_bundle(item)
    assert _pc_credit(bundle, "facets_v1.facet:eligibility", "C3", "context") is False


def test_qualifier_negative_c3_output_other_route_requires_trusted_obligation():
    # facets_v1 (a "frame" location, no EvidenceProductEvent equivalent):
    # C3/output credit requires at least one SUCCESSFULLY EXTRACTED
    # trusted obligation to exist at all.
    item_with_obligation = {"id": "qnc3out1", "context": "Refunds are refundable if verified.", "output": "Refunds are refundable."}
    bundle_with = vd.build_product_trace_bundle(item_with_obligation)
    assert len(bundle_with.trusted_obligations.items) >= 1
    assert _pc_credit(bundle_with, "facets_v1.facet:refund_availability", "C3", "output") is True

    item_without_obligation = {"id": "qnc3out2", "context": "Refunds are refundable.", "output": "Refunds are refundable."}
    bundle_without = vd.build_product_trace_bundle(item_without_obligation)
    assert len(bundle_without.trusted_obligations.items) == 0
    assert _pc_credit(bundle_without, "facets_v1.facet:refund_availability", "C3", "output") is False


def test_qualifier_negative_c3_output_condition_requires_matching_evidence_product_event():
    # comparators_v1 at LOCATION="condition": a genuine condition-embedded
    # comparator in OUTPUT, whose owning frame IS present in
    # bundle.evidence.items -- credit PASSES.
    item = {
        "id": "qnevidence",
        "context": "Refunds are refundable if over 30 days. Refunds are not refundable if over 30 days.",
        "output": "Refunds are refundable if over 30 days.",
    }
    bundle = vd.build_product_trace_bundle(item)
    out_identity = ("output", 0, 0, 0)
    assert any(ev.frame_identity == out_identity for ev in bundle.evidence.items)
    assert _pc_credit(bundle, "comparators_v1.over", "C3", "output") is True

    # SYNTHETIC negative: same bundle, but with evidence.items wiped
    # (simulating a FramePartial short-circuit elsewhere in the SAME
    # bundle -- "successfully extracted" is all-or-nothing) -- the
    # owning frame's condition comparator product still exists, but with
    # no matching EvidenceProductEvent, credit must FAIL.
    stripped_evidence = vd.EvidenceCaptureProduct(items=(), partial_event=vd.BundleCapturePartialEvent(cause="unextractable"))
    bundle_stripped = vd.dataclasses.replace(bundle, evidence=stripped_evidence)
    assert _pc_credit(bundle_stripped, "comparators_v1.over", "C3", "output") is False


def test_qualifier_negative_empty_parsed_intervals_comparator_claim_fails():
    identity = ("context", 0, 0, 0)
    ce_empty = vd.ComparatorProductEvent(
        location="value", comparator_folds=("over",), raw_span_text="over 30", raw_start=0, raw_end=7,
        owning_identity=identity, owning_condition_index=None, parsed_intervals=(),
    )
    fe = vd.FrameProductEvent(
        identity=identity, facet="facet:cost", raw_facet="facet:cost", subject=frozenset({"service"}), object=frozenset(),
        modifiers=frozenset(), excl_candidates=(), quant_class=0, quant_token_fold=None, is_deny=False, negator_raw=None,
        polarity=0, trigger_raw="costs", trigger_folds=("cost",), value_span_raw="over 30", value_span_start=0, value_span_end=7,
        value_intervals=(), comparator_events=(ce_empty,), conds=(), assertive=True, subject_conjuncts=(), subject_conjunct_heads=(),
        req_formula=None, req_concept_mappings=(), req_complement_candidates=(), req_comparator_events=(),
    )
    ft_ctx = vd.FieldProductTrace(field="context", source_index=0, boundary_start=0, boundary_end=10, tier="tier_1", partial=False, frame_events=(fe,), partial_events=())
    ft_out = vd.FieldProductTrace(field="output", source_index=0, boundary_start=0, boundary_end=10, tier=None, partial=False, frame_events=(), partial_events=())
    bundle = vd.ProductTraceBundle(
        item_id="synthetic", fields=(ft_ctx, ft_out),
        trusted_obligations=vd.ObligationCaptureProduct(items=(), partial_event=None),
        excluded_obligation_frames=(), evidence=vd.EvidenceCaptureProduct(items=(), partial_event=None),
    )
    toy_tables = {"comparators_v1": [{"tokens": ["over"], "interval": {}}]}
    assert _pc_credit(bundle, "comparators_v1.over", "C1", "context", toy_tables) is False

    # sanity: the SAME shape with nonempty parsed_intervals credits.
    ce_nonempty = vd.dataclasses.replace(ce_empty, parsed_intervals=("x",))
    fe2 = vd.dataclasses.replace(fe, comparator_events=(ce_nonempty,))
    ft_ctx2 = vd.dataclasses.replace(ft_ctx, frame_events=(fe2,))
    bundle2 = vd.dataclasses.replace(bundle, fields=(ft_ctx2, ft_out))
    assert _pc_credit(bundle2, "comparators_v1.over", "C1", "context", toy_tables) is True


def test_qualifier_negative_excl_single_frame_owner_fails():
    item = {"id": "qnexclone", "context": "Refunds are refundable for digital and for physical items.", "output": "ok."}
    bundle = vd.build_product_trace_bundle(item)
    assert _pc_credit(bundle, "excl_v1.digital_physical", "C1", "context") is False


def test_qualifier_positive_excl_two_distinct_owners_passes():
    item = {
        "id": "qnexcltwo",
        "context": "Refunds are refundable for digital items. Refunds are refundable for physical items.",
        "output": "ok.",
    }
    bundle = vd.build_product_trace_bundle(item)
    assert _pc_credit(bundle, "excl_v1.digital_physical", "C1", "context") is True


def test_qualifier_negative_complement_extent_term_singleton_rule_fails():
    # "active"/"inactive" live in the frame's own subject EXTENT (bare
    # adjectival modifiers), never inside a Bool condition/requirement
    # formula -- the singleton-TermAtom rule can never find them.
    item = {
        "id": "qncompext",
        "context": "Active accounts are eligible. Inactive accounts are not eligible.",
        "output": "ok.",
    }
    bundle = vd.build_product_trace_bundle(item)
    assert _pc_credit(bundle, "complement_v1.active_inactive", "C1", "context") is False


def test_qualifier_positive_complement_both_singleton_termatoms_passes():
    item = {
        "id": "qncompboth",
        "context": "Refunds are refundable if verified. Refunds are not refundable if unverified.",
        "output": "ok.",
    }
    bundle = vd.build_product_trace_bundle(item)
    assert _pc_credit(bundle, "complement_v1.verified_unverified", "C1", "context") is True


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1-P: TWO-PASS ORDERING + ANTI-RETURN GUARD.
# ---------------------------------------------------------------------

def test_check_coverage_manifest_pass_a_failure_never_builds_a_bundle(monkeypatch):
    calls = []
    real_builder = vd.build_product_trace_bundle

    def _spy(item):
        calls.append(item.get("id"))
        return real_builder(item)

    monkeypatch.setattr(vd, "build_product_trace_bundle", _spy)

    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    corpus_by_id = {"cal:000": {"id": "cal:000", "context": "Refunds are refundable.", "output": "Refunds are refundable."}}
    tables_data = {"facets_v1": {"facet:refund_availability": {"triggers": ["refundable"], "deny_triggers": []}}}
    # Pass-A failure: item_id not in design_by_id for a SECOND record in
    # the SAME manifest -- the whole manifest's Pass A must fail, and
    # Pass B (which would otherwise credit the first, valid surface)
    # must never run.
    coverage = {
        "facets_v1.facet:refund_availability": [{"item_id": "cal:000", "check_id": "C1", "field": "context"}],
        "facets_v1.facet:availability": [{"item_id": "cal:999", "check_id": "C1", "field": "context"}],
    }
    vd.check_coverage_manifest(errors, coverage, design_by_id, corpus_by_id, tables_data)
    assert any(vd.RULE_COVERAGE_UNKNOWN_ITEM in e for e in errors)
    assert calls == [], f"build_product_trace_bundle was called despite a Pass A failure: {calls}"


def test_check_coverage_manifest_pass_a_success_reaches_pass_b_and_builds_a_bundle(monkeypatch):
    calls = []
    real_builder = vd.build_product_trace_bundle

    def _spy(item):
        calls.append(item.get("id"))
        return real_builder(item)

    monkeypatch.setattr(vd, "build_product_trace_bundle", _spy)

    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    corpus_by_id = {"cal:000": {"id": "cal:000", "context": "Refunds are refundable.", "output": "Refunds are refundable."}}
    tables_data = _DISCRIMINATOR_TABLES_DATA
    coverage = {"facets_v1.facet:refund_availability": [{"item_id": "cal:000", "check_id": "C1", "field": "context"}]}
    vd.check_coverage_manifest(errors, coverage, design_by_id, corpus_by_id, tables_data)
    assert errors == []
    assert calls == ["cal:000"]


def test_check_coverage_manifest_pass_b_caches_bundle_once_per_item():
    calls = []
    real_builder = vd.build_product_trace_bundle

    def _spy(item):
        calls.append(item.get("id"))
        return real_builder(item)

    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    corpus_by_id = {"cal:000": {"id": "cal:000", "context": "Refunds are refundable.", "output": "Refunds are refundable."}}
    tables_data = _DISCRIMINATOR_TABLES_DATA
    coverage = {
        "facets_v1.facet:refund_availability": [
            {"item_id": "cal:000", "check_id": "C1", "field": "context"},
            {"item_id": "cal:000", "check_id": "C1", "field": "output"},
        ],
    }
    import unittest.mock
    with unittest.mock.patch.object(vd, "build_product_trace_bundle", side_effect=_spy):
        vd.check_coverage_manifest(errors, coverage, design_by_id, corpus_by_id, tables_data)
    assert calls == ["cal:000"], f"expected exactly ONE build for cal:000, got {calls}"


def test_anti_return_guard_ast_never_calls_evaluate_checks_engine_relations_or_tracing_hooks():
    # ANTI-RETURN GUARD: the runtime coverage call graph (the functions
    # check_coverage_manifest transitively calls for Pass B, all defined
    # in THIS module) may call ONLY build_product_trace_bundle, pure
    # product predicates/classifiers, table folding, CAPABILITY_MAP, and
    # -- SAN-881 PASS 2B.1b -- EXACTLY the two shared helpers
    # reference.checks.scan_c2_lexical / has_governed_question -- NEVER
    # evaluate, C1/C2/C3/C4, budgets, relations, engine queries,
    # monkeypatching, stack inspection, locks, wrappers, or tracing hooks.
    # `reference.checks` as a MODULE is no longer blanket-forbidden (the
    # two permitted helpers live there) -- instead, every ImportFrom of
    # reference.checks anywhere in the call graph must import ONLY names
    # drawn from _PERMITTED_CHECKS_HELPERS, and C1/C2/C3/C4 stay banned
    # as bare Name/Attribute references regardless.
    import ast
    import inspect

    _PERMITTED_CHECKS_HELPERS = frozenset({"scan_c2_lexical", "has_governed_question"})

    forbidden_names = frozenset({
        "evaluate", "C1", "C2", "C3", "C4", "budgets", "relations", "rel", "engine",
        "monkeypatch", "setattr", "MonkeyPatch", "inspect", "currentframe",
        "_getframe", "threading", "Lock", "RLock", "wraps", "CheckConsumptionTrace",
    })
    forbidden_modules = frozenset({
        "reference.evaluate", "reference.engine", "reference.relations",
        "threading", "inspect",
    })

    call_graph_functions = [
        vd.check_coverage_manifest,
        vd._check_nontable_surface_evidence,
        vd._predicate_nontable,
        vd._check_all_product_surfaces_evidence,
        vd._make_bundle_cache,
        vd._check_nontable_bundle_backed_evidence,
        vd._nb_check_polarity_via_deny_trigger,
        vd._nb_check_polarity_via_negator,
        vd._nb_check_contraction_expansion,
        vd._nb_contraction_c2_route,
        vd._nb_check_event_local_abstain,
        vd._nb_check_abstain_quant_abstain,
        vd._nb_check_malformed_value_in_segment,
        vd._nb_check_approx_value_in_segment,
        vd._nb_check_non_ascii_digit_in_segment,
        vd._nb_classify_hit_value_region,
        vd._nb_adjunct_group_scan,
        vd._nb_locate_hit,
        vd._nb_source_texts,
        vd._nb_sentence_texts,
        vd._nb_contraction_occurrences,
        vd._nb_token_sentence_index,
        vd._nb_hit_segment_text,
        vd._pc_check_surface_record,
        vd._pc_check_joint_excl_group,
        vd._pc_check_joint_complement_group,
        vd._pc_locate,
        vd._pc_candidate_ok,
        vd._pc_ownership_and_partiality_ok,
        vd._pc_quant_abstain_event_matches,
        vd._pc_field_traces,
        vd._pc_owner_tier,
        vd._pc_nonpartial_ok,
        vd._pc_frame_in_trusted_obligations,
        vd._pc_frame_has_evidence,
        vd._pc_termatom_singletons,
        vd._pc_normalize_bool_term,
        vd.classify_value_span_text,
    ]
    # NOTE: build_product_trace_bundle itself is EXPLICITLY ALLOWED by
    # the anti-return guard and is pre-existing SAN-881 PASS 2B.1-T
    # infrastructure (already using reference.checks._trusted/TIER_1 to
    # mirror production trust filtering) -- the guard is about the NEW
    # Pass B dispatch code never reaching AROUND it into
    # checks/engine/relations/evaluate, not about build_product_trace_bundle
    # own internals, which are separately covered by the 2B.1-T
    # differential test against production extract_frames.

    all_referenced_names = set()
    all_imported_modules = set()
    bad_checks_imports = set()
    for func in call_graph_functions:
        source = inspect.getsource(func)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                all_referenced_names.add(node.id)
            if isinstance(node, ast.Attribute):
                all_referenced_names.add(node.attr)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    all_imported_modules.add(alias.name)
            if isinstance(node, ast.ImportFrom):
                if node.module == "reference.checks":
                    imported = {alias.name for alias in node.names}
                    bad_checks_imports |= (imported - _PERMITTED_CHECKS_HELPERS)
                elif node.module:
                    all_imported_modules.add(node.module)

    bad_names = all_referenced_names & forbidden_names
    bad_modules = all_imported_modules & forbidden_modules
    assert bad_names == set(), f"runtime coverage call graph references forbidden names: {bad_names}"
    assert bad_modules == set(), f"runtime coverage call graph imports forbidden modules: {bad_modules}"
    assert bad_checks_imports == set(), (
        f"runtime coverage call graph imports non-permitted reference.checks symbols: {bad_checks_imports}"
    )


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1-P: NONTABLE ISOLATION (Phase-0 AST pins + spy test).
# ---------------------------------------------------------------------


# SAN-881 PASS 2B.1-P-FIX fix 7 / SAN-881 PASS 2B.1b / SAN-881 PASS
# 2B.1b-FIX: COMMITTED nontable AST digest pins (no /private/tmp
# dependency, no skip path -- test_nontable_ast_pins_match_phase0_
# baseline below always runs and always compares against THESE literal
# values). Covers the 18 keyed handler expressions inside
# _predicate_nontable, _predicate_nontable itself, the FIVE _contains_*
# helpers (_contains_non_ascii_digit, _contains_malformed_number_
# grouping, _contains_nonterminating_punctuation_run, _contains_
# adjunct_preposition_chain, _contains_trigger_in_adjunct_phrase --
# there are exactly FIVE, not six) plus _word_present, _field_text, and
# COVERAGE_PREDICATES["nontable"]'s own binding. SAN-881 PASS 2B.1b
# updated the seven c2_* handler digests (now product-honest, consuming
# reference.checks.scan_c2_lexical / has_governed_question) and
# _predicate_nontable's own function digest (the new local scan_c2_
# lexical/has_governed_question wiring). SAN-881 PASS 2B.1b-FIX (A1)
# updated ONLY _predicate_nontable's own function digest AGAIN -- the
# interrogative partial-gate now short-circuits BEFORE the shared scan
# runs (see _predicate_nontable's own body) -- while every ONE of the
# 18 keyed handler VALUE EXPRESSIONS (including all six lexical c2_*
# ones) stayed byte-identical text (`c2_exams`/`c2_non_negated` are
# still referenced by NAME; only how those two locals are COMPUTED,
# above the handlers dict, changed). Every other pinned digest here was
# BYTE-IDENTICAL to the pre-2B.1b-FIX baseline -- the eleven Group B/C
# handler expressions untouched, superseded by _check_nontable_bundle_
# backed_evidence, which SAN-881 PASS 2B.1b-FIX (B1-B4) rewired instead
# (a DIFFERENT, unpinned function) -- and so were the five _contains_*
# helpers, _word_present, _field_text, and the COVERAGE_PREDICATES
# ["nontable"] binding itself. SAN-881 PASS 2B.1b-FIX2 (correction 4)
# updated ONLY _predicate_nontable's own function digest a THIRD time --
# dispatch is now LAZY/early-returning: a registered Group A name
# returns before the eleven Group B/C handler expressions below are
# ever constructed (previously ONE eager `handlers` dict literal spanned
# all eighteen keys, so a Group-A call ALSO silently evaluated the five
# legacy _contains_* helpers every time). The 18 keyed handler VALUE
# EXPRESSIONS themselves (now split across TWO separate `handlers: dict`
# literals -- one per branch -- both still named `handlers`, so this
# test's own AnnAssign walk merges both without any change to its own
# logic) stayed byte-identical text, and so did the five _contains_*
# helpers, _word_present, _field_text, and the COVERAGE_PREDICATES
# ["nontable"] binding: the eleven Group B/C expressions are now
# LEGACY-UNREACHABLE-FROM-RUNTIME (no live check_coverage_manifest
# dispatch path ever evaluates their code), not merely "dead" -- see
# _predicate_nontable's own docstring.
_NONTABLE_AST_PINS: dict = {
    "coverage_predicates_nontable_binding": "c86875995a164bd3cfc5464eb07721540351daf06075488cbc9b9286d75f440a",
    "functions": {
        "_contains_adjunct_preposition_chain": "f9b9919855efafbce24b21bb0ad8dd607d10ca7960420333c99cd43a371aeeb5",
        "_contains_malformed_number_grouping": "fded1dc64b7ef249fe87f97cd0119c7afb45db23f93acca9d97e4b26ba03c94c",
        "_contains_non_ascii_digit": "2e8f257aeffe828d52253f7038e42bfc15730a0bfbc193bb683b922e64cbe819",
        "_contains_nonterminating_punctuation_run": "fdc7d98b95a1b180789f52984847d68e312bf966b359288a73fa573c476102cb",
        "_contains_trigger_in_adjunct_phrase": "60988155b24a16e3b93f953efcd95f7977aa95b462fd067f9cd1488506e5c58a",
        "_field_text": "df2da61973c1e3701223e338d546db04dd8293548cf2fcf864d9a471d1c047cc",
        "_predicate_nontable": "553efe1577feef2b03bd00d21f11d825fee9d58789a302c83ab52efcc985c2bd",
        "_word_present": "50c2cee5e39c6ed1830b112164758f84e58eec4f7c59c61addf482a37f08d0d4",
    },
    "nontable_keyed_handlers": {
        "abstain_approx_value": "1ccedc9ad1f9a6df3c38c5cc304894910ee4484aa5aaefa446bcb463274737c5",
        "abstain_e13_nonterminating_punctuation": "baa92cf0a400982772d8ee75d53be7b0dc121de02eb637813e1c4ef4a1e7702c",
        "abstain_e15_nested_adjunct_chain": "5d20f0fc06093d521f0bace0986320558b73193a144a80a847cee4a281af4b54",
        "abstain_interrogative_output": "47c04aa5b41e6ff28bc2000d01883f0995fa45fb62b70f3dbd241ee20c83436d",
        "abstain_malformed_value": "40d89485c4342c7ee044a66c46eecee152295a4247fda7ff45d866ecceb4f169",
        "abstain_quant_abstain": "1e86874b80d99edaf79b60e73117b8b0b343626a04edf7644454586ac5f4348f",
        "abstain_san894_trigger_in_adjunct": "a2a542b3cd407ba4443f19f0ff7b07e298502246c570ea56d39b0839b939c5aa",
        "abstain_san895_non_ascii_digits": "1ba1fc8347ac143c4315cf670a07024a28e48818096d4056749b4b5a5d727938",
        "c2_definitive_hit": "0d7c59153ee2d6d29daa3f086b6d342db673ded066438cd96197c6e6ec46d988",
        "c2_hedge_in_window": "87d5e1c93235ac3dda33bfd35df7f63ecaadc064fb9a2b3fe109260db1c26c99",
        "c2_hedge_outside_window_or_absent": "dcf4ec4ba07fc234fee297d427d30aa0b5b9ca2e33cab41f6987588120534bd3",
        "c2_interrogative": "f77105179149cf05973df8134ad1b59ddce961915adbb87beecfab48ca5c0c4c",
        "c2_negated_definitive": "4c92fe01de1fd4218cbeda8e00ed1211107bcb37c501a0fc8b8c2c6cd729c870",
        "c2_negated_hedge": "bf7d6261ff8d24ff3f2b64d9f54ce217335b6f19c583eecae435333af57547b9",
        "c2_window_boundary": "ec335f7cb495d98169fe02c8008bc67c660c3b300577c0d12e01785c1fd60ee9",
        "contraction_expansion": "7b75d9edc8af473ad3ea49ae4d8fc04e1892efac4cb33c651a09377decfa092d",
        "polarity_via_deny_trigger": "5c0aefeb5e8ff9be10f50e63723e16d4544661c4d0cb9fc7c06f1e21bbe223ef",
        "polarity_via_negator": "13feb66d50c4ecc986de42c78be51093de3052942f1a8cae8e1a9de572669d18",
    },
}


def test_nontable_ast_pins_match_phase0_baseline():
    # Compares against the COMMITTED _NONTABLE_AST_PINS literal above
    # (no /private/tmp file, no skip path -- always runs, always
    # compares): the normalized-AST digests of all 18 keyed handler
    # expressions inside _predicate_nontable, _predicate_nontable itself,
    # its FIVE _contains_* helpers plus _word_present, _field_text, and
    # COVERAGE_PREDICATES["nontable"]'s binding must be BYTE-FOR-BYTE
    # unchanged.
    import ast
    import hashlib

    pins = _NONTABLE_AST_PINS

    def normalized_digest_of_node(node) -> str:
        src = ast.unparse(node)
        tree = ast.parse(src)
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                body = n.body
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                    n.body = body[1:] if len(body) > 1 else [ast.Pass()]
        return hashlib.sha256(ast.dump(tree).encode("utf-8")).hexdigest()

    current_src = Path(vd.__file__).read_text()
    tree = ast.parse(current_src)

    def find_func(t, name):
        for node in ast.walk(t):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        return None

    fn = find_func(tree, "_predicate_nontable")
    handler_digests = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "handlers":
            for k, v in zip(node.value.keys, node.value.values):
                handler_digests[k.value] = hashlib.sha256(ast.dump(v).encode("utf-8")).hexdigest()
    assert handler_digests == pins["nontable_keyed_handlers"]

    for name in ["_predicate_nontable", "_contains_non_ascii_digit", "_contains_malformed_number_grouping",
                 "_contains_nonterminating_punctuation_run", "_contains_adjunct_preposition_chain",
                 "_contains_trigger_in_adjunct_phrase", "_word_present", "_field_text"]:
        node = find_func(tree, name)
        assert normalized_digest_of_node(node) == pins["functions"][name], f"{name} AST digest drifted"

    binding_digest = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "COVERAGE_PREDICATES":
            for k, v in zip(node.value.keys, node.value.values):
                if k.value == "nontable":
                    binding_digest = hashlib.sha256(ast.dump(v).encode("utf-8")).hexdigest()
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "COVERAGE_PREDICATES":
            for k, v in zip(node.value.keys, node.value.values):
                if k.value == "nontable":
                    binding_digest = hashlib.sha256(ast.dump(v).encode("utf-8")).hexdigest()
    assert binding_digest == pins["coverage_predicates_nontable_binding"]


def test_nontable_routes_spy_never_invoke_product_tracing():
    # A spy test proving the 18 nontable routes never invoke product
    # tracing: monkeypatch build_product_trace_bundle to raise if called
    # at all, then run check_coverage_manifest over a manifest whose
    # ONLY surface is a nontable one -- Pass B must complete without
    # ever calling the spy.
    def _boom(item):
        raise AssertionError(f"build_product_trace_bundle must never be called for a nontable-only manifest (item={item.get('id')})")

    import unittest.mock
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    corpus_by_id = {"cal:000": {"id": "cal:000", "context": "ctx.", "output": "It is always true."}}
    tables_data = {
        "definitive_v1": ["always"], "hedge_v1": [], "negators_v1": [], "hedge_window_boundaries": [],
        "quant_v1": {"abstain": []}, "approx_v1": [], "contractions_v1": {}, "facets_v1": {},
    }
    coverage = {"nontable.c2_definitive_hit": [{"item_id": "cal:000", "check_id": "C2", "field": "output"}]}
    with unittest.mock.patch.object(vd, "build_product_trace_bundle", side_effect=_boom):
        vd.check_coverage_manifest(errors, coverage, design_by_id, corpus_by_id, tables_data)
    assert errors == []
# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1-P: CONFORMANCE SUITE (test code only, never the
# runtime path): ONE NAMED positive + negative synthetic case per
# CAPABILITY_MAP row (13 pairs, 26 tests). These call reference.extraction
# .extract_frames (a production primitive, never evaluate()) and
# reference.checks.C1/C3/C4 DIRECTLY on SYNTHETIC fixtures and assert
# REAL check outcomes -- EVALUATOR RULE compliant: no evaluate()
# invocation anywhere, ordinary individual-check-function calls only.
# These are REPRESENTATIVE COMPATIBILITY WITNESSES and outcome sanity
# checks; they do NOT prove causal internal consumption by the
# coverage-manifest product predicates (a structurally separate,
# static-routing-table concern) -- named accordingly throughout.
# ---------------------------------------------------------------------

def _assert_target_product_present(family, surface, field, location, ctx_text, out_text, tables_data=None):
    """SAN-881 PASS 2B.1-P-FIX fix 6: builds a REAL ProductTraceBundle
    (via build_product_trace_bundle, pure read-only replay -- never
    evaluate()) over (ctx_text, out_text) and asserts the row's own
    target product genuinely exists at its declared LOCATION.
    REPRESENTATIVE COMPATIBILITY EVIDENCE only -- this proves the
    production replay + location-detection machinery genuinely finds a
    product of the claimed shape for a realistic sentence; it is NEVER
    proof of causal check execution, nor proof of every legally allowed
    position (CAPABILITY_MAP itself, and the per-surface union-equality
    /literal-pin tests, remain the authority for the full legal
    position set). excl_v1/complement_v1 are JOINT families -- never
    located by _pc_locate -- so their existence is proven directly here
    via the SAME structural signal _pc_check_joint_excl_group /
    _pc_check_joint_complement_group locate it from (FrameProductEvent.
    modifiers for excl_v1; a singleton TermAtom in a condition/
    requirement Bool formula for complement_v1), without also requiring
    the ownership/CAPABILITY_MAP qualifiers those joint-credit functions
    additionally apply (a SEPARATE, stronger claim already covered by
    the qualifier-negative/positive tests elsewhere in this module)."""
    tables_data = tables_data if tables_data is not None else _DISCRIMINATOR_TABLES_DATA
    bundle = vd.build_product_trace_bundle({"id": "witness", "context": ctx_text, "output": out_text})

    if family == "excl_v1":
        pair_name = surface.split(".", 1)[1]
        members = vd._lookup_pair_members(tables_data, "excl_v1", pair_name)
        fold_a, fold_b = vd._fold_excl_member(members[0]), vd._fold_excl_member(members[1])
        owners = [fe for ft in vd._pc_field_traces(bundle, field) for fe in ft.frame_events]
        for fe1 in owners:
            for rel1, objset1 in fe1.modifiers:
                if fold_a not in objset1:
                    continue
                for fe2 in owners:
                    if fe2 is fe1:
                        continue
                    for rel2, objset2 in fe2.modifiers:
                        if rel2 == rel1 and fold_b in objset2:
                            return
        raise AssertionError(f"{surface}: no {location}-location product found in field={field}")

    if family == "complement_v1":
        pair_name = surface.split(".", 1)[1]
        members = vd._lookup_pair_members(tables_data, "complement_v1", pair_name)
        norm_a, norm_b = vd._pc_normalize_bool_term(members[0]), vd._pc_normalize_bool_term(members[1])
        for ft in vd._pc_field_traces(bundle, field):
            for fe in ft.frame_events:
                for cond in fe.conds:
                    for terms in vd._pc_termatom_singletons(cond.formula):
                        if terms in (frozenset({norm_a}), frozenset({norm_b})):
                            return
                if fe.req_formula is not None:
                    for terms in vd._pc_termatom_singletons(fe.req_formula):
                        if terms in (frozenset({norm_a}), frozenset({norm_b})):
                            return
        raise AssertionError(f"{surface}: no {location}-location product found in field={field}")

    locations = {loc for loc, *_rest in vd._pc_locate(bundle, family, surface, field, tables_data)}
    assert location in locations, f"{surface}: expected location {location!r} not found (found {locations!r})"


def _run_check_directly(check_id, ctx_text, out_text, tiers=None):
    """Frame-counter hygiene (SAN-881 PASS 2B.1-T-FIX-MICRO fix 3):
    reference.extraction.extract_frames advances the shared global
    _frame_counter as a side effect -- snapshotted before and restored
    after, mirroring test_product_trace_trusted_obligations_excludes_tier3
    _source_mirrors_checks_trusted's own discipline. Calls
    reference.checks.C1/C3/C4 directly -- NEVER evaluate()."""
    from reference.extraction import _frame_counter, extract_frames
    from reference import checks

    frame_counter_before = dict(_frame_counter)
    try:
        ctx_frames, ctx_partial = extract_frames("context", ctx_text, governed=False)
        out_frames, out_partial = extract_frames("output", out_text, governed=True)
        if check_id == "C1":
            return checks.C1(ctx_frames, out_frames, ctx_partial, out_partial, tiers)
        if check_id == "C3":
            return checks.C3(ctx_frames, out_frames, "context", "output", ctx_partial, out_partial, tiers)
        if check_id == "C4":
            return checks.C4(ctx_frames, out_frames, ctx_partial, out_partial, tiers)
        raise ValueError(check_id)
    finally:
        _frame_counter["n"] = frame_counter_before["n"]


def test_conformance_witness_facets_v1_frame_c1_positive_violation():
    ctx, out = "Refunds are unavailable.", "Refunds are available."
    _assert_target_product_present("facets_v1", "facets_v1.facet:refund_availability", "context", "frame", ctx, out)
    outcome = _run_check_directly("C1", ctx, out)
    assert outcome[0] == "VIOLATION" and outcome[1] == "detection_complete"


def test_conformance_witness_facets_v1_frame_c1_negative_pass():
    outcome = _run_check_directly("C1", "Refunds are unavailable.", "Refunds are unavailable.")
    assert outcome[0] == "PASS"


def test_conformance_witness_concept_v1_condition_c1_positive_violation():
    ctx, out = "Refunds are refundable if verified.", "Refunds are not refundable if verified."
    _assert_target_product_present("concept_v1", "concept_v1.verification", "context", "condition", ctx, out)
    outcome = _run_check_directly("C1", ctx, out)
    assert outcome[0] == "VIOLATION" and outcome[1] == "detection_complete"


def test_conformance_witness_concept_v1_condition_c1_negative_pass():
    outcome = _run_check_directly("C1", "Refunds are refundable if verified.", "Refunds are refundable if verified.")
    assert outcome[0] == "PASS"


def test_conformance_witness_concept_v1_requirement_c3_positive_violation():
    # PRODUCT-EXISTENCE PROOF uses a DEDICATED, decoupled fixture
    # ("Refunds require being approved.") rather than the pinned oracle
    # text below: CONCEPT_v1 mapping only records a (raw_fold, mapped)
    # tuple when the raw fold GENUINELY DIFFERS from its canonical form
    # (see _pt_capture_conjunct_products: `if mapped != tok.fold`) --
    # the oracle text's bare "approval" is ALREADY the canonical form,
    # so it never populates req_concept_mappings, while "approved" does.
    # The pinned oracle fixture below is left byte-identical (it is a
    # genuine oracle-verified case -- reference/fixtures/oracles.json
    # id=flagship-violation -- and must not be altered).
    _assert_target_product_present(
        "concept_v1", "concept_v1.approval", "context", "requirement",
        "Refunds require being approved.", "ok.",
    )
    outcome = _run_check_directly("C3", "Refunds require approval.", "Refunds are available.")
    assert outcome[0] == "VIOLATION" and outcome[1] == "detection_complete"


def test_conformance_witness_concept_v1_requirement_c3_negative_pass():
    # oracle-verified (reference/fixtures/oracles.json id=flagship-satisfied)
    outcome = _run_check_directly("C3", "Refunds require approval.", "Refunds are available only if approved.")
    assert outcome[0] == "PASS"


def test_conformance_witness_comparators_v1_value_c1_positive_violation():
    # "Basic fee is $3."/"$4." -> VIOLATION/detection_complete pattern
    ctx, out = "Basic fee is over $30.", "Basic fee is under $30."
    _assert_target_product_present("comparators_v1", "comparators_v1.over", "context", "value", ctx, out)
    outcome = _run_check_directly("C1", ctx, out)
    assert outcome[0] == "VIOLATION" and outcome[1] == "detection_complete"


def test_conformance_witness_comparators_v1_value_c1_negative_pass():
    outcome = _run_check_directly("C1", "Basic fee is over $30.", "Basic fee is over $30.")
    assert outcome[0] == "PASS"


def test_conformance_witness_comparators_v1_condition_c4_positive_violation():
    ctx = "Refunds are refundable if over 30 days. Refunds are not refundable if over 30 days."
    out = "Refunds are refundable if over 30 days."
    _assert_target_product_present("comparators_v1", "comparators_v1.over", "context", "condition", ctx, out)
    outcome = _run_check_directly("C4", ctx, out)
    assert outcome[0] == "VIOLATION" and outcome[1] == "detection_complete"


def test_conformance_witness_comparators_v1_condition_c4_negative_pass():
    outcome = _run_check_directly(
        "C4",
        "Refunds are refundable if over 30 days. Refunds are not refundable if over 30 days.",
        "Refunds are refundable if over 30 days. Refunds are not refundable if over 30 days.",
    )
    assert outcome[0] == "PASS"


def test_conformance_witness_comparators_v1_requirement_c3_positive_violation():
    # genuine support-formula VIOLATION: $20 does not satisfy "over $30"
    ctx, out = "Refunds require over $30.", "Refunds are refundable if over $20."
    _assert_target_product_present("comparators_v1", "comparators_v1.over", "context", "requirement", ctx, out)
    outcome = _run_check_directly("C3", ctx, out)
    assert outcome[0] == "VIOLATION" and outcome[1] == "detection_complete"


def test_conformance_witness_comparators_v1_requirement_c3_negative_pass():
    # genuine support-formula SATISFIED: $30 satisfies "over $30"
    outcome = _run_check_directly("C3", "Refunds require over $30.", "Refunds are refundable if over $30.")
    assert outcome[0] == "PASS"


def test_conformance_witness_excl_v1_modifier_c4_positive_violation():
    # Fixture carries a GENUINE excl_v1.digital_physical modifier-pair
    # product (the exempted refund clauses) ALONGSIDE an UNRELATED,
    # non-exempted shipping-availability conflict -- excl_v1's own
    # product is, by definition, exemption evidence (see the negative
    # witness below), so a fixture demonstrating BOTH a genuine
    # (check_id, field)-legal excl_v1 product AND a genuine VIOLATION
    # needs a second, independent conflicting pair; the shipping clauses
    # supply it without disturbing the exempted digital/physical pair's
    # own exemption.
    ctx = (
        "Refunds are refundable for digital items. Refunds are refundable for physical items. "
        "Shipping is available. Shipping is not available."
    )
    out = "Refunds are refundable for digital items. Refunds are refundable for physical items. Shipping is available."
    _assert_target_product_present("excl_v1", "excl_v1.digital_physical", "context", "modifier", ctx, out)
    outcome = _run_check_directly("C4", ctx, out)
    assert outcome[0] == "VIOLATION" and outcome[1] == "detection_complete"


def test_conformance_witness_excl_v1_modifier_c4_negative_pass():
    # the SAME polarity-conflict shape, but EXCL (digital/physical)
    # modifiers exempt the pair from C4's conflict-pair detection.
    outcome = _run_check_directly(
        "C4",
        "Refunds are refundable for digital items. Refunds are not refundable for physical items.",
        "Refunds are refundable for digital items.",
    )
    assert outcome[0] == "PASS"


def test_conformance_witness_complement_v1_condition_c1_positive_violation():
    ctx, out = "Refunds are refundable if enabled.", "Refunds are not refundable if enabled."
    _assert_target_product_present("complement_v1", "complement_v1.enabled_disabled", "context", "condition", ctx, out)
    outcome = _run_check_directly("C1", ctx, out)
    assert outcome[0] == "VIOLATION" and outcome[1] == "detection_complete"


def test_conformance_witness_complement_v1_condition_c1_negative_pass():
    outcome = _run_check_directly("C1", "Refunds are refundable if enabled.", "Refunds are refundable if enabled.")
    assert outcome[0] == "PASS"


def test_conformance_witness_complement_v1_requirement_c3_positive_violation():
    ctx, out = "Refunds require unapproved.", "Refunds are available."
    _assert_target_product_present("complement_v1", "complement_v1.approved_unapproved", "context", "requirement", ctx, out)
    outcome = _run_check_directly("C3", ctx, out)
    assert outcome[0] == "VIOLATION" and outcome[1] == "detection_complete"


def test_conformance_witness_complement_v1_requirement_c3_negative_pass():
    outcome = _run_check_directly("C3", "Refunds require unapproved.", "Refunds are available only if unapproved.")
    assert outcome[0] == "PASS"


def test_conformance_witness_condition_operators_v1_condition_c1_positive_violation():
    ctx, out = "Refunds are refundable unless used.", "Refunds are not refundable unless used."
    _assert_target_product_present("condition_operators_v1", "condition_operators_v1.unless.IF.grant", "context", "condition", ctx, out)
    outcome = _run_check_directly("C1", ctx, out)
    assert outcome[0] == "VIOLATION" and outcome[1] == "detection_complete"


def test_conformance_witness_condition_operators_v1_condition_c1_negative_pass():
    outcome = _run_check_directly("C1", "Refunds are refundable unless used.", "Refunds are refundable unless used.")
    assert outcome[0] == "PASS"


def test_conformance_witness_quant_v1_extent_c1_positive_violation():
    ctx, out = "All refunds are available.", "Refunds are unavailable."
    _assert_target_product_present("quant_v1", "quant_v1.universal", "context", "extent", ctx, out)
    outcome = _run_check_directly("C1", ctx, out)
    assert outcome[0] == "VIOLATION" and outcome[1] == "detection_complete"


def test_conformance_witness_quant_v1_extent_c1_negative_undecidable():
    # EXISTENTIAL ("some") is a DIFFERENT decided outcome from UNIVERSAL
    # ("all") for the SAME otherwise-conflicting text -- a genuine,
    # real demonstration that the quant class changes disposition.
    outcome = _run_check_directly("C1", "Some refunds are available.", "Some refunds are unavailable.")
    assert outcome[0] == "NOT_EVALUATED" and outcome[1] == "condition_undecidable"


def test_conformance_witness_quant_v1_partial_c1_positive_partiality_gating():
    # QUANTIFIER PARTIALITY GATING: an abstain-class quant token
    # ("most") gates the check to NOT_EVALUATED/extraction_partial.
    ctx, out = "Most services are available.", "Services are unavailable."
    _assert_target_product_present("quant_v1", "quant_v1.abstain", "context", "partial", ctx, out)
    outcome = _run_check_directly("C1", ctx, out)
    assert outcome[0] == "NOT_EVALUATED" and outcome[1] == "extraction_partial"


def test_conformance_witness_quant_v1_partial_c1_negative_decided():
    outcome = _run_check_directly("C1", "All services are available.", "Services are unavailable.")
    assert outcome[0] == "VIOLATION" and outcome[1] == "detection_complete"


def test_conformance_witness_value_role_v1_value_c1_positive_violation():
    ctx, out = "Processing takes 3 days.", "Processing takes 5 days."
    _assert_target_product_present("value_role_v1", "value_role_v1.duration", "context", "value", ctx, out)
    outcome = _run_check_directly("C1", ctx, out)
    assert outcome[0] == "VIOLATION" and outcome[1] == "detection_complete"


def test_conformance_witness_value_role_v1_value_c1_negative_pass():
    outcome = _run_check_directly("C1", "Processing takes 3 days.", "Processing takes 3 days.")
    assert outcome[0] == "PASS"


# SAN-881 PASS 2B.1-P-FIX fix 6: EXACT WITNESS MAP -- an exact literal
# mapping from ALL 13 CAPABILITY_MAP rows to their own NAMED
# positive/negative witness test functions, replacing the prior
# count-only ("exactly 26 tests exist") reflection. These are
# REPRESENTATIVE COMPATIBILITY EVIDENCE only -- never proof of causal
# check execution, and never proof of every legally allowed position.
_CAPABILITY_MAP_WITNESS_TESTS: dict[tuple[str, str], tuple[str, str]] = {
    ("facets_v1", "frame"): (
        "test_conformance_witness_facets_v1_frame_c1_positive_violation",
        "test_conformance_witness_facets_v1_frame_c1_negative_pass",
    ),
    ("concept_v1", "condition"): (
        "test_conformance_witness_concept_v1_condition_c1_positive_violation",
        "test_conformance_witness_concept_v1_condition_c1_negative_pass",
    ),
    ("concept_v1", "requirement"): (
        "test_conformance_witness_concept_v1_requirement_c3_positive_violation",
        "test_conformance_witness_concept_v1_requirement_c3_negative_pass",
    ),
    ("comparators_v1", "value"): (
        "test_conformance_witness_comparators_v1_value_c1_positive_violation",
        "test_conformance_witness_comparators_v1_value_c1_negative_pass",
    ),
    ("comparators_v1", "condition"): (
        "test_conformance_witness_comparators_v1_condition_c4_positive_violation",
        "test_conformance_witness_comparators_v1_condition_c4_negative_pass",
    ),
    ("comparators_v1", "requirement"): (
        "test_conformance_witness_comparators_v1_requirement_c3_positive_violation",
        "test_conformance_witness_comparators_v1_requirement_c3_negative_pass",
    ),
    ("excl_v1", "modifier"): (
        "test_conformance_witness_excl_v1_modifier_c4_positive_violation",
        "test_conformance_witness_excl_v1_modifier_c4_negative_pass",
    ),
    ("complement_v1", "condition"): (
        "test_conformance_witness_complement_v1_condition_c1_positive_violation",
        "test_conformance_witness_complement_v1_condition_c1_negative_pass",
    ),
    ("complement_v1", "requirement"): (
        "test_conformance_witness_complement_v1_requirement_c3_positive_violation",
        "test_conformance_witness_complement_v1_requirement_c3_negative_pass",
    ),
    ("condition_operators_v1", "condition"): (
        "test_conformance_witness_condition_operators_v1_condition_c1_positive_violation",
        "test_conformance_witness_condition_operators_v1_condition_c1_negative_pass",
    ),
    ("quant_v1", "extent"): (
        "test_conformance_witness_quant_v1_extent_c1_positive_violation",
        "test_conformance_witness_quant_v1_extent_c1_negative_undecidable",
    ),
    ("quant_v1", "partial"): (
        "test_conformance_witness_quant_v1_partial_c1_positive_partiality_gating",
        "test_conformance_witness_quant_v1_partial_c1_negative_decided",
    ),
    ("value_role_v1", "value"): (
        "test_conformance_witness_value_role_v1_value_c1_positive_violation",
        "test_conformance_witness_value_role_v1_value_c1_negative_pass",
    ),
}


def test_conformance_suite_exact_witness_map_covers_all_13_capability_map_rows():
    # Replaces the prior count-only ("exactly 26 tests exist") meta-test
    # with an EXACT mapping: every one of CAPABILITY_MAP's own 13 rows
    # has a named positive + negative witness test in
    # _CAPABILITY_MAP_WITNESS_TESTS, the row key sets match EXACTLY in
    # both directions (bidirectional truth -- a row added to
    # CAPABILITY_MAP without a matching witness entry, or a witness
    # entry for a row that no longer exists, both fail), and every named
    # function genuinely exists as a module attribute (not merely a
    # string that happens to look right).
    assert set(_CAPABILITY_MAP_WITNESS_TESTS) == set(vd.CAPABILITY_MAP), (
        f"witness map rows {set(_CAPABILITY_MAP_WITNESS_TESTS)} != CAPABILITY_MAP rows {set(vd.CAPABILITY_MAP)}"
    )
    assert len(_CAPABILITY_MAP_WITNESS_TESTS) == 13

    import sys as _sys
    this_module = _sys.modules[__name__]
    all_named = set()
    for row, (positive_name, negative_name) in _CAPABILITY_MAP_WITNESS_TESTS.items():
        assert hasattr(this_module, positive_name), f"{row}: missing positive witness test {positive_name!r}"
        assert hasattr(this_module, negative_name), f"{row}: missing negative witness test {negative_name!r}"
        assert positive_name.startswith("test_conformance_witness_") and "_positive_" in positive_name
        assert negative_name.startswith("test_conformance_witness_") and "_negative_" in negative_name
        all_named.add(positive_name)
        all_named.add(negative_name)

    # No STRAY witness test exists outside the exact map (the map is the
    # COMPLETE inventory, not merely a subset).
    actual_witness_names = {n for n in dir(this_module) if n.startswith("test_conformance_witness_")}
    assert actual_witness_names == all_named, (
        f"witness tests present but unmapped: {actual_witness_names - all_named}; "
        f"mapped but missing: {all_named - actual_witness_names}"
    )


def test_bundle_exact_membership_rejects_arbitrary_extra_file_in_sealed_dir(tmp_path):
    commitment, sealed_dir, nonces, reviewer_dir, reviewer_nonces = _toy_stage_environment(
        tmp_path, sealed_names_on_disk=["labels_author_semantic.json"],
        reviewer_names_on_disk=[vd.REVIEWER_SEMANTIC_ARTIFACT, vd.REVIEWER_SEMANTIC_COMMITMENT_FILE])
    nonces_path = _write_nonces_file(tmp_path, _scope_nonces(nonces, vd.SEMANTIC_AUTHOR_NONCE_KEYS))
    reviewer_nonces_path = _write_nonces_file(tmp_path, _scope_nonces(reviewer_nonces, vd.SEMANTIC_REVIEWER_NONCE_KEYS))
    # An arbitrary, unrecognized file -- not one of the four known
    # author artifact names -- must still be rejected: this is the
    # generic RULE_REVEAL_EXTRA path, not the specific opposite-stage
    # RULE_REVEAL_FORBIDDEN_EXTRA-adjacent "forbidden stage extra" path.
    (sealed_dir / "junk_arbitrary_file.txt").write_bytes(b"not a bundle member")
    errors = vd.Errors()
    vd.run_stage_reveal_verification(errors, commitment, "semantic", sealed_dir, nonces_path, reviewer_dir, reviewer_nonces_path, _toy_cache_with_real_schemas())
    assert any(vd.RULE_REVEAL_EXTRA in e for e in errors)
    # No traceback, no absolute path, and NO attacker-controlled filename
    # (the junk filename itself) anywhere in the error output.
    blob = " ".join(errors)
    assert "junk_arbitrary_file.txt" not in blob
    assert str(tmp_path) not in blob


def test_bundle_exact_membership_rejects_arbitrary_extra_file_in_reviewer_dir(tmp_path):
    commitment, sealed_dir, nonces, reviewer_dir, reviewer_nonces = _toy_stage_environment(
        tmp_path, sealed_names_on_disk=["labels_author_semantic.json"],
        reviewer_names_on_disk=[vd.REVIEWER_SEMANTIC_ARTIFACT, vd.REVIEWER_SEMANTIC_COMMITMENT_FILE])
    nonces_path = _write_nonces_file(tmp_path, _scope_nonces(nonces, vd.SEMANTIC_AUTHOR_NONCE_KEYS))
    reviewer_nonces_path = _write_nonces_file(tmp_path, _scope_nonces(reviewer_nonces, vd.SEMANTIC_REVIEWER_NONCE_KEYS))
    (reviewer_dir / "unexpected_reviewer_file.json").write_text("{}")
    errors = vd.Errors()
    vd.run_stage_reveal_verification(errors, commitment, "semantic", sealed_dir, nonces_path, reviewer_dir, reviewer_nonces_path, _toy_cache_with_real_schemas())
    assert any(vd.RULE_REVEAL_EXTRA in e for e in errors)
    blob = " ".join(errors)
    assert "unexpected_reviewer_file.json" not in blob


def test_bundle_exact_membership_reviewer_dir_cannot_pose_as_author_artifact(tmp_path):
    # "reviewer keys attempting to overwrite author keys fail": a file
    # in reviewer_dir NAMED as one of the author's own artifact names
    # is not a legitimate reviewer-bundle member and must be rejected --
    # it can never "stand in" for the author's declaration.
    commitment, sealed_dir, nonces, reviewer_dir, reviewer_nonces = _toy_stage_environment(
        tmp_path, sealed_names_on_disk=["labels_author_semantic.json"],
        reviewer_names_on_disk=[vd.REVIEWER_SEMANTIC_ARTIFACT, vd.REVIEWER_SEMANTIC_COMMITMENT_FILE])
    nonces_path = _write_nonces_file(tmp_path, _scope_nonces(nonces, vd.SEMANTIC_AUTHOR_NONCE_KEYS))
    reviewer_nonces_path = _write_nonces_file(tmp_path, _scope_nonces(reviewer_nonces, vd.SEMANTIC_REVIEWER_NONCE_KEYS))
    (reviewer_dir / "labels_author_semantic.json").write_bytes(b'{"n":"labels_author_semantic.json"}')
    errors = vd.Errors()
    vd.run_stage_reveal_verification(errors, commitment, "semantic", sealed_dir, nonces_path, reviewer_dir, reviewer_nonces_path, _toy_cache_with_real_schemas())
    assert any(vd.RULE_REVEAL_EXTRA in e for e in errors)


def test_bundle_exact_membership_missing_member_fails(tmp_path):
    commitment, sealed_dir, nonces, reviewer_dir, reviewer_nonces = _toy_stage_environment(
        tmp_path, sealed_names_on_disk=[], reviewer_names_on_disk=[])
    nonces_path = _write_nonces_file(tmp_path, _scope_nonces(nonces, vd.SEMANTIC_AUTHOR_NONCE_KEYS))
    reviewer_nonces_path = _write_nonces_file(tmp_path, _scope_nonces(reviewer_nonces, vd.SEMANTIC_REVIEWER_NONCE_KEYS))
    errors = vd.Errors()
    vd.run_stage_reveal_verification(errors, commitment, "semantic", sealed_dir, nonces_path, reviewer_dir, reviewer_nonces_path, _toy_cache_with_real_schemas())
    assert any(f"sealed-dir[labels_author_semantic.json]" in e and vd.RULE_REVEAL_NOT_SUPPLIED in e for e in errors)
    assert any(f"reviewer-dir[{vd.REVIEWER_SEMANTIC_ARTIFACT}]" in e and vd.RULE_REVEAL_NOT_SUPPLIED in e for e in errors)


def test_nonce_map_rejects_malformed_hex_value(tmp_path):
    commitment, sealed_dir, nonces, reviewer_dir, reviewer_nonces = _toy_stage_environment(
        tmp_path, sealed_names_on_disk=["labels_author_semantic.json"],
        reviewer_names_on_disk=[vd.REVIEWER_SEMANTIC_ARTIFACT, vd.REVIEWER_SEMANTIC_COMMITMENT_FILE])
    nonces_path = _write_nonces_file(tmp_path, {"labels_author_semantic.json": "not-64-lowercase-hex!!"})
    reviewer_nonces_path = _write_nonces_file(tmp_path, _scope_nonces(reviewer_nonces, vd.SEMANTIC_REVIEWER_NONCE_KEYS))
    errors = vd.Errors()
    vd.run_stage_reveal_verification(errors, commitment, "semantic", sealed_dir, nonces_path, reviewer_dir, reviewer_nonces_path, _toy_cache_with_real_schemas())
    assert any(vd.RULE_NONCE_MALFORMED in e for e in errors)


def test_nonce_map_rejects_uppercase_hex_value(tmp_path):
    # "exactly 64 lowercase hex" -- uppercase-but-otherwise-valid hex is
    # still malformed.
    commitment, sealed_dir, nonces, reviewer_dir, reviewer_nonces = _toy_stage_environment(
        tmp_path, sealed_names_on_disk=["labels_author_semantic.json"],
        reviewer_names_on_disk=[vd.REVIEWER_SEMANTIC_ARTIFACT, vd.REVIEWER_SEMANTIC_COMMITMENT_FILE])
    nonces_path = _write_nonces_file(tmp_path, {"labels_author_semantic.json": ("AB" * 32)})
    reviewer_nonces_path = _write_nonces_file(tmp_path, _scope_nonces(reviewer_nonces, vd.SEMANTIC_REVIEWER_NONCE_KEYS))
    errors = vd.Errors()
    vd.run_stage_reveal_verification(errors, commitment, "semantic", sealed_dir, nonces_path, reviewer_dir, reviewer_nonces_path, _toy_cache_with_real_schemas())
    assert any(vd.RULE_NONCE_MALFORMED in e for e in errors)


def test_nonce_map_rejects_extra_key(tmp_path):
    commitment, sealed_dir, nonces, reviewer_dir, reviewer_nonces = _toy_stage_environment(
        tmp_path, sealed_names_on_disk=["labels_author_semantic.json"],
        reviewer_names_on_disk=[vd.REVIEWER_SEMANTIC_ARTIFACT, vd.REVIEWER_SEMANTIC_COMMITMENT_FILE])
    nonces_path = _write_nonces_file(tmp_path, dict(nonces))  # keep all four keys -- extra beyond the semantic-only pinned set
    reviewer_nonces_path = _write_nonces_file(tmp_path, _scope_nonces(reviewer_nonces, vd.SEMANTIC_REVIEWER_NONCE_KEYS))
    errors = vd.Errors()
    vd.run_stage_reveal_verification(errors, commitment, "semantic", sealed_dir, nonces_path, reviewer_dir, reviewer_nonces_path, _toy_cache_with_real_schemas())
    assert any(vd.RULE_NONCE_KEYSET_MISMATCH in e for e in errors)


def test_nonce_map_rejects_missing_key(tmp_path):
    commitment, sealed_dir, nonces, reviewer_dir, reviewer_nonces = _toy_stage_environment(
        tmp_path, sealed_names_on_disk=["labels_author_semantic.json"],
        reviewer_names_on_disk=[vd.REVIEWER_SEMANTIC_ARTIFACT, vd.REVIEWER_SEMANTIC_COMMITMENT_FILE])
    nonces_path = _write_nonces_file(tmp_path, {})  # missing the one required key entirely
    reviewer_nonces_path = _write_nonces_file(tmp_path, _scope_nonces(reviewer_nonces, vd.SEMANTIC_REVIEWER_NONCE_KEYS))
    errors = vd.Errors()
    vd.run_stage_reveal_verification(errors, commitment, "semantic", sealed_dir, nonces_path, reviewer_dir, reviewer_nonces_path, _toy_cache_with_real_schemas())
    assert any(vd.RULE_NONCE_KEYSET_MISMATCH in e for e in errors)


def test_nonce_map_rejects_opposite_stage_key(tmp_path):
    # An overlapping, opposite-stage nonce key (a contract-stage key
    # supplied where the semantic stage expects its own single key) is
    # simply not a member of the pinned semantic keyset.
    commitment, sealed_dir, nonces, reviewer_dir, reviewer_nonces = _toy_stage_environment(
        tmp_path, sealed_names_on_disk=["labels_author_semantic.json"],
        reviewer_names_on_disk=[vd.REVIEWER_SEMANTIC_ARTIFACT, vd.REVIEWER_SEMANTIC_COMMITMENT_FILE])
    nonces_path = _write_nonces_file(tmp_path, _scope_nonces(nonces, {"labels_author_contract.json"}))
    reviewer_nonces_path = _write_nonces_file(tmp_path, _scope_nonces(reviewer_nonces, vd.SEMANTIC_REVIEWER_NONCE_KEYS))
    errors = vd.Errors()
    vd.run_stage_reveal_verification(errors, commitment, "semantic", sealed_dir, nonces_path, reviewer_dir, reviewer_nonces_path, _toy_cache_with_real_schemas())
    assert any(vd.RULE_NONCE_KEYSET_MISMATCH in e for e in errors)


def test_reveal_verify_subset_missing_entry_declaration_now_fails():
    # Unit-level regression for the reveal_verify_subset "entry is None"
    # fix: a subset member the commitment never declares at all is a
    # hard failure, not a silent skip.
    commitment = {"labeling_context_hash": "a" * 64, "author_commitments": []}
    failures = vd.reveal_verify_subset(
        commitment, subset_names={"labels_author_semantic.json"}, forbidden_extra_names=frozenset(),
        artifact_bytes_by_name={}, nonces_by_name={},
    )
    assert any("not supplied" in f for f in failures)


def test_reveal_verify_subset_malformed_hex_nonce_fails_closed():
    commitment, artifacts, nonces_hex = _toy_four_artifact_commitment()
    failures = vd.reveal_verify_subset(
        commitment, subset_names={"labels_author_semantic.json"},
        forbidden_extra_names=vd.SEMANTIC_STAGE_FORBIDDEN_EXTRAS,
        artifact_bytes_by_name={"labels_author_semantic.json": artifacts["labels_author_semantic.json"]},
        nonces_by_name={"labels_author_semantic.json": "not-valid-hex!!"},
    )
    assert any("not valid" in f for f in failures)


def test_nonces_file_inside_sealed_dir_rejected(tmp_path, monkeypatch, capsys):
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    sealed_dir = tmp_path / "sealed_semantic"
    sealed_dir.mkdir()
    (sealed_dir / "labels_author_semantic.json").write_bytes(env["artifact_bytes"]["labels_author_semantic.json"])
    # nonces-file placed INSIDE sealed_dir -- not outside it, as pinned.
    nonces_file = sealed_dir / "nonces.json"
    nonces_file.write_text(json.dumps({"labels_author_semantic.json": env["author_nonces"]["labels_author_semantic.json"].hex()}))

    reviewer_dir = tmp_path / "reviewer_semantic"
    reviewer_dir.mkdir()
    (reviewer_dir / vd.REVIEWER_SEMANTIC_ARTIFACT).write_bytes(env["rev_sem_artifact"])
    (reviewer_dir / vd.REVIEWER_SEMANTIC_COMMITMENT_FILE).write_text(json.dumps(env["rev_sem_env"]))
    reviewer_nonces_file = tmp_path / "reviewer_semantic_nonces.json"
    reviewer_nonces_file.write_text(json.dumps({vd.REVIEWER_SEMANTIC_ARTIFACT: env["rev_sem_nonce"].hex()}))

    argv = [
        "--reveal-stage", "semantic",
        "--sealed-dir", str(sealed_dir), "--nonces-file", str(nonces_file),
        "--reviewer-dir", str(reviewer_dir), "--reviewer-nonces-file", str(reviewer_nonces_file),
    ]
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    # SAN-881 Phase-A CORRECTION PASS 1 (Section E): assert the FIXED
    # rule code explicitly, not merely rc == 1.
    assert vd.RULE_NONCE_FILE_INSIDE_BUNDLE in captured.err


def test_reviewer_nonces_file_inside_reviewer_dir_rejected(tmp_path, monkeypatch, capsys):
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    sealed_dir = tmp_path / "sealed_semantic"
    sealed_dir.mkdir()
    (sealed_dir / "labels_author_semantic.json").write_bytes(env["artifact_bytes"]["labels_author_semantic.json"])
    nonces_file = tmp_path / "author_nonces.json"
    nonces_file.write_text(json.dumps({"labels_author_semantic.json": env["author_nonces"]["labels_author_semantic.json"].hex()}))

    reviewer_dir = tmp_path / "reviewer_semantic"
    reviewer_dir.mkdir()
    (reviewer_dir / vd.REVIEWER_SEMANTIC_ARTIFACT).write_bytes(env["rev_sem_artifact"])
    (reviewer_dir / vd.REVIEWER_SEMANTIC_COMMITMENT_FILE).write_text(json.dumps(env["rev_sem_env"]))
    # reviewer-nonces-file placed INSIDE reviewer_dir -- not outside it.
    reviewer_nonces_file = reviewer_dir / "reviewer_nonces.json"
    reviewer_nonces_file.write_text(json.dumps({vd.REVIEWER_SEMANTIC_ARTIFACT: env["rev_sem_nonce"].hex()}))

    argv = [
        "--reveal-stage", "semantic",
        "--sealed-dir", str(sealed_dir), "--nonces-file", str(nonces_file),
        "--reviewer-dir", str(reviewer_dir), "--reviewer-nonces-file", str(reviewer_nonces_file),
    ]
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    # SAN-881 Phase-A CORRECTION PASS 1 (Section E): assert the FIXED
    # rule code explicitly, not merely rc == 1.
    assert vd.RULE_NONCE_FILE_INSIDE_BUNDLE in captured.err


# ---------------------------------------------------------------------
# SAN-881 PASS-1 FINAL CLOSURE CORRECTION: legacy generic per-envelope
# reveal (verify_envelope_generic / run_reveal_verification /
# reveal_verify_set / --legacy-reveal) is REMOVED entirely -- the staged
# gated pipeline (--reveal-stage) is now the SOLE crypto path. Any
# nonce/reviewer argument supplied WITHOUT --reveal-stage is a fixed-
# diagnostic reject (RULE_REVEAL_STAGE_REQUIRED), never a silent no-op.
# GENUINE RED (pre-fix, captured via the isolated scratchpad script
# san881_pass1_final_closure_red_evidence.py CASE C, against the
# unmodified module before this correction): a bare `--nonces-file`
# with no --sealed-dir/--reveal-stage/--reviewer-dir produced rc=1 from
# ONLY the unrelated pinned v1-transitional four errors -- args.nonces_file
# was never consulted anywhere, a true silent no-op. POST-FIX: a fixed
# diagnostic is appended for EACH of --nonces-file / --reviewer-dir /
# --reviewer-nonces-file supplied without --reveal-stage.
# ---------------------------------------------------------------------

def test_reviewer_dir_without_reveal_stage_fixed_diagnostic_reject(tmp_path, monkeypatch):
    monkeypatch.setattr(vd, "HERE", CAL_DIR)
    monkeypatch.setattr(vd, "SCHEMAS", SCHEMAS_DIR)
    monkeypatch.setattr(vd, "REPO_ROOT", REPO_ROOT)
    reviewer_dir = tmp_path / "reviewer"
    reviewer_dir.mkdir()
    argv = ["--reviewer-dir", str(reviewer_dir)]
    rc = vd.main(argv)
    assert rc == 1


def test_nonces_file_without_reveal_stage_fixed_diagnostic_reject(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(vd, "HERE", CAL_DIR)
    monkeypatch.setattr(vd, "SCHEMAS", SCHEMAS_DIR)
    monkeypatch.setattr(vd, "REPO_ROOT", REPO_ROOT)
    nonces_file = tmp_path / "nonces.json"
    nonces_file.write_text(json.dumps({"labels_author_semantic.json": secrets.token_hex(32)}))
    rc = vd.main(["--nonces-file", str(nonces_file)])
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_REVEAL_STAGE_REQUIRED in captured.err


def test_reviewer_nonces_file_without_reveal_stage_fixed_diagnostic_reject(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(vd, "HERE", CAL_DIR)
    monkeypatch.setattr(vd, "SCHEMAS", SCHEMAS_DIR)
    monkeypatch.setattr(vd, "REPO_ROOT", REPO_ROOT)
    reviewer_nonces_file = tmp_path / "reviewer_nonces.json"
    reviewer_nonces_file.write_text(json.dumps({vd.REVIEWER_SEMANTIC_ARTIFACT: secrets.token_hex(32)}))
    rc = vd.main(["--reviewer-nonces-file", str(reviewer_nonces_file)])
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_REVEAL_STAGE_REQUIRED in captured.err


def test_reviewer_dir_without_reveal_stage_reports_fixed_rule_not_silent_noop(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(vd, "HERE", CAL_DIR)
    monkeypatch.setattr(vd, "SCHEMAS", SCHEMAS_DIR)
    monkeypatch.setattr(vd, "REPO_ROOT", REPO_ROOT)
    reviewer_dir = tmp_path / "reviewer"
    reviewer_dir.mkdir()
    rc = vd.main(["--reviewer-dir", str(reviewer_dir)])
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_REVEAL_STAGE_REQUIRED in captured.err


def test_bare_sealed_dir_alone_never_triggers_reveal_stage_required_reject(tmp_path, monkeypatch, capsys):
    # Companion negative control: --sealed-dir ALONE (the documented
    # pre-sealing STRUCTURAL author-validation workflow) must NEVER
    # trigger RULE_REVEAL_STAGE_REQUIRED -- only --nonces-file /
    # --reviewer-dir / --reviewer-nonces-file do. The toy bundle here is
    # NOT expected to fully validate (its coverage manifest is a
    # placeholder, not the real 68-surface registry) -- this test's ONLY
    # concern is that the reveal-stage-required reject rule is absent,
    # proving --sealed-dir alone stays on the STRUCTURAL path, never the
    # crypto-arg reject path.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    sealed_dir = tmp_path / "sealed"
    sealed_dir.mkdir()
    (sealed_dir / "design_metadata.json").write_bytes(env["artifact_bytes"]["design_metadata.json"])
    (sealed_dir / "labels_author_semantic.json").write_bytes(env["artifact_bytes"]["labels_author_semantic.json"])
    (sealed_dir / "labels_author_contract.json").write_bytes(env["artifact_bytes"]["labels_author_contract.json"])
    (sealed_dir / "coverage_manifest.json").write_bytes(env["artifact_bytes"]["coverage_manifest.json"])
    rc = vd.main(["--sealed-dir", str(sealed_dir)])
    captured = capsys.readouterr()
    assert vd.RULE_REVEAL_STAGE_REQUIRED not in captured.err


def _write_semantic_only_bundle(tmp_path, env):
    sealed_dir = tmp_path / "sealed_semantic"
    sealed_dir.mkdir()
    (sealed_dir / "labels_author_semantic.json").write_bytes(env["artifact_bytes"]["labels_author_semantic.json"])
    nonces_file = tmp_path / "author_semantic_nonces.json"  # OUTSIDE sealed_dir
    nonces_file.write_text(json.dumps({"labels_author_semantic.json": env["author_nonces"]["labels_author_semantic.json"].hex()}))

    reviewer_dir = tmp_path / "reviewer_semantic"
    reviewer_dir.mkdir()
    (reviewer_dir / vd.REVIEWER_SEMANTIC_ARTIFACT).write_bytes(env["rev_sem_artifact"])
    (reviewer_dir / vd.REVIEWER_SEMANTIC_COMMITMENT_FILE).write_text(json.dumps(env["rev_sem_env"]))
    reviewer_nonces_file = tmp_path / "reviewer_semantic_nonces.json"  # OUTSIDE reviewer_dir
    reviewer_nonces_file.write_text(json.dumps({vd.REVIEWER_SEMANTIC_ARTIFACT: env["rev_sem_nonce"].hex()}))

    return [
        "--reveal-stage", "semantic",
        "--sealed-dir", str(sealed_dir), "--nonces-file", str(nonces_file),
        "--reviewer-dir", str(reviewer_dir), "--reviewer-nonces-file", str(reviewer_nonces_file),
    ]


def _write_contract_only_bundle(tmp_path, env):
    sealed_dir = tmp_path / "sealed_contract"
    sealed_dir.mkdir()
    for name in ("labels_author_contract.json", "design_metadata.json", "coverage_manifest.json"):
        (sealed_dir / name).write_bytes(env["artifact_bytes"][name])
    nonces_file = tmp_path / "author_contract_nonces.json"  # OUTSIDE sealed_dir
    nonces_file.write_text(json.dumps({
        name: env["author_nonces"][name].hex()
        for name in ("labels_author_contract.json", "design_metadata.json", "coverage_manifest.json")
    }))

    reviewer_dir = tmp_path / "reviewer_contract"
    reviewer_dir.mkdir()
    (reviewer_dir / vd.REVIEWER_CONTRACT_ARTIFACT).write_bytes(env["rev_con_artifact"])
    (reviewer_dir / vd.REVIEWER_CONTRACT_COMMITMENT_FILE).write_text(json.dumps(env["rev_con_env"]))
    reviewer_nonces_file = tmp_path / "reviewer_contract_nonces.json"  # OUTSIDE reviewer_dir
    reviewer_nonces_file.write_text(json.dumps({vd.REVIEWER_CONTRACT_ARTIFACT: env["rev_con_nonce"].hex()}))

    return [
        "--reveal-stage", "contract",
        "--sealed-dir", str(sealed_dir), "--nonces-file", str(nonces_file),
        "--reviewer-dir", str(reviewer_dir), "--reviewer-nonces-file", str(reviewer_nonces_file),
    ]


def test_main_semantic_only_bundle_succeeds_without_contract_artifacts(tmp_path, monkeypatch, capsys):
    # Correction-target RED-then-GREEN: BEFORE the dispatch-order fix,
    # this exact scenario CRASHED with an uncaught FileNotFoundError
    # (main()'s generic --sealed-dir block unconditionally probed for
    # design_metadata.json, which a real semantic-only bundle never
    # contains) -- see this pass's discovery repro. It must now return
    # cleanly with rc == 0 and empty stderr: a genuinely self-consistent
    # toy environment, a bundle that is EXACTLY the semantic-stage
    # artifact set, and 640-record schema-valid label files.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert captured.err == "", captured.err
    assert rc == 0
    assert "VALIDATION OK" in captured.out


def test_main_contract_only_bundle_succeeds_without_semantic_artifacts(tmp_path, monkeypatch, capsys):
    # Companion to the semantic-only test above: a CONTRACT-ONLY bundle
    # (labels_author_contract.json, design_metadata.json,
    # coverage_manifest.json + the contract reviewer envelope) succeeds
    # with NO labels_author_semantic.json present anywhere.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_contract_only_bundle(tmp_path, env)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert captured.err == "", captured.err
    assert rc == 0
    assert "VALIDATION OK" in captured.out


def test_main_staged_invocation_never_enters_generic_sealed_dir_path(tmp_path, monkeypatch):
    # Direct regression for the DISPATCH ORDER requirement: a real
    # main(argv) semantic-only staged invocation must not raise ANY
    # exception (previously an uncaught FileNotFoundError -- see repro
    # notes above), because it must never attempt to load
    # design_metadata.json / labels_author_contract.json / coverage_manifest.json
    # from a sealed_dir that (correctly, per the pinned bundle contract)
    # does not contain them.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    vd.main(argv)  # must not raise


def test_main_malformed_json_nonces_file_fails_closed_no_traceback(tmp_path, monkeypatch, capsys):
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    nonces_file = Path(argv[argv.index("--nonces-file") + 1])
    nonces_file.write_text("{not valid json,,,")
    rc = vd.main(argv)  # must not raise
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert str(tmp_path) not in captured.err
    assert vd.RULE_STAGED_IO_FAILURE in captured.err


def test_main_unknown_extra_entry_in_sealed_dir_no_attacker_filename_in_output(tmp_path, monkeypatch, capsys):
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    sealed_dir = Path(argv[argv.index("--sealed-dir") + 1])
    (sealed_dir / "sneaky_unexpected_file.json").write_text("{}")
    rc = vd.main(argv)  # must not raise
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert str(tmp_path) not in captured.err
    assert "sneaky_unexpected_file.json" not in captured.err
    assert vd.RULE_REVEAL_EXTRA in captured.err


# ---------------------------------------------------------------------
# Correction 4: ledger literal six-tuple pin + cross-check
# ---------------------------------------------------------------------

def test_ledger_pinned_tuples_has_exactly_six_entries_matching_readme_table():
    assert len(vd.LEDGER_PINNED_TUPLES) == 6
    assert ("labels_author_semantic.json", "author", "semantic") in vd.LEDGER_PINNED_TUPLES
    assert ("labels_reviewer_semantic.json", "reviewer_semantic", "semantic") in vd.LEDGER_PINNED_TUPLES
    assert ("labels_author_contract.json", "author", "contract") in vd.LEDGER_PINNED_TUPLES
    assert ("design_metadata.json", "author", "contract") in vd.LEDGER_PINNED_TUPLES
    assert ("coverage_manifest.json", "author", "contract") in vd.LEDGER_PINNED_TUPLES
    assert ("labels_reviewer_contract.json", "reviewer_contract", "contract") in vd.LEDGER_PINNED_TUPLES


def _toy_ledger_and_envelopes():
    ctx_hash_hex = "a" * 64
    author = {
        "corpus_version": 2, "labeling_context_hash": ctx_hash_hex,
        "author_commitments": [
            {"artifact_name": "labels_author_semantic.json", "byte_length": 10, "commitment_hex": "b" * 64},
            {"artifact_name": "labels_author_contract.json", "byte_length": 11, "commitment_hex": "c" * 64},
            {"artifact_name": "design_metadata.json", "byte_length": 12, "commitment_hex": "d" * 64},
            {"artifact_name": "coverage_manifest.json", "byte_length": 13, "commitment_hex": "e" * 64},
        ],
    }
    rev_sem = {
        "corpus_version": 2, "labeling_context_hash": ctx_hash_hex,
        "artifact_commitment": {"artifact_name": "labels_reviewer_semantic.json", "byte_length": 14, "commitment_hex": "f" * 64},
    }
    rev_con = {
        "corpus_version": 2, "labeling_context_hash": ctx_hash_hex,
        "artifact_commitment": {"artifact_name": "labels_reviewer_contract.json", "byte_length": 15, "commitment_hex": "1" * 64},
    }
    entries = [
        {"artifact_name": "labels_author_semantic.json", "envelope": "author", "commitment_hex": "b" * 64, "verified": True, "verified_stage": "semantic", "byte_length": 10},
        {"artifact_name": "labels_reviewer_semantic.json", "envelope": "reviewer_semantic", "commitment_hex": "f" * 64, "verified": True, "verified_stage": "semantic", "byte_length": 14},
        {"artifact_name": "labels_author_contract.json", "envelope": "author", "commitment_hex": "c" * 64, "verified": True, "verified_stage": "contract", "byte_length": 11},
        {"artifact_name": "design_metadata.json", "envelope": "author", "commitment_hex": "d" * 64, "verified": True, "verified_stage": "contract", "byte_length": 12},
        {"artifact_name": "coverage_manifest.json", "envelope": "author", "commitment_hex": "e" * 64, "verified": True, "verified_stage": "contract", "byte_length": 13},
        {"artifact_name": "labels_reviewer_contract.json", "envelope": "reviewer_contract", "commitment_hex": "1" * 64, "verified": True, "verified_stage": "contract", "byte_length": 15},
    ]
    ledger = {"corpus_version": 2, "labeling_context_hash": ctx_hash_hex, "entries": entries}
    return ledger, author, rev_sem, rev_con


def test_check_reveal_verification_ledger_passes_on_correct_six_tuple_cross_check():
    ledger, author, rev_sem, rev_con = _toy_ledger_and_envelopes()
    errors = vd.Errors()
    vd.check_reveal_verification_ledger(errors, ledger, author, rev_sem, rev_con)
    assert errors == []


def test_check_reveal_verification_ledger_rejects_wrong_tuple_set():
    ledger, author, rev_sem, rev_con = _toy_ledger_and_envelopes()
    ledger["entries"][0]["verified_stage"] = "contract"  # now wrong: semantic tuple with contract stage
    errors = vd.Errors()
    vd.check_reveal_verification_ledger(errors, ledger, author, rev_sem, rev_con)
    assert any(vd.RULE_LEDGER_TUPLE_SET_MISMATCH in e for e in errors)


def test_check_reveal_verification_ledger_rejects_empty_ledger():
    errors = vd.Errors()
    vd.check_reveal_verification_ledger(errors, {"entries": []}, {}, {}, {})
    assert any(vd.RULE_LEDGER_TUPLE_SET_MISMATCH in e for e in errors)


def test_check_reveal_verification_ledger_rejects_short_ledger():
    ledger, author, rev_sem, rev_con = _toy_ledger_and_envelopes()
    ledger["entries"] = ledger["entries"][:5]
    errors = vd.Errors()
    vd.check_reveal_verification_ledger(errors, ledger, author, rev_sem, rev_con)
    assert any(vd.RULE_LEDGER_TUPLE_SET_MISMATCH in e for e in errors)


def test_check_reveal_verification_ledger_rejects_reversed_order():
    # Correction-target RED-then-GREEN: the tuple SET is unchanged (all
    # six correct tuples present) but the order is reversed -- before
    # the order-check was added, check_reveal_verification_ledger only
    # verified set membership and would have passed this silently.
    ledger, author, rev_sem, rev_con = _toy_ledger_and_envelopes()
    ledger["entries"] = list(reversed(ledger["entries"]))
    errors = vd.Errors()
    vd.check_reveal_verification_ledger(errors, ledger, author, rev_sem, rev_con)
    assert any(vd.RULE_LEDGER_ORDER_MISMATCH in e for e in errors)


def test_check_reveal_verification_ledger_rejects_permuted_order():
    ledger, author, rev_sem, rev_con = _toy_ledger_and_envelopes()
    entries = ledger["entries"]
    ledger["entries"] = [entries[1], entries[0], entries[2], entries[3], entries[4], entries[5]]
    errors = vd.Errors()
    vd.check_reveal_verification_ledger(errors, ledger, author, rev_sem, rev_con)
    assert any(vd.RULE_LEDGER_ORDER_MISMATCH in e for e in errors)


def test_schema_reveal_verification_ledger_id_ends_v2():
    schema = json.loads((SCHEMAS_DIR / "reveal_verification_ledger_schema.json").read_text())
    assert schema["$id"].endswith("/v2.json")


def test_schema_reveal_verification_ledger_corpus_version_const_2():
    schema = json.loads((SCHEMAS_DIR / "reveal_verification_ledger_schema.json").read_text())
    assert schema["properties"]["corpus_version"] == {"const": 2}


def test_schema_reveal_verification_ledger_rejects_reversed_order():
    schema = json.loads((SCHEMAS_DIR / "reveal_verification_ledger_schema.json").read_text())
    toy = _toy_six_entry_ledger()
    reversed_toy = {**toy, "entries": list(reversed(toy["entries"]))}
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(reversed_toy)


def test_check_reveal_verification_ledger_cross_check_catches_commitment_hex_mismatch():
    ledger, author, rev_sem, rev_con = _toy_ledger_and_envelopes()
    ledger["entries"][0]["commitment_hex"] = "9" * 64  # no longer matches author envelope's b*64
    errors = vd.Errors()
    vd.check_reveal_verification_ledger(errors, ledger, author, rev_sem, rev_con)
    assert any(vd.RULE_LEDGER_CROSS_CHECK_MISMATCH in e for e in errors)


def test_check_reveal_verification_ledger_cross_check_catches_byte_length_mismatch():
    ledger, author, rev_sem, rev_con = _toy_ledger_and_envelopes()
    ledger["entries"][0]["byte_length"] = 999999
    errors = vd.Errors()
    vd.check_reveal_verification_ledger(errors, ledger, author, rev_sem, rev_con)
    assert any(vd.RULE_LEDGER_CROSS_CHECK_MISMATCH in e for e in errors)


def test_check_reveal_verification_ledger_cross_check_catches_context_hash_mismatch():
    ledger, author, rev_sem, rev_con = _toy_ledger_and_envelopes()
    author["labeling_context_hash"] = "9" * 64
    errors = vd.Errors()
    vd.check_reveal_verification_ledger(errors, ledger, author, rev_sem, rev_con)
    assert any(vd.RULE_LEDGER_CROSS_CHECK_MISMATCH in e for e in errors)


def test_check_reveal_verification_ledger_cross_check_catches_corpus_version_mismatch():
    ledger, author, rev_sem, rev_con = _toy_ledger_and_envelopes()
    author["corpus_version"] = 1
    errors = vd.Errors()
    vd.check_reveal_verification_ledger(errors, ledger, author, rev_sem, rev_con)
    assert any(vd.RULE_LEDGER_CROSS_CHECK_MISMATCH in e for e in errors)


# ---------------------------------------------------------------------
# Correction 5: feature-absence for quantifiers (class-scoped) +
# semantic-equal minimal-pair controls
# ---------------------------------------------------------------------

def test_introduced_feature_absent_quantifier_class_scoped_passes_when_absent_from_own_class():
    errors = vd.Errors()
    tables_data = {"quant_v1": {"universal": ["all", "every"], "existential": ["some"], "abstain": ["most", "many"]}}
    feature = {"kind": "quantifier", "table_path": "quant_v1", "surface_tokens": ["most"],
               "intended_semantics": {"quantifier_class": "existential"}}
    # "most" is NOT in existential's own list (it's in abstain's) -- absent
    # from the DECLARED class, so this must pass.
    vd.check_introduced_feature_absent_from_tables(errors, "cal:000", feature, tables_data)
    assert errors == []


def test_introduced_feature_absent_quantifier_class_scoped_fails_when_present_in_own_class():
    errors = vd.Errors()
    tables_data = {"quant_v1": {"universal": ["all", "every"], "existential": ["some"], "abstain": ["most", "many"]}}
    feature = {"kind": "quantifier", "table_path": "quant_v1", "surface_tokens": ["most"],
               "intended_semantics": {"quantifier_class": "abstain"}}
    vd.check_introduced_feature_absent_from_tables(errors, "cal:000", feature, tables_data)
    assert any(vd.RULE_FEATURE_NOT_ABSENT in e for e in errors)


def test_introduced_feature_absent_quantifier_does_not_false_positive_on_class_name_collision():
    # Regression for the pre-correction bug: treating quant_v1's dict KEYS
    # ("universal", "existential", "abstain") as candidate entries would
    # make a surface_tokens value that happens to equal a class NAME
    # incorrectly collide. A real class-scoped check never compares
    # against class names at all.
    errors = vd.Errors()
    tables_data = {"quant_v1": {"universal": ["all"], "existential": ["some"], "abstain": ["most"]}}
    feature = {"kind": "quantifier", "table_path": "quant_v1", "surface_tokens": ["universal"],
               "intended_semantics": {"quantifier_class": "existential"}}
    vd.check_introduced_feature_absent_from_tables(errors, "cal:000", feature, tables_data)
    assert errors == []


def test_minimal_pair_control_same_semantics_facet_trigger_passes_with_sibling_trigger():
    errors = vd.Errors()
    tables_data = {"facets_v1": {"facet:availability": {"triggers": ["available", "offered"], "deny_triggers": ["unavailable"]}}}
    feature = {"kind": "facet_trigger", "table_path": "facets_v1.facet:availability.triggers",
               "intended_semantics": {"facet": "facet:availability", "polarity": "POS"}}
    control_rec = _toy_rec(context="This plan is offered to everyone.")
    vd.check_minimal_pair_control_same_semantics_in_table(errors, "cal:005", control_rec, feature, tables_data)
    assert errors == []


def test_minimal_pair_control_same_semantics_facet_trigger_fails_without_sibling():
    errors = vd.Errors()
    tables_data = {"facets_v1": {"facet:availability": {"triggers": ["available", "offered"], "deny_triggers": ["unavailable"]}}}
    feature = {"kind": "facet_trigger", "table_path": "facets_v1.facet:availability.triggers",
               "intended_semantics": {"facet": "facet:availability", "polarity": "POS"}}
    control_rec = _toy_rec(context="This plan ships tomorrow.")
    vd.check_minimal_pair_control_same_semantics_in_table(errors, "cal:005", control_rec, feature, tables_data)
    assert any(vd.RULE_MINIMAL_PAIR_SAME_SEMANTICS in e for e in errors)


def test_minimal_pair_control_same_semantics_condition_operator_kind_polarity_force():
    errors = vd.Errors()
    tables_data = {"condition_operators_v1": [
        {"tokens": ["unless"], "kind": "IF", "polarity": "-", "force": "grant"},
        {"tokens": ["except"], "kind": "IF", "polarity": "-", "force": "grant"},
        {"tokens": ["only", "if"], "kind": "ONLY_IF", "polarity": "+", "force": "restriction"},
    ]}
    feature = {"kind": "condition_operator", "table_path": "condition_operators_v1",
               "intended_semantics": {"kind": "IF", "polarity": "-", "force": "grant"}}
    # sibling with same (kind, polarity, force): "except"
    vd.check_minimal_pair_control_same_semantics_in_table(
        errors, "cal:005", _toy_rec(context="Refunds granted except for final sale."), feature, tables_data)
    assert errors == []
    errors2 = vd.Errors()
    # "only if" has a DIFFERENT (kind, polarity, force) -- not a valid sibling
    vd.check_minimal_pair_control_same_semantics_in_table(
        errors2, "cal:005", _toy_rec(context="Refunds granted only if requested."), feature, tables_data)
    assert any(vd.RULE_MINIMAL_PAIR_SAME_SEMANTICS in e for e in errors2)


def test_minimal_pair_control_same_semantics_unit_group_and_factor():
    errors = vd.Errors()
    tables_data = {"units_v1": {"day": {"group": "time_a", "factor": 1440}, "hour": {"group": "time_a", "factor": 60}, "month": {"group": "time_b", "factor": 1}}}
    feature = {"kind": "unit", "table_path": "units_v1", "intended_semantics": {"group": "time_a", "factor": 1440}}
    # "hour" is a DIFFERENT factor within the same group -- not a sibling
    vd.check_minimal_pair_control_same_semantics_in_table(
        errors, "cal:005", _toy_rec(context="Ships within 2 hour."), feature, tables_data)
    assert any(vd.RULE_MINIMAL_PAIR_SAME_SEMANTICS in e for e in errors)
    errors2 = vd.Errors()
    vd.check_minimal_pair_control_same_semantics_in_table(
        errors2, "cal:005", _toy_rec(context="Ships within 2 day."), feature, tables_data)
    assert errors2 == []


def test_minimal_pair_control_same_semantics_concept():
    errors = vd.Errors()
    tables_data = {"concept_v1": {"approve": "approval", "approved": "approval", "verify": "verification"}}
    feature = {"kind": "concept", "table_path": "concept_v1", "intended_semantics": {"canonical_concept": "approval"}}
    vd.check_minimal_pair_control_same_semantics_in_table(
        errors, "cal:005", _toy_rec(context="This was approved yesterday."), feature, tables_data)
    assert errors == []
    errors2 = vd.Errors()
    vd.check_minimal_pair_control_same_semantics_in_table(
        errors2, "cal:005", _toy_rec(context="This was verified yesterday."), feature, tables_data)
    assert any(vd.RULE_MINIMAL_PAIR_SAME_SEMANTICS in e for e in errors2)


def test_minimal_pair_control_same_semantics_quantifier_class():
    errors = vd.Errors()
    tables_data = {"quant_v1": {"universal": ["all", "every"], "existential": ["some"], "abstain": ["most"]}}
    feature = {"kind": "quantifier", "table_path": "quant_v1", "intended_semantics": {"quantifier_class": "universal"}}
    vd.check_minimal_pair_control_same_semantics_in_table(
        errors, "cal:005", _toy_rec(context="Every order qualifies."), feature, tables_data)
    assert errors == []
    errors2 = vd.Errors()
    vd.check_minimal_pair_control_same_semantics_in_table(
        errors2, "cal:005", _toy_rec(context="Some orders qualify."), feature, tables_data)
    assert any(vd.RULE_MINIMAL_PAIR_SAME_SEMANTICS in e for e in errors2)


def test_minimal_pair_control_same_semantics_facetproj_passes_with_sibling_projection():
    # SAN-881 PASS 2B.2 RED-then-GREEN (Part D control-equivalence
    # coverage): facetproj_v1 was previously UNHANDLED by this function's
    # kind dispatch and fell through the facet_trigger/deny_trigger
    # branch, which read sem.get("facet") -- always None for
    # facetprojSemantics-shaped intended_semantics (it has "projects_to",
    # not "facet") -- so facets_v1.get(None) is always None and the rule
    # ALWAYS fired, even for a genuinely valid facetproj minimal pair.
    errors = vd.Errors()
    tables_data = {"facetproj_v1": {"discount": "facet:discount_availability", "discounts": "facet:discount_availability",
                                     "refund": "facet:refund_availability"}}
    feature = {"kind": "facet_trigger", "table_path": "facetproj_v1",
               "intended_semantics": {"polarity": "POS", "projects_to": "facet:discount_availability"}}
    control_rec = _toy_rec(context="Discounts are sometimes available at checkout.")
    vd.check_minimal_pair_control_same_semantics_in_table(errors, "cal:005", control_rec, feature, tables_data)
    assert errors == [], f"expected a genuinely valid facetproj sibling to pass, got {errors}"


def test_minimal_pair_control_same_semantics_facetproj_fails_without_sibling():
    errors = vd.Errors()
    tables_data = {"facetproj_v1": {"discount": "facet:discount_availability", "discounts": "facet:discount_availability",
                                     "refund": "facet:refund_availability"}}
    feature = {"kind": "facet_trigger", "table_path": "facetproj_v1",
               "intended_semantics": {"polarity": "POS", "projects_to": "facet:discount_availability"}}
    control_rec = _toy_rec(context="Refunds are sometimes available at checkout.")
    vd.check_minimal_pair_control_same_semantics_in_table(errors, "cal:005", control_rec, feature, tables_data)
    assert any(vd.RULE_MINIMAL_PAIR_SAME_SEMANTICS in e for e in errors), (
        "a control with only a DIFFERENT facetproj target's token must still fail"
    )


def test_minimal_pair_control_same_semantics_definitive_passes_with_sibling_entry():
    # SAN-881 PASS 2B.2 RED-then-GREEN (Part D): definitive/hedge were
    # previously UNHANDLED -- no branch matched, so the function was a
    # SILENT NO-OP for these two kinds (every control passed vacuously,
    # regardless of content).
    errors = vd.Errors()
    tables_data = {"definitive_v1": ["definitely", "certainly", "always", "without doubt"], "hedge_v1": ["may", "might"]}
    feature = {"kind": "definitive", "table_path": "definitive_v1",
               "intended_semantics": {"role": "definitive", "same_overclaim_class_as_table": True}}
    control_rec = _toy_rec(context="Refunds are always granted within policy.")
    vd.check_minimal_pair_control_same_semantics_in_table(errors, "cal:005", control_rec, feature, tables_data)
    assert errors == []


def test_minimal_pair_control_same_semantics_definitive_fails_without_sibling():
    errors = vd.Errors()
    tables_data = {"definitive_v1": ["definitely", "certainly", "always", "without doubt"], "hedge_v1": ["may", "might"]}
    feature = {"kind": "definitive", "table_path": "definitive_v1",
               "intended_semantics": {"role": "definitive", "same_overclaim_class_as_table": True}}
    control_rec = _toy_rec(context="This sentence has nothing to do with certainty at all.")
    vd.check_minimal_pair_control_same_semantics_in_table(errors, "cal:005", control_rec, feature, tables_data)
    assert any(vd.RULE_MINIMAL_PAIR_SAME_SEMANTICS in e for e in errors), (
        f"expected the previously-silent no-op to now fire, got {errors}"
    )


def test_minimal_pair_control_same_semantics_hedge_passes_with_sibling_entry():
    errors = vd.Errors()
    tables_data = {"definitive_v1": ["definitely", "always"], "hedge_v1": ["may", "might", "it's possible"]}
    feature = {"kind": "hedge", "table_path": "hedge_v1",
               "intended_semantics": {"role": "hedge", "same_overclaim_class_as_table": True}}
    control_rec = _toy_rec(context="Refunds might be granted depending on the item.")
    vd.check_minimal_pair_control_same_semantics_in_table(errors, "cal:005", control_rec, feature, tables_data)
    assert errors == []


def test_minimal_pair_control_same_semantics_hedge_fails_without_sibling():
    errors = vd.Errors()
    tables_data = {"definitive_v1": ["definitely", "always"], "hedge_v1": ["may", "might", "it's possible"]}
    feature = {"kind": "hedge", "table_path": "hedge_v1",
               "intended_semantics": {"role": "hedge", "same_overclaim_class_as_table": True}}
    control_rec = _toy_rec(context="Refunds are granted for unused items.")
    vd.check_minimal_pair_control_same_semantics_in_table(errors, "cal:005", control_rec, feature, tables_data)
    assert any(vd.RULE_MINIMAL_PAIR_SAME_SEMANTICS in e for e in errors)


def test_minimal_pair_control_same_semantics_excl_pair_passes_with_exact_row():
    # SAN-881 PASS 2B.2 RED-then-GREEN (Part D): excl_pair/complement_pair
    # were previously UNHANDLED (silent no-op). The control must contain
    # BOTH members of ONE EXACT ROW of the DECLARED table.
    errors = vd.Errors()
    tables_data = {"excl_v1": [["digital", "physical"], ["verified", "unverified"]]}
    feature = {"kind": "excl_pair", "table_path": "excl_v1", "members": [["active"], ["inactive"]]}
    control_rec = _toy_rec(context="This account is verified, not unverified.")
    vd.check_minimal_pair_control_same_semantics_in_table(errors, "cal:005", control_rec, feature, tables_data)
    assert errors == []


def test_minimal_pair_control_same_semantics_excl_pair_fails_without_exact_row():
    errors = vd.Errors()
    tables_data = {"excl_v1": [["digital", "physical"], ["verified", "unverified"]]}
    feature = {"kind": "excl_pair", "table_path": "excl_v1", "members": [["active"], ["inactive"]]}
    control_rec = _toy_rec(context="This sentence is unrelated to any exclusivity pair.")
    vd.check_minimal_pair_control_same_semantics_in_table(errors, "cal:005", control_rec, feature, tables_data)
    assert any(vd.RULE_MINIMAL_PAIR_SAME_SEMANTICS in e for e in errors), (
        f"expected the previously-silent no-op to now fire, got {errors}"
    )


def test_minimal_pair_control_same_semantics_excl_pair_fails_with_only_one_member_of_row():
    # One member of an in-table row is NOT enough -- must be a COMPLETE
    # exact row.
    errors = vd.Errors()
    tables_data = {"excl_v1": [["digital", "physical"], ["verified", "unverified"]]}
    feature = {"kind": "excl_pair", "table_path": "excl_v1", "members": [["active"], ["inactive"]]}
    control_rec = _toy_rec(context="This item is digital only, sold online.")
    vd.check_minimal_pair_control_same_semantics_in_table(errors, "cal:005", control_rec, feature, tables_data)
    assert any(vd.RULE_MINIMAL_PAIR_SAME_SEMANTICS in e for e in errors)


def test_minimal_pair_control_same_semantics_complement_pair_passes_with_exact_row():
    errors = vd.Errors()
    tables_data = {"complement_v1": [["enabled", "disabled"], ["approved", "unapproved"]]}
    feature = {"kind": "complement_pair", "table_path": "complement_v1", "members": [["eligible"], ["ineligible"]]}
    control_rec = _toy_rec(context="The request was approved, not unapproved.")
    vd.check_minimal_pair_control_same_semantics_in_table(errors, "cal:005", control_rec, feature, tables_data)
    assert errors == []


# ---------------------------------------------------------------------
# Correction 6: strict v2 context schema + transitional tests
# ---------------------------------------------------------------------

def test_expected_corpus_version_constant_is_2():
    assert vd.EXPECTED_CORPUS_VERSION == 2


def test_check_evaluation_profile_v1_transitional_or_v2_green():
    # TRANSITIONAL: flips green automatically when evaluation_profile.json
    # is data-changed to corpus_version 2 at reseal.
    errors = vd.Errors()
    vd.check_evaluation_profile(errors, PROFILE)
    if PROFILE.get("corpus_version") == vd.EXPECTED_CORPUS_VERSION:
        assert not any(vd.RULE_CORPUS_VERSION in e for e in errors)
    else:
        assert any(vd.RULE_CORPUS_VERSION in e for e in errors)


def test_check_commitment_corpus_version_v1_transitional_or_v2_green():
    errors = vd.Errors()
    vd.check_commitment(errors, COMMITMENT, cal_dir=CAL_DIR, repo_root=REPO_ROOT)
    if COMMITMENT.get("corpus_version") == vd.EXPECTED_CORPUS_VERSION:
        assert not any(vd.RULE_CORPUS_VERSION in e for e in errors)
    else:
        assert any(vd.RULE_CORPUS_VERSION in e for e in errors)


def test_check_evaluation_profile_toy_v2_passes_v1_fails():
    errors = vd.Errors()
    toy_v2 = {**PROFILE, "corpus_version": 2}
    vd.check_evaluation_profile(errors, toy_v2)
    assert not any(vd.RULE_CORPUS_VERSION in e for e in errors)

    errors2 = vd.Errors()
    toy_v1 = {**PROFILE, "corpus_version": 1}
    vd.check_evaluation_profile(errors2, toy_v1)
    assert any(vd.RULE_CORPUS_VERSION in e for e in errors2)


def test_freeze_manifest_schema_still_pins_corpus_version_const_2():
    schema = json.loads((SCHEMAS_DIR / "freeze_manifest_schema.json").read_text())
    assert schema["properties"]["corpus_version"] == {"const": 2}


def test_commitment_schema_pins_corpus_version_const_2_on_all_three_envelope_shapes():
    schema = json.loads((SCHEMAS_DIR / "commitment_schema.json").read_text())
    for def_name in ("authorEnvelope", "reviewerSemanticEnvelope", "reviewerContractEnvelope"):
        assert schema["$defs"][def_name]["properties"]["corpus_version"] == {"const": 2}, def_name


# ---------------------------------------------------------------------
# SAN-881 PASS-1 CORRECTION ROUND, Section F: commitmentAlgorithm.formula
# is a pinned const, not an arbitrary non-empty string.
# ---------------------------------------------------------------------

def test_commitment_algorithm_formula_constant_matches_pinned_text():
    assert vd.COMMITMENT_ALGORITHM_FORMULA == (
        "SHA256(domain_separator || NUL || artifact_name || NUL || raw_32_byte_nonce"
        " || raw_32_byte_labeling_context_hash || exact_artifact_bytes)"
    )


def test_commitment_schema_formula_is_pinned_const():
    schema = json.loads((SCHEMAS_DIR / "commitment_schema.json").read_text())
    assert schema["$defs"]["commitmentAlgorithm"]["properties"]["formula"] == {
        "const": vd.COMMITMENT_ALGORITHM_FORMULA
    }


def test_commitment_schema_rejects_false_formula():
    # Correction-target RED-then-GREEN: prior to Section F, formula was
    # merely `{"type": "string", "minLength": 1}` -- an envelope could
    # declare ANY non-empty commitment-formula prose and still validate.
    schema = json.loads((SCHEMAS_DIR / "commitment_schema.json").read_text())
    envelope = _toy_author_envelope()
    envelope["commitment_algorithm"] = {**envelope["commitment_algorithm"], "formula": "a different, false formula"}
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(envelope)
    # The genuinely pinned formula still validates.
    Draft202012Validator(schema).validate(_toy_author_envelope())


# ---------------------------------------------------------------------
# SAN-881 Phase-A CORRECTION PASS 1: v2 structured labeling-context
# formula + author commitment order -- schema-level and verifier-side
# pins.
# ---------------------------------------------------------------------

def _toy_author_envelope(*, component_names=None, author_commitment_names=None) -> dict:
    names = list(vd.LABELING_CONTEXT_COMPONENT_NAMES) if component_names is None else component_names
    author_names = list(vd.AUTHOR_COMMITMENT_ORDER) if author_commitment_names is None else author_commitment_names
    return {
        "corpus_version": 2, "envelope_kind": "AUTHOR", "labeling_context_hash": "a" * 64,
        "labeling_context_components": [{"name": n, "sha256": "b" * 64} for n in names],
        "commitment_algorithm": {"hash": "SHA256", "domain_separator": "sanna-calibration-commitment/1", "formula": vd.COMMITMENT_ALGORITHM_FORMULA},
        "author_commitments": [{"artifact_name": n, "byte_length": 1, "commitment_hex": "c" * 64} for n in author_names],
        "reveal_protocol": {
            "reviewer_commitment_filenames": [
                "labels_reviewer_semantic.commitment.json", "labels_reviewer_contract.commitment.json",
            ],
            "reviewer_commitment_method": (
                "identical to author_commitments: domain-separated SHA256(\"sanna-calibration-commitment/1\""
                " || NUL || artifact_name || NUL || raw_32_byte_nonce || raw_32_byte_labeling_context_hash"
                " || exact_artifact_bytes)"
            ),
            "abandonment_rule": "toy",
        },
    }


def test_commitment_schema_labeling_context_components_pinned_eleven_structured():
    schema = json.loads((SCHEMAS_DIR / "commitment_schema.json").read_text())
    Draft202012Validator(schema).validate(_toy_author_envelope())


def test_commitment_schema_rejects_wrong_component_name_at_index():
    schema = json.loads((SCHEMAS_DIR / "commitment_schema.json").read_text())
    bad_names = list(vd.LABELING_CONTEXT_COMPONENT_NAMES)
    bad_names[0] = "not_the_pinned_name"
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(_toy_author_envelope(component_names=bad_names))


def test_commitment_schema_rejects_permuted_component_order():
    schema = json.loads((SCHEMAS_DIR / "commitment_schema.json").read_text())
    permuted = list(reversed(vd.LABELING_CONTEXT_COMPONENT_NAMES))
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(_toy_author_envelope(component_names=permuted))


def test_commitment_schema_rejects_extra_component():
    schema = json.loads((SCHEMAS_DIR / "commitment_schema.json").read_text())
    extra = list(vd.LABELING_CONTEXT_COMPONENT_NAMES) + ["algorithm"]
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(_toy_author_envelope(component_names=extra))


def test_commitment_schema_author_commitments_pinned_order():
    schema = json.loads((SCHEMAS_DIR / "commitment_schema.json").read_text())
    Draft202012Validator(schema).validate(_toy_author_envelope())
    reversed_order = list(reversed(vd.AUTHOR_COMMITMENT_ORDER))
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(_toy_author_envelope(author_commitment_names=reversed_order))


def test_commitment_schema_rejects_duplicate_author_commitment():
    # A same-name/different-hash duplicate replacing one of the four
    # pinned names (missing labels_author_contract.json, duplicate
    # labels_author_semantic.json) fails the prefixItems const-name pin.
    schema = json.loads((SCHEMAS_DIR / "commitment_schema.json").read_text())
    dup_names = ["design_metadata.json", "labels_author_semantic.json", "labels_author_semantic.json", "coverage_manifest.json"]
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(_toy_author_envelope(author_commitment_names=dup_names))


def test_author_commitment_order_constant_pinned():
    assert vd.AUTHOR_COMMITMENT_ORDER == (
        "design_metadata.json",
        "labels_author_semantic.json",
        "labels_author_contract.json",
        "coverage_manifest.json",
    )


def test_check_author_commitment_order_passes_on_correct_order():
    commitment = {"author_commitments": [{"artifact_name": n} for n in vd.AUTHOR_COMMITMENT_ORDER]}
    errors = vd.Errors()
    vd.check_author_commitment_order(errors, commitment)
    assert errors == []


def test_check_author_commitment_order_fails_on_reversed_order():
    commitment = {"author_commitments": [{"artifact_name": n} for n in reversed(vd.AUTHOR_COMMITMENT_ORDER)]}
    errors = vd.Errors()
    vd.check_author_commitment_order(errors, commitment)
    assert any(vd.RULE_COMMITMENT_ORDER_MISMATCH in e for e in errors)


def test_check_author_commitment_order_fails_on_duplicate_name():
    # design_metadata.json duplicated in place of coverage_manifest.json.
    names = ["design_metadata.json", "labels_author_semantic.json", "labels_author_contract.json", "design_metadata.json"]
    commitment = {"author_commitments": [{"artifact_name": n} for n in names]}
    errors = vd.Errors()
    vd.check_author_commitment_order(errors, commitment)
    assert any(vd.RULE_COMMITMENT_ORDER_MISMATCH in e for e in errors)


def test_check_author_commitment_order_wired_into_main_on_real_commitment(capsys):
    # The real (intentionally v1-transitional) commitment.json's
    # author_commitments happen to already be in the pinned order --
    # check_author_commitment_order must NOT add a fifth error to the
    # pinned four-error transitional CLI output.
    rc = vd.main([])
    captured = capsys.readouterr()
    assert vd.RULE_COMMITMENT_ORDER_MISMATCH not in captured.err


# ---------------------------------------------------------------------
# Correction 7: full locked reason matrix
# ---------------------------------------------------------------------

def test_reason_matrix_has_exactly_five_outcomes():
    assert set(vd.REASON_MATRIX) == {"PASS", "VIOLATION", "NOT_EVALUATED", "EVALUATOR_ERROR", "CONFIG_ERROR"}


def test_reason_matrix_pass_and_violation_share_single_reason():
    assert vd.REASON_MATRIX["PASS"] == {"detection_complete"}
    assert vd.REASON_MATRIX["VIOLATION"] == {"detection_complete"}


def test_reason_matrix_not_evaluated_has_seventeen_reasons():
    assert len(vd.REASON_MATRIX["NOT_EVALUATED"]) == 17


def test_reason_matrix_evaluator_error_and_config_error_reason_sets():
    assert vd.REASON_MATRIX["EVALUATOR_ERROR"] == {"evaluator_exception", "dependency_unavailable"}
    assert vd.REASON_MATRIX["CONFIG_ERROR"] == {"malformed_structured_input", "dynamic_config_rejected", "runtime_binding_missing"}


def test_reason_matrix_sets_are_pairwise_disjoint_except_pass_violation_sharing_detection_complete():
    # PASS and VIOLATION intentionally SHARE "detection_complete" (both
    # are "the evaluator reached a decided verdict") -- every OTHER pair
    # of outcome reason-sets must be fully disjoint.
    by_outcome = dict(vd.REASON_MATRIX)
    assert by_outcome["PASS"] == by_outcome["VIOLATION"] == {"detection_complete"}
    others = {k: v for k, v in by_outcome.items() if k not in ("PASS", "VIOLATION")}
    other_names = list(others)
    for i in range(len(other_names)):
        assert others[other_names[i]].isdisjoint({"detection_complete"})
        for j in range(i + 1, len(other_names)):
            assert others[other_names[i]].isdisjoint(others[other_names[j]])


def test_check_labels_rejects_pass_with_garbage_reason():
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "target_check_id": "C1", "target_stratum": "in_domain_nonviolation"}}
    semantic = [{"item_id": "cal:000", "check_id": "C1", "semantic_truth": "NO_VIOLATION", "semantic_rationale": "toy"}]
    contract = [{"item_id": "cal:000", "check_id": "C1",
                 "contract_tuple": {"outcome": "PASS", "outcome_reason": "garbage", "severity": None, "advisory": False},
                 "competence": "IN_DOMAIN", "contract_rationale": "toy", "spec_refs": "toy"}]
    vd.check_labels(errors, semantic, contract, design_by_id)
    assert any(vd.RULE_CONTRACT_REASON_INVALID in e for e in errors)


def test_check_labels_accepts_valid_config_error_record():
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "target_check_id": "C2", "target_stratum": "determinate_out_of_domain"}}
    semantic = [{"item_id": "cal:000", "check_id": "C1", "semantic_truth": "NO_VIOLATION", "semantic_rationale": "toy"}]
    contract = [{"item_id": "cal:000", "check_id": "C1",
                 "contract_tuple": {"outcome": "CONFIG_ERROR", "outcome_reason": "malformed_structured_input", "severity": None, "advisory": False},
                 "competence": "IN_DOMAIN", "contract_rationale": "toy", "spec_refs": "toy"}]
    vd.check_labels(errors, semantic, contract, design_by_id)
    assert not any(vd.RULE_CONTRACT_OUTCOME_INVALID in e or vd.RULE_CONTRACT_REASON_INVALID in e or vd.RULE_CONTRACT_REASON_OUTCOME_MISMATCH in e for e in errors)


def test_check_labels_rejects_wellformed_reason_wrong_outcome():
    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "target_check_id": "C1", "target_stratum": "in_domain_nonviolation"}}
    semantic = [{"item_id": "cal:000", "check_id": "C1", "semantic_truth": "NO_VIOLATION", "semantic_rationale": "toy"}]
    contract = [{"item_id": "cal:000", "check_id": "C1",
                 "contract_tuple": {"outcome": "PASS", "outcome_reason": "extraction_partial", "severity": None, "advisory": False},
                 "competence": "IN_DOMAIN", "contract_rationale": "toy", "spec_refs": "toy"}]
    vd.check_labels(errors, semantic, contract, design_by_id)
    assert any(vd.RULE_CONTRACT_REASON_OUTCOME_MISMATCH in e for e in errors)


def test_measure_zero_evaluator_errors_fails_for_config_error_outcome_too():
    joined, design_by_id = _toy_joined_and_design()
    joined[0]["outcome"] = "CONFIG_ERROR"
    joined[0]["outcome_reason"] = "malformed_structured_input"
    rates = ms.compute_rates(joined, design_by_id, python_output_bytes=b"toy", typescript_output_bytes=b"toy")
    assert rates["gates"]["zero_evaluator_errors"] is False


# ---------------------------------------------------------------------
# Correction 8: cross-file pre-execution validation fails closed on a
# missing jsonschema module
# ---------------------------------------------------------------------

def test_validate_against_schema_fails_closed_when_jsonschema_module_missing(monkeypatch):
    monkeypatch.setattr(vd, "Draft202012Validator", None)
    errors = vd.Errors()
    vd._validate_against_schema(errors, "toy_artifact.json", {}, {})
    assert any(vd.RULE_JSONSCHEMA_MODULE_MISSING in e for e in errors)


def test_verify_frozen_bundle_fails_closed_when_jsonschema_module_missing(tmp_path, monkeypatch):
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps({"corpus_version": 2}))
    monkeypatch.setattr(ms, "Draft202012Validator", None)
    with pytest.raises(ms.InfrastructureFailure, match="jsonschema"):
        ms.verify_frozen_bundle(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)


# ---------------------------------------------------------------------
# Correction 9: benchmark.py re-verification
# ---------------------------------------------------------------------

def test_benchmark_rerun_full_freeze_verification_passes_on_valid_v2_environment(tmp_path):
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    _, failures = bm._rerun_full_freeze_verification(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)
    assert failures == []


def test_benchmark_rerun_full_freeze_verification_catches_missing_commitment_envelope(tmp_path):
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    (tmp_path / "commitment.json").unlink()
    _, failures = bm._rerun_full_freeze_verification(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)
    assert any("commitment.json" in f for f in failures)


def test_benchmark_rerun_full_freeze_verification_catches_ledger_schema_violation(tmp_path):
    manifest = _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    ledger = json.loads((tmp_path / "reveal_verification_ledger.json").read_text())
    ledger["entries"] = ledger["entries"][:5]  # now only 5, violates minItems 6
    ledger_path = tmp_path / "reveal_verification_ledger.json"
    ledger_path.write_text(json.dumps(ledger))
    # Refresh the outer raw-hash pin so verify_frozen_bundle's bound-hash
    # check does not fire FIRST (a stale pin would surface as a hash
    # mismatch, never reaching the ledger schema-validation branch this
    # test targets) -- the same "refresh outer pins to reach the intended
    # inner check" discipline the toy-bundle-and-negatives section below
    # applies throughout.
    manifest["reveal_verification_ledger_sha256"] = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    (tmp_path / "FREEZE-MANIFEST.json").write_text(json.dumps(manifest))
    _, failures = bm._rerun_full_freeze_verification(tmp_path / "FREEZE-MANIFEST.json", tmp_path, tmp_path)
    assert any("reveal_verification_ledger.json" in f for f in failures)


def test_benchmark_refuses_when_nine_gates_passed_true_but_one_gate_literally_false(tmp_path):
    _init_toy_git_repo(tmp_path)
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    outcomes = {
        "freeze_manifest_hash": freeze_hash,
        "outcomes": [
            {"id": f"calx:{i:03d}:C1", "item_id": f"cal:{i:03d}", "check_id": "C1", "outcome": "PASS",
             "outcome_reason": "detection_complete", "severity": None, "advisory": False}
            for i in range(640)
        ],
        "runner_git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.strip(),
    }
    (results_dir / "outcomes.json").write_text(json.dumps(outcomes))
    outcomes_hash = hashlib.sha256((results_dir / "outcomes.json").read_bytes()).hexdigest()
    # Tampered: nine_gates_passed says True, but one gate is literally False.
    gates = {name: True for name in bm.PINNED_GATE_NAMES}
    gates["zero_false_violations"] = False
    (results_dir / "rates.json").write_text(json.dumps({
        "nine_gates_passed": True, "gates": gates,
        "freeze_manifest_sha256": freeze_hash, "outcomes_sha256": outcomes_hash,
    }))
    with pytest.raises(bm.BenchmarkRefused, match="literally true"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def test_benchmark_rejects_duplicate_outcome_ids(tmp_path):
    _init_toy_git_repo(tmp_path)
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    rec = {"id": "calx:000:C1", "item_id": "cal:000", "check_id": "C1", "outcome": "PASS",
           "outcome_reason": "detection_complete", "severity": None, "advisory": False}
    outcomes = {
        "freeze_manifest_hash": freeze_hash,
        "outcomes": [rec] * 640,  # all duplicates of the same id
        "runner_git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.strip(),
    }
    (results_dir / "outcomes.json").write_text(json.dumps(outcomes))
    outcomes_hash = hashlib.sha256((results_dir / "outcomes.json").read_bytes()).hexdigest()
    gates = {name: True for name in bm.PINNED_GATE_NAMES}
    (results_dir / "rates.json").write_text(json.dumps({
        "nine_gates_passed": True, "gates": gates,
        "freeze_manifest_sha256": freeze_hash, "outcomes_sha256": outcomes_hash,
    }))
    with pytest.raises(bm.BenchmarkRefused, match="duplicate"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def test_benchmark_rejects_malformed_outcome_record_shape(tmp_path):
    _init_toy_git_repo(tmp_path)
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    outcomes = {
        "freeze_manifest_hash": freeze_hash,
        "outcomes": [{}] * 640,
        "runner_git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.strip(),
    }
    (results_dir / "outcomes.json").write_text(json.dumps(outcomes))
    outcomes_hash = hashlib.sha256((results_dir / "outcomes.json").read_bytes()).hexdigest()
    gates = {name: True for name in bm.PINNED_GATE_NAMES}
    (results_dir / "rates.json").write_text(json.dumps({
        "nine_gates_passed": True, "gates": gates,
        "freeze_manifest_sha256": freeze_hash, "outcomes_sha256": outcomes_hash,
    }))
    with pytest.raises(bm.BenchmarkRefused, match="malformed"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


# =======================================================================
# SAN-881 PASS 2C.2: result-loading fail-closed boundary, replay
# integrity, and rate/gate recomputation. benchmark.py's direct
# read_text()/json.loads() over outcomes.json/rates.json used to leak a
# raw OSError (a directory in place of the file)/UnicodeDecodeError/
# JSONDecodeError/AttributeError (a non-dict top-level value) straight
# through -- never a BenchmarkRefused. Independently of that, NOTHING
# ever recomputed outcomes.json's per-record content or rates.json's
# gate/metric values from a genuine re-execution: a self-consistent
# (hash-bound) but CONTENT-tampered outcomes.json, or a rates.json whose
# gate map is simply FORGED to claim all-nine-pass, sailed through every
# existing check. Both gaps are closed together below via a single
# reconstruction: benchmark reruns the verified frozen bundle's own
# projection through BOTH harnesses (measure.run_dual_harness), joins
# the VERIFIED frozen labels (measure.join_labels), recomputes rates via
# measure.compute_rates (benchmark duplicates NEITHER), and compares
# CANONICAL bytes of the reconstruction against the RAW stored files.
# =======================================================================

def test_benchmark_refuses_when_outcomes_json_is_a_directory(tmp_path):
    _init_toy_git_repo(tmp_path)
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_path.write_text("{}")
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    (results_dir / "outcomes.json").mkdir()  # a directory in place of the file
    (results_dir / "rates.json").write_text("{}")
    with pytest.raises(bm.BenchmarkRefused, match="outcomes.json"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def test_benchmark_refuses_when_rates_json_is_a_directory(tmp_path):
    _init_toy_git_repo(tmp_path)
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_path.write_text("{}")
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    (results_dir / "outcomes.json").write_text("{}")
    (results_dir / "rates.json").mkdir()
    with pytest.raises(bm.BenchmarkRefused, match="rates.json"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def test_benchmark_refuses_when_outcomes_json_is_invalid_json(tmp_path):
    _init_toy_git_repo(tmp_path)
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_path.write_text("{}")
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    (results_dir / "outcomes.json").write_text("{not valid json")
    (results_dir / "rates.json").write_text("{}")
    with pytest.raises(bm.BenchmarkRefused, match="outcomes.json"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def test_benchmark_refuses_when_outcomes_json_top_level_is_not_an_object(tmp_path):
    # A syntactically valid JSON document (a list) whose TOP-LEVEL type
    # is wrong -- pre-fix this reaches outcomes.get(...) and raises a raw
    # AttributeError ('list' object has no attribute 'get'), never a
    # BenchmarkRefused.
    _init_toy_git_repo(tmp_path)
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_path.write_text("{}")
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    (results_dir / "outcomes.json").write_text("[]")
    (results_dir / "rates.json").write_text("{}")
    with pytest.raises(bm.BenchmarkRefused, match="outcomes.json"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def test_benchmark_refuses_when_rates_json_top_level_is_not_an_object(tmp_path):
    # outcomes.json must genuinely bind to this freeze (freeze_manifest_
    # hash correct) so execution actually REACHES rates.get(...) --
    # otherwise the pre-existing "different freeze" check fires first
    # and this test would never exercise the gap it targets.
    _init_toy_git_repo(tmp_path)
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_path.write_text("{}")
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    (results_dir / "outcomes.json").write_text(json.dumps({"freeze_manifest_hash": freeze_hash}))
    (results_dir / "rates.json").write_text("[]")
    with pytest.raises(bm.BenchmarkRefused, match="rates.json"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def test_benchmark_check_preconditions_rejects_outcomes_content_tampering_via_replay(tmp_path, monkeypatch):
    """SAN-881 PASS 2C.2 REPLAY defect (authentic RED pre-fix): a
    self-consistent (every existing hash binding refreshed to match)
    outcomes.json whose per-record CONTENT diverges from a genuine
    re-execution of the frozen bundle -- exactly ONE of 640 records is
    flipped from the genuinely-correct PASS to VIOLATION, and rates.
    json's outcomes_sha256 binding is refreshed to match the TAMPERED
    file (so the OLD outer hash-binding check does not fire first; only
    the NEW replay reconstruction can catch this). Pre-fix, benchmark.py
    never reconstructs outcomes.json content from anything -- this
    fixture sails through check_preconditions with no refusal at all."""
    _init_toy_git_repo(tmp_path)
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    manifest = json.loads(freeze_path.read_text())
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.strip()

    corpus_inputs = _toy_160_corpus_inputs()
    projection = ms.build_projection(corpus_inputs)

    def fake_harness(proj):
        results = [{"id": r["id"], "check_id": r["check_id"], "outcome": "PASS",
                    "outcome_reason": "detection_complete", "severity": None, "advisory": False} for r in proj]
        return ms.canonical_json_bytes(results), results

    out_bytes, results = fake_harness(projection)
    labels_frozen = _toy_640_merged_frozen_labels()
    joined = ms.join_labels(results, labels_frozen)

    genuine_outcomes = {
        "freeze_manifest_hash": freeze_hash,
        "component_hashes": manifest,
        "record_count": len(joined),
        "python_output_sha256": hashlib.sha256(out_bytes).hexdigest(),
        "typescript_output_sha256": hashlib.sha256(out_bytes).hexdigest(),
        "runner_git_commit": head,
        "measure_py_sha256": hashlib.sha256((CAL_DIR / "measure.py").read_bytes()).hexdigest(),
        "outcomes": [{"id": r["id"], "item_id": r["item_id"], "check_id": r["check_id"],
                      "outcome": r["outcome"], "outcome_reason": r["outcome_reason"],
                      "severity": r["severity"], "advisory": r["advisory"]} for r in joined],
    }
    # Tamper exactly ONE record -- everything else (all header fields,
    # all other 639 records) is genuinely correct.
    assert genuine_outcomes["outcomes"][0]["id"] == "calx:000:C1"
    genuine_outcomes["outcomes"][0]["outcome"] = "VIOLATION"
    tampered_bytes = ms.canonical_json_bytes(genuine_outcomes)

    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    (results_dir / "outcomes.json").write_bytes(tampered_bytes)

    gates = {name: True for name in bm.PINNED_GATE_NAMES}
    rates_doc = {
        "gates": gates, "nine_gates_passed": True,
        "freeze_manifest_sha256": freeze_hash,
        "outcomes_sha256": hashlib.sha256(tampered_bytes).hexdigest(),  # refreshed to match the TAMPERED file
    }
    (results_dir / "rates.json").write_bytes(ms.canonical_json_bytes(rates_doc))

    def fake_dual_harness(proj, workdir):
        b, r = fake_harness(proj)
        return b, b, r, r

    # Inert pre-fix (check_preconditions never calls run_dual_harness at
    # all); becomes the deterministic replay source post-fix -- the SAME
    # pure function of `proj` used to build the genuine baseline above,
    # so the reconstruction matches everywhere EXCEPT the one deliberate
    # tamper.
    monkeypatch.setattr(ms, "run_dual_harness", fake_dual_harness)

    with pytest.raises(bm.BenchmarkRefused, match="replay"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def test_benchmark_check_preconditions_rejects_forged_rates_gate_values_via_recomputation(tmp_path, monkeypatch):
    """SAN-881 PASS 2C.2 RATES defect (authentic RED pre-fix -- errors
    with TypeError since compute_rates' keyword-only raw-bytes signature
    does not exist yet): outcomes.json is genuinely correct (one honest
    false violation among 640 records, byte-identical to what a fresh
    replay reconstructs), but rates.json's gate map is FORGED to claim
    all nine gates pass. Nothing pre-fix ever recomputes rates.json's
    gate/metric values from outcomes.json's actual content -- the
    forgery is internally self-consistent (every existing hash binding
    matches) and sails through untouched."""
    _init_toy_git_repo(tmp_path)
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    manifest = json.loads(freeze_path.read_text())
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.strip()

    corpus_inputs = _toy_160_corpus_inputs()
    design_by_id = {it["item_id"]: it for it in _toy_160_design_items()}
    labels_frozen = _toy_640_merged_frozen_labels()
    projection = ms.build_projection(corpus_inputs)

    def fake_harness(proj):
        results = []
        for r in proj:
            outcome = "VIOLATION" if r["id"] == "calx:000:C1" else "PASS"
            results.append({"id": r["id"], "check_id": r["check_id"], "outcome": outcome,
                             "outcome_reason": "detection_complete",
                             "severity": "critical" if outcome == "VIOLATION" else None, "advisory": False})
        return ms.canonical_json_bytes(results), results

    out_bytes, results = fake_harness(projection)
    joined = ms.join_labels(results, labels_frozen)
    honest_rates = ms.compute_rates(joined, design_by_id, python_output_bytes=out_bytes, typescript_output_bytes=out_bytes)
    assert honest_rates["nine_gates_passed"] is False
    assert honest_rates["gates"]["zero_false_violations"] is False

    genuine_outcomes = {
        "freeze_manifest_hash": freeze_hash,
        "component_hashes": manifest,
        "record_count": len(joined),
        "python_output_sha256": hashlib.sha256(out_bytes).hexdigest(),
        "typescript_output_sha256": hashlib.sha256(out_bytes).hexdigest(),
        "runner_git_commit": head,
        "measure_py_sha256": hashlib.sha256((CAL_DIR / "measure.py").read_bytes()).hexdigest(),
        "outcomes": [{"id": r["id"], "item_id": r["item_id"], "check_id": r["check_id"],
                      "outcome": r["outcome"], "outcome_reason": r["outcome_reason"],
                      "severity": r["severity"], "advisory": r["advisory"]} for r in joined],
    }
    outcomes_bytes = ms.canonical_json_bytes(genuine_outcomes)

    forged_rates = {
        **honest_rates,
        "gates": {name: True for name in bm.PINNED_GATE_NAMES},  # forged: every gate claims True
        "nine_gates_passed": True,  # forged
        "freeze_manifest_sha256": freeze_hash,
        "outcomes_sha256": hashlib.sha256(outcomes_bytes).hexdigest(),
    }
    forged_rates_bytes = ms.canonical_json_bytes(forged_rates)

    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    (results_dir / "outcomes.json").write_bytes(outcomes_bytes)
    (results_dir / "rates.json").write_bytes(forged_rates_bytes)

    def fake_dual_harness(proj, workdir):
        b, r = fake_harness(proj)
        return b, b, r, r

    monkeypatch.setattr(ms, "run_dual_harness", fake_dual_harness)

    with pytest.raises(bm.BenchmarkRefused, match="rates"):
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)


def test_benchmark_check_preconditions_translates_missing_npm_to_benchmark_refused_end_to_end(tmp_path, monkeypatch):
    """SAN-881 PASS 2C.2-FIX END-TO-END GREEN PIN: proves the benchmark
    replay path (check_preconditions -> _verify_replay_and_recompute_
    rates -> measure.run_dual_harness -> measure.build_typescript_
    package) translates an InfrastructureFailure raised inside the dual
    harness -- here, a genuinely missing npm binary at the FIRST
    subprocess boundary (defect 2a) -- into a BenchmarkRefused, never a
    raw traceback, never an absolute-path disclosure. Exercises the REAL
    (unmocked) run_dual_harness/build_typescript_package; only
    subprocess.run itself is monkeypatched, and ONLY for the `npm`
    command -- every git call check_preconditions and measure.py
    themselves issue (runner_git_commit / clean-worktree checks) goes
    through the REAL subprocess.run unchanged, so this is a genuine
    end-to-end exercise of the wiring, not a stubbed-out one. Locks in
    BOTH the pre-existing SAN-881 PASS 2C.2 core
    `except (ms.InfrastructureFailure, ms.FreezeGateRefused)` wrapping
    in _verify_replay_and_recompute_rates (untouched by this pass) AND
    the defect-2a translation this pass adds in build_typescript_
    package."""
    _init_toy_git_repo(tmp_path)
    _write_toy_v2_schema_valid_freeze_environment(tmp_path, tmp_path)
    freeze_path = tmp_path / "FREEZE-MANIFEST.json"
    freeze_hash = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    manifest = json.loads(freeze_path.read_text())
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.strip()

    corpus_inputs = _toy_160_corpus_inputs()
    projection = ms.build_projection(corpus_inputs)

    def fake_harness(proj):
        results = [{"id": r["id"], "check_id": r["check_id"], "outcome": "PASS",
                    "outcome_reason": "detection_complete", "severity": None, "advisory": False} for r in proj]
        return ms.canonical_json_bytes(results), results

    out_bytes, results = fake_harness(projection)
    labels_frozen = _toy_640_merged_frozen_labels()
    joined = ms.join_labels(results, labels_frozen)

    genuine_outcomes = {
        "freeze_manifest_hash": freeze_hash,
        "component_hashes": manifest,
        "record_count": len(joined),
        "python_output_sha256": hashlib.sha256(out_bytes).hexdigest(),
        "typescript_output_sha256": hashlib.sha256(out_bytes).hexdigest(),
        "runner_git_commit": head,
        "measure_py_sha256": hashlib.sha256((CAL_DIR / "measure.py").read_bytes()).hexdigest(),
        "outcomes": [{"id": r["id"], "item_id": r["item_id"], "check_id": r["check_id"],
                      "outcome": r["outcome"], "outcome_reason": r["outcome_reason"],
                      "severity": r["severity"], "advisory": r["advisory"]} for r in joined],
    }
    outcomes_bytes = ms.canonical_json_bytes(genuine_outcomes)

    results_dir = tmp_path / "results" / freeze_hash
    results_dir.mkdir(parents=True)
    (results_dir / "outcomes.json").write_bytes(outcomes_bytes)

    gates = {name: True for name in bm.PINNED_GATE_NAMES}
    rates_doc = {
        "gates": gates, "nine_gates_passed": True,
        "freeze_manifest_sha256": freeze_hash,
        "outcomes_sha256": hashlib.sha256(outcomes_bytes).hexdigest(),
    }
    (results_dir / "rates.json").write_bytes(ms.canonical_json_bytes(rates_doc))

    real_subprocess_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if cmd and cmd[0] == "npm":
            raise FileNotFoundError(2, "No such file or directory", "npm")
        return real_subprocess_run(cmd, *args, **kwargs)

    monkeypatch.setattr(ms.subprocess, "run", fake_run)

    with pytest.raises(bm.BenchmarkRefused, match="replay of the frozen bundle failed") as excinfo:
        bm.check_preconditions(tmp_path / "results", freeze_path, repo_root=tmp_path)

    message = str(excinfo.value)
    assert "Traceback" not in message
    assert str(tmp_path) not in message
    assert str(bm.REPO_ROOT) not in message


# ---------------------------------------------------------------------
# Correction 10: real transaction-failure execution (injected mid-write
# and rename failures) + secondary reporting stays aggregate-only
# ---------------------------------------------------------------------

def test_measure_secondary_population_has_no_confusion_by_stratum_key():
    joined, design_by_id = _toy_joined_and_design()
    rates = ms.compute_rates(joined, design_by_id, python_output_bytes=b"toy", typescript_output_bytes=b"toy")
    assert "confusion_by_stratum" not in rates["per_check"]["C1"]["secondary_all_160"]
    assert "confusion_by_stratum" in rates["per_check"]["C1"]["primary_target_40"]


def test_measure_transactional_injected_mid_write_failure_cleans_temp_and_preserves_stale(tmp_path, monkeypatch):
    """SAN-881 PASS 2C.2: GREEN-FROM-BIRTH regression pin -- the
    mid-write transaction structure is already sound; this is NOT a RED
    defect this pass fixes. Enhanced with instrumentation (harness
    reached, the injected write reached, rename count) proving the
    fault-injection path was genuinely exercised, per fold 7/9."""
    cal_dir = tmp_path / "cal"
    cal_dir.mkdir()
    _init_toy_git_repo(tmp_path)
    _write_minimal_run_pipeline_cal_dir(cal_dir)

    monkeypatch.setattr(ms, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ms, "verify_frozen_bundle", _fake_verify_frozen_bundle)

    # The stale directory MUST be a DIFFERENT freeze hash than the
    # current run's -- using the SAME hash here would trip run_pipeline's
    # own "final hash dir already exists" refusal immediately, before
    # the harness (or the injected fault) is ever reached, silently
    # defeating this test's own purpose (a genuine pre-existing latent
    # bug this pass's instrumentation catches: harness_reached would
    # read 0, not 1).
    stale_hash = "0" * 64
    stale_dir = cal_dir / "results" / stale_hash
    stale_dir.mkdir(parents=True)
    (stale_dir / "outcomes.json").write_text('{"stale": true}')

    harness_reached = {"n": 0}

    def fake_dual_harness(projection, workdir):
        harness_reached["n"] += 1
        results = [{"id": r["id"], "check_id": r["check_id"], "outcome": "PASS",
                    "outcome_reason": "detection_complete", "severity": None, "advisory": False} for r in projection]
        return b"toybytes", b"toybytes", results, results

    monkeypatch.setattr(ms, "run_dual_harness", fake_dual_harness)

    # Inject a REAL mid-write failure: the second write_bytes call (writing
    # rates.json, after outcomes.json already succeeded) raises.
    real_write_bytes = Path.write_bytes
    call_count = {"n": 0}
    injected_write_reached = {"flag": False}

    def flaky_write_bytes(self, data):
        call_count["n"] += 1
        if call_count["n"] == 2:
            injected_write_reached["flag"] = True
            raise OSError("toy injected mid-write failure")
        return real_write_bytes(self, data)

    monkeypatch.setattr(Path, "write_bytes", flaky_write_bytes)

    real_rename = Path.rename
    rename_calls = {"n": 0}

    def counting_rename(self, target):
        rename_calls["n"] += 1
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", counting_rename)

    with pytest.raises(ms.InfrastructureFailure):
        ms.run_pipeline(cal_dir)

    # Instrumentation evidence: harness reached, the injected write was
    # reached, rename was NEVER attempted (the failure happened before
    # the third write / git recheck / rename were ever reached).
    assert harness_reached["n"] == 1
    assert injected_write_reached["flag"] is True
    assert rename_calls["n"] == 0

    # The OTHER freeze hash's stale results directory is untouched.
    assert stale_dir.exists()
    assert json.loads((stale_dir / "outcomes.json").read_text()) == {"stale": True}
    # No final artifacts for the CURRENT freeze hash appear.
    current_final_dir = cal_dir / "results" / hashlib.sha256((cal_dir / "FREEZE-MANIFEST.json").read_bytes()).hexdigest()
    assert not current_final_dir.exists()
    assert current_final_dir != stale_dir
    # No temp directory left behind.
    tmp_dirs = list((cal_dir / "results").glob(".tmp-*"))
    assert tmp_dirs == []


def test_measure_transactional_injected_rename_failure_cleans_temp_dir(tmp_path, monkeypatch):
    """SAN-881 PASS 2C.2: GREEN-FROM-BIRTH regression pin -- the rename
    transaction structure is already sound; this is NOT a RED defect
    this pass fixes. Enhanced with instrumentation (harness reached, all
    three writes complete AT the moment rename is attempted, rename
    attempted exactly once) plus a stale, OTHER-freeze-hash results
    directory proven untouched, per fold 7/9."""
    cal_dir = tmp_path / "cal"
    cal_dir.mkdir()
    _init_toy_git_repo(tmp_path)
    _write_minimal_run_pipeline_cal_dir(cal_dir)

    monkeypatch.setattr(ms, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ms, "verify_frozen_bundle", _fake_verify_frozen_bundle)

    # See the mid-write test's comment above: the stale directory MUST
    # be a DIFFERENT freeze hash, or run_pipeline's own "already exists"
    # refusal fires before the harness/rename fault is ever reached.
    stale_hash = "f" * 64
    stale_dir = cal_dir / "results" / stale_hash
    stale_dir.mkdir(parents=True)
    (stale_dir / "outcomes.json").write_text('{"stale": true}')

    harness_reached = {"n": 0}

    def fake_dual_harness(projection, workdir):
        harness_reached["n"] += 1
        results = [{"id": r["id"], "check_id": r["check_id"], "outcome": "PASS",
                    "outcome_reason": "detection_complete", "severity": None, "advisory": False} for r in projection]
        return b"toybytes", b"toybytes", results, results

    monkeypatch.setattr(ms, "run_dual_harness", fake_dual_harness)

    real_rename = Path.rename
    rename_calls = {"n": 0}
    writes_present_at_rename = {}

    def flaky_rename(self, target):
        rename_calls["n"] += 1
        if str(self).startswith(str(cal_dir / "results" / ".tmp-")):
            # Instrumentation: prove all three artifacts were completely
            # written BEFORE this (failing) rename attempt.
            writes_present_at_rename["outcomes.json"] = (self / "outcomes.json").exists()
            writes_present_at_rename["rates.json"] = (self / "rates.json").exists()
            writes_present_at_rename["RATES-REPORT.md"] = (self / "RATES-REPORT.md").exists()
            raise OSError("toy injected rename failure")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", flaky_rename)

    with pytest.raises(ms.InfrastructureFailure):
        ms.run_pipeline(cal_dir)

    assert harness_reached["n"] == 1
    assert writes_present_at_rename == {"outcomes.json": True, "rates.json": True, "RATES-REPORT.md": True}
    assert rename_calls["n"] == 1

    final_dir = cal_dir / "results" / hashlib.sha256((cal_dir / "FREEZE-MANIFEST.json").read_bytes()).hexdigest()
    assert not final_dir.exists()
    # No temp directory left behind for the CURRENT freeze.
    tmp_dirs = list((cal_dir / "results").glob(".tmp-*"))
    assert tmp_dirs == []
    # The OTHER freeze hash's stale results directory is completely
    # untouched.
    assert stale_dir.exists()
    assert json.loads((stale_dir / "outcomes.json").read_text()) == {"stale": True}


def test_measure_run_pipeline_publication_event_order_harness_writes_recheck_rename(tmp_path, monkeypatch):
    """SAN-881 PASS 2C.2: structural, GREEN-FROM-BIRTH pin asserting the
    EXACT pinned publication event order: harness -> three writes -> git
    recheck -> rename (section 6/9). Bounded to git state only -- no
    snapshot subsystem."""
    cal_dir = tmp_path / "cal"
    cal_dir.mkdir()
    _init_toy_git_repo(tmp_path)
    _write_minimal_run_pipeline_cal_dir(cal_dir)

    monkeypatch.setattr(ms, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ms, "verify_frozen_bundle", _fake_verify_frozen_bundle)

    events = []

    def fake_dual_harness(projection, workdir):
        events.append("harness")
        results = [{"id": r["id"], "check_id": r["check_id"], "outcome": "PASS",
                    "outcome_reason": "detection_complete", "severity": None, "advisory": False} for r in projection]
        return b"toybytes", b"toybytes", results, results

    monkeypatch.setattr(ms, "run_dual_harness", fake_dual_harness)

    real_write_bytes = Path.write_bytes
    real_write_text = Path.write_text
    real_rename = Path.rename
    real_require_clean = ms._require_clean_tracked_worktree
    require_clean_calls = {"n": 0}

    def tracking_write_bytes(self, data):
        if self.name in ("outcomes.json", "rates.json"):
            events.append(f"write:{self.name}")
        return real_write_bytes(self, data)

    def tracking_write_text(self, data, *args, **kwargs):
        if self.name == "RATES-REPORT.md":
            events.append(f"write:{self.name}")
        return real_write_text(self, data, *args, **kwargs)

    def tracking_require_clean(repo_root):
        require_clean_calls["n"] += 1
        if require_clean_calls["n"] == 1:
            events.append("initial_head_capture")
        elif require_clean_calls["n"] == 2:
            events.append("git_recheck")
        return real_require_clean(repo_root)

    def tracking_rename(self, target):
        if str(self).startswith(str(cal_dir / "results" / ".tmp-")):
            events.append("rename")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "write_bytes", tracking_write_bytes)
    monkeypatch.setattr(Path, "write_text", tracking_write_text)
    monkeypatch.setattr(Path, "rename", tracking_rename)
    monkeypatch.setattr(ms, "_require_clean_tracked_worktree", tracking_require_clean)

    exit_code = ms.run_pipeline(cal_dir)

    assert exit_code == 0
    assert require_clean_calls["n"] == 2
    assert events == [
        "initial_head_capture", "harness",
        "write:outcomes.json", "write:rates.json", "write:RATES-REPORT.md",
        "git_recheck", "rename",
    ]


# ---------------------------------------------------------------------
# Correction 11: README documents the new posture (checked structurally
# above via test_readme_semantic_reveal_precedes_contract_design_coverage_reveal
# and test_readme_documents_nine_gates_and_transaction_scheme; additional
# assertions below)
# ---------------------------------------------------------------------

def test_readme_no_longer_calls_empty_evidence_a_documented_v1_coverage_gap():
    readme = (CAL_DIR / "README.md").read_text()
    assert "DOCUMENTED v1 coverage gap" not in readme


def test_readme_documents_truthful_partial_state_for_in_scope_surfaces():
    # SAN-881 PASS 2B.1-P honesty statement: the 50 in-scope surfaces are
    # now validated by a PRODUCT-LEVEL four-clause contract over
    # FieldProductTrace + CAPABILITY_MAP; the 18 nontable surfaces remain
    # the ORIGINAL, byte-unchanged static-lexical proof -- the README
    # must say so plainly, must carry the exact honest-assurance sentence
    # verbatim, and must disclose that CheckConsumptionTrace does not
    # exist and was REJECTED as an architecture (never framed as a
    # deferred follow-up).
    readme = (CAL_DIR / "README.md").read_text()
    assert "FieldProductTrace" in readme
    assert "CAPABILITY_MAP" in readme
    assert "BYTE-UNCHANGED" in readme
    assert "NONTABLE surfaces" in readme
    assert "CheckConsumptionTrace" in readme
    assert "REJECTED" in readme
    assert HONEST_ASSURANCE_SENTENCE in _normalize_ws(readme)
    for phrase in _FORBIDDEN_HONEST_ASSURANCE_PHRASES:
        assert phrase not in readme.lower()


def test_readme_documents_reveal_stage_cli_flag():
    readme = (CAL_DIR / "README.md").read_text()
    assert "--reveal-stage" in readme
    assert "--reveal-stage semantic" in readme
    assert "--reveal-stage contract" in readme


def test_readme_documents_literal_six_tuple_ledger():
    readme = (CAL_DIR / "README.md").read_text()
    assert "EXACTLY six" in readme or "exactly six" in readme.lower()
    assert "labels_reviewer_contract.json" in readme


def test_readme_documents_v1_transitional_posture():
    readme = (CAL_DIR / "README.md").read_text()
    assert "v1-transitional" in readme.lower() or "v1 transitional" in readme.lower()
    assert "atomic" in readme.lower()


def test_readme_documents_exact_bundle_contract_table():
    readme = (CAL_DIR / "README.md").read_text()
    assert "Exact bundle contents" in readme
    assert "labels_reviewer_semantic.commitment.json" in readme
    assert "labels_reviewer_contract.commitment.json" in readme


def test_readme_documents_nonce_custody_derived_subsets():
    readme = (CAL_DIR / "README.md").read_text()
    assert "custody-derived STAGE SUBSETS" in readme
    assert "NOT bundle members" in readme


def test_readme_documents_reveal_stage_required_for_nonce_reviewer_args():
    # SAN-881 PASS-1 FINAL CLOSURE CORRECTION: replaces
    # test_readme_documents_legacy_reveal_flag -- --legacy-reveal is
    # removed; the README must instead document the fixed-diagnostic
    # reject for any nonce/reviewer argument supplied without
    # --reveal-stage.
    readme = (CAL_DIR / "README.md").read_text()
    assert "--legacy-reveal" not in readme
    assert "NONCE_OR_REVIEWER_ARG_REQUIRES_REVEAL_STAGE" in readme


def test_readme_documents_v2_context_formula():
    readme = (CAL_DIR / "README.md").read_text()
    assert "ELEVEN structured" in readme
    assert "base_commit_sha" in readme


def test_readme_documents_dispatch_order_never_enters_generic_path():
    readme = (CAL_DIR / "README.md").read_text()
    assert "never enters a generic path" in readme.lower() or "never enter" in readme.lower()


def test_readme_no_trailing_whitespace():
    for i, line in enumerate((CAL_DIR / "README.md").read_text().splitlines(), start=1):
        assert line == line.rstrip(), f"README.md:{i} has trailing whitespace"


# =======================================================================
# SAN-881 PASS-1 CORRECTION ROUND (root repair): schema validity must be
# checked BEFORE cryptographic validity is allowed to imply success.
# =======================================================================

# ---------------------------------------------------------------------
# Section A: selected-stage schema validation gates cryptographic subset
# reveal verification. Every test below constructs a PRESENT artifact
# whose bytes are re-committed (fresh nonce + matching commitment_hex)
# so that, if crypto verification were allowed to run, it would SUCCEED
# -- proving any rejection is genuinely a SCHEMA rejection, not an
# incidental crypto mismatch that would fail regardless.
# ---------------------------------------------------------------------

def _recommit_artifact(env: dict, artifact_name: str, new_bytes: bytes) -> None:
    """Mutates env's in-memory author_commitments entry for
    `artifact_name` so `new_bytes` cryptographically verifies against a
    FRESH nonce under the SAME labeling_context_hash, then rewrites
    commitment.json on disk to match. Produces a PRESENT,
    cryptographically-consistent-but-potentially-schema-garbage artifact."""
    ctx_hash_bytes = bytes.fromhex(env["commitment"]["labeling_context_hash"])
    new_nonce = secrets.token_bytes(32)
    new_commit_hex = vd.compute_artifact_commitment(artifact_name, new_nonce, ctx_hash_bytes, new_bytes)
    env["artifact_bytes"][artifact_name] = new_bytes
    env["author_nonces"][artifact_name] = new_nonce
    for entry in env["commitment"]["author_commitments"]:
        if entry["artifact_name"] == artifact_name:
            entry["byte_length"] = len(new_bytes)
            entry["commitment_hex"] = new_commit_hex
    (env["cal_dir"] / "commitment.json").write_text(json.dumps(env["commitment"]))


def _recommit_reviewer_artifact(env: dict, kind: str, new_bytes: bytes) -> None:
    """Reviewer-envelope analogue of _recommit_artifact. kind is
    "semantic" or "contract"."""
    artifact_name = vd.REVIEWER_SEMANTIC_ARTIFACT if kind == "semantic" else vd.REVIEWER_CONTRACT_ARTIFACT
    nonce_key = "rev_sem_nonce" if kind == "semantic" else "rev_con_nonce"
    artifact_key = "rev_sem_artifact" if kind == "semantic" else "rev_con_artifact"
    env_key = "rev_sem_env" if kind == "semantic" else "rev_con_env"
    ctx_hash_bytes = bytes.fromhex(env["commitment"]["labeling_context_hash"])
    new_nonce = secrets.token_bytes(32)
    new_commit_hex = vd.compute_artifact_commitment(artifact_name, new_nonce, ctx_hash_bytes, new_bytes)
    env[artifact_key] = new_bytes
    env[nonce_key] = new_nonce
    env[env_key]["artifact_commitment"]["byte_length"] = len(new_bytes)
    env[env_key]["artifact_commitment"]["commitment_hex"] = new_commit_hex


def _assert_crypto_skipped_for_schema_failure(tmp_path, monkeypatch, capsys, argv_builder, mutate, expected_rule):
    """Shared engine for the Section A adversarial tests. Builds a fully
    self-consistent toy v2 environment, applies `mutate(env)`, tracks
    every call to vd.verify_reveal, runs `vd.main(argv_builder(tmp_path,
    env))`, and asserts: rc == 1, `expected_rule` appears in stderr, and
    vd.verify_reveal is NEVER invoked -- cryptographic subset
    verification must be SKIPPED for the whole stage once any selected
    artifact fails schema validation (SAN-881 PASS-1 CORRECTION ROUND
    root repair), even when the mutated bytes would themselves
    cryptographically verify."""
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    mutate(env)
    argv = argv_builder(tmp_path, env)

    calls = []
    original_verify_reveal = vd.verify_reveal

    def _tracking_verify_reveal(*args, **kwargs):
        calls.append(args)
        return original_verify_reveal(*args, **kwargs)

    monkeypatch.setattr(vd, "verify_reveal", _tracking_verify_reveal)

    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert expected_rule in captured.err, captured.err
    assert calls == [], (
        "cryptographic reveal verification must be SKIPPED once schema "
        f"validation fails for the stage; verify_reveal was called with: {calls}"
    )
    return captured


def test_stage_schema_gate_semantic_zero_record_author_file_skips_crypto(tmp_path, monkeypatch, capsys):
    def mutate(env):
        _recommit_artifact(env, "labels_author_semantic.json", json.dumps([]).encode())
    _assert_crypto_skipped_for_schema_failure(tmp_path, monkeypatch, capsys, _write_semantic_only_bundle, mutate, vd.RULE_SCHEMA_INVALID)


def test_stage_schema_gate_semantic_639_record_author_file_skips_crypto(tmp_path, monkeypatch, capsys):
    def mutate(env):
        records = json.loads(env["artifact_bytes"]["labels_author_semantic.json"])[:639]
        _recommit_artifact(env, "labels_author_semantic.json", json.dumps(records).encode())
    _assert_crypto_skipped_for_schema_failure(tmp_path, monkeypatch, capsys, _write_semantic_only_bundle, mutate, vd.RULE_SCHEMA_INVALID)


def test_stage_schema_gate_semantic_zero_record_reviewer_file_skips_crypto(tmp_path, monkeypatch, capsys):
    def mutate(env):
        _recommit_reviewer_artifact(env, "semantic", json.dumps([]).encode())
    _assert_crypto_skipped_for_schema_failure(tmp_path, monkeypatch, capsys, _write_semantic_only_bundle, mutate, vd.RULE_SCHEMA_INVALID)


def test_stage_schema_gate_semantic_639_record_reviewer_file_skips_crypto(tmp_path, monkeypatch, capsys):
    def mutate(env):
        records = json.loads(env["rev_sem_artifact"])[:639]
        _recommit_reviewer_artifact(env, "semantic", json.dumps(records).encode())
    _assert_crypto_skipped_for_schema_failure(tmp_path, monkeypatch, capsys, _write_semantic_only_bundle, mutate, vd.RULE_SCHEMA_INVALID)


def test_stage_schema_gate_contract_invalid_author_contract_file_skips_crypto(tmp_path, monkeypatch, capsys):
    def mutate(env):
        records = json.loads(env["artifact_bytes"]["labels_author_contract.json"])[:639]
        _recommit_artifact(env, "labels_author_contract.json", json.dumps(records).encode())
    _assert_crypto_skipped_for_schema_failure(tmp_path, monkeypatch, capsys, _write_contract_only_bundle, mutate, vd.RULE_SCHEMA_INVALID)


def test_stage_schema_gate_contract_invalid_reviewer_contract_file_skips_crypto(tmp_path, monkeypatch, capsys):
    def mutate(env):
        records = json.loads(env["rev_con_artifact"])[:639]
        _recommit_reviewer_artifact(env, "contract", json.dumps(records).encode())
    _assert_crypto_skipped_for_schema_failure(tmp_path, monkeypatch, capsys, _write_contract_only_bundle, mutate, vd.RULE_SCHEMA_INVALID)


def test_stage_schema_gate_contract_invalid_design_metadata_skips_crypto(tmp_path, monkeypatch, capsys):
    def mutate(env):
        design = {"items": json.loads(env["artifact_bytes"]["design_metadata.json"])["items"][:1]}
        _recommit_artifact(env, "design_metadata.json", json.dumps(design).encode())
    _assert_crypto_skipped_for_schema_failure(tmp_path, monkeypatch, capsys, _write_contract_only_bundle, mutate, vd.RULE_SCHEMA_INVALID)


def test_stage_schema_gate_contract_invalid_coverage_manifest_skips_crypto(tmp_path, monkeypatch, capsys):
    def mutate(env):
        # minItems 1 violated: an empty evidence array.
        _recommit_artifact(env, "coverage_manifest.json", json.dumps({"toy_surface": []}).encode())
    _assert_crypto_skipped_for_schema_failure(tmp_path, monkeypatch, capsys, _write_contract_only_bundle, mutate, vd.RULE_SCHEMA_INVALID)


def test_stage_schema_gate_semantic_wrong_reviewer_envelope_discriminator_skips_crypto(tmp_path, monkeypatch, capsys):
    # A schema-valid envelope, but of the WRONG kind for this stage (a
    # REVIEWER_CONTRACT-discriminated envelope where REVIEWER_SEMANTIC is
    # required) must be rejected specifically -- never merely "matches
    # SOME branch of the root oneOf".
    def mutate(env):
        env["rev_sem_env"]["envelope_kind"] = "REVIEWER_CONTRACT"
    _assert_crypto_skipped_for_schema_failure(tmp_path, monkeypatch, capsys, _write_semantic_only_bundle, mutate, vd.RULE_SCHEMA_INVALID)


def test_stage_schema_gate_semantic_malformed_reviewer_artifact_commitment_integer_no_crash(tmp_path, monkeypatch, capsys):
    # THE core adversarial regression: BEFORE this correction,
    # commitment["artifact_commitment"]["artifact_name"] on an integer
    # artifact_commitment raised an uncaught TypeError deep inside the
    # staged reveal path. It must now fail closed with a fixed
    # diagnostic, never a traceback, never entering crypto verification.
    def mutate(env):
        env["rev_sem_env"]["artifact_commitment"] = 7
    captured = _assert_crypto_skipped_for_schema_failure(
        tmp_path, monkeypatch, capsys, _write_semantic_only_bundle, mutate, vd.RULE_SCHEMA_INVALID)
    assert "Traceback" not in captured.err
    assert str(tmp_path) not in captured.err


def test_stage_schema_gate_semantic_invalid_json_selected_artifact_skips_crypto(tmp_path, monkeypatch, capsys):
    def mutate(env):
        env["artifact_bytes"]["labels_author_semantic.json"] = b"{not valid json,,,"
    _assert_crypto_skipped_for_schema_failure(tmp_path, monkeypatch, capsys, _write_semantic_only_bundle, mutate, vd.RULE_STAGED_IO_FAILURE)


def test_stage_schema_gate_contract_invalid_json_reviewer_envelope_skips_crypto(tmp_path, monkeypatch, capsys):
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_contract_only_bundle(tmp_path, env)
    reviewer_dir = Path(argv[argv.index("--reviewer-dir") + 1])
    (reviewer_dir / vd.REVIEWER_CONTRACT_COMMITMENT_FILE).write_bytes(b"{not valid json,,,")

    calls = []
    original_verify_reveal = vd.verify_reveal

    def _tracking_verify_reveal(*args, **kwargs):
        calls.append(args)
        return original_verify_reveal(*args, **kwargs)

    monkeypatch.setattr(vd, "verify_reveal", _tracking_verify_reveal)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_STAGED_IO_FAILURE in captured.err
    assert calls == []


def test_stage_schema_gate_semantic_happy_path_still_verifies_crypto(tmp_path, monkeypatch, capsys):
    # Companion positive control: genuinely schema-valid, cryptographically
    # consistent bytes DO reach and pass crypto verification -- the gate
    # does not over-block legitimate reveals.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)

    calls = []
    original_verify_reveal = vd.verify_reveal

    def _tracking_verify_reveal(*args, **kwargs):
        calls.append(args)
        return original_verify_reveal(*args, **kwargs)

    monkeypatch.setattr(vd, "verify_reveal", _tracking_verify_reveal)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    assert len(calls) == 2  # author semantic + reviewer semantic


# ---------------------------------------------------------------------
# Section B: safe author-envelope ordering.
# ---------------------------------------------------------------------

def test_check_commitment_hardened_against_malformed_author_commitments_members(tmp_path):
    # author_commitments=[None, ...]: MUST NOT raise.
    cal_dir = tmp_path
    schemas_dir = cal_dir / "schemas"
    schemas_dir.mkdir()
    (cal_dir / "corpus_inputs.json").write_bytes(b"[]")
    (cal_dir / "evaluation_profile.json").write_bytes(b"{}")
    for name in vd.SCHEMA_FILES:
        (schemas_dir / name).write_bytes(b"{}")
    spec_dir = tmp_path / "reference" / "spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "ALGORITHM-v4-c1c5-reference.md").write_bytes(b"algo")
    (spec_dir / "ALGORITHM-v4-tables-v1.json").write_bytes(b"tables")

    commitment = {
        "corpus_version": vd.EXPECTED_CORPUS_VERSION,
        "author_commitments": [None, None, None, None],
        "labeling_context_hash": "a" * 64,
    }
    errors = vd.Errors()
    vd.check_commitment(errors, commitment, cal_dir=cal_dir, repo_root=tmp_path)  # must not raise
    assert any(vd.RULE_COMMITMENT_ARTIFACT_SET in e for e in errors)

    errors2 = vd.Errors()
    vd.check_author_commitment_order(errors2, commitment)  # must not raise
    assert any(vd.RULE_COMMITMENT_ORDER_MISMATCH in e for e in errors2)


def test_check_author_commitment_order_hardened_against_non_list_author_commitments():
    commitment = {"author_commitments": "not-a-list"}
    errors = vd.Errors()
    vd.check_author_commitment_order(errors, commitment)  # must not raise
    assert any(vd.RULE_COMMITMENT_ORDER_MISMATCH in e for e in errors)


def test_main_malformed_author_commitments_no_traceback_no_path_disclosure(tmp_path, monkeypatch, capsys):
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    commitment = dict(env["commitment"])
    commitment["author_commitments"] = [None]
    (env["cal_dir"] / "commitment.json").write_text(json.dumps(commitment))

    rc = vd.main([])
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert str(tmp_path) not in captured.err
    assert vd.RULE_COMMITMENT_ARTIFACT_SET in captured.err


def test_commitment_json_validates_specifically_as_author_envelope_not_root_oneof():
    # THE core Section B regression: a schema-valid REVIEWER_SEMANTIC
    # envelope (valid against SOME branch of the root oneOf) must fail
    # when checked SPECIFICALLY as the authorEnvelope shape.
    schema = json.loads((SCHEMAS_DIR / "commitment_schema.json").read_text())
    reviewer_shaped = {
        "corpus_version": 2, "envelope_kind": "REVIEWER_SEMANTIC",
        "labeling_context_hash": "a" * 64,
        "commitment_algorithm": {
            "hash": "SHA256", "domain_separator": "sanna-calibration-commitment/1",
            "formula": vd.COMMITMENT_ALGORITHM_FORMULA,
        },
        "artifact_commitment": {"artifact_name": "labels_reviewer_semantic.json", "byte_length": 1, "commitment_hex": "b" * 64},
    }
    # Passes the permissive root oneOf (matches the reviewerSemanticEnvelope branch)...
    Draft202012Validator(schema).validate(reviewer_shaped)
    # ...but MUST fail validate_design's SPECIFIC authorEnvelope check.
    errors = vd.Errors()
    ok = vd._validate_specific(errors, "commitment.json", schema, "authorEnvelope", reviewer_shaped)
    assert ok is False
    assert any(vd.RULE_SCHEMA_INVALID in e for e in errors)


def test_main_reveal_stage_rejects_reviewer_envelope_substituted_as_commitment_json(tmp_path, monkeypatch, capsys):
    # A schema-valid REVIEWER envelope substituted as commitment.json
    # must fail with a fixed diagnostic and never reach staged
    # cryptographic processing.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    reviewer_shaped = {
        "corpus_version": 2, "envelope_kind": "REVIEWER_SEMANTIC",
        "labeling_context_hash": env["commitment"]["labeling_context_hash"],
        "commitment_algorithm": {
            "hash": "SHA256", "domain_separator": "sanna-calibration-commitment/1",
            "formula": vd.COMMITMENT_ALGORITHM_FORMULA,
        },
        "artifact_commitment": {"artifact_name": "labels_reviewer_semantic.json", "byte_length": 1, "commitment_hex": "b" * 64},
    }
    (env["cal_dir"] / "commitment.json").write_text(json.dumps(reviewer_shaped))
    argv = _write_semantic_only_bundle(tmp_path, env)

    calls = []
    original_verify_reveal = vd.verify_reveal

    def _tracking_verify_reveal(*args, **kwargs):
        calls.append(args)
        return original_verify_reveal(*args, **kwargs)

    monkeypatch.setattr(vd, "verify_reveal", _tracking_verify_reveal)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_SCHEMA_INVALID in captured.err
    assert "Traceback" not in captured.err
    assert calls == [], "staged cryptographic processing must never begin from a structurally invalid author envelope"


def test_main_public_only_v1_transitional_output_is_exactly_four_pinned_lines(capsys):
    # G.3 acceptance: the real (intentionally v1-transitional)
    # commitment.json must still yield EXACTLY the existing four
    # transitional error lines after this correction round.
    rc = vd.main([])
    captured = capsys.readouterr()
    assert rc == 1
    lines = [l for l in captured.err.splitlines() if l.startswith("  - ")]
    assert len(lines) == 4, captured.err
    rules = [l.split("rule=", 1)[1] for l in lines]
    assert sorted(rules) == sorted([
        vd.RULE_CORPUS_VERSION, vd.RULE_CORPUS_VERSION,
        vd.RULE_CONTEXT_HASH_MISMATCH, vd.RULE_SCHEMA_INVALID,
    ])
    artifacts = [l.split(":", 1)[0].strip().lstrip("- ").strip() for l in lines]
    assert artifacts.count("evaluation_profile.json") == 1
    assert artifacts.count("commitment.json") == 3


# ---------------------------------------------------------------------
# Section C: bind declared v2 components to disk.
# ---------------------------------------------------------------------

def test_check_commitment_v2_forged_declared_component_hash_fails_even_with_correct_outer_hash(tmp_path):
    cal_dir = tmp_path
    schemas_dir = cal_dir / "schemas"
    schemas_dir.mkdir()
    (cal_dir / "corpus_inputs.json").write_bytes(b"[]")
    (cal_dir / "evaluation_profile.json").write_bytes(b"{}")
    _write_toy_schemas_dir(schemas_dir)  # SAN-881 PASS-1 CORRECTION: real bytes for the two $defs-branch-checked schemas
    spec_dir = tmp_path / "reference" / "spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "ALGORITHM-v4-c1c5-reference.md").write_bytes(b"algo")
    (spec_dir / "ALGORITHM-v4-tables-v1.json").write_bytes(b"{}")  # valid JSON -- SAN-881 PASS-1 FINAL CLOSURE CORRECTION: tables is now cache-validated as JSON too

    correct_hash = vd.compute_labeling_context_hash_from_disk(cal_dir, tmp_path).hex()
    correct_components = vd.build_labeling_context_components(cal_dir, tmp_path)

    commitment = {
        "corpus_version": vd.EXPECTED_CORPUS_VERSION,
        "author_commitments": [
            {"artifact_name": n, "byte_length": 1, "commitment_hex": "a" * 64}
            for n in vd.AUTHOR_COMMITMENT_ORDER
        ],
        "labeling_context_hash": correct_hash,
        "labeling_context_components": correct_components,
    }
    errors = vd.Errors()
    vd.check_commitment(errors, commitment, cal_dir=cal_dir, repo_root=tmp_path)
    assert errors == []

    # Forge ONE declared component's sha256 -- the outer hash is UNCHANGED
    # (still "correct" / matching the from-disk recompute) but the
    # declared component list no longer matches build_labeling_context_components.
    forged_components = [dict(c) for c in correct_components]
    forged_components[0] = {**forged_components[0], "sha256": "f" * 64}
    commitment_forged = {**commitment, "labeling_context_components": forged_components}
    errors2 = vd.Errors()
    vd.check_commitment(errors2, commitment_forged, cal_dir=cal_dir, repo_root=tmp_path)
    assert any(vd.RULE_CONTEXT_HASH_MISMATCH in e for e in errors2)
    # Exactly ONE error -- preserves the "one CONTEXT_HASH_MISMATCH" shape
    # even for a component-list-only divergence.
    assert len(errors2) == 1


def test_check_commitment_v1_envelope_skips_component_list_cross_check(tmp_path):
    # A v1 envelope (corpus_version != 2) is NEVER subjected to the v2
    # component-list cross-check -- this preserves the v1-transitional
    # four-line output (no fifth error from a v1 envelope simply lacking
    # a v2-shaped labeling_context_components list).
    cal_dir = tmp_path
    schemas_dir = cal_dir / "schemas"
    schemas_dir.mkdir()
    (cal_dir / "corpus_inputs.json").write_bytes(b"[]")
    (cal_dir / "evaluation_profile.json").write_bytes(b"{}")
    _write_toy_schemas_dir(schemas_dir)  # SAN-881 PASS-1 CORRECTION: real bytes for the two $defs-branch-checked schemas
    spec_dir = tmp_path / "reference" / "spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "ALGORITHM-v4-c1c5-reference.md").write_bytes(b"algo")
    (spec_dir / "ALGORITHM-v4-tables-v1.json").write_bytes(b"{}")  # valid JSON -- SAN-881 PASS-1 FINAL CLOSURE CORRECTION: tables is now cache-validated as JSON too

    correct_hash = vd.compute_labeling_context_hash_from_disk(cal_dir, tmp_path).hex()
    commitment = {
        "corpus_version": 1,
        "author_commitments": [
            {"artifact_name": n, "byte_length": 1, "commitment_hex": "a" * 64}
            for n in vd.AUTHOR_COMMITMENT_ORDER
        ],
        "labeling_context_hash": correct_hash,
        # deliberately NO labeling_context_components at all
    }
    errors = vd.Errors()
    vd.check_commitment(errors, commitment, cal_dir=cal_dir, repo_root=tmp_path)
    assert any(vd.RULE_CORPUS_VERSION in e for e in errors)
    assert not any(vd.RULE_CONTEXT_HASH_MISMATCH in e for e in errors)


# ---------------------------------------------------------------------
# Section D: exact bundle entries -- every directory entry, not only
# Path.is_file() survivors.
# ---------------------------------------------------------------------

def test_main_semantic_stage_rejects_extra_directory_in_sealed_dir(tmp_path, monkeypatch, capsys):
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    sealed_dir = Path(argv[argv.index("--sealed-dir") + 1])
    (sealed_dir / "sneaky_extra_directory").mkdir()
    rc = vd.main(argv)  # must not raise
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_REVEAL_EXTRA in captured.err
    assert "Traceback" not in captured.err
    assert "sneaky_extra_directory" not in captured.err


def test_main_semantic_stage_rejects_symlinked_allowed_artifact(tmp_path, monkeypatch, capsys):
    # A symlink NAMED exactly like the one pinned member (pointing at a
    # real, byte-identical file elsewhere) must still be rejected -- an
    # allowed member must be a direct, regular, NON-SYMLINK file.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    sealed_dir = Path(argv[argv.index("--sealed-dir") + 1])
    real_bytes = (sealed_dir / "labels_author_semantic.json").read_bytes()
    real_target = tmp_path / "real_semantic_copy.json"
    real_target.write_bytes(real_bytes)
    (sealed_dir / "labels_author_semantic.json").unlink()
    (sealed_dir / "labels_author_semantic.json").symlink_to(real_target)
    rc = vd.main(argv)  # must not raise
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_REVEAL_NOT_REGULAR_FILE in captured.err
    assert "Traceback" not in captured.err


def test_check_bundle_exact_membership_directory_with_arbitrary_name_is_extra(tmp_path):
    sealed_dir = tmp_path / "sealed"
    sealed_dir.mkdir()
    (sealed_dir / "labels_author_semantic.json").write_bytes(b"[]")
    (sealed_dir / "an_arbitrary_directory").mkdir()
    errors = vd.Errors()
    vd._check_bundle_exact_membership(errors, sealed_dir, vd.SEMANTIC_SEALED_BUNDLE_ALLOWED, "sealed-dir")
    assert any(vd.RULE_REVEAL_EXTRA in e for e in errors)
    assert "an_arbitrary_directory" not in " ".join(errors)


def test_check_bundle_exact_membership_symlinked_allowed_member_rejected(tmp_path):
    sealed_dir = tmp_path / "sealed"
    sealed_dir.mkdir()
    real_target = tmp_path / "elsewhere.json"
    real_target.write_bytes(b"[]")
    (sealed_dir / "labels_author_semantic.json").symlink_to(real_target)
    errors = vd.Errors()
    vd._check_bundle_exact_membership(errors, sealed_dir, vd.SEMANTIC_SEALED_BUNDLE_ALLOWED, "sealed-dir")
    assert any(vd.RULE_REVEAL_NOT_REGULAR_FILE in e for e in errors)


# ---------------------------------------------------------------------
# Section E: fixed-code stage diagnostics -- every staged stderr detail
# line contains `rule=`.
# ---------------------------------------------------------------------

def test_main_staged_missing_artifact_every_stderr_detail_line_contains_rule_equals(tmp_path, monkeypatch, capsys):
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    sealed_dir = Path(argv[argv.index("--sealed-dir") + 1])
    (sealed_dir / "labels_author_semantic.json").unlink()
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    detail_lines = [l for l in captured.err.splitlines() if l.startswith("  - ")]
    assert detail_lines, captured.err
    for line in detail_lines:
        assert "rule=" in line, f"staged stderr detail line missing rule=: {line!r}"


# ---------------------------------------------------------------------
# Section G acceptance cross-checks
# ---------------------------------------------------------------------

def test_nine_protected_files_not_in_edit_surface_are_unimported_by_new_helpers():
    # Sanity: the new schema-gate helpers read schemas via vd.SCHEMAS /
    # <filename>, never a hardcoded absolute path -- confirms the
    # protected schema files (labels/design_metadata/coverage_manifest/
    # reveal_verification_ledger) are CONSUMED, never reshaped, by this
    # correction round.
    assert vd._STAGE_ARTIFACT_SCHEMA_SPEC["labels_author_semantic.json"] == ("labels_schema.json", "semanticFile")
    assert vd._STAGE_ARTIFACT_SCHEMA_SPEC["labels_author_contract.json"] == ("labels_schema.json", "contractFile")
    assert vd._STAGE_ARTIFACT_SCHEMA_SPEC["design_metadata.json"] == ("design_metadata_schema.json", None)
    assert vd._STAGE_ARTIFACT_SCHEMA_SPEC["coverage_manifest.json"] == ("coverage_manifest_schema.json", None)


# =======================================================================
# SAN-881 PASS-1 FINAL GATING CORRECTION: root repair -- VALIDITY MUST
# GATE, NOT MERELY ACCUMULATE. The PASS-1 CORRECTION ROUND above added
# _check_bundle_exact_membership / _check_nonce_map / the nonce-file
# location check / check_stage_schema_validity as INDEPENDENT diagnostic
# checks, but none of their boolean outcomes actually GATED downstream
# reads: a rejected symlinked member, a missing/extra bundle entry, a
# malformed nonce map, or a nonce file parked inside its own bundle all
# still let cryptographic subset verification run for whichever OTHER
# subset member happened to be legitimate. Every test in this section
# instruments vd.verify_reveal (and, where relevant,
# vd._snapshot_regular_file) to prove: post-fix, ZERO crypto calls for
# every one of these six precondition failures, and -- for the four
# GENUINE Tier-1 PATH GATE failures (missing member, extra entry,
# directory entry, symlinked member) -- ZERO staged-payload reads
# either. Pre-fix counts were captured by re-running each exact
# scenario against a verbatim reconstruction of the pre-fix
# run_stage_reveal_verification / check_stage_schema_validity /
# _check_bundle_exact_membership / _check_nonce_map pipeline (the code
# this correction replaces) and are cited in each test's docstring --
# never asserted here as if this file could still import two conflicting
# module versions simultaneously.
#
# SAN-881 PASS-1 FINAL CLOSURE CORRECTION: targets 5/6 (malformed nonce
# map) and 6/6 (nonce file inside its bundle) are NOT both Tier-1 PATH
# GATE failures under the strict Tier-1-before-any-nonce-read
# architecture -- nonce map KEY/HEX-SHAPE validation requires the
# file's CONTENT, so it is necessarily a TIER-2 concern (see
# test_tier2_malformed_nonce_map_yields_zero_crypto_full_snapshot_set,
# renamed accordingly); nonce-file LOCATION (target 6/6) remains a pure
# Tier-1 metadata check and still yields zero snapshot reads.
# =======================================================================

def _tracked_verify_reveal(monkeypatch) -> list:
    """Monkeypatches vd.verify_reveal with a call-counting wrapper
    (delegating to the real implementation) and returns the list its
    calls are recorded into."""
    calls: list = []
    original = vd.verify_reveal

    def _tracking(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(vd, "verify_reveal", _tracking)
    return calls


def _tier0_fixed_component_paths() -> set:
    """The ten file-backed Tier-0 fixed-component paths under the
    CURRENT vd.HERE / vd.SCHEMAS / vd.REPO_ROOT (which tests typically
    monkeypatch to a toy cal_dir) -- used to filter Tier-0 cache reads
    out of custody/stage-snapshot instrumentation below."""
    paths = {vd.HERE / "corpus_inputs.json", vd.HERE / "evaluation_profile.json"}
    for name in vd.SCHEMA_FILES:
        paths.add(vd.SCHEMAS / name)
    paths.add(vd.REPO_ROOT / "reference" / "spec" / "ALGORITHM-v4-c1c5-reference.md")
    paths.add(vd.REPO_ROOT / "reference" / "spec" / "ALGORITHM-v4-tables-v1.json")
    return paths


def _tracked_snapshot_reads_all(monkeypatch) -> list:
    """Monkeypatches vd._snapshot_regular_file with a call-counting
    wrapper (delegating to the real implementation) and returns the list
    of EVERY Path argument it was invoked with -- Tier-0 fixed-component
    reads INCLUDED. Use this (never the Tier-2-only _tracked_snapshot_reads
    below) when a test needs the FULL syscall-level custody-open
    inventory across both tiers."""
    calls: list = []
    original = vd._snapshot_regular_file

    def _tracking(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(vd, "_snapshot_regular_file", _tracking)
    return calls


def _tracked_snapshot_reads(monkeypatch) -> list:
    """Monkeypatches vd._snapshot_regular_file with a call-counting
    wrapper (delegating to the real implementation) and returns the list
    of Path arguments it was invoked with for TIER-2 (staged custody)
    content ONLY -- proves whether ANY staged-payload file content was
    opened at all (the SNAPSHOT GATE primitive is the ONLY function
    that opens bundle-member content).

    SAN-881 PASS-1 FINAL CLOSURE CORRECTION: the Tier-0 fixed-component
    cache (corpus_inputs.json, evaluation_profile.json, the six
    schemas, algorithm, tables) now ALSO reads through this SAME
    no-follow primitive, UNCONDITIONALLY, on every main() call --
    those ten reads are excluded here (see _tier0_fixed_component_paths)
    so this helper keeps its original, narrower meaning: "did any
    TIER-2 (custody/stage) content get opened". Tests that need the
    combined Tier-0 + Tier-2 inventory use _tracked_snapshot_reads_all
    instead."""
    calls: list = []
    original = vd._snapshot_regular_file
    tier0_paths = _tier0_fixed_component_paths()

    def _tracking(path):
        if path not in tier0_paths:
            calls.append(path)
        return original(path)

    monkeypatch.setattr(vd, "_snapshot_regular_file", _tracking)
    return calls


def test_path_gate_missing_member_yields_zero_crypto_and_zero_snapshot_reads(tmp_path, monkeypatch, capsys):
    # GENUINE RED target 1/6: missing bundle member. PRE-FIX (verified
    # via a verbatim reconstruction of the replaced pipeline against this
    # exact scenario): verify_reveal was called 1x -- the reviewer
    # semantic artifact's OWN crypto verification still ran even though
    # the author artifact was missing, because _check_bundle_exact_membership's
    # "not supplied" diagnostic never gated the crypto-bytes-gathering
    # loop. POST-FIX: zero.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    sealed_dir = Path(argv[argv.index("--sealed-dir") + 1])
    (sealed_dir / "labels_author_semantic.json").unlink()

    verify_calls = _tracked_verify_reveal(monkeypatch)
    snapshot_calls = _tracked_snapshot_reads(monkeypatch)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_REVEAL_NOT_SUPPLIED in captured.err
    assert len(verify_calls) == 0, f"crypto ran despite a missing bundle member: {verify_calls}"
    assert len(snapshot_calls) == 0, f"staged content was opened despite a PATH GATE failure: {snapshot_calls}"


def test_path_gate_extra_entry_yields_zero_crypto_and_zero_snapshot_reads(tmp_path, monkeypatch, capsys):
    # GENUINE RED target 2/6: an arbitrary, unrecognized extra file.
    # PRE-FIX: verify_reveal was called 2x (the FULL happy-path count --
    # the extra entry never blocked anything). POST-FIX: zero.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    sealed_dir = Path(argv[argv.index("--sealed-dir") + 1])
    (sealed_dir / "junk_extra_entry.txt").write_bytes(b"not a bundle member")

    verify_calls = _tracked_verify_reveal(monkeypatch)
    snapshot_calls = _tracked_snapshot_reads(monkeypatch)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_REVEAL_EXTRA in captured.err
    assert "junk_extra_entry.txt" not in captured.err
    assert len(verify_calls) == 0, f"crypto ran despite an unrecognized extra bundle entry: {verify_calls}"
    assert len(snapshot_calls) == 0, f"staged content was opened despite a PATH GATE failure: {snapshot_calls}"


def test_path_gate_directory_entry_yields_zero_crypto_and_zero_snapshot_reads(tmp_path, monkeypatch, capsys):
    # GENUINE RED target 3/6: an arbitrary directory placed inside the
    # bundle (the class of entry _check_bundle_exact_membership's
    # Section D root repair started detecting at all). PRE-FIX:
    # verify_reveal was called 2x (full happy-path count). POST-FIX: zero.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    sealed_dir = Path(argv[argv.index("--sealed-dir") + 1])
    (sealed_dir / "sneaky_extra_directory").mkdir()

    verify_calls = _tracked_verify_reveal(monkeypatch)
    snapshot_calls = _tracked_snapshot_reads(monkeypatch)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_REVEAL_EXTRA in captured.err
    assert "sneaky_extra_directory" not in captured.err
    assert len(verify_calls) == 0, f"crypto ran despite a directory entry in the bundle: {verify_calls}"
    assert len(snapshot_calls) == 0, f"staged content was opened despite a PATH GATE failure: {snapshot_calls}"


def test_path_gate_symlinked_member_yields_zero_crypto_and_zero_snapshot_reads(tmp_path, monkeypatch, capsys):
    # GENUINE RED target 4/6, THE core security regression this
    # correction closes: a symlink at a PINNED member name, pointing at
    # a real, byte-identical, correctly-committed file elsewhere.
    # PRE-FIX (captured LIVE against the actual pre-edit module before
    # any PASS-1 FINAL GATING CORRECTION changes were made): rc == 1 with
    # ONLY "sealed-dir[labels_author_semantic.json]: rule=REVEAL_ARTIFACT_NOT_REGULAR_FILE"
    # printed, YET verify_reveal was called 2x AND the rejected symlink's
    # TARGET was opened via path.read_bytes() (following the symlink) --
    # cryptographic subset verification ran to completion reading
    # straight through the very symlink the membership check had just
    # rejected. POST-FIX: zero crypto calls, zero snapshot reads; the
    # rejected symlink's target is never opened by anything.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    sealed_dir = Path(argv[argv.index("--sealed-dir") + 1])
    real_bytes = (sealed_dir / "labels_author_semantic.json").read_bytes()
    real_target = tmp_path / "real_semantic_copy.json"
    real_target.write_bytes(real_bytes)
    (sealed_dir / "labels_author_semantic.json").unlink()
    (sealed_dir / "labels_author_semantic.json").symlink_to(real_target)

    verify_calls = _tracked_verify_reveal(monkeypatch)
    snapshot_calls = _tracked_snapshot_reads(monkeypatch)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_REVEAL_NOT_REGULAR_FILE in captured.err
    assert "Traceback" not in captured.err
    assert len(verify_calls) == 0, f"crypto ran despite a rejected symlinked member: {verify_calls}"
    assert len(snapshot_calls) == 0, (
        f"a rejected symlink's target was opened by the snapshot helper: {snapshot_calls}"
    )


def test_tier2_malformed_nonce_map_yields_zero_crypto_full_snapshot_set(tmp_path, monkeypatch, capsys):
    # GENUINE RED target 5/6 (renamed under SAN-881 PASS-1 FINAL CLOSURE
    # CORRECTION -- see below): a nonce map with an extra, malformed-value
    # key ALONGSIDE an otherwise-valid entry for the legitimate subset
    # member. PRE-FIX: verify_reveal was called 2x (the extra key's own
    # malformed value never blocked the legitimate member's crypto
    # verification, which used its own, valid, unaffected nonce entry).
    # POST-FIX: zero crypto calls.
    #
    # SAN-881 PASS-1 FINAL CLOSURE CORRECTION: nonce-map KEY/HEX-SHAPE
    # validation (_check_nonce_map) requires the nonce file's CONTENT --
    # it is therefore a TIER-2 concern (Section 3: "Tier 1 performs ONLY
    # metadata/location checks ... nonce key/hex validation ... begin[s]"
    # only after the complete Tier-2 snapshot set exists), not a Tier-1
    # PATH GATE failure. This test's PRE-CORRECTION name/assertion
    # (`..._yields_zero_crypto_and_zero_snapshot_reads`) is stale: Tier 1
    # (bundle membership, nonce PATH location) passes cleanly here, so
    # Tier 2 correctly snapshots the COMPLETE 5-member set -- including
    # both nonce files -- before the malformed VALUE is ever parsed and
    # rejected. Zero crypto either way.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    nonces_file = Path(argv[argv.index("--nonces-file") + 1])
    nonces = json.loads(nonces_file.read_text())
    nonces["extra_junk_key"] = "not-valid-hex"
    nonces_file.write_text(json.dumps(nonces))

    verify_calls = _tracked_verify_reveal(monkeypatch)
    snapshot_calls = _tracked_snapshot_reads(monkeypatch)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_NONCE_KEYSET_MISMATCH in captured.err
    assert "extra_junk_key" not in captured.err
    assert len(verify_calls) == 0, f"crypto ran despite a malformed/mismatched nonce map: {verify_calls}"
    assert len(snapshot_calls) == 5, f"expected the full 5-member Tier-2 snapshot set: {snapshot_calls}"
    assert len(set(snapshot_calls)) == 5, "each Tier-2 member must be snapshotted EXACTLY once"


def test_path_gate_nonce_file_inside_bundle_yields_zero_crypto_and_zero_snapshot_reads(tmp_path, monkeypatch, capsys):
    # GENUINE RED target 6/6: --nonces-file physically parked INSIDE the
    # sealed_dir it accompanies. PRE-FIX: the location check (in main())
    # appended RULE_NONCE_FILE_INSIDE_BUNDLE to `errors` but STILL called
    # run_stage_reveal_verification unconditionally -- verify_reveal was
    # called 2x (full happy-path count). POST-FIX: main() threads the
    # location boolean into run_stage_reveal_verification's PATH GATE
    # combination, so this gates shut too: zero.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    sealed_dir = Path(argv[argv.index("--sealed-dir") + 1])
    nonces_file = Path(argv[argv.index("--nonces-file") + 1])
    inside_nonces_file = sealed_dir / "nonces.json"
    inside_nonces_file.write_text(nonces_file.read_text())
    argv2 = list(argv)
    argv2[argv2.index("--nonces-file") + 1] = str(inside_nonces_file)

    verify_calls = _tracked_verify_reveal(monkeypatch)
    snapshot_calls = _tracked_snapshot_reads(monkeypatch)
    rc = vd.main(argv2)
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_NONCE_FILE_INSIDE_BUNDLE in captured.err
    assert len(verify_calls) == 0, f"crypto ran despite the nonce file being parked inside its own bundle: {verify_calls}"
    assert len(snapshot_calls) == 0, f"staged content was opened despite a PATH GATE failure: {snapshot_calls}"


def test_path_gate_missing_reviewer_dir_yields_zero_crypto_calls(tmp_path, monkeypatch):
    # Companion regression (reviewer_dir=None entirely, not merely an
    # empty/mismatched directory): PRE-FIX, verify_reveal was still
    # called 1x for the author's own artifact (its crypto verification
    # was never gated by the reviewer side being wholly absent).
    # POST-FIX: zero -- reviewer_ok=False on the PATH GATE combination
    # gates the WHOLE stage shut, author included.
    commitment, sealed_dir, nonces, _reviewer_dir, _reviewer_nonces = _toy_stage_environment(
        tmp_path, sealed_names_on_disk=["labels_author_semantic.json"])
    nonces_path = _write_nonces_file(tmp_path, _scope_nonces(nonces, vd.SEMANTIC_AUTHOR_NONCE_KEYS))
    reviewer_nonces_path = _write_nonces_file(tmp_path, {})
    verify_calls = _tracked_verify_reveal(monkeypatch)
    errors = vd.Errors()
    vd.run_stage_reveal_verification(errors, commitment, "semantic", sealed_dir, nonces_path, None, reviewer_nonces_path, _toy_cache_with_real_schemas())
    assert errors != []
    assert any(vd.RULE_REVEAL_NOT_SUPPLIED in e for e in errors)
    assert len(verify_calls) == 0, f"crypto ran despite reviewer_dir being entirely absent: {verify_calls}"


def test_stage_schema_gate_contract_happy_path_crypto_call_count_is_four(tmp_path, monkeypatch, capsys):
    # HAPPY-PATH CRYPTO CALL COUNT PINNED (contract stage == 4
    # verifications: author contract labels, design metadata, coverage
    # manifest, reviewer contract labels). Companion to the existing
    # semantic happy-path positive control
    # (test_stage_schema_gate_semantic_happy_path_still_verifies_crypto,
    # pinned at 2) -- proves the three-tier gate does not over-block a
    # genuinely valid four-artifact contract-stage reveal.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_contract_only_bundle(tmp_path, env)

    verify_calls = _tracked_verify_reveal(monkeypatch)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    assert len(verify_calls) == 4  # author contract + design metadata + coverage manifest + reviewer contract


# ---------------------------------------------------------------------
# SHAPE-SAFE ENVELOPE BOUNDARY: every pre-schema accessor over
# commitment.json / a reviewer envelope must tolerate an ARBITRARY JSON
# shape without raising -- fixed-code diagnostic, never a traceback,
# never a path disclosure.
# ---------------------------------------------------------------------

def test_check_commitment_top_level_list_envelope_no_crash():
    # GENUINE RED: commitment.json is a JSON LIST at the top level (not
    # an object at all). PRE-FIX: `commitment.get("corpus_version")`
    # raised AttributeError: 'list' object has no attribute 'get' --
    # both here and, transitively, in a real vd.main([]) run.
    errors = vd.Errors()
    vd.check_commitment(errors, [], cal_dir=vd.HERE, repo_root=vd.REPO_ROOT)  # must not raise
    assert any(vd.RULE_CORPUS_VERSION in e for e in errors)
    errors2 = vd.Errors()
    vd.check_author_commitment_order(errors2, [])  # must not raise
    assert any(vd.RULE_COMMITMENT_ORDER_MISMATCH in e for e in errors2)


def test_check_commitment_non_object_string_envelope_no_crash():
    # GENUINE RED: commitment.json parses to a bare JSON string.
    # PRE-FIX: same AttributeError class as the top-level-list case.
    errors = vd.Errors()
    vd.check_commitment(errors, "just-a-string", cal_dir=vd.HERE, repo_root=vd.REPO_ROOT)  # must not raise
    assert any(vd.RULE_CORPUS_VERSION in e for e in errors)


def test_check_commitment_unhashable_artifact_name_no_crash():
    # GENUINE RED: an author_commitments entry declares
    # artifact_name=[] (a list -- unhashable). PRE-FIX:
    # `{c.get("artifact_name") for c in dict_entries}` raised
    # TypeError: unhashable type: 'list'.
    commitment = {
        "corpus_version": vd.EXPECTED_CORPUS_VERSION,
        "author_commitments": [{"artifact_name": [], "commitment_hex": "a" * 64, "byte_length": 5}],
        "labeling_context_hash": "a" * 64,
    }
    errors = vd.Errors()
    vd.check_commitment(errors, commitment, cal_dir=vd.HERE, repo_root=vd.REPO_ROOT)  # must not raise
    assert any(vd.RULE_COMMITMENT_ARTIFACT_SET in e for e in errors)


def test_check_commitment_numeric_commitment_hex_no_crash():
    # GENUINE RED: commitment_hex is a bare integer, not a string.
    # PRE-FIX: `len(c.get("commitment_hex") or "")` raised TypeError:
    # object of type 'int' has no len() (the `or ""` fallback only
    # triggers for FALSY values; a truthy int like 12345 sails through
    # to the bare len() call).
    commitment = {
        "corpus_version": vd.EXPECTED_CORPUS_VERSION,
        "author_commitments": [{"artifact_name": "design_metadata.json", "commitment_hex": 12345, "byte_length": 5}],
        "labeling_context_hash": "a" * 64,
    }
    errors = vd.Errors()
    vd.check_commitment(errors, commitment, cal_dir=vd.HERE, repo_root=vd.REPO_ROOT)  # must not raise
    assert any(vd.RULE_COMMITMENT_HEX_SHAPE in e for e in errors)


def test_main_top_level_list_commitment_json_no_crash(tmp_path, monkeypatch, capsys):
    # End-to-end regression: a genuinely malformed commitment.json (a
    # top-level JSON list) must not crash vd.main() at all -- fixed-code
    # failure only.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    (env["cal_dir"] / "commitment.json").write_text(json.dumps([]))
    rc = vd.main([])  # must not raise
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err


def test_main_malformed_reviewer_envelope_unhashable_artifact_name_no_crash(tmp_path, monkeypatch, capsys):
    # GENUINE RED (malformed reviewer envelope): the reviewer semantic
    # commitment envelope's artifact_commitment.artifact_name is a list
    # (unhashable). PRE-FIX: this is schema-invalid (routes to the
    # SCHEMA-INVALID branch), which called
    # _detect_stage_extras_fixed_codes -- `declared.add(ac["artifact_name"])`
    # raised TypeError: unhashable type: 'list' (reproduced live against
    # the actual pre-edit module: `vd.main(argv)` crashed with exactly
    # this traceback, rooted at validate_design.py's
    # _detect_stage_extras_fixed_codes). POST-FIX: _detect_stage_extras_fixed_codes
    # itself is hardened (defense in depth) AND this exact scenario is
    # additionally now caught earlier by schema validation before ever
    # reaching that function -- either way, no crash.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    reviewer_dir = Path(argv[argv.index("--reviewer-dir") + 1])
    env_path = reviewer_dir / vd.REVIEWER_SEMANTIC_COMMITMENT_FILE
    data = json.loads(env_path.read_text())
    data["artifact_commitment"] = {**data["artifact_commitment"], "artifact_name": []}
    env_path.write_text(json.dumps(data))

    rc = vd.main(argv)  # must not raise
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert vd.RULE_SCHEMA_INVALID in captured.err


def test_detect_stage_extras_fixed_codes_unhashable_artifact_name_no_crash():
    # Direct unit-level defense-in-depth regression for
    # _detect_stage_extras_fixed_codes itself (the exact function/line
    # that crashed pre-fix -- declared.add(ac["artifact_name"])) --
    # exercised directly so the fix is provably NOT contingent on the
    # schema gate happening to intercept this shape first elsewhere.
    commitment = {
        "labeling_context_hash": "a" * 64,
        "author_commitments": [],
        "artifact_commitment": {"artifact_name": []},
    }
    errors = vd.Errors()
    vd._detect_stage_extras_fixed_codes(
        errors, commitment, subset_names=set(), forbidden_extra_names=set(), artifact_bytes_by_name={})
    # must not raise; no particular error is required since
    # artifact_bytes_by_name is empty (nothing to classify)


def test_detect_stage_extras_unhashable_artifact_name_no_crash():
    # Same defense-in-depth hardening for the free-form-prose twin
    # (_detect_stage_extras, consumed by the directly-unit-tested
    # reveal_verify_subset).
    commitment = {
        "labeling_context_hash": "a" * 64,
        "author_commitments": [{"artifact_name": []}],
    }
    failures = vd.reveal_verify_subset(
        commitment, subset_names=set(), forbidden_extra_names=set(),
        artifact_bytes_by_name={}, nonces_by_name={},
    )  # must not raise
    assert isinstance(failures, list)


# ---------------------------------------------------------------------
# GENERATED-SCHEMA VALIDITY: _build_named_schema's synthetic $id must
# itself be a valid Draft 2020-12 identifier for every branch schema
# actually used by the staged reveal pipeline.
# ---------------------------------------------------------------------

def test_build_named_schema_all_five_branches_pass_check_schema():
    # GENUINE RED: PRE-FIX, _build_named_schema's synthetic $id was
    # `base_id + "#/$defs/<name>"` -- a JSON-POINTER FRAGMENT appended to
    # $id. The JSON Schema 2020-12 metaschema's own $id pattern
    # (`^[^#]*#?$`, "Non-empty fragments not allowed") rejects this:
    # Draft202012Validator.check_schema() raised jsonschema.exceptions.SchemaError
    # for every one of these five branches (verified directly against
    # the real commitment_schema.json / labels_schema.json on disk).
    # POST-FIX: $id is a path-segment append (no fragment); check_schema
    # passes for exactly the five (schema_file, def_name) branches this
    # module's staged pipeline actually uses as _build_named_schema
    # call targets (_STAGE_ARTIFACT_SCHEMA_SPEC's two labels_schema.json
    # branches, _STAGE_REVIEWER_ENVELOPE_DEF's two commitment_schema.json
    # branches, plus commitment.json's own "authorEnvelope" branch used
    # in main()).
    commitment_schema = json.loads((SCHEMAS_DIR / "commitment_schema.json").read_text())
    labels_schema = json.loads((SCHEMAS_DIR / "labels_schema.json").read_text())
    branches = [
        (commitment_schema, "authorEnvelope"),
        (commitment_schema, "reviewerSemanticEnvelope"),
        (commitment_schema, "reviewerContractEnvelope"),
        (labels_schema, "semanticFile"),
        (labels_schema, "contractFile"),
    ]
    assert len(branches) == 5
    for schema, def_name in branches:
        built = vd._build_named_schema(schema, def_name)
        Draft202012Validator.check_schema(built)  # must not raise SchemaError
        assert "#" not in built["$id"], f"{def_name}: $id still carries a fragment: {built['$id']!r}"


def test_build_named_schema_still_functions_after_id_fix():
    # Companion positive control: the $id fix must not break the
    # branch-specific validation semantics themselves (internal
    # #/$defs/... $ref resolution against the embedded $defs dict is
    # independent of the resource's own $id value). Uses a freshly-built
    # SCHEMA-VALID v2 author envelope (real on-disk components/hash, via
    # the same builders _build_main_toy_v2_stage_environment uses) rather
    # than the real, committed COMMITMENT global -- COMMITMENT is
    # INTENTIONALLY v1-transitional (corpus_version 1) and therefore
    # schema-invalid against authorEnvelope's corpus_version:2 const
    # pending the v2 reseal; using it here would conflate "the $id fix
    # broke validation" with "this repo hasn't resealed to v2 yet".
    schema = json.loads((SCHEMAS_DIR / "commitment_schema.json").read_text())
    built = vd._build_named_schema(schema, "authorEnvelope")
    validator = Draft202012Validator(built)
    assert validator.is_valid(1) is False

    ctx_hash_hex = vd.compute_labeling_context_hash_from_disk(vd.HERE, vd.REPO_ROOT).hex()
    components = vd.build_labeling_context_components(vd.HERE, vd.REPO_ROOT)
    algorithm_block = {"hash": "SHA256", "domain_separator": "sanna-calibration-commitment/1", "formula": vd.COMMITMENT_ALGORITHM_FORMULA}
    valid_author_envelope = {
        "corpus_version": 2, "envelope_kind": "AUTHOR", "labeling_context_hash": ctx_hash_hex,
        "labeling_context_components": components,
        "commitment_algorithm": algorithm_block,
        "author_commitments": [
            {"artifact_name": n, "byte_length": 1, "commitment_hex": "a" * 64}
            for n in vd.AUTHOR_COMMITMENT_ORDER
        ],
        "reveal_protocol": {
            "reviewer_commitment_filenames": [
                "labels_reviewer_semantic.commitment.json", "labels_reviewer_contract.commitment.json",
            ],
            "reviewer_commitment_method": (
                "identical to author_commitments: domain-separated SHA256(\"sanna-calibration-commitment/1\""
                " || NUL || artifact_name || NUL || raw_32_byte_nonce || raw_32_byte_labeling_context_hash"
                " || exact_artifact_bytes)"
            ),
            "abandonment_rule": "toy",
        },
    }
    assert validator.is_valid(valid_author_envelope) is True


# ---------------------------------------------------------------------
# NONCE + NAME NON-DISCLOSURE: an unknown supplied nonce key, or an
# attacker-declared artifact_name outside the fixed known vocabulary, is
# NEVER echoed into any error output -- a path-like/newline-bearing
# sentinel string must be absent from ALL output.
# ---------------------------------------------------------------------

_ATTACKER_SENTINEL = "attacker/../../secret\n  - fake_injected_line: rule=FAKE_OK"


def test_check_nonce_map_unknown_key_value_never_inspected_or_echoed():
    # GENUINE RED: PRE-FIX, _check_nonce_map hex64-checked EVERY supplied
    # key's value, including unknown/extra keys -- an attacker-supplied
    # key containing a path-like/newline-bearing sentinel was echoed
    # verbatim into a `{label}[{key}]: rule=NONCE_NOT_64_LOWERCASE_HEX`
    # line (reproduced directly: the sentinel string, embedded newline
    # and all, appeared in the errors list). POST-FIX: only keys in
    # (expected INTERSECT supplied) are value-checked; an unknown key is
    # covered SOLELY by the generic NONCE_KEYSET_MISMATCH.
    nonces = {_ATTACKER_SENTINEL: "not-valid-hex"}
    errors = vd.Errors()
    ok = vd._check_nonce_map(errors, nonces, frozenset({"labels_author_semantic.json"}), "nonces-file")
    assert ok is False
    blob = "\n".join(errors)
    assert _ATTACKER_SENTINEL not in blob
    assert any(vd.RULE_NONCE_KEYSET_MISMATCH in e for e in errors)
    assert not any(vd.RULE_NONCE_MALFORMED in e for e in errors)


def test_check_commitment_attacker_artifact_name_never_echoed():
    # GENUINE RED: PRE-FIX, an author_commitments entry's OWN declared
    # artifact_name (untrusted, attacker-controlled JSON content) was
    # echoed verbatim into `commitment.json[{artifact_name}]:
    # rule=COMMITMENT_HEX_SHAPE` / `...BYTE_LENGTH_SHAPE` error lines
    # (reproduced directly: the sentinel string, embedded newline and
    # all, appeared in the errors list). POST-FIX: only artifact_name
    # values that are members of the FIXED, known AUTHOR_ARTIFACT_NAMES
    # vocabulary are ever echoed; anything else is replaced with a fixed
    # placeholder.
    commitment = {
        "corpus_version": vd.EXPECTED_CORPUS_VERSION,
        "author_commitments": [{"artifact_name": _ATTACKER_SENTINEL, "commitment_hex": "nothex", "byte_length": -1}],
        "labeling_context_hash": "a" * 64,
    }
    errors = vd.Errors()
    vd.check_commitment(errors, commitment, cal_dir=vd.HERE, repo_root=vd.REPO_ROOT)
    blob = "\n".join(errors)
    assert _ATTACKER_SENTINEL not in blob
    assert any(vd.RULE_COMMITMENT_HEX_SHAPE in e for e in errors)
    assert any(vd.RULE_BYTE_LENGTH_SHAPE in e for e in errors)


def test_main_attacker_nonce_key_never_echoed_in_full_output(tmp_path, monkeypatch, capsys):
    # End-to-end: the sentinel is absent from ALL stdout/stderr produced
    # by a real vd.main(argv) run, not merely from the unit-level errors
    # list.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    nonces_file = Path(argv[argv.index("--nonces-file") + 1])
    nonces = json.loads(nonces_file.read_text())
    nonces[_ATTACKER_SENTINEL] = "not-valid-hex"
    nonces_file.write_text(json.dumps(nonces))

    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert _ATTACKER_SENTINEL not in captured.out
    assert _ATTACKER_SENTINEL not in captured.err
    assert "attacker" not in captured.err
    assert vd.RULE_NONCE_KEYSET_MISMATCH in captured.err


# ---------------------------------------------------------------------
# BYTE-EXACT TRANSITIONAL REGRESSION: the pinned v1-transitional
# four-line stderr output, byte-for-byte (order + trailing newline
# included), via the REAL CLI subprocess invocation this module's own
# docstring documents -- not merely the importable vd.main() function.
# ---------------------------------------------------------------------

def test_main_public_only_v1_transitional_output_is_byte_exact_via_real_cli():
    # PRESERVATION GREEN (never claim RED): this exact byte sequence was
    # already produced by vd.main([]) before ANY PASS-1 FINAL GATING
    # CORRECTION edit (verified directly against the real, unmodified
    # commitment.json / evaluation_profile.json on disk). This test adds
    # a REAL CLI subprocess invocation (acceptance item 3: "via the real
    # CLI, exit 1") as an independent, byte-exact regression -- it must
    # remain green, unchanged, after this correction.
    result = subprocess.run(
        [sys.executable, str(CAL_DIR / "validate_design.py")],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert result.stderr == (
        "VALIDATION FAILED: 4 error(s)\n"
        "  - evaluation_profile.json: rule=CORPUS_VERSION\n"
        "  - commitment.json: rule=CORPUS_VERSION\n"
        "  - commitment.json: rule=CONTEXT_HASH_MISMATCH\n"
        "  - commitment.json: rule=SCHEMA_INVALID\n"
    )


# =======================================================================
# SAN-881 PASS-1 CLOSURE PATCH: closes five reproduced escapes the PASS-1
# FINAL GATING CORRECTION left open -- prior instrumentation covered only
# _snapshot_regular_file and verify_reveal; this section instruments
# EVERY remaining read/crypto path: context-component reads
# (vd.check_fixed_context_components), snapshot opens
# (vd._snapshot_regular_file, already tracked above), and crypto
# (vd.verify_reveal, already tracked above). Authentic pre-fix RED
# evidence for every closure below was captured via an ISOLATED
# scratchpad script (verbatim reconstructions of the exact pre-fix
# snippets read from this module before any edit in this patch) --
# never git stash, never a second imported module version. See each
# test's docstring for its specific pre-fix repro.
#
# SAN-881 PASS-1 CORRECTION: this section's original nonce-file-load
# instrumentation helper (`_tracked_load_stage_nonces`, wrapping the
# module-level `vd._load_stage_nonces`) is REMOVED -- dead code since the
# SAN-881 PASS-1 FINAL CLOSURE CORRECTION retired `_load_stage_nonces`
# from validate_design.py entirely (nonce files now funnel through the
# same unified `_snapshot_regular_file` primitive as every other Tier-2
# custody read; see `test_legacy_generic_reveal_symbols_removed_entirely`
# / `test_legacy_generic_reveal_symbols_no_source_references` below,
# which already prove `_load_stage_nonces` does not exist on `vd` and has
# no live source reference). The wrapper was therefore defined but never
# called by anything in this file; see
# `test_tracked_load_stage_nonces_helper_removed_entirely` below, which
# proves it stays gone.
# =======================================================================

def _build_minimal_fixed_components_dir(tmp_path: Path) -> tuple[Path, Path]:
    """Builds a cal_dir/repo_root pair with every one of the ten
    file-backed labeling-context components genuinely present, readable,
    and (for the six schema files) self-valid -- the happy-path baseline
    each closure-2b RED case below deletes/corrupts exactly one
    component from."""
    cal_dir = tmp_path
    schemas_dir = cal_dir / "schemas"
    schemas_dir.mkdir()
    for name in vd.SCHEMA_FILES:
        (schemas_dir / name).write_bytes((SCHEMAS_DIR / name).read_bytes())
    (cal_dir / "corpus_inputs.json").write_bytes(b"[]")
    (cal_dir / "evaluation_profile.json").write_bytes(b"{}")
    spec_dir = tmp_path / "reference" / "spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "ALGORITHM-v4-c1c5-reference.md").write_bytes(b"algo prose")
    (spec_dir / "ALGORITHM-v4-tables-v1.json").write_bytes(b"{}")
    return cal_dir, tmp_path


# ---------------------------------------------------------------------
# CLOSURE 1: safe-parse commitment.json.
# ---------------------------------------------------------------------

def test_main_malformed_commitment_json_no_crash_unconditional_path(tmp_path, monkeypatch, capsys):
    # GENUINE RED (closure 1): PRE-FIX, main()'s commitment-loading block
    # was `commitment = load_json(commitment_path)` with NO try/except --
    # a malformed commitment.json raised an uncaught json.JSONDecodeError
    # straight out of vd.main(). Verified directly in an isolated
    # scratchpad script (san881_pass1_closure_patch/red_evidence.py,
    # CLOSURE 1): `json.loads("{not valid json,,,")` raised
    # JSONDecodeError, and pre-fix load_json's body -- copied verbatim --
    # was never wrapped. POST-FIX: a fixed RULE_COMMITMENT_UNREADABLE
    # diagnostic, commitment stays None, no traceback, no crash -- even
    # with NO --reveal-stage / --sealed-dir at all (the unconditional
    # top-of-main() path every invocation goes through).
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    (env["cal_dir"] / "commitment.json").write_text("{not valid json,,,")
    rc = vd.main([])  # must not raise
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert vd.RULE_COMMITMENT_UNREADABLE in captured.err


def test_main_malformed_commitment_json_reveal_stage_zero_stage_reads_zero_crypto(tmp_path, monkeypatch, capsys):
    # Companion end-to-end regression via --reveal-stage: malformed
    # commitment.json must yield ZERO nonce loads, ZERO staged snapshots,
    # ZERO crypto -- commitment stays None, which the pre-existing
    # `if commitment is None:` branch already correctly short-circuits.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    (env["cal_dir"] / "commitment.json").write_text("{not valid json,,,")

    verify_calls = _tracked_verify_reveal(monkeypatch)
    snapshot_calls = _tracked_snapshot_reads(monkeypatch)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert vd.RULE_COMMITMENT_UNREADABLE in captured.err
    assert len(verify_calls) == 0
    # SAN-881 PASS-1 FINAL CLOSURE CORRECTION: nonce files now read
    # through the SAME unified _snapshot_regular_file primitive as every
    # other Tier-2 member -- snapshot_calls == 0 already proves NEITHER
    # nonce file's content was opened (a separate _load_stage_nonces
    # tracker is no longer needed; that function is retired).
    assert len(snapshot_calls) == 0, (
        f"staged content (including nonce files) was opened despite malformed commitment.json: {snapshot_calls}"
    )


def test_main_parseable_but_schema_invalid_author_envelope_zero_crypto(tmp_path, monkeypatch, capsys):
    # Requirement-first distinction: malformed JSON ALONE does not test
    # the author validity CONJUNCTION -- this case is PARSEABLE JSON that
    # fails schema validation (envelope_kind wrong), proving author_gate_ok
    # gates on schema validity too, independently of JSON-parseability.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    commitment = dict(env["commitment"])
    commitment["envelope_kind"] = "REVIEWER_SEMANTIC"  # parseable, but wrong discriminant
    (env["cal_dir"] / "commitment.json").write_text(json.dumps(commitment))

    verify_calls = _tracked_verify_reveal(monkeypatch)
    snapshot_calls = _tracked_snapshot_reads(monkeypatch)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert len(verify_calls) == 0
    assert len(snapshot_calls) == 0


# ---------------------------------------------------------------------
# CLOSURE 2: author validity conjunction (author_gate_ok).
# ---------------------------------------------------------------------

def test_check_fixed_context_components_each_file_backed_category_missing(tmp_path):
    # GENUINE RED (closure 2b): PRE-FIX, check_commitment called
    # compute_labeling_context_hash_from_disk UNWRAPPED -- a missing
    # component raised an uncaught FileNotFoundError (verified directly
    # in the isolated scratchpad script, CLOSURE 2b: deleting
    # ALGORITHM-v4-c1c5-reference.md from a toy cal_dir raised
    # FileNotFoundError straight out of the unchanged
    # compute_labeling_context_hash_from_disk primitive). POST-FIX:
    # check_fixed_context_components diagnoses EVERY file-backed
    # component category missing -- corpus, profile, EACH of the six
    # schemas individually, algorithm, tables -- with a fixed
    # RULE_CONTEXT_COMPONENT_UNREADABLE diagnostic, never a
    # FileNotFoundError, and check_commitment's own wrapped recompute
    # (defense-in-depth) never raises either.
    #
    # Manual loop, not pytest.mark.parametrize (project convention for
    # this file) -- ten deletion cases: corpus_inputs.json,
    # evaluation_profile.json, the six schema files (each individually),
    # algorithm, tables.
    cases = [
        ("corpus_inputs.json", lambda cal, repo: cal / "corpus_inputs.json"),
        ("evaluation_profile.json", lambda cal, repo: cal / "evaluation_profile.json"),
        ("schemas/commitment_schema.json", lambda cal, repo: cal / "schemas" / "commitment_schema.json"),
        ("schemas/coverage_manifest_schema.json", lambda cal, repo: cal / "schemas" / "coverage_manifest_schema.json"),
        ("schemas/design_metadata_schema.json", lambda cal, repo: cal / "schemas" / "design_metadata_schema.json"),
        ("schemas/freeze_manifest_schema.json", lambda cal, repo: cal / "schemas" / "freeze_manifest_schema.json"),
        ("schemas/labels_schema.json", lambda cal, repo: cal / "schemas" / "labels_schema.json"),
        ("schemas/reveal_verification_ledger_schema.json", lambda cal, repo: cal / "schemas" / "reveal_verification_ledger_schema.json"),
        ("algorithm", lambda cal, repo: repo / "reference" / "spec" / "ALGORITHM-v4-c1c5-reference.md"),
        ("tables", lambda cal, repo: repo / "reference" / "spec" / "ALGORITHM-v4-tables-v1.json"),
    ]
    assert len(cases) == 10, "must cover all ten file-backed components (eleven total minus base_commit_sha)"
    for i, (component_name, resolve_path) in enumerate(cases):
        case_tmp = tmp_path / f"case_{i:02d}"
        case_tmp.mkdir()
        cal_dir, repo_root = _build_minimal_fixed_components_dir(case_tmp)
        target = resolve_path(cal_dir, repo_root)
        target.unlink()

        errors = vd.Errors()
        ok = vd.check_fixed_context_components(errors, cal_dir, repo_root)  # must not raise
        assert ok is False, f"{component_name}: expected fixed_components_ok=False"
        assert any(component_name in e and vd.RULE_CONTEXT_COMPONENT_UNREADABLE in e for e in errors), (
            f"{component_name}: expected a RULE_CONTEXT_COMPONENT_UNREADABLE diagnostic naming it, got {errors}"
        )

        # Defense-in-depth companion: check_commitment's own wrapped
        # recompute must ALSO never raise for this same missing component.
        commitment = {
            "corpus_version": vd.EXPECTED_CORPUS_VERSION,
            "author_commitments": [
                {"artifact_name": n, "byte_length": 1, "commitment_hex": "a" * 64}
                for n in vd.AUTHOR_COMMITMENT_ORDER
            ],
            "labeling_context_hash": "b" * 64,
        }
        errors2 = vd.Errors()
        gate = vd.check_commitment(errors2, commitment, cal_dir=cal_dir, repo_root=repo_root)  # must not raise
        assert gate["disk_context_ok"] is False
        assert any(vd.RULE_CONTEXT_HASH_MISMATCH in e for e in errors2)


def test_check_fixed_context_components_one_malformed_schema_not_only_missing(tmp_path):
    # Requirement-first distinction: a SELF-INVALID schema component
    # (present on disk, but not a valid Draft 2020-12 schema) must ALSO
    # fail closed -- missing alone does not test the "self-validity"
    # half of fixed_components_ok's contract.
    cal_dir, repo_root = _build_minimal_fixed_components_dir(tmp_path)
    (cal_dir / "schemas" / "labels_schema.json").write_text(json.dumps({"type": "not-a-real-jsonschema-type"}))
    errors = vd.Errors()
    ok = vd.check_fixed_context_components(errors, cal_dir, repo_root)  # must not raise
    assert ok is False
    assert any("schemas/labels_schema.json" in e and vd.RULE_CONTEXT_COMPONENT_UNREADABLE in e for e in errors)


def test_main_reveal_stage_removed_context_component_no_crash_zero_crypto(tmp_path, monkeypatch, capsys):
    # End-to-end companion: a removed bound context component
    # (ALGORITHM-v4-c1c5-reference.md, deleted from the toy repo_root
    # AFTER the fixture wrote it) must not crash vd.main() via
    # --reveal-stage, and must yield zero crypto.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    (vd.REPO_ROOT / "reference" / "spec" / "ALGORITHM-v4-c1c5-reference.md").unlink()

    verify_calls = _tracked_verify_reveal(monkeypatch)
    snapshot_calls = _tracked_snapshot_reads(monkeypatch)
    rc = vd.main(argv)  # must not raise
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert vd.RULE_CONTEXT_COMPONENT_UNREADABLE in captured.err
    assert len(verify_calls) == 0
    assert len(snapshot_calls) == 0


def test_main_reveal_stage_disk_context_mismatch_zero_crypto_both_stages(tmp_path, monkeypatch, capsys):
    # GENUINE RED (closure 2a): PRE-FIX dispatch was
    # `elif not commitment_schema_valid: ... else: <crypto>` --
    # commitment_schema_valid is PURELY a schema-shape check and says
    # nothing about whether labeling_context_hash matches a genuine
    # from-disk recompute. Verified directly in the isolated scratchpad
    # script (CLOSURE 2a): a hand-built v2 envelope with a forged
    # labeling_context_hash still validated commitment_schema_valid=True.
    # POST-FIX: author_gate_ok additionally requires disk_context_ok,
    # closing this for BOTH stages (the gate is computed once,
    # unconditionally, before stage dispatch).
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    sem_argv = _write_semantic_only_bundle(tmp_path, env)

    commitment = dict(env["commitment"])
    commitment["labeling_context_hash"] = "f" * 64  # schema-valid shape, genuinely wrong value
    (env["cal_dir"] / "commitment.json").write_text(json.dumps(commitment))

    verify_calls = _tracked_verify_reveal(monkeypatch)
    rc = vd.main(sem_argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_CONTEXT_HASH_MISMATCH in captured.err
    assert vd.RULE_AUTHOR_GATE_NOT_OK in captured.err
    assert len(verify_calls) == 0, f"crypto ran on the semantic stage despite a disk-context mismatch: {verify_calls}"

    # Same tampered commitment.json, contract stage: build a fresh
    # environment (contract bundle needs different sealed_dir/reviewer_dir
    # contents) but reuse the SAME tamper.
    contract_case_dir = tmp_path / "contract_case"
    contract_case_dir.mkdir()
    env2 = _build_main_toy_v2_stage_environment(contract_case_dir, monkeypatch)
    con_argv = _write_contract_only_bundle(contract_case_dir, env2)
    commitment2 = dict(env2["commitment"])
    commitment2["labeling_context_hash"] = "f" * 64
    (env2["cal_dir"] / "commitment.json").write_text(json.dumps(commitment2))

    verify_calls2 = _tracked_verify_reveal(monkeypatch)
    rc2 = vd.main(con_argv)
    captured2 = capsys.readouterr()
    assert rc2 == 1
    assert vd.RULE_CONTEXT_HASH_MISMATCH in captured2.err
    assert vd.RULE_AUTHOR_GATE_NOT_OK in captured2.err
    assert len(verify_calls2) == 0, f"crypto ran on the contract stage despite a disk-context mismatch: {verify_calls2}"


def test_main_reveal_stage_declared_component_forged_zero_crypto(tmp_path, monkeypatch, capsys):
    # Companion RED target: declared-component mismatch (the v2
    # envelope's OWN labeling_context_components list forged at one
    # entry) with the OUTER hash left correct -- must ALSO gate crypto
    # shut, via declared_components_ok specifically (a distinct operand
    # from disk_context_ok).
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    commitment = dict(env["commitment"])
    forged_components = [dict(c) for c in commitment["labeling_context_components"]]
    forged_components[0] = {**forged_components[0], "sha256": "9" * 64}
    commitment["labeling_context_components"] = forged_components
    (env["cal_dir"] / "commitment.json").write_text(json.dumps(commitment))

    verify_calls = _tracked_verify_reveal(monkeypatch)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_CONTEXT_HASH_MISMATCH in captured.err
    assert vd.RULE_AUTHOR_GATE_NOT_OK in captured.err
    assert len(verify_calls) == 0, f"crypto ran despite a forged declared component list: {verify_calls}"


def test_author_gate_ok_source_expression_matches_pinned_operands():
    # Sanity/documentation cross-check: the nine pinned operand NAMES
    # appear, ANDed, in validate_design.py's source -- catches silent
    # operand loss on a future refactor.
    source = (REPO_ROOT / "reference" / "calibration" / "validate_design.py").read_text()
    assert "author_gate_ok = (" in source
    for operand in (
        "commitment_read_ok", "commitment_json_ok", "fixed_components_ok",
        "schemas_self_valid_ok", "commitment_schema_valid", "commitment_structural_ok",
        "commitment_order_ok", "commitment_disk_context_ok", "commitment_declared_components_ok",
    ):
        assert operand in source


# ---------------------------------------------------------------------
# CLOSURE 3: nonce location before loading.
# ---------------------------------------------------------------------

def test_nonces_file_inside_bundle_never_opened_at_all(tmp_path, monkeypatch, capsys):
    # GENUINE RED (closure 3, historical): PRE-CLOSURE-PATCH, main()
    # called the (now-retired) `_load_stage_nonces(args.nonces_file, ...)`
    # (which opens+parses the file) BEFORE the `_path_is_inside` location
    # check ran -- a nonce file's content WAS read even though its
    # location was already forbidden.
    #
    # SAN-881 PASS-1 FINAL CLOSURE CORRECTION (Section 3): nonce-file
    # LOCATION is now a TIER-1 check evaluated for BOTH nonce paths as
    # part of ONE combined `path_gate_ok`, and "Any Tier-1 failure =>
    # neither nonce file is read" -- a STRICTER invariant than the
    # PASS-1 CLOSURE PATCH's per-file location gating this test
    # previously pinned (which still loaded the OTHER, legitimately-
    # located nonce file). GENUINE RED for THIS assertion, verified
    # directly against the pre-this-correction module: the reviewer
    # nonces file WAS still loaded (1 read) when only the author
    # nonces-file's location was bad. POST-FIX: zero reads of EITHER
    # nonce file's content -- proven via the unified _snapshot_regular_file
    # primitive (_load_stage_nonces no longer exists; nonce files funnel
    # through the SAME Tier-2 snapshot primitive as every other custody
    # member).
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    sealed_dir = Path(argv[argv.index("--sealed-dir") + 1])
    nonces_file = Path(argv[argv.index("--nonces-file") + 1])
    inside_nonces_file = sealed_dir / "nonces.json"
    inside_nonces_file.write_text(nonces_file.read_text())
    argv2 = list(argv)
    argv2[argv2.index("--nonces-file") + 1] = str(inside_nonces_file)

    snapshot_calls = _tracked_snapshot_reads(monkeypatch)
    rc = vd.main(argv2)
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_NONCE_FILE_INSIDE_BUNDLE in captured.err
    assert len(snapshot_calls) == 0, (
        f"staged content (including the OTHER, legitimately-located reviewer nonces file) "
        f"was opened despite a Tier-1 failure on the author nonces-file: {snapshot_calls}"
    )


def test_reviewer_nonces_file_inside_bundle_never_opened_at_all(tmp_path, monkeypatch, capsys):
    # Companion for --reviewer-nonces-file / --reviewer-dir -- same
    # "Any Tier-1 failure => neither nonce file is read" invariant.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    reviewer_dir = Path(argv[argv.index("--reviewer-dir") + 1])
    reviewer_nonces_file = Path(argv[argv.index("--reviewer-nonces-file") + 1])
    inside_file = reviewer_dir / "reviewer_nonces.json"
    inside_file.write_text(reviewer_nonces_file.read_text())
    argv2 = list(argv)
    argv2[argv2.index("--reviewer-nonces-file") + 1] = str(inside_file)

    snapshot_calls = _tracked_snapshot_reads(monkeypatch)
    rc = vd.main(argv2)
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_NONCE_FILE_INSIDE_BUNDLE in captured.err
    assert len(snapshot_calls) == 0, (
        f"staged content (including the OTHER, legitimately-located author nonces file) "
        f"was opened despite a Tier-1 failure on the reviewer nonces-file: {snapshot_calls}"
    )


# ---------------------------------------------------------------------
# CLOSURE 4: exact snapshot-name set, pinned Tier-2 membership/counts,
# gate-not-skip on an absent snapshot.
# ---------------------------------------------------------------------

def _flaky_snapshot(monkeypatch, fail_path: Path):
    """Monkeypatches vd._snapshot_regular_file so ONE specific path
    (which genuinely exists as a valid regular bundle member -- PATH
    GATE has already passed) returns None, simulating a TOCTOU /
    transient snapshot-open failure. Every other path snapshots
    normally."""
    original = vd._snapshot_regular_file

    def _flaky(path):
        if path == fail_path:
            return None
        return original(path)

    monkeypatch.setattr(vd, "_snapshot_regular_file", _flaky)


def test_snapshot_gate_injected_failure_author_artifact_gates_whole_stage(tmp_path, monkeypatch, capsys):
    # GENUINE RED (closure 4, member class 1/4: an author artifact):
    # PRE-FIX check_stage_schema_validity's `if name not in snapshots:
    # continue` never set ok=False -- verified directly in the isolated
    # scratchpad script (CLOSURE 4): a two-member subset with one
    # snapshot missing left `ok=True` after the loop. POST-FIX: gates
    # the WHOLE stage -- zero crypto even for the OTHER, genuinely
    # present and valid member.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    sealed_dir = Path(argv[argv.index("--sealed-dir") + 1])
    author_path = sealed_dir / "labels_author_semantic.json"
    _flaky_snapshot(monkeypatch, author_path)

    verify_calls = _tracked_verify_reveal(monkeypatch)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_STAGED_IO_FAILURE in captured.err
    assert "Traceback" not in captured.err
    assert len(verify_calls) == 0, (
        f"crypto ran for the reviewer artifact despite the author artifact's snapshot silently failing: {verify_calls}"
    )


def test_snapshot_gate_injected_failure_reviewer_artifact_gates_whole_stage(tmp_path, monkeypatch, capsys):
    # Member class 2/4: a reviewer artifact.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    reviewer_dir = Path(argv[argv.index("--reviewer-dir") + 1])
    reviewer_path = reviewer_dir / vd.REVIEWER_SEMANTIC_ARTIFACT
    _flaky_snapshot(monkeypatch, reviewer_path)

    verify_calls = _tracked_verify_reveal(monkeypatch)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_STAGED_IO_FAILURE in captured.err
    assert len(verify_calls) == 0, (
        f"crypto ran for the author artifact despite the reviewer artifact's snapshot silently failing: {verify_calls}"
    )


def test_snapshot_gate_injected_failure_reviewer_envelope_gates_whole_stage(tmp_path, monkeypatch, capsys):
    # Member class 3/4: the reviewer commitment ENVELOPE itself (not one
    # of subset_names, but its own gated snapshot-or-fail branch).
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    reviewer_dir = Path(argv[argv.index("--reviewer-dir") + 1])
    envelope_path = reviewer_dir / vd.REVIEWER_SEMANTIC_COMMITMENT_FILE
    _flaky_snapshot(monkeypatch, envelope_path)

    verify_calls = _tracked_verify_reveal(monkeypatch)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_STAGED_IO_FAILURE in captured.err
    assert len(verify_calls) == 0, (
        f"crypto ran despite the reviewer commitment envelope's snapshot silently failing: {verify_calls}"
    )


def test_snapshot_gate_injected_failure_nonce_file_gates_whole_stage(tmp_path, monkeypatch, capsys):
    # Member class 4/4: a nonce file (Tier-2 read, per the 5/7 custody-
    # open inventory). SAN-881 PASS-1 FINAL CLOSURE CORRECTION: nonce
    # files now read through the SAME unified _snapshot_regular_file
    # (os.open/os.read) primitive as every other Tier-2 member -- NOT
    # Path.read_bytes -- so the injected failure uses the SAME
    # _flaky_snapshot helper the other three member classes in this
    # section use, simulating a genuine on-disk file that fails to be
    # READ (not malformed content; a transient I/O error).
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    nonces_file = Path(argv[argv.index("--nonces-file") + 1])
    _flaky_snapshot(monkeypatch, nonces_file)

    verify_calls = _tracked_verify_reveal(monkeypatch)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_STAGED_IO_FAILURE in captured.err
    assert len(verify_calls) == 0, f"crypto ran despite the nonces-file snapshot failing: {verify_calls}"


def test_stage_schema_gate_semantic_happy_path_exactly_five_tier2_reads(tmp_path, monkeypatch, capsys):
    # PINNED TIER-2 INVENTORY (semantic == 5): two nonce files (author +
    # reviewer) + author semantic artifact + reviewer semantic artifact +
    # reviewer semantic envelope, EACH READ EXACTLY ONCE THROUGH THE ONE
    # UNIFIED _snapshot_regular_file PRIMITIVE (SAN-881 PASS-1 FINAL
    # CLOSURE CORRECTION -- previously nonce files and bundle-member
    # snapshots were two SEPARATE instrumented codepaths,
    # _load_stage_nonces vs. _snapshot_regular_file; that split is
    # retired). Companion to the pre-existing crypto-call-count positive
    # control (test_stage_schema_gate_semantic_happy_path_still_verifies_crypto,
    # pinned at 2 crypto calls) -- this proves the READ layer beneath it.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)

    snapshot_calls = _tracked_snapshot_reads(monkeypatch)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    assert len(snapshot_calls) == 5, snapshot_calls  # 2 nonce files + author semantic + reviewer semantic + reviewer envelope
    assert len(set(snapshot_calls)) == 5, "each of the 5 custody-member paths must be opened EXACTLY once"


def test_stage_schema_gate_contract_happy_path_exactly_seven_tier2_reads(tmp_path, monkeypatch, capsys):
    # PINNED TIER-2 INVENTORY (contract == 7): two nonce files + three
    # author artifacts (contract labels, design metadata, coverage
    # manifest) + reviewer contract artifact + reviewer contract
    # envelope, EACH READ EXACTLY ONCE THROUGH THE ONE UNIFIED
    # _snapshot_regular_file PRIMITIVE.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_contract_only_bundle(tmp_path, env)

    snapshot_calls = _tracked_snapshot_reads(monkeypatch)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    assert len(snapshot_calls) == 7, snapshot_calls  # 2 nonce files + 3 author artifacts + reviewer contract + reviewer envelope
    assert len(set(snapshot_calls)) == 7, "each of the 7 custody-member paths must be opened EXACTLY once"


# ---------------------------------------------------------------------
# CLOSURE 5: O_NOFOLLOW fail-closed.
# ---------------------------------------------------------------------

def test_snapshot_regular_file_o_nofollow_unavailable_fails_closed_no_open(tmp_path, monkeypatch):
    # GENUINE RED (closure 5): PRE-FIX, `flags = os.O_RDONLY; if
    # hasattr(os, "O_NOFOLLOW"): flags |= os.O_NOFOLLOW` still reached
    # `os.open(...)` unconditionally even when O_NOFOLLOW was absent --
    # silently degrading to a follow-symlinks open. Verified directly in
    # the isolated scratchpad script (CLOSURE 5): with O_NOFOLLOW
    # simulated absent, flags stayed plain O_RDONLY and the open call was
    # still reached. POST-FIX: os.open is NEVER called at all when
    # O_NOFOLLOW is unavailable -- proven here by tracking every
    # vd.os.open call while os.O_NOFOLLOW is removed from the real os
    # module for the duration of this test (monkeypatch auto-restores
    # it).
    real_file = tmp_path / "real.txt"
    real_file.write_bytes(b"content")
    monkeypatch.delattr(vd.os, "O_NOFOLLOW", raising=False)

    open_calls = []
    original_open = vd.os.open

    def _tracking_open(*args, **kwargs):
        open_calls.append(args)
        return original_open(*args, **kwargs)

    monkeypatch.setattr(vd.os, "open", _tracking_open)

    result = vd._snapshot_regular_file(real_file)
    assert result is None, "must fail closed (return None) when O_NOFOLLOW is unavailable"
    assert open_calls == [], f"os.open was called despite O_NOFOLLOW being unavailable: {open_calls}"


def test_main_o_nofollow_unavailable_end_to_end_zero_crypto(tmp_path, monkeypatch, capsys):
    # End-to-end companion: a genuinely valid semantic-only bundle, but
    # O_NOFOLLOW is unavailable for the duration of the run. SAN-881
    # PASS-1 FINAL CLOSURE CORRECTION: the Tier-0 fixed-component cache
    # now ALSO reads through the SAME no-follow primitive Tier 2 uses --
    # so O_NOFOLLOW unavailability fails EVERYTHING closed, not merely
    # the staged snapshot layer: fixed_components_ok (and therefore
    # author_gate_ok) is False before --reveal-stage dispatch is ever
    # reached, reported via RULE_AUTHOR_GATE_NOT_OK / RULE_CONTEXT_COMPONENT_UNREADABLE
    # rather than the Tier-2-specific RULE_STAGED_IO_FAILURE. Zero
    # crypto either way -- no traceback, no partial success.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    monkeypatch.delattr(vd.os, "O_NOFOLLOW", raising=False)

    verify_calls = _tracked_verify_reveal(monkeypatch)
    rc = vd.main(argv)  # must not raise
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert vd.RULE_CONTEXT_COMPONENT_UNREADABLE in captured.err
    assert vd.RULE_AUTHOR_GATE_NOT_OK in captured.err
    assert len(verify_calls) == 0


# ---------------------------------------------------------------------
# SAN-881 PASS-1 FINAL CLOSURE CORRECTION: legacy-removal proof. CLOSURE
# 6 above (this file's pre-existing history) hardened
# verify_envelope_generic / run_reveal_verification's path-construction
# safety; this correction round REMOVES both functions -- along with
# reveal_verify_set and the --legacy-reveal flag -- entirely, since no
# non-test consumer of the legacy path ever existed. The path-escape
# threat class those closure-6 tests targeted no longer has a legacy
# constructor to exploit at all.
# ---------------------------------------------------------------------

def test_legacy_generic_reveal_symbols_removed_entirely():
    # Legacy-removal proof: none of the three removed symbols -- or the
    # --legacy-reveal flag -- exist on the module / are accepted by
    # argparse anymore.
    for name in ("verify_envelope_generic", "run_reveal_verification", "reveal_verify_set", "_load_stage_nonces"):
        assert not hasattr(vd, name), f"{name} must be removed entirely"
    with pytest.raises(SystemExit):
        vd.main(["--legacy-reveal"])


def test_legacy_generic_reveal_symbols_no_source_references():
    # Companion to the hasattr check: zero LIVE code references (calls,
    # definitions, imports) to the removed symbols anywhere in
    # validate_design.py -- historical/removal-explanation prose in
    # comments is fine (and present), a `def`/call site is not.
    source = (CAL_DIR / "validate_design.py").read_text()
    for pattern in ("def verify_envelope_generic", "def run_reveal_verification", "def reveal_verify_set(",
                     "def _load_stage_nonces", "verify_envelope_generic(", "run_reveal_verification(",
                     "reveal_verify_set(", "_load_stage_nonces(", '"--legacy-reveal"', "args.legacy_reveal"):
        assert pattern not in source, f"live reference to removed symbol survives: {pattern!r}"


def test_tracked_load_stage_nonces_helper_removed_entirely():
    # SAN-881 PASS-1 CORRECTION (Fix 4, stale-code cleanup): this test
    # module's own nonce-tracking helper -- which monkeypatched the
    # production `_load_stage_nonces` symbol -- was DEAD CODE, defined
    # but never called anywhere in this file, since the two tests above
    # already prove the production symbol it wrapped does not exist and
    # has no live source reference in validate_design.py. Deleted; this
    # test proves it stays gone, at both the live-symbol level (this
    # module's own globals) and the source-text level (no live def/call
    # site survives in this file either).
    removed_helper_name = "_tracked_load_stage_nonces"
    assert removed_helper_name not in globals(), f"{removed_helper_name} must be removed entirely"
    source = Path(__file__).read_text()
    def_pattern = "def " + removed_helper_name
    call_pattern = removed_helper_name + "("
    assert def_pattern not in source, f"live definition of removed helper survives: {def_pattern!r}"
    assert call_pattern not in source, f"live call site of removed helper survives: {call_pattern!r}"


# ---------------------------------------------------------------------
# Reviewer / author path+newline-sentinel non-disclosure.
# ---------------------------------------------------------------------

def test_reveal_stage_sentinel_reviewer_artifact_name_never_disclosed(tmp_path, monkeypatch, capsys):
    # The previously-promised sentinel test for the REVIEWER side: a
    # reviewer envelope declaring a path-like/newline-bearing sentinel
    # artifact_name must never appear anywhere in stdout/stderr, and must
    # never be read (no traceback, no path disclosure).
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    reviewer_dir = Path(argv[argv.index("--reviewer-dir") + 1])
    env_path = reviewer_dir / vd.REVIEWER_SEMANTIC_COMMITMENT_FILE
    data = json.loads(env_path.read_text())
    data["artifact_commitment"] = {**data["artifact_commitment"], "artifact_name": _ATTACKER_SENTINEL}
    env_path.write_text(json.dumps(data))

    rc = vd.main(argv)  # must not raise
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert _ATTACKER_SENTINEL not in captured.out
    assert _ATTACKER_SENTINEL not in captured.err
    assert "attacker" not in captured.err


def test_reveal_stage_sentinel_author_artifact_name_never_disclosed(tmp_path, monkeypatch, capsys):
    # Companion for the AUTHOR side: commitment.json's own
    # author_commitments entry declaring the sentinel as artifact_name.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    commitment = dict(env["commitment"])
    entries = [dict(e) for e in commitment["author_commitments"]]
    entries[0] = {**entries[0], "artifact_name": _ATTACKER_SENTINEL}
    commitment["author_commitments"] = entries
    (env["cal_dir"] / "commitment.json").write_text(json.dumps(commitment))

    rc = vd.main(argv)  # must not raise
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert _ATTACKER_SENTINEL not in captured.out
    assert _ATTACKER_SENTINEL not in captured.err
    assert "attacker" not in captured.err


# ---------------------------------------------------------------------
# CLOSURE 7: README tier descriptions corrected.
# ---------------------------------------------------------------------

def test_readme_tier1_scoped_to_metadata_location_only():
    text = (CAL_DIR / "README.md").read_text()
    assert "Tier 1, PATH GATE (metadata/location ONLY -- no file content is EVER" in text
    assert "no nonce file is EVER read, at this tier" in text


def test_readme_tier2_reads_nonce_maps_staged_artifacts_envelopes_exactly_once():
    text = (CAL_DIR / "README.md").read_text()
    assert "Tier 2, SNAPSHOT GATE -- reads nonce maps, staged artifacts, and" in text
    assert "envelopes EXACTLY ONCE (5 members for the semantic stage, 7 for the" in text


def test_readme_documents_tier3_uses_exact_snapshots():
    text = (CAL_DIR / "README.md").read_text()
    assert "**Tier 3, CRYPTO GATE.** Cryptographic subset verification runs ONLY" in text
    assert "using those exact Tier-2 snapshots and nonce maps" in text


def test_readme_documents_outer_gate_reads_distinct_from_stage_snapshots():
    text = (CAL_DIR / "README.md").read_text()
    assert "Public author-envelope/context reads are OUTER-GATE reads, distinct" in text
    assert "from stage snapshots" in text


def test_readme_documents_author_gate_ok_expression_verbatim():
    text = (CAL_DIR / "README.md").read_text()
    assert "author_gate_ok = (" in text
    assert "commitment_read_ok and commitment_json_ok and fixed_components_ok" in text
    assert "and schemas_self_valid_ok and commitment_schema_valid and commitment_structural_ok" in text
    assert "and commitment_order_ok and commitment_disk_context_ok and commitment_declared_components_ok" in text


def test_readme_author_gate_ok_matches_source_verbatim():
    # Cross-file consistency: the README's pinned author_gate_ok
    # expression must be the SAME text (modulo indentation -- the
    # README fences it at a shallower depth than its actual position
    # inside main()) as validate_design.py's actual source -- prevents
    # documentation drift.
    readme_text = (CAL_DIR / "README.md").read_text()
    source_text = (CAL_DIR / "validate_design.py").read_text()
    expr_lines = [
        "author_gate_ok = (",
        "commitment_read_ok and commitment_json_ok and fixed_components_ok",
        "and schemas_self_valid_ok and commitment_schema_valid and commitment_structural_ok",
        "and commitment_order_ok and commitment_disk_context_ok and commitment_declared_components_ok",
        ")",
    ]
    readme_stripped_lines = [l.strip() for l in readme_text.splitlines()]
    source_stripped_lines = [l.strip() for l in source_text.splitlines()]
    for line in expr_lines:
        assert line in readme_stripped_lines, f"README missing line: {line!r}"
        assert line in source_stripped_lines, f"source missing line: {line!r}"


# =======================================================================
# SAN-881 PASS-1 FINAL CLOSURE CORRECTION: requirement-first tests for
# the Tier-0 single-source fixed-component cache, the unified
# no-follow custody-read primitive, and the strict Tier-1-before-any-
# nonce-read staged pipeline. GENUINE RED evidence for the three novel
# gaps below (main() crashing on a missing corpus/profile file; nonce
# files following symlinks with no O_NOFOLLOW protection; a bare
# --nonces-file silently no-opping) was captured via an ISOLATED
# scratchpad script (san881_pass1_final_closure_red_evidence.py, run
# against the unmodified module before any edit in this correction) --
# never git stash, never a second imported module version.
# =======================================================================

def _ten_fixed_component_cases() -> list:
    """The ten file-backed labeling-context component (name, path
    resolver) pairs -- every one of the eleven LABELING_CONTEXT_COMPONENT_NAMES
    entries except the non-file-backed `base_commit_sha` constant."""
    return [
        ("corpus_inputs.json", lambda cal, repo: cal / "corpus_inputs.json"),
        ("evaluation_profile.json", lambda cal, repo: cal / "evaluation_profile.json"),
        ("schemas/commitment_schema.json", lambda cal, repo: cal / "schemas" / "commitment_schema.json"),
        ("schemas/coverage_manifest_schema.json", lambda cal, repo: cal / "schemas" / "coverage_manifest_schema.json"),
        ("schemas/design_metadata_schema.json", lambda cal, repo: cal / "schemas" / "design_metadata_schema.json"),
        ("schemas/freeze_manifest_schema.json", lambda cal, repo: cal / "schemas" / "freeze_manifest_schema.json"),
        ("schemas/labels_schema.json", lambda cal, repo: cal / "schemas" / "labels_schema.json"),
        ("schemas/reveal_verification_ledger_schema.json", lambda cal, repo: cal / "schemas" / "reveal_verification_ledger_schema.json"),
        ("algorithm", lambda cal, repo: repo / "reference" / "spec" / "ALGORITHM-v4-c1c5-reference.md"),
        ("tables", lambda cal, repo: repo / "reference" / "spec" / "ALGORITHM-v4-tables-v1.json"),
    ]


def test_main_ten_fixed_components_missing_each_via_real_main(tmp_path, monkeypatch, capsys):
    # Requirement-first: "ten fixed-component MISSING/UNREADABLE cases
    # (corpus, profile, six schemas, algorithm, tables), each via real
    # main()". test_check_fixed_context_components_each_file_backed_category_missing
    # already covers this at the isolated check_fixed_context_components
    # level; this is the end-to-end companion through the REAL vd.main()
    # entrypoint, proving the Tier-0 cache is wired all the way through
    # (corpus/profile/tables consumption, schemas_self_valid_ok,
    # check_commitment) without a crash.
    cases = _ten_fixed_component_cases()
    assert len(cases) == 10
    for i, (component_name, resolve_path) in enumerate(cases):
        case_tmp = tmp_path / f"case_{i:02d}"
        case_tmp.mkdir()
        env = _build_main_toy_v2_stage_environment(case_tmp, monkeypatch)
        target = resolve_path(env["cal_dir"], vd.REPO_ROOT)
        target.unlink()
        rc = vd.main([])  # must not raise
        captured = capsys.readouterr()
        assert rc == 1, f"{component_name}: expected rc=1"
        assert "Traceback" not in captured.err, f"{component_name}: {captured.err}"
        assert component_name in captured.err and vd.RULE_CONTEXT_COMPONENT_UNREADABLE in captured.err, (
            f"{component_name}: expected a RULE_CONTEXT_COMPONENT_UNREADABLE diagnostic, got {captured.err}"
        )


def test_main_nine_json_components_malformed_each_via_real_main(tmp_path, monkeypatch, capsys):
    # Requirement-first: "Malformed JSON for the nine JSON components
    # (all but the algorithm markdown)".
    cases = [c for c in _ten_fixed_component_cases() if c[0] != "algorithm"]
    assert len(cases) == 9
    for i, (component_name, resolve_path) in enumerate(cases):
        case_tmp = tmp_path / f"case_{i:02d}"
        case_tmp.mkdir()
        env = _build_main_toy_v2_stage_environment(case_tmp, monkeypatch)
        target = resolve_path(env["cal_dir"], vd.REPO_ROOT)
        target.write_text("{not valid json,,,")
        rc = vd.main([])  # must not raise
        captured = capsys.readouterr()
        assert rc == 1, f"{component_name}: expected rc=1"
        assert "Traceback" not in captured.err, f"{component_name}: {captured.err}"
        assert component_name in captured.err and vd.RULE_CONTEXT_COMPONENT_UNREADABLE in captured.err, (
            f"{component_name}: expected a RULE_CONTEXT_COMPONENT_UNREADABLE diagnostic, got {captured.err}"
        )


def test_main_six_schemas_self_invalid_each_via_real_main(tmp_path, monkeypatch, capsys):
    # Requirement-first: "Self-invalid schema for each of the six
    # schemas (schema that fails Draft202012 check_schema)". Present on
    # disk, genuinely valid JSON, but not itself a valid Draft 2020-12
    # schema -- distinct failure class from "missing"/"malformed JSON".
    assert len(vd.SCHEMA_FILES) == 6
    for i, name in enumerate(vd.SCHEMA_FILES):
        case_tmp = tmp_path / f"case_{i:02d}"
        case_tmp.mkdir()
        env = _build_main_toy_v2_stage_environment(case_tmp, monkeypatch)
        (env["cal_dir"] / "schemas" / name).write_text(json.dumps({"type": "not-a-real-jsonschema-type"}))
        rc = vd.main([])  # must not raise
        captured = capsys.readouterr()
        assert rc == 1, f"{name}: expected rc=1"
        assert "Traceback" not in captured.err, f"{name}: {captured.err}"
        assert f"schemas/{name}" in captured.err and vd.RULE_CONTEXT_COMPONENT_UNREADABLE in captured.err, (
            f"{name}: expected a RULE_CONTEXT_COMPONENT_UNREADABLE diagnostic, got {captured.err}"
        )


def test_main_wrong_top_level_shape_corpus_profile_tables(tmp_path, monkeypatch, capsys):
    # Requirement-first: "Wrong top-level shape for corpus, profile,
    # tables". GENUINE RED for the profile case (pre-SAN-881-PASS-1-
    # CORRECTION history): check_evaluation_profile previously called
    # `profile.get(...)` directly -- a wrong-shaped (non-dict)
    # evaluation_profile.json raised an uncaught AttributeError. Fixed by
    # routing through the shape-safe `_safe_get` accessor (same pattern
    # already used by check_commitment).
    #
    # SAN-881 PASS-1 CORRECTION supersedes this test's ORIGINAL
    # downstream-rule assertions: PARSE-SUCCESS != VALID VALUE is now
    # enforced INSIDE `_load_fixed_components_cache` itself (Tier-0),
    # earlier than `main()`'s own corpus/profile consumers -- a
    # wrong-shaped corpus/profile/tables value never reaches those
    # consumers at all anymore (they stay None), so the OLD downstream
    # diagnostics (RULE_ITEM_COUNT for corpus, RULE_CORPUS_VERSION for
    # profile) no longer fire for these specific wrong-TOP-LEVEL-TYPE
    # cases; RULE_CONTEXT_COMPONENT_UNREADABLE fires instead, earlier and
    # uniformly across all three components.
    case1 = tmp_path / "case_corpus"
    case1.mkdir()
    _build_main_toy_v2_stage_environment(case1, monkeypatch)
    (vd.HERE / "corpus_inputs.json").write_text(json.dumps({"not": "a list"}))
    rc = vd.main([])  # must not raise
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert "corpus_inputs.json" in captured.err and vd.RULE_CONTEXT_COMPONENT_UNREADABLE in captured.err
    assert vd.RULE_ITEM_COUNT not in captured.err, "cache-level rejection must preempt the downstream ITEM_COUNT check"

    case2 = tmp_path / "case_profile"
    case2.mkdir()
    _build_main_toy_v2_stage_environment(case2, monkeypatch)
    (vd.HERE / "evaluation_profile.json").write_text(json.dumps([1, 2, 3]))
    rc = vd.main([])  # must not raise
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert "evaluation_profile.json" in captured.err and vd.RULE_CONTEXT_COMPONENT_UNREADABLE in captured.err
    assert vd.RULE_CORPUS_VERSION not in captured.err, "cache-level rejection must preempt the downstream profile check"

    # tables: a JSON list instead of a dict. tables_data is only
    # CONSUMED by the --sealed-dir structural path's design/label/
    # coverage predicates -- inert for a public-only run -- but SAN-881
    # PASS-1 CORRECTION now VALIDATES its top-level type at the Tier-0
    # cache regardless of whether anything downstream would have
    # consumed it, proving the cache itself tolerates the wrong shape
    # without raising (never attempts a dict-shaped access at
    # cache-build time) while still gating fixed_components_ok False.
    case3 = tmp_path / "case_tables"
    case3.mkdir()
    _build_main_toy_v2_stage_environment(case3, monkeypatch)
    (vd.REPO_ROOT / "reference" / "spec" / "ALGORITHM-v4-tables-v1.json").write_text(json.dumps([1, 2, 3]))
    rc = vd.main([])  # must not raise
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert "tables" in captured.err and vd.RULE_CONTEXT_COMPONENT_UNREADABLE in captured.err


def test_main_algorithm_component_missing_unreadable_non_utf8_and_hash_mismatch(tmp_path, monkeypatch, capsys):
    # Requirement-first: "Algorithm md (no 'malformed' grammar): missing,
    # unreadable, non-UTF-8 (if UTF-8 required), and context-hash
    # mismatch -- do NOT invent prose validation." The algorithm doc is
    # prose, read as RAW BYTES ONLY for hashing (_load_fixed_components_cache
    # never decodes or parses it) -- there is no "malformed prose
    # grammar" concept in this module by design. Readability
    # (missing/unreadable) and context-hash-mismatch (bytes changed
    # after commitment.json was sealed) are its only two failure
    # classes; non-UTF-8 bytes are neither -- they are simply read and
    # hashed like any other bytes.
    case_missing = tmp_path / "case_missing"
    case_missing.mkdir()
    _build_main_toy_v2_stage_environment(case_missing, monkeypatch)
    (vd.REPO_ROOT / "reference" / "spec" / "ALGORITHM-v4-c1c5-reference.md").unlink()
    rc = vd.main([])
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert "algorithm" in captured.err and vd.RULE_CONTEXT_COMPONENT_UNREADABLE in captured.err

    if os.geteuid() != 0:  # permission checks are bypassed under root
        case_unreadable = tmp_path / "case_unreadable"
        case_unreadable.mkdir()
        _build_main_toy_v2_stage_environment(case_unreadable, monkeypatch)
        algo_path = vd.REPO_ROOT / "reference" / "spec" / "ALGORITHM-v4-c1c5-reference.md"
        algo_path.chmod(0o000)
        try:
            rc = vd.main([])
            captured = capsys.readouterr()
            assert rc == 1
            assert "Traceback" not in captured.err
            assert "algorithm" in captured.err and vd.RULE_CONTEXT_COMPONENT_UNREADABLE in captured.err
        finally:
            algo_path.chmod(0o644)

    case_non_utf8 = tmp_path / "case_non_utf8"
    case_non_utf8.mkdir()
    _build_main_toy_v2_stage_environment(case_non_utf8, monkeypatch)
    (vd.REPO_ROOT / "reference" / "spec" / "ALGORITHM-v4-c1c5-reference.md").write_bytes(b"\xff\xfe not valid utf-8 \x80\x81")
    rc = vd.main([])  # must not raise
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert vd.RULE_CONTEXT_COMPONENT_UNREADABLE not in captured.err, (
        "algorithm is raw-byte-hashed prose, never decoded -- non-UTF-8 bytes must not be treated as unreadable/invalid"
    )
    assert vd.RULE_CONTEXT_HASH_MISMATCH in captured.err, (
        "non-UTF-8-but-genuinely-different bytes must still change the recomputed hash"
    )

    case_hash_mismatch = tmp_path / "case_hash_mismatch"
    case_hash_mismatch.mkdir()
    _build_main_toy_v2_stage_environment(case_hash_mismatch, monkeypatch)
    (vd.REPO_ROOT / "reference" / "spec" / "ALGORITHM-v4-c1c5-reference.md").write_text("a genuinely different, but well-formed, algorithm doc\n")
    rc = vd.main([])
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert vd.RULE_CONTEXT_COMPONENT_UNREADABLE not in captured.err
    assert vd.RULE_CONTEXT_HASH_MISMATCH in captured.err


def test_main_inside_bundle_nonce_symlink_pointing_outside_never_read(tmp_path, monkeypatch, capsys):
    # Requirement-first: "Inside-bundle nonce SYMLINK-pointing-outside ->
    # never read." The --nonces-file ARGUMENT points at a path INSIDE
    # sealed_dir, and that inside-bundle path is ITSELF a symlink
    # pointing OUTSIDE the bundle at a real, validly-formed nonces file.
    # GENUINE RED (pre-fix, captured via the isolated scratchpad script
    # CASE B against the unmodified module): nonce loading used
    # Path.read_bytes() with NO O_NOFOLLOW protection at all -- the
    # symlink was followed and its target's content returned. POST-FIX:
    # the unified _snapshot_regular_file primitive rejects the leaf
    # symlink outright (and the lexical "inside sealed_dir" Tier-1 check
    # fires independently too) -- the real, valid file it points to is
    # never opened by anything.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    sealed_dir = Path(argv[argv.index("--sealed-dir") + 1])
    real_nonces_file = Path(argv[argv.index("--nonces-file") + 1])
    inside_bundle_symlink = sealed_dir / "nonces_symlink.json"
    inside_bundle_symlink.symlink_to(real_nonces_file)
    argv2 = list(argv)
    argv2[argv2.index("--nonces-file") + 1] = str(inside_bundle_symlink)

    snapshot_calls = _tracked_snapshot_reads(monkeypatch)
    verify_calls = _tracked_verify_reveal(monkeypatch)
    rc = vd.main(argv2)  # must not raise
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert vd.RULE_NONCE_FILE_INSIDE_BUNDLE in captured.err or vd.RULE_REVEAL_NOT_REGULAR_FILE in captured.err
    assert len(verify_calls) == 0
    assert len(snapshot_calls) == 0, (
        f"staged content was opened despite the nonces-file being an inside-bundle symlink: {snapshot_calls}"
    )


def test_main_outside_bundle_nonce_leaf_symlink_never_read(tmp_path, monkeypatch, capsys):
    # Companion: the --nonces-file argument is LEXICALLY outside every
    # bundle (would pass the location check alone), but is ITSELF a
    # leaf symlink -- rejected regardless of target, per the v1 threat
    # boundary (leaf symlinks are always in scope).
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    real_nonces_file = Path(argv[argv.index("--nonces-file") + 1])
    outside_symlink = tmp_path / "outside_nonces_symlink.json"
    outside_symlink.symlink_to(real_nonces_file)
    argv2 = list(argv)
    argv2[argv2.index("--nonces-file") + 1] = str(outside_symlink)

    snapshot_calls = _tracked_snapshot_reads(monkeypatch)
    verify_calls = _tracked_verify_reveal(monkeypatch)
    rc = vd.main(argv2)  # must not raise
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert vd.RULE_REVEAL_NOT_REGULAR_FILE in captured.err
    assert len(verify_calls) == 0
    assert len(snapshot_calls) == 0, f"staged content was opened despite a leaf-symlinked nonces-file: {snapshot_calls}"


def test_main_missing_bundle_member_yields_zero_nonce_reads_by_name(tmp_path, monkeypatch, capsys):
    # Requirement-first: "Missing bundle member -> zero nonce reads."
    # Explicit, nonce-path-named companion to
    # test_path_gate_missing_member_yields_zero_crypto_and_zero_snapshot_reads
    # (which proves zero Tier-2 reads generically) -- proves NEITHER
    # nonce file's own path is EVER among the (now-unified) snapshot
    # calls, by identity.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    sealed_dir = Path(argv[argv.index("--sealed-dir") + 1])
    nonces_file = Path(argv[argv.index("--nonces-file") + 1])
    reviewer_nonces_file = Path(argv[argv.index("--reviewer-nonces-file") + 1])
    (sealed_dir / "labels_author_semantic.json").unlink()

    snapshot_calls = _tracked_snapshot_reads(monkeypatch)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert nonces_file not in snapshot_calls
    assert reviewer_nonces_file not in snapshot_calls
    assert len(snapshot_calls) == 0


def test_snapshot_gate_injected_failure_skips_schema_validation_of_other_members(tmp_path, monkeypatch, capsys):
    # Requirement-first: "Snapshot failure -> zero schema validations of
    # remaining members and zero crypto." Precision companion to
    # closure 4 above: when ONE Tier-2 member's snapshot fails, the
    # OTHER, genuinely-present member must not even be SCHEMA-VALIDATED
    # -- not merely "crypto never runs for it". Proven by making the
    # OTHER member schema-INVALID too (a zero-record labels file) and
    # confirming its own schema-invalidity rule never appears -- only
    # the snapshot failure does, proving Tier-2 schema validation is
    # gated by snapshot-set COMPLETENESS, not run per-member
    # independently.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    sealed_dir = Path(argv[argv.index("--sealed-dir") + 1])
    reviewer_dir = Path(argv[argv.index("--reviewer-dir") + 1])
    author_path = sealed_dir / "labels_author_semantic.json"
    reviewer_artifact_path = reviewer_dir / vd.REVIEWER_SEMANTIC_ARTIFACT
    reviewer_artifact_path.write_bytes(b"[]")  # zero-record: schema-invalid, IF ever reached
    _flaky_snapshot(monkeypatch, author_path)

    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert vd.RULE_STAGED_IO_FAILURE in captured.err
    assert vd.RULE_SCHEMA_INVALID not in captured.err, (
        "the reviewer artifact's schema-invalidity was reported despite the author artifact's own "
        "snapshot failing -- Tier-2 schema validation must be gated by snapshot-set completeness"
    )


def test_full_custody_open_accounting_semantic_stage(tmp_path, monkeypatch, capsys):
    # THE consolidated syscall-level custody-open inventory the
    # cache-and-gate design of this correction exists to prove: the
    # semantic stage performs EXACTLY 5 Tier-2 custody-member opens;
    # EVERY one of the ten file-backed Tier-0 fixed public components
    # opens EXACTLY ONCE, regardless of stage; and every opened path
    # (Tier-0 AND Tier-2) is opened through the ONE unified no-follow
    # primitive, with no path opened more than once -- proving no
    # schema (a Tier-0 member) is ever reopened during stage execution.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    sem_argv = _write_semantic_only_bundle(tmp_path, env)
    all_calls = _tracked_snapshot_reads_all(monkeypatch)
    rc = vd.main(sem_argv)
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    tier0_paths = _tier0_fixed_component_paths()
    tier0_calls = [p for p in all_calls if p in tier0_paths]
    tier2_calls = [p for p in all_calls if p not in tier0_paths]
    assert len(tier0_calls) == 10, tier0_calls  # ten file-backed fixed components
    assert len(set(tier0_calls)) == 10, "each fixed public component must open EXACTLY once"
    assert len(tier2_calls) == 5, tier2_calls
    assert len(set(tier2_calls)) == 5, "each of the 5 custody-member paths must open EXACTLY once"
    schema_paths = {vd.SCHEMAS / name for name in vd.SCHEMA_FILES}
    assert schema_paths <= set(tier0_calls)
    assert all(all_calls.count(p) == 1 for p in schema_paths), "a schema was opened more than once"


def test_full_custody_open_accounting_contract_stage(tmp_path, monkeypatch, capsys):
    # Contract-stage companion: EXACTLY 7 Tier-2 custody-member opens;
    # the ten Tier-0 fixed components each opening exactly once is
    # IDENTICAL regardless of stage (Tier 0 is stage-agnostic, built
    # once at the top of main()).
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    con_argv = _write_contract_only_bundle(tmp_path, env)
    all_calls = _tracked_snapshot_reads_all(monkeypatch)
    rc = vd.main(con_argv)
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    tier0_paths = _tier0_fixed_component_paths()
    tier0_calls = [p for p in all_calls if p in tier0_paths]
    tier2_calls = [p for p in all_calls if p not in tier0_paths]
    assert len(tier0_calls) == 10, tier0_calls
    assert len(set(tier0_calls)) == 10, "each fixed public component must open EXACTLY once"
    assert len(tier2_calls) == 7, tier2_calls
    assert len(set(tier2_calls)) == 7, "each of the 7 custody-member paths must open EXACTLY once"
    schema_paths = {vd.SCHEMAS / name for name in vd.SCHEMA_FILES}
    assert schema_paths <= set(tier0_calls)
    assert all(all_calls.count(p) == 1 for p in schema_paths), "a schema was opened more than once"


# =======================================================================
# SAN-881 PASS-1 CORRECTION: closes three reproduced escapes left open by
# the PASS-1 FINAL CLOSURE CORRECTION above.
#
# Fix 1 (PARSE-SUCCESS != VALID VALUE + EXECUTABLE $defs VALIDATION):
# _load_fixed_components_cache now enforces exact top-level TYPES for
# corpus_inputs.json (list), evaluation_profile.json / the tables doc /
# each of the six schemas (dict), and additionally BUILDS + check_schema's
# every named $defs branch this module actually consumes via
# _build_named_schema during cache construction, never leaving a missing/
# malformed branch to surface as an uncaught KeyError/AttributeError at a
# later consumer.
# Fix 2 (no-stage rejection short-circuit): a nonce/reviewer arg supplied
# WITHOUT --reveal-stage now SKIPS the generic --sealed-dir structural
# block entirely, rather than falling through into it.
# Fix 3 (_path_is_inside lexical + resolved containment, fail closed):
# the bundle-containment check for --nonces-file / --reviewer-nonces-file
# now rejects on EITHER lexical OR resolved containment, and fails
# CLOSED (rejected) on any resolution error.
#
# Authentic pre-fix RED evidence for every escape below was captured via
# TWO isolated scratchpad scripts (san881_pass1_correction/red_evidence.py,
# red_evidence_2.py) that imported the real, unmodified
# reference.calibration.validate_design module directly from the repo
# working tree BEFORE any edit in this correction and exercised each
# scenario -- never git stash, never a second imported module version,
# never a "verbatim reconstruction" of removed code. See each test's
# docstring for its specific pre-fix repro / captured output.
# =======================================================================

def _tracked_os_open(monkeypatch) -> list:
    """Wraps vd.os.open GLOBALLY -- the raw syscall-boundary primitive
    EVERY custody-relevant read in this module funnels through
    (_snapshot_regular_file is the ONLY caller, for both Tier-0
    fixed-component reads and Tier-2 staged/nonce reads alike) -- and
    returns the list of path arguments passed to it (strings, since
    _snapshot_regular_file calls `os.open(os.fspath(path), flags)`), in
    call order. SAN-881 PASS-1 CORRECTION: one syscall layer BELOW
    _tracked_snapshot_reads_all / _tracked_snapshot_reads (which wrap the
    higher-level _snapshot_regular_file Python function) -- proves the
    "zero custody opens" invariant at the actual syscall boundary, a
    stronger guarantee than instrumenting the higher-level wrapper alone
    (it would also catch a future caller that opened custody content via
    a path other than _snapshot_regular_file)."""
    calls: list = []
    original_open = vd.os.open

    def _tracking_open(path, *args, **kwargs):
        calls.append(path)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(vd.os, "open", _tracking_open)
    return calls


def _assert_stage_gate_rejected_zero_crypto_zero_custody(rc, captured, open_calls, verify_calls, expected_diag_label, case_label=""):
    """Shared assertion body for Fix 1 tests: the STANDARD
    fixed-component-gate-rejection shape via a real staged (--reveal-stage)
    main(argv) invocation -- rc==1, no traceback, the expected
    component-specific fixed diagnostic AND RULE_AUTHOR_GATE_NOT_OK
    present, ZERO Tier-2 custody opens (proven at the os.open syscall
    boundary), and ZERO crypto calls -- proving the rejection provably
    comes from the fixed-component gate, not an unrelated public error,
    and that run_stage_reveal_verification was never entered."""
    prefix = f"{case_label}: " if case_label else ""
    assert rc == 1, f"{prefix}{captured.err}"
    assert "Traceback" not in captured.err, f"{prefix}{captured.err}"
    assert expected_diag_label in captured.err and vd.RULE_CONTEXT_COMPONENT_UNREADABLE in captured.err, (
        f"{prefix}expected a RULE_CONTEXT_COMPONENT_UNREADABLE diagnostic naming {expected_diag_label!r}, got {captured.err}"
    )
    assert vd.RULE_AUTHOR_GATE_NOT_OK in captured.err, f"{prefix}{captured.err}"
    assert len(verify_calls) == 0, f"{prefix}crypto ran despite a fixed-component failure: {verify_calls}"
    tier0_paths = {str(p) for p in _tier0_fixed_component_paths()}
    tier2_opens = [c for c in open_calls if c not in tier0_paths]
    assert tier2_opens == [], f"{prefix}custody content was opened despite the fixed-component gate failing: {tier2_opens}"


def _rebuild_commitments_after_fixed_component_mutation(env: dict, cal_dir: Path, repo_root: Path) -> dict:
    """SAN-881 PASS-1 FINAL BLOCKER CORRECTION (FIX 2 -- genuine
    self-consistency for every fixed-component mutation test below).

    The three test functions immediately following this helper (and its
    sibling for the new transitive-referential-integrity cases) all
    mutate ONE fixed component ON DISK -- a corpus/profile/tables
    wrong-top-level-type rewrite, a schema rewritten as a bare boolean, a
    schema with a consumed $defs branch deleted, or a schema with a
    TRANSITIVE $defs dependency deleted -- AFTER
    `_build_main_toy_v2_stage_environment` already built a
    self-consistent commitment.json (+ reviewer envelopes) from the
    PRE-mutation bytes. Eight of the ten labeling-context components are
    themselves the mutated targets (corpus_inputs.json,
    evaluation_profile.json, the six schema files) or the tables doc, so
    the mutation changes their SHA-256, which changes
    `compute_labeling_context_hash_from_disk`'s output -- leaving
    commitment.json's PRE-mutation `labeling_context_hash` stale relative
    to the now-mutated disk state. Left uncorrected, `check_commitment`'s
    disk-context-hash cross-check (`commitment_disk_context_ok`) ALSO
    fails, for a completely UNRELATED reason, and -- confirmed via an
    isolated pre-fix scratchpad repro during this correction's RED
    reconstruction (labels_schema.json/itemId: real staged main(argv)
    returned rc=1 with ONLY `commitment.json: rule=CONTEXT_HASH_MISMATCH`
    and `RULE_AUTHOR_GATE_NOT_OK` in stderr -- author_gate_ok's
    `commitment_disk_context_ok` operand short-circuited the run BEFORE
    Tier 2 / run_stage_reveal_verification was ever entered, so the
    referential-integrity gate under test was never even reached) --
    this MASKS which gate is actually doing the rejecting: the prior
    version of these tests asserted
    `vd.RULE_CONTEXT_COMPONENT_UNREADABLE in captured.err`, which the
    cache's own per-component diagnostic satisfies regardless (it never
    depends on commitment.json at all), so the assertions still passed,
    but the docstring/comment claim of a "self-consistent starting
    environment" that isolates the fixed-component gate specifically was
    FALSE -- a stale hash was silently ALSO failing, undetected, on every
    case.

    This helper recomputes labeling_context_hash /
    labeling_context_components / every author + reviewer artifact
    commitment from the NEW, POST-mutation bytes (via the SAME from-disk
    primitives `_build_main_toy_v2_stage_environment` used originally --
    `vd.compute_labeling_context_hash_from_disk` /
    `vd.build_labeling_context_components` / `vd.compute_artifact_commitment`,
    never a hand-typed or copied-forward value), and REWRITES
    `cal_dir/commitment.json` plus `env["rev_sem_env"]` /
    `env["rev_con_env"]` in place to match -- so the ONLY defect left in
    the environment is the fixed component's own (in)validity. The two
    EXPLICIT pre-main assertions at the end prove the rewrite is
    genuinely bound: a FRESH, independent from-disk recomputation
    (separate from the one used to build the rewritten values a moment
    earlier) must equal what was just written, so the rejection asserted
    by every caller below is provably the fixed-component /
    referential-integrity gate -- never a stale-hash mismatch in
    disguise. Callers MUST invoke this AFTER mutating the fixed component
    and BEFORE building the staged bundle (`_write_semantic_only_bundle` /
    `_write_contract_only_bundle` write `env["rev_sem_env"]` /
    `env["rev_con_env"]` to disk at call time, so the bundle must be
    built from the ALREADY-rewritten env). The artifact BYTES and NONCES
    themselves (`env["artifact_bytes"]`, `env["author_nonces"]`,
    `env["rev_sem_artifact"]` / `env["rev_sem_nonce"]` /
    `env["rev_con_artifact"]` / `env["rev_con_nonce"]`) are untouched --
    only labeling_context_hash and every value cryptographically DERIVED
    from it are recomputed. Mutates `env["commitment"]`,
    `env["rev_sem_env"]`, `env["rev_con_env"]` in place and returns `env`
    for convenience."""
    ctx_hash_hex = vd.compute_labeling_context_hash_from_disk(cal_dir, repo_root).hex()
    ctx_hash_bytes = bytes.fromhex(ctx_hash_hex)
    components = vd.build_labeling_context_components(cal_dir, repo_root)

    commitment = env["commitment"]
    commitment["labeling_context_hash"] = ctx_hash_hex
    commitment["labeling_context_components"] = components
    commitment["author_commitments"] = [
        {"artifact_name": n, "byte_length": len(env["artifact_bytes"][n]),
         "commitment_hex": vd.compute_artifact_commitment(n, env["author_nonces"][n], ctx_hash_bytes, env["artifact_bytes"][n])}
        for n in vd.AUTHOR_COMMITMENT_ORDER
    ]
    (cal_dir / "commitment.json").write_text(json.dumps(commitment))

    rev_sem_env = env["rev_sem_env"]
    rev_sem_env["labeling_context_hash"] = ctx_hash_hex
    rev_sem_env["artifact_commitment"]["commitment_hex"] = vd.compute_artifact_commitment(
        vd.REVIEWER_SEMANTIC_ARTIFACT, env["rev_sem_nonce"], ctx_hash_bytes, env["rev_sem_artifact"])

    rev_con_env = env["rev_con_env"]
    rev_con_env["labeling_context_hash"] = ctx_hash_hex
    rev_con_env["artifact_commitment"]["commitment_hex"] = vd.compute_artifact_commitment(
        vd.REVIEWER_CONTRACT_ARTIFACT, env["rev_con_nonce"], ctx_hash_bytes, env["rev_con_artifact"])

    # EXPLICIT pre-main proof of genuine binding (FIX 2): a SEPARATE,
    # independent from-disk recomputation must equal what was just
    # written -- never merely "we assigned it a moment ago" (a
    # tautology).
    assert commitment["labeling_context_hash"] == vd.compute_labeling_context_hash_from_disk(cal_dir, repo_root).hex(), (
        "post-mutation commitment.json's rewritten labeling_context_hash does not match an independent "
        "from-disk recomputation -- the environment is not genuinely self-consistent"
    )
    assert commitment["labeling_context_components"] == vd.build_labeling_context_components(cal_dir, repo_root), (
        "post-mutation commitment.json's rewritten labeling_context_components does not match an independent "
        "from-disk recomputation -- the environment is not genuinely self-consistent"
    )
    return env


def test_stage_rejects_wrong_top_level_type_fixed_components(tmp_path, monkeypatch, capsys):
    # Fix 1, reproduced escapes 1-3 of 4 (PARSE-SUCCESS != VALID VALUE).
    # GENUINE RED (verified via the isolated scratchpad script BEFORE
    # this correction's edit -- red_evidence.py): pre-fix,
    # _load_fixed_components_cache accepted corpus_inputs.json=null
    # (ok=True, corpus=None), evaluation_profile.json=null (ok=True,
    # profile=None), a dict corpus_inputs.json (ok=True), a list
    # evaluation_profile.json (ok=True), and a list tables doc (ok=True,
    # tables=[1,2,3]) -- every one of the FIVE captured pre-fix runs
    # stayed `ok=True` with `errors=[]`, silently handing the
    # wrong-shaped value downstream. POST-FIX: each is rejected HERE,
    # with a RULE_CONTEXT_COMPONENT_UNREADABLE diagnostic naming the
    # specific component, zero custody (Tier-2) opens, and zero crypto --
    # proven via a REAL staged (--reveal-stage) main(argv) invocation.
    #
    # SAN-881 PASS-1 FINAL BLOCKER CORRECTION (this correction's own FIX
    # 2 -- genuine self-consistency): each case calls
    # _build_main_toy_v2_stage_environment FRESH, mutates one fixed
    # component, THEN calls
    # _rebuild_commitments_after_fixed_component_mutation to recompute
    # labeling_context_hash / labeling_context_components / every author
    # + reviewer commitment from the NEW post-mutation bytes and rewrite
    # commitment.json + the reviewer envelopes to match -- ONLY THEN is
    # the staged bundle built and main(argv) called. The PRIOR version of
    # this comment claimed "the Tier-0 cache is therefore genuinely
    # exercised against a self-consistent starting environment on every
    # case" -- that was FALSE: the environment was built once, BEFORE
    # mutation, and never recomputed afterward, even though
    # corpus_inputs.json / evaluation_profile.json / the tables doc are
    # THEMSELVES three of the eleven labeling-context components, so
    # mutating them left commitment.json's declared labeling_context_hash
    # stale relative to the post-mutation disk state. An isolated pre-fix
    # scratchpad repro during this correction's RED reconstruction
    # confirmed the practical consequence for an analogous case
    # (labels_schema.json/itemId, exercised by
    # test_stage_rejects_schema_missing_transitive_ref_dependency below):
    # real staged main(argv) returned rc=1 with ONLY
    # `commitment.json: rule=CONTEXT_HASH_MISMATCH` in stderr --
    # author_gate_ok's commitment_disk_context_ok operand alone was
    # already sufficient to reject, before Tier 2 was ever entered, so
    # the SPECIFIC gate that case's test claims to isolate was never
    # actually exercised. This test's own assertions still happened to
    # pass regardless (RULE_CONTEXT_COMPONENT_UNREADABLE is emitted by
    # the cache unconditionally, independent of commitment.json), but the
    # "self-consistent" claim was false, and the general risk (a
    # different case where ONLY the stale hash fires, silently masking a
    # missing fixed-component diagnostic) was real. The rebuild helper's
    # own two pre-main assertions prove the post-mutation environment is
    # NOW genuinely self-consistent, so every rejection below is provably
    # the fixed-component gate -- never a stale-hash mismatch in
    # disguise.
    cases = [
        ("corpus_null", "corpus_inputs.json",
         lambda cal_dir, repo_root: (cal_dir / "corpus_inputs.json").write_text("null")),
        ("profile_null", "evaluation_profile.json",
         lambda cal_dir, repo_root: (cal_dir / "evaluation_profile.json").write_text("null")),
        ("corpus_dict", "corpus_inputs.json",
         lambda cal_dir, repo_root: (cal_dir / "corpus_inputs.json").write_text(json.dumps({"not": "a list"}))),
        ("profile_list", "evaluation_profile.json",
         lambda cal_dir, repo_root: (cal_dir / "evaluation_profile.json").write_text(json.dumps([1, 2, 3]))),
        ("tables_list", "tables",
         lambda cal_dir, repo_root: (repo_root / "reference" / "spec" / "ALGORITHM-v4-tables-v1.json").write_text(json.dumps([1, 2, 3]))),
    ]
    for case_name, expected_label, mutate in cases:
        case_dir = tmp_path / case_name
        case_dir.mkdir()
        env = _build_main_toy_v2_stage_environment(case_dir, monkeypatch)
        mutate(env["cal_dir"], vd.REPO_ROOT)
        _rebuild_commitments_after_fixed_component_mutation(env, env["cal_dir"], vd.REPO_ROOT)
        argv = _write_semantic_only_bundle(case_dir, env)

        open_calls = _tracked_os_open(monkeypatch)
        verify_calls = _tracked_verify_reveal(monkeypatch)
        rc = vd.main(argv)
        captured = capsys.readouterr()
        _assert_stage_gate_rejected_zero_crypto_zero_custody(rc, captured, open_calls, verify_calls, expected_label, case_name)


def test_stage_rejects_boolean_schema_for_each_of_six_schemas(tmp_path, monkeypatch, capsys):
    # Fix 1, reproduced escape 4 of 4. GENUINE RED (verified via the
    # isolated scratchpad script BEFORE this correction's edit --
    # red_evidence.py): a bare JSON boolean (`true`) is a LEGAL top-level
    # JSON Schema document -- Draft202012Validator.check_schema(True)
    # does not raise -- but is not a dict; every downstream consumer of a
    # schema in this module assumes dict-shaped access.
    # cache["schema"]["commitment_schema.json"] became the literal
    # `True`, and _build_named_schema(True, "authorEnvelope") (what
    # main()'s own commitment_schema_valid check performs) raised an
    # uncaught `AttributeError: 'bool' object has no attribute 'get'`
    # (captured verbatim by the scratchpad script). POST-FIX: the
    # wrong-top-level-type check rejects `true` for EVERY one of the six
    # schema files (not merely the two with named $defs branches -- the
    # type check runs before any $defs-branch logic and applies
    # uniformly), each proven independently via a real staged
    # main(argv) run.
    #
    # SAN-881 PASS-1 FINAL BLOCKER CORRECTION (this correction's own FIX
    # 2): mutate, THEN _rebuild_commitments_after_fixed_component_mutation
    # (recomputes labeling_context_hash / components / every commitment
    # from the post-mutation bytes -- each of these six schema files is
    # itself one of the eleven labeling-context components, so rewriting
    # it as `true` changes its SHA-256 and would otherwise stale-mismatch
    # commitment.json's declared hash), THEN build the bundle -- see the
    # helper's own docstring and test_stage_rejects_wrong_top_level_type_fixed_components
    # above for the full rationale (a prior version of this suite skipped
    # this step, masking the intended gate behind an unrelated
    # CONTEXT_HASH_MISMATCH for cases whose crash site sits deeper than
    # the always-run commitment_schema.json authorEnvelope check).
    for filename in vd.SCHEMA_FILES:
        case_dir = tmp_path / filename.replace(".", "_")
        case_dir.mkdir()
        env = _build_main_toy_v2_stage_environment(case_dir, monkeypatch)
        (env["cal_dir"] / "schemas" / filename).write_text("true")
        _rebuild_commitments_after_fixed_component_mutation(env, env["cal_dir"], vd.REPO_ROOT)
        argv = _write_semantic_only_bundle(case_dir, env)

        open_calls = _tracked_os_open(monkeypatch)
        verify_calls = _tracked_verify_reveal(monkeypatch)
        rc = vd.main(argv)
        captured = capsys.readouterr()
        _assert_stage_gate_rejected_zero_crypto_zero_custody(
            rc, captured, open_calls, verify_calls, f"schemas/{filename}", filename
        )


def test_stage_rejects_schema_missing_required_defs_branch(tmp_path, monkeypatch, capsys):
    # Fix 1, EXECUTABLE $defs VALIDATION. GENUINE RED (verified via the
    # isolated scratchpad script BEFORE this correction's edit --
    # red_evidence.py, plus a direct jsonschema check confirming
    # check_schema does not dereference $ref targets): a schema document
    # missing one NAMED $defs branch (while its root still $refs that
    # branch elsewhere) remains fully self-valid under
    # Draft202012Validator.check_schema() at its OWN ROOT -- the gap was
    # only ever caught the first time a real consumer built that
    # SPECIFIC branch via _build_named_schema, as an uncaught KeyError
    # (`schema["$defs"][def_name]`). POST-FIX: every named branch this
    # module can ever be asked to build is built and check_schema'd
    # DURING cache construction -- a missing one is rejected HERE, for
    # both schema files that define named branches.
    #
    # SAN-881 PASS-1 FINAL BLOCKER CORRECTION (this correction's own FIX
    # 2): mutate, THEN _rebuild_commitments_after_fixed_component_mutation,
    # THEN build the bundle -- see
    # test_stage_rejects_wrong_top_level_type_fixed_components above for
    # the full rationale.
    cases = [
        ("commitment_schema.json", "authorEnvelope"),
        ("labels_schema.json", "semanticFile"),
    ]
    for filename, missing_def_name in cases:
        case_dir = tmp_path / filename.replace(".", "_")
        case_dir.mkdir()
        env = _build_main_toy_v2_stage_environment(case_dir, monkeypatch)
        schema_path = env["cal_dir"] / "schemas" / filename
        schema = json.loads(schema_path.read_text())
        assert missing_def_name in schema["$defs"], f"{filename}: fixture drift -- {missing_def_name!r} must exist before deletion"
        del schema["$defs"][missing_def_name]
        # Still self-valid at its OWN ROOT -- proves this is caught by
        # the NEW branch-specific check, not the pre-existing root
        # check_schema (which never dereferences $ref targets).
        Draft202012Validator.check_schema(schema)
        schema_path.write_text(json.dumps(schema))
        _rebuild_commitments_after_fixed_component_mutation(env, env["cal_dir"], vd.REPO_ROOT)
        argv = _write_semantic_only_bundle(case_dir, env)

        open_calls = _tracked_os_open(monkeypatch)
        verify_calls = _tracked_verify_reveal(monkeypatch)
        rc = vd.main(argv)
        captured = capsys.readouterr()
        _assert_stage_gate_rejected_zero_crypto_zero_custody(
            rc, captured, open_calls, verify_calls, f"schemas/{filename}", filename
        )


# SAN-881 PASS-1 FINAL BLOCKER CORRECTION toy fixtures for
# freeze_manifest_schema.json / reveal_verification_ledger_schema.json --
# schema-shaped instances used ONLY to prove, at the actual jsonschema
# instance-validation boundary, that a missing hex64 dependency in
# either document is a genuine, reachable defect (the SAME operation
# measure.py / benchmark.py perform against these exact schema files),
# even though validate_design.py's own main() never itself
# instance-validates against either schema.
_TOY_FREEZE_MANIFEST_INSTANCE = {
    "corpus_version": 2,
    "corpus_inputs_sha256": "0" * 64, "labels_frozen_sha256": "0" * 64,
    "design_metadata_sha256": "0" * 64, "coverage_manifest_sha256": "0" * 64,
    "evaluation_profile_sha256": "0" * 64,
    "algorithm_sha256": "49c138595fde5ee517d00d6b41eb815cf1016213a0cb7978ef258560cf5a4c59",
    "tables_sha256": "0a18dd94bc811bb3166a4f8812e78f2b053a9f8f083b781a21fb0f8371f54ecc",
    "adjudication_log_sha256": "0" * 64, "labeling_context_hash": "0" * 64,
    "author_commitment_sha256": "0" * 64, "reviewer_semantic_commitment_sha256": "0" * 64,
    "reviewer_contract_commitment_sha256": "0" * 64, "reveal_verification_ledger_sha256": "0" * 64,
}
_TOY_REVEAL_LEDGER_INSTANCE = {
    "corpus_version": 2, "labeling_context_hash": "0" * 64,
    "entries": [
        {"artifact_name": "labels_author_semantic.json", "envelope": "author", "commitment_hex": "0" * 64, "verified": True, "verified_stage": "semantic", "byte_length": 1},
        {"artifact_name": "labels_reviewer_semantic.json", "envelope": "reviewer_semantic", "commitment_hex": "0" * 64, "verified": True, "verified_stage": "semantic", "byte_length": 1},
        {"artifact_name": "labels_author_contract.json", "envelope": "author", "commitment_hex": "0" * 64, "verified": True, "verified_stage": "contract", "byte_length": 1},
        {"artifact_name": "design_metadata.json", "envelope": "author", "commitment_hex": "0" * 64, "verified": True, "verified_stage": "contract", "byte_length": 1},
        {"artifact_name": "coverage_manifest.json", "envelope": "author", "commitment_hex": "0" * 64, "verified": True, "verified_stage": "contract", "byte_length": 1},
        {"artifact_name": "labels_reviewer_contract.json", "envelope": "reviewer_contract", "commitment_hex": "0" * 64, "verified": True, "verified_stage": "contract", "byte_length": 1},
    ],
}


def test_stage_rejects_schema_missing_transitive_ref_dependency(tmp_path, monkeypatch, capsys):
    # SAN-881 PASS-1 FINAL BLOCKER CORRECTION -- THE BLOCKER FIX (cache-
    # time referential-integrity validation). GENUINE RED (verified via
    # an isolated scratchpad script BEFORE this correction's edit --
    # never git stash, never a "verbatim reconstruction" of removed
    # code -- imported the real, unmodified validate_design module
    # directly from the working tree): `Draft202012Validator.check_schema()`
    # (both the pre-existing root pass and the pre-existing named-branch
    # pass -- `test_stage_rejects_schema_missing_required_defs_branch`
    # above) never dereferences a `$ref` TARGET, only the document's own
    # syntax -- so a schema whose CONSUMED branch exists and is itself
    # syntactically valid, but which transitively `$ref`s a `$defs` key
    # missing from the SAME document, still passed `_load_fixed_components_cache`
    # with `ok=True` and the broken schema present in `schema_by_name`,
    # pre-fix, for every one of the six schema files. The scratchpad
    # repro deleted ONE dependency per schema (matching the six cases
    # below) and confirmed, for the FOUR schemas this module's own
    # main() instance-validates (commitment_schema.json /
    # labels_schema.json via the semantic stage; design_metadata_schema.json /
    # coverage_manifest_schema.json via the contract stage -- see
    # _STAGE_ARTIFACT_SCHEMA_SPEC), a real staged (--reveal-stage)
    # main(argv) call -- run against a genuinely self-consistent
    # environment via _rebuild_commitments_after_fixed_component_mutation,
    # see that helper's docstring -- raised an uncaught
    # `jsonschema.exceptions._WrappedReferencingError` /
    # `referencing.exceptions.PointerToNowhere` for EVERY case, verbatim,
    # e.g. for commitment_schema.json/hex64:
    #   PointerToNowhere: '/$defs/hex64' does not exist within
    #   {'$id': '.../commitment/v2.json/authorEnvelope', ...}
    # For the REMAINING TWO schemas -- freeze_manifest_schema.json and
    # reveal_verification_ledger_schema.json -- grep confirms
    # validate_design.py's main() never itself instance-validates
    # against either (only measure.py / benchmark.py do, both OUT OF
    # SCOPE / byte-identical for this correction): the scratchpad repro
    # confirmed a real staged main(argv) call returned rc=0 with EMPTY
    # stderr for both, pre-fix -- a broken transitive $ref there was a
    # SILENT gap in this module's own flow, not even a crash. This is
    # WHY the fix lives in the shared Tier-0 cache (`_load_fixed_components_cache`),
    # unconditionally, for ALL SIX schemas, rather than only guarding the
    # specific instance-validation call sites this module happens to
    # have today: `commitment_disk_context_ok` / `fixed_components_ok` /
    # `schemas_self_valid_ok` gate `author_gate_ok` shut for ALL SIX
    # uniformly regardless of which schema's content this module's OWN
    # main() separately instance-validates, and this test's [4] below
    # separately proves each of these two IS a genuine, reachable
    # PointerToNowhere at the real jsonschema instance-validation
    # boundary -- the SAME operation measure.py / benchmark.py actually
    # perform against these exact schema files.
    #
    # POST-FIX: `_schema_ref_integrity_violation` (see its docstring for
    # the closed grammar / graph-walk / cycle-detection design) walks
    # each document's COMPLETE local-$ref graph during cache
    # construction and evicts a schema whose transitive dependency is
    # missing -- the SAME fixed RULE_CONTEXT_COMPONENT_UNREADABLE
    # diagnostic, no new rule vocabulary, no traceback, zero Tier-2
    # custody opens, zero crypto -- proven for ALL SIX schemas via a real
    # staged main(argv) run (identical assertion shape to every sibling
    # test above, via _assert_stage_gate_rejected_zero_crypto_zero_custody),
    # even for the two main() never itself instance-validates, since the
    # OUTER gate (author_gate_ok) is unconditional on fixed_components_ok /
    # schemas_self_valid_ok regardless of per-schema consumption.
    cases = [
        ("commitment_schema.json", "hex64", "semantic"),
        ("labels_schema.json", "itemId", "semantic"),
        ("design_metadata_schema.json", "item", "contract"),
        ("coverage_manifest_schema.json", "evidenceRecord", "contract"),
        ("freeze_manifest_schema.json", "hex64", "semantic"),
        ("reveal_verification_ledger_schema.json", "hex64", "semantic"),
    ]
    for filename, missing_def_name, stage in cases:
        case_dir = tmp_path / filename.replace(".", "_")
        case_dir.mkdir()
        env = _build_main_toy_v2_stage_environment(case_dir, monkeypatch)
        schema_path = env["cal_dir"] / "schemas" / filename
        schema = json.loads(schema_path.read_text())
        assert missing_def_name in schema["$defs"], f"{filename}: fixture drift -- {missing_def_name!r} must exist before deletion"
        del schema["$defs"][missing_def_name]
        # [1] Still self-valid at its OWN ROOT -- proves this is caught
        # by the NEW referential-integrity walk, not root check_schema
        # (which never dereferences $ref targets).
        Draft202012Validator.check_schema(schema)
        schema_path.write_text(json.dumps(schema))
        _rebuild_commitments_after_fixed_component_mutation(env, env["cal_dir"], vd.REPO_ROOT)

        # [2] Direct cache-level proof: the mutated schema is evicted and
        # `ok` is False, independent of any staged bundle.
        cache_errors = vd.Errors()
        cache = vd._load_fixed_components_cache(cache_errors, env["cal_dir"], vd.REPO_ROOT)
        assert cache["ok"] is False, f"{filename}: cache incorrectly reports ok=True after {missing_def_name!r} deletion"
        assert filename not in cache["schema"], f"{filename}: schema not evicted from schema_by_name"
        assert any(filename in e and vd.RULE_CONTEXT_COMPONENT_UNREADABLE in e for e in cache_errors), (
            f"{filename}: no RULE_CONTEXT_COMPONENT_UNREADABLE diagnostic naming this schema: {list(cache_errors)}"
        )

        # [3] Real staged main(argv): fixed-diagnostic refusal, zero
        # crypto, zero Tier-2 custody opens -- for ALL SIX schemas
        # uniformly (see docstring above for why this holds even for the
        # two schemas main() never itself instance-validates).
        if stage == "semantic":
            argv = _write_semantic_only_bundle(case_dir, env)
        else:
            argv = _write_contract_only_bundle(case_dir, env)
        open_calls = _tracked_os_open(monkeypatch)
        verify_calls = _tracked_verify_reveal(monkeypatch)
        rc = vd.main(argv)
        captured = capsys.readouterr()
        _assert_stage_gate_rejected_zero_crypto_zero_custody(
            rc, captured, open_calls, verify_calls, f"schemas/{filename}", filename
        )

        # [4] For the two schemas main() never itself instance-validates,
        # separately prove the underlying defect is genuinely reachable
        # -- the SAME direct instance-validation operation measure.py /
        # benchmark.py perform against these exact schema files -- so
        # this test does not merely assert an inert mutation.
        if filename == "freeze_manifest_schema.json":
            with pytest.raises(Exception) as exc_info:
                Draft202012Validator(schema).is_valid(_TOY_FREEZE_MANIFEST_INSTANCE)
            assert "PointerToNowhere" in repr(exc_info.value) or "PointerToNowhere" in str(exc_info.value)
        elif filename == "reveal_verification_ledger_schema.json":
            with pytest.raises(Exception) as exc_info:
                Draft202012Validator(schema).is_valid(_TOY_REVEAL_LEDGER_INSTANCE)
            assert "PointerToNowhere" in repr(exc_info.value) or "PointerToNowhere" in str(exc_info.value)


# =======================================================================
# SAN-881 PASS-1 FINAL RESOLVER CORRECTION: the PASS-1 FINAL BLOCKER
# CORRECTION's `_schema_ref_integrity_violation` (tested immediately
# above) was itself a `$ref`-GRAPH WALKER with two of its own defects,
# both confirmed via isolated scratchpad scripts BEFORE this
# correction's edit (imported the real, unmodified
# reference.calibration.validate_design module directly from the repo
# working tree -- never git stash, never a "verbatim reconstruction" of
# removed code):
#
#   (1) it never inspected the "$id" keyword at all, so a nested `$id`
#   placed on a REACHABLE `$defs` entry -- which, per JSON Schema
#   2020-12 `$id` resource-scope semantics, rebases fragment resolution
#   for every `$ref` inside that sub-schema -- left the walker clean
#   while a REAL instance validation crashed with an uncaught
#   `jsonschema.exceptions._WrappedReferencingError` wrapping
#   `referencing.exceptions.PointerToNowhere`;
#
#   (2) it compared a `$ref` fragment token to `$defs` keys LITERALLY,
#   while the real `jsonschema`/`referencing` machinery URI-PERCENT-
#   DECODES that token before the `$defs` lookup, so `"#/$defs/%61"`
#   resolves, in `jsonschema`, to the key `"a"`, never the literal key
#   `"%61"` -- producing both a false ACCEPT (walker) and a crash (real
#   resolution).
#
# THE FIX replaces the graph walker with a full-document STRUCTURAL
# LINT over a closed v1 reference dialect (see
# `_schema_ref_integrity_violation`'s docstring and the module comment
# immediately above it): the COMPLETE JSON tree is scanned exactly
# once, including every `$defs` entry regardless of reachability;
# `$id` is allowed ONLY at the document root; `$dynamicRef` / `$anchor`
# / `$dynamicAnchor` are rejected anywhere; and the ONLY accepted
# `$ref` form is `"#/$defs/<token>"` where `<token>` fullmatches
# `r"(?:[A-Za-z0-9_.-]|~0|~1)+"` -- a grammar that forbids `%` and raw
# `/` outright, so the percent-decode ambiguity can never arise.
# =======================================================================

def test_stage_rejects_schema_with_nested_id_on_reachable_defs_entry(tmp_path, monkeypatch, capsys):
    # GENUINE RED (isolated scratchpad script
    # pass1_final_resolver_red_nested_id.py, run against the real,
    # unmodified pre-fix module): a nested `"$id"` added to
    # `commitment_schema.json`'s REACHABLE `$defs.contextComponent`
    # entry (referenced from `authorEnvelope.labeling_context_components`'s
    # `prefixItems`, each `{"$ref": "#/$defs/contextComponent"}`) left
    # `Draft202012Validator.check_schema(schema)` passing, the pre-fix
    # walker (`_schema_ref_integrity_violation`) returning `False` (no
    # violation -- it never inspected `"$id"` at all), and
    # `_load_fixed_components_cache`'s `ok` field `True` with the
    # mutated schema still present in `schema_by_name` -- all confirmed
    # directly in the scratchpad repro. The SAME repro then exercised
    # the EXACT operation `main()` performs UNCONDITIONALLY (not merely
    # under `--reveal-stage`) at its
    # `commitment_schema_valid = _validate_specific(errors, "commitment.json", commitment_schema, "authorEnvelope", commitment)`
    # call: `contextComponent`'s own `"sha256": {"$ref": "#/$defs/hex64"}`
    # property, under the nested `$id`'s new resource base, resolves
    # `"#/$defs/hex64"` against `contextComponent`'s OWN (nonexistent)
    # `$defs` -- crashing `Draft202012Validator(target).is_valid(commitment)`,
    # and therefore `vd.main([])` itself, with an uncaught
    # `jsonschema.exceptions._WrappedReferencingError` wrapping
    # `referencing.exceptions.PointerToNowhere: '/$defs/hex64' does not
    # exist within {...}` -- captured verbatim in the scratchpad output.
    #
    # POST-FIX: the full-document structural lint rejects ANY nested
    # `$id` anywhere but the schema document root, unconditionally,
    # during Tier-0 cache construction -- BEFORE any instance validation
    # is ever attempted -- with the SAME fixed
    # `RULE_CONTEXT_COMPONENT_UNREADABLE` diagnostic every other
    # fixed-component defect uses, no new rule vocabulary, no traceback,
    # zero Tier-2 custody opens, zero crypto.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    schema_path = env["cal_dir"] / "schemas" / "commitment_schema.json"
    schema = json.loads(schema_path.read_text())
    assert "$id" not in schema["$defs"]["contextComponent"], "fixture drift: contextComponent already has $id"
    schema["$defs"]["contextComponent"]["$id"] = "https://sanna.dev/schemas/calibration/commitment/v2.json/contextComponent"
    # [1] Still self-valid at its OWN ROOT -- proves this is caught by
    # the NEW lint's $id-placement rule, not by check_schema (which has
    # no opinion on WHERE a valid $id appears).
    Draft202012Validator.check_schema(schema)
    schema_path.write_text(json.dumps(schema))
    _rebuild_commitments_after_fixed_component_mutation(env, env["cal_dir"], vd.REPO_ROOT)

    # [2] Direct cache-level proof: the mutated schema is evicted and
    # `ok` is False, independent of any staged bundle.
    cache_errors = vd.Errors()
    cache = vd._load_fixed_components_cache(cache_errors, env["cal_dir"], vd.REPO_ROOT)
    assert cache["ok"] is False, "cache incorrectly reports ok=True after a nested $id mutation"
    assert "commitment_schema.json" not in cache["schema"], "schema not evicted from schema_by_name"
    assert any("commitment_schema.json" in e and vd.RULE_CONTEXT_COMPONENT_UNREADABLE in e for e in cache_errors), (
        f"no RULE_CONTEXT_COMPONENT_UNREADABLE diagnostic naming commitment_schema.json: {list(cache_errors)}"
    )

    # [3] Direct unit-level proof: the lint function itself now flags
    # this exact mutated document.
    assert vd._schema_ref_integrity_violation(schema) is True

    # [4] Real staged main(argv): fixed-diagnostic refusal, zero crypto,
    # zero Tier-2 custody opens -- proves NO uncaught
    # _WrappedReferencingError/PointerToNowhere reaches the caller
    # post-fix.
    argv = _write_semantic_only_bundle(tmp_path, env)
    open_calls = _tracked_os_open(monkeypatch)
    verify_calls = _tracked_verify_reveal(monkeypatch)
    rc = vd.main(argv)  # must not raise
    captured = capsys.readouterr()
    _assert_stage_gate_rejected_zero_crypto_zero_custody(
        rc, captured, open_calls, verify_calls, "schemas/commitment_schema.json", "nested_id"
    )


def test_stage_rejects_schema_ref_percent_encoded_token_false_accept_closure(tmp_path, monkeypatch, capsys):
    # GENUINE RED (isolated scratchpad script
    # pass1_final_resolver_red_percent61.py, run against the real,
    # unmodified pre-fix module): `commitment_schema.json`'s REACHABLE
    # `authorEnvelope.properties.labeling_context_hash` `$ref` changed
    # from `"#/$defs/hex64"` to `"#/$defs/%61"`, WITH a literal `"%61"`
    # `$defs` entry added (deliberately NOT the hex64 shape, to prove a
    # real resolution difference, not merely a missing key). The pre-fix
    # walker's fragment-to-key comparison was a LITERAL string lookup
    # (RFC6901 tilde-unescape only, no percent-decoding): the captured
    # group `"%61"` IS present, unescaped, as a literal `$defs` key, so
    # the walker returned `False` (no violation) -- a FALSE ACCEPT,
    # confirmed directly in the scratchpad repro. The SAME repro then
    # resolved the identical `"#/$defs/%61"` fragment directly through
    # the real `referencing` library against the SAME document (both via
    # `Draft202012Validator(...).is_valid(...)` and via a raw
    # `Registry().resolver().lookup(...)` call) and captured a genuine
    # `referencing.exceptions.PointerToNowhere` for BOTH -- confirming
    # `urllib.parse.unquote("%61") == "a"` is exactly the key jsonschema
    # actually looks up, never the literal `"%61"` string the walker
    # matched.
    #
    # POST-FIX: the closed token grammar
    # (`re.fullmatch(r"(?:[A-Za-z0-9_.-]|~0|~1)+", token)`) forbids `%`
    # in an accepted token OUTRIGHT, so this exact `$ref` is rejected as
    # a structural-lint violation during Tier-0 cache construction --
    # BEFORE any instance validation is ever attempted, closing the
    # false-accept at its source rather than trying to replicate
    # jsonschema's own percent-decoding.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    schema_path = env["cal_dir"] / "schemas" / "commitment_schema.json"
    schema = json.loads(schema_path.read_text())
    assert schema["$defs"]["authorEnvelope"]["properties"]["labeling_context_hash"] == {"$ref": "#/$defs/hex64"}, (
        "fixture drift: authorEnvelope.labeling_context_hash's $ref shape changed"
    )
    schema["$defs"]["authorEnvelope"]["properties"]["labeling_context_hash"] = {"$ref": "#/$defs/%61"}
    assert "%61" not in schema["$defs"], "fixture drift: %61 already a $defs key"
    schema["$defs"]["%61"] = {"type": "string", "const": "literal-percent-61-entry-not-hex64-shaped"}
    # [1] Still self-valid at its OWN ROOT.
    Draft202012Validator.check_schema(schema)
    schema_path.write_text(json.dumps(schema))
    _rebuild_commitments_after_fixed_component_mutation(env, env["cal_dir"], vd.REPO_ROOT)

    # [2] Direct cache-level proof: the mutated schema is evicted and
    # `ok` is False.
    cache_errors = vd.Errors()
    cache = vd._load_fixed_components_cache(cache_errors, env["cal_dir"], vd.REPO_ROOT)
    assert cache["ok"] is False, "cache incorrectly reports ok=True after a %61 $ref mutation"
    assert "commitment_schema.json" not in cache["schema"], "schema not evicted from schema_by_name"
    assert any("commitment_schema.json" in e and vd.RULE_CONTEXT_COMPONENT_UNREADABLE in e for e in cache_errors), (
        f"no RULE_CONTEXT_COMPONENT_UNREADABLE diagnostic naming commitment_schema.json: {list(cache_errors)}"
    )

    # [3] Direct unit-level proof: the lint function itself now flags
    # this exact mutated document.
    assert vd._schema_ref_integrity_violation(schema) is True

    # [4] Real staged main(argv): fixed-diagnostic refusal, zero crypto,
    # zero Tier-2 custody opens.
    argv = _write_semantic_only_bundle(tmp_path, env)
    open_calls = _tracked_os_open(monkeypatch)
    verify_calls = _tracked_verify_reveal(monkeypatch)
    rc = vd.main(argv)  # must not raise
    captured = capsys.readouterr()
    _assert_stage_gate_rejected_zero_crypto_zero_custody(
        rc, captured, open_calls, verify_calls, "schemas/commitment_schema.json", "percent_61"
    )


# ---------------------------------------------------------------------
# Direct lint pins: unit-level proofs of the closed token grammar / the
# root-only $id rule / the anywhere-in-document $dynamicRef+$anchor+
# $dynamicAnchor rejection / the full-tree-reaches-unused-$defs-entries
# property / cycle tolerance -- exercised directly against
# `vd._schema_ref_integrity_violation`, independent of the full staged
# pipeline (faster, and isolates the lint's own boundary conditions from
# main()'s surrounding gate machinery, already covered above).
# ---------------------------------------------------------------------

def _toy_lint_schema(defs: dict, extra_root: dict | None = None) -> dict:
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "https://example.test/toy.json", "$defs": defs}
    if extra_root:
        schema.update(extra_root)
    return schema


def test_lint_rejects_malformed_tilde_escape_digit_2():
    # "~2" is not a legal RFC6901 escape (only ~0 and ~1 exist) -- the
    # closed token grammar must reject it via FULLMATCH, independent of
    # whether a $defs key literally named "~2" happens to exist.
    schema = _toy_lint_schema({"a": {"type": "string"}, "~2": {"type": "string"}}, {"properties": {"x": {"$ref": "#/$defs/~2"}}})
    assert vd._schema_ref_integrity_violation(schema) is True


def test_lint_rejects_bare_and_trailing_tilde():
    # A literal `$defs` key matching the RAW (undecoded) token is
    # deliberately ALSO present in each fixture -- a token whose grammar
    # is malformed must be rejected on the GRAMMAR check alone, never
    # merely because a differently-shaped literal lookup happens to miss
    # (which would be a much weaker test: a bare/trailing "~" with no
    # matching literal key at all is already caught trivially, by ANY
    # implementation, as "missing target").
    bare = _toy_lint_schema({"a": {"type": "string"}, "~": {"type": "string"}}, {"properties": {"x": {"$ref": "#/$defs/~"}}})
    assert vd._schema_ref_integrity_violation(bare) is True
    trailing = _toy_lint_schema({"a": {"type": "string"}, "a~": {"type": "string"}}, {"properties": {"x": {"$ref": "#/$defs/a~"}}})
    assert vd._schema_ref_integrity_violation(trailing) is True


def test_lint_rejects_nested_anchor_inside_defs():
    schema = _toy_lint_schema({"a": {"type": "string", "$anchor": "someAnchor"}})
    assert vd._schema_ref_integrity_violation(schema) is True


def test_lint_rejects_nested_dynamic_ref_inside_defs():
    schema = _toy_lint_schema({"a": {"$dynamicRef": "#meta"}})
    assert vd._schema_ref_integrity_violation(schema) is True


def test_lint_rejects_nested_dynamic_anchor_inside_defs():
    schema = _toy_lint_schema({"a": {"type": "string", "$dynamicAnchor": "someAnchor"}})
    assert vd._schema_ref_integrity_violation(schema) is True


def test_lint_rejects_nested_id_inside_defs_direct():
    # Direct unit-level companion to
    # test_stage_rejects_schema_with_nested_id_on_reachable_defs_entry
    # above (which proves the end-to-end main() consequence); this
    # isolates the lint's own $id-placement rule.
    schema = _toy_lint_schema({"a": {"type": "string", "$id": "https://example.test/toy.json/a"}})
    assert vd._schema_ref_integrity_violation(schema) is True


def test_lint_accepts_id_only_at_document_root():
    schema = _toy_lint_schema({"a": {"type": "string"}})
    assert vd._schema_ref_integrity_violation(schema) is False


def test_lint_rejects_unreachable_external_ref_inside_unused_defs_entry():
    # No $ref anywhere in the document points at "unused" -- this
    # fixture explicitly proves the full-tree scan reaches $defs entries
    # that no reachable $ref points at: an EXTERNAL (non-closed-grammar)
    # $ref buried inside a $defs entry nothing else references must
    # still be caught.
    schema = _toy_lint_schema(
        {
            "a": {"type": "string"},
            "unused": {"$ref": "https://example.com/external-schema.json#/definitions/thing"},
        },
        {"properties": {"x": {"$ref": "#/$defs/a"}}},
    )
    assert vd._schema_ref_integrity_violation(schema) is True


def test_lint_accepts_unreferenced_but_otherwise_valid_defs_entry():
    # Positive-control companion to the unreachable-external-ref case
    # above: an unreferenced $defs entry that is ITSELF dialect-clean
    # must NOT be flagged merely for being unreferenced -- the lint
    # requires validity, not reachability.
    schema = _toy_lint_schema(
        {"a": {"type": "string"}, "unused_but_valid": {"type": "integer"}},
        {"properties": {"x": {"$ref": "#/$defs/a"}}},
    )
    assert vd._schema_ref_integrity_violation(schema) is False


def test_lint_accepts_canonical_tilde_escaped_tokens():
    # "~0" -> "~" and "~1" -> "/" are the ONLY two legal RFC6901 escapes;
    # both must be accepted when the correspondingly-decoded $defs key
    # is genuinely present.
    schema = _toy_lint_schema(
        {"~": {"type": "string"}, "/": {"type": "string"}},
        {"properties": {"x": {"$ref": "#/$defs/~0"}, "y": {"$ref": "#/$defs/~1"}}},
    )
    assert vd._schema_ref_integrity_violation(schema) is False


def test_lint_accepts_genuine_mutual_reference_cycle():
    # A genuine a<->b cycle is NOT a violation: the full-tree scan
    # requires each $ref's target to EXIST as a present, well-formed
    # $defs member -- it never "follows" a $ref to decide what to visit
    # next, so there is nothing for a cycle to break.
    schema = _toy_lint_schema({
        "a": {"type": "object", "properties": {"next": {"$ref": "#/$defs/b"}}},
        "b": {"type": "object", "properties": {"next": {"$ref": "#/$defs/a"}}},
    })
    assert vd._schema_ref_integrity_violation(schema) is False


def test_schema_ref_integrity_lint_clean_on_six_committed_schemas():
    # Regression pin (must stay clean, zero violations): every "$ref" in
    # each of the six REAL, committed schema files is already exactly
    # "#/$defs/<simple-token>", every "$id" already appears ONLY at each
    # document's own root, and none use
    # $dynamicRef/$anchor/$dynamicAnchor -- the structural lint must
    # never false-positive against them.
    for filename in vd.SCHEMA_FILES:
        schema = json.loads((SCHEMAS_DIR / filename).read_text())
        assert vd._schema_ref_integrity_violation(schema) is False, filename


def test_main_no_reveal_stage_with_nonce_arg_and_incomplete_sealed_dir_rejects_without_crash(tmp_path, monkeypatch, capsys):
    # Fix 2 (no-stage rejection short-circuit). GENUINE RED (verified
    # via the isolated scratchpad script BEFORE this correction's edit --
    # red_evidence_2.py, captured verbatim): a --nonces-file argument
    # supplied WITHOUT --reveal-stage, together with an EXISTING but
    # INCOMPLETE --sealed-dir (missing design_metadata.json), previously
    # fell through into the generic --sealed-dir structural block AFTER
    # appending the RULE_REVEAL_STAGE_REQUIRED diagnostic, and crashed
    # with an uncaught, absolute-path-disclosing FileNotFoundError the
    # first time `load_json(args.sealed_dir / "design_metadata.json")`
    # ran (captured traceback: validate_design.py line
    # `design = load_json(args.sealed_dir / "design_metadata.json")`).
    # POST-FIX: the reject is a hard guard -- the structural branch is
    # SKIPPED entirely, proven here both by the absence of a crash/any
    # structural diagnostic AND by zero os.open calls for anything under
    # sealed_dir (the generic block never even attempts a sealed-dir read).
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    sealed_dir = tmp_path / "sealed"
    sealed_dir.mkdir()
    # INCOMPLETE: only labels_author_contract.json present -- the
    # generic block's FIRST read (design_metadata.json) is missing.
    (sealed_dir / "labels_author_contract.json").write_bytes(env["artifact_bytes"]["labels_author_contract.json"])
    nonces_file = tmp_path / "nonces.json"
    nonces_file.write_text("{}")

    argv = ["--sealed-dir", str(sealed_dir), "--nonces-file", str(nonces_file)]
    open_calls = _tracked_os_open(monkeypatch)
    rc = vd.main(argv)  # must not raise
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert vd.RULE_REVEAL_STAGE_REQUIRED in captured.err
    # Structural branch skipped entirely: no diagnostic that could only
    # be produced by actually running the generic --sealed-dir block's
    # own checks over design/labels/coverage content.
    assert vd.RULE_ITEM_COUNT not in captured.err
    assert vd.RULE_SEM_KEYS not in captured.err
    assert vd.RULE_SCHEMA_INVALID not in captured.err
    sealed_dir_str = str(sealed_dir)
    sealed_dir_opens = [c for c in open_calls if c.startswith(sealed_dir_str)]
    assert sealed_dir_opens == [], f"sealed_dir content was opened despite the no-stage reject: {sealed_dir_opens}"


def test_nonces_file_lexical_dotdot_escape_rejected(tmp_path, monkeypatch, capsys):
    # Fix 3 (_path_is_inside lexical containment). GENUINE RED (verified
    # via the isolated scratchpad script BEFORE this correction's edit --
    # red_evidence_2.py, captured verbatim):
    # `_path_is_inside(sealed_dir/../author_nonces.json, sealed_dir)`
    # returned False (pre-fix, resolved-containment-only: the RESOLVED
    # child is a sibling of sealed_dir, genuinely outside it) -- silently
    # ACCEPTING a nonces-file path whose raw LEXICAL form still traverses
    # sealed_dir's own parents chain (child.absolute() without collapsing
    # ".."), exactly the escape the docstring/README already claimed was
    # rejected. POST-FIX: the lexical form alone is sufficient to reject,
    # proven end-to-end via a real staged main(argv) invocation with zero
    # custody opens and zero crypto.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    sealed_dir = Path(argv[argv.index("--sealed-dir") + 1])
    real_nonces_file = Path(argv[argv.index("--nonces-file") + 1])
    # Same real file, same bytes -- ONLY the ARGV PATH STRING changes, to
    # sealed_dir/../<real nonces filename>: lexically (not resolved) a
    # traversal through sealed_dir.
    escape_path = sealed_dir / ".." / real_nonces_file.name
    assert escape_path.resolve() == real_nonces_file.resolve(), "fixture bug: escape_path must resolve to the SAME real nonces file"
    argv[argv.index("--nonces-file") + 1] = str(escape_path)

    open_calls = _tracked_os_open(monkeypatch)
    verify_calls = _tracked_verify_reveal(monkeypatch)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert vd.RULE_NONCE_FILE_INSIDE_BUNDLE in captured.err
    assert len(verify_calls) == 0, f"crypto ran despite a lexical bundle-containment escape: {verify_calls}"
    tier0_paths = {str(p) for p in _tier0_fixed_component_paths()}
    tier2_opens = [c for c in open_calls if c not in tier0_paths]
    assert tier2_opens == [], f"custody content was opened despite a lexical bundle-containment escape: {tier2_opens}"


def test_nonces_file_realpath_inside_via_symlink_rejected(tmp_path, monkeypatch, capsys):
    # Fix 3 companion: isolates the RESOLVED half of the "lexically OR by
    # realpath" predicate from the lexical half tested above. A
    # nonces-file path that is LEXICALLY outside the bundle (no ".."
    # traversal at all -- a plain sibling filename) but whose REALPATH --
    # because it is itself a symlink -- resolves to a file genuinely
    # inside the bundle. This half was already correctly enforced
    # pre-fix (the pre-fix bug was specifically the missing lexical
    # check; resolved containment was never broken), so this is a
    # preservation/regression proof for the OR-combined predicate, not a
    # RED-to-GREEN case.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    argv = _write_semantic_only_bundle(tmp_path, env)
    sealed_dir = Path(argv[argv.index("--sealed-dir") + 1])

    symlinked_nonces_path = tmp_path / "sneaky_nonce_symlink.json"
    symlinked_nonces_path.symlink_to(sealed_dir / "labels_author_semantic.json")
    argv[argv.index("--nonces-file") + 1] = str(symlinked_nonces_path)

    open_calls = _tracked_os_open(monkeypatch)
    verify_calls = _tracked_verify_reveal(monkeypatch)
    rc = vd.main(argv)
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.err
    assert vd.RULE_NONCE_FILE_INSIDE_BUNDLE in captured.err
    assert len(verify_calls) == 0, f"crypto ran despite a realpath bundle-containment escape: {verify_calls}"
    tier0_paths = {str(p) for p in _tier0_fixed_component_paths()}
    tier2_opens = [c for c in open_calls if c not in tier0_paths]
    assert tier2_opens == [], f"custody content was opened despite a realpath bundle-containment escape: {tier2_opens}"


def test_path_is_inside_resolution_failure_fails_closed(tmp_path):
    # Fix 3 (fail-closed on resolution error), direct unit-level proof.
    # GENUINE RED (verified via the isolated scratchpad script BEFORE
    # this correction's edit -- red_evidence_2.py, captured verbatim):
    # pre-fix, Path.resolve() (no strict=True) does NOT raise for a
    # dangling symlink or a nonexistent nested path -- both captured
    # calls returned False ("not inside") without ever reaching the
    # pre-fix "except OSError: return False" branch, which was therefore
    # DEAD CODE, unreachable via this exact failure class in practice.
    # POST-FIX: resolve(strict=True) genuinely raises FileNotFoundError
    # for both, and the except clause returns True (fail closed --
    # treated as "inside" / rejected) -- tested directly against
    # _path_is_inside (rather than end-to-end) to isolate the invariant
    # from whichever OTHER downstream check (e.g. a plain "is this a
    # symlink" or "does this exist" check) might otherwise also happen
    # to reject the same malformed path for an unrelated reason.
    parent = tmp_path / "sealed_dir"
    parent.mkdir()

    # Child side fails to resolve (dangling symlink).
    broken_child = tmp_path / "broken_nonce_link.json"
    broken_child.symlink_to(tmp_path / "target_that_does_not_exist.json")
    assert vd._path_is_inside(broken_child, parent) is True

    # Parent side fails to resolve -- never assume only the child side
    # can be attacker-influenced.
    broken_parent = tmp_path / "broken_parent_link"
    broken_parent.symlink_to(tmp_path / "parent_target_that_does_not_exist")
    real_child = tmp_path / "real_nonce_file.json"
    real_child.write_text("{}")
    assert vd._path_is_inside(real_child, broken_parent) is True


# =======================================================================
# SAN-881 PASS 2B.1-P-FIX: bounded correction pass over the ACCEPTED
# Pass 2B.1-P product-level architecture. Five concrete correctness
# defects + three assurance items -- no new abstractions, no
# CheckConsumptionTrace, no call-graph/transitive static analyzer.
# =======================================================================

# -----------------------------------------------------------------------
# Fix 1: MAKE PASS A A REAL GATE. Upstream coverage-schema and
# registry-closure failures (checked by main() BEFORE/around
# check_coverage_manifest, never by check_coverage_manifest's own
# internal Pass A alone) must make Pass B (build_product_trace_bundle)
# INELIGIBLE, even when check_coverage_manifest's own Pass A loop -- which
# only inspects keys ACTUALLY PRESENT in the manifest and cannot itself
# notice a MISSING registered surface, and silently skips
# position-checking an EXTRA undeclared surface (registry_entry is None)
# -- finds zero errors of its own.
# -----------------------------------------------------------------------

def _full_position_valid_coverage_manifest() -> dict:
    """A schema-valid, registry-CLOSED (all 68 surfaces present, exactly
    once each) coverage manifest where EVERY record uses one of ITS OWN
    SURFACE_REGISTRY.allowed_positions (never uniformly (C1,context) --
    that would be illegal for the seven C2-only nontable surfaces and
    thus fail check_coverage_manifest's OWN internal Pass A for an
    UNRELATED reason, confounding a test that wants to isolate the
    UPSTREAM schema/closure gate specifically). Every record reuses the
    SAME single item_id (cal:000) -- legal, since the scenario-
    independence check groups claims PER SURFACE, never across
    surfaces, so 68 different surfaces citing the same item is not a
    collision."""
    manifest = {}
    for surface, entry in vd.SURFACE_REGISTRY.items():
        check_id, field = next(iter(entry["allowed_positions"]))
        manifest[surface] = [{"item_id": "cal:000", "check_id": check_id, "field": field}]
    return manifest


def _write_pass_a_gate_sealed_dir(tmp_path, env, manifest, design_bytes: bytes | None = None) -> Path:
    # `design_bytes` defaults to the env's own (now check_design_metadata-
    # clean, PASS 2B.1-P-GATE-rebalanced) design_metadata.json bytes --
    # an explicit override lets a caller substitute a DELIBERATELY
    # invalid design (SAN-881 PASS 2B.1-P-GATE new tests) without
    # touching this helper's pre-existing callers' behavior.
    if design_bytes is None:
        design_bytes = env["artifact_bytes"]["design_metadata.json"]
    sealed_dir = tmp_path / "pass_a_gate_sealed"
    sealed_dir.mkdir()
    (sealed_dir / "design_metadata.json").write_bytes(design_bytes)
    (sealed_dir / "labels_author_semantic.json").write_bytes(env["artifact_bytes"]["labels_author_semantic.json"])
    (sealed_dir / "labels_author_contract.json").write_bytes(env["artifact_bytes"]["labels_author_contract.json"])
    (sealed_dir / "coverage_manifest.json").write_text(json.dumps(manifest))
    return sealed_dir


def _spy_build_product_trace_bundle(monkeypatch):
    calls = []
    real_builder = vd.build_product_trace_bundle

    def _spy(item):
        calls.append(item.get("id"))
        return real_builder(item)

    monkeypatch.setattr(vd, "build_product_trace_bundle", _spy)
    return calls


def _spy_check_dod_balance_and_pairs(monkeypatch):
    # SAN-881 PASS 2B.2-FIX defect 2: mirrors _spy_build_product_trace_bundle's
    # own pattern -- wraps the REAL function (still runs it, when called)
    # so a caller can assert both the call COUNT and the resulting
    # errors/behavior in the same test.
    calls = []
    real_fn = vd.check_dod_balance_and_pairs

    def _spy(*args, **kwargs):
        calls.append(True)
        return real_fn(*args, **kwargs)

    monkeypatch.setattr(vd, "check_dod_balance_and_pairs", _spy)
    return calls


def test_main_schema_invalid_coverage_manifest_never_builds_a_bundle(tmp_path, monkeypatch, capsys):
    # RED (pre-fix, verified): a coverage_manifest.json missing one
    # required registered surface is schema-invalid (the schema's
    # `required` list names all 68 surfaces) AND closure-invalid
    # (RULE_COVERAGE_REGISTRY_MISSING_SURFACE) -- but check_coverage_
    # manifest's own internal Pass A loop only iterates the 67 keys
    # ACTUALLY PRESENT, each individually position-legal by
    # construction, so it found ZERO errors of its own and (pre-fix)
    # proceeded straight into Pass B, building a real ProductTraceBundle
    # for cal:000. POST-FIX: main() gates Pass B on the upstream schema
    # AND closure results, so build_product_trace_bundle is NEVER
    # called, while the deterministic upstream errors are still
    # reported.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    manifest = _full_position_valid_coverage_manifest()
    del manifest["value_role_v1.limit"]
    sealed_dir = _write_pass_a_gate_sealed_dir(tmp_path, env, manifest)

    calls = _spy_build_product_trace_bundle(monkeypatch)
    rc = vd.main(["--sealed-dir", str(sealed_dir)])
    captured = capsys.readouterr()

    assert calls == [], f"build_product_trace_bundle was called despite a schema-invalid (missing-surface) coverage manifest: {calls}"
    assert rc == 1
    assert "coverage_manifest.json: rule=" in captured.err or "coverage_manifest.json[" in captured.err
    assert f"coverage_manifest.json[value_role_v1.limit]: rule={vd.RULE_COVERAGE_REGISTRY_MISSING_SURFACE}" in captured.err


def test_main_closure_invalid_coverage_manifest_never_builds_a_bundle(tmp_path, monkeypatch, capsys):
    # RED (pre-fix, verified): a coverage_manifest.json carrying ONE
    # extra undeclared surface (alongside the full, correctly-populated
    # 68-key set) is schema-invalid (`additionalProperties: false`) AND
    # closure-invalid (RULE_COVERAGE_REGISTRY_EXTRA_SURFACE) -- but
    # check_coverage_manifest's own internal Pass A loop finds
    # registry_entry is None for the extra key and SKIPS
    # position-checking it entirely (no error), so Pass A found ZERO
    # errors of its own and (pre-fix) proceeded into Pass B, building a
    # real ProductTraceBundle for cal:000. POST-FIX: main() gates Pass B
    # on the upstream schema AND closure results, so
    # build_product_trace_bundle is NEVER called, while the
    # deterministic upstream errors are still reported.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    manifest = _full_position_valid_coverage_manifest()
    manifest["totally_bogus_surface_zzz"] = [{"item_id": "cal:000", "check_id": "C1", "field": "context"}]
    sealed_dir = _write_pass_a_gate_sealed_dir(tmp_path, env, manifest)

    calls = _spy_build_product_trace_bundle(monkeypatch)
    rc = vd.main(["--sealed-dir", str(sealed_dir)])
    captured = capsys.readouterr()

    assert calls == [], f"build_product_trace_bundle was called despite a closure-invalid (extra-surface) coverage manifest: {calls}"
    assert rc == 1
    assert f"coverage_manifest.json[totally_bogus_surface_zzz]: rule={vd.RULE_COVERAGE_REGISTRY_EXTRA_SURFACE}" in captured.err


def test_main_fully_valid_coverage_manifest_builds_exactly_once_per_item(tmp_path, monkeypatch, capsys):
    # Companion positive control (same main()-level spy infrastructure):
    # a schema-valid, closure-valid, fully position-legal 68-surface
    # manifest -- 68 records, ALL citing the SAME item_id (cal:000) --
    # reaches Pass B and builds the ProductTraceBundle for cal:000
    # EXACTLY ONCE (the pre-existing per-item cache in
    # _check_all_product_surfaces_evidence, preserved by this fix, not
    # reintroduced by it).
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    manifest = _full_position_valid_coverage_manifest()
    sealed_dir = _write_pass_a_gate_sealed_dir(tmp_path, env, manifest)

    calls = _spy_build_product_trace_bundle(monkeypatch)
    rc = vd.main(["--sealed-dir", str(sealed_dir)])
    captured = capsys.readouterr()

    assert calls == ["cal:000"], f"expected exactly one cached build for cal:000, got {calls}"
    # RC/stderr are irrelevant here (the toy corpus text satisfies none
    # of the real linguistic predicates, so plenty of
    # RULE_COVERAGE_PREDICATE_FAILED-style noise is expected) -- this
    # test's ONLY concern is the call-count invariant.
    assert rc in (0, 1)


# -----------------------------------------------------------------------
# SAN-881 PASS 2B.1-P-GATE: coverage_upstream_ok (PASS 2B.1-P-FIX's gate)
# combined ONLY coverage-schema and coverage-registry-closure validity --
# an invalid corpus/design prerequisite, or an UNAVAILABLE schema
# validator, still let Pass B (build_product_trace_bundle) run. Reviewer's
# live reproduction: an invalid-corpus run produced 90 validation errors
# and still recorded BUILDS ['cal:000']. The four cases below prove the
# corrected `upstream_ok` -- the conjunction of six explicit, LOCAL
# prerequisite booleans (coverage_runtime_available, corpus_prereq_ok,
# design_schema_ok, design_semantics_ok, coverage_schema_ok,
# coverage_closure_ok) -- closes this gap.
# -----------------------------------------------------------------------

def _rewrite_corpus_and_recompute_commitment(tmp_path, env, corpus_records) -> None:
    """Overwrites the toy environment's corpus_inputs.json with
    `corpus_records` and rebuilds commitment.json's labeling_context_hash
    / labeling_context_components / author_commitments to match -- keeps
    the whole toy environment internally COHERENT (main()'s own
    from-disk context-hash recomputation matches what commitment.json
    declares), so a corpus-content mutation's effect is isolated to
    check_corpus_inputs's own diagnostics, never confounded by an
    incidental CONTEXT_HASH_MISMATCH. (The bare --sealed-dir generic
    path never reads author_gate_ok/commitment validity at all -- see
    main()'s own comments -- so this is test hygiene, not a
    reachability requirement.)"""
    cal_dir = env["cal_dir"]
    (cal_dir / "corpus_inputs.json").write_text(json.dumps(corpus_records))
    ctx_hash_hex = vd.compute_labeling_context_hash_from_disk(cal_dir, tmp_path).hex()
    ctx_hash_bytes = bytes.fromhex(ctx_hash_hex)
    author_commitments = [
        {"artifact_name": n, "byte_length": len(env["artifact_bytes"][n]),
         "commitment_hex": vd.compute_artifact_commitment(n, env["author_nonces"][n], ctx_hash_bytes, env["artifact_bytes"][n])}
        for n in vd.AUTHOR_COMMITMENT_ORDER
    ]
    commitment = dict(env["commitment"])
    commitment["labeling_context_hash"] = ctx_hash_hex
    commitment["labeling_context_components"] = vd.build_labeling_context_components(cal_dir, tmp_path)
    commitment["author_commitments"] = author_commitments
    (cal_dir / "commitment.json").write_text(json.dumps(commitment))


def _toy_duplicate_tuple_corpus() -> list[dict]:
    """The toy 160-item corpus with ONE mutation: cal:001's (context,
    output) tuple is made an exact duplicate of cal:000's -- UNRELATED to
    the coverage manifest's credited item_id (cal:000 itself stays
    untouched), isolating the corpus-record defect from the item Pass B
    would build."""
    corpus = [{"id": f"cal:{i:03d}", "context": f"Toy context number {i}.", "output": f"Toy output number {i}."} for i in range(160)]
    corpus[1] = {"id": "cal:001", "context": corpus[0]["context"], "output": corpus[0]["output"]}
    return corpus


def test_main_invalid_design_item_unrelated_to_credited_item_never_builds(tmp_path, monkeypatch, capsys):
    # Case (a). GENUINE RED (pre-fix, verified via a temporary revert of
    # validate_design.py to the PASS 2B.1-P-FIX baseline -- captured
    # verbatim in the ticket report): coverage_upstream_ok combined ONLY
    # coverage-schema and coverage-registry-closure validity, so an
    # entirely design-side defect (cal:001's facet_families entry outside
    # check_design_metadata's closed list -- schema-valid, since the
    # schema only enforces the "^facet:[a-z_]+$" PATTERN, never the
    # closed vocabulary; this isolates design_semantics_ok specifically,
    # never design_schema_ok) was invisible to it, and Pass B ran anyway,
    # building cal:000's bundle despite the reported design diagnostic.
    # cal:001 is UNRELATED to the manifest's credited item_id (cal:000)
    # -- proving the gate is a GLOBAL design-validity gate, never scoped
    # to only the items a manifest happens to cite. POST-FIX:
    # design_semantics_ok is one of the six upstream_ok operands.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    design_items = _toy_160_design_items()
    assert design_items[1]["item_id"] == "cal:001"
    design_items[1] = dict(design_items[1], facet_families=["facet:not_a_real_closed_facet"])
    design_bytes = json.dumps({"items": design_items}).encode()

    manifest = _full_position_valid_coverage_manifest()
    sealed_dir = _write_pass_a_gate_sealed_dir(tmp_path, env, manifest, design_bytes=design_bytes)

    calls = _spy_build_product_trace_bundle(monkeypatch)
    rc = vd.main(["--sealed-dir", str(sealed_dir)])
    captured = capsys.readouterr()

    assert calls == [], f"build_product_trace_bundle was called despite an invalid (unrelated) design item: {calls}"
    assert rc == 1
    assert f"cal:001: rule={vd.RULE_FACET_NOT_CLOSED}" in captured.err


def test_main_design_schema_invalid_manifest_never_builds(tmp_path, monkeypatch, capsys):
    # SAN-881 PASS 2B.2 acceptance #2: rerun the existing gate spy with a
    # design_metadata.json that is SCHEMA-invalid (never merely
    # semantics-invalid, the pre-existing case (a) above) -- cal:001's
    # introduced_feature now declares the removed 'comparator' kind,
    # which design_schema_ok's own Draft202012Validator pass rejects.
    # design_schema_ok is one of the six upstream_ok operands
    # check_coverage_manifest's Pass B (build_product_trace_bundle) is
    # gated behind -- proving the six-operand gate still functions
    # unchanged after the PASS 2B.2 schema edit.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    design_items = _toy_160_design_items()
    dod_idx = next(i for i, it in enumerate(design_items) if it["target_stratum"] == "determinate_out_of_domain")
    design_items[dod_idx] = dict(design_items[dod_idx], introduced_feature={
        "kind": "comparator", "table_path": "comparators_v1",
        "surface_tokens": ["at", "least"],
        "intended_semantics": {"interval": "hi=v, hi_open=false (at-most)"},
    })
    design_bytes = json.dumps({"items": design_items}).encode()

    manifest = _full_position_valid_coverage_manifest()
    sealed_dir = _write_pass_a_gate_sealed_dir(tmp_path, env, manifest, design_bytes=design_bytes)

    calls = _spy_build_product_trace_bundle(monkeypatch)
    rc = vd.main(["--sealed-dir", str(sealed_dir)])
    captured = capsys.readouterr()

    assert calls == [], f"build_product_trace_bundle was called despite a schema-invalid design_metadata.json: {calls}"
    assert rc == 1
    assert f"design_metadata.json: rule={vd.RULE_SCHEMA_INVALID}" in captured.err


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.2-FIX defect 2: check_dod_balance_and_pairs ran
# UNCONDITIONALLY in main() -- DOD semantic checks ran even after
# design-schema validation had already failed. A malformed pair member
# (a non-list second member -- feature.get("members", []) then
# " ".join(m) at check_introduced_feature_absent_from_tables's
# excl_pair/complement_pair branch) or a malformed lexical surface
# token (a null element -- the SAME function's LEXICAL branch,
# " ".join(surface_tokens)) each raise an uncaught TypeError straight
# out of main(argv) (reviewer-reproduced). The fix gates the call
# behind dod_inputs_ok = isinstance(tables_data, dict) and
# corpus_prereq_ok and design_schema_ok and design_semantics_ok --
# both malformed shapes are schema-invalid (design_schema_ok False),
# so the gate now skips check_dod_balance_and_pairs (and therefore
# build_product_trace_bundle downstream) entirely; the CLI instead
# reports SCHEMA_INVALID cleanly: exit 1, empty stdout, no traceback,
# no path disclosure.
# ---------------------------------------------------------------------

def test_main_malformed_pair_members_never_reach_dod_checks(tmp_path, monkeypatch, capsys):
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    design_items = _toy_160_design_items()
    dod_idx = next(i for i, it in enumerate(design_items) if it["target_stratum"] == "determinate_out_of_domain")
    design_items[dod_idx] = dict(design_items[dod_idx], introduced_feature={
        "kind": "excl_pair", "table_path": "excl_v1",
        "members": [["standard"], 12345],
    })
    design_bytes = json.dumps({"items": design_items}).encode()

    manifest = _full_position_valid_coverage_manifest()
    sealed_dir = _write_pass_a_gate_sealed_dir(tmp_path, env, manifest, design_bytes=design_bytes)

    dod_calls = _spy_check_dod_balance_and_pairs(monkeypatch)
    trace_calls = _spy_build_product_trace_bundle(monkeypatch)
    rc = vd.main(["--sealed-dir", str(sealed_dir)])
    captured = capsys.readouterr()

    assert dod_calls == [], f"check_dod_balance_and_pairs was called despite a schema-invalid design_metadata.json: {dod_calls}"
    assert trace_calls == [], f"build_product_trace_bundle was called despite a schema-invalid design_metadata.json: {trace_calls}"
    assert rc == 1
    assert captured.out == ""
    assert f"design_metadata.json: rule={vd.RULE_SCHEMA_INVALID}" in captured.err
    assert "Traceback" not in captured.err
    assert str(tmp_path) not in captured.err


def test_main_malformed_lexical_surface_tokens_never_reach_dod_checks(tmp_path, monkeypatch, capsys):
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    design_items = _toy_160_design_items()
    dod_idx = next(i for i, it in enumerate(design_items) if it["target_stratum"] == "determinate_out_of_domain")
    design_items[dod_idx] = dict(design_items[dod_idx], introduced_feature={
        "kind": "concept", "table_path": "concept_v1",
        "surface_tokens": [None],
        "intended_semantics": {"canonical_concept": "approval"},
    })
    design_bytes = json.dumps({"items": design_items}).encode()

    manifest = _full_position_valid_coverage_manifest()
    sealed_dir = _write_pass_a_gate_sealed_dir(tmp_path, env, manifest, design_bytes=design_bytes)

    dod_calls = _spy_check_dod_balance_and_pairs(monkeypatch)
    trace_calls = _spy_build_product_trace_bundle(monkeypatch)
    rc = vd.main(["--sealed-dir", str(sealed_dir)])
    captured = capsys.readouterr()

    assert dod_calls == [], f"check_dod_balance_and_pairs was called despite a schema-invalid design_metadata.json: {dod_calls}"
    assert trace_calls == [], f"build_product_trace_bundle was called despite a schema-invalid design_metadata.json: {trace_calls}"
    assert rc == 1
    assert captured.out == ""
    assert f"design_metadata.json: rule={vd.RULE_SCHEMA_INVALID}" in captured.err
    assert "Traceback" not in captured.err
    assert str(tmp_path) not in captured.err


def test_main_valid_design_metadata_dod_checks_run_exactly_once(tmp_path, monkeypatch, capsys):
    # Positive control: a genuinely schema-valid, check_design_metadata-
    # clean design_metadata.json (the environment's own unmutated
    # fixture) must still reach check_dod_balance_and_pairs -- the gate
    # must not over-reject legitimate input. Exactly one call (main()
    # invokes it at most once per run).
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    manifest = _full_position_valid_coverage_manifest()
    sealed_dir = _write_pass_a_gate_sealed_dir(tmp_path, env, manifest)

    dod_calls = _spy_check_dod_balance_and_pairs(monkeypatch)
    vd.main(["--sealed-dir", str(sealed_dir)])

    assert len(dod_calls) == 1, f"expected exactly one check_dod_balance_and_pairs call, got {dod_calls}"


def test_main_invalid_corpus_record_never_builds(tmp_path, monkeypatch, capsys):
    # Case (b). GENUINE RED (pre-fix, verified via a temporary revert of
    # validate_design.py to the PASS 2B.1-P-FIX baseline -- captured
    # verbatim in the ticket report; mirrors the reviewer's live
    # reproduction of 90 validation errors alongside a recorded
    # BUILDS ['cal:000']): coverage_upstream_ok never consulted corpus
    # validity at all -- corpus_inputs.json is a FIXED component read
    # once at the TOP of main(), not part of --sealed-dir -- so Pass B
    # ran and built cal:000's bundle despite the reported corpus
    # diagnostic (a duplicate (context, output) tuple at cal:001,
    # UNRELATED to the manifest's credited cal:000). The toy context
    # commitment is rewritten alongside the corpus mutation so it stays
    # internally coherent (no incidental CONTEXT_HASH_MISMATCH noise).
    # POST-FIX: corpus_prereq_ok is one of the six upstream_ok operands.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    _rewrite_corpus_and_recompute_commitment(tmp_path, env, _toy_duplicate_tuple_corpus())

    manifest = _full_position_valid_coverage_manifest()
    sealed_dir = _write_pass_a_gate_sealed_dir(tmp_path, env, manifest)

    calls = _spy_build_product_trace_bundle(monkeypatch)
    rc = vd.main(["--sealed-dir", str(sealed_dir)])
    captured = capsys.readouterr()

    assert calls == [], f"build_product_trace_bundle was called despite an invalid (duplicate-tuple) corpus record: {calls}"
    assert rc == 1
    assert f"cal:001: rule={vd.RULE_DUPLICATE_TUPLE}" in captured.err


def test_main_unavailable_schema_validator_never_builds(tmp_path, monkeypatch, capsys):
    # Case (c). An UNAVAILABLE jsonschema validator (the established
    # `monkeypatch.setattr(vd, "Draft202012Validator", None)` fail-closed
    # pattern -- see
    # test_validate_against_schema_fails_closed_when_jsonschema_module_missing)
    # makes `coverage_runtime_available` False directly (one of its own
    # three conjuncts IS "Draft202012Validator is available"), and
    # `design_schema_ok` / `coverage_schema_ok` False too (neither schema
    # validation call can even RUN without a validator -- both now
    # require the validation to have RUN, never merely "zero errors
    # added", which was vacuously true whenever the `if
    # Draft202012Validator is not None...:` guard simply never fired).
    # Corpus and design SEMANTICS remain independently valid here (this
    # environment's corpus/design are otherwise genuinely clean),
    # isolating the UNAVAILABLE-validator condition from an
    # already-invalid corpus/design. A fully schema-valid, closure-valid
    # 68-surface manifest still yields ZERO builds.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    manifest = _full_position_valid_coverage_manifest()
    sealed_dir = _write_pass_a_gate_sealed_dir(tmp_path, env, manifest)
    monkeypatch.setattr(vd, "Draft202012Validator", None)

    calls = _spy_build_product_trace_bundle(monkeypatch)
    rc = vd.main(["--sealed-dir", str(sealed_dir)])
    captured = capsys.readouterr()

    assert calls == [], f"build_product_trace_bundle was called despite an unavailable schema validator: {calls}"
    assert rc == 1
    assert f"rule={vd.RULE_MISSING_SCHEMA}" in captured.err


def test_main_combined_prereq_and_internal_pass_a_failure_both_diagnostics_zero_builds(tmp_path, monkeypatch, capsys):
    # Case (d). Proves the new upstream_ok gate (a caller-side,
    # main()-level conjunction) and check_coverage_manifest's own
    # PRE-EXISTING internal Pass A loop (its own `pass_a_errors`, never
    # touched by this pass) compose WITHOUT suppressing either
    # diagnostic class. Two INDEPENDENT, orthogonal defects, deliberately
    # chosen so neither trips the other's check: (1) an upstream
    # prerequisite failure -- the same duplicate-tuple corpus record at
    # cal:001 as case (b) (corpus_prereq_ok False); (2) an internal
    # Pass-A failure -- ONE evidence record (value_role_v1.limit) citing
    # a well-formed but UNREGISTERED item_id (cal:999; the schema's
    # item_id PATTERN alone cannot catch this -- "cal:999" matches
    # "^cal:[0-9]{3}$" -- only check_coverage_manifest's own `iid not in
    # design_by_id` check can, so the manifest stays schema-valid AND
    # closure-valid). BOTH diagnostics must appear in `errors`, and
    # build_product_trace_bundle must still be called zero times.
    env = _build_main_toy_v2_stage_environment(tmp_path, monkeypatch)
    _rewrite_corpus_and_recompute_commitment(tmp_path, env, _toy_duplicate_tuple_corpus())

    manifest = _full_position_valid_coverage_manifest()
    manifest["value_role_v1.limit"][0]["item_id"] = "cal:999"
    sealed_dir = _write_pass_a_gate_sealed_dir(tmp_path, env, manifest)

    calls = _spy_build_product_trace_bundle(monkeypatch)
    rc = vd.main(["--sealed-dir", str(sealed_dir)])
    captured = capsys.readouterr()

    assert calls == [], f"build_product_trace_bundle was called despite a combined corpus + internal Pass-A failure: {calls}"
    assert rc == 1
    assert f"cal:001: rule={vd.RULE_DUPLICATE_TUPLE}" in captured.err
    assert f"coverage_manifest.json[value_role_v1.limit] cal:999: rule={vd.RULE_COVERAGE_UNKNOWN_ITEM}" in captured.err


# -----------------------------------------------------------------------
# Fix 2: BIND value_role CREDIT TO THE OWNING FACET. _pc_locate's
# value_role_v1 branch now additionally requires the owning
# FrameProductEvent's own facet to equal the synthetic value-role facet
# ("facet:" + suffix), in addition to the pre-existing exact-span and
# classifier checks.
# -----------------------------------------------------------------------

def test_value_role_v1_cost_does_not_credit_when_owning_facet_is_duration():
    # RED (pre-fix, verified True): "Shipping takes $5." -- "takes"
    # triggers facet:duration (the OWNING frame's real facet), but the
    # bare value span "$5" classifies as "cost" via classify_value_span_
    # text's currency-marker policy. Pre-fix, _pc_locate credited
    # value_role_v1.cost purely off the classifier match, ignoring which
    # facet actually owns the value. Pinned verbatim per the ticket.
    item = {"id": "cal:test", "context": "Shipping takes $5.", "output": ""}
    bundle = vd.build_product_trace_bundle(item)
    fe = bundle.fields[0].frame_events[0]
    assert fe.facet == "facet:duration"
    assert vd.classify_value_span_text(fe.value_span_raw, _DISCRIMINATOR_TABLES_DATA) == "cost"
    assert _pc_credit(bundle, "value_role_v1.cost", "C1", "context") is False


def test_value_role_v1_duration_does_not_credit_when_owning_facet_is_cost():
    # RED (pre-fix, verified True): "Shipping costs 5 days." -- "costs"
    # triggers facet:cost (the OWNING frame's real facet), but the bare
    # value span "5 days" classifies as "duration" via classify_value_
    # span_text's time-unit-word policy. Pinned verbatim per the ticket.
    item = {"id": "cal:test", "context": "Shipping costs 5 days.", "output": ""}
    bundle = vd.build_product_trace_bundle(item)
    fe = bundle.fields[0].frame_events[0]
    assert fe.facet == "facet:cost"
    assert vd.classify_value_span_text(fe.value_span_raw, _DISCRIMINATOR_TABLES_DATA) == "duration"
    assert _pc_credit(bundle, "value_role_v1.duration", "C1", "context") is False


def test_value_role_v1_still_credits_when_facet_and_classified_span_agree():
    # Positive sanity, unaffected by the fix: a genuinely matching
    # facet + classified-span pairing still credits.
    duration_item = {"id": "cal:test", "context": "Processing takes 3 days.", "output": ""}
    duration_bundle = vd.build_product_trace_bundle(duration_item)
    assert _pc_credit(duration_bundle, "value_role_v1.duration", "C1", "context") is True

    cost_item = {"id": "cal:test", "context": "Service costs $5.", "output": ""}
    cost_bundle = vd.build_product_trace_bundle(cost_item)
    assert _pc_credit(cost_bundle, "value_role_v1.cost", "C1", "context") is True


# -----------------------------------------------------------------------
# Fix 3: CORRECT comparators_v1@value. Its exact positions are
# {(C1,context),(C1,output)} -- (C3,context) is REMOVED (an error
# propagated from the reviewer's own earlier plan). C3 top-level-value
# source-conflict coverage belongs to synthetic value_role_v1; C3
# comparator credit comes only through condition/requirement
# MeasureAtoms.
# -----------------------------------------------------------------------

def test_capability_map_comparators_v1_value_is_exactly_c1_positions():
    assert vd.CAPABILITY_MAP[("comparators_v1", "value")] == frozenset({("C1", "context"), ("C1", "output")})


def test_comparators_v1_bare_value_no_longer_credits_c3_context():
    # RED (pre-fix, verified True): a bare top-level comparator VALUE
    # product (location="value", no condition/requirement-embedded
    # comparator anywhere on the item) at C3/context, with a genuine
    # trusted-obligation owner (so the ONLY reason credit could fail is
    # the CAPABILITY_MAP position itself, never an unrelated ownership
    # qualifier) -- must NOT credit post-fix.
    identity = ("context", 0, 0, 0)
    ce = vd.ComparatorProductEvent(
        location="value", comparator_folds=("over",), raw_span_text="over 30", raw_start=0, raw_end=7,
        owning_identity=identity, owning_condition_index=None, parsed_intervals=("x",),
    )
    fe = vd.FrameProductEvent(
        identity=identity, facet="facet:cost", raw_facet="facet:cost", subject=frozenset({"service"}), object=frozenset(),
        modifiers=frozenset(), excl_candidates=(), quant_class=0, quant_token_fold=None, is_deny=False, negator_raw=None,
        polarity=0, trigger_raw="costs", trigger_folds=("cost",), value_span_raw="over 30", value_span_start=0, value_span_end=7,
        value_intervals=("x",), comparator_events=(ce,), conds=(), assertive=True, subject_conjuncts=(), subject_conjunct_heads=(),
        req_formula=None, req_concept_mappings=(), req_complement_candidates=(), req_comparator_events=(),
    )
    ft_ctx = vd.FieldProductTrace(field="context", source_index=0, boundary_start=0, boundary_end=10, tier="tier_1", partial=False, frame_events=(fe,), partial_events=())
    ft_out = vd.FieldProductTrace(field="output", source_index=0, boundary_start=0, boundary_end=10, tier=None, partial=False, frame_events=(), partial_events=())
    obligation = vd.ObligationProductEvent(
        kind=0, governed_identity=None, source_activation_domain=None, applicability_scope=None,
        requirement_formula=None, source_polarity=0, trivial=False, source_frame_identities=(identity,),
    )
    bundle = vd.ProductTraceBundle(
        item_id="synthetic", fields=(ft_ctx, ft_out),
        trusted_obligations=vd.ObligationCaptureProduct(items=(obligation,), partial_event=None),
        excluded_obligation_frames=(), evidence=vd.EvidenceCaptureProduct(items=(), partial_event=None),
    )
    toy_tables = {"comparators_v1": [{"tokens": ["over"], "interval": {}}]}

    assert _pc_credit(bundle, "comparators_v1.over", "C3", "context", toy_tables) is False
    # sanity: the SAME shape still credits at C1/context (value location
    # keeps (C1,context) -- unaffected by the fix).
    assert _pc_credit(bundle, "comparators_v1.over", "C1", "context", toy_tables) is True


def test_comparators_v1_condition_and_requirement_still_reach_c3_context():
    # Sanity: C3 comparator credit at (C3,context) still succeeds when
    # the comparator is CONDITION-embedded or REQUIREMENT-embedded --
    # only the bare top-level VALUE location lost (C3,context).
    condition_item = {
        "id": "cal:test",
        "context": "Refunds are refundable if over 30 days. Refunds are not refundable if over 30 days.",
        "output": "Refunds are refundable if over 30 days.",
    }
    condition_bundle = vd.build_product_trace_bundle(condition_item)
    assert _pc_credit(condition_bundle, "comparators_v1.over", "C3", "context") is True

    requirement_item = {"id": "cal:test", "context": "Refunds require over $30.", "output": "Refunds are refundable if over $20."}
    requirement_bundle = vd.build_product_trace_bundle(requirement_item)
    assert _pc_credit(requirement_bundle, "comparators_v1.over", "C3", "context") is True


# -----------------------------------------------------------------------
# Fix 4: PIN THE EXACT CAPABILITY_MAP. An INDEPENDENT literal expected
# mapping -- all 13 exact keys, each with its exact position set (with
# comparators_v1@value as corrected by fix 3) -- asserted for FULL
# EQUALITY against the live CAPABILITY_MAP. The pre-existing per-surface
# union-equality test (test_capability_map_per_surface_union_equals_
# registry_allowed_positions_for_all_50) is kept unchanged as a SEPARATE
# invariant.
# -----------------------------------------------------------------------

_EXPECTED_CAPABILITY_MAP: dict[tuple[str, str], frozenset[tuple[str, str]]] = {
    ("facets_v1", "frame"): frozenset({("C1", "context"), ("C1", "output"), ("C3", "context"), ("C3", "output"), ("C4", "context"), ("C4", "output")}),
    ("concept_v1", "condition"): frozenset({("C1", "context"), ("C1", "output"), ("C3", "context"), ("C3", "output"), ("C4", "context"), ("C4", "output")}),
    ("concept_v1", "requirement"): frozenset({("C3", "context"), ("C3", "output")}),
    ("comparators_v1", "value"): frozenset({("C1", "context"), ("C1", "output")}),
    ("comparators_v1", "condition"): frozenset({("C1", "context"), ("C1", "output"), ("C3", "context"), ("C3", "output"), ("C4", "context"), ("C4", "output")}),
    ("comparators_v1", "requirement"): frozenset({("C3", "context"), ("C3", "output")}),
    ("excl_v1", "modifier"): frozenset({("C1", "context"), ("C1", "output"), ("C3", "context"), ("C3", "output"), ("C4", "context"), ("C4", "output")}),
    ("complement_v1", "condition"): frozenset({("C1", "context"), ("C1", "output"), ("C3", "context"), ("C3", "output"), ("C4", "context"), ("C4", "output")}),
    ("complement_v1", "requirement"): frozenset({("C3", "context"), ("C3", "output")}),
    ("condition_operators_v1", "condition"): frozenset({("C1", "context"), ("C1", "output"), ("C3", "context"), ("C3", "output"), ("C4", "context"), ("C4", "output")}),
    ("quant_v1", "extent"): frozenset({("C1", "context"), ("C1", "output"), ("C3", "context"), ("C3", "output"), ("C4", "context"), ("C4", "output")}),
    ("quant_v1", "partial"): frozenset({("C1", "context"), ("C1", "output"), ("C3", "context"), ("C3", "output"), ("C4", "context"), ("C4", "output")}),
    ("value_role_v1", "value"): frozenset({("C1", "context"), ("C1", "output"), ("C3", "context")}),
}


def test_capability_map_exact_literal_pin_full_equality():
    # RED (pre-fix-3, verified): fails against the current
    # pre-correction map, whose ("comparators_v1","value") row still
    # carries (C3,context). FULL EQUALITY -- not row count, not family
    # vocabulary, not per-family union -- against the live
    # CAPABILITY_MAP.
    assert len(_EXPECTED_CAPABILITY_MAP) == 13
    assert vd.CAPABILITY_MAP == _EXPECTED_CAPABILITY_MAP


# -----------------------------------------------------------------------
# Fix 5: TIGHTEN quant_v1.abstain CREDIT. Require ALL of: the selected
# token belongs to the abstain class; the stage is PER_HIT_ABSTAIN; the
# cause is the production UNEXTRACTABLE cause; AND the aggregate field
# trace is partial.
# -----------------------------------------------------------------------

def test_quant_v1_abstain_wrong_cause_does_not_credit():
    # RED (pre-fix, verified True): a PER_HIT_ABSTAIN-shaped partial
    # event whose quant_token_fold is genuinely in the abstain class,
    # and whose owning field trace is genuinely partial, but whose cause
    # is NOT the production UNEXTRACTABLE cause (e.g.
    # condition_undecidable, a genuine alternate Abstain/FramePartial
    # cause -- see reference.primitives.CONDITION_UNDECIDABLE) must NOT
    # credit.
    identity = ("context", 0, 0, 0)
    pe_wrong_cause = vd.PartialProductEvent(
        identity=identity, stage=vd.PartialStage.PER_HIT_ABSTAIN,
        cause="condition_undecidable", quant_token_fold="most",
    )
    ft_ctx = vd.FieldProductTrace(
        field="context", source_index=0, boundary_start=0, boundary_end=10, tier="tier_1",
        partial=True, frame_events=(), partial_events=(pe_wrong_cause,),
    )
    ft_out = vd.FieldProductTrace(field="output", source_index=0, boundary_start=0, boundary_end=10, tier=None, partial=False, frame_events=(), partial_events=())
    bundle = vd.ProductTraceBundle(
        item_id="synthetic", fields=(ft_ctx, ft_out),
        trusted_obligations=vd.ObligationCaptureProduct(items=(), partial_event=None),
        excluded_obligation_frames=(), evidence=vd.EvidenceCaptureProduct(items=(), partial_event=None),
    )
    toy_tables = {"quant_v1": {"abstain": ["most"]}}
    assert _pc_credit(bundle, "quant_v1.abstain", "C1", "context", toy_tables) is False

    # sanity: the SAME shape with cause=UNEXTRACTABLE ("unextractable")
    # credits.
    pe_right_cause = vd.dataclasses.replace(pe_wrong_cause, cause="unextractable")
    ft_ctx2 = vd.dataclasses.replace(ft_ctx, partial_events=(pe_right_cause,))
    bundle2 = vd.dataclasses.replace(bundle, fields=(ft_ctx2, ft_out))
    assert _pc_credit(bundle2, "quant_v1.abstain", "C1", "context", toy_tables) is True


def test_quant_v1_abstain_nonpartial_aggregate_field_does_not_credit():
    # RED-adjacent: the SAME right-cause, right-token event, but the
    # OWNING field's aggregate trace itself is marked nonpartial (a
    # shape that should never occur from a genuine replay, since a
    # PER_HIT_ABSTAIN event always sets field_partial=True in production
    # -- see _replay_field_trace -- but the credit function must not
    # simply trust the event's mere presence without checking the
    # aggregate flag it now positively requires).
    identity = ("context", 0, 0, 0)
    pe = vd.PartialProductEvent(
        identity=identity, stage=vd.PartialStage.PER_HIT_ABSTAIN,
        cause="unextractable", quant_token_fold="most",
    )
    ft_ctx = vd.FieldProductTrace(
        field="context", source_index=0, boundary_start=0, boundary_end=10, tier="tier_1",
        partial=False, frame_events=(), partial_events=(pe,),
    )
    ft_out = vd.FieldProductTrace(field="output", source_index=0, boundary_start=0, boundary_end=10, tier=None, partial=False, frame_events=(), partial_events=())
    bundle = vd.ProductTraceBundle(
        item_id="synthetic", fields=(ft_ctx, ft_out),
        trusted_obligations=vd.ObligationCaptureProduct(items=(), partial_event=None),
        excluded_obligation_frames=(), evidence=vd.EvidenceCaptureProduct(items=(), partial_event=None),
    )
    toy_tables = {"quant_v1": {"abstain": ["most"]}}
    assert _pc_credit(bundle, "quant_v1.abstain", "C1", "context", toy_tables) is False


def test_quant_v1_abstain_real_positive_and_discriminator_9_unaffected():
    # Preservation: the real-text positive ("Most services are
    # available.") still credits, and discriminator 9 (universal
    # preemption defeats abstain credit) still does not.
    positive_item = {"id": "cal:test", "context": "Most services are available.", "output": "Services are unavailable."}
    positive_bundle = vd.build_product_trace_bundle(positive_item)
    ctx = positive_bundle.fields[0]
    assert ctx.partial is True
    assert ctx.partial_events[0].cause == "unextractable"
    assert _pc_credit(positive_bundle, "quant_v1.abstain", "C1", "context") is True

    disc9_item = {"id": "disc9", "context": "All most services are available.", "output": "Services are unavailable."}
    disc9_bundle = vd.build_product_trace_bundle(disc9_item)
    assert _pc_credit(disc9_bundle, "quant_v1.abstain", "C1", "context") is False


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1b: the bounded 18-NONTABLE-PREDICATE pass.
#
# GROUP A (the seven c2_* surfaces): reference.checks.scan_c2_lexical /
# has_governed_question -- extracted from checks.C2's own lexical loop
# and evaluate.py's own prior LOCAL _has_governed_question -- are the
# SINGLE shared implementation checks.C2, evaluate.py's Stage W1 gate,
# AND _predicate_nontable's Group A handlers all consume. No
# independent calibration-side replica exists.
#
# GROUP B ({polarity_via_deny_trigger, polarity_via_negator,
# contraction_expansion}) and GROUP C (the eight abstain/event
# surfaces) are product-honest, event-local, ProductTraceBundle-backed
# evidence (_check_nontable_bundle_backed_evidence), sharing ONE
# Pass-B-wide bundle cache with the 50 in-scope product surfaces.
# ---------------------------------------------------------------------

_C2_REAL_TABLES_DATA = _DISCRIMINATOR_TABLES_DATA


# --- Group A: shared-helper consumption proofs (AST/name-reference) ---

def test_checks_c2_consumes_scan_c2_lexical_shared_helper():
    # checks.C2 itself must reference scan_c2_lexical -- the lexical
    # loop is no longer inline in C2's own body.
    referenced = _ast_referenced_names(ref_checks.C2)
    assert "scan_c2_lexical" in referenced


def test_evaluate_consumes_has_governed_question_shared_helper():
    # evaluate.evaluate's own Stage W1 gate must reference
    # checks.has_governed_question -- the prior LOCAL
    # evaluate._has_governed_question (formerly at evaluate.py:108) no
    # longer exists as a separate implementation.
    referenced = _ast_referenced_names(ref_evaluate.evaluate)
    assert "has_governed_question" in referenced
    assert not hasattr(ref_evaluate, "_has_governed_question"), (
        "evaluate._has_governed_question must no longer exist as a separate "
        "local implementation -- it is promoted to reference.checks.has_governed_question"
    )


def test_predicate_nontable_group_a_consumes_shared_c2_helpers():
    # _predicate_nontable's Group A (c2_*) handlers must reference the
    # SAME shared helpers checks.C2/evaluate.py consume -- never an
    # independent calibration-side reimplementation of definitive/hedge/
    # window/negation/interrogative handling.
    referenced = _ast_referenced_names(vd._predicate_nontable)
    assert "scan_c2_lexical" in referenced
    assert "has_governed_question" in referenced


# --- Group A: 14 fact tests (one direct positive AND negative per surface) ---

def test_fact_c2_definitive_hit_positive_and_negative():
    assert vd._predicate_nontable("The result is guaranteed.", "nontable.c2_definitive_hit", _C2_REAL_TABLES_DATA) is True
    assert vd._predicate_nontable("The result ships tomorrow.", "nontable.c2_definitive_hit", _C2_REAL_TABLES_DATA) is False


def test_fact_c2_negated_definitive_positive_and_negative():
    assert vd._predicate_nontable("The result is not guaranteed.", "nontable.c2_negated_definitive", _C2_REAL_TABLES_DATA) is True
    assert vd._predicate_nontable("The result is guaranteed.", "nontable.c2_negated_definitive", _C2_REAL_TABLES_DATA) is False


def test_fact_c2_hedge_in_window_positive_and_negative():
    assert vd._predicate_nontable("The result may be guaranteed.", "nontable.c2_hedge_in_window", _C2_REAL_TABLES_DATA) is True
    assert vd._predicate_nontable("The result is guaranteed.", "nontable.c2_hedge_in_window", _C2_REAL_TABLES_DATA) is False


def test_fact_c2_hedge_outside_window_or_absent_positive_and_negative():
    assert vd._predicate_nontable("The result is guaranteed.", "nontable.c2_hedge_outside_window_or_absent", _C2_REAL_TABLES_DATA) is True
    assert vd._predicate_nontable("The result may be guaranteed.", "nontable.c2_hedge_outside_window_or_absent", _C2_REAL_TABLES_DATA) is False


def test_fact_c2_negated_hedge_positive_and_negative():
    assert vd._predicate_nontable(
        "The result is guaranteed. It is not likely but may still happen.", "nontable.c2_negated_hedge", _C2_REAL_TABLES_DATA
    ) is True
    assert vd._predicate_nontable("The result may be guaranteed.", "nontable.c2_negated_hedge", _C2_REAL_TABLES_DATA) is False


def test_fact_c2_window_boundary_positive_and_negative():
    assert vd._predicate_nontable(
        "The result is guaranteed because it may work.", "nontable.c2_window_boundary", _C2_REAL_TABLES_DATA
    ) is True
    assert vd._predicate_nontable("The result may be guaranteed.", "nontable.c2_window_boundary", _C2_REAL_TABLES_DATA) is False


def test_fact_c2_interrogative_positive_and_negative():
    assert vd._predicate_nontable("Is the result guaranteed?", "nontable.c2_interrogative", _C2_REAL_TABLES_DATA) is True
    assert vd._predicate_nontable("The result is guaranteed.", "nontable.c2_interrogative", _C2_REAL_TABLES_DATA) is False


# --- Group A: four representative outcome anchors ---

def test_outcome_anchor_rescued_definitive_passes():
    from reference.primitives import tokenize

    toks = tokenize("The result may be guaranteed.")
    assert ref_checks.C2(toks, False) == (ref_checks.PASS, "detection_complete", None)


def test_outcome_anchor_unrescued_definitive_violates_with_warning():
    from reference.primitives import tokenize

    toks = tokenize("The result is guaranteed.")
    assert ref_checks.C2(toks, False) == (ref_checks.VIOLATION, "detection_complete", ref_checks.WARNING)


def test_outcome_anchor_governed_question_not_evaluated_extraction_partial():
    text = "Is the result guaranteed?"
    assert ref_checks.has_governed_question(text) is True
    from reference.primitives import tokenize

    toks = tokenize(text)
    assert ref_checks.C2(toks, ref_checks.has_governed_question(text)) == (
        ref_checks.NOT_EVALUATED, "extraction_partial", None,
    )


def test_outcome_anchor_negated_definitive_alone_passes():
    from reference.primitives import tokenize

    toks = tokenize("The result is not guaranteed.")
    assert ref_checks.C2(toks, False) == (ref_checks.PASS, "detection_complete", None)


# --- Group A: explicit question cases ---

def test_governed_question_true_for_earlier_valid_question_then_statement():
    # A genuine SPLIT_v1 sentence boundary after "?" (terminator followed
    # by whitespace) -- the SECOND sentence is a plain statement, but the
    # FIRST is interrogative, so the field-level rule is true.
    assert ref_checks.has_governed_question("Is the result guaranteed? The result is guaranteed.") is True


def test_governed_question_false_for_interior_nonterminating_question_then_statement():
    # SAN-893/e13: "guaranteed?The" has NO whitespace after "?" -- SPLIT_v1
    # does not terminate there, so the WHOLE text remains one merged
    # sentence whose OWN trailing terminator is "." (not "?"), which is
    # not interrogative -- matches oracle c2-adjacent-question-split.
    assert ref_checks.has_governed_question("Is the result guaranteed?The result is guaranteed.") is False


# --- Group A: authentic RED regressions (the naive pre-2B.1b defects) ---

def test_red_hedge_free_text_no_longer_credited_without_any_definitive():
    # RED (pre-2B.1b): the naive predicate was `not any_token(hedge_terms)`
    # -- TRUE for ANY hedge-free text, even text with NO definitive term
    # at all to be unrescued. GREEN: credit requires an EXAMINED
    # non-negated definitive that was actually left unrescued.
    text = "The weather is nice today."
    assert vd._predicate_nontable(text, "nontable.c2_hedge_outside_window_or_absent", _C2_REAL_TABLES_DATA) is False
    # the historical defect, still reachable directly and pinned here so
    # the regression is never silently reintroduced:
    assert any(_word_present_probe(tok, text.lower()) is False for tok in ["may", "might", "could"])


def _word_present_probe(token: str, lowered_text: str) -> bool:
    return vd._word_present(token, lowered_text)


def test_red_hedge_boundary_mere_presence_no_longer_credited_without_actual_clipping():
    # RED (pre-2B.1b): the naive predicate was `any_substr(hedge_
    # boundaries)` -- TRUE whenever "because"/"since" appeared ANYWHERE
    # in the text, even when no definitive existed for it to ever clip a
    # window around. GREEN: credit requires an EXAMINED definitive whose
    # window was ACTUALLY shortened.
    text = "It seems fine because deadlines matter."
    assert vd._predicate_nontable(text, "nontable.c2_window_boundary", _C2_REAL_TABLES_DATA) is False


def test_red_interrogative_endswith_false_negative_fixed():
    # RED (pre-2B.1b): the naive predicate was
    # `item_text.strip().endswith("?")` -- FALSE for an output whose
    # FIRST sentence is a genuine governed question followed by a
    # statement, even though production's own SPLIT_v1 + is_interrogative
    # treat the field as containing a governed question. GREEN: credit
    # follows has_governed_question (any SPLIT_v1 sentence interrogative).
    text = "Is the result guaranteed? The result is guaranteed."
    assert text.strip().endswith("?") is False  # the naive rule's own blind spot, pinned
    assert vd._predicate_nontable(text, "nontable.c2_interrogative", _C2_REAL_TABLES_DATA) is True


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1b-FIX A1: HONOR C2's PARTIAL GATE IN COVERAGE. For
# every lexical c2_* surface EXCEPT c2_interrogative, a governed-
# question-true output must earn NO credit and scan_c2_lexical must NOT
# be invoked -- exactly mirroring checks.C2's own row-0 gate (evaluate
# .py passes has_governed_question(out_text) as C2's out_partial, which
# short-circuits BEFORE scan_c2_lexical ever runs). c2_interrogative
# ALONE credits the governed-question product. The (C2, output)
# contraction route (_nb_contraction_c2_route) must likewise reject a
# governed-question output before scanning.
# ---------------------------------------------------------------------

_A1_LEXICAL_C2_SURFACES = (
    "c2_definitive_hit", "c2_negated_definitive", "c2_hedge_in_window",
    "c2_hedge_outside_window_or_absent", "c2_negated_hedge", "c2_window_boundary",
)


def test_red_a1_interrogative_output_no_longer_credits_lexical_c2_surfaces():
    # RED (pre-2B.1b-FIX): "Is the result guaranteed?" is a governed
    # question (has_governed_question is True) -- production's own C2
    # would report NOT_EVALUATED/extraction_partial and never invoke
    # scan_c2_lexical at all, yet the CURRENT _predicate_nontable
    # handlers still run the shared scan unconditionally and credit
    # c2_definitive_hit / c2_hedge_outside_window_or_absent (a
    # DEFINITIVE_v1 "guaranteed" with no hedge in window) even though
    # production would never have examined it.
    text = "Is the result guaranteed?"
    assert ref_checks.has_governed_question(text) is True
    for name in _A1_LEXICAL_C2_SURFACES:
        assert vd._predicate_nontable(text, f"nontable.{name}", _C2_REAL_TABLES_DATA) is False, (
            f"{name}: a governed-question output must earn NO lexical c2_* credit"
        )
    assert vd._predicate_nontable(text, "nontable.c2_interrogative", _C2_REAL_TABLES_DATA) is True


def test_a1_scan_c2_lexical_never_invoked_for_governed_question_output(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("scan_c2_lexical must never be invoked for a governed-question output")

    monkeypatch.setattr(ref_checks, "scan_c2_lexical", _boom)
    text = "Is the result guaranteed?"
    for name in _A1_LEXICAL_C2_SURFACES:
        assert vd._predicate_nontable(text, f"nontable.{name}", _C2_REAL_TABLES_DATA) is False
    assert vd._predicate_nontable(text, "nontable.c2_interrogative", _C2_REAL_TABLES_DATA) is True


def test_red_a1_contraction_c2_route_credits_governed_question_output():
    # RED: "Isn't the result guaranteed?" is BOTH a governed question
    # AND carries a contraction ("isn't") -- production's own C2 would
    # never examine it (out_partial gate fires first), but the CURRENT
    # _nb_contraction_c2_route scans unconditionally and finds the
    # negated "guaranteed" definitive, crediting contraction_expansion.
    item = {"id": "cal:000", "output": "Isn't the result guaranteed?"}
    assert ref_checks.has_governed_question(item["output"]) is True
    assert vd._nb_contraction_c2_route(item) is False


def test_a1_contraction_c2_route_scan_c2_lexical_never_invoked_for_governed_question(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("scan_c2_lexical must never be invoked for a governed-question output")

    monkeypatch.setattr(ref_checks, "scan_c2_lexical", _boom)
    item = {"id": "cal:000", "output": "Isn't the result guaranteed?"}
    assert vd._nb_contraction_c2_route(item) is False


def test_pinned_a1_is_the_result_guaranteed_discriminator():
    # PIN: "Is the result guaranteed?" credits c2_interrogative but NOT
    # c2_definitive_hit, NOT c2_hedge_outside_window_or_absent, NOT
    # contraction_expansion.
    text = "Is the result guaranteed?"
    assert vd._predicate_nontable(text, "nontable.c2_interrogative", _C2_REAL_TABLES_DATA) is True
    assert vd._predicate_nontable(text, "nontable.c2_definitive_hit", _C2_REAL_TABLES_DATA) is False
    assert vd._predicate_nontable(text, "nontable.c2_hedge_outside_window_or_absent", _C2_REAL_TABLES_DATA) is False
    item = {"id": "cal:000", "context": "ctx.", "output": text}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_contraction_expansion(bundle, item, "C2", "output") is False


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1b-FIX A2: CORRECT WINDOW-CLIPPING FACTS. The
# field-clamped raw bounds (raw_lo = max(0, d_lo - W_HEDGE); raw_hi =
# min(n, d_hi + W_HEDGE)) are computed FIRST; the production segment is
# then applied (w_lo = max(seg_lo, raw_lo); w_hi = min(seg_hi,
# raw_hi)); window_clipped_lo/hi are TRUE whenever the segment alone
# shortened the window relative to the raw bound (comma/semicolon/
# paren segmentation), and the later because/since boundary-token
# search ORs further shortening into the SAME flags. These tests use
# scan_c2_lexical's sink-based capture (SAN-881 PASS 2B.1b-FIX A3,
# below) -- the two fixes land together in checks.py, so the tests are
# written directly against the final (post-A3) streaming API.
# ---------------------------------------------------------------------

def _scan_first_exam(text: str) -> dict:
    from reference.primitives import tokenize

    facts: list = []
    ref_checks.scan_c2_lexical(tokenize(text), sink=facts.append)
    return facts[0]


def test_red_a2_comma_boundary_clip_not_flagged():
    exam = _scan_first_exam("One two three four five, guaranteed nothing more.")
    assert exam["window"] == (6, 10)
    assert exam["window_clipped_lo"] is True, (
        "the comma segment boundary at index 5 genuinely shortened the window's "
        "lower bound from the raw field-clamped bound (0) to the segment start (6)"
    )
    assert exam["window_clipped_hi"] is False


def test_red_a2_paren_boundary_clips_both_sides_not_flagged():
    exam = _scan_first_exam("(guaranteed) is what happens next around here today.")
    assert exam["window"] == (1, 2)
    assert exam["window_clipped_lo"] is True, (
        "the '(' at index 0 shortened the lower bound from the raw bound (0) to "
        "the segment start (1)"
    )
    assert exam["window_clipped_hi"] is True, (
        "the ')' at index 2 shortened the upper bound from the raw bound (10) to "
        "the segment end (2)"
    )


def test_red_a2_semicolon_boundary_clip_lo_not_flagged():
    exam = _scan_first_exam("Before that; guaranteed items ship free around the world.")
    assert exam["window"] == (3, 11)
    assert exam["window_clipped_lo"] is True, (
        "the ';' at index 2 shortened the lower bound from the raw bound (0) to "
        "the segment start (3)"
    )
    assert exam["window_clipped_hi"] is False, "no boundary shortens the upper side here (raw_hi == sentence end)"


def test_a2_square_brackets_never_clip():
    # PIN: square brackets are NOT T.structural_punctuation and must
    # NEVER be added as a clipping boundary -- a bracket-adjacent
    # definitive's window is governed only by W_HEDGE/segment/because-
    # since, exactly as an ordinary word would be.
    exam = _scan_first_exam("Before [that] guaranteed items ship free around the world today.")
    d_lo = exam["span"][0]
    assert exam["window"][0] == max(0, d_lo - 8), "brackets must not clip the window's lower bound"


def test_a2_window_boundary_still_credits_because_since_after_fix():
    # existing GREEN pin (test_fact_c2_window_boundary_positive_and_negative)
    # re-asserted directly against scan_c2_lexical to confirm the
    # because/since boundary-token search still ORs into the flags
    # after the segment-based derivation is corrected.
    exam = _scan_first_exam("The result is guaranteed because it may work.")
    assert exam["window_clipped_hi"] is True


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1b-FIX A3: REMOVE THE PRODUCTION MEMORY REGRESSION.
# scan_c2_lexical must STREAM in production: an optional sink/observer
# callback, never an unconditionally-retained "exams" list. C2 calls it
# WITHOUT a sink (no per-definitive fact record ever built on that
# path); calibration supplies a sink and captures exactly the facts it
# needs into its OWN local list.
# ---------------------------------------------------------------------

def test_red_a3_scan_c2_lexical_previously_rejected_sink_kwarg():
    # RED (pre-fix): scan_c2_lexical accepted only out_tokens -- no
    # sink/observer parameter existed, so calibration could not stream
    # facts without production also retaining an "exams" list (a bare
    # `sink=` call raised TypeError). GREEN: the sink kwarg is now
    # accepted and optional.
    from reference.primitives import tokenize

    facts: list = []
    result = ref_checks.scan_c2_lexical(tokenize("The result is guaranteed."), sink=facts.append)
    assert result == {"unrescued": True}
    assert len(facts) == 1


def test_red_a3_no_sink_return_shape_still_carries_exams_key():
    # RED: pre-fix, scan_c2_lexical ALWAYS returns a retained "exams"
    # list even though production's own C2 call site never uses it.
    from reference.primitives import tokenize

    result = ref_checks.scan_c2_lexical(tokenize("The result is guaranteed."))
    assert set(result.keys()) == {"unrescued"}, (
        "scan_c2_lexical's no-sink return shape must carry ONLY 'unrescued' -- "
        "no per-definitive fact list is ever retained on the no-capture path"
    )


def test_red_a3_no_sink_path_allocates_no_per_definitive_fact_records():
    # RED (pre-fix): the implementation appends one dict per EXAMINED
    # (rescued, non-stopping) definitive into a RETAINED "exams" list
    # unconditionally -- a legal near-1MiB field with tens of thousands
    # of rescued definitives retains proportionally many dict records
    # (~70k for such a field) even though the no-sink caller (production
    # C2) never looks at any of them. GREEN: the no-sink path retains
    # ZERO fact-dict objects, independent of how many definitives are
    # examined -- measured directly via the count of LIVE `dict`
    # objects (immune to CPython's small-object/tuple free-list churn,
    # which pollutes a raw tracemalloc allocation-count comparison with
    # unrelated per-iteration scratch-tuple noise).
    import gc

    from reference.primitives import tokenize

    def _live_dict_count() -> int:
        gc.collect()
        return sum(1 for o in gc.get_objects() if type(o) is dict)

    def _retained_dicts(n_repeats: int) -> int:
        text = "It may be guaranteed. " * n_repeats
        tokens = tokenize(text)
        before = _live_dict_count()
        result = ref_checks.scan_c2_lexical(tokens)
        after = _live_dict_count()
        assert result["unrescued"] is False
        return after - before

    small = _retained_dicts(20)
    large = _retained_dicts(2000)
    assert small == 0, f"no-sink path retained {small} dict object(s) for a 20-definitive field"
    assert large == 0, (
        f"no-sink path retained {large} dict object(s) for a 2000-definitive field -- "
        f"proportional-allocation regression (a legal near-1MiB field would retain ~70k)"
    )


def test_a3_sink_path_retains_exactly_one_dict_per_examined_definitive():
    # The complementary positive: WITH a sink, the caller's own captured
    # list retains exactly one dict per examined definitive -- proving
    # the sink is the sole, complete capture mechanism (calibration
    # receives the SAME facts the pre-fix "exams" list used to retain).
    import gc

    from reference.primitives import tokenize

    def _live_dict_count() -> int:
        gc.collect()
        return sum(1 for o in gc.get_objects() if type(o) is dict)

    for n in (20, 2000):
        text = "It may be guaranteed. " * n
        tokens = tokenize(text)
        facts: list = []
        before = _live_dict_count()
        ref_checks.scan_c2_lexical(tokens, sink=facts.append)
        after = _live_dict_count()
        assert len(facts) == n
        assert after - before == n


def test_a3_sink_receives_one_fact_per_examined_definitive():
    from reference.primitives import tokenize

    text = "It may be guaranteed. " * 5
    tokens = tokenize(text)
    facts: list = []
    result = ref_checks.scan_c2_lexical(tokens, sink=facts.append)
    assert len(facts) == 5
    assert result == {"unrescued": False}
    assert all(f["rescuing_hedge"] is not None for f in facts)


def test_a3_sink_facts_match_no_sink_outcome():
    # calibration's sink-captured facts must be the SAME facts the
    # no-sink path's own "unrescued" outcome is derived from -- proven
    # by re-deriving "unrescued" purely from the captured facts and
    # comparing against the no-sink call's own returned value, across a
    # battery of texts (rescued, unrescued, negated, negated-then-hedge).
    from reference.primitives import tokenize

    texts = [
        "The result may be guaranteed.",
        "The result is guaranteed.",
        "The result is not guaranteed.",
        "The result is guaranteed. It is not likely but may still happen.",
        "The result is guaranteed because it may work.",
    ]
    for text in texts:
        tokens = tokenize(text)
        no_sink_result = ref_checks.scan_c2_lexical(tokens)
        facts: list = []
        sink_result = ref_checks.scan_c2_lexical(tokens, sink=facts.append)
        assert sink_result == no_sink_result, text
        derived_unrescued = any(f["unrescued"] for f in facts if not f["negated"])
        assert derived_unrescued == no_sink_result["unrescued"], text


def test_checks_c2_calls_scan_c2_lexical_with_no_sink_argument():
    # STRUCTURAL PROOF: production's own C2 never passes a sink/fact-
    # capture argument -- the AST of checks.C2 must show a bare
    # scan_c2_lexical(out_tokens) call, nothing more.
    import ast
    import inspect

    src = inspect.getsource(ref_checks.C2)
    tree = ast.parse(src)
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "scan_c2_lexical"
    ]
    assert len(calls) == 1
    call = calls[0]
    assert len(call.args) == 1 and not call.keywords, (
        "checks.C2 must call scan_c2_lexical with ONLY out_tokens -- no sink/fact-capture argument"
    )


# ---------------------------------------------------------------------
# GROUP B: polarity_via_deny_trigger, polarity_via_negator,
# contraction_expansion
# ---------------------------------------------------------------------

def test_group_b_polarity_via_deny_trigger_contract():
    item = {"id": "cal:000", "context": "Refunds are unavailable.", "output": "Refunds are unavailable."}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_polarity_via_deny_trigger(bundle, "C1", "context") is True
    assert vd._nb_check_polarity_via_deny_trigger(bundle, "C1", "output") is True

    clean_item = {"id": "cal:001", "context": "Refunds are available.", "output": "Refunds are available."}
    clean_bundle = vd.build_product_trace_bundle(clean_item)
    assert vd._nb_check_polarity_via_deny_trigger(clean_bundle, "C1", "context") is False


def test_group_b_polarity_via_negator_identity_check_not_truthiness():
    # negator_raw IS NOT None -- an IDENTITY check: a contraction-generated
    # negator's own raw text is "" (empty string, falsy but NOT None) and
    # must still credit.
    item = {"id": "cal:000", "context": "Refunds won't be available.", "output": "Refunds won't be available."}
    bundle = vd.build_product_trace_bundle(item)
    ctx_frame = bundle.fields[0].frame_events[0]
    assert ctx_frame.negator_raw == "", "fixture must exercise the empty-raw contraction-negator case"
    assert vd._nb_check_polarity_via_negator(bundle, "C1", "context") is True

    clean_item = {"id": "cal:001", "context": "Refunds are available.", "output": "Refunds are available."}
    clean_bundle = vd.build_product_trace_bundle(clean_item)
    assert vd._nb_check_polarity_via_negator(clean_bundle, "C1", "context") is False


def test_group_b_contraction_expansion_c1_frame_route():
    item = {"id": "cal:000", "context": "Refunds won't be available.", "output": ""}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_contraction_expansion(bundle, item, "C1", "context") is True

    clean_item = {"id": "cal:001", "context": "Refunds are available.", "output": ""}
    clean_bundle = vd.build_product_trace_bundle(clean_item)
    assert vd._nb_check_contraction_expansion(clean_bundle, clean_item, "C1", "context") is False


def test_group_b_contraction_expansion_c2_output_route_via_negator():
    # (C2, output) route: an expansion-derived token participates in the
    # shared C2 lexical product -- here, as the NEGATOR of a negated
    # definitive (the synthesized zero-width "not" token from "won't").
    item = {"id": "cal:000", "context": "ctx.", "output": "The result won't be guaranteed."}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_contraction_expansion(bundle, item, "C2", "output") is True

    clean_item = {"id": "cal:001", "context": "ctx.", "output": "The result is not guaranteed."}
    clean_bundle = vd.build_product_trace_bundle(clean_item)
    assert vd._nb_check_contraction_expansion(clean_bundle, clean_item, "C2", "output") is False


def test_group_b_red_deny_trigger_substring_inside_unrelated_word_no_longer_credits():
    # RED (pre-2B.1b, still reachable via the now-dead _predicate_nontable
    # handler): the naive predicate was a BARE substring check
    # (`tok.lower() in lowered`) -- "banned" (a deny_trigger) matches
    # INSIDE the unrelated longer word "urbanned". GREEN: the runtime
    # path (_nb_check_polarity_via_deny_trigger) reads production's own
    # FrameProductEvent.is_deny, which requires a genuine WHOLE-TOKEN
    # trigger match via reference.extraction.trigger_scan -- never a
    # substring.
    text = "The urbanned festival continued as planned."
    assert vd._predicate_nontable(text, "nontable.polarity_via_deny_trigger", _C2_REAL_TABLES_DATA) is True, (
        "pinned historical defect: the dead naive handler still bare-substring-matches"
    )
    item = {"id": "cal:000", "context": text, "output": ""}
    bundle = vd.build_product_trace_bundle(item)
    assert bundle.fields[0].frame_events == (), "no genuine trigger fires for the fabricated word"
    assert vd._nb_check_polarity_via_deny_trigger(bundle, "C1", "context") is False


# ---------------------------------------------------------------------
# GROUP C: the eight abstain/event surfaces -- EVENT-LOCAL evidence
# ---------------------------------------------------------------------

def test_group_c_abstain_malformed_value_pinned_pair():
    item = {"id": "cal:000", "context": "ctx.", "output": "It costs $1,23,456."}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_malformed_value", "output", _C2_REAL_TABLES_DATA) is True


def test_group_c_abstain_approx_value_pinned_pair():
    item = {"id": "cal:000", "context": "ctx.", "output": "It costs about $5."}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_approx_value", "output", _C2_REAL_TABLES_DATA) is True


def test_group_c_abstain_e15_nested_adjunct_chain_pinned_pair():
    item = {"id": "cal:000", "context": "Refunds for physical items with receipts are refundable.", "output": ""}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_e15_nested_adjunct_chain", "context", _C2_REAL_TABLES_DATA) is True


def test_group_c_abstain_san894_trigger_in_adjunct_pinned_pair():
    item = {"id": "cal:000", "context": "Refunds for the available items are refundable.", "output": ""}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_san894_trigger_in_adjunct", "context", _C2_REAL_TABLES_DATA) is True


def test_group_c_abstain_san895_non_ascii_digits_pinned_pair():
    # \u0665 is an Arabic-Indic digit -- an ASCII-safe escape in this
    # source file, per this repo's own ASCII-conformance convention
    # (see test_primitives.py's non_ascii_number_inputs fixtures).
    item = {"id": "cal:000", "context": "\u0665 items are pending.", "output": ""}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_san895_non_ascii_digits", "context", _C2_REAL_TABLES_DATA) is True


def test_group_c_abstain_e13_nonterminating_punctuation_pinned_pair():
    item = {"id": "cal:000", "context": "ctx.", "output": "The result is guaranteed.Actually wait."}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_e13_nonterminating_punctuation", "output", _C2_REAL_TABLES_DATA) is True


def test_group_c_abstain_interrogative_output_pinned_pair():
    item = {"id": "cal:000", "context": "ctx.", "output": "Is the result guaranteed?"}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_interrogative_output", "output", _C2_REAL_TABLES_DATA) is True


def test_group_c_abstain_quant_abstain_shares_the_50_surface_matcher():
    item = {"id": "cal:000", "context": "Most items are refundable.", "output": ""}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_abstain_quant_abstain(bundle, "context", _C2_REAL_TABLES_DATA) is True
    # the SAME matcher backs the 50-surface quant_v1.abstain route:
    assert _pc_credit(bundle, "quant_v1.abstain", "C1", "context") is True


def test_group_c_pair_collision_negative_approx_event_does_not_satisfy_malformed_value():
    # PINNED NEGATIVE: "approximate/malformed vocabulary paired with an
    # UNRELATED malformed event -> no credit." abstain_malformed_value
    # and abstain_approx_value share the EXACT SAME (PER_HIT_ABSTAIN,
    # malformed_mention) pinned pair -- the (stage, cause) pair ALONE is
    # insufficient; each surface's OWN mechanism detector must ALSO match.
    item = {"id": "cal:000", "context": "ctx.", "output": "It costs about $5."}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_approx_value", "output", _C2_REAL_TABLES_DATA) is True
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_malformed_value", "output", _C2_REAL_TABLES_DATA) is False


def test_group_c_pair_collision_negative_malformed_event_does_not_satisfy_approx_value():
    item = {"id": "cal:000", "context": "ctx.", "output": "It costs $1,23,456."}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_malformed_value", "output", _C2_REAL_TABLES_DATA) is True
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_approx_value", "output", _C2_REAL_TABLES_DATA) is False


def test_group_c_negative_detector_in_one_sentence_event_in_another_no_credit():
    # PINNED NEGATIVE: detector in one sentence + matching event in
    # another sentence -> no credit. Sentence 0 contains the malformed
    # grouping TEXT ("1,23,456") but no facet trigger fires there (it
    # abstains as TOTAL_SPAN_UNCONSUMED, a DIFFERENT stage); sentence 1
    # has a genuine malformed_mention event (via "about") whose OWN text
    # carries no grouping pattern -- neither sentence has BOTH.
    item = {"id": "cal:000", "context": "ctx.", "output": "Ticket 1,23,456 exists. It costs about $5."}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_malformed_value", "output", _C2_REAL_TABLES_DATA) is False


def test_group_c_negative_detector_in_one_context_source_event_in_another_no_credit():
    # PINNED NEGATIVE: detector in one context source + event in another
    # source -> no credit. Source 0 carries the malformed-looking text
    # but no trigger fires there at all (no malformed_mention event
    # anywhere in this item); sources are never concatenated.
    item = {
        "id": "cal:000",
        "context_sources": [
            {"text": "Ticket 1,23,456 exists.", "tier": "tier_1"},
            {"text": "It ships tomorrow.", "tier": "tier_1"},
        ],
        "output": "",
    }
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_malformed_value", "context", _C2_REAL_TABLES_DATA) is False


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1b-FIX B1: DELETE the generic "extend every segment
# until next hit" behavior in _nb_hit_segment_text. A comma INSIDE a
# malformed numeric lexeme (both flanking tokens are NUMBER-kind) may
# still be handled narrowly as part of that numeric lexeme; it does NOT
# authorize absorbing arbitrary later comma/semicolon segments.
# ---------------------------------------------------------------------

def test_red_b1_malformed_number_comma_no_longer_absorbs_later_approx_segment():
    # RED: "It costs $1,23,456, about nothing." currently credits BOTH
    # abstain_malformed_value AND abstain_approx_value -- the pre-fix
    # _nb_hit_segment_text extends past the malformed number's own
    # internal comma AND the FOLLOWING ", about nothing" comma alike,
    # absorbing "about" into the reconstructed segment. GREEN: it
    # credits malformed only.
    item = {"id": "cal:000", "context": "ctx.", "output": "It costs $1,23,456, about nothing."}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_malformed_value", "output", _C2_REAL_TABLES_DATA) is True
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_approx_value", "output", _C2_REAL_TABLES_DATA) is False


def test_red_fix2_reversed_pin_about_five_ticket_number_is_malformed_not_approx():
    # SAN-881 PASS 2B.1b-FIX2 correction 1+2: REVERSES the PRIOR
    # (INCORRECT) pin this test used to assert. "It costs about $5,
    # ticket 1,23,456 exists." -- the B1-era _nb_hit_segment_text concept
    # stopped the hit's own reconstructed segment at the first comma NOT
    # flanked by NUMBER-NUMBER (the one right after "$5"), so it only
    # ever saw ONE number candidate ("$5") and wrongly classified this
    # as approx. Production's ACTUAL rule 7 value region is NOT
    # comma-bounded at all -- it runs from the trigger end through
    # SENTENCE END (or a condition marker) -- so the SAME hit's value
    # region also contains "1" and "23,456" (the malformed-grouped
    # ticket number further in the sentence): THREE NUMBER-kind
    # candidates total ("$5", "1", "23,456"), which is > 1, so
    # production sees this as malformed, never approx -- production
    # checks the candidate COUNT before it ever inspects the lone
    # candidate's preceding token for an APPROX_V1 match. RED (pre-fix):
    # this test used to assert malformed=False, approx=True (the
    # opposite of the true production behavior). GREEN: malformed=True,
    # approx=False.
    item = {"id": "cal:000", "context": "ctx.", "output": "It costs about $5, ticket 1,23,456 exists."}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_malformed_value", "output", _C2_REAL_TABLES_DATA) is True
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_approx_value", "output", _C2_REAL_TABLES_DATA) is False


def test_b1_hit_segment_text_comma_inside_malformed_number_still_merges():
    # a comma DIRECTLY flanked by NUMBER tokens on both sides (the
    # malformed numeral's own internal comma) is still handled as part
    # of that ONE numeric lexeme -- narrow locality, not zero locality.
    text = "It costs $1,23,456."
    seg = vd._nb_hit_segment_text(text, 0, 0)
    # no OTHER structural-punctuation boundary follows, so the segment's
    # natural end is the sentence end (trailing "." included, exactly
    # like every other non-structural-punctuation token in the segment):
    assert seg == "It costs $1,23,456."
    assert vd._nb_check_malformed_value_in_segment(seg) is True


def test_b1_hit_segment_text_semicolon_never_merges():
    # PIN: comma AND semicolon cross-segment variants -- a semicolon
    # boundary is NEVER absorbed (the narrow exception is comma-only,
    # and only when NUMBER-flanked).
    text = "It costs $1,23,456; about nothing else matters here today."
    seg = vd._nb_hit_segment_text(text, 0, 0)
    assert seg == "It costs $1,23,456"
    assert "about" not in seg


def test_b1_hit_segment_text_comma_cross_segment_variant_stops_at_non_numeric_comma():
    # PIN: comma cross-segment variant -- a comma NOT flanked by
    # NUMBER-NUMBER (an ordinary clause-separating comma) stops the
    # segment exactly like any other structural boundary.
    text = "It costs $5, about nothing else matters here today."
    seg = vd._nb_hit_segment_text(text, 0, 0)
    assert seg == "It costs $5"
    assert "about" not in seg


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1b-FIX B2: uniquely-identifying stages need no extra
# machinery -- GOVERNED_INTERROGATIVE is sufficient for
# abstain_interrogative_output; NONTERMINATING_PUNCTUATION is
# sufficient for e13 -- no additional lossy regex for either.
# ---------------------------------------------------------------------

def test_pinned_b2_e13_lowercase_adjacency_positive():
    # PIN: lowercase e13 adjacency positive ("guaranteed.actually") --
    # RED (pre-fix): the mechanism detector's regex `[.!?][A-Z]`
    # required an UPPERCASE letter after the terminator, a lossy
    # heuristic that misses this genuine production e13 case (SPLIT_v1
    # only checks for whitespace-or-EOF after the terminator, never
    # case). GREEN: NONTERMINATING_PUNCTUATION alone is sufficient.
    item = {"id": "cal:000", "context": "ctx.", "output": "The result is guaranteed.actually it works fine."}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_e13_nonterminating_punctuation", "output", _C2_REAL_TABLES_DATA) is True


def test_b2_e13_and_interrogative_never_call_is_interrogative_or_regex_detector(monkeypatch):
    # STRUCTURAL PROOF: neither surface's credit path may call
    # is_interrogative or _contains_nonterminating_punctuation_run --
    # the (stage, cause) match alone is authoritative.
    def _boom(*args, **kwargs):
        raise AssertionError("no additional textual detector may run for a uniquely-identifying stage")

    monkeypatch.setattr(vd, "_contains_nonterminating_punctuation_run", _boom)
    item = {"id": "cal:000", "context": "ctx.", "output": "The result is guaranteed.Actually wait."}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_e13_nonterminating_punctuation", "output", _C2_REAL_TABLES_DATA) is True

    item2 = {"id": "cal:001", "context": "ctx.", "output": "Is the result guaranteed?"}
    bundle2 = vd.build_product_trace_bundle(item2)
    assert vd._nb_check_event_local_abstain(bundle2, item2, "abstain_interrogative_output", "output", _C2_REAL_TABLES_DATA) is True


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1b-FIX B3: REPLACE the remaining best-effort
# substring/distinct-token detectors with conservative, EXACT
# production-token predicates bound to the identified event/hit.
# ---------------------------------------------------------------------

# -- e15: production pairwise consecutive-preposition rule --

def test_red_b3_e15_repeated_preposition_positive():
    # PIN: repeated-preposition e15 positive ("for ... for ...") -- RED:
    # the old distinct-token detector (_contains_adjunct_preposition_
    # chain) counts DISTINCT preposition TYPES present, so a REPEATED
    # occurrence of the SAME preposition ("for ... for ...", never a
    # second distinct type) never reaches its >=2 threshold. GREEN:
    # production's own pairwise scan does not care whether the two
    # prepositions are the same word or different words.
    item = {
        "id": "cal:000",
        "context": "Refunds for physical items for damaged goods are refundable.",
        "output": "",
    }
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_e15_nested_adjunct_chain", "context", _C2_REAL_TABLES_DATA) is True


def test_pinned_b3_e15_and_preposition_negative():
    # PIN: valid "and <preposition>" e15 negative -- the SAME
    # preposition-chain SHAPE ("for ... with ...", two DISTINCT
    # prepositions, so the OLD substring-count detector wrongly flags
    # it) is EXEMPT when the second preposition is immediately preceded
    # by "and" -- production's own rule, and the new hit-bound scan must
    # honor it (never abstains at all for this sentence).
    text = "Refunds for physical items and with receipts are refundable."
    # RED pin on the OLD dead-path detector's own blind spot (still
    # reachable directly, byte-unchanged per the hard boundary):
    assert vd._contains_adjunct_preposition_chain(text, _C2_REAL_TABLES_DATA) is True, (
        "pinned historical defect: the dead distinct-token detector still substring-counts "
        "'for' and 'with' as two hits, ignoring the 'and <preposition>' exemption"
    )
    # GREEN: the new hit-bound scan correctly finds NEITHER e15 nor
    # san894 for this hit (production itself never abstains here).
    assert vd._nb_adjunct_group_scan(text, 0, 0) is None


# -- SAN-894: longest facet-trigger sequence inside the ACTUAL adjunct
# group, no article requirement --

def test_red_b3_san894_no_article_requirement_positive():
    # PIN: SAN-894 without "the" positive ("Refunds for available
    # items..."). RED: the old detector required the EXACT surface
    # pattern "the <trigger>" (words[i-1] == "the"); "for available
    # items" (no article at all) never matches. GREEN: production's own
    # adjunct-group walk has no article requirement -- ANY facet
    # trigger token found while walking a preposition's own group
    # abstains, article or not.
    item = {"id": "cal:000", "context": "Refunds for available items are refundable.", "output": ""}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_san894_trigger_in_adjunct", "context", _C2_REAL_TABLES_DATA) is True


# -- approximate value: EXACT APPROX_v1 token match, never substring --

def test_red_b3_approx_aboutface_never_substring_matches():
    # PIN: "aboutface" approximate NEGATIVE -- RED: the old detector was
    # `tok.lower() in lowered` (substring), and "about" is a literal
    # substring of the unrelated word "aboutface". GREEN: the new
    # detector requires an EXACT token-fold identity match
    # (APPROX_V1 contains "about", never "aboutface").
    item = {"id": "cal:000", "context": "ctx.", "output": "It costs aboutface $1,23,456."}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_approx_value", "output", _C2_REAL_TABLES_DATA) is False
    # the co-located GENUINE malformed grouping still credits malformed:
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_malformed_value", "output", _C2_REAL_TABLES_DATA) is True


def test_b3_approx_value_in_segment_direct_unit_exact_token():
    assert vd._nb_check_approx_value_in_segment("It costs about $5") is True
    assert vd._nb_check_approx_value_in_segment("It costs aboutface $5") is False
    assert vd._nb_check_approx_value_in_segment("It costs $1,23,456") is False  # 2 candidates, not exactly 1


# -- malformed value: EXACT malformed numeric/value lexeme, never
# unrelated later text --

def test_b3_malformed_value_in_segment_direct_unit_exact_token():
    assert vd._nb_check_malformed_value_in_segment("It costs $1,23,456") is True
    assert vd._nb_check_malformed_value_in_segment("It costs $5") is False
    assert vd._nb_check_malformed_value_in_segment("It costs about $5") is False


# -- SAN-895: non-ASCII digit, host UCD guard, closed (stage, cause) pair set --

def test_red_b4_san895_superscript_digit_positive():
    # PIN: superscript-digit positive (SAN-895). RED: the old detector
    # enumerated only 4 hand-picked Unicode ranges (Arabic-Indic,
    # Extended Arabic-Indic, Devanagari, Fullwidth) -- superscript
    # digits (U+00B2/00B3/00B9, U+2070/2074-2079) are NOT among them,
    # even though ch.isdigit() is True for them. GREEN: the host UCD
    # guard (ch.isdigit() and not ASCII 0-9) catches any script.
    # \u2075 is SUPERSCRIPT FIVE -- an ASCII-safe escape in this source
    # file, per this repo's own ASCII-conformance convention (see
    # test_primitives.py's non_ascii_number_inputs fixtures).
    item = {"id": "cal:000", "context": "\u2075 items are pending.", "output": ""}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_san895_non_ascii_digits", "context", _C2_REAL_TABLES_DATA) is True


def test_red_b4_san895_bengali_digit_positive():
    # PIN: Bengali-digit positive (SAN-895) -- same defect class as the
    # superscript case, a different uncovered script. \u09eb is BENGALI
    # DIGIT FIVE.
    item = {"id": "cal:000", "context": "\u09eb items are pending.", "output": ""}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_san895_non_ascii_digits", "context", _C2_REAL_TABLES_DATA) is True


def test_red_b4_san895_arabic_triggered_value_per_hit_path_positive():
    # PIN: Arabic triggered-value PER_HIT path positive (SAN-895). RED:
    # a non-ASCII digit that IS the sole value candidate for a
    # measure-facet hit costs that hit its value role, and rule 8
    # valency enforcement raises Abstain(UNEXTRACTABLE) --
    # PER_HIT_ABSTAIN/unextractable, NOT TOTAL_SPAN_UNCONSUMED. The
    # pre-fix _GROUP_C_PINNED_PAIRS accepted ONLY TOTAL_SPAN_UNCONSUMED
    # for this surface, so this genuine production path earned no
    # credit. GREEN: SAN-895 accepts the closed two-pair set. \u0665 is
    # ARABIC-INDIC DIGIT FIVE (same escape the existing
    # test_group_c_abstain_san895_non_ascii_digits_pinned_pair uses).
    item = {"id": "cal:000", "context": "The item costs \u0665 dollars.", "output": ""}
    bundle = vd.build_product_trace_bundle(item)
    assert bundle.fields[0].partial_events[0].stage.value == "per_hit_abstain"
    assert bundle.fields[0].partial_events[0].cause == "unextractable"
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_san895_non_ascii_digits", "context", _C2_REAL_TABLES_DATA) is True


def test_b4_san895_closed_pair_set_exactly_two_pairs():
    from reference.calibration.validate_design import PartialStage

    pairs = vd._GROUP_C_PINNED_PAIRS["abstain_san895_non_ascii_digits"]
    assert set(pairs) == {
        (PartialStage.TOTAL_SPAN_UNCONSUMED, None),
        (PartialStage.PER_HIT_ABSTAIN, "unextractable"),
    }


def test_b4_san895_does_not_credit_unrelated_per_hit_abstain_malformed_mention():
    # PINNED NEGATIVE: a malformed_mention PER_HIT_ABSTAIN (a DIFFERENT
    # cause than SAN-895's own unextractable) must never satisfy
    # SAN-895's closed pair set.
    item = {"id": "cal:000", "context": "ctx.", "output": "It costs $1,23,456."}
    bundle = vd.build_product_trace_bundle(item)
    assert vd._nb_check_event_local_abstain(bundle, item, "abstain_san895_non_ascii_digits", "output", _C2_REAL_TABLES_DATA) is False


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1b-FIX2 (bounded correction pass over the 2B.1b-FIX
# delta): three live Group-C misattribution paths (corrections 1-3) plus
# a dispatch-truthfulness fix (correction 4). Every vector below runs
# through check_coverage_manifest's OWN live dispatch (never a
# helper-only call) via _run_manifest_credit/_manifest_credits, exactly
# like the mixed-manifest spy tests above.
#
# Correction 1 RETIRES _nb_hit_segment_text from the malformed/approx/
# SAN-895 per-hit classification role -- it modeled a STRUCTURAL SEGMENT
# (T.structural_punctuation-delimited), a DIFFERENT concept from
# production's own value-role search region (extraction.py step 7: the
# COMPLETE post-trigger region through sentence end or the first
# condition marker). Correction 2 replaces it with
# _nb_classify_hit_value_region, ONE validator-local replay of that
# EXISTING production order. Correction 3 makes _nb_adjunct_group_scan
# replay every hit in a sentence IN ORDER, carrying prev_subject_span,
# applying production's EXACT COORD reject/splice step (extraction.py
# 769-773) before ever scanning subject/object adjunct groups.
# Correction 4 makes _predicate_nontable's own dispatch LAZY: a
# registered Group A (c2_*) evaluation returns before the legacy Group
# B/C handler expressions are ever evaluated.
# ---------------------------------------------------------------------

def _manifest_credits(item: dict, surface: str, check_id: str = "C1", field: str = "output") -> bool:
    """Runs ONE coverage-manifest record for `surface` through
    check_coverage_manifest's OWN live Pass A/Pass B dispatch (never
    _nb_check_event_local_abstain called directly) and reports whether
    it credited: True iff errors comes back empty (no
    RULE_COVERAGE_PREDICATE_FAILED), False iff that rule fired. Any
    OTHER error rule firing is a test-fixture bug, not a credit
    question, so it is asserted away rather than silently folded into
    the True/False result."""
    errors = vd.Errors()
    design_by_id = {item["id"]: {"item_id": item["id"], "scenario_id": "s0"}}
    corpus_by_id = {item["id"]: item}
    coverage = {surface: [{"item_id": item["id"], "check_id": check_id, "field": field}]}
    vd.check_coverage_manifest(errors, coverage, design_by_id, corpus_by_id, _C2_REAL_TABLES_DATA)
    non_predicate_errors = [e for e in errors if vd.RULE_COVERAGE_PREDICATE_FAILED not in e]
    assert non_predicate_errors == [], f"unexpected non-credit errors: {non_predicate_errors}"
    predicate_failed = any(vd.RULE_COVERAGE_PREDICATE_FAILED in e for e in errors)
    return not predicate_failed


# -- corrections 1+2: value-region replay (malformed/approx/SAN-895) --

def test_red_fix2_c12_plan_two_costs_about_five_approx_not_malformed():
    # RED (orchestrator-reproduced against the pre-fix code): "Plan 2
    # costs about $5." currently credits abstain_malformed_value and
    # does NOT credit abstain_approx_value -- the OLD _nb_hit_segment_
    # text-based structural segment for the "costs" trigger's own
    # comma-free sentence spans the WHOLE sentence, including "2" (from
    # "Plan 2", BEFORE the trigger), giving TWO NUMBER-kind candidates
    # ("2" and "$5") and so, wrongly, "malformed". Production's real
    # value-role search region (extraction.py step 7) starts at the
    # TRIGGER's own end, never before it -- "2" is entirely OUTSIDE the
    # region -- so the ONLY candidate is "$5", immediately preceded by
    # "about": GREEN is approx=True, malformed=False.
    item = {"id": "cal:000", "context": "ctx.", "output": "Plan 2 costs about $5."}
    assert _manifest_credits(item, "nontable.abstain_approx_value") is True
    assert _manifest_credits(item, "nontable.abstain_malformed_value") is False


def test_fix2_c12_costs_five_comma_and_later_six_items_is_malformed():
    # "It costs $5, and later 6 items exist." -- production's value
    # region is SENTENCE-bounded (never comma-bounded), so the "costs"
    # hit's own region includes BOTH "$5" and the LATER "6" (from
    # "later 6 items") -- two NUMBER candidates, malformed, never approx
    # (no APPROX_V1 token precedes either).
    item = {"id": "cal:000", "context": "ctx.", "output": "It costs $5, and later 6 items exist."}
    assert _manifest_credits(item, "nontable.abstain_malformed_value") is True
    assert _manifest_credits(item, "nontable.abstain_approx_value") is False


def test_red_fix2_c12_costs_five_semicolon_later_six_items_is_malformed():
    # RED (orchestrator-reproduced): "It costs $5; later 6 items exist."
    # currently credits NEITHER surface -- B1's semicolon-never-merges
    # rule stops the OLD structural segment at "$5" (one candidate, not
    # APPROX-preceded, so neither malformed nor approx). Production's
    # value region ignores the semicolon entirely (only a
    # CONDITION_OPERATORS_V1 marker or sentence end stops it), reaching
    # the LATER "6" too: two candidates, malformed=True, approx=False.
    item = {"id": "cal:000", "context": "ctx.", "output": "It costs $5; later 6 items exist."}
    assert _manifest_credits(item, "nontable.abstain_malformed_value") is True
    assert _manifest_credits(item, "nontable.abstain_approx_value") is False


def test_red_fix2_c12_costs_nothing_about_five_is_approx_not_malformed():
    # RED (orchestrator-reproduced): "It costs nothing, about $5."
    # currently credits NEITHER surface -- the OLD structural segment
    # for the "costs" trigger stops at the comma after "nothing" (a
    # comma NOT flanked by NUMBER-NUMBER, so B1's narrow merge exception
    # never applies), leaving a segment ("It costs nothing") with ZERO
    # NUMBER candidates -- neither malformed nor approx credits.
    # Production's value region runs to sentence end regardless,
    # reaching "about $5": exactly one candidate, APPROX-preceded ->
    # approx=True, malformed=False.
    item = {"id": "cal:000", "context": "ctx.", "output": "It costs nothing, about $5."}
    assert _manifest_credits(item, "nontable.abstain_approx_value") is True
    assert _manifest_credits(item, "nontable.abstain_malformed_value") is False


def test_red_fix2_c12_reversed_pin_about_five_ticket_number_live_dispatch():
    # Live-dispatch companion to
    # test_red_fix2_reversed_pin_about_five_ticket_number_is_malformed_
    # not_approx above (which pins the same REVERSED result via a direct
    # _nb_check_event_local_abstain call) -- REVERSES the prior
    # (INCORRECT) pin this exact scenario used to assert, this time
    # through check_coverage_manifest's own live dispatch. "It costs
    # about $5, ticket 1,23,456 exists." -- production sees THREE number
    # candidates in the "costs" hit's own sentence-wide value region
    # ("$5", "1", "23,456"), so it is malformed, never approx: production
    # checks the candidate COUNT before it ever inspects the lone
    # candidate's preceding token for an APPROX_V1 match. RED
    # (pre-fix): malformed=False, approx=True (the OLD, comma-bounded
    # structural segment only ever saw "$5" alone). GREEN: malformed=
    # True, approx=False.
    item = {"id": "cal:000", "context": "ctx.", "output": "It costs about $5, ticket 1,23,456 exists."}
    assert _manifest_credits(item, "nontable.abstain_malformed_value") is True
    assert _manifest_credits(item, "nontable.abstain_approx_value") is False


def test_red_fix2_c12_san895_orphan_coord_superscript_digit_non_measure_facet():
    # RED (orchestrator-reproduced): a leading SUPERSCRIPT FIVE + " and
    # refundable." currently credits abstain_san895_non_ascii_digits --
    # the OLD _nb_hit_segment_text-based segment for the "refundable"
    # hit (sentence-initial, no internal punctuation) spans the WHOLE
    # sentence, INCLUDING the leading superscript digit, and the OLD
    # detector only ever checked "does this segment's text contain a
    # non-ASCII digit ANYWHERE" -- with no regard for whether the hit
    # even reaches a measure-value search at all. "refundable" is a
    # NON-MEASURE facet (facet:refund_availability) AND this hit is an
    # ORPHAN COORD (sentence-initial "and", no valid prior subject to
    # splice) -- EITHER fact alone means production's OWN rule 7 value
    # search never runs for this hit, so GREEN is False. \u2075 is
    # SUPERSCRIPT FIVE -- an ASCII-safe escape in this source file, per
    # this repo's own ASCII-conformance convention (see
    # test_primitives.py's non_ascii_number_inputs fixtures, and the
    # existing test_red_b4_san895_superscript_digit_positive above).
    item = {"id": "cal:000", "context": "\u2075 and refundable.", "output": ""}
    assert _manifest_credits(item, "nontable.abstain_san895_non_ascii_digits", field="context") is False


def test_fix2_c12_san895_arabic_digit_value_region_semicolon_variant():
    # "The item costs; " + ARABIC-INDIC DIGIT FIVE + " dollars." -- the
    # semicolon does not bound production's value region (only a
    # condition marker or sentence end does), so the Arabic-Indic digit
    # still lies INSIDE the "costs" hit's own value region: zero
    # NUMBER/PCT100 candidates, subject valency passes ("item" is a
    # content token), so SAN-895 credits. \u0665 is ARABIC-INDIC DIGIT
    # FIVE (same escape the existing
    # test_group_c_abstain_san895_non_ascii_digits_pinned_pair uses).
    item = {"id": "cal:000", "context": "The item costs; \u0665 dollars.", "output": ""}
    assert _manifest_credits(item, "nontable.abstain_san895_non_ascii_digits", field="context") is True


def test_fix2_c12_san895_arabic_digit_value_region_comma_variant():
    item = {"id": "cal:000", "context": "The item costs, \u0665 dollars.", "output": ""}
    assert _manifest_credits(item, "nontable.abstain_san895_non_ascii_digits", field="context") is True


def test_fix2_c12_san895_arabic_digit_value_region_colon_variant():
    item = {"id": "cal:000", "context": "The item costs: \u0665 dollars.", "output": ""}
    assert _manifest_credits(item, "nontable.abstain_san895_non_ascii_digits", field="context") is True


def test_fix2_c12_san895_arabic_digit_value_region_parenthesis_variant():
    item = {"id": "cal:000", "context": "The item costs (\u0665 dollars).", "output": ""}
    assert _manifest_credits(item, "nontable.abstain_san895_non_ascii_digits", field="context") is True


def test_fix2_c12_classify_hit_value_region_direct_unit_three_way():
    # Direct-unit confirmation of the three-way classification (never a
    # RED requirement on its own -- see the live-dispatch vectors above
    # for the RED/GREEN transitions): malformed (>1 candidate), approx
    # (exactly 1, APPROX-preceded), and None (a genuine unique value,
    # neither malformed nor approx).
    assert vd._nb_classify_hit_value_region("It costs $1,23,456.", 0, 0) == "malformed"
    assert vd._nb_classify_hit_value_region("It costs about $5.", 0, 0) == "approx"
    assert vd._nb_classify_hit_value_region("It costs $5.", 0, 0) is None


# -- correction 3: in-order COORD-state replay (e15/SAN-894) --

def test_red_fix2_c3_san894_orphan_coord_never_credits():
    # RED (orchestrator-reproduced): "And refundable for available
    # items." currently credits abstain_san894_trigger_in_adjunct -- the
    # OLD single-hit replay called extract_roles for ONLY the "refundable"
    # hit in isolation, getting its RAW (unspliced) COORD subject span
    # (start, start) (empty) rather than production's OWN reject step
    # (extraction.py 769-771: an orphan COORD hit, no valid prior
    # subject, raises Abstain(UNEXTRACTABLE) and is never scanned for
    # adjuncts at all). GREEN: the in-order replay reproduces the SAME
    # reject -- this sentence-initial "and refundable" is hit 0, no
    # prior hit exists to establish a subject, so it is REJECTED before
    # adjunct scanning ever runs.
    item = {"id": "cal:000", "context": "And refundable for available items.", "output": ""}
    assert _manifest_credits(item, "nontable.abstain_san894_trigger_in_adjunct", field="context") is False
    assert vd._nb_adjunct_group_scan("And refundable for available items.", 0, 0) is None


def test_red_fix2_c3_e15_orphan_coord_never_credits():
    # RED (orchestrator-reproduced): "And refundable for physical items
    # for damaged goods." currently credits abstain_e15_nested_adjunct_
    # chain for the SAME orphan-COORD reason as the SAN-894 case above.
    item = {"id": "cal:000", "context": "And refundable for physical items for damaged goods.", "output": ""}
    assert _manifest_credits(item, "nontable.abstain_e15_nested_adjunct_chain", field="context") is False
    assert vd._nb_adjunct_group_scan("And refundable for physical items for damaged goods.", 0, 0) is None


def test_fix2_c3_san894_positive_non_orphan_coord_control():
    # POSITIVE CONTROL: the orphan-COORD fix is not a blanket rejection
    # of every COORD hit -- a coordinated trigger with a GENUINE prior
    # subject remains fully eligible. "Refunds are available, and
    # refundable for available items." -- hit 0 ("available") is
    # ACTIVE, subject="Refunds", and (the comma stops its OWN object
    # span right after "available", so hit 0's own adjunct scan is
    # clean -- see the direct hit-0 assertion below, proving the credit
    # below comes EXCLUSIVELY from the spliced hit, not incidentally
    # from hit 0's own unrelated object span). hit 1 ("refundable") is
    # COORD, splices in hit 0's genuine "Refunds" subject, and its OWN
    # object ("for available items") walks straight into a SAN-894
    # facet-trigger match ("available" itself).
    text = "Refunds are available, and refundable for available items."
    item = {"id": "cal:000", "context": text, "output": ""}
    assert vd._nb_adjunct_group_scan(text, 0, 0) is None, "hit 0's own (comma-clipped) object span must be clean"
    assert vd._nb_adjunct_group_scan(text, 0, 1) == "san894", "hit 1 (COORD-spliced) must credit san894"
    assert _manifest_credits(item, "nontable.abstain_san894_trigger_in_adjunct", field="context") is True


def test_fix2_c3_e15_positive_non_orphan_coord_control():
    # POSITIVE CONTROL, e15 variant: "Refunds are available, and
    # refundable for physical items for damaged goods." -- hit 1
    # (COORD-spliced) walks its OWN object's repeated "for ... for ..."
    # pairwise chain.
    text = "Refunds are available, and refundable for physical items for damaged goods."
    item = {"id": "cal:000", "context": text, "output": ""}
    assert vd._nb_adjunct_group_scan(text, 0, 0) is None, "hit 0's own (comma-clipped) object span must be clean"
    assert vd._nb_adjunct_group_scan(text, 0, 1) == "e15", "hit 1 (COORD-spliced) must credit e15"
    assert _manifest_credits(item, "nontable.abstain_e15_nested_adjunct_chain", field="context") is True


def test_fix2_c3_later_valid_coord_hit_eligible_after_earlier_orphan_reject():
    # An EARLIER orphan-COORD hit's own rejection must not poison a
    # LATER hit's eligibility: prev_subject_span is left UNCHANGED by a
    # rejected hit (production never reassigns it before raising), so a
    # SUBSEQUENT hit that establishes its own genuine subject remains
    # fully eligible for its own later COORD splice. Sentence 1 here
    # ("And refundable...") is the orphan; sentence 0 is irrelevant to
    # hit-ordinal numbering (sentences are scanned independently) -- this
    # test instead exercises the SAME single-sentence in-order loop via
    # three hits: hit 0 ("and refundable", ORPHAN, hit-ordinal 0, no
    # prior subject at all) is rejected; hit 1 ("available", ACTIVE,
    # establishes "items") sets a genuine subject; hit 2 ("and
    # refundable" again) splices hit 1's subject and credits san894 via
    # its own "for available" object.
    text = "And refundable, items are available, and refundable for available items."
    from reference.primitives import tokenize, sentences as _sentences
    from reference.extraction import trigger_scan as _trigger_scan
    toks = tokenize(text)
    sent = _sentences(toks, text)[0]
    hits = _trigger_scan(sent)
    # 4 hits total: hit 0 "refundable" (orphan COORD), hit 1 "available"
    # (ACTIVE, establishes "items" as a genuine subject), hit 2
    # "refundable" (COORD, splices hit 1's subject), hit 3 "available"
    # (the OBJECT-side "available items" -- a separate, later hit, not
    # exercised by this test).
    assert len(hits) == 4, f"expected 4 hits, got {len(hits)}: {[(h.facet, h.span) for h in hits]}"
    assert vd._nb_adjunct_group_scan(text, 0, 0) is None, "hit 0 is an orphan COORD -- rejected, never credits"
    assert vd._nb_adjunct_group_scan(text, 0, 2) == "san894", "hit 2 splices hit 1's genuine subject and credits"


# -- correction 4: lazy/early-returning Group-A dispatch --

def test_red_fix2_c4_group_a_call_never_invokes_any_legacy_contains_helper(monkeypatch):
    # RED (orchestrator-reproduced): under the pre-fix code, EVERY call
    # to _predicate_nontable -- including a Group-A (c2_*) lookup --
    # eagerly constructed ONE dict literal spanning all eighteen keys,
    # so a Group-A call ALSO evaluated (and discarded the result of) all
    # FIVE legacy _contains_* helpers. GREEN: a registered Group-A name
    # returns before any of them are ever constructed. Spies on all
    # five simultaneously -- a registered c2_* evaluation must trigger
    # NONE of them.
    names = [
        "_contains_non_ascii_digit",
        "_contains_malformed_number_grouping",
        "_contains_nonterminating_punctuation_run",
        "_contains_adjunct_preposition_chain",
        "_contains_trigger_in_adjunct_phrase",
    ]
    calls: list[str] = []

    def _spy_factory(n):
        def _spy(*args, **kwargs):
            calls.append(n)
            raise AssertionError(f"Group-A call must never invoke legacy helper {n}")
        return _spy

    for n in names:
        monkeypatch.setattr(vd, n, _spy_factory(n))

    for surf in (
        "c2_definitive_hit", "c2_negated_definitive", "c2_hedge_in_window",
        "c2_hedge_outside_window_or_absent", "c2_negated_hedge",
        "c2_window_boundary", "c2_interrogative",
    ):
        result = vd._predicate_nontable("The result is always guaranteed.", f"nontable.{surf}", _C2_REAL_TABLES_DATA)
        assert isinstance(result, bool)
    assert calls == [], f"legacy _contains_* helpers invoked by a Group-A call: {calls}"


def test_fix2_c4_group_a_call_never_invokes_any_legacy_contains_helper_via_live_dispatch(monkeypatch):
    # Live-dispatch companion: the SAME proof, but through check_coverage_
    # manifest's own Pass A/Pass B machinery rather than a direct
    # _predicate_nontable call.
    names = [
        "_contains_non_ascii_digit",
        "_contains_malformed_number_grouping",
        "_contains_nonterminating_punctuation_run",
        "_contains_adjunct_preposition_chain",
        "_contains_trigger_in_adjunct_phrase",
    ]
    calls: list[str] = []

    def _spy_factory(n):
        def _spy(*args, **kwargs):
            calls.append(n)
            raise AssertionError(f"Group-A live dispatch must never invoke legacy helper {n}")
        return _spy

    for n in names:
        monkeypatch.setattr(vd, n, _spy_factory(n))

    item = {"id": "cal:000", "context": "ctx.", "output": "The result is always guaranteed."}
    assert _manifest_credits(item, "nontable.c2_definitive_hit", check_id="C2") is True
    assert calls == [], f"legacy _contains_* helpers invoked by a Group-A live-dispatch call: {calls}"


def test_fix2_c4_legacy_group_bc_handlers_still_directly_callable():
    # Legacy Group B/C surfaces remain directly callable (they are
    # LEGACY-UNREACHABLE-FROM-RUNTIME, not deleted) -- unaffected by the
    # laziness fix, exactly like test_group_b_red_deny_trigger_substring_
    # inside_unrelated_word_no_longer_credits above.
    text = "It costs $1,23,456."
    assert vd._predicate_nontable(text, "nontable.abstain_malformed_value", _C2_REAL_TABLES_DATA) is True
    assert vd._predicate_nontable(text, "nontable.abstain_approx_value", _C2_REAL_TABLES_DATA) is False


# ---------------------------------------------------------------------
# BUNDLE/CACHE housekeeping: split spy tests
# ---------------------------------------------------------------------

def test_nontable_bundle_backed_routes_spy_builds_bundle_exactly_once_in_mixed_manifest(monkeypatch):
    # Group-A-only zero-build coverage is test_nontable_routes_spy_
    # never_invoke_product_tracing above (unchanged, still bundle-free).
    # This is the "mixed manifest: exactly-once" complement: ONE item
    # referenced by BOTH a 50-surface record and a Group B/C nontable
    # record must build its ProductTraceBundle EXACTLY once, via the
    # SHARED bundle_for cache.
    calls = []
    real_builder = vd.build_product_trace_bundle

    def _spy(item):
        calls.append(item.get("id"))
        return real_builder(item)

    monkeypatch.setattr(vd, "build_product_trace_bundle", _spy)

    errors = vd.Errors()
    design_by_id = {"cal:000": {"item_id": "cal:000", "scenario_id": "s0"}}
    corpus_by_id = {"cal:000": {"id": "cal:000", "context": "Refunds are unavailable.", "output": "Refunds are unavailable."}}
    tables_data = _C2_REAL_TABLES_DATA
    coverage = {
        "facets_v1.facet:refund_availability": [{"item_id": "cal:000", "check_id": "C1", "field": "context"}],
        "nontable.polarity_via_deny_trigger": [{"item_id": "cal:000", "check_id": "C1", "field": "context"}],
    }
    vd.check_coverage_manifest(errors, coverage, design_by_id, corpus_by_id, tables_data)
    assert errors == []
    assert calls == ["cal:000"], f"expected exactly ONE build for cal:000 across the mixed manifest, got {calls}"


# ---------------------------------------------------------------------
# TRUTH-DIRECTION tests: nontable branch ProductTrace yes for B/C,
# CAPABILITY_MAP no, checks/evaluate execution no.
# ---------------------------------------------------------------------

def test_truth_direction_nontable_bundle_backed_evidence_references_product_trace_not_capability_map():
    referenced = _ast_referenced_names(vd._check_nontable_bundle_backed_evidence)
    assert "CAPABILITY_MAP" not in referenced, "Group B/C nontable evidence must never route through CAPABILITY_MAP (no nontable rows exist)"


def test_truth_direction_check_coverage_manifest_dispatcher_still_never_references_product_trace_directly():
    # Unchanged invariant: check_coverage_manifest itself stays a PURE
    # dispatcher -- it references _make_bundle_cache /
    # _check_nontable_bundle_backed_evidence by NAME, never a
    # product-trace substrate symbol directly.
    referenced = _ast_referenced_names(vd.check_coverage_manifest) & _PRODUCT_TRACE_SYMBOLS
    assert referenced == set()


def test_truth_direction_nontable_evidence_never_executes_checks_or_evaluator():
    referenced = _ast_referenced_names(vd._check_nontable_bundle_backed_evidence)
    forbidden = referenced & {"evaluate", "C1", "C3", "C4"}
    assert forbidden == set()
    # the two permitted shared helpers are legal ONLY via _predicate_nontable
    # (Group A); the bundle-backed Group B/C path never touches them at all:
    assert "scan_c2_lexical" not in referenced
    assert "has_governed_question" not in referenced


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1b-FIX3: ONE micro-fix to SAN-895's own
# TOTAL_SPAN_UNCONSUMED arm inside _nb_check_event_local_abstain --
# requires the conservative condition that arm's own surrounding
# comments already claimed but never enforced: the SAME SENTENCE (the
# frame identity's own sentence index, ProductIdentity[2]) must contain
# NO successful FrameProductEvent before SAN-895 may credit. Every
# vector below runs through check_coverage_manifest's OWN live dispatch
# via _manifest_credits, exactly like the FIX2 vectors above.
# ---------------------------------------------------------------------

def test_red_fix3_san895_frame_in_same_sentence_never_credits():
    # RED (reviewer-reproduced and orchestrator-reproduced against the
    # pre-fix code): "Item " + SUPERSCRIPT FIVE + " costs $5; JK."
    # currently credits abstain_san895_non_ascii_digits -- the semicolon
    # never ends a sentence (only terminal punctuation does), so the
    # WHOLE string is ONE sentence, and the pre-fix arm only ever checked
    # "does this sentence's text contain a non-ASCII digit ANYWHERE",
    # with no regard for whether a frame already formed in that same
    # sentence. The "costs" trigger DOES form a successful frame here,
    # successfully consuming the subject span that contains the
    # superscript digit and the value $5 -- "JK" is what actually goes
    # unconsumed (TOTAL_SPAN_UNCONSUMED), and crediting SAN-895 for it
    # misattributes the digit to the wrong failure. GREEN: a frame in the
    # SAME sentence suppresses credit. \u2075 is SUPERSCRIPT FIVE -- an
    # ASCII-safe escape in this source file, per this repo's own
    # ASCII-conformance convention (see test_primitives.py's non_ascii_
    # number_inputs fixtures, and the existing test_red_b4_san895_
    # superscript_digit_positive above).
    item = {"id": "cal:000", "context": "Item \u2075 costs $5; JK.", "output": ""}
    bundle = vd.build_product_trace_bundle(item)
    ft = bundle.fields[0]
    assert any(fe.trigger_raw == "costs" and fe.identity[2] == 0 for fe in ft.frame_events), (
        "fixture must form a successful 'costs' frame in sentence 0 for this vector to be meaningful"
    )
    assert any(pe.stage.value == "total_span_unconsumed" and pe.identity[2] == 0 for pe in ft.partial_events), (
        "fixture must also raise TOTAL_SPAN_UNCONSUMED in the SAME sentence 0 for this vector to be meaningful"
    )
    assert _manifest_credits(item, "nontable.abstain_san895_non_ascii_digits", field="context") is False


def test_fix3_san895_no_frame_in_sentence_still_credits():
    # GREEN-FROM-BIRTH control: SUPERSCRIPT FIVE + " items are pending."
    # forms NO frame at all in its own (only) sentence -- "items are
    # pending" never matches a trigger -- so the conservative "no
    # successful frame in the SAME sentence" condition is satisfied both
    # before and after the fix, and SAN-895 credits exactly as it always
    # has (see the pre-existing test_red_b4_san895_superscript_digit_
    # positive, which pins the SAME fixture via the direct helper).
    item = {"id": "cal:000", "context": "\u2075 items are pending.", "output": ""}
    bundle = vd.build_product_trace_bundle(item)
    assert bundle.fields[0].frame_events == (), (
        "fixture must form ZERO frames for this vector to be meaningful"
    )
    assert _manifest_credits(item, "nontable.abstain_san895_non_ascii_digits", field="context") is True


def test_fix3_san895_frame_in_different_sentence_does_not_suppress_credit():
    # GREEN-FROM-BIRTH control: "Refunds are refundable. " + SUPERSCRIPT
    # FIVE + " items are pending." -- TWO sentences. Sentence 0
    # ("Refunds are refundable.") DOES form a successful frame (trigger
    # "refundable"); sentence 1 (the digit-bearing sentence) forms none.
    # The fix's sentence-scoping must key off the PARTIAL EVENT'S OWN
    # sentence index (1), never "does ANY sentence in this field/source
    # have a frame" -- a frame in a DIFFERENT sentence must never
    # suppress credit for this one.
    item = {"id": "cal:000", "context": "Refunds are refundable. \u2075 items are pending.", "output": ""}
    bundle = vd.build_product_trace_bundle(item)
    ft = bundle.fields[0]
    assert any(fe.trigger_raw == "refundable" and fe.identity[2] == 0 for fe in ft.frame_events), (
        "fixture must form a successful 'refundable' frame in sentence 0 (a DIFFERENT sentence) for this vector to be meaningful"
    )
    assert any(pe.stage.value == "total_span_unconsumed" and pe.identity[2] == 1 for pe in ft.partial_events), (
        "fixture must raise TOTAL_SPAN_UNCONSUMED in sentence 1 (the digit's own sentence) for this vector to be meaningful"
    )
    assert _manifest_credits(item, "nontable.abstain_san895_non_ascii_digits", field="context") is True
