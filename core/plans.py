"""Plan catalogue: single source of truth for pricing and entitlements."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    tagline: str
    monthly: int            # INR per month when billed monthly
    yearly_monthly: int     # INR per month when billed yearly
    dynamic_limit: int
    analytics_days: int
    bulk_rows: int
    shapes: tuple
    gradients: bool
    logo: bool
    watermark: bool
    formats: tuple
    csv_export: bool
    api: bool
    smart_rules: bool = False
    highlights: tuple = field(default_factory=tuple)

    @property
    def yearly_total(self) -> int:
        return self.yearly_monthly * 12


ALL_SHAPES = ("Square", "Rounded", "Dots", "Gapped", "Vertical bars", "Horizontal bars")

PLANS: dict[str, Plan] = {
    "free": Plan("free", "Free", "Try it, no card needed", 0, 0, 2, 7, 0,
                 ("Square", "Rounded"), False, False, True, ("PNG",), False, False,
                 highlights=("Unlimited static QR codes", "2 dynamic QR codes", "Unlimited scans, never capped",
                             "Live scan history (7 days)", "Safety score for every destination",
                             "Watermark + short branded page on scan")),
    "starter": Plan("starter", "Starter", "For creators & small shops", 249, 199, 10, 30, 0,
                    ALL_SHAPES, False, True, False, ("PNG", "JPG", "SVG"), False, False,
                    highlights=("10 dynamic QR codes", "30-day scan history & analytics", "No watermark, direct redirect",
                                "Trust-preview page with your name", "UTM auto-tagging", "Logo, all shapes, PNG / JPG / SVG")),
    "pro": Plan("pro", "Pro", "For growing businesses", 699, 549, 50, 365, 500,
                ALL_SHAPES, True, True, False, ("PNG", "JPG", "SVG", "PDF"), True, False, True,
                highlights=("50 dynamic QR codes", "1-year history, unique visitors, heatmap",
                            "Smart routing: device, schedule, scan limit, A/B", "Password-protected codes",
                            "Destination link-health monitor", "Gradients, bulk (500 rows), CSV export")),
    "business": Plan("business", "Business", "For teams & agencies", 1799, 1499, 500, 3650, 5000,
                     ALL_SHAPES, True, True, False, ("PNG", "JPG", "SVG", "PDF"), True, True, True,
                     highlights=("500 dynamic QR codes", "10-year analytics history", "Everything in Pro",
                                 "Bulk generator (5,000 rows)", "API access (coming soon)", "Priority support")),
}

ORDER = ["free", "starter", "pro", "business"]
COUPONS = {"LAUNCH20": 20, "WELCOME10": 10}   # % off, demo coupons


def get_plan(key: str) -> Plan:
    return PLANS.get(key, PLANS["free"])


def price_for(plan: Plan, period: str, coupon: str | None = None) -> int:
    base = plan.yearly_total if period == "yearly" else plan.monthly
    pct = COUPONS.get((coupon or "").strip().upper(), 0)
    return round(base * (100 - pct) / 100)
