#!/usr/bin/python3
import sys, subprocess
from etcdget import etcdget as get
from etcddel import etcddel as dels 
from etcdput import etcdput as put
from time import time as stamp
import logmsg

def dosync(leader, leaderip, sync, *args):
  dels(leaderip, sync)
  put(leaderip, *args)
  put(leaderip, args[0]+'/'+leader,args[1])
  return 


def changepriv(leader, leaderip, myhost, myip, user,priv,request='admin'):
 with open('/root/Privtmp','w') as f:
  f.write(' '.join([leader, leaderip, myhost, myip, user,priv,request])+'/n')
 logmsg.initlog(leaderip,myhost)
 if leader == myhost:
    etcdip = leaderip
 else:
    etcdip = myip
 syspriv = 'UserPrivilegesch'
 cmdline = ['/TopStor/privthis.sh',syspriv, request]
 res = subprocess.run(cmdline,stdout=subprocess.PIPE).stdout
 if 'true' not in res.decode('utf-8'):
  return
 userinfo = get(etcdip,'usersinfo/'+user)
 # QSD5.321 (test 625 step 5): a user that does not exist (etcdget answers '_1') or a malformed row (fewer than 4 '/'
 # fields) is refused and nothing is written; before, usersinfo/<user> = '_1/<privs>' was written with Priv1003 "Success"
 leftpart = str(userinfo[0]).split('/')[0:4] if len(userinfo) > 0 else []
 if len(leftpart) < 4 or leftpart[0] in ('_1', '-1', '', 'None'):
  logmsg.sendlog('Priv1005','error',request,user)
  return
 logmsg.sendlog('Priv1002','info',request,user)
 put(leaderip, 'usersinfo/'+user, '/'.join(leftpart)+'/'+priv)
 dosync(leader, leaderip, 'sync/priv/'+user,'sync/priv/'+user+'/request', 'priv_'+user+'_'+str(stamp()))
 #put(leaderip, 'user/'+myhost,str(stamp()))
 #broadcasttolocal('usersinfo/'+user, '/'.join(leftpart)+'/'+priv)
 print('/'.join(leftpart)+'/'+priv)
 logmsg.sendlog('Priv1003','info',request,user)
 
 return


if __name__=='__main__':
 changepriv(*sys.argv[1:])

