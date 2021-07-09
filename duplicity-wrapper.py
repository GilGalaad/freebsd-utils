#!/usr/bin/env python3.8

"""
Wrapper for Duplicity command line parameters

File name: duplicity_wrapper.py
Author: Francesco Magno
Date created: 21/04/2020
Licence: GPL-3.0
Repository: https://github.com/GilGalaad/freebsd-utils
Python Version: 3.8
"""

import argparse
import datetime
import os
import re
import shlex
import smtplib
import subprocess
import sys
from argparse import Namespace
from email.mime.text import MIMEText
from typing import Optional

"""
global parameters, customize here
"""
# remote repository
remote_name = "gsuite:"
remote_url = f"rclone://{remote_name}/duplicity"
passphrase = "my_strong_password"
# paths
work_dir = os.path.normpath("/store/maintenance/duplicity")
tmp_dir = os.path.join(work_dir, "tmp")
archive_dir = os.path.join(work_dir, "archive")
restore_dir = os.path.join(work_dir, "data")
lock_file = os.path.join(tmp_dir, "lock")
log_file = os.path.join(work_dir, "execution.log")
filelist_file = os.path.join(work_dir, "filelist.txt")
rclone_log_file = os.path.join(work_dir, "rclone.log")
# mail
mail_from = "DarkSun <francesco@magno.cc>"
mail_to = "root"
# duplicity params
backup_path = "/store"
backup_name = "store"
common_opts = f"--name {backup_name} --archive-dir {archive_dir} --tempdir {tmp_dir} --num-retries 10"
backup_opts = "--volsize 1000 --allow-source-mismatch --asynchronous-upload"
filelist_opts = f"--exclude-device-files --include-filelist {filelist_file} --exclude '**'"
verify_opts = "--compare-data"
"""
end of global parameters
"""


def main():
    # parse arguments
    args = parse_args()
    # dry run
    if args.print_only:
        print_cmdline(args)
        exit(0)

    # check for lock
    if check_lock():
        cmd = sys.argv[0]
        cmd = os.path.basename(cmd).rstrip(".py")
        print(f"Another {cmd} instance is running, aborting execution...")
        exit(1)

    # acquire lock
    try:
        acquire_lock()
        try:
            rc = run_duplicity(args)
            if args.daemon:
                send_mail(rc, read_file(log_file))
        except OSError as ex:
            print(f"Error while launching duplicity: {ex.strerror}")
            exit(1)
    finally:
        release_lock()


def print_cmdline(args: Namespace) -> None:
    env = generate_command_env(args)
    envline = " ".join("=".join(_) for _ in env.items())
    cmdline = generate_duplicity_cmdline(args.command, dry_run=True, file_to_restore=args.file_to_restore)
    print(f"{envline} {cmdline}")


def run_duplicity(args: Namespace) -> int:
    env = os.environ.copy()
    env.update(generate_command_env(args))
    # if incremental backup, dry run first
    if args.command == "inc":
        cmdline = generate_duplicity_cmdline(args.command, dry_run=True)
        rc = run_subprocess(cmdline, env, True)
        out = read_file(log_file)
        delta = extract_delta_entries(out)
        if delta == 0:
            footer = "\n" + "No changes detected in dataset, skipping backup"
            if args.daemon:
                write_file(log_file, out + footer)
                return rc
            else:
                print(out + footer)
                return rc
    # continue normally
    cmdline = generate_duplicity_cmdline(args.command, dry_run=False, file_to_restore=args.file_to_restore)
    rc = run_subprocess(cmdline, env, args.daemon)
    return rc


def extract_delta_entries(out: str) -> int:
    match = re.search("DeltaEntries (\\d+)", out)
    if match:
        delta = int(match.group(1))
    else:
        delta = -1
    return delta


def run_subprocess(cmdline: str, env: dict, daemon: bool) -> int:
    cmd = shlex.split(cmdline)
    start_time = datetime.datetime.now()
    if daemon:
        p = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, text=True)
    else:
        p = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=None, stderr=None, env=env, text=True)
    end_time = datetime.datetime.now()
    footer = f"\nProcess completed in {int((end_time - start_time).total_seconds())} seconds with exit code {p.returncode}"
    if daemon:
        with open(log_file, "w") as out:
            out.write(p.stdout.rstrip("\n"))
            out.write(footer)
    else:
        print(footer)
    return p.returncode


def generate_command_env(args: Namespace) -> dict:
    env = {}
    env["PASSPHRASE"] = passphrase
    env["RCLONE_DRIVE_USE_TRASH"] = "false"
    env["RCLONE_NO_TRAVERSE"] = "true"
    env["RCLONE_DRIVE_CHUNK_SIZE"] = "128M"
    if args.rclone_verbose:
        env["RCLONE_LOG_FILE"] = rclone_log_file
        env["RCLONE_LOG_LEVEL"] = "DEBUG"
        env["RCLONE_STATS"] = "10m"
        env["RCLONE_STATS_ONE_LINE"] = "true"
    if args.bwlimit:
        env["RCLONE_BWLIMIT"] = "8.5M"
    return env


def generate_duplicity_cmdline(command: str, dry_run: bool = False, file_to_restore: Optional[str] = None) -> str:
    if command == "inc":
        cmdline = f"duplicity {common_opts} {backup_opts} {filelist_opts} {backup_path} {remote_url}"
    elif command == "full":
        cmdline = f"duplicity full {common_opts} {backup_opts} {filelist_opts} {backup_path} {remote_url}"
    elif command == "verify":
        if not file_to_restore:
            cmdline = f"duplicity verify {common_opts} {verify_opts} {filelist_opts} {remote_url} {backup_path}"
        else:
            ftr = file_to_restore.rstrip("/")
            cmdline = f"duplicity verify {common_opts} {verify_opts} {remote_url} {backup_path}/{ftr} --file-to-restore {ftr}"
    elif command == "status":
        cmdline = f"duplicity collection-status {common_opts} {remote_url}"
    elif command == "remove":
        cmdline = f"duplicity remove-all-but-n-full 1 {common_opts} --force {remote_url}"
    elif command == "cleanup":
        cmdline = f"duplicity cleanup {common_opts} --force {remote_url}"
    elif command == "list":
        cmdline = f"duplicity list-current-files {common_opts} {remote_url}"
    elif command == "restore":
        ftr = file_to_restore.rstrip("/")
        cmdline = f"duplicity restore {common_opts} {remote_url} {restore_dir}/{os.path.basename(ftr)} --file-to-restore {ftr}"
    else:
        raise NotImplementedError(f"Unexpected exception: command {command} not implemented")
    if dry_run:
        return cmdline + " --dry-run"
    return cmdline


def read_file(file):
    with open(file, "r") as infile:
        return infile.read()


def write_file(file, content):
    with open(file, "w") as outfile:
        outfile.write(content)


def check_lock():
    return os.path.isfile(lock_file)


def acquire_lock():
    with open(lock_file, "w"):
        pass


def release_lock():
    os.remove(lock_file)


def send_mail(rc: int, report: str) -> None:
    msg = MIMEText(report)
    msg["Subject"] = "duplicity log: return code {rc}".format(rc=rc)
    msg["From"] = mail_from
    msg["To"] = mail_to
    s = smtplib.SMTP('localhost')
    s.sendmail(mail_from, mail_to, msg.as_string())
    s.quit()


def parse_args() -> Namespace:
    parser = argparse.ArgumentParser(description="Wrapper for Duplicity command line parameters", formatter_class=lambda prog: argparse.HelpFormatter(prog, width=150))
    parser.add_argument("command", help="command to execute, must be one of the following: inc, full, verify, status, remove, cleanup, list, restore")
    parser.add_argument("file_to_restore", action="store", nargs="?", help="relative path to be restored or verified")
    mode_group = parser.add_mutually_exclusive_group(required=False)
    mode_group.add_argument("-n", "--print-only", action="store_true", help="show the generated duplicity command line and exit")
    mode_group.add_argument("-d", "--daemon", action="store_true", help="redirect all output to file, and send by mail the outcome of the execution")
    parser.add_argument("-b", "--bwlimit", action="store_true", help="limit rclone bandwidth to prevent Google Drive ban")
    parser.add_argument("-v", "--rclone-verbose", action="store_true", help="redirect rclone output to file")
    args = parser.parse_args()
    if args.command not in ["inc", "full", "verify", "status", "remove", "cleanup", "list", "restore"]:
        parser.error("command must be one of the following: inc, full, verify, status, remove, cleanup, list, restore")
    if args.command == "restore" and not args.file_to_restore:
        parser.error("file_to_restore is mandatory when restoring")
    return args


if __name__ == "__main__":
    main()
