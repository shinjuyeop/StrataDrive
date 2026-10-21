#!/usr/bin/env python3
"""Offline grouping of the preserved64 occurrences; never executes DDS.

Deduplicate the ordered pair of complete function call chains, ignoring addresses,
thread IDs and source-line shifts. Keep exact original frames/lines per occurrence.
A group is a stack shape, not an independently proven defect or a PASS decision.
"""
import collections
import hashlib
import json
from pathlib import Path
import re
import tarfile

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE.parent/'m5_dds_operating_profile/raw.tar.gz'


def family(pair):
    first, second = pair
    if 'gc_buckets_cb' in first: return 'GC-BUCKET'
    if 'whc_default_free' in first: return 'GC-WHC'
    if 'ddsi_free_wr_prd_match' in first: return 'GC-MATCH'
    if 'ddsrt_mutex_destroy' in first: return 'GC-MUTEX'
    if 'gc_delete_writer' in first: return 'GC-WRITER'
    if 'ddsi_unref_participant' in first: return 'GC-PARTICIPANT'
    if 'ddsi_writer_clear_retransmitting' in first: return 'SHARED-BITFIELD'
    if 'ddsrt_chh_resize' in second: return 'PUB-BUCKET'
    if 'entity_guid_eq' in first: return 'PUB-GUID'
    if 'dds_tk_equals' in first: return 'PUB-TKMAP'
    if 'ddsi_lease_renew' in first: return 'PUB-LEASE'
    if 'ddsrt_mutex_lock' in first: return 'PUB-MUTEX'
    if first[0] in ('handle_Heartbeat', 'handle_Data', 'handle_regular'): return 'PUB-PROXY'
    raise AssertionError(pair)


def main():
    groups = {}
    occurrences = []
    with tarfile.open(ARCHIVE) as archive:
        members = sorted((m for m in archive if m.isfile() and m.name.endswith('.stderr')
                          and (m.name.startswith('cohort-v1/tsan-') or
                               m.name.startswith('readiness-v2/tsan-'))), key=lambda m:m.name)
        for member in members:
            raw = archive.extractfile(member).read()
            text = raw.decode()
            matches = list(re.finditer(r'WARNING: ThreadSanitizer:.*?SUMMARY: ThreadSanitizer:[^\n]*', text, re.S))
            assert len(matches) == text.count('WARNING: ThreadSanitizer:')
            for match in matches:
                block = match.group()
                paragraphs = [p for p in re.split(r'\n\s*\n', block) if re.search(r'^    #0 ', p, re.M)][:2]
                pair = tuple(tuple(re.findall(r'^    #\d+ (.*?) (?:/|\.\./)', p, re.M)) for p in paragraphs)
                assert len(pair) == 2 and all(pair)
                if pair not in groups:
                    fam = family(pair)
                    groups[pair] = dict(id=f'G{len(groups)+1:02d}', family=fam,
                        classification=('instrumentation-visibility-gap' if fam in ('PUB-BUCKET','PUB-GUID')
                                        else 'unresolved-sdk-actual-use'),
                        verdict='FAIL retained; no suppression or exoneration',
                        function_stacks=pair, occurrences=[])
                group = groups[pair]
                row = dict(id=f'W{len(occurrences)+1:02d}', group=group['id'], family=group['family'],
                           classification=group['classification'], archive_member=member.name,
                           line=text[:match.start()].count('\n')+1,
                           end_line=text[:match.end()].count('\n')+1,
                           log_sha256=hashlib.sha256(raw).hexdigest(),
                           report_sha256=hashlib.sha256(block.encode()).hexdigest(),
                           conflicting_stacks=paragraphs, summary=block.splitlines()[-1])
                occurrences.append(row)
                group['occurrences'].append(row['id'])
    assert len(occurrences) == 64
    assert len(groups) == 32
    assert collections.Counter(r['archive_member'].split('/')[0] for r in occurrences) == {'cohort-v1':58,'readiness-v2':6}
    summary = dict(archive=str(ARCHIVE.relative_to(HERE.parent)),
                   archive_sha256=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
                   occurrence_count=len(occurrences), function_stack_pairs=len(groups),
                   families=dict(collections.Counter(r['family'] for r in occurrences)),
                   classifications=dict(collections.Counter(r['classification'] for r in occurrences)),
                   application_defect_found=0, diagnostic_only_defect_found=0,
                   warning_acceptance='FAIL: all64 retained; classification is not waiver',
                   groups=list(groups.values()), occurrences=occurrences)
    (HERE/'warnings.json').write_text(json.dumps(summary, indent=2)+'\n')
    lines = ['# Duplicate stack index', '', 'Generated offline from the original archive. Each row links to the complete',
             'pair and every occurrence in [warnings.json](warnings.json); the original',
             'member and1-based line are retained there. Group count is not defect count.', '',
             '| Group | Occurrences | Family | First raw location |', '| --- | ---: | --- | --- |']
    by_id = {r['id']:r for r in occurrences}
    for group in groups.values():
        r = by_id[group['occurrences'][0]]
        lines.append(f"| {group['id']} | {len(group['occurrences'])} | {group['family']} | `{r['archive_member']}:{r['line']}` |")
    (HERE/'warning-index.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:summary[k] for k in ('occurrence_count','function_stack_pairs','families','classifications')}, indent=2))


if __name__ == '__main__':
    main()
