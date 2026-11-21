from __future__ import annotations

import os
from pathlib import Path
import tempfile

_TEST_HOME = Path(tempfile.mkdtemp(prefix="hsptl-test-"))
os.environ["HSPTL_HOME"] = str(_TEST_HOME)
os.environ.pop("HSPTL_DATA_HOME", None)
os.environ.pop("WARDX_HOME", None)
os.environ.pop("CASEDLE_HOME", None)
os.environ.pop("SYNTHEA_CSV_DIR", None)

os.environ["HSPTL_DISABLE_EXTERNAL_AUTOMATION"] = "1"  # Tests use mocked providers; never call live clinical APIs.
