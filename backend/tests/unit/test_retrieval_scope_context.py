from types import SimpleNamespace

from app.services.retrieval_scope_context import RetrievalScopeContext


def test_scope_fingerprint_changes_with_approval_allowlist():
    first = RetrievalScopeContext.from_scope(SimpleNamespace(public_dict=lambda: {"allowed": ["a"]}))
    second = RetrievalScopeContext.from_scope(SimpleNamespace(public_dict=lambda: {"allowed": ["b"]}))
    assert first.fingerprint != second.fingerprint
