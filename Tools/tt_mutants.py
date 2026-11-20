"""P03 TestTrust - source-level mutation operators for UE C++ .cpp files.

A mutant is one small, deliberate change to one place in one source file. This module finds the places and describes
the changes; it never writes files (tt_mutate.py applies them to a snapshot, one at a time).

Why a lexer and not a C++ parser: no C++ front end ships with Python, and the compiler is the final judge anyway.
A mutant that doesn't compile is classified "stillborn" and excluded from the score (02 section 4.1). The lexer's job is
to avoid obvious non-mutants: comments, strings, preprocessor lines, template brackets, assertion macros.

Operators (02 section 7, "Mutation operators"):
  ROR   relational:   <  <=  >  >=  ==  !=   -> boundary shift and negation (e.g. < becomes <= and >=)
  AOR   arithmetic:   +  -  *  /  and  +=  -=  *=  /=   -> the inverse operation
  LCR   logical:      &&  ||   -> the other one
  COND  condition:    if (X) / while (X)   -> if (!(X))
  BOOL  literal:      true  false   -> the other one
  SDL   statement deletion: an assignment, increment or call statement   -> ;
Binary operators are mutated only with whitespace on both sides. UE's coding standard spaces binary operators, and
template brackets (TArray<int32>), pointers (AActor* A) and references (T&& V) are written without, so this one rule
separates them cheaply. The compiler catches the rare exception.

Self-test (no UE needed): python -I tt_mutants.py --selftest
"""
from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass, field

# Longest first, so ">>=" is one token, not ">" ">" "=".
OPERATORS = sorted("""
>>= <<= ->* ... :: -> ++ -- << >> <= >= == != && || += -= *= /= %= &= |= ^=
+ - * / % < > = ! & | ^ ~ ? : ; , . ( ) [ ] { } #
""".split(), key=len, reverse=True)

# Macros whose arguments are never mutated: assertions, logging, profiling, registration, text.
SKIP_MACROS = re.compile(r"^(check|checkf|checkSlow|checkNoEntry|ensure|ensureMsgf|ensureAlways|ensureAlwaysMsgf|verify|"
                         r"verifyf|static_assert|UE_LOG|UE_LOGF|UE_CLOG|UE_INLINE_GENERATED_CPP_BY_NAME|TEXT|LOCTEXT|"
                         r"NSLOCTEXT|CSV_\w+|TRACE_\w+|SCOPE_\w+|QUICK_SCOPE_\w+|DECLARE_\w+|DEFINE_\w+|IMPLEMENT_\w+|"
                         r"RETURN_QUICK_DECLARE_CYCLE_STAT|GET_MEMBER_NAME_CHECKED|UE_DEPRECATED)$")

# A statement starting with one of these is never deleted (control flow or a declaration).
NOT_DELETABLE_START = {
    "return", "break", "continue", "goto", "if", "else", "for", "while", "do", "switch", "case", "default", "try",
    "catch", "throw", "co_return", "co_yield", "const", "constexpr", "static", "auto", "using", "typedef", "struct",
    "class", "enum", "union", "namespace", "template", "typename", "friend", "virtual", "inline", "extern",
    "void", "bool", "char", "int", "float", "double", "long", "short", "signed", "unsigned", "volatile", "mutable",
    "new", "delete", "sizeof", "decltype", "this", "operator", "public", "private", "protected",
}

ROR = {"<": ["<=", ">="], "<=": ["<", ">"], ">": [">=", "<="], ">=": [">", "<"], "==": ["!="], "!=": ["=="]}
AOR = {"+": ["-"], "-": ["+"], "*": ["/"], "/": ["*"], "+=": ["-="], "-=": ["+="], "*=": ["/="], "/=": ["*="]}
LCR = {"&&": ["||"], "||": ["&&"]}
ASSIGNMENTS = {"=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="}
ALL_OPERATORS = ("ROR", "AOR", "LCR", "COND", "BOOL", "SDL")

NO_MUTATE_MARKER = "tt-nomutate"   # a comment on a line excludes every mutant on that line


@dataclass
class Token:
    kind: str            # ident, number, string, op
    text: str
    start: int           # offset in the source
    end: int
    line: int            # 1-based
    col: int             # 1-based
    ws_before: bool = False
    ws_after: bool = False
    mutable: bool = False


@dataclass(frozen=True)
class Mutant:
    file: str            # path relative to the UE project, forward slashes
    operator: str
    start: int
    end: int
    original: str
    replacement: str
    line: int
    col: int
    id: str = field(default="")

    def apply(self, source: str) -> str:
        if source[self.start:self.end] != self.original:
            raise ValueError(f"{self.file}:{self.line}: source changed since the mutant was planned")
        return source[:self.start] + self.replacement + source[self.end:]


def _mutant(path: str, op: str, start: int, end: int, source: str, replacement: str, line: int, col: int) -> Mutant:
    original = source[start:end]
    key = f"{path}|{start}|{end}|{op}|{replacement}".encode("utf-8")
    return Mutant(path, op, start, end, original, replacement, line, col, hashlib.sha1(key).hexdigest()[:10])


def tokenize(source: str) -> list[Token]:
    """Tokens outside comments, string/char literals (kept as one token) and preprocessor lines (dropped)."""
    tokens: list[Token] = []
    i, n, line, line_start = 0, len(source), 1, 0
    at_line_start = True
    while i < n:
        c = source[i]
        if c == "\n":
            line, line_start, at_line_start = line + 1, i + 1, True
            i += 1
            continue
        if c in " \t\r\f\v":
            i += 1
            continue
        if source.startswith("//", i):
            i = source.find("\n", i)
            i = n if i < 0 else i
            continue
        if source.startswith("/*", i):
            close = source.find("*/", i + 2)
            close = n if close < 0 else close + 2
            line += source.count("\n", i, close)
            if "\n" in source[i:close]:
                line_start = source.rfind("\n", i, close) + 1
            i = close
            continue
        if c == "#" and at_line_start:
            # A preprocessor line, with backslash continuations: never mutated.
            while i < n:
                end = source.find("\n", i)
                end = n if end < 0 else end
                if source[i:end].rstrip("\r").endswith("\\"):
                    i, line, line_start = end + 1, line + 1, end + 1
                    continue
                i = end
                break
            continue
        at_line_start = False
        start, col = i, i - line_start + 1
        raw = re.match(r'(?:u8|[uUL])?R"([^()\\\s]{0,16})\(', source[i:])
        if raw:
            close = source.find(")" + raw.group(1) + '"', i + raw.end())
            end = n if close < 0 else close + len(raw.group(1)) + 2
            kind = "string"
        elif c in "\"'" or (c in "uUL" and re.match(r'(?:u8|[uUL])["\']', source[i:])):
            quote_at = i + (re.match(r'(?:u8|[uUL])?', source[i:]).end())
            quote = source[quote_at]
            j = quote_at + 1
            while j < n and source[j] != quote and source[j] != "\n":
                j += 2 if source[j] == "\\" else 1
            end, kind = min(j + 1, n), "string"
        elif c.isalpha() or c == "_":
            end = re.match(r"[A-Za-z_0-9]+", source[i:]).end() + i
            kind = "ident"
        elif c.isdigit() or (c == "." and i + 1 < n and source[i + 1].isdigit()):
            end = re.match(r"(?:0[xX][0-9A-Fa-f']+|[0-9'.]+(?:[eE][+-]?[0-9]+)?)[A-Za-z0-9_]*", source[i:]).end() + i
            kind = "number"
        else:
            op = next((o for o in OPERATORS if source.startswith(o, i)), c)
            end, kind = i + len(op), "op"
        line += source.count("\n", start, end)
        tokens.append(Token(kind, source[start:end], start, end, line - source.count("\n", start, end), col))
        i = end
    for token in tokens:
        token.ws_before = token.start > 0 and source[token.start - 1] in " \t\r\n"
        token.ws_after = token.end < n and source[token.end] in " \t\r\n"
    return tokens


def _matching(tokens: list[Token], index: int) -> int:
    """Index of the bracket closing tokens[index] ('(' '[' '{'), or -1."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    opening, closing, depth = tokens[index].text, pairs[tokens[index].text], 0
    for j in range(index, len(tokens)):
        if tokens[j].text == opening:
            depth += 1
        elif tokens[j].text == closing:
            depth -= 1
            if depth == 0:
                return j
    return -1


def mark_mutable(tokens: list[Token], source: str) -> None:
    """A token is mutable if it is inside a function body (or another code block) and not inside a skipped macro."""
    stack: list[str] = []                    # brace kinds: "ns", "type", "code"
    statement_start = 0
    skip_until = -1
    excluded_lines = {number for number, text in enumerate(source.split("\n"), 1) if NO_MUTATE_MARKER in text}
    for i, token in enumerate(tokens):
        if i <= skip_until:
            continue
        if token.kind == "ident" and SKIP_MACROS.match(token.text) and i + 1 < len(tokens) and tokens[i + 1].text == "(":
            skip_until = _matching(tokens, i + 1)
            continue
        if token.text == "{":
            head = [t.text for t in tokens[statement_start:i]]
            if "namespace" in head:
                stack.append("ns")
            elif any(k in head for k in ("class", "struct", "union", "enum")) and "(" not in head:
                stack.append("type")
            else:
                stack.append("code")
            statement_start = i + 1
            continue
        if token.text == "}":
            if stack:
                stack.pop()
            statement_start = i + 1
            continue
        if token.text == ";":
            statement_start = i + 1
        token.mutable = "code" in stack and token.line not in excluded_lines


def generate(path: str, source: str, operators: tuple[str, ...] = ALL_OPERATORS) -> list[Mutant]:
    """Every mutant of one .cpp file, in source order. `path` is only used for ids and reports."""
    tokens = tokenize(source)
    mark_mutable(tokens, source)
    statement_level = _statement_level(tokens)
    mutants: list[Mutant] = []
    for i, t in enumerate(tokens):
        if not t.mutable:
            continue
        binary = t.kind == "op" and t.ws_before and t.ws_after
        if "ROR" in operators and binary and t.text in ROR:
            mutants += [_mutant(path, "ROR", t.start, t.end, source, r, t.line, t.col) for r in ROR[t.text]]
        if "AOR" in operators and binary and t.text in AOR:
            mutants += [_mutant(path, "AOR", t.start, t.end, source, r, t.line, t.col) for r in AOR[t.text]]
        if "LCR" in operators and binary and t.text in LCR:
            mutants += [_mutant(path, "LCR", t.start, t.end, source, r, t.line, t.col) for r in LCR[t.text]]
        if "BOOL" in operators and t.kind == "ident" and t.text in ("true", "false"):
            mutants.append(_mutant(path, "BOOL", t.start, t.end, source, "false" if t.text == "true" else "true", t.line, t.col))
        if "COND" in operators and t.kind == "ident" and t.text in ("if", "while") and i + 1 < len(tokens) \
                and tokens[i + 1].text == "(":
            close = _matching(tokens, i + 1)
            inner = tokens[i + 2:close]
            depth0 = [x.text for x in _top_level(inner)]
            # A declaration or init-statement inside the condition can't be negated as a whole.
            if close > 0 and inner and "=" not in depth0 and ";" not in depth0 and inner[0].text != "const":
                start, end = tokens[i + 1].start, tokens[close].end
                text = source[tokens[i + 2].start:tokens[close - 1].end]
                mutants.append(_mutant(path, "COND", start, end, source, f"(!({text}))", t.line, t.col))
        if "SDL" in operators and statement_level[i] and _starts_statement(tokens, i):
            end = _statement_end(tokens, i)
            if end > 0 and _deletable(tokens[i:end + 1]):
                mutants.append(_mutant(path, "SDL", t.start, tokens[end].end, source, ";", t.line, t.col))
    return mutants


def _top_level(tokens: list[Token]) -> list[Token]:
    depth, out = 0, []
    for t in tokens:
        if t.text in "([{":
            depth += 1
        elif t.text in ")]}":
            depth -= 1
        elif depth == 0:
            out.append(t)
    return out


def _statement_level(tokens: list[Token]) -> list[bool]:
    """True for tokens directly inside a brace block, not inside parentheses or brackets of that block.

    So the conditions of `for (int32 I = 0; I < N; ++I)` are not statements, but the body of a lambda passed as an
    argument (`Sort([](...) { return ...; })`) is: each '{' remembers the bracket depth it opened at.
    """
    depth, at_brace, out = 0, [0], []
    for t in tokens:
        out.append(depth == at_brace[-1])
        if t.text in "([":
            depth += 1
        elif t.text in ")]":
            depth -= 1
        elif t.text == "{":
            at_brace.append(depth)
        elif t.text == "}" and len(at_brace) > 1:
            at_brace.pop()
    return out


def _starts_statement(tokens: list[Token], i: int) -> bool:
    return tokens[i].mutable and i > 0 and tokens[i - 1].text in (";", "{", "}")


def _statement_end(tokens: list[Token], i: int) -> int:
    depth = 0
    for j in range(i, len(tokens)):
        text = tokens[j].text
        if text in "([{":
            depth += 1
        elif text in ")]}":
            depth -= 1
            if depth < 0:
                return -1
        elif text == ";" and depth == 0:
            return j
    return -1


def _deletable(statement: list[Token]) -> bool:
    """An expression statement with a visible effect: an assignment, an increment, or a call. Never a declaration."""
    first = statement[0]
    if first.kind == "op":
        return first.text in ("++", "--") and len(statement) > 2
    if first.kind != "ident" or first.text in NOT_DELETABLE_START:
        return False
    second = statement[1] if len(statement) > 1 else None
    if second is None or second.kind == "ident":                       # "Type Name ..." is a declaration
        return False
    if second.text == "<" and not second.ws_before:                    # "TArray<int32> X" is a declaration
        return False
    if second.text in ("*", "&", "&&") and not second.ws_before:       # "AActor* A" is a declaration
        return False
    top = [t.text for t in _top_level(statement[:-1])]
    is_call = len(statement) >= 3 and statement[-2].text == ")"
    return bool(ASSIGNMENTS.intersection(top)) or "++" in top or "--" in top or is_call


# ---------------------------------------------------------------------------------------------------------------- tests

SELFTEST_SOURCE = r'''
#include "Foo.h"
#define TWICE(x) ((x) * 2)
namespace Game
{
static const float Scale = 2.0f * 3.0f;   // namespace scope: not code, never mutated
int32 Compute(int32 A, int32 B, bool bFlag)
{
	check(A < 100);                         // assertion macro: skipped
	UE_LOG(LogTemp, Log, TEXT("a < b && c"));
	TArray<int32> Values;
	AActor* Owner = nullptr;
	int32 Sum = A + B;                      // AOR (declaration itself is not deleted)
	if (Sum < B && bFlag)                   // ROR, LCR, COND
	{
		Sum *= 2;                           // AOR, SDL
		Values.Add(Sum);                    // SDL (call)
	}
	if (const AActor* Found = Owner)        // COND skipped: declaration in the condition
	{
		++Sum;                              // SDL
	}
	for (int32 I = 0; I < B; ++I)            // ROR on the condition; the header is not a statement
	{
		Sum += I;                           // AOR, SDL
	}
	const char* Raw = R"x(a < b)x";        // raw string: skipped
	return bFlag ? Sum : -Sum;              // unary minus: not AOR
}
}
'''


def _selftest() -> int:
    mutants = generate("Selftest.cpp", SELFTEST_SOURCE)
    summary = sorted((m.operator, m.original, m.replacement) for m in mutants)
    expected = sorted([
        ("AOR", "+", "-"), ("ROR", "<", "<="), ("ROR", "<", ">="), ("LCR", "&&", "||"),
        ("COND", "(Sum < B && bFlag)", "(!(Sum < B && bFlag))"), ("AOR", "*=", "/="),
        ("SDL", "Sum *= 2;", ";"), ("SDL", "Values.Add(Sum);", ";"), ("SDL", "++Sum;", ";"),
        ("ROR", "<", "<="), ("ROR", "<", ">="), ("AOR", "+=", "-="), ("SDL", "Sum += I;", ";"),
    ])
    ok = summary == expected
    for m in mutants:
        assert m.apply(SELFTEST_SOURCE) != SELFTEST_SOURCE
    ids = [m.id for m in mutants]
    ok = ok and len(ids) == len(set(ids))
    print("selftest:", "ok" if ok else "FAILED")
    if not ok:
        print("got     :", summary)
        print("expected:", expected)
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    for file_path in sys.argv[1:]:
        with open(file_path, encoding="utf-8") as handle:
            for m in generate(file_path, handle.read()):
                print(f"{m.id} {m.file}:{m.line}:{m.col} {m.operator:4} {m.original!r} -> {m.replacement!r}")
