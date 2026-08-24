import json
from pathlib import Path

import yaml

ADDON = Path("addons/house_brain")


def test_home_assistant_addon_has_a_restricted_supervisor_contract() -> None:
    configuration = yaml.safe_load((ADDON / "config.yaml").read_text())

    assert configuration["slug"] == "house_brain"
    assert configuration["arch"] == ["amd64", "aarch64"]
    assert configuration["homeassistant_api"] is True
    assert configuration["map"] == ["addon_config:rw"]
    assert configuration["stage"] == "experimental"
    assert "host_network" not in configuration
    assert "docker_api" not in configuration
    assert "privileged" not in configuration
    assert "/var/run/docker.sock" not in json.dumps(configuration)


def test_addon_launcher_uses_supervisor_token_without_persisting_it() -> None:
    launcher = (ADDON / "addon_launcher.py").read_text()
    compile(launcher, str(ADDON / "addon_launcher.py"), "exec")

    assert 'os.environ["HOME_ASSISTANT_URL"] = "http://supervisor/core"' in launcher
    assert 'os.environ["HOME_ASSISTANT_TOKEN"] = supervisor_token' in launcher
    assert "SUPERVISOR_TOKEN" in launcher
    assert "write_text" not in launcher
    assert "unlink" not in launcher
    assert "docker.sock" not in launcher


def test_hacs_and_addon_distribution_metadata_are_present() -> None:
    workflow = Path(".github/workflows/container.yml").read_text()
    repository = yaml.safe_load(Path("repository.yaml").read_text())

    assert "uses: hacs/action@main" in workflow
    assert "category: integration" in workflow
    assert repository["url"] == "https://github.com/vince87/house-brain"
    assert (Path("custom_components/house_brain") / "manifest.json").exists()
    assert Path("hacs.json").exists()
    assert Path("LICENSE").read_text().startswith("MIT License")
    assert 'license = "MIT"' in Path("pyproject.toml").read_text()
