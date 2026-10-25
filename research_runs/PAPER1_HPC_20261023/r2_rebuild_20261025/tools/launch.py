"""Detach byte transfer and independent GitHub reporting from the terminal."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
STATE = Path('/workspace/paper1-archive-state')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('--status', action='store_true')
    args = p.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    if args.status:
        for name in ('status.json', 'summary.json', 'progress.json'):
            path = STATE / name
            if path.exists():
                print(json.dumps({'file': name, 'record': json.loads(path.read_text())}))
        return 0
    if args.worker:
        # The transfer owns an exclusive flock; duplicate launches cannot move data twice.
        result = subprocess.run([sys.executable, '-u', str(ROOT/'transfer.py'), '--run'],
                                cwd=ROOT, stdin=subprocess.DEVNULL)
        # Reporting is a separate process; its failures cannot stop this subprocess.
        return result.returncode
    worker_log = open(STATE/'worker.log', 'ab', buffering=0)
    worker = subprocess.Popen([sys.executable, '-u', str(__file__), '--worker'],
                              cwd=ROOT, stdin=subprocess.DEVNULL, stdout=worker_log,
                              stderr=subprocess.STDOUT, start_new_session=True)
    worker_log.close()
    sync_log = open(STATE/'github.log', 'ab', buffering=0)
    sync = subprocess.Popen([sys.executable, '-u', str(ROOT/'github_progress.py'), '--watch'],
                            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=sync_log,
                            stderr=subprocess.STDOUT, start_new_session=True)
    sync_log.close()
    result = {'status': 'background_processes_started_not_archive_completion',
              'worker_pid': worker.pid, 'github_sync_pid': sync.pid,
              'started_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (STATE/'processes.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
