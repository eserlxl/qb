"""Direct tests for the frontmatter_name helper's parsing guarantees.

The manifest/frontmatter suite only feeds this helper real component files, so
its subtle contracts -- in particular that a ``name:`` in the document *body*
never leaks past the closing ``---`` fence -- are not otherwise pinned.
"""

from __future__ import annotations

import unittest

from tests.qb_monorepo import frontmatter_name


class FrontmatterNameTests(unittest.TestCase):
    def test_name_inside_block_is_returned(self) -> None:
        text = "---\nname: qb-planner\ndescription: x\n---\n\n# Body\n"
        self.assertEqual(frontmatter_name(text), "qb-planner")

    def test_body_name_does_not_leak_past_closing_fence(self) -> None:
        # The block has no name:; a name: appears only in the body. The helper
        # must stop at the closing fence and report None, not the body value.
        text = "---\ndescription: x\n---\n\nname: not-the-frontmatter-name\n"
        self.assertIsNone(frontmatter_name(text))

    def test_no_block_falls_back_to_top_of_file_scan(self) -> None:
        text = "name: fallback-name\nother: value\n"
        self.assertEqual(frontmatter_name(text), "fallback-name")

    def test_missing_name_returns_none(self) -> None:
        self.assertIsNone(frontmatter_name("---\ndescription: x\n---\n\n# Body only\n"))
        self.assertIsNone(frontmatter_name(""))


if __name__ == "__main__":
    unittest.main()
