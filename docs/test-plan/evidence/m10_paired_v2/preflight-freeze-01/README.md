# Superseded before any live attempt

This immutable source archive passed37 focused tests but was not used to launch
a paired live case. Inspection of the retained owner V2 binding found Unreal's
uppercase, hyphenated UUID format. The proposed joiner compared it to lowercase
hexadecimal text and would have rejected the same identity.

The current parent freeze parses UUID values and includes the regression for the
actual upstream format. It passes38 focused tests and451 workspace tests. This
preflight revision remains retained; there was no result-based selection or
discarded live measurement between these two freezes.
