# handoff-update

A skill for AI coding agents that maintain a short, current project handoff.

Give the next session the goal, current state, and first action within one minute. Keep evidence, human notes, and concurrent work intact.

## Use

Install this repository with your agent's skill installer, or copy the repository folder into its configured skills directory. The entry point is [SKILL.md](SKILL.md).

Ask your agent:

- “Update this project's handoff from the work we completed.”
- “Audit the handoff against current local sources.”
- “Refresh only the stream I own. Preserve the other sections.”

The skill follows the established project location. Without one, it uses `docs/handoff.md` for a repository or `handoff-<topic>.md` for a non-repository folder. Local schemas and stricter limits take precedence. Ordinary file edits do not trigger handoff work.

## Included

- [Skill instructions](SKILL.md): source checks, scope, concise resume state, and preservation rules.
- [New-handoff outline](references/handoff.md): a small template adapted to the local schema.
- [Concurrent streams](references/streams.md): ownership, fences, caps, and archive review.
- [Structure checker](references/audit_streams.py): a read-only Python tool.
- [Optional integration](references/integration.md): host integration guidance. No hooks are installed.

## Check a handoff

Python 3 is required. The checker uses only the standard library.

Run from this repository:

```sh
python3 references/audit_streams.py /path/to/handoff.md
```

Use a stricter local limit when needed:

```sh
python3 references/audit_streams.py /path/to/handoff.md --total-cap 99
```

Exit codes:

- `0`: structure and size checks passed.
- `1`: the file could not be read.
- `2`: review or repair is required.

Stream metadata supports flat scalar values in inline or block rows. Nested and multiline YAML forms are rejected. The checker validates structure and size. It cannot prove that facts are current, links resolve, ownership is correct, or open work has been preserved elsewhere. A `CLOSED` stream requires review before archival.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

The 28 tests cover valid metadata, missing or duplicate fences, nested streams, invalid archives, local limits, and CLOSED review behavior. Tests use disposable files.

## Scope

This package contains the portable skill, references, checker, and tests. Project handoffs, private audit records, personal configuration, and host-specific loader code are not included. The skill does not infer approval to send, deploy, publish, or delete.
