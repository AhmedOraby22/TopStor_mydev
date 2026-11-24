#!/bin/bash
# -oExitOnForwardFailure/-oServerAlive (test 22 re-check): a tunnel whose port is still held on the partner (a stale sshd session
# of an earlier partnership) used to stay up without its forward, so users, groups and snapshots silently stopped syncing
ssh -oStrictHostKeyChecking=no -oExitOnForwardFailure=yes -oServerAliveInterval=15 -oServerAliveCountMax=3 -p secureport -i /TopStordata/receiver/remotenode   -N -R remotecluster:tunnelport:mycluster:2379 remotenode Rremote sshreceiver
if [ $? -ne 0 ];
then
	echo Somthing went wrong, removing active links to this remote node
	kill -9 `pgrep Rremote  -a | grep remotenode  | awk '{print $1}'`
fi
#_REMOTE_ssh -p secureport -i /TopStordata/remotenode/remotenode remotenode ls
