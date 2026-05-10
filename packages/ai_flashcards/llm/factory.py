def build_provider(config: dict):
    provider_name = config.get("provider", "google")

    if provider_name == "google":
        from .providers.google_provider import GoogleProvider

        return GoogleProvider(
            api_key=config.get("gemini_api_key", ""),
            model=config.get("model", "gemini-3.1-flash-lite-preview"),
        )

    if provider_name == "apple":
        from .providers.apple_provider import AppleProvider

        return AppleProvider()

    raise ValueError(f"Unknown provider: {provider_name}")
