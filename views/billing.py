from core import license as _license

_license.require()
import pandas as pd
import streamlit as st

from core import auth, db
from core.plans import get_plan

user = auth.current_user()
plan = get_plan(user["plan"])

st.title("Billing & plan")
if msg := st.session_state.pop("flash", None):
    st.success(msg)

_pend = db.get_pending_claim(user["id"])
if _pend:
    st.warning(f"Payment claim for **{_pend['plan'].title()}** ({_pend['period']}) submitted {_pend['created_at'][:10]} is awaiting review.", icon=":material/hourglass_top:")

c1, c2, c3 = st.columns(3)
c1.metric("Current plan", plan.name)
c2.metric("Billing", (user["period"] or "-").title())
c3.metric("Renews / expires", (user["plan_expires"] or "-")[:10])

used = db.count_dynamic(user["id"])
st.progress(min(used / plan.dynamic_limit, 1.0), text=f"Dynamic QR codes: {used} / {plan.dynamic_limit}")

a, b, _ = st.columns([1, 1, 2])
a.page_link("views/pricing.py", label="Change plan", icon=":material/workspace_premium:", width="stretch")
if user["plan"] != "free" and b.button("Cancel subscription", width="stretch"):
    db.set_plan(user["id"], "free")
    st.session_state["flash"] = "Subscription cancelled. You are back on the Free plan."
    st.rerun()

st.subheader("Payment history")
pay = db.payments_for_user(user["id"])
if pay:
    df = pd.DataFrame(pay)[["created_at", "plan", "period", "amount", "coupon", "status", "txn_ref"]]
    df.columns = ["Date", "Plan", "Period", "Amount (₹)", "Coupon", "Status", "Reference"]
    st.dataframe(df, width="stretch", hide_index=True)
else:
    st.caption("No payments yet.")
