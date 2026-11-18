import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools import m10_parked_world_readiness as readiness


class ParkedWorldReadinessTest(unittest.TestCase):
    def test_only_selected_map_completion_triggers_one_sdk_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "server.log"
            path.write_bytes(b"1 seconds to LoadMap(/Game/Wrong)\n" + b"x" * 65500)
            selected = b" seconds to LoadMap(/Game/Test)"
            calls = []

            def finish_load(_interval):
                calls.append("completed")
                with path.open("ab") as writer:
                    writer.write(selected)

            def connect(*args, **options):
                self.assertEqual(calls, ["completed"])
                self.assertEqual(options["timeout"], 180)
                return subprocess.CompletedProcess(args, 0, '{"world":1,"frame":5,"version":"v"}', "")

            live = Mock()
            live.poll.return_value = None
            with patch.object(readiness.time, "sleep", side_effect=finish_load), patch.object(
                readiness.subprocess, "run", side_effect=connect
            ) as sdk:
                result = readiness.prepare_empty_world("python", 2400, root, {}, live, "/Game/Test")
            self.assertEqual(result["frame"], 5)
            self.assertEqual(sdk.call_count, 1)
            self.assertEqual(json.loads((root / "readiness.jsonl").read_text())["sdk_exit"], 0)

    def test_dead_server_never_receives_a_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "server.log").write_text("2 seconds to LoadMap(/Game/Test)")
            dead = Mock(returncode=-11)
            dead.poll.return_value = -11
            with patch.object(readiness.subprocess, "run") as sdk, self.assertRaisesRegex(
                RuntimeError, "server exited"
            ):
                readiness.prepare_empty_world("python", 2400, root, {}, dead, "/Game/Test")
            sdk.assert_not_called()
