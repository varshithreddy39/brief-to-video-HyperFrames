from __future__ import annotations

from app.core.models import MotionSpec
from app.core.models import Scene

def selector(target: str) -> str:
    if not target or not target.strip():
        raise ValueError("Motion target cannot be empty.")

    safe_target = target.replace('"', '\\"')
    return f'#{safe_target}'

def build_motion_at(
    motion: MotionSpec,
    position: float,
    target_override: str | None = None,
) -> str:
    target = selector(target_override or motion.target)
    duration = motion.duration
    rendered_target = target_override or motion.target

    if motion.type == "fade_in":
        return (
            f'tl.fromTo("{target}", '
            f'{{opacity: 0}}, '
            f'{{opacity: 1, duration: {duration}, ease: "power2.out"}}, '
            f'{position});'
        )

    if motion.type == "fade_up":
        return (
            f'tl.fromTo("{target}", '
            f'{{opacity: 0, y: 40}}, '
            f'{{opacity: 1, y: 0, duration: {duration}, ease: "power3.out"}}, '
            f'{position});'
        )

    if motion.type == "slide_left":
        return (
            f'tl.fromTo("{target}", '
            f'{{opacity: 0, x: 80}}, '
            f'{{opacity: 1, x: 0, duration: {duration}, ease: "power3.out"}}, '
            f'{position});'
        )

    if motion.type == "slide_right":
        return (
            f'tl.fromTo("{target}", '
            f'{{opacity: 0, x: -80}}, '
            f'{{opacity: 1, x: 0, duration: {duration}, ease: "power3.out"}}, '
            f'{position});'
        )

    if motion.type == "scale_in":
        if rendered_target.endswith("_accent"):
            # Accent lines are decorative punctuation, not a hero object.
            # Keep them visible from the first frame and use a short scale
            # emphasis so a long model-supplied duration cannot violate an
            # appears-by assertion during seek-based validation.
            accent_duration = min(duration, 0.45)
            return (
                f'tl.fromTo("{target}", '
                f'{{opacity: 1, scaleX: 0.86}}, '
                f'{{opacity: 1, scaleX: 1, duration: {accent_duration}, '
                f'ease: "power2.out"}}, '
                f'{position});'
            )

        return (
            f'tl.fromTo("{target}", '
            f'{{opacity: 0, scale: 0.85}}, '
            f'{{opacity: 1, scale: 1, duration: {duration}, ease: "back.out(1.15)"}}, '
            f'{position});'
        )

    if motion.type == "type_reveal":
        return (
            f'tl.fromTo("{target}", '
            f'{{opacity: 0, clipPath: "inset(0 100% 0 0)"}}, '
            f'{{opacity: 1, clipPath: "inset(0 0% 0 0)", duration: {duration}, ease: "power3.out"}}, '
            f'{position});'
        )

    if motion.type == "image_zoom":
        # A full-frame image has no spare geometry to scale into. Scaling it
        # pushes its box outside the canvas, which both looks like a cheap
        # camera zoom and fails HyperFrames' off-frame check.  Move the crop
        # inside a fixed image viewport instead: the image stays in frame
        # while the viewer still gets a slow, cinematic camera drift.
        return (
            f'tl.fromTo("{target}", '
            f'{{objectPosition: "50% 50%"}}, '
            f'{{objectPosition: "54% 50%", duration: {duration}, ease: "none"}}, '
            f'{position});'
        )

    if motion.type == "stagger":
        return (
            f'tl.fromTo("{target}", '
            f'{{opacity: 0, y: 24}}, '
            f'{{opacity: 1, y: 0, duration: {duration}, ease: "power3.out"}}, '
            f'{position});'
        )

    raise ValueError(
        f"Unsupported motion type: {motion.type}"
    )
def build_timeline(
    scenes: list[Scene],
    asset_target_map: dict[str, str] | None = None,
) -> str:
    """
    Build a deterministic GSAP timeline using
    each scene's absolute start time.
    """

    lines = [
        "const tl = gsap.timeline({ paused: true });",
        "",
    ]

    asset_target_map = asset_target_map or {}

    for scene in scenes:
        # Every scene gets a low-amplitude ambient change through its final
        # beat. This is a deterministic safety net for plans whose CTA or
        # card entrances finish early; it prevents a dead, frozen end frame
        # without changing the story or moving text out of its layout zone.
        ambient_target = selector(f"{scene.id}_background")
        ambient_start = scene.start
        ambient_duration = max(0.8, scene.duration / 2)
        lines.append(
            f'tl.fromTo("{ambient_target}", '
            f'{{opacity: 0.94}}, '
            f'{{opacity: 1, duration: {ambient_duration}, '
            f'ease: "sine.inOut", repeat: 1, yoyo: true}}, '
            f'{ambient_start});'
        )

        if scene.type == "feature":
            signal_target = selector(f"{scene.id}_signal")
            lines.append(
                f'tl.to("{signal_target}", '
                f'{{x: -12, duration: {scene.duration:.3f}, ease: "sine.inOut", '
                f'repeat: 1, yoyo: true}}, {scene.start});'
            )

        for motion in scene.motion:
            position = scene.start + motion.delay
            if motion.type in {
                "fade_in",
                "fade_up",
                "slide_left",
                "slide_right",
                "scale_in",
                "stagger",
                "type_reveal",
            }:
                position = max(0.0, position - 0.05)

            lines.append(
                build_motion_at(
                    motion,
                    position,
                    target_override=asset_target_map.get(motion.target),
                )
            )

    lines.extend(
        [
            "",
            'window.__timelines["main"] = tl;',
        ]
    )

    return "\n".join(lines)
