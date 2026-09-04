import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class HyperFramesCheckResult:
    """Structured result returned by the HyperFrames validation gate."""

    ok: bool
    data: dict[str, Any]
    return_code: int
    raw_stdout: str = ""
    raw_stderr: str = ""

    @property
    def failed(self) -> bool:
        return not self.ok

    def save(self, path: str | Path) -> None:
        """Save the complete HyperFrames result as JSON."""
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        output_path.write_text(
            json.dumps(self.data, indent=2),
            encoding="utf-8",
        )


class HyperFramesValidator:
    """
    Runs the HyperFrames composition gate.

    The gate command is intentionally kept here rather than in the
    orchestrator so the pipeline only needs to ask:

        result = validator.check(composition_dir)

    """

    def __init__(
        self,
        command: str = "npx",
        timeout: int = 120,
    ) -> None:
        self.command = command
        self.timeout = timeout

    def check(
        self,
        composition_dir: str | Path,
    ) -> HyperFramesCheckResult:
        """
        Run:

            npx hyperframes check <composition_dir> --json

        Returns:
            HyperFramesCheckResult

        Raises:
            FileNotFoundError: if the composition directory doesn't exist.
            RuntimeError: if HyperFrames cannot be started.
            TimeoutError: if the gate exceeds the timeout.
        """

        composition_path = Path(composition_dir)

        if not composition_path.exists():
            raise FileNotFoundError(
                f"Composition directory does not exist: {composition_path}"
            )

        if not composition_path.is_dir():
            raise ValueError(
                f"Composition path is not a directory: {composition_path}"
            )

        command = [
            self.command,
            "hyperframes",
            "check",
            str(composition_path),
            "--json",
        ]

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )

        except FileNotFoundError as exc:
            raise RuntimeError(
                "Could not execute 'npx'. "
                "Make sure Node.js and npm are installed."
            ) from exc

        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"HyperFrames check timed out after {self.timeout} seconds."
            ) from exc

        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()

        data = self._parse_json(stdout)

        # HyperFrames normally exposes the authoritative status through
        # the JSON "ok" field. If JSON cannot be parsed, the check failed.
        if data is None:
            data = {
                "ok": False,
                "error": "HyperFrames returned non-JSON output.",
                "return_code": completed.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }

        ok = bool(data.get("ok", False))

        # A non-zero process exit code must never be interpreted as success.
        if completed.returncode != 0:
            ok = False
            data.setdefault("ok", False)

        return HyperFramesCheckResult(
            ok=ok,
            data=data,
            return_code=completed.returncode,
            raw_stdout=stdout,
            raw_stderr=stderr,
        )

    @staticmethod
    def _parse_json(stdout: str) -> dict[str, Any] | None:
        """Parse HyperFrames JSON output safely."""

        if not stdout:
            return None

        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            return None

        if not isinstance(parsed, dict):
            return None

        return parsed


def run_hyperframes_check(
    composition_dir: str | Path,
    output_path: str | Path | None = None,
    timeout: int = 120,
) -> HyperFramesCheckResult:
    """
    Convenience function for one HyperFrames check.

    Example:

        result = run_hyperframes_check(
            "runs/test_composition",
            "runs/test_composition/check.json",
        )

        if result.ok:
            print("PASS")
    """

    validator = HyperFramesValidator(timeout=timeout)

    result = validator.check(composition_dir)

    if output_path is not None:
        result.save(output_path)

    return result