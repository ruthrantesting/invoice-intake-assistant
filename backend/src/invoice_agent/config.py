import json
import os
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://invoice:invoice@localhost:5432/invoice_agent"
    blob_root: Path = Path("./backend/var/blobs")
    data_encryption_key: SecretStr | None = None
    oidc_issuer: str | None = None
    oidc_callback_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: SecretStr | None = None
    session_secret: SecretStr | None = None
    csrf_secret: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    openrouter_model: str = "qwen/qwen3.7-flash"
    openrouter_allowed_providers: str = ""
    external_provider_approved: bool = False
    allow_insecure_local_auth: bool = False
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    max_pdf_pages: int = Field(default=100, gt=0)
    max_image_pixels: int = Field(default=40_000_000, gt=0)
    currency_tolerances_json: str = "{}"
    max_workbook_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    max_cell_text_length: int = Field(default=32767, gt=0, le=32767)
    retention_days: int | None = Field(default=None, gt=0)
    external_data_residency: str | None = None
    workbook_profile_approved: bool = False
    oidc_role_claim: str = "roles"
    oidc_tenant_claim: str = "tenant_id"
    prototype_mode: bool = False
    prototype_auto_login: bool = True
    prototype_user_id: str = "local-operator"
    prototype_user_name: str = "Jamie Davis"
    prototype_tenant_id: str = "00000000-0000-4000-8000-000000000001"

    @model_validator(mode="after")
    def require_expected_model(self) -> "Settings":
        if self.openrouter_model != "qwen/qwen3.7-flash":
            raise ValueError(
                "The configured model must be qwen/qwen3.7-flash; substitutions are unsupported."
            )
        return self

    @model_validator(mode="after")
    def validate_currency_tolerances(self) -> "Settings":
        try:
            tolerances = json.loads(self.currency_tolerances_json)
        except json.JSONDecodeError as exc:
            raise ValueError("CURRENCY_TOLERANCES_JSON must be valid JSON.") from exc
        if not isinstance(tolerances, dict) or any(
            not isinstance(currency, str)
            or len(currency) != 3
            or not currency.isalpha()
            or not isinstance(value, (str, int, float))
            for currency, value in tolerances.items()
        ):
            raise ValueError(
                "Currency tolerances must map three-letter currency codes to decimal strings."
            )
        return self

    def production_readiness_issues(self) -> list[str]:
        issues: list[str] = []
        required_secrets = {
            "DATA_ENCRYPTION_KEY": self.data_encryption_key,
            "SESSION_SECRET": self.session_secret,
            "CSRF_SECRET": self.csrf_secret,
        }
        for name, secret in required_secrets.items():
            if secret is None:
                issues.append(f"{name} must be configured.")
        if self.session_secret and len(self.session_secret.get_secret_value().encode()) < 32:
            issues.append("SESSION_SECRET must be at least 32 bytes.")
        if not all(
            (self.oidc_issuer, self.oidc_client_id, self.oidc_client_secret, self.oidc_callback_url)
        ):
            issues.append(
                "Organization OIDC issuer, client credentials, and callback URL must be configured."
            )
        if not self.external_provider_approved:
            issues.append("External model provider processing must be approved.")
        if not self.openrouter_api_key:
            issues.append("OPENROUTER_API_KEY must be configured.")
        if not self.openrouter_allowed_providers.strip():
            issues.append("Approved OpenRouter provider routing must be explicitly restricted.")
        if not self.workbook_profile_approved:
            issues.append("The workbook compatibility profile must be approved.")
        if self.retention_days is None:
            issues.append("Retention duration must be approved and configured.")
        if not self.external_data_residency:
            issues.append("External provider data residency must be approved and documented.")
        if not self.currency_tolerances_json.strip() or self.currency_tolerances_json == "{}":
            issues.append(
                "Currency-specific tolerance configuration must be approved and configured."
            )
        return issues


@lru_cache
def get_settings() -> Settings:
    requested_prototype = os.getenv("PROTOTYPE_MODE", "false").lower() in {"1", "true", "yes"}
    if requested_prototype:
        os.environ.setdefault("PROTOTYPE_MODE", "true")
    configured = Settings()
    prototype_mode = configured.prototype_mode or requested_prototype
    if not prototype_mode:
        return configured
    configured.prototype_mode = True
    # Prototype-only ephemeral keys are generated locally and are not suitable for
    # multi-process or production deployments. They are never used unless opted in.
    if configured.database_url.startswith("postgresql+"):
        configured.database_url = f"sqlite+aiosqlite:///{Path.cwd() / 'invoice-agent-prototype.db'}"
    configured.blob_root = Path.cwd() / "var" / "prototype-blobs"
    secret_dir = Path.cwd() / ".prototype_data"
    secret_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    def local_secret(filename: str, expected_length: int) -> SecretStr:
        secret_file = secret_dir / filename
        if (
            not secret_file.exists()
            or len(secret_file.read_text(encoding="utf-8").strip()) != expected_length
        ):
            secret_file.write_text(secrets.token_hex(expected_length // 2), encoding="utf-8")
            secret_file.chmod(0o600)
        return SecretStr(secret_file.read_text(encoding="utf-8").strip())

    if configured.session_secret is None:
        configured.session_secret = local_secret("session.key", 64)
    if configured.data_encryption_key is None:
        configured.data_encryption_key = local_secret("data.key", 32)
    if configured.currency_tolerances_json == "{}":
        configured.currency_tolerances_json = (
            '{"USD":"0.01","EUR":"0.01","GBP":"0.01","CAD":"0.01"}'
        )
    configured.workbook_profile_approved = True
    return configured


settings = get_settings()
