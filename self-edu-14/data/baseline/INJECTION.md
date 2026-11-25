# baseline-v2: сховище ЛР 11 + синтетичні дефекти

Згенеровано `scripts/inject_defects.py` (seed 42) з `data/lab11`. Імітує другий потік даних (feed-b-import, legacy-roster, codeshare-feed) і дзеркала статей.

Усього дефектів: 123; за типами: {'duplicate': 58, 'value_conflict': 19, 'logical_conflict': 10, 'temporal_conflict': 3, 'terminology_conflict': 5, 'missing_value': 14, 'invalid_value': 5, 'missing_provenance': 1, 'stale': 6, 'inconsistent_metadata': 2}.
Пар-дублікатів сутностей: 52; двійників-приманок: 14; дзеркальних документів: 6.

Ground truth (для оцінювання): `quality/ground_truth/injected_defects.json`.
