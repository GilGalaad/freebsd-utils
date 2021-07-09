#!/usr/bin/env python3.8

"""
Wrapper for Restic command line parameters

File name: restic_wrapper.py
Author: Francesco Magno
Date created: 01/05/2020
Licence: GPL-3.0
Repository: https://github.com/GilGalaad/freebsd-utils
Python Version: 3.8
"""

import os
import signal
import sys
from subprocess import Popen
from typing import Optional, List

# remote repository
remote_name = "gsuite"
remote_url = f"rclone:{remote_name}:/restic"
passphrase = "my_strong_password"
# paths
restic_bin = "/store/maintenance/restic/bin/restic"
work_dir = os.path.normpath("/store/maintenance/restic")
cache_dir = os.path.join(work_dir, "cache")
# process handler
p: Optional[Popen] = None


def main():
    cmd_args = sys.argv[1:]
    rc = run_command(cmd_args)
    exit(rc)


def run_command(cmd_args: List[str]) -> int:
    global p
    proc_env = os.environ.copy()
    proc_env["RESTIC_REPOSITORY"] = remote_url
    proc_env["RESTIC_PASSWORD"] = passphrase
    proc_env["RCLONE_DRIVE_USE_TRASH"] = "false"
    proc_env["RCLONE_NO_TRAVERSE"] = "true"
    proc_env["RCLONE_DRIVE_CHUNK_SIZE"] = "128M"
    args = [restic_bin, "--cache-dir", cache_dir, "--cleanup-cache"]
    args.extend(cmd_args)
    try:
        p = Popen(args, env=proc_env, text=True)
        p.wait()
        return p.returncode
    except OSError as ex:
        print(ex.strerror)
        return 1


def signal_handler(sig, frame):
    if p is not None and p.poll() is None:
        p.send_signal(sig)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    main()
