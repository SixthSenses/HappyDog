"""Central application-wide constants.

PR2 introduction: consolidate magic numbers used across domains.
"""

# Max length for summary / preview texts (notifications, posts, comments, etc.)
SUMMARY_MAX_LEN: int = 80

# Batch size for like existence checks (comments/posts)
LIKE_BATCH: int = 30

# Biometric folder prefixes (PR2B system-level hardening)
NOSE_STAGING_PREFIX = "nose_prints_staging/"
NOSE_VERIFIED_PREFIX = "nose_prints_verified/"
EYE_ANALYSIS_PREFIX = "eye_analysis_images/"

# Allowed image magic prefixes (simple signature check)
ALLOWED_IMAGE_MAGICS = {
	b"\xFF\xD8\xFF": "JPEG",
	b"\x89PNG\r\n\x1a\n": "PNG",
	b"RIFF": "RIFF"  # Will further check for WEBP chunk header if needed
}

__all__ = [
	"SUMMARY_MAX_LEN",
	"LIKE_BATCH",
	"NOSE_STAGING_PREFIX",
	"NOSE_VERIFIED_PREFIX",
	"EYE_ANALYSIS_PREFIX",
	"ALLOWED_IMAGE_MAGICS"
]
