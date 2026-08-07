import unittest

from app.services.synology_service import SynologyService


class SynologyServiceBackupTests(unittest.TestCase):
    def test_parses_task_variants_and_detects_failed_and_stale_tasks(self) -> None:
        tasks = SynologyService._parse_backup_tasks(
            {
                "task_list": [
                    {
                        "id": 7,
                        "name": "Off-site",
                        "state": "idle",
                        "last_status": "failed",
                        "last_bkp_time": 1_700_000_000,
                        "enabled": 1,
                        "dest": "C2 Storage",
                    }
                ]
            }
        )

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].task_id, "7")
        self.assertEqual(tasks[0].destination, "C2 Storage")
        self.assertTrue(SynologyService._backup_failed(tasks[0]))
        self.assertTrue(SynologyService._backup_stale(tasks[0]))

    def test_disabled_task_is_not_stale(self) -> None:
        task = SynologyService._parse_backup_tasks(
            {"tasks": [{"id": "1", "name": "Archive", "enabled": False, "last_run_time": 1}]}
        )[0]

        self.assertFalse(SynologyService._backup_stale(task))

    def test_history_is_normalized_and_sorted_newest_first(self) -> None:
        history = SynologyService._parse_backup_history(
            {
                "logs": [
                    {"task_name": "NAS", "result": "success", "end_time": 1_700_000_000},
                    {"task_name": "Cloud", "result": "error", "end_time": 1_800_000_000},
                ]
            }
        )

        self.assertEqual([item.task_name for item in history], ["Cloud", "NAS"])
        self.assertTrue(SynologyService._backup_success(history[1].status))
        self.assertEqual(SynologyService._recent_failed_backups(history), 1)

    def test_future_schedule_prevents_false_stale_alert(self) -> None:
        task = SynologyService._parse_backup_tasks(
            {
                "items": [
                    {
                        "id": "weekly",
                        "last_run_time": 1_700_000_000,
                        "next_run_time": 4_102_444_800,
                    }
                ]
            }
        )[0]

        self.assertFalse(SynologyService._backup_stale(task))


if __name__ == "__main__":
    unittest.main()
