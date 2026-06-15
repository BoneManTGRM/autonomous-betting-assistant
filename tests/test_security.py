from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from autonomous_betting_agent.security import (
    all_checks_passed,
    count_formula_injection_cells,
    count_secret_like_cells,
    escape_csv_formulas,
    file_sha256,
    redact_secret_text,
    safe_join,
    secure_csv_download,
    validate_dataframe,
    validate_upload_bytes,
    validate_upload_name,
)


class SecurityTests(unittest.TestCase):
    def test_upload_name_blocks_dangerous_extensions(self) -> None:
        checks = validate_upload_name('../evil.exe')
        by_name = {check.name: check for check in checks}
        self.assertFalse(by_name['allowed_extension'].passed)
        self.assertFalse(by_name['dangerous_extension_block'].passed)

    def test_upload_bytes_limits(self) -> None:
        checks = validate_upload_bytes(b'abc', max_bytes=10)
        self.assertTrue(all_checks_passed(checks))
        too_large = validate_upload_bytes(b'a' * 11, max_bytes=10)
        self.assertFalse(all_checks_passed(too_large))

    def test_formula_injection_escape(self) -> None:
        frame = pd.DataFrame([{'pick': '=HYPERLINK("http://bad")'}, {'pick': 'normal'}])
        self.assertEqual(count_formula_injection_cells(frame), 1)
        escaped = escape_csv_formulas(frame)
        self.assertTrue(str(escaped.loc[0, 'pick']).startswith("'="))

    def test_secret_redaction(self) -> None:
        text = 'API_KEY=abc123secretvalue'
        self.assertEqual(redact_secret_text(text), '[REDACTED_SECRET]')
        frame = pd.DataFrame([{'note': 'token: abc123secretvalue'}])
        self.assertEqual(count_secret_like_cells(frame), 1)
        csv_text = secure_csv_download(frame)
        self.assertIn('[REDACTED_SECRET]', csv_text)

    def test_dataframe_checks_detect_risky_cells(self) -> None:
        frame = pd.DataFrame([{'a': '=1+1', 'b': 'password: abc123secretvalue'}])
        checks = validate_dataframe(frame)
        by_name = {check.name: check for check in checks}
        self.assertFalse(by_name['csv_formula_cells_detected'].passed)
        self.assertFalse(by_name['secret_like_cells_detected'].passed)

    def test_safe_join_blocks_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            base = Path(tempdir)
            safe = safe_join(base, 'uploads', 'file.csv')
            self.assertIn(str(base.resolve()), str(safe))
            unsafe = safe_join(base, '../outside.csv')
            self.assertIn(str(base.resolve()), str(unsafe))

    def test_file_hash_is_stable(self) -> None:
        self.assertEqual(file_sha256(b'abc'), file_sha256(b'abc'))
        self.assertNotEqual(file_sha256(b'abc'), file_sha256(b'abd'))


if __name__ == '__main__':
    unittest.main()
