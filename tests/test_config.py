# -*- coding: utf-8 -*-
"""Unit tests for quicktile.config.

Kept free of GTK/X imports so they run without a display server.
"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 2.0 or later"

import os
import shutil
import tempfile
import unittest

from quicktile import config


class LoadConfigTest(unittest.TestCase):
    """Tests for config.load_config edge cases."""

    def setUp(self):
        """Set up scratch space for config files at the start of each unit"""
        self.testdir = tempfile.mkdtemp(prefix='quicktile-config-test-')

    def tearDown(self):
        """Delete the scratch space when each test is finished"""
        shutil.rmtree(self.testdir, ignore_errors=True)

    def test_creates_missing_parent_dirs(self):
        """Config file is created even if the parent dir is missing"""
        testpath = os.path.join(self.testdir, 'missing-parent',
                                'test.config')
        self.assertFalse(os.path.exists(os.path.dirname(testpath)))
        parsed = config.load_config(testpath)
        self.assertTrue(os.path.isfile(testpath))
        self.assertEqual('1', parsed.get('general', 'cfg_schema'))


if __name__ == '__main__':
    unittest.main()

# vim: set sw=4 sts=4 expandtab :
