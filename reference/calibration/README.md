# SAN-881 C1-C4 Calibration Corpus (Phase A)

Calibration infrastructure for measuring C1-C4 detector competence
against a purposive, synthetic, tier_1-only corpus. This directory is
built in two phases under separate authorization:

- **Phase A (this commit)**: authors the corpus, the commit/reveal
  sealing scheme, and the measurement infrastructure. Phase A never
  runs a full `evaluate()` pass (Python or TypeScript) over any corpus
  item and never records, publishes, or gates on an evaluator outcome.
  SAN-881 PASS 2B.1-T: `validate_design.py` implements an ephemeral,
  typed, validator-local product-trace substrate over public corpus
  text (see "No-evaluator-before-freeze rule" below) -- it is not yet
  invoked by the coverage-manifest check, never publishes trace data or
  outcomes, and never computes rates or gates.
- **Phase B (future, separate authorization)**: runs `measure.py` and
  `benchmark.py` for real, once `labels_frozen.json` and
  `FREEZE-MANIFEST.json` exist.

Scope: **C1-C4 only**. No C_COV, no C5, no provenance/wrapper
measurement (see `reference/spec/ALGORITHM-v4-c1c5-reference.md`
section 0 for the slice boundary this corpus stays inside).

## Files in this directory

Public (this commit):

- `corpus_inputs.json` -- 160 items (`cal:000`..`cal:159`), each
  `{id, context|context_sources, output}`. TIER_1 ONLY.
- `evaluation_profile.json` -- binds the evaluator invocation contract,
  the pinned spec hashes, and the expected C1-C4 identities.
- `commitment.json` -- the commit/reveal envelope: `labeling_context_hash`,
  its component list, and the four author-artifact commitments.
- `measure.py` -- the Phase-B execution contract (never run in Phase A).
- `benchmark.py` -- the Phase-B Python-only timing harness (never run in
  Phase A).
- `validate_design.py` -- structural + cryptographic validator; the only
  script in this directory that is actually run in Phase A.
- `schemas/` -- SIX JSON Schemas covering design metadata, labels
  (semantic-only / contract-only / merged-frozen, whole-file forms),
  the coverage manifest, the discriminated author/reviewer commitment
  envelope, the freeze manifest, and the reveal-verification ledger.
  `design_metadata.json`'s `items` and each labels whole-file form
  (`labels_author_semantic.json`, `labels_author_contract.json`,
  `labels_frozen.json`) are pinned SCHEMA-LEVEL (not merely
  validator-level) to EXACTLY 160 and EXACTLY 640 records respectively,
  independently per form (SAN-881 Phase-A CORRECTION PASS 1).

Sealed (private; staged under a directory OUTSIDE this repo during
authoring; never committed, never printed, never logged):

- `design_metadata.json`, `labels_author_semantic.json`,
  `labels_author_contract.json`, `coverage_manifest.json`, `nonces.json`.

Future artifacts (Phase B; not present after this commit):

- `labels_reviewer_semantic.commitment.json`,
  `labels_reviewer_contract.commitment.json` -- reviewer commitment
  envelopes (filenames pinned now, in `commitment.json`; validated ONLY
  as part of the staged `--reveal-stage` pipeline together with
  `--reviewer-dir` -- SAN-881 PASS-1 FINAL CLOSURE CORRECTION removed
  the legacy generic per-envelope `--reviewer-dir` mode entirely; see
  "`--reveal-stage` is the SOLE cryptographic reveal path" below).
- `labels_frozen.json` -- the merged, adjudicated label set (schema:
  `schemas/labels_schema.json`, `mergedFrozenRecord` whole-file form).
- `adjudication_log.json` -- the operator's disagreement-resolution log.
- `reveal_verification_ledger.json` -- the canonical record of which
  sealed envelopes were revealed and verified, and at which stage
  (schema: `schemas/reveal_verification_ledger_schema.json`).
- `FREEZE-MANIFEST.json` -- the raw-SHA-256 binding `measure.py` refuses
  to run without (schema: `schemas/freeze_manifest_schema.json`),
  including the five provenance fields (`labeling_context_hash`,
  `author_commitment_sha256`, `reviewer_semantic_commitment_sha256`,
  `reviewer_contract_commitment_sha256`, `reveal_verification_ledger_sha256`).
- `results/<freeze_manifest_sha256>/outcomes.json`,
  `results/<freeze_manifest_sha256>/rates.json`,
  `results/<freeze_manifest_sha256>/RATES-REPORT.md` -- `measure.py`
  output, hash-addressed by the freeze manifest that produced them.
- `results/<freeze_manifest_sha256>/benchmark.json` -- `benchmark.py`
  output, under the same hash-addressed directory.

## Custody workflow

The sealed staging directory (and, at the SAN-881 Phase-A correction
point, a fresh `-v2` sealed staging directory + a fresh `-v2` Sol export
directory) live OUTSIDE this repository under operator custody. After
each authoring/correction pass completes, the staging directory for
that pass AND the session transcript that produced it join the
operator-custody set BEFORE blind labeling begins -- no agent retains or
re-derives sealed content past that point (workflow step 2 below).

## The commit/reveal + staged-adjudication workflow

1. **Author seals.** The author writes the four sealed artifacts, runs
   `validate_design.py --sealed-dir <path>` privately until green
   (whole-file schema validation, feature-absence + minimal-pair
   semantic-equivalence checks, executable coverage predicates, no-leak
   error output), then computes `commitment.json`: an AUTHOR envelope
   (`envelope_kind: "AUTHOR"`) with a `labeling_context_hash` binding
   the base commit SHA and every public artifact this corpus depends on
   (corpus, evaluation profile, all SIX schemas, both pinned spec
   files), and a domain-separated SHA-256 commitment per sealed artifact
   using a fresh 32-byte nonce. `validate_design.py` recomputes this
   hash FROM DISK on every run (normal validation and every reveal
   path) -- the envelope's own `labeling_context_components` list is
   descriptive metadata only and is never trusted as an input. The v2
   `labeling_context_components` shape (SAN-881 Phase-A CORRECTION PASS
   1, an INTENTIONAL formula change from v1) is an exact, ordered list
   of ELEVEN structured `{name, sha256}` entries -- `base_commit_sha`,
   `corpus_inputs.json`, `evaluation_profile.json`, the six schema files,
   `algorithm`, `tables` -- pinned index-by-index in
   `commitment_schema.json`. EVERY component, including
   `base_commit_sha`, is individually SHA-256'd first; the outer
   `labeling_context_hash` is `SHA256` of the concatenation of the eleven
   raw 32-byte digests, in that exact order (v1 concatenated
   `base_commit_sha`'s raw ASCII bytes directly, unhashed, ahead of the
   other components' digests -- v2 is uniform, and the two formulas can
   never agree on the same inputs). `commitment.json`'s
   `author_commitments` array is likewise pinned to an exact four-entry
   order -- `design_metadata.json`, `labels_author_semantic.json`,
   `labels_author_contract.json`, `coverage_manifest.json` -- index-by-
   index in `commitment_schema.json`, with `validate_design.check_author_commitment_order`
   as a verifier-side belt to that schema-level pin.
2. **Operator custody transfer.** The operator takes custody of the
   sealed staging directory (the four sealed artifacts + `nonces.json`)
   and **removes it from every agent-readable path on this machine**
   before reviewer labeling begins. This is a manual, out-of-band step;
   no agent should retain or re-derive sealed content after this point.
3. **Fresh no-history reviewer task.** A reviewer -- a fresh task with
   NO access to this session's history, the sealed staging directory, or
   any design/contract reasoning -- receives only the Sol export
   (`corpus_inputs.json`, `evaluation_profile.json`, the six schemas,
   copies of the two pinned spec artifacts, `export_manifest.json`) and
   independently labels the corpus.
4. **Reviewer commits semantic labels, then separately commits contract
   labels.** Same commitment scheme, same `labeling_context_hash`, each
   as its own single-artifact REVIEWER_SEMANTIC / REVIEWER_CONTRACT
   envelope, filenames pinned above. The two reviewer label sets are
   committed SEPARATELY (semantic first) so contract-layer,
   algorithm-relative reasoning cannot leak into the semantic-truth
   judgment.
5. **Semantic-only reveal and adjudication (STRICTLY FIRST).** Author
   semantic labels + reviewer semantic labels (and ONLY those two
   artifacts) are revealed via `validate_design.py`'s SUBSET reveal
   verification: the other two declared author artifacts (contract,
   coverage) and design metadata remain sealed and unrevealed, and
   `validate_design.py` HARD-REJECTS any of them if supplied at this
   stage. Both semantic commitments are verified by recomputing the
   domain-separated hash from the revealed bytes, nonce, and the
   from-disk-recomputed `labeling_context_hash`. Author vs. reviewer
   semantic labels are mechanically diffed. **The operator adjudicates
   semantic truth with contract, design metadata, and the coverage
   manifest still inaccessible** -- adjudication of what actually
   happened in the text must not be contaminated by which algorithm
   behavior is "expected." Semantic adjudication is then frozen.
6. **Contract/design/coverage reveal (STRICTLY AFTER semantic
   adjudication is frozen).** Only now are author contract labels,
   reviewer contract labels, design metadata, and the coverage manifest
   revealed, via `validate_design.py --reveal-stage contract --sealed-dir
   <path> --nonces-file <path> --reviewer-dir <path> --reviewer-nonces-file
   <path>` (the four-artifact contract-stage bundle; see "Staged reveal"
   below for the exact bundle contract). Author vs. reviewer contract
   labels are mechanically diffed. The contract-layer disagreements are
   adjudicated with the frozen semantic layer as ground truth.
7. **`reveal_verification_ledger.json`** is produced: the canonical
   record of every artifact revealed and verified across both stages, in
   the PINNED CANONICAL ORDER (see "Reveal-verification ledger: literal
   six-tuple pin" below -- the ledger builder EMITS this order directly,
   it does not sort by envelope/artifact_name), with `verified_stage`
   marking `semantic` vs. `contract`.
8. **`labels_frozen.json` + `FREEZE-MANIFEST.json`** are produced,
   binding every input artifact's raw SHA-256 PLUS the five provenance
   fields (`labeling_context_hash`, `author_commitment_sha256`,
   `reviewer_semantic_commitment_sha256`,
   `reviewer_contract_commitment_sha256`,
   `reveal_verification_ledger_sha256`). `measure.py` proves all three
   envelopes (author, reviewer-semantic, reviewer-contract) carry the
   IDENTICAL `labeling_context_hash` and that every ledger entry is
   `verified: true` before any measurement runs.
9. **Phase B measurement** runs under separate authorization -- see
   below.

Any byte change to the corpus or a sealed artifact after `commitment.json`
is finalized abandons that corpus version; restart at the next version.
There is no in-place correction once blind labeling has begun.

## Tier_1-only scope

Every `corpus_inputs.json` item is either a plain `"context"` string (one
tier_1 source) or a `"context_sources"` array where every source has
`"tier": "tier_1"`. No tier_2/tier_3 source and no basis-empty or
advisory-path construction appears anywhere in this corpus -- those
belong to the existing conformance-fixture lane
(`reference/fixtures/oracles.json`, `generated.json`), not this
calibration corpus.

## C1-C4-only scope

This corpus measures C1, C2, C3, C4 detector competence only. C_COV is
uncalibrated (SAN-882) and C5 is out of slice scope; neither is touched
here.

## No-evaluator-before-freeze rule

Phase A NEVER runs a full `reference.evaluate.evaluate()` pass (or the
TypeScript port) over any corpus item, in either SDK, and never
records, publishes, or uses an evaluator OUTCOME for a rate or a gate.
`validate_design.py`'s inline toy tests exercise harness/report code
paths on INLINE TOY fixtures that are explicitly not corpus items.
`measure.py` and `benchmark.py` refuse to run without
`FREEZE-MANIFEST.json`, which does not exist until the workflow above
completes.

**SAN-881 PASS 2B.1-T** built an EPHEMERAL, TYPED, validator-local
product-trace substrate (`FieldProductTrace` / `FrameProductEvent` /
`PartialProductEvent` / `ProductTraceBundle`) by pure read-only replay
of the pinned production extraction primitives over public corpus
text -- it captures exact per-field frame/partiality PRODUCTS.
**SAN-881 PASS 2B.1-P boundary (honesty statement):** this substrate is
now WIRED into `check_coverage_manifest` for the 50 in-scope surfaces
(47 table-derived + the 3 `value_role_v1` surfaces) via `CAPABILITY_MAP`
(a CLOSED, reviewed STATIC routing declaration, `(family, location) ->`
legal `(check_id, field)` positions -- never dynamically inferred) and
a FOUR-CLAUSE product contract (POSITION, PRODUCT PRESENT, NON-PARTIAL,
CHECK-APPLICABLE) plus ownership/partiality qualifiers -- see "Coverage
manifest: pre-registered closed registry" below for the full contract.
**SAN-881 PASS 2B.1b** upgraded the 18 NONTABLE surfaces to
product-honest, event-local proof. GROUP A (the seven `c2_*` surfaces)
is bundle-free -- it consumes `reference.checks.scan_c2_lexical` /
`has_governed_question`, the SAME shared helpers `checks.C2` and
`evaluate.py`'s own Stage W1 gate consume, over the declared field's
own re-tokenized text, and never builds a `ProductTraceBundle`. GROUPS
B and C (the remaining eleven surfaces) ARE `ProductTraceBundle`-backed
event-local evidence, sharing one Pass-B-wide bundle cache with the 50
in-scope surfaces, but reusing only the ordinary ownership/nonpartial
portion of the four-clause contract -- no nontable surface is ever
routed through `CAPABILITY_MAP`. The five `_contains_*` lexical
helpers and the eleven Group B/C handler expressions inside
`_predicate_nontable` itself remain BYTE-UNCHANGED. **SAN-881 PASS
2B.1b-FIX2** made `_predicate_nontable`'s own dispatch LAZY/early-
returning: a registered Group A (`c2_*`) name now returns before the
eleven Group B/C expressions are ever constructed, so those eleven --
like the eight dead non-nontable `COVERAGE_PREDICATES` entries this
module already carries -- are LEGACY-UNREACHABLE-FROM-RUNTIME (no live
`check_coverage_manifest` dispatch path ever evaluates their code at
all; they remain directly callable/tested only).

Runtime validation proves parsed-product presence, ownership and
partiality qualifiers, declared-field integrity, and compatibility
with a reviewed static routing map. It does not prove internal branch
reach, causality, or per-corpus-item execution. Phase B evaluator
runs remain the authority for measured behavior.

No `CheckConsumptionTrace` class exists, and none is planned: a genuine
internal-branch-consumption-tracing architecture (event vocabulary,
locks, phase state, call attribution, runtime monkeypatching of
production code, replay of a check's own branch against a real
outcome) was proposed and **REJECTED** -- this pass achieves
product-level, not consumption-level, assurance, and that boundary is
permanent, not a staging step toward consumption tracing. The trace
substrate itself never publishes trace data or outcomes, never persists
a trace to any artifact, and never computes a rate or a gate from a
trace. The rule above still prohibits any full `evaluate()` run whose
OUTCOMES are recorded, published, or used for a rate or a gate -- that
prohibition is unchanged by this pass.

## The Phase-B execution contract (`measure.py`)

1. Refuses to run unless `measure.verify_frozen_bundle(freeze_manifest_path,
   cal_dir, repo_root)` -- the SINGLE, shared, centralized frozen-bundle
   verifier (SAN-881 PASS 2C.1; both `measure.run_pipeline` and
   `benchmark._rerun_full_freeze_verification` call ONLY this function,
   using explicit paths derived from their own arguments, never a module
   global) -- succeeds. It: validates `FREEZE-MANIFEST.json` against
   `schemas/freeze_manifest_schema.json` (schema check strictly BEFORE
   any hash check); verifies every bound raw SHA-256 (corpus_inputs,
   labels_frozen, design_metadata, coverage_manifest, evaluation_profile,
   algorithm, tables, adjudication_log); schema-validates the AUTHOR
   commitment envelope, both reviewer commitment envelopes, and
   `reveal_verification_ledger.json` each against their OWN specific
   schema branch (never relying on `oneOf` disambiguation, so a
   wrong-envelope-kind document is rejected precisely); recomputes
   `labeling_context_hash` and the complete `labeling_context_components`
   list from disk (never trusting any envelope's own declared copy) and
   requires the recomputed hash to equal the manifest, all three
   envelopes, and the ledger, and the AUTHOR envelope's declared
   component list to equal the recomputed list EXACTLY; and cross-checks
   `reveal_verification_ledger.json` index-by-index against the pinned
   canonical six-tuple order, including that every declared `byte_length`
   (ledger AND envelope) equals the ACTUAL raw byte length of the
   corresponding committed artifact (resolved ONLY by its canonical
   name, never an envelope- or ledger-supplied path).
2. Validates ALL frozen schemas (design metadata, `labels_frozen.json`,
   coverage manifest) and cross-file population invariants (160 ordered
   corpus items, 640 ordered frozen labels, the closed 68-surface
   coverage structure with every evidence `item_id` a genuine corpus
   member) BEFORE any harness execution, and requires a clean tracked
   worktree and a resolvable `HEAD`. SAN-881 PASS 2C.1-FIX: `labels_
   frozen.json`'s per-record CROSS-REFERENTIAL coherence is ALSO
   verified here, not merely its contract-tuple internal consistency --
   every merged frozen-label record is projected into
   `validate_design.check_labels`'s own SEMANTIC and CONTRACT shapes and
   run through THE SAME authoritative validator authored labels are
   checked against, over the verified `design_by_id`. This closes a real
   gap: `semantic_truth=VIOLATION` paired with a `PASS` contract, a C1
   `VIOLATION` with `severity=warning` (must be `critical`), a non-C1
   `VIOLATION` with `severity=critical` (must be `warning`),
   `advisory=true` (this tier_1-only corpus requires exactly `false`),
   and a competence value inconsistent with the item's own design
   stratum were all previously ACCEPTED (the contract-tuple-only check
   never receives `semantic_truth` or `competence` as inputs at all) --
   any `check_labels` diagnostic now fails `verify_frozen_bundle` closed.
3. Builds the canonical ephemeral 640-record projection: every
   allowlisted `corpus_inputs.json` entry x {C1,C2,C3,C4}, ids EXACTLY
   `calx:NNN:CN`, canonical JSON bytes (sorted keys, compact separators,
   `ensure_ascii`, single trailing LF), written ONCE to a single file --
   the SAME path is handed to both harnesses. The allowlist (`context` |
   `context_sources`, `output`) makes a label leak into evaluator input
   structurally impossible. `corpus_inputs.json` carries NO JSON Schema
   (by design), so every field's TYPE is proven EXPLICITLY before use:
   `context` (when present) is a string; `output` is a string;
   `context_sources` (when present) is a list, and each source's `text`
   is a string -- all checked BEFORE duplicate-tuple detection, the
   `context_sources` join, or any `.encode()` call, so a malformed field
   (e.g. `context: []`) fails with a specific, fixed diagnostic instead
   of a raw `TypeError`/`AttributeError`.
4. ALWAYS rebuilds the TypeScript package first (`npm ci --ignore-scripts`
   + `npm run build`; a pre-existing `dist/` is never trusted), then
   invokes BOTH harnesses (`reference/diff_harness.py`,
   `reference/ts/dist/src/diff_harness.js`) on the exact same projected
   file. Each must yield zero exit and 640 complete, unique, well-formed
   results; each harness's stdout must equal the canonical
   reserialization of its own parsed records (attribution closure);
   every result's `check_id` must match its id's compound check segment;
   every tuple's outcome/outcome_reason/severity/advisory must be
   internally closed-set consistent.
5. Byte-compares the two canonical outputs; any inequality is FATAL and
   is also recorded as the `py_ts_byte_equality_640` gate (derived
   directly from the two raw output byte strings' equality -- never a
   caller-supplied boolean, never defaulted true; see `measure.
   compute_rates`'s keyword-only `python_output_bytes`/
   `typescript_output_bytes` parameters, SAN-881 PASS 2C.2).
6. Joins the frozen labels and emits `outcomes.json` (outcomes + freeze
   hash + component hashes + record count + SEPARATE PER-SDK output
   hashes -- `python_output_sha256` and `typescript_output_sha256`,
   each the SHA-256 of that SDK's own canonical output bytes, SAN-881
   PASS 2C.2 -- + runner git commit + `measure.py`'s own SHA-256),
   `rates.json` (additionally binding `freeze_manifest_sha256` and the
   RAW `outcomes.json` bytes hash), and `RATES-REPORT.md`.

### SAN-881 PASS 2C.2: separate per-SDK output hashes, publication ordering, and benchmark replay integrity

`outcomes.json` no longer records a single combined output-hash field
-- it records `python_output_sha256` and `typescript_output_sha256`
separately, each the SHA-256 of that SDK's OWN canonical harness output
bytes (`measure.run_dual_harness` returns the four raw values --
`python_bytes, typescript_bytes, python_results, typescript_results` --
never a single combined hash). **Separate per-SDK hashes do NOT publish
or diagnose a divergent accepted run -- byte divergence still ABORTS
publication** (the `py_ts_byte_equality_640` gate and the FATAL
byte-compare in step 5 above are both unchanged). Their purpose is
INDEPENDENT PER-SDK REPLAY BINDING: a third party (or `benchmark.py`'s
own replay integrity check below) can verify each SDK's output
independently against its own hash, without the combined hash's
information loss.

Publication ordering is pinned. `_require_clean_tracked_worktree`
returns the verified, resolvable HEAD it just checked; `run_pipeline`
captures this HEAD ONCE, before the harness runs, and that CAPTURED
value -- never a later, fresh, unverified `git rev-parse HEAD` -- is
what `outcomes.json` records as `runner_git_commit`. AFTER all three
artifacts are written (`outcomes.json`, `rates.json`,
`RATES-REPORT.md`) but BEFORE the atomic rename, cleanliness and HEAD
are RECHECKED (a second, separate call to
`_require_clean_tracked_worktree`): if a concurrent commit landed (HEAD
moved) or a tracked file went dirty WHILE the harness ran, publication
is refused -- the artifacts just written would otherwise misattribute
themselves to a HEAD/worktree state that no longer holds. The pinned
event order is: harness -> three writes -> git recheck -> rename.
Bounded to git state only; no snapshot subsystem.

`benchmark.py`'s own precondition check (SAN-881 PASS 2C.2) closes the
gap this leaves for a THIRD party auditing published results after the
fact: before any timing pass, and after every cheap structural sanity
check on `outcomes.json`/`rates.json` has passed, `benchmark.
check_preconditions` reruns the verified frozen bundle's own projection
through BOTH harnesses (`measure.run_dual_harness`), joins the VERIFIED
frozen labels (`measure.join_labels`), and recomputes rates via
`measure.compute_rates` -- `benchmark.py` NEVER duplicates metric or
gate logic. It reconstructs the EXACT expected `outcomes.json` document
(`freeze_manifest_hash`, `component_hashes`, `record_count`,
`python_output_sha256`, `typescript_output_sha256`, `runner_git_commit`,
`measure_py_sha256`, `outcomes`) and the EXACT expected `rates.json`
document (the reconstructed rates plus `freeze_manifest_sha256` and the
RAW outcomes bytes hash), and compares CANONICAL bytes of each
reconstruction against the STORED raw file bytes on disk. This closes
header tampering, per-record tampering, and forged gate values alike --
gate acceptance downstream uses ONLY the RECONSTRUCTED rates object,
never a caller-supplied one. `outcomes.json`/`rates.json` are
themselves loaded through a fixed-name fail-closed helper
(`_load_result_document_or_fail`, routed through `measure.
_load_json_or_fail`) so a directory in place of either file, invalid
UTF-8, invalid JSON, or a non-object top-level value all translate into
`BenchmarkRefused` -- with a canonical artifact-name-only message, never
an absolute path -- instead of a raw `OSError`/`UnicodeDecodeError`/
`JSONDecodeError`/`AttributeError` escaping straight through.

### SAN-881 PASS 2C.1-FIX: the fail-closed file-read boundary

Every file `verify_frozen_bundle` reads (bound-hash targets, the six
schema files, the three commitment envelopes, the reveal ledger,
`corpus_inputs.json`, `design_metadata.json`, `labels_frozen.json`,
`coverage_manifest.json`, `adjudication_log.json`, `FREEZE-MANIFEST.json`
itself) goes through one of a small set of FIXED-NAME helpers --
`_read_bytes_or_fail`, `_sha256_or_fail`, `_load_json_or_fail`,
`_schema_validate_or_fail` -- each of which translates every failure
class (`OSError`, including a DIRECTORY in place of a file;
`UnicodeDecodeError`; `json.JSONDecodeError`; a `jsonschema` validation-
ENGINE failure, distinct from a validation-error result) into
`FreezeGateRefused`/`InfrastructureFailure`, never a raw traceback, and
names the artifact by its CANONICAL NAME only (`Path.name`), never an
absolute filesystem path. `verify_freeze_manifest` -- the eight-plus-
four raw-SHA-256 bound-hash checker -- is REDUCED to exactly that: a
raw-hash-only helper. It previously ALSO parsed the three commitment
envelopes and the reveal ledger as JSON, unguarded, before any schema
gate, to cross-check `labeling_context_hash` agreement and each ledger
entry's `verified` flag -- an envelope that was `[]` produced a raw
`AttributeError`, one that was `{` (truncated JSON) produced a raw
`JSONDecodeError`, and a raw committed artifact replaced by a directory
produced a raw `IsADirectoryError`, all escaping straight through the
fail-closed boundary as uncaught Python tracebacks instead of a
`FreezeGateRefused`. Both of those checks moved entirely into
`verify_frozen_bundle`, which performs them ONLY over documents already
proven schema-valid: the `labeling_context_hash` agreement check is now
the from-disk RECOMPUTED-hash cross-check (a strictly stronger, ground-
truth check than the old pairwise envelope comparison), and the
per-entry `verified` check now lives exclusively in the ledger
index-by-index cross-check. `benchmark.py`'s own wrapper
(`_rerun_full_freeze_verification`) needed no changes to get this same
protection -- it already caught only the two approved exception classes
and simply never saw anything else escape `verify_frozen_bundle` once
`verify_frozen_bundle` itself stopped leaking them.

### Transactional hash-addressed publication

Results are immutable at `results/<freeze_manifest_sha256>/`. Each run
writes into a FRESH sibling temporary directory
(`results/.tmp-<freeze_manifest_sha256>-<uuid>/`) and only performs an
ATOMIC rename to the final hash-addressed directory once all three
artifacts (`outcomes.json`, `rates.json`, `RATES-REPORT.md`) are
completely written. The final hash directory MUST NOT already exist --
a run refuses outright rather than overwrite a prior hash-addressed
result. A crash, nonzero harness exit, byte mismatch, or any other
INFRASTRUCTURE FAILURE removes ONLY the temporary directory; any prior
hash-addressed results directory is left completely untouched and is
never presented as current. A SEMANTIC GATE failure (any of the nine
hard gates below is false) still completes the atomic rename -- the
complete auditable artifact set IS published -- but the process exits
nonzero. Stale success artifacts can never survive a failed run, and a
failed run can never masquerade as a prior success.

### The nine hard gates

Populations are pinned per check: **primary** = the check's own 40
target records; **secondary** = all 160 for that check, aggregate only.
**640 pooled across checks is never used for any gate or metric.**

1. `py_ts_byte_equality_640` (the two harnesses' canonical outputs are
   byte-identical; recorded as an explicit gate, not merely a raise)
2. `contract_tuple_agreement_640` (all 640 records, full tuple equality)
3. `zero_evaluator_errors` (keys on `outcome == "EVALUATOR_ERROR"` --
   NEVER on `outcome_reason`; an evaluator-crash marker is an outcome
   value, and `outcome_reason` such as `evaluator_exception` is
   corroborating detail, not the gate's own signal)
4. `zero_false_violations`
5. `zero_unsafe_violations`
6. `zero_in_domain_escapes` (escape numerator 0 over records whose item
   is the target `in_domain_violation` item for that check; an escape is
   ONLY a true `VIOLATION` that emits `PASS` -- a true `VIOLATION` that
   emits `NOT_EVALUATED` is a coverage-loss / recall miss, tracked by
   `coverage_loss_abstention_rate`, and is NEVER counted as an escape)
7. `in_domain_semantic_accuracy_100` (pinned semantic correctness
   mapping: `NO_VIOLATION -> PASS`, `VIOLATION -> VIOLATION`,
   `INDETERMINATE -> NOT_EVALUATED`; every target `in_domain_*` record
   maps correctly)
8. `deliberate_abstention_correct_100` (every target
   `indeterminate_or_unsafe` record: `NOT_EVALUATED` AND
   `outcome_reason` equals the frozen contract reason)
9. `zero_envelope_breaches_640` (no record with `outcome_reason ==
   envelope_exceeded`)

The gate object carries EXACTLY these nine pinned names, in this order,
every run -- no more, no fewer.

Near-miss recall and coverage-loss abstention are REPORT-ONLY (not
gates). The corpus-impact ranking counts `introduced_feature`
occurrences where `competence == KNOWN_COVERAGE_GAP`, deduped by item,
KEYED BY THE COMPLETE `introduced_feature` object (two distinct
features that merely share a `kind` -- e.g. two different condition_operator
tokens -- never collapse into the same ranking bucket). Every
`primary_target_40` population additionally reports a per-`target_stratum`
confusion-matrix breakdown (`confusion_by_stratum`).

### Two reporting views, no Wilson intervals

Every population reports the **primary (40 target items)** view and the
**secondary (all 160, aggregate)** view separately, plus scenario count
alongside item count. Every ratio is `{"numerator": int, "denominator":
int, "value": decimal-string-or-null}` -- a zero denominator is `null`,
never `0%`/`100%`; `value` uses fixed-precision decimal, scale 4,
`ROUND_HALF_EVEN` (Python `decimal`); `RATES-REPORT.md` renders every
ratio as a PERCENTAGE (`"25.00%"`, computed as `value * 100`), never a
bare fraction (`"0.25"`). **No Wilson intervals anywhere** (removed
by operator direction): this is a purposive synthetic corpus with paired
minimal-pair scenarios, which cannot support statistical inference over
a real-world population. `RATES-REPORT.md` and `rates.json` both state
this caveat prominently.

## Benchmark separation (`benchmark.py`)

TIMING is Python-reference-only (`timing_python_reference_only: true`
in `benchmark.json`) -- the 10 warm-up + 30 timed passes over all 160
items call `reference.evaluate.evaluate` directly, never touching the
TypeScript reference. INTEGRITY REPLAY (SAN-881 PASS 2C.2), by
contrast, executes BOTH SDKs (`integrity_replay_sdks: ["python",
"typescript"]`): before any timing pass, `benchmark.check_preconditions`
reruns the verified frozen bundle's own projection through
`measure.run_dual_harness` (subprocess-based, the SAME dual-harness
invocation `measure.py` itself uses -- never a second direct evaluator
call) to independently verify `outcomes.json`/`rates.json` against a
GENUINE re-execution, not merely their own self-declared, self-
consistent hash bindings. These two keys replace the prior single,
ambiguous `python_reference_only` flag -- timing and integrity are
DIFFERENT claims and are now stated separately.

Before any timing pass, `benchmark._rerun_full_freeze_verification`
calls `measure.verify_frozen_bundle` EXACTLY ONCE, fresh from disk
(SAN-881 PASS 2C.1) -- benchmark.py carries NO JSON-Schema,
labeling-context, reveal-ledger, or population-invariant implementation
of its own; it trusts nothing measure.py already checked at measurement
time and re-verifies the complete frozen bundle again, now, against the
artifacts actually on disk, via the SAME single, shared verifier
measure.py's own execution contract uses. It returns the VERIFIED
bundle (manifest, corpus_inputs, design, labels_frozen,
evaluation_profile, coverage_manifest) alongside any failures, so the
replay-integrity check below reuses the ALREADY-VERIFIED corpus/labels/
design/manifest without ever re-reading or re-verifying them a second
time -- `verify_frozen_bundle` is called exactly once total per
`check_preconditions` invocation, not once per consumer of its output.

It refuses to run on an empty or not-exactly-nine gate map; it derives
(never accepts as a caller-supplied path) the EXACT current freeze-hash
results directory, `results/<freeze_manifest_sha256>/`, from the live
`FREEZE-MANIFEST.json`; it requires `outcomes.json` to report exactly
640 outcomes; it binds to the RAW `outcomes.json` file bytes hash (never
a reserialization) and to `rates.json`'s own `freeze_manifest_sha256` +
`outcomes_sha256` bindings; and it requires the current git `HEAD` to
equal `outcomes.json`'s `runner_git_commit` with a clean tracked
implementation state -- benchmarking a different implementation than the
one that produced the outcomes it is timing is refused.

SAN-881 PASS 2C.2, as the LAST and most expensive precondition (after
every cheap structural sanity check above has passed): `benchmark.
check_preconditions` reruns BOTH harnesses over the verified bundle's
own projection, joins the verified frozen labels, and recomputes rates
via `measure.compute_rates` -- reconstructing the COMPLETE expected
`outcomes.json` (all eight keys) and `rates.json` documents and
comparing their CANONICAL bytes against the RAW stored files. ANY
divergence -- a tampered per-record outcome, a tampered header field, or
a `rates.json` gate map simply FORGED to claim all-nine-pass while the
underlying data would recompute a failure -- is refused. Gate acceptance
downstream uses ONLY this RECONSTRUCTED rates object, never the
caller-supplied (on-disk) one. `outcomes.json`/`rates.json` are loaded
through a fixed-name fail-closed helper so a directory in place of
either file, invalid UTF-8/JSON, or a non-object top-level value
translate into `BenchmarkRefused`, never a raw traceback. The timed pass
itself (SAN-881 PASS 2C.2) reuses the SAME already-verified
`corpus_inputs` `check_preconditions` returns -- it never re-reads
`corpus_inputs.json` from disk a second, independent time.

A persistent process with the corpus preloaded runs 10 warm-up passes +
30 timed passes over all 160 items in fixed `cal:000..cal:159` order,
`time.monotonic_ns()` per item. Percentiles use the nearest-rank method
(sort ascending, 1-indexed rank = `ceil(p/100 * N)`); per-item N=30
samples, per-pass N=30 totals; P50/P95/max reported for both.
Envelope-breach count is copied from the deterministic `outcomes.json`,
never independently measured during a timing pass. Benchmark runs are
excluded from every determinism gate.

## Verifier commands

```
# Public-only validation (every commit; CI-run):
python3 reference/calibration/validate_design.py

# Private author validation before sealing:
python3 reference/calibration/validate_design.py --sealed-dir <path>

# Semantic-only reveal (workflow step 5, STRICTLY FIRST): explicit
# --reveal-stage semantic -- a TWO-ARTIFACT verification event (author +
# reviewer semantic labels ONLY; contract/design/coverage extras
# hard-rejected if supplied; an envelope omitting its artifact fails):
python3 reference/calibration/validate_design.py --reveal-stage semantic \
    --sealed-dir <path> --nonces-file <path> \
    --reviewer-dir <path> --reviewer-nonces-file <path>

# Contract/design/coverage reveal (workflow step 6, STRICTLY AFTER
# semantic adjudication is frozen): explicit --reveal-stage contract --
# a FOUR-ARTIFACT verification event (author contract labels, design
# metadata, coverage manifest, reviewer contract labels; semantic extras
# hard-rejected if supplied):
python3 reference/calibration/validate_design.py --reveal-stage contract \
    --sealed-dir <path> --nonces-file <path> \
    --reviewer-dir <path> --reviewer-nonces-file <path>

# Phase B (separate authorization only):
python3 reference/calibration/measure.py
python3 reference/calibration/benchmark.py
```

### Staged reveal: exact bundle contract, custody-derived nonce subsets, dispatch order

SAN-881 Phase-A CORRECTION PASS 1 pins the `--reveal-stage` bundle
contract exactly, and closes several gaps in the pre-correction
implementation (a real semantic-only staged invocation previously
crashed with an uncaught `FileNotFoundError` -- see below).

**Exact bundle contents (directory listing, not "contains at least").**
`--sealed-dir` and `--reviewer-dir` for a given stage must contain
EXACTLY the files below -- no more, no fewer. A missing pinned member,
an arbitrary/unrecognized extra file, or the OTHER stage's artifact
(present opportunistically) all fail with a fixed `RULE_*` code. This
check inspects EVERY immediate directory entry, not only regular-file
survivors of a naive `is_file()` filter (SAN-881 PASS-1 CORRECTION
ROUND): every allowed member must be a DIRECT, REGULAR, NON-SYMLINK
file, so a directory or symlink at a pinned name -- even a symlink
pointing at a legitimate regular file elsewhere -- fails with
`REVEAL_ARTIFACT_NOT_REGULAR_FILE`, and an arbitrarily-named directory
(previously invisible to this check, since it was silently dropped by
the `is_file()` filter) now fails as an extra:

| stage | `--sealed-dir` contains EXACTLY | `--reviewer-dir` contains EXACTLY |
|---|---|---|
| `semantic` | `labels_author_semantic.json` | `labels_reviewer_semantic.json`, `labels_reviewer_semantic.commitment.json` |
| `contract` | `labels_author_contract.json`, `design_metadata.json`, `coverage_manifest.json` | `labels_reviewer_contract.json`, `labels_reviewer_contract.commitment.json` |

**Nonce maps are custody-derived STAGE SUBSETS.** `--nonces-file` and
`--reviewer-nonces-file` are each a JSON object of EXACTLY the nonce
keys for that stage (the author nonce map is `{artifact_name: hex_nonce}`
scoped to the stage's own author artifact names; the reviewer nonce map
has exactly one key, that stage's reviewer artifact name). These are
custody-derived STAGE SUBSETS carved out of the original four-key author
nonce file produced at sealing time -- NOT that original file itself, and
NOT a superset. Every nonce value must be exactly 64 lowercase hex; a
missing key, an extra key, a key naming the OTHER side's own artifact
(a reviewer nonce map key attempting to overwrite an author key, or vice
versa), or a malformed value all fail. `--nonces-file` and
`--reviewer-nonces-file` are NOT bundle members: they must live OUTSIDE
`--sealed-dir` / `--reviewer-dir` respectively (a nonces file placed
inside the bundle directory it accompanies is rejected), and their
parent directories are not subject to the exact-bundle-content check
above.

**Dispatch order: a staged invocation never enters a generic path.**
After argument parsing and the public schema/corpus/profile/AUTHOR-
envelope checks, `--reveal-stage` dispatch is mutually exclusive with
the generic `--sealed-dir` design/labels/coverage block -- a staged
invocation can never fall into it. (Pre-correction, `--reveal-stage
semantic` with a real semantic-only `--sealed-dir` unconditionally hit
the generic block's `design_metadata.json` load first and crashed with
an uncaught, absolute-path-disclosing `FileNotFoundError` -- exactly
the failure mode this ordering exists to prevent.)

**Missing reviewer artifacts fail; they are never silently skipped.**
An unresolvable reviewer commitment envelope (no `--reviewer-dir`, or
its commitment file absent/unreadable) is a hard failure for that
stage's reviewer artifact, not a silent no-op.

**`--reveal-stage` is the SOLE cryptographic reveal path (SAN-881
PASS-1 FINAL CLOSURE CORRECTION).** The deprecated legacy generic
per-envelope verification path -- `verify_envelope_generic`,
`run_reveal_verification`, `reveal_verify_set`, and the opt-in flag
that wired them -- is REMOVED entirely: no non-test consumer of that
path ever existed. Any of `--nonces-file`, `--reviewer-dir`, or
`--reviewer-nonces-file` supplied WITHOUT `--reveal-stage` is now a
fixed-diagnostic reject (`rule=NONCE_OR_REVIEWER_ARG_REQUIRES_REVEAL_STAGE`),
never a silent no-op (the pre-correction generic `--sealed-dir` block
silently ignored a bare `--nonces-file` with no `--sealed-dir`, and
required an explicit opt-in flag for `--reviewer-dir`). Bare
`--sealed-dir` alone -- the documented pre-sealing STRUCTURAL
author-validation workflow (step 1 above) -- is unaffected and never
triggers this reject.

### SAN-881 PASS-1 CORRECTION ROOT REPAIR: schema validity gates cryptographic validity

The staged reveal path previously proved "these are the committed
bytes" (a successful cryptographic subset reveal) WITHOUT proving "these
bytes are valid labels/design/coverage under the frozen schemas" -- a
selected artifact could be byte-for-byte the artifact the author sealed
and STILL be schema garbage (wrong record count, wrong shape, a
zero-record or 639-record labels file, a malformed reviewer envelope).
The SAN-881 PASS-1 CORRECTION ROUND closes this gap:

**Selected-stage schema validation runs BEFORE cryptographic subset
verification.** Every PRESENT artifact belonging to the selected
stage's subset -- `labels_author_semantic.json` /
`labels_reviewer_semantic.json` against `labels_schema.json`'s
`semanticFile` form SPECIFICALLY; `labels_author_contract.json` /
`labels_reviewer_contract.json` against its `contractFile` form
SPECIFICALLY; `design_metadata.json` against
`design_metadata_schema.json`; `coverage_manifest.json` against
`coverage_manifest_schema.json`; and the reviewer commitment envelope
itself against `commitment_schema.json`'s `REVIEWER_SEMANTIC` /
`REVIEWER_CONTRACT` discriminant SPECIFICALLY -- is parsed and
schema-validated first. Stage labels are NEVER validated against
`labels_schema.json`'s root `oneOf` (a contract-shaped file supplied at
the semantic stage, or vice versa, would otherwise still validate,
since it matches a DIFFERENT `oneOf` branch). If ANY present selected
artifact or the reviewer envelope fails JSON parsing, this
stage-specific schema validation, or discriminator validation,
cryptographic subset verification is SKIPPED ENTIRELY for that stage --
malformed or schema-invalid bytes are never handed to the crypto layer
merely to accumulate additional errors.

**Every staged stderr diagnostic is now a fixed `rule=CODE` line.** The
staged path no longer appends the underlying reveal-verification
helper's free-form prose ("sealed artifact ... not supplied", "forbidden
stage extra supplied: ..."); every staged detail line carries a fixed
`RULE_*` code (`REVEAL_ARTIFACT_NOT_SUPPLIED`,
`REVEAL_FORBIDDEN_STAGE_EXTRA`, `REVEAL_UNDECLARED_EXTRA_ARTIFACT`,
`REVEAL_BYTE_LENGTH_MISMATCH`, `REVEAL_NO_NONCE`,
`NONCE_NOT_64_LOWERCASE_HEX`, `REVEAL_DOES_NOT_VERIFY`), mechanically
greppable.

**`commitment.json` validates SPECIFICALLY as the AUTHOR envelope.** The
public commitment envelope is checked against `commitment_schema.json`'s
`authorEnvelope` branch SPECIFICALLY, never merely "matches SOME branch
of the root `oneOf`" -- a schema-valid `REVIEWER_SEMANTIC` or
`REVIEWER_CONTRACT` envelope substituted as `commitment.json` fails with
a fixed diagnostic and can never reach staged cryptographic processing.
`check_commitment` and `check_author_commitment_order` remain shape-safe
accessors (never raise on a malformed `author_commitments`, including a
non-list value or `None` members) and continue to run regardless of
schema validity, preserving the pinned v1-transitional four-line public
output exactly.

**A v2 envelope's declared component list is bound to disk, not merely
descriptive.** For a `corpus_version: 2` envelope, `check_commitment`
additionally requires `commitment.json`'s own
`labeling_context_components` list to equal
`build_labeling_context_components(cal_dir, repo_root)` exactly (names,
order, hashes) -- the outer `labeling_context_hash` still derives SOLELY
from fixed disk paths/constants (an envelope's declared list is never an
INPUT to that hash), but a correct outer hash paired with a forged or
stale declared component entry now fails, collapsed into the SAME single
`CONTEXT_HASH_MISMATCH` rule. A v1-transitional envelope (`corpus_version
!= 2`) is never subjected to this cross-check, preserving the pinned
four-line output.

**`commitmentAlgorithm.formula` is a pinned const.** Previously any
non-empty string satisfied the schema; `formula` is now pinned to the
exact commitment formula text (see "Author seals" above) -- a false or
stale formula string fails schema validation.

### SAN-881 PASS-1 FINAL GATING CORRECTION: the three-tier gated pipeline

The PASS-1 CORRECTION ROUND above added exact-bundle-membership,
exact-nonce-keyset, and selected-stage schema checks as INDEPENDENT
diagnostics, but none of their outcomes actually GATED what happened
next: a rejected symlinked member, a missing or extra bundle entry, a
malformed nonce map, or a nonce file parked inside its own bundle could
each still leave cryptographic subset verification running for whatever
OTHER artifact in the stage happened to be legitimate -- for a symlinked
member specifically, `run_stage_reveal_verification`'s own bytes-gathering
step reopened the path with a follow-symlinks read, so cryptographic
verification ran to completion reading straight through the very symlink
the membership check had just rejected. This section's root repair is
**validity must gate, not merely accumulate**: `run_stage_reveal_verification`
is now a strict three-tier pipeline, each tier's outcome gating entry
into the next.

**Tier 1, PATH GATE (metadata/location ONLY -- no file content is EVER
opened, no nonce file is EVER read, at this tier).** Every immediate
directory entry of `--sealed-dir` and `--reviewer-dir` is inspected
against the stage's exact pinned name set (missing member,
extra/unrecognized entry, non-regular-file member -- including a member
that is itself a directory, and a member that is a symlink even when its
target is a byte-identical, legitimately-committed file elsewhere) --
this is pure filesystem METADATA (`iterdir()` / `is_symlink()` /
`is_file()`), never content. SAN-881 PASS-1 FINAL CLOSURE CORRECTION:
`--nonces-file` / `--reviewer-nonces-file` LOCATION and TYPE are ALSO
evaluated entirely at this tier, for BOTH nonce paths, INSIDE
`run_stage_reveal_verification` itself (`_check_nonce_path_tier1` --
`main()` passes the raw `Path` arguments straight through, it no longer
precomputes a location boolean): outside the bundle directory it
accompanies, both LEXICALLY and by REALPATH; not itself a symlink
(a leaf symlink is rejected regardless of where it points -- the same
threat class as a symlinked bundle member); and a genuinely resolvable
regular file. Every one of these checks -- four in total, two bundles
and two nonce paths -- runs UNCONDITIONALLY -- never short-circuited --
so every independent, safe diagnostic is still reported even when the
stage will ultimately be gated shut. **If ANY of the four fails, the
combined PATH GATE result is `False` and NEITHER nonce file is ever
read** -- not merely the one whose own check failed: `run_stage_reveal_verification`
returns immediately, before Tier 2 begins. ZERO staged-payload reads,
ZERO nonce-file reads, ZERO schema validation, ZERO cryptographic
verification follow. An artifact that is simply ABSENT is caught here by
the exact-bundle-membership check; unlike the schema gate below, a PATH
GATE failure means the WHOLE stage -- every artifact in it, present or
absent -- is gated shut, not merely the missing artifact's own crypto
entry.

**Tier 2, SNAPSHOT GATE -- reads nonce maps, staged artifacts, and
envelopes EXACTLY ONCE (5 members for the semantic stage, 7 for the
contract stage), ALL through ONE unified no-follow primitive.** Once
PATH GATE has passed (bundle membership AND both nonce paths' location
and type all confirmed safe), Tier 2 performs every CONTENT-touching
read for the stage, exactly once each, through the SAME `O_NOFOLLOW`
(`_snapshot_regular_file`) primitive Tier 0 (the fixed-component cache,
below) also uses -- there is no longer a separate, `Path.read_bytes`-based
nonce-loading codepath:

- `--nonces-file` and `--reviewer-nonces-file` are now (and only now)
  snapshotted -- exactly two nonce-map reads, for EVERY stage. ONLY
  after the COMPLETE 5/7-member snapshot set exists (every bundle
  member, the reviewer envelope, AND both nonce files) does JSON
  parsing, nonce key/hex-shape validation (`_check_nonce_map`), or
  schema validation begin -- an incomplete snapshot set (any ONE
  member failing to open) gates the whole stage shut before any of
  them are inspected.
- Every approved bundle-member file is read EXACTLY ONCE via the same
  no-follow (`O_NOFOLLOW`) regular-file snapshot helper -- a rejected
  symlink target, having already failed Tier 1, is never even a
  snapshot candidate, so it can never be opened by anything downstream.
  If `os.O_NOFOLLOW` is unavailable on the platform, this helper fails
  closed WITHOUT calling `os.open` at all (SAN-881 PASS-1 CLOSURE PATCH,
  closure 5) -- it never silently degrades to a follow-symlinks open.

  Semantic stage (5 total Tier-2 reads): `--nonces-file`,
  `--reviewer-nonces-file`, `labels_author_semantic.json`,
  `labels_reviewer_semantic.json`, and the reviewer semantic commitment
  envelope. Contract stage (7 total Tier-2 reads): `--nonces-file`,
  `--reviewer-nonces-file`, `labels_author_contract.json`,
  `design_metadata.json`, `coverage_manifest.json`,
  `labels_reviewer_contract.json`, and the reviewer contract commitment
  envelope.
- The resulting bytes are parsed and schema-validated (selected-artifact
  stage-specific forms, and BOTH envelopes: the author envelope as
  `authorEnvelope` specifically, checked earlier in `main()`, and the
  reviewer envelope as its stage's own discriminant specifically) --
  against the Tier-0 cache's already-self-valid schema objects, so
  `check_stage_schema_validity` performs ZERO schema reads of its own
  and a schema is NEVER reopened during stage execution -- plus
  reviewer-envelope CONTEXT CONSISTENCY -- a schema-valid reviewer
  envelope whose OWN declared `labeling_context_hash` disagrees with the
  author envelope's now gates Tier 3 shut too, rather than merely
  accumulating `ENVELOPE_CONTEXT_HASH_INCONSISTENT` alongside a crypto
  run that would usually fail anyway. Malformed content necessarily
  incurs its one validation read -- but zero cryptographic calls follow
  it. An approved member that is ABSENT from the snapshot set -- PATH
  GATE confirmed it as a genuine regular bundle member, yet the
  subsequent read itself failed (a transient I/O error or a
  stat-then-open race) -- now GATES the whole stage shut too (SAN-881
  PASS-1 CLOSURE PATCH, closure 4): it is never silently skipped while
  `schema_ok` stays `True` for whatever else happened to snapshot
  cleanly.

**Tier 3, CRYPTO GATE.** Cryptographic subset verification runs ONLY
using those exact Tier-2 snapshots and nonce maps -- and ONLY when Tier
2 reports every one of them present and valid. There is no second,
path-based read at this tier, so nothing here can reopen (let alone
follow a symlink into) anything Tier 1 rejected or Tier 2 already read.

**Tier 0, the fixed-component cache -- a SINGLE-SOURCE cache shared by
every consumer, distinct from stage snapshots (SAN-881 PASS-1 FINAL
CLOSURE CORRECTION).** `_load_fixed_components_cache` reads each of the
ten file-backed fixed labeling-context components (`corpus_inputs.json`,
`evaluation_profile.json`, the six schema files, the algorithm doc, the
tables doc) EXACTLY ONCE, through the SAME no-follow primitive Tier 2
uses, at the very top of `main()` -- unconditionally, before
`commitment.json` is even read. The resulting cached raw bytes and
parsed values are what `schemas_self_valid_ok`, corpus/profile
structural validation, `check_commitment`'s context-hash recomputation
and declared-component comparison, `check_stage_schema_validity`'s
per-artifact schema lookups, and the bare `--sealed-dir` structural
path's `tables_data` / schema consumers all draw from -- NONE of them
independently re-reads a fixed component from disk (`check_commitment`
no longer calls `compute_labeling_context_hash_from_disk` or rebuilds
the component list; it consumes the cache `main()` built once). Any
component failure (missing, unreadable, malformed JSON, or -- for the
six schemas -- self-invalid) is a single fixed
`CONTEXT_COMPONENT_UNREADABLE_OR_INVALID` diagnostic per component
name, and `fixed_components_ok` is `False`, BEFORE any nonce/snapshot/
crypto work is attempted for that invocation.

**Public author-envelope/context reads are OUTER-GATE reads, distinct
from stage snapshots.** `commitment.json` itself and the eleven
labeling-context components it binds (SAN-881 PASS-1 CLOSURE PATCH: see
`author_gate_ok` below) are read UNCONDITIONALLY at the top of `main()`,
before ANY `--reveal-stage` tier runs -- they are public artifacts, not
staged/sealed ones, and reading them is never gated by anything. What IS
gated is every cryptographic and staged-payload read that FOLLOWS them:
`author_gate_ok` being `False` means the Tier 1/2/3 pipeline above is
never even entered for that invocation.

This correction round adds 22 new regression tests (the suite grows from
700 to 722): six PATH-GATE precondition failures (missing member, extra
entry, directory entry, symlinked member, malformed/mismatched nonce
map, nonce file inside its bundle) each now produce ZERO cryptographic
calls where they previously produced one or more; the
shape-safe envelope boundary (below) now tolerates an arbitrary
top-level JSON shape for `commitment.json` and a malformed reviewer
envelope without raising; and the happy-path cryptographic call counts
remain pinned at exactly 2 (semantic stage: author + reviewer semantic)
and exactly 4 (contract stage: author contract + design metadata +
coverage manifest + reviewer contract).

### SAN-881 PASS-1 FINAL CLOSURE CORRECTION: v1 threat boundary

**IN SCOPE for v1:** leaf symlinks at a pinned bundle-member name or a
nonce-file path (rejected regardless of target, via the shared
`O_NOFOLLOW` primitive); path escapes (a nonce file lexically or, by
realpath, actually located inside the bundle it accompanies); nonce
placement (a nonce file supplied at all, outside its bundle, as a
genuine regular file).

**OUT OF SCOPE for v1:** concurrent hostile mutation of an
operator-controlled custody directory DURING a single verifier run (a
TOCTOU race where a legitimate member is replaced between the Tier-1
stat and the Tier-2 open is still caught -- the Tier-2 open simply
fails and gates the stage shut -- but a race that swaps one
already-approved regular file for ANOTHER already-approved regular file
between tiers is not specifically detected). This round does not build
a directory-file-descriptor / `openat`-relative subsystem to close that
narrower window; the custody model already assumes the operator-owned
staging directories are not being concurrently mutated by an untrusted
party during a single `validate_design.py` invocation.

### SAN-881 PASS-1 CLOSURE PATCH: the author validity conjunction (`author_gate_ok`)

The PASS-1 FINAL GATING CORRECTION above closed six PATH/SNAPSHOT-tier
escapes, but left five further gaps: `commitment.json`'s own read/parse
was unguarded (a malformed file crashed `main()` with an uncaught
`json.JSONDecodeError`); the eleven fixed labeling-context components
`check_commitment` recomputes the context hash from were read unguarded
(a removed component crashed with an uncaught `FileNotFoundError`); the
`--reveal-stage` dispatch gated crypto on `commitment_schema_valid`
ALONE -- a pure schema-shape check that says nothing about whether the
declared `labeling_context_hash` (or, for a v2 envelope, the declared
component list) actually matches a from-disk recomputation, so a
schema-valid-but-disk-mismatched envelope still reached
`run_stage_reveal_verification` and performed real crypto calls;
`--nonces-file` / `--reviewer-nonces-file` were opened and parsed BEFORE
their location was checked; `_snapshot_regular_file` silently degraded
to a follow-symlinks open when `os.O_NOFOLLOW` was unavailable instead
of failing closed; and the two legacy per-envelope constructors (since
removed entirely -- see "the SOLE cryptographic reveal path" above)
both constructed a filesystem `Path` from an envelope-declared
`artifact_name` BEFORE confirming it belongs to the caller's own pinned
name vocabulary.

Every operand below is computed SAFELY (no exceptions escape) before
being combined:

```
author_gate_ok = (
    commitment_read_ok and commitment_json_ok and fixed_components_ok
    and schemas_self_valid_ok and commitment_schema_valid and commitment_structural_ok
    and commitment_order_ok and commitment_disk_context_ok and commitment_declared_components_ok
)
```

`commitment_read_ok` / `commitment_json_ok`: `commitment.json` is read
and parsed defensively; an unreadable or malformed file is a single
fixed `COMMITMENT_JSON_UNREADABLE_OR_MALFORMED` diagnostic, never an
uncaught exception. `fixed_components_ok` (SAN-881 PASS-1 FINAL CLOSURE
CORRECTION: simply the Tier-0 single-source cache's own `ok` field --
see above; `check_fixed_context_components` is now a thin wrapper over
that SAME cache, not an independent second read): READABILITY/PARSING
and (for the six schema files) SCHEMA SELF-VALIDITY of every one of the
eleven fixed labeling-context components except `base_commit_sha` (a
constant) -- never mere existence -- with a single fixed
`CONTEXT_COMPONENT_UNREADABLE_OR_INVALID` diagnostic per missing or
invalid component name (component names are always drawn from the
fixed, never attacker-controlled, `LABELING_CONTEXT_COMPONENT_NAMES`
tuple, so echoing one is safe). `schemas_self_valid_ok`: the six schema
files load and are themselves self-valid Draft 2020-12 schemas
(`check_schemas_self_valid`, unconditional, already run first, and
itself now consuming the Tier-0 cache rather than reading the schemas a
second time). `commitment_schema_valid`: `commitment.json` validates
SPECIFICALLY as the `authorEnvelope` branch. `commitment_structural_ok`:
the author-artifact-set membership, commitment-hex shape, and
byte-length shape checks inside `check_commitment` all pass.
`commitment_order_ok`: `check_author_commitment_order` passes.
`commitment_disk_context_ok`: the from-disk recomputed
`labeling_context_hash` (via the Tier-0 cache) matches the declared
value. `commitment_declared_components_ok`: for a `corpus_version: 2`
envelope, its OWN declared `labeling_context_components` list matches
the Tier-0 cache's own component list exactly (vacuously `True` when
the cross-check does not apply).

Every false operand means ZERO nonce-file loads, ZERO staged snapshots,
and ZERO cryptographic calls -- this conjunction gates the SOLE
remaining crypto-performing code path, `--reveal-stage` dispatch (SAN-881
PASS-1 FINAL CLOSURE CORRECTION: the generic `--sealed-dir` nonce-driven
reveal and the legacy `--reviewer-dir` reveal this conjunction used to
ALSO gate are both removed entirely -- see "the SOLE cryptographic
reveal path" above).

**Shape-safe envelope boundary.** Every pre-schema accessor over
`commitment.json` now tolerates an ARBITRARY top-level JSON shape (a
list, a string, a number, `null` -- not merely a dict with malformed
fields) and an arbitrary declared value within an otherwise-dict
envelope (an unhashable `artifact_name` such as `[]`, a numeric
`commitment_hex`) without raising -- a fixed-code diagnostic, never a
traceback, never a path disclosure.

**Nonce and artifact-name non-disclosure.** A nonce map's per-value
hex64-shape check now runs ONLY over keys that are BOTH expected AND
supplied; an unknown/extra supplied key is covered SOLELY by the
generic `NONCE_KEYSET_MISMATCH` rule and is never separately inspected
or echoed into a `[key]`-suffixed diagnostic line. Likewise, an
`author_commitments` entry's declared `artifact_name` is echoed into a
`commitment.json[...]` error label ONLY when it is a member of the
fixed, known four-name author-artifact vocabulary; any other declared
value is replaced with a fixed placeholder before it can ever reach
error output.

**Generated-schema validity.** `_build_named_schema`'s synthetic `$id`
for a named `$defs` branch (used to validate `commitment.json`'s
`authorEnvelope` / `reviewerSemanticEnvelope` / `reviewerContractEnvelope`
branches and `labels_schema.json`'s `semanticFile` / `contractFile`
branches SPECIFICALLY, bypassing the root `oneOf`) is now a plain
path-segment append with no fragment, so every one of these five branch
schemas is itself a valid Draft 2020-12 schema
(`Draft202012Validator.check_schema()` passes) -- the prior
fragment-bearing construction (`base_id + "#/$defs/<name>"`) violated
the metaschema's own "non-empty fragments not allowed" `$id` rule, even
though it still happened to validate instances correctly.

### SAN-881 PASS-1 FINAL RESOLVER CORRECTION: a closed structural reference dialect, not a graph resolver

`Draft202012Validator.check_schema()` validates schema SYNTAX only --
it never dereferences a `$ref` target, and it has no opinion on WHERE a
nested `$id` appears. `_load_fixed_components_cache` (Tier 0, above)
therefore runs one further check over all SIX fixed schema files,
unconditionally, during cache construction, BEFORE any instance
validation is ever attempted: `_schema_ref_integrity_violation`, a
full-document STRUCTURAL LINT over a deliberately tiny, CLOSED v1
reference dialect. This is a LINT, not a `$ref`-graph resolver -- it
never follows a `$ref` to decide what to check next, never builds a
worklist, and never needs cycle-detection bookkeeping, because it does
something structurally simpler and strictly stronger: it scans the
COMPLETE JSON tree of the schema document EXACTLY ONCE -- every dict
and list, INCLUDING every `$defs` entry, regardless of whether anything
in the document actually references it -- and checks, at every node:

- **`$id` allowed ONLY at the document root.** A nested `$id` anywhere
  else -- reachable via some `$ref` or not -- is a violation. Per JSON
  Schema 2020-12 `$id` resource-scope semantics, a nested `$id`
  declares a NEW resource base for everything beneath it, silently
  REBASING fragment resolution for any `$ref` inside that sub-schema
  (a `"#/$defs/hex64"` fragment inside a sub-schema carrying its own
  `$id` no longer resolves against the DOCUMENT's top-level `$defs` --
  it resolves against THAT sub-schema's own, almost certainly absent,
  `$defs`). This rule closes that gap at the source: no sub-schema in
  this dialect may ever declare a new resource base.
- **`$dynamicRef` / `$anchor` / `$dynamicAnchor` rejected anywhere**,
  lexically, including inside `$defs` -- none of the six fixed schema
  files need dynamic scoping, and admitting it would reopen exactly the
  kind of resolution complexity this closed dialect exists to avoid.
- **The ONLY accepted `$ref` form is `"#/$defs/<token>"`**, where
  `<token>` is validated with
  `re.fullmatch(r"(?:[A-Za-z0-9_.-]|~0|~1)+", token)` -- FULLMATCH,
  anchored end to end. This single grammar closes two gaps at once:
  `%` can never appear in an accepted token, so the ambiguity between a
  LITERAL string comparison and jsonschema's own URI-PERCENT-DECODING
  of a `$ref` fragment (where, for example, `"#/$defs/%61"` resolves,
  in `jsonschema`, to the key `"a"`, never the literal key `"%61"`) can
  never arise; and a raw, unescaped `/` can never appear, so a
  multi-segment JSON pointer is always rejected. A token that passes
  the grammar is then RFC6901-decoded (`~1` -> `/` BEFORE `~0` -> `~`,
  the RFC-mandated order) and must name a PRESENT member of the
  document's own TOP-LEVEL `$defs`, whose value must itself be a dict
  or a JSON boolean (the only two legal top-level schema shapes).
  Anything else -- a missing `"#/$defs/"` prefix, a bare `#`, an
  external URI, a malformed or out-of-grammar token, a missing or
  wrong-shaped target -- is a violation.

Because the scan is unconditional over the WHOLE tree rather than
worklist-driven, two properties fall out for free rather than needing
special-case logic: a `$defs` entry that nothing in the document
actually references is still fully scanned (so a violation buried
inside an otherwise-unreferenced entry is still caught), and a genuine
`a`<->`b` reference cycle is automatically fine (each side's target
need only EXIST as a present, well-formed `$defs` member; nothing here
ever "follows" a `$ref` to decide what to visit next, so there is
nothing for a cycle to break). A schema failing this lint is evicted
from `schema_by_name` with the SAME fixed
`CONTEXT_COMPONENT_UNREADABLE_OR_INVALID` diagnostic every other
fixed-component defect uses -- no new rule vocabulary, no traceback,
zero Tier-2 custody opens, zero cryptographic calls (this pass runs
strictly before `author_gate_ok` can ever become `True`). `check_schema`
(both the root pass and the named-branch pass, above) remains an
INDEPENDENT, unchanged layer -- this lint neither replaces nor
duplicates syntactic Draft 2020-12 validity checking; it closes the gap
`check_schema` structurally cannot: reference TARGETS and `$id`
PLACEMENT, not schema syntax.

### v1-transitional posture

`corpus_inputs.json`, `evaluation_profile.json`, and `commitment.json` in
this commit remain at `corpus_version: 1` -- intentionally. The SAN-881
Phase-A correction pins `commitment_schema.json` and
`freeze_manifest_schema.json` STRICTLY to `corpus_version: 2` (no
weakening to accept v1), and `validate_design.py`'s
`EXPECTED_CORPUS_VERSION` constant drives every version check the same
way. Running `validate_design.py` against these three files today
therefore fails, by design, on the pinned `CORPUS_VERSION` and
`CONTEXT_HASH_MISMATCH` rule codes (the addition of
`schemas/reveal_verification_ledger_schema.json` also changed the
labeling-context component set the v1 `commitment.json` was sealed
against -- see its from-disk recomputation in `check_commitment`; the
SAN-881 Phase-A CORRECTION PASS 1 v2 formula change -- every component,
including `base_commit_sha`, individually SHA-256'd first, see "Author
seals" above -- is a SECOND, independent reason no v1-sealed
`labeling_context_hash` can ever match a v2 from-disk recomputation,
even holding the component byte set fixed). A full v2 reseal (fresh
nonces, recomputed commitments, `corpus_version` bumped across all three
files) restores a green run; until then, this failure mode is the
EXPECTED, documented state, not a defect. See
`tests/reference/test_calibration.py`'s TRANSITIONAL tests, which pin
this exact behavior so the eventual reseal is a data change, not a test
rewrite.

## Corpus construction

160 items = 4 checks (C1-C4) x 4 strata x 10 items, one item per
`facets_v1` family per (check, stratum) block:

- `in_domain_nonviolation` -- target-check semantic `NO_VIOLATION`,
  `IN_DOMAIN` competence, `introduced_feature` null.
- `in_domain_violation` -- `VIOLATION`, `IN_DOMAIN`, null.
- `determinate_out_of_domain` -- a human-determinate truth (balanced
  EXACTLY 5 `VIOLATION` / 5 `NO_VIOLATION` per check), competence
  `KNOWN_COVERAGE_GAP` on the target check, EXACTLY ONE
  `introduced_feature` (a lexical surface or table-pair relation
  verified ABSENT from the pinned tables artifact). One-way pointer to a
  unique in-domain control sharing check/domain/semantic-truth/scenario
  -- `validate_design.check_dod_balance_and_pairs` enforces ALL FOUR of
  these shared fields explicitly (SAN-881 PASS 2B.2-FIX: `scenario_id`
  now included; a scenario-only mismatch previously produced zero
  diagnostics despite this documented contract).
- `indeterminate_or_unsafe` -- `INDETERMINATE`, `DELIBERATE_ABSTENTION`,
  null `introduced_feature`; grounded in documented abstention classes
  from `ALGORITHM-v4-c1c5-reference.md` section 10 and its errata
  catalog (e10/e13/e15, SAN-894, SAN-895).

Domains rotate across all ten `facets_v1` families (`availability`,
`refund_availability`, `exchange_availability`, `discount_availability`
via FACETPROJ projection, `access_permission`, `approval_requirement`,
`eligibility`, and the three measure facets `cost`/`duration`/`limit`
with values, units, comparators, and PCT100/currency).

### `introduced_feature`: a closed, ten-branch discriminated union (SAN-881 PASS 2B.2)

`introduced_feature` is null everywhere except `determinate_out_of_domain`
items, where it is EXACTLY ONE of TEN mutually exclusive, non-null
branches, closed at BOTH the schema level (`design_metadata_schema.json`'s
`lexicalSurfaceFeature` / `pairRelationFeature` `$defs` and their
per-kind `allOf` bindings) and the validator level
(`validate_design._dod_kind_table_binding_ok`, kept in lockstep with
the schema by a build-time parity test): `facet_trigger` (a
`facets_v1.<facet>.triggers` leaf matching the declared `facet` +
`polarity: POS`, OR `facetproj_v1`), `deny_trigger` (a
`facets_v1.<facet>.deny_triggers` leaf matching the declared `facet` +
`polarity: NEG` -- NEVER `facetproj_v1`), `concept` (`concept_v1`),
`unit` (`units_v1`), `condition_operator` (`condition_operators_v1`),
`quantifier` (`quant_v1`), `definitive` (`definitive_v1`, `role`
CLOSED to `"definitive"`), `hedge` (`hedge_v1`, `role` CLOSED to
`"hedge"`), `excl_pair` (`excl_v1`), `complement_pair`
(`complement_v1`). `comparator` is NOT a legal `introduced_feature`
kind -- comparator PARSING, coverage, and measurement (`comparators_v1`,
`checks.py`/`evaluate.py`) are untouched product features; only its use
as an introduced-feature TARGET table is removed, closing a binding gap
where a proposed feature's `kind` and `table_path` could silently
disagree (e.g. a `concept` feature bound to `units_v1`).

Each branch's `intended_semantics` shape is itself a LITERAL, CLOSED
contract, enforced IDENTICALLY at both layers (SAN-881 PASS 2B.2-FIX):
the object's key set must equal the branch's own required set EXACTLY
(no missing, no extra), and every enumerable field is closed to its
pinned vocabulary -- facet leaves (`facet_trigger`/`deny_trigger`)
require exactly `{facet, polarity}` with `facet` one of the ten pinned
families AND matching the `table_path` leaf; the `facetproj_v1`
projection requires exactly `{polarity, projects_to}` with
`projects_to` ALSO closed to the same ten families (previously an open
`^facet:[a-z_]+$` pattern); `concept` requires exactly
`{canonical_concept}`, a nonempty string; `unit` requires exactly
`{group, factor}`, nonempty `group`, `factor` a JSON number that
EXCLUDES boolean; `condition_operator` requires exactly `{kind,
polarity, force}`, each closed; `quantifier` requires exactly
`{quantifier_class}`, closed; `definitive`/`hedge` require exactly
`{role, same_overclaim_class_as_table}`, `role` matching the kind name,
and `same_overclaim_class_as_table` is now `const: true` (previously a
plain boolean -- a schema-valid `false` passed validation despite the
control-equivalence check treating the field as an unconditional "yes,
this is a genuine same-class swap" assertion); the two pair kinds carry
NO `intended_semantics` object at all. A validator-side shape violation
reports the SAME `RULE_FEATURE_NOT_ABSENT` code any other binding
failure uses -- never a new rule.

Each branch is LEXICAL (a single `surface_tokens` fold sequence) or
PAIR (`excl_pair`/`complement_pair`, two `members` fold sequences).
`validate_design.check_minimal_pair_semantic_equivalence` /
`check_minimal_pair_control_same_semantics_in_table` prove, via the
pinned `fold_sequence` tokenizer/fold primitive, that: (1) a LEXICAL
feature's complete surface sequence genuinely occurs in the DOD item
and genuinely does NOT occur in its control; (2) a PAIR feature's BOTH
member sequences genuinely occur in the DOD item (possibly in
different logical fields), and leakage into the control fires only
when the COMPLETE pair is found there (one overlapping member alone is
allowed); (3) the control genuinely swaps in a semantically-equivalent
IN-TABLE sibling (same facet+polarity, same `projects_to`,
kind+polarity+force, group+factor, canonical concept, quantifier
class, a complete `definitive_v1`/`hedge_v1` entry, or an exact row of
the declared pair table). Every presence/absence search is scoped to
ONE logical field at a time -- the item's direct `context`, or EACH
`context_sources` entry independently, or `output` -- so a folded
token sequence can never be "found" merely because two independent
fields were concatenated. Table ABSENCE for a pair feature compares
the COMPLETE UNORDERED PAIR (a sorted two-element tuple of
folded-sequence tuples) against each table row, never individual-member
overlap.

A lexical `surface_tokens` entry (and each pair-member token) must
contain at least one non-whitespace character (SAN-881 PASS 2B.2-FIX:
schema `pattern: "\S"` alongside the pre-existing `minLength: 1` on
both `$defs`) -- a whitespace-only token folds to the EMPTY sequence
under `fold_sequence`, and an empty lexical fold now emits exactly one
`RULE_FEATURE_TOKENS_NOT_IN_ITEM` diagnostic from
`check_minimal_pair_semantic_equivalence` rather than silently
returning with zero errors (previously bypassing table-absence, DOD
evidence, and control-equivalence proof entirely).

### DOD semantic checks require a genuinely valid design (SAN-881 PASS 2B.2-FIX)

`validate_design.main`'s `check_dod_balance_and_pairs` call (minimal-pair
balance, table-absence, and semantic-equivalence proof) is gated behind
an explicit, LOCAL `dod_inputs_ok` boolean -- `isinstance(tables_data,
dict) and corpus_prereq_ok and design_schema_ok and
design_semantics_ok` -- mirroring the coverage manifest's own
`upstream_ok` prerequisite-gating pattern. Previously the call ran
UNCONDITIONALLY, even after `design_metadata.json` had already failed
schema validation; a schema-invalid `introduced_feature` (a malformed
pair member, or a null lexical surface token) could reach
`fold_sequence(" ".join(...))` and raise an uncaught `TypeError`
straight out of `main(argv)`. A schema-invalid design now short-circuits
before `check_dod_balance_and_pairs` is ever called, reporting
`SCHEMA_INVALID` cleanly instead.

### Coverage manifest: pre-registered closed registry, not a documented gap

`coverage_manifest.json`'s required surfaces are drawn from a
PRE-REGISTERED, CLOSED, DECLARATIVE 68-surface registry -- the
operator-ratified Coverage Routing Matrix v3 (SAN-881 CORRECTION PASS 2)
-- (`validate_design.SURFACE_REGISTRY`: `surface -> {allowed_positions,
predicate_id}`), not dynamically enumerated from the pinned tables
artifact at validation time. `allowed_positions` is a set of explicit
`(check_id, field)` pairs, REPLACING the prior `allowed_checks` x
`allowed_fields` cartesian sets: the cartesian form could not describe a
forbidden pair whose components are each individually legal elsewhere
(e.g. `value_role_v1.cost` is legal at `(C1,output)` and at
`(C3,context)` but NOT at `(C3,output)`). A pair whose `check_id` and
`field` are each individually legal values but whose specific pairing is
not in the surface's `allowed_positions` fails with
`RULE_COVERAGE_POSITION_NOT_ALLOWED` (`COVERAGE_POSITION_NOT_ALLOWED_FOR_SURFACE`).

47 table-derived surfaces (one entry per facet family, concept family,
comparator sequence, EXCL pair, COMPLEMENT pair, condition operator, and
quantifier class -- `excl_v1.refundable_nonrefundable` is RETIRED under
v3) + 3 SYNTHETIC `value_role_v1.{cost,duration,limit}` measure-facet
value-role surfaces (renamed from the retired `units_v1.facet:*`
naming; `allowed_positions` = `{(C1,context),(C1,output),(C3,context)}`
only) + 18 nontable behavioral surfaces = 68. Every table-derived
surface's `allowed_positions` is `{C1,C3,C4} x {context,output}` (6
positions) -- table-derived surfaces are never legal C2 evidence. Of the
18 nontable surfaces: the seven `c2_*` surfaces are `{(C2,output)}`
only; `polarity_via_deny_trigger`, `polarity_via_negator`, and the seven
abstention surfaces share the same 6-position table-family set;
`contraction_expansion` carries that 6-position set plus `(C2,output)`
(7 positions); `abstain_interrogative_output` is `{C1,C3,C4} x {output}`
only (3 positions -- never context). One `?` item may evidence BOTH
`c2_interrogative` `(C2,output)` and `abstain_interrogative_output`
`((C1|C3|C4),output)` -- two independent surfaces, not a conflict.
Total allowed positions across the registry: 362
(`47*6 + 3*3 + 71 nontable positions`).

`check_coverage_registry_closure` requires the manifest's top-level key
set to equal the registry's key set EXACTLY -- a missing registry
surface and an extra undeclared surface both fail. `coverage_manifest_schema.json`
now mirrors this same closure at the SCHEMA level too (SAN-881 PASS
2B.1): the top level is a closed enumeration of the 68 registered
surface names, `additionalProperties: false`, so a manifest carrying a
retired or otherwise unregistered surface fails schema validation
directly. **Every required surface MUST carry genuine, nonempty
evidence; an empty evidence array is a schema violation, never a
documented gap.**

**SAN-881 PASS 2B.1-P honesty statement:** `validate_design.py`'s
executable coverage checks prove each evidence record's (item_id,
check_id, field) is PRODUCT-PRESENT and STATIC-COMPATIBLE with the
surface it claims -- never that the check genuinely executed or
consumed it -- the proof now DIFFERS by surface class.

The 50 IN-SCOPE surfaces (the 47 table-derived families + the 3
`value_role_v1` surfaces) are validated by a PRODUCT-LEVEL FOUR-CLAUSE
CONTRACT over the EPHEMERAL, TYPED, validator-local product-trace
substrate (`FieldProductTrace`, `FrameProductEvent`,
`PartialProductEvent`, `ProductTraceBundle`) built by pure read-only
replay of the pinned production extraction primitives -- it captures
exact per-field frame/partiality PRODUCTS (comparator folds and
location, condition marker folds/kind/force/formula, actual CONCEPT_v1
mappings, projection-normalized facet, deny-trigger/negator inputs and
resulting polarity, raw `Roles.value` spans, selected quantifier token
and class), differentially verified against production `extract_frames`
-- plus `CAPABILITY_MAP`, a CLOSED, reviewed STATIC compatibility
declaration of exactly 13 `(family, location) ->` legal `(check_id,
field)` position-set rows. `CAPABILITY_MAP` is a reviewed static
routing table, never a dynamically inferred consumption proof. The
four clauses, per evidence record:

1. **POSITION** -- `(check_id, field)` in the surface's own
   `SURFACE_REGISTRY.allowed_positions` (unchanged from Pass-1/2).
2. **PRODUCT PRESENT** -- the declared field's `FieldProductTrace(s)`
   contain the exact normalized product, located family-specifically:
   facets -- normalized `Frame.extent.facet` equals the surface facet;
   concept -- a conjunct-bound `(raw_fold, canonical_term)` mapping at a
   condition or requirement location; comparators -- a
   `ComparatorProductEvent` with the surface's exact folds at a
   map-consumable location; excl/complement -- per the JOINT rules
   below; condition_operators -- a `ConditionProductEvent` with the
   exact marker folds, kind, and force; quant -- the selected token's
   class matches (`quant_v1.abstain` uses the `PER_HIT_ABSTAIN` rule
   below); value_role -- `classify_value_span_text` over the exact raw
   value span, matching the surface's facet.
3. **NON-PARTIAL** -- every `FieldProductTrace` belonging to the
   declared field is nonpartial (for context, ALL separate
   context-source traces, never concatenated). `quant_v1.abstain` is
   the SOLE exception, and requires ALL of: an exact `PER_HIT_ABSTAIN`
   event carrying the selected abstain-class quant token; that event's
   own `cause` equals the production `UNEXTRACTABLE` cause (a
   `PER_HIT_ABSTAIN`-shaped event raised for a DIFFERENT cause, e.g.
   `malformed_mention` or `condition_undecidable`, does not credit); AND
   the owning field's AGGREGATE trace is itself partial (checked
   positively, never merely assumed). NO other partial event credits
   any of the 50 surfaces.
4. **CHECK-APPLICABLE** -- `CAPABILITY_MAP[(family, location)]`
   contains `(check_id, field)`.

OWNERSHIP QUALIFIERS apply on top of the four clauses: every
frame-backed product requires an assertive `FrameProductEvent` owner; a
context owner used for ordinary C1/C4 coverage must be authoritative
tier_1/tier_2; a C3/context product owner must occur in
`trusted_obligations`' own `source_frame_identities`; a C3/output
condition or requirement claimed as evidence must have a matching
`EvidenceProductEvent`; other C3/output frame routes require at least
one successfully extracted trusted obligation; comparator credit
requires nonempty `parsed_intervals`; value_role credit requires
nonempty `value_intervals` plus exact-span classifier success.
EXCL_v1/COMPLEMENT_v1 require JOINT evidence, never a one-record rule:
EXCL requires TWO DISTINCT assertive frame owners whose
`FrameProductEvent.modifiers` carry the two normalized pair members in
a SAME-RELATION modifier object set (`excl_candidates` may prefilter
but cannot itself prove the relation -- the joint check inspects
`.modifiers` directly); COMPLEMENT requires each pair member as an
exact SINGLETON `TermAtom` inside a STORED condition/requirement Bool
formula (a flattened complement-candidate list alone is insufficient);
neither ever concatenates context and output.

**SAN-881 PASS 2B.1b** upgraded the 18 NONTABLE surfaces to
product-honest, event-local proof, split into three groups.

- **GROUP A** (the seven `c2_*` surfaces: `c2_definitive_hit`,
  `c2_negated_definitive`, `c2_hedge_in_window`,
  `c2_hedge_outside_window_or_absent`, `c2_negated_hedge`,
  `c2_window_boundary`, `c2_interrogative`) is BUNDLE-FREE: it consumes
  `reference.checks.scan_c2_lexical` / `has_governed_question` -- the
  SAME shared helpers `checks.C2` and `evaluate.py`'s own Stage W1 gate
  consume (extracted so there is no independent calibration-side
  replica of definitive/hedge/window/negation/interrogative handling)
  -- over the declared field's own re-tokenized text; it never builds a
  `ProductTraceBundle`. An AST/name-reference test proves
  `_check_nontable_surface_evidence` (Group A's own dispatcher) still
  never references the product-trace substrate or `CAPABILITY_MAP`.
- **GROUPS B** (`polarity_via_deny_trigger`, `polarity_via_negator`,
  `contraction_expansion`) **and C** (`abstain_interrogative_output`
  and the remaining seven abstention surfaces) ARE
  `ProductTraceBundle`-backed, EVENT-LOCAL evidence
  (`_check_nontable_bundle_backed_evidence`), sharing ONE Pass-B-wide
  bundle cache with the 50 in-scope surfaces below -- but reusing ONLY
  the ordinary ownership/nonpartial portion of the four-clause contract
  (`_pc_ownership_and_partiality_ok`); no nontable surface is EVER
  routed through `CAPABILITY_MAP`, which has no nontable rows. Group B
  reads `FrameProductEvent.is_deny` / `negator_raw` (an IDENTITY check,
  never truthiness -- a contraction-generated negator's own raw text is
  `""`, empty but not `None`) / a genuine tokenizer-verified contraction
  occurrence. Group C requires a mechanism-specific textual detector and
  a PINNED `(PartialStage, cause)` `PartialProductEvent` pair to be
  found within the SAME `FieldProductTrace`/source AND sentence
  (`PER_HIT_ABSTAIN` mechanisms additionally corroborated within that
  hit's own reconstructed production structural segment, without
  extending `ProductTrace`), and never inherits frame trust qualifiers.

The five `_contains_*` lexical helper functions, `_word_present`,
`_field_text`, and the ELEVEN Group B/C handler expressions inside
`_predicate_nontable` itself remain **BYTE-UNCHANGED** -- only Group
A's seven handler expressions were rewritten to call the shared C2
helpers. **SAN-881 PASS 2B.1b-FIX2** (below) later made the dispatch
around those eleven expressions LAZY, so they are now
LEGACY-UNREACHABLE-FROM-RUNTIME rather than merely unchanged -- see
that section.

**SAN-881 PASS 2B.1b-FIX** (bounded correction pass over the 2B.1b
delta) corrected four defects surfaced against that upgrade. (1) The
six lexical `c2_*` surfaces now honor `checks.C2`'s OWN row-0 partial
gate: a governed-question `item_text` earns credit ONLY via
`c2_interrogative`, and `scan_c2_lexical` is never invoked for it --
mirroring production's own short-circuit exactly (`evaluate.py` passes
`has_governed_question(out_text)` as `C2`'s `out_partial`, which
returns `NOT_EVALUATED` before the scan ever runs); the `(C2, output)`
contraction route rejects the same way. (2) `scan_c2_lexical`'s
window-clipping flags are now derived from the field-clamped raw
`W_HEDGE` bound versus the production-segment-clamped bound, so a
comma/semicolon/colon/paren segment boundary that genuinely shortens
the window is correctly flagged (not only a because/since boundary
token); `scan_c2_lexical` itself now STREAMS in production via an
optional `sink` callback -- no per-definitive fact record is built at
all on the no-sink (production `C2`) path, closing a proportional
memory-allocation regression; calibration supplies its own sink and
captures exactly the facts it needs. (3) `_nb_hit_segment_text`'s
forward extension across a segment boundary is narrowed to a comma
DIRECTLY flanked by NUMBER tokens on both sides (a malformed numeral's
own internal comma) -- it no longer absorbs an arbitrary LATER
comma/semicolon segment. (4) The `abstain_malformed_value`/
`abstain_approx_value`/`abstain_e15_nested_adjunct_chain`/
`abstain_san894_trigger_in_adjunct`/`abstain_san895_non_ascii_digits`
mechanisms are no longer best-effort substring/distinct-token text
detectors: each is now a conservative, EXACT production-token
predicate (exact `APPROX_V1` fold identity; exact NUMBER/PCT100 token
counts; production's own pairwise consecutive-adjunct-preposition rule
-- REPEATED occurrences of the same preposition included, with the
literal `"and <preposition>"` exemption honored; the longest
`TRIGGER_INDEX` match inside the ACTUAL adjunct group, with NO article
requirement; and a host-UCD non-ASCII-digit character guard --
`ch.isdigit() and not ASCII 0-9` -- never a hand-enumerated Unicode
range table). `abstain_interrogative_output` and
`abstain_e13_nonterminating_punctuation` now credit on their own
uniquely-identifying `(PartialStage, cause)` pair alone, with no
further textual corroboration run (each is the SOLE Group C surface
pinned to its own pair). `abstain_san895_non_ascii_digits` now accepts
a CLOSED two-pair set -- `(TOTAL_SPAN_UNCONSUMED, None)` (sentence-
level, no hit) and `(PER_HIT_ABSTAIN, "unextractable")` (when the digit
is a measure-facet hit's own sole value candidate and rule 8 valency
enforcement aborts extraction) -- rather than the single pair the prior
pass pinned.

**SAN-881 PASS 2B.1b-FIX2** (bounded correction pass over the
2B.1b-FIX delta) corrected three further live Group-C misattribution
paths plus a dispatch-truthfulness fix, without reopening the
architecture. (1+2) `_nb_hit_segment_text` is RETIRED from the
`abstain_malformed_value`/`abstain_approx_value`/
`abstain_san895_non_ascii_digits` per-hit classification role -- it
models a STRUCTURAL SEGMENT (`T.structural_punctuation`-delimited), a
DIFFERENT concept from production's own value-role search region
(`extraction.py` step 7: the complete post-trigger region through
sentence end or the first condition marker, never comma/semicolon-
bounded). `_nb_classify_hit_value_region` replaces it: ONE
validator-local replay of that EXISTING production order -- establish
the hit actually reaches the measure-value branch (rules 1-3 each
return before rule 7 ever runs, an orphan-COORD hit included); the
value region runs from the trigger's end through sentence end or the
first condition marker; MORE than one `NUMBER`/`PCT100` token in that
region is malformed; EXACTLY one, immediately preceded by an EXACT
`APPROX_V1` token, is approximate; ZERO candidates may credit
SAN-895's `PER_HIT_ABSTAIN`/`unextractable` arm ONLY when the hit's own
non-value valencies also pass and a non-ASCII digit lies INSIDE that
exact value region. (3) `_nb_adjunct_group_scan` now replays EVERY hit
in a sentence, IN ORDER, from the first hit through the target hit,
carrying `prev_subject_span` forward and applying production's EXACT
COORD reject/splice step (`extraction.py` 769-773) BEFORE ever scanning
subject/object adjunct groups -- an orphan COORD hit (no valid prior
subject) is REJECTED, never credits `e15`/SAN-894, and never poisons a
LATER hit's own eligibility (a rejected hit leaves `prev_subject_span`
unchanged, exactly like production). (4) `_predicate_nontable`'s own
dispatch is now LAZY/early-returning: a registered Group A (`c2_*`)
name returns before any of the eleven legacy Group B/C handler
expressions are ever constructed -- the pre-fix body built ONE eager
`handlers` dict literal spanning all eighteen keys, so a Group-A call
ALSO silently evaluated (and discarded the result of) the five legacy
`_contains_*` helpers every time, correct only by accident. See "Group
A/B/C nontable evidence" above for the corrected LEGACY-UNREACHABLE-
FROM-RUNTIME wording this fix motivated.

Runtime validation proves parsed-product presence, ownership and
partiality qualifiers, declared-field integrity, and compatibility
with a reviewed static routing map. It does not prove internal branch
reach, causality, or per-corpus-item execution. Phase B evaluator
runs remain the authority for measured behavior.

No `CheckConsumptionTrace` class exists, and none is planned: a genuine
internal-branch-consumption-tracing architecture (identity comparison
and disposition for C1; activation screening or source-conflict
disposition for C3 context, bound evidence for C3 output;
structural-prefilter survival and modifier/domain comparison for C4
context, engagement/preservation comparison for C4 output; the selected
token causing the partiality AND gating the credited check for
`quant_v1`; runtime monkeypatching of production code; event
vocabulary; locks; phase state; call attribution; replay of a check's
own branch against a real outcome) was proposed and **REJECTED** -- this
pass achieves product-level, not consumption-level, assurance, and that
boundary is permanent, not a staging step toward consumption tracing.
EXCL/COMPLEMENT surfaces' JOINT proof spans all evidence for a
`(surface, item_id, check_id)`: BOTH pair members must be found, each
via a genuine parsed product, possibly across multiple records and
fields (never concatenated). Every trace this validator builds is
ephemeral and process-local to one validation invocation: no trace, no
evaluator outcome, and no rate derived from either is ever persisted to
an artifact, published, or used to gate anything -- see "No-evaluator-
before-freeze rule" above for the pinned boundary this pass stays
inside. Future expansion to close specific gaps requires fresh holdout
items AND a reviewed registry change -- no silent table-driven
widening.

### Reveal-verification ledger: literal six-tuple pin

`reveal_verification_ledger.json`'s `entries` array contains EXACTLY six
records, in this EXACT index order (SAN-881 Phase-A CORRECTION PASS 1):
`schemas/reveal_verification_ledger_schema.json` pins `minItems`/`maxItems`
6 AND pins each index position via `prefixItems` (its `$id` ends
`/v2.json`, and `corpus_version` is `const: 2`); `validate_design.LEDGER_CANONICAL_ORDER`
is the single source of truth for this order, and
`validate_design.LEDGER_PINNED_TUPLES` (the order-blind SET form, used
for the tuple-membership pre-check) is derived from it:

| index | artifact_name | envelope | verified_stage |
|---|---|---|---|
| 1 | `labels_author_semantic.json` | `author` | `semantic` |
| 2 | `labels_reviewer_semantic.json` | `reviewer_semantic` | `semantic` |
| 3 | `labels_author_contract.json` | `author` | `contract` |
| 4 | `design_metadata.json` | `author` | `contract` |
| 5 | `coverage_manifest.json` | `author` | `contract` |
| 6 | `labels_reviewer_contract.json` | `reviewer_contract` | `contract` |

`validate_design.build_reveal_verification_ledger` EMITS this order
DIRECTLY (it does not sort by envelope/artifact_name -- that ordering is
different from the pinned canonical sequence above). `validate_design.check_reveal_verification_ledger`
checks the tuple SET first (empty/short/tuple-mismatched fails outright),
THEN the exact ORDER (a reversed or otherwise permuted ledger whose
tuple set is otherwise correct also fails outright, before any
per-entry cross-check), THEN cross-checks EVERY entry's artifact name,
envelope, stage, commitment hex, byte length, context hash, and corpus
version against the corresponding commitment envelope.
