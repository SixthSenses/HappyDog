"""RFC7807 Problem Details & Extended Error Builder
=================================================
중앙 ErrorSpec 기반으로 RFC7807 호환 JSON 생성.

출력 구조 (확장):
{
  "type": "about:blank" | "https://docs.happydog/errors/<code>",
  "title": <error_code>,
  "status": <http_status>,
  "error_code": <code>,
  "category": <category>,
  "retriable": <bool>,
  "message": <localized or override>,
  "details": {...}? ,
  "trace_id": "..."? (추후)
}
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from .error_catalog import ERRORS, ErrorSpec

DOC_BASE = "https://docs.happydog/errors"


def build_problem(code: str, message: Optional[str] = None, details: Any = None,
                  type_url: bool = True) -> Tuple[int, Dict[str, Any]]:
    spec: Optional[ErrorSpec] = ERRORS.get(code)
    if not spec:  # fallback unknown
        status = 500
        body = {
            "type": "about:blank",
            "title": code,
            "status": status,
            "error_code": code,
            "category": "INTERNAL",
            "retriable": True,
            "message": message or "알 수 없는 오류"
        }
        if details is not None:
            body["details"] = details
        return status, body

    status = spec.http_status
    body: Dict[str, Any] = {
        "type": f"{DOC_BASE}/{spec.code}" if type_url else "about:blank",
        "title": spec.code,
        "status": status,
        "error_code": spec.code,
        "category": spec.category,
        "retriable": spec.retriable,
    }
    msg = message or spec.default_message
    if msg:
        body["message"] = msg
    if details is not None:
        body["details"] = details
    return status, body


__all__ = ["build_problem"]
