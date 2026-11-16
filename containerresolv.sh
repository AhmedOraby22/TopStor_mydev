#!/bin/sh
# containerresolv.sh [dns] [search]   (test 673, QX-074 step 2)
# The node's containers (flask = the API, httpd, etcd, etcdclient, ...) share /root/gitrepo/resolv.conf as /etc/resolv.conf.
# It was only "nameserver 10.11.12.7" (intdns, dnsmasq), so the API container never used the DNS set in Running Nodes and
# could not resolve the AD domain.  The internal DNS must stay FIRST: every container finds its local etcd by the name
# 'etcd' (http://etcd:2379), which only intdns knows; a cluster DNS in front of it answers NXDOMAIN and the resolver stops
# there (QSD5.356 put it first: every local etcd read failed).  So:
#  - intdns forwards the cluster's search domain to the cluster DNS (/etc/dnsmasq.d/cluster.conf, server=/<domain>/<dns>);
#  - the shared resolv.conf: intdns, then the cluster DNS (used if intdns does not answer), then the search domain.
# Without arguments the values come from the node itself: the DNS that HostManualconfigDNS set (/etc/dhcp/dhclient.conf
# "supersede domain-name-server") and the search line of /etc/resolv.conf.
# The file is bind-mounted into running containers: it is rewritten in place (same inode), never replaced.
dns="$1"
search="$2"
if [ $# -eq 0 ]; then
 dns=`grep -h 'supersede domain-name-server' /etc/dhcp/dhclient.conf 2>/dev/null | head -1 | sed 's/.*domain-name-server *//; s/[;,].*//; s/ //g'`
 search=`grep -h '^search ' /etc/resolv.conf 2>/dev/null | head -1 | awk '{print $2}'`
 # after a reboot NetworkManager rewrites /etc/resolv.conf without the search line (the node connections lose dns-search):
 # HostManualconfigDNS also keeps it in dhclient.conf, which survives
 [ -z "$search" ] && search=`grep -h 'supersede domain-search' /etc/dhcp/dhclient.conf 2>/dev/null | head -1 | sed 's/.*domain-search *//; s/[";]//g; s/ //g'`
fi
case "$dns" in ''|_1|10.11.12.7) dns='';; esac
case "$search" in _1) search='';; esac
tmp=`mktemp`
{
 echo "nameserver 10.11.12.7"
 [ -n "$dns" ] && echo "nameserver $dns"
 [ -n "$search" ] && echo "search $search"
 # a single name ('etcd') is asked as it is FIRST: without ndots:0 the resolver asked etcd.<domain> first, which waits
 # for the cluster DNS (10 s per lookup when it is slow or unreachable, test 674 step 6: node1 could not rejoin)
 [ -n "$search" ] && echo "options ndots:0 timeout:2 attempts:1"
} > $tmp
mkdir -p /root/gitrepo
cmp -s $tmp /root/gitrepo/resolv.conf || cat $tmp > /root/gitrepo/resolv.conf
# intdns: forward the search domain to the cluster DNS; restarted only when that changes (dnsmasq reads it at start)
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx intdns; then
 want=''
 [ -n "$dns" ] && [ -n "$search" ] && want="server=/$search/$dns"
 have=`docker exec intdns sh -c 'cat /etc/dnsmasq.d/cluster.conf 2>/dev/null'`
 if [ "$want" != "$have" ]; then
  if [ -n "$want" ]; then
   docker exec intdns sh -c "echo '$want' > /etc/dnsmasq.d/cluster.conf"
  else
   docker exec intdns rm -f /etc/dnsmasq.d/cluster.conf
  fi
  docker restart -t 2 intdns >/dev/null; sleep 2
 fi
 # docker gives intdns the node's search domain whenever it (re)starts the container; intdns must not use it: the start
 # scripts look up 'etcd' with `docker exec intdns nslookup etcd`, which then asked etcd.<domain> (forwarded to the cluster
 # DNS: NXDOMAIN), got no address and started the leader's etcd without one (test 673 step 4: no etcd on the new leader)
 docker exec intdns sh -c "grep -v '^search' /etc/resolv.conf > /tmp/r.c; cat /tmp/r.c > /etc/resolv.conf; rm -f /tmp/r.c" 2>/dev/null
fi
rm -f $tmp
