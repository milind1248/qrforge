from core import license as _license

_license.require()
import streamlit as st

from core import auth, payments
from core.plans import COUPONS, ORDER, PLANS, get_plan, price_for
from core.ui import footer, hero

user = auth.current_user()
cur = user["plan"] if user else None

hero("Simple pricing that grows with you", "Start free. Upgrade when you need more dynamic codes, longer analytics or bulk tools.",
     "Prices in INR · GST extra · cancel any time")

if msg := st.session_state.pop("flash", None):
    st.success(msg)

period = st.segmented_control("Billing", ["monthly", "yearly"], default="yearly",
                              format_func=lambda x: "Monthly" if x == "monthly" else "Yearly · save ~20%",
                              key="bill_period") or "yearly"


@st.dialog("Checkout")
def checkout(plan_key: str):
    p = PLANS[plan_key]
    st.markdown(f"**{p.name}** plan · billed **{period}**")
    coupon = st.text_input("Coupon code (optional)", placeholder="LAUNCH20")
    pct = COUPONS.get(coupon.strip().upper(), 0)
    if coupon and not pct:
        st.warning("Coupon not recognised.")
    amt = price_for(p, period, coupon)
    if pct:
        st.success(f"{pct}% discount applied")
    st.metric("Total today", f"₹{amt:,}")
    st.caption("Test mode: no real payment is taken. A live gateway (Razorpay / Stripe) plugs in here.")
    if st.button(f"Pay ₹{amt:,}", type="primary", width="stretch"):
        payments.charge(user["id"], plan_key, period, coupon if pct else None)
        st.session_state["flash"] = f"You are now on the {p.name} plan. Thank you!"
        st.rerun()


cols = st.columns(4, gap="medium")
for col, key in zip(cols, ORDER):
    p = PLANS[key]
    hot = key == "pro"
    per = p.yearly_monthly if period == "yearly" else p.monthly
    strike = f'<span class="strike">₹{p.monthly:,}</span>' if period == "yearly" and p.monthly else ""
    lis = "".join(f"<li>{h}</li>" for h in p.highlights)
    badge = '<div class="badge">MOST POPULAR</div>' if hot else ""
    bill = f"₹{p.yearly_total:,} billed yearly" if period == "yearly" and p.monthly else "&nbsp;"
    with col:
        st.markdown(
            f'<div class="plan {"hot" if hot else ""}">{badge}<h3>{p.name}</h3><div class="tag">{p.tagline}</div>'
            f'<div class="price">₹{per:,}<small>/mo</small>{strike}</div>'
            f'<div class="tag">{bill}</div><ul>{lis}</ul></div>', unsafe_allow_html=True)
        st.write("")
        if key == "free":
            if user:
                st.button("Current plan" if cur == "free" else "Included", disabled=True, key="b_free", width="stretch")
            else:
                st.page_link("views/login.py", label="Start free", width="stretch")
        elif not user:
            st.page_link("views/login.py", label=f"Sign up for {p.name}", width="stretch")
        elif cur == key:
            st.button("Current plan", disabled=True, key=f"b_{key}", width="stretch")
        elif st.button(f"Choose {p.name}", key=f"b_{key}", type="primary" if hot else "secondary", width="stretch"):
            checkout(key)

st.write("")
st.subheader("Our promises")
pc = st.columns(4)
for c_, (ico, ttl, txt) in zip(pc, [
        ("♾️", "Never-dead codes", "Cancel any time. Your printed dynamic codes keep redirecting, always. No hostage-taking."),
        ("📈", "Scans are never capped", "No monthly scan limits on any plan. A busy week never breaks your campaign."),
        ("🛡️", "Safety built in", "Every destination gets a safety score, and visitors can see where a code leads."),
        ("📦", "Your data is portable", "Download a backup of all your codes and destinations whenever you like.")]):
    c_.markdown(f'<div class="card"><div class="feat-ico">{ico}</div><h4>{ttl}</h4><p>{txt}</p></div>', unsafe_allow_html=True)
st.write("")
st.subheader("Compare plans")
rows = {
    "Static QR codes": ["Unlimited"] * 4,
    "Dynamic QR codes": [str(PLANS[k].dynamic_limit) for k in ORDER],
    "Scan analytics history": ["7 days", "30 days", "1 year", "10 years"],
    "Live scan history": ["✓", "✓", "✓", "✓"],
    "Scan caps": ["None", "None", "None", "None"],
    "Direct redirect (no interstitial)": ["–", "✓", "✓", "✓"],
    "Trust page with your name": ["–", "✓", "✓", "✓"],
    "UTM auto-tagging": ["–", "✓", "✓", "✓"],
    "Unique visitors & scan heatmap": ["–", "–", "✓", "✓"],
    "Device routing, schedule, scan limit": ["–", "–", "✓", "✓"],
    "A/B split testing": ["–", "–", "✓", "✓"],
    "Password-protected codes": ["–", "–", "✓", "✓"],
    "Destination link-health check": ["–", "–", "✓", "✓"],
    "Watermark-free downloads": ["–", "✓", "✓", "✓"],
    "Logo in the centre": ["–", "✓", "✓", "✓"],
    "All dot styles": ["–", "✓", "✓", "✓"],
    "Gradient colours": ["–", "–", "✓", "✓"],
    "Download formats": ["PNG", "PNG, JPG, SVG", "+ PDF", "+ PDF"],
    "Bulk generator (rows)": ["–", "–", "500", "5,000"],
    "CSV analytics export": ["–", "–", "✓", "✓"],
    "API access": ["–", "–", "–", "Soon"],
}
import pandas as pd  # noqa: E402
st.dataframe(pd.DataFrame(rows, index=[PLANS[k].name for k in ORDER]).T, width="stretch")

st.subheader("Frequently asked questions")
for q, a in [
    ("What is the difference between static and dynamic QR codes?",
     "A static code stores your content directly, so it can never change or be tracked. A dynamic code stores a short link that "
     "redirects to your destination, so you can edit the destination later and see scan analytics."),
    ("Do my static QR codes expire?", "No. Static codes work forever, even if you cancel your account."),
    ("What happens to my printed codes if I cancel or downgrade?", "They keep working. Premium routing rules pause and visitors see a short QRForge trust page, but your base destination stays live. We never switch a printed code off to force you to pay."),
    ("Can I get a refund?", "Contact support within 7 days of purchase and we will refund you in full."),
]:
    with st.expander(q):
        st.write(a)
footer()
