import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class PromptLoader:
    """Load and manage versioned prompts for essay evaluation."""

    def __init__(self, prompts_dir: Optional[str] = None, version: str = "v1.0.0") -> None:
        """
        Initialize the prompt loader.

        - If `prompts_dir` is None, resolve to `<package_root>/prompts` where
          package_root is the `creverse2` directory.
        - If `prompts_dir` is provided and not found relative to the CWD,
          also try resolving it relative to the package root.
        """
        package_root = Path(__file__).resolve().parents[2]

        if prompts_dir is None:
            # Default to the prompts directory inside the package root (creverse2/prompts)
            self.prompts_dir: Path = package_root / "prompts"
        else:
            # Try as provided first
            candidate = Path(prompts_dir)
            # If not exists, try relative to package root
            self.prompts_dir = candidate if candidate.exists() else (package_root / candidate)

        self.version = version
        self._prompts_cache: Dict[str, Dict[str, str]] = {}
        self._load_prompts()

    def _load_prompts(self) -> None:
        """Load all prompts from the versioned directory."""
        version_dir = self.prompts_dir / self.version

        if not version_dir.exists():
            raise FileNotFoundError(
                f"Prompts directory not found: {version_dir}. "
                f"Please ensure the prompts are properly set up in {version_dir}"
            )

        # Load prompts from JSON files
        required_files = ["introduction.json", "body.json", "conclusion.json", "grammar.json"]

        for filename in required_files:
            json_file = version_dir / filename
            if not json_file.exists():
                raise FileNotFoundError(f"Required prompt file not found: {json_file}")

            try:
                with open(json_file, "r", encoding="utf-8") as file:
                    prompts_data: Dict[str, str] = json.load(file)
                    rubric_item = json_file.stem
                    self._prompts_cache[rubric_item] = prompts_data

                # Validate that all required levels are present
                required_levels = ["Basic", "Intermediate", "Advanced", "Expert"]
                for level in required_levels:
                    if level not in prompts_data:
                        raise ValueError(f"Missing level '{level}' in {json_file}")

            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"Error loading prompts from {json_file}: {exc}") from exc

    def load_prompt(
        self,
        rubric_item: str,
        level_or_params: Optional[Union[str, Dict[str, Any]]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Load a specific prompt.

        This method is lenient to ease test/dev usage:
        - The second argument can be either a `level` string (e.g., "Basic") or a
          `params` dict. When a dict is provided, the level defaults to "Basic".
        - Any provided `params` are accepted but not applied to the prompt text
          (prompts are plain strings and may contain braces that would conflict
          with naive formatting).
        """
        # Validate rubric item
        if rubric_item not in self._prompts_cache:
            available_items = list(self._prompts_cache.keys())
            raise ValueError(
                f"No prompts found for rubric item: '{rubric_item}'. "
                f"Available items: {available_items}"
            )

        # Prompts grouped by level for this rubric item
        level_prompts: Dict[str, str] = self._prompts_cache[rubric_item]

        # Interpret the second argument
        if isinstance(level_or_params, dict):
            # When params dict is passed as second arg, default to Basic level
            level_group = "Basic"
            # Merge params if both provided; reserved for potential future use
            _ = {**level_or_params, **(params or {})}
        else:
            # Use provided level or default to Basic
            level_group = (level_or_params or "Basic")

        if level_group not in level_prompts:
            available_levels = list(level_prompts.keys())
            raise ValueError(
                f"No prompt found for level: '{level_group}' in rubric: '{rubric_item}'. "
                f"Available levels: {available_levels}"
            )

        return level_prompts[level_group]

    def get_available_rubric_items(self) -> List[str]:
        """Get list of available rubric items."""
        return list(self._prompts_cache.keys())

    def get_available_levels(self, rubric_item: str) -> List[str]:
        """Get list of available levels for a specific rubric item."""
        if rubric_item not in self._prompts_cache:
            return []
        return list(self._prompts_cache[rubric_item].keys())

    def reload_prompts(self) -> None:
        """Reload prompts from files (useful for development/testing)."""
        self._prompts_cache.clear()
        self._load_prompts()
