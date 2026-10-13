"""Explicit, bounded provider calls for opt-in simulation experiments.

No client is instantiated from implicit environment defaults. Each call reserves
the configured input/output maximum before sending. Unknown usage retains that
reservation; failed requests are not retried automatically. Dollar accounting is
an estimate at the explicitly configured prices, not a billing statement.
"""
import asyncio
from dataclasses import asdict, dataclass
import json
import math
import os
import re
from threading import RLock
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError
import uuid


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str
    base_url: str
    api_key_env: str
    max_cost_usd: float
    input_usd_per_million: float
    output_usd_per_million: float
    max_input_tokens: int = 32768
    max_output_tokens: int = 1024
    max_calls: int = 200
    timeout_seconds: float = 60
    opt_in: bool = False
    temperature: float = .3

    def validate(self, require_opt_in=True):
        if require_opt_in and self.opt_in is not True:
            raise ValueError("Actual model runs require explicit opt_in=true")
        if self.provider not in ("openai-compatible", "anthropic"):
            raise ValueError("Select openai-compatible or anthropic provider")
        if not isinstance(self.model, str) or not self.model.strip() or not isinstance(self.api_key_env, str) or not self.api_key_env.strip():
            raise ValueError("An explicit model and API-key environment-variable name are required")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.api_key_env):
            raise ValueError("api_key_env must be an environment-variable identifier, never an API key")
        if not isinstance(self.base_url, str):
            raise ValueError("An explicit provider base URL is required")
        parsed = urlparse(self.base_url)
        if not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Use an explicit base URL without embedded credentials, query, or fragment")
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")):
            raise ValueError("Provider base URL must use HTTPS or trusted loopback HTTP")
        for name in ("input_usd_per_million", "output_usd_per_million"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be an explicitly known finite nonnegative price")
        if not isinstance(self.max_cost_usd, (int, float)) or isinstance(self.max_cost_usd, bool) or not math.isfinite(self.max_cost_usd) or self.max_cost_usd <= 0:
            raise ValueError("A positive finite US-dollar spending cap is required")
        for name in ("max_input_tokens", "max_output_tokens", "max_calls"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.max_input_tokens > 1_000_000 or self.max_output_tokens > 1_000_000:
            raise ValueError("Token limits above one million are unsupported")
        if not isinstance(self.timeout_seconds, (int, float)) or isinstance(self.timeout_seconds, bool) or not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 300:
            raise ValueError("timeout_seconds must be in (0,300]")
        if not isinstance(self.temperature, (int, float)) or isinstance(self.temperature, bool) or not math.isfinite(self.temperature) or not 0 <= self.temperature <= 1:
            raise ValueError("temperature must be a finite number in [0,1]")

    def reservation_cost(self):
        self.validate()
        return (self.max_input_tokens * self.input_usd_per_million +
                self.max_output_tokens * self.output_usd_per_million) / 1_000_000

    def public_dict(self):
        self.validate(require_opt_in=False)
        return asdict(self)  # Contains the environment-variable NAME, never a key.


class BudgetLedger:
    """Shared across assistant, learning calls, candidates, and perspectives."""
    def __init__(self, max_cost_usd, max_calls=200):
        if not isinstance(max_cost_usd, (int, float)) or isinstance(max_cost_usd, bool) or not math.isfinite(max_cost_usd) or max_cost_usd <= 0:
            raise ValueError("Ledger needs a positive finite cap")
        if not isinstance(max_calls, int) or isinstance(max_calls, bool) or max_calls <= 0:
            raise ValueError("Ledger needs a positive maximum call count")
        self.max_cost_usd, self.max_calls = max_cost_usd, max_calls
        self.calls = []
        self._by_id = {}
        self._accounted_budget = 0.0
        self._lock = RLock()
        self._breached = False
        self._blocked_reason = None

    def _accounted(self):
        return self._accounted_budget

    def reserve(self, amount, metadata):
        if not isinstance(amount, (int, float)) or isinstance(amount, bool) or not math.isfinite(amount) or amount < 0:
            raise ValueError("Reservation must be finite and nonnegative")
        with self._lock:
            if self._breached or self._blocked_reason or len(self.calls) >= self.max_calls or self._accounted() + amount > self.max_cost_usd + 1e-12:
                raise BudgetExceeded("Shared evaluation spending/call limit prevents issuing this request")
            call = {"id": str(uuid.uuid4()), **metadata, "reserved_cost_usd": amount,
                    "accounted_cost_usd": amount, "usage_status": "unknown", "cost_status": "reserved-estimate",
                    "input_tokens": None, "output_tokens": None, "status": "reserved"}
            self.calls.append(call)
            self._by_id[call["id"]] = call
            self._accounted_budget += amount
            return call["id"]

    def block(self, reason):
        with self._lock:
            self._blocked_reason = str(reason)

    def has_provider_limit_violation(self):
        with self._lock:
            return self._breached

    def finish(self, call_id, config, input_tokens=None, output_tokens=None, error=None):
        with self._lock:
            call = self._by_id[call_id]
            known = all(isinstance(value, int) and not isinstance(value, bool) and value >= 0
                        for value in (input_tokens, output_tokens))
            call["status"] = "failed" if error else "completed"
            call["error_type"] = error
            if known:
                amount = (input_tokens * config.input_usd_per_million + output_tokens * config.output_usd_per_million) / 1_000_000
                self._accounted_budget += amount - call["accounted_cost_usd"]
                call.update({"input_tokens": input_tokens, "output_tokens": output_tokens, "usage_status": "actual",
                             "accounted_cost_usd": amount, "cost_status": "estimated-at-configured-prices"})
                if input_tokens > config.max_input_tokens or output_tokens > config.max_output_tokens or amount > call["reserved_cost_usd"] + 1e-12:
                    self._breached = True
                    call["provider_limit_violation"] = True
            # Unknown/failed requests retain the full reservation. Never infer free.
            if self._accounted() > self.max_cost_usd + 1e-12:
                self._breached = True

    def snapshot(self):
        from copy import deepcopy
        with self._lock:
            return {"max_cost_usd": self.max_cost_usd, "max_calls": self.max_calls,
                    "request_count": len(self.calls), "accounted_budget_usd": self._accounted(),
                    "provider_limit_violation": self._breached,
                    "blocked_reason": self._blocked_reason,
                    "cost_status": "estimated-and-reserved-at-configured-prices",
                    "actual_usage_calls": sum(call["usage_status"] == "actual" for call in self.calls),
                    "unknown_usage_calls": sum(call["usage_status"] == "unknown" for call in self.calls),
                    "calls": deepcopy(self.calls)}


@dataclass(frozen=True)
class ModelReply:
    content: str
    raw_response: dict


def _messages(messages):
    result = []
    for message in messages:
        role = message.get("role") if isinstance(message, dict) else message.role
        content = message.get("content") if isinstance(message, dict) else message.content
        if role not in ("system", "user", "assistant"):
            raise ValueError("Simulation models support only system/user/assistant text messages")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list) and all(isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str) for block in content):
            text = "\n".join(block["text"] for block in content)
        else:
            raise ValueError("Only text content is supported in bounded simulation calls")
        result.append({"role": role, "content": text})
    if not result:
        raise ValueError("At least one text message is required")
    return result


async def _http_transport(url, payload, headers, timeout):
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            raise HTTPError(req.full_url, code, "Provider redirects are unsupported", hdrs, fp)

    def request():
        body = json.dumps(payload).encode("utf-8")
        with build_opener(NoRedirect()).open(Request(url, data=body, headers=headers, method="POST"), timeout=timeout) as response:
            data = response.read(4_000_001)
        if len(data) > 4_000_000:
            raise ValueError("Provider response exceeded the supported size")
        return json.loads(data)
    return await asyncio.to_thread(request)


class BudgetedModel:
    """SDK-compatible text model with a shared budget and injectable transport."""
    def __init__(self, config: ModelConfig, ledger=None, transport=None, stage="unspecified"):
        config.validate()
        self.config = config
        self.model = config.model
        self.ledger = ledger if ledger is not None else BudgetLedger(config.max_cost_usd, config.max_calls)
        if self.ledger.max_cost_usd > config.max_cost_usd or self.ledger.max_calls > config.max_calls:
            raise ValueError("Shared ledger cannot exceed the selected model's explicit limits")
        self.transport = transport or _http_transport
        self.injected_transport = transport is not None
        self.stage = stage

    def for_stage(self, stage):
        return BudgetedModel(self.config, self.ledger,
                             self.transport if self.injected_transport else None, stage)

    async def generate(self, messages):
        normalized = _messages(messages)
        # Conservative text-byte bound plus generous role/request overhead.
        # Supported contract: text tokenizers with <=1 token/UTF-8 byte and no
        # undisclosed billable input. Provider violations stop later calls.
        input_bound = len(json.dumps(normalized, ensure_ascii=False).encode("utf-8")) + 4096 + 256 * len(normalized)
        if input_bound > self.config.max_input_tokens:
            raise ValueError("Text input exceeds the configured conservative input-token bound")
        headers = {"Content-Type": "application/json"}
        if self.injected_transport:
            key = "injected-offline-transport-no-live-key"
        else:
            key = os.environ.get(self.config.api_key_env)
            if not key:
                raise ValueError("The explicitly selected API-key environment variable is missing")
        if self.config.provider == "anthropic":
            headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
            system = "\n".join(message["content"] for message in normalized if message["role"] == "system")
            payload = {"model": self.model, "max_tokens": self.config.max_output_tokens,
                       "messages": [m for m in normalized if m["role"] != "system"], "temperature": self.config.temperature}
            if system:
                payload["system"] = system
            url = self.config.base_url.rstrip("/") + "/messages"
        else:
            headers["Authorization"] = "Bearer " + key
            payload = {"model": self.model, "messages": normalized,
                       "max_tokens": self.config.max_output_tokens, "temperature": self.config.temperature}
            url = self.config.base_url.rstrip("/") + "/chat/completions"
        call_id = self.ledger.reserve(self.config.reservation_cost(), {
            "provider": self.config.provider, "model": self.model, "stage": self.stage,
            "input_upper_bound": input_bound, "input_limit": self.config.max_input_tokens,
            "output_limit": self.config.max_output_tokens, "injected_transport": self.injected_transport})
        input_tokens = output_tokens = None
        try:
            raw = await self.transport(url, payload, headers, self.config.timeout_seconds)
            usage = raw.get("usage") or {}
            if self.config.provider == "anthropic":
                input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
                # Cache/read/write billing uses additional prices this config
                # does not support: retain the reservation rather than misprice.
                if usage.get("cache_creation_input_tokens") or usage.get("cache_read_input_tokens"):
                    input_tokens = output_tokens = None
                    self.ledger.block("Provider returned unsupported cache billing; explicit additional rates are required")
                    raise ValueError("Provider cache billing is unsupported; later requests are blocked")
                content = "".join(block.get("text", "") for block in raw.get("content", []) if block.get("type") == "text")
            else:
                input_tokens, output_tokens = usage.get("prompt_tokens"), usage.get("completion_tokens")
                content = raw["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Expected a text model response")
            self.ledger.finish(call_id, self.config, input_tokens, output_tokens)
            if self.ledger.has_provider_limit_violation():
                raise BudgetExceeded("Provider exceeded the configured token/reservation contract; later calls are blocked")
            return ModelReply(content, raw)
        except Exception as exc:
            self.ledger.finish(call_id, self.config, input_tokens, output_tokens, error=type(exc).__name__)
            raise
