"""Payment abstraction. 'mock' activates the plan instantly (test mode).
To go live, implement a provider with the same `charge` signature (Razorpay / Stripe)
and set PAYMENT_PROVIDER. Verify payments server-side (webhook) before calling activate()."""
import uuid

from core import db
from core.config import PAYMENT_PROVIDER
from core.plans import get_plan, price_for


def activate(uid, plan_key, period, coupon=None, provider="mock", txn_ref=None):
    amount = price_for(get_plan(plan_key), period, coupon)
    db.add_payment(uid, plan_key, period, amount, coupon, provider, "paid", txn_ref or uuid.uuid4().hex[:12])
    db.set_plan(uid, plan_key, period)
    return amount


def charge(uid, plan_key, period, coupon=None):
    if PAYMENT_PROVIDER == "mock":
        return activate(uid, plan_key, period, coupon)
    raise NotImplementedError(f"Payment provider '{PAYMENT_PROVIDER}' is not wired up yet.")
