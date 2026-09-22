# Online Grocery

Django grocery storefront with catalog management, delivery slots, Stripe payments,
referral credits, order history, and invoices.

## Local setup

Use Python 3.12 (the deployment version). From the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-test.txt
Copy-Item .env.example .env
```

Set a local secret and Stripe **test** credentials in `.env`. This portable,
fully pinned dependency set supports the storefront and tests; `requirements.txt`
also includes deployment, scraping, and optional PDF renderer dependencies.
On Linux/macOS activate with `source .venv/bin/activate` and copy with `cp`.

```text
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Add catalog products and delivery/pricing settings in Django admin. SQLite is
suitable for local browsing; use PostgreSQL for production and concurrency testing.
Database-backed login throttling requires no separate cache service.

## Checks and tests

```text
python manage.py check --settings=GROCERY.test_settings
python manage.py makemigrations --check --dry-run --settings=GROCERY.test_settings
python manage.py test --settings=GROCERY.test_settings --noinput
```

Tests use an isolated database, in-memory email, and mocked Stripe requests.
They never read deployment database credentials. For PostgreSQL coverage, set
`TEST_DATABASE_URL` to a **dedicated local test server** whose user can create
databases. Django creates and removes its test database there. The two concurrent
payment tests skip SQLite because SQLite has no row-level `SELECT FOR UPDATE`.
GitHub Actions runs the suite against PostgreSQL 16 on Python 3.12.

## Payment lifecycle

1. Browsing the basket and delivery form does not write orders. Submitting the
   delivery form saves an editable draft. GET checkout only displays confirmation.
2. POST checkout validates the basket, customer details, address, delivery slot,
   current prices, and minimum total. It locks the customer and freezes an order
   snapshot before creating a payment attempt.
3. The order becomes `awaiting_payment`. Refreshes reuse the same Stripe intent
   and persistent idempotency key. Only one order per customer can await payment;
   its referral credit is reserved. Newly added basket items remain separate.
4. A signed webhook verifies intent ID, currency, amount, and full receipt, then
   atomically marks the order paid, spends credit, awards rewards, and records
   conversion events. Repeated events cannot repeat these effects. A fully
   credit-funded order uses the same completion logic without charging Stripe.
5. The return page only displays status. Failed card attempts can retry the same
   intent. Explicit POST cancellation cancels Stripe first, then releases credit.
   A processing or already successful payment cannot be canceled locally.
6. Fulfilment proceeds `paid -> processed -> delivered`. Staff cannot override
   payment verification or move completed orders backwards.

Configure Stripe to send `payment_intent.succeeded`, `payment_intent.canceled`,
and `payment_intent.payment_failed` to `/payments/stripe-webhook/`, using the
matching webhook signing secret. For local testing, forward Stripe CLI events
to that endpoint and use the CLI's displayed test signing secret.

## Deployment and historical records

Back up the database and rehearse migrations on a restored copy first.
Do not run test settings in production. No production credentials or data are
needed to run the automated suite.

Before cutting over, pause new checkouts and reconcile all existing Stripe
payment attempts, including older intents whose IDs may have been overwritten
by the previous implementation. Confirm genuine successful payments and cancel
remaining unpaid intents in Stripe. Automated migrations never contact Stripe.

```text
python manage.py migrate
python manage.py audit_order_history
python manage.py check --deploy
```

The migration assigns a distinct attempt key to every existing payment. It
flags old completed orders for review and preserves a recorded paid amount only
when exactly one succeeded payment exists. Legacy pending orders with payment
records are held in `awaiting_payment` for reconciliation; their incomplete
snapshots cannot be used for a new payment. They require an operator-reviewed
correction after reconciling Stripe, rather than automated fulfilment.

Old invoices return an explicit review notice until their historical data is
verified. Do not fill missing addresses, tax rates, or discounts from current
settings. `audit_order_history` is read-only and does not invent missing data.

New invoices use frozen customer, seller, address, item, tax-rate, discount, and
charge data. Products referenced by orders cannot be deleted; hide them instead.
Completed orders and payment attempts cannot be deleted through customer/admin
flows. Account deletion removes the login and personal profile and detaches
orders/payments; transaction snapshots remain for transaction support. Account
deletion is blocked while a payment is active.

Before reopening checkout, exercise Stripe test payments, failed payments,
browser closure before return, webhook retries, cancellation, and multiple tabs
in staging. Verify webhook delivery and the historical-review list. Order email
notifications are attempted after commit; email failure does not reverse payment
and is logged for operators. Monitor this log separately from payment status.
