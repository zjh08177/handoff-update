#!/usr/bin/env python3
"""Read-only handoff structure check. Exit 0: valid; 2: review/fix; 1: read error.

Accepts scalar inline or block stream rows. Other YAML forms fail explicitly.
CLOSED requests human/agent review; this tool never decides whether work is filed.
"""
import argparse
from datetime import date
import pathlib
import re
import sys

CLOSED = re.compile(r'^CLOSED\b', re.I)
FENCE = re.compile(r'^\s*<!--\s*(BEGIN|END)-STREAM-([A-Z0-9_-]+)\s*-->\s*$')
OPEN = re.compile(r'^\s*[-*]\s+\[ \]|\bTODO\b|\bOPEN\s*:|\bunresolved\b', re.I | re.M)


def split_fields(value):
    """Split a flat map without mistaking a comma inside quotes for a field."""
    parts, start, quote, escaped = [], 0, None, False
    for i, char in enumerate(value):
        if escaped:
            escaped = False
        elif quote == '"' and char == '\\':
            escaped = True
        elif quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == ',':
            parts.append(value[start:i].strip())
            start = i + 1
    if quote:
        raise ValueError('unclosed quote in stream metadata')
    parts.append(value[start:].strip())
    return parts


def scalar(value):
    value = value.strip()
    if value.startswith(('"', "'")):
        quote = value[0]
        if len(value) < 2 or value[-1] != quote:
            raise ValueError('unsupported quoted stream value')
        return value[1:-1]
    value = re.split(r'\s+#', value, maxsplit=1)[0].strip()
    if not value or value[0] in '{[&*!>|' or value in ('~', 'null'):
        raise ValueError('stream fields need scalar values; nested/multiline YAML is unsupported')
    return value


def fields(items):
    result = {}
    for item in items:
        match = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)', item.strip())
        if not match or match[1] in result:
            raise ValueError('invalid or duplicate stream field: ' + item)
        result[match[1]] = scalar(match[2])
    return result


def parse_streams(text):
    lines = text.splitlines()
    if not lines or lines[0] != '---':
        return None
    try:
        end = lines.index('---', 1)
    except ValueError:
        raise ValueError('unclosed frontmatter')
    fm = lines[1:end]
    starts = [i for i, line in enumerate(fm) if re.match(r'^streams\s*:', line)]
    if not starts:
        return None
    if len(starts) != 1 or not re.fullmatch(r'streams:\s*(?:#.*)?', fm[starts[0]]):
        raise ValueError('streams must be one block map')
    rows, name, row_indent = {}, None, None
    inline_rows, child_indents = set(), {}
    for line in fm[starts[0] + 1:]:
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if not line.startswith((' ', '\t')):
            break
        if '\t' in line[:len(line) - len(line.lstrip())]:
            raise ValueError('use spaces for stream indentation')
        indent = len(line) - len(line.lstrip())
        match = re.fullmatch(r'\s*([A-Za-z0-9_-]+):\s*(.*)', line)
        if not match:
            raise ValueError('invalid stream row: ' + line)
        if row_indent is None:
            row_indent = indent
        if indent == row_indent:
            name = match[1].lower()
            if name in rows:
                raise ValueError('duplicate stream metadata: ' + name)
            tail = match[2].strip()
            if not tail:
                rows[name] = {}
            elif tail.startswith('{') and tail.endswith('}'):
                rows[name] = fields(split_fields(tail[1:-1]))
                inline_rows.add(name)
            else:
                raise ValueError('stream row must be an inline or block map: ' + name)
        elif indent > row_indent and name:
            if name in inline_rows:
                raise ValueError('inline stream row cannot have block fields: ' + name)
            child_indents.setdefault(name, indent)
            if indent != child_indents[name]:
                raise ValueError('nested stream fields are unsupported: ' + name)
            row = fields([line.strip()])
            if set(row) & set(rows[name]):
                raise ValueError('duplicate field in stream: ' + name)
            rows[name].update(row)
        else:
            raise ValueError('invalid stream indentation')
    if not rows:
        raise ValueError('empty streams map')
    return rows


def audit(text, total_cap=None, stream_cap=150, base_cap=50):
    lines = text.splitlines()
    issues, messages = [], []
    try:
        streams = parse_streams(text)
    except ValueError as error:
        return [str(error)], []
    has_markers = any('BEGIN-STREAM-' in line or 'END-STREAM-' in line for line in lines)
    if streams is None:
        if has_markers:
            issues.append('stream fences require streams metadata')
        cap = total_cap if total_cap is not None else 150
        if len(lines) > cap:
            issues.append(f'single-stream size {len(lines)} exceeds {cap} lines')
        return issues, [f'single-stream: {len(lines)} lines; cap {cap}']

    bounds, stack, seen = {}, None, set()
    for index, line in enumerate(lines):
        if 'BEGIN-STREAM-' not in line and 'END-STREAM-' not in line:
            continue
        match = FENCE.fullmatch(line)
        if not match:
            issues.append(f'line {index + 1}: invalid stream fence')
            continue
        kind, token = match.groups()
        name = token.lower()
        if name not in streams:
            issues.append(f'line {index + 1}: fence has no metadata: {name}')
        if kind == 'BEGIN':
            if name in seen:
                issues.append(f'line {index + 1}: duplicate stream fence: {name}')
            seen.add(name)
            if stack:
                issues.append(f'line {index + 1}: nested stream fence')
            else:
                stack = (name, index)
        elif not stack or stack[0] != name:
            issues.append(f'line {index + 1}: unmatched END fence: {name}')
        else:
            bounds[name] = (stack[1], index)
            stack = None
    if stack:
        issues.append('missing END fence: ' + stack[0])

    active = 0
    covered = set()
    for name, meta in streams.items():
        archived = bool(meta.get('archived'))
        status = meta.get('status', '')
        if archived:
            try:
                date.fromisoformat(meta['archived'])
            except ValueError:
                issues.append('archived needs a YYYY-MM-DD retirement date: ' + name)
            if name == 'base':
                issues.append('the shared Base cannot be an archive pointer')
            if not CLOSED.match(status):
                issues.append('archived stream needs CLOSED status: ' + name)
            if not meta.get('archive'):
                issues.append('archived stream needs an archive destination: ' + name)
        if name != 'base' and not archived:
            active += 1
            if not status:
                issues.append('missing status: ' + name)
        if archived:
            if name in seen:
                issues.append('archived stream still has active fences: ' + name)
            messages.append(name + ': archive pointer; destination needs manual link check')
            continue
        if name not in bounds:
            issues.append('active stream has no complete fence pair: ' + name)
            continue
        begin, end = bounds[name]
        count = end - begin + 1
        if name != 'base':
            covered.update(range(begin, end + 1))
            if count > stream_cap:
                issues.append(f'{name}: {count} lines exceeds {stream_cap}')
        if CLOSED.match(status):
            hint = '; possible open work markers present' if OPEN.search('\n'.join(lines[begin:end + 1])) else ''
            issues.append(name + ': CLOSED; review all open items and preservation before archive' + hint)
        messages.append(f'{name}: {count} lines; {status or "shared orientation"}')
    base_count = len(lines) - len(covered)
    if base_count > base_cap:
        issues.append(f'Base/router: {base_count} lines exceeds {base_cap}')
    cap = total_cap if total_cap is not None else base_cap + stream_cap * active
    if len(lines) > cap:
        issues.append(f'total: {len(lines)} lines exceeds {cap}')
    messages.append(f'total {len(lines)}; Base/router {base_count}; active streams {active}; cap {cap}')
    return issues, messages


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('handoff', type=pathlib.Path)
    parser.add_argument('--total-cap', type=int)
    parser.add_argument('--stream-cap', type=int, default=150)
    parser.add_argument('--base-cap', type=int, default=50)
    args = parser.parse_args(argv)
    if any(value is not None and value < 1 for value in (args.total_cap, args.stream_cap, args.base_cap)):
        parser.error('caps must be positive')
    try:
        text = args.handoff.read_text(encoding='utf-8')
    except (OSError, UnicodeError) as error:
        print(f'audit_streams: {error}', file=sys.stderr)
        return 1
    issues, messages = audit(text, args.total_cap, args.stream_cap, args.base_cap)
    for message in messages:
        print(message)
    for issue in issues:
        print('REVIEW: ' + issue)
    if not issues:
        print('Structure passed. Source facts and ownership were not verified.')
    return 2 if issues else 0


if __name__ == '__main__':
    sys.exit(main())
