import json

import pytest
from pydantic import ValidationError

from app.attacks.registry import Registry
from app.core.config import Settings


def test_duplicate_and_invalid_files(tmp_path):
    entry = next(iter(Registry(Settings().scenario_dir).entries.values())).model_dump(mode="json")
    path = tmp_path / "custom.json"
    path.write_text(json.dumps([entry, entry]))
    with pytest.raises(ValueError, match="duplicate"):
        Registry(tmp_path)
    path.write_text(json.dumps([dict(entry, attack_steps=[])]))
    with pytest.raises(ValidationError):
        Registry(tmp_path)
