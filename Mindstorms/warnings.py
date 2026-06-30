from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List


_SCENARIO_FALLBACK_RE = re.compile(
    r"apply_to_all\(\): No scenario internal data for Scenario/(?P<scenario>[^;]+);"
)
_SCENARIO_UPDATES_IGNORED_RE = re.compile(
    r"apply_to_all\(\): Scenario internal data for Scenario/(?P<scenario>\S+) is unavailable;"
)


def summarize_warning_text(text: str) -> List[Dict[str, Any]]:
    counts: Counter[str] = Counter()
    scenarios: Dict[str, set[str]] = {}

    for match in _SCENARIO_FALLBACK_RE.finditer(text):
        code = "SCENARIO_INTERNAL_DATA_FALLBACK"
        counts[code] += 1
        scenarios.setdefault(code, set()).add(match.group("scenario"))

    for match in _SCENARIO_UPDATES_IGNORED_RE.finditer(text):
        code = "SCENARIO_INTERNAL_UPDATES_SKIPPED"
        counts[code] += 1
        scenarios.setdefault(code, set()).add(match.group("scenario"))

    summaries: List[Dict[str, Any]] = []
    for code in sorted(counts):
        if code == "SCENARIO_INTERNAL_DATA_FALLBACK":
            message = (
                "No scenario internal data was available for some scenarios; "
                "main internal data was used as feature-engineering context."
            )
        else:
            message = (
                "Scenario internal updates were skipped because scenario "
                "internal data was unavailable."
            )

        summaries.append(
            {
                "code": code,
                "count": counts[code],
                "severity": "info",
                "fatal": False,
                "message": message,
                "scenarios": sorted(scenarios.get(code, set())),
            }
        )

    return summaries
