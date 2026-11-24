# etcdfast.sh -- sourced by the user scripts (UnixAddUser, UnixChangeUser) that run in the node's single command consumer.
# Test 612 (QX-013) step 1: every /TopStor|/pace etcdget.py / etcdput.py / etcddel.py call starts a python interpreter
# (0.1-0.4 s each on a loaded 2-vCPU leader); a bare etcdctl call takes 0.03-0.05 s. These functions give the SAME output as
# the python helpers (checked: identical bytes for usersigroup/user/volumes prefixes and single keys) without the python start.
# Same etcd endpoint form as the python helpers (http://<ip>:2379, no user).
# ec <ip> <etcdctl args...>
ec() { local ip=$1; shift; ETCDCTL_API=3 timeout 10 etcdctl --endpoints=http://$ip:2379 "$@"; }
# erows <ip> <prefix>: like "etcdget.py <ip> <prefix> --prefix": one "('<key>', '<value>')" line per key
erows() { ec "$1" get "$2" --prefix | awk 'NR%2{k=$0;next}{printf "(%c%s%c, %c%s%c)\n",39,k,39,39,$0,39}'; }
# eget <ip> <key>: like "etcdget.py <ip> <key>": the value, or _1 when the key does not exist (or etcd does not answer)
eget() { local o; o=`ec "$1" get -- "$2"`; if [ -n "$o" ]; then printf '%s\n' "$o" | sed -n '2,$p'; else echo _1; fi; }
# eput <ip> <key> <value>: like "etcdput.py <ip> <key> <value>" (output dropped)
eput() { ec "$1" put -- "$2" "$3" >/dev/null 2>&1; }
# edelmatch <ip> <prefix> <text>: like "etcddel.py <ip> <prefix> <text>": delete the keys under <prefix> whose key or value
# holds <text>
edelmatch() { ec "$1" get "$2" --prefix | awk -v t="$3" 'NR%2{k=$0;next} index(k,t)||index($0,t){print k}' | while IFS= read -r k; do [ -n "$k" ] && ec "$1" del -- "$k" >/dev/null 2>&1; done; }
