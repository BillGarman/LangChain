from pathlib import Path
from typing import Iterable, cast

from tomlkit import dump, inline_table, load
from tomlkit.container import Container
from tomlkit.items import InlineTable


def _get_dep_inline_table(path: Path) -> InlineTable:
    dep = inline_table()
    dep.update({"path": str(path), "develop": True})
    return dep


def add_dependencies_to_pyproject_toml(
    pyproject_toml: Path, local_editable_dependencies: Iterable[tuple[str, Path]]
) -> None:
    """Add dependencies to pyproject.toml."""
    with open(pyproject_toml, encoding="utf-8") as f:
        pyproject = load(f)
        cast(Container, pyproject["tool.poetry.dependencies"]).update(
            {
                name: _get_dep_inline_table(loc.relative_to(pyproject_toml.parent))
                for name, loc in local_editable_dependencies
            }
        )
    with open(pyproject_toml, "w", encoding="utf-8") as f:
        dump(pyproject, f)


def remove_dependencies_from_pyproject_toml(
    pyproject_toml: Path, local_editable_dependencies: Iterable[str]
) -> None:
    """Remove dependencies from pyproject.toml."""
    with open(pyproject_toml, encoding="utf-8") as f:
        pyproject = load(f)
        dependencies = cast(Container, pyproject["tool.poetry.dependencies"])
        for name in local_editable_dependencies:
            try:
                del dependencies[name]
            except KeyError:
                pass
    with open(pyproject_toml, "w", encoding="utf-8") as f:
        dump(pyproject, f)
