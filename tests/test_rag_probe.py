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
