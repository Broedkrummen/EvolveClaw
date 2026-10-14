"""Authored pure-Python coding sequences with executable, private regression tests.

These exercises cover constrained snippets, not complete repositories. Diagnostic
and heldout families have separate mechanisms; variants remain family clusters.
The public checker receives only advertised cases. Private tests never enter the
tool specification or the offline public-contract response helper.
"""
from __future__ import annotations

from copy import deepcopy
import json
import subprocess
import sys
import tempfile

from .scenarios import Feedback, Scope, ScoringKey, Sequence, Task, ToolFixture


MAX_SOURCE_CHARS = 16000
WALL_SECONDS = 2
RUNTIME_CONTRACT = (
    "Python 3 pure functions; define solve with the signature shown by source_code. "
    "No imports, I/O, global/nonlocal statements, classes, decorators, dunder names, "
    "reflection, eval/exec, or access to environment/files/network. Only JSON inputs "
    "and JSON outputs; preserve input values. Ordinary loops, comprehensions, "
    "local helper functions and safe builtins/string/list/dict methods are allowed. "
    "Execution has a 1-second CPU, 2-second wall, 128-MiB memory and 16,000-character source bound."
)

# This fixed trusted program runs in a fresh interpreter, with an empty inherited
# environment and disposable cwd. Candidate imports and reflection are rejected
# before compilation; candidate globals contain only the restricted builtins.
_RUNNER = r'''
import ast, json, resource, sys
resource.setrlimit(resource.RLIMIT_CPU, (1, 1))
resource.setrlimit(resource.RLIMIT_AS, (128*1024*1024, 128*1024*1024))
resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_NOFILE, (8, 8))
resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
SAFE = {name: getattr(__builtins__, name) for name in (
    'abs','all','any','bool','dict','enumerate','float','int','isinstance','len',
    'list','max','min','range','reversed','round','set','sorted','str','sum',
    'tuple','zip','ValueError','TypeError','ZeroDivisionError')}
METHODS = {'append','extend','pop','get','items','keys','values','copy','sort',
    'reverse','count','index','insert','remove','add','discard','lower','upper',
    'strip','split','join','replace','isdigit','isalpha','startswith','endswith'}
ALLOWED = {getattr(ast, name) for name in (
    'Module','FunctionDef','arguments','arg','Return','Assign','AugAssign',
    'AnnAssign','Expr','If','For','While','Break','Continue','Pass','Try',
    'ExceptHandler','Raise','Name','Load','Store','Constant','List','Tuple',
    'Set','Dict','Subscript','Slice','Call','keyword','Attribute','Lambda',
    'ListComp','SetComp','DictComp','GeneratorExp','comprehension','IfExp',
    'UnaryOp','BoolOp','BinOp','Compare','And','Or','Not','UAdd','USub',
    'Add','Sub','Mult','Div','FloorDiv','Mod','Pow','Eq','NotEq','Lt','LtE',
    'Gt','GtE','Is','IsNot','In','NotIn','JoinedStr','FormattedValue')}
def equal(a,b):
    if type(a) is not type(b): return False
    if isinstance(a,list): return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    if isinstance(a,dict): return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    return a==b
def json_value(value):
    if type(value) in (type(None),bool,int,float,str): return True
    if type(value) is list: return all(json_value(item) for item in value)
    if type(value) is dict: return all(type(key) is str and json_value(item) for key,item in value.items())
    return False
def emit(value):
    sys.stdout.write(json.dumps(value, allow_nan=False))
try:
    request=json.loads(sys.stdin.read(262145))
    tree=ast.parse(request['code'])
    if not tree.body or any(not isinstance(node,ast.FunctionDef) for node in tree.body):
        raise ValueError('shape')
    for node in ast.walk(tree):
        if type(node) not in ALLOWED: raise ValueError('syntax')
        if isinstance(node,ast.Name) and node.id.startswith('__'): raise ValueError('name')
        if isinstance(node,ast.Attribute) and node.attr not in METHODS: raise ValueError('attribute')
        if isinstance(node,ast.FunctionDef) and (node.decorator_list or node.name.startswith('__')):
            raise ValueError('definition')
    namespace={'__builtins__':SAFE}
    exec(compile(tree,'<coding_candidate>','exec'),namespace)
    function=namespace.get('solve')
    if not callable(function): raise ValueError('function')
except SyntaxError:
    emit({'status':'invalid-syntax','tests':[]}); sys.exit(0)
except Exception:
    emit({'status':'unsupported-code','tests':[]}); sys.exit(0)
results=[]
for index,case in enumerate(request['tests']):
    args=json.loads(json.dumps(case['args'],allow_nan=False))
    before=json.loads(json.dumps(args,allow_nan=False))
    try:
        actual=function(*args)
        if not json_value(actual): raise ValueError('non-json-output')
        encoded=json.dumps(actual,allow_nan=False)
        if len(encoded)>32768: raise ValueError('output')
        actual=json.loads(encoded)
        mutated=not equal(args,before)
        results.append({'index':index,'passed':equal(actual,case['expected']) and not mutated,
                        'mutated_inputs':mutated,'actual':actual})
    except Exception:
        results.append({'index':index,'passed':False,'error':'candidate-exception'})
emit({'status':'checked','tests':results})
'''


def _run_code(code, tests):
    if not isinstance(code, str) or not code.strip() or len(code) > MAX_SOURCE_CHARS:
        return {"status": "invalid-source", "tests": []}
    if not isinstance(tests, list) or not 1 <= len(tests) <= 64:
        return {"status": "invalid-contract", "tests": []}
    try:
        payload = json.dumps({"code": code, "tests": tests}, allow_nan=False).encode()
    except (TypeError, ValueError):
        return {"status": "invalid-contract", "tests": []}
    if len(payload) > 262144:
        return {"status": "invalid-contract", "tests": []}
    try:
        with tempfile.TemporaryDirectory(prefix="evolveclaw-code-") as directory:
            run = subprocess.run([sys.executable, "-I", "-S", "-c", _RUNNER],
                input=payload, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                cwd=directory, env={}, timeout=WALL_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        return {"status": "execution-limit", "tests": []}
    if run.returncode != 0:
        return {"status": "execution-limit", "tests": []}
    if len(run.stdout) > 2_200_000:
        return {"status": "output-limit", "tests": []}
    try:
        result = json.loads(run.stdout)
        if result.get("status") == "checked" and len(result.get("tests", [])) != len(tests):
            return {"status": "invalid-runner-result", "tests": []}
        return result
    except (ValueError, AttributeError):
        return {"status": "invalid-runner-result", "tests": []}


def public_code_check(spec, arguments):
    """Execute candidate code on public cases only; never consult private keys."""
    if not isinstance(arguments, dict) or set(arguments) != {"code"} or not isinstance(arguments["code"], str):
        raise ValueError("code.check requires exactly one code string")
    if spec.get("function_name") != "solve":
        raise ValueError("Public coding contract requires solve")
    result = _run_code(arguments["code"], deepcopy(spec.get("tests")))
    rows = result["tests"]
    passed = sum(row["passed"] for row in rows)
    total = len(spec.get("tests", []))
    return {"status": "completed" if result["status"] == "checked" and passed == total else "failed",
            "passed": passed, "failed": total - passed, "total": total,
            "execution_status": result["status"], "tests": rows}


def grade_code(response, grading):
    """Return failed-field strings from real private regression execution."""
    if not isinstance(response, dict) or not isinstance(response.get("code"), str):
        return ["code"]
    if grading.get("kind") != "coding" or grading.get("function_name") != "solve":
        return ["coding_contract"]
    result = _run_code(response["code"], deepcopy(grading.get("tests")))
    if result["status"] != "checked":
        return ["coding_" + result["status"].replace("-", "_")]
    return ["coding_test_" + str(row["index"]) for row in result["tests"] if not row["passed"]]


# Each original has a concrete local defect. Correct source is used solely by
# the offline public-contract helper; it is never placed in a public tool result.
_DEFINITIONS = {
    "even-total": ("Sum every even integer, including negative values.",
        "def solve(values):\n    return sum(x for x in values if x % 2 == 0)\n", "x % 2 == 0", "x % 2 == 0 and x > 0"),
    "bounded-value": ("Clamp an integer to the inclusive bounds lower and upper.",
        "def solve(value):\n    return max(@L@, min(@H@, value))\n", "max(@L@, min(@H@, value))", "min(@L@, max(@H@, value))"),
    "ordered-dedup": ("Remove duplicate strings while preserving their first appearance order.",
        "def solve(values):\n    output = []\n    for value in values:\n        if value not in output:\n            output.append(value)\n    return output\n", "return output", "return sorted(output)"),
    "empty-mean": ("Return the arithmetic mean as a float; an empty list returns fallback.",
        "def solve(values):\n    return float(sum(values)) / len(values) if values else @F@\n", "if values else @F@", "if values else 0.0"),
    "word-token-count": ("Count exact whitespace-delimited word tokens matching target, ignoring letter case; punctuation remains part of a token.",
        "def solve(text):\n    return sum(word.lower() == '@T@' for word in text.split())\n", "word.lower()", "word"),
    "stable-rank-sort": ("Return records sorted by ascending rank, preserving input order for equal ranks; do not mutate the input.",
        "def solve(rows):\n    return sorted(rows, key=lambda row: row['rank'])\n", "key=lambda row: row['rank']", "key=lambda row: row['rank'], reverse=True"),
    "fixed-chunks": ("Partition a list into consecutive chunks of size width; retain a final shorter chunk.",
        "def solve(values):\n    return [values[i:i + @N@] for i in range(0, len(values), @N@)]\n", "len(values), @N@", "len(values) - @N@ + 1, @N@"),
    "sliding-window-sums": ("Return sums of every contiguous window of width; return an empty list when there are too few values.",
        "def solve(values):\n    return [sum(values[i:i + @N@]) for i in range(max(0, len(values) - @N@ + 1))]\n", "len(values) - @N@ + 1", "len(values) - @N@"),
    "merge-closed-intervals": ("Merge unsorted closed integer intervals that overlap or touch at an endpoint; return ascending, non-overlapping interval pairs.",
        "def solve(intervals):\n    result = []\n    for start, end in sorted(intervals):\n        if result and start <= result[-1][1]:\n            result[-1][1] = max(result[-1][1], end)\n        else:\n            result.append([start, end])\n    return result\n", "start <= result[-1][1]", "start < result[-1][1]"),
    "run-length-encoding": ("Encode consecutive runs of strings as [value, run_count] pairs, preserving order.",
        "def solve(values):\n    result = []\n    for value in values:\n        if result and result[-1][0] == value:\n            result[-1][1] += 1\n        else:\n            result.append([value, 1])\n    return result\n", "result[-1][1] += 1", "result[-1][1] = 1"),
    "longest-unique-span": ("Return the length of the longest contiguous substring with no repeated character.",
        "def solve(text):\n    seen = {}\n    left = 0\n    best = 0\n    for right, char in enumerate(text):\n        left = max(left, seen.get(char, -1) + 1)\n        seen[char] = right\n        best = max(best, right - left + 1)\n    return best\n", "max(left, seen.get(char, -1) + 1)", "seen.get(char, -1) + 1"),
    "ragged-transpose": ("Transpose ragged rows; use fill for absent cells and include columns up to the longest row.",
        "def solve(rows):\n    width = max((len(row) for row in rows), default=0)\n    return [[row[c] if c < len(row) else '@T@' for row in rows] for c in range(width)]\n", "max((len(row) for row in rows), default=0)", "min((len(row) for row in rows), default=0)"),
    "clockwise-matrix-rotation": ("Rotate a square matrix clockwise by 90 degrees without changing the original rows; empty input returns empty output.",
        "def solve(rows):\n    n = len(rows)\n    return [[rows[n - 1 - r][c] for r in range(n)] for c in range(n)]\n", "rows[n - 1 - r][c]", "rows[r][c]"),
    "first-match-search": ("For ascending integers and target, return the first matching index, or -1 if absent; duplicate values must use their leftmost index.",
        "def solve(values, target):\n    left, right = 0, len(values)\n    while left < right:\n        middle = (left + right) // 2\n        if values[middle] < target:\n            left = middle + 1\n        else:\n            right = middle\n    return left if left < len(values) and values[left] == target else -1\n", "values[middle] < target", "values[middle] <= target"),
    "window-maxima": ("Return the maximum for every contiguous window of width; too-short input returns an empty list.",
        "def solve(values):\n    return [max(values[i:i + @N@]) for i in range(max(0, len(values) - @N@ + 1))]\n", "max(values[i:i + @N@])", "values[i]"),
    "weighted-average": ("Input pairs are [value, nonnegative_weight]. Return the weighted mean as a float; zero total weight returns fallback.",
        "def solve(pairs):\n    total = sum(pair[1] for pair in pairs)\n    return float(sum(value * weight for value, weight in pairs)) / total if total else @F@\n", "/ total if total", "/ len(pairs) if total"),
    "polynomial-evaluation": ("Evaluate integer polynomial coefficients ordered from highest degree to constant at x; empty coefficients represent zero.",
        "def solve(coefficients, x):\n    value = 0\n    for coefficient in coefficients:\n        value = value * x + coefficient\n    return value\n", "for coefficient in coefficients:", "for coefficient in reversed(coefficients):"),
    "signed-decimal-parser": ("Parse an optional leading sign followed by one or more ASCII digits, optionally a dot and one or more digits; reject whitespace, missing digits, repeated signs, and other characters with None. Return a float for valid input.",
        "def solve(text):\n    body = text[1:] if text.startswith(('+', '-')) else text\n    parts = body.split('.')\n    valid = len(parts) <= 2 and all(part and all('0' <= c <= '9' for c in part) for part in parts)\n    return float(text) if valid else None\n", "all(part and all('0' <= c <= '9' for c in part) for part in parts)", "all(all('0' <= c <= '9' for c in part) for part in parts)"),
    "rooted-path-normalization": ("Normalize a fictional rooted slash path: drop empty and dot segments, resolve dot-dot by removing a previous segment, and clamp traversal at root. Return a leading slash and no trailing slash except root. No filesystem operations.",
        "def solve(path):\n    result = []\n    for part in path.split('/'):\n        if part == '..':\n            if result:\n                result.pop()\n        elif part and part != '.':\n            result.append(part)\n    return '/' + '/'.join(result)\n", "elif part and part != '.':", "elif part:"),
    "top-frequency": ("Return at most limit distinct strings sorted by descending frequency, then lexicographically ascending on ties.",
        "def solve(values):\n    counts = {}\n    for value in values:\n        counts[value] = counts.get(value, 0) + 1\n    return sorted(counts, key=lambda value: (-counts[value], value))[:@N@]\n", "(-counts[value], value)", "(counts[value], value)"),
    "missing-integer-ranges": ("Within inclusive lower and upper bounds, return consecutive missing integer ranges as [start, end] pairs; ignore duplicate and out-of-range supplied values.",
        "def solve(values):\n    present = set(values)\n    result = []\n    for value in range(@L@, @H@ + 1):\n        if value not in present:\n            if result and value == result[-1][1] + 1:\n                result[-1][1] = value\n            else:\n                result.append([value, value])\n    return result\n", "range(@L@, @H@ + 1)", "range(@L@, @H@)"),
    "recursive-list-flattening": ("Flatten arbitrarily nested lists of integers from left to right; discard empty lists without mutating input.",
        "def solve(values):\n    result = []\n    for value in values:\n        if isinstance(value, list):\n            result.extend(solve(value))\n        else:\n            result.append(value)\n    return result\n", "result.extend(solve(value))", "result.extend(value)"),
    "levenshtein-distance": ("Return the minimum count of single-character insertions, deletions, and substitutions needed to transform first string to second.",
        "def solve(first, second):\n    previous = list(range(len(second) + 1))\n    for i, a in enumerate(first, 1):\n        current = [i]\n        for j, b in enumerate(second, 1):\n            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))\n        previous = current\n    return previous[-1]\n", "previous[j - 1] + (a != b)", "previous[j - 1] + 1"),
    "modular-list-rotation": ("Rotate a list to the right by offset, with negative offsets rotating left; use modulo list length and return an empty list for empty input.",
        "def solve(values):\n    if not values:\n        return []\n    offset = @N@ % len(values)\n    return values[-offset:] + values[:-offset] if offset else values[:]\n", "@N@ % len(values)", "@N@"),
    "closed-interval-intersection": ("Intersect two ascending internally disjoint lists of closed intervals. Include point intersections and return ordered [start,end] pairs.",
        "def solve(first, second):\n    result = []\n    i, j = 0, 0\n    while i < len(first) and j < len(second):\n        start = max(first[i][0], second[j][0])\n        end = min(first[i][1], second[j][1])\n        if start <= end:\n            result.append([start, end])\n        if first[i][1] < second[j][1]:\n            i += 1\n        else:\n            j += 1\n    return result\n", "if start <= end:", "if start < end:"),
}

DIAGNOSTIC_FAMILIES = tuple(list(_DEFINITIONS)[:5])
HELDOUT_FAMILIES = tuple(list(_DEFINITIONS)[5:])


def _parameters(family, variant, phase):
    seed = variant + phase + 2
    return {"lower": -seed, "upper": seed + 4, "width": 2 + (variant + phase) % 3,
            "fallback": float(seed), "target": "word" + str(seed),
            "fill": "missing" + str(seed), "limit": 1 + (variant + phase) % 3,
            "offset": seed + 7 if phase % 2 == 0 else -seed - 7,
            "case_seed": variant * 10 + phase}


def _source(family, parameters, *, original=False):
    _, source, old, new = _DEFINITIONS[family]
    if original:
        if old not in source:
            raise AssertionError("Missing authored defect")
        source = source.replace(old, new, 1)
    n = (parameters["limit"] if family == "top-frequency" else
         parameters["offset"] if family == "modular-list-rotation" else parameters["width"])
    target = parameters["fill"] if family == "ragged-transpose" else parameters["target"]
    for token, value in (("@N@", n), ("@L@", parameters["lower"]), ("@H@", parameters["upper"]),
                         ("@F@", parameters["fallback"]), ("@T@", target)):
        source = source.replace(token, str(value))
    return source


def _inputs(family, p):
    n, lo, hi = p["width"], p["lower"], p["upper"]
    if family == "even-total": return [[[-4, 2, hi, -lo]], [[]], [[-8, -2, 1]], [[0]], [[2, 2, -2]], [[hi, hi + 1]]]
    if family == "bounded-value": return [[lo - 3], [hi + 2], [lo], [hi], [0], [lo + 1]]
    if family == "ordered-dedup": return [[['z', 'a', 'z']], [[]], [['b','a','b','c']], [['x']], [['a','a']], [['y','x']]]
    if family == "empty-mean": return [[[]], [[1, hi]], [[-3, 3]], [[0]], [[1,2,3]], [[hi, hi]]]
    if family == "word-token-count":
        t = p["target"]
        return [[t.upper() + ' ' + t], [''], [t + ',' + ' ' + t], ['not' + t], ['  ' + t + '\t' + t.upper()], [t + 's']]
    if family == "stable-rank-sort": return [[[{'id':'a','rank':2},{'id':'b','rank':1},{'id':'c','rank':1}]], [[]], [[{'id':'d','rank':hi},{'id':'e','rank':lo}]], [[{'id':'f','rank':0}]], [[{'id':'g','rank':2},{'id':'h','rank':2}]], [[{'id':'i','rank':3},{'id':'j','rank':1},{'id':'k','rank':2}]]]
    if family == "fixed-chunks": return [[list(range(n + 1))], [[]], [list(range(n - 1))], [list(range(2*n))], [[hi]], [list(range(2*n + 1))]]
    if family == "sliding-window-sums": return [[list(range(n))], [[]], [[hi] * (n + 1)], [list(range(n - 1))], [list(range(-n, n))], [[0] * n]]
    if family == "merge-closed-intervals": return [[[[1,2],[2,4]]], [[]], [[[5,7],[1,3],[2,6]]], [[[1,1]]], [[[1,2],[4,5]]], [[[1,hi],[2,3]]]]
    if family == "run-length-encoding": return [[['a','a','b']], [[]], [['b','b','b']], [['a','b','a']], [['x']], [['x','y','y','z','z']]]
    if family == "longest-unique-span": return [['abba'], [''], ['abcabc'], ['aaaa'], ['dvdf'], ['abcaef']]
    if family == "ragged-transpose": return [[[[1,2],[3]]], [[]], [[[],[hi]]], [[[1,2,3],[4,5],[]]], [[[1],[2]]], [[[]]]]
    if family == "clockwise-matrix-rotation": return [[[[1,2],[3,4]]], [[]], [[[hi]]], [[[1,2,3],[4,5,6],[7,8,9]]], [[[0,-1],[hi,lo]]], [[[1,1],[1,1]]]]
    if family == "first-match-search": return [[[1,2,2,3],2], [[],hi], [[hi,hi],hi], [[lo,0,hi],0], [[1,3],2], [[1,2,3],3]]
    if family == "window-maxima": return [[[1,hi] + [0]*(n-2)], [[]], [[lo]*n], [[hi]*(n-1)], [list(range(2*n))], [[hi]+[0]*n]]
    if family == "weighted-average": return [[[[2,1],[hi,3]]], [[]], [[[hi,0]]], [[[lo,2],[hi,2]]], [[[5,1]]], [[[0,4],[8,0],[4,1]]]]
    if family == "polynomial-evaluation": return [[[2,3,4],2], [[],hi], [[hi],3], [[1,0,0],-2], [[1,-1],0], [[lo,2,1],1]]
    if family == "signed-decimal-parser": return [['.5'], ['+12.25'], ['-3'], [''], ['4.'], [' 3'], ['+-2'], ['1.2.3'], ['0'], ['-0.5'], ['１２']]
    if family == "rooted-path-normalization": return [['/a/./b/../c'], ['/'], ['../../x'], ['/a//b/'], ['/a/../../..'], ['/a/b/../..']]
    if family == "top-frequency": return [[['a','b','b','b','c','c']], [[]], [['z','a','z','a']], [['only']], [['c','b','a']], [['x','x','y']]]
    if family == "missing-integer-ranges": return [[[lo, hi-1]], [[]], [list(range(lo,hi+1))], [[lo-1, hi+1]], [[lo,lo,hi]], [[0]]]
    if family == "recursive-list-flattening": return [[[[1,[2]],3]], [[]], [[[[]],hi]], [[[1,[2,[3]]]]], [[lo,[hi]]], [[[[[]]]]]]
    if family == "levenshtein-distance": return [['abc','abc'], ['','abc'], ['cat','cut'], ['ab','ba'], ['a',''], ['snow','stone']]
    if family == "modular-list-rotation": return [[[1,2,3]], [[]], [[hi]], [[1,2,3,4,5]], [[lo,hi]], [[0,1,2,3]]]
    if family == "closed-interval-intersection": return [[[[1,3]],[[3,5]]], [[],[[1,2]]], [[[1,5]],[[2,3],[4,6]]], [[[1,2]],[[4,5]]], [[[1,1]],[[1,1]]], [[[1,4],[6,9]],[[2,7]]]]
    raise ValueError("Unknown coding mechanism")


def _expected(family, args, p):
    """Independent Python ground truth, never derived by running the answer source."""
    x = args[0]
    if family == "even-total": return sum(x[i] for i in range(len(x)) if x[i] % 2 == 0)
    if family == "bounded-value": return p["lower"] if x < p["lower"] else p["upper"] if x > p["upper"] else x
    if family == "ordered-dedup": return [value for i,value in enumerate(x) if value not in x[:i]]
    if family == "empty-mean": return sum(float(v)/len(x) for v in x) if x else p["fallback"]
    if family == "word-token-count": return x.lower().split().count(p["target"])
    if family == "stable-rank-sort": return [row for _,row in sorted(enumerate(x), key=lambda pair:(pair[1]["rank"],pair[0]))]
    if family == "fixed-chunks":
        output=[]
        for i,value in enumerate(x):
            if i % p["width"] == 0: output.append([])
            output[-1].append(value)
        return output
    if family == "sliding-window-sums": return [sum(x[j] for j in range(i,i+p["width"])) for i in range(len(x)-p["width"]+1)]
    if family == "merge-closed-intervals":
        components=[]
        for interval in x:
            start,end=interval
            changed=True
            while changed:
                changed=False
                for old in components[:]:
                    if start <= old[1] and old[0] <= end:
                        start,end=min(start,old[0]),max(end,old[1]); components.remove(old); changed=True
            components.append([start,end])
        return sorted(components)
    if family == "run-length-encoding":
        boundaries=[i for i in range(len(x)) if i==0 or x[i]!=x[i-1]]+[len(x)]
        return [[x[a],b-a] for a,b in zip(boundaries,boundaries[1:])]
    if family == "longest-unique-span": return max([0]+[j-i for i in range(len(x)) for j in range(i+1,len(x)+1) if len(set(x[i:j]))==j-i])
    if family == "ragged-transpose":
        cells={(r,c):value for r,row in enumerate(x) for c,value in enumerate(row)}
        return [[cells.get((r,c),p["fill"]) for r in range(len(x))] for c in range(max((len(row) for row in x),default=0))]
    if family == "clockwise-matrix-rotation": return [list(reversed(column)) for column in zip(*x)]
    if family == "first-match-search": return x.index(args[1]) if args[1] in x else -1
    if family == "window-maxima": return [sorted(x[i:i+p["width"]])[-1] for i in range(len(x)-p["width"]+1)]
    if family == "weighted-average":
        weight=sum(row[1] for row in x)
        return sum(float(value)*count for value,count in x)/weight if weight else p["fallback"]
    if family == "polynomial-evaluation": return sum(c*args[1]**(len(x)-i-1) for i,c in enumerate(x))
    if family == "signed-decimal-parser":
        import re
        return float(x) if re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?",x) else None
    if family == "rooted-path-normalization":
        segments=[part for part in x.split('/') if part and part!='.']
        stack=[]
        for part in segments:
            if part=='..': stack=stack[:-1]
            else: stack=stack+[part]
        return '/'+ '/'.join(stack)
    if family == "top-frequency": return sorted(set(x),key=lambda item:(-x.count(item),item))[:p["limit"]]
    if family == "missing-integer-ranges":
        missing=sorted(set(range(p["lower"],p["upper"]+1))-set(x)); result=[]
        while missing:
            start=end=missing.pop(0)
            while missing and missing[0]==end+1: end=missing.pop(0)
            result.append([start,end])
        return result
    if family == "recursive-list-flattening":
        queue=deepcopy(x); output=[]
        while queue:
            value=queue.pop(0)
            if isinstance(value,list): queue=value+queue
            else: output.append(value)
        return output
    if family == "levenshtein-distance":
        def distance(a,b):
            if not a:return len(b)
            if not b:return len(a)
            return min(distance(a[1:],b)+1,distance(a,b[1:])+1,distance(a[1:],b[1:])+(a[0]!=b[0]))
        return distance(x,args[1])
    if family == "modular-list-rotation":
        if not x:return []
        return [x[(i-p["offset"])%len(x)] for i in range(len(x))]
    if family == "closed-interval-intersection": return sorted([[max(a,c),min(b,d)] for a,b in x for c,d in args[1] if max(a,c)<=min(b,d)])
    raise ValueError("Unknown coding mechanism")


def _fresh_inputs(family, inputs, parameters):
    """Vary actual data per task state while retaining each tested mechanism."""
    seed = parameters["case_seed"]
    factor = 2 * seed + 1
    rows = deepcopy(inputs)
    if family in {"ordered-dedup", "run-length-encoding", "top-frequency"}:
        return [[[value + str(seed) for value in args[0]]] for args in rows]
    if family in {"longest-unique-span", "levenshtein-distance"}:
        def shift(text):
            return "".join(chr(97 + (ord(char) - 97 + seed) % 26) for char in text)
        return [[shift(text) for text in args] for args in rows]
    if family in {"even-total", "empty-mean", "fixed-chunks", "sliding-window-sums",
                  "window-maxima", "modular-list-rotation"}:
        return [[[value * factor for value in args[0]]] for args in rows]
    if family == "stable-rank-sort":
        return [[[dict(record, id=record["id"] + str(seed), rank=record["rank"] * factor)
                  for record in args[0]]] for args in rows]
    if family in {"merge-closed-intervals", "clockwise-matrix-rotation"}:
        return [[[[value * factor for value in row] for row in args[0]]] for args in rows]
    if family == "first-match-search":
        return [[[value * factor for value in args[0]], args[1] * factor] for args in rows]
    if family == "weighted-average":
        return [[[[value * factor, weight] for value, weight in args[0]]] for args in rows]
    if family == "polynomial-evaluation":
        return [[[value * factor for value in args[0]], args[1]] for args in rows]
    if family == "recursive-list-flattening":
        def scale(value):
            return [scale(item) for item in value] if isinstance(value,list) else value * factor
        return [[scale(args[0])] for args in rows]
    if family == "signed-decimal-parser":
        rows[0][0] = "." + str(seed)
        rows[1][0] = "+" + str(seed) + ".25"
        rows[2][0] = "-" + str(seed)
        return rows
    if family == "rooted-path-normalization":
        return [["/".join(part + str(seed) if part and part not in (".", "..") else part
                          for part in args[0].split("/"))] for args in rows]
    if family == "closed-interval-intersection":
        return [[[[value * factor for value in interval] for interval in side] for side in args]
                for args in rows]
    # These families already have state-specific bounds, word targets or fills.
    return rows


def _task(split, family, variant, phase, scope, topic):
    parameters = _parameters(family,variant,phase)
    inputs = _fresh_inputs(family,_inputs(family,parameters),parameters)
    cases = [{"args": deepcopy(args), "expected": _expected(family,args,parameters)} for args in inputs]
    parameters = {key: value for key,value in parameters.items() if key in {
        "bounded-value": ("lower","upper"), "empty-mean": ("fallback",), "word-token-count": ("target",),
        "fixed-chunks": ("width",), "sliding-window-sums": ("width",), "window-maxima": ("width",),
        "ragged-transpose": ("fill",), "weighted-average": ("fallback",), "top-frequency": ("limit",),
        "missing-integer-ranges": ("lower","upper"), "modular-list-rotation": ("offset",),
    }.get(family, ())}
    # Source rendering uses all tokens, while the public contract advertises only
    # parameters relevant to this mechanism, keeping unrelated hints out.
    full_parameters = _parameters(family,variant,phase)
    contract={"mechanism":family,"parameters":parameters,"description":_DEFINITIONS[family][0],"runtime":RUNTIME_CONTRACT}
    spec={"function_name":"solve","contract":contract,"source_code":_source(family,full_parameters,original=True),"tests":deepcopy(cases[:2])}
    task_id=f"coding.{split}.{family}.{variant:02d}.{'learn' if phase<2 else 'probe'}-{phase+1}"
    inspect=ToolFixture("code.inspect",{"task_id":task_id},deepcopy(spec))
    check=ToolFixture("code.check",{},deepcopy(spec),input_schema={"code":"string"},handler="coding-check")
    instruction=("Repair or complete the supplied pure-Python solve function to satisfy its public contract, preserving inputs. "
                 "Use code.inspect to read its source and public checks; code.check can test your own candidate using a code string. "
                 "Return the complete Python source in final answer.code. Public checks are examples, so satisfy the whole contract. " + RUNTIME_CONTRACT)
    task=Task(task_id,instruction,scope,(inspect,check),topic,"learning" if phase<2 else "future")
    grading={"kind":"coding","function_name":"solve","tests":deepcopy(cases)}
    key=ScoringKey({},("coding_regression",) if phase>=2 else (),topic,grading=grading)
    return task,key


def coding_response(task):
    """Offline fixture helper derives source solely from the public contract."""
    spec=next(tool.result for tool in task.tools if tool.name=="code.inspect")
    contract=spec["contract"]
    family=contract["mechanism"]
    defaults={"lower":0,"upper":0,"width":1,"fallback":0.0,"target":"","fill":"","limit":1,"offset":0}
    defaults.update(deepcopy(contract["parameters"]))
    return {"code":_source(family,defaults)}


def coding_sequences(split="diagnostic"):
    """10 diagnostic or 100 heldout sequences, clustered at 5 or 20 mechanisms."""
    if split not in ("diagnostic","heldout"):
        raise ValueError("Coding split must be diagnostic or heldout")
    families=DIAGNOSTIC_FAMILIES if split=="diagnostic" else HELDOUT_FAMILIES
    variants=2 if split=="diagnostic" else 5
    sequences=[]
    for family in families:
        for variant in range(1,variants+1):
            sequence_id=f"coding.{split}.{family}.{variant:02d}"
            scope=Scope(f"sim:coding-{split}-user-{variant}",f"sim:coding-{family}-project")
            topic=f"coding:{family}"
            tasks,keys=[],{}
            for phase in range(4):
                task,key=_task(split,family,variant,phase,scope,topic)
                tasks.append(task);keys[task.task_id]=key
            feedback=Feedback("Please keep checking boundary and empty inputs against the current contract, and preserve the caller's data when repairing this function.",
                              scope,topic,"coding-regression-checks")
            family_id="coding-"+family
            sequences.append(Sequence(sequence_id,family_id,family_id,"coding",split,
                                      (tasks[0],tasks[1],feedback,tasks[2],tasks[3]),keys))
    return tuple(sequences)


def coding_metadata():
    return {"diagnostic_sequences":10,"heldout_sequences":100,"diagnostic_families":5,
            "heldout_families":20,"scored_tasks":440,"synthetic":True,"published_benchmark":False,
            "limitations":"Constrained pure-Python snippets; no full repository, dependency, filesystem or deployment coverage. Variants share family mechanisms."}
