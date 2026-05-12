def build_provider(config: dict):
    provider_name = config.get("provider", "google")

    if provider_name == "google":
        from .gemini_config import DEFAULT_GEMINI_MODEL
        from .providers.google_provider import GoogleProvider

        model = (config.get("model") or "").strip() or DEFAULT_GEMINI_MODEL
        return GoogleProvider(
            api_key=config.get("gemini_api_key", ""),
            model=model,
        )

    if provider_name == "apple":
        from .providers.apple_provider import AppleProvider

        return AppleProvider()

    raise ValueError(f"Unknown provider: {provider_name}")
