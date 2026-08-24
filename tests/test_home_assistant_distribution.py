import json
from pathlib import Path

import yaml

ADDON = Path("addons/house_brain")


def test_home_assistant_addon_has_a_restricted_supervisor_contract() -> None:
    configuration = yaml.safe_load((ADDON / "config.yaml").read_text())

    assert configuration["slug"] == "house_brain"
    assert configuration["arch"] == ["amd64", "aarch64"]
    assert configuration["homeassistant_api"] is True
    assert configuration["map"] == [
        {
            "type": "addon_config",
            "read_only": False,
            "path": "/config",
        }
    ]
    assert configuration["stage"] == "experimental"
    assert "host_network" not in configuration
    assert "docker_api" not in configuration
    assert "privileged" not in configuration
    assert "/var/run/docker.sock" not in json.dumps(configuration)
    option_names = set(configuration["options"]) | set(configuration["schema"])
    assert not any(
        token in option.casefold()
        for option in option_names
        for token in ("path", "database", "autonomy", "context_views")
    )


def test_addon_launcher_uses_supervisor_token_without_persisting_it() -> None:
    launcher = (ADDON / "addon_launcher.py").read_text()
    compile(launcher, str(ADDON / "addon_launcher.py"), "exec")

    assert 'os.environ["HOME_ASSISTANT_URL"] = "http://supervisor/core"' in launcher
    assert 'os.environ["HOME_ASSISTANT_TOKEN"] = supervisor_token' in launcher
    assert "SUPERVISOR_TOKEN" in launcher
    assert "write_text" not in launcher
    assert "unlink" not in launcher
    assert "docker.sock" not in launcher
    assert 'OPTIONS_PATH = Path("/data/options.json")' in launcher


def test_hacs_and_addon_distribution_metadata_are_present() -> None:
    workflow = Path(".github/workflows/container.yml").read_text()
    repository = yaml.safe_load(Path("repository.yaml").read_text())

    assert "uses: hacs/action@main" in workflow
    assert "addon-build:" in workflow
    assert "context: addons/house_brain" in workflow
    assert "platforms: linux/amd64,linux/arm64" in workflow
    assert "category: integration" in workflow
    assert "github.event_name == 'pull_request'" in workflow
    assert "'license' || ''" in workflow
    assert repository["url"] == "https://github.com/vince87/house-brain"
    assert (Path("custom_components/house_brain") / "manifest.json").exists()
    assert Path("hacs.json").exists()
    assert Path("LICENSE").read_text().startswith("MIT License")
    assert 'license = "MIT"' in Path("pyproject.toml").read_text()


def test_addon_documentation_and_configuration_page_explain_fixed_paths() -> None:
    readme = (ADDON / "README.md").read_text()
    docs = (ADDON / "DOCS.md").read_text()
    english = yaml.safe_load((ADDON / "translations" / "en.yaml").read_text())
    italian = yaml.safe_load((ADDON / "translations" / "it.yaml").read_text())

    for content in (readme, docs):
        assert "/addon_configs/<repository>_house_brain" in content
        assert "/config/house_brain.db" in content
        assert "/config/context-views.yaml" in content
        assert "/data/options.json" in content
        assert "Home Assistant Core" in content
    assert english["configuration"]["api_key"]["name"] == "API key"
    assert italian["configuration"]["api_key"]["name"] == "Chiave API"
    assert english.keys() == italian.keys()


def test_addon_version_and_base_image_remain_pinned_together() -> None:
    configuration = yaml.safe_load((ADDON / "config.yaml").read_text())
    dockerfile = (ADDON / "Dockerfile").read_text()

    assert (
        "ARG HOUSE_BRAIN_BASE_IMAGE="
        f'ghcr.io/vince87/house-brain:{configuration["version"]}'
    ) in dockerfile
    assert "FROM ${HOUSE_BRAIN_BASE_IMAGE}" in dockerfile
    assert ":latest" not in dockerfile

    workflow = Path(".github/workflows/container.yml").read_text()
    assert (
        "HOUSE_BRAIN_BASE_IMAGE=ghcr.io/vince87/house-brain:0.1.5"
        in workflow
    )
