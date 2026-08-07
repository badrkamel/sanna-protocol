#!/usr/bin/env python3
"""SAN-881 calibration corpus validator.

Public artifacts (corpus_inputs.json, evaluation_profile.json, the
schemas/, commitment.json) are always validated, including a from-disk
recomputation of labeling_context_hash -- the envelope's own component
list is NEVER trusted; every component is re-read and re-hashed off the
filesystem on every run. Sealed artifacts (design_metadata.json,
labels_author_semantic.json, labels_author_contract.json,
coverage_manifest.json) are validated ONLY when --sealed-dir points at a
local directory containing them -- this is how the author validates
privately before sealing (README workflow step 5), and how a later
commit/reveal step re-validates against the sealed staging copy.
Reviewer artifacts (labels_reviewer_semantic.json,
labels_reviewer_contract.json + their .commitment.json envelopes) are
validated when --reviewer-dir is supplied. This script never runs a
full evaluator pass (reference.evaluate.evaluate(), or the TypeScript
port) over any corpus item, and never records, publishes, or gates on
an evaluator OUTCOME.

SAN-881 PASS 2B.1-T built an EPHEMERAL, TYPED, validator-local
product-trace substrate (FieldProductTrace / FrameProductEvent /
PartialProductEvent / ProductTraceBundle, see the "Product trace
substrate" section below) that replays the pinned production
extraction primitives (never extract_frames itself, never the
production frame counter) over public corpus text to capture exact
per-field frame/partiality PRODUCTS. SAN-881 PASS 2B.1-P wires this
substrate into check_coverage_manifest for the 50 IN-SCOPE surfaces (47
table-derived + the 3 value_role_v1 surfaces) via CAPABILITY_MAP: a
closed, reviewed STATIC routing declaration ((family, location) ->
legal (check_id, field) positions) -- a reviewed static compatibility
declaration, never a dynamically inferred consumption proof -- plus a
FOUR-CLAUSE product contract
per evidence record -- POSITION (SURFACE_REGISTRY.allowed_positions,
unchanged), PRODUCT PRESENT (the declared field's FieldProductTrace(s)
contain the exact normalized product, family-specifically located),
NON-PARTIAL (every FieldProductTrace belonging to the declared field
is nonpartial, with quant_v1.abstain's PER_HIT_ABSTAIN as the sole
documented exception), and CHECK-APPLICABLE (CAPABILITY_MAP[(family,
location)] contains (check_id, field)) -- plus OWNERSHIP QUALIFIERS
(assertive frame ownership; tier_1/tier_2 authoritative context for
ordinary C1/C4; trusted-obligations membership for C3/context;
EvidenceProductEvent backing for C3/output condition/requirement
claims). SAN-881 PASS 2B.1b upgraded the 18 NONTABLE surfaces to
product-honest, event-local proof, split into three groups (see
_check_nontable_surface_evidence, _check_nontable_bundle_backed_
evidence, and their own AST-isolation truth tests). GROUP A (the seven
c2_* surfaces) is bundle-free: it consumes reference.checks.
scan_c2_lexical / has_governed_question, the SAME shared helpers
checks.C2 and evaluate.py's own Stage W1 gate consume, over the
declared field's own re-tokenized text -- a static-lexical scan that
never calls evaluate() and never builds a ProductTraceBundle. GROUPS B
({polarity_via_deny_trigger, polarity_via_negator, contraction_
expansion}) and C (abstain_interrogative_output and the remaining
seven abstention surfaces) ARE ProductTraceBundle-backed, EVENT-LOCAL
evidence (mechanism detector and PartialProductEvent co-located within
the SAME FieldProductTrace/source AND sentence), sharing ONE
Pass-B-wide bundle cache with the 50 in-scope surfaces below, but
reusing ONLY the ordinary ownership/nonpartial portion of the
four-clause contract -- nontable surfaces are NEVER routed through
CAPABILITY_MAP, which has no nontable rows. The five _contains_*
lexical helpers, _word_present, _field_text, and the eleven Group B/C
handler expressions inside _predicate_nontable itself remain
BYTE-UNCHANGED. SAN-881 PASS 2B.1b-FIX2 made _predicate_nontable's own
dispatch LAZY/early-returning: a registered Group A (c2_*) name now
returns before the eleven Group B/C expressions are ever constructed,
so those eleven -- like the eight dead non-nontable COVERAGE_PREDICATES
entries this module already carries -- are LEGACY-UNREACHABLE-FROM-
RUNTIME (no live check_coverage_manifest dispatch path ever evaluates
their code at all; they remain directly callable/tested only). This is
NOT consumption tracing in any form: no
CheckConsumptionTrace class, no runtime monkeypatching of production
code, no event vocabulary, no locks/phase-state/call-attribution, and
no replay of a check's own branch against a real outcome -- that
architecture was proposed and REJECTED; it does not exist and must
never be reintroduced.

HONEST ASSURANCE: Runtime validation proves parsed-product presence,
ownership and partiality qualifiers, declared-field integrity, and
compatibility with a reviewed static routing map. It does not prove
internal branch reach, causality, or per-corpus-item execution. Phase
B evaluator runs remain the authority for measured behavior.

No trace built by this substrate is ever
persisted, published, or used to compute a rate or a gate. Every other
check here is either a JSON Schema validation or a structural /
cryptographic consistency check over already-authored bytes.

Error-output discipline: every error string emitted by this module may
contain ONLY an artifact name, a record index, an item_id/check_id, and
a fixed RULE_* code -- never sealed prose (semantic_truth,
contract_tuple values, rationale, competence, severity, advisory, scenario
text), nonce material, or artifact bytes. See RULE_* constants below.

Usage:
    python3 reference/calibration/validate_design.py [--sealed-dir DIR]
        [--nonces-file FILE] [--reviewer-dir DIR] [--reviewer-nonces-file FILE]

Exit code 0 = all checks green. Nonzero = at least one check failed;
every failure is printed with enough detail to locate (never disclose)
the problem.
"""
from __future__ import annotations

import argparse
import dataclasses
import enum
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any, Callable, FrozenSet, Tuple

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - CI pins jsonschema; keep a clear message locally
    Draft202012Validator = None

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
SCHEMAS = HERE / "schemas"

# `reference` is only importable when REPO_ROOT is on sys.path. Direct
# invocation (`python3 reference/calibration/validate_design.py`, as
# documented in README.md's verifier commands) puts this file's OWN
# directory on sys.path[0], NOT the repo root -- `import reference...`
# would silently fail there. Fix sys.path BEFORE the primitives import so
# the pinned tokenizer/fold primitive is available regardless of how this
# script is invoked (direct path, `python3 -m`, or package import from
# tests) -- a silent ImportError fallback here previously caused every
# feature-absence and minimal-pair-semantics check to silently no-op when
# run exactly as the README instructs.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from reference.primitives import fold_sequence  # noqa: E402 -- pinned tokenizer/fold primitive only, NEVER the evaluator

# base_commit_sha this corpus's labeling_context_hash is anchored to (the
# commit at which the public Phase-A files this context binds were
# frozen). A fixed pin, not derived via `git rev-parse` at validation
# time, so the context hash is reproducible independent of local git state.
BASE_COMMIT_SHA = "c185daa4042f7be562df6632197c4ed9e11474d9"

SCHEMA_FILES = (
    "commitment_schema.json",
    "coverage_manifest_schema.json",
    "design_metadata_schema.json",
    "freeze_manifest_schema.json",
    "labels_schema.json",
    "reveal_verification_ledger_schema.json",
)

CHECK_IDS = ("C1", "C2", "C3", "C4")
STRATA = (
    "in_domain_nonviolation",
    "in_domain_violation",
    "determinate_out_of_domain",
    "indeterminate_or_unsafe",
)

# Single shared corpus-version pin. Every corpus_version check (evaluation
# profile, commitment envelope, freeze manifest schema) drives off this ONE
# constant -- SAN-881 Phase-A correction. The v1 files committed alongside
# this correction (corpus_inputs.json, evaluation_profile.json,
# commitment.json) are INTENTIONALLY left at corpus_version 1: they are
# abandoned by this correction (see README.md abandonment rule) and are
# expected to fail the checks below until a full v2 reseal (fresh nonces,
# recomputed commitments, corpus_version bumped in the sealed workflow)
# restores a green run. See test_calibration.py's TRANSITIONAL tests.
EXPECTED_CORPUS_VERSION = 2

# Full locked outcome/outcome_reason matrix -- ONE shared definition
# consumed by check_labels() below AND (via import) by measure.py's live
# tuple-consistency check, so authored-label validation and measurement
# validation can never drift apart. PASS and VIOLATION share the same
# reason set (both are "the evaluator reached a decided verdict");
# NOT_EVALUATED covers every abstention/no-attempt class; EVALUATOR_ERROR
# is a runtime crash; CONFIG_ERROR is a bad invocation/configuration --
# both error outcomes are hard failures for the zero_evaluator_errors gate.
REASON_MATRIX: dict[str, frozenset[str]] = {
    "PASS": frozenset({"detection_complete"}),
    "VIOLATION": frozenset({"detection_complete"}),
    "NOT_EVALUATED": frozenset({
        "advisory_only", "manual_required", "input_empty", "context_disabled",
        "attestation_missing", "attestation_invalid", "applicability_mismatch",
        "envelope_exceeded", "scan_incomplete", "basis_incomplete",
        "basis_unclassified", "basis_empty", "basis_conflict",
        "identity_ambiguous", "condition_undecidable", "unsupported_claim_form",
        "extraction_partial",
    }),
    "EVALUATOR_ERROR": frozenset({"evaluator_exception", "dependency_unavailable"}),
    "CONFIG_ERROR": frozenset({
        "malformed_structured_input", "dynamic_config_rejected", "runtime_binding_missing",
    }),
}
CLOSED_OUTCOMES = frozenset(REASON_MATRIX)
OUTCOME_REASONS = frozenset().union(*REASON_MATRIX.values())

SEMANTIC_TO_OUTCOME = {
    "NO_VIOLATION": "PASS",
    "VIOLATION": "VIOLATION",
    "INDETERMINATE": "NOT_EVALUATED",
}
DOMAIN_SEPARATOR = b"sanna-calibration-commitment/1"

# SAN-881 PASS-1 CORRECTION ROUND, Section F: the single source of truth
# for commitmentAlgorithm.formula, consumed by BOTH commitment.json (the
# real, committed value) and schemas/commitment_schema.json (pinned as a
# const, SAN-881 PASS-1 CORRECTION ROUND) -- never restated as a second,
# independently-typo-able literal.
COMMITMENT_ALGORITHM_FORMULA = (
    "SHA256(domain_separator || NUL || artifact_name || NUL || raw_32_byte_nonce"
    " || raw_32_byte_labeling_context_hash || exact_artifact_bytes)"
)

AUTHOR_ARTIFACT_NAMES = {
    "design_metadata.json", "labels_author_semantic.json",
    "labels_author_contract.json", "coverage_manifest.json",
}
REVIEWER_SEMANTIC_ARTIFACT = "labels_reviewer_semantic.json"
REVIEWER_CONTRACT_ARTIFACT = "labels_reviewer_contract.json"
REVIEWER_SEMANTIC_COMMITMENT_FILE = "labels_reviewer_semantic.commitment.json"
REVIEWER_CONTRACT_COMMITMENT_FILE = "labels_reviewer_contract.commitment.json"

# The literal, pinned author_commitments ORDER (SAN-881 Phase-A correction
# item 4): commitment.json's author_commitments array must contain
# EXACTLY these four artifact names, in this exact index order. Mirrored
# index-by-index in commitment_schema.json's authorEnvelope.author_commitments
# prefixItems pin; check_author_commitment_order below is the belt to that
# schema's suspenders (fires even when jsonschema is unavailable, or when
# a same-name/different-hash duplicate happens to still satisfy the
# older, order-blind set-based check_commitment check).
AUTHOR_COMMITMENT_ORDER: tuple[str, ...] = (
    "design_metadata.json",
    "labels_author_semantic.json",
    "labels_author_contract.json",
    "coverage_manifest.json",
)

# Exact bundle-content contract per reveal stage (SAN-881 Phase-A
# correction item 1): the DIRECTORY CONTENTS of --sealed-dir and
# --reviewer-dir must equal these sets EXACTLY -- not merely "contains
# at least" -- for a staged reveal. Any file not in the relevant set
# (missing, extra, opposite-stage, or an arbitrary unrecognized name) is
# a hard rejection. --nonces-file / --reviewer-nonces-file are NOT bundle
# members and are never checked against these sets (their PARENT
# directory is not scanned by this check at all).
SEMANTIC_SEALED_BUNDLE_ALLOWED = frozenset({"labels_author_semantic.json"})
SEMANTIC_REVIEWER_BUNDLE_ALLOWED = frozenset({REVIEWER_SEMANTIC_ARTIFACT, REVIEWER_SEMANTIC_COMMITMENT_FILE})
CONTRACT_SEALED_BUNDLE_ALLOWED = frozenset({"labels_author_contract.json", "design_metadata.json", "coverage_manifest.json"})
CONTRACT_REVIEWER_BUNDLE_ALLOWED = frozenset({REVIEWER_CONTRACT_ARTIFACT, REVIEWER_CONTRACT_COMMITMENT_FILE})

# Exact nonce-map KEYSET contract per stage (companion to the bundle-
# content contract above): --nonces-file / --reviewer-nonces-file must
# have EXACTLY these keys -- a missing key, an extra key, an
# opposite-stage key, or a key overlapping the OTHER side's own artifact
# name (a reviewer nonce map key attempting to name an author artifact,
# or vice versa) is a hard rejection, independent of whether the
# corresponding bundle file even exists on disk.
SEMANTIC_AUTHOR_NONCE_KEYS = frozenset({"labels_author_semantic.json"})
SEMANTIC_REVIEWER_NONCE_KEYS = frozenset({REVIEWER_SEMANTIC_ARTIFACT})
CONTRACT_AUTHOR_NONCE_KEYS = frozenset({"labels_author_contract.json", "design_metadata.json", "coverage_manifest.json"})
CONTRACT_REVIEWER_NONCE_KEYS = frozenset({REVIEWER_CONTRACT_ARTIFACT})

# Semantic-stage subset reveal: only these may be revealed; the rest of
# the author's declared artifacts may remain sealed, and any of the
# EXTRA names below being supplied anyway is a hard rejection (contract
# reasoning / design metadata / coverage evidence must never leak into
# semantic adjudication).
SEMANTIC_STAGE_ALLOWED = {"labels_author_semantic.json", REVIEWER_SEMANTIC_ARTIFACT}
SEMANTIC_STAGE_FORBIDDEN_EXTRAS = {
    "design_metadata.json", "labels_author_contract.json",
    "coverage_manifest.json", REVIEWER_CONTRACT_ARTIFACT,
}

# Contract-stage subset reveal (workflow step 6, STRICTLY AFTER semantic
# adjudication is frozen): the four remaining artifacts -- author contract
# labels, design metadata, coverage manifest, reviewer contract labels.
# Mirrors LEDGER_PINNED_TUPLES' four (*, *, "contract") entries exactly.
CONTRACT_STAGE_ALLOWED = {
    "design_metadata.json", "labels_author_contract.json",
    "coverage_manifest.json", REVIEWER_CONTRACT_ARTIFACT,
}
CONTRACT_STAGE_FORBIDDEN_EXTRAS = {"labels_author_semantic.json", REVIEWER_SEMANTIC_ARTIFACT}

# ---------------------------------------------------------------------
# Pre-registered, closed, DECLARATIVE coverage-surface registry --
# operator-ratified Coverage Routing Matrix v3 (SAN-881 CORRECTION PASS
# 2). surface -> {allowed_positions, predicate_id}.
#
# EXACTLY 68 surfaces, closed by construction: coverage_manifest.json's
# top-level key set must equal this registry's key set EXACTLY (a
# missing key or an extra key both fail -- see check_coverage_manifest).
# The registry is pre-registered and static, not recomputed from
# ALGORITHM-v4-tables-v1.json at validation time, so a future table edit
# cannot silently widen or narrow what counts as a valid surface without
# a reviewed registry change.
#
# allowed_positions REPLACES the Pass-1 allowed_checks x allowed_fields
# cartesian pair (SAN-881 CORRECTION PASS 2): a set of explicit
# (check_id, field) PAIRS. The cartesian form could not describe a
# forbidden pair whose components are each individually legal elsewhere
# (e.g. value_role_v1.cost is legal at (C1, output) and at (C3, context)
# but NOT at (C3, output) -- a cartesian allowed_checks={C1,C3} x
# allowed_fields={context,output} would wrongly accept (C3, output) too).
#
# Derivation (cross-checked against reference/spec/ALGORITHM-v4-tables-v1.json):
#   - facets_v1: one surface per facet family (10).
#   - concept_v1: one surface per distinct canonical concept value (5:
#     approval, verification, authorization, confirmation, registration).
#   - comparators_v1: one surface per comparator entry (10), keyed by its
#     tokens joined with "_" (matches _predicate_comparators's own
#     token-join comparison).
#   - excl_v1: one surface per pair (4 -- refundable_nonrefundable is
#     RETIRED under v3, not a valid coverage surface).
#   - complement_v1: one surface per pair (5).
#   - condition_operators_v1: one surface per entry (10), keyed
#     "<tokens joined with _>.<kind>.<force>".
#   - quant_v1: one surface per quantifier class (3: universal, existential,
#     abstain).
#   47 table-derived = 10 + 5 + 10 + 4 + 5 + 10 + 3.
#   Every table-derived surface's allowed_positions is the SAME fixed set,
#   {C1,C3,C4} x {context,output} (6 positions) -- table-derived surfaces
#   are NEVER legal C2 evidence (definitive/hedge calibration is the only
#   C2-scoped semantics, and it is nontable, see below).
#
#   - value_role_v1.{cost,duration,limit}: 3 SYNTHETIC (not table-derived)
#     measure-facet value-role surfaces, replacing Pass-1's
#     units_v1.facet:* naming. allowed_positions is the fixed 3-element
#     set {(C1,context),(C1,output),(C3,context)} -- NOT (C3,output) and
#     NOT any C4 position. See _predicate_value_role.
#
#   - nontable: a small explicit inventory of non-table-derived behavioral
#     surfaces (18), matching _predicate_nontable's handler keys exactly:
#       * the seven c2_* surfaces: {(C2,output)} only.
#       * polarity_via_deny_trigger, polarity_via_negator, and the seven
#         abstention surfaces (abstain_quant_abstain, abstain_malformed_value,
#         abstain_e15_nested_adjunct_chain, abstain_san894_trigger_in_adjunct,
#         abstain_san895_non_ascii_digits, abstain_e13_nonterminating_punctuation,
#         abstain_approx_value): the same table-family 6-position set,
#         {C1,C3,C4} x {context,output}.
#       * contraction_expansion: the 6-position set PLUS (C2,output).
#       * abstain_interrogative_output: {C1,C3,C4} x {output} only (3
#         positions; NOT context). One '?' item may evidence BOTH
#         c2_interrogative (C2,output) and abstain_interrogative_output
#         ((C1|C3|C4),output) -- these are two independent surfaces, not
#         a conflict.
#   47 + 3 + 18 = 68.
#   Total allowed positions: 47*6 + 3*3 + (7*1 + 2*6 + 7*6 + 1*7 + 1*3)
#   = 282 + 9 + 71 = 362.
_C2_ONLY_NONTABLE = frozenset({
    "c2_definitive_hit", "c2_negated_definitive", "c2_hedge_in_window",
    "c2_hedge_outside_window_or_absent", "c2_negated_hedge",
    "c2_window_boundary", "c2_interrogative",
})
_NONTABLE_TABLE_FAMILY_POSITION_NAMES = frozenset({
    "polarity_via_deny_trigger", "polarity_via_negator",
    "abstain_quant_abstain", "abstain_malformed_value",
    "abstain_e15_nested_adjunct_chain", "abstain_san894_trigger_in_adjunct",
    "abstain_san895_non_ascii_digits", "abstain_e13_nonterminating_punctuation",
    "abstain_approx_value",
})
_NONTABLE_SURFACE_NAMES = (
    "c2_definitive_hit", "c2_negated_definitive", "c2_hedge_in_window",
    "c2_hedge_outside_window_or_absent", "c2_negated_hedge",
    "c2_window_boundary", "c2_interrogative", "polarity_via_deny_trigger",
    "polarity_via_negator", "contraction_expansion",
    "abstain_interrogative_output", "abstain_quant_abstain",
    "abstain_malformed_value", "abstain_e15_nested_adjunct_chain",
    "abstain_san894_trigger_in_adjunct", "abstain_san895_non_ascii_digits",
    "abstain_e13_nonterminating_punctuation", "abstain_approx_value",
)
_ALL_CHECKS = frozenset(CHECK_IDS)
_ALL_FIELDS = frozenset({"context", "output"})

# The fixed 6-position set shared by every table-derived surface (and by
# most nontable surfaces): {C1,C3,C4} x {context,output}. C2 is NEVER a
# legal position for a table-derived surface.
_TABLE_POSITIONS: frozenset[tuple[str, str]] = frozenset(
    (c, f) for c in ("C1", "C3", "C4") for f in ("context", "output")
)
# value_role_v1's fixed 3-position set: (C1,context), (C1,output),
# (C3,context) only -- NOT (C3,output), NOT any C4 position.
_VALUE_ROLE_POSITIONS: frozenset[tuple[str, str]] = frozenset({
    ("C1", "context"), ("C1", "output"), ("C3", "context"),
})
# The single-position set shared by every c2_* nontable surface.
_C2_OUTPUT_ONLY: frozenset[tuple[str, str]] = frozenset({("C2", "output")})
# abstain_interrogative_output's fixed 3-position set: output-only across
# C1/C3/C4 (never context).
_OUTPUT_ONLY_TABLE_CHECKS: frozenset[tuple[str, str]] = frozenset(
    (c, "output") for c in ("C1", "C3", "C4")
)


def _build_surface_registry() -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}

    facet_families = (
        "facet:availability", "facet:refund_availability", "facet:exchange_availability",
        "facet:discount_availability", "facet:access_permission", "facet:approval_requirement",
        "facet:eligibility", "facet:cost", "facet:duration", "facet:limit",
    )
    for facet in facet_families:
        registry[f"facets_v1.{facet}"] = {
            "allowed_positions": _TABLE_POSITIONS, "predicate_id": "facets_v1",
        }

    for concept in ("approval", "verification", "authorization", "confirmation", "registration"):
        registry[f"concept_v1.{concept}"] = {
            "allowed_positions": _TABLE_POSITIONS, "predicate_id": "concept_v1",
        }

    for name in ("over", "above", "more_than", "at_least", "under", "below", "less_than", "at_most", "up_to", "within"):
        registry[f"comparators_v1.{name}"] = {
            "allowed_positions": _TABLE_POSITIONS, "predicate_id": "comparators_v1",
        }

    for pair in ("digital_physical", "verified_unverified", "active_inactive", "internal_external"):
        registry[f"excl_v1.{pair}"] = {
            "allowed_positions": _TABLE_POSITIONS, "predicate_id": "excl_v1",
        }

    for pair in ("verified_unverified", "approved_unapproved", "active_inactive", "enabled_disabled", "eligible_ineligible"):
        registry[f"complement_v1.{pair}"] = {
            "allowed_positions": _TABLE_POSITIONS, "predicate_id": "complement_v1",
        }

    for name, kind, force in (
        ("if", "IF", "grant"), ("when", "IF", "grant"), ("provided_that", "IF", "grant"),
        ("as_long_as", "IF", "grant"), ("unless", "IF", "grant"), ("except", "IF", "grant"),
        ("only_if", "ONLY_IF", "restriction"), ("subject_to", "SUBJECT_TO", "restriction"),
        ("depending_on", "SUBJECT_TO", "restriction"), ("must_first", "SUBJECT_TO", "restriction"),
    ):
        registry[f"condition_operators_v1.{name}.{kind}.{force}"] = {
            "allowed_positions": _TABLE_POSITIONS, "predicate_id": "condition_operators_v1",
        }

    for cls in ("universal", "existential", "abstain"):
        registry[f"quant_v1.{cls}"] = {
            "allowed_positions": _TABLE_POSITIONS, "predicate_id": "quant_v1",
        }

    for facet in ("cost", "duration", "limit"):
        registry[f"value_role_v1.{facet}"] = {
            "allowed_positions": _VALUE_ROLE_POSITIONS, "predicate_id": "value_role_v1",
        }

    for name in _NONTABLE_SURFACE_NAMES:
        if name in _C2_ONLY_NONTABLE:
            positions = _C2_OUTPUT_ONLY
        elif name == "contraction_expansion":
            positions = _TABLE_POSITIONS | _C2_OUTPUT_ONLY
        elif name == "abstain_interrogative_output":
            positions = _OUTPUT_ONLY_TABLE_CHECKS
        else:
            assert name in _NONTABLE_TABLE_FAMILY_POSITION_NAMES, name
            positions = _TABLE_POSITIONS
        registry[f"nontable.{name}"] = {
            "allowed_positions": positions,
            "predicate_id": "nontable",
        }

    return registry


SURFACE_REGISTRY: dict[str, dict[str, Any]] = _build_surface_registry()
assert len(SURFACE_REGISTRY) == 68, f"SURFACE_REGISTRY must have exactly 68 entries, got {len(SURFACE_REGISTRY)}"
_SURFACE_REGISTRY_TOTAL_POSITIONS = sum(len(e["allowed_positions"]) for e in SURFACE_REGISTRY.values())
assert _SURFACE_REGISTRY_TOTAL_POSITIONS == 362, (
    f"SURFACE_REGISTRY must have exactly 362 total allowed positions, got {_SURFACE_REGISTRY_TOTAL_POSITIONS}"
)

# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1-P: CAPABILITY_MAP -- closed, reviewed STATIC
# compatibility declaration of WHERE, within one item's parsed-product
# structure, each of the 50 in-scope surfaces' family may be credited.
# NEVER dynamically inferred: a pre-registered routing table, not a
# consumption-tracing proof (see the honest-assurance prose in
# README.md / coverage_manifest_schema.json / this module's own
# docstring; CAPABILITY_MAP never proves internal branch reach,
# causality, or per-corpus-item execution).
#
# "location" names WHERE within one frame's own parsed structure a
# family's product lives:
#   "frame"       -- the frame's own Extent (facets_v1's normalized,
#                     projection-resolved Frame.extent.facet).
#   "modifier"    -- FrameProductEvent.modifiers / excl_candidates
#                     (PP-adjunct modifier object sets; excl_v1 only).
#   "extent"      -- the frame's own selected quant_class/quant_token_fold.
#   "value"       -- a frame's own top-level Roles.value span (a bare
#                     comparator+number/measure span, or value_role_v1's
#                     classified span).
#   "condition"   -- inside a ConditionProductEvent's own Bool formula
#                     (a conds entry -- concept mappings, COMPLEMENT_v1
#                     singleton candidates, comparator events all bound
#                     to THIS condition's own conjuncts).
#   "requirement" -- inside a requirement-parent frame's own req_formula
#                     Bool formula (facet:approval_requirement only).
#   "partial"     -- a PartialProductEvent (quant_v1.abstain's own
#                     PER_HIT_ABSTAIN event only; no frame is produced).
#
# BIDIRECTIONAL CONSISTENCY (re-proven by dedicated pytest tests in
# test_calibration.py, in addition to the build-time asserts
# immediately below): exactly 13 nonempty rows; every mapped position
# is itself a member of the closed _TABLE_POSITIONS/_VALUE_ROLE_POSITIONS
# vocabulary already governing SURFACE_REGISTRY; for EVERY one of the 50
# in-scope surfaces, the UNION of its family's routed locations' own
# position sets EQUALS (not merely subsets) that surface's own
# SURFACE_REGISTRY allowed_positions; SURFACE_REGISTRY itself remains
# exactly 68 surfaces / 362 positions (asserted above, unchanged by this
# pass).
# ---------------------------------------------------------------------
CAPABILITY_MAP: dict[tuple[str, str], frozenset[tuple[str, str]]] = {
    ("facets_v1", "frame"): _TABLE_POSITIONS,
    ("concept_v1", "condition"): _TABLE_POSITIONS,
    ("concept_v1", "requirement"): frozenset({("C3", "context"), ("C3", "output")}),
    # SAN-881 PASS 2B.1-P-FIX fix 3: comparators_v1@value's exact
    # positions are {(C1,context),(C1,output)} ONLY -- (C3,context) is
    # REMOVED (an error propagated from the reviewer's own earlier
    # plan). C3 top-level-value source-conflict coverage belongs to
    # SYNTHETIC value_role_v1 (its own ("value_role_v1","value") row,
    # unchanged, still carries (C3,context)); C3 comparator credit comes
    # only through the ("comparators_v1","condition") /
    # ("comparators_v1","requirement") rows below -- never a bare
    # top-level comparator VALUE product.
    ("comparators_v1", "value"): frozenset({("C1", "context"), ("C1", "output")}),
    ("comparators_v1", "condition"): _TABLE_POSITIONS,
    ("comparators_v1", "requirement"): frozenset({("C3", "context"), ("C3", "output")}),
    ("excl_v1", "modifier"): _TABLE_POSITIONS,
    ("complement_v1", "condition"): _TABLE_POSITIONS,
    ("complement_v1", "requirement"): frozenset({("C3", "context"), ("C3", "output")}),
    ("condition_operators_v1", "condition"): _TABLE_POSITIONS,
    ("quant_v1", "extent"): _TABLE_POSITIONS,
    ("quant_v1", "partial"): _TABLE_POSITIONS,
    ("value_role_v1", "value"): _VALUE_ROLE_POSITIONS,
}
assert len(CAPABILITY_MAP) == 13, f"CAPABILITY_MAP must have exactly 13 rows, got {len(CAPABILITY_MAP)}"

_CAPABILITY_MAP_CLOSED_POSITIONS: frozenset[tuple[str, str]] = _TABLE_POSITIONS | _VALUE_ROLE_POSITIONS
for _cm_key, _cm_positions in CAPABILITY_MAP.items():
    assert _cm_positions <= _CAPABILITY_MAP_CLOSED_POSITIONS, (
        f"CAPABILITY_MAP{_cm_key} contains a position outside the closed vocabulary: {_cm_positions!r}"
    )

_CAPABILITY_MAP_FAMILIES: frozenset[str] = frozenset(family for family, _location in CAPABILITY_MAP)
assert _CAPABILITY_MAP_FAMILIES == frozenset({
    "facets_v1", "concept_v1", "comparators_v1", "excl_v1", "complement_v1",
    "condition_operators_v1", "quant_v1", "value_role_v1",
}), f"CAPABILITY_MAP families = {_CAPABILITY_MAP_FAMILIES!r}"

# Per-surface union EQUALITY: every one of the 50 in-scope surfaces'
# SURFACE_REGISTRY allowed_positions must equal the UNION, over every
# CAPABILITY_MAP row whose family matches that surface's predicate_id,
# of that row's own position set -- not merely a subset either way.
for _surface_name, _entry in SURFACE_REGISTRY.items():
    _family = _entry["predicate_id"]
    if _family not in _CAPABILITY_MAP_FAMILIES:
        continue  # nontable: CAPABILITY_MAP never routes nontable surfaces
    _union: set[tuple[str, str]] = set()
    for (_f, _loc), _positions in CAPABILITY_MAP.items():
        if _f == _family:
            _union |= _positions
    assert frozenset(_union) == _entry["allowed_positions"], (
        f"{_surface_name}: CAPABILITY_MAP union {_union!r} != registry allowed_positions {_entry['allowed_positions']!r}"
    )
del _cm_key, _cm_positions, _surface_name, _entry, _family, _union, _f, _loc, _positions

# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1-T: derived excl_v1 collision set (BUILD/TEST-TIME
# ONLY -- never called from main() or any runtime acceptance path;
# proves the registry's retirement of excl_v1.refundable_nonrefundable
# is not arbitrary, it is the ONE excl_v1 pair whose both members
# ALSO appear in the folded union of every facets_v1 facet's own
# triggers + deny_triggers).
#
# Folding uses EXACTLY reference.primitives.fold_sequence -- the same
# pinned production tokenizer/fold primitive used everywhere else in
# this module -- never a hand-rolled .lower(). A facet's trigger /
# deny_trigger entry folds to its COMPLETE token sequence (a tuple,
# possibly multi-token); an excl_v1 member is a single MODIFIER word by
# construction and MUST fold to exactly one token -- anything else is a
# build/test-time authoring defect in the tables artifact, raised loud
# as ValueError rather than silently truncated or first-token-only.
# Canonicalization is the UNORDERED sorted 2-tuple of the two members'
# single folded tokens, so raw table row order (and any registry-key
# join order) never leaks into the returned set's element order.
#
# derive_excl_trigger_collision_set is derived PURELY from the raw
# tables data (facets_v1 + excl_v1) -- it never reads SURFACE_REGISTRY.
# derive_excl_registry_excluded_set is derived PURELY from cross-
# referencing the raw excl_v1 rows against SURFACE_REGISTRY -- it never
# inspects facets_v1 triggers. The two functions are therefore
# independent derivations; a test asserting they produce the SAME set
# is a genuine, non-circular proof, not a tautology.
# ---------------------------------------------------------------------

def _fold_excl_member(member: str) -> str:
    """Folds one excl_v1 pair member via the pinned production
    fold_sequence primitive and REQUIRES the result to be exactly one
    token (excl_v1 members are single MODIFIER words, never phrases) --
    a build/test-time-only helper, so any other shape is a loud,
    immediate ValueError rather than a silently-truncated/first-token
    guess."""
    folded = fold_sequence(member)
    if len(folded) != 1:
        raise ValueError(
            f"excl_v1 member {member!r} folds to {folded!r} (expected exactly one token)"
        )
    return folded[0]


def _validate_excl_v1_rows(rows) -> list[tuple[str, str, str, str]]:
    """SHARED row-validity gate for BOTH excl_v1 derivation helpers
    below (SAN-881 PASS 2B.1-T-FIX blocker 6) -- so the two helpers (and
    assert_excl_collision_registry_alignment, which calls both) reject
    IDENTICALLY rather than one silently accepting what the other
    rejects. Rejects, loudly, with ValueError (build/test-time-only;
    never called at runtime), the instant any of three malformed forms
    is found: (a) row cardinality != 2; (b) a row whose two members fold
    to the SAME token (a degenerate self-pair, never a genuine 2-member
    exclusion); (c) ANY second row that normalizes to an
    already-seen unordered folded pair -- whether a reversed-order
    duplicate of DIFFERENT row content, or a byte-identical repeat of
    the SAME row content (SAN-881 PASS 2B.1-T-FIX-MICRO fix 2: an exact
    duplicate previously passed silently, since the prior check also
    required the second row's content to differ from the first's)
    -- previously silently collapsed into one set entry. Never silently
    skips a malformed row, never silently accepts a folded duplicate of
    any form. Returns [(a, b, fa, fb), ...] -- the original two raw
    members plus their single folded tokens, one 4-tuple per validated
    row, in original row order, for each caller's own (independent)
    downstream logic."""
    validated: list[tuple[str, str, str, str]] = []
    seen_pairs: dict[tuple[str, str], Any] = {}
    for row in rows:
        if len(row) != 2:
            raise ValueError(f"excl_v1 row {row!r} does not have exactly 2 members (cardinality != 2)")
        a, b = row[0], row[1]
        fa, fb = _fold_excl_member(a), _fold_excl_member(b)
        if fa == fb:
            raise ValueError(f"excl_v1 row {row!r} folds both members to the SAME token {fa!r}")
        pair = tuple(sorted((fa, fb)))
        if pair in seen_pairs:
            raise ValueError(
                f"excl_v1 rows {seen_pairs[pair]!r} and {row!r} both normalize to the same folded pair {pair!r}"
            )
        seen_pairs[pair] = row
        validated.append((a, b, fa, fb))
    return validated


def derive_excl_trigger_collision_set(tables_data: dict) -> frozenset[tuple[str, str]]:
    """A facet's own triggers + deny_triggers already encode POS/NEG
    polarity for its own vocabulary (e.g. facets_v1["facet:refund_availability"]'s
    "refundable" trigger / "nonrefundable" deny_trigger). An excl_v1
    MODIFIER-exclusivity pair whose BOTH members also appear -- as a
    COMPLETE folded trigger sequence, via fold_sequence, e.g. a plural
    "refundables" trigger stems to ("refundable",) and so still matches
    a singular "refundable" excl_v1 member -- in the folded union of
    every facet's own triggers + deny_triggers is therefore a genuine
    semantic COLLISION -- the same word pair already carries trigger
    polarity for some facet, so registering it as an EXCL coverage
    surface would test a redundant/conflicting relation, not a genuine
    standalone modifier-exclusion pair. Returns the set of colliding
    excl_v1 rows, each normalized as the UNORDERED sorted 2-tuple of the
    two members' single folded tokens -- order-agnostic both in how
    membership is tested (an excl_v1 row is an unordered pair, so
    [a, b] and [b, a] collide identically) and in the RETURNED tuple's
    own element order (never inherited from raw row order). EVERY row is
    first validated via _validate_excl_v1_rows (SAN-881 PASS
    2B.1-T-FIX) -- see that helper for the three malformed forms
    rejected with a loud ValueError (build/test-time-only; never called
    at runtime), including the original single-member-fold-shape check."""
    trigger_union: set[tuple[str, ...]] = set()
    for facet in tables_data.get("facets_v1", {}).values():
        for tok in list(facet.get("triggers", [])) + list(facet.get("deny_triggers", [])):
            trigger_union.add(fold_sequence(tok))

    collisions: set[tuple[str, str]] = set()
    for _a, _b, fa, fb in _validate_excl_v1_rows(tables_data.get("excl_v1", [])):
        if (fa,) in trigger_union and (fb,) in trigger_union:
            collisions.add(tuple(sorted((fa, fb))))
    return frozenset(collisions)


def derive_excl_registry_excluded_set(
    tables_data: dict, registry: dict[str, dict[str, Any]] | None = None
) -> frozenset[tuple[str, str]]:
    """The set of raw excl_v1 table rows that are NOT registered as a
    SURFACE_REGISTRY `excl_v1.*` coverage surface (i.e. retired rows),
    normalized as the UNORDERED sorted 2-tuple of the two members'
    single folded tokens (see derive_excl_trigger_collision_set).
    Registry membership matching is ORDER-INSENSITIVE: a raw excl_v1
    row [a, b] is registered iff EITHER `excl_v1.<a>_<b>` OR
    `excl_v1.<name b>_<name a>` names a live SURFACE_REGISTRY key --
    SURFACE_REGISTRY's own key names are pre-registered fixed strings
    inherited from whatever row order the registry was built against,
    so a raw table row reversed relative to that fixed name must still
    be recognized as registered. Never inspects facets_v1 -- see the
    module comment above for why this matters (independence from
    derive_excl_trigger_collision_set). EVERY row is first validated via
    _validate_excl_v1_rows (build/test-time-only; never called at
    runtime) -- see that helper for the three malformed forms rejected
    with a loud ValueError, IDENTICAL to derive_excl_trigger_collision_set's
    own rejection."""
    reg = SURFACE_REGISTRY if registry is None else registry
    excluded: set[tuple[str, str]] = set()
    for a, b, fa, fb in _validate_excl_v1_rows(tables_data.get("excl_v1", [])):
        name_ab = "_".join((a, b))
        name_ba = "_".join((b, a))
        if f"excl_v1.{name_ab}" not in reg and f"excl_v1.{name_ba}" not in reg:
            excluded.add(tuple(sorted((fa, fb))))
    return frozenset(excluded)


def assert_excl_collision_registry_alignment(
    tables_data: dict, registry: dict[str, dict[str, Any]] | None = None
) -> None:
    """BUILD/TEST-TIME ONLY (never called from main() or any runtime
    acceptance path): asserts that the two INDEPENDENT derivations above
    agree exactly -- collision_set == excluded_set == the single
    canonical pinned pair {("nonrefundable", "refundable")} -- and that
    the registry's own 47 + 3 + 18 == 68 family-count accounting holds.
    Reads `tables_data` and `registry` (defaulting to the real, live
    SURFACE_REGISTRY) as READ-ONLY inputs; never mutates either, never
    monkeypatches production tables/T/compiled constants. A genuine,
    deliberately LOUD proof: raises plain AssertionError (not a fixed
    RULE_* diagnostic -- this helper is never on a runtime error-output
    path) the moment either equality or the accounting fails, so a
    manufactured second collision in a deep-copied tables_data makes
    THIS function fail, proving the equality assertion is live rather
    than vacuously true."""
    reg = SURFACE_REGISTRY if registry is None else registry
    collision_set = derive_excl_trigger_collision_set(tables_data)
    excluded_set = derive_excl_registry_excluded_set(tables_data, reg)
    pinned = frozenset({("nonrefundable", "refundable")})
    assert collision_set == excluded_set == pinned, (
        f"collision_set={collision_set!r} excluded_set={excluded_set!r} expected={pinned!r}"
    )

    predicate_ids = [e["predicate_id"] for e in reg.values()]
    table_derived = sum(
        1
        for e in reg.values()
        if e["predicate_id"] in (
            "facets_v1", "concept_v1", "comparators_v1", "excl_v1",
            "complement_v1", "condition_operators_v1", "quant_v1",
        )
    )
    value_role = predicate_ids.count("value_role_v1")
    nontable = predicate_ids.count("nontable")
    assert table_derived == 47, f"table_derived={table_derived}"
    assert value_role == 3, f"value_role={value_role}"
    assert nontable == 18, f"nontable={nontable}"
    assert table_derived + value_role + nontable == 68
    assert 47 + 3 + 18 == 68


# The literal, pinned reveal-verification ledger ORDER (SAN-881 Phase-A
# correction item 2): the final canonical ledger contains EXACTLY these six
# (artifact_name, envelope, verified_stage) entries, in EXACTLY this index
# order -- no more, no fewer, no permutation. build_reveal_verification_ledger
# EMITS this order directly (it does not sort); check_reveal_verification_ledger
# and reveal_verification_ledger_schema.json's prefixItems both pin it
# index-by-index. LEDGER_PINNED_TUPLES (the order-blind SET form, used by
# the tuple-membership pre-check) is derived from this tuple, never the
# reverse -- there is exactly one source of truth for the six tuples.
LEDGER_CANONICAL_ORDER: tuple[tuple[str, str, str], ...] = (
    ("labels_author_semantic.json", "author", "semantic"),
    ("labels_reviewer_semantic.json", "reviewer_semantic", "semantic"),
    ("labels_author_contract.json", "author", "contract"),
    ("design_metadata.json", "author", "contract"),
    ("coverage_manifest.json", "author", "contract"),
    ("labels_reviewer_contract.json", "reviewer_contract", "contract"),
)
LEDGER_PINNED_TUPLES: frozenset[tuple[str, str, str]] = frozenset(LEDGER_CANONICAL_ORDER)

# ---------------------------------------------------------------------
# Rule codes -- the ONLY vocabulary allowed to appear in an error string
# alongside {artifact_name, record_index, item_id, check_id}.
# ---------------------------------------------------------------------
RULE_SCHEMA_INVALID = "SCHEMA_INVALID"
RULE_MISSING_SCHEMA = "MISSING_SCHEMA"
RULE_ID_ORDINAL_MISMATCH = "ID_ORDINAL_MISMATCH"
RULE_CONTEXT_SHAPE = "CONTEXT_SHAPE_NOT_EXACTLY_ONE"
RULE_DISALLOWED_KEYS = "DISALLOWED_KEYS"
RULE_NON_TIER1 = "NON_TIER1_SOURCE"
RULE_SOURCE_SHAPE = "SOURCE_SHAPE"
RULE_DUPLICATE_TUPLE = "DUPLICATE_TUPLE"
RULE_FIELD_BYTES_EXCEEDED = "FIELD_BYTES_EXCEEDED"
RULE_CORPUS_VERSION = "CORPUS_VERSION"
RULE_PROFILE_SCOPE = "PROFILE_SCOPE"
RULE_SPEC_PIN_MISMATCH = "SPEC_PIN_MISMATCH"
RULE_CONTEXT_HASH_MISMATCH = "CONTEXT_HASH_MISMATCH"
RULE_COMMITMENT_ARTIFACT_SET = "COMMITMENT_ARTIFACT_SET_MISMATCH"
RULE_COMMITMENT_HEX_SHAPE = "COMMITMENT_HEX_SHAPE"
RULE_BYTE_LENGTH_SHAPE = "BYTE_LENGTH_SHAPE"
RULE_DUPLICATE_ITEM_ID = "DUPLICATE_ITEM_ID"
RULE_ITEM_NOT_IN_CORPUS = "ITEM_NOT_IN_CORPUS"
RULE_INVALID_CHECK_ID = "INVALID_CHECK_ID"
RULE_INVALID_STRATUM = "INVALID_STRATUM"
RULE_ITEM_COUNT = "ITEM_COUNT"
RULE_STRATUM_COUNT = "STRATUM_COUNT_NOT_10"
RULE_FACET_NOT_CLOSED = "FACET_NOT_IN_CLOSED_LIST"
RULE_DOD_MISSING_PAIR_FIELD = "DOD_MISSING_PAIR_OR_FEATURE"
RULE_NON_DOD_HAS_PAIR_FIELD = "NON_DOD_HAS_PAIR_OR_FEATURE"
RULE_SEM_KEYS = "SEMANTIC_KEY_SET_VIOLATION"
RULE_SEM_TRUTH_INVALID = "SEMANTIC_TRUTH_INVALID"
RULE_DUP_SEM_PAIR = "DUPLICATE_SEMANTIC_PAIR"
RULE_DUP_CONTRACT_PAIR = "DUPLICATE_CONTRACT_PAIR"
RULE_CONTRACT_OUTCOME_INVALID = "CONTRACT_OUTCOME_INVALID"
RULE_CONTRACT_REASON_INVALID = "CONTRACT_REASON_INVALID"
RULE_SEVERITY_MISMATCH = "SEVERITY_MISMATCH"
RULE_SEVERITY_MUST_BE_NULL = "SEVERITY_MUST_BE_NULL"
RULE_ADVISORY_MUST_BE_FALSE = "ADVISORY_MUST_BE_FALSE"
RULE_COMPETENCE_INVALID = "COMPETENCE_INVALID"
RULE_LABEL_COUNT = "LABEL_COUNT"
RULE_KEYSET_MISMATCH = "KEYSET_MISMATCH"
RULE_ABSTENTION_TRUTH_MISMATCH = "DELIBERATE_ABSTENTION_REQUIRES_INDETERMINATE"
RULE_INDETERMINATE_COMPETENCE = "INDETERMINATE_REQUIRES_DELIBERATE_ABSTENTION"
RULE_COVERAGE_GAP_SCOPE = "KNOWN_COVERAGE_GAP_OUT_OF_SCOPE"
RULE_IN_DOMAIN_COMPETENCE = "IN_DOMAIN_COMPETENCE_MISMATCH"
RULE_IN_DOMAIN_OUTCOME_MAP = "IN_DOMAIN_OUTCOME_MAP_MISMATCH"
RULE_DOD_TRUTH_INVALID = "DOD_TRUTH_NOT_DETERMINATE"
RULE_DOD_TRUTH_BALANCE = "DOD_TRUTH_BALANCE"
RULE_MINIMAL_PAIR_UNRESOLVED = "MINIMAL_PAIR_UNRESOLVED"
RULE_MINIMAL_PAIR_STRATUM = "MINIMAL_PAIR_CONTROL_STRATUM_INVALID"
RULE_MINIMAL_PAIR_CHECK = "MINIMAL_PAIR_CHECK_MISMATCH"
RULE_MINIMAL_PAIR_DOMAIN = "MINIMAL_PAIR_DOMAIN_MISMATCH"
RULE_MINIMAL_PAIR_CONTROL_TRUTH = "MINIMAL_PAIR_CONTROL_TRUTH_MISMATCH"
RULE_MINIMAL_PAIR_SAME_SEMANTICS = "MINIMAL_PAIR_SAME_SEMANTICS_PROOF_FAILED"
RULE_MINIMAL_PAIR_SELF = "MINIMAL_PAIR_SELF_REFERENTIAL"
RULE_MINIMAL_PAIR_REUSED = "MINIMAL_PAIR_CONTROL_REUSED"
RULE_MINIMAL_PAIR_CYCLE = "MINIMAL_PAIR_CONTROL_CYCLE"
RULE_FEATURE_NOT_ABSENT = "INTRODUCED_FEATURE_NOT_ABSENT_FROM_TABLE"
RULE_FEATURE_TOKENS_NOT_IN_ITEM = "INTRODUCED_FEATURE_TOKENS_NOT_PRESENT_IN_ITEM"
RULE_FEATURE_TOKENS_IN_CONTROL = "INTRODUCED_FEATURE_TOKENS_PRESENT_IN_CONTROL"
RULE_COVERAGE_TOP_LEVEL = "COVERAGE_MANIFEST_TOP_LEVEL_SHAPE"
RULE_COVERAGE_SURFACE_LIST = "COVERAGE_SURFACE_NOT_A_LIST"
RULE_COVERAGE_RECORD_SHAPE = "COVERAGE_EVIDENCE_RECORD_SHAPE"
RULE_COVERAGE_UNKNOWN_ITEM = "COVERAGE_UNKNOWN_ITEM_ID"
RULE_COVERAGE_INVALID_CHECK = "COVERAGE_INVALID_CHECK_ID"
RULE_COVERAGE_INVALID_FIELD = "COVERAGE_INVALID_FIELD"
RULE_COVERAGE_EMPTY_EVIDENCE = "COVERAGE_EVIDENCE_EMPTY"
RULE_COVERAGE_SCENARIO_INDEPENDENCE = "COVERAGE_SCENARIO_INDEPENDENCE_VIOLATED"
RULE_COVERAGE_PREDICATE_FAILED = "COVERAGE_PREDICATE_NOT_SATISFIED"
RULE_COVERAGE_NO_PREDICATE = "COVERAGE_NO_REGISTERED_PREDICATE"
RULE_REVEAL_NOT_SUPPLIED = "REVEAL_ARTIFACT_NOT_SUPPLIED"
RULE_REVEAL_EXTRA = "REVEAL_UNDECLARED_EXTRA_ARTIFACT"
RULE_REVEAL_FORBIDDEN_EXTRA = "REVEAL_FORBIDDEN_STAGE_EXTRA"
RULE_REVEAL_BYTE_LENGTH = "REVEAL_BYTE_LENGTH_MISMATCH"
RULE_REVEAL_NO_NONCE = "REVEAL_NO_NONCE"
RULE_REVEAL_DOES_NOT_VERIFY = "REVEAL_DOES_NOT_VERIFY"
RULE_ENVELOPE_KIND_MISMATCH = "ENVELOPE_KIND_MISMATCH"
RULE_ENVELOPE_CONTEXT_HASH_INCONSISTENT = "ENVELOPE_CONTEXT_HASH_INCONSISTENT"
RULE_CONTRACT_REASON_OUTCOME_MISMATCH = "CONTRACT_REASON_NOT_VALID_FOR_OUTCOME"
RULE_JSONSCHEMA_MODULE_MISSING = "JSONSCHEMA_MODULE_MISSING_FAILS_CLOSED"
RULE_COVERAGE_REGISTRY_MISSING_SURFACE = "COVERAGE_REGISTRY_MISSING_SURFACE"
RULE_COVERAGE_REGISTRY_EXTRA_SURFACE = "COVERAGE_REGISTRY_EXTRA_SURFACE"
RULE_COVERAGE_CHECK_NOT_ALLOWED = "COVERAGE_CHECK_NOT_ALLOWED_FOR_SURFACE"
RULE_COVERAGE_FIELD_NOT_ALLOWED = "COVERAGE_FIELD_NOT_ALLOWED_FOR_SURFACE"
# SAN-881 CORRECTION PASS 2 (operator-ratified Coverage Routing Matrix
# v3): the ONLY new rule code this pass. RULE_COVERAGE_CHECK_NOT_ALLOWED
# and RULE_COVERAGE_FIELD_NOT_ALLOWED above are PER-AXIS codes -- they
# can only describe "this check_id is never legal for this surface" or
# "this field is never legal for this surface" independently, never "this
# check_id IS legal for this surface (in some other field) and this field
# IS legal for this surface (at some other check_id), but this exact PAIR
# is not." RULE_COVERAGE_POSITION_NOT_ALLOWED fires exactly for that pair
# case (e.g. value_role_v1.cost at (C3, output): C3 is legal for
# value_role_v1 at (C3, context), output is legal at (C1, output), but
# the pair (C3, output) is not itself in value_role_v1's allowed_positions).
RULE_COVERAGE_POSITION_NOT_ALLOWED = "COVERAGE_POSITION_NOT_ALLOWED_FOR_SURFACE"
RULE_COVERAGE_JOINT_MEMBER_MISSING = "COVERAGE_JOINT_PAIR_MEMBER_MISSING"
RULE_LEDGER_TUPLE_SET_MISMATCH = "LEDGER_TUPLE_SET_MISMATCH"
RULE_LEDGER_CROSS_CHECK_MISMATCH = "LEDGER_CROSS_CHECK_MISMATCH"
RULE_INVALID_REVEAL_STAGE = "INVALID_REVEAL_STAGE"

# SAN-881 Phase-A CORRECTION PASS 1: staged bundle-contract enforcement,
# canonical ledger ordering, and the v2 structured labeling-context
# formula. Every new rule code below is emitted ONLY with the fixed
# vocabulary already promised by the module docstring (artifact name,
# record index, item_id/check_id, fixed RULE_* code) -- never a
# directory-listing-derived (attacker-controlled) filename, never an
# absolute custody path, never a raw exception message.
RULE_NONCE_MALFORMED = "NONCE_NOT_64_LOWERCASE_HEX"
RULE_NONCE_KEYSET_MISMATCH = "NONCE_KEYSET_MISMATCH"
RULE_NONCE_FILE_INSIDE_BUNDLE = "NONCE_FILE_MUST_BE_OUTSIDE_BUNDLE_DIR"
RULE_STAGED_IO_FAILURE = "STAGED_ARTIFACT_IO_OR_JSON_FAILURE"
RULE_LEDGER_ORDER_MISMATCH = "LEDGER_ORDER_MISMATCH"
RULE_COMMITMENT_ORDER_MISMATCH = "AUTHOR_COMMITMENT_ORDER_MISMATCH"

# SAN-881 PASS-1 CORRECTION ROUND (root repair): schema validity must be
# checked BEFORE cryptographic validity is allowed to imply success. A
# bundle member that exists on disk under a pinned name but is not a
# direct, regular, non-symlink file (a directory, a symlink -- even one
# pointing at a legitimate regular file elsewhere -- a socket, a FIFO,
# ...) can never stand in for the pinned artifact.
RULE_REVEAL_NOT_REGULAR_FILE = "REVEAL_ARTIFACT_NOT_REGULAR_FILE"

# SAN-881 PASS-1 CLOSURE PATCH: closes the five reproduced escapes left
# by the PASS-1 FINAL GATING CORRECTION -- the prior instrumentation
# only covered _snapshot_regular_file and verify_reveal, missing
# nonce-file loads and context-component reads as independent read/crypto
# paths. Every new rule code below is emitted ONLY with the fixed
# vocabulary already promised by the module docstring.
RULE_COMMITMENT_UNREADABLE = "COMMITMENT_JSON_UNREADABLE_OR_MALFORMED"
RULE_CONTEXT_COMPONENT_UNREADABLE = "CONTEXT_COMPONENT_UNREADABLE_OR_INVALID"
RULE_AUTHOR_GATE_NOT_OK = "AUTHOR_ENVELOPE_GATE_NOT_SATISFIED"

# SAN-881 PASS-1 FINAL CLOSURE CORRECTION: the deprecated legacy
# generic per-envelope reveal-verification code path -- and the opt-in
# flag that wired it -- is REMOVED entirely: no non-test consumer
# existed, and the staged gated pipeline (--reveal-stage) is now the
# SOLE crypto path. Any nonce/reviewer argument supplied WITHOUT
# --reveal-stage is a fixed-diagnostic reject, never a silent no-op.
RULE_REVEAL_STAGE_REQUIRED = "NONCE_OR_REVIEWER_ARG_REQUIRES_REVEAL_STAGE"


class Errors(list):
    def add(self, msg: str) -> None:
        self.append(msg)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_read_json_file(errors: Errors, path: Path, label: str) -> tuple[Any, bool]:
    """SAN-881 PASS-1 CLOSURE PATCH: read+parse `path` as JSON, never
    raising. A missing/unreadable path (any OSError) or malformed JSON
    is a single fixed RULE_STAGED_IO_FAILURE diagnostic -- never a
    traceback, never a path disclosure. Returns (parsed_value_or_None,
    ok). Used for every read path that is neither commitment.json's own
    dedicated safe-parse (which uses a commitment-specific rule code) nor
    a staged bundle-member snapshot (which goes through the O_NOFOLLOW
    _snapshot_regular_file primitive instead)."""
    try:
        raw = path.read_bytes()
    except OSError:
        errors.add(f"{label}: rule={RULE_STAGED_IO_FAILURE}")
        return None, False
    try:
        return json.loads(raw.decode("utf-8")), True
    except (UnicodeDecodeError, ValueError):
        errors.add(f"{label}: rule={RULE_STAGED_IO_FAILURE}")
        return None, False


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(obj: Any) -> bytes:
    """sorted keys, compact separators, ensure_ascii, single trailing LF."""
    return (json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n").encode("ascii")


# ---------------------------------------------------------------------
# Commit/reveal primitives (also used by measure.py's freeze-gate cousin
# and by tests/reference/test_calibration.py's toy reveal tests)
# ---------------------------------------------------------------------

def compute_labeling_context_hash(components: list[bytes]) -> bytes:
    """SHA256 over the exact concatenation of the ordered raw components."""
    return hashlib.sha256(b"".join(components)).digest()


# The literal, pinned v2 labeling-context component NAME order (SAN-881
# Phase-A correction item 3, an INTENTIONAL v2 formula change from v1):
# EXACTLY 11 named components, in this exact order. v1 concatenated
# base_commit_sha's raw 40-ASCII-byte pin directly (unhashed) ahead of
# the other ten components' SHA-256 digests; v2 is uniform -- EVERY
# component, including base_commit_sha, is individually SHA-256'd first,
# and labeling_context_hash is SHA256 of the concatenation of the eleven
# resulting raw 32-byte digests. This is a deliberate, documented break
# from v1 (see README.md's v1-transitional posture), not a compatible
# extension -- a v1 hash can never equal a v2 hash for the same inputs.
LABELING_CONTEXT_COMPONENT_NAMES: tuple[str, ...] = (
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


def _labeling_context_component_source_bytes(name: str, cal_dir: Path, repo_root: Path, base_commit_sha: str) -> bytes:
    """Resolves ONE pinned component name to its exact source bytes, via a
    fixed path/constant per name -- NEVER directory globbing, and NEVER
    interpreting an envelope-supplied name as a filesystem path (the
    caller only ever passes names drawn from LABELING_CONTEXT_COMPONENT_NAMES)."""
    if name == "base_commit_sha":
        return base_commit_sha.encode("ascii")
    if name == "algorithm":
        return (repo_root / "reference" / "spec" / "ALGORITHM-v4-c1c5-reference.md").read_bytes()
    if name == "tables":
        return (repo_root / "reference" / "spec" / "ALGORITHM-v4-tables-v1.json").read_bytes()
    # "corpus_inputs.json", "evaluation_profile.json", and the six fixed
    # "schemas/*.json" names all resolve directly under cal_dir.
    return (cal_dir / name).read_bytes()


def build_labeling_context_components(cal_dir: Path, repo_root: Path, base_commit_sha: str = BASE_COMMIT_SHA) -> list[dict[str, str]]:
    """CODE-PINNED (never directory-globbed) construction of the eleven
    structured {name, sha256} components, in LABELING_CONTEXT_COMPONENT_NAMES
    order, each sha256 = SHA-256 hex of that component's exact source
    bytes read from its fixed path/constant. This is the SAME structure
    commitment_schema.json's authorEnvelope.labeling_context_components
    pins via prefixItems -- descriptive metadata only; a verifier still
    NEVER trusts an envelope's own copy of this list as an input to
    compute_labeling_context_hash_from_disk below."""
    return [
        {"name": name, "sha256": sha256_hex(_labeling_context_component_source_bytes(name, cal_dir, repo_root, base_commit_sha))}
        for name in LABELING_CONTEXT_COMPONENT_NAMES
    ]


def compute_labeling_context_hash_from_disk(cal_dir: Path, repo_root: Path, base_commit_sha: str = BASE_COMMIT_SHA) -> bytes:
    """Recompute labeling_context_hash under the v2 formula (SAN-881
    Phase-A correction item 3): every one of the eleven pinned components
    -- including base_commit_sha -- is individually SHA-256'd first (see
    build_labeling_context_components); the result is SHA256 of the
    concatenation of the eleven raw 32-byte digests, in
    LABELING_CONTEXT_COMPONENT_NAMES order. Schema filenames are FIXED
    (SCHEMA_FILES via LABELING_CONTEXT_COMPONENT_NAMES), never a
    directory glob -- a schemas/ directory containing an extra,
    unlisted file no longer silently changes this hash. NEVER trusts a
    commitment envelope's own labeling_context_components list -- that
    field is descriptive metadata only, not an input to this function."""
    components = build_labeling_context_components(cal_dir, repo_root, base_commit_sha)
    digests = [bytes.fromhex(c["sha256"]) for c in components]
    return compute_labeling_context_hash(digests)


# SAN-881 PASS-1 CORRECTION: every $defs branch actually consumed by
# `_build_named_schema` anywhere in this module, keyed by which of the
# six schema files defines it -- the AUTHOR envelope and BOTH reviewer
# envelopes (`commitment_schema.json`), and BOTH labels branches
# (`labels_schema.json`). `design_metadata_schema.json` and
# `coverage_manifest_schema.json` are single-shape schemas (def_name=None,
# validated at their own root, never via `_build_named_schema`);
# `freeze_manifest_schema.json` and `reveal_verification_ledger_schema.json`
# are likewise never branch-consumed by this module. Checked HERE, during
# Tier-0 cache construction, rather than left to the first downstream
# consumer that happens to build one of these branches.
_SCHEMA_NAMED_BRANCHES: dict[str, tuple[str, ...]] = {
    "commitment_schema.json": ("authorEnvelope", "reviewerSemanticEnvelope", "reviewerContractEnvelope"),
    "labels_schema.json": ("semanticFile", "contractFile"),
}


def _fixed_component_path(name: str, cal_dir: Path, repo_root: Path) -> Path | None:
    """Resolves a file-backed fixed component NAME to its fixed path --
    NEVER directory globbing, NEVER attacker-influenced. Returns None
    for `base_commit_sha`, the one non-file-backed component."""
    if name == "base_commit_sha":
        return None
    if name == "algorithm":
        return repo_root / "reference" / "spec" / "ALGORITHM-v4-c1c5-reference.md"
    if name == "tables":
        return repo_root / "reference" / "spec" / "ALGORITHM-v4-tables-v1.json"
    if name.startswith("schemas/"):
        return cal_dir / name
    return cal_dir / name


# SAN-881 PASS-1 FINAL RESOLVER CORRECTION: CACHE-TIME STRUCTURAL LINT
# OVER A CLOSED V1 REFERENCE DIALECT. `Draft202012Validator.check_schema()`
# validates schema SYNTAX only -- it never dereferences a `$ref` target,
# and it has no opinion on WHERE a nested `$id` appears. The PRIOR
# correction here (a `$ref`-GRAPH WALKER: start at the root, follow each
# `$ref` into its `$defs` target, recurse, track a visited-set for
# cycles) closed the missing-target gap but had two of its own: (1) it
# never inspected the `$id` keyword at all, so a nested `$id` on a
# REACHABLE `$defs` entry -- which, per JSON Schema 2020-12 `$id`
# resource-scope semantics, REBASES fragment resolution for every
# `$ref` inside that sub-schema to a new resource rooted at that entry
# -- left the walker clean while a REAL consumer's instance validation
# (`Draft202012Validator(...).is_valid(...)`, called unconditionally
# inside `main()` to validate `commitment.json` against the
# `authorEnvelope` branch) crashed with an uncaught
# `jsonschema.exceptions._WrappedReferencingError` wrapping
# `referencing.exceptions.PointerToNowhere`; and (2) it compared a
# `$ref`'s fragment token to `$defs` keys LITERALLY (RFC6901
# tilde-unescape only), while the real `jsonschema`/`referencing`
# machinery URI-PERCENT-DECODES that same token before the `$defs`
# lookup -- so `"#/$defs/%61"` resolves, in `jsonschema`, to the key
# `"a"`, never the literal key `"%61"`, producing both a false ACCEPT
# (a literal `"%61"` `$defs` entry satisfies the walker while the real
# target is `"a"`, missing or different) and a false REJECT (a genuine
# `"a"` entry the walker can never match via a `%`-encoded `$ref`).
#
# This correction REPLACES the graph walker with a full-document
# STRUCTURAL LINT over a deliberately tiny, CLOSED v1 reference dialect,
# for ALL SIX fixed schema documents unconditionally, during cache
# construction:
#   1. The COMPLETE JSON tree of the schema document is traversed
#      EXACTLY ONCE -- every dict/list, INCLUDING every `$defs` entry,
#      regardless of whether anything in the document actually `$ref`s
#      it. There is no `$ref`-target worklist, no per-`$defs`-key
#      visited-set, and no recursion keyed off resolving a reference --
#      the document is finite, so scanning it once, unconditionally,
#      makes reference-worklist/cycle bookkeeping unnecessary. A genuine
#      `a`<->`b` reference cycle is therefore automatically fine: each
#      target need only EXIST as a present, well-formed `$defs` member;
#      the scan never "follows" a `$ref` to decide what to visit next.
#   2. `$id` is allowed ONLY on the schema document's own ROOT object.
#      Any `$id` found on ANY other node -- reachable via some `$ref` or
#      not -- is a violation (closes gap 1 above at the SOURCE: no
#      sub-schema can ever declare a new resource base).
#   3. `$dynamicRef`, `$anchor`, and `$dynamicAnchor` are rejected
#      ANYWHERE in the document, lexically, including inside `$defs`.
#   4. The ONLY accepted `$ref` form is the literal prefix
#      `"#/$defs/"` followed by a TOKEN matched with
#      `re.fullmatch(r"(?:[A-Za-z0-9_.-]|~0|~1)+", token)` -- anchored
#      end to end. This single grammar closes gap 2 above at the
#      SOURCE: `%` can never appear in an accepted token (no
#      URI-percent-decode ambiguity ever arises), a raw `/` can never
#      appear (no multi-segment pointer), and every `~` must be part of
#      an exact `~0` or `~1` pair (never a bare/trailing `~`, never
#      `~2` or any other digit). A token passing the grammar is then
#      RFC6901-decoded (`~1` -> `/` BEFORE `~0` -> `~`, the RFC-mandated
#      order) and must name a PRESENT member of the document's own
#      TOP-LEVEL `$defs`, whose value must itself be a dict or a JSON
#      boolean (the only two legal top-level schema shapes). Anything
#      else -- a missing prefix, a bare `#`, an external URI, a
#      multi-segment or malformed-tilde token, a missing or
#      wrong-shaped target -- is a violation.
# `check_schema` (both the root pass and the named-branch pass) remain
# INDEPENDENT, unchanged layers -- this lint neither replaces nor
# duplicates syntactic Draft-2020-12 validity checking.
_REF_TOKEN_GRAMMAR_RE = re.compile(r"(?:[A-Za-z0-9_.-]|~0|~1)+")
_LOCAL_DEF_REF_PREFIX = "#/$defs/"


def _unescape_json_pointer_token(token: str) -> str:
    """RFC 6901 unescape, in the RFC-mandated order: `~1` -> `/` BEFORE
    `~0` -> `~` (reversing the order would corrupt a token whose
    original character was literally the two characters `~1`)."""
    return token.replace("~1", "/").replace("~0", "~")


def _schema_ref_integrity_violation(schema: dict) -> bool:
    """True iff `schema` (a full schema DOCUMENT -- one of the six fixed
    schema files) contains ANY violation of the CLOSED v1 structural
    reference dialect (see the module comment above this function for
    the full design). Scans the COMPLETE JSON tree of the document
    EXACTLY ONCE -- every dict and list, INCLUDING every `$defs` entry
    regardless of reachability -- checking, at every dict node:

      - `$id`: allowed ONLY at the document ROOT (the top-level `schema`
        dict itself); present on ANY other node, it is a violation.
      - `$dynamicRef` / `$anchor` / `$dynamicAnchor`: a violation
        wherever they appear.
      - `$ref`: MUST be the literal prefix `"#/$defs/"` followed by a
        token that `re.fullmatch(r"(?:[A-Za-z0-9_.-]|~0|~1)+", token)`
        (anchored end to end, so `%`, raw `/`, and any malformed `~`
        sequence all fail). The token is then RFC6901-decoded (`~1` ->
        `/` before `~0` -> `~`) and must name a PRESENT member of the
        document's own TOP-LEVEL `$defs` whose value is a dict or a
        JSON boolean. Anything else is a violation.

    No `$ref`-target worklist, no per-key visited-set: the scan does not
    "follow" a `$ref` to decide what to visit next -- every node is
    visited exactly once via plain recursive descent, so a `$defs` entry
    that nothing in the document actually references is still scanned
    (and a violation inside it -- e.g. a malformed nested `$ref` or a
    stray `$anchor` -- is still caught), and a genuine `a`<->`b`
    reference cycle is automatically fine (each side's target need only
    EXIST; nothing here ever re-enters a target's own body because a
    `$ref` pointed at it). Never raises; returns a bare bool so the
    caller can emit the SAME fixed `RULE_CONTEXT_COMPONENT_UNREADABLE`
    diagnostic every other fixed-component defect uses -- no new rule
    vocabulary."""
    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        defs = {}

    def _ref_violates(value: Any) -> bool:
        if not isinstance(value, str):
            return True
        if not value.startswith(_LOCAL_DEF_REF_PREFIX):
            return True  # external URI / bare "#" / non-$defs fragment
        token = value[len(_LOCAL_DEF_REF_PREFIX):]
        if not _REF_TOKEN_GRAMMAR_RE.fullmatch(token):
            return True  # "%..", raw "/", malformed "~", or an empty token
        def_key = _unescape_json_pointer_token(token)
        if def_key not in defs:
            return True  # missing target
        target = defs[def_key]
        return not isinstance(target, (dict, bool))  # malformed target shape

    def _walk(node: Any, at_root: bool) -> bool:
        if isinstance(node, dict):
            if not at_root and "$id" in node:
                return True  # nested $id: only the document root may declare one
            if "$dynamicRef" in node or "$anchor" in node or "$dynamicAnchor" in node:
                return True
            if "$ref" in node and _ref_violates(node["$ref"]):
                return True
            for value in node.values():
                if _walk(value, at_root=False):
                    return True
        elif isinstance(node, list):
            for item in node:
                if _walk(item, at_root=False):
                    return True
        return False

    return _walk(schema, at_root=True)


def _load_fixed_components_cache(errors: Errors, cal_dir: Path = HERE, repo_root: Path = REPO_ROOT, base_commit_sha: str = BASE_COMMIT_SHA) -> dict[str, Any]:
    """SAN-881 PASS-1 FINAL CLOSURE CORRECTION: Tier-0 SINGLE-SOURCE
    cache. Every one of the ten file-backed fixed labeling-context
    components (`corpus_inputs.json`, `evaluation_profile.json`, the six
    schema files, the algorithm doc, the tables doc) is read EXACTLY
    ONCE, HERE, via the SAME no-follow custody-read primitive
    (`_snapshot_regular_file`) the staged reveal pipeline's Tier 2 uses
    for bundle members and nonce files -- so a leaf symlink at a fixed
    component's own pinned path is rejected exactly like a leaf symlink
    at a staged bundle member, and instrumentation of ALL security-
    relevant reads lives at one syscall boundary. The resulting cached
    raw bytes and parsed values are what `check_schemas_self_valid`,
    `check_commitment` (context-hash recomputation + declared-component
    comparison), `main()`'s corpus/profile/tables consumers, and the
    staged schema-validation gate (`check_stage_schema_validity`) all
    consume -- NONE of them independently re-reads a fixed component
    from disk after this cache is built.

    NEVER raises: a missing (including a rejected leaf symlink),
    unreadable, unparseable (for the JSON-shaped components), WRONG
    TOP-LEVEL TYPE (SAN-881 PASS-1 CORRECTION -- PARSE-SUCCESS != VALID
    VALUE: `corpus_inputs.json` must parse to a `list`, `evaluation_profile.json`
    and the tables doc must parse to a `dict`, and each of the six
    schema files must parse to a `dict`; a parsed JSON `null`, or any
    other wrong-shaped value, is rejected here even though `json.loads`
    itself raised nothing), or self-invalid component is a single fixed
    `RULE_CONTEXT_COMPONENT_UNREADABLE` diagnostic PER COMPONENT NAME --
    `base_commit_sha` is a constant and can never fail. For the six
    schema files, "self-invalid" additionally covers EXECUTABLE $defs
    VALIDATION (SAN-881 PASS-1 CORRECTION): every named $defs branch this
    module actually consumes via `_build_named_schema`
    (`_SCHEMA_NAMED_BRANCHES` above -- the author envelope, both reviewer
    envelopes, and both labels branches) is itself built and
    `check_schema`'d here, so a missing or malformed branch fails HERE,
    never as an uncaught KeyError/AttributeError the first time a later
    consumer builds that branch; AND (SAN-881 PASS-1 FINAL RESOLVER
    CORRECTION) a FULL-DOCUMENT STRUCTURAL LINT, for ALL SIX schema
    files, unconditionally, over a closed v1 reference dialect:
    `_schema_ref_integrity_violation` scans the document's COMPLETE JSON
    tree exactly once (every dict/list, including every `$defs` entry,
    regardless of reachability) and requires `$id` to appear ONLY at the
    document root, `$dynamicRef`/`$anchor`/`$dynamicAnchor` to appear
    NOWHERE, and every `$ref` to match EXACTLY `"#/$defs/<token>"` under
    a closed token grammar (see that function's docstring) naming a
    present, well-formed `$defs` member of the SAME document --
    `check_schema` (both the root pass above and the named-branch pass)
    never dereferences `$ref` targets and has no opinion on `$id`
    placement, so a schema whose consumed branch exists and is itself
    syntactically valid, but which transitively `$ref`s a `$defs` key
    missing from the SAME document, or nests an `$id` that rebases
    fragment resolution for a reachable sub-schema, or uses a `$ref`
    token jsonschema's own URI-percent-decoding would resolve to a
    DIFFERENT key than a literal string comparison would, would
    otherwise still pass every check above cleanly and crash (or
    silently mis-resolve) the first real consumer that instance-validates
    against it (`jsonschema.exceptions._WrappedReferencingError` /
    `referencing.exceptions.PointerToNowhere`). Component names are
    drawn exclusively from the fixed `LABELING_CONTEXT_COMPONENT_NAMES`
    tuple / `SCHEMA_FILES`, never attacker-controlled, so echoing one is
    safe. Never a component's own bytes, never a traceback, never an
    absolute path.

    Returns a dict:
      `ok` -- the OUTER-GATE operand `fixed_components_ok`: True iff
        every one of the ten file-backed components read, parsed
        (where JSON-shaped), matched its required top-level type, and
        (for the six schemas) self-validated cleanly INCLUDING every
        consumed $defs branch AND full referential integrity.
      `corpus`, `profile`, `tables` -- parsed JSON value, or None if
        that component failed (independently of whether any OTHER
        component failed).
      `schema` -- `{filename: parsed schema dict}`, containing an entry
        ONLY for a schema file that individually read, parsed, matched
        the required `dict` top-level type, passed
        `Draft202012Validator.check_schema()` at its own root, passed
        `check_schema()` for every named branch in `_SCHEMA_NAMED_BRANCHES`
        it defines, AND passed the full referential-integrity walk.
      `components` -- the eleven pinned `{name, sha256}` structures
        (built from these SAME read bytes, in
        `LABELING_CONTEXT_COMPONENT_NAMES` order) -- None unless `ok`
        is True (a hash built from a partially-missing component set
        could never be safely trusted).
      `context_hash` -- `SHA256` of the concatenation of the eleven
        components' raw 32-byte digests -- None unless `ok` is True.
    """
    ok = True
    digest_hex: dict[str, str] = {"base_commit_sha": sha256_hex(base_commit_sha.encode("ascii"))}

    def _read_json_component(name: str, expected_type: type | tuple[type, ...] | None = None) -> Any:
        nonlocal ok
        path = _fixed_component_path(name, cal_dir, repo_root)
        raw = _snapshot_regular_file(path)
        if raw is None:
            errors.add(f"{name}: rule={RULE_CONTEXT_COMPONENT_UNREADABLE}")
            ok = False
            return None
        digest_hex[name] = sha256_hex(raw)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            errors.add(f"{name}: rule={RULE_CONTEXT_COMPONENT_UNREADABLE}")
            ok = False
            return None
        # SAN-881 PASS-1 CORRECTION: PARSE-SUCCESS != VALID VALUE. A
        # parsed JSON `null` (or any other wrong top-level type -- a list
        # where a dict is required, a dict where a list is required, a
        # boolean where an object is required, ...) is NOT a valid fixed
        # component merely because `json.loads` accepted it -- it must
        # gate `ok` False HERE, with the SAME fixed diagnostic, never
        # silently pass through as a wrongly-shaped value that crashes a
        # far-downstream consumer instead (AttributeError / KeyError /
        # TypeError with no relationship to this read at all).
        if expected_type is not None and not isinstance(parsed, expected_type):
            errors.add(f"{name}: rule={RULE_CONTEXT_COMPONENT_UNREADABLE}")
            ok = False
            return None
        return parsed

    corpus = _read_json_component("corpus_inputs.json", expected_type=list)
    profile = _read_json_component("evaluation_profile.json", expected_type=dict)

    schema_by_name: dict[str, Any] = {}
    for filename in SCHEMA_FILES:
        component_name = f"schemas/{filename}"
        parsed = _read_json_component(component_name, expected_type=dict)
        if parsed is None:
            continue
        if Draft202012Validator is None:
            errors.add(f"{component_name}: rule={RULE_JSONSCHEMA_MODULE_MISSING}")
            ok = False
            continue
        try:
            Draft202012Validator.check_schema(parsed)
        except Exception:  # noqa: BLE001
            errors.add(f"{component_name}: rule={RULE_CONTEXT_COMPONENT_UNREADABLE}")
            ok = False
            continue
        schema_by_name[filename] = parsed

    # SAN-881 PASS-1 CORRECTION: EXECUTABLE $defs VALIDATION. A schema
    # file passing `Draft202012Validator.check_schema()` at its OWN ROOT
    # (above) proves the document itself is a self-valid JSON Schema --
    # it does NOT prove every NAMED $defs branch this module actually
    # consumes via `_build_named_schema` (`_SCHEMA_NAMED_BRANCHES` above)
    # is even present, let alone that constructing a standalone schema
    # from it (embedding `$defs`, dropping the enclosing root `oneOf`)
    # itself passes `check_schema`. `check_schema` never dereferences
    # `$ref` targets, so a schema whose root still `$ref`s a $defs key
    # that has gone missing still passes root-level `check_schema`
    # cleanly -- the gap surfaces only the first time a real consumer
    # (e.g. commitment.json's authorEnvelope check) builds that specific
    # branch, as an uncaught KeyError (missing key) or, for a
    # non-schema-shaped $defs entry / a non-dict top-level schema value
    # that still individually passed `check_schema` (a bare `true`/`false`
    # boolean schema is legal JSON Schema), an uncaught AttributeError.
    # Every branch this module can ever be asked to build is built and
    # `check_schema`'d HERE, unconditionally, during cache construction,
    # so a bad branch fails `fixed_components_ok` (via
    # `schemas_self_valid_ok`) with the SAME fixed diagnostic instead of
    # crashing a later consumer. A schema failing this pass is evicted
    # from `schema_by_name` entirely -- no downstream consumer can ever
    # retrieve (and build a branch from) a schema this cache itself
    # could not fully validate.
    for schema_filename, def_names in _SCHEMA_NAMED_BRANCHES.items():
        schema = schema_by_name.get(schema_filename)
        if schema is None:
            continue
        defs = schema.get("$defs")
        branches_ok = isinstance(defs, dict)
        if branches_ok:
            for def_name in def_names:
                if def_name not in defs:
                    branches_ok = False
                    break
                try:
                    Draft202012Validator.check_schema(_build_named_schema(schema, def_name))
                except Exception:  # noqa: BLE001
                    branches_ok = False
                    break
        if not branches_ok:
            errors.add(f"schemas/{schema_filename}: rule={RULE_CONTEXT_COMPONENT_UNREADABLE}")
            ok = False
            del schema_by_name[schema_filename]

    # SAN-881 PASS-1 FINAL RESOLVER CORRECTION: FULL-DOCUMENT STRUCTURAL
    # LINT, for ALL SIX schema files still present in `schema_by_name`
    # (i.e. that already survived root `check_schema` and, where
    # applicable, the named-branch pass above) -- not merely
    # `commitment_schema.json` / `labels_schema.json`, the only two
    # `_SCHEMA_NAMED_BRANCHES` covers. `check_schema` validates syntax
    # only: it never dereferences a `$ref` target and has no opinion on
    # WHERE a nested `$id` appears, so a schema whose consumed branch
    # exists and is itself syntactically valid, but which transitively
    # `$ref`s a `$defs` key missing from the SAME document, or nests an
    # `$id` on a reachable `$defs` entry (rebasing fragment resolution
    # for everything inside it), or uses a `$ref` token that jsonschema's
    # own URI-percent-decoding would resolve to a key OTHER than a
    # literal string match, still reaches here unevicted --
    # `_schema_ref_integrity_violation` scans the document's COMPLETE
    # JSON tree exactly once (see its docstring / the module comment
    # above it for the closed-dialect design: root-only `$id`, no
    # `$dynamicRef`/`$anchor`/`$dynamicAnchor` anywhere, and a `$ref`
    # token grammar that forbids `%` and raw `/` outright, so the
    # percent-decode ambiguity can never arise) and catches exactly
    # those gaps, for every one of the six files uniformly, independent
    # of whether this module's own `main()` happens to instance-validate
    # that specific schema's content (design_metadata_schema.json /
    # coverage_manifest_schema.json are validated only under a real
    # `--sealed-dir` or staged `--reveal-stage contract` run;
    # freeze_manifest_schema.json / reveal_verification_ledger_schema.json
    # are never instance-validated by this module AT ALL -- only by
    # measure.py / benchmark.py -- so without this pass a broken schema
    # in either would be a SILENT gap here, not even a crash, until a
    # caller in one of those sibling modules hit it). A schema failing
    # this pass is evicted from `schema_by_name` -- the SAME fixed
    # diagnostic, no new rule vocabulary, no traceback -- and (since
    # eviction is a dict `del`) can never be double-processed even
    # though a schema failing BOTH this pass and the named-branch pass
    # above would already be absent here.
    for schema_filename in list(schema_by_name):
        schema = schema_by_name[schema_filename]
        if _schema_ref_integrity_violation(schema):
            errors.add(f"schemas/{schema_filename}: rule={RULE_CONTEXT_COMPONENT_UNREADABLE}")
            ok = False
            del schema_by_name[schema_filename]

    algorithm_path = _fixed_component_path("algorithm", cal_dir, repo_root)
    algorithm_raw = _snapshot_regular_file(algorithm_path)
    if algorithm_raw is None:
        errors.add(f"algorithm: rule={RULE_CONTEXT_COMPONENT_UNREADABLE}")
        ok = False
    else:
        digest_hex["algorithm"] = sha256_hex(algorithm_raw)

    tables = _read_json_component("tables", expected_type=dict)

    components = None
    context_hash = None
    if ok:
        components = [{"name": n, "sha256": digest_hex[n]} for n in LABELING_CONTEXT_COMPONENT_NAMES]
        context_hash = compute_labeling_context_hash([bytes.fromhex(c["sha256"]) for c in components])

    return {
        "ok": ok, "corpus": corpus, "profile": profile, "tables": tables,
        "schema": schema_by_name, "algorithm_raw": algorithm_raw,
        "components": components, "context_hash": context_hash,
    }


def check_fixed_context_components(errors: Errors, cal_dir: Path = HERE, repo_root: Path = REPO_ROOT) -> bool:
    """SAN-881 PASS-1 CLOSURE PATCH -- OUTER-GATE operand `fixed_components_ok`.
    SAN-881 PASS-1 FINAL CLOSURE CORRECTION: thin wrapper over the Tier-0
    single-source cache (`_load_fixed_components_cache`) -- preserved as
    its own function/signature since it is independently unit-tested,
    but no longer performs its own, second, independent disk read: every
    diagnostic below is produced by the SAME cache-building pass
    `main()` uses for corpus/profile/schema/tables consumption."""
    return _load_fixed_components_cache(errors, cal_dir, repo_root)["ok"]


def compute_artifact_commitment(artifact_name: str, nonce: bytes, context_hash: bytes, artifact_bytes: bytes) -> str:
    """domain-separated SHA256 per commitment.json's commitment_algorithm.formula:
    SHA256("sanna-calibration-commitment/1" || NUL || artifact_name || NUL ||
    raw_32_byte_nonce || raw_32_byte_labeling_context_hash || exact_artifact_bytes)
    """
    if len(nonce) != 32:
        raise ValueError(f"nonce must be exactly 32 raw bytes, got {len(nonce)}")
    if len(context_hash) != 32:
        raise ValueError(f"labeling_context_hash must be exactly 32 raw bytes, got {len(context_hash)}")
    h = hashlib.sha256()
    h.update(DOMAIN_SEPARATOR)
    h.update(b"\x00")
    h.update(artifact_name.encode("ascii"))
    h.update(b"\x00")
    h.update(nonce)
    h.update(context_hash)
    h.update(artifact_bytes)
    return h.hexdigest()


def verify_reveal(commitment_hex: str, artifact_name: str, nonce: bytes, context_hash: bytes, artifact_bytes: bytes) -> bool:
    """Recompute the commitment from revealed bytes and compare, constant-shape."""
    try:
        recomputed = compute_artifact_commitment(artifact_name, nonce, context_hash, artifact_bytes)
    except ValueError:
        return False
    return recomputed == commitment_hex


# ---------------------------------------------------------------------
# Public-artifact checks
# ---------------------------------------------------------------------

def check_schemas_self_valid(errors: Errors, cache: dict[str, Any]) -> bool:
    """Returns the OUTER-GATE operand `schemas_self_valid_ok` (SAN-881
    PASS-1 CLOSURE PATCH). SAN-881 PASS-1 FINAL CLOSURE CORRECTION:
    consumes the Tier-0 single-source cache (`_load_fixed_components_cache`)
    -- the six schema files are read and self-validated ONCE, by that
    cache-building pass; this function never re-reads or re-validates
    them, and never emits a duplicate diagnostic for a failure the cache
    already reported under `RULE_CONTEXT_COMPONENT_UNREADABLE`. True iff
    jsonschema is available and every one of the six schema files is
    present in `cache["schema"]` (present there only if it individually
    read, parsed, AND passed `Draft202012Validator.check_schema()`)."""
    if Draft202012Validator is None:
        errors.add(f"schemas: rule={RULE_MISSING_SCHEMA} (jsonschema not installed)")
        return False
    return set(cache["schema"]) == set(SCHEMA_FILES)


def _validate_against_schema(errors: Errors, artifact_name: str, schema: dict, instance: Any, record_index: int | None = None) -> None:
    if Draft202012Validator is None:
        # Fails closed: a missing jsonschema MODULE must never silently
        # skip validation (SAN-881 Phase-A correction). Every caller of
        # this helper still runs its own structural checks, but the
        # schema-shape layer is otherwise entirely unenforced without this.
        errors.add(f"{artifact_name}: rule={RULE_JSONSCHEMA_MODULE_MISSING}")
        return
    validator = Draft202012Validator(schema)
    for _err in validator.iter_errors(instance):
        idx = f"[{record_index}]" if record_index is not None else ""
        errors.add(f"{artifact_name}{idx}: rule={RULE_SCHEMA_INVALID}")


# ---------------------------------------------------------------------
# SAN-881 PASS-1 CORRECTION ROUND root repair: SPECIFIC-BRANCH schema
# validation. `_validate_against_schema` above validates against a
# schema's OWN ROOT -- for a oneOf-discriminated schema (commitment_schema.json,
# labels_schema.json) that means "matches ANY of the oneOf branches",
# which lets a REVIEWER envelope pass as an AUTHOR envelope (or a
# contract-shaped labels file pass at the semantic stage) merely because
# it matches a DIFFERENT branch than the caller actually needs. The
# helpers below validate against ONE named $defs branch SPECIFICALLY,
# chosen by the CALLER'S OWN CONTEXT (which file this is, which stage is
# selected) -- never by inspecting the instance's own discriminant field
# first. Collapsed to AT MOST ONE fixed-vocabulary error per artifact
# (mirrors a top-level oneOf failure, which jsonschema itself reports as
# ONE error with an empty path) -- never a per-field explosion, which
# would multiply commitment.json's pinned transitional error count.
# ---------------------------------------------------------------------

def _build_named_schema(schema: dict, def_name: str) -> dict:
    """Standalone schema object for schema['$defs'][def_name], embedding
    the full $defs dict so internal $ref resolution ("#/$defs/...") still
    works, WITHOUT the enclosing root oneOf.

    SAN-881 PASS-1 FINAL GATING CORRECTION (GENERATED-SCHEMA VALIDITY):
    the synthetic `$id` is a PATH SEGMENT appended after the base
    schema's own `$id` (never a `#`-prefixed JSON-pointer FRAGMENT). The
    JSON Schema 2020-12 metaschema's own `$id` pattern
    (`^[^#]*#?$`, "non-empty fragments not allowed") forbids a
    JSON-pointer fragment in `$id` -- `$id` may carry AT MOST a trailing
    bare `#`, never `#/$defs/...`. A fragment-bearing synthetic `$id`
    (the prior construction) makes every branch schema built by this
    function itself INVALID under Draft202012Validator.check_schema(),
    even though it still happened to validate instances correctly --
    "generated but never itself schema-checked" is exactly the kind of
    drift this correction closes. Internal `#/$defs/...` $ref resolution
    is unaffected: those are same-document JSON-pointer fragments
    resolved against the embedded `$defs` dict below, independent of the
    resource's own `$id` value."""
    base_id = schema.get("$id") or ""
    return {
        "$schema": schema.get("$schema"),
        "$id": f"{base_id}/{def_name}" if base_id else def_name,
        **schema["$defs"][def_name],
        "$defs": schema["$defs"],
    }


def _is_valid_specific(schema: dict, def_name: str | None, instance: Any) -> bool:
    """def_name=None validates against the schema's own root (used for
    design_metadata_schema.json / coverage_manifest_schema.json, which
    are single-shape schemas with no oneOf to disambiguate)."""
    target = schema if def_name is None else _build_named_schema(schema, def_name)
    return Draft202012Validator(target).is_valid(instance)


def _validate_specific(errors: Errors, artifact_name: str, schema: dict, def_name: str | None, instance: Any) -> bool:
    """Whole-instance validation against ONE specific schema shape,
    collapsed to AT MOST ONE fixed-vocabulary error. Returns True iff
    `instance` is schema-valid against that SPECIFIC shape. Fails closed
    (one error, False) if the jsonschema module is unavailable."""
    if Draft202012Validator is None:
        errors.add(f"{artifact_name}: rule={RULE_JSONSCHEMA_MODULE_MISSING}")
        return False
    if not _is_valid_specific(schema, def_name, instance):
        errors.add(f"{artifact_name}: rule={RULE_SCHEMA_INVALID}")
        return False
    return True


def check_corpus_inputs(errors: Errors, corpus: list[dict]) -> dict[str, dict]:
    """Structural checks (allowlist, ordinals relative to list position,
    tier_1-only, dup-tuple, ENV-cap statics). Count-against-160 is
    checked separately by the caller so this function stays toy-testable
    on corpora of any size."""
    by_id: dict[str, dict] = {}
    seen_tuples: dict[tuple, int] = {}
    for idx, rec in enumerate(corpus):
        expected_id = f"cal:{idx:03d}"
        if rec.get("id") != expected_id:
            errors.add(f"corpus_inputs.json[{idx}]: rule={RULE_ID_ORDINAL_MISMATCH}")
        by_id[rec.get("id", expected_id)] = rec

        keys = set(rec.keys())
        has_context = "context" in keys
        has_sources = "context_sources" in keys
        if has_context == has_sources:
            errors.add(f"{rec.get('id')}: rule={RULE_CONTEXT_SHAPE}")
        allowed = {"id", "output"} | ({"context"} if has_context else {"context_sources"})
        if keys != allowed:
            errors.add(f"{rec.get('id')}: rule={RULE_DISALLOWED_KEYS}")

        if has_sources:
            for s_idx, source in enumerate(rec["context_sources"]):
                if set(source.keys()) != {"text", "tier"}:
                    errors.add(f"{rec.get('id')}.context_sources[{s_idx}]: rule={RULE_SOURCE_SHAPE}")
                if source.get("tier") != "tier_1":
                    errors.add(f"{rec.get('id')}.context_sources[{s_idx}]: rule={RULE_NON_TIER1}")

        ctx_text = rec.get("context") or " ".join(s["text"] for s in rec.get("context_sources", []))
        out_text = rec.get("output", "")
        key = (ctx_text, out_text)
        if key in seen_tuples:
            errors.add(f"{rec.get('id')}: rule={RULE_DUPLICATE_TUPLE}")
        seen_tuples[key] = idx

        # ENV-cap statics (field bytes, sentence counts) -- generous
        # static ceilings; the corpus is breach-free by construction.
        if len(out_text.encode("utf-8")) > 1_048_576:
            errors.add(f"{rec.get('id')}: rule={RULE_FIELD_BYTES_EXCEEDED}")
        if len(ctx_text.encode("utf-8")) > 1_048_576:
            errors.add(f"{rec.get('id')}: rule={RULE_FIELD_BYTES_EXCEEDED}")
    return by_id


def check_evaluation_profile(errors: Errors, profile: Any) -> None:
    """SAN-881 PASS-1 FINAL CLOSURE CORRECTION: shape-safe against
    `profile` being an ARBITRARY JSON shape (a list, a string, a number,
    null -- not merely a dict with malformed fields), via `_safe_get`
    -- never raises. `evaluation_profile.json` now comes from the Tier-0
    cache (a genuinely-parsed JSON value of ANY shape), not a
    caller-guaranteed dict."""
    if _safe_get(profile, "corpus_version") != EXPECTED_CORPUS_VERSION:
        errors.add(f"evaluation_profile.json: rule={RULE_CORPUS_VERSION}")
    if _safe_get(profile, "scope") != ["C1", "C2", "C3", "C4"]:
        errors.add(f"evaluation_profile.json: rule={RULE_PROFILE_SCOPE}")
    pins = _safe_get(profile, "spec_pins", {})
    if _safe_get(pins, "algorithm_sha256") != "49c138595fde5ee517d00d6b41eb815cf1016213a0cb7978ef258560cf5a4c59":
        errors.add(f"evaluation_profile.json: rule={RULE_SPEC_PIN_MISMATCH}")
    if _safe_get(pins, "tables_sha256") != "0a18dd94bc811bb3166a4f8812e78f2b053a9f8f083b781a21fb0f8371f54ecc":
        errors.add(f"evaluation_profile.json: rule={RULE_SPEC_PIN_MISMATCH}")


# ---------------------------------------------------------------------
# SAN-881 PASS-1 FINAL GATING CORRECTION: shape-safe envelope boundary.
# Every pre-schema accessor over an author/reviewer envelope must
# tolerate an ARBITRARY top-level JSON shape (a list, a string, a
# number, null, ...) and an arbitrary DECLARED VALUE within an
# otherwise-dict envelope (a non-string / unhashable artifact_name, a
# numeric commitment_hex, ...) -- fixed-code diagnostic, never a
# traceback, never a path disclosure. This is strictly a robustness
# boundary: it never widens what counts as VALID, only what counts as a
# safely-diagnosed INVALID.
# ---------------------------------------------------------------------

def _safe_get(obj: Any, key: str, default: Any = None) -> Any:
    """dict.get, but tolerates a non-dict `obj` (list, str, int, None,
    ...) by returning `default` instead of raising."""
    return obj.get(key, default) if isinstance(obj, dict) else default


_UNHASHABLE_MARKER = object()


def _hashable_or_marker(value: Any) -> Any:
    """Returns `value` unchanged if hashable, else a private sentinel
    that can never equal any real artifact name -- used ONLY for set
    membership over untrusted envelope-declared values (e.g.
    artifact_name), so an unhashable declared value (a list, a dict)
    safely contributes to a "names mismatch" rather than raising."""
    try:
        hash(value)
        return value
    except TypeError:
        return _UNHASHABLE_MARKER


def _safe_artifact_label(name: Any) -> str:
    """Returns `name` for embedding in a `commitment.json[...]` error
    label ONLY when it is a member of the FIXED, known author-artifact
    vocabulary -- an attacker-declared artifact_name (arbitrary string,
    or a non-string/unhashable value) is NEVER echoed into error output;
    a fixed placeholder is used instead (nonce/name non-disclosure)."""
    return name if isinstance(name, str) and name in AUTHOR_ARTIFACT_NAMES else "UNKNOWN_ARTIFACT_NAME"


def check_commitment(errors: Errors, commitment: Any, cal_dir: Path = HERE, repo_root: Path = REPO_ROOT, cache: dict[str, Any] | None = None) -> dict[str, bool]:
    """Structural checks over commitment.json PLUS an unconditional,
    from-disk recomputation of labeling_context_hash -- this runs on
    every invocation of main(), not only under --sealed-dir. SAN-881
    PASS-1 CORRECTION ROUND (Section B) hardening: every accessor below
    is shape-safe against a malformed `author_commitments` (a non-list,
    or a list containing `None` / non-dict members) -- this function must
    NEVER raise, however garbled the input, since it is one of the
    "shape-safe accessors" a schema-invalid author envelope still runs
    through (see main()). SAN-881 PASS-1 FINAL GATING CORRECTION extends
    this tolerance to `commitment` itself being an arbitrary JSON shape
    (a top-level list, string, number, or null -- not merely a dict with
    malformed fields), and to individual declared values that are
    unhashable (`artifact_name: []`) or non-string-but-truthy
    (`commitment_hex: 12345`) -- neither raises, and neither is echoed
    into any error message unless it is one of the four fixed,
    known artifact names.

    SAN-881 PASS-1 CLOSURE PATCH: returns a dict of three additional,
    independently-computed OUTER-GATE operands `main()` folds into
    `author_gate_ok` -- `structural_ok` (artifact-set membership +
    commitment-hex shape + byte-length shape; NEVER corpus_version,
    which is subsumed by the authorEnvelope schema's own const:2 pin),
    `disk_context_ok` (the from-disk recomputed hash matches the
    declared hash), `declared_components_ok` (a v2 envelope's OWN
    declared component list matches the from-disk build; vacuously True
    whenever the cross-check does not apply -- a v1 envelope, or a
    hash mismatch already reported).

    SAN-881 PASS-1 FINAL CLOSURE CORRECTION: no longer independently
    recomputes anything from disk -- consumes the Tier-0 single-source
    cache (`cache`, built by `_load_fixed_components_cache`) instead of
    calling `compute_labeling_context_hash_from_disk` /
    `build_labeling_context_components`. When `cache` is omitted (every
    pre-existing direct caller), one is built fresh HERE, still via that
    SAME cache-loading routine -- so this function remains safe, and
    NEVER re-reads via the two functions named above, even when called
    in isolation. When `main()` passes its own single top-level cache
    in, no second read of any fixed component occurs anywhere in this
    module. A cache with `ok` False (a removed/unreadable/malformed/
    self-invalid fixed component) can never be trusted to prove a hash
    match: fails closed as a CONTEXT_HASH_MISMATCH, never an uncaught
    FileNotFoundError/OSError/JSONDecodeError. check_fixed_context_components
    / the cache's own per-component diagnostics are the independent,
    PER-COMPONENT record of this same failure class."""
    if cache is None:
        cache = _load_fixed_components_cache(errors, cal_dir, repo_root)
    structural_ok = True
    if _safe_get(commitment, "corpus_version") != EXPECTED_CORPUS_VERSION:
        errors.add(f"commitment.json: rule={RULE_CORPUS_VERSION}")
    raw_entries = _safe_get(commitment, "author_commitments", [])
    entries = raw_entries if isinstance(raw_entries, list) else []
    dict_entries = [c for c in entries if isinstance(c, dict)]
    names = {_hashable_or_marker(c.get("artifact_name")) for c in dict_entries}
    if names != AUTHOR_ARTIFACT_NAMES or len(dict_entries) != len(entries):
        errors.add(f"commitment.json: rule={RULE_COMMITMENT_ARTIFACT_SET}")
        structural_ok = False
    for c in dict_entries:
        label = _safe_artifact_label(c.get("artifact_name"))
        commitment_hex = c.get("commitment_hex")
        if not isinstance(commitment_hex, str) or len(commitment_hex) != 64:
            errors.add(f"commitment.json[{label}]: rule={RULE_COMMITMENT_HEX_SHAPE}")
            structural_ok = False
        byte_length = c.get("byte_length")
        if not isinstance(byte_length, int) or isinstance(byte_length, bool) or byte_length <= 0:
            errors.add(f"commitment.json[{label}]: rule={RULE_BYTE_LENGTH_SHAPE}")
            structural_ok = False
    ctx_hash = _safe_get(commitment, "labeling_context_hash") or ""
    if not isinstance(ctx_hash, str) or len(ctx_hash) != 64:
        errors.add(f"commitment.json: rule={RULE_CONTEXT_HASH_MISMATCH}")
        return {"structural_ok": structural_ok, "disk_context_ok": False, "declared_components_ok": False}

    if not cache["ok"] or cache["context_hash"] is None:
        errors.add(f"commitment.json: rule={RULE_CONTEXT_HASH_MISMATCH}")
        return {"structural_ok": structural_ok, "disk_context_ok": False, "declared_components_ok": False}
    recomputed = cache["context_hash"].hex()
    hash_mismatch = recomputed != ctx_hash

    # SAN-881 PASS-1 CORRECTION ROUND, Section C: for a v2 envelope
    # (never a v1-transitional one -- preserves the pinned four-line
    # transitional output), ADDITIONALLY require the envelope's OWN
    # declared labeling_context_components list to equal the cache's
    # `components` list exactly (names, order, hashes). The outer hash
    # still derives SOLELY from fixed disk paths/constants (never from
    # the envelope's declared list); this is a SEPARATE, additional
    # cross-check, collapsed into the SAME single CONTEXT_HASH_MISMATCH
    # rule so an otherwise-matching outer hash with a forged/stale
    # declared component list still fails with exactly one error, never
    # a fifth distinct rule.
    components_mismatch = False
    if not hash_mismatch and _safe_get(commitment, "corpus_version") == 2:
        expected_components = cache["components"]
        if expected_components is None or _safe_get(commitment, "labeling_context_components") != expected_components:
            components_mismatch = True

    if hash_mismatch or components_mismatch:
        errors.add(f"commitment.json: rule={RULE_CONTEXT_HASH_MISMATCH}")

    return {
        "structural_ok": structural_ok,
        "disk_context_ok": not hash_mismatch,
        "declared_components_ok": not components_mismatch,
    }


def check_author_commitment_order(errors: Errors, commitment: Any) -> bool:
    """Verifier-side pin (SAN-881 Phase-A correction item 4) -- the belt
    to commitment_schema.json's authorEnvelope.author_commitments
    prefixItems suspenders: author_commitments must be EXACTLY four
    entries whose artifact_name sequence equals AUTHOR_COMMITMENT_ORDER
    index-by-index. Catches a same-name/different-hash duplicate that
    replaces one of the four pinned names (which the older, order-blind
    set-based check_commitment check above cannot distinguish from a
    legitimately-missing name in every case) and fires independent of
    whether jsonschema is installed. SAN-881 PASS-1 CORRECTION ROUND
    (Section B): hardened against a non-list `author_commitments` (a
    string, dict, int, ...) -- never raises. SAN-881 PASS-1 FINAL GATING
    CORRECTION: also hardened against `commitment` itself being a
    non-dict top-level shape (list, string, number, null).

    SAN-881 PASS-1 CLOSURE PATCH: returns the OUTER-GATE operand
    `author_order_ok`."""
    raw_entries = _safe_get(commitment, "author_commitments", [])
    entries = raw_entries if isinstance(raw_entries, list) else []
    names = [e.get("artifact_name") if isinstance(e, dict) else None for e in entries]
    if names != list(AUTHOR_COMMITMENT_ORDER):
        errors.add(f"commitment.json: rule={RULE_COMMITMENT_ORDER_MISMATCH}")
        return False
    return True


# ---------------------------------------------------------------------
# Sealed-artifact checks (require --sealed-dir)
# ---------------------------------------------------------------------

def check_design_metadata(errors: Errors, design: dict, corpus_by_id: dict) -> dict[str, dict]:
    items = design.get("items", [])
    by_id: dict[str, dict] = {}
    if len(items) != 160:
        errors.add(f"design_metadata.json: rule={RULE_ITEM_COUNT}")

    per_check_stratum: dict[tuple, int] = {}
    facet_closed_list = {
        "facet:availability", "facet:refund_availability", "facet:exchange_availability",
        "facet:discount_availability", "facet:access_permission", "facet:approval_requirement",
        "facet:eligibility", "facet:cost", "facet:duration", "facet:limit",
    }

    for it in items:
        iid = it.get("item_id")
        if iid in by_id:
            errors.add(f"design_metadata.json[{iid}]: rule={RULE_DUPLICATE_ITEM_ID}")
        by_id[iid] = it
        if iid not in corpus_by_id:
            errors.add(f"design_metadata.json[{iid}]: rule={RULE_ITEM_NOT_IN_CORPUS}")

        check_id = it.get("target_check_id")
        stratum = it.get("target_stratum")
        if check_id not in CHECK_IDS:
            errors.add(f"{iid}: rule={RULE_INVALID_CHECK_ID}")
        if stratum not in STRATA:
            errors.add(f"{iid}: rule={RULE_INVALID_STRATUM}")
        per_check_stratum[(check_id, stratum)] = per_check_stratum.get((check_id, stratum), 0) + 1

        for ff in it.get("facet_families", []):
            if ff not in facet_closed_list:
                errors.add(f"{iid}: rule={RULE_FACET_NOT_CLOSED}")

        mp = it.get("minimal_pair_of")
        feat = it.get("introduced_feature")
        if stratum == "determinate_out_of_domain":
            if mp is None or feat is None:
                errors.add(f"{iid}: rule={RULE_DOD_MISSING_PAIR_FIELD}")
        else:
            if mp is not None or feat is not None:
                errors.add(f"{iid}: rule={RULE_NON_DOD_HAS_PAIR_FIELD}")

    for check_id in CHECK_IDS:
        for stratum in STRATA:
            n = per_check_stratum.get((check_id, stratum), 0)
            if n != 10:
                errors.add(f"design_metadata.json[{check_id}/{stratum}]: rule={RULE_STRATUM_COUNT}")

    return by_id


def _item_field_texts(rec: dict) -> list[str]:
    """SAN-881 PASS 2B.2 -- EVIDENCE BOUNDARIES: the item's independent
    logical text fields for fold-sequence search, kept STRICTLY SEPARATE
    (never joined/concatenated): the item's own direct `context` (if
    present) as ONE field, OR each `context_sources` entry's own `text`
    as its OWN separate field (mutually exclusive with `context` --
    check_corpus_inputs's RULE_CONTEXT_SHAPE enforces this upstream),
    PLUS `output` as its own field. A folded token sequence is searched
    WITHIN one returned field at a time -- see _fold_present_in_fields --
    so no sequence can ever be synthesized across a field/source
    boundary (e.g. one context_source ending "...at" immediately
    followed by another beginning "least..." must never read as the
    phrase "at least")."""
    fields: list[str] = []
    if rec.get("context") is not None:
        fields.append(rec["context"])
    else:
        for src in rec.get("context_sources", []):
            fields.append(src.get("text", ""))
    fields.append(rec.get("output", ""))
    return fields


def _fold_contains(haystack: tuple, needle: tuple) -> bool:
    """True iff `needle` (a non-empty folded-token tuple) occurs as a
    CONTIGUOUS subsequence of `haystack` (both already fold_sequence'd).
    An empty needle never "occurs" (vacuous match would defeat the
    presence/absence checks that call this)."""
    n = len(needle)
    if n == 0 or n > len(haystack):
        return False
    return any(haystack[i:i + n] == needle for i in range(len(haystack) - n + 1))


def _fold_present_in_fields(field_texts: list, needle: tuple) -> bool:
    """True iff `needle` occurs, as a CONTIGUOUS fold-sequence, within
    SOME ONE field of `field_texts` (each field folded and searched
    independently -- see _item_field_texts's own docstring for why
    fields are never joined before folding)."""
    return any(_fold_contains(fold_sequence(t), needle) for t in field_texts)


def _lookup_table_entries(tables_data: dict, table_path: str) -> Any:
    """Resolve a dotted table_path (e.g. 'comparators_v1' or
    'facets_v1.facet:availability.triggers') against the raw tables JSON."""
    node: Any = tables_data
    for part in table_path.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


_DOD_SIMPLE_KIND_TABLE = {
    "concept": "concept_v1",
    "unit": "units_v1",
    "condition_operator": "condition_operators_v1",
    "quantifier": "quant_v1",
    "excl_pair": "excl_v1",
    "complement_pair": "complement_v1",
}

_DOD_CLOSED_FACETS = frozenset({
    "facet:availability", "facet:refund_availability", "facet:exchange_availability",
    "facet:discount_availability", "facet:access_permission", "facet:approval_requirement",
    "facet:eligibility", "facet:cost", "facet:duration", "facet:limit",
})


def _dod_sem_exact_keys_ok(sem: dict, required: frozenset) -> bool:
    """SAN-881 PASS 2B.2-FIX defect 4 -- LITERAL PER-KIND SEMANTIC PARITY:
    intended_semantics' key set must equal `required` EXACTLY -- belt to
    the schema's own additionalProperties: false + required list, so a
    missing or extra field is caught validator-side too, independent of
    whether the caller's data ever passed schema validation."""
    return isinstance(sem, dict) and set(sem.keys()) == required


def _dod_kind_table_binding_ok(kind: Any, table_path: Any, sem: dict) -> bool:
    """SAN-881 PASS 2B.2 -- THE CLOSED DISCRIMINATED UNION's kind-to-table
    BINDING, validator-side (belt to design_metadata_schema.json's own
    per-kind allOf conditionals, which enforce the IDENTICAL ten
    combinations; a build-time test -- test_dod_schema_kind_vocabulary_
    matches_validator_kind_vocabulary -- asserts the two kind
    vocabularies stay in lockstep). Ten mutually exclusive non-null
    branches, EXACTLY: facet_trigger (a facets_v1.<facet>.triggers leaf
    whose OWN facet equals intended_semantics.facet, polarity POS, OR
    facetproj_v1), deny_trigger (a facets_v1.<facet>.deny_triggers leaf
    whose OWN facet equals intended_semantics.facet, polarity NEG --
    NEVER facetproj_v1), concept/unit/condition_operator/quantifier
    (their own single fixed table), definitive/hedge (their own single
    fixed table, EACH ALSO requiring intended_semantics.role to equal
    the kind name), excl_pair/complement_pair (their own single fixed
    table). Any other kind (including a since-removed 'comparator') or
    any table_path outside its kind's own closed set is a BINDING
    FAILURE -- the caller reports it via the SAME RULE_FEATURE_NOT_ABSENT
    code a genuine table-membership failure uses (see the RULE-CODE
    REUSE pin: 'Binding failure or prohibited comparator ->
    RULE_FEATURE_NOT_ABSENT'), never a new rule.

    SAN-881 PASS 2B.2-FIX defects 4/5 -- LITERAL PER-KIND SEMANTIC
    PARITY CONTRACT: this is ALSO where intended_semantics' own SHAPE is
    enforced, validator-side, mirroring design_metadata_schema.json's
    per-kind $defs exactly (a missing field, an extra field, a
    wrong-type field, or a wrong-domain/non-closed-value field are all
    BINDING FAILURES, same RULE_FEATURE_NOT_ABSENT code): facet leaf
    (exact {facet, polarity}; facet closed to the ten pinned families
    AND matching table_path; polarity matching kind); facet projection
    (exact {polarity, projects_to}; projects_to closed to the same ten
    families); concept (exact {canonical_concept}, a nonempty string);
    unit (exact {group, factor}; nonempty group; factor a JSON number
    EXCLUDING bool -- Python bool is an int subclass, so a bare
    isinstance(x, (int, float)) check alone would wrongly accept
    True/False); condition_operator (exact {kind, polarity, force},
    each closed); quantifier (exact {quantifier_class}, closed);
    definitive/hedge (exact {role, same_overclaim_class_as_table}; role
    matching kind; same_overclaim_class_as_table STRICTLY True --
    `is True`, never merely truthy); excl_pair/complement_pair (NO
    semantics object at all -- sem must be the empty dict
    feature.get("intended_semantics") normalizes an absent/null value
    to)."""
    if not isinstance(table_path, str):
        return False

    if kind in ("excl_pair", "complement_pair"):
        if sem != {}:
            return False
        return table_path == _DOD_SIMPLE_KIND_TABLE[kind]

    if kind == "concept":
        if not _dod_sem_exact_keys_ok(sem, frozenset({"canonical_concept"})):
            return False
        canonical_concept = sem.get("canonical_concept")
        if not isinstance(canonical_concept, str) or not canonical_concept:
            return False
        return table_path == _DOD_SIMPLE_KIND_TABLE[kind]

    if kind == "unit":
        if not _dod_sem_exact_keys_ok(sem, frozenset({"group", "factor"})):
            return False
        group = sem.get("group")
        factor = sem.get("factor")
        if not isinstance(group, str) or not group:
            return False
        if isinstance(factor, bool) or not isinstance(factor, (int, float)):
            return False
        return table_path == _DOD_SIMPLE_KIND_TABLE[kind]

    if kind == "condition_operator":
        if not _dod_sem_exact_keys_ok(sem, frozenset({"kind", "polarity", "force"})):
            return False
        if sem.get("kind") not in ("IF", "ONLY_IF", "SUBJECT_TO"):
            return False
        if sem.get("polarity") not in ("+", "-"):
            return False
        if sem.get("force") not in ("grant", "restriction"):
            return False
        return table_path == _DOD_SIMPLE_KIND_TABLE[kind]

    if kind == "quantifier":
        if not _dod_sem_exact_keys_ok(sem, frozenset({"quantifier_class"})):
            return False
        if sem.get("quantifier_class") not in ("universal", "existential", "abstain"):
            return False
        return table_path == _DOD_SIMPLE_KIND_TABLE[kind]

    if kind in ("definitive", "hedge"):
        if not _dod_sem_exact_keys_ok(sem, frozenset({"role", "same_overclaim_class_as_table"})):
            return False
        if sem.get("role") != kind:
            return False
        if sem.get("same_overclaim_class_as_table") is not True:
            return False
        return table_path == f"{kind}_v1"

    if kind == "facet_trigger":
        if table_path == "facetproj_v1":
            if not _dod_sem_exact_keys_ok(sem, frozenset({"polarity", "projects_to"})):
                return False
            if sem.get("polarity") not in ("POS", "NEG"):
                return False
            return sem.get("projects_to") in _DOD_CLOSED_FACETS
        if table_path.startswith("facets_v1.") and table_path.endswith(".triggers"):
            if not _dod_sem_exact_keys_ok(sem, frozenset({"facet", "polarity"})):
                return False
            if sem.get("facet") not in _DOD_CLOSED_FACETS:
                return False
            facet = table_path[len("facets_v1."):-len(".triggers")]
            if facet not in _DOD_CLOSED_FACETS:
                return False
            return facet == sem.get("facet") and sem.get("polarity") == "POS"
        return False

    if kind == "deny_trigger":
        if table_path.startswith("facets_v1.") and table_path.endswith(".deny_triggers"):
            if not _dod_sem_exact_keys_ok(sem, frozenset({"facet", "polarity"})):
                return False
            if sem.get("facet") not in _DOD_CLOSED_FACETS:
                return False
            facet = table_path[len("facets_v1."):-len(".deny_triggers")]
            if facet not in _DOD_CLOSED_FACETS:
                return False
            return facet == sem.get("facet") and sem.get("polarity") == "NEG"
        return False

    return False


def check_introduced_feature_absent_from_tables(errors: Errors, item_id: str, feature: dict, tables_data: dict) -> None:
    """Post-fold, EXACT-table-path absence: the feature's tokens/pair must
    not appear in the specific NAMED table (never merely 'absent
    globally'). Uses the pinned tokenizer/fold primitive fold_sequence,
    never the evaluator. SAN-881 PASS 2B.2: gated by
    _dod_kind_table_binding_ok FIRST -- a kind/table/facet/polarity/role
    binding mismatch (or a prohibited/unrecognized kind, e.g. the
    removed 'comparator') is itself a RULE_FEATURE_NOT_ABSENT failure,
    reported before any table lookup is even attempted.

    SAN-881 PASS 2B.2-FIX2: pair kinds (excl_pair/complement_pair) carry
    NO semantics object at all -- but `feature.get("intended_semantics")
    or {}` below normalizes ANY falsy present value ({}, None, [], "")
    to the SAME {} an absent property produces, making a PRESENT-but-
    falsy value indistinguishable from genuine absence to the `sem !=
    {}` check inside _dod_kind_table_binding_ok. The schema correctly
    rejects all four as an unexpected property; this explicit presence
    check runs BEFORE that normalization can erase it, so a pair kind
    with the key set at all -- regardless of value -- is a binding
    failure, same as a genuinely non-empty semantics object."""
    if feature is None:
        return
    kind = feature.get("kind")
    table_path = feature.get("table_path", "")
    if kind in ("excl_pair", "complement_pair") and "intended_semantics" in feature:
        errors.add(f"{item_id}: rule={RULE_FEATURE_NOT_ABSENT}")
        return
    sem = feature.get("intended_semantics") or {}
    if not isinstance(sem, dict):
        sem = {}
    if not _dod_kind_table_binding_ok(kind, table_path, sem):
        errors.add(f"{item_id}: rule={RULE_FEATURE_NOT_ABSENT}")
        return

    node = _lookup_table_entries(tables_data, table_path)
    if node is None:
        errors.add(f"{item_id}: rule={RULE_FEATURE_NOT_ABSENT}")
        return

    if kind in ("excl_pair", "complement_pair"):
        # SAN-881 PASS 2B.2: table ABSENCE compares the COMPLETE
        # UNORDERED PAIR against each table row, never individual-member
        # overlap -- a proposed pair sharing exactly one word with some
        # UNRELATED existing row (e.g. proposing (digital, cost) when
        # the table already has (digital, physical)) is genuinely
        # ABSENT and must not false-positive. Canonicalized as a SORTED
        # TWO-ELEMENT TUPLE of folded-sequence tuples -- never a set (a
        # set would collapse a degenerate same-fold pair's multiplicity).
        members = feature.get("members", [])
        if len(members) != 2:
            errors.add(f"{item_id}: rule={RULE_FEATURE_NOT_ABSENT}")
            return
        proposed = tuple(sorted(fold_sequence(" ".join(m)) for m in members))
        rows = node if isinstance(node, list) else []
        for row in rows:
            if not isinstance(row, list) or len(row) != 2:
                continue
            row_canon = tuple(sorted(fold_sequence(tok) for tok in row))
            if row_canon == proposed:
                errors.add(f"{item_id}: rule={RULE_FEATURE_NOT_ABSENT}")
                return
        return

    surface_tokens = feature.get("surface_tokens", [])
    target_fold = tuple(fold_sequence(" ".join(surface_tokens)))

    if kind == "quantifier":
        # CLASS-SCOPED absence (SAN-881 Phase-A correction): quant_v1 is a
        # dict of {quantifier_class: [token, ...]}, NOT a flat list -- the
        # feature's surface_tokens must be absent from ONLY its declared
        # intended_semantics.quantifier_class's own token list, never the
        # dict's top-level keys (which are class NAMES, not tokens, and
        # would never collide with a real surface token -- silently
        # bypassing this check for every quantifier feature).
        quant_class = (feature.get("intended_semantics") or {}).get("quantifier_class")
        class_node = node.get(quant_class) if isinstance(node, dict) else None
        entries: list = class_node if isinstance(class_node, list) else []
        for entry in entries:
            entry_fold = tuple(fold_sequence(entry)) if isinstance(entry, str) else None
            if entry_fold == target_fold:
                errors.add(f"{item_id}: rule={RULE_FEATURE_NOT_ABSENT}")
                return
        return

    entries: list = []
    if isinstance(node, list):
        entries = node
    elif isinstance(node, dict):
        entries = list(node.keys())

    for entry in entries:
        if isinstance(entry, dict) and "tokens" in entry:
            entry_fold = tuple(fold_sequence(" ".join(entry["tokens"])))
        elif isinstance(entry, str):
            entry_fold = tuple(fold_sequence(entry))
        else:
            continue
        if entry_fold == target_fold:
            errors.add(f"{item_id}: rule={RULE_FEATURE_NOT_ABSENT}")
            return


def check_minimal_pair_semantic_equivalence(errors: Errors, dod_item_id: str, dod_rec: dict, control_rec: dict, feature: dict) -> None:
    """Best-effort, executable proof that the swap is real (not just a
    metadata label). SAN-881 PASS 2B.2 -- EVIDENCE-BOUNDARY-RESPECTING,
    FOLD-SEQUENCE search (never a flattened-text substring match): every
    presence/absence test below searches `dod_rec` / `control_rec`'s OWN
    logical fields independently (direct context, EACH context_source,
    output -- via _item_field_texts / _fold_present_in_fields) so a
    phrase can never be "found" merely because two unrelated fields were
    concatenated.

    LEXICAL (one complete folded surface_tokens sequence): must occur,
    as a CONTIGUOUS fold sequence, in SOME ONE field of the dod item
    (else RULE_FEATURE_TOKENS_NOT_IN_ITEM); must NOT occur in ANY field
    of the control (else RULE_FEATURE_TOKENS_IN_CONTROL).

    PAIR (excl_pair/complement_pair, two complete folded member
    sequences): BOTH members must each independently occur in the dod
    item -- possibly in DIFFERENT fields, but an individual member's own
    multi-token fold sequence may never itself straddle a field boundary
    -- else RULE_FEATURE_TOKENS_NOT_IN_ITEM (fired once, regardless of
    whether one or both members are missing). Control leakage fires
    ONLY when the COMPLETE pair (both members) is found in the control;
    one overlapping member alone is allowed (RULE_FEATURE_TOKENS_IN_CONTROL)."""
    if feature is None:
        return
    dod_fields = _item_field_texts(dod_rec)
    control_fields = _item_field_texts(control_rec)
    kind = feature.get("kind")
    if kind in ("excl_pair", "complement_pair"):
        members = feature.get("members", [])
        if len(members) != 2:
            errors.add(f"{dod_item_id}: rule={RULE_FEATURE_TOKENS_NOT_IN_ITEM}")
            return
        member_folds = [fold_sequence(" ".join(m)) for m in members]
        if not all(_fold_present_in_fields(dod_fields, mf) for mf in member_folds):
            errors.add(f"{dod_item_id}: rule={RULE_FEATURE_TOKENS_NOT_IN_ITEM}")
        if all(_fold_present_in_fields(control_fields, mf) for mf in member_folds):
            errors.add(f"{dod_item_id}: rule={RULE_FEATURE_TOKENS_IN_CONTROL}")
        return

    surface_tokens = feature.get("surface_tokens", [])
    target_fold = fold_sequence(" ".join(surface_tokens))
    if not target_fold:
        # SAN-881 PASS 2B.2-FIX defect 3: a whitespace-only (or otherwise
        # entirely-punctuation) surface_tokens value folds to the empty
        # sequence -- this must not silently pass as "vacuously proven";
        # it is precisely the case where NO evidence for the introduced
        # feature exists in the DOD item at all.
        errors.add(f"{dod_item_id}: rule={RULE_FEATURE_TOKENS_NOT_IN_ITEM}")
        return
    if not _fold_present_in_fields(dod_fields, target_fold):
        errors.add(f"{dod_item_id}: rule={RULE_FEATURE_TOKENS_NOT_IN_ITEM}")
    if _fold_present_in_fields(control_fields, target_fold):
        errors.add(f"{dod_item_id}: rule={RULE_FEATURE_TOKENS_IN_CONTROL}")


def check_minimal_pair_control_same_semantics_in_table(
    errors: Errors, item_id: str, control_rec: dict, feature: dict, tables_data: dict,
) -> None:
    """SEMANTIC-EQUAL CONTROL proof (SAN-881 Phase-A correction; SAN-881
    PASS 2B.2 extends coverage + evidence discipline): the minimal-pair
    control's replacement must be proven IN-TABLE with EQUAL intended
    semantics to the dod item's introduced_feature -- same facet+polarity
    (facet_trigger/deny_trigger leaf kind), same projects_to (facet_trigger
    bound to facetproj_v1), kind+polarity+force (condition_operator),
    group+factor (unit), concept (concept), quantifier class (quantifier),
    a complete definitive_v1/hedge_v1 entry (definitive/hedge), or an
    EXACT ROW of the declared pair table (excl_pair/complement_pair).
    This is stronger than "any token from the same table is present": it
    proves the control's replacement token(s) belong to the SAME
    semantic-equivalence class the dod feature was swapped out of, using
    the pinned tables data as the equivalence-class source of truth.
    Presence is proven via a field-scoped fold-sequence search
    (_fold_present_in_fields over _item_field_texts(control_rec)), never
    a flattened-text substring match -- see check_minimal_pair_semantic_
    equivalence's own docstring for why field boundaries matter."""
    if feature is None or tables_data is None:
        return
    kind = feature.get("kind")
    sem = feature.get("intended_semantics") or {}
    control_fields = _item_field_texts(control_rec)

    def any_present(phrases: list) -> bool:
        return any(
            _fold_present_in_fields(control_fields, fold_sequence(p))
            for p in phrases if isinstance(p, str) and p
        )

    if kind in ("facet_trigger", "deny_trigger"):
        table_path = feature.get("table_path")
        if table_path == "facetproj_v1":
            target_projects_to = sem.get("projects_to")
            sibling_tokens = [tok for tok, target in tables_data.get("facetproj_v1", {}).items() if target == target_projects_to]
            if not sibling_tokens or not any_present(sibling_tokens):
                errors.add(f"{item_id}: rule={RULE_MINIMAL_PAIR_SAME_SEMANTICS}")
            return
        facet = tables_data.get("facets_v1", {}).get(sem.get("facet"))
        if facet is None:
            errors.add(f"{item_id}: rule={RULE_MINIMAL_PAIR_SAME_SEMANTICS}")
            return
        sibling_tokens = facet.get("triggers", []) if sem.get("polarity") == "POS" else facet.get("deny_triggers", [])
        if not any_present(sibling_tokens):
            errors.add(f"{item_id}: rule={RULE_MINIMAL_PAIR_SAME_SEMANTICS}")
    elif kind == "condition_operator":
        target = (sem.get("kind"), sem.get("polarity"), sem.get("force"))
        siblings = [e for e in tables_data.get("condition_operators_v1", [])
                    if (e.get("kind"), e.get("polarity"), e.get("force")) == target]
        if not siblings or not any(any_present([" ".join(e.get("tokens", []))]) for e in siblings):
            errors.add(f"{item_id}: rule={RULE_MINIMAL_PAIR_SAME_SEMANTICS}")
    elif kind == "unit":
        target = (sem.get("group"), sem.get("factor"))
        sibling_tokens = [tok for tok, meta in tables_data.get("units_v1", {}).items()
                           if (meta.get("group"), meta.get("factor")) == target]
        if not any_present(sibling_tokens):
            errors.add(f"{item_id}: rule={RULE_MINIMAL_PAIR_SAME_SEMANTICS}")
    elif kind == "concept":
        target_concept = sem.get("canonical_concept")
        sibling_tokens = [form for form, concept in tables_data.get("concept_v1", {}).items() if concept == target_concept]
        if not any_present(sibling_tokens):
            errors.add(f"{item_id}: rule={RULE_MINIMAL_PAIR_SAME_SEMANTICS}")
    elif kind == "quantifier":
        sibling_tokens = tables_data.get("quant_v1", {}).get(sem.get("quantifier_class"), [])
        if not any_present(sibling_tokens):
            errors.add(f"{item_id}: rule={RULE_MINIMAL_PAIR_SAME_SEMANTICS}")
    elif kind in ("definitive", "hedge"):
        # SAN-881 PASS 2B.2: previously UNHANDLED (silent no-op -- every
        # definitive/hedge DOD item's control passed this check
        # vacuously, regardless of whether the control genuinely
        # contained a same-table sibling word). definitive_v1/hedge_v1
        # are each a flat list of complete entries (single words or
        # short phrases, e.g. "without doubt", "it's possible") -- the
        # control must contain at least one COMPLETE entry.
        table_path = f"{kind}_v1"
        sibling_tokens = tables_data.get(table_path, [])
        if not isinstance(sibling_tokens, list) or not any_present(sibling_tokens):
            errors.add(f"{item_id}: rule={RULE_MINIMAL_PAIR_SAME_SEMANTICS}")
    elif kind in ("excl_pair", "complement_pair"):
        # SAN-881 PASS 2B.2: previously UNHANDLED (silent no-op). The
        # control must contain BOTH members of ONE EXACT ROW of the
        # DECLARED pair table (never a row from the other table, and
        # never one member from one row plus one member from another).
        table_path = feature.get("table_path")
        rows = tables_data.get(table_path, []) if isinstance(table_path, str) else []
        found_row = False
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, list) or len(row) != 2:
                continue
            if all(any_present([tok]) for tok in row):
                found_row = True
                break
        if not found_row:
            errors.add(f"{item_id}: rule={RULE_MINIMAL_PAIR_SAME_SEMANTICS}")


def check_dod_balance_and_pairs(errors: Errors, design_by_id: dict, semantic_by_key: dict, corpus_by_id: dict | None = None, tables_data: dict | None = None) -> None:
    for check_id in CHECK_IDS:
        dod_items = [it for it in design_by_id.values()
                     if it["target_check_id"] == check_id and it["target_stratum"] == "determinate_out_of_domain"]
        truths = {"VIOLATION": 0, "NO_VIOLATION": 0, "INDETERMINATE": 0}
        for it in dod_items:
            truth = semantic_by_key.get((it["item_id"], check_id), {}).get("semantic_truth")
            if truth in truths:
                truths[truth] += 1
            else:
                errors.add(f"{it['item_id']}/{check_id}: rule={RULE_DOD_TRUTH_INVALID}")
        if truths["VIOLATION"] != 5 or truths["NO_VIOLATION"] != 5 or truths["INDETERMINATE"] != 0:
            errors.add(f"design_metadata.json[{check_id}]: rule={RULE_DOD_TRUTH_BALANCE}")

    # Minimal pairs: one-way, unique, acyclic; control shares check+domain+
    # semantic_truth+scenario_id; same-semantics in-table replacement proof.
    control_usage: dict[str, str] = {}
    for it in design_by_id.values():
        if it["target_stratum"] != "determinate_out_of_domain":
            continue
        iid = it["item_id"]
        mp = it["minimal_pair_of"]
        control = design_by_id.get(mp)
        if control is None:
            errors.add(f"{iid}: rule={RULE_MINIMAL_PAIR_UNRESOLVED}")
            continue
        if control["target_stratum"] not in ("in_domain_nonviolation", "in_domain_violation"):
            errors.add(f"{iid}: rule={RULE_MINIMAL_PAIR_STRATUM}")
        if control["target_check_id"] != it["target_check_id"]:
            errors.add(f"{iid}: rule={RULE_MINIMAL_PAIR_CHECK}")
        if control["domain"] != it["domain"]:
            errors.add(f"{iid}: rule={RULE_MINIMAL_PAIR_DOMAIN}")
        control_truth = semantic_by_key.get((mp, it["target_check_id"]), {}).get("semantic_truth")
        expected_control_truth = "NO_VIOLATION" if control["target_stratum"] == "in_domain_nonviolation" else "VIOLATION"
        if control_truth != expected_control_truth:
            errors.add(f"{iid}: rule={RULE_MINIMAL_PAIR_CONTROL_TRUTH}")
        dod_truth = semantic_by_key.get((iid, it["target_check_id"]), {}).get("semantic_truth")
        if dod_truth != control_truth:
            errors.add(f"{iid}: rule={RULE_MINIMAL_PAIR_SAME_SEMANTICS}")
        # SAN-881 PASS 2B.2-FIX defect 1: the comment above this loop has
        # always claimed the control shares check+domain+semantic_truth+
        # scenario_id, but no scenario_id comparison existed until now --
        # a scenario-only mismatch produced zero diagnostics.
        if control.get("scenario_id") != it.get("scenario_id"):
            errors.add(f"{iid}: rule={RULE_MINIMAL_PAIR_SAME_SEMANTICS}")
        if mp == iid:
            errors.add(f"{iid}: rule={RULE_MINIMAL_PAIR_SELF}")
        if mp in control_usage:
            errors.add(f"{iid}: rule={RULE_MINIMAL_PAIR_REUSED}")
        control_usage[mp] = iid
        if control["target_stratum"] == "determinate_out_of_domain":
            errors.add(f"{iid}: rule={RULE_MINIMAL_PAIR_CYCLE}")

        feature = it.get("introduced_feature")
        if tables_data is not None and feature is not None:
            check_introduced_feature_absent_from_tables(errors, iid, feature, tables_data)
        if corpus_by_id is not None and feature is not None and iid in corpus_by_id and mp in corpus_by_id:
            check_minimal_pair_semantic_equivalence(
                errors, iid, corpus_by_id[iid], corpus_by_id[mp], feature)
            if tables_data is not None:
                check_minimal_pair_control_same_semantics_in_table(
                    errors, iid, corpus_by_id[mp], feature, tables_data)


def check_labels(errors: Errors, semantic: list[dict], contract: list[dict], design_by_id: dict):
    if len(semantic) != 640:
        errors.add(f"labels_author_semantic.json: rule={RULE_LABEL_COUNT}")
    if len(contract) != 640:
        errors.add(f"labels_author_contract.json: rule={RULE_LABEL_COUNT}")

    ALLOWED_SEMANTIC_KEYS = {"item_id", "check_id", "semantic_truth", "semantic_rationale"}
    semantic_by_key: dict[tuple, dict] = {}
    seen_pairs = set()
    for idx, r in enumerate(semantic):
        if set(r.keys()) != ALLOWED_SEMANTIC_KEYS:
            errors.add(f"labels_author_semantic.json[{idx}] {r.get('item_id')}/{r.get('check_id')}: rule={RULE_SEM_KEYS}")
        if r.get("semantic_truth") not in SEMANTIC_TO_OUTCOME:
            errors.add(f"labels_author_semantic.json[{idx}] {r.get('item_id')}/{r.get('check_id')}: rule={RULE_SEM_TRUTH_INVALID}")
        key = (r.get("item_id"), r.get("check_id"))
        if key in seen_pairs:
            errors.add(f"labels_author_semantic.json[{idx}] {r.get('item_id')}/{r.get('check_id')}: rule={RULE_DUP_SEM_PAIR}")
        seen_pairs.add(key)
        semantic_by_key[key] = r

    contract_by_key: dict[tuple, dict] = {}
    seen_pairs_c = set()
    for idx, r in enumerate(contract):
        key = (r.get("item_id"), r.get("check_id"))
        if key in seen_pairs_c:
            errors.add(f"labels_author_contract.json[{idx}] {r.get('item_id')}/{r.get('check_id')}: rule={RULE_DUP_CONTRACT_PAIR}")
        seen_pairs_c.add(key)
        contract_by_key[key] = r
        ct = r.get("contract_tuple", {})
        outcome = ct.get("outcome")
        reason = ct.get("outcome_reason")
        severity = ct.get("severity")
        advisory = ct.get("advisory")
        if outcome not in CLOSED_OUTCOMES:
            errors.add(f"{key[0]}/{key[1]}: rule={RULE_CONTRACT_OUTCOME_INVALID}")
        if reason not in OUTCOME_REASONS:
            errors.add(f"{key[0]}/{key[1]}: rule={RULE_CONTRACT_REASON_INVALID}")
        elif outcome in REASON_MATRIX and reason not in REASON_MATRIX[outcome]:
            # A well-formed reason code (e.g. "extraction_partial") that is
            # nonetheless not a member of ITS OWN outcome's allowed set
            # (e.g. paired with PASS, whose only valid reason is
            # detection_complete) -- the full locked reason matrix (SAN-881
            # Phase-A correction) is outcome-specific, not a flat allowlist.
            errors.add(f"{key[0]}/{key[1]}: rule={RULE_CONTRACT_REASON_OUTCOME_MISMATCH}")
        if outcome == "VIOLATION":
            expected_sev = "critical" if r.get("check_id") == "C1" else "warning"
            if severity != expected_sev:
                errors.add(f"{key[0]}/{key[1]}: rule={RULE_SEVERITY_MISMATCH}")
        else:
            if severity is not None:
                errors.add(f"{key[0]}/{key[1]}: rule={RULE_SEVERITY_MUST_BE_NULL}")
        if advisory is not False:
            errors.add(f"{key[0]}/{key[1]}: rule={RULE_ADVISORY_MUST_BE_FALSE}")
        if r.get("competence") not in ("IN_DOMAIN", "KNOWN_COVERAGE_GAP", "DELIBERATE_ABSTENTION"):
            errors.add(f"{key[0]}/{key[1]}: rule={RULE_COMPETENCE_INVALID}")

    expected_keys = {(iid, c) for iid in design_by_id for c in CHECK_IDS}
    if set(semantic_by_key) != expected_keys:
        errors.add(f"labels_author_semantic.json: rule={RULE_KEYSET_MISMATCH}")
    if set(contract_by_key) != expected_keys:
        errors.add(f"labels_author_contract.json: rule={RULE_KEYSET_MISMATCH}")

    for (iid, cid), r in contract_by_key.items():
        design_item = design_by_id.get(iid)
        if design_item is None:
            continue
        sem = semantic_by_key.get((iid, cid), {})
        truth = sem.get("semantic_truth")
        expected_outcome_from_truth = SEMANTIC_TO_OUTCOME.get(truth)
        comp = r.get("competence")
        if comp == "DELIBERATE_ABSTENTION" and truth != "INDETERMINATE":
            errors.add(f"{iid}/{cid}: rule={RULE_ABSTENTION_TRUTH_MISMATCH}")
        if truth == "INDETERMINATE" and comp != "DELIBERATE_ABSTENTION":
            errors.add(f"{iid}/{cid}: rule={RULE_INDETERMINATE_COMPETENCE}")
        if comp == "KNOWN_COVERAGE_GAP":
            if not (design_item["target_check_id"] == cid and design_item["target_stratum"] == "determinate_out_of_domain"):
                errors.add(f"{iid}/{cid}: rule={RULE_COVERAGE_GAP_SCOPE}")
        if design_item["target_check_id"] == cid and design_item["target_stratum"] in ("in_domain_nonviolation", "in_domain_violation"):
            if comp != "IN_DOMAIN":
                errors.add(f"{iid}/{cid}: rule={RULE_IN_DOMAIN_COMPETENCE}")
            if expected_outcome_from_truth and r["contract_tuple"]["outcome"] != expected_outcome_from_truth:
                errors.add(f"{iid}/{cid}: rule={RULE_IN_DOMAIN_OUTCOME_MAP}")

    return semantic_by_key, contract_by_key


# ---------------------------------------------------------------------
# Coverage manifest: schema + executable predicate proof
# ---------------------------------------------------------------------

def _word_present(token: str, lowered_text: str) -> bool:
    """Word-boundary substring match tolerant of adjacent punctuation
    (e.g. "guaranteed?", "nonrefundable.") -- naive space-padding alone
    misses a word directly followed by punctuation with no trailing space."""
    return re.search(r"(?<![a-z0-9'])" + re.escape(token.lower()) + r"(?![a-z0-9'])", lowered_text) is not None


def _predicate_facets(item_text: str, surface: str, tables_data: dict) -> bool:
    facet_key = surface.split(".", 1)[1] if "." in surface else surface
    facet_key = facet_key.split(".")[0]
    facet = tables_data.get("facets_v1", {}).get(facet_key)
    if not facet:
        return False
    lowered = item_text.lower()
    for trig in facet.get("triggers", []) + facet.get("deny_triggers", []):
        if _word_present(trig, lowered):
            return True
    if not facet.get("triggers") and not facet.get("deny_triggers"):
        # projection-only facet (facets_v1.json note: "reached via benefit
        # normalization of generic triggers"): triggered by a
        # facetproj_v1 key word that projects onto THIS facet, combined
        # with a generic_benefit_triggers_v1 word.
        facetproj = tables_data.get("facetproj_v1", {})
        projects_here = [word for word, target in facetproj.items() if target == f"facet:{facet_key.split(':', 1)[1]}"] if ":" in facet_key else []
        generic_triggers = tables_data.get("generic_benefit_triggers_v1", [])
        has_projection_word = any(_word_present(w, lowered) for w in projects_here)
        has_generic_trigger = any(_word_present(w, lowered) for w in generic_triggers)
        if has_projection_word and has_generic_trigger:
            return True
    return False


def _predicate_concept(item_text: str, surface: str, tables_data: dict) -> bool:
    concept_name = surface.split(".", 1)[1] if "." in surface else ""
    lowered = item_text.lower()
    for surface_form, concept in tables_data.get("concept_v1", {}).items():
        if concept == concept_name and surface_form.lower() in lowered:
            return True
    return False


def _predicate_comparators(item_text: str, surface: str, tables_data: dict) -> bool:
    trigger = surface.split(".", 1)[1] if "." in surface else ""
    lowered = item_text.lower()
    for entry in tables_data.get("comparators_v1", []):
        phrase = " ".join(entry["tokens"])
        if phrase.replace(" ", "_") == trigger or "_".join(entry["tokens"]) == trigger:
            return phrase.lower() in lowered
    return False


def _predicate_excl_or_complement(item_text: str, surface: str, table_key: str, tables_data: dict) -> bool:
    """Single-record predicate: at least one member present. Retained for
    direct unit-testability, but check_coverage_manifest no longer relies
    on this alone for excl_v1/complement_v1 surfaces -- see
    _pair_members_found_jointly below, which requires BOTH members,
    evaluated per-record against that record's own declared field only
    (never concatenated), possibly across multiple evidence records."""
    pair_name = surface.split(".", 1)[1] if "." in surface else ""
    lowered = item_text.lower()
    for pair in tables_data.get(table_key, []):
        name = "_".join(pair)
        if name == pair_name:
            return any(tok.lower() in lowered for tok in pair)
    return False


def _lookup_pair_members(tables_data: dict, table_key: str, pair_name: str) -> tuple[str, str] | None:
    for pair in tables_data.get(table_key, []):
        if "_".join(pair) == pair_name and len(pair) == 2:
            return pair[0], pair[1]
    return None


def _predicate_condition_operators(item_text: str, surface: str, tables_data: dict) -> bool:
    rest = surface.split(".", 1)[1] if "." in surface else ""
    parts = rest.split(".")
    if not parts:
        return False
    trigger_name = parts[0]
    lowered = item_text.lower()
    for entry in tables_data.get("condition_operators_v1", []):
        phrase = " ".join(entry["tokens"])
        if phrase.replace(" ", "_") == trigger_name:
            return phrase.lower() in lowered
    return False


def _predicate_quant(item_text: str, surface: str, tables_data: dict) -> bool:
    quant_class = surface.split(".", 1)[1] if "." in surface else ""
    lowered = item_text.lower()
    for tok in tables_data.get("quant_v1", {}).get(quant_class, []):
        if f" {tok.lower()} " in f" {lowered} ":
            return True
    return False


def _predicate_value_role(item_text: str, surface: str, tables_data: dict) -> bool:
    """value_role_v1 SYNTHETIC MEASURE-FACET VALUE-ROLE surfaces
    (value_role_v1.cost, value_role_v1.duration, value_role_v1.limit --
    SAN-881 CORRECTION PASS 2 rename of Pass-1's units_v1.facet:* naming)
    prove a genuine value+unit (or value+currency) pairing was expressed
    ALONGSIDE the measure facet's own trigger vocabulary -- this is what
    distinguishes it from the plain facets_v1.facet:X surface, which only
    proves the bare trigger word appears. The surface's suffix (e.g.
    "cost") maps onto the corresponding facets_v1 table entry
    ("facet:cost") for its trigger vocabulary; units_v1's alphabetic keys
    + currency_symbols_v1's symbol keys supply the unit vocabulary.

    NOTE (SAN-881 PASS 2B.1): this predicate itself remains the Pass-1
    LEXICAL, field-wide co-occurrence proof (a trigger word and a
    unit/currency token both present somewhere in the declared field).
    The span-bound value CLASSIFIER this predicate was originally
    documented as eventually consuming (cost/duration/limit determined
    from the exact parsed value span, Roles.value, of the exact frame)
    now EXISTS as `classify_value_span_text` / `first_measure_value_
    span_text` below, with the exact policy and full positive/negative
    vector coverage ratified by the matrix.

    SAN-881 PASS 2B.1-P (and its PASS 2B.1-P-FIX correction): the full
    value_role_v1 family contract -- (a) a matching classified span,
    bound to its OWNING FrameProductEvent's own facet, AND (b) actual
    participation in C1 disposition or C3 source-conflict -- is now
    enforced for the RUNTIME evidence path entirely through the
    product-trace substrate + CAPABILITY_MAP (see _pc_locate's
    value_role_v1 branch and _check_all_product_surfaces_evidence), NOT
    through this predicate. This function is retained as the original
    Pass-1 lexical proof only, is no longer consulted by check_coverage_
    manifest's Pass B for value_role_v1 (COVERAGE_PREDICATES["value_
    role_v1"] is dead in the runtime dispatch path -- only
    COVERAGE_PREDICATES["nontable"] is ever read there; see
    _check_all_product_surfaces_evidence / _check_nontable_surface_
    evidence), and was never actually blocked on CheckConsumptionTrace:
    no CheckConsumptionTrace class exists, and none is planned -- that
    internal-branch-consumption-tracing architecture was proposed and
    REJECTED (see this module's own docstring), not deferred, and the
    real product-trace contract above was never staged behind it."""
    facet_suffix = surface.split(".", 1)[1] if "." in surface else ""
    facet_key = f"facet:{facet_suffix}"
    facet = tables_data.get("facets_v1", {}).get(facet_key)
    if not facet:
        return False
    lowered = item_text.lower()
    has_trigger = any(_word_present(t, lowered) for t in facet.get("triggers", []) + facet.get("deny_triggers", []))
    if not has_trigger:
        return False
    unit_words = [u for u in tables_data.get("units_v1", {}) if u.isalpha()]
    if any(_word_present(u, lowered) for u in unit_words):
        return True
    currency_symbols = [c for c in tables_data.get("currency_symbols_v1", {}) if not c.isalnum()]
    return any(c in item_text for c in currency_symbols)


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1: span-bound value-role CLASSIFIER (RED target 4).
# classify_value_span_text is a PURE POLICY function -- documented as
# POLICY, not a restatement of the algorithm's own value-parsing
# semantics: it never re-implements NUMBER/PCT100/currency/unit
# grammar itself, it tokenizes the exact span text with the SAME
# pinned production tokenizer (reference.primitives.tokenize) and
# reads token.kind / token.fold, so a currency/percent/unit judgment
# can never silently drift from the real evaluator's own tokenizer.
# first_measure_value_span_text is the SPAN-BOUND integration point: a
# genuine (never monkeypatched, never re-implemented) call into the
# pinned production trigger_scan / extract_roles primitives to locate
# the EXACT raw Roles.value span of one real frame -- classification
# never operates on field-wide text.
# ---------------------------------------------------------------------

def classify_value_span_text(value_span_text: str, tables_data: dict) -> str | None:
    """SPAN-BOUND POLICY (never field-wide co-occurrence): classifies
    the EXACT raw text of one frame's own Roles.value span as
    "cost" | "duration" | "limit" | None. Tokenizes `value_span_text`
    with the pinned production tokenizer so percent/currency/unit
    detection is never a hand-rolled reimplementation of that grammar.

    Policy (documented as POLICY, not algorithm semantics -- a
    downstream integration may refine it):
      - ANY percent marker in the span (a PCT100-kind token, or a
        NUMBER-kind token whose raw text ends in "%") -> None
        (mixed/percent forms are a known, documented gap -- never
        guessed at).
      - a currency marker (a NUMBER-kind token whose raw text starts
        with a currency_symbols_v1 symbol) AND a units_v1 time-unit
        WORD-kind token (matched via token.fold, so "days" folds to
        the table's "day" entry) BOTH present in the span -> None
        (mixed cost+duration span).
      - a currency marker alone -> "cost".
      - a units_v1 time-unit word alone -> "duration".
      - none of the three markers present -> "limit"."""
    from reference.primitives import tokenize

    currency_symbols = list(tables_data.get("currency_symbols_v1", {}))
    unit_words = {u.lower() for u in tables_data.get("units_v1", {})}

    has_percent = False
    has_currency = False
    has_time_unit = False
    for tok in tokenize(value_span_text):
        if tok.kind == "PCT100" or (tok.kind == "NUMBER" and tok.raw.endswith("%")):
            has_percent = True
        if tok.kind == "NUMBER" and any(tok.raw.startswith(sym) for sym in currency_symbols):
            has_currency = True
        if tok.kind == "WORD" and tok.fold in unit_words:
            has_time_unit = True

    if has_percent:
        return None
    if has_currency and has_time_unit:
        return None
    if has_currency:
        return "cost"
    if has_time_unit:
        return "duration"
    return "limit"


def first_measure_value_span_text(field_text: str, tables_data: dict) -> tuple[str, str] | None:
    """SPAN-BOUND INTEGRATION: locates the FIRST measure-facet Hit's
    Roles.value span in `field_text` via a genuine call into the
    pinned production extraction primitives (tokenize, sentences,
    trigger_scan, extract_roles) -- never a hand-rolled span-finding
    regex, never a monkeypatch (these are pure, side-effect-free reads
    of already-public functions). Returns (facet, raw_span_text) where
    raw_span_text is sliced from `field_text` using the matched
    Roles.value span's own Token.start/Token.end character offsets
    (the EXACT raw span, never a re-joined/re-normalized
    reconstruction), or None if no measure-facet frame with a
    Roles.value span is found in any sentence. A per-sentence
    Abstain/FramePartial is treated as "this hit produced no value
    span" and scanning continues -- this helper never raises; it is a
    best-effort LOOKUP, not itself a proof of check-level consumption.
    SAN-881 PASS 2B.1-P's own runtime value_role_v1 evidence path does
    NOT route through this helper at all -- it goes through the
    product-trace substrate's own replay (_pc_locate's value_role_v1
    branch, over FrameProductEvent.value_span_raw); no
    CheckConsumptionTrace class exists, and none is planned -- that
    architecture was proposed and REJECTED, not a prerequisite this
    helper (or any coverage predicate) is waiting on."""
    from reference.primitives import Abstain, sentences, tokenize
    from reference.extraction import FramePartial, _segment_bounds, extract_roles, trigger_scan

    tokens = tokenize(field_text)
    for sent in sentences(tokens, field_text):
        seg_bounds = _segment_bounds(sent)
        try:
            hits = trigger_scan(sent)
        except Abstain:
            continue
        for hit in hits:
            facet_def = tables_data.get("facets_v1", {}).get(hit.facet)
            if not facet_def or not facet_def.get("measure"):
                continue
            try:
                roles = extract_roles(hit, sent, seg_bounds)
            except (Abstain, FramePartial):
                continue
            if roles.value is None:
                continue
            lo, hi = roles.value
            if lo >= hi or hi > len(sent):
                continue
            span_text = field_text[sent[lo].start : sent[hi - 1].end]
            return hit.facet, span_text
    return None


_NON_ASCII_DIGIT_RANGES = (
    (0x0660, 0x0669),  # Arabic-Indic digits
    (0x06F0, 0x06F9),  # Extended Arabic-Indic digits
    (0x0966, 0x096F),  # Devanagari digits
    (0xFF10, 0xFF19),  # Fullwidth digits
)


def _contains_non_ascii_digit(text: str) -> bool:
    return any(any(lo <= ord(ch) <= hi for lo, hi in _NON_ASCII_DIGIT_RANGES) for ch in text)


def _contains_malformed_number_grouping(text: str) -> bool:
    """A comma-grouped numeral whose groups are not exactly 3 digits
    (e.g. "1,23,456") -- the malformed-value abstention class."""
    for m in re.finditer(r"\d[\d,]*\d|\d", text):
        token = m.group(0)
        if "," not in token:
            continue
        parts = token.split(",")
        if any(len(p) != 3 for p in parts[1:]) or len(parts[0]) > 3:
            return True
    return False


def _contains_nonterminating_punctuation_run(text: str) -> bool:
    """Erratum e13: a sentence terminator immediately followed by the next
    sentence's capital letter with NO intervening whitespace (e.g.
    "exchangeable.Running") -- ambiguous sentence boundary."""
    return re.search(r"[.!?][A-Z]", text) is not None


def _contains_adjunct_preposition_chain(text: str, tables_data: dict) -> bool:
    """Erratum e15: two or more adjunct_prepositions_v1 tokens introducing
    nested prepositional phrases within the same clause (best-effort:
    two or more distinct adjunct-preposition tokens present)."""
    lowered = text.lower()
    preps = list(tables_data.get("adjunct_prepositions_v1", []))
    hits = sum(1 for p in preps if f" {p.lower()} " in f" {lowered} ")
    return hits >= 2


def _contains_trigger_in_adjunct_phrase(text: str, tables_data: dict) -> bool:
    """SAN-894: a facet trigger token appearing immediately after an
    article inside what reads as an adjunct-modified noun phrase
    (best-effort surface heuristic: "<adjunct-preposition> the <trigger>"
    or "the <trigger> <noun>" pattern) rather than as the main predicate."""
    lowered = text.lower()
    all_triggers = set()
    for facet in tables_data.get("facets_v1", {}).values():
        all_triggers |= {t.lower() for t in facet.get("triggers", [])}
        all_triggers |= {t.lower() for t in facet.get("deny_triggers", [])}
    words = lowered.replace(".", " . ").replace(",", " , ").split()
    for i, w in enumerate(words):
        if w in all_triggers and i > 0 and words[i - 1] == "the":
            return True
    return False


def _predicate_nontable(item_text: str, surface: str, tables_data: dict) -> bool:
    """nontable surfaces are proven by presence of the relevant lexical
    class or textual pattern rather than a single pinned table entry.
    `item_text` is the text of ONLY the evidence record's OWN declared
    field (context OR output) -- SAN-881 Phase-A correction: lexical
    predicates inspect ONLY the declared field of the declared item,
    never a context+output concatenation. A nontable surface whose
    triggering token and observed effect genuinely live in different
    fields (e.g. a quant_v1.abstain token in context driving an
    abstention outcome reported against output) is proven by TWO
    separate evidence records under the same surface/item/check, one per
    field -- exactly like the excl_v1/complement_v1 joint-evidence
    pattern -- never by silently widening a single record's scope.

    SAN-881 PASS 2B.1b: the seven c2_* handlers (Group A -- the ONLY
    legal position for any of them is (C2, output), enforced upstream by
    SURFACE_REGISTRY/Pass A) are now PRODUCT-HONEST: they consume
    reference.checks.scan_c2_lexical / has_governed_question -- the SAME
    shared helpers checks.C2 and evaluate.py's Stage W1 gate consume --
    over `item_text` re-tokenized with the pinned production tokenizer,
    never the injected `tables_data` argument and never an independent
    calibration-side reimplementation of definitive/hedge/window/negation
    handling. The remaining eleven handlers (Groups B and C) are
    superseded at the call layer by _check_nontable_bundle_backed_
    evidence below (event-local, ProductTraceBundle-backed proof) and are
    RETAINED HERE UNCHANGED, for direct-call test coverage only (deferred
    cleanup, out of THIS pass's scope).

    SAN-881 PASS 2B.1b-FIX2 correction 4: dispatch is now LAZY/EARLY-
    RETURNING -- a registered Group A name returns its own computed
    result IMMEDIATELY, before any of the eleven legacy Group B/C
    handler expressions below are ever constructed or evaluated (the
    prior body built ONE eager `handlers` dict literal spanning all
    eighteen keys, so every Group-A call ALSO silently ran the five
    legacy _contains_* helpers and discarded their results -- correct
    only by accident, not by construction, and inconsistent with the
    "dead in the runtime dispatch path" claim this module's docstring,
    this function's own prior docstring, and README.md all made about
    those eleven expressions: they were NOT dead, they executed on every
    single call). check_coverage_manifest's own live dispatch (see its
    per_surface_nontable_a/per_surface_nontable_bc split) never routes a
    Group-B/C surface name to this function at all -- routed instead to
    _check_nontable_bundle_backed_evidence -- so after this fix, the
    eleven legacy expressions' own code is LEGACY-UNREACHABLE-FROM-
    RUNTIME along every live path: never merely unread, never executed.
    They remain reachable ONLY via a direct call naming a Group-B/C
    surface (as the dedicated unit tests below do), exactly like the
    eight dead non-nontable COVERAGE_PREDICATES entries this module
    already carries."""
    from reference.checks import has_governed_question, scan_c2_lexical
    from reference.primitives import tokenize

    name = surface.split(".", 1)[1] if "." in surface else surface

    if name in _C2_ONLY_NONTABLE:
        # Group A: ONE shared scan (reference.checks.scan_c2_lexical, the
        # SAME implementation checks.C2 itself consumes) over the real
        # production-compiled DEFINITIVE_V1/HEDGE_V1/HEDGE_WINDOW_BOUNDARIES
        # -- never tables_data, which is an injected/toy JSON view unrelated
        # to the fold-compiled production tables this scan actually reads.
        # SAN-881 PASS 2B.1b-FIX A1: production's own C2 NEVER invokes
        # scan_c2_lexical for a governed-question output -- evaluate.py
        # passes has_governed_question(out_text) as C2's out_partial, which
        # short-circuits at C2's own row-0 gate BEFORE the scan ever runs
        # (checks.C2: "if out_partial: return (NOT_EVALUATED, ...)"). The
        # six lexical c2_* surfaces below must honor the SAME gate: a
        # governed-question item_text earns NO lexical c2_* credit, and the
        # scan is skipped entirely (c2_exams stays empty) -- ONLY
        # c2_interrogative (has_governed_question itself, below) may credit.
        # SAN-881 PASS 2B.1b-FIX A3: scan_c2_lexical streams in production
        # (no sink -> no retained fact list); calibration supplies a sink
        # and captures the bounded corpus facts it needs into its own local
        # list -- still ONE scanner implementation, the sink is the sole
        # capture mechanism.
        c2_exams: list[dict] = []
        if not has_governed_question(item_text):
            scan_c2_lexical(tokenize(item_text), sink=c2_exams.append)
        c2_non_negated = [e for e in c2_exams if not e["negated"]]

        handlers: dict[str, bool] = {
            "c2_definitive_hit": any(not e["negated"] for e in c2_exams),
            "c2_negated_definitive": any(e["negated"] for e in c2_exams),
            "c2_hedge_in_window": any(e["rescuing_hedge"] is not None for e in c2_non_negated),
            "c2_hedge_outside_window_or_absent": any(e["unrescued"] for e in c2_non_negated),
            "c2_negated_hedge": any(e["negated_hedges"] for e in c2_non_negated),
            "c2_window_boundary": any(e["window_clipped_lo"] or e["window_clipped_hi"] for e in c2_non_negated),
            "c2_interrogative": has_governed_question(item_text),
        }
        return handlers[name]

    # -- LEGACY Group B/C handlers (SAN-881 PASS 2B.1b-FIX2 correction 4:
    # legacy-unreachable-from-runtime -- see docstring above). Retained
    # BYTE-UNCHANGED, direct-call test coverage only. --
    lowered = item_text.lower()

    # definitive_v1/hedge_v1 are raw string entries in the on-disk tables
    # JSON (a multi-word entry, if any, is a single space-joined string,
    # e.g. "no more than"); no per-character re-join is needed here.
    definitive_terms = list(tables_data.get("definitive_v1", []))
    hedge_terms = list(tables_data.get("hedge_v1", []))
    negators = list(tables_data.get("negators_v1", []))
    hedge_boundaries = list(tables_data.get("hedge_window_boundaries", []))
    quant_abstain = list(tables_data.get("quant_v1", {}).get("abstain", []))
    approx_terms = list(tables_data.get("approx_v1", []))
    contraction_keys = list(tables_data.get("contractions_v1", {}).keys())
    all_deny_triggers = [t for facet in tables_data.get("facets_v1", {}).values() for t in facet.get("deny_triggers", [])]

    def any_token(tokens: list[str]) -> bool:
        return any(_word_present(tok, lowered) for tok in tokens)

    def any_substr(tokens: list[str]) -> bool:
        return any(tok.lower() in lowered for tok in tokens)

    handlers: dict[str, bool] = {
        "polarity_via_deny_trigger": any_substr(all_deny_triggers),
        "polarity_via_negator": any_substr(negators),
        "contraction_expansion": any_substr(contraction_keys),
        "abstain_interrogative_output": item_text.strip().endswith("?"),
        "abstain_quant_abstain": any_token(quant_abstain),
        "abstain_malformed_value": _contains_malformed_number_grouping(item_text),
        "abstain_e15_nested_adjunct_chain": _contains_adjunct_preposition_chain(item_text, tables_data),
        "abstain_san894_trigger_in_adjunct": _contains_trigger_in_adjunct_phrase(item_text, tables_data),
        "abstain_san895_non_ascii_digits": _contains_non_ascii_digit(item_text),
        "abstain_e13_nonterminating_punctuation": _contains_nonterminating_punctuation_run(item_text),
        "abstain_approx_value": any_substr(approx_terms),
    }
    if name not in handlers:
        return False
    return handlers[name]


COVERAGE_PREDICATES: dict[str, Callable[[str, str, dict], bool]] = {
    "facets_v1": _predicate_facets,
    "concept_v1": _predicate_concept,
    "comparators_v1": _predicate_comparators,
    "excl_v1": lambda text, surface, tables: _predicate_excl_or_complement(text, surface, "excl_v1", tables),
    "complement_v1": lambda text, surface, tables: _predicate_excl_or_complement(text, surface, "complement_v1", tables),
    "condition_operators_v1": _predicate_condition_operators,
    "quant_v1": _predicate_quant,
    "value_role_v1": _predicate_value_role,
    "nontable": _predicate_nontable,
}


def _field_text(item_record: dict, field: str) -> str:
    if field == "output":
        return item_record.get("output", "")
    return item_record.get("context") or " ".join(s["text"] for s in item_record.get("context_sources", []))


def check_coverage_registry_closure(errors: Errors, coverage: Any) -> None:
    """COMPLETE-INVENTORY CLOSURE (SAN-881 Phase-A correction): the
    manifest's top-level key set must equal the pre-registered
    SURFACE_REGISTRY key set EXACTLY. A missing registry surface and an
    extra undeclared surface both fail -- this replaces the prior
    dynamically-enumerated posture, which could silently accept a
    manifest with fewer (or differently-named) surfaces than the
    registry requires. Kept as its own function (rather than folded into
    check_coverage_manifest) so unit tests of the per-surface predicate
    logic can exercise a single toy surface without also having to
    satisfy full-registry completeness."""
    if not isinstance(coverage, dict):
        errors.add(f"coverage_manifest.json: rule={RULE_COVERAGE_TOP_LEVEL}")
        return
    manifest_keys = set(coverage.keys())
    registry_keys = set(SURFACE_REGISTRY)
    for missing in sorted(registry_keys - manifest_keys):
        errors.add(f"coverage_manifest.json[{missing}]: rule={RULE_COVERAGE_REGISTRY_MISSING_SURFACE}")
    for extra in sorted(manifest_keys - registry_keys):
        errors.add(f"coverage_manifest.json[{extra}]: rule={RULE_COVERAGE_REGISTRY_EXTRA_SURFACE}")


def check_coverage_manifest(errors: Errors, coverage: Any, design_by_id: dict, corpus_by_id: dict | None = None, tables_data: dict | None = None, upstream_ok: bool = True) -> None:
    """SAN-881 PASS 2B.1-P: TWO-PASS VALIDATION. Pass A (below, inline)
    validates the COMPLETE manifest -- schema-adjacent shape, item/check/
    field IDs, SURFACE_REGISTRY position legality (clause 1), and
    scenario independence -- across EVERY surface. ONLY a fully
    successful Pass A (zero errors added by this function, for the
    WHOLE manifest) may proceed to Pass B, which builds
    ProductTraceBundles and runs the four-clause product contract for
    the 50 in-scope surfaces (delegated to
    _check_all_product_surfaces_evidence), the ORIGINAL unchanged
    static-lexical proof for the seven Group-A (c2_*) nontable surfaces
    (delegated to _check_nontable_surface_evidence), and the
    ProductTraceBundle-backed dispatcher for the remaining eleven
    Group-B/C nontable surfaces (delegated to
    _check_nontable_bundle_backed_evidence). A schema-shaped-but-otherwise-
    invalid manifest (bad item_id, bad check_id, bad field, a forbidden
    position, a scenario-independence violation) never reaches
    build_product_trace_bundle -- see
    test_check_coverage_manifest_pass_a_failure_never_builds_a_bundle.

    SAN-881 PASS 2B.1-P-FIX fix 1: `upstream_ok` is an ADDITIONAL gate,
    orthogonal to this function's OWN internal Pass A, set by the caller
    (main()) to False whenever the coverage_manifest.json JSON-SCHEMA
    validation or check_coverage_registry_closure (the manifest's
    top-level key set vs. SURFACE_REGISTRY) found ANY error. This
    function's own internal Pass A loop iterates only the KEYS ACTUALLY
    PRESENT in `coverage` and cannot itself notice a MISSING registered
    surface, and silently skips position-checking an EXTRA undeclared
    surface (registry_entry is None) -- so neither defect necessarily
    produces a pass_a_errors entry here. `upstream_ok=False` closes that
    gap: Pass A (this function's own mechanical checks) still runs and
    still accumulates its own deterministic errors into `errors`
    regardless of `upstream_ok`, but Pass B (build_product_trace_bundle)
    is INELIGIBLE -- never runs -- whenever `upstream_ok` is False, even
    if this function's own Pass A found zero errors of its own. Defaults
    to True so every pre-existing direct caller (unit tests exercising
    this function's own Pass A/Pass B split in isolation, never routing
    through main()) is unaffected."""
    if not isinstance(coverage, dict):
        errors.add(f"coverage_manifest.json: rule={RULE_COVERAGE_TOP_LEVEL}")
        return

    pass_a_errors = Errors()
    scenario_by_item = {iid: it["scenario_id"] for iid, it in design_by_id.items()}
    per_surface_valid_records: dict[str, list[dict]] = {}
    for surface, records in coverage.items():
        registry_entry = SURFACE_REGISTRY.get(surface)
        if not isinstance(records, list):
            pass_a_errors.add(f"coverage_manifest.json[{surface}]: rule={RULE_COVERAGE_SURFACE_LIST}")
            continue
        if len(records) == 0:
            pass_a_errors.add(f"coverage_manifest.json[{surface}]: rule={RULE_COVERAGE_EMPTY_EVIDENCE}")
            continue
        scenarios_claimed: dict[str, list] = {}
        valid_records: list[dict] = []
        for rec in records:
            if not isinstance(rec, dict) or set(rec.keys()) != {"item_id", "check_id", "field"}:
                pass_a_errors.add(f"coverage_manifest.json[{surface}]: rule={RULE_COVERAGE_RECORD_SHAPE}")
                continue
            iid = rec["item_id"]
            if iid not in design_by_id:
                pass_a_errors.add(f"coverage_manifest.json[{surface}] {iid}: rule={RULE_COVERAGE_UNKNOWN_ITEM}")
                continue
            check_valid = rec["check_id"] in CHECK_IDS
            field_valid = rec["field"] in ("context", "output")
            if not check_valid:
                pass_a_errors.add(f"coverage_manifest.json[{surface}] {iid}/{rec['check_id']}: rule={RULE_COVERAGE_INVALID_CHECK}")
            if not field_valid:
                pass_a_errors.add(f"coverage_manifest.json[{surface}] {iid}: rule={RULE_COVERAGE_INVALID_FIELD}")
            # SAN-881 CORRECTION PASS 2: allowed_positions REPLACES the
            # Pass-1 allowed_checks x allowed_fields cartesian check. The
            # position check only ever evaluates a PAIR whose check_id
            # AND field are each individually legal values -- an already
            # out-of-vocabulary check_id/field is diagnosed ONLY via the
            # RULE_COVERAGE_INVALID_CHECK/RULE_COVERAGE_INVALID_FIELD
            # codes above, never double-diagnosed here too.
            if registry_entry is not None and check_valid and field_valid:
                if (rec["check_id"], rec["field"]) not in registry_entry["allowed_positions"]:
                    pass_a_errors.add(f"coverage_manifest.json[{surface}] {iid}/{rec['check_id']}/{rec['field']}: rule={RULE_COVERAGE_POSITION_NOT_ALLOWED}")
            sid = scenario_by_item.get(iid)
            scenarios_claimed.setdefault(sid, []).append(iid)
            valid_records.append(rec)

        for sid, item_ids in scenarios_claimed.items():
            if len(set(item_ids)) > 1:
                pass_a_errors.add(f"coverage_manifest.json[{surface}]: rule={RULE_COVERAGE_SCENARIO_INDEPENDENCE}")

        per_surface_valid_records[surface] = valid_records

    errors.extend(pass_a_errors)
    if pass_a_errors:
        return  # Pass A failed for the manifest -- Pass B never runs.
    if not upstream_ok:
        # SAN-881 PASS 2B.1-P-FIX fix 1: an upstream coverage-SCHEMA or
        # REGISTRY-CLOSURE failure makes trace construction INELIGIBLE
        # -- this function's own Pass A already ran and accumulated its
        # own deterministic errors above (unaffected); Pass B simply
        # never runs on top of a manifest the caller has already
        # determined is schema-invalid or closure-invalid.
        return
    if corpus_by_id is None or tables_data is None:
        return

    # SAN-881 PASS 2B.1b: the 18 nontable surfaces now split into Group A
    # (the seven c2_* surfaces -- bundle-free, routed to
    # _check_nontable_surface_evidence exactly as before) and Groups B/C
    # (the remaining eleven -- ProductTraceBundle-backed, routed to
    # _check_nontable_bundle_backed_evidence, sharing ONE Pass-B-wide
    # bundle cache with the 50 in-scope product surfaces).
    per_surface_nontable_a: dict[str, list[dict]] = {}
    per_surface_nontable_bc: dict[str, list[dict]] = {}
    per_surface_product: dict[str, list[dict]] = {}
    for surface, valid_records in per_surface_valid_records.items():
        registry_entry = SURFACE_REGISTRY.get(surface)
        predicate_id = registry_entry["predicate_id"] if registry_entry else surface.split(".", 1)[0]
        if predicate_id == "nontable":
            name = surface.split(".", 1)[1] if "." in surface else surface
            if name in _C2_ONLY_NONTABLE:
                per_surface_nontable_a[surface] = valid_records
            else:
                per_surface_nontable_bc[surface] = valid_records
        else:
            per_surface_product[surface] = valid_records

    for surface, valid_records in per_surface_nontable_a.items():
        _check_nontable_surface_evidence(errors, surface, valid_records, corpus_by_id, tables_data)

    bundle_for = _make_bundle_cache(corpus_by_id)
    _check_nontable_bundle_backed_evidence(errors, per_surface_nontable_bc, corpus_by_id, tables_data, bundle_for)
    _check_all_product_surfaces_evidence(errors, per_surface_product, corpus_by_id, tables_data, bundle_for)


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1-T: PRODUCT TRACE SUBSTRATE.
#
# An EPHEMERAL, TYPED, validator-local product-trace substrate, built
# by PURE READ-ONLY REPLAY of production extraction primitives over the
# COMPLETE corpus item -- never _field_text(), never a concatenated
# context string; individual context_sources, their boundaries, and
# their tiers are preserved (each source is processed strictly on its
# own text; sources are never joined).
#
# ARCHITECTURE (pinned):
#   - This substrate NEVER calls reference.extraction.extract_frames,
#     reference.extraction._next_frame_id, or the global
#     reference.extraction._frame_counter. It replays the PURE
#     primitives extract_frames itself calls (tokenize, sentences /
#     _segment_bounds, trigger_scan, NEG_v1 / polarity, extract_roles,
#     condition_marker_spans / parse_conditions / parse_bool, concept
#     normalization via CONCEPT_v1, quant, adjunct_modifiers,
#     normalize_benefit_facet, parse_values) itself, then separately
#     calls extract_obligations / extract_evidence (also production
#     primitives, unmodified) over LOCALLY assembled Frame objects.
#   - Production extraction imports are FUNCTION-LOCAL (lazy; never at
#     module top level) -- see _replay_field_trace below.
#   - Stable identity is (field, source_index, sentence_index,
#     hit_ordinal) -- never a dependence on production frame IDs. A
#     small LOCAL frame_id counter (never reference.extraction's own
#     _frame_counter) is used ONLY to satisfy the Frame dataclass's
#     required int field and to let extract_obligations /
#     extract_evidence key their own source_frame_ids bookkeeping; every
#     externally visible identity in this substrate is the stable tuple.
#   - This substrate NEVER computes rates, gates, or evaluator outcomes;
#     it captures PRODUCTS only. It is NOT invoked by
#     check_coverage_manifest or by any other runtime acceptance path
#     in this module (see the module docstring).
# ---------------------------------------------------------------------


class PartialStage(enum.Enum):
    """CLOSED processing-stage enum: the five distinct places production
    extract_frames sets its own `partial` flag (spec 2.6 / 3.4). Never
    invents a stage extract_frames does not have; the ORDER here has no
    significance beyond enumeration."""

    GOVERNED_INTERROGATIVE = "governed_interrogative"
    NONTERMINATING_PUNCTUATION = "nonterminating_punctuation"
    TRIGGER_SCAN_ABSTAIN = "trigger_scan_abstain"
    PER_HIT_ABSTAIN = "per_hit_abstain"
    TOTAL_SPAN_UNCONSUMED = "total_span_unconsumed"


# Stable per-frame/per-partial-event identity: (field, source_index,
# sentence_index, hit_ordinal). hit_ordinal is None for a partial event
# that is not tied to any specific trigger hit (sentence-level causes:
# GOVERNED_INTERROGATIVE, NONTERMINATING_PUNCTUATION,
# TRIGGER_SCAN_ABSTAIN, TOTAL_SPAN_UNCONSUMED).
ProductIdentity = Tuple[str, int, int, int | None]


@dataclasses.dataclass(frozen=True)
class ComparatorProductEvent:
    """PRODUCT CAPTURE: exact comparator FOLDS, raw span, LOCATION, and
    PARSED INTERVALS -- all bound to the SAME event object (a frame's
    own top-level Roles.value span, vs a condition's own parsed
    formula, vs a requirement formula's own parsed formula -- SAN-881
    PASS 2B.1-T-FIX blocker 1 extends the vocabulary to include
    "requirement", without which C3 requirement-comparator credit is
    impossible in 2B.1-C) -- comparator_folds is None when a
    value/measure span carries no comparator prefix (a bare NUMBER).
    parsed_intervals (SAN-881 PASS 2B.1-T-FIX-MICRO fix 1) is EXACTLY
    the owning MeasureAtom conjunct's own atom.intervals for location ==
    "condition"/"requirement", and EXACTLY the frame's own parsed
    Extent.values for location == "value" -- the raw comparator lexeme
    and the parsed interval are bound together on THIS event, never
    split across the event and a separate formula/atom node."""

    location: str  # "value" | "condition" | "requirement"
    comparator_folds: Tuple[str, ...] | None
    raw_span_text: str
    raw_start: int
    raw_end: int
    owning_identity: ProductIdentity
    owning_condition_index: int | None  # index into the owning frame's conds tuple; None when location == "value"
    parsed_intervals: Tuple[Any, ...] | None  # atom.intervals (condition/requirement) or the frame's own Extent.values (value)


@dataclasses.dataclass(frozen=True)
class ConditionProductEvent:
    """PRODUCT CAPTURE: exact condition marker folds, kind, force, and
    formula (the SAME Bool AST object production's own parse_conditions
    builds), plus the actual CONCEPT_v1 mappings applied inside this
    condition's own Bool-atom terms and the Bool-atom-only COMPLEMENT_v1
    candidates observed among those same terms."""

    marker_folds: Tuple[str, ...]
    kind: str
    force: int
    formula: Any
    concept_mappings: Tuple[Tuple[str, str], ...]
    complement_candidates: Tuple[str, ...]
    comparator_events: Tuple[ComparatorProductEvent, ...]


@dataclasses.dataclass(frozen=True)
class FrameProductEvent:
    """PRODUCT CAPTURE: one captured frame product, the trace-substrate
    analogue of a production Frame, keyed by the STABLE identity tuple
    rather than a production frame_id."""

    identity: ProductIdentity
    facet: str  # projection-normalized (normalize_benefit_facet)
    raw_facet: str  # hit.facet, pre-normalization
    subject: FrozenSet[str]
    object: FrozenSet[str]
    modifiers: FrozenSet[Tuple[str, FrozenSet[str]]]
    excl_candidates: Tuple[str, ...]  # modifier-only EXCL_v1 candidates
    quant_class: int
    quant_token_fold: str | None  # selected quantifier token (None: no quantifier token present)
    is_deny: bool
    negator_raw: str | None
    polarity: int
    trigger_raw: str
    trigger_folds: Tuple[str, ...]
    value_span_raw: str | None
    value_span_start: int | None
    value_span_end: int | None
    value_intervals: Tuple[Any, ...] | None  # SAN-881 PASS 2B.1-T-FIX blocker 2: production's own parsed Extent.values, exactly as production yields (None, never a fabricated empty tuple)
    comparator_events: Tuple[ComparatorProductEvent, ...]  # location == "value" only
    conds: Tuple[ConditionProductEvent, ...]
    assertive: bool
    subject_conjuncts: Tuple[FrozenSet[str], ...]
    subject_conjunct_heads: Tuple[str | None, ...]
    req_formula: Any | None
    req_concept_mappings: Tuple[Tuple[str, str], ...]
    req_complement_candidates: Tuple[str, ...]
    req_comparator_events: Tuple[ComparatorProductEvent, ...]  # location == "requirement" only (SAN-881 PASS 2B.1-T-FIX blocker 1 extension)


@dataclasses.dataclass(frozen=True)
class PartialProductEvent:
    """PRODUCT CAPTURE: `cause` is OPTIONAL and is NEVER an invented
    value -- it is None unless production itself supplied one (an
    Abstain/FramePartial's own `.cause`). NONTERMINATING_PUNCTUATION,
    GOVERNED_INTERROGATIVE, and TOTAL_SPAN_UNCONSUMED are structural
    (production never raises an exception for them), so `cause` is
    always None for those three stages."""

    identity: ProductIdentity
    stage: PartialStage
    cause: str | None
    quant_token_fold: str | None = None  # PER_HIT_ABSTAIN via quant-abstain: the selected token, recorded as an event even though no frame results


@dataclasses.dataclass(frozen=True)
class FieldProductTrace:
    """PRODUCT CAPTURE: one context_sources entry (or the single
    plain-`context` string, or `output`) -- source boundaries + tier
    preserved, NEVER a concatenated context string. SAN-881 PASS
    2B.1-T-FIX blocker 3: `tier` is resolved with EXACT tier-resolution
    PARITY to reference.evaluate._context_sources (plain `context` and a
    context_sources entry missing `tier` both resolve to "tier_1"), so
    in practice this is always a real tier string for a context field;
    still typed `str | None` for the OUTPUT field, which has no tier
    concept at all."""

    field: str  # "context" | "output"
    source_index: int
    boundary_start: int
    boundary_end: int
    tier: str | None  # "tier_1" | "tier_2" | "tier_3" for context fields (never None); always None for the output field
    partial: bool
    frame_events: Tuple[FrameProductEvent, ...]
    partial_events: Tuple[PartialProductEvent, ...]


@dataclasses.dataclass(frozen=True)
class ObligationProductEvent:
    """PRODUCT CAPTURE mirror of reference.primitives.Obligation, with
    `source_frame_identities` translated from production's own
    source_frame_ids (this substrate's LOCAL frame ids) back to the
    stable identity tuples."""

    kind: int
    governed_identity: Any
    source_activation_domain: Any
    applicability_scope: Any
    requirement_formula: Any
    source_polarity: int
    trivial: bool
    source_frame_identities: Tuple[ProductIdentity, ...]


@dataclasses.dataclass(frozen=True)
class EvidenceProductEvent:
    """PRODUCT CAPTURE mirror of reference.primitives.Evidence, with
    `frame_identity` translated from production's own frame_id back to
    the stable identity tuple."""

    frame_identity: ProductIdentity
    span_id: int
    governed_identity: Any
    domain: Any
    asserted_formula: Any
    assertion_polarity: int


@dataclasses.dataclass(frozen=True)
class BundleCapturePartialEvent:
    """PRODUCT CAPTURE (SAN-881 PASS 2B.1-T-FIX blocker 4): a
    BUNDLE-level (not per-frame) partial marker, raised by
    extract_obligations/extract_evidence THEMSELVES (spec 3.5
    facetproj_v1 miss -> FramePartial(UNEXTRACTABLE)) -- structurally
    DISTINCT from PartialProductEvent, which is keyed by a per-frame
    ProductIdentity and covers only extract_frames' own five partial
    stages (never raised by extract_obligations/extract_evidence).
    `cause` is the production exception's own .cause -- never an
    invented value."""

    cause: str


@dataclasses.dataclass(frozen=True)
class ObligationCaptureProduct:
    """PRODUCT CAPTURE (SAN-881 PASS 2B.1-T-FIX blocker 4): obligation
    extraction captured as an INDEPENDENT typed {items, partial_event}
    product -- a genuinely empty `items` tuple (no approval_requirement
    /conds-bearing trusted frames) is never conflated with a
    FramePartial short-circuit (`partial_event` is not None); the two
    are always mutually distinguishable."""

    items: Tuple[ObligationProductEvent, ...]
    partial_event: BundleCapturePartialEvent | None


@dataclasses.dataclass(frozen=True)
class EvidenceCaptureProduct:
    """PRODUCT CAPTURE (SAN-881 PASS 2B.1-T-FIX blocker 4): evidence
    extraction captured as an INDEPENDENT typed {items, partial_event}
    product -- see ObligationCaptureProduct."""

    items: Tuple[EvidenceProductEvent, ...]
    partial_event: BundleCapturePartialEvent | None


@dataclasses.dataclass(frozen=True)
class ObligationExclusionRecord:
    """PRODUCT CAPTURE (SAN-881 PASS 2B.1-T-FIX blocker 5): one context
    frame EXCLUDED from trusted_obligations' aggregation input, with its
    EFFECTIVE resolved tier (post tier-resolution-parity fix, blocker 3)
    and the exact exclusion reason -- mirrors reference.checks._trusted's
    own two-part test (assertive AND resolved tier in {tier_1, tier_2})
    EXACTLY: `non_assertive` fires first (frame.assertive is False,
    regardless of tier); `untrusted_tier` fires only for an assertive
    frame whose tier is NOT in {tier_1, tier_2} (tier_3, the only other
    legal value)."""

    identity: ProductIdentity
    tier: str
    reason: str  # "non_assertive" | "untrusted_tier"


@dataclasses.dataclass(frozen=True)
class ProductTraceBundle:
    """PRODUCT CAPTURE, per corpus item. SAN-881 PASS 2B.1-T-FIX
    (blockers 4+5): `trusted_obligations` is computed from context
    frames passing EXACTLY reference.checks._trusted (assertive AND
    resolved tier in {tier_1, tier_2}) BEFORE aggregation -- mirroring
    production's own C3 trust-before-aggregation order (SAN-881 PASS
    2B.1-T-FIX-MICRO fix 4: trust filtering before obligation
    aggregation is C3's own consumption semantics -- see C3 step 1,
    `obs = aggregate(extract_obligations(trusted(ctx_frames)))` --
    never C1's or C4's) -- and is
    captured as an INDEPENDENT typed {items, partial_event} product,
    structurally distinguishable from a genuinely empty result (never
    check-level CONSUMPTION proof: no CheckConsumptionTrace class
    exists, and none is planned -- that internal-branch-consumption-
    tracing architecture was proposed and REJECTED, permanently, not
    staged for a later pass; this substrate only mirrors production's
    OWN trust-filter INPUT selection, exactly as blocker 5 specifies,
    and is itself STATIC-COMPATIBLE product evidence, never a
    consumption proof). `evidence` is captured
    the same typed way, over output frames (output has no tier concept,
    so no trust filtering applies there). `excluded_obligation_frames`
    records EVERY context frame NOT in the trusted aggregation input,
    with its effective tier and exclusion reason. ALL frame products
    (`fields`) are retained for EVERY source regardless of trust status
    -- exclusion applies only to the obligations aggregation input,
    never to capture."""

    item_id: str
    fields: Tuple[FieldProductTrace, ...]
    trusted_obligations: ObligationCaptureProduct
    excluded_obligation_frames: Tuple[ObligationExclusionRecord, ...]
    evidence: EvidenceCaptureProduct


def _pt_capture_comparator_at(tokens: list, num_idx: int, lo: int) -> Tuple[Tuple[str, ...] | None, int]:
    """CAPTURE-ONLY helper: the LONGEST reference.primitives.COMPARATORS_V1
    folded sequence immediately preceding tokens[num_idx], bounded below
    by `lo` -- mirrors the exact longest-match rule production's own
    parse_values / extraction._find_unique_value_span apply (reads the
    SAME production table; never reimplements number/currency/unit
    grammar). Returns (comparator_folds_or_None, span_start_idx)."""
    from reference.primitives import COMPARATORS_V1

    best_len = 0
    for entry in COMPARATORS_V1:
        seq = entry["folds"]
        ln = len(seq)
        if num_idx - ln < lo:
            continue
        window = tuple(t.fold for t in tokens[num_idx - ln : num_idx])
        if window == seq and ln > best_len:
            best_len = ln
    if best_len == 0:
        return None, num_idx
    return tuple(t.fold for t in tokens[num_idx - best_len : num_idx]), num_idx - best_len


def _pt_capture_value_comparator(tokens: list, value_span: tuple) -> ComparatorProductEvent | None:
    """LOCATION == "value": captures the comparator (if any) prefixing
    the NUMBER/PCT100 token within a frame's own top-level Roles.value
    span. raw_start:raw_end bounds EXACTLY the matched comparator-fold
    tokens plus the NUMBER/PCT100 token itself -- consistent with the
    LOCATION == "condition"/"requirement" capture
    (_pt_capture_conjunct_products), it never extends to include a
    trailing unit word; the full
    value/measure span (including any unit) is separately and exactly
    captured on FrameProductEvent.value_span_raw/start/end. Returns None
    only if the span carries no NUMBER/PCT100 token at all (should not
    happen for a valid measure-facet Roles.value, but this helper never
    raises)."""
    lo, hi = value_span
    num_idx = next((i for i in range(lo, hi) if tokens[i].kind in ("NUMBER", "PCT100")), None)
    if num_idx is None:
        return None
    folds, start = _pt_capture_comparator_at(tokens, num_idx, lo)
    return ComparatorProductEvent(
        location="value",
        comparator_folds=folds,
        raw_span_text="",  # filled in by the caller, which has the field text
        raw_start=tokens[start].start,
        raw_end=tokens[num_idx].end,
        owning_identity=("", 0, 0, 0),  # filled in by the caller
        owning_condition_index=None,
        parsed_intervals=None,  # filled in by the caller, which has the frame's own parsed Extent.values
    )


def _pt_split_and_replay_bool(tokens: list, lo: int, hi: int, restrictive: bool):
    """SAN-881 PASS 2B.1-T-FIX blocker 1: CONJUNCT-BOUND FAITHFUL REPLAY
    of production parse_bool's own token-level split (content =
    PUNCT-filtered tokens[lo:hi]; split at top-level 'or' into
    alt_spans; each alt further split at 'and' into conj_spans) --
    reproduces the EXACT same conjunct token lists Bool AST construction
    consumes. Each conjunct's ATOM is built by calling production's OWN
    reference.extraction._atom_from_conjunct (never re-derived or
    re-guessed), so atom-type classification (TermAtom / MeasureAtom /
    UnknownAtom) is always production's authoritative answer for that
    exact token list -- production atoms DISCARD raw-token provenance
    (MeasureAtom carries only (qty, intervals), no comparator lexeme),
    so capture must be bound to THIS replayed split, never inferred from
    the final formula alone. Returns (reconstructed_formula,
    ((conj_tokens, atom), ...)) -- the flat, left-to-right sequence of
    every conjunct across every OR-alternative, paired 1:1 with its own
    atom, for the caller to bind capture events per-conjunct. The
    caller MUST assert reconstructed_formula == production's own
    already-built formula for the SAME [lo, hi) span -- this function
    only proves the split is reproduced faithfully when that assertion
    holds; it never assumes it. Raises the SAME Abstain production's
    parse_bool would raise for a malformed split (empty content, empty
    alt, empty conjunct) -- if OUR split were ever empty here,
    production's own SAME split already raised for the SAME span, so
    the caller would never have reached a production formula to capture
    against in the first place."""
    from reference.extraction import MALFORMED_MENTION, _atom_from_conjunct
    from reference.primitives import Abstain, And, Or

    content = [t for t in tokens[lo:hi] if t.kind != "PUNCT"]
    if not content:
        raise Abstain(MALFORMED_MENTION)
    alt_spans: list = [[]]
    for t in content:
        if t.fold == "or":
            alt_spans.append([])
        else:
            alt_spans[-1].append(t)
    if any(len(a) == 0 for a in alt_spans):
        raise Abstain(MALFORMED_MENTION)

    flat: list = []
    alt_atoms = []
    for alt in alt_spans:
        conj_spans: list = [[]]
        for t in alt:
            if t.fold == "and":
                conj_spans.append([])
            else:
                conj_spans[-1].append(t)
        if any(len(c) == 0 for c in conj_spans):
            raise Abstain(MALFORMED_MENTION)
        conj_atoms = []
        for conj_tokens in conj_spans:
            atom = _atom_from_conjunct(conj_tokens, restrictive)
            conj_atoms.append(atom)
            flat.append((conj_tokens, atom))
        alt_atoms.append(conj_atoms[0] if len(conj_atoms) == 1 else And(tuple(conj_atoms)))
    formula = alt_atoms[0] if len(alt_atoms) == 1 else Or(tuple(alt_atoms))
    return formula, tuple(flat)


def _pt_capture_conjunct_products(
    conj_tokens: list, atom: Any, identity: ProductIdentity, cond_index: int | None, location: str
) -> Tuple[Tuple[Tuple[str, str], ...], Tuple[str, ...], Tuple[ComparatorProductEvent, ...]]:
    """CONJUNCT-BOUND PRODUCT CAPTURE (SAN-881 PASS 2B.1-T-FIX blocker
    1, items 1+2+4): given ONE conjunct's own token list and the atom
    production's own _atom_from_conjunct built from THAT EXACT list,
    returns (concept_mappings, complement_candidates, comparator_events)
    bound to the atom's OWN type -- never inferred from the parent
    formula. TermAtom -> CONCEPT_v1 mappings scoped to this conjunct's
    own content tokens (reading the SAME production CONCEPT_V1 dict)
    + COMPLEMENT_v1 candidates from the atom's OWN terms (reading the
    SAME production COMPLEMENT_V1 tuple). MeasureAtom -> one comparator
    event per NUMBER/PCT100 token in THIS conjunct's own tokens (search
    window bounded by the CONJUNCT's own start, never a sibling
    conjunct's tokens), each event's PARSED intervals living on the atom
    itself (`atom.intervals`) -- the raw comparator lexeme and the
    parsed interval are bound together via the SAME conjunct, one event.
    UnknownAtom (or any other atom kind) -> neither -- a conjunct
    production itself could not parse credits nothing."""
    from reference.primitives import CONCEPT_V1, COMPLEMENT_V1, MeasureAtom, TermAtom, is_content_token

    if isinstance(atom, TermAtom):
        concept_mappings: list = []
        for tok in conj_tokens:
            if not is_content_token(tok):
                continue
            mapped = CONCEPT_V1.get(tok.fold, tok.fold)
            if mapped != tok.fold:
                concept_mappings.append((tok.fold, mapped))
        complement_members = {m for pair in COMPLEMENT_V1 for m in pair}
        complement_candidates = tuple(sorted(t for t in atom.terms if t in complement_members))
        return tuple(concept_mappings), complement_candidates, ()

    if isinstance(atom, MeasureAtom):
        events = []
        for idx, tok in enumerate(conj_tokens):
            if tok.kind not in ("NUMBER", "PCT100"):
                continue
            folds, start = _pt_capture_comparator_at(conj_tokens, idx, 0)
            events.append(
                ComparatorProductEvent(
                    location=location,
                    comparator_folds=folds,
                    raw_span_text="",  # filled in by the caller, which has the field text
                    raw_start=conj_tokens[start].start,
                    raw_end=conj_tokens[idx].end,
                    owning_identity=identity,
                    owning_condition_index=cond_index,
                    parsed_intervals=atom.intervals,
                )
            )
        return (), (), tuple(events)

    return (), (), ()


def _pt_capture_bool_products(
    tokens: list,
    lo: int,
    hi: int,
    restrictive: bool,
    identity: ProductIdentity,
    cond_index: int | None,
    location: str,
    production_formula: Any,
) -> Tuple[Tuple[Tuple[str, str], ...], Tuple[str, ...], Tuple[ComparatorProductEvent, ...]]:
    """Drives the conjunct-bound split+replay+capture (blocker 1) for
    ONE Bool formula span (a condition body or a requirement's required
    span), then ASSERTS the reconstructed tree equals production's OWN
    already-built formula for the SAME span -- the replayed split is
    proven faithful HERE, every time this is called, never merely
    assumed (exercised corpus-wide by the differential test, which
    calls build_product_trace_bundle for every public corpus item).
    Aggregates every conjunct's own concept_mappings (in order, never
    deduplicated -- matches production's own multiplicity) /
    complement_candidates (deduplicated + sorted, matching the prior
    whole-formula-tree-walk's own set semantics) / comparator_events
    (in order), left to right across every OR-alternative."""
    reconstructed, flat = _pt_split_and_replay_bool(tokens, lo, hi, restrictive)
    assert reconstructed == production_formula, (
        "conjunct-bound replay produced a formula DIFFERENT from production's own parse_bool "
        f"for the same span -- replay is not faithful: {reconstructed!r} != {production_formula!r}"
    )
    concept_mappings: list = []
    complement_candidates: list = []
    comparator_events: list = []
    for conj_tokens, atom in flat:
        cm, cc, ce = _pt_capture_conjunct_products(conj_tokens, atom, identity, cond_index, location)
        concept_mappings.extend(cm)
        complement_candidates.extend(cc)
        comparator_events.extend(ce)
    return tuple(concept_mappings), tuple(sorted(set(complement_candidates))), tuple(comparator_events)


def _replay_field_trace(
    field: str, source_index: int, text: str, tier: str | None, governed: bool, local_frame_id: "list[int]"
) -> Tuple[FieldProductTrace, list]:
    """Replays reference.extraction.extract_frames' own per-sentence
    control flow for ONE field/source (never extract_frames itself,
    never _next_frame_id, never the global _frame_counter), capturing
    FrameProductEvent / PartialProductEvent products as it goes.
    Returns (FieldProductTrace, list[reference.primitives.Frame]) --
    the Frame list is fed to extract_obligations / extract_evidence by
    the caller (build_product_trace_bundle), unmodified production
    primitives over LOCALLY assembled Frame objects (never touching the
    production frame counter). `local_frame_id` is a one-element list
    used as a mutable counter, threaded across every source of one item
    so every locally-built Frame carries a unique int id within the
    bundle (an implementation detail Frame's own dataclass shape
    requires; the STABLE identity tuple is the real, externally visible
    identity everywhere in this substrate)."""
    from reference.extraction import (
        FramePartial,
        NEG_v1,
        _consumed_negator_index,
        _is_filler,
        _segment_bounds,
        _conjunct_terms_and_heads,
        adjunct_modifiers,
        condition_marker_spans,
        extract_roles,
        noun_groups,
        normalize_benefit_facet,
        parse_bool,
        parse_conditions,
        polarity as polarity_fn,
        quant,
        trigger_scan,
    )
    from reference.primitives import (
        Abstain,
        EXCL_V1,
        Extent,
        Frame,
        Not,
        QUANT_ABSTAIN,
        QUANT_EXISTENTIAL,
        QUANT_UNIVERSAL,
        RESTRICTION,
        Roles,
        UNEXTRACTABLE,
        is_interrogative,
        list_marker_indices,
        parse_values,
        sentences,
        tokenize,
    )
    from reference.tables import T

    def _next_id() -> int:
        local_frame_id[0] += 1
        return local_frame_id[0]

    def _quant_selection(subject_tokens: list) -> Tuple[str | None, str]:
        """CAPTURE-ONLY parallel replay of quant()'s own first-match
        scan (SAME production frozensets), additionally returning WHICH
        token was selected -- quant() itself remains the sole
        AUTHORITATIVE class/abstain decision; this only recovers the
        specific token for product capture."""
        for tok in subject_tokens:
            if tok.fold in QUANT_UNIVERSAL:
                return tok.fold, "universal"
            if tok.fold in QUANT_EXISTENTIAL:
                return tok.fold, "existential"
            if tok.fold in QUANT_ABSTAIN:
                return tok.fold, "abstain"
        return None, "none"

    tokens = tokenize(text)
    frame_events: list = []
    partial_events: list = []
    local_frames: list = []
    field_partial = False

    for sentence_index, sent in enumerate(sentences(tokens, text)):
        seg_bounds = _segment_bounds(sent)
        interrogative = is_interrogative(sent)

        if interrogative and governed:
            field_partial = True
            partial_events.append(
                PartialProductEvent(
                    identity=(field, source_index, sentence_index, None),
                    stage=PartialStage.GOVERNED_INTERROGATIVE,
                    cause=None,
                )
            )
            continue

        markers = list_marker_indices(sent, text)
        e13_nonterminating = False
        for i, tok in enumerate(sent):
            if tok.kind == "PUNCT" and tok.raw in T.sentence_terminators:
                terminates = tok.end == len(text) or text[tok.end] in T.ws_v1
                if i not in markers and not terminates:
                    e13_nonterminating = True
                    break
        if e13_nonterminating:
            field_partial = True
            partial_events.append(
                PartialProductEvent(
                    identity=(field, source_index, sentence_index, None),
                    stage=PartialStage.NONTERMINATING_PUNCTUATION,
                    cause=None,
                )
            )
            continue

        try:
            hits = trigger_scan(sent)
        except Abstain as exc:
            field_partial = True
            partial_events.append(
                PartialProductEvent(
                    identity=(field, source_index, sentence_index, None),
                    stage=PartialStage.TRIGGER_SCAN_ABSTAIN,
                    cause=exc.cause,
                )
            )
            continue

        assertive = not interrogative
        consumed: set = set()
        sentence_abstained = False
        prev_subject_span = None

        for hit_ordinal, hit in enumerate(hits):
            identity: ProductIdentity = (field, source_index, sentence_index, hit_ordinal)
            quant_selected_fold: str | None = None
            try:
                roles = extract_roles(hit, sent, seg_bounds)
                coordinator_idx = None
                if roles.pattern == "COORD":
                    if prev_subject_span is None:
                        raise Abstain(UNEXTRACTABLE)
                    coordinator_idx = hit.span[0] - 1
                    roles = Roles(subject=prev_subject_span, object=roles.object, value=roles.value, pattern="COORD")
                prev_subject_span = roles.subject

                neg_idx = _consumed_negator_index(sent, hit.span, seg_bounds)
                neg_excl = frozenset() if neg_idx is None else frozenset({neg_idx})
                negator_raw = sent[neg_idx].raw if neg_idx is not None else None

                mods_subj, consumed_subj = adjunct_modifiers(sent, roles.subject)
                mods_obj, consumed_obj = adjunct_modifiers(sent, roles.object) if roles.object else (frozenset(), [])
                mods = mods_subj | mods_obj
                consumed_subj_set = frozenset(consumed_subj) | neg_excl
                consumed_obj_set = frozenset(consumed_obj) | neg_excl

                if roles.value is not None and roles.object is not None:
                    consumed_obj_set = consumed_obj_set | frozenset(range(roles.value[0], roles.value[1]))

                subj_groups, subj_heads = _conjunct_terms_and_heads(sent, roles.subject, consumed_subj_set)
                subj_terms = frozenset().union(*subj_groups) if subj_groups else frozenset()
                obj_groups = noun_groups(sent, roles.object, consumed_obj_set) if roles.object else []
                obj_terms = frozenset().union(*obj_groups) if obj_groups else frozenset()

                subj_head = subj_heads[0] if subj_heads else None

                fx = normalize_benefit_facet(hit, subj_head)

                quant_selected_fold, _quant_kind = _quant_selection(sent[roles.subject[0] : roles.subject[1]])
                q = quant(sent[roles.subject[0] : roles.subject[1]])  # authoritative; may raise FramePartial

                is_neg = NEG_v1(sent, hit.span, seg_bounds)
                pol = polarity_fn(is_neg, hit.is_deny)

                values = None
                value_span_raw = None
                value_span_start = None
                value_span_end = None
                value_comparator_events: tuple = ()
                if roles.value is not None:
                    vlo, vhi = roles.value
                    values = parse_values(sent[vlo:vhi])
                    value_span_raw = text[sent[vlo].start : sent[vhi - 1].end]
                    value_span_start = sent[vlo].start
                    value_span_end = sent[vhi - 1].end
                    comp_event = _pt_capture_value_comparator(sent, roles.value)
                    if comp_event is not None:
                        comp_event = dataclasses.replace(
                            comp_event,
                            raw_span_text=text[comp_event.raw_start : comp_event.raw_end],
                            owning_identity=identity,
                            parsed_intervals=tuple(values) if values else None,
                        )
                        value_comparator_events = (comp_event,)

                req_formula = None
                req_concept_mappings: tuple = ()
                req_complement_candidates: tuple = ()
                req_comparator_events: tuple = ()
                if fx == "facet:approval_requirement" and roles.object is not None:
                    req_formula = parse_bool(sent, roles.object[0], roles.object[1], restrictive=True)
                    req_concept_mappings, req_complement_candidates, req_comparator_events = _pt_capture_bool_products(
                        sent, roles.object[0], roles.object[1], True, identity, None, "requirement", req_formula
                    )
                    req_comparator_events = tuple(
                        dataclasses.replace(ce, raw_span_text=text[ce.raw_start : ce.raw_end])
                        for ce in req_comparator_events
                    )

                extent = Extent(
                    facet=fx,
                    subject=subj_terms,
                    object=obj_terms,
                    modifiers=mods,
                    quant=q,
                    polarity=pol,
                    values=tuple(values) if values else None,
                )

                # -- condition capture: replays condition_marker_spans
                # AND parse_conditions in parallel over the SAME
                # (op, body_start, body_end, marker_start) sequence --
                # parse_conditions is deterministic over identical
                # inputs, so the two calls stay index-aligned.
                seg = next(((lo, hi) for lo, hi in seg_bounds if lo <= hit.span[0] < hi), (0, len(sent)))
                marker_spans = condition_marker_spans(sent, hit.span[1], seg[1])
                cond_nodes = parse_conditions(sent, hit, seg_bounds)
                conds_captured = []
                for cond_index, ((op, body_start, body_end, _marker_start), cond_node) in enumerate(zip(marker_spans, cond_nodes)):
                    # cond_node.formula is Not-wrapped by production's own
                    # parse_conditions when op["polarity"] == "-"; the
                    # replay target is the RAW parse_bool product for the
                    # SAME span, so unwrap identically before asserting
                    # structural equality against it.
                    cond_restrictive = op["force"] == RESTRICTION
                    if op["polarity"] == "-":
                        assert isinstance(cond_node.formula, Not)
                        target_formula = cond_node.formula.child
                    else:
                        target_formula = cond_node.formula
                    c_concept, c_complement, c_comparators = _pt_capture_bool_products(
                        sent, body_start, body_end, cond_restrictive, identity, cond_index, "condition", target_formula
                    )
                    # EACH comparator event's raw_span_text is sliced from
                    # its OWN exact raw_start:raw_end -- never the whole
                    # condition body -- so "only if" is never captured as
                    # "if" and "more than" is never collapsed to "over".
                    c_comparators = tuple(
                        dataclasses.replace(ce, raw_span_text=text[ce.raw_start : ce.raw_end])
                        for ce in c_comparators
                    )
                    conds_captured.append(
                        ConditionProductEvent(
                            marker_folds=op["folds"],
                            kind=op["kind"],
                            force=op["force"],
                            formula=cond_node.formula,
                            concept_mappings=c_concept,
                            complement_candidates=c_complement,
                            comparator_events=c_comparators,
                        )
                    )

                excl_candidates = tuple(
                    sorted({term for _prep, objset in mods for term in objset if any(term in pair for pair in EXCL_V1)})
                )

                frame_events.append(
                    FrameProductEvent(
                        identity=identity,
                        facet=fx,
                        raw_facet=hit.facet,
                        subject=subj_terms,
                        object=obj_terms,
                        modifiers=mods,
                        excl_candidates=excl_candidates,
                        quant_class=q,
                        quant_token_fold=quant_selected_fold,
                        is_deny=hit.is_deny,
                        negator_raw=negator_raw,
                        polarity=pol,
                        trigger_raw=text[sent[hit.span[0]].start : sent[hit.span[1] - 1].end],
                        trigger_folds=hit.trigger_key,
                        value_span_raw=value_span_raw,
                        value_span_start=value_span_start,
                        value_span_end=value_span_end,
                        value_intervals=tuple(values) if values else None,
                        comparator_events=value_comparator_events,
                        conds=tuple(conds_captured),
                        assertive=assertive,
                        subject_conjuncts=tuple(subj_groups),
                        subject_conjunct_heads=tuple(subj_heads),
                        req_formula=req_formula,
                        req_concept_mappings=req_concept_mappings,
                        req_complement_candidates=req_complement_candidates,
                        req_comparator_events=req_comparator_events,
                    )
                )
                local_frames.append(
                    Frame(
                        field_id=field,
                        frame_id=_next_id(),
                        extent=extent,
                        conds=cond_nodes,
                        assertive=assertive,
                        subject_conjuncts=tuple(subj_groups),
                        subject_conjunct_heads=tuple(subj_heads),
                        req_formula=req_formula,
                    )
                )

                consumed.update(range(hit.span[0], hit.span[1]))
                if neg_idx is not None:
                    consumed.add(neg_idx)
                if coordinator_idx is not None:
                    consumed.add(coordinator_idx)
                consumed.update(range(roles.subject[0], roles.subject[1]))
                if roles.object is not None:
                    consumed.update(range(roles.object[0], roles.object[1]))
                if roles.value is not None:
                    consumed.update(range(roles.value[0], roles.value[1]))
                for _op, _bstart, body_end, marker_start in marker_spans:
                    consumed.update(range(marker_start, body_end))
            except (Abstain, FramePartial) as exc:
                field_partial = True
                sentence_abstained = True
                partial_events.append(
                    PartialProductEvent(
                        identity=identity,
                        stage=PartialStage.PER_HIT_ABSTAIN,
                        cause=exc.cause,
                        quant_token_fold=quant_selected_fold,
                    )
                )
                continue

        if interrogative:
            continue
        if not sentence_abstained:
            unconsumed = False
            for i, tok in enumerate(sent):
                if i in consumed or i in markers:
                    continue
                if _is_filler(tok):
                    continue
                unconsumed = True
                break
            if unconsumed:
                field_partial = True
                partial_events.append(
                    PartialProductEvent(
                        identity=(field, source_index, sentence_index, None),
                        stage=PartialStage.TOTAL_SPAN_UNCONSUMED,
                        cause=None,
                    )
                )

    trace = FieldProductTrace(
        field=field,
        source_index=source_index,
        boundary_start=0,
        boundary_end=len(text),
        tier=tier,
        partial=field_partial,
        frame_events=tuple(frame_events),
        partial_events=tuple(partial_events),
    )
    return trace, local_frames


def build_product_trace_bundle(item: dict) -> ProductTraceBundle:
    """Builds the complete ProductTraceBundle for one corpus item (a
    dict shaped like a corpus_inputs.json record: {id, context |
    context_sources, output}) by pure read-only replay of production
    extraction primitives -- see the module section banner above for
    the full architecture. Deterministic: repeated calls over the SAME
    item produce an equal bundle (frame/partial-event field values
    compare equal; Bool-AST `formula`/`req_formula` objects are
    themselves frozen dataclasses of primitive/frozenset leaves, so
    equality is structural) and never mutate reference.extraction's
    frame counter, reference.tables.T, any compiled
    reference.primitives constant, or any evaluator result."""
    item_id = item.get("id", "")
    local_frame_id = [0]

    # SAN-881 PASS 2B.1-T-FIX blocker 3 (TIER RESOLUTION PARITY): mirrors
    # reference.evaluate._context_sources EXACTLY -- plain `context` and
    # a context_sources entry missing `tier` both resolve to "tier_1",
    # never None.
    if "context_sources" in item:
        sources = [(s.get("text", ""), s.get("tier", "tier_1")) for s in item["context_sources"]]
    else:
        sources = [(item.get("context", ""), "tier_1")]

    field_traces: list = []
    ctx_frames: list = []
    tiers: dict = {}
    for source_index, (text, tier) in enumerate(sources):
        trace, frames = _replay_field_trace("context", source_index, text, tier, governed=False, local_frame_id=local_frame_id)
        field_traces.append(trace)
        for f in frames:
            tiers[f.frame_id] = tier
        ctx_frames.extend(frames)

    out_text = item.get("output", "")
    out_trace, out_frames = _replay_field_trace("output", 0, out_text, None, governed=True, local_frame_id=local_frame_id)
    field_traces.append(out_trace)

    # Map this bundle's LOCAL frame_id -> stable identity, so
    # extract_obligations'/extract_evidence's own source_frame_ids /
    # frame_id fields (opaque local ints) can be translated back to the
    # externally visible identity tuples. Built directly from the
    # (Frame, FrameProductEvent) pairing order, since both lists are
    # appended in lockstep per source/hit.
    frame_id_to_identity: dict = {}
    all_local_frames = list(ctx_frames) + list(out_frames)
    all_frame_events = [fe for trace in field_traces for fe in trace.frame_events]
    assert len(all_local_frames) == len(all_frame_events)
    for local_frame, fe in zip(all_local_frames, all_frame_events):
        frame_id_to_identity[local_frame.frame_id] = fe.identity

    from reference.checks import TIER_1, _trusted
    from reference.extraction import FramePartial, extract_evidence, extract_obligations

    # SAN-881 PASS 2B.1-T-FIX blocker 5 (TRUST-BEFORE-AGGREGATION):
    # mirrors reference.checks._trusted EXACTLY (assertive AND resolved
    # tier in {tier_1, tier_2}) as the INPUT to extract_obligations,
    # BEFORE aggregation -- production's own C3 order (SAN-881 PASS
    # 2B.1-T-FIX-MICRO fix 4: this is C3's own consumption semantics,
    # never C1's or C4's). Every EXCLUDED context frame is recorded
    # with its effective tier and reason; capture of frame PRODUCTS
    # (`fields`, above) is completely unaffected -- exclusion applies
    # only to this aggregation input.
    trusted_ctx_frames = _trusted(ctx_frames, tiers)
    trusted_frame_ids = {f.frame_id for f in trusted_ctx_frames}
    excluded_records = []
    for f in ctx_frames:
        if f.frame_id in trusted_frame_ids:
            continue
        excl_identity = frame_id_to_identity[f.frame_id]
        eff_tier = tiers.get(f.frame_id, TIER_1)
        reason = "non_assertive" if not f.assertive else "untrusted_tier"
        excluded_records.append(ObligationExclusionRecord(identity=excl_identity, tier=eff_tier, reason=reason))
    excluded_obligation_frames = tuple(excluded_records)

    # SAN-881 PASS 2B.1-T-FIX blocker 4 (TYPED, INDEPENDENT
    # OBLIGATION/EVIDENCE CAPTURE): extract_obligations / extract_evidence
    # can themselves raise FramePartial (spec 3.5: a facetproj_v1 miss on
    # an approval_requirement conjunct head) even when every underlying
    # frame extracted cleanly -- production's own evaluate.py Stage W2
    # treats this identically ("except FramePartial: pass", C3 reports
    # extraction_partial through its own gate). This substrate mirrors
    # that, but -- unlike the prior flattening into an indistinguishable
    # empty tuple -- captures the FramePartial as an explicit typed
    # partial_event (production's own exception `.cause`, never
    # invented), independently for obligations and for evidence, so a
    # genuinely empty result is never conflated with a partial one.
    try:
        obligation_items = tuple(
            ObligationProductEvent(
                kind=ob.kind,
                governed_identity=ob.governed_identity,
                source_activation_domain=ob.source_activation_domain,
                applicability_scope=ob.applicability_scope,
                requirement_formula=ob.requirement_formula,
                source_polarity=ob.source_polarity,
                trivial=ob.trivial,
                source_frame_identities=tuple(frame_id_to_identity[fid] for fid in ob.source_frame_ids),
            )
            for ob in extract_obligations(trusted_ctx_frames)
        )
        trusted_obligations = ObligationCaptureProduct(items=obligation_items, partial_event=None)
    except FramePartial as exc:
        trusted_obligations = ObligationCaptureProduct(items=(), partial_event=BundleCapturePartialEvent(cause=exc.cause))

    try:
        evidence_items = tuple(
            EvidenceProductEvent(
                frame_identity=frame_id_to_identity[ev.frame_id],
                span_id=ev.span_id,
                governed_identity=ev.governed_identity,
                domain=ev.domain,
                asserted_formula=ev.asserted_formula,
                assertion_polarity=ev.assertion_polarity,
            )
            for ev in extract_evidence(out_frames, "output")
        )
        evidence = EvidenceCaptureProduct(items=evidence_items, partial_event=None)
    except FramePartial as exc:
        evidence = EvidenceCaptureProduct(items=(), partial_event=BundleCapturePartialEvent(cause=exc.cause))

    return ProductTraceBundle(
        item_id=item_id,
        fields=tuple(field_traces),
        trusted_obligations=trusted_obligations,
        excluded_obligation_frames=excluded_obligation_frames,
        evidence=evidence,
    )


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1-P: PRODUCT-LEVEL COVERAGE for the 50 in-scope
# surfaces (47 table-derived + 3 value_role_v1). Consumes ONLY
# build_product_trace_bundle, pure product predicates/classifiers,
# table folding, and CAPABILITY_MAP -- NEVER evaluate, C1/C3/C4,
# budgets, relations, engine queries, monkeypatching, stack inspection,
# locks, wrappers, or tracing hooks (ANTI-RETURN GUARD; proven by
# test_calibration.py's AST/name-reference test over this section's
# call graph). This is NOT consumption tracing: no CheckConsumptionTrace
# class exists, no runtime monkeypatching of production code occurs, no
# event vocabulary is recorded, no locks/phase-state/call-attribution
# exist, and no EXCL branch is replayed against a real check outcome --
# that architecture was proposed and REJECTED; this section proves
# PRODUCT PRESENCE + OWNERSHIP/PARTIALITY QUALIFIERS + POSITION +
# CAPABILITY_MAP compatibility only. See the honest-assurance paragraph
# in this module's own docstring for the precise, non-overstated claim.
# ---------------------------------------------------------------------

TIER_1, TIER_2 = "tier_1", "tier_2"


def _pc_field_traces(bundle: "ProductTraceBundle", field: str) -> list:
    return [ft for ft in bundle.fields if ft.field == field]


def _pc_owner_tier(bundle: "ProductTraceBundle", identity) -> str | None:
    field, source_index = identity[0], identity[1]
    for ft in bundle.fields:
        if ft.field == field and ft.source_index == source_index:
            return ft.tier
    return None


def _pc_nonpartial_ok(bundle: "ProductTraceBundle", field: str) -> bool:
    """clause 3 (NON-PARTIAL), ordinary-product case: EVERY FieldProductTrace
    belonging to the declared logical field must be nonpartial -- for
    context this means ALL separate context-source traces (never
    concatenated; a source's own partial flag is never inferred from a
    sibling source). A field with zero traces (should not happen for a
    real corpus item) is conservatively treated as not-ok."""
    traces = _pc_field_traces(bundle, field)
    return bool(traces) and all(not t.partial for t in traces)


def _pc_frame_in_trusted_obligations(bundle: "ProductTraceBundle", identity) -> bool:
    return any(identity in ob.source_frame_identities for ob in bundle.trusted_obligations.items)


def _pc_frame_has_evidence(bundle: "ProductTraceBundle", identity) -> bool:
    return any(ev.frame_identity == identity for ev in bundle.evidence.items)


def _pc_ownership_and_partiality_ok(
    bundle: "ProductTraceBundle", location: str, owner_identity, owner_assertive: bool,
    check_id: str, field: str, *, exempt_frame_ownership: bool = False, skip_nonpartial: bool = False,
) -> bool:
    """SAN-881 PASS 2B.1b EXTRACTION: the shared OWNERSHIP QUALIFIER +
    NON-PARTIAL (clause 3) gate, WITHOUT the CAPABILITY_MAP
    CHECK-APPLICABLE (clause 4) test -- pulled out of _pc_candidate_ok
    (below, which still performs the CAPABILITY_MAP test first, then
    delegates the rest to this function -- BYTE-IDENTICAL combined
    behavior, verified by the full pre-existing product-surface suite)
    so nontable's Group B/C evidence (reference/calibration/
    validate_design.py's _check_nontable_bundle_backed_evidence) can
    reuse ONLY this ordinary ownership/nonpartial portion: nontable
    surfaces are NEVER routed through CAPABILITY_MAP (it has no nontable
    rows; predicate_id=="nontable" is never a CAPABILITY_MAP family), so
    nontable evidence must never call _pc_candidate_ok itself -- only
    this function."""
    if not skip_nonpartial and not _pc_nonpartial_ok(bundle, field):
        return False
    if exempt_frame_ownership:
        # quant_v1.abstain only: "quant-abstain is EXEMPT from frame
        # ownership (no frame is produced)".
        return True
    if not owner_assertive:
        return False
    if check_id in ("C1", "C4") and field == "context":
        if _pc_owner_tier(bundle, owner_identity) not in (TIER_1, TIER_2):
            return False
    if check_id == "C3" and field == "context":
        if not _pc_frame_in_trusted_obligations(bundle, owner_identity):
            return False
    if check_id == "C3" and field == "output":
        if location in ("condition", "requirement"):
            if not _pc_frame_has_evidence(bundle, owner_identity):
                return False
        else:
            if not bundle.trusted_obligations.items or bundle.trusted_obligations.partial_event is not None:
                return False
    return True


def _pc_candidate_ok(
    bundle: "ProductTraceBundle", family: str, location: str, owner_identity, owner_assertive: bool,
    check_id: str, field: str, *, exempt_frame_ownership: bool = False, skip_nonpartial: bool = False,
) -> bool:
    """The shared OWNERSHIP QUALIFIER + POSITION (clause 4) + NON-PARTIAL
    (clause 3) gate, applied to one located candidate product. clause 1
    (POSITION, against SURFACE_REGISTRY allowed_positions) is enforced
    earlier, unchanged, in check_coverage_manifest's own Pass A -- this
    function's own CAPABILITY_MAP membership test is clause 4
    (CHECK-APPLICABLE), a DIFFERENT, per-LOCATION test clause 1 cannot
    express (e.g. comparators_v1 at LOCATION=value excludes C4 even
    though the SURFACE's own allowed_positions includes C4 via its
    LOCATION=condition route)."""
    if (check_id, field) not in CAPABILITY_MAP.get((family, location), frozenset()):
        return False
    return _pc_ownership_and_partiality_ok(
        bundle, location, owner_identity, owner_assertive, check_id, field,
        exempt_frame_ownership=exempt_frame_ownership, skip_nonpartial=skip_nonpartial,
    )


def _pc_termatom_singletons(formula):
    """Walks a STORED Bool AST (a ConditionProductEvent.formula or a
    FrameProductEvent.req_formula -- the SAME object production's own
    parse_conditions/parse_bool built) and yields every TermAtom.terms
    frozenset found anywhere in it. Used ONLY by the complement_v1 joint
    rule: 'flattened complement candidates alone are insufficient' --
    this walks the REAL formula tree so a member's SINGLETON-ness
    (atom.terms == frozenset({member}), never a compound multi-term
    atom) can be verified directly, never inferred from a
    pre-flattened/deduplicated candidate list."""
    from reference.primitives import And, Not, Or, TermAtom

    stack = [formula]
    while stack:
        node = stack.pop()
        if isinstance(node, TermAtom):
            yield node.terms
        elif isinstance(node, (And, Or)):
            stack.extend(node.children)
        elif isinstance(node, Not):
            stack.append(node.child)


def _pc_normalize_bool_term(word: str) -> str:
    """The SAME normalized form Bool-atom terms carry in production
    (post-fold_sequence, then post-CONCEPT_v1 -- mirrors
    reference.primitives._bool_atom_normalize exactly, read-only, never
    reimplemented): COMPLEMENT_v1 pair members must be compared in this
    SAME normalized form (e.g. table member 'verified' normalizes to
    'verification' via CONCEPT_v1, so a raw string match against the
    table's own un-normalized member would never find the genuine
    TermAtom the trace substrate captured)."""
    from reference.primitives import CONCEPT_V1

    fold = fold_sequence(word)[0]
    return CONCEPT_V1.get(fold, fold)


def _pc_quant_abstain_event_matches(ft: "FieldProductTrace", pe: "PartialProductEvent", abstain_folds: set) -> bool:
    """SAN-881 PASS 2B.1b EXTRACTION: the pure FOUR-CONDITION quant_v1
    .abstain matcher -- (a) the selected token belongs to the abstain
    class (pe.quant_token_fold in abstain_folds), (b) the stage is
    PER_HIT_ABSTAIN, (c) the cause is production's own UNEXTRACTABLE
    cause, AND (d) the owning field's AGGREGATE trace is itself partial
    (ft.partial, checked positively) -- pulled out of _pc_locate's own
    quant_v1.abstain branch (below) so BOTH that branch (the 50-surface
    quant_v1.abstain product coverage) and nontable.abstain_quant_abstain
    (Group C, in _check_nontable_bundle_backed_evidence) call this SAME
    single implementation; there is no duplicate re-statement of these
    four conditions anywhere else."""
    from reference.primitives import UNEXTRACTABLE

    return (
        ft.partial
        and pe.stage == PartialStage.PER_HIT_ABSTAIN
        and pe.quant_token_fold in abstain_folds
        and pe.cause == UNEXTRACTABLE
    )


def _pc_locate(bundle: "ProductTraceBundle", family: str, surface: str, field: str, tables_data: dict) -> list:
    """PRODUCT PRESENT (clause 2), per family -- returns a list of
    (location, owner_identity, owner_assertive, exempt_frame_ownership,
    skip_nonpartial) candidate 5-tuples located WITHIN `field` only
    (never a context+output concatenation). excl_v1/complement_v1 are
    NOT located here -- their JOINT proof spans multiple fields/records
    and is handled by _pc_check_joint_excl_group /
    _pc_check_joint_complement_group instead."""
    out: list = []
    traces = _pc_field_traces(bundle, field)

    if family == "facets_v1":
        facet_key = surface.split(".", 1)[1]
        for ft in traces:
            for fe in ft.frame_events:
                if fe.facet == facet_key:
                    out.append(("frame", fe.identity, fe.assertive, False, False))

    elif family == "concept_v1":
        concept_name = surface.split(".", 1)[1]
        for ft in traces:
            for fe in ft.frame_events:
                for cond in fe.conds:
                    for _raw, mapped in cond.concept_mappings:
                        if mapped == concept_name:
                            out.append(("condition", fe.identity, fe.assertive, False, False))
                for _raw, mapped in fe.req_concept_mappings:
                    if mapped == concept_name:
                        out.append(("requirement", fe.identity, fe.assertive, False, False))

    elif family == "comparators_v1":
        trigger = surface.split(".", 1)[1]
        expected_folds = None
        for entry in tables_data.get("comparators_v1", []):
            if "_".join(entry["tokens"]) == trigger:
                expected_folds = fold_sequence(" ".join(entry["tokens"]))
                break
        if expected_folds is not None:
            for ft in traces:
                for fe in ft.frame_events:
                    for ce in fe.comparator_events:  # location == "value"
                        if ce.comparator_folds == expected_folds and ce.parsed_intervals:
                            out.append(("value", fe.identity, fe.assertive, False, False))
                    for cond in fe.conds:
                        for ce in cond.comparator_events:  # location == "condition"
                            if ce.comparator_folds == expected_folds and ce.parsed_intervals:
                                out.append(("condition", fe.identity, fe.assertive, False, False))
                    for ce in fe.req_comparator_events:  # location == "requirement"
                        if ce.comparator_folds == expected_folds and ce.parsed_intervals:
                            out.append(("requirement", fe.identity, fe.assertive, False, False))

    elif family == "condition_operators_v1":
        from reference.primitives import GRANT, RESTRICTION

        rest = surface.split(".", 1)[1]
        parts = rest.split(".")
        trigger_name = parts[0] if len(parts) > 0 else ""
        kind_name = parts[1] if len(parts) > 1 else ""
        force_name = parts[2] if len(parts) > 2 else ""
        expected_folds = None
        for entry in tables_data.get("condition_operators_v1", []):
            if "_".join(entry["tokens"]) == trigger_name:
                expected_folds = fold_sequence(" ".join(entry["tokens"]))
                break
        expected_force = GRANT if force_name == "grant" else RESTRICTION
        if expected_folds is not None:
            for ft in traces:
                for fe in ft.frame_events:
                    for cond in fe.conds:
                        if cond.marker_folds == expected_folds and cond.kind == kind_name and cond.force == expected_force:
                            out.append(("condition", fe.identity, fe.assertive, False, False))

    elif family == "quant_v1":
        from reference.primitives import EXISTENTIAL, UNIVERSAL

        quant_name = surface.split(".", 1)[1]
        if quant_name == "abstain":
            # SAN-881 PASS 2B.1-P-FIX fix 5: TIGHTENED credit -- ALL FOUR
            # of (a) the selected token belongs to the abstain class,
            # (b) the stage is PER_HIT_ABSTAIN, (c) the cause is the
            # production UNEXTRACTABLE cause (a PER_HIT_ABSTAIN-shaped
            # event raised for a DIFFERENT cause, e.g. malformed_mention
            # or condition_undecidable, must NOT credit), AND (d) the
            # owning field's AGGREGATE trace is itself partial (checked
            # here directly, positively -- never merely skipped) are
            # required.
            abstain_folds = {fold_sequence(w)[0] for w in tables_data.get("quant_v1", {}).get("abstain", [])}
            for ft in traces:
                for pe in ft.partial_events:
                    if _pc_quant_abstain_event_matches(ft, pe, abstain_folds):
                        # quant-abstain is EXEMPT from frame ownership
                        # (no frame is produced) AND from the general
                        # NON-PARTIAL clause's own all-traces-nonpartial
                        # test (skip_nonpartial=True) -- the aggregate
                        # field partiality requirement is instead
                        # enforced POSITIVELY inside
                        # _pc_quant_abstain_event_matches, never merely
                        # expected/assumed.
                        out.append(("partial", pe.identity, True, True, True))
        else:
            expected_class = UNIVERSAL if quant_name == "universal" else EXISTENTIAL
            for ft in traces:
                for fe in ft.frame_events:
                    if fe.quant_class == expected_class and fe.quant_token_fold is not None:
                        out.append(("extent", fe.identity, fe.assertive, False, False))

    elif family == "value_role_v1":
        # SAN-881 PASS 2B.1-P-FIX fix 2: credit is bound to the OWNING
        # frame's own facet, IN ADDITION to the exact-span classifier
        # match -- a classified value span whose OWNING frame's facet is
        # a DIFFERENT measure facet (e.g. "Shipping takes $5.": the
        # owning frame's facet is facet:duration via the "takes"
        # trigger, even though the bare span "$5" classifies as "cost")
        # must NOT credit the classifier's facet; it may only ever
        # credit the facet the frame itself actually carries.
        facet_suffix = surface.split(".", 1)[1]
        expected_facet = f"facet:{facet_suffix}"
        for ft in traces:
            for fe in ft.frame_events:
                if fe.value_span_raw is None or not fe.value_intervals:
                    continue
                if fe.facet != expected_facet:
                    continue
                if classify_value_span_text(fe.value_span_raw, tables_data) == facet_suffix:
                    out.append(("value", fe.identity, fe.assertive, False, False))

    return out


def _pc_check_surface_record(bundle: "ProductTraceBundle", surface: str, family: str, check_id: str, field: str, tables_data: dict) -> bool:
    """The four-clause product contract for ONE non-joint evidence
    record: clause 1 (POSITION) was already enforced in Pass A; this
    evaluates clauses 2+3+4 (PRODUCT PRESENT, NON-PARTIAL,
    CHECK-APPLICABLE) plus the ownership qualifiers, over EVERY located
    candidate, succeeding if ANY ONE candidate satisfies all of them."""
    for location, owner_identity, owner_assertive, exempt, skip_np in _pc_locate(bundle, family, surface, field, tables_data):
        if _pc_candidate_ok(
            bundle, family, location, owner_identity, owner_assertive, check_id, field,
            exempt_frame_ownership=exempt, skip_nonpartial=skip_np,
        ):
            return True
    return False


def _pc_check_joint_excl_group(bundle: "ProductTraceBundle", surface: str, tables_data: dict, fields_named, check_id: str) -> bool:
    """JOINT EVIDENCE for excl_v1 (never the one-record rule): TWO
    DISTINCT assertive frame owners, inspecting FrameProductEvent.modifiers
    DIRECTLY -- the two normalized members must occur in SAME-RELATION
    modifier object sets across those TWO owners. excl_candidates may
    prefilter but cannot itself prove the relation (this walks
    .modifiers, never .excl_candidates, to decide same-relation
    membership)."""
    pair_name = surface.split(".", 1)[1] if "." in surface else ""
    members = _lookup_pair_members(tables_data, "excl_v1", pair_name)
    if members is None:
        return False
    fold_a, fold_b = _fold_excl_member(members[0]), _fold_excl_member(members[1])

    owners = [fe for field in fields_named for ft in _pc_field_traces(bundle, field) for fe in ft.frame_events]
    for fe1 in owners:
        for rel1, objset1 in fe1.modifiers:
            if fold_a not in objset1:
                continue
            for fe2 in owners:
                if fe2 is fe1:
                    continue
                for rel2, objset2 in fe2.modifiers:
                    if rel2 != rel1 or fold_b not in objset2:
                        continue
                    if (
                        _pc_candidate_ok(bundle, "excl_v1", "modifier", fe1.identity, fe1.assertive, check_id, fe1.identity[0])
                        and _pc_candidate_ok(bundle, "excl_v1", "modifier", fe2.identity, fe2.assertive, check_id, fe2.identity[0])
                    ):
                        return True
    return False


def _pc_check_joint_complement_group(bundle: "ProductTraceBundle", surface: str, tables_data: dict, fields_named, check_id: str) -> bool:
    """JOINT EVIDENCE for complement_v1 (never the one-record rule):
    traverses the STORED condition/requirement Bool formulas (never a
    pre-flattened candidate list) and requires EACH member as an exact
    SINGLETON TermAtom (atom.terms == frozenset({member})) at a
    CAPABILITY_MAP-permitted location. NEVER concatenates context and
    output: each field named by the group is scanned independently, over
    its OWN frames' OWN formula objects."""
    pair_name = surface.split(".", 1)[1] if "." in surface else ""
    members = _lookup_pair_members(tables_data, "complement_v1", pair_name)
    if members is None:
        return False
    norm_a = _pc_normalize_bool_term(members[0])
    norm_b = _pc_normalize_bool_term(members[1])

    found_a = found_b = False
    for field in fields_named:
        for ft in _pc_field_traces(bundle, field):
            for fe in ft.frame_events:
                for cond in fe.conds:
                    for terms in _pc_termatom_singletons(cond.formula):
                        ok = _pc_candidate_ok(bundle, "complement_v1", "condition", fe.identity, fe.assertive, check_id, field)
                        if terms == frozenset({norm_a}) and ok:
                            found_a = True
                        if terms == frozenset({norm_b}) and ok:
                            found_b = True
                if fe.req_formula is not None:
                    for terms in _pc_termatom_singletons(fe.req_formula):
                        ok = _pc_candidate_ok(bundle, "complement_v1", "requirement", fe.identity, fe.assertive, check_id, field)
                        if terms == frozenset({norm_a}) and ok:
                            found_a = True
                        if terms == frozenset({norm_b}) and ok:
                            found_b = True
    return found_a and found_b


# ---------------------------------------------------------------------
# SAN-881 PASS 2B.1b: Groups B ({polarity_via_deny_trigger,
# polarity_via_negator, contraction_expansion}) and C (the eight
# abstain/event surfaces) -- PRODUCT-HONEST, EVENT-LOCAL nontable
# evidence over the SAME ProductTraceBundle substrate the 50 in-scope
# surfaces use (a shared bundle_for cache -- see _make_bundle_cache and
# check_coverage_manifest below -- never an independent nontable-side
# replay). These surfaces are NEVER routed through CAPABILITY_MAP (it
# has no nontable rows), so they reuse ONLY the ORDINARY ownership/
# nonpartial portion of the four-clause product contract
# (_pc_ownership_and_partiality_ok), never _pc_candidate_ok itself.
# ---------------------------------------------------------------------

def _make_bundle_cache(corpus_by_id: dict):
    """ONE Pass-B-wide ProductTraceBundle cache, shared by
    _check_all_product_surfaces_evidence (the 50 in-scope surfaces) and
    _check_nontable_bundle_backed_evidence (Groups B/C) via the SAME
    `bundle_for` callable, passed to both by check_coverage_manifest --
    a mixed manifest referencing the same item from both callers builds
    that item's ProductTraceBundle EXACTLY once."""
    bundle_cache: dict[str, ProductTraceBundle] = {}

    def _bundle_for(item_id: str) -> ProductTraceBundle:
        if item_id not in bundle_cache:
            bundle_cache[item_id] = build_product_trace_bundle(corpus_by_id[item_id])
        return bundle_cache[item_id]

    return _bundle_for


def _nb_source_texts(item: dict, field: str) -> list[str]:
    """PER-SOURCE raw texts for `field`, in source_index order -- mirrors
    build_product_trace_bundle's own source derivation EXACTLY (never a
    _field_text-style concatenated join): for "output", the single
    output text; for "context", each context_sources[i]["text"] (or the
    single plain "context" string) independently, index-aligned with
    ProductTraceBundle's own FieldProductTrace.source_index."""
    if field == "output":
        return [item.get("output", "")]
    if "context_sources" in item:
        return [s.get("text", "") for s in item["context_sources"]]
    return [item.get("context", "")]


def _nb_sentence_texts(text: str) -> list[str]:
    """Splits `text` into its SAME SPLIT_v1 sentences production uses
    (reference.primitives.sentences) and returns each sentence's OWN raw
    substring (sliced by its first/last token's char offsets) -- scopes
    a mechanism-detector lexical scan to ONE sentence at a time, never
    the whole field."""
    from reference.primitives import sentences, tokenize

    tokens = tokenize(text)
    out = []
    for sent in sentences(tokens, text):
        if not sent:
            out.append("")
            continue
        out.append(text[sent[0].start : sent[-1].end])
    return out


def _nb_contraction_occurrences(text: str) -> list:
    """Re-tokenizes `text` with the pinned production tokenizer
    (reference.primitives.tokenize) and returns one (carrier_index,
    expansion_indices) pair per genuine contraction occurrence --
    carrier_index is the token that carries the ORIGINAL raw contraction
    text (e.g. "won't", fold "will"); expansion_indices is the EXACT
    tuple of every token index production's own _expand_contractions
    emitted for THAT SAME occurrence (the carrier itself, plus every
    zero-width raw=="" continuation token immediately following it, at
    the SAME character offset) -- an EXACT positional binding to
    production's own tokenizer output, never a substring search and
    never an independently-derived expansion list."""
    from reference.primitives import tokenize

    tokens = tokenize(text)
    n = len(tokens)
    out = []
    i = 0
    while i < n:
        tok = tokens[i]
        if tok.kind == "WORD" and tok.raw:
            j = i + 1
            while (
                j < n
                and tokens[j].kind == "WORD"
                and tokens[j].raw == ""
                and tokens[j].start == tok.end
                and tokens[j].end == tok.end
            ):
                j += 1
            if j > i + 1:
                out.append((i, tuple(range(i, j))))
                i = j
                continue
        i += 1
    return out


def _nb_token_sentence_index(text: str, token_index: int) -> int | None:
    """Maps a GLOBAL token index (into reference.primitives.tokenize(text))
    to its SPLIT_v1 sentence index, via the SAME production `sentences`
    primitive -- sentences() slices the SAME Token objects (never
    copies), so object identity is an exact, safe correlation key."""
    from reference.primitives import sentences, tokenize

    tokens = tokenize(text)
    if token_index >= len(tokens):
        return None
    target = tokens[token_index]
    for sentence_index, sent in enumerate(sentences(tokens, text)):
        for tok in sent:
            if tok is target:
                return sentence_index
    return None


def _nb_locate_hit(source_text: str, sentence_index: int, hit_ordinal: int | None):
    """SAN-881 PASS 2B.1b-FIX: the SHARED replay step _nb_classify_hit_
    value_region and _nb_adjunct_group_scan both start from (SAN-881
    PASS 2B.1b-FIX2 correction 1 retired _nb_hit_segment_text from this
    shared role -- it still calls this same function on its own, but is
    no longer part of the malformed/approx/SAN-895 per-hit classification
    path) -- tokenize/sentences/trigger_scan/_segment_bounds over
    `source_text`, a fresh, read-only call into the SAME production
    primitives the trace substrate itself already replays, keyed by the
    SAME stable (sentence_index, hit_ordinal) identity components every
    PartialProductEvent carries. Returns (sent_tokens, hit, seg_bounds,
    hits) or None."""
    from reference.primitives import Abstain, sentences, tokenize
    from reference.extraction import _segment_bounds, trigger_scan

    if hit_ordinal is None:
        return None
    tokens = tokenize(source_text)
    sents = sentences(tokens, source_text)
    if sentence_index >= len(sents):
        return None
    sent = sents[sentence_index]
    if not sent:
        return None
    try:
        hits = trigger_scan(sent)
    except Abstain:
        return None
    if hit_ordinal >= len(hits):
        return None
    seg_bounds = _segment_bounds(sent)
    return sent, hits[hit_ordinal], seg_bounds, hits


def _nb_hit_segment_text(source_text: str, sentence_index: int, hit_ordinal: int | None) -> str | None:
    """Reconstructs, WITHOUT extending ProductTrace (no new dataclass
    field anywhere), the raw text of the `hit_ordinal`-th hit's OWN
    production structural region, for sentence `sentence_index` of
    `source_text`, via the SAME shared replay _nb_locate_hit performs.

    SAN-881 PASS 2B.1b-FIX2 correction 1: RETIRED from the malformed/
    approx/SAN-895 per-hit classification role (see
    _nb_classify_hit_value_region below) -- this function models a
    STRUCTURAL SEGMENT (T.structural_punctuation-delimited), a DIFFERENT
    concept from production's own value-role search region (extraction.
    py step 7: trigger end through sentence end or the first condition
    marker, never comma/semicolon-bounded). Retained BYTE-UNCHANGED,
    directly callable/tested on its own terms only (its own dedicated
    unit tests below still exercise its numeral-comma-merge behavior).

    SAN-881 PASS 2B.1b-FIX B1: starts at the T.structural_punctuation-
    delimited segment containing the hit's own trigger token, then
    extends forward across a segment boundary ONLY when that boundary
    is a COMMA directly flanked by NUMBER-kind tokens on BOTH sides --
    i.e. a stray comma INSIDE a malformed numeric lexeme (e.g.
    "$1,23,456" tokenizes as NUMBER "$1" + PUNCT "," + NUMBER "23,456",
    and _segment_bounds treats that PUNCT as a segment boundary; this
    narrow exception keeps the malformed numeral's own two halves
    together). This does NOT authorize absorbing arbitrary LATER
    comma/semicolon/colon/paren segments -- the generic "extend every
    segment until the next hit" behavior is DELETED: a semicolon never
    merges, and a comma not flanked by NUMBER on both sides never merges
    either. Still never crosses into the NEXT hit's own trigger position
    (or the sentence end), so a sibling hit's own unrelated content in
    the same sentence is never absorbed."""
    located = _nb_locate_hit(source_text, sentence_index, hit_ordinal)
    if located is None:
        return None
    sent, hit, seg_bounds, hits = located
    seg = next(((lo, hi) for lo, hi in seg_bounds if lo <= hit.span[0] < hi), None)
    if seg is None:
        return None
    lo, hi = seg
    next_hit_start = hits[hit_ordinal + 1].span[0] if hit_ordinal + 1 < len(hits) else len(sent)
    seg_hi_by_lo = {s_lo: s_hi for s_lo, s_hi in seg_bounds}
    while hi < next_hit_start and hi < len(sent):
        boundary = sent[hi]
        numeral_comma = (
            boundary.kind == "PUNCT" and boundary.raw == ","
            and hi - 1 >= lo and sent[hi - 1].kind == "NUMBER"
            and hi + 1 < len(sent) and sent[hi + 1].kind == "NUMBER"
        )
        if not numeral_comma:
            break
        nxt_hi = seg_hi_by_lo.get(hi + 1)
        if nxt_hi is None:
            break
        hi = min(nxt_hi, next_hit_start)
    if lo >= hi:
        return ""
    return source_text[sent[lo].start : sent[hi - 1].end]


def _nb_classify_hit_value_region(source_text: str, sentence_index: int, hit_ordinal: int | None) -> str | None:
    """SAN-881 PASS 2B.1b-FIX2 corrections 1+2: replaces _nb_hit_segment_
    text as the malformed/approx/SAN-895 per-hit classifier -- a
    validator-local replay of production's EXISTING value-search order
    (extraction.py's extract_roles rules 1-4 gating + rule 7's own value-
    region bound + _find_unique_value_span's own candidate-count/APPROX
    dichotomy), never a new detector and never new semantics.

    Step A -- establish the hit actually REACHES the measure-value
    branch (extraction.py rules 1-4, 386-433): rule 1 (OBLIGATION-
    PASSIVE), rule 2 (PASSIVE), and rule 3 (COORDINATION) each compute
    value=None and RETURN before rule 7 ever runs -- so a hit matching
    ANY of those three patterns (an orphan COORD hit INCLUDED: COORD
    never reaches rule 7 regardless of whether a valid prior subject
    exists to splice -- that gate belongs to _nb_adjunct_group_scan's
    OWN adjunct-group concept, not this one) returns None here. Only the
    rule 4 (ACTIVE) fallthrough, for a MEASURE facet, reaches rule 7.

    Step B -- the value region (extraction.py 434-451): trigger end
    through SENTENCE END, or the first CONDITION_OPERATORS_V1 marker
    inside [trigger end, sentence end) if one exists first -- bounded by
    the sentence, never by the hit's own comma-delimited structural
    segment (rule 4's OBJECT span uses a DIFFERENT, segment-bounded
    condition-marker search; rule 7's value region does not).

    Step C -- _find_unique_value_span's own dichotomy (extraction.py
    483-511), replayed over GLOBAL token indices into `sent` (never a
    re-tokenized text substring, which could silently lose an APPROX_V1
    token sitting immediately BEFORE the region's own first token):
      - MORE than one NUMBER/PCT100 token in the region -> "malformed";
      - EXACTLY one, immediately preceded (tokens[idx - 1].fold) by an
        EXACT APPROX_V1 token -> "approx";
      - EXACTLY one, not APPROX-preceded -> None (a genuine, unique,
        non-abstaining value -- not malformed, not approx);
      - ZERO candidates -> rule 7 leaves value=None, and rule 8 (453-
        465) then raises Abstain(UNEXTRACTABLE) for THIS hit's "value"
        valency alone -- but ONLY credits SAN-895's PER_HIT/unextractable
        arm here ("unextractable") when ALL of: this is an active
        measure hit (established in Step A); the hit's OWN non-value
        valencies (subject/object, rule 4's OWN spans, replayed
        independently -- object's condition-marker clip uses the
        SEGMENT bound, matching rule 4 exactly, NOT the sentence-bounded
        value-region bound from Step B) ALSO pass (so this credit is
        never a coincidental corroboration of an UNRELATED subject/
        object valency failure); AND a non-ASCII digit
        (_nb_check_non_ascii_digit_in_segment's own host-UCD guard)
        lies INSIDE this exact value region's own text span. Any other
        zero-candidate case returns None."""
    from reference.extraction import _COPULAS, _find_operator_after, _first_condition_marker_index
    from reference.primitives import APPROX_V1, PARTICIPLE_TRIGGERS_V1, is_content_token
    from reference.tables import T

    located = _nb_locate_hit(source_text, sentence_index, hit_ordinal)
    if located is None:
        return None
    sent, hit, seg_bounds, _hits = located
    start, end = hit.span
    seg_lo, seg_hi = next(((lo, hi) for lo, hi in seg_bounds if lo <= start < hi), (0, len(sent)))

    facet_def = T.facets_v1[hit.facet] if hit.facet in T.facets_v1 else None
    if not (facet_def and facet_def.get("measure")):
        return None

    # rule 1: OBLIGATION-PASSIVE -- claims this hit before rule 4/7 ever runs.
    if hit.facet == "facet:approval_requirement" and hit.trigger_key == ("required",):
        prev_tok = sent[start - 1] if start - 1 >= seg_lo else None
        if prev_tok is not None and prev_tok.fold in _COPULAS:
            if _find_operator_after(sent, end, seg_hi, "for") is not None:
                return None

    # rule 2: PASSIVE -- claims this hit (whether "by" is found or not) before rule 4/7.
    prev_tok = sent[start - 1] if start - 1 >= seg_lo else None
    if prev_tok is not None and prev_tok.fold in _COPULAS and hit.trigger_key[0] in PARTICIPLE_TRIGGERS_V1:
        return None

    # rule 3: COORDINATION -- claims this hit before rule 4/7 (value always None).
    if start - 1 >= seg_lo and sent[start - 1].fold == "and":
        return None

    # rule 4 (ACTIVE) reached; rule 7's OWN value-region bound (sentence-wide).
    sent_hi = len(sent)
    value_region_hi = sent_hi
    cs = _first_condition_marker_index(sent, end, sent_hi)
    if cs is not None:
        value_region_hi = cs

    num_positions = [i for i in range(end, value_region_hi) if sent[i].kind in ("NUMBER", "PCT100")]
    if len(num_positions) > 1:
        return "malformed"
    if len(num_positions) == 1:
        idx = num_positions[0]
        if idx > 0 and sent[idx - 1].fold in APPROX_V1:
            return "approx"
        return None

    # zero candidates: SAN-895's PER_HIT/unextractable arm, gated on the
    # hit's OWN non-value valencies (rule 4's subject/object spans,
    # rule 8's content-token check) passing independently.
    valency = facet_def.get("valency", [])
    obj_span = (end, seg_hi)
    obj_cond_start = _first_condition_marker_index(sent, end, seg_hi)
    if obj_cond_start is not None and obj_cond_start < obj_span[1]:
        obj_span = (obj_span[0], obj_cond_start)
    subj_span = (seg_lo, start)

    for role_name in valency:
        if role_name == "subject":
            if not any(is_content_token(t) for t in sent[subj_span[0] : subj_span[1]]):
                return None
        elif role_name == "object":
            if not any(is_content_token(t) for t in sent[obj_span[0] : obj_span[1]]):
                return None

    if end >= value_region_hi:
        return None
    region_text = source_text[sent[end].start : sent[value_region_hi - 1].end]
    if _nb_check_non_ascii_digit_in_segment(region_text):
        return "unextractable"
    return None


def _nb_adjunct_group_scan(source_text: str, sentence_index: int, hit_ordinal: int | None) -> str | None:
    """SAN-881 PASS 2B.1b-FIX B3: replays extract_roles -> adjunct_
    modifiers(subject) -> adjunct_modifiers(object) -- production's OWN
    call order for one hit (reference.extraction.extract_frames) --
    over the SHARED _nb_locate_hit replay's whole-sentence `sent`/
    `seg_bounds` (an adjunct GROUP is a subject/object ROLE-SPAN
    concept; a single hit's own narrow structural segment, as
    _nb_hit_segment_text reconstructs it, cannot express it). Returns
    which of adjunct_modifiers' own TWO group-walk abstain conditions
    would fire FIRST for this hit's OWN role spans, using the REAL
    production-compiled ADJUNCT_PREPOSITIONS_V1/RELATIVE_MARKERS_V1/
    TRIGGER_INDEX/MAX_TRIGGER_LEN tables (never the injected `tables_data`
    JSON view):
      "e15"    -- SAN-897 pairwise consecutive-adjunct-preposition chain:
                  ANY two adjunct prepositions in the SAME role span
                  with content between them are abstain-worthy UNLESS
                  the second is immediately preceded by "and" -- REPEATED
                  occurrences of the SAME preposition count exactly like
                  two distinct ones (production's own pairwise scan
                  never distinguishes same-vs-different preposition
                  words);
      "san894" -- SAN-894 a facet-trigger TOKEN (longest TRIGGER_INDEX
                  match, descending window length) found while walking
                  ANY preposition's own group -- NO article requirement;
    or None when neither condition fires for this hit at all (a CLEAN
    walk, OR extract_roles itself abstains, OR the group-walk aborts for
    an UNRELATED reason -- a RELATIVE_MARKERS_V1 token or a bare
    NUMBER/PCT100 token inside the group -- which is a DIFFERENT
    UNEXTRACTABLE cause, never mistaken for e15/san894 credit). Mirrors
    production's OWN short-circuit dispatch order EXACTLY: subject is
    scanned before object, and object is NEVER scanned if subject's own
    walk already aborted for ANY reason (matching/unrelated alike).

    SAN-881 PASS 2B.1b-FIX2 correction 3: extract_roles' own COORD
    pattern (rule 3) returns subject=(start, start) -- an EMPTY span --
    UNSPLICED; splicing in the genuine prior subject is a CALLER
    responsibility production discharges in extract_frames's OWN hit
    loop (extraction.py 765-774), never inside extract_roles itself.
    The prior version of this replay called extract_roles for ONLY the
    target hit, in isolation, so a COORD-pattern target hit was always
    scanned against its own empty (start, start) subject span -- never
    the SAME reject-or-splice extract_frames itself performs. This
    version replays EVERY hit in the sentence from the FIRST hit through
    hit_ordinal, IN ORDER, carrying prev_subject_span forward exactly as
    extract_frames's loop does: for each hit, if its own pattern is
    COORD, EITHER splice in prev_subject_span (when one already exists)
    OR -- production's EXACT reject step, extraction.py 769-771 --
    raise/reject this ONE hit with no update to prev_subject_span at all
    (an ORPHAN COORD hit, no valid prior subject, NEVER credits e15 or
    san894: if it is the target hit, this replay returns None here,
    before adjunct scanning ever runs; if it is an EARLIER hit, its
    rejection simply leaves prev_subject_span unchanged for the NEXT
    hit -- exactly like production, where the exception is raised
    BEFORE prev_subject_span is reassigned). A LATER COORD hit with a
    genuine prior subject (established by an earlier, successfully-
    processed hit -- COORD-spliced or not) remains fully eligible."""
    from reference.extraction import extract_roles
    from reference.primitives import (
        ADJUNCT_PREPOSITIONS_V1,
        Abstain,
        MAX_TRIGGER_LEN,
        RELATIVE_MARKERS_V1,
        Roles,
        TRIGGER_INDEX,
        UNEXTRACTABLE,
        is_content_token,
    )

    located = _nb_locate_hit(source_text, sentence_index, hit_ordinal)
    if located is None:
        return None
    sent, _target_hit, seg_bounds, hits = located

    prev_subject_span = None
    roles = None
    for idx, h in enumerate(hits[: hit_ordinal + 1]):
        try:
            r = extract_roles(h, sent, seg_bounds)
            if r.pattern == "COORD":
                if prev_subject_span is None:
                    raise Abstain(UNEXTRACTABLE)
                r = Roles(subject=prev_subject_span, object=r.object, value=r.value, pattern="COORD")
        except Abstain:
            if idx == hit_ordinal:
                return None
            continue
        prev_subject_span = r.subject
        if idx == hit_ordinal:
            roles = r
    if roles is None:
        return None

    _CLEAN, _OTHER = "clean", "other"

    def scan(span) -> str:
        if span is None:
            return _CLEAN
        start, end = span
        prep_idx = [k for k in range(start, end) if sent[k].fold in ADJUNCT_PREPOSITIONS_V1]
        for p, q in zip(prep_idx, prep_idx[1:]):
            if any(is_content_token(sent[m]) for m in range(p + 1, q)) and sent[q - 1].fold != "and":
                return "e15"
        i = start
        while i < end:
            tok = sent[i]
            if tok.fold in ADJUNCT_PREPOSITIONS_V1:
                j = i + 1
                group_end = end
                for k in range(j, end):
                    if sent[k].fold == "and" or sent[k].fold in ADJUNCT_PREPOSITIONS_V1:
                        group_end = k
                        break
                while j < end:
                    t2 = sent[j]
                    if t2.fold == "and" or t2.fold in ADJUNCT_PREPOSITIONS_V1:
                        break
                    if t2.fold in RELATIVE_MARKERS_V1:
                        return _OTHER
                    if t2.kind in ("NUMBER", "PCT100"):
                        return _OTHER
                    for length in range(min(MAX_TRIGGER_LEN, group_end - j), 0, -1):
                        key = tuple(t.fold for t in sent[j : j + length])
                        if key in TRIGGER_INDEX:
                            return "san894"
                    j += 1
                i = j
                continue
            i += 1
        return _CLEAN

    result = scan(roles.subject)
    if result in ("e15", "san894"):
        return result
    if result == _OTHER:
        return None
    if roles.object is not None:
        result = scan(roles.object)
        if result in ("e15", "san894"):
            return result
    return None


def _nb_check_polarity_via_deny_trigger(bundle: "ProductTraceBundle", check_id: str, field: str) -> bool:
    """FrameProductEvent.is_deny == True, ownership-qualified (assertive;
    tier_1/tier_2 for C1/C4 context; trusted_obligations for C3 context;
    aggregate obligation-satisfaction for C3 output -- the SAME frame-
    level ownership semantics facets_v1 uses)."""
    for ft in _pc_field_traces(bundle, field):
        for fe in ft.frame_events:
            if fe.is_deny and _pc_ownership_and_partiality_ok(bundle, "frame", fe.identity, fe.assertive, check_id, field):
                return True
    return False


def _nb_check_polarity_via_negator(bundle: "ProductTraceBundle", check_id: str, field: str) -> bool:
    """FrameProductEvent.negator_raw IS NOT None -- an IDENTITY check,
    never truthiness: a contraction-generated negator's own raw text is
    "" (empty string, e.g. the synthesized "not" from "won't"), which is
    falsy but NOT None, and must still credit."""
    for ft in _pc_field_traces(bundle, field):
        for fe in ft.frame_events:
            if fe.negator_raw is not None and _pc_ownership_and_partiality_ok(
                bundle, "frame", fe.identity, fe.assertive, check_id, field
            ):
                return True
    return False


def _nb_check_contraction_expansion(bundle: "ProductTraceBundle", item: dict, check_id: str, field: str) -> bool:
    """Binds an EXACT raw contraction token to the EXACT expansion
    production's own tokenizer emitted (_nb_contraction_occurrences),
    never substring matching and never independently locating expansion
    folds elsewhere. (C2, output) route: an expansion-derived token
    participates in the SHARED C2 lexical product (scan_c2_lexical) as a
    definitive span, a hedge span (rescuing or negated), or a negator
    token (via reference.extraction._consumed_negator_index, the SAME
    primitive production itself uses to identify the negator NEG_v1
    consumed). C1/C3/C4 routes: a qualifying assertive frame in the SAME
    source and sentence as a genuine contraction occurrence."""
    if check_id == "C2" and field == "output":
        return _nb_contraction_c2_route(item)

    source_texts = _nb_source_texts(item, field)
    for ft in _pc_field_traces(bundle, field):
        if ft.source_index >= len(source_texts):
            continue
        source_text = source_texts[ft.source_index]
        occurrences = _nb_contraction_occurrences(source_text)
        if not occurrences:
            continue
        occ_sentences = {
            _nb_token_sentence_index(source_text, carrier_idx)
            for carrier_idx, _expansion_idxs in occurrences
        }
        occ_sentences.discard(None)
        if not occ_sentences:
            continue
        for fe in ft.frame_events:
            if fe.identity[2] not in occ_sentences:
                continue
            if _pc_ownership_and_partiality_ok(bundle, "frame", fe.identity, fe.assertive, check_id, field):
                return True
    return False


def _nb_contraction_c2_route(item: dict) -> bool:
    from reference.checks import has_governed_question, scan_c2_lexical
    from reference.extraction import _consumed_negator_index, _segment_bounds
    from reference.primitives import tokenize

    output_text = item.get("output", "")
    occurrences = _nb_contraction_occurrences(output_text)
    if not occurrences:
        return False
    if has_governed_question(output_text):
        # SAN-881 PASS 2B.1b-FIX A1: production's own C2 never invokes
        # scan_c2_lexical for a governed-question output -- this route
        # rejects before scanning too, exactly like the six lexical
        # c2_* handlers in _predicate_nontable.
        return False
    expansion_indices: set = set()
    for _carrier_idx, expansion_idxs in occurrences:
        expansion_indices.update(expansion_idxs)

    out_tokens = tokenize(output_text)
    seg_bounds = _segment_bounds(out_tokens)
    # SAN-881 PASS 2B.1b-FIX A3: scan_c2_lexical streams -- this route
    # supplies its own sink to capture exactly the facts it needs.
    exams: list[dict] = []
    scan_c2_lexical(out_tokens, sink=exams.append)

    def _span_overlaps(span) -> bool:
        lo, hi = span
        return any(idx in expansion_indices for idx in range(lo, hi))

    for exam in exams:
        if _span_overlaps(exam["span"]):
            return True
        if exam["negated"]:
            neg_idx = _consumed_negator_index(out_tokens, exam["span"], seg_bounds)
            if neg_idx is not None and neg_idx in expansion_indices:
                return True
            continue
        rescuing = exam["rescuing_hedge"]
        if rescuing is not None and _span_overlaps(rescuing):
            return True
        for hedge_span in exam["negated_hedges"]:
            if _span_overlaps(hedge_span):
                return True
            neg_idx = _consumed_negator_index(out_tokens, hedge_span, seg_bounds)
            if neg_idx is not None and neg_idx in expansion_indices:
                return True
    return False


# PINNED (stage, cause) pairs (SAN-881 PASS 2B.1b, no empirical
# discretion): PartialStage enum member + the production cause string
# (or None for the three structural stages, which production never
# raises an exception for) -- "malformed_mention" / "unextractable" are
# production's OWN reference.primitives.MALFORMED_MENTION /
# .UNEXTRACTABLE literal values (a module-level dict literal cannot use
# a function-local production import, per this module's own lazy-import
# architecture, so the two pinned literal strings are spelled out
# directly here, exactly as production defines them). abstain_quant_
# abstain is handled separately via _pc_quant_abstain_event_matches (its
# own four-condition matcher, shared with the 50-surface
# quant_v1.abstain product coverage). Every value is a TUPLE of
# acceptable (stage, cause) pairs -- SAN-881 PASS 2B.1b-FIX B4:
# abstain_san895_non_ascii_digits is the SOLE surface with more than
# one acceptable production path: a non-ASCII digit character never
# forms a NUMBER token (host UCD guard: ch.isdigit() and not ASCII
# 0-9, so it consumes neither production's own _is_digit nor
# _is_letter), so it is either left wholly UNCONSUMED at sentence-level
# total-span accounting (TOTAL_SPAN_UNCONSUMED/None, no hit ever forms)
# or -- when it sits inside a measure-facet hit's own sole value
# candidate, so trigger_scan DOES find a hit -- costs that hit its
# value role, and rule 8 valency enforcement then aborts extract_roles
# with Abstain(UNEXTRACTABLE) (PER_HIT_ABSTAIN/unextractable). The
# other six surfaces keep their pre-fix SINGLE pinned pair, now wrapped
# in a one-element tuple for a uniform (name -> tuple-of-pairs) shape.
_GROUP_C_PINNED_PAIRS: dict = {
    "abstain_malformed_value": ((PartialStage.PER_HIT_ABSTAIN, "malformed_mention"),),
    "abstain_approx_value": ((PartialStage.PER_HIT_ABSTAIN, "malformed_mention"),),
    "abstain_e15_nested_adjunct_chain": ((PartialStage.PER_HIT_ABSTAIN, "unextractable"),),
    "abstain_san894_trigger_in_adjunct": ((PartialStage.PER_HIT_ABSTAIN, "unextractable"),),
    "abstain_san895_non_ascii_digits": (
        (PartialStage.TOTAL_SPAN_UNCONSUMED, None),
        (PartialStage.PER_HIT_ABSTAIN, "unextractable"),
    ),
    "abstain_e13_nonterminating_punctuation": ((PartialStage.NONTERMINATING_PUNCTUATION, None),),
    "abstain_interrogative_output": ((PartialStage.GOVERNED_INTERROGATIVE, None),),
}

# SAN-881 PASS 2B.1b-FIX B2: GOVERNED_INTERROGATIVE and
# NONTERMINATING_PUNCTUATION are each the SOLE Group C surface pinned
# to their own (stage, cause) pair above -- uniquely identifying on
# their own, with no other surface to disambiguate from. No additional
# (and, for e13, LOSSY: the retired regex `[.!?][A-Z]` required an
# uppercase letter after the terminator, missing genuine lowercase-
# adjacent production e13 cases like "guaranteed.actually" -- SPLIT_v1
# itself never checks case) textual detector runs for either.
_GROUP_C_STAGE_ONLY_SURFACES = frozenset({
    "abstain_interrogative_output",
    "abstain_e13_nonterminating_punctuation",
})


def _nb_check_malformed_value_in_segment(seg_text: str) -> bool:
    """SAN-881 PASS 2B.1b-FIX B3: the EXACT malformed numeric/value
    lexeme belonging to the identified hit -- re-tokenizes the hit's
    own (B1-narrowed) _nb_hit_segment_text through the pinned production
    tokenizer and counts NUMBER/PCT100-kind tokens: more than one
    candidate is the EXACT SAME "ZERO or MORE THAN ONE candidate"
    condition reference.extraction._find_unique_value_span itself
    raises malformed_mention on. Never substring/regex matching, and
    never unrelated later text (the segment is already event-local)."""
    from reference.primitives import tokenize

    toks = tokenize(seg_text)
    return sum(1 for t in toks if t.kind in ("NUMBER", "PCT100")) > 1


def _nb_check_approx_value_in_segment(seg_text: str) -> bool:
    """SAN-881 PASS 2B.1b-FIX B3: an EXACT APPROX_v1 token match
    immediately associated with the identified hit's value candidate --
    re-tokenizes the (B1-narrowed) segment text, requires EXACTLY one
    NUMBER/PCT100 candidate (never a malformed multi-candidate span --
    see _nb_check_malformed_value_in_segment, the two are mutually
    exclusive over the SAME segment, exactly mirroring
    _find_unique_value_span's own dichotomy), and checks the
    immediately-preceding token's FOLD identity against the REAL
    production APPROX_V1 table -- never a substring match (so
    "aboutface" never matches "about")."""
    from reference.primitives import APPROX_V1, tokenize

    toks = tokenize(seg_text)
    num_positions = [i for i, t in enumerate(toks) if t.kind in ("NUMBER", "PCT100")]
    if len(num_positions) != 1:
        return False
    idx = num_positions[0]
    return idx > 0 and toks[idx - 1].fold in APPROX_V1


def _nb_check_non_ascii_digit_in_segment(seg_text: str) -> bool:
    """SAN-881 PASS 2B.1b-FIX B3/B4 (SAN-895): a non-ASCII digit
    character in the event's own sentence/value region -- the host UCD
    guard (ch.isdigit() and not ASCII 0-9), NEVER a hand-enumerated
    Unicode code-point range table (the retired _contains_non_ascii_
    digit covered only 4 scripts and silently missed others, e.g.
    superscript digits and Bengali digits, both of which satisfy
    ch.isdigit() == True)."""
    return any(ch.isdigit() and not ("0" <= ch <= "9") for ch in seg_text)


def _nb_check_event_local_abstain(bundle: "ProductTraceBundle", item: dict, name: str, field: str, tables_data: dict) -> bool:
    """EVENT-LOCAL evidence for the seven pinned-pair Group C surfaces: a
    mechanism detector anywhere in a logical field plus an UNRELATED
    matching partial event is INSUFFICIENT -- the matching partial event
    must be found within the SAME FieldProductTrace/source AND sentence.
    SAN-881 PASS 2B.1b-FIX: `tables_data` is accepted for call-site
    signature compatibility but is NEVER read here -- every mechanism
    now consumes the REAL production-compiled tables (APPROX_V1,
    ADJUNCT_PREPOSITIONS_V1, TRIGGER_INDEX, ...) via the EXACT
    production-token predicates below, never the injected/toy JSON view.
    B2: abstain_interrogative_output/abstain_e13_nonterminating_
    punctuation credit on the (stage, cause) match ALONE (each is the
    sole surface at its own pair -- no textual corroboration is run).
    B3: abstain_e15_nested_adjunct_chain/abstain_san894_trigger_in_
    adjunct are PER_HIT_ABSTAIN-only and resolved via
    _nb_adjunct_group_scan (whole-sentence role-span replay -- an
    adjunct GROUP is not expressible within one hit's own narrow
    structural segment). SAN-881 PASS 2B.1b-FIX2 corrections 1+2:
    abstain_malformed_value/abstain_approx_value/abstain_san895_non_
    ascii_digits's PER_HIT_ABSTAIN pair are now resolved via
    _nb_classify_hit_value_region -- production's OWN value-role search
    region (extraction.py step 7: trigger end through sentence end or
    the first condition marker), never the hit's own comma-delimited
    structural segment _nb_hit_segment_text reconstructs (a DIFFERENT,
    narrower concept -- retired from this role); abstain_san895_non_
    ascii_digits's OTHER pinned pair (TOTAL_SPAN_UNCONSUMED, sentence-
    level, hit_ordinal is None) is still resolved directly against the
    WHOLE sentence text. Partial-event surfaces do NOT inherit frame
    trust qualifiers -- C1/C3/C4 consume field partiality BEFORE source
    trust filtering, so no ownership/tier check applies here at all."""
    pairs = _GROUP_C_PINNED_PAIRS.get(name)
    if pairs is None:
        return False
    source_texts = _nb_source_texts(item, field)
    for ft in _pc_field_traces(bundle, field):
        if not ft.partial:
            continue
        if ft.source_index >= len(source_texts):
            continue
        source_text = source_texts[ft.source_index]
        sentence_texts = _nb_sentence_texts(source_text)
        for pe in ft.partial_events:
            if (pe.stage, pe.cause) not in pairs:
                continue
            sentence_index = pe.identity[2]
            if sentence_index is None or sentence_index >= len(sentence_texts):
                continue

            if name in _GROUP_C_STAGE_ONLY_SURFACES:
                return True

            if pe.stage == PartialStage.PER_HIT_ABSTAIN:
                hit_ordinal = pe.identity[3]
                if name in ("abstain_e15_nested_adjunct_chain", "abstain_san894_trigger_in_adjunct"):
                    expected = "e15" if name == "abstain_e15_nested_adjunct_chain" else "san894"
                    if _nb_adjunct_group_scan(source_text, sentence_index, hit_ordinal) == expected:
                        return True
                    continue
                classification = _nb_classify_hit_value_region(source_text, sentence_index, hit_ordinal)
                if name == "abstain_malformed_value" and classification == "malformed":
                    return True
                if name == "abstain_approx_value" and classification == "approx":
                    return True
                if name == "abstain_san895_non_ascii_digits" and classification == "unextractable":
                    return True
                continue

            # the ONLY remaining reachable pair here is SAN-895's
            # sentence-level TOTAL_SPAN_UNCONSUMED (hit_ordinal is None).
            # SAN-881 PASS 2B.1b-FIX3: the conservative condition this
            # arm's own surrounding docstring already claimed but never
            # enforced -- crediting also requires the SAME SENTENCE
            # (ft.frame_events whose own identity[2] == this sentence_
            # index, never the field/source as a whole) to have formed NO
            # successful FrameProductEvent. "Item <superscript-5> costs
            # $5; JK." is ONE sentence (no terminal punctuation splits
            # it): the "costs" frame successfully consumes the subject
            # span containing the digit and the value $5, so this
            # sentence DOES have a frame -- "JK" is what actually goes
            # unconsumed, and crediting SAN-895 here would misattribute
            # the digit. A frame formed in a DIFFERENT sentence of the
            # same field/source must never suppress credit for this one.
            if name == "abstain_san895_non_ascii_digits" and _nb_check_non_ascii_digit_in_segment(sentence_texts[sentence_index]):
                if any(fe.identity[2] == sentence_index for fe in ft.frame_events):
                    continue
                return True
    return False


def _nb_check_abstain_quant_abstain(bundle: "ProductTraceBundle", field: str, tables_data: dict) -> bool:
    """nontable.abstain_quant_abstain calls the SAME single four-condition
    matcher (_pc_quant_abstain_event_matches) the 50-surface
    quant_v1.abstain product coverage uses -- no duplicate logic. The
    matcher is itself inherently event-local (PartialProductEvent.
    quant_token_fold is an attribute of the event, never a separate
    textual scan that could land in an unrelated sentence)."""
    abstain_folds = {fold_sequence(w)[0] for w in tables_data.get("quant_v1", {}).get("abstain", [])}
    for ft in _pc_field_traces(bundle, field):
        for pe in ft.partial_events:
            if _pc_quant_abstain_event_matches(ft, pe, abstain_folds):
                return True
    return False


def _check_nontable_bundle_backed_evidence(
    errors: Errors, per_surface_valid_records: dict, corpus_by_id: dict, tables_data: dict, bundle_for,
) -> None:
    """Groups B ({polarity_via_deny_trigger, polarity_via_negator,
    contraction_expansion}) and C (the eight abstain/event surfaces) --
    product-honest, event-local nontable evidence, using the SAME shared
    `bundle_for` cache _check_all_product_surfaces_evidence uses (see
    _make_bundle_cache / check_coverage_manifest)."""
    for surface, valid_records in per_surface_valid_records.items():
        name = surface.split(".", 1)[1] if "." in surface else surface
        for rec in valid_records:
            iid = rec["item_id"]
            if iid not in corpus_by_id:
                continue
            item = corpus_by_id[iid]
            bundle = bundle_for(iid)
            check_id, field = rec["check_id"], rec["field"]

            if name == "polarity_via_deny_trigger":
                ok = _nb_check_polarity_via_deny_trigger(bundle, check_id, field)
            elif name == "polarity_via_negator":
                ok = _nb_check_polarity_via_negator(bundle, check_id, field)
            elif name == "contraction_expansion":
                ok = _nb_check_contraction_expansion(bundle, item, check_id, field)
            elif name == "abstain_quant_abstain":
                ok = _nb_check_abstain_quant_abstain(bundle, field, tables_data)
            elif name in _GROUP_C_PINNED_PAIRS:
                ok = _nb_check_event_local_abstain(bundle, item, name, field, tables_data)
            else:
                ok = False

            if not ok:
                errors.add(f"coverage_manifest.json[{surface}] {iid}: rule={RULE_COVERAGE_PREDICATE_FAILED}")


def _check_nontable_surface_evidence(errors: Errors, surface: str, valid_records: list, corpus_by_id: dict, tables_data: dict) -> None:
    """The seven Group-A (c2_*) nontable surfaces' evidence check,
    BYTE-IDENTICAL to their pre-2B.1-P behavior: the ORIGINAL
    static-lexical presence proof over ONLY the declared record's OWN
    field text (_field_text / COVERAGE_PREDICATES['nontable'] /
    _predicate_nontable), never the product-trace substrate and never
    CAPABILITY_MAP (see
    test_check_coverage_nontable_ast_never_references_product_trace_or_capability_map,
    which asserts this function's own AST contains NEITHER). The
    remaining eleven Group-B/C nontable surfaces are NOT checked here --
    they route through _check_nontable_bundle_backed_evidence instead
    (see check_coverage_manifest's own Pass B dispatch)."""
    predicate = COVERAGE_PREDICATES.get("nontable")
    for rec in valid_records:
        iid = rec["item_id"]
        if iid not in corpus_by_id:
            continue
        predicate_text = _field_text(corpus_by_id[iid], rec["field"])
        if predicate_text is None:
            continue
        if predicate is None:
            errors.add(f"coverage_manifest.json[{surface}] {iid}: rule={RULE_COVERAGE_NO_PREDICATE}")
        elif not predicate(predicate_text, surface, tables_data):
            errors.add(f"coverage_manifest.json[{surface}] {iid}: rule={RULE_COVERAGE_PREDICATE_FAILED}")


def _check_all_product_surfaces_evidence(
    errors: Errors, per_surface_valid_records: dict, corpus_by_id: dict, tables_data: dict,
    bundle_for=None,
) -> None:
    """The 50 in-scope surfaces' (47 table-derived + 3 value_role_v1)
    PASS B evidence check: builds (and caches, ONCE per item) each
    referenced item's ProductTraceBundle via build_product_trace_bundle,
    then evaluates the four-clause product contract (this function's own
    AST references BOTH build_product_trace_bundle and CAPABILITY_MAP --
    see test_check_coverage_product_ast_references_product_trace_and_capability_map)
    for every evidence record of every surface whose predicate_id is one
    of CAPABILITY_MAP's own eight families. Reached ONLY when Pass A
    (schema-adjacent shape/ID/position/scenario-independence, in
    check_coverage_manifest) found ZERO errors across the COMPLETE
    manifest.

    SAN-881 PASS 2B.1b: `bundle_for` is an OPTIONAL shared cache callable
    (item_id -> ProductTraceBundle) -- check_coverage_manifest now builds
    ONE Pass-B-wide cache (_make_bundle_cache) and passes the SAME
    callable to this function AND to _check_nontable_bundle_backed_
    evidence (Groups B/C), so a mixed manifest referencing the same item
    from BOTH a 50-surface record and a Group B/C nontable record builds
    that item's bundle EXACTLY once. Defaults to building its own LOCAL,
    independently-cached callable (this function's own pre-2B.1b
    behavior, unchanged) when not supplied, so this function remains
    independently callable/testable exactly as before, and its own AST
    still directly references build_product_trace_bundle."""
    if bundle_for is None:
        bundle_cache: dict[str, ProductTraceBundle] = {}

        def _bundle_for(item_id: str) -> ProductTraceBundle:
            if item_id not in bundle_cache:
                bundle_cache[item_id] = build_product_trace_bundle(corpus_by_id[item_id])
            return bundle_cache[item_id]
    else:
        _bundle_for = bundle_for

    for surface, valid_records in per_surface_valid_records.items():
        registry_entry = SURFACE_REGISTRY.get(surface)
        family = registry_entry["predicate_id"] if registry_entry else surface.split(".", 1)[0]
        if not any(family == cm_family for cm_family, _cm_location in CAPABILITY_MAP):
            # Not one of the eight CAPABILITY_MAP families (an
            # unregistered surface's guessed predicate_id, in a toy/unit
            # test that bypasses check_coverage_registry_closure) -- no
            # predicate exists for it, matching the pre-2B.1-P fallback.
            for rec in valid_records:
                errors.add(f"coverage_manifest.json[{surface}] {rec['item_id']}: rule={RULE_COVERAGE_NO_PREDICATE}")
            continue

        if family in ("excl_v1", "complement_v1"):
            groups: dict[tuple, list] = {}
            for rec in valid_records:
                groups.setdefault((rec["item_id"], rec["check_id"]), []).append(rec)
            for (iid, cid), recs in groups.items():
                if iid not in corpus_by_id:
                    continue
                bundle = _bundle_for(iid)
                fields_named = {r["field"] for r in recs}
                if family == "excl_v1":
                    ok = _pc_check_joint_excl_group(bundle, surface, tables_data, fields_named, cid)
                else:
                    ok = _pc_check_joint_complement_group(bundle, surface, tables_data, fields_named, cid)
                if not ok:
                    errors.add(f"coverage_manifest.json[{surface}] {iid}/{cid}: rule={RULE_COVERAGE_JOINT_MEMBER_MISSING}")
            continue

        for rec in valid_records:
            iid = rec["item_id"]
            if iid not in corpus_by_id:
                continue
            bundle = _bundle_for(iid)
            if not _pc_check_surface_record(bundle, surface, family, rec["check_id"], rec["field"], tables_data):
                errors.add(f"coverage_manifest.json[{surface}] {iid}: rule={RULE_COVERAGE_PREDICATE_FAILED}")


# ---------------------------------------------------------------------
# Reveal verification (executable; toy-tested by test_calibration.py)
# ---------------------------------------------------------------------

def _detect_stage_extras(
    commitment: dict,
    subset_names: set[str],
    forbidden_extra_names: set[str],
    artifact_bytes_by_name: dict[str, bytes],
) -> list[str]:
    """Presence-only checks (forbidden stage extra, undeclared extra) --
    require only WHICH artifact names were supplied plus the commitment's
    own declared names, never parsed/schema-valid content. Extracted from
    reveal_verify_subset (SAN-881 PASS-1 CORRECTION ROUND, Section E) so
    these checks can run independently of -- and are never gated by -- any
    schema-validity check on the legitimate subset members' content.
    SAN-881 PASS-1 FINAL GATING CORRECTION: hardened against non-dict
    `author_commitments` members and an unhashable declared
    `artifact_name` (e.g. a list) -- never raises."""
    failures: list[str] = []
    declared = {_hashable_or_marker(c.get("artifact_name")) for c in commitment.get("author_commitments", []) if isinstance(c, dict)}
    ac = commitment.get("artifact_commitment")
    if isinstance(ac, dict) and "artifact_name" in ac:
        declared.add(_hashable_or_marker(ac["artifact_name"]))
    for name in artifact_bytes_by_name:
        if name in forbidden_extra_names:
            failures.append(f"reveal verification: forbidden stage extra supplied: {name}")
        elif name not in subset_names and name not in declared:
            failures.append(f"reveal verification: undeclared extra artifact(s) supplied: {name}")
    return failures


def reveal_verify_subset(
    commitment: dict,
    subset_names: set[str],
    forbidden_extra_names: set[str],
    artifact_bytes_by_name: dict[str, bytes],
    nonces_by_name: dict[str, str],
) -> list[str]:
    """SINGLE-ARTIFACT/SUBSET reveal verification for the semantic-only
    stage: only `subset_names` need be supplied and verified. Any
    OTHER artifact declared in the commitment may remain unrevealed
    (not an error). Supplying anything in `forbidden_extra_names`
    (contract/design/coverage reasoning) is a hard rejection -- that
    content must never leak into semantic adjudication. An artifact
    outside BOTH subset_names and forbidden_extra_names but not declared
    at all is also rejected as an undeclared extra.

    This function's own free-form failure strings are PRESERVED exactly
    (they are directly unit-tested). SAN-881 PASS-1 CORRECTION ROUND: the
    STAGED path (run_stage_reveal_verification) no longer calls this
    function directly -- it calls _reveal_verify_subset_fixed_codes
    instead, which shares this function's exact logic but emits fixed
    rule=CODE diagnostics (Section E)."""
    failures: list[str] = []
    try:
        ctx_hash = bytes.fromhex(commitment["labeling_context_hash"])
    except (ValueError, TypeError, KeyError):
        failures.append("reveal verification: labeling_context_hash is not valid 64-lowercase-hex")
        return failures
    failures.extend(_detect_stage_extras(commitment, subset_names, forbidden_extra_names, artifact_bytes_by_name))

    # SAN-881 PASS-1 FINAL GATING CORRECTION: hardened against non-dict
    # author_commitments members and an unhashable declared artifact_name
    # (e.g. a list) -- never raises. Well-formed dict entries (the only
    # shape this function's own preserved unit tests ever supply) are
    # keyed identically to before.
    entries_by_name: dict = {}
    for c in commitment.get("author_commitments", []):
        if isinstance(c, dict):
            entries_by_name[_hashable_or_marker(c.get("artifact_name"))] = c
    ac = commitment.get("artifact_commitment")
    if isinstance(ac, dict):
        entries_by_name[_hashable_or_marker(ac.get("artifact_name"))] = ac

    for name in subset_names:
        entry = entries_by_name.get(name)
        if entry is None:
            # SAN-881 Phase-A correction: a subset member this envelope
            # never declares at all (e.g. no reviewer commitment envelope
            # was resolvable) is NOT "nothing to verify" -- it is a hard
            # failure, identical in effect to the artifact being missing.
            # Missing reviewer artifacts FAIL, never skip.
            failures.append(f"reveal verification: sealed artifact {name} not supplied")
            continue
        artifact_bytes = artifact_bytes_by_name.get(name)
        if artifact_bytes is None:
            failures.append(f"reveal verification: sealed artifact {name} not supplied")
            continue
        if len(artifact_bytes) != entry["byte_length"]:
            failures.append(f"reveal verification: {name} byte_length mismatch")
            continue
        nonce_hex = nonces_by_name.get(name)
        if nonce_hex is None:
            failures.append(f"reveal verification: no nonce provided for {name}")
            continue
        try:
            nonce = bytes.fromhex(nonce_hex)
        except (ValueError, TypeError):
            failures.append(f"reveal verification: {name} nonce is not valid 64-lowercase-hex")
            continue
        if not verify_reveal(entry["commitment_hex"], name, nonce, ctx_hash, artifact_bytes):
            failures.append(f"reveal verification: {name} commitment does NOT verify against revealed nonce+bytes")
    return failures


def _detect_stage_extras_fixed_codes(
    errors: Errors,
    commitment: dict,
    subset_names: set[str],
    forbidden_extra_names: set[str],
    artifact_bytes_by_name: dict[str, bytes],
) -> None:
    """Fixed-rule-code twin of _detect_stage_extras (SAN-881 PASS-1
    CORRECTION ROUND, Section E) -- appends directly to `errors` instead
    of returning free-form strings. SAN-881 PASS-1 FINAL GATING
    CORRECTION: hardened against an unhashable declared `artifact_name`
    (e.g. a malformed reviewer envelope's `artifact_commitment:
    {"artifact_name": []}` -- schema-invalid, but this function must
    still never raise if it is ever reached with such a value) -- never
    raises."""
    declared = {_hashable_or_marker(c.get("artifact_name")) for c in commitment.get("author_commitments", []) if isinstance(c, dict)}
    ac = commitment.get("artifact_commitment")
    if isinstance(ac, dict) and "artifact_name" in ac:
        declared.add(_hashable_or_marker(ac["artifact_name"]))
    for name in artifact_bytes_by_name:
        if name in forbidden_extra_names:
            errors.add(f"reveal-verification: rule={RULE_REVEAL_FORBIDDEN_EXTRA}")
        elif name not in subset_names and name not in declared:
            errors.add(f"reveal-verification: rule={RULE_REVEAL_EXTRA}")


def _reveal_verify_subset_fixed_codes(
    errors: Errors,
    commitment: dict,
    subset_names: set[str],
    forbidden_extra_names: set[str],
    artifact_bytes_by_name: dict[str, bytes],
    nonces_by_name: dict[str, str],
) -> None:
    """Fixed-rule-code twin of reveal_verify_subset (SAN-881 PASS-1
    CORRECTION ROUND, Section E): identical subset/crypto logic, but
    every diagnostic is a fixed `{artifact_name}: rule=RULE_*` string --
    NEVER reveal_verify_subset's own free-form prose. This is the ONLY
    function the staged reveal path (run_stage_reveal_verification) may
    use to append extras/crypto outcomes to `errors`; the staged path
    never appends reveal_verify_subset's own return value directly."""
    try:
        ctx_hash = bytes.fromhex(commitment["labeling_context_hash"])
    except (ValueError, TypeError, KeyError):
        errors.add(f"reveal-verification: rule={RULE_CONTEXT_HASH_MISMATCH}")
        return

    _detect_stage_extras_fixed_codes(errors, commitment, subset_names, forbidden_extra_names, artifact_bytes_by_name)

    entries_by_name = {c["artifact_name"]: c for c in commitment.get("author_commitments", []) if isinstance(c, dict)}
    ac = commitment.get("artifact_commitment")
    if isinstance(ac, dict) and "artifact_name" in ac:
        entries_by_name[ac["artifact_name"]] = ac

    for name in subset_names:
        entry = entries_by_name.get(name)
        if entry is None:
            errors.add(f"{name}: rule={RULE_REVEAL_NOT_SUPPLIED}")
            continue
        artifact_bytes = artifact_bytes_by_name.get(name)
        if artifact_bytes is None:
            errors.add(f"{name}: rule={RULE_REVEAL_NOT_SUPPLIED}")
            continue
        if len(artifact_bytes) != entry.get("byte_length"):
            errors.add(f"{name}: rule={RULE_REVEAL_BYTE_LENGTH}")
            continue
        nonce_hex = nonces_by_name.get(name)
        if nonce_hex is None:
            errors.add(f"{name}: rule={RULE_REVEAL_NO_NONCE}")
            continue
        try:
            nonce = bytes.fromhex(nonce_hex)
        except (ValueError, TypeError):
            errors.add(f"{name}: rule={RULE_NONCE_MALFORMED}")
            continue
        if not verify_reveal(entry.get("commitment_hex"), name, nonce, ctx_hash, artifact_bytes):
            errors.add(f"{name}: rule={RULE_REVEAL_DOES_NOT_VERIFY}")


REVEAL_STAGES = ("semantic", "contract")

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def _is_hex64(value: Any) -> bool:
    return isinstance(value, str) and _HEX64_RE.match(value) is not None


def _path_is_inside(child: Path, parent: Path) -> bool:
    """True if `child` is inside `parent` (or equal to it) EITHER
    LEXICALLY (raw `.absolute()`, no symlink resolution, `..` segments
    NOT collapsed) OR by REALPATH (`.resolve(strict=True)`, symlinks and
    `..` fully resolved) -- SAN-881 PASS-1 CORRECTION: the pre-fix
    version checked resolved containment ONLY, despite the
    docstring/README already claiming both. A path such as
    `sealed_dir/../author_nonces.json` resolves OUTSIDE `sealed_dir` yet
    its raw lexical ancestry still traverses `sealed_dir` via
    `child.absolute().parents` -- that lexical traversal alone is now
    sufficient to reject it, independent of where it ultimately resolves.
    A resolution error (missing path, broken symlink, symlink loop,
    permission) FAILS CLOSED -- returns True (treated as inside /
    rejected) -- never silently treated as "safely outside". Used to
    reject --nonces-file / --reviewer-nonces-file paths that live inside
    the bundle directory they accompany -- they are not bundle members
    and must be supplied from outside it."""
    child_lexical = child.absolute()
    parent_lexical = parent.absolute()
    lexical_inside = child_lexical == parent_lexical or parent_lexical in child_lexical.parents
    try:
        child_resolved = child.resolve(strict=True)
        parent_resolved = parent.resolve(strict=True)
    except (OSError, RuntimeError):
        return True
    resolved_inside = child_resolved == parent_resolved or parent_resolved in child_resolved.parents
    return lexical_inside or resolved_inside


def _check_bundle_exact_membership(
    errors: Errors,
    dir_path: Path | None,
    allowed_names: frozenset[str],
    label: str,
    forbidden_names: frozenset[str] = frozenset(),
) -> bool:
    """PATH GATE: directory-listing-based EXACT membership check (SAN-881
    Phase-A correction item 1): dir_path's entries must equal
    allowed_names EXACTLY. A missing pinned member is reported by its
    (fixed, never attacker-controlled) name; an extra/unrecognized entry
    is reported WITHOUT echoing its name (that name comes from the
    filesystem, i.e. an attacker-controlled value in the threat model
    this check exists for) -- one RULE_REVEAL_EXTRA per extra entry is
    still emitted, just without the filename in the message. An extra
    entry whose name happens to be a member of the FIXED, known
    `forbidden_names` vocabulary (the other stage's own artifact names --
    always a compile-time constant, never attacker-controlled) is
    reported with the more specific RULE_REVEAL_FORBIDDEN_EXTRA instead,
    still without echoing anything beyond the fixed rule code.

    This entire check is PRESENCE/TYPE-ONLY -- it opens no file content,
    just `iterdir()` + `is_symlink()`/`is_file()` metadata -- so it is
    safe to run as the FIRST, content-free tier of the three-tier gated
    pipeline (PATH GATE). Returns True iff dir_path exists and its
    entries equal allowed_names exactly, with every allowed member a
    direct regular non-symlink file (no missing, no extra of either
    kind, no wrong-type member) -- callers combine this boolean across
    every independent PATH GATE check before permitting ANY staged-
    payload content read for the stage.

    SAN-881 PASS-1 CORRECTION ROUND (Section D) root repair: this
    inspects EVERY immediate directory entry, not only `Path.is_file()`
    survivors -- the prior `if p.is_file()` filter SILENTLY DROPPED
    directories, sockets, and FIFOs from consideration entirely (an
    arbitrarily-named directory was previously INVISIBLE to this check:
    neither counted as "extra" nor as "present"). `Path.is_file()` also
    FOLLOWS SYMLINKS, so a pinned name symlinked to a real regular file
    elsewhere previously satisfied this check even though it is not
    itself a regular file -- a genuine custody-bypass vector. Every
    allowed member must now be a DIRECT, REGULAR, NON-SYMLINK file;
    anything else at a pinned name (directory, symlink, socket, FIFO,
    ...) fails with RULE_REVEAL_NOT_REGULAR_FILE (the name is pinned,
    never attacker-controlled, so it is safe to echo)."""
    if dir_path is None or not dir_path.exists():
        for missing in sorted(allowed_names):
            errors.add(f"{label}[{missing}]: rule={RULE_REVEAL_NOT_SUPPLIED}")
        return not allowed_names

    try:
        entries = list(dir_path.iterdir())
    except OSError:
        errors.add(f"{label}: rule={RULE_STAGED_IO_FAILURE}")
        return False

    actual_names = {p.name for p in entries}
    regular_file_names = {p.name for p in entries if not p.is_symlink() and p.is_file()}

    missing = sorted(allowed_names - actual_names)
    extra = sorted(actual_names - allowed_names)
    wrong_type = sorted((allowed_names & actual_names) - regular_file_names)

    for name in missing:
        errors.add(f"{label}[{name}]: rule={RULE_REVEAL_NOT_SUPPLIED}")
    for name in extra:
        if name in forbidden_names:
            errors.add(f"{label}: rule={RULE_REVEAL_FORBIDDEN_EXTRA}")
        else:
            errors.add(f"{label}: rule={RULE_REVEAL_EXTRA}")
    for name in wrong_type:
        errors.add(f"{label}[{name}]: rule={RULE_REVEAL_NOT_REGULAR_FILE}")

    return not (missing or extra or wrong_type)


def _check_nonce_map(errors: Errors, nonces: Any, expected_keys: frozenset[str], label: str) -> bool:
    """PATH-GATE-ADJACENT: exact keyset + per-value hex64-shape check for
    a nonce map (SAN-881 Phase-A correction item 1). A missing key, an
    extra key (including one that names the OTHER side's own artifact --
    a reviewer nonce map key attempting to overwrite an author key, or
    vice versa, is simply not a member of expected_keys and is caught
    here the same as any other extra), and a malformed (non-64-lowercase-
    hex) value are each reported with a fixed RULE_* code. Returns True
    iff the keyset matches EXACTLY and every value is valid hex64.

    SAN-881 PASS-1 FINAL GATING CORRECTION (nonce/name non-disclosure):
    the hex64-shape check runs ONLY over keys that are BOTH expected AND
    supplied (`expected_keys & nonces.keys()`) -- an unknown/extra
    supplied key (attacker-controlled, arbitrary text) is covered SOLELY
    by the generic RULE_NONCE_KEYSET_MISMATCH above; its name is never
    echoed via a `{label}[{key}]: rule=...` line, and its value is never
    separately inspected. Previously every supplied key's value was
    hex64-checked regardless of whether the key was expected, which
    echoed an attacker-controlled key verbatim into `{label}[{key}]`."""
    if not isinstance(nonces, dict):
        errors.add(f"{label}: rule={RULE_STAGED_IO_FAILURE}")
        return False
    keyset_ok = set(nonces.keys()) == expected_keys
    if not keyset_ok:
        errors.add(f"{label}: rule={RULE_NONCE_KEYSET_MISMATCH}")
    values_ok = True
    for key in sorted(expected_keys & nonces.keys()):
        if not _is_hex64(nonces[key]):
            values_ok = False
            errors.add(f"{label}[{key}]: rule={RULE_NONCE_MALFORMED}")
    return keyset_ok and values_ok


def _snapshot_regular_file(path: Path) -> bytes | None:
    """SNAPSHOT GATE primitive: reads `path` EXACTLY ONCE as a genuine,
    non-symlink regular file, refusing to follow a symlink at the leaf
    (O_NOFOLLOW) -- a rejected symlink target must never be opened, even
    when it happens to point at legitimate bytes elsewhere (the PATH
    GATE symlink-rejection above must never be undermined by a SECOND,
    less careful read later in the pipeline). Returns None -- never
    raises -- for ANY failure: missing, wrong type (directory, socket,
    FIFO, symlink), permission, or other OS-level I/O error. This is the
    ONLY function in this module that opens a staged bundle member's
    content; every downstream consumer (schema validation, cryptographic
    reveal) reuses the SAME bytes object it returns rather than
    re-opening the path.

    SAN-881 PASS-1 CLOSURE PATCH (closure 5, O_NOFOLLOW fail-closed): if
    `os.O_NOFOLLOW` is unavailable on this platform, this helper fails
    closed WITHOUT ever calling os.open -- proceeding with a
    follow-symlinks open would silently defeat the entire no-follow
    safety guarantee this function exists to provide. `os.open` is
    called ONLY when O_NOFOLLOW can genuinely be included in the open
    flags."""
    if not hasattr(os, "O_NOFOLLOW"):
        return None
    flags = os.O_RDONLY | os.O_NOFOLLOW
    try:
        fd = os.open(os.fspath(path), flags)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return None
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    except OSError:
        return None
    finally:
        os.close(fd)


# ---------------------------------------------------------------------
# SAN-881 PASS-1 CORRECTION ROUND, Section A: SELECTED-STAGE SCHEMA
# VALIDATION. Root repair -- the staged verifier previously proved "these
# are the committed bytes" (cryptographic reveal) without proving "these
# bytes are valid labels/design/coverage under the frozen schemas". Every
# selected-stage artifact -- INCLUDING the reviewer commitment envelope,
# checked SPECIFICALLY against its stage's own discriminant, never the
# root oneOf -- is parsed and schema-validated here BEFORE any
# cryptographic subset verification is permitted for that stage.
# ---------------------------------------------------------------------

# Per-artifact-name -> (schema filename under SCHEMAS/, specific $defs
# branch or None for a single-shape schema). A contract-shaped labels
# file must FAIL the semantic stage and vice versa -- semanticFile /
# contractFile are validated SPECIFICALLY, never labels_schema's root
# oneOf (which would accept either shape).
_STAGE_ARTIFACT_SCHEMA_SPEC: dict[str, tuple[str, str | None]] = {
    "labels_author_semantic.json": ("labels_schema.json", "semanticFile"),
    REVIEWER_SEMANTIC_ARTIFACT: ("labels_schema.json", "semanticFile"),
    "labels_author_contract.json": ("labels_schema.json", "contractFile"),
    REVIEWER_CONTRACT_ARTIFACT: ("labels_schema.json", "contractFile"),
    "design_metadata.json": ("design_metadata_schema.json", None),
    "coverage_manifest.json": ("coverage_manifest_schema.json", None),
}

# The reviewer commitment envelope's SPECIFIC discriminant per stage --
# never inferred from the envelope's own envelope_kind field (that would
# let a wrong-kind envelope choose its own, more permissive, validation
# branch).
_STAGE_REVIEWER_ENVELOPE_DEF: dict[str, str] = {
    "semantic": "reviewerSemanticEnvelope",
    "contract": "reviewerContractEnvelope",
}


def _parse_json_bytes(errors: Errors, data: bytes, label: str) -> tuple[Any, bool]:
    """JSON-safe parse of ALREADY-READ bytes (no filesystem access --
    this module's SNAPSHOT GATE reads a staged file's bytes exactly once
    via _snapshot_regular_file; this helper never re-opens the path).
    Never raises. Returns (parsed_value, ok)."""
    try:
        return json.loads(data.decode("utf-8")), True
    except (UnicodeDecodeError, ValueError):
        errors.add(f"{label}: rule={RULE_STAGED_IO_FAILURE}")
        return None, False


def check_stage_schema_validity(
    errors: Errors,
    stage: str,
    subset_names: set[str],
    reviewer_artifact_name: str,
    reviewer_commitment_file: str,
    snapshots: dict[str, bytes],
    expected_ctx_hash_hex: Any,
    cache: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    """SNAPSHOT GATE: parses and schema-validates every snapshotted
    artifact belonging to `stage`'s subset -- including the reviewer
    commitment envelope -- against its SPECIFIC stage-appropriate shape.
    This function performs NO filesystem access of its own: every byte
    it parses came from `snapshots`, populated by the caller via
    _snapshot_regular_file EXACTLY ONCE per approved file (a rejected
    PATH GATE member is never a key in `snapshots` at all, so it is
    never even a candidate for parsing here). An artifact that is simply
    ABSENT from `snapshots` is SKIPPED here (its absence is
    independently reported by the PATH GATE bundle-membership check --
    this function's job is narrowly "is every SNAPSHOTTED selected
    artifact genuinely valid under its frozen schema", not presence).

    ALSO performs reviewer-envelope CONTEXT CONSISTENCY: a
    schema-valid, correctly-discriminated reviewer commitment envelope
    whose OWN declared labeling_context_hash does not match
    `expected_ctx_hash_hex` (the author envelope's hash) now GATES ok to
    False too -- SAN-881 PASS-1 FINAL GATING CORRECTION root repair: a
    context-hash-inconsistent reviewer envelope previously still let
    cryptographic subset verification run (and merely accumulated
    RULE_ENVELOPE_CONTEXT_HASH_INCONSISTENT alongside it), instead of
    being gated shut before any crypto call.

    Returns (ok, parsed): ok is True iff no snapshotted artifact failed
    JSON parsing, schema validation, discriminator validation, or (for
    the reviewer envelope) context consistency. `parsed` holds the
    successfully-parsed JSON value for every snapshot name that parsed
    cleanly, so the CRYPTO GATE caller never re-parses a snapshot it has
    already paid the cost of decoding once. Never raises: malformed
    JSON or a schema-invalid structure are fixed-code failures here,
    never an uncaught exception -- and never passed into cryptographic
    subset verification merely to accumulate additional errors.

    SAN-881 PASS-1 CLOSURE PATCH (closure 4, gate-not-skip): a subset
    member or the reviewer commitment envelope that is APPROVED (its
    name belongs to `subset_names` / it is `reviewer_commitment_file`)
    but is ABSENT from `snapshots` -- meaning PATH GATE confirmed it as a
    genuine regular, non-symlink bundle member, yet the subsequent
    no-follow snapshot read itself failed (a transient I/O error or a
    TOCTOU race between the PATH GATE stat and the SNAPSHOT GATE open)
    -- now GATES this stage shut (`ok = False`, a fixed
    RULE_STAGED_IO_FAILURE diagnostic) instead of being silently
    skipped. Previously `ok` stayed True whenever every OTHER
    snapshotted member validated, letting cryptographic verification
    proceed for those other members even though one required member's
    content was never actually inspected -- never skip an absent
    snapshot.

    SAN-881 PASS-1 FINAL CLOSURE CORRECTION: per-artifact schemas are
    read from `cache["schema"]` (the Tier-0 single-source cache built
    ONCE at the top of `main()`) instead of `load_json(SCHEMAS / ...)` --
    this function performs ZERO schema reads of its own; a schema is
    NEVER reopened during stage execution. `cache["schema"]` is
    guaranteed to hold all six self-valid schemas by the time this
    function can be reached (author_gate_ok already requires
    `schemas_self_valid_ok`), but a defensive missing-entry check still
    fails closed with a fixed diagnostic rather than raising a
    KeyError."""
    parsed: dict[str, Any] = {}
    if Draft202012Validator is None:
        errors.add(f"{stage}: rule={RULE_JSONSCHEMA_MODULE_MISSING}")
        return False, parsed

    ok = True
    for name in sorted(subset_names):
        if name not in snapshots:
            errors.add(f"{name}: rule={RULE_STAGED_IO_FAILURE}")
            ok = False
            continue
        instance, ok_parse = _parse_json_bytes(errors, snapshots[name], name)
        if not ok_parse:
            ok = False
            continue
        parsed[name] = instance
        schema_filename, def_name = _STAGE_ARTIFACT_SCHEMA_SPEC[name]
        schema = cache["schema"].get(schema_filename)
        if schema is None:
            errors.add(f"{name}: rule={RULE_SCHEMA_INVALID}")
            ok = False
        elif not _validate_specific(errors, name, schema, def_name, instance):
            ok = False

    if reviewer_commitment_file in snapshots:
        env_instance, env_ok_parse = _parse_json_bytes(errors, snapshots[reviewer_commitment_file], reviewer_commitment_file)
        if not env_ok_parse:
            ok = False
        else:
            parsed[reviewer_commitment_file] = env_instance
            commitment_schema = cache["schema"].get("commitment_schema.json")
            def_name = _STAGE_REVIEWER_ENVELOPE_DEF[stage]
            if commitment_schema is None:
                errors.add(f"{reviewer_commitment_file}: rule={RULE_SCHEMA_INVALID}")
                ok = False
            elif not _validate_specific(errors, reviewer_commitment_file, commitment_schema, def_name, env_instance):
                ok = False
            elif isinstance(env_instance, dict) and env_instance.get("labeling_context_hash") != expected_ctx_hash_hex:
                errors.add(f"{reviewer_commitment_file}: rule={RULE_ENVELOPE_CONTEXT_HASH_INCONSISTENT}")
                ok = False
    else:
        errors.add(f"{reviewer_commitment_file}: rule={RULE_STAGED_IO_FAILURE}")
        ok = False

    return ok, parsed


def _check_nonce_path_tier1(errors: Errors, path: Path | None, bundle_dir: Path | None, label: str) -> bool:
    """TIER 1 (metadata/location ONLY -- ZERO content read, ZERO nonce
    read). A stage nonce-file path must be SUPPLIED, resolve to a
    genuinely existing DIRECT REGULAR NON-SYMLINK file (a leaf symlink
    is rejected regardless of where it points -- SAN-881 PASS-1 FINAL
    CLOSURE CORRECTION v1 threat boundary: leaf symlinks are in scope,
    same as a bundle member), and live OUTSIDE `bundle_dir` both
    LEXICALLY and by REALPATH (`_path_is_inside` resolves both sides).
    Uses ONLY path-metadata calls (`is_symlink`, `exists`, `is_file`) --
    never opens file content; the actual nonce-file READ happens at
    Tier 2, and only after every Tier-1 operand across BOTH nonce paths
    and BOTH bundles has passed."""
    if path is None:
        errors.add(f"{label}: rule={RULE_STAGED_IO_FAILURE}")
        return False
    if bundle_dir is not None and _path_is_inside(path, bundle_dir):
        errors.add(f"{label}: rule={RULE_NONCE_FILE_INSIDE_BUNDLE}")
        return False
    try:
        is_symlink = path.is_symlink()
    except OSError:
        errors.add(f"{label}: rule={RULE_STAGED_IO_FAILURE}")
        return False
    if is_symlink:
        errors.add(f"{label}: rule={RULE_REVEAL_NOT_REGULAR_FILE}")
        return False
    try:
        exists = path.exists()
        is_file = path.is_file() if exists else False
    except OSError:
        errors.add(f"{label}: rule={RULE_STAGED_IO_FAILURE}")
        return False
    if not exists:
        errors.add(f"{label}: rule={RULE_STAGED_IO_FAILURE}")
        return False
    if not is_file:
        errors.add(f"{label}: rule={RULE_REVEAL_NOT_REGULAR_FILE}")
        return False
    return True


def run_stage_reveal_verification(
    errors: Errors,
    commitment: dict,
    stage: str,
    sealed_dir: Path | None,
    nonces_path: Path | None,
    reviewer_dir: Path | None,
    reviewer_nonces_path: Path | None,
    cache: dict[str, Any],
) -> None:
    """Explicit --reveal-stage semantic|contract dispatch (SAN-881
    Phase-A correction). The semantic stage is a TWO-ARTIFACT
    verification event: author semantic labels + reviewer semantic
    labels, BOTH required, never a partial final ledger. The contract
    stage is a FOUR-artifact verification event: author contract labels,
    design metadata, coverage manifest, reviewer contract labels --
    mirrors LEDGER_PINNED_TUPLES' four "contract" entries exactly. Every
    artifact in the stage's subset is REQUIRED: an envelope omitting its
    artifact is a hard failure. Any artifact from the OTHER stage
    supplied anyway is hard-rejected.

    SAN-881 PASS-1 FINAL CLOSURE CORRECTION root repair -- STRICT
    TIER-1-BEFORE-ANY-NONCE-READ, THEN A SINGLE TIER-2 SNAPSHOT SET,
    THEN TIER 3:

    TIER 1, PATH GATE (metadata/location ONLY -- no file content is
    EVER opened here, no nonce file is EVER read, at this tier):
    bundle membership + type (exact name set, direct regular
    non-symlink files only) for BOTH `sealed_dir` and `reviewer_dir`
    (`_check_bundle_exact_membership`), and nonce-PATH rejection for
    BOTH `nonces_path` and `reviewer_nonces_path`
    (`_check_nonce_path_tier1`) -- lexically OR resolutely (realpath)
    inside the bundle it accompanies, a leaf symlink (regardless of
    target), non-regular, or unresolvable. `nonces_path` /
    `reviewer_nonces_path` are raw `Path` arguments (never a
    pre-loaded map) -- THIS function computes their Tier-1 location/type
    safety itself; `main()` no longer precomputes it. Every one of
    these four checks runs UNCONDITIONALLY (never short-circuited) so
    every safe diagnostic is still reported even when the stage will
    ultimately be gated shut. ANY single Tier-1 failure means the
    combined `path_gate_ok` is False and this function returns
    immediately: ZERO staged-payload reads, ZERO nonce-file reads (for
    EITHER nonce path, not merely the one that failed), ZERO schema
    validation, ZERO cryptographic verification.

    TIER 2, SNAPSHOT GATE: ONLY once every Tier-1 operand has passed,
    BOTH nonce files plus every subset-member artifact plus the
    reviewer commitment envelope are read EXACTLY ONCE each, through
    the SAME no-follow `_snapshot_regular_file` primitive Tier 0 (the
    fixed-component cache) uses -- 5 total custody-member opens for the
    semantic stage, 7 for the contract stage. Only AFTER this COMPLETE
    snapshot set exists does JSON parsing, nonce key/hex validation
    (`_check_nonce_map`), or schema validation
    (`check_stage_schema_validity`, itself schema-reopen-free -- it
    consumes `cache["schema"]`) begin. Any Tier-2 snapshot failure
    (missing/unreadable member -- including a TOCTOU race between the
    Tier-1 stat and the Tier-2 open) gates the WHOLE stage shut: zero
    parsing, zero schema validation, zero crypto for every OTHER member,
    even one that snapshotted cleanly.

    TIER 3, CRYPTO GATE: cryptographic subset verification runs ONLY
    when Tier 2 reports every snapshotted artifact valid (schema AND
    nonce-map shape) -- and consumes ONLY the exact Tier-2 snapshots (no
    second, path-based read)."""
    if stage not in REVEAL_STAGES:
        errors.add(f"--reveal-stage: rule={RULE_INVALID_REVEAL_STAGE}")
        return

    if stage == "semantic":
        subset_names = SEMANTIC_STAGE_ALLOWED
        forbidden = SEMANTIC_STAGE_FORBIDDEN_EXTRAS
        reviewer_commitment_file = REVIEWER_SEMANTIC_COMMITMENT_FILE
        reviewer_artifact_name = REVIEWER_SEMANTIC_ARTIFACT
        sealed_bundle_allowed = SEMANTIC_SEALED_BUNDLE_ALLOWED
        reviewer_bundle_allowed = SEMANTIC_REVIEWER_BUNDLE_ALLOWED
        author_nonce_keys = SEMANTIC_AUTHOR_NONCE_KEYS
        reviewer_nonce_keys = SEMANTIC_REVIEWER_NONCE_KEYS
    else:
        subset_names = CONTRACT_STAGE_ALLOWED
        forbidden = CONTRACT_STAGE_FORBIDDEN_EXTRAS
        reviewer_commitment_file = REVIEWER_CONTRACT_COMMITMENT_FILE
        reviewer_artifact_name = REVIEWER_CONTRACT_ARTIFACT
        sealed_bundle_allowed = CONTRACT_SEALED_BUNDLE_ALLOWED
        reviewer_bundle_allowed = CONTRACT_REVIEWER_BUNDLE_ALLOWED
        author_nonce_keys = CONTRACT_AUTHOR_NONCE_KEYS
        reviewer_nonce_keys = CONTRACT_REVIEWER_NONCE_KEYS

    # ============================= TIER 1: PATH GATE =============================
    # Every check below is presence/type/location-only. Each runs
    # unconditionally -- never short-circuited via `and` -- so every
    # independent safe diagnostic is still reported even when the stage
    # will ultimately be gated shut.
    sealed_ok = _check_bundle_exact_membership(errors, sealed_dir, sealed_bundle_allowed, "sealed-dir", forbidden)
    reviewer_ok = _check_bundle_exact_membership(errors, reviewer_dir, reviewer_bundle_allowed, "reviewer-dir", forbidden)
    nonces_path_ok = _check_nonce_path_tier1(errors, nonces_path, sealed_dir, "nonces-file")
    reviewer_nonces_path_ok = _check_nonce_path_tier1(errors, reviewer_nonces_path, reviewer_dir, "reviewer-nonces-file")

    path_gate_ok = sealed_ok and reviewer_ok and nonces_path_ok and reviewer_nonces_path_ok
    if not path_gate_ok:
        # ANY Tier-1 failure means ZERO staged-payload reads and ZERO
        # nonce-file reads -- for BOTH nonce paths, not merely the one
        # that failed: no schema-validation parse, no crypto bytes
        # gathering, no verify_reveal call.
        return

    # ============================= TIER 2: SNAPSHOT GATE =============================
    # Read each approved file, PLUS both nonce files, EXACTLY ONCE each
    # via the no-follow snapshot helper -- 5 total custody-member opens
    # for the semantic stage, 7 for the contract stage. PATH GATE having
    # passed guarantees sealed_dir/reviewer_dir are non-None, exist, and
    # contain EXACTLY the allowed regular, non-symlink files, and that
    # both nonce paths are non-None, non-symlink, regular files outside
    # their bundle -- so every path below is a legitimate,
    # already-verified-safe-to-open snapshot candidate.
    snapshots: dict[str, bytes] = {}
    for name in subset_names:
        base_dir = reviewer_dir if name == reviewer_artifact_name else sealed_dir
        data = _snapshot_regular_file(base_dir / name)
        if data is not None:
            snapshots[name] = data
        else:
            errors.add(f"{name}: rule={RULE_STAGED_IO_FAILURE}")
    env_data = _snapshot_regular_file(reviewer_dir / reviewer_commitment_file)
    if env_data is not None:
        snapshots[reviewer_commitment_file] = env_data
    else:
        errors.add(f"{reviewer_commitment_file}: rule={RULE_STAGED_IO_FAILURE}")

    nonces_data = _snapshot_regular_file(nonces_path)
    if nonces_data is None:
        errors.add(f"nonces-file: rule={RULE_STAGED_IO_FAILURE}")
    reviewer_nonces_data = _snapshot_regular_file(reviewer_nonces_path)
    if reviewer_nonces_data is None:
        errors.add(f"reviewer-nonces-file: rule={RULE_STAGED_IO_FAILURE}")

    # COMPLETE snapshot set required (5/7, each opened once) BEFORE any
    # parsing, nonce key/hex validation, or schema validation begins.
    snapshot_complete = (
        len(snapshots) == len(subset_names) + 1
        and nonces_data is not None and reviewer_nonces_data is not None
    )
    if not snapshot_complete:
        return

    nonces_json, nonces_parse_ok = _parse_json_bytes(errors, nonces_data, "nonces-file")
    nonces_ok = nonces_parse_ok and _check_nonce_map(errors, nonces_json, author_nonce_keys, "nonces-file")
    reviewer_nonces_json, reviewer_nonces_parse_ok = _parse_json_bytes(errors, reviewer_nonces_data, "reviewer-nonces-file")
    reviewer_nonces_ok = reviewer_nonces_parse_ok and _check_nonce_map(errors, reviewer_nonces_json, reviewer_nonce_keys, "reviewer-nonces-file")

    expected_ctx_hash_hex = commitment.get("labeling_context_hash") if isinstance(commitment, dict) else None
    schema_ok, parsed = check_stage_schema_validity(
        errors, stage, subset_names, reviewer_artifact_name, reviewer_commitment_file,
        snapshots, expected_ctx_hash_hex, cache)

    # ============================= TIER 3: CRYPTO GATE =============================
    if not (nonces_ok and reviewer_nonces_ok and schema_ok):
        # Malformed/mismatched nonce maps, or malformed/schema-invalid/
        # context-inconsistent content, incurred their one Tier-2 read
        # above; ZERO crypto calls follow.
        return

    # A single merged pseudo-commitment combining the author envelope's
    # multi-artifact commitments with the relevant reviewer envelope's
    # single artifact commitment, so _reveal_verify_subset_fixed_codes
    # can resolve entries for BOTH sides under one call. Missing
    # reviewer artifacts FAIL here too (never skip): if the reviewer
    # envelope never declared an artifact_commitment,
    # merged["artifact_commitment"] is simply never set, and
    # _reveal_verify_subset_fixed_codes's own "not supplied" branch
    # fires for the reviewer artifact name.
    merged: dict[str, Any] = {
        "labeling_context_hash": commitment.get("labeling_context_hash") if isinstance(commitment, dict) else None,
        "author_commitments": commitment.get("author_commitments", []) if isinstance(commitment, dict) else [],
    }
    rev_env = parsed.get(reviewer_commitment_file)
    if isinstance(rev_env, dict):
        merged["artifact_commitment"] = rev_env.get("artifact_commitment")

    merged_nonces: dict[str, str] = dict(nonces_json) if isinstance(nonces_json, dict) else {}
    if isinstance(reviewer_nonces_json, dict):
        merged_nonces.update(reviewer_nonces_json)

    # CRYPTO GATE consumes ONLY the exact TIER 2 snapshots -- no second,
    # path-based read. Scoped to `subset_names` (excludes the reviewer
    # commitment ENVELOPE snapshot itself, which SNAPSHOT GATE also reads
    # for schema/context-consistency purposes but which is never one of
    # the subset's own ARTIFACT names).
    artifact_snapshots = {name: data for name, data in snapshots.items() if name in subset_names}
    _reveal_verify_subset_fixed_codes(errors, merged, subset_names, forbidden, artifact_snapshots, merged_nonces)


# ---------------------------------------------------------------------
# Reveal-verification ledger (canonical; consumed by FREEZE-MANIFEST.json)
# ---------------------------------------------------------------------

def build_reveal_verification_ledger(corpus_version: int, ctx_hash_hex: str, entries: list[dict]) -> dict:
    """entries: [{artifact_name, envelope, commitment_hex, verified_stage, byte_length}, ...],
    in ANY caller-supplied order. Ordering is PINNED (SAN-881 Phase-A
    correction item 2): this builder EMITS LEDGER_CANONICAL_ORDER
    directly -- it does NOT sort by (envelope, artifact_name) (that was
    the pre-correction behavior, and produced a DIFFERENT order than the
    pinned canonical sequence). Each canonical position is resolved by
    an exact (artifact_name, envelope, verified_stage) tuple lookup
    against the caller-supplied entries; reversing or otherwise
    permuting the INPUT list has NO effect on the output order. A
    caller-supplied entry whose tuple is not one of the six canonical
    tuples is simply not emitted -- the caller is expected to supply
    exactly the six pinned entries."""
    by_tuple = {(e["artifact_name"], e["envelope"], e["verified_stage"]): e for e in entries}
    ledger_entries = []
    for artifact_name, envelope, verified_stage in LEDGER_CANONICAL_ORDER:
        e = by_tuple.get((artifact_name, envelope, verified_stage))
        if e is None:
            continue
        ledger_entries.append({
            "artifact_name": e["artifact_name"],
            "envelope": e["envelope"],
            "commitment_hex": e["commitment_hex"],
            "verified": True,
            "verified_stage": e["verified_stage"],
            "byte_length": e["byte_length"],
        })
    return {
        "corpus_version": corpus_version,
        "labeling_context_hash": ctx_hash_hex,
        "entries": ledger_entries,
    }


def canonical_ledger_bytes(ledger: dict) -> bytes:
    return _canonical_json_bytes(ledger)


def check_reveal_verification_ledger(
    errors: Errors,
    ledger: dict,
    author_commitment: dict | None,
    reviewer_semantic_envelope: dict | None,
    reviewer_contract_envelope: dict | None,
) -> None:
    """Cross-checks reveal_verification_ledger.json against the pinned
    six-tuple set (LEDGER_PINNED_TUPLES) AND against the author/reviewer
    commitment envelopes: every entry's artifact_name, envelope,
    verified_stage, commitment_hex, byte_length, context hash, and
    corpus_version must agree with whichever envelope declared that
    artifact's commitment. An empty, short, misordered, or
    tuple-mismatched ledger fails outright (checked first, before any
    cross-check); `verified: true` and `verified_stage` enum membership
    are schema-level checks (reveal_verification_ledger_schema.json),
    not repeated here."""
    entries = ledger.get("entries", [])
    actual_tuples = {(e.get("artifact_name"), e.get("envelope"), e.get("verified_stage")) for e in entries}
    if actual_tuples != LEDGER_PINNED_TUPLES:
        errors.add(f"reveal_verification_ledger.json: rule={RULE_LEDGER_TUPLE_SET_MISMATCH}")
        return

    actual_order = tuple((e.get("artifact_name"), e.get("envelope"), e.get("verified_stage")) for e in entries)
    if actual_order != LEDGER_CANONICAL_ORDER:
        # The tuple SET is correct (checked above) but the ORDER is not
        # the pinned canonical sequence -- reversal or any other
        # permutation fails outright, before any per-entry cross-check
        # (SAN-881 Phase-A correction item 2; README.md's own "misordered"
        # ledger rule).
        errors.add(f"reveal_verification_ledger.json: rule={RULE_LEDGER_ORDER_MISMATCH}")
        return

    ledger_ctx_hash = ledger.get("labeling_context_hash")
    ledger_corpus_version = ledger.get("corpus_version")
    envelopes_by_kind = {
        "author": author_commitment,
        "reviewer_semantic": reviewer_semantic_envelope,
        "reviewer_contract": reviewer_contract_envelope,
    }
    for entry in entries:
        name = entry.get("artifact_name")
        envelope = envelopes_by_kind.get(entry.get("envelope"))
        if envelope is None:
            errors.add(f"reveal_verification_ledger.json[{name}]: rule={RULE_LEDGER_CROSS_CHECK_MISMATCH}")
            continue
        if envelope.get("labeling_context_hash") != ledger_ctx_hash:
            errors.add(f"reveal_verification_ledger.json[{name}]: rule={RULE_LEDGER_CROSS_CHECK_MISMATCH}")
        if envelope.get("corpus_version") != ledger_corpus_version:
            errors.add(f"reveal_verification_ledger.json[{name}]: rule={RULE_LEDGER_CROSS_CHECK_MISMATCH}")

        if entry.get("envelope") == "author":
            commitments = envelope.get("author_commitments", [])
        else:
            commitments = [envelope["artifact_commitment"]] if envelope.get("artifact_commitment") else []
        matching = next((c for c in commitments if c and c.get("artifact_name") == name), None)
        if matching is None:
            errors.add(f"reveal_verification_ledger.json[{name}]: rule={RULE_LEDGER_CROSS_CHECK_MISMATCH}")
            continue
        if matching.get("commitment_hex") != entry.get("commitment_hex"):
            errors.add(f"reveal_verification_ledger.json[{name}]: rule={RULE_LEDGER_CROSS_CHECK_MISMATCH}")
        if matching.get("byte_length") != entry.get("byte_length"):
            errors.add(f"reveal_verification_ledger.json[{name}]: rule={RULE_LEDGER_CROSS_CHECK_MISMATCH}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sealed-dir", type=Path, default=None,
                         help="local directory containing design_metadata.json, labels_author_*.json, coverage_manifest.json (never committed)")
    parser.add_argument("--nonces-file", type=Path, default=None,
                         help="local JSON {artifact_name: hex_nonce} for reveal verification (never committed)")
    parser.add_argument("--reviewer-dir", type=Path, default=None,
                         help="local directory containing reviewer semantic/contract label files + their .commitment.json envelopes (never committed)")
    parser.add_argument("--reviewer-nonces-file", type=Path, default=None,
                         help="local JSON {artifact_name: hex_nonce} for reviewer reveal verification (never committed)")
    parser.add_argument("--reveal-stage", choices=list(REVEAL_STAGES), default=None,
                         help="explicit reveal-verification stage (workflow steps 5/6): "
                              "'semantic' verifies ONLY author+reviewer semantic labels "
                              "(two-artifact event; contract/design/coverage extras hard-rejected); "
                              "'contract' verifies author contract labels, design metadata, "
                              "coverage manifest, and reviewer contract labels "
                              "(four-artifact event; semantic extras hard-rejected). "
                              "Requires --sealed-dir, --nonces-file, --reviewer-dir, and "
                              "--reviewer-nonces-file, each pointing at a bundle whose "
                              "directory contents are EXACTLY the stage's pinned artifact "
                              "set. This is the SOLE cryptographic reveal path -- "
                              "--nonces-file / --reviewer-dir / --reviewer-nonces-file are "
                              "REJECTED outright (fixed diagnostic, never a silent no-op) "
                              "whenever supplied WITHOUT --reveal-stage.")
    args = parser.parse_args(argv)

    errors = Errors()

    # SAN-881 PASS-1 FINAL CLOSURE CORRECTION: the Tier-0 SINGLE-SOURCE
    # cache is built EXACTLY ONCE, HERE, unconditionally -- every one of
    # corpus_inputs.json, evaluation_profile.json, the six schema files,
    # the algorithm doc, and the tables doc is read ONCE, through the
    # SAME no-follow custody-read primitive (`_snapshot_regular_file`)
    # the staged reveal pipeline's Tier 2 uses. schemas_self_valid_ok,
    # corpus/profile validation, check_commitment's context-hash
    # recomputation + declared-component comparison,
    # check_stage_schema_validity's per-artifact schema lookups, and the
    # bare --sealed-dir structural-validation block's tables_data /
    # schema consumers all draw from THIS SAME cache -- none of them
    # independently re-reads a fixed component from disk.
    cache = _load_fixed_components_cache(errors, HERE, REPO_ROOT)

    # SAN-881 PASS-1 CLOSURE PATCH: `schemas_self_valid_ok` is the OUTER-GATE
    # operand check_schemas_self_valid now returns (belt to the check
    # itself, already unconditional here).
    schemas_self_valid_ok = check_schemas_self_valid(errors, cache)

    # SAN-881 PASS-1 FINAL CLOSURE CORRECTION: corpus/profile now come
    # from the cache instead of an independent, UNGUARDED load_json call
    # -- a missing/malformed corpus_inputs.json or evaluation_profile.json
    # previously raised an uncaught FileNotFoundError/JSONDecodeError
    # straight out of main() (the cache's own RULE_CONTEXT_COMPONENT_UNREADABLE
    # diagnostic, added above, is what now reports it); structural
    # checks below simply do not run over a component the cache could
    # not produce.
    corpus = cache["corpus"]
    corpus_by_id: dict = {}
    _corpus_check_delta_zero = False
    if corpus is not None:
        if not isinstance(corpus, list) or len(corpus) != 160:
            errors.add(f"corpus_inputs.json: rule={RULE_ITEM_COUNT}")
        if isinstance(corpus, list):
            _errcount_before_corpus_inputs = len(errors)
            corpus_by_id = check_corpus_inputs(errors, corpus)
            _corpus_check_delta_zero = len(errors) == _errcount_before_corpus_inputs

    # SAN-881 PASS 2B.1-P-GATE: `corpus_prereq_ok` is an EXPLICIT, LOCAL
    # prerequisite boolean -- one of the six operands the coverage
    # block below conjoins into `upstream_ok` (fix 1 of this pass: MAKE
    # PASS A A REAL GATE, PART 2 -- the PASS 2B.1-P-FIX gate combined
    # only coverage-schema and coverage-registry-closure validity,
    # which still let an invalid corpus (or an invalid design, see
    # below) reach Pass B/build_product_trace_bundle, because neither
    # was ever consulted). Corpus present, list-shaped, exactly 160
    # items, AND check_corpus_inputs added zero errors of its own --
    # never derived from global `not errors`.
    corpus_prereq_ok = (
        corpus is not None and isinstance(corpus, list)
        and len(corpus) == 160 and _corpus_check_delta_zero
    )

    profile = cache["profile"]
    if profile is not None:
        check_evaluation_profile(errors, profile)

    # SAN-881 PASS-1 CLOSURE PATCH (closure 1, safe-parse commitment.json):
    # commitment.json is READ and PARSED defensively -- a missing file is
    # unchanged prior behavior (commitment stays None, no error here; the
    # --reveal-stage dispatch below reports it specifically). An EXISTING
    # but unreadable (any OSError) or malformed-JSON commitment.json now
    # fails with a single fixed RULE_COMMITMENT_UNREADABLE diagnostic
    # instead of an uncaught OSError/json.JSONDecodeError -- and
    # commitment_json_ok=False means every downstream check below (which
    # all require a successfully-parsed `commitment`) is skipped, exactly
    # like the pre-existing "file missing" case.
    commitment_path = HERE / "commitment.json"
    commitment = None
    commitment_read_ok = False
    commitment_json_ok = False
    if commitment_path.exists():
        try:
            commitment_raw = commitment_path.read_bytes()
            commitment_read_ok = True
        except OSError:
            errors.add(f"commitment.json: rule={RULE_COMMITMENT_UNREADABLE}")
        if commitment_read_ok:
            try:
                commitment = json.loads(commitment_raw.decode("utf-8"))
                commitment_json_ok = True
            except (UnicodeDecodeError, ValueError):
                errors.add(f"commitment.json: rule={RULE_COMMITMENT_UNREADABLE}")

    # SAN-881 PASS-1 CLOSURE PATCH (closure 2, author validity
    # conjunction): every operand below is computed SAFELY (no exceptions
    # escape) BEFORE they are combined into author_gate_ok. fixed_components_ok
    # covers READABILITY/PARSING/SCHEMA-SELF-VALIDITY of every fixed
    # labeling-context component -- this is what makes it safe to call
    # check_commitment (which recomputes the hash from those same
    # components) at all. commitment_structural_ok / commitment_disk_context_ok /
    # commitment_declared_components_ok are the three operands
    # check_commitment now returns. commitment_schema_valid and
    # commitment_order_ok remain the pre-existing SPECIFIC authorEnvelope
    # schema check and the pinned author_commitments order check.
    #
    # SAN-881 PASS-1 FINAL CLOSURE CORRECTION: fixed_components_ok is
    # simply the cache's own `ok` -- computed UNCONDITIONALLY above
    # (before commitment.json is even read), not gated on
    # commitment_json_ok, so a broken fixed component is always reported
    # even alongside an ALSO-broken commitment.json.
    #
    # SAN-881 PASS-1 CORRECTION ROUND, Section B: whether commitment.json
    # validates SPECIFICALLY as the authorEnvelope shape (envelope_kind
    # AUTHOR) -- computed here so `--reveal-stage` dispatch below can gate
    # on it, but the ERROR is still appended in the SAME relative
    # position as before (after check_commitment / check_author_commitment_order)
    # so the pinned v1-transitional four-line output is byte-for-byte
    # unchanged. check_commitment and check_author_commitment_order are
    # both shape-safe accessors (never raise on a malformed envelope) and
    # run regardless of schema validity -- "semantic checks continue only
    # through shape-safe accessors" even when the envelope is
    # schema-invalid.
    fixed_components_ok = cache["ok"]
    commitment_structural_ok = False
    commitment_disk_context_ok = False
    commitment_declared_components_ok = False
    commitment_order_ok = False
    commitment_schema_valid = False
    if commitment_json_ok:
        commitment_gate = check_commitment(errors, commitment, cal_dir=HERE, repo_root=REPO_ROOT, cache=cache)
        commitment_structural_ok = commitment_gate["structural_ok"]
        commitment_disk_context_ok = commitment_gate["disk_context_ok"]
        commitment_declared_components_ok = commitment_gate["declared_components_ok"]
        commitment_order_ok = check_author_commitment_order(errors, commitment)
        commitment_schema = cache["schema"].get("commitment_schema.json")
        if Draft202012Validator is not None and commitment_schema is not None:
            # SPECIFICALLY the authorEnvelope branch (envelope_kind
            # AUTHOR) -- not merely the root oneOf, which would let a
            # schema-valid REVIEWER envelope substituted as commitment.json
            # pass merely because it matches a DIFFERENT branch.
            commitment_schema_valid = _validate_specific(errors, "commitment.json", commitment_schema, "authorEnvelope", commitment)

    # THE PINNED OUTER GATE: every crypto/nonce/snapshot read this module
    # performs on the author side is preceded by author_gate_ok being
    # True. A false operand means ZERO nonce-file loads, ZERO staged
    # snapshots, ZERO crypto -- see the --reveal-stage dispatch below,
    # the SOLE path that reads this conjunction. (SAN-881 PASS-1 FINAL
    # CLOSURE CORRECTION: the legacy generic per-envelope reveal-
    # verification code path -- the one that used to ALSO gate on this
    # conjunction -- has been removed entirely; see
    # RULE_REVEAL_STAGE_REQUIRED below. SAN-881 PASS-1 FINAL BLOCKER
    # CORRECTION: stale-comment fix -- the bare --sealed-dir branch that
    # remains below is STRUCTURAL ONLY [design/labels/coverage schema +
    # consistency checks over already-authored bytes]; it never reads
    # author_gate_ok and performs zero crypto. --reveal-stage is the SOLE
    # cryptographic reveal path in this module.)
    author_gate_ok = (
        commitment_read_ok and commitment_json_ok and fixed_components_ok
        and schemas_self_valid_ok and commitment_schema_valid and commitment_structural_ok
        and commitment_order_ok and commitment_disk_context_ok and commitment_declared_components_ok
    )

    tables_data = cache["tables"]

    if args.reveal_stage is not None:
        # Explicit reveal-stage dispatch (SAN-881 Phase-A correction):
        # a two-artifact (semantic) or four-artifact (contract)
        # verification event, subset-enforced, exact-bundle-enforced,
        # and forbidden-extra hard-rejecting -- see
        # run_stage_reveal_verification. DISPATCH ORDER: this branch is
        # mutually exclusive with BOTH the generic --sealed-dir design/
        # labels/coverage block AND the legacy --reviewer-dir block
        # below (the `else` branch) -- a staged invocation NEVER enters
        # either generic path, so it can never crash probing for
        # artifacts (e.g. design_metadata.json) that a semantic-only
        # bundle never contains.
        if commitment is None:
            errors.add(f"--reveal-stage {args.reveal_stage}: rule={RULE_REVEAL_NOT_SUPPLIED} (commitment.json missing or malformed)")
        elif not author_gate_ok:
            # SAN-881 PASS-1 CLOSURE PATCH (closure 2): staged
            # cryptographic processing must NOT begin unless EVERY
            # author_gate_ok operand is True -- not merely
            # commitment_schema_valid. commitment.json's own per-operand
            # diagnostic(s) were already appended above by whichever
            # check(s) failed (CORPUS_VERSION / COMMITMENT_ARTIFACT_SET /
            # CONTEXT_HASH_MISMATCH / SCHEMA_INVALID / ORDER_MISMATCH /
            # a CONTEXT_COMPONENT_UNREADABLE-per-component set); this is
            # the fixed, dispatch-specific diagnostic proving crypto was
            # never entered for this stage.
            errors.add(f"--reveal-stage {args.reveal_stage}: rule={RULE_AUTHOR_GATE_NOT_OK} (author envelope validity gate not satisfied)")
        else:
            # SAN-881 PASS-1 FINAL CLOSURE CORRECTION: nonce-file
            # location/type safety (Tier 1) and the actual nonce-file
            # READ (Tier 2) both now live INSIDE run_stage_reveal_verification
            # -- main() passes the raw `Path` arguments straight through
            # (never a pre-loaded map, never a precomputed location
            # boolean); "Tier 1 strictly before any nonce read" is an
            # invariant of that function's own internal ordering, not
            # something main() has to reconstruct.
            run_stage_reveal_verification(
                errors, commitment, args.reveal_stage,
                args.sealed_dir, args.nonces_file, args.reviewer_dir, args.reviewer_nonces_file,
                cache)
    else:
        # SAN-881 PASS-1 FINAL CLOSURE CORRECTION: the legacy generic
        # per-envelope --reviewer-dir reveal path -- and its opt-in flag --
        # is REMOVED entirely -- the staged gated pipeline
        # (--reveal-stage) is now the SOLE crypto path. Any nonce/
        # reviewer argument supplied WITHOUT --reveal-stage is a fixed-
        # diagnostic reject, never a silent no-op: bare --sealed-dir
        # STRUCTURAL author validation (the documented pre-sealing
        # workflow, below) is the only thing this branch still performs.
        # SAN-881 PASS-1 CORRECTION: the fixed-diagnostic reject above
        # must SKIP the structural --sealed-dir branch entirely -- a
        # nonce/reviewer argument supplied without --reveal-stage,
        # together with an EXISTING (possibly incomplete, since it was
        # never meant to be read this way) --sealed-dir, previously fell
        # through into the generic block below anyway, which
        # unconditionally probed for design_metadata.json /
        # labels_author_semantic.json / labels_author_contract.json and
        # raised an uncaught, absolute-path-disclosing FileNotFoundError
        # the first time one was missing. The reject above is now a hard
        # `return`-equivalent guard: no nonce/reviewer arg means this
        # structural branch never even attempts a sealed-dir read this
        # invocation.
        no_stage_reject = (
            args.nonces_file is not None or args.reviewer_dir is not None or args.reviewer_nonces_file is not None
        )
        if no_stage_reject:
            errors.add(f"--reveal-stage: rule={RULE_REVEAL_STAGE_REQUIRED}")
        else:
            design_by_id: dict = {}
            design_schema_ok = False
            design_semantics_ok = False
            if args.sealed_dir and args.sealed_dir.exists():
                design = load_json(args.sealed_dir / "design_metadata.json")
                design_schema = cache["schema"].get("design_metadata_schema.json")
                # SAN-881 PASS 2B.1-P-GATE: `design_schema_ok` /
                # `design_semantics_ok` are two more of the six explicit
                # upstream_ok operands (fix 1, PART 2). `design_schema_ok`
                # requires the schema validation to actually RUN (not
                # merely "zero errors", which was vacuously true whenever
                # Draft202012Validator or the schema itself was
                # unavailable -- see coverage_runtime_available below for
                # the analogous fix on the coverage side).
                _design_schema_ran = Draft202012Validator is not None and design_schema is not None
                _errcount_before_design_schema = len(errors)
                if _design_schema_ran:
                    _validate_against_schema(errors, "design_metadata.json", design_schema, design)
                design_schema_ok = _design_schema_ran and len(errors) == _errcount_before_design_schema

                _errcount_before_design_semantics = len(errors)
                design_by_id = check_design_metadata(errors, design, corpus_by_id)
                design_semantics_ok = len(errors) == _errcount_before_design_semantics

                semantic = load_json(args.sealed_dir / "labels_author_semantic.json")
                contract = load_json(args.sealed_dir / "labels_author_contract.json")
                labels_schema = cache["schema"].get("labels_schema.json")
                if Draft202012Validator is not None and labels_schema is not None:
                    _validate_against_schema(errors, "labels_author_semantic.json", labels_schema, semantic)
                    _validate_against_schema(errors, "labels_author_contract.json", labels_schema, contract)
                semantic_by_key, _contract_by_key = check_labels(errors, semantic, contract, design_by_id)

                # SAN-881 PASS 2B.2-FIX defect 2: DOD semantic checks
                # (check_dod_balance_and_pairs -> check_introduced_feature_
                # absent_from_tables et al.) previously ran UNCONDITIONALLY,
                # even after design-schema validation had already failed --
                # a schema-invalid introduced_feature (e.g. a malformed
                # pair member, or a null lexical surface token) could reach
                # fold_sequence(" ".join(...)) and raise an uncaught
                # TypeError straight out of main(argv). `dod_inputs_ok` is
                # an explicit, LOCAL prerequisite boolean -- table data
                # available, corpus valid, design genuinely schema- AND
                # semantics-valid -- never derived from global `not
                # errors` or any other gate's own state.
                dod_inputs_ok = (
                    isinstance(tables_data, dict)
                    and corpus_prereq_ok
                    and design_schema_ok
                    and design_semantics_ok
                )
                if dod_inputs_ok:
                    check_dod_balance_and_pairs(errors, design_by_id, semantic_by_key, corpus_by_id, tables_data)

                coverage_path = args.sealed_dir / "coverage_manifest.json"
                if coverage_path.exists():
                    coverage = load_json(coverage_path)
                    cov_schema = cache["schema"].get("coverage_manifest_schema.json")
                    # SAN-881 PASS 2B.1-P-FIX fix 1: MAKE PASS A A REAL
                    # GATE. Upstream coverage-SCHEMA validity and
                    # REGISTRY-CLOSURE validity are each captured as
                    # their own before/after error-count deltas -- both
                    # checks still run UNCONDITIONALLY and still
                    # accumulate their own deterministic errors into
                    # `errors` exactly as before -- but their combined
                    # result now GATES whether check_coverage_manifest's
                    # Pass B (trace construction, via
                    # build_product_trace_bundle) may run at all.
                    # Previously an upstream schema-invalid or
                    # closure-invalid manifest (e.g. a manifest missing a
                    # registered surface, or carrying an extra undeclared
                    # one) could still reach Pass B, because
                    # check_coverage_manifest's OWN internal Pass A only
                    # inspects the KEYS ACTUALLY PRESENT in the manifest
                    # dict and has no way to notice a MISSING key, and
                    # silently skips position-checking an EXTRA
                    # undeclared key (registry_entry is None) -- neither
                    # case added a pass_a_errors entry, so Pass B ran
                    # regardless. See
                    # test_main_schema_invalid_coverage_manifest_never_builds_a_bundle
                    # and
                    # test_main_closure_invalid_coverage_manifest_never_builds_a_bundle.
                    #
                    # SAN-881 PASS 2B.1-P-GATE: `coverage_upstream_ok`
                    # (renamed `upstream_ok` below, PASS-2B.1-P-FIX's
                    # gate) combined ONLY these last two operands --
                    # coverage-schema and coverage-registry-closure
                    # validity -- leaving corpus/design prerequisites (or
                    # an UNAVAILABLE schema validator, which silently made
                    # `coverage_schema_ok` vacuously True whenever the
                    # `if Draft202012Validator is not None and cov_schema
                    # is not None:` guard below never even ran) free to
                    # still permit trace construction. `upstream_ok` is
                    # now the conjunction of ALL SIX explicit, LOCAL
                    # prerequisite booleans actually required to
                    # construct and validate coverage products:
                    # `coverage_runtime_available` (below),
                    # `corpus_prereq_ok` (top of main()),
                    # `design_schema_ok` / `design_semantics_ok` (above),
                    # and `coverage_schema_ok` / `coverage_closure_ok`
                    # (this block) -- never derived from global `not
                    # errors`, `fixed_components_ok`,
                    # `schemas_self_valid_ok`, commitment validity,
                    # labels, DOD checks, evaluation-profile validity, or
                    # reveal diagnostics, none of which are inputs to
                    # constructing a coverage product.
                    coverage_runtime_available = (
                        Draft202012Validator is not None
                        and isinstance(tables_data, dict)
                        and cache["schema"].get("design_metadata_schema.json") is not None
                        and cache["schema"].get("coverage_manifest_schema.json") is not None
                    )

                    _cov_schema_ran = Draft202012Validator is not None and cov_schema is not None
                    _errcount_before_schema = len(errors)
                    if _cov_schema_ran:
                        _validate_against_schema(errors, "coverage_manifest.json", cov_schema, coverage)
                    coverage_schema_ok = _cov_schema_ran and len(errors) == _errcount_before_schema

                    _errcount_before_closure = len(errors)
                    check_coverage_registry_closure(errors, coverage)
                    coverage_closure_ok = len(errors) == _errcount_before_closure

                    coverage_upstream_ok = (
                        coverage_runtime_available
                        and corpus_prereq_ok
                        and design_schema_ok
                        and design_semantics_ok
                        and coverage_schema_ok
                        and coverage_closure_ok
                    )
                    check_coverage_manifest(
                        errors, coverage, design_by_id, corpus_by_id, tables_data,
                        upstream_ok=coverage_upstream_ok,
                    )

    if errors:
        sys.stderr.write(f"VALIDATION FAILED: {len(errors)} error(s)\n")
        for e in errors:
            sys.stderr.write(f"  - {e}\n")
        return 1

    sys.stdout.write("VALIDATION OK: all checks passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
