from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    database_url_sync: str

    jetstream_url: str = "wss://jetstream2.us-east.bsky.network/subscribe"
    jetstream_collections: str = "app.bsky.feed.post"

    fetch_user_agent: str = "snubstack/0.1"
    fetch_timeout_seconds: float = 10.0
    fetch_max_bytes: int = 2_000_000
    fetch_global_rps: float = 10.0
    fetch_per_host_concurrency: int = 1
    fetch_max_attempts: int = 5

    auto_promote_confidence: float = 0.9
    review_confidence: float = 0.6
    red_revalidate_days: int = 30
    green_revalidate_days: int = 180

    emit_labels: bool = False
    labeler_did: str = "did:plc:replace_me"

    ozone_url: str = "http://ozone:3000"
    ozone_admin_password: str = ""

    heron_oauth_client_id: str = ""
    heron_oauth_client_secret: str = ""
    heron_oauth_token_endpoint: str = ""
    heron_api_endpoint: str = ""


settings = Settings()  # type: ignore[call-arg]
