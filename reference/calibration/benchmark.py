#!/usr/bin/env python3
"""SAN-881 Phase-B benchmark. NEVER executed against the corpus in Phase
A. TIMING is Python-reference-only: cross-SDK claims made elsewhere in
this project are about semantic parity (byte-identical outcomes), never
performance, and the timed pass never touches the TypeScript reference.
INTEGRITY REPLAY (SAN-881 PASS 2C.2), by contrast, executes BOTH SDKs --
before any timing pass, benchmark reruns the verified frozen bundle's
own projection through measure.run_dual_harness (Python AND TypeScript)
to independently reconstruct outcomes.json and rates.json from a
genuine re-execution, never trusting either file's self-declared
content. See build_benchmark_json's `timing_python_reference_only` /
`integrity_replay_sdks` posture keys.

Preconditions (checked BEFORE any timing pass): FREEZE-MANIFEST.json
exists; the results directory EXACTLY corresponding to its current
freeze hash exists (results/<freeze_manifest_sha256>/, never a
caller-supplied path); outcomes.json exists with exactly 640 outcomes
and belongs to that SAME freeze (freeze_manifest_hash match, bound to
the RAW outcomes.json file bytes -- never a reserialization); the
current git HEAD matches outcomes.json's runner_git_commit and the
tracked worktree is clean; rates.json reports a nonempty, exactly-nine
gate map with ALL NINE hard gates passed; and (SAN-881 PASS 2C.2) a
fresh replay of the verified frozen bundle through BOTH harnesses
reconstructs outcomes.json and rates.json BYTE-IDENTICALLY -- closing
header tampering, per-record tampering, and forged gate values alike,
since gate acceptance uses ONLY the RECONSTRUCTED rates object, never a
caller-supplied one. Refuses to run otherwise -- a benchmark over an
evaluator that failed a correctness gate, or over a stale/foreign/
tampered result set, is not a benchmark, it's noise.

Method: persistent process, corpus preloaded once; 10 warm-up passes +
30 timed passes over all 160 items in fixed id order (cal:000..cal:159);
time.monotonic_ns() per item. Nearest-rank percentiles, pinned: sort
ascending, 1-indexed rank = ceil(p/100 * N); per-item N = 30 samples
(one pass's worth of an item across all timed passes); per-pass N = 30
totals (one sample per pass). P50/P95/max reported for both views.
Envelope-breach count is COPIED from the deterministic outcomes.json
(zero_envelope_breaches_640 gate), never independently measured during a
timing pass -- timing runs are excluded from every determinism gate.
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

WARMUP_PASSES = 10
TIMED_PASSES = 30

EXPECTED_OUTCOME_COUNT = 640
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


class BenchmarkRefused(RuntimeError):
    pass


def nearest_rank_percentile(sorted_samples: list[int], p: float) -> int:
    """sorted_samples ascending; 1-indexed rank = ceil(p/100 * N)."""
    n = len(sorted_samples)
    if n == 0:
        raise ValueError("cannot compute a percentile over zero samples")
    rank = math.ceil((p / 100.0) * n)
    rank = max(1, min(n, rank))
    return sorted_samples[rank - 1]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


_REQUIRED_OUTCOME_RECORD_KEYS = {"id", "item_id", "check_id", "outcome", "outcome_reason", "severity", "advisory"}


def _reject_duplicate_or_malformed_outcomes(outcomes_list: list) -> list[str]:
    """rejects duplicate/malformed 640-record outcome sets (SAN-881
    Phase-A correction): every record must carry exactly the expected
    keys, and every `id` must be unique -- a benchmark run over a
    silently-duplicated or malformed outcome set is not measuring what it
    claims to measure."""
    failures: list[str] = []
    seen_ids: set = set()
    for idx, rec in enumerate(outcomes_list):
        if not isinstance(rec, dict) or set(rec.keys()) != _REQUIRED_OUTCOME_RECORD_KEYS:
            failures.append(f"outcomes.json[{idx}]: malformed outcome record shape")
            continue
        rec_id = rec.get("id")
        if rec_id in seen_ids:
            failures.append(f"outcomes.json[{idx}]: duplicate outcome id {rec_id!r}")
        seen_ids.add(rec_id)
    return failures


def _rerun_full_freeze_verification(freeze_manifest_path: Path, cal_dir: Path, repo_root: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """RERUNS full freeze verification itself (SAN-881 Phase-A
    correction), by calling measure.verify_frozen_bundle -- the single,
    shared, centralized frozen-bundle verifier (SAN-881 PASS 2C.1) --
    EXACTLY ONCE, fresh from disk. benchmark.py trusts nothing measure.py
    already checked at measurement time; it checks it all again, now, at
    benchmark time, against the artifacts actually on disk. This module
    carries NO JSON-Schema, labeling-context, reveal-ledger, or
    population-invariant implementation of its own -- verify_frozen_bundle
    (which necessarily lives in measure.py) is the ONLY place that logic
    exists.

    SAN-881 PASS 2C.2: returns `(verified_bundle, failures)` -- the SAME
    dict verify_frozen_bundle itself returns (manifest, corpus_inputs,
    evaluation_profile, design, labels_frozen, coverage_manifest) on
    success, `None` on failure -- so callers can reuse the ALREADY-
    VERIFIED corpus/labels/design/manifest for replay integrity and rate
    recomputation without ever re-reading or re-verifying them a second
    time. verify_frozen_bundle is STILL called EXACTLY ONCE."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from reference.calibration import measure as ms  # noqa: E402

    try:
        verified = ms.verify_frozen_bundle(freeze_manifest_path, cal_dir, repo_root)
    except (ms.FreezeGateRefused, ms.InfrastructureFailure) as exc:
        return None, [str(exc)]
    return verified, []


def _load_result_document_or_fail(path: Path, label: str) -> dict[str, Any]:
    """SAN-881 PASS 2C.2: fixed-name helper for outcomes.json/rates.json.
    Routes through measure._load_json_or_fail (the SAME fixed-name
    helper measure.py's own fail-closed file-read boundary uses) so a
    directory in place of the file, invalid UTF-8, and invalid JSON all
    translate into BenchmarkRefused -- with a canonical artifact-name-
    only message, never an absolute path -- instead of a raw OSError /
    UnicodeDecodeError / JSONDecodeError escaping straight through. Also
    enforces the top-level type: a syntactically valid JSON document
    whose root is not an object (e.g. `[]`) would otherwise reach a
    `.get(...)` call downstream and raise a raw AttributeError."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from reference.calibration import measure as ms  # noqa: E402

    doc = ms._load_json_or_fail(path, label, BenchmarkRefused)
    if not isinstance(doc, dict):
        raise BenchmarkRefused(f"{label} is not a JSON object at its top level")
    return doc


def _verify_replay_and_recompute_rates(
    verified_bundle: dict[str, Any], freeze_hash: str, runner_git_commit: str,
    outcomes_path: Path, rates_path: Path,
) -> dict[str, Any]:
    """SAN-881 PASS 2C.2: reconstructs the COMPLETE expected outcomes.json
    and rates.json from a FRESH replay of the verified frozen bundle --
    rebuilds the projection, reruns BOTH harnesses via
    measure.run_dual_harness (the ONLY direct-evaluator-adjacent call
    this module makes beyond its existing Python-only timing pass, and
    it is a subprocess harness invocation, never a direct `evaluate()`
    call), joins the VERIFIED frozen labels via measure.join_labels, and
    recomputes rates via measure.compute_rates -- benchmark.py NEVER
    duplicates metric or gate logic. Compares the CANONICAL bytes of
    each reconstruction against the STORED raw file bytes on disk: this
    closes header tampering, per-record tampering, and forged gate
    values alike, since ANY divergence from a genuine replay fails the
    comparison regardless of what the stored files self-declare. Returns
    the reconstructed, freeze/outcomes-bound rates object -- gate
    acceptance downstream uses ONLY this RECONSTRUCTED object, never a
    caller-supplied one."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from reference.calibration import measure as ms  # noqa: E402

    corpus_inputs = verified_bundle["corpus_inputs"]
    labels_frozen = verified_bundle["labels_frozen"]
    design = verified_bundle["design"]
    manifest = verified_bundle["manifest"]
    design_by_id = {it["item_id"]: it for it in design["items"]}

    projection = ms.build_projection(corpus_inputs)
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        try:
            python_bytes, typescript_bytes, python_results, _typescript_results = ms.run_dual_harness(projection, workdir)
        except (ms.InfrastructureFailure, ms.FreezeGateRefused) as exc:
            raise BenchmarkRefused(f"replay of the frozen bundle failed: {exc}") from exc

    joined = ms.join_labels(python_results, labels_frozen)
    reconstructed_rates = ms.compute_rates(
        joined, design_by_id, python_output_bytes=python_bytes, typescript_output_bytes=typescript_bytes)

    expected_outcomes = {
        "freeze_manifest_hash": freeze_hash,
        "component_hashes": manifest,
        "record_count": len(joined),
        "python_output_sha256": hashlib.sha256(python_bytes).hexdigest(),
        "typescript_output_sha256": hashlib.sha256(typescript_bytes).hexdigest(),
        "runner_git_commit": runner_git_commit,
        "measure_py_sha256": hashlib.sha256(Path(ms.__file__).read_bytes()).hexdigest(),
        "outcomes": [{"id": r["id"], "item_id": r["item_id"], "check_id": r["check_id"],
                      "outcome": r["outcome"], "outcome_reason": r["outcome_reason"],
                      "severity": r["severity"], "advisory": r["advisory"]} for r in joined],
    }
    expected_outcomes_bytes = ms.canonical_json_bytes(expected_outcomes)
    actual_outcomes_bytes = outcomes_path.read_bytes()
    if expected_outcomes_bytes != actual_outcomes_bytes:
        raise BenchmarkRefused(
            "outcomes.json does not match the reconstructed replay of the frozen bundle (replay "
            "integrity failure -- the stored outcomes do not correspond to a genuine re-execution "
            "of both harnesses over the verified frozen corpus and labels)"
        )

    expected_rates = {
        **reconstructed_rates,
        "freeze_manifest_sha256": freeze_hash,
        "outcomes_sha256": hashlib.sha256(actual_outcomes_bytes).hexdigest(),
    }
    expected_rates_bytes = ms.canonical_json_bytes(expected_rates)
    actual_rates_bytes = rates_path.read_bytes()
    if expected_rates_bytes != actual_rates_bytes:
        raise BenchmarkRefused(
            "rates.json does not match the rates recomputed via measure.compute_rates over the "
            "verified replay (rates recomputation failure -- the stored gate/metric values do not "
            "correspond to a genuine recomputation from the frozen bundle)"
        )

    return expected_rates


def check_preconditions(results_root: Path, freeze_manifest_path: Path, repo_root: Path | None = None) -> dict[str, Any]:
    if repo_root is None:
        repo_root = REPO_ROOT
    if not freeze_manifest_path.exists():
        raise BenchmarkRefused("FREEZE-MANIFEST.json does not exist")
    freeze_hash = _sha256_file(freeze_manifest_path)

    results_dir = results_root / freeze_hash
    outcomes_path = results_dir / "outcomes.json"
    rates_path = results_dir / "rates.json"
    if not outcomes_path.exists():
        raise BenchmarkRefused(f"outcomes.json does not exist under the current freeze-hash results directory ({freeze_hash}) -- run measure.py first")
    if not rates_path.exists():
        raise BenchmarkRefused(f"rates.json does not exist under the current freeze-hash results directory ({freeze_hash}) -- run measure.py first")

    outcomes = _load_result_document_or_fail(outcomes_path, "outcomes.json")
    rates = _load_result_document_or_fail(rates_path, "rates.json")

    # Binds to the RAW outcomes.json bytes hash -- never a reserialization.
    outcomes_bytes_hash = _sha256_file(outcomes_path)
    if outcomes.get("freeze_manifest_hash") != freeze_hash:
        raise BenchmarkRefused(
            f"outcomes.json belongs to a different freeze (outcomes says {outcomes.get('freeze_manifest_hash')}, "
            f"current FREEZE-MANIFEST.json hashes to {freeze_hash})"
        )
    if rates.get("freeze_manifest_sha256") != freeze_hash:
        raise BenchmarkRefused("rates.json freeze_manifest_sha256 does not match the current FREEZE-MANIFEST.json")
    if rates.get("outcomes_sha256") != outcomes_bytes_hash:
        raise BenchmarkRefused("rates.json outcomes_sha256 does not match the raw bytes of outcomes.json on disk")

    # SAN-881 PASS 2C.2-FIX (defect 1): both nested members are proven to
    # be the type len/iteration/set/sorted/.items() require BEFORE any of
    # those operations ever runs -- an absent member (None from .get())
    # and a malformed one (wrong type) are rejected the SAME way, by the
    # SAME fixed, artifact-only diagnostic. `outcomes_list` and `gates`
    # are the validated locals; every downstream use in this function
    # reuses them rather than re-fetching the raw member from `outcomes`/
    # `rates`.
    outcomes_list = outcomes.get("outcomes")
    if not isinstance(outcomes_list, list):
        raise BenchmarkRefused("outcomes.json 'outcomes' field is missing or is not a list")
    n_outcomes = len(outcomes_list)
    if n_outcomes != EXPECTED_OUTCOME_COUNT:
        raise BenchmarkRefused(f"outcomes.json has {n_outcomes} outcomes, expected {EXPECTED_OUTCOME_COUNT}")

    gates = rates.get("gates")
    if not isinstance(gates, dict):
        raise BenchmarkRefused("rates.json 'gates' field is missing or is not an object")
    if not gates or set(gates) != set(PINNED_GATE_NAMES):
        raise BenchmarkRefused(f"rates.json gate map is empty or does not have exactly the nine pinned gates (got {sorted(gates)})")
    if not rates.get("nine_gates_passed"):
        failed = [k for k, v in gates.items() if not v]
        raise BenchmarkRefused(f"not all nine hard gates passed; refusing to benchmark. Failed: {failed}")
    # A tampered/inconsistent rates.json could carry nine_gates_passed:
    # true while one underlying gate value is literally false (SAN-881
    # Phase-A correction) -- the flag alone is not the source of truth;
    # every one of the nine gate values must be LITERALLY true.
    if not all(gates.get(name) is True for name in PINNED_GATE_NAMES):
        literally_failed = [k for k in PINNED_GATE_NAMES if gates.get(k) is not True]
        raise BenchmarkRefused(f"rates.json nine_gates_passed is true but not every gate value is literally true; refusing to benchmark. Failed: {literally_failed}")

    runner_commit = outcomes.get("runner_git_commit")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True)
    if head.returncode != 0:
        raise BenchmarkRefused("could not resolve current git HEAD")
    current_head = head.stdout.strip()
    if runner_commit != current_head:
        raise BenchmarkRefused(
            f"current HEAD ({current_head}) does not match outcomes.json's runner_git_commit ({runner_commit}); "
            "benchmarking a different implementation than the one that produced these outcomes is refused"
        )
    status = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=no"], cwd=repo_root, capture_output=True, text=True)
    if status.returncode != 0 or status.stdout.strip():
        raise BenchmarkRefused("clean tracked implementation state is required before benchmarking")

    malformed = _reject_duplicate_or_malformed_outcomes(outcomes_list)
    if malformed:
        raise BenchmarkRefused("outcomes.json has duplicate/malformed outcome record(s):\n" + "\n".join(f"  - {f}" for f in malformed))

    verified_bundle, verification_failures = _rerun_full_freeze_verification(freeze_manifest_path, freeze_manifest_path.parent, repo_root)
    if verification_failures:
        raise BenchmarkRefused("full freeze re-verification failed:\n" + "\n".join(f"  - {f}" for f in verification_failures))

    # SAN-881 PASS 2C.2: replay integrity + rates recomputation -- the
    # LAST gate (most expensive: reruns both harnesses), after every
    # cheap, fast-failing structural sanity check above has already
    # passed. Gate acceptance downstream uses ONLY this RECONSTRUCTED
    # rates object, never the caller-supplied (on-disk) one.
    reconstructed_rates = _verify_replay_and_recompute_rates(
        verified_bundle, freeze_hash, current_head, outcomes_path, rates_path)

    return {
        "outcomes": outcomes, "rates": reconstructed_rates, "freeze_hash": freeze_hash,
        "results_dir": results_dir, "corpus_inputs": verified_bundle["corpus_inputs"],
    }


def run_timed_passes(corpus_ids_in_order: list[str], evaluate_one, warmup: int = WARMUP_PASSES, timed: int = TIMED_PASSES) -> dict[str, list[int]]:
    """evaluate_one(item_id) -> None (side-effect timed only). Returns
    {item_id: [ns_sample, ...]} with exactly `timed` samples per item,
    in fixed pass order."""
    for _ in range(warmup):
        for iid in corpus_ids_in_order:
            evaluate_one(iid)

    per_item: dict[str, list[int]] = {iid: [] for iid in corpus_ids_in_order}
    for _ in range(timed):
        for iid in corpus_ids_in_order:
            start = time.monotonic_ns()
            evaluate_one(iid)
            per_item[iid].append(time.monotonic_ns() - start)
    return per_item


def summarize(per_item: dict[str, list[int]]) -> dict[str, Any]:
    per_item_summary = {}
    for iid, samples in per_item.items():
        s = sorted(samples)
        per_item_summary[iid] = {
            "n": len(s),
            "p50_ns": nearest_rank_percentile(s, 50),
            "p95_ns": nearest_rank_percentile(s, 95),
            "max_ns": s[-1],
        }
    pass_totals = []
    n_items = len(per_item)
    n_passes = len(next(iter(per_item.values()))) if per_item else 0
    for pass_idx in range(n_passes):
        total = sum(per_item[iid][pass_idx] for iid in per_item)
        pass_totals.append(total)
    pass_totals_sorted = sorted(pass_totals)
    per_pass_summary = {
        "n": len(pass_totals_sorted),
        "p50_ns": nearest_rank_percentile(pass_totals_sorted, 50) if pass_totals_sorted else None,
        "p95_ns": nearest_rank_percentile(pass_totals_sorted, 95) if pass_totals_sorted else None,
        "max_ns": pass_totals_sorted[-1] if pass_totals_sorted else None,
    }
    return {"per_item": per_item_summary, "per_pass": per_pass_summary}


def machine_metadata() -> dict[str, Any]:
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "machine": platform.machine(),
    }


def build_benchmark_json(preconditions: dict[str, Any], timing_summary: dict[str, Any]) -> dict[str, Any]:
    envelope_breaches = sum(
        1 for r in preconditions["outcomes"]["outcomes"] if r["outcome_reason"] == "envelope_exceeded"
    )
    return {
        "freeze_manifest_hash": preconditions["freeze_hash"],
        "outcomes_hash": _sha256_file(preconditions["results_dir"] / "outcomes.json"),
        # SAN-881 PASS 2C.2: replaces the ambiguous "python_reference_
        # only" -- TIMING remains Python-only, but INTEGRITY REPLAY (see
        # check_preconditions -> _verify_replay_and_recompute_rates) now
        # executes BOTH SDKs. Two keys, stated precisely, never one
        # overloaded flag.
        "timing_python_reference_only": True,
        "integrity_replay_sdks": ["python", "typescript"],
        "warmup_passes": WARMUP_PASSES,
        "timed_passes": TIMED_PASSES,
        "corpus_item_count": len(timing_summary["per_item"]),
        "envelope_breach_count_from_outcomes": envelope_breaches,
        "timing": timing_summary,
        "machine": machine_metadata(),
        "excluded_from_determinism_gates": True,
    }


def main(argv: list[str] | None = None) -> int:
    results_root = HERE / "results"
    freeze_manifest_path = HERE / "FREEZE-MANIFEST.json"
    try:
        preconditions = check_preconditions(results_root, freeze_manifest_path)
    except BenchmarkRefused as exc:
        sys.stderr.write(f"BENCHMARK REFUSED: {exc}\n")
        return 2

    sys.path.insert(0, str(REPO_ROOT))
    from reference.evaluate import evaluate  # noqa: E402

    # SAN-881 PASS 2C.2: the ALREADY-VERIFIED corpus_inputs from
    # check_preconditions's own replay -- never a second, independent
    # re-read of corpus_inputs.json from disk (that used to let the
    # timed pass silently diverge from the corpus the integrity replay
    # just verified).
    corpus_inputs = preconditions["corpus_inputs"]
    corpus_ids = [r["id"] for r in corpus_inputs]
    by_id = {r["id"]: r for r in corpus_inputs}

    def evaluate_one(iid: str) -> None:
        rec = by_id[iid]
        fixture = {"output": rec["output"]}
        if "context_sources" in rec:
            fixture["context_sources"] = rec["context_sources"]
        else:
            fixture["context"] = rec["context"]
        evaluate(fixture)

    timing = run_timed_passes(corpus_ids, evaluate_one)
    summary = summarize(timing)
    out = build_benchmark_json(preconditions, summary)

    (preconditions["results_dir"]).mkdir(parents=True, exist_ok=True)
    (preconditions["results_dir"] / "benchmark.json").write_text(json.dumps(out, sort_keys=True, indent=2) + "\n")
    sys.stdout.write(f"benchmark.json written: {preconditions['results_dir'] / 'benchmark.json'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
