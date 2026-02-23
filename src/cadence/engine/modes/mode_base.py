"""Base mode specification for orchestrators.

This module defines the abstract base for orchestration modes.
"""

from abc import ABC
from typing import Any, Dict


class OrchestratorMode(ABC):
    """Abstract base class for orchestration modes.

    Each mode (supervisor, coordinator, handoff) extends this class
    with mode-specific configuration.

    Attributes:
        mode_name: Name of the mode
        config: Mode-specific configuration
    """

    def __init__(self, mode_name: str, config: Dict[str, Any]):
        """Initialize orchestrator mode.

        Args:
            mode_name: Name of the mode
            config: Mode configuration dictionary
        """
        self.mode_name = mode_name
        self.config = config

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value
        """
        return self.config.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert mode to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "mode_name": self.mode_name,
            "config": self.config,
        }
