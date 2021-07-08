#!/usr/bin/env python3.8

"""
Show temperature for all attached SATA and NVME drives

File name: hdd_temp.py
Author: Francesco Magno
Date created: 01/04/2018
Licence: GPL-3.0
Repository: https://github.com/GilGalaad/freebsd-utils
Python Version: 3.7
"""

import shlex
import subprocess
import sys


def main():
    dev_list = detect_devices()
    temp_list = []
    for dev in dev_list:
        temp_list.append(read_temp_smartctl(dev))
    for i in range(0, len(dev_list)):
        sys.stdout.write("{:<10} {}\n".format(dev_list[i], temp_list[i]))


def subpr(cmd_line):
    args = shlex.split(cmd_line)
    try:
        p = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return p.returncode, p.stdout, p.stderr
    except OSError as ex:
        sys.stderr.write("Error while calling `{}`: {}\n".format(args[0], ex.strerror))
        sys.exit(1)


def detect_devices():
    dev_list = []
    cmd_line = "geom disk list"
    rc, out, err = subpr(cmd_line)
    if rc != 0:
        sys.stderr.write("Error while calling `geom`: {}".format(err))
        sys.exit(1)
    for line in out.split("\n"):
        if "Name:" in line:
            dev_name = line.split()[2]
            if dev_name.startswith("nvd"):
                dev_name = dev_name.replace("nvd", "nvme")
            dev_list.append(dev_name)
    return dev_list


def read_temp_smartctl(dev):
    cmd_line = "smartctl -a /dev/" + dev
    rc, out, _ = subpr(cmd_line)
    if rc == 1:
        sys.stderr.write("Error while calling `smartctl`: {}\n".format(out.split("\n")[3]))
        sys.exit(1)
    for line in out.split("\n"):
        if "Temperature_Celsius" in line:
            return line.split()[9] + " Celsius"
        elif "Temperature:" in line:
            return line.split()[1] + " Celsius"
    return "Temperature not available"


if __name__ == "__main__":
    main()
