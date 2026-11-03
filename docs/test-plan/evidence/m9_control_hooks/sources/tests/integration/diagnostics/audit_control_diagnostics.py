#!/usr/bin/env python3
"""Independent v1 journal/CSV/owner-event/physical audit of the M9 logical fixture."""
import argparse
import copy
import csv
import json
import math
from pathlib import Path
import shutil
import struct
import tempfile
import zlib


def require(ok, message):
    if not ok:
        raise ValueError(message)


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def uint(self, width):
        require(self.pos + width <= len(self.data), 'truncated event')
        value = int.from_bytes(self.data[self.pos:self.pos+width], 'little')
        self.pos += width
        return value

    def boolean(self):
        value = self.uint(1)
        require(value in (0, 1), 'invalid boolean')
        return bool(value)

    def identity(self):
        return tuple(self.uint(8) for _ in range(3))

    def stamp(self):
        return dict(domain=self.uint(1), instance=self.uint(8), ns=self.uint(8),
                    present=self.boolean(), trusted=self.boolean())

    def source(self):
        return dict(present=self.boolean(), producer=self.uint(8), sequence=self.uint(8),
                    epoch=self.uint(4), source=self.stamp(), expiry=self.stamp())

    def real(self):
        require(self.pos + 8 <= len(self.data), 'truncated binary64')
        value = struct.unpack_from('<d', self.data, self.pos)[0]
        self.pos += 8
        require(math.isfinite(value), 'nonfinite event')
        return value


def event(payload):
    r = Reader(payload)
    require(r.uint(1) == 0 and r.uint(2) == 1, 'not a v1 event transaction')
    identity, related, proof = r.identity(), r.identity(), r.identity()
    run, epoch = r.uint(8), r.uint(4)
    code, component, monitor, subject = r.uint(2), r.uint(4), r.uint(4), r.uint(4)
    occurrence = (r.uint(8), r.uint(8), r.uint(4), r.uint(4), r.uint(8))
    kind, latch, qualification = r.uint(1), r.uint(1), r.uint(1)
    native, severity, model, before, after = (r.uint(4) for _ in range(5))
    profile, requirements, interfaces = (r.uint(8) for _ in range(3))
    enable = r.stamp()
    source, command, lease = r.source(), r.source(), r.source()
    times = [r.stamp() for _ in range(8)]
    expected, roles = r.uint(4), r.uint(4)
    unknown, unmapped = r.boolean(), r.boolean()
    measured, low, high = r.real(), r.real(), r.real()
    require(r.pos == len(payload), 'event trailing bytes')
    return dict(event_sequence=identity[2], kind=kind, code=code, component=component, monitor=monitor,
                subject=subject, native_reason=native, epoch=epoch, occurrence_sequence=occurrence[4],
                related_sequence=related[2], detected_ns=times[2]['ns'], selected_ns=times[3]['ns'],
                actual_source_ns=times[5]['ns'], observed_ns=times[6]['ns'], source_ns=source['source']['ns'],
                command_source_ns=command['source']['ns'], command_expiry_ns=command['expiry']['ns'],
                measured=measured, acknowledged_ns=times[4]['ns'], source_producer=source['producer'],
                source_sequence=source['sequence'], received_roles=roles,
                _run=run, _id=identity, _occurrence=occurrence, _enable=enable, _profile=profile,
                _times=times, _source=source, _unmapped=unmapped, _after=after)


def checksum(data, magic):
    require(len(data) >= 12 and data[:8] == magic, 'journal magic/size')
    require(int.from_bytes(data[-4:], 'little') == zlib.crc32(data[:-4]), 'journal checksum')


def journal(directory):
    manifest, commit, data = ((directory/name).read_bytes() for name in ('manifest', 'commit', 'journal'))
    require(len(manifest) == 40 and len(commit) == 28 and len(data) <= 64*1024*1024, 'store size')
    checksum(manifest, b'SDDMAN\x01\x00')
    checksum(commit, b'SDDCMT\x01\x00')
    count, end = struct.unpack_from('<QQ', commit, 8)
    require(end == len(data) and not (directory/'incomplete').exists(), 'incomplete store')
    rows, cursor = [], 0
    for sequence in range(1, count+1):
        require(cursor+24 <= end, 'truncated frame')
        number, length = struct.unpack_from('<QI', data, cursor+8)
        require(number == sequence and length <= 256*1024 and cursor+length+24 <= end, 'frame sequence/length')
        frame = data[cursor:cursor+length+24]
        checksum(frame, b'SDDEVT\x01\x00')
        rows.append(event(frame[20:-4]))
        cursor += length+24
    require(cursor == end, 'commit position')
    return rows


def csv_rows(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def load(directory):
    summary = json.loads((directory/'diagnostics.json').read_text())
    rows, exported = journal(directory/'store'), csv_rows(directory/'diagnostics.csv')
    require(len(rows) == len(exported) == summary['diagnostic_events'], 'event denominator')
    for raw, text in zip(rows, exported):
        for key, value in text.items():
            decoded = float(value) if key == 'measured' else int(value)
            require(raw[key] == decoded, 'journal/CSV mismatch: '+key)
    loss = bool(summary['dtc_records'])
    prefix = 'logical-speed-input-loss' if loss else 'logical-normal'
    runtime = json.loads((directory/(prefix+'.json')).read_text())
    physical = csv_rows(directory/'physical.csv')
    control = csv_rows(directory/'control.csv')
    owners = csv_rows(directory/(prefix+'-events.csv'))
    return dict(summary=summary, events=rows, runtime=runtime, physical=physical, control=control, owners=owners, loss=loss)


def judge(data):
    s, rows, runtime = data['summary'], data['events'], data['runtime']
    require(s['complete'] and s['monitor_hooks_complete'] and runtime['passed'], 'runtime/recording failed')
    require(all(r['_run'] == s['run'] and r['_id'][:2] == (s['run'], 7) and r['epoch'] == 1 and
                r['_enable']['domain'] == 1 and r['_enable']['instance'] == s['clock_instance'] and
                r['_profile'] == 1 and not r['_unmapped'] for r in rows), 'identity/domain/profile')
    physical = data['physical']
    require(len(physical) == s['physical_samples'] and len(data['control']) == s['controller_samples'], 'physical/control denominator')
    require(all(int(p['model_epoch']) == 7 and abs(float(p['balance_j'])) <= 1e-5 for p in physical), 'physical model/energy')
    faults = [r for r in rows if r['kind'] == 1]
    if not data['loss']:
        require(not faults and s['dtc_records'] == 0 and len(data['control']) == 4350, 'normal false DTC/coverage')
        require({2, 3, 4, 5}.issubset({r['_after'] for r in rows if r['component'] == 2}), 'normal stop phases')
        require(any(r['kind'] == 4 and r['source_producer'] == 6 and r['measured'] <= 30 for r in rows), 'actual HV-off')
        return dict(pass_=True, faults=0, events=len(rows), controller_samples=len(data['control']))
    require(len(faults) == s['dtc_records'] == 1, 'fault count')
    fault = faults[0]
    require((fault['code'], fault['component'], fault['monitor'], fault['subject'], fault['native_reason']) == (0x1001, 1, 1, 1, 768), 'fault classification')
    detected = fault['detected_ns']
    require(detected == 1_000_000_000+runtime['first_fault_ns'] and 11_000_000_000 <= detected < 11_020_000_000, 'original detection')
    selections = [r for r in rows if r['kind'] == 2]
    require(len(selections) == 5 and {r['received_roles'] for r in selections} == {4, 8, 16, 32, 64}, 'local role selections')
    actors = {2: 9, 3: 5, 4: 4, 5: 10, 6: 6}
    for r in selections:
        owner = r['received_roles'].bit_length()-1
        require(r['source_producer'] == actors[owner] and r['selected_ns'] == r['source_ns'], 'local actor/time')
        require(any(e['kind'] == 'leaf-protection-selected' and int(e['owner']) == owner and int(e['epoch']) == 1 and
                    int(e['time_ns']) == r['selected_ns'] for e in data['owners']), 'selection not in original owner log')
        require(detected <= r['selected_ns'] <= 1_000_000_000+runtime['all_protected_ns'], 'local selection order')
    ack = [r for r in rows if r['kind'] == 3 and r['source_producer'] == 3]
    require(len(ack) == 1 and ack[0]['acknowledged_ns'] >= 1_000_000_000+runtime['all_protected_ns'] and ack[0]['selected_ns'] == 0, 'ACK confused with selection')
    actual = [r for r in rows if r['kind'] == 4]
    require(len(actual) == 3 and {r['source_producer'] for r in actual} == {4, 5, 11}, 'actual sources')
    for r in selections+ack+actual:
        require(r['related_sequence'] == fault['event_sequence'] and r['occurrence_sequence'] == fault['occurrence_sequence'], 'causal link')
    for r in actual:
        require(detected <= r['actual_source_ns'] == r['source_ns'] <= 1_000_000_000+runtime['all_protected_ns']+230_000_000, 'actual acquisition budget')
        if r['source_producer'] == 4:
            require(abs(r['measured']) <= 1, 'actual torque')
        if r['source_producer'] == 5:
            require(r['measured'] >= 1_000_000, 'actual pressure')
    after = [p for p in physical if int(p['source_ns']) >= 1_000_000_000+runtime['all_protected_ns']+230_000_000]
    require(after and all(abs(float(p['torque_nm'])) <= 1 and float(p['pressure_pa']) >= 1_000_000 and int(p['run_gate']) == 0 for p in after), 'physical response/latch')
    return dict(pass_=True, faults=1, events=len(rows), detection_ms=(detected-11_000_000_000)/1e6,
                selection_ms=(max(r['selected_ns'] for r in selections)-detected)/1e6,
                central_ack_ms=(ack[0]['acknowledged_ns']-detected)/1e6,
                actual_ms=(max(r['actual_source_ns'] for r in actual)-detected)/1e6)


def mutations(original):
    changes = {
        'missing-local-owner': lambda d: d['events'].remove(next(r for r in d['events'] if r['kind'] == 2)),
        'ack-as-selection': lambda d: next(r for r in d['events'] if r['kind'] == 3 and r['source_producer'] == 3).update(kind=2),
        'wrong-code': lambda d: next(r for r in d['events'] if r['kind'] == 1).update(code=0),
        'retimestamped-fault': lambda d: next(r for r in d['events'] if r['kind'] == 1).update(detected_ns=12_000_000_000),
        'bad-actual-torque': lambda d: next(r for r in d['events'] if r['kind'] == 4 and r['source_producer'] == 4).update(measured=5),
        'stale-actual': lambda d: next(r for r in d['events'] if r['kind'] == 4).update(actual_source_ns=1),
        'wrong-epoch': lambda d: next(r for r in d['events'] if r['kind'] == 1).update(epoch=0),
    }
    results = {}
    for name, mutate in changes.items():
        data = copy.deepcopy(original)
        mutate(data)
        try:
            judge(data)
        except ValueError as error:
            results[name] = dict(rejected=True, reason=str(error))
        else:
            results[name] = dict(rejected=False)
    require(all(r['rejected'] for r in results.values()), 'mutation accepted')
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    parser.add_argument('--mutations', action='store_true')
    args = parser.parse_args()
    try:
        data = load(args.directory)
        result = judge(data)
        if args.mutations:
            result['mutations'] = mutations(data)
            with tempfile.TemporaryDirectory(prefix='stratadrive-diag-audit-') as temp:
                damaged = Path(temp)/'store'
                shutil.copytree(args.directory/'store', damaged)
                payload = bytearray((damaged/'journal').read_bytes())
                payload[-1] ^= 1
                (damaged/'journal').write_bytes(payload)
                try:
                    journal(damaged)
                except ValueError:
                    result['mutations']['journal-corruption'] = dict(rejected=True)
                else:
                    raise ValueError('corrupt journal accepted')
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, KeyError, OSError, struct.error) as error:
        print(json.dumps(dict(pass_=False, error=str(error)), indent=2))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
