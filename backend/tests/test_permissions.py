import pytest
from fastapi import HTTPException

from app.core.dependencies import require_admin, require_roles


@pytest.mark.parametrize("role", ["admin", "expert", "engineer", "viewer"])
def test_each_supported_role_can_access_matching_route(make_user, role: str) -> None:
    user = make_user(username=f"{role}_permission_user", role=role)
    dependency = require_roles(role)
    assert dependency(user) is user


def test_viewer_cannot_access_admin_route(make_user) -> None:
    viewer = make_user(username="viewer_denied_user", role="viewer")
    with pytest.raises(HTTPException) as exc_info:
        require_roles("admin")(viewer)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == 40302


def test_require_admin_rejects_non_admin(make_user) -> None:
    expert = make_user(username="expert_denied_user", role="expert")
    with pytest.raises(HTTPException) as exc_info:
        require_admin(expert)
    assert exc_info.value.status_code == 403
