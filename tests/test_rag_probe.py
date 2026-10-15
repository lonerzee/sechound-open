"""Proves rag_probe: a scoped index holds isolation; an unscoped (shared) index
leaks across tenants and persists — the observed-effect the playbook requires."""
import rag_probe
from rag_probe import (
    InMemoryCorpus, classify_cross_context, classify_persistence,
    marker_present, probe_cross_context, probe_persistence,
)


# ---- pure classifiers -----------------------------------------------------

def test_cross_context_classifier():
    assert classify_cross_context("M1", ["... M1 ..."]) == "cross_context_leak"
    assert classify_cross_context("M1", ["unrelated"]) == "isolation_holds"


def test_persistence_classifier():
    assert classify_persistence("M1", ["M1"], ["M1"]) == "memory_persists"
    assert classify_persistence("M1", ["M1"], ["gone"]) == "no_persistence"
    assert classify_persistence("M1", ["none"], ["none"]) == "not_retrieved"


def test_marker_present_handles_none():
    assert marker_present("M", ["x", None, "yMz"]) is True
    assert marker_present("M", [None, ""]) is False


# ---- end-to-end: scoped index is safe, shared index is vulnerable ---------

def test_cross_context_isolation_holds_when_scoped():
    res = probe_cross_context(InMemoryCorpus(scoped=True),
                              planter="tenantA", reader="tenantB")
    assert res["verdict"] == "isolation_holds"


def test_cross_context_leak_when_shared_index():
    res = probe_cross_context(InMemoryCorpus(scoped=False),
                              planter="tenantA", reader="tenantB")
    assert res["verdict"] == "cross_context_leak"
    assert res["verdict"] in rag_probe.CONFIRM_GRADE
    # the planted marker must actually be the thing that surfaced
    assert res["marker"].startswith("RAGPROBE-")


def test_persistence_confirms_on_durable_store():
    res = probe_persistence(InMemoryCorpus(scoped=True), identity="tenantA")
    assert res["verdict"] == "memory_persists"
    assert res["verdict"] in rag_probe.CONFIRM_GRADE


# ---- a failed adapter must be inconclusive, never "safe" -----------------

def test_failed_ingest_is_inconclusive_not_isolation():
    # ingest command exits non-zero (broken auth/endpoint) → must NOT read as safe
    bad = rag_probe.CommandCorpus(ingest_cmd="false", query_cmd="true")
    res = probe_cross_context(bad, planter="tenantA", reader="tenantB")
    assert res["verdict"] == "inconclusive" and "error" in res


def test_failed_query_is_inconclusive():
    bad = rag_probe.CommandCorpus(ingest_cmd="true", query_cmd="false")
    res = probe_persistence(bad, identity="tenantA")
    assert res["verdict"] == "inconclusive"


def test_cross_context_positive_control_catches_noop_adapter():
    # commands succeed (rc 0) but retrieve nothing — the retrieval path is
    # unproven, so reader-absence must NOT read as isolation_holds.
    noop = rag_probe.CommandCorpus(ingest_cmd="true", query_cmd="true")
    res = probe_cross_context(noop, planter="tenantA", reader="tenantB")
    assert res["verdict"] == "inconclusive" and "positive control" in res["error"]


def test_not_retrieved_exits_inconclusive():
    assert rag_probe._emit({"check": "x", "verdict": "not_retrieved"}, True) \
        == rag_probe.INCONCLUSIVE_EXIT
