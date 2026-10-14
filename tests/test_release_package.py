"""Tests for the release packaging script and the release configuration."""

import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "package-release.sh"

needs_zip = pytest.mark.skipif(
    shutil.which("zip") is None, reason="zip is not installed"
)


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A minimal repository layout with a built card for version 0.9.9."""
    (tmp_path / "scripts").mkdir()
    shutil.copy(SCRIPT, tmp_path / "scripts" / "package-release.sh")
    src = tmp_path / "custom_components" / "inkop"
    (src / "www").mkdir(parents=True)
    (src / "translations").mkdir()
    (src / "__pycache__").mkdir()
    (src / "manifest.json").write_text(
        json.dumps({"domain": "inkop", "name": "Inköp", "version": "0.1.0"})
    )
    (src / "__init__.py").write_text("")
    (src / "translations" / "en.json").write_text("{}")
    (src / "www" / "inkop-card.js").write_text('console.info("v0.9.9");')
    (src / "__pycache__" / "x.pyc").write_bytes(b"compiled")
    return tmp_path


def package(tree: Path, tag: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(tree / "scripts" / "package-release.sh"), tag],
        capture_output=True,
        text=True,
        check=False,
    )


@needs_zip
def test_builds_a_zip_with_the_integration_at_its_root(tree: Path) -> None:
    result = package(tree, "v0.9.9")

    assert result.returncode == 0, result.stderr
    names = zipfile.ZipFile(tree / "dist" / "inkop.zip").namelist()
    assert (
        "manifest.json" in names
    )  # HACS unpacks the zip into custom_components/inkop/
    assert "__init__.py" in names
    assert "translations/en.json" in names
    assert "www/inkop-card.js" in names


@needs_zip
def test_stamps_the_release_version_into_the_packaged_manifest_only(tree: Path) -> None:
    package(tree, "v0.9.9")

    archive = zipfile.ZipFile(tree / "dist" / "inkop.zip")
    packaged = json.loads(archive.read("manifest.json"))
    assert packaged == {"domain": "inkop", "name": "Inköp", "version": "0.9.9"}
    source = json.loads(
        (tree / "custom_components" / "inkop" / "manifest.json").read_text()
    )
    assert source["version"] == "0.1.0"  # the repository copy is left alone


@needs_zip
def test_leaves_out_python_caches(tree: Path) -> None:
    package(tree, "v0.9.9")

    names = zipfile.ZipFile(tree / "dist" / "inkop.zip").namelist()
    assert not [
        name for name in names if "__pycache__" in name or name.endswith(".pyc")
    ]


@needs_zip
def test_a_second_run_replaces_the_first(tree: Path) -> None:
    package(tree, "v0.9.9")
    (tree / "dist" / "stale.txt").write_text("old")

    assert package(tree, "v0.9.9").returncode == 0

    assert not (tree / "dist" / "stale.txt").exists()


@needs_zip
def test_accepts_a_pre_release_suffix(tree: Path) -> None:
    (tree / "custom_components" / "inkop" / "www" / "inkop-card.js").write_text(
        "0.9.9-beta1"
    )

    assert package(tree, "v0.9.9-beta1").returncode == 0


@pytest.mark.parametrize("tag", ["0.9.9", "v0.9", "v", "version", "vx.y.z"])
def test_rejects_tags_that_are_not_versions(tree: Path, tag: str) -> None:
    result = package(tree, tag)

    assert result.returncode != 0
    assert "must look like v1.2.3" in result.stderr
    assert not (tree / "dist").exists()


def test_needs_a_tag(tree: Path) -> None:
    result = subprocess.run(
        ["sh", str(tree / "scripts" / "package-release.sh")],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "usage" in result.stderr


def test_refuses_to_package_without_a_built_card(tree: Path) -> None:
    (tree / "custom_components" / "inkop" / "www" / "inkop-card.js").unlink()

    result = package(tree, "v0.9.9")

    assert result.returncode != 0
    assert "not built" in result.stderr
    assert not (tree / "dist").exists()


def test_refuses_a_card_built_with_another_version(tree: Path) -> None:
    result = package(tree, "v1.0.0")

    assert result.returncode != 0
    assert "does not contain version 1.0.0" in result.stderr
    assert not (tree / "dist").exists()


# --- configuration that must stay consistent -----------------------------------


def _load(path: str) -> Any:
    return yaml.safe_load((ROOT / path).read_text())


def test_hacs_installs_the_zip_that_the_release_workflow_attaches() -> None:
    hacs = json.loads((ROOT / "hacs.json").read_text())
    workflow = (ROOT / ".github" / "workflows" / "release.yaml").read_text()
    script = SCRIPT.read_text()

    assert hacs["zip_release"] is True
    assert hacs["filename"] == "inkop.zip"
    assert hacs["render_readme"] is True
    assert hacs["homeassistant"]
    assert "dist/inkop.zip" in workflow
    assert "inkop.zip" in script


def test_release_workflow_runs_when_a_release_is_published() -> None:
    workflow = _load(".github/workflows/release.yaml")
    triggers = workflow.get("on", workflow.get(True))  # YAML reads a bare `on` as True

    assert triggers == {"release": {"types": ["published"]}}
    assert workflow["permissions"] == {"contents": "write"}
    steps = workflow["jobs"]["asset"]["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)
    assert "npm pkg set version" in commands
    assert "npm run build" in commands
    assert "scripts/package-release.sh" in commands
    assert "gh release upload" in commands


def test_release_workflow_passes_the_tag_to_scripts_only_through_the_environment() -> (
    None
):
    """The tag name comes from outside: expressions in shell code could be abused."""
    job = _load(".github/workflows/release.yaml")["jobs"]["asset"]

    assert job["env"] == {"TAG": "${{ github.event.release.tag_name }}"}
    for step in job["steps"]:
        assert "${{" not in step.get("run", "").replace(
            "${{ secrets", ""
        )  # no expressions


def test_ci_builds_the_release_package_on_every_change() -> None:
    ci = _load(".github/workflows/ci.yaml")

    steps = ci["jobs"]["package"]["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)
    assert "scripts/package-release.sh" in commands


def test_the_integration_and_the_card_start_from_the_same_version() -> None:
    manifest = json.loads(
        (ROOT / "custom_components" / "inkop" / "manifest.json").read_text()
    )
    package_json = json.loads((ROOT / "frontend" / "package.json").read_text())

    assert manifest["version"] == package_json["version"]
