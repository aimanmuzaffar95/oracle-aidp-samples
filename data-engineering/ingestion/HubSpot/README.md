# HubSpot Connector Sample

`HubSpot.ipynb` ingests HubSpot CRM contacts, companies, deals and the associations between them into Delta tables with the [HubSpot CRM API](https://developers.hubspot.com/docs/api/crm/understanding-the-crm). It is Python in notebook cells on the Spark driver, not a built-in `aidataplatform` type. Set the placeholders in the Configuration cell and run the cells in order. The Configuration cell checks `CATALOG`, `SCHEMA`, `TABLE_PREFIX`, `MODE` and `OBJECTS` and stops with a clear message if one is invalid.

## Prerequisites

- A HubSpot service key or legacy private app token with the read scopes for contacts, companies and deals, stored as a **Secret Token** in the Credential Store.
- Outbound HTTPS access to `api.hubapi.com`. `requests` is already on the cluster, so there is no `requirements.txt`.
- An existing target catalog. Run one instance at a time.

## Behavior

- **Tables.** `contacts`, `companies`, `deals` and `associations` in `<CATALOG>.<SCHEMA>`, plus `hubspot_sync_state` with one row per object: watermark, last mode, last status and row count. A failed object gets `last_status = FAILED` and keeps its previous watermark. Each object table keeps typed columns and the full record in `raw_json`.
- **Incremental.** Searches for ids modified since the watermark minus 300 seconds, reads the records in batches, merges on `id`, then flags archived ids and ids merged into another record. The watermark is the run start and moves only after a successful write. An object with no watermark loads in full.
- **Full.** Reads every live and archived record and overwrites the table. Records are streamed into the staging table, not held in memory.
- **Associations.** Contacts to companies, deals to contacts and deals to companies. Always re-read in full from the synced tables, so run them after the objects. The table is overwritten only when every pair was read. If a source object is not in `OBJECTS` or its table cannot be read, the other pairs are merged and the old links of the skipped pair stay.
- **Limits handled.** Search stops at 10,000 results, so paging restarts after the last id. A `429` is retried with backoff. HubSpot usually sends no `Retry-After`, and the code honors it only when it is a number of seconds. A `207` error for a deleted record or an input with no links is skipped.

## Known limits

- HubSpot search is eventually consistent. An edit indexed after the overlap window is missed until the next full run.
- GDPR-erased contacts and records archived more than 90 days ago are never flagged by an incremental run. Only a full run clears them.
- When `OBJECTS` leaves out a source object, or a source table is unreadable, associations are merged instead of overwritten. Links deleted in HubSpot for the pairs that were refreshed are not removed until the next full run of all objects.
- The table schemas are fixed. After a schema change, drop the tables and run a full load.
- Requests run one at a time on the driver, and associations are re-read on every run, which is slow on large accounts.
- CRM data holds personal data. The tables inherit the catalog's access controls.

## Validation status

Run on an AIDP cluster with Spark 3.5.0 and Python 3.11 on 2026-10-01, against a small HubSpot test account, with the token read from the Credential Store. First load: contacts 14, companies 7, deals 45 (including archived) and associations 115. A second incremental run with no changes read 0 changed rows. Renaming a deal brought exactly that deal in as one row in the next incremental run, with no duplicate. Deleting a deal flagged it archived on the next incremental run and dropped its links, so associations went from 115 to 113. Two linked contacts also showed up as changed, because HubSpot updates the modified date of contacts linked to a deleted deal. A full refresh gave the same counts as the first load, and a rerun from the same notebook session moved the watermark to the new run start.

Not run on AIDP: merged contacts, the `429` retry against HubSpot's real rate limit, a scheduled job, accounts with many thousands of records, and a non-empty deal currency, which is `NULL` here because the account has no deal currency set. Keyset paging with the 10,000-result restart, `429` retry, `207` handling and the watermark window were also checked offline against small fakes.
