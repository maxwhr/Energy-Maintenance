from __future__ import annotations

import re


def keyword_hit_count(text: str, keyword: str) -> int:
    if not text or not keyword:
        return 0
    return len(re.findall(re.escape(keyword.lower()), text.lower()))
