#!/usr/bin/env python3.7

"""
Wrapper for Duplicity command line parameters

File name: duplicity_wrapper.py
Author: Francesco Magno
Date created: 21/04/2020
Licence: GPL-3.0
Repository: https://github.com/GilGalaad/freebsd-utils
Python Version: 3.7
"""

import argparse
import datetime
import os
import re
import shlex
import smtplib
import subprocess
import sys
from email.mime.text import MIMEText

"""
global parameters, customize here
"""
# remote repository
remote_name = "gsuite:"
remote_url = "rclone://" + remote_name + "/duplicity"
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
common_opts = "--name {bn} --archive-dir {ad} --tempdir {td} --num-retries 10".format(bn=backup_name, ad=archive_dir, td=tmp_dir)
backup_opts = "--volsize 1000 --allow-source-mismatch --asynchronous-upload"
filelist_opts = "--exclude-device-files --include-filelist {fl} --exclude '**'".format(fl=filelist_file)
verify_opts = "--compare-data"
# misc
tms_format = "%d/%m/%Y %H:%M:%S"
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
        print("{tms} - Another {cmd} instance is running, aborting execution...".format(tms=datetime.datetime.today().strftime(tms_format), cmd=cmd))
        exit(1)

    # acquire lock
    try:
        acquire_lock()
        try:
            rc = run_duplicity(args)
        except OSError as ex:
            print("Error while launching duplicity: {err}".format(err=ex.strerror))
            exit(1)

        if args.daemon:
            send_mail(rc, read_file(log_file))
    finally:
        release_lock()


def print_cmdline(args):
    env = generate_command_env(args)
    envline = " ".join("=".join(_) for _ in env.items())
    cmdline = generate_duplicity_cmdline(args.command, dry_run=True, file_to_restore=args.file_to_restore)
    print(envline + " " + cmdline)


def run_duplicity(args):
    env = os.environ.copy()
    env.update(generate_command_env(args))
    # if backing up, dry run first
    if args.command == "inc":
        cmdline = generate_duplicity_cmdline(args.command, dry_run=True)
        rc = exec_subprocess(cmdline, env, True)
        out = read_file(log_file)
        delta = extractDeltaEntries(out)
        if delta == 0:
            message = "\n" + "No changes detected in dataset, skipping backup"
            if args.daemon:
                write_file(log_file, out + message)
                return rc
            else:
                print(out + message)
                return rc
    # continue normally
    cmdline = generate_duplicity_cmdline(args.command, dry_run=False, file_to_restore=args.file_to_restore)
    rc = exec_subprocess(cmdline, env, args.daemon)
    return rc


def extractDeltaEntries(out):
    match = re.search("DeltaEntries (\\d+)", out)
    if match:
        delta = int(match.group(1))
    else:
        delta = -1
    return delta


def exec_subprocess(cmdline, env, daemon):
    cmd = shlex.split(cmdline)
    if daemon:
        start_time = datetime.datetime.today()
        p = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, text=True)
        end_time = datetime.datetime.today()
        rc = p.returncode
        with open(log_file, "w") as out:
            out.write(p.stdout.rstrip("\n"))
            report = ("\n" + "Process completed in {elapsed} seconds with exit code {rc}".format(elapsed=int((end_time - start_time).total_seconds()), rc=rc))
            out.write(report)
    else:
        start_time = datetime.datetime.today()
        p = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=None, stderr=None, env=env)
        end_time = datetime.datetime.today()
        rc = p.returncode
        report = ("\n" + "Process completed in {elapsed} seconds with exit code {rc}".format(elapsed=int((end_time - start_time).total_seconds()), rc=rc))
        print(report)
    return rc


def generate_command_env(args):
    env = {}
    env["PASSPHRASE"] = passphrase
    env["RCLONE_DRIVE_USE_TRASH"] = "false"
    env["RCLONE_NO_TRAVERSE"] = "true"
    env["RCLONE_DRIVE_CHUNK_SIZE"] = "64M"
    if args.rclone_verbose:
        env["RCLONE_LOG_FILE"] = rclone_log_file
        env["RCLONE_LOG_LEVEL"] = "DEBUG"
        env["RCLONE_STATS"] = "10m"
        env["RCLONE_STATS_ONE_LINE"] = "true"
    if args.bwlimit:
        env["RCLONE_BWLIMIT"] = "8.5M"
    return env


def generate_duplicity_cmdline(command, dry_run=False, file_to_restore=None):
    if command == "inc":
        cmdline = "duplicity {co} {bo} {fl} {pa} {url}".format(co=common_opts, bo=backup_opts, fl=filelist_opts, pa=backup_path, url=remote_url)
    elif command == "full":
        cmdline = "duplicity full {co} {bo} {fl} {pa} {url}".format(co=common_opts, bo=backup_opts, fl=filelist_opts, pa=backup_path, url=remote_url)
    elif command == "verify":
        if not file_to_restore:
            cmdline = "duplicity verify {co} {vo} {fl} {url} {pa}".format(co=common_opts, vo=verify_opts, fl=filelist_opts, url=remote_url, pa=backup_path)
        else:
            ftr = file_to_restore.rstrip("/")
            cmdline = "duplicity verify {co} {vo} {url} {pa}/{ftr} --file-to-restore {ftr}".format(co=common_opts, vo=verify_opts, fl=filelist_opts, url=remote_url, pa=backup_path, ftr=ftr)
    elif command == "status":
        cmdline = "duplicity collection-status {co} {url}".format(co=common_opts, url=remote_url)
    elif command == "remove":
        cmdline = "duplicity remove-all-but-n-full 1 {co} --force {url}".format(co=common_opts, url=remote_url)
    elif command == "cleanup":
        cmdline = "duplicity cleanup {co} --force {url}".format(co=common_opts, url=remote_url)
    elif command == "list":
        cmdline = "duplicity list-current-files {co} {url}".format(co=common_opts, url=remote_url)
    elif command == "restore":
        ftr = file_to_restore.rstrip("/")
        cmdline = "duplicity restore {co} {url} {res}/{dest} --file-to-restore {ftr}".format(co=common_opts, url=remote_url, res=restore_dir, dest=os.path.basename(ftr), ftr=ftr)
    else:
        raise NotImplementedError("Unexpected exception: comand {} not implemented".format(command))
    if dry_run == True:
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


def send_mail(rc, report):
    msg = MIMEText(report)
    msg["Subject"] = "duplicity log: return code {rc}".format(rc=rc)
    msg["From"] = mail_from
    msg["To"] = mail_to
    s = smtplib.SMTP('localhost')
    s.sendmail(mail_from, mail_to, msg.as_string())
    s.quit()


def parse_args():
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
