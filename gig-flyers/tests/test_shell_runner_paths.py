"""Shell runner resolves pass-1 output when GIG_OUTPUT_DIR is external."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from output_paths import resolve_output_path


class ShellRunnerPathTests(unittest.TestCase):
    def test_resolve_pass1_shell_path_on_fly(self) -> None:
        rel = "output/shell_design/hendrix_sicks_stadium_1970_design_shell.png"
        with patch.dict(os.environ, {"GIG_OUTPUT_DIR": "/data/flyers-output"}):
            resolved = resolve_output_path(rel)
            self.assertEqual(
                resolved,
                Path("/data/flyers-output/shell_design/hendrix_sicks_stadium_1970_design_shell.png"),
            )


if __name__ == "__main__":
    unittest.main()
