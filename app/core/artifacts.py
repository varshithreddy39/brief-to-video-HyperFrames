from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunArtifacts:
    """
    Standardized filesystem layout for a single video-generation run.

    Example:
        runs/<run_id>/
            brief.txt
            plan.json
            assets/
            composition/
            checks/
            snapshots/
            renders/
            logs/
    """

    root: Path

    @property
    def brief(self) -> Path:
        return self.root / "brief.txt"

    @property
    def plan(self) -> Path:
        return self.root / "plan.json"

    @property
    def assets(self) -> Path:
        return self.root / "assets"

    @property
    def composition(self) -> Path:
        return self.root / "composition"

    @property
    def checks(self) -> Path:
        return self.root / "checks"

    @property
    def snapshots(self) -> Path:
        return self.root / "snapshots"

    @property
    def renders(self) -> Path:
        return self.root / "renders"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def output_mp4(self) -> Path:
        return self.renders / "output.mp4"

    def check_output(self, attempt: int) -> Path:
        return self.checks / f"attempt_{attempt}.json"

    def ensure_directories(self) -> None:
        """Create all directories required for the run."""
        for directory in (
            self.root,
            self.assets,
            self.composition,
            self.checks,
            self.snapshots,
            self.renders,
            self.logs,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def create_run_artifacts(
    run_id: str,
    base_dir: str | Path = "runs",
) -> RunArtifacts:
    """
    Create and initialize the artifact directory for a run.

    Args:
        run_id: Deterministic or unique identifier for the run.
        base_dir: Root directory containing all pipeline runs.

    Returns:
        Initialized RunArtifacts instance.
    """
    if not run_id or not run_id.strip():
        raise ValueError("run_id cannot be empty.")

    base_path = Path(base_dir)
    artifacts = RunArtifacts(
        root=base_path / run_id.strip()
    )
    artifacts.ensure_directories()

    return artifacts