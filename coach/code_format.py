"""Format C++ as text only; the formatter never executes the submitted code."""
import re
import subprocess
from functools import lru_cache
from clang_format import get_executable

STYLE = '{BasedOnStyle: LLVM, IndentWidth: 4, ColumnLimit: 88, SortIncludes: false, ReflowComments: false, BreakStringLiterals: false, AllowShortFunctionsOnASingleLine: None, AllowShortLoopsOnASingleLine: false, AllowShortIfStatementsOnASingleLine: Never}'

@lru_cache(maxsize=128)
def format_cpp(code):
    result = subprocess.run([get_executable('clang-format'), '-assume-filename=answer.cpp', '-style=' + STYLE],
        input=code, text=True, encoding='utf-8', capture_output=True, timeout=5, check=True)
    return result.stdout.rstrip() + '\n'

def format_cpp_blocks(answer):
    pattern = re.compile(r'^(`{3,}|~{3,})(?:cpp|c\+\+|cxx|cc|c\+\+17|cpp17)\s*\n(.*?)^\1\s*$', re.M | re.S | re.I)
    def replace(match):
        try:
            return f'{match[1]}cpp\n{format_cpp(match[2])}{match[1]}'
        except (OSError, subprocess.SubprocessError):
            # An incomplete model fragment must remain visible with its partial status.
            return match[0]
    return pattern.sub(replace, answer)
