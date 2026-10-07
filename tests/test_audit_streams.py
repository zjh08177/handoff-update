from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'references/audit_streams.py'


class StreamAudit(unittest.TestCase):
    def run_audit(self, text, *args):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'handoff.md'
            path.write_text(text)
            return subprocess.run([sys.executable, str(SCRIPT), str(path), *args],
                                  capture_output=True, text=True)

    def sample(self, row='  prep: {status: "active"}', body='Next: inspect the source.'):
        return ('---\nstreams:\n  base: {last_verified_at: "2026-10-07"}\n' + row +
                '\n---\n<!-- BEGIN-STREAM-BASE -->\nGoal.\n<!-- END-STREAM-BASE -->\n'
                '<!-- BEGIN-STREAM-PREP -->\n' + body + '\n<!-- END-STREAM-PREP -->\n')

    def test_valid_inline(self):
        self.assertEqual(self.run_audit(self.sample()).returncode, 0)

    def test_valid_block(self):
        self.assertEqual(self.run_audit(self.sample('  prep:\n    status: "active"')).returncode, 0)

    def test_missing_active_section(self):
        text = self.sample().split('<!-- BEGIN-STREAM-PREP -->')[0]
        self.assertNotEqual(self.run_audit(text).returncode, 0)

    def test_block_missing_active_section(self):
        text = self.sample('  prep:\n    status: "active"').split('<!-- BEGIN-STREAM-PREP -->')[0]
        self.assertNotEqual(self.run_audit(text).returncode, 0)

    def test_duplicate_fence(self):
        text = self.sample() + '<!-- BEGIN-STREAM-PREP -->\nextra\n<!-- END-STREAM-PREP -->\n'
        self.assertNotEqual(self.run_audit(text).returncode, 0)

    def test_orphan_fence(self):
        self.assertNotEqual(self.run_audit(self.sample() + '<!-- BEGIN-STREAM-GHOST -->\n').returncode, 0)

    def test_nested_fence(self):
        self.assertNotEqual(self.run_audit(self.sample(body='<!-- BEGIN-STREAM-GHOST -->')).returncode, 0)

    def test_reversed_fence(self):
        self.assertNotEqual(self.run_audit(self.sample().replace('BEGIN-STREAM-PREP', 'END-STREAM-PREP', 1)).returncode, 0)

    def test_fences_without_metadata(self):
        self.assertNotEqual(self.run_audit('<!-- BEGIN-STREAM-PREP -->\nx\n<!-- END-STREAM-PREP -->\n').returncode, 0)

    def test_duplicate_metadata(self):
        self.assertNotEqual(self.run_audit(self.sample('  prep: {status: active}\n  PREP: {status: active}')).returncode, 0)

    def test_missing_status(self):
        self.assertNotEqual(self.run_audit(self.sample('  prep: {last_verified_at: "2026-10-07"}')).returncode, 0)

    def test_status_word_archived_is_not_field(self):
        self.assertNotEqual(self.run_audit(self.sample('  prep: {status: "CLOSED, not archived: pending"}')).returncode, 0)

    def test_archived_section_must_be_removed(self):
        self.assertNotEqual(self.run_audit(self.sample('  prep: {archived: "2026-10-07", status: "CLOSED"}')).returncode, 0)

    def test_closed_requires_review(self):
        result = self.run_audit(self.sample('  prep: {status: "CLOSED"}', '- [ ] Fix regression.'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('review', result.stdout.lower())
        self.assertNotIn('ARCHIVE NOW', result.stdout)

    def test_closed_does_not_assert_open_work_is_unfiled(self):
        result = self.run_audit(self.sample('  prep: {status: "CLOSED"}', 'Unresolved item is filed in [[backlog#123]].'))
        self.assertNotIn('open work with no home', result.stdout)

    def test_base_budget(self):
        text = self.sample().replace('Goal.', 'orientation\n' * 51)
        self.assertNotEqual(self.run_audit(text).returncode, 0)

    def test_stream_budget(self):
        self.assertNotEqual(self.run_audit(self.sample(body='line\n' * 150)).returncode, 0)

    def test_stricter_local_cap(self):
        self.assertNotEqual(self.run_audit(self.sample(), '--total-cap', '10').returncode, 0)

    def test_single_cap_counts_real_lines(self):
        self.assertEqual(self.run_audit('line\n' * 99, '--total-cap', '99').returncode, 0)
        self.assertNotEqual(self.run_audit('line\n' * 100, '--total-cap', '99').returncode, 0)

    def test_malformed_stream_map_fails(self):
        self.assertNotEqual(self.run_audit('---\nstreams: invalid\n---\n').returncode, 0)

    def test_crlf(self):
        self.assertEqual(self.run_audit(self.sample().replace('\n', '\r\n')).returncode, 0)

    def test_archived_only(self):
        text = '---\nstreams:\n  old: {archived: "2026-10-07", status: "CLOSED", archive: "archive.md"}\n---\nRead archive.md.\n'
        self.assertEqual(self.run_audit(text).returncode, 0)

    def test_false_archived_flag_fails(self):
        text = '---\nstreams:\n  prep: {archived: false, status: active}\n---\n'
        self.assertNotEqual(self.run_audit(text).returncode, 0)

    def test_archived_base_fails(self):
        text = '---\nstreams:\n  base: {archived: "2026-10-07"}\n---\n'
        self.assertNotEqual(self.run_audit(text).returncode, 0)

    def test_archived_active_status_fails(self):
        text = '---\nstreams:\n  prep: {archived: "2026-10-07", status: active, archive: "archive.md"}\n---\n'
        self.assertNotEqual(self.run_audit(text).returncode, 0)

    def test_archived_missing_destination_fails(self):
        text = '---\nstreams:\n  prep: {archived: "2026-10-07", status: CLOSED}\n---\n'
        self.assertNotEqual(self.run_audit(text).returncode, 0)

    def test_nested_scalar_field_fails(self):
        text = '---\nstreams:\n  prep:\n    status: CLOSED\n      archived: "2026-10-07"\n      archive: "archive.md"\n---\n'
        self.assertNotEqual(self.run_audit(text).returncode, 0)

    def test_mixed_inline_block_fails(self):
        text = '---\nstreams:\n  prep: {status: CLOSED}\n    archived: "2026-10-07"\n    archive: "archive.md"\n---\n'
        self.assertNotEqual(self.run_audit(text).returncode, 0)


if __name__ == '__main__':
    unittest.main()
