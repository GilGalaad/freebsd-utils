#!/usr/bin/env python3.8

"""
Show temperature for all attached SATA and NVME drives

File name: hdd_temp.py
Author: Francesco Magno
Date created: 01/04/2018
Licence: GPL-3.0
Repository: https://github.com/GilGalaad/freebsd-utils
Python Version: 3.8
"""

import shlex
import subprocess
import sys
from typing import List, Tuple, Union


def main():
    dev_list = detect_devices()
    temperature_list = [read_temp_smartctl(dev) for dev in dev_list]
    for i in range(0, len(dev_list)):
        print(f"{dev_list[i]:<10} {temperature_list[i]}")


def detect_devices() -> List[str]:
    cmd_line = "geom disk list"
    rc, out, err = run_subprocess(cmd_line)
    if rc != 0:
        print(f"Error while calling 'geom': {err}")
        sys.exit(1)
    dev_list: List[str] = []
    for line in out.split("\n"):
        if "Name:" in line:
            dev_name = line.split()[2]
            if dev_name.startswith("nvd"):
                dev_name = dev_name.replace("nvd", "nvme")
            dev_list.append(dev_name)
    return dev_list


def run_subprocess(cmd_line: str) -> Tuple[int, Union[str, bytes], Union[str, bytes]]:
    args = shlex.split(cmd_line)
    try:
        p = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return p.returncode, p.stdout, p.stderr
    except OSError as ex:
        print(f"OSError while calling '{args[0]}': {ex.strerror}")
        sys.exit(1)


def read_temp_smartctl(dev: str) -> str:
    cmd_line = f"smartctl -a /dev/{dev}"
    rc, out, _ = run_subprocess(cmd_line)
    if rc == 1:
        error_msg = out.split("\n")[3]
        print(f"Error while calling 'smartctl': {error_msg}\n")
        sys.exit(1)
    for line in out.split("\n"):
        if "Temperature_Celsius" in line:
            return f"{line.split()[9]} Celsius"
        elif "Temperature:" in line:
            return f"{line.split()[1]} Celsius"
    return "Temperature not available"


if __name__ == "__main__":
    main()
