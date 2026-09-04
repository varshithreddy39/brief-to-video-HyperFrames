from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from openai import OpenAI, OpenAIError

from app.assets.registry import AssetRegistry
from app.core.client import client
from app.core.config import IMAGE_MODEL
from app.core.models import AssetSpec


class AssetGenerator:
    """
    Generates image assets using gpt-image-2 and manages
    their registration through AssetRegistry.
    """

    def __init__(
        self,
        output_dir: str | Path,
        openai_client: OpenAI | None = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.client = openai_client or client
        self.registry = AssetRegistry(self.output_dir)

    def generate(
        self,
        asset: AssetSpec,
        size: str = "1536x1024",
    ) -> Path:
        """
        Generate one asset.

        If the asset already exists in the registry,
        return the existing file instead of calling the API.
        """

        # 1. Check registry first.
        registered_path = self.registry.get(asset.id)

        if registered_path is not None:
            print(
                f"[AssetGenerator] Registry hit: {asset.id}"
            )
            return registered_path

        # 2. Build deterministic cache path.
        cache_key = self._build_cache_key(asset, size=size)
        output_path = self.output_dir / f"{cache_key}.png"

        # 3. Handle an existing file that isn't registered.
        if output_path.exists():
            print(
                f"[AssetGenerator] Cache file found: {asset.id}"
            )

            self.registry.register(
                asset.id,
                output_path,
            )

            return output_path

        print(
            f"[AssetGenerator] Generating asset: {asset.id}"
        )

        # 4. Call gpt-image-2.
        try:
            response = self.client.images.generate(
                model=IMAGE_MODEL,
                prompt=asset.prompt,
                size=size,
            )
        except OpenAIError as exc:
            raise RuntimeError(
                f"Image generation failed for asset "
                f"'{asset.id}': {exc}"
            ) from exc

        # 5. Validate API response.
        if not response.data:
            raise RuntimeError(
                f"Image generation returned no data "
                f"for asset '{asset.id}'."
            )

        image = response.data[0]

        b64_json = getattr(
            image,
            "b64_json",
            None,
        )

        if not b64_json:
            raise RuntimeError(
                f"Image generation returned no b64_json "
                f"for asset '{asset.id}'."
            )

        # 6. Decode base64.
        try:
            image_bytes = base64.b64decode(
                b64_json,
                validate=True,
            )
        except (ValueError, base64.binascii.Error) as exc:
            raise RuntimeError(
                f"Invalid base64 image returned for "
                f"asset '{asset.id}'."
            ) from exc

        if not image_bytes:
            raise RuntimeError(
                f"Decoded image is empty for asset "
                f"'{asset.id}'."
            )

        # 7. Save image.
        output_path.write_bytes(image_bytes)

        # 8. Register the generated asset.
        self.registry.register(
            asset.id,
            output_path,
        )

        print(
            f"[AssetGenerator] Saved: {output_path}"
        )

        return output_path

    def generate_all(
        self,
        assets: list[AssetSpec],
        size: str = "1536x1024",
    ) -> dict[str, Path]:
        """
        Generate all assets and return:

            asset_id -> image path
        """

        generated: dict[str, Path] = {}

        for asset in assets:
            generated[asset.id] = self.generate(asset, size=size)

        return generated

    @staticmethod
    def _build_cache_key(
        asset: AssetSpec,
        size: str = "1536x1024",
    ) -> str:
        """
        Build a deterministic cache key from the asset definition.
        """

        normalized = "|".join(
            [
                IMAGE_MODEL,
                asset.id,
                asset.type,
                asset.scene_id,
                " ".join(asset.prompt.split()),
                size,
            ]
        )

        return hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest()[:16]
