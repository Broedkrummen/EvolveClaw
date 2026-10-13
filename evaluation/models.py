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


def _integer(value, minimum=0):
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _price(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def token_plan_endpoint(url):
    host = urlparse(url).hostname or ""
    return host.startswith("token-plan") and host.endswith(".xiaomimimo.com")


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str
    base_url: str
    api_key_env: str
    max_cost_usd: float | None = None
    input_usd_per_million: float | None = None
    output_usd_per_million: float | None = None
    max_input_tokens: int = 32768
    max_output_tokens: int = 1024
    max_calls: int = 200
    timeout_seconds: float = 60
    opt_in: bool = False
    temperature: float = .3
    max_total_tokens: int | None = None
    max_quota_credits: int | None = None
    quota_uncached_input_credits: int | None = None
    quota_cached_input_credits: int | None = None
    quota_output_credits: int | None = None
    execution_backend: str = "direct-http"
    native_json_mode: bool = False

    def validate(self, require_opt_in=True):
        if require_opt_in and self.opt_in is not True:
            raise ValueError("Actual model runs require explicit opt_in=true")
        if self.provider not in ("openai-compatible", "anthropic", "xiaomi-mimo"):
            raise ValueError("Select openai-compatible, anthropic, or xiaomi-mimo provider")
        if self.execution_backend not in ("direct-http", "native-openclaw"):
            raise ValueError("Select direct-http or native-openclaw execution backend")
        if type(self.native_json_mode) is not bool or (self.native_json_mode and
                (self.execution_backend != "native-openclaw" or self.provider != "xiaomi-mimo")):
            raise ValueError("native_json_mode requires the native Xiaomi backend and a boolean flag")
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
        prices = (self.input_usd_per_million, self.output_usd_per_million)
        if any(value is not None for value in prices) and not all(_price(value) for value in prices):
            raise ValueError("Supply both known finite nonnegative prices or omit both; unknown prices stay unknown")
        if self.max_cost_usd is not None and (not _price(self.max_cost_usd) or self.max_cost_usd <= 0):
            raise ValueError("The optional US-dollar cap must be positive and finite")
        if self.max_cost_usd is not None and not all(_price(value) for value in prices):
            raise ValueError("Enforcing a US-dollar cap requires both known unit prices")
        for name in ("max_total_tokens", "max_quota_credits"):
            value = getattr(self, name)
            if value is not None and not _integer(value, 1):
                raise ValueError(f"{name} must be a positive integer when supplied")
        if self.max_cost_usd is None and self.max_total_tokens is None:
            raise ValueError("An explicit total-token or priced US-dollar cap is required")
        weights = (self.quota_uncached_input_credits, self.quota_cached_input_credits, self.quota_output_credits)
        if any(value is not None for value in weights) and not all(_integer(value) for value in weights):
            raise ValueError("Supply all three known nonnegative credit weights or omit all three")
        if self.max_quota_credits is not None and not all(_integer(value) for value in weights):
            raise ValueError("A quota-credit cap requires explicit input/cache/output credit weights")
        if all(_integer(value) for value in weights) and self.quota_cached_input_credits > self.quota_uncached_input_credits:
            raise ValueError("Cached input cannot exceed the uncached weight used for conservative reservation")
        if token_plan_endpoint(self.base_url):
            if self.provider != "xiaomi-mimo" or self.max_total_tokens is None or self.max_quota_credits is None:
                raise ValueError("Token Plan requires explicit xiaomi-mimo provider, total-token cap, and weighted-credit cap")
            if self.execution_backend != "native-openclaw":
                raise ValueError("Token Plan usage requires the approved native OpenClaw backend; direct HTTP is disabled")
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
        if self.input_usd_per_million is None or self.output_usd_per_million is None:
            return None
        return (self.max_input_tokens * self.input_usd_per_million +
                self.max_output_tokens * self.output_usd_per_million) / 1_000_000

    def reservation_credits(self):
        self.validate()
        if self.quota_uncached_input_credits is None or self.quota_output_credits is None:
            return None
        return self.max_input_tokens * self.quota_uncached_input_credits + self.max_output_tokens * self.quota_output_credits

    def public_dict(self):
        self.validate(require_opt_in=False)
        return asdict(self)  # Contains the environment-variable NAME, never a key.


class BudgetLedger:
    """Shared across assistant, learning calls, candidates, and perspectives."""
    def __init__(self, max_cost_usd=None, max_calls=200, *, max_total_tokens=None, max_quota_credits=None):
        if max_cost_usd is not None and (not _price(max_cost_usd) or max_cost_usd <= 0):
            raise ValueError("Ledger dollar cap must be positive and finite")
        if max_total_tokens is not None and not _integer(max_total_tokens, 1):
            raise ValueError("Ledger total-token cap must be a positive integer")
        if max_quota_credits is not None and not _integer(max_quota_credits, 1):
            raise ValueError("Ledger quota-credit cap must be a positive integer")
        if max_cost_usd is None and max_total_tokens is None:
            raise ValueError("Ledger requires an explicit dollar or total-token cap")
        if not isinstance(max_calls, int) or isinstance(max_calls, bool) or max_calls <= 0:
            raise ValueError("Ledger needs a positive maximum call count")
        self.max_cost_usd, self.max_calls = max_cost_usd, max_calls
        self.max_total_tokens, self.max_quota_credits = max_total_tokens, max_quota_credits
        self.calls = []
        self._by_id = {}
        self._accounted_budget = 0.0
        self._accounted_tokens = 0
        self._accounted_credits = 0
        self._lock = RLock()
        self._breached = False
        self._blocked_reason = None

    def _accounted(self):
        return self._accounted_budget

    def reserve(self, amount, metadata, *, input_tokens=None, output_tokens=None, quota_credits=None):
        if amount is not None and not _price(amount):
            raise ValueError("Dollar reservation must be finite and nonnegative, or unknown")
        known_tokens = _integer(input_tokens) and _integer(output_tokens)
        tokens = input_tokens + output_tokens if known_tokens else None
        if self.max_cost_usd is not None and amount is None:
            raise ValueError("A dollar-capped ledger requires a known dollar reservation")
        if self.max_total_tokens is not None and tokens is None:
            raise ValueError("A token-capped ledger requires input/output token reservations")
        if quota_credits is not None and not _integer(quota_credits):
            raise ValueError("Credit reservation must be a nonnegative integer")
        if self.max_quota_credits is not None and quota_credits is None:
            raise ValueError("A credit-capped ledger requires a known credit reservation")
        with self._lock:
            exceeded = (self.max_cost_usd is not None and self._accounted() + amount > self.max_cost_usd + 1e-12) or (
                self.max_total_tokens is not None and self._accounted_tokens + tokens > self.max_total_tokens) or (
                self.max_quota_credits is not None and self._accounted_credits + quota_credits > self.max_quota_credits)
            if self._breached or self._blocked_reason or len(self.calls) >= self.max_calls or exceeded:
                raise BudgetExceeded("Shared evaluation token/credit/spending/call limit prevents issuing this request")
            call = {"id": str(uuid.uuid4()), **metadata, "reserved_cost_usd": amount,
                    "accounted_cost_usd": amount, "usage_status": "unknown",
                    "cost_status": "reserved-estimate" if amount is not None else "unknown",
                    "reserved_input_tokens": input_tokens, "reserved_output_tokens": output_tokens,
                    "reserved_total_tokens": tokens, "accounted_total_tokens": tokens,
                    "reserved_quota_credits": quota_credits, "accounted_quota_credits": quota_credits,
                    "quota_status": "reserved-conservative-estimate" if quota_credits is not None else "unknown",
                    "input_tokens": None, "output_tokens": None, "total_tokens": None,
                    "cached_input_tokens": None, "reasoning_tokens": None, "status": "reserved"}
            self.calls.append(call)
            self._by_id[call["id"]] = call
            self._accounted_budget += amount or 0
            self._accounted_tokens += tokens or 0
            self._accounted_credits += quota_credits or 0
            return call["id"]

    def block(self, reason):
        with self._lock:
            self._blocked_reason = str(reason)

    def has_provider_limit_violation(self):
        with self._lock:
            return self._breached

    def stop_reason(self):
        with self._lock:
            return self._blocked_reason or ("Provider exceeded a configured reservation/limit" if self._breached else None)

    def finish(self, call_id, config, input_tokens=None, output_tokens=None, error=None, *,
               total_tokens=None, cached_input_tokens=None, reasoning_tokens=None):
        with self._lock:
            call = self._by_id[call_id]
            known = _integer(input_tokens) and _integer(output_tokens)
            total_known = _integer(total_tokens)
            if known and total_tokens is None:
                total_tokens, total_known = input_tokens + output_tokens, True
            inconsistent = any(value is not None and not _integer(value) for value in
                (input_tokens, output_tokens, total_tokens, cached_input_tokens, reasoning_tokens)) or (
                known and total_known and total_tokens != input_tokens + output_tokens) or (
                total_known and _integer(input_tokens) and total_tokens < input_tokens) or (
                total_known and _integer(output_tokens) and total_tokens < output_tokens) or (
                _integer(cached_input_tokens) and _integer(input_tokens) and cached_input_tokens > input_tokens) or (
                _integer(reasoning_tokens) and _integer(output_tokens) and reasoning_tokens > output_tokens)
            call["status"] = "failed" if error else "completed"
            call["error_type"] = error
            if inconsistent:
                call["usage_error"] = "Provider usage totals/details are inconsistent"
                self._blocked_reason = call["usage_error"]
                return  # Keep every reservation rather than releasing on unreliable usage.
            if total_known:
                self._accounted_tokens += total_tokens - (call["accounted_total_tokens"] or 0)
                call.update({"total_tokens": total_tokens, "accounted_total_tokens": total_tokens,
                             "usage_status": "actual" if known else "actual-total-only"})
                if call["reserved_total_tokens"] is not None and total_tokens > call["reserved_total_tokens"]:
                    self._breached = True
                    call["provider_limit_violation"] = True
            if known:
                call.update({"input_tokens": input_tokens, "output_tokens": output_tokens})
                if input_tokens > config.max_input_tokens or output_tokens > config.max_output_tokens:
                    self._breached = True
                    call["provider_limit_violation"] = True
            if _integer(cached_input_tokens):
                call["cached_input_tokens"] = cached_input_tokens
            if _integer(reasoning_tokens):
                call["reasoning_tokens"] = reasoning_tokens  # Subset of completion, never added twice.
            if known and config.input_usd_per_million is not None and config.output_usd_per_million is not None:
                amount = (input_tokens * config.input_usd_per_million + output_tokens * config.output_usd_per_million) / 1_000_000
                self._accounted_budget += amount - (call["accounted_cost_usd"] or 0)
                call.update({
                             "accounted_cost_usd": amount, "cost_status": "estimated-at-configured-prices"})
                if call["reserved_cost_usd"] is not None and amount > call["reserved_cost_usd"] + 1e-12:
                    self._breached = True
                    call["provider_limit_violation"] = True
            if known and config.quota_uncached_input_credits is not None and config.quota_output_credits is not None:
                cached = cached_input_tokens if _integer(cached_input_tokens) else 0
                credits = ((input_tokens - cached) * config.quota_uncached_input_credits +
                           cached * config.quota_cached_input_credits + output_tokens * config.quota_output_credits)
                self._accounted_credits += credits - (call["accounted_quota_credits"] or 0)
                call.update({"accounted_quota_credits": credits, "quota_status": "conservative-estimate-no-discount",
                             "cache_accounting": "provider-reported" if _integer(cached_input_tokens) else "unknown-assumed-uncached"})
                if call["reserved_quota_credits"] is not None and credits > call["reserved_quota_credits"]:
                    self._breached = True
                    call["provider_limit_violation"] = True
            # Unknown requests retain the reservation; valid reported usage is
            # reconciled even when execution failed. Never infer a free request.
            if (self.max_cost_usd is not None and self._accounted() > self.max_cost_usd + 1e-12) or (
                self.max_total_tokens is not None and self._accounted_tokens > self.max_total_tokens) or (
                self.max_quota_credits is not None and self._accounted_credits > self.max_quota_credits):
                self._breached = True

    def snapshot(self):
        from copy import deepcopy
        with self._lock:
            priced = self.max_cost_usd is not None or (bool(self.calls) and all(call["accounted_cost_usd"] is not None for call in self.calls))
            quota_known = self.max_quota_credits is not None or (bool(self.calls) and all(call["accounted_quota_credits"] is not None for call in self.calls))
            return {"max_cost_usd": self.max_cost_usd, "max_calls": self.max_calls,
                    "max_total_tokens": self.max_total_tokens, "max_quota_credits": self.max_quota_credits,
                    "request_count": len(self.calls), "accounted_budget_usd": self._accounted() if priced else None,
                    "accounted_total_tokens": self._accounted_tokens,
                    "known_total_tokens": sum(call["total_tokens"] or 0 for call in self.calls),
                    "reserved_unknown_tokens": sum(call["accounted_total_tokens"] or 0 for call in self.calls if call["total_tokens"] is None),
                    "accounted_quota_credits": self._accounted_credits if quota_known else None,
                    "quota_status": "conservative-estimate-and-reserved-no-discount" if quota_known else "unknown",
                    "provider_limit_violation": self._breached,
                    "blocked_reason": self._blocked_reason,
                    "cost_status": "estimated-and-reserved-at-configured-prices" if priced else "unknown",
                    "actual_usage_calls": sum(call["usage_status"].startswith("actual") for call in self.calls),
                    "unknown_usage_calls": sum(not call["usage_status"].startswith("actual") for call in self.calls),
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
    def __init__(self, config: ModelConfig, ledger=None, transport=None, stage="unspecified", transport_kind=None):
        config.validate()
        self.config = config
        self.model = config.model
        self.ledger = ledger if ledger is not None else BudgetLedger(config.max_cost_usd, config.max_calls,
            max_total_tokens=config.max_total_tokens, max_quota_credits=config.max_quota_credits)
        for name in ("max_cost_usd", "max_total_tokens", "max_quota_credits"):
            expected, actual = getattr(config, name), getattr(self.ledger, name)
            if expected is not None and (actual is None or actual > expected):
                raise ValueError("Shared ledger cannot exceed or omit the selected model's explicit limits")
        if self.ledger.max_calls > config.max_calls:
            raise ValueError("Shared ledger cannot exceed the selected model's call limit")
        if self.ledger.max_cost_usd is not None and config.reservation_cost() is None:
            raise ValueError("Shared dollar budget requires known model prices")
        if self.ledger.max_quota_credits is not None and config.reservation_credits() is None:
            raise ValueError("Shared credit budget requires known credit weights")
        self.transport = transport or _http_transport
        self.injected_transport = transport is not None
        self.transport_kind = transport_kind or ("native-openclaw" if getattr(transport, "native_openclaw", False) is True else "offline-mock" if transport is not None else "direct-http")
        if self.transport_kind not in ("direct-http", "native-openclaw", "offline-mock"):
            raise ValueError("Unknown model transport kind")
        if self.transport_kind == "native-openclaw":
            if config.execution_backend != "native-openclaw" or transport is None or getattr(transport, "native_openclaw", False) is not True:
                raise ValueError("Native execution requires an explicit approved OpenClaw transport")
        elif self.transport_kind == "direct-http" and (config.execution_backend == "native-openclaw" or token_plan_endpoint(config.base_url)):
            raise ValueError("Native/Token Plan execution cannot fall back to direct HTTP")
        self.stage = stage

    def for_stage(self, stage):
        return BudgetedModel(self.config, self.ledger,
                             self.transport if self.injected_transport else None, stage, self.transport_kind)

    async def generate(self, messages):
        normalized = _messages(messages)
        # Conservative text-byte bound plus generous role/request overhead.
        # Supported contract: text tokenizers with <=1 token/UTF-8 byte and no
        # undisclosed billable input. Provider violations stop later calls.
        input_bound = len(json.dumps(normalized, ensure_ascii=False).encode("utf-8")) + 4096 + 256 * len(normalized)
        if input_bound > self.config.max_input_tokens:
            raise ValueError("Text input exceeds the configured conservative input-token bound")
        headers = {"Content-Type": "application/json"}
        if self.transport_kind == "native-openclaw":
            key = None  # Host owns authentication; no environment or key-header access.
        elif self.injected_transport:
            key = "injected-offline-transport-no-live-key"
        else:
            key = os.environ.get(self.config.api_key_env)
            if not key:
                raise ValueError("The explicitly selected API-key environment variable is missing")
        if self.config.provider == "anthropic":
            headers["anthropic-version"] = "2023-06-01"
            if key is not None:
                headers["x-api-key"] = key
            system = "\n".join(message["content"] for message in normalized if message["role"] == "system")
            payload = {"model": self.model, "max_tokens": self.config.max_output_tokens,
                       "messages": [m for m in normalized if m["role"] != "system"], "temperature": self.config.temperature}
            if system:
                payload["system"] = system
            url = self.config.base_url.rstrip("/") + "/messages"
        else:
            if key is not None:
                headers["Authorization"] = "Bearer " + key
            payload = {"model": self.model, "messages": normalized, "temperature": self.config.temperature}
            if self.config.provider == "xiaomi-mimo":
                payload.update({"max_completion_tokens": self.config.max_output_tokens,
                                "thinking": {"type": "disabled"}})
            else:
                payload["max_tokens"] = self.config.max_output_tokens
            if self.config.native_json_mode:
                payload["response_format"] = {"type": "json_object"}
            url = self.config.base_url.rstrip("/") + "/chat/completions"
        call_id = self.ledger.reserve(self.config.reservation_cost(), {
            "provider": self.config.provider, "model": self.model, "stage": self.stage,
            "input_upper_bound": input_bound, "input_limit": self.config.max_input_tokens,
            "output_limit": self.config.max_output_tokens, "injected_transport": self.injected_transport,
            "transport_kind": self.transport_kind,
            "native_budget_contract": getattr(self.transport, "budget_contract", None) if self.transport_kind == "native-openclaw" else None,
            "thinking": "disabled" if self.config.provider == "xiaomi-mimo" else "not-configured"},
            input_tokens=self.config.max_input_tokens, output_tokens=self.config.max_output_tokens,
            quota_credits=self.config.reservation_credits())
        input_tokens = output_tokens = total_tokens = cached_input_tokens = reasoning_tokens = None
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
                total_tokens = usage.get("total_tokens")
                prompt_details = usage.get("prompt_tokens_details") or {}
                completion_details = usage.get("completion_tokens_details") or {}
                cached_input_tokens = prompt_details.get("cached_tokens") if isinstance(prompt_details, dict) else None
                reasoning_tokens = completion_details.get("reasoning_tokens") if isinstance(completion_details, dict) else None
                content = raw["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Expected a text model response")
            self.ledger.finish(call_id, self.config, input_tokens, output_tokens,
                total_tokens=total_tokens, cached_input_tokens=cached_input_tokens, reasoning_tokens=reasoning_tokens)
            if self.ledger.stop_reason():
                raise BudgetExceeded("Provider violated the configured usage/reservation contract; later calls are blocked")
            return ModelReply(content, raw)
        except BaseException as exc:
            # SDK helpers can swallow execution errors and continue reflection.
            # Fence the shared ledger before propagating any issued-call failure,
            # including cancellation, rather than waiting for the outer runner.
            self.ledger.block(self.ledger.stop_reason() or "Model execution failed; later requests are blocked")
            if self.transport_kind == "native-openclaw":
                from .openclaw_transport import NativeOpenClawError
                # Only the approved native adapter's sanitized error type carries
                # trusted normalized usage. Arbitrary exception metadata cannot
                # release a reservation. finish() validates all totals/details.
                if isinstance(exc, NativeOpenClawError) and isinstance(exc.metadata, dict):
                    usage = exc.metadata.get("usage")
                    if isinstance(usage, dict):
                        input_tokens, output_tokens = usage.get("prompt_tokens"), usage.get("completion_tokens")
                        total_tokens = usage.get("total_tokens")
                        prompt_details = usage.get("prompt_tokens_details")
                        completion_details = usage.get("completion_tokens_details")
                        cached_input_tokens = prompt_details.get("cached_tokens") if isinstance(prompt_details, dict) else None
                        reasoning_tokens = completion_details.get("reasoning_tokens") if isinstance(completion_details, dict) else None
            self.ledger.finish(call_id, self.config, input_tokens, output_tokens, error=type(exc).__name__,
                total_tokens=total_tokens, cached_input_tokens=cached_input_tokens, reasoning_tokens=reasoning_tokens)
            raise
