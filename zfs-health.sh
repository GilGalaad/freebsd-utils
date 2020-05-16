#!/usr/local/bin/bash

# variables
HEALTH_PROBLEM=0
CAPACITY_PROBLEM=0
MAX_CAPACITY=80

# health check
ZSTATUS=$(zpool status -x)
if [[ $ZSTATUS != "all pools are healthy" ]]; then
	HEALTH_PROBLEM=1
fi

# errors check
ZSTATUS=$(zpool status | grep ONLINE | grep -v state | awk '{print $3 $4 $5}' | grep -v 000)
if [[ -n "${ZSTATUS}" ]]; then
	HEALTH_PROBLEM=1
fi

# capacity check
ZCAPACITY=$(zpool list -H -o capacity | cut -d'%' -f1)
for i in ${ZCAPACITY[@]}
do
	if [[ $i -gt $MAX_CAPACITY ]]; then
		CAPACITY_PROBLEM=1
	fi
done

# mail report
if [[ $HEALTH_PROBLEM -ne 0 ]]; then
	zpool status | mailx -s "ZFS pool - Health problem" root
fi
if [[ $CAPACITY_PROBLEM -ne 0 ]]; then
	zpool list | mailx -s "ZFS pool - Capacity exceeded" root
fi
