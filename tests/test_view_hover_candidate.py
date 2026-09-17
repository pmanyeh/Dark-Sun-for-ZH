import unittest
from unittest.mock import patch

from tools.build_view_hover_candidate import (
    HOVER_CONTINUATION_IP,
    HOVER_SITE,
    PARENT_EXE_HASH,
    patch_executable,
)
from tools.plan_name_slot_consumers import NAME_POINTER_SEQUENCE, ds_relative_consumer_redirect_bytes


class ViewHoverCandidateTests(unittest.TestCase):
    def test_wrong_parent_rejected(self):
        with self.assertRaisesRegex(ValueError, "not v59"):
            patch_executable(b"wrong")

    def test_patch_is_exact_overlay_safe_redirect(self):
        image = bytearray(HOVER_SITE + len(NAME_POINTER_SEQUENCE) + 16)
        image[HOVER_SITE:HOVER_SITE + len(NAME_POINTER_SEQUENCE)] = NAME_POINTER_SEQUENCE
        with (
            patch("tools.build_view_hover_candidate.sha256", return_value=PARENT_EXE_HASH),
            patch("tools.build_view_hover_candidate.verify_overlay_relocations") as guard,
            patch("tools.build_view_hover_candidate.mz_relocation_file_offsets", return_value=frozenset({0x1234})),
        ):
            result = patch_executable(bytes(image))
        end = HOVER_SITE + len(NAME_POINTER_SEQUENCE)
        guard.assert_called_once_with(bytes(image), [(HOVER_SITE, end)])
        self.assertEqual(result[HOVER_SITE:end], ds_relative_consumer_redirect_bytes(HOVER_CONTINUATION_IP))
        self.assertEqual(result[:HOVER_SITE], image[:HOVER_SITE])
        self.assertEqual(result[end:], image[end:])

    def test_consumer_mismatch_rejected(self):
        image = bytes(HOVER_SITE + len(NAME_POINTER_SEQUENCE) + 1)
        with patch("tools.build_view_hover_candidate.sha256", return_value=PARENT_EXE_HASH):
            with self.assertRaisesRegex(ValueError, "consumer differs"):
                patch_executable(image)


if __name__ == "__main__":
    unittest.main()
