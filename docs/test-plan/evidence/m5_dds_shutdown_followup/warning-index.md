# Duplicate stack index

Generated offline from the original archive. Each row links to the complete
pair and every occurrence in [warnings.json](warnings.json); the original
member and1-based line are retained there. Group count is not defect count.

| Group | Occurrences | Family | First raw location |
| --- | ---: | --- | --- |
| G01 | 2 | GC-BUCKET | `cohort-v1/tsan-callback-delete/central-42.stderr:2` |
| G02 | 3 | GC-BUCKET | `cohort-v1/tsan-callback-delete/zone-42.stderr:2` |
| G03 | 5 | GC-WHC | `cohort-v1/tsan-callback-delete/zone-42.stderr:63` |
| G04 | 14 | GC-WRITER | `cohort-v1/tsan-callback-delete/zone-42.stderr:115` |
| G05 | 1 | GC-PARTICIPANT | `cohort-v1/tsan-close-saturated/central-42.stderr:2` |
| G06 | 2 | PUB-BUCKET | `cohort-v1/tsan-close-saturated/zone-42.stderr:2` |
| G07 | 2 | GC-BUCKET | `cohort-v1/tsan-close-saturated/zone-42.stderr:95` |
| G08 | 1 | SHARED-BITFIELD | `cohort-v1/tsan-close-saturated/zone-42.stderr:146` |
| G09 | 1 | PUB-TKMAP | `cohort-v1/tsan-coordinated-restart/central-42.stderr:2` |
| G10 | 1 | PUB-TKMAP | `cohort-v1/tsan-coordinated-restart/central-42.stderr:78` |
| G11 | 3 | GC-BUCKET | `cohort-v1/tsan-coordinated-restart/zone-43.stderr:2` |
| G12 | 1 | PUB-GUID | `cohort-v1/tsan-normal/central-42.stderr:2` |
| G13 | 1 | PUB-GUID | `cohort-v1/tsan-normal/central-42.stderr:55` |
| G14 | 1 | GC-BUCKET | `cohort-v1/tsan-overflow/zone-42.stderr:95` |
| G15 | 1 | PUB-TKMAP | `cohort-v1/tsan-overflow/zone-42.stderr:155` |
| G16 | 1 | PUB-TKMAP | `cohort-v1/tsan-overflow/zone-42.stderr:226` |
| G17 | 1 | PUB-TKMAP | `cohort-v1/tsan-overflow/zone-42.stderr:301` |
| G18 | 1 | PUB-BUCKET | `cohort-v1/tsan-partial/zone-42.stderr:2` |
| G19 | 6 | GC-MATCH | `cohort-v1/tsan-partial/zone-42.stderr:94` |
| G20 | 3 | GC-MUTEX | `cohort-v1/tsan-partial/zone-42.stderr:287` |
| G21 | 1 | PUB-BUCKET | `cohort-v1/tsan-peer-stop/central-42.stderr:2` |
| G22 | 2 | GC-BUCKET | `cohort-v1/tsan-peer-stop/zone-42.stderr:2` |
| G23 | 1 | PUB-GUID | `cohort-v1/tsan-restart/zone-42.stderr:2` |
| G24 | 1 | PUB-PROXY | `cohort-v1/tsan-restart/zone-42.stderr:82` |
| G25 | 1 | PUB-LEASE | `cohort-v1/tsan-restart/zone-42.stderr:166` |
| G26 | 1 | PUB-MUTEX | `cohort-v1/tsan-restart/zone-42.stderr:236` |
| G27 | 1 | PUB-BUCKET | `cohort-v1/tsan-restart/zone-43.stderr:2` |
| G28 | 1 | PUB-GUID | `readiness-v2/tsan-D-ready/zone-42.stderr:2` |
| G29 | 1 | PUB-PROXY | `readiness-v2/tsan-D-ready/zone-42.stderr:83` |
| G30 | 1 | PUB-LEASE | `readiness-v2/tsan-D-ready/zone-42.stderr:167` |
| G31 | 1 | PUB-PROXY | `readiness-v2/tsan-D-ready/zone-42.stderr:238` |
| G32 | 1 | PUB-MUTEX | `readiness-v2/tsan-D-ready/zone-42.stderr:309` |
