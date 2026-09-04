from typing import Literal

from pydantic import BaseModel, Field, model_validator


# -------------------------
# Supported primitive types
# -------------------------

SceneType = Literal[
    "hero",
    "feature",
    "feature_grid",
    "image",
    "stats",
    "cta",
]

MotionType = Literal[
    "fade_in",
    "fade_up",
    "slide_left",
    "slide_right",
    "scale_in",
    "stagger",
    "type_reveal",
    "image_zoom",
]


# -------------------------
# Scene design
# -------------------------

LayoutType = Literal[
    "center_stage",
    "split_left",
    "split_right",
    "full_bleed",
    "cards",
    "dashboard",
    "kinetic",
]

TransitionType = Literal[
    "cut",
    "crossfade",
    "slide",
    "scale_through",
]


class SceneDesign(BaseModel):
    """
    Creative direction for how a scene should look and feel.

    GPT-5.5 decides this.
    The composition compiler decides how to implement it.
    """

    layout: LayoutType = "center_stage"

    visual_intent: str = Field(
        default="A clear, focused composition that supports the scene message.",
        min_length=1,
        description=(
            "Describe the visual concept and composition of the scene. "
            "Focus on what the viewer should see and feel."
        ),
    )

    focus_target: str | None = Field(
        default=None,
        description="The primary visual element that should receive attention.",
    )

    transition_in: TransitionType = "cut"

    transition_out: TransitionType = "cut"

    continuous_motion: str | None = Field(
        default=None,
        description=(
            "Describe subtle motion that should continue throughout "
            "the scene, such as floating, camera push, or ambient movement."
        ),
    )

    visual_hierarchy: list[str] = Field(
        default_factory=list,
        description=(
            "Ordered list of what the viewer should notice first, second, "
            "and third."
        ),
    )


# -------------------------
# Motion
# -------------------------

class MotionSpec(BaseModel):
    type: MotionType
    target: str
    duration: float = Field(gt=0)
    delay: float = Field(default=0.0, ge=0.0)


# -------------------------
# Scene
# -------------------------

class Scene(BaseModel):
    id: str = Field(min_length=1)

    type: SceneType

    start: float = Field(ge=0)

    duration: float = Field(gt=0)

    text: list[str] = Field(default_factory=list)

    visual: str | None = None

    # New creative direction layer
    design: SceneDesign = Field(
        default_factory=SceneDesign
    )

    motion: list[MotionSpec] = Field(
        default_factory=list
    )

    @property
    def end(self) -> float:
        return self.start + self.duration


# -------------------------
# Assets
# -------------------------

class AssetSpec(BaseModel):
    id: str = Field(min_length=1)

    type: Literal["image"]

    prompt: str = Field(min_length=1)

    scene_id: str = Field(min_length=1)


# -------------------------
# Motion assertions
# -------------------------

class MotionAssertion(BaseModel):
    selector: str = Field(min_length=1)

    appears_by: float | None = Field(
        default=None,
        ge=0,
    )

    before: float | None = Field(
        default=None,
        ge=0,
    )

    stays_in_frame: bool = False

    keeps_moving: bool = False


# -------------------------
# Video Plan
# -------------------------

class VideoPlan(BaseModel):

    version: str = "1.0"

    duration: float = Field(gt=0)

    width: int = Field(gt=0)

    height: int = Field(gt=0)

    fps: int = Field(gt=0)

    theme: str = Field(min_length=1)

    scenes: list[Scene] = Field(min_length=1)

    assets: list[AssetSpec] = Field(
        default_factory=list
    )

    motion_assertions: list[MotionAssertion] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_plan(self):

        # -------------------------
        # Validate supported dimensions
        # -------------------------

        supported_sizes = {
            (1920, 1080),  # 16:9
            (1080, 1920),  # 9:16
            (1080, 1080),  # 1:1
        }

        if (self.width, self.height) not in supported_sizes:
            raise ValueError(
                "Unsupported video dimensions. "
                "Use 1920x1080, 1080x1920, or 1080x1080."
            )

        # -------------------------
        # Validate scenes
        # -------------------------

        for scene in self.scenes:

            if scene.end > self.duration:
                raise ValueError(
                    f"Scene '{scene.id}' ends at "
                    f"{scene.end:.2f}s but video duration is "
                    f"{self.duration:.2f}s."
                )

            for motion in scene.motion:

                if (
                    motion.delay + motion.duration
                    > scene.duration + 1e-6
                ):
                    raise ValueError(
                        f"Motion '{motion.target}' in scene "
                        f"'{scene.id}' does not fit inside "
                        f"scene duration."
                    )

        # -------------------------
        # Scene IDs must be unique
        # -------------------------

        scene_ids = [
            scene.id
            for scene in self.scenes
        ]

        if len(scene_ids) != len(set(scene_ids)):
            raise ValueError(
                "Scene IDs must be unique."
            )

        # -------------------------
        # Asset IDs must be unique
        # -------------------------

        asset_ids = [
            asset.id
            for asset in self.assets
        ]

        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError(
                "Asset IDs must be unique."
            )

        # -------------------------
        # Asset scene references
        # -------------------------

        scene_id_set = set(scene_ids)

        for asset in self.assets:

            if asset.scene_id not in scene_id_set:
                raise ValueError(
                    f"Asset '{asset.id}' references "
                    f"unknown scene '{asset.scene_id}'."
                )

        return self
