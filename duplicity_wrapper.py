#!/usr/bin/env python2

"""
Wrapper for Duplicity command line parameters

File name: duplicity_wrapper.py
Author: Francesco Magno
Date created: 06/04/2018
Licence: GPL-3.0
Repository: https://github.com/GilGalaad/freebsd-utils
Python Version: 2.7
"""

import os
import sys
import argparse
import shlex
import datetime
import multiprocessing.dummy
import subprocess
import smtplib
from email.mime.text import MIMEText
from collections import namedtuple
Task = namedtuple("Task", ["args", "path"])
TaskResult = namedtuple("TaskResult", ["rc", "out"])

"""
global variables, customize here
"""
passphrase = "a_very_strong_password"
work_dir = "/opt/duplicity_work_dir"
temp_dir = work_dir + "/tempdir"
restore_dir = work_dir + "/restore"
log_file = work_dir + "/execution.log"
mail_from = "duplicity@example.com"
mail_to = "me@example.com"
common_opts = "--archive-dir {} --tempdir {} --num-retries 10".format(work_dir, temp_dir)
backup_opts = "--volsize 1000 --allow-source-mismatch --asynchronous-upload"
verify_opts = "--compare-data"
remote_url="duplicity://remote/url"
default_path_list=[
	"/store/documents",
	"/store/pictures",
	"/store/music",
	"/store/video",
	"/store/other_stuff"
]
"""
end of global variables
"""

def main():
	# parse arguments
	args = parse_args()
	if args.all:
		path_list = default_path_list
	else:
		path_list = [args.path]

	# create tasks
	task_list = []
	for path in path_list:
		task_list.append(Task(args, path))

	# if parallel mode, check and create global lock file
	if args.all:
		if check_lock("global"):
			sys.stderr.write(datetime.datetime.today().strftime("%d/%m/%Y %H:%M:%S") + " - Another {} instance is running, aborting execution...\n".format(sys.argv[0].rstrip(".py")))
			sys.exit(1)
		else:
			acquire_lock("global")

	# process pool
	pool = multiprocessing.dummy.Pool(processes=len(task_list))
	res = pool.map(execute_task, task_list, 1)
	pool.close()
	pool.join()

	# if parallel mode, remove global lock file
	if args.all:
		release_lock("global")

	# if interactive mode, write to stdout, else write to file and send mail
	aggr_rc = 0
	aggr_report = ""
	for task_result in res:
		aggr_rc += task_result.rc
		aggr_report += task_result.out
		if not args.dry_run:
			aggr_report += "\n\n"
	aggr_report = aggr_report.rstrip("\n") + "\n"
	if not args.daemon:
		sys.stdout.write(aggr_report)
	else:
		with open(log_file, "w+") as file:
			file.write(aggr_report)
		send_mail(aggr_rc, aggr_report)


def execute_task(task):
	cmdline = generate_duplicity_cmdline(task)
	if task.args.dry_run:
		return TaskResult(0, cmdline + "\n")
	# check and create lock file
	backup_name = get_backup_name(task.path)
	if check_lock(backup_name):
		return TaskResult(1, datetime.datetime.today().strftime("%d/%m/%Y %H:%M:%S") + " - Another {} instance is running on path `{}`, aborting execution...\n".format(sys.argv[0].rstrip(".py"), task.path))
	else:
		acquire_lock(backup_name)
	# execute duplicity
	start_time = datetime.datetime.today()
	rc, out = exec_duplicity(cmdline)
	end_time = datetime.datetime.today()
	report = "********************************************************************************\n"
	report += start_time.strftime("%d/%m/%Y %H:%M:%S") + " - Running command `{}` on path `{}`\n".format(task.args.command, task.path)
	report += out
	report += end_time.strftime("%d/%m/%Y %H:%M:%S") + " - Process completed in {} seconds with exit code {}\n".format(int((end_time - start_time).total_seconds()), rc)
	report += "********************************************************************************\n"
	# remove lock file
	release_lock(backup_name)
	return TaskResult(rc, report)

def exec_duplicity(cmd_line):
	args = shlex.split(cmd_line)
	try:
		pass_env = os.environ.copy()
		pass_env["PASSPHRASE"]=passphrase
		p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=pass_env)
		out, _ = p.communicate()
		out = out.rstrip("\n") + "\n"
		return p.returncode, out
	except OSError as ex:
		return 1, "Error while calling `{}`: {}\n".format(args[0], ex.strerror)

def generate_duplicity_cmdline(task):
	if task.args.command == "auto":
		cmdline = "duplicity --full-if-older-than 12M {co} {bo} --name {bn} {pa} {url}/{bn}".format(co=common_opts, bo=backup_opts, bn=get_backup_name(task.path), pa=task.path, url=remote_url)
	elif task.args.command == "inc":
		cmdline = "duplicity {co} {bo} --name {bn} {pa} {url}/{bn}".format(co=common_opts, bo=backup_opts, bn=get_backup_name(task.path), pa=task.path, url=remote_url)
	elif task.args.command == "full":
		cmdline = "duplicity full {co} {bo} --name {bn} {pa} {url}/{bn}".format(co=common_opts, bo=backup_opts, bn=get_backup_name(task.path), pa=task.path, url=remote_url)
	elif task.args.command == "verify":
		cmdline = "duplicity verify {co} {vo} --name {bn} {url}/{bn} {pa}".format(co=common_opts, vo=verify_opts, bn=get_backup_name(task.path), url=remote_url, pa=task.path)
	elif task.args.command == "status":
		cmdline="duplicity collection-status {co} --name {bn} {url}/{bn}".format(co=common_opts, bn=get_backup_name(task.path), url=remote_url)
	elif task.args.command == "remove":
		cmdline="duplicity remove-all-but-n-full 1 {co} --force --name {bn} {url}/{bn}".format(co=common_opts, bn=get_backup_name(task.path), url=remote_url)
	elif task.args.command == "cleanup":
		cmdline="duplicity cleanup {co} --force --name {bn} {url}/{bn}".format(co=common_opts, bn=get_backup_name(task.path), url=remote_url)
	elif task.args.command == "list":
		cmdline="duplicity list-current-files {co} --name {bn} {url}/{bn}".format(co=common_opts, bn=get_backup_name(task.path), url=remote_url)
	elif task.args.command == "restore":
		cmdline="duplicity restore {co} --name {bn} {url}/{bn} {res}/{bn}".format(co=common_opts, bn=get_backup_name(task.path), url=remote_url, res=restore_dir)
	else:
		raise NotImplementedError("Unexpected exception: comand {} not implemented".format(command))
	return cmdline

def parse_args():
	parser = argparse.ArgumentParser(description="Wrapper for Duplicity command line parameters", formatter_class=lambda prog: argparse.HelpFormatter(prog, width=150))
	parser.add_argument("command", help="command to execute, must be one of the following: auto, inc, full, verify, status, remove, cleanup, list, restore")
	mode_group = parser.add_mutually_exclusive_group(required=False)
	mode_group.add_argument("-n", "--dry-run", action="store_true", help="show the generated duplicity command line and exit, mutually exclusive with `--daemon` since no process is actually executed")
	mode_group.add_argument("-d", "--daemon", action="store_true", help="redirect all output to file, and send by mail the outcome of the execution")
	dir_group = parser.add_mutually_exclusive_group(required=True)
	dir_group.add_argument("-a", "--all", action="store_true", help="spawn a parallel duplicity process for each configured directory")
	dir_group.add_argument("path", nargs="?", help="absolute path of the directory to work with, mutually exclusive with `--all` option")
	args = parser.parse_args()
	if args.command not in ["auto", "inc", "full", "verify", "status", "remove", "cleanup", "list", "restore"]:
		parser.error("command must be one of the following: auto, inc, full, verify, status, remove, cleanup, list, restore")
	if args.path != None and not args.path.startswith("/"):
		parser.error("path must be absolute")
	if args.path != None:
		args.path = args.path.rstrip("/")
	return args

def get_backup_name(path):
	return path.strip("/").replace("/","_")

def check_lock(name):
	path = "{}/{}.lock".format(temp_dir, name)
	return os.path.isfile(path)

def acquire_lock(name):
	path = "{}/{}.lock".format(temp_dir, name)
	with open(path, "w+"):
		pass

def release_lock(name):
	path = "{}/{}.lock".format(temp_dir, name)
	os.remove(path)

def send_mail(aggr_rc, aggr_report):
	msg = MIMEText(aggr_report)
	msg["Subject"] = "duplicity log: status {}".format(aggr_rc)
	msg["From"] = mail_from
	msg["To"] = mail_to
	s = smtplib.SMTP('localhost')
	s.sendmail(mail_from, mail_to, msg.as_string())
	s.quit()

if __name__ == "__main__":
	main()
