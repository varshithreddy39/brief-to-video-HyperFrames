import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class MP4ValidationResult:
    """Result of validating a rendered MP4 file."""

    ok: bool
    path: str
    errors: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "path": self.path,
            "errors": self.errors,
            "metadata": self.metadata,
        }

    def save(self, path: str | Path) -> None:
        """Save the validation result as JSON."""
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        output_path.write_text(
            json.dumps(self.to_dict(), indent=2),
            encoding="utf-8",
        )


class MP4Validator:
    """
    Validates a rendered MP4 using ffprobe.

    Checks:
    - file exists
    - file is non-empty
    - ffprobe is available
    - video stream exists
    - width
    - height
    - frame rate
    - duration
    """

    def __init__(
        self,
        ffprobe_command: str = "ffprobe",
        timeout: int = 30,
    ) -> None:
        self.ffprobe_command = ffprobe_command
        self.timeout = timeout

    def validate(
        self,
        video_path: str | Path,
        expected_width: int | None = None,
        expected_height: int | None = None,
        expected_fps: int | float | None = None,
        expected_duration: float | None = None,
        duration_tolerance: float = 0.15,
    ) -> MP4ValidationResult:
        """
        Validate an MP4 file and optionally compare it against
        expected video properties.
        """

        path = Path(video_path)
        errors: list[str] = []

        # ---------------------------------------------------------
        # Basic filesystem validation
        # ---------------------------------------------------------

        if not path.exists():
            return MP4ValidationResult(
                ok=False,
                path=str(path),
                errors=[f"MP4 file does not exist: {path}"],
                metadata={},
            )

        if not path.is_file():
            return MP4ValidationResult(
                ok=False,
                path=str(path),
                errors=[f"MP4 path is not a file: {path}"],
                metadata={},
            )

        if path.stat().st_size == 0:
            return MP4ValidationResult(
                ok=False,
                path=str(path),
                errors=["MP4 file is empty."],
                metadata={},
            )

        if path.suffix.lower() != ".mp4":
            errors.append(
                f"Expected an .mp4 file, got: {path.suffix or 'no extension'}"
            )

        # ---------------------------------------------------------
        # Check ffprobe availability
        # ---------------------------------------------------------

        if shutil.which(self.ffprobe_command) is None:
            return MP4ValidationResult(
                ok=False,
                path=str(path),
                errors=[
                    f"'{self.ffprobe_command}' was not found in PATH."
                ],
                metadata={},
            )

        # ---------------------------------------------------------
        # Run ffprobe
        # ---------------------------------------------------------

        command = [
            self.ffprobe_command,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=index,codec_type,codec_name,width,height,r_frame_rate",
            "-of",
            "json",
            str(path),
        ]

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )

        except subprocess.TimeoutExpired:
            return MP4ValidationResult(
                ok=False,
                path=str(path),
                errors=[
                    f"ffprobe timed out after {self.timeout} seconds."
                ],
                metadata={},
            )

        except OSError as exc:
            return MP4ValidationResult(
                ok=False,
                path=str(path),
                errors=[
                    f"Could not execute ffprobe: {exc}"
                ],
                metadata={},
            )

        if completed.returncode != 0:
            error_message = completed.stderr.strip()

            return MP4ValidationResult(
                ok=False,
                path=str(path),
                errors=[
                    "ffprobe failed."
                    + (
                        f" {error_message}"
                        if error_message
                        else ""
                    )
                ],
                metadata={},
            )

        # ---------------------------------------------------------
        # Parse ffprobe output
        # ---------------------------------------------------------

        try:
            probe_data = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            return MP4ValidationResult(
                ok=False,
                path=str(path),
                errors=[
                    f"ffprobe returned invalid JSON: {exc}"
                ],
                metadata={},
            )

        streams = probe_data.get("streams", [])
        format_data = probe_data.get("format", {})

        if not isinstance(streams, list):
            streams = []

        video_streams = [
            stream
            for stream in streams
            if isinstance(stream, dict)
            and stream.get("codec_type") == "video"
        ]

        # ---------------------------------------------------------
        # Video stream validation
        # ---------------------------------------------------------

        if not video_streams:
            errors.append("No video stream found in MP4.")
            return MP4ValidationResult(
                ok=False,
                path=str(path),
                errors=errors,
                metadata={
                    "format": format_data,
                    "streams": streams,
                },
            )

        video = video_streams[0]

        width = _to_int(video.get("width"))
        height = _to_int(video.get("height"))

        fps = _parse_frame_rate(
            video.get("r_frame_rate")
        )

        duration = _to_float(
            format_data.get("duration")
        )

        codec = video.get("codec_name")

        # ---------------------------------------------------------
        # Required metadata validation
        # ---------------------------------------------------------

        if width is None:
            errors.append("Could not determine video width.")

        if height is None:
            errors.append("Could not determine video height.")

        if fps is None or fps <= 0:
            errors.append("Could not determine a valid frame rate.")

        if duration is None or duration <= 0:
            errors.append("Could not determine a valid duration.")

        # ---------------------------------------------------------
        # Expected dimensions
        # ---------------------------------------------------------

        if expected_width is not None and width != expected_width:
            errors.append(
                f"Expected width {expected_width}, got {width}."
            )

        if expected_height is not None and height != expected_height:
            errors.append(
                f"Expected height {expected_height}, got {height}."
            )

        # ---------------------------------------------------------
        # Expected FPS
        # ---------------------------------------------------------

        if expected_fps is not None and fps is not None:
            if abs(fps - float(expected_fps)) > 0.01:
                errors.append(
                    f"Expected FPS {expected_fps}, got {fps:.3f}."
                )

        # ---------------------------------------------------------
        # Expected duration
        # ---------------------------------------------------------

        if (
            expected_duration is not None
            and duration is not None
        ):
            if abs(duration - expected_duration) > duration_tolerance:
                errors.append(
                    f"Expected duration approximately "
                    f"{expected_duration:.3f}s, "
                    f"got {duration:.3f}s."
                )

        metadata = {
            "codec": codec,
            "width": width,
            "height": height,
            "fps": fps,
            "duration": duration,
            "size_bytes": path.stat().st_size,
        }

        return MP4ValidationResult(
            ok=not errors,
            path=str(path),
            errors=errors,
            metadata=metadata,
        )


def validate_mp4(
    video_path: str | Path,
    expected_width: int | None = None,
    expected_height: int | None = None,
    expected_fps: int | float | None = None,
    expected_duration: float | None = None,
    duration_tolerance: float = 0.15,
    output_path: str | Path | None = None,
) -> MP4ValidationResult:
    """Convenience function for validating one MP4."""

    validator = MP4Validator()

    result = validator.validate(
        video_path=video_path,
        expected_width=expected_width,
        expected_height=expected_height,
        expected_fps=expected_fps,
        expected_duration=expected_duration,
        duration_tolerance=duration_tolerance,
    )

    if output_path is not None:
        result.save(output_path)

    return result


def _to_int(value: Any) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_frame_rate(value: Any) -> float | None:
    if not value:
        return None

    try:
        if isinstance(value, str) and "/" in value:
            numerator, denominator = value.split("/", 1)

            numerator = float(numerator)
            denominator = float(denominator)

            if denominator == 0:
                return None

            return numerator / denominator

        return float(value)

    except (TypeError, ValueError, ZeroDivisionError):
        return None