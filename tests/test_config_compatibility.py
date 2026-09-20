from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from config_compatibility import without_defaults


def test_default_normalization_retains_all_validation_logic():
    old = 'DEFAULTS = {"k": 1}\ndef validate(x):\n return x > 0\n'
    changed_default = old.replace('"k": 1', '"k": 2')
    changed_logic = changed_default.replace('x > 0', 'x >= 0')
    assert without_defaults(old) == without_defaults(changed_default)
    assert without_defaults(old) != without_defaults(changed_logic)
