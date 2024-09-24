# pyre-unsafe
import unittest

from autoval.lib.utils.manifest import Manifest


class ManifestTest(unittest.TestCase):
    def test_manifest(self):
        manifest = Manifest().get_test_manifest()
        self.assertIsInstance(manifest, dict)
        self.assertIn("version", manifest)
        self.assertIn("build_time", manifest)
        self.assertIn("release", manifest)
        self.assertIn("revision", manifest)
        self.assertIn("revision_epochtime", manifest)
        self.assertIn("revision_time", manifest)
