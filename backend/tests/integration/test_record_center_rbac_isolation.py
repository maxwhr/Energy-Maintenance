import inspect

from app.api.routes import record_center


def test_every_record_center_route_requires_current_user() -> None:
    source = inspect.getsource(record_center)
    assert source.count("Depends(get_current_user)") == 4
    assert "require_admin" not in source
    assert "require_roles" not in source

