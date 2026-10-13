import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))


class ServerConfig:
    # Set for manually hosted sidecars; managed Gateway calls stay on loopback.
    AUTH_TOKEN: str | None = os.getenv("EVOLVECLAW_SIDECAR_TOKEN") or os.getenv("EVOLVECLAW_TOKEN")
    ESTIMATE_USAGE: bool = os.getenv("EVOLVECLAW_ESTIMATE_USAGE", "false").lower() == "true"
    INPUT_COST_PER_MILLION: float | None = float(os.environ["EVOLVECLAW_INPUT_COST_PER_MILLION"]) if "EVOLVECLAW_INPUT_COST_PER_MILLION" in os.environ else None
    OUTPUT_COST_PER_MILLION: float | None = float(os.environ["EVOLVECLAW_OUTPUT_COST_PER_MILLION"]) if "EVOLVECLAW_OUTPUT_COST_PER_MILLION" in os.environ else None
    HOST: str = os.getenv("EVOLVECLAW_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("EVOLVECLAW_PORT", "5757"))

    # LLM for SCOPE guideline synthesis (optional — auto-detected from OpenClaw)
    SCOPE_DATA_PATH: str = os.getenv("EVOLVECLAW_SCOPE_DATA") or os.getenv("EVOLVECLAW_SCOPE_DATA_DEFAULT", "./scope_data")
    SCOPE_MODEL: str = os.getenv("EVOLVECLAW_SCOPE_MODEL", "")
    SCOPE_PROVIDER: str = os.getenv("EVOLVECLAW_SCOPE_PROVIDER", "")
    SCOPE_API_KEY: str | None = os.getenv("EVOLVECLAW_SCOPE_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
    SCOPE_BASE_URL: str | None = os.getenv("EVOLVECLAW_SCOPE_BASE_URL") or os.getenv("ANTHROPIC_BASE_URL")

    # SCOPE optimizer settings
    SCOPE_SYNTHESIS_MODE: str = os.getenv("EVOLVECLAW_SYNTHESIS_MODE", "efficiency")
    SCOPE_QUALITY_ANALYSIS: bool = os.getenv("EVOLVECLAW_QUALITY_ANALYSIS", "true").lower() == "true"
    SCOPE_QUALITY_FREQUENCY: int = int(os.getenv("EVOLVECLAW_QUALITY_FREQUENCY", "3"))
    SCOPE_ACCEPT_THRESHOLD: str = os.getenv("EVOLVECLAW_ACCEPT_THRESHOLD", "medium")
    SCOPE_STRATEGIC_THRESHOLD: float = float(os.getenv("EVOLVECLAW_STRATEGIC_THRESHOLD", "0.85"))
    SCOPE_MAX_RULES_PER_TASK: int = int(os.getenv("EVOLVECLAW_MAX_RULES_PER_TASK", "20"))
    SCOPE_MAX_STRATEGIC_PER_DOMAIN: int = int(os.getenv("EVOLVECLAW_MAX_STRATEGIC_PER_DOMAIN", "10"))

    def has_explicit_llm_config(self) -> bool:
        """True when the user explicitly set an API key via .env / env vars."""
        return bool(self.SCOPE_API_KEY)
