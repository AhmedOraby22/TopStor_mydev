#!/usr/bin/python3
# Runs after a pool import (see DGsetPool's "import" branch and pace zpooltoimport.py). If the pool that
# just got imported here has a cache (L2ARC) vdev that lives on a different
# host than the one now owning the pool, that disk is no longer local -
# reachable only over the network - so it's worse than useless as a read
# cache. A cache disk whose host is unknown or that zpool reports as
# UNAVAIL/FAULTED/REMOVED/OFFLINE (the disk of a stopped or lost node) is
# not local either. Swap it for a disk of this host:
#   1. a spare cache disk of this host ("Save as Spare", etcd cachespares,
#      the pree 'cache' raid), smallest first;
#   2. else a free disk of this host at the smallest size tier - strictly
#      smaller than the rest of this host's free disks - the same relative-size
#      rule the manual "Update Cache" button uses (see fapi.py's dgsupdatecache);
#   3. else (every free disk the same size) the smallest free disk, but only
#      when the host keeps at least one more free disk for self-heal.
# A gone disk is removed by its guid (zpool status -g), its by-id path cannot
# be resolved any more.
import sys
import subprocess

sys.path.insert(0, '/TopStor')
from allphysicalinfo import getall, initallphy

BADSTATES = ('UNAVAIL', 'FAULT', 'REMOVED', 'OFF')
BADHOSTS = ('', '_1', 'UNAVAIL', None)


def resolve_by_id(disk_substr):
    out = subprocess.run(['ls', '/dev/disk/by-id/'], stdout=subprocess.PIPE).stdout.decode()
    for line in out.splitlines():
        if disk_substr in line and 'part' not in line:
            return line
    return None


def diskwwn(name):
    n = str(name).split('/')[-1]
    if '-part' in n:
        n = n.split('-part')[0]
    for pre in ('scsi-', 'wwn-0x', 'wwn-'):
        if n.startswith(pre):
            return n[len(pre):]
    return n


def samedisk(a, b):
    wa, wb = diskwwn(a), diskwwn(b)
    return a == b or (len(wa) > 3 and (wa == wb or '3' + wa == wb or wa == '3' + wb))


def cache_section(text):
    # [(name, state)] of the cache vdev section of a 'zpool status <pool>' output
    entries = []
    incache = False
    depth = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        words = stripped.split()
        indent = len(line) - len(line.lstrip())
        if words[0] == 'cache' and len(words) == 1:
            incache, depth = True, indent
            continue
        if incache:
            if indent <= depth or ':' in words[0]:
                break
            entries.append((words[0], words[1] if len(words) > 1 else ''))
    return entries


def local_cache(pool):
    # [(name, state, guid)] of the pool's cache vdevs as zpool on THIS node sees them
    try:
        plain = subprocess.run(['/sbin/zpool', 'status', pool], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30).stdout.decode()
        guids = subprocess.run(['/sbin/zpool', 'status', '-g', pool], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30).stdout.decode()
    except Exception as e:
        print(f"fixcachelocality: zpool status {pool} failed: {e}")
        return []
    p, g = cache_section(plain), cache_section(guids)
    return [(name, state, g[i][0] if i < len(g) else None) for i, (name, state) in enumerate(p)]


def notlocal(d, info, myhost, zcache):
    disk = info['disks'].get(d)
    if not disk:
        return True
    if disk.get('host') in BADHOSTS or disk.get('host') != myhost:
        return True
    if any(s in str(disk.get('status', '')) or s in str(disk.get('changeop', '')) for s in BADSTATES):
        return True
    for name, state, _ in zcache:
        if samedisk(name, d) and state != 'ONLINE':
            return True
    return False


def pick_cache(info, myhost, exclude):
    # returns (disk, kind) or (None, None)
    pooldisks = set()
    for rid, raid in info['raids'].items():
        if '_pdhcp' in rid:
            pooldisks.update(raid.get('disks', []))

    def usable(did):
        disk = info['disks'].get(did, {})
        return disk.get('host') == myhost and did not in pooldisks and did not in exclude

    def size(did):
        try:
            return float(info['disks'].get(did, {}).get('size', 0))
        except (TypeError, ValueError):
            return None

    spares = set(info['raids'].get('cache_pree', {}).get('disks', []))
    spares.update(d for d, v in info['disks'].items() if v.get('pool') == 'pree' and v.get('raid') == 'cache')
    spare_sizes = {d: size(d) for d in spares if usable(d) and size(d) is not None}
    if spare_sizes:
        return min(spare_sizes, key=lambda d: (spare_sizes[d], d)), 'spare cache'

    free = set(info['raids'].get('free', {}).get('disks', []))
    free.update(d for d, v in info['disks'].items() if v.get('raid') == 'free')
    local_sizes = {d: size(d) for d in free if usable(d) and d not in spares and size(d) is not None}
    if not local_sizes:
        return None, None
    smallest = min(local_sizes.values())
    largest = max(local_sizes.values())
    candidates = sorted(d for d, s in local_sizes.items() if s == smallest)
    if smallest < largest:
        return candidates[0], 'free (smallest)'
    if len(local_sizes) > 1:
        return candidates[0], 'free (all the same size, one left for self-heal)'
    return None, None


def main():
    if len(sys.argv) < 4:
        return
    leaderip = sys.argv[1]
    pool = sys.argv[2]
    myhost = sys.argv[3]

    initallphy(leaderip)
    info = getall(leaderip)

    pool_data = info['pools'].get(pool)
    if not pool_data:
        return

    cache_disks = []
    for raid_id in pool_data.get('raids', []):
        if raid_id.split('_')[0] == 'cache':
            cache_disks.extend(info['raids'].get(raid_id, {}).get('disks', []))
    zcache = local_cache(pool)

    if not cache_disks and not zcache:
        print(f"fixcachelocality: pool {pool} has no cache vdev, nothing to do")
        return

    remote_cache_disks = [d for d in cache_disks if notlocal(d, info, myhost, zcache)]
    # a cache vdev zpool here reports as not ONLINE that getall does not list (stale record) is not local either
    for name, state, _ in zcache:
        if state != 'ONLINE' and not any(samedisk(name, d) for d in cache_disks):
            remote_cache_disks.append(name)
    if not remote_cache_disks:
        print(f"fixcachelocality: pool {pool}'s cache is already local to {myhost}")
        return

    print(f"fixcachelocality: pool {pool}'s cache disk(s) {remote_cache_disks} are not local to {myhost}, relocating")

    local_spare, kind = pick_cache(info, myhost, set(cache_disks) | set(remote_cache_disks))
    if local_spare and not resolve_by_id(local_spare):
        print(f"fixcachelocality: candidate {local_spare} is not visible in /dev/disk/by-id here, skipped")
        local_spare = None

    for d in remote_cache_disks:
        resolved = resolve_by_id(d) if len(diskwwn(d)) > 8 else None
        guid = next((g for name, _, g in zcache if samedisk(name, d) and g), None)
        if resolved:
            print(f"fixcachelocality: removing remote cache disk {resolved} from {pool}")
            res = subprocess.run(['/sbin/zpool', 'remove', pool, resolved])
            if res.returncode == 0 or not guid:
                continue
        if guid:
            print(f"fixcachelocality: removing remote cache disk {d} from {pool} by guid {guid}")
            subprocess.run(['/sbin/zpool', 'remove', pool, guid])
        else:
            print(f"fixcachelocality: could not resolve {d} locally to remove (expected - it lives on another host)")

    still_local = [d for d in cache_disks if d not in remote_cache_disks]
    if still_local:
        print(f"fixcachelocality: pool {pool} keeps its local cache {still_local}")
        return
    if local_spare:
        resolved = resolve_by_id(local_spare)
        print(f"fixcachelocality: adding local disk {resolved} ({kind}) as new cache for {pool}")
        subprocess.run(['/sbin/zpool', 'add', '-f', pool, 'cache', resolved])
    else:
        print(f"fixcachelocality: no disk on {myhost} is smaller than the rest, pool {pool} now has no cache")


if __name__ == '__main__':
    main()
