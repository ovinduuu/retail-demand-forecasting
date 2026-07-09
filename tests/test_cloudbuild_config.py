from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_cloudbuild_yaml_is_valid_and_has_expected_steps():
    config = yaml.safe_load((REPO_ROOT / "cloudbuild.yaml").read_text())

    step_ids = [step["id"] for step in config["steps"]]
    assert step_ids == [
        "build-pipeline-image",
        "push-pipeline-image-sha",
        "push-pipeline-image-latest",
        "submit-training-pipeline",
    ]
    assert config["steps"][-1]["waitFor"] == ["push-pipeline-image-sha"]
