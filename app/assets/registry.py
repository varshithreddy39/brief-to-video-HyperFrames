from __future__ import annotations

import json
from pathlib import Path


class AssetRegistry:
    """
    Keeps track of generated assets for a video run.

    The registry maps:
        asset_id -> generated file path
    """

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.registry_path = self.output_dir / "registry.json"

        self._assets: dict[str, str] = {}

        self._load()

    def register(
        self,
        asset_id: str,
        path: str | Path,
    ) -> None:
        """
        Register an asset ID and its generated file path.
        """

        if not asset_id:
            raise ValueError(
                "Asset ID cannot be empty."
            )

        asset_path = Path(path)

        if not asset_path.exists():
            raise FileNotFoundError(
                f"Cannot register missing asset: {asset_path}"
            )

        self._assets[asset_id] = str(
            asset_path
        )

        self._save()

    def get(
        self,
        asset_id: str,
    ) -> Path | None:
        """
        Return the registered asset path.

        Returns None when the asset is not registered
        or the registered file no longer exists.
        """

        path = self._assets.get(asset_id)

        if path is None:
            return None

        asset_path = Path(path)

        if not asset_path.exists():
            return None

        return asset_path

    def contains(
        self,
        asset_id: str,
    ) -> bool:
        """
        Check whether an asset exists in the registry
        and its file is still present.
        """

        return self.get(asset_id) is not None

    def all(self) -> dict[str, Path]:
        """
        Return all currently available registered assets.
        """

        result: dict[str, Path] = {}

        for asset_id in self._assets:
            path = self.get(asset_id)

            if path is not None:
                result[asset_id] = path

        return result

    def remove(
        self,
        asset_id: str,
    ) -> None:
        """
        Remove an asset from the registry.

        This does not delete the actual image file.
        """

        self._assets.pop(asset_id, None)
        self._save()

    def clear(self) -> None:
        """
        Clear the registry.

        This does not delete image files.
        """

        self._assets.clear()
        self._save()

    def _load(self) -> None:
        if not self.registry_path.exists():
            return

        try:
            data = json.loads(
                self.registry_path.read_text(
                    encoding="utf-8"
                )
            )
        except (json.JSONDecodeError, OSError) as exc:
            raise RuntimeError(
                f"Failed to load asset registry: "
                f"{self.registry_path}"
            ) from exc

        if not isinstance(data, dict):
            raise RuntimeError(
                "Asset registry must contain a JSON object."
            )

        self._assets = {
            str(asset_id): str(path)
            for asset_id, path in data.items()
        }

    def _save(self) -> None:
        self.registry_path.write_text(
            json.dumps(
                self._assets,
                indent=2,
            ),
            encoding="utf-8",
        )