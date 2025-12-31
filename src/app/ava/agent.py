"""Ava AI Agent powered by Google Gemini."""

import logging

from google import genai
from google.genai import types

from ..config import get_settings
from .prompts import COMMAND_RESPONSES, FALLBACK_RESPONSE, SYSTEM_PROMPT
from .security import (
    SessionManager,
    detect_injection_attempt,
    get_injection_warning,
    sanitize_input,
    sanitize_output,
    validate_message,
)

logger = logging.getLogger(__name__)


class AvaAgent:
    """Ava AI assistant using Google Gemini with security hardening."""

    def __init__(self):
        self.settings = get_settings()
        self.client: genai.Client | None = None
        self.session_manager = SessionManager()

        # Initialize Gemini if API key is available
        if self.settings.gemini_api_key:
            self._initialize_gemini()
        else:
            logger.warning("GEMINI_API_KEY not set. Ava will use fallback responses.")

    def _initialize_gemini(self):
        """Initialize the Gemini client."""
        try:
            self.client = genai.Client(api_key=self.settings.gemini_api_key)
            logger.info("Gemini client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            self.client = None

    def _check_builtin_command(self, message: str) -> str | None:
        """Check if the message is a built-in command."""
        command = message.strip().lower()

        # Direct command match
        if command in COMMAND_RESPONSES:
            return COMMAND_RESPONSES[command]

        # Partial matches for common queries
        if "project" in command:
            return COMMAND_RESPONSES["projects"]
        if "skill" in command or "tech" in command or "stack" in command:
            return COMMAND_RESPONSES["skills"]
        if "contact" in command or "email" in command or "reach" in command:
            return COMMAND_RESPONSES["contact"]
        if "hire" in command or "job" in command or "work" in command:
            return COMMAND_RESPONSES["contact"]

        return None

    async def chat(self, message: str, session_id: str = "default") -> tuple[str, bool]:
        """
        Process a chat message and return Ava's response.

        Args:
            message: The user's message
            session_id: Session identifier for conversation context

        Returns:
            Tuple of (response: str, success: bool)
        """
        # Sanitize input first
        message = sanitize_input(message)

        # Validate message
        is_valid, error = validate_message(message)
        if not is_valid:
            return error, False

        # Check for built-in commands first (before injection check)
        builtin_response = self._check_builtin_command(message)
        if builtin_response:
            return builtin_response, True

        # Check for prompt injection attempts
        is_injection, pattern = detect_injection_attempt(message)
        if is_injection:
            logger.warning(
                f"Injection attempt detected from session {session_id}: pattern={pattern}"
            )
            return get_injection_warning(), True

        # If no Gemini client, return fallback
        if not self.client:
            return FALLBACK_RESPONSE, True

        try:
            # Get existing session or create new one
            chat = self.session_manager.get_session(session_id)

            if chat is None:
                # Check if we can create a new session
                if not self.session_manager.can_create_session():
                    logger.warning("Max sessions reached, rejecting new session")
                    return "Server busy. Try again in a few minutes.", False

                # Create new chat session
                chat = self.client.chats.create(
                    model="gemini-2.5-flash-lite",
                    config=types.GenerateContentConfig(
                        temperature=0.8,
                        max_output_tokens=300,  # Reduced from 500 for cost control
                        top_p=0.95,
                        top_k=40,
                        system_instruction=SYSTEM_PROMPT,
                    ),
                )
                self.session_manager.add_session(session_id, chat)

            # Send message and get response
            response = chat.send_message(message)

            # Update session activity
            self.session_manager.update_session_activity(session_id)

            # Sanitize output before returning
            return sanitize_output(response.text), True

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return FALLBACK_RESPONSE, True

    def reset_session(self, session_id: str = "default"):
        """Reset a chat session."""
        self.session_manager.remove_session(session_id)
