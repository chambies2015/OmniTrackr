"""Smaller scripts and stylesheets, made when they are served.

The files in app/static stay as they are written: readable, commented, and the
same on disk as in git. What a browser downloads is a copy with the comments and
the spare whitespace taken out, made the first time each file is asked for and
kept in memory, keyed by a hash of the file's contents so an edited file can
never get an old copy.

This is deliberately the cautious kind of minifying. Nothing is renamed or
rewritten; strings, template literals and regular expressions are copied byte
for byte. Scripts keep every line break, so a line number in an error report
from a phone is still the line number in the file. Stylesheets keep one space
wherever they had any, except next to `{`, `}` and `;`, so selectors, media
queries and calc() mean exactly what they did.

When anything in a file looks unusual (an unterminated string, a stray quote, a
bracket that doesn't close, whitespace characters outside ASCII), the file is
served as written. tests/test_minify_equivalence.cjs checks every script and
stylesheet in the repository with esbuild's parser: the minified copy must parse
to the same program, or the same rules. MINIFY_ASSETS=off turns it all off.
"""
from __future__ import annotations

import hashlib
import os
import re
import threading
from collections import OrderedDict

JS_TYPES = {"application/javascript", "text/javascript"}
CSS_TYPES = {"text/css"}

# Files that are left exactly as written. The service worker is compared byte for
# byte by browsers, and a changed copy would install a new worker on every phone.
SKIP_PATHS = frozenset({"/sw.js", "/static/sw.js", "/credentials.js"})

# Copies kept in memory. Every script and stylesheet the site serves comes to
# about 2 MB minified, so this holds a few deploys' worth.
CACHE_BYTES = 12 * 1024 * 1024


class MinifyError(ValueError):
    """The file has something the minifier doesn't expect; serve it as written."""


# Added to a file's ETag when the minified copy is sent (app/compression.py). A browser that
# rechecks its copy then only gets "not modified" while that same copy is still what the
# server sends: with MINIFY_ASSETS=off, or after this file changes, the old ETag no longer
# matches and the browser downloads the file again. Without it, switching minifying off
# left a broken minified copy in every browser that had one, because the file's own ETag
# (its size and date on disk) stays the same (Nov 24 2026 sweep).
def _own_version() -> str:
    try:
        with open(__file__, "rb") as source:
            return hashlib.blake2b(source.read(), digest_size=4).hexdigest()
    except OSError:  # pragma: no cover
        return "0"


ETAG_MARK = "-m" + _own_version()


def enabled() -> bool:
    return os.getenv("MINIFY_ASSETS", "on").strip().lower() not in {"0", "off", "false", "no"}


def version_tag() -> str:
    """Mixed into the dashboard bundles' ?v= versions (app/dashboard_assets.py).

    Browsers keep a versioned file for a year without asking again, so an ETag can't
    reach them. Turning minifying off, or a change to this file, gives the two bundles
    new URLs instead, and every browser fetches them again.
    """
    return ETAG_MARK if enabled() else ""


# --------------------------------------------------------------------- scripts

# Characters that make up identifiers, keywords and numbers. Backslash is here for
# \u escapes in identifiers and # for private names.
_WORD_CHARS = (r"A-Za-z0-9_$\\#\u0080-\u009f\u00a1-\u167f\u1681-\u1fff\u200b-\u2027\u202a-\u202e"
               r"\u2030-\u205e\u2060-\u2fff\u3001-\ufefe\uff00-\U0010ffff")
_WORD = re.compile(f"[{_WORD_CHARS}]")
# Whitespace and line breaks outside ASCII (no-break space, U+2028 and so on) are left
# out of _WORD_CHARS and every other pattern, so a file with one between tokens raises
# MinifyError and is served as written. Inside strings and comments they are fine.

_JS_TOKEN = re.compile(
    r"""
    (?P<space>[ \t\f\v]+)
  | (?P<newline>\r\n|[\n\r])
  | (?P<line_comment>//[^\n\r\u2028\u2029]*)
  | (?P<block_comment>/\*[\s\S]*?\*/)
  | (?P<word>[""" + _WORD_CHARS + r"""]+)
  | (?P<string>"(?:[^"\\\n\r]|\\(?:\r\n|[\s\S]))*"|'(?:[^'\\\n\r]|\\(?:\r\n|[\s\S]))*')
  | (?P<tick>`)
  | (?P<slash>/)
  | (?P<open>[(\[{])
  | (?P<close>[)\]}])
  | (?P<punct>>>>=|\.\.\.|===|!==|\*\*=|<<=|>>=|>>>|&&=|\|\|=|\?\?=|=>|==|!=|<=|>=|&&|\|\||\?\?|\?\.|\+\+|--|\+=|-=|\*=|%=|&=|\|=|\^=|<<|>>|\*\*|[-+*%<>=!&|^~?:;,.@])
    """,
    re.VERBOSE,
)
# The rest of a template literal's text, up to its closing backtick or the next ${.
_TEMPLATE_TEXT = re.compile(r"(?:[^`\\$]|\\[\s\S]|\$(?!\{))*")
_REGEX = re.compile(r"/(?:[^/\\\[\n\r]|\\[^\n\r]|\[(?:[^\]\\\n\r]|\\[^\n\r])*\])+/[A-Za-z]*")
_LINE_BREAKS = re.compile(r"\r\n|[\n\r\u2028\u2029]")

# After these words a slash starts a regular expression, not a division.
_REGEX_AFTER_WORDS = frozenset({
    "return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw",
    "case", "do", "else", "yield", "await",
})
# A ) that closes one of these conditions is followed by a statement, so a slash
# after it starts a regular expression: if (x) /y/.test(z).
_CONDITION_WORDS = frozenset({"if", "while", "for", "with"})
# Pairs that would join into a different token, or start a comment, without a space.
_KEEP_APART = frozenset({("+", "+"), ("-", "-"), ("<", "!"), ("-", ">"), ("/", "/"), ("/", "*"),
                         ("?", "."), (".", ".")})


def _needs_space(before: str, after: str, after_regex: bool = False) -> bool:
    if not before:
        return False
    a, b = before[-1], after[0]
    if _WORD.match(a) and _WORD.match(b):
        return True
    if (a, b) in _KEEP_APART:
        return True
    if after_regex and _WORD.match(b):
        return True  # /re/ in x must not become /re/in x (flags "in").
    if a.isdigit() and b == ".":
        return True  # 1 .toFixed() must not become 1.toFixed()
    if a == "." and b.isdigit():
        return True
    return False


def minify_js(source: str) -> str:
    """Drop comments and spare spaces from a script, keeping every line break."""
    out: list[str] = []
    last = ""  # Last text written (for the spacing check); "" right after a line break.
    pending_space = False
    previous = None  # (kind, value) of the last token that wasn't a space or comment.
    # Open brackets; "${" marks a template substitution, ("(", True) an if/while/for condition.
    brackets: list = []
    position = 0
    length = len(source)

    def emit(text: str) -> None:
        nonlocal last, pending_space
        if pending_space and _needs_space(last, text, previous is not None and previous[0] == "regex"):
            out.append(" ")
        pending_space = False
        out.append(text)
        last = text

    def newlines(count: int) -> None:
        nonlocal last, pending_space
        if count:
            out.append("\n" * count)
            last = ""
            pending_space = False

    def template_text(start: int) -> int:
        """Copy template text from start; return where code resumes (after ${ or the closing `)."""
        nonlocal previous, last, pending_space
        match = _TEMPLATE_TEXT.match(source, start)
        end = match.end()
        if end >= length:
            raise MinifyError("unterminated template literal")
        pending_space = False
        if source[end] == "`":
            out.append(source[start:end + 1])
            last = "`"
            previous = ("template", "`")
            return end + 1
        # source[end:end + 2] == "${"
        out.append(source[start:end + 2])
        last = "{"
        brackets.append("${")
        previous = ("open", "${")
        return end + 2

    def regex_allowed() -> bool:
        if previous is None:
            return True
        kind, value = previous
        if kind in ("punct", "open"):
            return value not in ("++", "--")
        if kind == "close":
            return value in ("}", "cond)")
        if kind == "word":
            return value in _REGEX_AFTER_WORDS
        return False  # After a string, template, regex or number: division.

    while position < length:
        match = _JS_TOKEN.match(source, position)
        if match is None:
            raise MinifyError(f"unexpected character at {position}: {source[position]!r}")
        kind = match.lastgroup
        text = match.group()
        position = match.end()

        if kind == "space":
            pending_space = True
            continue
        if kind == "newline":
            newlines(1)
            continue
        if kind == "line_comment":
            pending_space = True
            continue
        if kind == "block_comment":
            breaks = len(_LINE_BREAKS.findall(text))
            if breaks:
                newlines(breaks)
            else:
                pending_space = True
            continue

        if kind == "word":
            emit(text)
            previous = ("word", text)
        elif kind == "string":
            emit(text)
            previous = ("string", text)
        elif kind == "tick":
            if pending_space and _needs_space(last, "`"):
                out.append(" ")
            out.append("`")
            position = template_text(position)
        elif kind == "slash":
            if regex_allowed():
                found = _REGEX.match(source, position - 1)
                if found is None:
                    raise MinifyError(f"unreadable regular expression at {position - 1}")
                emit(found.group())
                position = found.end()
                previous = ("regex", found.group())
            else:
                # Division (or /=); the = is read as the next punctuator.
                emit("/")
                previous = ("punct", "/")
        elif kind == "open":
            condition = text == "(" and previous is not None and previous[0] == "word" and previous[1] in _CONDITION_WORDS
            brackets.append(("(", True) if condition else text)
            emit(text)
            previous = ("open", text)
        elif kind == "close":
            if not brackets:
                raise MinifyError(f"unbalanced {text!r} at {position - 1}")
            opened = brackets.pop()
            if opened == "${":
                if text != "}":
                    raise MinifyError(f"unbalanced {text!r} in template at {position - 1}")
                # Back into the template's text: written as it is, no space before it.
                out.append("}")
                position = template_text(position)
                continue
            expected = {"(": ")", "[": "]", "{": "}"}[opened[0] if isinstance(opened, tuple) else opened]
            if text != expected:
                raise MinifyError(f"mismatched {text!r} at {position - 1}")
            emit(text)
            previous = ("close", "cond)" if isinstance(opened, tuple) else text)
        elif kind == "punct":
            emit(text)
            previous = ("punct", text)

    if brackets:
        raise MinifyError("unclosed bracket at end of file")
    result = "".join(out)
    if len(_LINE_BREAKS.findall(result)) != len(_LINE_BREAKS.findall(source)):
        raise MinifyError("line count changed")
    return result


# ----------------------------------------------------------------- stylesheets

_CSS_TOKEN = re.compile(
    r"""
    (?P<space>[ \t\n\r\f]+)
  | (?P<comment>/\*[\s\S]*?\*/)
  | (?P<string>"(?:[^"\\\n\r\f]|\\(?:\r\n|[\s\S]))*"|'(?:[^'\\\n\r\f]|\\(?:\r\n|[\s\S]))*')
  | (?P<url>url\((?=[^'"])[^)'"\s\\]*(?:\\.[^)'"\s\\]*)*\))
  | (?P<escape>\\[0-9A-Fa-f]{1,6}(?:\r\n|[ \t\n\r\f])?|\\[^\n\r\f0-9A-Fa-f])
  | (?P<quote>["'])
  | (?P<other>[^ \t\n\r\f/"'\\u]+|.)
    """,
    re.VERBOSE | re.DOTALL,
)
_CSS_TIGHT = set("{};")
_CSS_WORDISH = re.compile(r"[A-Za-z0-9_%.\-#\\\u0080-\U0010ffff]")


def minify_css(source: str) -> str:
    """Drop comments and spare whitespace from a stylesheet."""
    out: list[str] = []
    pending_space = False
    comment_between = False
    position = 0
    length = len(source)

    while position < length:
        match = _CSS_TOKEN.match(source, position)
        if match is None:
            raise MinifyError(f"unexpected character at {position}")
        kind = match.lastgroup
        text = match.group()
        position = match.end()
        if kind == "space":
            pending_space = True
            continue
        if kind == "comment":
            comment_between = True
            continue
        if kind == "quote":
            raise MinifyError(f"unterminated string at {position - 1}")
        before = out[-1][-1] if out else ""
        if pending_space:
            if before and before not in _CSS_TIGHT and text[0] not in _CSS_TIGHT:
                out.append(" ")
            elif before == ":" and text[0] in ";}":
                # "--flag: ;" sets a custom property to a space (the space toggle trick).
                # "--flag:;" is an empty value, which older browsers throw away.
                out.append(" ")
        elif comment_between and before and _CSS_WORDISH.match(before) and _CSS_WORDISH.match(text[0]):
            out.append("/**/")  # 1px/**/2px are two values; 1px2px would be one.
        pending_space = False
        comment_between = False
        out.append(text)
    return "".join(out)


# ----------------------------------------------------------------------- cache

class _Copies:
    """Minified copies by hash of the original body, least recently used dropped first."""

    def __init__(self, max_bytes: int = CACHE_BYTES):
        self.max_bytes = max_bytes
        self.size = 0
        self.entries: OrderedDict[bytes, bytes] = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key: bytes) -> bytes | None:
        with self.lock:
            found = self.entries.get(key)
            if found is not None:
                self.entries.move_to_end(key)
            return found

    def put(self, key: bytes, body: bytes) -> None:
        with self.lock:
            if key in self.entries or len(body) > self.max_bytes:
                return
            self.entries[key] = body
            self.size += len(body)
            while self.size > self.max_bytes and self.entries:
                _, dropped = self.entries.popitem(last=False)
                self.size -= len(dropped)

    def clear(self) -> None:
        with self.lock:
            self.entries.clear()
            self.size = 0


copies = _Copies()


def kind_for(path: str, media_type: str) -> str | None:
    """"js", "css" or None (left as written) for a response's path and media type."""
    if path in SKIP_PATHS or path.endswith((".min.js", ".min.css")):
        return None
    if media_type in JS_TYPES:
        return "js"
    if media_type in CSS_TYPES:
        return "css"
    return None


def minify_text(text: str, kind: str) -> str:
    return minify_js(text) if kind == "js" else minify_css(text)


def _key(body: bytes, kind: str) -> bytes:
    return hashlib.blake2b(kind.encode() + b"\0" + body, digest_size=20).digest()


def cached(body: bytes, kind: str) -> bytes | None:
    """The kept minified copy of body, if it has been made already."""
    return copies.get(_key(body, kind))


def minified(body: bytes, kind: str) -> bytes:
    """The minified copy of body, or body itself if it can't be minified safely."""
    key = _key(body, kind)
    found = copies.get(key)
    if found is not None:
        return found
    try:
        smaller = minify_text(body.decode("utf-8"), kind).encode("utf-8")
    except (MinifyError, UnicodeDecodeError, RecursionError):
        smaller = body
    if len(smaller) >= len(body):
        smaller = body
    copies.put(key, smaller)
    return smaller
