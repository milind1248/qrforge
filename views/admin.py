import pandas as pd
import streamlit as st

from core import auth, db
from core.plans import ORDER, PLANS

user = auth.current_user()
if user["role"] != "admin":
    st.error("Admins only.")
    st.stop()

st.title("Admin console")
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
t1, t2, t3, t4 = st.tabs(["Users", "Payments", "Plan mix", f"Abuse reports ({len(open_reports)})"])
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
    st.dataframe(pd.DataFrame(pays), width="stretch", hide_index=True) if pays else st.caption("No payments yet.")
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
