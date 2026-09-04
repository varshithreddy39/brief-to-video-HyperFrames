from dataclasses import dataclass, field

from app.core.models import VideoPlan


@dataclass
class ValidationIssue:
    """
    A single planning validation problem.
    """

    code: str
    message: str
    severity: str = "error"
    scene_id: str | None = None
    target: str | None = None

    def __str__(self) -> str:
        location = []

        if self.scene_id:
            location.append(f"scene={self.scene_id}")

        if self.target:
            location.append(f"target={self.target}")

        suffix = f" ({', '.join(location)})" if location else ""

        return f"[{self.severity.upper()}] {self.code}: {self.message}{suffix}"


@dataclass
class ValidationResult:
    """
    Result of semantic VideoPlan validation.
    """

    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == "error"
        ]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == "warning"
        ]

    def format_for_model(self) -> str:
        """
        Convert validation failures into concise feedback that can
        be given to gpt-5.5 during a planning retry.
        """

        if self.valid:
            return "VideoPlan passed semantic validation."

        lines = [
            "VideoPlan semantic validation failed:"
        ]

        for issue in self.errors:
            lines.append(f"- {issue}")

        return "\n".join(lines)


class PlanningValidator:
    """
    Performs semantic validation on an already parsed VideoPlan.

    Pydantic handles schema/type validation.
    This class handles application-specific usability rules.
    """

    MIN_SCENE_DURATION = 0.5
    MAX_SCENE_DURATION = 10.0
    MAX_MOTION_DELAY = 8.0

    def validate(self, plan: VideoPlan) -> ValidationResult:
        issues: list[ValidationIssue] = []

        self._validate_duration(plan, issues)
        self._validate_scenes(plan, issues)
        self._validate_scene_timing(plan, issues)
        self._validate_assets(plan, issues)
        self._validate_motion(plan, issues)
        self._validate_assertions(plan, issues)
        self._validate_text(plan, issues)

        errors = [
            issue
            for issue in issues
            if issue.severity == "error"
        ]

        return ValidationResult(
            valid=len(errors) == 0,
            issues=issues,
        )

    def _validate_duration(
        self,
        plan: VideoPlan,
        issues: list[ValidationIssue],
    ) -> None:
        if plan.duration < 3:
            issues.append(
                ValidationIssue(
                    code="VIDEO_TOO_SHORT",
                    message=(
                        "Video duration should be at least 3 seconds "
                        "for a usable motion-graphics composition."
                    ),
                )
            )

        if plan.duration > 120:
            issues.append(
                ValidationIssue(
                    code="VIDEO_TOO_LONG",
                    message=(
                        "Video duration must not exceed 120 seconds."
                    ),
                )
            )

    def _validate_scenes(
        self,
        plan: VideoPlan,
        issues: list[ValidationIssue],
    ) -> None:
        if not plan.scenes:
            issues.append(
                ValidationIssue(
                    code="NO_SCENES",
                    message="VideoPlan must contain at least one scene.",
                )
            )
            return

        for scene in plan.scenes:
            if scene.duration < self.MIN_SCENE_DURATION:
                issues.append(
                    ValidationIssue(
                        code="SCENE_TOO_SHORT",
                        message=(
                            f"Scene duration is {scene.duration:.2f}s. "
                            f"Minimum supported duration is "
                            f"{self.MIN_SCENE_DURATION:.2f}s."
                        ),
                        scene_id=scene.id,
                    )
                )

            if scene.duration > self.MAX_SCENE_DURATION:
                issues.append(
                    ValidationIssue(
                        code="SCENE_TOO_LONG",
                        message=(
                            f"Scene duration is {scene.duration:.2f}s. "
                            f"Maximum recommended duration is "
                            f"{self.MAX_SCENE_DURATION:.2f}s."
                        ),
                        scene_id=scene.id,
                    )
                )

    def _validate_scene_timing(
        self,
        plan: VideoPlan,
        issues: list[ValidationIssue],
    ) -> None:
        scenes = sorted(
            plan.scenes,
            key=lambda scene: scene.start,
        )

        for index, scene in enumerate(scenes):
            if scene.start < 0:
                issues.append(
                    ValidationIssue(
                        code="NEGATIVE_SCENE_START",
                        message="Scene start time cannot be negative.",
                        scene_id=scene.id,
                    )
                )

            if scene.end > plan.duration:
                issues.append(
                    ValidationIssue(
                        code="SCENE_OUT_OF_BOUNDS",
                        message=(
                            f"Scene ends at {scene.end:.2f}s, "
                            f"after the video ends at "
                            f"{plan.duration:.2f}s."
                        ),
                        scene_id=scene.id,
                    )
                )

            if index == 0:
                continue

            previous = scenes[index - 1]

            # Accidental overlaps are rejected. Intentional overlaps
            # are not currently part of the supported plan contract.
            if scene.start < previous.end:
                overlap = previous.end - scene.start

                issues.append(
                    ValidationIssue(
                        code="SCENE_OVERLAP",
                        message=(
                            f"Scene overlaps previous scene by "
                            f"{overlap:.2f}s. "
                            "Scenes must currently be sequential."
                        ),
                        scene_id=scene.id,
                    )
                )

            # Gaps are allowed, but large gaps are suspicious.
            gap = scene.start - previous.end

            if gap > 1.0:
                issues.append(
                    ValidationIssue(
                        code="LARGE_TIMELINE_GAP",
                        message=(
                            f"There is a {gap:.2f}s gap before this scene. "
                            "Use gaps only when intentionally designed."
                        ),
                        severity="warning",
                        scene_id=scene.id,
                    )
                )

    def _validate_assets(
        self,
        plan: VideoPlan,
        issues: list[ValidationIssue],
    ) -> None:
        scene_ids = {
            scene.id
            for scene in plan.scenes
        }

        asset_ids = set()

        for asset in plan.assets:
            if asset.id in asset_ids:
                issues.append(
                    ValidationIssue(
                        code="DUPLICATE_ASSET_ID",
                        message=f"Duplicate asset ID '{asset.id}'.",
                    )
                )

            asset_ids.add(asset.id)

            if asset.scene_id not in scene_ids:
                issues.append(
                    ValidationIssue(
                        code="INVALID_ASSET_SCENE",
                        message=(
                            f"Asset '{asset.id}' references scene "
                            f"'{asset.scene_id}', which does not exist."
                        ),
                    )
                )

            if not asset.prompt.strip():
                issues.append(
                    ValidationIssue(
                        code="EMPTY_ASSET_PROMPT",
                        message=(
                            f"Asset '{asset.id}' has an empty image "
                            "generation prompt."
                        ),
                    )
                )

    def _validate_motion(
        self,
        plan: VideoPlan,
        issues: list[ValidationIssue],
    ) -> None:
        asset_ids = {
            asset.id
            for asset in plan.assets
        }

        scene_ids = {
            scene.id
            for scene in plan.scenes
        }

        for scene in plan.scenes:
            for motion in scene.motion:
                if motion.duration > scene.duration:
                    issues.append(
                        ValidationIssue(
                            code="MOTION_LONGER_THAN_SCENE",
                            message=(
                                f"Motion duration {motion.duration:.2f}s "
                                f"exceeds scene duration "
                                f"{scene.duration:.2f}s."
                            ),
                            scene_id=scene.id,
                            target=motion.target,
                        )
                    )

                if motion.delay >= scene.duration:
                    issues.append(
                        ValidationIssue(
                            code="MOTION_DELAY_OUT_OF_BOUNDS",
                            message=(
                                f"Motion delay {motion.delay:.2f}s "
                                f"starts at or after the end of the scene."
                            ),
                            scene_id=scene.id,
                            target=motion.target,
                        )
                    )

                if (
                    motion.delay + motion.duration
                    > scene.duration
                ):
                    issues.append(
                        ValidationIssue(
                            code="MOTION_EXCEEDS_SCENE",
                            message=(
                                f"Motion ends at "
                                f"{motion.delay + motion.duration:.2f}s "
                                "relative to the scene, beyond its "
                                f"{scene.duration:.2f}s duration."
                            ),
                            scene_id=scene.id,
                            target=motion.target,
                        )
                    )

                if motion.delay > self.MAX_MOTION_DELAY:
                    issues.append(
                        ValidationIssue(
                            code="MOTION_DELAY_TOO_LARGE",
                            message=(
                                f"Motion delay {motion.delay:.2f}s is "
                                "unusually large."
                            ),
                            severity="warning",
                            scene_id=scene.id,
                            target=motion.target,
                        )
                    )

                # Targets are allowed to reference:
                # - assets
                # - compiler-generated semantic element IDs
                #
                # We only reject obviously invalid empty targets here.
                if not motion.target.strip():
                    issues.append(
                        ValidationIssue(
                            code="EMPTY_MOTION_TARGET",
                            message="Motion target cannot be empty.",
                            scene_id=scene.id,
                        )
                    )

        # Verify assertion selectors separately below.
        _ = asset_ids
        _ = scene_ids

    def _validate_assertions(
        self,
        plan: VideoPlan,
        issues: list[ValidationIssue],
    ) -> None:
        for assertion in plan.motion_assertions:
            if (
                assertion.appears_by is not None
                and assertion.appears_by > plan.duration
            ):
                issues.append(
                    ValidationIssue(
                        code="ASSERTION_OUT_OF_BOUNDS",
                        message=(
                            f"appears_by={assertion.appears_by:.2f}s "
                            f"exceeds video duration "
                            f"{plan.duration:.2f}s."
                        ),
                        target=assertion.selector,
                    )
                )

            if (
                assertion.before is not None
                and assertion.before > plan.duration
            ):
                issues.append(
                    ValidationIssue(
                        code="ASSERTION_BEFORE_OUT_OF_BOUNDS",
                        message=(
                            f"before={assertion.before:.2f}s exceeds "
                            f"video duration {plan.duration:.2f}s."
                        ),
                        target=assertion.selector,
                    )
                )

            if (
                assertion.appears_by is not None
                and assertion.before is not None
                and assertion.appears_by > assertion.before
            ):
                issues.append(
                    ValidationIssue(
                        code="ASSERTION_ORDER_INVALID",
                        message=(
                            f"appears_by={assertion.appears_by:.2f}s "
                            f"must be before "
                            f"before={assertion.before:.2f}s."
                        ),
                        target=assertion.selector,
                    )
                )

            if not assertion.selector.strip():
                issues.append(
                    ValidationIssue(
                        code="EMPTY_ASSERTION_SELECTOR",
                        message="Motion assertion selector is empty.",
                    )
                )

    def _validate_text(
        self,
        plan: VideoPlan,
        issues: list[ValidationIssue],
    ) -> None:
        for scene in plan.scenes:
            if not scene.text:
                issues.append(
                    ValidationIssue(
                        code="SCENE_HAS_NO_TEXT",
                        message=(
                            "Scene contains no on-screen text. "
                            "This is allowed for visual-only scenes, "
                            "but should be intentional."
                        ),
                        severity="warning",
                        scene_id=scene.id,
                    )
                )

            for text in scene.text:
                if not text.strip():
                    issues.append(
                        ValidationIssue(
                            code="EMPTY_TEXT",
                            message="Scene contains an empty text element.",
                            scene_id=scene.id,
                        )
                    )

                if len(text) > 120:
                    issues.append(
                        ValidationIssue(
                            code="TEXT_TOO_LONG",
                            message=(
                                f"Text contains {len(text)} characters. "
                                "Motion-graphics text should remain concise."
                            ),
                            severity="warning",
                            scene_id=scene.id,
                        )
                    )


def validate_plan(plan: VideoPlan) -> ValidationResult:
    """
    Convenience function for callers that do not need to keep a
    PlanningValidator instance.
    """

    return PlanningValidator().validate(plan)
