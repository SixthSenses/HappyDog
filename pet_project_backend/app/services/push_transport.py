"""Push notification transport abstraction for decoupling from Firebase Messaging."""
from __future__ import annotations

import logging
from typing import Protocol, Tuple, Optional
from firebase_admin import messaging

from app.models.notification import Notification


class PushTransport(Protocol):
    """Abstract interface for push notification delivery."""

    def send_push(self, token: str, title: str, body: str, data: dict) -> Tuple[bool, Optional[str]]:
        """Send a push notification to the given FCM token.
        
        Args:
            token: FCM registration token
            title: Notification title
            body: Notification body text
            data: Additional data payload
            
        Returns:
            Tuple of (success: bool, error_reason: Optional[str])
            error_reason should be one of: 'unregistered', 'invalid-argument', 'mismatch-sender', 'other'
        """
        ...


class FCMPushTransport:
    """Firebase Cloud Messaging implementation of PushTransport."""

    def send_push(self, token: str, title: str, body: str, data: dict) -> Tuple[bool, Optional[str]]:
        """Send FCM push notification."""
        message = messaging.Message(
            token=token,
            notification=messaging.Notification(title=title, body=body),
            data=data
        )
        try:
            response = messaging.send(message)
            logging.debug(f"FCM message sent: {response}")
            return True, None
        except Exception as e:
            reason = self._classify_error(e)
            logging.warning(f"FCM push failed (reason={reason}): {e}")
            return False, reason

    def _classify_error(self, exc: Exception) -> str:
        """Classify Firebase Messaging error into actionable reason codes."""
        msg = str(exc).lower()
        if 'unregistered' in msg or 'registration-token-not-registered' in msg:
            return 'unregistered'
        if 'invalidargument' in msg or 'invalid registration' in msg or 'invalid-argument' in msg:
            return 'invalid-argument'
        if 'mismatchsenderid' in msg:
            return 'mismatch-sender'
        return 'other'


class StubPushTransport:
    """No-op push transport for testing/docs mode."""

    def send_push(self, token: str, title: str, body: str, data: dict) -> Tuple[bool, Optional[str]]:
        """Stub: always succeeds without actual delivery."""
        logging.info(f"StubPushTransport: would send push to token={token[:10]}... title={title}")
        return True, None
