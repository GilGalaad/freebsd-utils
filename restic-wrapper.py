#!/usr/bin/env python3.7

"""
Wrapper for Restic command line parameters

File name: restic_wrapper.py
Author: Francesco Magno
Date created: 01/05/2020
Licence: GPL-3.0
Repository: https://github.com/GilGalaad/freebsd-utils
Python Version: 3.7
"""

import os
import signal
import subprocess
import sys

# remote repository
remote_name = "gsuite"
remote_url = "rclone:" + remote_name + ":/restic"
passphrase = "my_strong_password"
# paths
restic_bin = "/store/maintenance/restic/bin/restic"
work_dir = os.path.normpath("/store/maintenance/restic")
cache_dir = os.path.join(work_dir, "cache")
# process handler
p = None


def main():
  cmd_args = sys.argv[1:]
  rc = run_command(cmd_args)
  exit(rc)


def run_command(cmd_args):
  global p
  proc_env = os.environ.copy()
  proc_env["RESTIC_REPOSITORY"] = remote_url
  proc_env["RESTIC_PASSWORD"] = passphrase
  proc_env["RCLONE_DRIVE_USE_TRASH"] = "false"
  proc_env["RCLONE_NO_TRAVERSE"] = "true"
  proc_env["RCLONE_DRIVE_CHUNK_SIZE"] = "64M"
  args = [restic_bin]
  args.append("--cache-dir")
  args.append(cache_dir)
  args.append("--cleanup-cache")
  args.extend(cmd_args)
  try:
    p = subprocess.Popen(args, env=proc_env)
    p.wait()
    return p.returncode
  except OSError as ex:
    print(ex.strerror)
    return 1


def signal_handler(sig, frame):
  global p
  if p is not None and p.poll() is None:
    p.send_signal(sig)


if __name__ == "__main__":
  signal.signal(signal.SIGINT, signal_handler)
  main()
