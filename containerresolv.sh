#!/bin/sh
# containerresolv.sh [dns] [search]   (test 673, QX-074 step 2)
# Writes /root/gitrepo/resolv.conf, the /etc/resolv.conf of the node's containers (flask, httpd, etcd, etcdclient):
# the cluster DNS server FIRST (the resolver stops at the first answer and the internal DNS 10.11.12.7 answers NXDOMAIN for
# the AD domain), then the internal DNS, then the search domain.  It was always only "nameserver 10.11.12.7", so the API
# container never used the DNS set in Running Nodes.  Without arguments the values come from the node itself: the DNS that
# HostManualconfigDNS set (/etc/dhcp/dhclient.conf "supersede domain-name-server") and the search line of /etc/resolv.conf.
# The file is bind-mounted into running containers: it is rewritten in place (same inode), never replaced.
dns="$1"
search="$2"
if [ $# -eq 0 ]; then
 dns=`grep -h 'supersede domain-name-server' /etc/dhcp/dhclient.conf 2>/dev/null | head -1 | sed 's/.*domain-name-server *//; s/[;,].*//; s/ //g'`
 search=`grep -h '^search ' /etc/resolv.conf 2>/dev/null | head -1 | awk '{print $2}'`
fi
case "$dns" in ''|_1|10.11.12.7) dns='';; esac
case "$search" in _1) search='';; esac
tmp=`mktemp`
{
 [ -n "$dns" ] && echo "nameserver $dns"
 echo "nameserver 10.11.12.7"
 [ -n "$search" ] && echo "search $search"
} > $tmp
mkdir -p /root/gitrepo
cat $tmp > /root/gitrepo/resolv.conf
rm -f $tmp
