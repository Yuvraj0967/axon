# Packaged Paderborn bearing classifier

This small deployment bundle is included in Git. The raw recordings and prepared
training windows remain local. `metadata.json` records the artifact SHA-256,
feature order, sample-rate contract, source hash, training library version and
the physical bearings in each partition. The loader verifies the checksum and
scikit-learn version before loading the artifact.

Input: 4,096 vibration samples at 64,000 Hz, transformed into 16 features.
Output: `healthy` or `other_bearing_damage`. It cannot localize an inner/outer
race, estimate remaining useful life, or establish accuracy on a new sensor.

The stored test report covers 2,981 windows from held-out bearings K003 and KI04:
95.30% accuracy, macro F1 0.9529, damaged-bearing recall 90.59%. There were 140
missed damaged windows. These are laboratory dataset results, not field results.
K001 and KA04 replay examples belonged to training and are integration checks.

Source: Paderborn University Bearing DataCenter,
https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download
Source dataset licence: CC-BY-NC-4.0. Retain attribution and the noncommercial
restriction for this dataset-derived demonstration bundle. No raw source data
is included here. The repository's software licence does not replace these terms.
