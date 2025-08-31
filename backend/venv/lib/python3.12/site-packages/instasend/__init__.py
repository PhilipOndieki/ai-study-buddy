"""
InstaSend: A Python package for sending messages to Instagram users via the Instagram API with Instagram Login.
"""

from .Instagram import Instagram
from .constants import INSTAGRAM_BASE_URL, INSTAGRAM_MESSAGES_ENDPOINT
from .custom_types import InstagramPayload, Attachment, QuickReply, AdsContextData, Referral, ReplyToStory, ReplyTo, Message, Messaging, Entry

__version__ = "0.1.0"
__author__ = "Tomas Santana"
