"""
Utilities for extracting mention nicknames from text.

Supports:
- Korean Hangul syllables (가-힣) and Jamo (ㄱ-ㅎ, ㅏ-ㅣ)
- Latin letters, digits, underscore, hyphen, and dot

Example:
  "안녕 @홍길동 @dog_master-01 @케이.pop" -> ["홍길동", "dog_master-01", "케이.pop"]
"""
import re
from typing import List


_MENTION_PATTERN = re.compile(r"@([0-9A-Za-z_\.가-힣ㄱ-ㅎㅏ-ㅣ\-]+)")

# Common Korean postpositions/suffixes often attached after mentions in running text
# We strip one occurrence if present at the tail of a captured nickname.
_TRAILING_SUFFIXES = [
  # 2-char or longer first (order matters: longest match first)
  "으로", "에서", "에게", "한테", "이라도", "이나마", "이나", "든지",
  # 1-char
  "께", "와", "과", "은", "는", "이", "가", "을", "를", "로", "에", "랑", "님"
]


def extract_mention_nicknames(text: str) -> List[str]:
  """Extract mention nicknames from the given text.

  Returns a de-duplicated list (order not guaranteed).
  """
  if not text:
    return []
  raw = _MENTION_PATTERN.findall(text)
  cleaned: List[str] = []
  for name in raw:
    trimmed = name
    for suf in _TRAILING_SUFFIXES:
      if trimmed.endswith(suf) and len(trimmed) > len(suf):
        trimmed = trimmed[: -len(suf)]
        break  # strip only one suffix
    cleaned.append(trimmed)
  return list(set(cleaned))
