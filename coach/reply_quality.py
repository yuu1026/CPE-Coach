"""Language and repetition checks on prose, preserving code and output literals."""
import re
from difflib import SequenceMatcher
from functools import lru_cache
from opencc import OpenCC

PROTECTED = re.compile(r'(`+)[^\n]*?\1|https?://[^\s)]+')

@lru_cache(maxsize=1)
def converter():
    return OpenCC('s2twp')

def map_prose(text, transform):
    result, fence = [], None
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            result.append(line)
        elif fence is not None or line.startswith(('    ', '\t')):
            result.append(line)
        else:
            parts, start = [], 0
            for match in PROTECTED.finditer(line):
                parts.extend([transform(line[start:match.start()]), match.group()])
                start = match.end()
            parts.append(transform(line[start:]))
            result.append(''.join(parts))
    return ''.join(result)

def traditional_reply(text):
    return map_prose(text, converter().convert)

def prose_only(text):
    # map_prose keeps literals intact; collect only the parts passed to transform.
    collected = []
    map_prose(text, lambda part: collected.append(part) or '')
    return ''.join(collected)

def quality_issue(answer, messages):
    prose = prose_only(answer)
    chinese = len(re.findall(r'[\u3400-\u9fff]', prose))
    english = len(re.findall(r'[A-Za-z]{2,}', prose))
    if chinese < 4 and english >= 8:
        return 'language'
    normalized = re.sub(r'\s+', '', prose)
    latest = next((m['content'] for m in reversed(messages[:-1]) if m['role'] == 'assistant'), '')
    previous = re.sub(r'\s+', '', prose_only(traditional_reply(latest)))
    if len(normalized) >= 30 and previous and SequenceMatcher(None, normalized, previous).ratio() > .88:
        return 'repetition'
    sentences = [s.strip() for s in re.split(r'[。！？\n]', prose) if len(s.strip()) >= 12]
    if len(sentences) >= 3 and len(set(sentences)) <= len(sentences) // 2:
        return 'repetition'
    return None
