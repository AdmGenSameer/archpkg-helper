"""Recipe loading for the installation engine."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from arjax.config.logging import get_logger
from arjax.installation.models import ProviderConfig, Recipe

logger = get_logger(__name__)

try:
    import yaml
except ImportError:  # pragma: no cover - handled at runtime with a clear error
    yaml = None


@dataclass(slots=True)
class RecipeLocation:
    """Tracks where a recipe was loaded from."""

    path: Path
    recipe: Recipe


class RecipeStore:
    """Load declarative installation recipes from package and user directories."""

    def __init__(self, extra_dirs: Optional[Iterable[Path]] = None):
        package_dir = Path(__file__).resolve().parent.parent / "recipes"
        user_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "arjax" / "recipes"

        self.recipe_dirs: List[Path] = [package_dir, user_dir]
        if extra_dirs:
            self.recipe_dirs.extend(extra_dirs)

    def load_all(self) -> List[RecipeLocation]:
        """Load every YAML recipe available in the configured directories."""
        recipes: List[RecipeLocation] = []
        for recipe_file in self._recipe_files():
            recipe = self._load_recipe_file(recipe_file)
            if recipe:
                recipes.append(RecipeLocation(path=recipe_file, recipe=recipe))
        return recipes

    def find(self, name: str) -> Optional[Recipe]:
        """Find a recipe by file stem, declared name, or alias."""
        normalized = name.lower().strip()
        for location in self.load_all():
            recipe = location.recipe
            candidates = {recipe.name.lower(), location.path.stem.lower(), *(alias.lower() for alias in recipe.aliases)}
            if normalized in candidates:
                return recipe
        return None

    def list_names(self) -> List[str]:
        """Return the known recipe names for display/debugging."""
        names = []
        for location in self.load_all():
            names.append(location.recipe.name)
        return sorted(set(names))

    def _recipe_files(self) -> Iterable[Path]:
        for recipe_dir in self.recipe_dirs:
            if recipe_dir.exists():
                yield from sorted(recipe_dir.glob("*.y*ml"))

    def _load_recipe_file(self, path: Path) -> Optional[Recipe]:
        if yaml is None:
            raise RuntimeError("PyYAML is required to load installation recipes. Install pyyaml first.")

        try:
            raw_data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(raw_data, dict):
                logger.warning("Skipping recipe %s because it is not a mapping", path)
                return None

            providers = {}
            for provider_name, provider_data in (raw_data.get("providers") or {}).items():
                if not isinstance(provider_data, dict):
                    continue
                providers[provider_name.lower()] = ProviderConfig(
                    package=provider_data.get("package"),
                    package_manager=provider_data.get("package_manager"),
                    repo_url=provider_data.get("repo_url"),
                    key_url=provider_data.get("key_url"),
                    github_repo=provider_data.get("repo") or provider_data.get("github_repo"),
                    github_install_type=provider_data.get("install_type"),
                    github_download_url=provider_data.get("download_url"),
                    flatpak_id=provider_data.get("app_id") or provider_data.get("flatpak_id"),
                    snap_id=provider_data.get("snap_id") or provider_data.get("id"),
                    appimage_url=provider_data.get("url"),
                    appimage_name=provider_data.get("name"),
                    metadata={k: v for k, v in provider_data.items() if k not in {
                        "package", "package_manager", "repo_url", "key_url", "repo",
                        "github_repo", "install_type", "download_url", "app_id",
                        "flatpak_id", "snap_id", "id", "url", "name"
                    }},
                )

            return Recipe(
                name=str(raw_data.get("name") or path.stem),
                display_name=raw_data.get("display_name"),
                description=str(raw_data.get("description") or ""),
                aliases=list(raw_data.get("aliases") or []),
                providers=providers,
                metadata={k: v for k, v in raw_data.items() if k not in {"name", "display_name", "description", "aliases", "providers"}},
            )
        except Exception as exc:
            logger.warning("Failed to load recipe %s: %s", path, exc)
            return None
