import os
import stat
import tempfile
import unittest
from pathlib import Path

import steamos_sleep_fix


GRUB_DEFAULTS_WITH_OFF = '''GRUB_CMDLINE_LINUX="${GRUB_CMDLINE_LINUX} \\
log_buf_len=4M \\
amd_iommu=off \\
audit=0 \\
"
'''

GRUB_DEFAULTS_WITHOUT_OFF = '''GRUB_CMDLINE_LINUX="${GRUB_CMDLINE_LINUX} \\
log_buf_len=4M \\
audit=0 \\
"
'''


class SteamOSSleepFixTests(unittest.TestCase):
    def test_enable_removes_all_iommu_off_arguments(self):
        updated, changed = steamos_sleep_fix.set_amd_iommu_disabled(
            GRUB_DEFAULTS_WITH_OFF, False
        )

        self.assertTrue(changed)
        self.assertNotIn("amd_iommu=off", updated)

    def test_enable_is_idempotent_when_iommu_off_is_absent(self):
        updated, changed = steamos_sleep_fix.set_amd_iommu_disabled(
            GRUB_DEFAULTS_WITHOUT_OFF, False
        )

        self.assertFalse(changed)
        self.assertEqual(updated, GRUB_DEFAULTS_WITHOUT_OFF)

    def test_disable_adds_one_iommu_off_argument(self):
        updated, changed = steamos_sleep_fix.set_amd_iommu_disabled(
            GRUB_DEFAULTS_WITHOUT_OFF, True
        )

        self.assertTrue(changed)
        self.assertEqual(updated.count("amd_iommu=off"), 1)

    def test_disable_is_idempotent_when_one_iommu_off_argument_exists(self):
        updated, changed = steamos_sleep_fix.set_amd_iommu_disabled(
            GRUB_DEFAULTS_WITH_OFF, True
        )

        self.assertFalse(changed)
        self.assertEqual(updated, GRUB_DEFAULTS_WITH_OFF)

    def test_rejects_an_unexpected_grub_assignment(self):
        with self.assertRaises(steamos_sleep_fix.SleepFixConfigurationError):
            steamos_sleep_fix.set_amd_iommu_disabled('GRUB_CMDLINE_LINUX="quiet"\n', False)

    def test_failed_generation_restores_both_grub_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            os_release_path = root / "os-release"
            defaults_path = root / "grub-steamos"
            generated_path = root / "grub.cfg"
            mkconfig_path = root / "grub-mkconfig"
            runtime_dir = root / "runtime"

            os_release_path.write_text('ID="steamos"\n', encoding="utf-8")
            defaults_path.write_text(GRUB_DEFAULTS_WITH_OFF, encoding="utf-8")
            generated_path.write_text("previous generated config\n", encoding="utf-8")
            mkconfig_path.write_text("placeholder", encoding="utf-8")
            mkconfig_path.chmod(mkconfig_path.stat().st_mode | stat.S_IXUSR)

            def failing_runner(args, **kwargs):
                generated_path.write_text("partial generated config\n", encoding="utf-8")
                raise RuntimeError("grub-mkconfig failed")

            sleep_fix = steamos_sleep_fix.SteamOSSleepFix(
                command_runner=failing_runner,
                runtime_dir=runtime_dir,
                os_release_paths=(os_release_path,),
                grub_default_path=defaults_path,
                grub_config_path=generated_path,
                grub_mkconfig_path=mkconfig_path,
            )

            with self.assertRaises(steamos_sleep_fix.SleepFixConfigurationError):
                sleep_fix.apply_iommu_disabled(False)

            self.assertEqual(
                defaults_path.read_text(encoding="utf-8"), GRUB_DEFAULTS_WITH_OFF
            )
            self.assertEqual(
                generated_path.read_text(encoding="utf-8"), "previous generated config\n"
            )
            self.assertEqual(
                (runtime_dir / steamos_sleep_fix.ORIGINAL_GRUB_BACKUP_FILENAME).read_text(
                    encoding="utf-8"
                ),
                GRUB_DEFAULTS_WITH_OFF,
            )


if __name__ == "__main__":
    unittest.main()
