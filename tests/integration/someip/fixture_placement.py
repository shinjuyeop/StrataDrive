"""Resolve test IO placement using physical cores, before native startup."""
from pathlib import Path

BUSY_CPUS = frozenset((1, 2, 3, 4, 5, 6, 7))  # owners, plant, SDK


def read_topology(cpus, root=Path('/sys/devices/system/cpu')):
    topology = {}
    for cpu in sorted(cpus):
        path = root / f'cpu{cpu}' / 'topology'
        topology[str(cpu)] = {
            'package': int((path / 'physical_package_id').read_text()),
            'core': int((path / 'core_id').read_text()),
            'siblings': (path / 'thread_siblings_list').read_text().strip(),
        }
    return topology


def auxiliary_placement(allowed, topology, separate):
    def core(cpu):
        entry = topology[str(cpu)]
        return entry['package'], entry['core']
    if not BUSY_CPUS.issubset(allowed):
        raise ValueError('owner/SDK/plant CPU placement unavailable')
    busy = {core(cpu) for cpu in BUSY_CPUS}
    if separate:
        candidates = [cpu for cpu in allowed if core(cpu) not in busy]
        if not candidates:
            raise ValueError('no auxiliary physical core separate from owners/SDK/plant')
        cpu = max(candidates)
    else:
        if 15 not in allowed:
            raise ValueError('legacy auxiliary CPU15 unavailable')
        cpu = 15
    return {'cpu': cpu, 'separate_requested': separate,
            'separate_observed': core(cpu) not in busy, 'topology': topology}
