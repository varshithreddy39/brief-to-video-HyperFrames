from __future__ import annotations

from html import escape


def esc(value: str) -> str:
    """Safely escape text before inserting it into HTML."""
    return escape(str(value))


def scene_container(
    scene_id: str,
    scene_type: str,
    start: float,
    duration: float,
    content: str,
    layout: str = "center_stage",
) -> str:
    """
    Create the root HTML container for a HyperFrames scene.

    The layout is selected by GPT-5.5 in SceneDesign and is used
    by the deterministic compiler to control scene composition.
    """

    return f"""
<section
    id="{esc(scene_id)}"
    class="scene scene-{esc(scene_type)} layout-{esc(layout)}"
    data-composition-id="{esc(scene_id)}"
    data-start="{start:.3f}"
    data-duration="{duration:.3f}"
>
{content}
</section>
""".strip()


def background(
    scene_id: str,
    theme_class: str = "gradient-bg",
) -> str:
    """
    Reusable animated background layer.
    """

    return f"""
<div
    id="{esc(scene_id)}_background"
    class="background-layer {esc(theme_class)}"
    data-role="background"
    data-layout-allow-occlusion="true"
></div>
""".strip()


def headline(
    element_id: str,
    text: str,
    class_name: str = "headline",
) -> str:
    """
    Render a headline element with a stable semantic ID.
    """

    return f"""
<h1
    id="{esc(element_id)}"
    class="{esc(class_name)}"
    data-role="headline"
>
    {esc(text)}
</h1>
""".strip()


def body_text(
    element_id: str,
    text: str,
    class_name: str = "body-text",
    style: str = "",
) -> str:
    """
    Render a normal text element.
    """
    style_attr = f' style="{esc(style)}"' if style else ""

    return f"""
<p
    id="{esc(element_id)}"
    class="{esc(class_name)}"
    data-role="text"{style_attr}
>
    {esc(text)}
</p>
""".strip()


def image(
    element_id: str,
    image_path: str,
    class_name: str = "visual-image",
    asset_id: str | None = None,
) -> str:
    """
    Render an image asset.

    The path is inserted as a local file URL so HyperFrames
    can load the generated asset during rendering.
    """

    asset_attr = (
        f' data-asset-id="{esc(asset_id)}"'
        if asset_id
        else ""
    )

    return f"""
<img
    id="{esc(element_id)}"
    class="{esc(class_name)}"
    src="{esc(image_path)}"
    data-role="image"
    {asset_attr}
    alt=""
/>
""".strip()


def glass_card(
    element_id: str,
    title: str,
    description: str = "",
    class_name: str = "glass-card",
) -> str:
    """
    Reusable glassmorphism card.
    """

    description_html = ""

    if description:
        description_html = f"""
<p class="card-description">
    {esc(description)}
</p>
""".strip()

    return f"""
<div
    id="{esc(element_id)}"
    class="{esc(class_name)}"
    data-role="card"
>
    <div class="card-title">
        {esc(title)}
    </div>

    {description_html}
</div>
""".strip()


def stat_card(
    element_id: str,
    value: str,
    label: str,
) -> str:
    """
    Reusable metric/stat card.
    """

    return f"""
<div
    id="{esc(element_id)}"
    class="stat-card glass-card"
    data-role="stat"
>
    <div class="stat-value">
        {esc(value)}
    </div>

    <div class="stat-label">
        {esc(label)}
    </div>
</div>
""".strip()


def cta_button(
    element_id: str,
    text: str,
) -> str:
    """
    Reusable CTA button.
    """

    return f"""
<div
    id="{esc(element_id)}"
    class="cta-button"
    data-role="cta"
>
    {esc(text)}
</div>
""".strip()


def accent_line(
    element_id: str,
    class_name: str = "accent-line",
) -> str:
    """
    Reusable decorative accent line.
    """

    return f"""
<div
    id="{esc(element_id)}"
    class="{esc(class_name)}"
    data-role="accent"
></div>
""".strip()


def icon_card(
    element_id: str,
    icon: str,
    title: str,
) -> str:
    """
    Simple card for feature-grid scenes.
    """

    return f"""
<div
    id="{esc(element_id)}"
    class="icon-card glass-card"
    data-role="feature-card"
>
    <div class="feature-icon">
        {esc(icon)}
    </div>

    <div class="feature-title">
        {esc(title)}
    </div>
</div>
""".strip()


def signal_field(
    element_id: str,
) -> str:
    """A deterministic product-motion visual for feature scenes.

    It gives a text-led feature scene a specific visual metaphor (many
    fragments resolving into one signal) without asking an image model to
    invent unreadable UI microcopy.
    """

    return f"""
<div
    id="{esc(element_id)}"
    class="signal-field"
    data-role="visual"
    aria-hidden="true"
>
    <div class="signal-halo"></div>
    <div class="signal-track"></div>
    <div class="signal-node signal-node-a"></div>
    <div class="signal-node signal-node-b"></div>
    <div class="signal-node signal-node-c"></div>
    <div class="signal-card signal-card-a"><i></i><i></i><i></i></div>
    <div class="signal-card signal-card-b"><i></i><i></i></div>
    <div class="signal-card signal-card-c"><i></i><i></i><i></i></div>
</div>
""".strip()


def spark(
    element_id: str,
    left: str | None = None,
    top: str | None = None,
    right: str | None = None,
    bottom: str | None = None,
) -> str:
    """
    Small decorative AI spark element.
    """
    style_parts = []
    if left is not None:
        style_parts.append(f"left: {left};")
    if right is not None:
        style_parts.append(f"right: {right};")
    if top is not None:
        style_parts.append(f"top: {top};")
    if bottom is not None:
        style_parts.append(f"bottom: {bottom};")

    style_attr = f' style="{" ".join(style_parts)}"' if style_parts else ""

    return f"""
<div
    id="{esc(element_id)}"
    class="spark"
    data-role="spark"{style_attr}
></div>
""".strip()


def arrow(
    element_id: str,
) -> str:
    """
    Forward-motion arrow used by feature scenes.
    """

    return f"""
<div
    id="{esc(element_id)}"
    class="momentum-arrow"
    data-role="arrow"
>
    →
</div>
""".strip()
