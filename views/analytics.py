from core import license as _license

_license.require()
import altair as alt
import pandas as pd
import streamlit as st

from core import auth, db
from core.plans import get_plan
from core.ui import lock_note

user = auth.current_user()
plan = get_plan(user["plan"])

st.title("Scan analytics")
st.caption(f"Your {plan.name} plan keeps {plan.analytics_days:,} days of scan history. Scans are never capped on any plan.")

qrs = [q for q in db.list_qrs(user["id"]) if q["is_dynamic"]]
if not qrs:
    st.info("Analytics are available for dynamic QR codes. Create one to start tracking scans.", icon=":material/insights:")
    st.page_link("views/home.py", label="Create a dynamic QR code", icon=":material/add:")
    st.stop()

ZONES = {"India (IST)": "Asia/Kolkata", "UTC": "UTC", "UK": "Europe/London", "UAE": "Asia/Dubai",
         "Singapore": "Asia/Singapore", "US East": "America/New_York"}
campaigns = sorted({q["campaign"] for q in qrs if q["campaign"]})

f1, f2, f3, f4 = st.columns([2, 1.3, 1.2, 1.2])
choice = f1.selectbox("QR code", ["All dynamic codes"] + [q["name"] for q in qrs])
camp = f2.selectbox("Campaign", ["All"] + campaigns)
periods = [d for d in (7, 30, 90, 365) if d <= plan.analytics_days] or [plan.analytics_days]
rng = f3.selectbox("Period", periods, format_func=lambda d: f"Last {d} days")
zone = ZONES[f4.selectbox("Time zone", list(ZONES))]

df = pd.DataFrame(db.scans_for_user(user["id"], plan.analytics_days))
if df.empty:
    st.info("No scans yet. Open one of your dynamic codes (or scan it with a phone) and it will appear here within seconds.")
    st.stop()

df["ts"] = pd.to_datetime(df["ts"]).dt.tz_localize("UTC").dt.tz_convert(zone)
df["visitor"] = df["visitor"].fillna("unknown")
df["new_visitor"] = ~df.duplicated(["qr_id", "visitor"])  # first sighting within retention window
df["region"] = df["lang"].fillna("unknown").str.extract(r"-([A-Za-z]{2})$")[0].str.upper().fillna("n/a")
df["outcome"] = df["outcome"].fillna("redirect")
cutoff = pd.Timestamp.now(tz=zone) - pd.Timedelta(days=rng)
view = df[df["ts"] >= cutoff]
if choice != "All dynamic codes":
    view = view[view["qr_name"] == choice]
if camp != "All":
    view = view[view["campaign"] == camp]
if view.empty:
    st.info("No scans match these filters.")
    st.stop()

view = view.assign(day=view["ts"].dt.date, hour=view["ts"].dt.hour, weekday=view["ts"].dt.day_name())
uniq = int(view["new_visitor"].sum())
peak = view["hour"].mode().iat[0]
m = st.columns(5)
m[0].metric("Total scans", len(view))
m[1].metric("Unique visitors", uniq if plan.smart_rules else "Pro", help="Approximate: anonymous hash of browser + language. No IP address is stored.")
m[2].metric("Returning scans", f"{100 - round(100 * uniq / len(view))}%" if plan.smart_rules else "Pro")
m[3].metric("Top device", view["device"].mode().iat[0])
m[4].metric("Peak hour", f"{peak:02d}:00")

t_over, t_hist, t_when, t_test = st.tabs([":material/monitoring: Overview", ":material/history: Scan history",
                                          ":material/schedule: When & where", ":material/science: A/B & outcomes"])

with t_over:
    daily = view.groupby("day").size()
    daily = daily.reindex(pd.date_range(daily.index.min(), daily.index.max()).date, fill_value=0)
    st.subheader("Scans over time")
    st.area_chart(daily.rename("scans"), color="#4F46E5")
    a, b, c = st.columns(3)
    for col, field, title in ((a, "device", "Device"), (b, "os", "Operating system"), (c, "browser", "Browser")):
        with col:
            st.subheader(title)
            st.bar_chart(view[field].value_counts(), color="#7C3AED", horizontal=True)
    st.subheader("Top QR codes")
    st.dataframe(view.groupby("qr_name").agg(scans=("ts", "size"), unique=("new_visitor", "sum"),
                                              last_scan=("ts", "max")).sort_values("scans", ascending=False),
                 width="stretch")


def history_table(frame: pd.DataFrame, limit: int = 500):
    h = frame.sort_values("ts", ascending=False).head(limit)
    show = pd.DataFrame({
        "When": h["ts"].dt.strftime("%d %b %Y, %H:%M:%S"), "QR code": h["qr_name"], "Campaign": h["campaign"].fillna(""),
        "Device": h["device"], "OS": h["os"], "Browser": h["browser"], "Region": h["region"],
        "Visitor": h["new_visitor"].map({True: "New", False: "Returning"}),
        "Result": h["outcome"] + h["variant"].fillna("").map(lambda v: f" ({v})" if v else ""),
    })
    st.dataframe(show, width="stretch", hide_index=True)


with t_hist:
    st.caption("Every scan with time, device and result. Newest first. Times shown in the selected time zone.")
    live = st.toggle("Live updates (refresh every 5 s)", value=False)

    def render_history():
        fresh = pd.DataFrame(db.scans_for_user(user["id"], plan.analytics_days))
        if fresh.empty:
            return
        fresh["ts"] = pd.to_datetime(fresh["ts"]).dt.tz_localize("UTC").dt.tz_convert(zone)
        fresh["visitor"] = fresh["visitor"].fillna("unknown")
        fresh["new_visitor"] = ~fresh.duplicated(["qr_id", "visitor"])
        fresh["region"] = fresh["lang"].fillna("").str.extract(r"-([A-Za-z]{2})$")[0].str.upper().fillna("n/a")
        fresh["outcome"] = fresh["outcome"].fillna("redirect")
        fv = fresh[fresh["ts"] >= pd.Timestamp.now(tz=zone) - pd.Timedelta(days=rng)]
        if choice != "All dynamic codes":
            fv = fv[fv["qr_name"] == choice]
        if camp != "All":
            fv = fv[fv["campaign"] == camp]
        st.metric("Scans in view", len(fv))
        history_table(fv)

    if live:
        st.fragment(render_history, run_every="5s")()
    else:
        render_history()
    if plan.csv_export:
        out = view.drop(columns=["day", "hour", "weekday"]).assign(ts=lambda d: d["ts"].dt.tz_localize(None))
        st.download_button("Download full scan log (CSV)", out.to_csv(index=False), "scan_history.csv", "text/csv",
                           icon=":material/download:")
    else:
        lock_note("CSV export is on the Pro plan.")

with t_when:
    if not plan.smart_rules:
        lock_note("The scan heatmap and region breakdown are on the Pro plan.")
    else:
        st.subheader("Best time to be scanned")
        order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        grid = view.groupby(["weekday", "hour"]).size().reset_index(name="scans")
        chart = alt.Chart(grid).mark_rect(cornerRadius=3).encode(
            x=alt.X("hour:O", title="Hour of day"), y=alt.Y("weekday:O", sort=order, title=None),
            color=alt.Color("scans:Q", scale=alt.Scale(range=["#EEF2FF", "#4F46E5"]), title="Scans"),
            tooltip=["weekday", "hour", "scans"]).properties(height=260)
        st.altair_chart(chart, width="stretch")
        best = grid.sort_values("scans", ascending=False).iloc[0]
        st.success(f"Most scans happen on **{best['weekday']}s around {int(best['hour']):02d}:00**. "
                   "Refresh offers and staff your counter around then.", icon=":material/lightbulb:")
        st.subheader("Visitor region (from browser language)")
        st.caption("Estimated from the browser's language setting, for example en-IN means India. No IP lookup is made.")
        st.bar_chart(view["region"].value_counts().head(10), color="#7C3AED", horizontal=True)

with t_test:
    if not plan.smart_rules:
        lock_note("A/B testing and smart-routing outcomes are on the Pro plan.")
    else:
        st.subheader("Routing outcomes")
        st.dataframe(view["outcome"].value_counts().rename("scans"), width="stretch")
        ab = view[view["variant"].notna()]
        if ab.empty:
            st.info("No A/B data yet. Add two or more destinations under My QR codes → Smart routing.")
        else:
            st.subheader("A/B split results")
            res = ab.groupby(["qr_name", "variant"]).agg(scans=("ts", "size"), unique=("new_visitor", "sum")).reset_index()
            st.dataframe(res, width="stretch", hide_index=True)
            st.caption("Tip: run the test until each variant has at least 100 scans before picking a winner.")
