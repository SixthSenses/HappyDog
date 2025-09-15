import os
import logging
from typing import Dict, Optional, List

_DEF_TRUE = {"1","true","yes","on"}

def as_bool(val: Optional[str]) -> bool:
    if val is None:
        return False
    return val.strip().lower() in _DEF_TRUE

def resolve_path(raw: Optional[str], bases: List[str]) -> Optional[str]:
    """Resolve a possibly relative path against candidate base directories.

    Returns first existing absolute path; if none exist returns original raw (may be non-existent) so caller can log.
    """
    if not raw:
        return None
    cleaned = raw.strip().strip('"').strip("'")
    if os.path.isabs(cleaned) and os.path.exists(cleaned):
        return os.path.abspath(cleaned)
    for base in bases:
        cand = os.path.abspath(os.path.join(base, cleaned))
        if os.path.exists(cand):
            return cand
    return cleaned  # unresolved (caller decides if warning needed)

def resolve_ml_paths(env: Dict[str, str]) -> Dict[str, Optional[str]]:
    """Resolve ML related paths using repo + backend roots as fallbacks.
    Expected keys: YOLO_WEIGHTS_PATH, ML_CONFIG_PATH, EXTRACTOR_WEIGHTS_PATH, FAISS_INDEX_PATH
    """
    backend_root = os.path.dirname(os.path.dirname(__file__))  # .../pet_project_backend
    repo_root = os.path.dirname(backend_root)
    bases = [backend_root, repo_root]
    keys = [
        'YOLO_WEIGHTS_PATH',
        'ML_CONFIG_PATH',
        'EXTRACTOR_WEIGHTS_PATH',
        'FAISS_INDEX_PATH'
    ]
    resolved = {}
    for k in keys:
        resolved[k] = resolve_path(env.get(k) or os.getenv(k), bases)
    # Emit summary log once
    logging.info("ML path resolution summary: %s", {k: resolved[k] for k in keys})
    return resolved
