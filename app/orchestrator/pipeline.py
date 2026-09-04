from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.assets.generator import AssetGenerator
from app.composition.compiler import CompositionCompiler
from app.core.artifacts import RunArtifacts, create_run_artifacts
from app.core.config import MAX_REPAIR_ATTEMPTS
from app.core.models import VideoPlan
from app.planning.planner import Planner
from app.planning.validator import PlanningValidator
from app.repair.repairer import CompositionRepairer
from app.validation.hyperframes import (
    HyperFramesCheckResult,
    HyperFramesValidator,
)
from app.validation.mp4 import MP4ValidationResult, MP4Validator
from app.validation.normalizer import (
    ValidationIssue,
    normalize_hyperframes_result,
)


@dataclass
class PipelineResult:
    run_id: str
    artifacts: RunArtifacts
    plan: VideoPlan
    hyperframes_check: HyperFramesCheckResult
    mp4_validation: MP4ValidationResult
    repair_attempts: int

    @property
    def output_path(self) -> Path:
        return self.artifacts.output_mp4


class PipelineError(RuntimeError):
    """Raised when the video pipeline cannot produce a valid MP4."""

    pass


class VideoPipeline:
    """
    End-to-end motion graphics video generation pipeline.

    Flow:

        brief
          ↓
        GPT-5.5 planning
          ↓
        plan validation
          ↓
        gpt-image-2 assets
          ↓
        HyperFrames composition
          ↓
        HyperFrames gate
          ↓
        repair loop if needed
          ↓
        HyperFrames render
          ↓
        MP4 validation
    """

    def __init__(
        self,
        base_runs_dir: str | Path = "runs",
        max_repair_attempts: int = MAX_REPAIR_ATTEMPTS,
        render_timeout: int = 600,
    ):
        if max_repair_attempts < 0:
            raise ValueError("max_repair_attempts must be >= 0")

        self.base_runs_dir = Path(base_runs_dir)
        self.max_repair_attempts = max_repair_attempts
        self.render_timeout = render_timeout

         
        self.hyperframes_validator = HyperFramesValidator()
        self.mp4_validator = MP4Validator()
        self.repairer = CompositionRepairer()

    def run(self, brief: str) -> PipelineResult:
        """
        Run the complete video generation pipeline.

        The run ID is derived from the normalized brief. Therefore the
        same brief maps to the same artifact directory, allowing the
        pipeline to reuse the already-generated plan and assets.
        """

        normalized_brief = self._normalize_brief(brief)

        if not normalized_brief:
            raise PipelineError("Brief cannot be empty.")

        run_id = self._create_run_id(normalized_brief)
        artifacts = create_run_artifacts(
            run_id,
            base_dir=self.base_runs_dir,
        )

        self._log(
            artifacts,
            f"Starting pipeline. run_id={run_id}",
        )

        self._save_brief(artifacts, normalized_brief)

        # ---------------------------------------------------------
        # 1. Planning
        # ---------------------------------------------------------
        plan = self._load_existing_plan(artifacts)

        if plan is not None:
            self._log(
                artifacts,
                "Existing plan.json found. Reusing plan for deterministic rerun.",
            )
        else:
            self._log(
                artifacts,
                "Generating VideoPlan with GPT-5.5.",
            )

            planner = Planner(
                output_dir=artifacts.root,
            )

            plan = planner.create_plan(normalized_brief)

        # ---------------------------------------------------------
        # 2. Planning validation
        # ---------------------------------------------------------
        self._log(
            artifacts,
            "Validating VideoPlan.",
        )

        self._validate_plan(plan)

        self._save_plan(artifacts, plan)

        # ---------------------------------------------------------
        # 3. Asset generation
        # ---------------------------------------------------------
        self._log(
            artifacts,
            f"Generating/reusing {len(plan.assets)} asset(s).",
        )

        asset_generator = AssetGenerator(
            output_dir=artifacts.assets,
        )

        asset_generator.generate_all(
            plan.assets,
            size=self._image_size_for_plan(plan),
        )

        # ---------------------------------------------------------
        # 4. Composition compilation
        # ---------------------------------------------------------
        self._log(
            artifacts,
            "Compiling HyperFrames composition.",
        )

        compiler = CompositionCompiler(
            output_dir=artifacts.composition,
            asset_registry=asset_generator.registry,
        )

        compiler.compile(plan)

        # ---------------------------------------------------------
        # 5. HyperFrames gate + repair loop
        # ---------------------------------------------------------
        check_result, repair_attempts = self._validate_and_repair(
            artifacts=artifacts,
            plan=plan,
            compiler=compiler,
        )

        # ---------------------------------------------------------
        # 6. Render MP4
        # ---------------------------------------------------------
        self._log(
            artifacts,
            "HyperFrames gate passed. Rendering MP4.",
        )

        self._render(
            artifacts=artifacts,
        )

        # ---------------------------------------------------------
        # 7. Validate final MP4
        # ---------------------------------------------------------
        self._log(
            artifacts,
            "Validating rendered MP4.",
        )

        mp4_result = self.mp4_validator.validate(
            video_path=artifacts.output_mp4,
            expected_width=plan.width,
            expected_height=plan.height,
            expected_fps=plan.fps,
            expected_duration=plan.duration,
        )

        mp4_result.save(
            artifacts.checks / "mp4.json"
        )

        if not mp4_result.ok:
            self._log(
                artifacts,
                "MP4 validation FAILED.",
            )

            raise PipelineError(
                "Rendered MP4 failed validation:\n"
                + "\n".join(mp4_result.errors)
            )

        self._log(
            artifacts,
            "Pipeline completed successfully.",
        )

        return PipelineResult(
            run_id=run_id,
            artifacts=artifacts,
            plan=plan,
            hyperframes_check=check_result,
            mp4_validation=mp4_result,
            repair_attempts=repair_attempts,
        )

    # =============================================================
    # Determinism
    # =============================================================

    @staticmethod
    def _normalize_brief(brief: str) -> str:
        """
        Normalize whitespace so equivalent briefs produce the same
        deterministic run ID.
        """
        return " ".join(brief.strip().split())

    @staticmethod
    def _create_run_id(brief: str) -> str:
        """
        Create deterministic run ID from the normalized brief.
        """
        digest = hashlib.sha256(
            brief.encode("utf-8")
        ).hexdigest()

        return digest[:16]

    @staticmethod
    def _image_size_for_plan(plan: VideoPlan) -> str:
        """Select an image canvas that preserves the video's composition.

        gpt-image-2 has landscape, square, and portrait canvases.  Using
        a portrait source for a vertical video avoids cropping away the
        planned subject or the reserved text-safe region before the image
        reaches the HyperFrames composition.
        """

        if plan.height > plan.width:
            return "1024x1536"

        if plan.height == plan.width:
            return "1024x1024"

        return "1536x1024"

    # =============================================================
    # Planning
    # =============================================================

    @staticmethod
    def _load_existing_plan(
        artifacts: RunArtifacts,
    ) -> Optional[VideoPlan]:
        """
        Reuse an existing validated/repaired plan.

        This is important for the requirement:

            same brief → same video
        """

        if not artifacts.plan.exists():
            return None

        try:
            raw = artifacts.plan.read_text(
                encoding="utf-8"
            )

            data = json.loads(raw)

            return VideoPlan.model_validate(data)

        except Exception as exc:
            raise PipelineError(
                f"Existing plan.json is unusable: {exc}"
            ) from exc

    @staticmethod
    def _save_plan(
        artifacts: RunArtifacts,
        plan: VideoPlan,
    ) -> None:
        artifacts.plan.write_text(
            plan.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def _validate_plan(
    self,
    plan: VideoPlan,
) -> None:
        validator = PlanningValidator()
        result = validator.validate(plan)

        if not result.valid:
            details = result.format_for_model()

            raise PipelineError(
                "VideoPlan failed semantic validation:\n"
                + details
            )

    # =============================================================
    # HyperFrames validation + repair
    # =============================================================

    def _validate_and_repair(
        self,
        artifacts: RunArtifacts,
        plan: VideoPlan,
        compiler: CompositionCompiler,
    ) -> tuple[HyperFramesCheckResult, int]:

        repair_attempts = 0

        # ---------------------------------------------------------
        # Initial gate
        # ---------------------------------------------------------
        check_result = self.hyperframes_validator.check(
            artifacts.composition
        )

        check_result.save(
            artifacts.check_output(0)
        )

        self._log(
            artifacts,
            f"HyperFrames attempt 0: ok={check_result.ok}",
        )

        if check_result.ok:
            return check_result, repair_attempts

        # ---------------------------------------------------------
        # Repair loop
        # ---------------------------------------------------------
        while (
            not check_result.ok
            and repair_attempts < self.max_repair_attempts
        ):
            repair_attempts += 1

            issues = normalize_hyperframes_result(
                check_result.data
            )

            if not issues:
                raise PipelineError(
                    "HyperFrames reported failure, but no actionable "
                    "issues could be normalized."
                )

            repair_issues = self._prioritize_issues(
                issues
            )

            self._log(
                artifacts,
                (
                    f"Repair attempt {repair_attempts}/"
                    f"{self.max_repair_attempts}. "
                    f"Issues: {len(repair_issues)}"
                ),
            )

            # -----------------------------------------------------
            # Ask GPT-5.5 to repair the VideoPlan
            # -----------------------------------------------------
            repair_result = self.repairer.repair(
                plan=plan,
                issues=repair_issues,
            )

            if not repair_result.success or repair_result.plan is None:
                self._log(
                    artifacts,
                    (
                        f"Repair attempt {repair_attempts} "
                        f"failed: {repair_result.error}"
                    ),
                )

                if repair_attempts >= self.max_repair_attempts:
                    raise PipelineError(
                        self._build_repair_failure_message(
                            artifacts,
                            repair_attempts,
                            issues,
                            repair_result.error,
                        )
                    )

                continue

            repaired_plan = repair_result.plan

            # -----------------------------------------------------
            # Validate repaired plan before compiling
            # -----------------------------------------------------
            try:
                self._validate_plan(
                    repaired_plan
                )
            except PipelineError as exc:
                self._log(
                    artifacts,
                    f"Repaired plan failed validation: {exc}",
                )

                if repair_attempts >= self.max_repair_attempts:
                    raise PipelineError(
                        self._build_repair_failure_message(
                            artifacts,
                            repair_attempts,
                            issues,
                            str(exc),
                        )
                    ) from exc

                continue

            # -----------------------------------------------------
            # Replace plan
            # -----------------------------------------------------
            plan = repaired_plan

            self._save_plan(
                artifacts,
                plan,
            )

            # -----------------------------------------------------
            # Recompile
            # -----------------------------------------------------
            self._log(
                artifacts,
                f"Recompiling after repair attempt {repair_attempts}.",
            )

            compiler.compile(plan)

            # -----------------------------------------------------
            # Re-run gate
            # -----------------------------------------------------
            check_result = self.hyperframes_validator.check(
                artifacts.composition
            )

            check_result.save(
                artifacts.check_output(
                    repair_attempts
                )
            )

            self._log(
                artifacts,
                (
                    f"HyperFrames attempt {repair_attempts}: "
                    f"ok={check_result.ok}"
                ),
            )

            if check_result.ok:
                self._log(
                    artifacts,
                    (
                        f"HyperFrames passed after "
                        f"{repair_attempts} repair attempt(s)."
                    ),
                )

                return check_result, repair_attempts

        # ---------------------------------------------------------
        # Repair cap reached
        # ---------------------------------------------------------
        final_issues = normalize_hyperframes_result(
            check_result.data
        )

        raise PipelineError(
            self._build_repair_failure_message(
                artifacts,
                repair_attempts,
                final_issues,
                "Maximum repair attempts reached.",
            )
        )

    @staticmethod
    def _prioritize_issues(
        issues: list[ValidationIssue],
    ) -> list[ValidationIssue]:
        """
        Repair higher-priority categories first.

        Order:
            lint
            runtime
            layout
            motion
            contrast
            snapshots
        """

        priority = {
            "lint": 0,
            "runtime": 1,
            "layout": 2,
            "motion": 3,
            "contrast": 4,
            "snapshots": 5,
        }

        minimum_priority = min(
            priority.get(issue.category, 99)
            for issue in issues
        )

        return [
            issue
            for issue in issues
            if priority.get(issue.category, 99)
            == minimum_priority
        ]

    @staticmethod
    def _build_repair_failure_message(
        artifacts: RunArtifacts,
        attempts: int,
        issues: list[ValidationIssue],
        error: Optional[str],
    ) -> str:

        lines = [
            "HyperFrames validation could not be repaired.",
            f"Repair attempts used: {attempts}",
            f"Run artifacts: {artifacts.root}",
        ]

        if error:
            lines.append(f"Repair error: {error}")

        if issues:
            lines.append("Remaining issues:")

            for issue in issues:
                selector = (
                    f" selector={issue.selector}"
                    if issue.selector
                    else ""
                )

                time_info = (
                    f" time={issue.time}"
                    if issue.time is not None
                    else ""
                )

                lines.append(
                    f"- [{issue.category}] "
                    f"{issue.code}{selector}{time_info}: "
                    f"{issue.message}"
                )

        return "\n".join(lines)

    # =============================================================
    # Rendering
    # =============================================================

    def _render(
        self,
        artifacts: RunArtifacts,
    ) -> None:

        artifacts.renders.mkdir(
            parents=True,
            exist_ok=True,
        )

        command = [
            "npx",
            "hyperframes",
            "render",
            str(artifacts.composition),
            "--docker",
            "-o",
            str(artifacts.output_mp4),
        ]

        self._log(
            artifacts,
            "Running render command:",
        )

        self._log(
            artifacts,
            " ".join(command),
        )

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.render_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise PipelineError(
                f"HyperFrames render timed out after "
                f"{self.render_timeout} seconds."
            ) from exc
        except OSError as exc:
            raise PipelineError(
                f"Could not start HyperFrames render: {exc}"
            ) from exc

        self._write_render_log(
            artifacts,
            completed.stdout,
            completed.stderr,
        )

        if completed.returncode != 0:
            raise PipelineError(
                "HyperFrames render failed.\n"
                f"Return code: {completed.returncode}\n"
                f"stderr:\n{completed.stderr[-4000:]}"
            )

        if not artifacts.output_mp4.exists():
            raise PipelineError(
                "HyperFrames render reported success, "
                "but output.mp4 was not created."
            )

        if artifacts.output_mp4.stat().st_size == 0:
            raise PipelineError(
                "HyperFrames render produced an empty MP4."
            )

    # =============================================================
    # Artifact helpers
    # =============================================================

    @staticmethod
    def _save_brief(
        artifacts: RunArtifacts,
        brief: str,
    ) -> None:
        artifacts.brief.write_text(
            brief,
            encoding="utf-8",
        )

    @staticmethod
    def _log(
        artifacts: RunArtifacts,
        message: str,
    ) -> None:

        artifacts.logs.mkdir(
            parents=True,
            exist_ok=True,
        )

        log_path = artifacts.logs / "pipeline.log"

        with log_path.open(
            "a",
            encoding="utf-8",
        ) as f:
            f.write(message + "\n")

    @staticmethod
    def _write_render_log(
        artifacts: RunArtifacts,
        stdout: str,
        stderr: str,
    ) -> None:

        artifacts.logs.mkdir(
            parents=True,
            exist_ok=True,
        )

        log_path = artifacts.logs / "render.log"

        with log_path.open(
            "w",
            encoding="utf-8",
        ) as f:
            f.write("=== STDOUT ===\n")
            f.write(stdout or "")
            f.write("\n\n=== STDERR ===\n")
            f.write(stderr or "")


def run_pipeline(
    brief: str,
    base_runs_dir: str | Path = "runs",
) -> PipelineResult:
    """
    Convenience function for running the complete pipeline.
    """

    pipeline = VideoPipeline(
        base_runs_dir=base_runs_dir,
    )

    return pipeline.run(brief)
