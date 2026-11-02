"""Issue #177: every integration *_live.py module opts into requires_live_project."""
from __future__ import annotations

from pathlib import Path


def test_every_integration_live_module_declares_requires_live_project_marker():
    integration = Path(__file__).resolve().parents[1] / "integration"
    missing = []
    for path in sorted(integration.glob("*_live.py")):
        text = path.read_text(encoding="utf-8")
        if "requires_live_project" not in text:
            missing.append(path.name)
    assert not missing, (
        "Add pytest.mark.requires_live_project to: %s" % ", ".join(missing)
    )
