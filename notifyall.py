#!/usr/bin/python3
# notifyall.py -- send several notifications in ONE python (run in the etcdclient container, as logmsg.py and logqueue.py are).
# stdin: one notification per line, written by the notify() function of UnixAddUser/UnixChangeUser:
#   /TopStor/logmsg.py <code> <level> <requester> <args...>     -> logmsg.sendlog(...)
#   /TopStor/logqueue.py <script> <state> <requester>           -> logqueue.queuethis(...)
# The lines are sent in their order. Test 612 (QX-013) step 1: each notification was its own docker exec + python + pika import
# (9 per user add); on a loaded 2-vCPU leader they took the CPU the next user add needed.
import sys
from etcdgetlocalpy import etcdget as getlocal
import logmsg, logqueue

if __name__ == '__main__':
 leaderip, host = getlocal('leaderip')[0], getlocal('clusternode')[0]
 logmsg.initlog(leaderip, host)
 logqueue.initqueue(leaderip, host)
 for line in sys.stdin:
  args = line.split()
  if len(args) < 2:
   continue
  try:
   if args[0].endswith('logmsg.py'):
    logmsg.sendlog(*args[1:])
   elif args[0].endswith('logqueue.py'):
    logqueue.queuethis(*args[1:])
  except Exception as e:
   print('notifyall: not sent:', args[0], args[1:2], e, file=sys.stderr)
