# Eligibility Reconciliation
Authoritative DB total: 29252 file IDs
Strict eligible (is_supported from ingestion/client.py): 5539
Excluded (images/video/audio/font/design/executable): 19848
Gap from stated 5,875: 5875 - 5539 = 336
Explanation: 5,875 likely includes broader categories (forms, presentations, additional text types, some image-based documents). Authoritative V1 eligibility = 5,539 using exact ingested-supported rule.
File: data/audit/eligible_authoritative_ids.json contains the precise 5,539 IDs.
