"""Factory for instantiating the configured simplification AI provider."""

from app.core.config import Settings
from app.modules.simplification.provider.base import (
    ProviderUnavailableError,
    SimplificationProvider,
)
from app.modules.simplification.provider.disabled import DisabledSimplificationProvider


def get_simplification_provider(settings: Settings) -> SimplificationProvider:
    """Instantiate and return the configured simplification AI provider.

    Raises:
        ValueError: If an unsupported provider name or invalid configuration is specified.
        ProviderUnavailableError: If the provider is disabled or not yet implemented.
    """
    provider_name = settings.simplification_ai_provider

    if provider_name == "disabled":
        return DisabledSimplificationProvider()

    if provider_name in {"gemini", "openai"}:
        # External provider network execution is scheduled for Part 7B.
        # Confirm that an API key is configured and return safe unavailability.
        if (
            settings.simplification_ai_api_key is None
            or not settings.simplification_ai_api_key.get_secret_value().strip()
        ):
            raise ValueError(
                f"A valid API key is required when simplification_ai_provider is '{provider_name}'"
            )
        raise ProviderUnavailableError(
            f"Provider '{provider_name}' is configured but network execution is not yet implemented"
        )

    raise ValueError(f"Unsupported simplification AI provider: {provider_name}")
