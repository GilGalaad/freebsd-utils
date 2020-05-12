#!/usr/bin/env python3.7

"""
Killer for rclone long running instances

File name: rclone-killer.py
Author: Francesco Magno
Date created: 11/05/2020
Licence: GPL-3.0
Repository: https://github.com/GilGalaad/freebsd-utils
Python Version: 3.7
"""

import os
import shlex
import signal
import subprocess
import time


threshold_seconds = 300


def main():
  while True:
    rc, out = pgrep_subprocess()
    if out:
      lines = out.split("\n")
      for line in lines:
        pid = int(line)
        rc2, out2 = ps_subprocess(pid)
        elapsed = int(out2)
        if elapsed > threshold_seconds:
          print("Rclone instance with pid {pid} has been running for {elapsed} seconds, killing it".format(pid=pid, elapsed=elapsed))
          os.kill(pid, signal.SIGINT)

    time.sleep(10)


def pgrep_subprocess():
  cmdline = "pgrep -x rclone"
  cmd = shlex.split(cmdline)
  try:
    p = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return p.returncode, p.stdout.rstrip("\n")
  except OSError as ex:
    print("Error while launching pgrep: {err}".format(err=ex.strerror))
    exit(1)


def ps_subprocess(pid):
  cmdline = "ps -o etimes= {pid}".format(pid=pid)
  cmd = shlex.split(cmdline)
  try:
    p = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return p.returncode, p.stdout.rstrip("\n")
  except OSError as ex:
    print("Error while launching ps: {err}".format(err=ex.strerror))
    exit(1)


def graceful_quit_handler(signum, frame):
  exit(0)


if __name__ == "__main__":
  signal.signal(signal.SIGINT, graceful_quit_handler)
  signal.signal(signal.SIGTERM, graceful_quit_handler)
  main()
