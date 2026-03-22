# Payments

## Stripe Connect (Express)

Instructors onboard via Stripe Connect Express. The platform takes a configurable share (`STRIPE_PLATFORM_SHARE_PCT`, default 20%) of each transaction.

### Instructor onboarding

```
POST /api/v1/payments/onboard-stripe/
← { onboarding_url }   # redirect instructor here
```

After the instructor completes Stripe's OAuth flow, Stripe sends an `account.updated` webhook. The handler sets `instructor.stripe_onboarded = True`.

### Course purchase

```
POST /api/v1/payments/initiate-payment/
Body: { course_id }
← { client_secret }    # Stripe PaymentIntent client secret
```

The API creates a `PaymentIntent` with `application_fee_amount` (platform share) and `transfer_data.destination` (instructor's Connect account) when the instructor is onboarded. Falls back to a no-fee intent otherwise.

### Webhook

`POST /api/v1/payments/webhook/` handles:

| Event | Action |
|-------|--------|
| `payment_intent.succeeded` | Create `Enrollment`, record `Invoice` |
| `account.updated` | Set `stripe_onboarded = True` on the instructor |

Webhook processing is idempotent — duplicate events are safe.

### Refunds

```
POST /api/v1/payments/refund/   # admin only
Body: { payment_intent_id }
```

Issues a full refund via the Stripe API.
