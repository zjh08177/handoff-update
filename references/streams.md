# Concurrent handoff streams

Treat either `streams:` metadata or `BEGIN-STREAM-` / `END-STREAM-` markers as stream mode. The documented project, cwd, branch, or role rule decides ownership. Ask only if ownership remains ambiguous. A shared Base change needs lead ownership or an authorized cross-stream update.

Run `python3 <skill-dir>/references/audit_streams.py <handoff>` before and after editing. The checker accepts inline scalar rows and block scalar rows under `streams:`. Unsupported metadata fails with a diagnostic. Use `--total-cap N`, `--stream-cap N`, or `--base-cap N` for stricter local limits. It checks structure and size; it cannot prove current facts, ownership, link validity, or that open work has another home.

Keep one matching pair of `<!-- BEGIN-STREAM-NAME -->` and `<!-- END-STREAM-NAME -->` per active metadata row. Fence tokens use uppercase; metadata keys match without case. `base` is reserved. Keep the router and all content outside non-Base stream fences within 50 lines. Each stream has at most 150 lines. The default total cap is `50 + 150 × active streams`; a local hard cap wins.

Patch only the owned body and metadata. Preserve other bodies byte-for-byte. Re-read immediately before saving; if another writer changed the file, apply the patch to that version. Verify preserved-body hashes after the edit. Keep the shared router aligned with the live sections. Do not stamp another stream as verified.

Only a status beginning with `CLOSED` opts into retirement. “Shipped” and “done” do not. The checker requests review; it does not authorize deletion or infer that work is filed. Inspect every unresolved item, unchecked task, and human note. Preserve each in a linked live record before retiring the section.

For an explicit CLOSED section, retain its complete original text in the established archive. Verify the saved text and destination before removing the active body. Replace its metadata with `status: CLOSED`, `archived: YYYY-MM-DD`, and `archive: <path>`; remove its live route. Follow local link-aware move rules. If preservation or authority is unresolved, keep the section and report the gap.

Report any remaining checker failure. Do not call a structurally valid handoff current without source checks.
