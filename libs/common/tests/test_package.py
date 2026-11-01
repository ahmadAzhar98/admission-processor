import re

import common


def test_version_is_semver_string():
    assert re.fullmatch(r"\d+\.\d+\.\d+", common.__version__)
