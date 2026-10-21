import os
import subprocess
import time
from pathlib import Path


def test_run_job_lock_prevents_overlap(tmp_path):
    root = Path(__file__).parents[1]
    lock = tmp_path / "ff-job.lock"
    logs = tmp_path / "logs"
    reports = tmp_path / "reports"
    holder = subprocess.Popen(["flock", str(lock), "sleep", "5"])
    try:
        time.sleep(0.2)
        env = {
            **os.environ,
            "FF_JOB_LOCK": str(lock),
            "FF_JOB_LOG_DIR": str(logs),
            "FF_JOB_REPORT_DIR": str(reports),
        }
        result = subprocess.run(
            ["bash", "scripts/run_job.sh", "daily", "--dry-run"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
    finally:
        holder.terminate()
        holder.wait(timeout=5)

    assert result.returncode == 75
    failure = reports / "JOB_FAILED_daily.md"
    assert failure.exists()
    assert "another ff-model job holds" in failure.read_text(encoding="utf-8")
