"""ForgeGod Shortcut Detector — catches coder efficiency shortcuts."""

from __future__ import annotations

import re
from dataclasses import dataclass

SKIP_VERIFICATION_PATTERNS = [
    re.compile(r"skip\s+(test|lint|type\s*check|verify|review)", re.I),
    re.compile(r"no\s+need\s+to\s+run", re.I),
    re.compile(r"won't\s+run\s+(tests?|lint|check)", re.I),
    re.compile(r"verif(y|ication)\s+not\s+(needed|required|necessary)", re.I),
    re.compile(r"assum(?:e|ing)\s+it\s+(should|will)\s+work", re.I),
    re.compile(r"test(?:s)?\s+(can|will)\s+(be|feel)\s+redundant", re.I),
]

GOOD_ENOUGH_PATTERNS = [
    re.compile(r"\bgood\s+enough\b", re.I),
    re.compile(r"\bshould\s+work\b", re.I),
    re.compile(r"\blooks?\s+good\b", re.I),
    re.compile(r"\bsufficient\b", re.I),
    re.compile(r"\bacceptable\b", re.I),
    re.compile(r"\bthis\s+will\s+do\b", re.I),
    re.compile(r"\bgood\s+to\s+go\b", re.I),
    re.compile(r"\bfine\s+for\s+now\b", re.I),
    re.compile(r"\bclose\s+enough\b", re.I),
]

SINGLE_PASS_PATTERNS = [
    re.compile(r"^done[.!]?\s*$", re.I),
    re.compile(r"^complete[.!]?\s*$", re.I),
    re.compile(r"^all\s+set[.!]?\s*$", re.I),
    re.compile(r"implement(?:ed|ation)?\s+complete", re.I),
    re.compile(r"task\s+(is\s+)?done", re.I),
]

VAGUE_COPY_PATTERNS = [
    re.compile(r"\bwe\s+help\s+you\b", re.I),
    re.compile(r"\btransform(?:s|ing)?\s+your\s+\w+", re.I),
    re.compile(r"\bseamless(?:ly)?\b", re.I),
    re.compile(r"\bpow(?:er|ered)\s+by\b", re.I),
    re.compile(r"\bcutting[\-\s]edge\b", re.I),
    re.compile(r"\bnext[\-\s]generation\b", re.I),
    re.compile(r"\bunlock(?:s|ing)?\s+(your|the)?\s*\w*", re.I),
    re.compile(r"\bleverage(?:s|ing)?\s+(your|the)?\s*\w*", re.I),
    re.compile(r"\bscalab(?:le|ility)\b", re.I),
    re.compile(r"\brobust\b", re.I),
    re.compile(r"\beffortless(?:ly)?\b", re.I),
]

SHORTCUT_CATEGORIES = {
    "skipped_verification": SKIP_VERIFICATION_PATTERNS,
    "good_enough_language": GOOD_ENOUGH_PATTERNS,
    "single_pass": SINGLE_PASS_PATTERNS,
    "vague_copy": VAGUE_COPY_PATTERNS,
}

@dataclass
class ShortcutMatch:
    category: str
    matched_text: str
    line: str
    line_number: int

class ShortcutDetector:
    def __init__(self, blocked_categories=None, custom_patterns=None):
        self.blocked_categories = set(blocked_categories or set(SHORTCUT_CATEGORIES))
        self._patterns = dict(SHORTCUT_CATEGORIES)
        if custom_patterns:
            self._patterns.update(custom_patterns)

    def detect(self, text: str) -> list[ShortcutMatch]:
        matches = []
        lines = text.splitlines()
        for category, patterns in self._patterns.items():
            if category not in self.blocked_categories:
                continue
            for line_num, line in enumerate(lines, 1):
                for pattern in patterns:
                    m = pattern.search(line)
                    if m:
                        matches.append(ShortcutMatch(
                            category=category,
                            matched_text=m.group(0),
                            line=line.strip(),
                            line_number=line_num,
                        ))
        return matches

    def has_skipped_verification(self, text: str) -> bool:
        return any(m.category == "skipped_verification" for m in self.detect(text))

    def detect_single_pass(self, text: str) -> bool:
        return any(m.category == "single_pass" for m in self.detect(text))

    def summary(self, matches: list[ShortcutMatch]) -> str:
        if not matches:
            return "No shortcuts detected."
        by_cat = {}
        for m in matches:
            by_cat.setdefault(m.category, []).append(m)
        lines = []
        for cat, ms in by_cat.items():
            lines.append(f"  [{cat}] ({len(ms)} occurrence(s))")
            for m in ms[:3]:
                lines.append(f"    line {m.line_number}: ...{m.line[-80:]}")
        return "\n".join(lines)
