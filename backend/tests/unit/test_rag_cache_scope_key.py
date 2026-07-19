from types import SimpleNamespace

from app.services.retrieval_scope_context import RetrievalScopeContext


def test_cache_scope_fingerprint_prevents_cross_scope_reuse():
    admin = RetrievalScopeContext.from_scope(SimpleNamespace(public_dict=lambda: {"permission": "admin", "docs": ["a"]}))
    viewer = RetrievalScopeContext.from_scope(SimpleNamespace(public_dict=lambda: {"permission": "viewer", "docs": ["a"]}))
    assert admin.fingerprint != viewer.fingerprint
