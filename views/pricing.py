from core import license as _license

_license.require()
import streamlit as st

from datetime import date

from core import auth, db, notify, payments, upi
from core.config import PAYMENT_PROVIDER
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
            st.session_state["sub_plan"] = key
            st.session_state.pop("qr_revealed", None)

def subscribe_section():
    """Manual UPI flow: blurred QR -> reveal -> pay -> upload screenshot -> admin approves."""
    if not user:
        return
    pending = db.get_pending_claim(user["id"])
    plan_key = st.session_state.get("sub_plan")
    if not pending and not plan_key:
        return
    st.divider()
    if pending:
        st.warning(f"Your **{pending['plan'].title()}** ({pending['period']}) payment claim submitted on "
                   f"{pending['created_at'][:10]} is awaiting review. Your plan updates automatically once it is approved. "
                   "You will get an email.", icon=":material/hourglass_top:")
        return
    p = PLANS[plan_key]
    st.subheader(f"Subscribe to {p.name}")
    if PAYMENT_PROVIDER == "mock":
        amt = price_for(p, period)
        st.caption("Test mode: no real payment is taken.")
        if st.button(f"Activate {p.name} (test) ₹{amt:,}", type="primary"):
            payments.charge(user["id"], plan_key, period)
            st.session_state.pop("sub_plan", None)
            st.session_state["flash"] = f"You are now on the {p.name} plan."
            st.rerun()
        return

    coupon = st.text_input("Coupon code (optional)", placeholder="LAUNCH20", key="sub_coupon")
    pct = COUPONS.get(coupon.strip().upper(), 0)
    if coupon and not pct:
        st.warning("Coupon not recognised.")
    expected = price_for(p, period, coupon if pct else None)
    st.markdown(f"**{p.name}** · billed **{period}** · amount to pay: **₹{expected:,}**" + (f"  ({pct}% off)" if pct else ""))

    qc1, qc2 = st.columns([1, 2], gap="large")
    qr = upi.get_payment_qr()
    with qc1:
        if qr:
            if st.session_state.get("qr_revealed"):
                st.image(qr, caption=f"Scan to pay ₹{expected:,} via any UPI app", width=240)
            else:
                st.image(upi.blurred(qr), width=240)
                st.caption("QR code hidden. Tap to reveal.")
                if st.button("Show QR Code", icon=":material/visibility:", type="primary", width="stretch", key="qr_btn"):
                    st.session_state["qr_revealed"] = True
                    st.rerun()
        else:
            st.info("The payment QR code is not configured yet. Please contact the site admin.")
    with qc2:
        st.markdown("**How to subscribe**\n\n1. Scan the QR code and pay via any UPI app.\n"
                    "2. Take a screenshot of the successful payment.\n3. Fill in the form below and upload the screenshot.\n"
                    "4. We verify it and activate your plan, usually within a day.")
    st.markdown("<div style='background:#FFF7ED;border-left:4px solid #F59E0B;padding:8px 12px;border-radius:8px;"
                "font-size:13px;color:#92400E;margin:8px 0'>⚠️ All payments are final and non-refundable. By submitting a payment "
                "claim you acknowledge that no refunds, full or partial, are issued for cancellation, downgrade or non-usage.</div>",
                unsafe_allow_html=True)
    with st.form("claim_form"):
        c1, c2 = st.columns(2)
        amount = c1.number_input("Amount paid (₹)", min_value=0.0, value=float(expected), step=1.0)
        pay_date = c2.date_input("Payment date", value=date.today(), max_value=date.today())
        ref = st.text_input("UPI transaction ID (optional)")
        shot = st.file_uploader("Payment screenshot", type=["png", "jpg", "jpeg"])
        notes = st.text_area("Notes (optional)", height=68)
        go = st.form_submit_button("Submit payment claim", type="primary", width="stretch")
    if go:
        if shot is None:
            st.error("Please upload a screenshot of the successful payment.")
        elif amount <= 0:
            st.error("Enter the amount you paid.")
        else:
            try:
                b64, mime = upi.prepare_screenshot(shot.getvalue())
            except Exception:  # noqa: BLE001
                st.error("That file is not a valid image. Upload a PNG or JPG screenshot.")
                st.stop()
            db.submit_claim(user["id"], plan_key, period, amount, coupon if pct else None, pay_date, ref, notes, b64, mime)
            import base64
            notify.on_claim_submitted(user, plan_key, period, int(round(amount)), expected, ref, str(pay_date), notes,
                                      base64.b64decode(b64), mime)
            st.session_state.pop("sub_plan", None)
            st.session_state.pop("qr_revealed", None)
            st.session_state["flash"] = "Submitted. We will review your payment and activate your plan shortly."
            st.rerun()


subscribe_section()

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
    "Event passes: active events / guests each": ["1 / 50", "3 / 300", "20 / 2,000", "100 / 20,000"],
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
    ("Can I get a refund?",
     "No. All payments are final and non-refundable. Here is why: QRForge is a digital service. The moment your payment is "
     "verified, your plan is activated and the resources behind it are reserved for you (dynamic-link hosting, scan tracking "
     "and analytics storage, and support). That cost is incurred immediately and cannot be recovered, and a digital service "
     "cannot be 'returned' like a physical product. "
     "To make sure you never pay for something that does not fit, you can try QR generation, the safety score and the scan "
     "test on the **Free plan** before buying, and you can cancel at any time so you are never charged again. Your printed "
     "dynamic codes also keep working after you cancel. The only exception is a genuine billing error on our side, such as "
     "a duplicate payment, which we will correct."),
]:
    with st.expander(q):
        st.write(a)
footer()
