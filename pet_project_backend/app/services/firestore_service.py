# app/services/firestore_service.py
import logging
from typing import Optional

from app.utils.datetime_utils import DateTimeUtils

def save_analysis_result(collection_name: str, user_id: str, data: dict, db_client=None) -> Optional[str]:
    """Persist AI analysis result if a Firestore client is available.

    In docs-mode or tests where `db_client` is None the function becomes a no-op
    and returns None to avoid side effects or accidental Firestore initialization.
    """
    if db_client is None:
        logging.info(f"Skipping save_analysis_result (no db client) for collection {collection_name}")
        return None

    try:
        data['created_at'] = DateTimeUtils.now()
        data['user_id'] = user_id
        data = DateTimeUtils.for_firestore(data)
        doc_ref = db_client.collection(collection_name).document()
        doc_ref.set(data)
        logging.info(f"Firestore save succeeded (Collection: {collection_name}, Doc ID: {doc_ref.id})")
        return doc_ref.id
    except Exception as e:
        logging.error(f"Firestore save failed (Collection: {collection_name}): {e}", exc_info=True)
        raise