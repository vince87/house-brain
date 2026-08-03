from pathlib import Path

EXAMPLES = Path("examples/home_assistant")
PACKAGE = EXAMPLES / "packages/house_brain_garage_fan.yaml"


def test_home_assistant_package_is_simulation_only() -> None:
    package = PACKAGE.read_text()

    assert package.count("event_mode: simulate") == 3
    assert "event_mode: execute" not in package
    assert "AUTONOMOUS_EXECUTION_ENABLED=true" not in package
    assert "timeout: 150" in package
    assert "!secret house_brain_events_url" in package
    assert "!secret house_brain_api_key" in package


def test_home_assistant_example_covers_bounded_fan_events() -> None:
    package = PACKAGE.read_text()
    secrets = (EXAMPLES / "secrets.yaml.example").read_text()

    assert "garage_humidity_high" in package
    assert "garage_humidity_low" in package
    assert "garage_night_window_ended" in package
    assert "switch.ventola" in package
    assert "replace-with-the-value-from-house-brain-dot-env" in secrets
    assert "HOME_ASSISTANT_TOKEN" not in package
    assert "HOUSE_BRAIN_API_KEY=" not in package
