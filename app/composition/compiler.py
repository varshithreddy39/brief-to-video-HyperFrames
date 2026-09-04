from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.assets.registry import AssetRegistry
from app.composition.motion import build_timeline
from app.composition.primitives import (
    accent_line,
    background,
    body_text,
    cta_button,
    glass_card,
    headline,
    icon_card,
    image,
    scene_container,
    signal_field,
    spark,
)
from app.core.models import Scene, VideoPlan


class CompositionCompiler:
    """
    Deterministically compiles a VideoPlan into a HyperFrames
    HTML composition.

    GPT decides WHAT the video contains.
    This compiler decides HOW supported primitives are rendered.
    """

    def __init__(
        self,
        output_dir: str | Path,
        asset_registry: AssetRegistry,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.asset_registry = asset_registry

    def compile(self, plan: VideoPlan) -> Path:
        """
        Compile a complete VideoPlan into HyperFrames files.

        Returns:
            Path to generated index.html.
        """

        self._validate_assets(plan)
        self._copy_assets(plan)
        self._copy_gsap()


        html = self._build_html(plan)
        css = self._build_css(plan)
        timeline = self._build_timeline(plan)

        

        motion_assertions = []

        for assertion in plan.motion_assertions:

            if assertion.appears_by is not None:
                motion_assertions.append({
                    "kind": "appearsBy",
                    "selector": f"#{self._render_target(plan, assertion.selector)}",
                    "bySec": assertion.appears_by,
                })

            if assertion.stays_in_frame:
                motion_assertions.append({
                    "kind": "staysInFrame",
                    "selector": f"#{self._render_target(plan, assertion.selector)}",
                })

            if assertion.keeps_moving:
                motion_assertions.append({
                    "kind": "keepsMoving",
                    "selector": f"#{self._render_target(plan, assertion.selector)}",
                })

        self._write(
            "index.html",
            html,
        )

        self._write(
            "styles.css",
            css,
        )

        self._write(
            "timeline.js",
            timeline,
        )

        self._write(
            "index.motion.json",
            json.dumps(
                {
                    "assertions": motion_assertions,
                },
                indent=2,
            ),
        )

        return self.output_dir / "index.html"

 
    def _build_html(
        self,
        plan: VideoPlan,
    ) -> str:
        scenes = []

        for scene in plan.scenes:
            content = self._compile_scene(
                plan,
                scene,
            )

            scenes.append(
                scene_container(
                    scene_id=scene.id,
                    scene_type=scene.type,
                    start=scene.start,
                    duration=scene.duration,
                    content=content,
                    layout=scene.design.layout,

                )
            )

        return f"""<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>HyperFrames Motion Composition</title>

        <link
            rel="stylesheet"
            href="./styles.css"
        >

        <script src="./gsap.min.js"></script>
    </head>

    <body
        data-composition-id="main"
        data-duration="{plan.duration:.3f}"
        data-width="{plan.width}"
        data-height="{plan.height}"
        data-fps="{plan.fps}"
    >

        <main
            id="composition"
            class="composition"
        >
            {"".join(scenes)}
        </main>

        <script>
    {self._build_timeline(plan)}
    </script>
    </body>
    </html>
    """

    def _copy_gsap(self) -> None:
        source = Path("node_modules/gsap/dist/gsap.min.js")

        if not source.exists():
            raise FileNotFoundError(
                f"Local GSAP not found: {source}"
            )

        destination = self.output_dir / "gsap.min.js"
        shutil.copy2(source, destination)



    def _compile_scene(
        self,
        plan: VideoPlan,
        scene: Scene,
    ) -> str:

        if scene.type == "hero":
            return self._compile_hero(
                plan,
                scene,
            )

        if scene.type == "feature":
            return self._compile_feature(
                plan,
                scene,
            )

        if scene.type == "feature_grid":
            return self._compile_feature_grid(
                plan,
                scene,
            )

        if scene.type == "image":
            return self._compile_image_scene(
                plan,
                scene,
            )

        if scene.type == "stats":
            return self._compile_stats(
                plan,
                scene,
            )

        if scene.type == "cta":
            return self._compile_cta(
                plan,
                scene,
            )

        raise ValueError(
            f"Unsupported scene type: {scene.type}"
        )

    def _compile_hero(
        self,
        plan: VideoPlan,
        scene: Scene,
    ) -> str:

        parts = [
            background(scene.id),
            accent_line(
                f"{scene.id}_accent"
            ),
        ]

        for index, text in enumerate(scene.text):
            element_id = self._text_id(scene, index)

            if index == 0:
                parts.append(
                    headline(
                        element_id,
                        text,
                        "headline hero-headline",
                    )
                )
            else:
                parts.append(
                    body_text(
                        element_id,
                        text,
                        "body-text hero-text",
                    )
                )

        asset = self._asset_for_scene(
            plan,
            scene,
        )

        if asset is not None:
            parts.append(
                image(
                    f"{scene.id}_image",
                    self._asset_src(asset.id),
                    "visual-image hero-image",
                    asset_id=asset.id,
                )
            )

        return "\n".join(parts)

    def _compile_feature(self, plan: VideoPlan, scene: Scene) -> str:
        parts = [
            background(scene.id),
            accent_line(f"{scene.id}_accent"),
            signal_field(f"{scene.id}_signal"),
        ]

        text_index = 0  # counts body-text elements only, headline excluded
        for index, text in enumerate(scene.text):
            element_id = self._text_id(scene, index)

            if index == 0:
                parts.append(headline(element_id, text, "headline feature-headline"))
            else:
                top_offset = f"calc(62% + {text_index} * 70px)"
                parts.append(
                    body_text(
                        element_id,
                        text,
                        "body-text feature-text",
                        style=f"top: {top_offset};",
                    )
                )
                text_index += 1

        return "\n".join(parts)

    def _compile_feature_grid(
        self,
        plan: VideoPlan,
        scene: Scene,
    ) -> str:

        parts = [
            background(scene.id),
        ]

        if scene.text:
            parts.append(
                headline(
                    f"{scene.id}_header",
                    scene.text[0],
                    "headline grid-header",
                )
            )

        card_texts = scene.text[1:5]

        cards = []
        for index, text in enumerate(card_texts):
            cards.append(
                icon_card(
                    f"{scene.id}_card_{index + 1}",
                    self._feature_icon(index),
                    text,
                )
            )

        if cards:
            parts.append(
                '<div class="feature-grid-cards">'
                + "\n".join(cards)
                + "</div>"
            )

        return "\n".join(parts)

    def _compile_image_scene(
    self,
    plan: VideoPlan,
    scene: Scene,
) -> str:

        parts = [
            background(scene.id),
        ]

        asset = self._asset_for_scene(
            plan,
            scene,
        )

        if asset is not None:
            parts.append(
                image(
                    f"{scene.id}_image",
                    self._asset_src(asset.id),
                    "visual-image full-image",
                    asset_id=asset.id,
                )
            )

        for index, text in enumerate(scene.text):
            element_id = self._text_id(scene, index)
            if index == 0:
                parts.append(
                    headline(
                        element_id,
                        text,
                        "headline image-headline",
                    )
                )
            else:
                parts.append(
                    body_text(
                        element_id,
                        text,
                        "body-text image-text",
                    )
                )

        parts.append(
            accent_line(
                f"{scene.id}_accent"
            )
        )

        return "\n".join(parts)

    def _compile_stats(
        self,
        plan: VideoPlan,
        scene: Scene,
    ) -> str:

        parts = [
            background(scene.id),
        ]

        if scene.text:
            parts.append(
                headline(
                    f"{scene.id}_header",
                    scene.text[0],
                    "headline stats-header",
                )
            )

        cards = []
        for index, text in enumerate(scene.text[1:]):
            cards.append(
                glass_card(
                    f"{scene.id}_stat_{index + 1}",
                    text,
                    "",
                    "stat-card glass-card",
                )
            )

        if cards:
            parts.append(
                '<div class="stats-cards">'
                + "\n".join(cards)
                + "</div>"
            )

        return "\n".join(parts)

    def _compile_cta(
        self,
        plan: VideoPlan,
        scene: Scene,
    ) -> str:

        parts = [
            background(
                scene.id,
                "cta-gradient",
            ),
        ]

        if scene.text:
            parts.append(
                headline(
                    f"{scene.id}_headline",
                    scene.text[0],
                    "headline cta-headline",
                )
            )

        if len(scene.text) > 1:
            parts.append(
                cta_button(
                    f"{scene.id}_button",
                    scene.text[1],
                )
            )

        for index in range(3):
            positions = [
                {"left": "17%", "top": "26%"},
                {"right": "17%", "top": "39%"},
                {"left": "29%", "bottom": "20%"},
            ]
            parts.append(
                spark(
                    f"{scene.id}_spark_{index + 1}",
                    **positions[index],
                )
            )

        return "\n".join(parts)

    def _build_timeline(
    self,
    plan: VideoPlan,
) -> str:
        """
        Build a deterministic GSAP timeline using
        each scene's absolute start time.
        """

        return build_timeline(
            plan.scenes,
            asset_target_map={
                asset.id: f"{asset.scene_id}_image"
                for asset in plan.assets
            },
        )

    def _validate_assets(
        self,
        plan: VideoPlan,
    ) -> None:
        """
        Ensure every planned asset is available.
        """

        for asset in plan.assets:
            path = self.asset_registry.get(
                asset.id
            )

            if path is None:
                raise FileNotFoundError(
                    f"Required asset '{asset.id}' "
                    f"is not available in the registry."
                )

    def _asset_for_scene(
        self,
        plan: VideoPlan,
        scene: Scene,
    ):
        """
        Return the first planned asset belonging
        to the given scene.
        """

        for asset in plan.assets:
            if asset.scene_id == scene.id:
                return asset

        return None

    @staticmethod
    def _render_target(
        plan: VideoPlan,
        target: str,
    ) -> str:
        """Map legacy asset IDs to the stable image element IDs.

        Plans produced before the image-target convention used the asset
        ID as a motion/assertion target. Keeping this compatibility layer
        means a cached deterministic run can still be rendered correctly,
        while all newly planned videos use ``{scene_id}_image`` directly.
        """

        for asset in plan.assets:
            if target == asset.id:
                return f"{asset.scene_id}_image"

        return target
    def _copy_assets(
    self,
    plan: VideoPlan,
) -> None:
        """
        Copy all generated assets into the composition directory.
        """

        assets_dir = self.output_dir / "assets"

        assets_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        for asset in plan.assets:
            source = self.asset_registry.get(asset.id)

            if source is None:
                raise FileNotFoundError(
                    f"Asset '{asset.id}' is not registered."
                )

            destination = assets_dir / source.name

            shutil.copy2(
                source,
                destination,
            )

    def _asset_src(
    self,
    asset_id: str,
) -> str:
        path = self.asset_registry.get(asset_id)

        if path is None:
            raise FileNotFoundError(
                f"Asset '{asset_id}' is not registered."
            )

        return f"./assets/{path.name}"

    @staticmethod
    def _text_id(
        scene: Scene,
        index: int,
    ) -> str:

        if index == 0:
            return f"{scene.id}_headline"

        return f"{scene.id}_text_{index + 1}"

    @staticmethod
    def _feature_icon(
        index: int,
    ) -> str:

        icons = [
            "✦",
            "◌",
            "✓",
            "→",
        ]

        return icons[index % len(icons)]

    @staticmethod
    def _theme_palette(theme: str) -> dict[str, str]:
        """Project a plan's natural-language theme into safe CSS tokens.

        This is intentionally deterministic.  The planner can choose the
        creative direction, but an unsupported or vague colour request must
        never make the rendered composition unreadable or non-repeatable.
        """

        normalized = theme.lower()

        # Ordered from most specific to least specific.  A theme such as
        # "warm off-white with cobalt accents" must choose the editorial
        # palette rather than the generic blue technology palette.
        if any(word in normalized for word in (
            "off-white", "off white", "ivory", "cream", "paper",
            "warm white", "editorial", "minimal white",
        )):
            return {
                "canvas": "#F6F0E7", "canvas_deep": "#E7DAC8",
                "ink": "#101828", "muted": "#435166",
                "accent": "#1648C8", "accent_alt": "#5E87F5",
                "glow": "rgba(22, 72, 200, 0.24)",
                "glow_alt": "rgba(94, 135, 245, 0.18)",
                "surface": "rgba(255, 255, 255, 0.72)",
                "surface_deep": "rgba(255, 255, 255, 0.88)",
                "border": "rgba(16, 24, 40, 0.16)",
                "shadow": "rgba(35, 48, 70, 0.18)",
                "overlay": "rgba(246, 240, 231, 0.10)",
                "button_ink": "#FFFFFF",
            }

        if any(word in normalized for word in (
            "lime", "green", "eco", "nature", "organic",
        )):
            return {
                "canvas": "#0A1110", "canvas_deep": "#14231D",
                "ink": "#F4FAF5", "muted": "#C0D1C5",
                "accent": "#C8F34A", "accent_alt": "#64D89A",
                "glow": "rgba(200, 243, 74, 0.28)",
                "glow_alt": "rgba(100, 216, 154, 0.20)",
                "surface": "rgba(19, 37, 30, 0.72)",
                "surface_deep": "rgba(25, 47, 38, 0.90)",
                "border": "rgba(220, 255, 228, 0.19)",
                "shadow": "rgba(0, 0, 0, 0.32)",
                "overlay": "rgba(3, 10, 8, 0.26)",
                "button_ink": "#102014",
            }

        if any(word in normalized for word in (
            "coral", "orange", "red", "amber", "warm dark", "sunset",
        )):
            return {
                "canvas": "#1C0D0B", "canvas_deep": "#3A1711",
                "ink": "#FFF7F1", "muted": "#F2CFC1",
                "accent": "#FF7045", "accent_alt": "#FFB15C",
                "glow": "rgba(255, 112, 69, 0.30)",
                "glow_alt": "rgba(255, 177, 92, 0.20)",
                "surface": "rgba(66, 28, 22, 0.70)",
                "surface_deep": "rgba(76, 31, 23, 0.90)",
                "border": "rgba(255, 232, 219, 0.18)",
                "shadow": "rgba(0, 0, 0, 0.34)",
                "overlay": "rgba(20, 6, 4, 0.28)",
                "button_ink": "#25100A",
            }

        if any(word in normalized for word in (
            "cyan", "teal", "aqua", "ocean", "meeting",
        )):
            return {
                "canvas": "#06161C", "canvas_deep": "#0A2A34",
                "ink": "#EFFBFC", "muted": "#BFDEE1",
                "accent": "#38D6D1", "accent_alt": "#7A8CFF",
                "glow": "rgba(56, 214, 209, 0.28)",
                "glow_alt": "rgba(122, 140, 255, 0.20)",
                "surface": "rgba(10, 43, 53, 0.70)",
                "surface_deep": "rgba(12, 51, 62, 0.90)",
                "border": "rgba(214, 254, 255, 0.18)",
                "shadow": "rgba(0, 0, 0, 0.34)",
                "overlay": "rgba(1, 10, 14, 0.28)",
                "button_ink": "#062022",
            }

        if any(word in normalized for word in (
            "purple", "violet", "lavender", "magenta",
        )):
            return {
                "canvas": "#110A21", "canvas_deep": "#251444",
                "ink": "#FBF6FF", "muted": "#DDD0F4",
                "accent": "#B57BFF", "accent_alt": "#F080D5",
                "glow": "rgba(181, 123, 255, 0.30)",
                "glow_alt": "rgba(240, 128, 213, 0.18)",
                "surface": "rgba(44, 25, 75, 0.70)",
                "surface_deep": "rgba(51, 28, 89, 0.90)",
                "border": "rgba(245, 232, 255, 0.18)",
                "shadow": "rgba(0, 0, 0, 0.34)",
                "overlay": "rgba(8, 3, 18, 0.28)",
                "button_ink": "#1C0D36",
            }

        # A safe default for broad technology briefs.
        return {
            "canvas": "#060817", "canvas_deep": "#18265A",
            "ink": "#F7F9FF", "muted": "#C9D4F2",
            "accent": "#5D95FF", "accent_alt": "#AA7CFF",
            "glow": "rgba(93, 149, 255, 0.30)",
            "glow_alt": "rgba(170, 124, 255, 0.22)",
            "surface": "rgba(20, 33, 74, 0.70)",
            "surface_deep": "rgba(22, 37, 82, 0.90)",
            "border": "rgba(209, 225, 255, 0.20)",
            "shadow": "rgba(0, 0, 0, 0.34)",
            "overlay": "rgba(2, 4, 15, 0.30)",
            "button_ink": "#111A42",
        }

    def _build_css(
        self,
        plan: VideoPlan,
    ) -> str:
        """
        Build deterministic CSS for all supported
        composition primitives.
        """

        palette = self._theme_palette(plan.theme)

        return f"""
* {{
    box-sizing: border-box;
}}

:root {{
    --canvas: {palette["canvas"]};
    --canvas-deep: {palette["canvas_deep"]};
    --ink: {palette["ink"]};
    --muted: {palette["muted"]};
    --accent: {palette["accent"]};
    --accent-alt: {palette["accent_alt"]};
    --glow: {palette["glow"]};
    --glow-alt: {palette["glow_alt"]};
    --surface: {palette["surface"]};
    --surface-deep: {palette["surface_deep"]};
    --border: {palette["border"]};
    --shadow: {palette["shadow"]};
    --overlay: {palette["overlay"]};
    --button-ink: {palette["button_ink"]};
}}

html,
body {{
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: #060817;
    font-family: Inter, ui-sans-serif, system-ui, -apple-system,
        BlinkMacSystemFont, "Segoe UI", sans-serif;
    text-rendering: geometricPrecision;
}}

body {{
    width: {plan.width}px;
    height: {plan.height}px;
}}

.composition {{
    position: relative;
    width: {plan.width}px;
    height: {plan.height}px;
    overflow: hidden;
    background: #060817;
    isolation: isolate;
}}

.scene {{
    position: absolute;
    inset: 0;
    overflow: hidden;
    opacity: 1;
    --canvas-pad: clamp(52px, 6vw, 120px);
    --headline-size: clamp(52px, 5.2vw, 102px);
    --body-size: clamp(23px, 2vw, 40px);
}}

.scene::before {{
    position: absolute;
    z-index: 1;
    inset: 0;
    background:
        linear-gradient(90deg, rgba(6, 8, 23, 0.36), transparent 42%),
        radial-gradient(circle at 55% 50%, transparent 0 47%, rgba(2, 4, 15, 0.45) 100%);
    content: "";
    pointer-events: none;
}}

.scene::after {{
    position: absolute;
    z-index: 3;
    inset: 0;
    background-image: linear-gradient(rgba(255, 255, 255, 0.022) 1px, transparent 1px), linear-gradient(90deg, rgba(255, 255, 255, 0.018) 1px, transparent 1px);
    background-size: 72px 72px;
    content: "";
    opacity: 0.42;
    pointer-events: none;
}}
/* ---------------------------------
   GPT-5.5 Scene Layouts
   --------------------------------- */

.layout-center_stage {{
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
}}

.layout-split_left {{
    display: grid;
    grid-template-columns: 45% 55%;
    align-items: center;
}}

.layout-split_right {{
    display: grid;
    grid-template-columns: 55% 45%;
    align-items: center;
}}

.layout-full_bleed {{
    display: block;
}}

.layout-cards {{
    display: block;
}}

.layout-dashboard {{
    display: block;
}}

.layout-kinetic {{
    display: flex;
    align-items: center;
    justify-content: center;
}}

/* These two scene types own their internal grid/card flow. This also
   preserves readable layouts for cached plans that predate SceneDesign
   and therefore use the model's center_stage default. */
.scene-feature_grid,
.scene-stats {{
    display: block;
}}

.background-layer {{
    position: absolute;
    inset: 0;
    background:
        radial-gradient(
            circle at 20% 20%,
            rgba(74, 132, 255, 0.42),
            transparent 35%
        ),
        radial-gradient(
            circle at 80% 70%,
            rgba(166, 89, 255, 0.35),
            transparent 40%
        ),
        linear-gradient(
            135deg,
            #07091a 0%,
            #101b38 50%,
            #1a1039 100%
        );
}}

.scene-feature .background-layer {{
    background:
        radial-gradient(circle at 79% 52%, rgba(86, 196, 255, 0.22), transparent 22%),
        radial-gradient(circle at 14% 85%, rgba(155, 92, 255, 0.28), transparent 34%),
        linear-gradient(135deg, #080b1d 0%, #101b37 56%, #201042 100%);
}}

.scene-feature_grid .background-layer {{
    background:
        radial-gradient(circle at 50% -10%, rgba(78, 149, 255, 0.45), transparent 47%),
        linear-gradient(150deg, #08091b 0%, #15153b 58%, #211448 100%);
}}

.scene-stats .background-layer {{
    background:
        radial-gradient(circle at 79% 24%, rgba(83, 223, 200, 0.19), transparent 28%),
        radial-gradient(circle at 16% 80%, rgba(117, 91, 255, 0.32), transparent 38%),
        linear-gradient(135deg, #071323 0%, #0e2139 53%, #1b1040 100%);
}}

.cta-gradient {{
    background:
        radial-gradient(
            circle at 50% 35%,
            rgba(59, 130, 246, 0.55),
            transparent 38%
        ),
        linear-gradient(
            135deg,
            #07111f 0%,
            #18245c 50%,
            #32175b 100%
        );
}}

.headline {{
    position: relative;
    z-index: 5;
    margin: 0;
    color: white;
    font-weight: 760;
    letter-spacing: -0.052em;
    text-wrap: balance;
    text-shadow: 0 5px 24px rgba(0, 0, 0, 0.22);
}}

.hero-headline {{
    position: absolute;
    left: var(--canvas-pad);
    top: 50%;
    width: min(48%, 880px);
    margin: 0;
    font-size: var(--headline-size);
    line-height: 0.94;
    transform: translateY(-67%);
}}

.feature-headline {{
    position: absolute;
    left: var(--canvas-pad);
    top: 19%;
    width: min(70%, 1180px);
    margin: 0;
    font-size: clamp(46px, 4.2vw, 82px);
    line-height: 0.98;
}}

.body-text {{
    position: absolute;
    z-index: 5;
    color: rgba(239, 244, 255, 0.82);
    font-weight: 470;
    letter-spacing: -0.022em;
}}

.hero-text {{
    left: var(--canvas-pad);
    width: min(42%, 720px);
    font-size: var(--body-size);
    line-height: 1.22;
}}

.hero-text:nth-of-type(1) {{ top: 59%; }}
.hero-text:nth-of-type(2) {{ top: 68%; color: rgba(181, 201, 255, 0.95); font-size: clamp(19px, 1.45vw, 28px); }}

.feature-text {{
    left: var(--canvas-pad);
    width: min(57%, 930px);
    margin: 0;
    font-size: var(--body-size);
    line-height: 1.18;
}}

.feature-text::before {{
    display: inline-block;
    width: 0.58em;
    height: 0.58em;
    margin-right: 0.55em;
    border-radius: 50%;
    background: linear-gradient(135deg, #79a7ff, #c192ff);
    box-shadow: 0 0 18px rgba(139, 112, 255, 0.65);
    content: "";
}}

/* Supporting copy has fixed, non-overlapping reading zones. Inline
   offsets from older plans are deliberately overridden: their 70px
   spacing was insufficient for a two-line sentence at ad-sized type. */
.feature-text:nth-of-type(1) {{ top: 52% !important; }}
.feature-text:nth-of-type(2) {{ top: 67% !important; }}
.feature-text:nth-of-type(3) {{ top: 80% !important; }}

.signal-field {{
    position: absolute;
    z-index: 4;
    top: 16%;
    right: 7%;
    width: min(37%, 650px);
    height: 68%;
    overflow: hidden;
    border: 1px solid rgba(163, 195, 255, 0.18);
    border-radius: 34px;
    background: linear-gradient(145deg, rgba(99, 139, 255, 0.13), rgba(63, 29, 117, 0.08));
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1), 0 36px 90px rgba(0, 0, 0, 0.34);
}}

.signal-halo {{
    position: absolute;
    top: 11%;
    right: 12%;
    width: 48%;
    aspect-ratio: 1;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(102, 197, 255, 0.42) 0 6%, rgba(109, 88, 255, 0.18) 26%, transparent 68%);
    filter: blur(2px);
}}

.signal-track {{
    position: absolute;
    top: 19%;
    right: 25%;
    width: 2px;
    height: 63%;
    background: linear-gradient(180deg, transparent, rgba(114, 183, 255, 0.8), rgba(172, 116, 255, 0.75), transparent);
    box-shadow: 0 0 20px rgba(105, 164, 255, 0.75);
}}

.signal-node {{
    position: absolute;
    right: calc(25% - 8px);
    width: 18px;
    height: 18px;
    border: 3px solid #d8e7ff;
    border-radius: 50%;
    background: #7058ff;
    box-shadow: 0 0 22px rgba(114, 118, 255, 0.92);
}}

.signal-node-a {{ top: 24%; }}
.signal-node-b {{ top: 48%; background: #3ac0ff; }}
.signal-node-c {{ top: 70%; background: #bd80ff; }}

.signal-card {{
    position: absolute;
    left: 9%;
    width: 55%;
    height: 12%;
    padding: 7% 8%;
    border: 1px solid rgba(199, 219, 255, 0.22);
    border-radius: 14px;
    background: rgba(8, 18, 49, 0.6);
    box-shadow: 0 10px 26px rgba(1, 4, 20, 0.28);
}}

.signal-card i {{
    display: block;
    height: 7px;
    margin: 0 0 9px;
    border-radius: 999px;
    background: linear-gradient(90deg, rgba(209, 225, 255, 0.9), rgba(115, 170, 255, 0.45));
}}

.signal-card i:nth-child(2) {{ width: 72%; opacity: 0.68; }}
.signal-card i:nth-child(3) {{ width: 48%; opacity: 0.42; }}
.signal-card-a {{ top: 19%; }}
.signal-card-b {{ top: 43%; left: 26%; width: 57%; }}
.signal-card-c {{ top: 67%; left: 12%; width: 51%; }}

.grid-header {{
    position: relative;
    z-index: 5;
    margin: 9.5% auto 5%;
    width: min(78%, 1260px);
    text-align: center;
    font-size: clamp(45px, 4vw, 78px);
    line-height: 0.98;
}}

.visual-image {{
    position: absolute;
    object-fit: cover;
    z-index: 2;
    display: block;
    border: 1px solid rgba(177, 204, 255, 0.26);
    box-shadow: 0 32px 100px rgba(0, 0, 0, 0.42), 0 0 60px rgba(103, 85, 255, 0.16);
    filter: saturate(1.08) contrast(1.03);
    will-change: opacity, transform;
}}

.hero-image {{
    right: 5.5%;
    top: 50%;
    width: min(48%, 860px);
    height: 58%;
    border-radius: clamp(22px, 2vw, 38px);
    opacity: 0.96;
    transform: translateY(-50%);
}}

.full-image {{
    inset: 0;
    width: 100%;
    height: 100%;
    border: 0;
    border-radius: 0;
    box-shadow: none;
    opacity: 0.78;
    filter: saturate(1.04) contrast(1.04) brightness(0.78);
}}

.image-headline {{
    position: absolute;
    left: var(--canvas-pad);
    bottom: 23%;
    width: min(58%, 920px);
    font-size: var(--headline-size);
    line-height: 0.96;
}}

.image-text {{
    left: var(--canvas-pad);
    bottom: 13%;
    width: min(50%, 760px);
    font-size: clamp(22px, 2vw, 38px);
    line-height: 1.2;
}}

/* Image scenes use a top-to-bottom editorial lockup rather than three
   competing elements anchored to the same lower-third region. */
.scene-image .image-headline {{
    top: 15%;
    bottom: auto;
    width: min(44%, 790px);
}}

.scene-image .image-text {{
    left: var(--canvas-pad);
    width: min(39%, 680px);
    bottom: auto;
}}

.scene-image .image-text:nth-of-type(1) {{ top: 49%; }}
.scene-image .image-text:nth-of-type(2) {{ top: 64%; color: rgba(206, 220, 255, 0.96); }}

.layout-split_left.scene-image .image-headline,
.layout-split_left.scene-image .image-text {{ left: 8%; }}

.layout-split_right.scene-image .image-headline,
.layout-split_right.scene-image .image-text {{
    right: 8%;
    left: auto;
}}
/* ---------------------------------
   Layout-specific composition
   --------------------------------- */

/* SPLIT LEFT */

.layout-split_left .hero-headline,
.layout-split_left .feature-headline {{
    position: absolute;
    left: 8%;
    top: 19%;
    transform: none;
    margin: 0;
    width: min(39%, 700px);
    max-width: none;
}}

.layout-split_left .feature-text {{
    position: absolute;
    left: 8%;
    width: min(35%, 620px);
    margin: 0;
}}

.layout-split_left .hero-image {{
    right: 5%;
    top: 50%;
    bottom: auto;
    transform: translateY(-50%);
    width: 48%;
    height: 60%;
}}


/* SPLIT RIGHT */

.layout-split_right .hero-headline,
.layout-split_right .feature-headline {{
    position: absolute;
    right: 8%;
    top: 19%;
    transform: none;
    margin: 0;
    width: min(39%, 700px);
    max-width: none;
}}

.layout-split_right .feature-text {{
    position: absolute;
    right: 8%;
    width: min(35%, 620px);
    margin: 0;
}}

.layout-split_right .hero-image {{
    left: 5%;
    right: auto;
    top: 50%;
    bottom: auto;
    transform: translateY(-50%);
    width: 48%;
    height: 60%;
}}


/* FULL BLEED */

.layout-full_bleed .full-image {{
    opacity: 0.8;
    transform: scale(1.04);
}}

.layout-full_bleed .image-headline {{
    left: 8%;
    bottom: 18%;
    max-width: 65%;
    text-shadow: 0 8px 30px rgba(0, 0, 0, 0.6);
}}


/* CARDS */

.layout-cards .icon-card {{
    width: 20.5%;
    min-height: 300px;
    margin: 0 1.2%;
}}

.feature-grid-cards,
.stats-cards {{
    position: relative;
    z-index: 5;
    display: flex;
    justify-content: center;
    align-items: stretch;
    width: min(92%, 1660px);
    margin: 0 auto;
    gap: clamp(18px, 2vw, 38px);
}}

.feature-grid-cards .icon-card,
.stats-cards .stat-card {{
    flex: 1 1 0;
    width: auto;
    max-width: 390px;
    margin: 0;
}}


/* DASHBOARD */

.layout-dashboard .hero-image {{
    left: 50%;
    right: auto;
    top: 54%;
    bottom: auto;
    transform: translate(-50%, -50%);
    width: 80%;
    height: 64%;
}}

.layout-dashboard .hero-headline {{
    position: absolute;
    left: 8%;
    top: 8%;
    margin: 0;
    max-width: 70%;
    font-size: clamp(42px, 3.5vw, 70px);
}}


/* KINETIC */

.layout-kinetic .hero-headline,
.layout-kinetic .feature-headline {{
    position: relative;
    margin: 0;
    max-width: 85%;
    text-align: center;
    font-size: clamp(60px, 6vw, 114px);
    line-height: 0.92;
}}

.layout-kinetic .feature-text {{
    position: relative;
    margin: 30px auto 0;
    max-width: 65%;
    text-align: center;
}}

.glass-card {{
    position: relative;
    z-index: 5;
    overflow: hidden;
    border: 1px solid rgba(194, 213, 255, 0.2);
    border-radius: 26px;
    background: linear-gradient(145deg, rgba(255, 255, 255, 0.12), rgba(163, 148, 255, 0.045));
    backdrop-filter: blur(20px);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12), 0 24px 65px rgba(0, 0, 0, 0.26);
}}

.glass-card::before {{
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 2px;
    background: linear-gradient(90deg, transparent, rgba(151, 183, 255, 0.78), transparent);
    content: "";
}}

.icon-card {{
    display: inline-flex;
    flex-direction: column;
    justify-content: center;
    vertical-align: top;
    width: 21%;
    min-height: 300px;
    margin: 0 1.35%;
    padding: clamp(25px, 2.2vw, 42px);
    text-align: left;
    will-change: opacity, transform;
}}

.feature-icon {{
    margin-bottom: 28px;
    color: #dce9ff;
    font-size: clamp(42px, 3.4vw, 64px);
    text-shadow: 0 0 28px rgba(133, 158, 255, 0.75);
}}

.feature-title {{
    color: #f6f8ff;
    font-size: clamp(23px, 1.8vw, 34px);
    font-weight: 650;
    letter-spacing: -0.028em;
    line-height: 1.08;
}}

.stats-header {{
    position: relative;
    z-index: 5;
    display: block;
    width: min(78%, 1180px);
    margin: 11% auto 5%;
    color: white;
    font-size: clamp(44px, 4vw, 78px);
    line-height: 0.98;
    text-align: center;
}}

.stat-card {{
    display: inline-block;
    width: min(25%, 390px);
    min-height: 210px;
    margin: 1.3%;
    padding: 42px 34px;
    vertical-align: top;
    text-align: left;
    will-change: opacity, transform;
}}

.stat-value {{
    color: white;
    font-size: clamp(30px, 2.7vw, 54px);
    font-weight: 720;
    letter-spacing: -0.045em;
    line-height: 1.02;
}}

.stat-label {{
    margin-top: 16px;
    color: rgba(225, 235, 255, 0.68);
    font-size: clamp(17px, 1.25vw, 24px);
    line-height: 1.2;
}}

/* Stats use glass_card primitives, whose visible label is card-title. */
.stat-card .card-title {{
    position: relative;
    z-index: 1;
    color: #ffffff;
    font-size: clamp(27px, 2.45vw, 48px);
    font-weight: 720;
    letter-spacing: -0.04em;
    line-height: 1.04;
    text-shadow: 0 2px 14px rgba(0, 0, 0, 0.34);
}}

.cta-headline {{
    position: absolute;
    left: 50%;
    top: 36%;
    z-index: 5;
    width: min(76%, 1120px);
    margin: 0;
    text-align: center;
    font-size: clamp(54px, 4.8vw, 94px);
    line-height: 0.96;
    transform: translate(-50%, -50%);
}}

.cta-button {{
    position: absolute;
    left: 50%;
    top: 60%;
    z-index: 5;
    width: fit-content;
    margin: 0;
    padding: 21px 42px;
    border-radius: 999px;
    background: linear-gradient(135deg, #f2f6ff, #bcd2ff);
    border: 1px solid rgba(255, 255, 255, 0.72);
    box-shadow: 0 14px 44px rgba(85, 123, 255, 0.42);
    color: white;
    color: #111a42;
    font-size: clamp(21px, 1.65vw, 31px);
    font-weight: 720;
    letter-spacing: -0.025em;
    transform-origin: center;
    transform: translateX(-50%);
}}
.accent-line {{
    position: absolute;
    left: var(--canvas-pad);
    top: 9%;
    width: clamp(82px, 9vw, 170px);
    height: 5px;
    border-radius: 999px;
    background: linear-gradient(
        90deg,
        #3b82f6,
        #8b5cf6
    );
    z-index: 5;
    transform-origin: left center;
}}

.spark {{
    position: absolute;
    z-index: 5;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: white;
    box-shadow:
        0 0 24px rgba(206, 218, 255, 0.95);
}}

/* ---------------------------------
   Theme projection

   The planner's theme changes this whole visual layer.  Layout and motion
   remain deterministic, but a warm editorial brief must not inherit the
   default dark-tech art direction.
   --------------------------------- */

html,
body,
.composition {{
    background: var(--canvas);
}}

.scene::before {{
    background:
        linear-gradient(90deg, var(--overlay), transparent 48%),
        radial-gradient(circle at 56% 48%, transparent 0 45%, var(--overlay) 100%);
}}

.scene::after {{
    background-image:
        linear-gradient(var(--border) 1px, transparent 1px),
        linear-gradient(90deg, var(--border) 1px, transparent 1px);
    opacity: 0.20;
}}

.background-layer {{
    background:
        radial-gradient(circle at 18% 18%, var(--glow), transparent 36%),
        radial-gradient(circle at 82% 76%, var(--glow-alt), transparent 42%),
        linear-gradient(135deg, var(--canvas) 0%, var(--canvas-deep) 100%);
}}

.scene-feature .background-layer {{
    background:
        radial-gradient(circle at 79% 52%, var(--glow), transparent 24%),
        radial-gradient(circle at 14% 85%, var(--glow-alt), transparent 37%),
        linear-gradient(135deg, var(--canvas) 0%, var(--canvas-deep) 100%);
}}

.scene-feature_grid .background-layer {{
    background:
        radial-gradient(circle at 50% -10%, var(--glow), transparent 49%),
        linear-gradient(150deg, var(--canvas) 0%, var(--canvas-deep) 100%);
}}

.scene-stats .background-layer {{
    background:
        radial-gradient(circle at 79% 24%, var(--glow), transparent 31%),
        radial-gradient(circle at 16% 80%, var(--glow-alt), transparent 39%),
        linear-gradient(135deg, var(--canvas) 0%, var(--canvas-deep) 100%);
}}

.cta-gradient {{
    background:
        radial-gradient(circle at 50% 35%, var(--glow), transparent 40%),
        linear-gradient(135deg, var(--canvas) 0%, var(--canvas-deep) 100%);
}}

.headline,
.stats-header,
.stat-value,
.stat-card .card-title,
.feature-title {{
    color: var(--ink);
}}

.body-text,
.hero-text:nth-of-type(2),
.scene-image .image-text:nth-of-type(2),
.stat-label {{
    color: var(--muted);
}}

.feature-text::before {{
    background: linear-gradient(135deg, var(--accent), var(--accent-alt));
    box-shadow: 0 0 18px var(--glow);
}}

.accent-line {{
    background: linear-gradient(90deg, var(--accent), var(--accent-alt));
}}

.spark {{
    background: var(--accent-alt);
    box-shadow: 0 0 24px var(--glow);
}}

.glass-card,
.signal-field {{
    border-color: var(--border);
    background: linear-gradient(145deg, var(--surface-deep), var(--surface));
    box-shadow: inset 0 1px 0 var(--border), 0 24px 65px var(--shadow);
}}

.glass-card::before {{
    background: linear-gradient(90deg, transparent, var(--accent-alt), transparent);
}}

.feature-icon {{
    color: var(--accent);
    text-shadow: 0 0 28px var(--glow);
}}

.visual-image {{
    border-color: var(--border);
    box-shadow: 0 32px 100px var(--shadow), 0 0 60px var(--glow-alt);
}}

.signal-halo {{
    background: radial-gradient(circle, var(--glow) 0 6%, var(--glow-alt) 26%, transparent 68%);
}}

.signal-track {{
    background: linear-gradient(180deg, transparent, var(--accent), var(--accent-alt), transparent);
    box-shadow: 0 0 20px var(--glow);
}}

.signal-node {{
    border-color: var(--ink);
    background: var(--accent);
    box-shadow: 0 0 22px var(--glow);
}}

.signal-node-b {{ background: var(--accent-alt); }}
.signal-node-c {{ background: var(--accent); }}

.signal-card {{
    border-color: var(--border);
    background: var(--surface-deep);
    box-shadow: 0 10px 26px var(--shadow);
}}

.signal-card i {{
    background: linear-gradient(90deg, var(--ink), var(--accent-alt));
}}

.cta-button {{
    border-color: var(--accent-alt);
    background: linear-gradient(135deg, var(--accent), var(--accent-alt));
    box-shadow: 0 14px 44px var(--glow);
    color: var(--button-ink);
}}

@media (max-aspect-ratio: 3 / 4) {{
    .scene {{
        --canvas-pad: 8%;
        --headline-size: clamp(52px, 9.5vw, 96px);
        --body-size: clamp(24px, 4.3vw, 42px);
    }}

    .hero-headline,
    .feature-headline {{
        width: 84%;
    }}

    .hero-headline {{ top: 28%; transform: none; }}
    .hero-text {{ width: 82%; }}
    .hero-text:nth-of-type(1) {{ top: 47%; }}
    .hero-text:nth-of-type(2) {{ top: 56%; }}

    .hero-image {{
        top: auto;
        right: 8%;
        bottom: 8%;
        width: 84%;
        height: 31%;
        transform: none;
    }}

    .layout-split_left .hero-headline,
    .layout-split_right .hero-headline,
    .layout-split_left .feature-headline,
    .layout-split_right .feature-headline {{
        right: auto;
        left: 8%;
        top: 17%;
        width: 84%;
        transform: none;
    }}

    .layout-split_left .feature-text,
    .layout-split_right .feature-text {{
        right: auto;
        left: 8%;
        width: 82%;
    }}

    .feature-text:nth-of-type(1) {{ top: 48% !important; }}
    .feature-text:nth-of-type(2) {{ top: 62% !important; }}
    .feature-text:nth-of-type(3) {{ top: 76% !important; }}

    .signal-field {{
        top: auto;
        right: 8%;
        bottom: 7%;
        width: 84%;
        height: 31%;
        opacity: 0.82;
    }}

    .layout-split_left .hero-image,
    .layout-split_right .hero-image {{
        right: 8%;
        left: auto;
        top: auto;
        bottom: 8%;
        width: 84%;
        height: 31%;
        transform: none;
    }}

    .grid-header, .stats-header {{
        width: 84%;
        margin-top: 13%;
        font-size: clamp(42px, 8vw, 76px);
    }}

    .icon-card {{
        width: 39%;
        min-height: 185px;
        margin: 1.4% 2.2%;
        padding: 24px;
    }}

    .feature-grid-cards,
    .stats-cards {{
        width: 86%;
        flex-wrap: wrap;
        gap: 16px;
    }}

    .feature-grid-cards .icon-card {{
        flex: 0 0 calc(50% - 8px);
        width: calc(50% - 8px);
        margin: 0;
    }}

    .stats-cards .stat-card {{
        flex: 0 0 100%;
        width: 100%;
        margin: 0;
    }}

    .stat-card {{
        display: block;
        width: 78%;
        min-height: 0;
        margin: 3% auto;
        padding: 25px 28px;
    }}

    .image-headline {{
        bottom: 24%;
        width: 80%;
    }}

    .image-text {{
        bottom: 14%;
        width: 78%;
    }}

    .scene-image .image-headline {{ top: 14%; bottom: auto; width: 82%; }}
    .scene-image .image-text {{ left: 8%; width: 80%; bottom: auto; }}
    .scene-image .image-text:nth-of-type(1) {{ top: 50%; }}
    .scene-image .image-text:nth-of-type(2) {{ top: 63%; }}

    .cta-headline {{ top: 35%; width: 84%; }}
    .cta-button {{ top: 57%; }}
}}
""".strip()

    def _write(
        self,
        filename: str,
        content: str,
    ) -> None:

        path = self.output_dir / filename

        path.write_text(
            content,
            encoding="utf-8",
        )
