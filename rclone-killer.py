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

threshold_seconds_diff = 300
threshold_seconds_sig = 3600


def main():
    while True:
        rc, out = pgrep_subprocess()
        if rc == 0 and out:
            lines = out.split("\n")
            for line in lines:
                pid = int(line)
                rc_cmd, out_cmd = ps_subprocess(pid, "command")
                if rc_cmd != 0:
                    continue

                if "copyto" not in out_cmd:
                    continue

                if "sigtar.gpg" in out_cmd:
                    threshold_seconds = threshold_seconds_sig
                else:
                    threshold_seconds = threshold_seconds_diff

                rc_etimes, out_etimes = ps_subprocess(pid, "etimes")
                if rc_etimes != 0:
                    continue

                elapsed = int(out_etimes)
                if elapsed > threshold_seconds:
                    print("Rclone instance with pid {pid} has been running for {elapsed} seconds, killing it".format(pid=pid, elapsed=elapsed))
                    os.kill(pid, signal.SIGTERM)

        time.sleep(15)


def pgrep_subprocess():
    cmdline = "pgrep -x rclone"
    cmd = shlex.split(cmdline)
    try:
        p = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return p.returncode, p.stdout.rstrip("\n")
    except OSError as ex:
        print("Error while launching pgrep: {err}".format(err=ex.strerror))
        exit(1)


def ps_subprocess(pid, field):
    cmdline = "ps -o {field}= {pid}".format(field=field, pid=pid)
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
