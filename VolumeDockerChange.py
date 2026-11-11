#!/usr/bin/python3
import subprocess,sys


def delcifs(*args):
 oldipaddr = args[0]
 oldsubnet = args[1]
 vtype = args[2]
 res = vtype+'-'+oldipaddr 
 cmdline = 'docker rm -f '+res
 result = subprocess.run(cmdline.split(),stdout=subprocess.PIPE).stdout.decode('utf-8')
 # QSD5.337 (test 646 QX-047 step 3): the old address goes live with shareaddr.sh (ip addr del + profile edit); the former
 # "nmcli conn up cmynode" re-activated bond0 and dropped the node and cluster addresses with it
 cmdline='/TopStor/shareaddr.sh del '+oldipaddr+' '+oldsubnet
 result = subprocess.run(cmdline.split(),stdout=subprocess.PIPE).stdout.decode('utf-8')
   
   
if __name__=='__main__':
 with open('/root/volumedockerchange','w') as f:
    f.write(str(sys.argv[1:])+'\n')
 delcifs(*sys.argv[1:])
