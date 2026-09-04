from pathlib import Path

from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from app.core.client import client
from app.core.config import MAX_PLAN_RETRIES, PLANNER_MODEL
from app.core.models import VideoPlan
from app.planning.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from app.planning.validator import PlanningValidator


class Planner:
    """
    Converts a plain-language video brief into a validated VideoPlan.

    Responsibilities:
    - Call gpt-5.5 using structured outputs.
    - Detect unusable model output.
    - Retry with actionable failure feedback.
    - Save only validated plans as plan.json.
    """

    def __init__(
        self,
        output_dir: str | Path,
        openai_client: OpenAI | None = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Use the shared application client by default.
        self.client = openai_client or client
        self.validator = PlanningValidator()

    def create_plan(self, brief: str) -> VideoPlan:
        """
        Generate a validated VideoPlan from a plain-language brief.

        The planner retries when:
        - the model refuses to produce a plan
        - structured output is missing
        - the generated plan fails Pydantic validation
        - the API returns a recoverable error

        Raises:
            ValueError: Empty brief.
            RuntimeError: Planning failed after all retries.
        """

        brief = self._normalize_brief(brief)

        if not brief:
            raise ValueError("Video brief cannot be empty.")

        previous_error: str | None = None

        total_attempts = MAX_PLAN_RETRIES + 1

        for attempt in range(total_attempts):
            try:
                plan = self._request_plan(
                    brief=brief,
                    previous_error=previous_error,
                )

                self._save_plan(plan)

                return plan

            except ValidationError as exc:
                previous_error = self._format_validation_error(exc)

                print(
                    f"[Planner] Attempt {attempt + 1}/{total_attempts} "
                    f"failed validation."
                )

            except ValueError as exc:
                previous_error = str(exc)

                print(
                    f"[Planner] Attempt {attempt + 1}/{total_attempts} "
                    f"returned unusable output."
                )

            except OpenAIError as exc:
                previous_error = (
                    f"OpenAI API error: {type(exc).__name__}: {exc}"
                )

                print(
                    f"[Planner] Attempt {attempt + 1}/{total_attempts} "
                    f"failed with an API error."
                )

            except Exception as exc:
                previous_error = (
                    f"Unexpected planning error: "
                    f"{type(exc).__name__}: {exc}"
                )

                print(
                    f"[Planner] Attempt {attempt + 1}/{total_attempts} "
                    f"failed unexpectedly."
                )
                print(f"[Planner] Exception type: {type(exc).__name__}")
                print(f"[Planner] Exception: {exc}")


        raise RuntimeError(
            "Planning failed after "
            f"{total_attempts} attempts.\n"
            f"Last failure: {previous_error}"
        )

    def _request_plan(
        self,
        brief: str,
        previous_error: str | None = None,
    ) -> VideoPlan:
        """
        Request a structured VideoPlan from gpt-5.5.
        """

        user_prompt = USER_PROMPT_TEMPLATE.format(
            brief=brief
        )

        if previous_error:
            user_prompt += f"""

The previous planning attempt was unusable.

Previous failure:
{previous_error}

Generate a corrected VideoPlan.

Do not repeat the previous mistake.
Re-evaluate the entire plan against all planning constraints.
"""

        response = self.client.chat.completions.parse(
            model=PLANNER_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            response_format=VideoPlan,
            max_tokens=8000,
        )

        if not response.choices:
            raise ValueError(
                "gpt-5.5 returned no choices."
            )

        message = response.choices[0].message

        # The model may explicitly refuse the request.
        if getattr(message, "refusal", None):
            raise ValueError(
                f"Model refused to create a VideoPlan: "
                f"{message.refusal}"
            )

        # Structured output was expected but not returned.
        if message.parsed is None:
            raise ValueError(
                "gpt-5.5 returned no structured VideoPlan."
            )

        plan = message.parsed

        validation = self.validator.validate(plan)

        if not validation.valid:
            raise ValueError(
                validation.format_for_model()
            )

        return plan

    def _save_plan(self, plan: VideoPlan) -> Path:
        """
        Save only a validated VideoPlan.

        This file is the printable planning artifact required by
        the assignment.
        """

        plan_path = self.output_dir / "plan.json"

        plan_path.write_text(
            plan.model_dump_json(
                indent=2,
            ),
            encoding="utf-8",
        )

        return plan_path

    @staticmethod
    def _normalize_brief(brief: str) -> str:
        """
        Normalize whitespace so equivalent briefs have the same
        canonical representation.

        This also supports deterministic run hashing later.
        """

        return " ".join(brief.split())

    @staticmethod
    def _format_validation_error(
        error: ValidationError,
    ) -> str:
        """
        Convert Pydantic validation errors into compact feedback
        that can be sent back to the planning model.
        """

        errors = []

        for item in error.errors():
            location = ".".join(
                str(part)
                for part in item["loc"]
            )

            message = item["msg"]

            errors.append(
                f"- {location}: {message}"
            )

        return (
            "VideoPlan validation failed:\n"
            + "\n".join(errors)
        )

