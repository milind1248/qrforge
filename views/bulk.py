import io
import re
import zipfile

import pandas as pd
import streamlit as st

from core import auth, qr_engine as qe
from core.plans import get_plan
from core.ui import lock_note

user = auth.current_user()
plan = get_plan(user["plan"])

st.title("Bulk QR generator")
st.caption("Upload a CSV with a **data** column (URL or text) and an optional **name** column. Get all codes as a ZIP.")

if plan.bulk_rows == 0:
    lock_note("Bulk generation is available on Pro (500 rows) and Business (5,000 rows).")
    st.page_link("views/pricing.py", label="See plans", icon=":material/workspace_premium:")
    st.download_button("Download sample CSV", "name,data\nMenu,https://example.com/menu\nOffer,https://example.com/offer\n",
                       "sample.csv", "text/csv")
    st.stop()

st.caption(f"Your {plan.name} plan allows up to **{plan.bulk_rows:,}** rows per file.")
up = st.file_uploader("CSV file", type=["csv"])
c1, c2, c3 = st.columns(3)
fg = c1.color_picker("QR colour", "#0F172A")
bg = c2.color_picker("Background", "#FFFFFF")
shape = c3.selectbox("Dot style", list(plan.shapes))
st.download_button("Download sample CSV", "name,data\nMenu,https://example.com/menu\nOffer,https://example.com/offer\n",
                   "sample.csv", "text/csv")

if up:
    try:
        df = pd.read_csv(up)
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not read the file: {e}")
        st.stop()
    df.columns = [c.strip().lower() for c in df.columns]
    if "data" not in df.columns:
        st.error("The CSV needs a column called 'data'.")
        st.stop()
    df = df.dropna(subset=["data"])
    if len(df) > plan.bulk_rows:
        st.warning(f"Only the first {plan.bulk_rows:,} rows will be processed.")
        df = df.head(plan.bulk_rows)
    st.dataframe(df.head(10), width="stretch")
    if st.button(f"Generate {len(df):,} QR codes", type="primary"):
        style = {"fg": fg, "bg": bg, "shape": shape}
        buf, used = io.BytesIO(), set()
        bar = st.progress(0.0)
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for i, r in enumerate(df.itertuples(index=False), 1):
                base = re.sub(r"[^\w\-]+", "_", str(getattr(r, "name", "") or f"qr_{i}"))[:40] or f"qr_{i}"
                while base in used:
                    base += f"_{i}"
                used.add(base)
                blob, _ = qe.export(str(r.data), style, "PNG", False)
                z.writestr(f"{base}.png", blob)
                if i % 10 == 0:
                    bar.progress(i / len(df))
        bar.progress(1.0)
        st.success("Done!")
        st.download_button("Download ZIP", buf.getvalue(), "qrforge_bulk.zip", "application/zip", type="primary")
