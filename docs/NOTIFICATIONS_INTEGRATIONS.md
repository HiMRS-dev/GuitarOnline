# Notifications Integrations (v1)

This document defines the minimum integration contract for notification delivery providers.

## 1. Provider Interface Contract

Every channel provider must implement:

```python
async def send(message) -> DeliveryResult
```

Required behavior:

- Input `message` must contain normalized notification data:
  - `notification_id`,
  - `user_id`,
  - `channel`,
  - `template_key`,
  - `title`,
  - `body`.
- Return value must include:
  - `success: bool`,
  - `error_message: str | None`.
- Provider must not mutate the source notification record directly; worker owns final status update.

Current implementation:

- `StubEmailDeliveryClient.send(message)` writes a delivery attempt to logs and returns `success=True`.

## 2. Channel-Specific Payload Adapter

Provider implementations should keep transport payload mapping in adapter functions:

- `build_email_payload(message)` for SMTP/API email providers.
- `build_telegram_payload(message)` for Telegram Bot API providers.

Adapter expectations:

- convert generic message fields into provider-specific fields (`subject`, `text`, `chat_id`, etc.),
- keep template rendering outside adapter (worker passes rendered text),
- preserve `notification_id` in transport metadata when supported for traceability.

## 3. Retry and Error Handling Expectations

Delivery flow expectations:

- transient failures should return `success=False` with actionable `error_message`,
- worker marks notification as `failed` and moves outbox event to retry path,
- retries are controlled by worker backoff/max retry settings,
- provider code must raise only for unexpected runtime faults; expected transport failures should be returned as failed result.

Error classification guidelines:

- retryable:
  - network timeout,
  - temporary upstream outage,
  - rate limit.
- non-retryable:
  - invalid recipient address/chat id,
  - malformed request payload rejected by provider.

## 4. Idempotency and Observability

- reminder notifications use deterministic `idempotency_key` and must not be duplicated.
- delivery logs should include:
  - `notification_id`,
  - channel name,
  - provider response/error summary.
- provider implementations should avoid logging sensitive user content beyond what is required for debugging.
