from dataclasses import dataclass, field
from typing import Any


VALID_CATEGORIES = {
    "lint",
    "runtime",
    "layout",
    "motion",
    "contrast",
    "snapshots",
}


@dataclass
class ValidationIssue:
    """A normalized HyperFrames validation issue."""

    category: str
    code: str
    severity: str
    message: str
    selector: str | None = None
    time: float | None = None
    first_seen: float | None = None
    last_seen: float | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "selector": self.selector,
            "time": self.time,
            "firstSeen": self.first_seen,
            "lastSeen": self.last_seen,
            "details": self.details,
        }


def normalize_hyperframes_result(
    result: dict[str, Any],
) -> list[ValidationIssue]:
    """
    Convert a raw HyperFrames check result into normalized issues.

    Only actual errors and warnings are returned.
    Informational findings are intentionally ignored because they
    should not trigger automatic repair.
    """

    if not isinstance(result, dict):
        raise ValueError("HyperFrames result must be a dictionary.")

    issues: list[ValidationIssue] = []

    for category in VALID_CATEGORIES:
        section = result.get(category)

        if not isinstance(section, dict):
            continue

        findings = section.get("findings", [])

        if not isinstance(findings, list):
            continue

        for finding in findings:
            if not isinstance(finding, dict):
                continue

            severity = str(
                finding.get("severity", "")
            ).lower()

            # Only actionable validation problems should reach
            # the repair system.
            if severity not in {"error", "warning"}:
                continue

            issues.append(
                ValidationIssue(
                    category=category,
                    code=str(
                        finding.get("code", "unknown")
                    ),
                    severity=severity,
                    message=str(
                        finding.get("message", "Unknown validation issue.")
                    ),
                    selector=_optional_string(
                        finding.get("selector")
                    ),
                    time=_optional_float(
                        finding.get("time")
                    ),
                    first_seen=_optional_float(
                        finding.get("firstSeen")
                    ),
                    last_seen=_optional_float(
                        finding.get("lastSeen")
                    ),
                    details={
                        key: value
                        for key, value in finding.items()
                        if key not in {
                            "code",
                            "severity",
                            "message",
                            "selector",
                            "time",
                            "firstSeen",
                            "lastSeen",
                        }
                    },
                )
            )

    # Deterministic ordering is useful for both debugging and
    # reproducibility.
    return sorted(
        issues,
        key=lambda issue: (
            _category_priority(issue.category),
            _severity_priority(issue.severity),
            issue.code,
            issue.selector or "",
            issue.time if issue.time is not None else -1,
        ),
    )


def has_actionable_issues(
    result: dict[str, Any],
) -> bool:
    """Return True when errors or warnings require attention."""
    return bool(normalize_hyperframes_result(result))


def summarize_issues(
    issues: list[ValidationIssue],
) -> str:
    """Create a concise human-readable summary for logs/repair prompts."""

    if not issues:
        return "No actionable HyperFrames issues."

    lines = []

    for index, issue in enumerate(issues, start=1):
        location = ""

        if issue.selector:
            location += f" selector={issue.selector}"

        if issue.time is not None:
            location += f" time={issue.time}"

        lines.append(
            f"{index}. "
            f"[{issue.category}] "
            f"{issue.severity.upper()} "
            f"{issue.code}: "
            f"{issue.message}"
            f"{location}"
        )

    return "\n".join(lines)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None

    value = str(value).strip()

    return value or None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _category_priority(category: str) -> int:
    """
    Repair priority.

    Lint/runtime problems are more fundamental than visual issues.
    """

    priorities = {
        "lint": 0,
        "runtime": 1,
        "layout": 2,
        "motion": 3,
        "contrast": 4,
        "snapshots": 5,
    }

    return priorities.get(category, 99)


def _severity_priority(severity: str) -> int:
    return {
        "error": 0,
        "warning": 1,
    }.get(severity, 99)