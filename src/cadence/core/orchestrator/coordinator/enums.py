"""Enums for coordinator functionality."""

from enum import Enum


class ResponseTone(Enum):
    """Available response styles for conversation finalization."""

    NATURAL = "natural"
    EXPLANATORY = "explanatory"
    FORMAL = "formal"
    CONCISE = "concise"
    LEARNING = "learning"

    @property
    def description(self) -> str:
        """Return detailed description for this tone."""
        descriptions = {
            "natural": "Respond in a friendly, conversational way as if talking to a friend. Use casual language, contractions, and a warm tone. Be helpful and approachable.",
            "explanatory": "Provide detailed, educational explanations that help users understand concepts. Break down complex information into clear, digestible parts. Use examples and analogies when helpful.",
            "formal": "Use professional, structured language with clear organization. Present information in a business-like manner with proper formatting, bullet points, and formal language.",
            "concise": "Keep responses brief and to-the-point. Focus only on essential information. Avoid unnecessary elaboration or repetition.",
            "learning": "Adopt a teaching approach with step-by-step guidance. Structure responses like a lesson with clear progression, examples, and educational explanations.",
        }
        return descriptions.get(self.value, descriptions["natural"])

    @classmethod
    def get_description(cls, tone: str) -> str:
        """Return description for given tone value."""
        try:
            return cls(tone).description
        except ValueError:
            return cls.NATURAL.description
