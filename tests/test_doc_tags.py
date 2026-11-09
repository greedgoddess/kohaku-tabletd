"""Every [doc:<id>] tag has an anchor in docs/CODE.md under its file's table, and vice versa."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED = ("src", "bin", "data", "packaging", "Makefile")
TAG = re.compile(r"^\s*#\s*\[doc:([a-z0-9]+(?:-[a-z0-9]+)+)\]\s*$")
ANCHOR = re.compile(r'<a id="([^"]+)"></a>')
SECTION = re.compile(r"^## `([^`]+)`\s*$")


def code_tags():
    tags = {}
    for entry in SCANNED:
        path = ROOT / entry
        files = [path] if path.is_file() else sorted(
            p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        for file in files:
            for line in file.read_text().splitlines():
                match = TAG.match(line)
                if match:
                    tags.setdefault(match.group(1), []).append(file.relative_to(ROOT).as_posix())
    return tags


def doc_anchors():
    anchors, section = {}, None
    for line in (ROOT / "docs" / "CODE.md").read_text().splitlines():
        match = SECTION.match(line)
        if match:
            section = match.group(1)
            continue
        for anchor in ANCHOR.findall(line):
            anchors.setdefault(anchor, []).append(section)
    return anchors


class DocTagsTest(unittest.TestCase):
    def setUp(self):
        self.tags = code_tags()
        self.anchors = doc_anchors()

    def test_tags_unique(self):
        self.assertEqual({k: v for k, v in self.tags.items() if len(v) > 1}, {})

    def test_anchors_unique(self):
        self.assertEqual({k: v for k, v in self.anchors.items() if len(v) > 1}, {})

    def test_every_tag_documented_in_its_file_section(self):
        wrong = {tag: (files[0], self.anchors.get(tag)) for tag, files in self.tags.items()
                 if self.anchors.get(tag, [None])[0] != files[0]}
        self.assertEqual(wrong, {})

    def test_no_orphan_doc_entries(self):
        self.assertEqual(sorted(set(self.anchors) - set(self.tags)), [])


class VersionTest(unittest.TestCase):
    def test_spec_matches_package(self):
        from kohaku_tabletd import __version__
        spec = (ROOT / "packaging" / "kohaku-tabletd.spec").read_text()
        self.assertRegex(spec, rf"(?m)^Version:\s+{re.escape(__version__)}$")
