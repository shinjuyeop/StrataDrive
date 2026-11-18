import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import audit_visual_tags_v1 as module


class VisualTagBoundaryTests(unittest.TestCase):
    def fixture(self, root):
        flag = '-StrataM10NoVisualTags'
        value = dict(owner_no_visual_tags=True,
            argv=dict(owner=[flag, '-nullrhi', '-norenderthread'], renderer=[]))
        (root/'server.json').write_text(json.dumps(value))
        (root/'owner.log').write_text('StrataM10NoVisualTags: retain semantic stencils; omit auxiliary visual tag components')
        (root/'renderer.log').write_text('original renderer')
        return value

    def test_explicit_owner_activation_requires_original_gate_audit(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(module, 'owner_four', return_value={}) as base:
            root = Path(tmp); self.fixture(root)
            self.assertEqual(module.audit(root)['status'], 'PASS_OWNER_VISUAL_TAG_INTEGRITY')
            base.assert_called_once_with(root)

    def test_renderer_activation_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(module, 'owner_four', return_value={}):
            root = Path(tmp); value = self.fixture(root)
            value['argv']['renderer'].append('-StrataM10NoVisualTags')
            (root/'server.json').write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'NullRHI-only'): module.audit(root)

    def test_declared_flag_without_actual_activation_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(module, 'owner_four', return_value={}):
            root = Path(tmp); self.fixture(root); (root/'owner.log').write_text('old module')
            with self.assertRaisesRegex(ValueError, 'actual owner activation'): module.audit(root)

    def test_original_gate_failure_cannot_be_overridden(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(module, 'owner_four', side_effect=ValueError('original gate failure')):
            root = Path(tmp); self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'original gate failure'): module.audit(root)
