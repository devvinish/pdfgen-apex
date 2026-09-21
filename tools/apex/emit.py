"""Low-level writer for Oracle APEX application export files (26.1 format).

Only produces syntax the reference 26.1 export uses: API calls with named
parameters, wwv_flow_string.join for multi-line text, named plug-in
attributes and wwv_flow_imp.g_varchar2_table chunks for large scripts.
"""
import re

LF_JOIN = "'||wwv_flow.LF||\n'"


class Raw(str):
    """A PL/SQL expression emitted as-is (ids, booleans, function calls)."""


def lit(s, width=250):
    """Single-quoted literal; long strings continue on new lines with ||."""
    s = '' if s is None else str(s)
    if not s:
        return "''"
    parts = [s[i:i + width] for i in range(0, len(s), width)]
    return '\n||'.join("'" + p.replace("'", "''") + "'" for p in parts)


def join_lines(text, indent=''):
    lines = text.split('\n')
    return Raw('wwv_flow_string.join(wwv_flow_t_varchar2(\n' +
               ',\n'.join(indent + lit(l) for l in lines) + '))')


def fmt(v, indent=''):
    if isinstance(v, Raw):
        return str(v)
    if v is True:
        return 'true'
    if v is False:
        return 'false'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        s = repr(v)
        return s[1:] if s.startswith('0.') else s
    if isinstance(v, str):
        if '\n' in v:
            return str(join_lines(v, indent))
        return lit(v)
    raise TypeError('cannot format %r' % (v,))


def call(api, params):
    """api(p=>v,...) in the export layout. params: iterable of (name, value); None skipped."""
    out = [api + '(']
    first = True
    for k, v in params:
        if v is None:
            continue
        out.append((' ' if first else ',') + k + '=>' + fmt(v))
        first = False
    out.append(');')
    return '\n'.join(out)


def attrs(d):
    """Named plug-in attributes: wwv_flow_t_plugin_attributes(...).to_clob"""
    items = []
    for k, v in d.items():
        if v is None:
            continue
        items.append("  '%s', %s" % (k, fmt(v, '    ')))
    return Raw('wwv_flow_t_plugin_attributes(wwv_flow_t_varchar2(\n' + ',\n'.join(items) + ')).to_clob')


def static_id(name, used):
    """lower-case-hyphenated identifier, unique within `used` (a set)."""
    base = re.sub(r'[^a-z0-9]+', '-', (name or 'x').lower()).strip('-')[:60] or 'x'
    sid, n = base, 1
    while sid in used:
        n += 1
        sid = '%s-%d' % (base, n)
    used.add(sid)
    return sid


def varchar2_table(text, chunk=200):
    """Statements filling wwv_flow_imp.g_varchar2_table with `text`."""
    out = ['wwv_flow_imp.g_varchar2_table := wwv_flow_imp.empty_varchar2_table;']
    pieces = [text[i:i + chunk] for i in range(0, len(text), chunk)] or ['']
    for n, piece in enumerate(pieces, 1):
        segs = piece.split('\n')
        expr = LF_JOIN.join(s.replace("'", "''") for s in segs)
        out.append("wwv_flow_imp.g_varchar2_table(%d) := '%s';" % (n, expr))
    return '\n'.join(out)


def hex_table(data, chunk=200):
    """Statements filling wwv_flow_imp.g_varchar2_table with the hex dump of `data` (bytes),
    as exports do for application static files (read back by varchar2_to_blob)."""
    out = ['wwv_flow_imp.g_varchar2_table := wwv_flow_imp.empty_varchar2_table;']
    for n, i in enumerate(range(0, len(data), chunk), 1):
        out.append("wwv_flow_imp.g_varchar2_table(%d) := '%s';" % (n, data[i:i + chunk].hex().upper()))
    return '\n'.join(out)


class Ids:
    """Component ids, emitted through wwv_flow_imp.id() like an export."""

    def __init__(self, start=81000000000000000):
        self.n = start

    def new(self):
        self.n += 1
        return self.n


def wid(n):
    return Raw('wwv_flow_imp.id(%d)' % n)


class Export:
    def __init__(self):
        self.parts = []

    def prompt(self, path):
        self.parts.append('prompt --application/' + path)

    def raw(self, text):
        self.parts.append(text)

    def block(self, *statements):
        body = '\n'.join(s for s in statements if s)
        self.parts.append('begin\n' + (body if body else 'null;') + '\nend;\n/')

    def text(self):
        return '\n'.join(self.parts) + '\n'
