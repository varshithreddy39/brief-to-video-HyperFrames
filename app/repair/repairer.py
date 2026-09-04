import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from openai import OpenAI, OpenAIError

from app.core.config import PLANNER_MODEL
from app.core.models import VideoPlan
from app.core.client import client
from app.validation.normalizer import ValidationIssue


@dataclass
class RepairResult:
    """Result of one composition repair attempt."""

    success: bool
    plan: VideoPlan | None
    issues: list[ValidationIssue]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "plan": self.plan.model_dump() if self.plan else None,
            "issues": [
                issue.to_dict()
                for issue in self.issues
            ],
            "error": self.error,
        }


class CompositionRepairer:
    """
    Uses GPT-5.5 to repair a VideoPlan based on HyperFrames findings.

    The repairer does NOT directly modify generated HTML/CSS/JS.

    Instead:
        HyperFrames findings
            ↓
        targeted repair request
            ↓
        corrected VideoPlan
            ↓
        deterministic compiler
    """

    def __init__(
        self,
        llm_client: OpenAI | None = None,
        model: str = PLANNER_MODEL,
        max_tokens: int = 6000,
    ) -> None:
        self.client = llm_client or client
        self.model = model
        self.max_tokens = max_tokens

    def repair(
        self,
        plan: VideoPlan,
        issues: list[ValidationIssue],
    ) -> RepairResult:
        """
        Produce a corrected VideoPlan for the supplied validation issues.

        This performs ONE repair operation.

        The orchestrator is responsible for:
            - counting attempts
            - recompiling
            - re-running HyperFrames
            - enforcing the maximum repair cap
        """

        if not issues:
            return RepairResult(
                success=True,
                plan=plan,
                issues=[],
            )

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(plan, issues)

        try:
            response = self.client.chat.completions.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                response_format=VideoPlan,
                max_tokens=self.max_tokens,
            )

            repaired_plan = response.choices[0].message.parsed

            if repaired_plan is None:
                return RepairResult(
                    success=False,
                    plan=None,
                    issues=issues,
                    error="GPT-5.5 returned no parsed VideoPlan.",
                )

            semantic_errors = self._validate_repair(
                original=plan,
                repaired=repaired_plan,
            )

            if semantic_errors:
                return RepairResult(
                    success=False,
                    plan=None,
                    issues=issues,
                    error=(
                        "Repaired plan failed safety checks: "
                        + "; ".join(semantic_errors)
                    ),
                )

            return RepairResult(
                success=True,
                plan=repaired_plan,
                issues=issues,
            )

        except ValidationError as exc:
            return RepairResult(
                success=False,
                plan=None,
                issues=issues,
                error=f"Invalid repaired VideoPlan: {exc}",
            )

        except OpenAIError as exc:
            return RepairResult(
                success=False,
                plan=None,
                issues=issues,
                error=f"Repair model request failed: {exc}",
            )

        except Exception as exc:
            return RepairResult(
                success=False,
                plan=None,
                issues=issues,
                error=f"Unexpected repair failure: {exc}",
            )

    def _build_system_prompt(self) -> str:
        return """
You are the repair agent for a deterministic motion graphics
video generator.

You receive:
1. The current valid VideoPlan.
2. Specific HyperFrames validation findings.

Your job is to produce a CORRECTED VideoPlan that fixes the reported
validation problems while preserving the original creative intent.

CRITICAL RULES:

1. Return ONLY a structured VideoPlan.
2. Do not generate HTML.
3. Do not generate CSS.
4. Do not generate JavaScript.
5. Do not generate GSAP code.
6. Do not invent unsupported scene types.
7. Do not invent unsupported motion types.
8. Do not invent new compiler target naming conventions.
9. Do not change the aspect ratio unless the validation problem
   explicitly requires it.
10. Do not change the video's core message.
11. Do not add facts that were not present in the original plan.
12. Keep the same scene IDs whenever possible.
13. Keep the same asset IDs whenever possible.
14. Keep the same overall scene structure unless a validation error
    makes it impossible to preserve.
15. Every MotionSpec must fit inside its scene duration.
16. Do not introduce motion that moves an element outside the canvas.
17. If a motion issue is reported, prefer adjusting the motion timing,
    duration, target, or motion type rather than redesigning the scene.
18. If a layout/off-frame issue is reported, prefer reducing scale,
    changing motion, or adjusting timing.
19. If a static/frozen-motion issue is reported, add or redistribute
    meaningful supported motion without making the scene visually
    chaotic.
20. If a lint/runtime issue is reported, make the smallest plan-level
    change that can reasonably prevent the compiler from generating
    the problematic composition.

SUPPORTED SCENE TYPES:
hero
feature
feature_grid
image
stats
cta

SUPPORTED MOTION TYPES:
fade_in
fade_up
slide_left
slide_right
scale_in
stagger
type_reveal
image_zoom

The compiler generates exact target IDs from scene IDs.

Target naming rules:

HERO / FEATURE / IMAGE:

{{scene_id}}_headline

{{scene_id}}_text_2

{{scene_id}}_text_3

{{scene_id}}_accent

FEATURE_GRID:

{{scene_id}}_header

{{scene_id}}_card_1

{{scene_id}}_card_2

...

STATS:

{{scene_id}}_header

{{scene_id}}_stat_1

{{scene_id}}_stat_2

...

CTA:

{{scene_id}}_headline

{{scene_id}}_button

{{scene_id}}_spark_1

{{scene_id}}_spark_2

...

IMAGE:

{{scene_id}}_image

Never use AssetSpec.id as a motion target.
Never invent target IDs.
Motion targets must correspond to HTML element IDs generated by the compiler.

DETERMINISM:

Do not introduce randomness.

Do not randomly reorder scenes.

Do not randomly change copy.

Make the smallest safe correction necessary.

"""
    def _build_user_prompt(
        self,
        plan: VideoPlan,
        issues: list[ValidationIssue],
    ) -> str:
        issue_text = "\n".join(
            self._format_issue(issue)
            for issue in issues
        )

        plan_json = json.dumps(
            plan.model_dump(),
            indent=2,
        )

        return f"""
Repair the following VideoPlan based on the HyperFrames findings.

VALIDATION FINDINGS:
{issue_text}

CURRENT VIDEOPLAN:
{plan_json}

Return the corrected VideoPlan.

Before producing the final structured result, reason about:
- which element caused each finding
- which supported plan-level property can fix it
- whether the resulting motion still fits inside the scene
- whether the correction preserves the original creative intent
- whether the corrected plan remains compiler-compatible

Do not return explanations.
Return only the corrected VideoPlan.
"""

    @staticmethod
    def _format_issue(
        issue: ValidationIssue,
    ) -> str:
        details = ""

        if issue.selector:
            details += f" selector={issue.selector}"

        if issue.time is not None:
            details += f" time={issue.time}"

        if issue.first_seen is not None:
            details += f" firstSeen={issue.first_seen}"

        if issue.last_seen is not None:
            details += f" lastSeen={issue.last_seen}"

        if issue.details:
            details += f" details={issue.details}"

        return (
            f"- category={issue.category}"
            f" severity={issue.severity}"
            f" code={issue.code}"
            f" message={issue.message}"
            f"{details}"
        )

    @staticmethod
    def _validate_repair(
        original: VideoPlan,
        repaired: VideoPlan,
    ) -> list[str]:
        """
        Safety checks preventing the repair model from unnecessarily
        changing the overall video.
        """

        errors: list[str] = []

        # ---------------------------------------------------------
        # Preserve fundamental video properties
        # ---------------------------------------------------------

        if repaired.duration != original.duration:
            errors.append(
                "Video duration changed during repair."
            )

        if repaired.width != original.width:
            errors.append(
                "Video width changed during repair."
            )

        if repaired.height != original.height:
            errors.append(
                "Video height changed during repair."
            )

        if repaired.fps != original.fps:
            errors.append(
                "Video FPS changed during repair."
            )

        # ---------------------------------------------------------
        # Preserve scene identity
        # ---------------------------------------------------------

        original_scene_ids = [
            scene.id
            for scene in original.scenes
        ]

        repaired_scene_ids = [
            scene.id
            for scene in repaired.scenes
        ]

        if original_scene_ids != repaired_scene_ids:
            errors.append(
                "Scene IDs/order changed during repair."
            )

        # ---------------------------------------------------------
        # Preserve asset identity
        # ---------------------------------------------------------

        original_asset_ids = [
            asset.id
            for asset in original.assets
        ]

        repaired_asset_ids = [
            asset.id
            for asset in repaired.assets
        ]

        if original_asset_ids != repaired_asset_ids:
            errors.append(
                "Asset IDs changed during repair."
            )

        # ---------------------------------------------------------
        # Ensure motion remains inside scenes
        # ---------------------------------------------------------

        for scene in repaired.scenes:
            for motion in scene.motion:
                if (
                    motion.delay + motion.duration
                    > scene.duration + 1e-6
                ):
                    errors.append(
                        f"Motion '{motion.target}' in scene "
                        f"'{scene.id}' exceeds scene duration."
                    )

        return errors


def repair_video_plan(
    plan: VideoPlan,
    issues: list[ValidationIssue],
) -> RepairResult:
    """Convenience function for one repair operation."""

    repairer = CompositionRepairer()

    return repairer.repair(
        plan=plan,
        issues=issues,
    )