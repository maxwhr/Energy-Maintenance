from scripts.task25g_audits import wheel_tag_allowed


def test_wheel_tag_policy_accepts_only_universal_or_loongarch():
    assert wheel_tag_allowed("anyio-4.13.0-py3-none-any.whl")
    assert wheel_tag_allowed("pydantic_core-2.46.4-cp312-cp312-manylinux_loongarch64.whl")
    assert not wheel_tag_allowed("pydantic_core-2.46.4-cp312-cp312-win_amd64.whl")
    assert not wheel_tag_allowed("pydantic_core-2.46.4-cp312-cp312-manylinux_x86_64.whl")
    assert not wheel_tag_allowed("pydantic_core-2.46.4-cp312-cp312-manylinux_aarch64.whl")

