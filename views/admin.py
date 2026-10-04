from core import license as _license

_license.require()
import pandas as pd
import streamlit as st

from core import auth, db, notify, upi
from core.plans import ORDER, PLANS

user = auth.current_user()
if user["role"] != "admin":
    st.error("Admins only.")
    st.stop()

st.title("Admin console")
if msg := st.session_state.pop("flash", None):
    st.success(msg)
users, pays, stats = db.list_users(), db.all_payments(), db.platform_stats()
paid_users = [u for u in users if u["plan"] != "free"]
mrr = sum(PLANS[u["plan"]].yearly_monthly if u["period"] == "yearly" else PLANS[u["plan"]].monthly for u in paid_users)
revenue = sum(p["amount"] for p in pays if p["status"] == "paid")

m = st.columns(5)
m[0].metric("Users", stats["users"])
m[1].metric("Paying", len(paid_users))
m[2].metric("MRR", f"₹{mrr:,}")
m[3].metric("Lifetime revenue", f"₹{revenue:,}")
m[4].metric("Total scans", stats["scans"])

reports = db.list_reports()
open_reports = [r for r in reports if r["status"] == "open"]
claims = db.list_pending_claims()
t0, t1, t2, t3, t4 = st.tabs([f"Payment claims ({len(claims)})", "Users", "Payments", "Plan mix", f"Abuse reports ({len(open_reports)})"])
with t1:
    df = pd.DataFrame(users)
    st.dataframe(df, width="stretch", hide_index=True)
    st.subheader("Change a user's plan")
    c1, c2, c3 = st.columns([2, 1, 1])
    target = c1.selectbox("User", users, format_func=lambda u: u["email"])
    newplan = c2.selectbox("Plan", ORDER, index=ORDER.index(target["plan"]))
    per = c3.selectbox("Period", ["monthly", "yearly"])
    if st.button("Apply", type="primary"):
        db.set_plan(target["id"], newplan, per if newplan != "free" else None)
        st.success("Plan updated.")
        st.rerun()
with t2:
    if pays:
        st.dataframe(pd.DataFrame(pays), width="stretch", hide_index=True)
    else:
        st.caption("No payments yet.")
with t3:
    mix = pd.Series([u["plan"] for u in users]).value_counts().reindex(ORDER, fill_value=0)
    st.bar_chart(mix, color="#4F46E5")
with t4:
    if not reports:
        st.caption("No reports. Visitors can report a code from the trust page shown before redirect.")
    for r in reports:
        with st.expander(f"#{r['id']} · {r['reason']} · code {r['short_code']} · {r['status']}"):
            st.write(f"Owner: {r['owner']} · Destination: `{r['dest']}` · Reported {r['created_at']}")
            if r["note"]:
                st.write(f"Note: {r['note']}")
            c1, c2, c3 = st.columns(3)
            if c1.button("Disable code", key=f"rd{r['id']}"):
                db.set_qr_active_admin(r["qr_id"], False)
                db.set_report_status(r["id"], "actioned")
                st.rerun()
            if c2.button("Dismiss", key=f"rx{r['id']}"):
                db.set_report_status(r["id"], "dismissed")
                st.rerun()

with t0:
    st.subheader("Pending UPI payment claims")
    if not claims:
        st.caption("No claims waiting for review.")
    for c in claims:
        from core.plans import get_plan, price_for
        exp = price_for(get_plan(c["plan"]), c["period"], c["coupon"])
        flag = "" if int(c["amount"]) == exp else "  ⚠️ amount mismatch"
        with st.expander(f"#{c['id']} · {c['email']} · {c['plan'].title()} ({c['period']}) · ₹{int(c['amount']):,}{flag}", expanded=True):
            l, r = st.columns([2, 1])
            with l:
                st.write(f"**User:** {c['name']} ({c['email']})")
                st.write(f"**Plan:** {c['plan'].title()} · {c['period']} · expected ₹{exp:,}, paid ₹{int(c['amount']):,}"
                         + (f" · coupon {c['coupon']}" if c["coupon"] else ""))
                st.write(f"**Payment date:** {c['pay_date']} · **UPI ref:** {c['txn_ref'] or '-'} · **Submitted:** {c['created_at']}")
                if c["notes"]:
                    st.write(f"**Notes:** {c['notes']}")
                reason = st.text_input("Rejection reason (optional)", key=f"rr{c['id']}")
                a1, a2 = st.columns(2)
                if a1.button("Approve and activate plan", key=f"ap{c['id']}", type="primary", width="stretch"):
                    row = db.approve_claim(c["id"], user["email"])
                    if row:
                        notify.on_claim_decision({"email": c["email"], "name": c["name"]}, c["plan"], c["period"], True)
                    st.session_state["flash"] = f"Approved. {c['email']} is now on {c['plan'].title()}."
                    st.rerun()
                if a2.button("Reject", key=f"rj{c['id']}", width="stretch"):
                    row = db.reject_claim(c["id"], user["email"], reason)
                    if row:
                        notify.on_claim_decision({"email": c["email"], "name": c["name"]}, c["plan"], c["period"], False, reason)
                    st.session_state["flash"] = "Claim rejected."
                    st.rerun()
            with r:
                shot = db.get_claim_screenshot(c["id"])
                if shot and shot["screenshot"]:
                    import base64
                    st.image(base64.b64decode(shot["screenshot"]), caption="Payment screenshot", width="stretch")
    st.divider()
    st.subheader("Payment QR code")
    cur_qr = upi.get_payment_qr()
    if cur_qr:
        st.image(cur_qr, caption="Current UPI QR (shown blurred to users until they tap Show QR)", width=200)
    else:
        st.warning("No payment QR configured yet. Users cannot pay until you upload one.")
    new_qr = st.file_uploader("Upload / replace your UPI QR image", type=["png", "jpg", "jpeg"], key="qr_up")
    if new_qr and st.button("Save payment QR", type="primary"):
        try:
            upi.save_payment_qr(new_qr.getvalue())
            st.success("Payment QR saved.")
            st.rerun()
        except Exception:  # noqa: BLE001
            st.error("That file is not a valid image.")
