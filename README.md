# QRForge: QR code generator SaaS (Streamlit)

Original implementation inspired by the feature set of dynamic-QR products. No third-party code or assets.

## Licensing
The app requires `LICENSE_KEY` (Streamlit secret or env var; `[deploy] license_key` also accepted). Without a valid key every page, scan link and the DB layer refuse to run. Only a salted hash of the key is in the code. The repository is private.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```
The SQLite database is created automatically at `data/qrforge.db`. **The first account you register becomes the admin** (Admin page appears under "My account").

## Features
- 11 QR types: URL, text, Wi-Fi, contact card, email, SMS, phone, WhatsApp, UPI payment, location, calendar event
- Design: colours, gradients (Pro), 6 dot styles, 3 corner styles, error correction, centre logo, contrast warning
- Downloads: PNG / JPG / SVG / PDF (gated by plan); free plan gets a watermark
- **Dynamic QR**: short link `BASE_URL/?r=<code>`; editable destination, pause/resume, scan logging (device, OS, browser)
- Analytics (plan-limited history, CSV export on Pro), bulk CSV to ZIP generator, QR scanner (image / camera)
- Auth (bcrypt), plans + checkout (mock gateway, coupons `LAUNCH20`, `WELCOME10`), billing history, admin console (users, MRR, revenue, plan changes)

## What makes it different (from market research on user complaints)
- **Never-dead promise:** printed dynamic codes keep redirecting after cancellation or limits (top complaint about competitors: codes die when the plan lapses or scan caps hit). Premium rules pause; the base destination stays live. No scan caps on any plan.
- **Scan history:** live feed (time, device, OS, browser, region, new/returning visitor, routing result), time-zone aware, CSV export (Pro).
- **Analytics:** unique visitors (anonymous hash, no IP stored), weekday x hour heatmap with "best time" insight, region from browser language, per-campaign filter, A/B results.
- **Smart routing (Pro):** per-device links (iOS / Android / desktop), A/B split, schedule, scan limit with fallback (coupons), password-protected codes, UTM auto-tagging (Starter+).
- **Quishing defence:** offline destination safety score on every link, trust-preview page showing the real domain and publisher name, no auto-redirect for risky links, blocked `javascript:`/`data:` links, visitor "Report this code" + admin takedown queue.
- **Scan-reliability stress test:** simulates blur, small size, noise, tilt, JPEG compression and fading, plus print-size advice by scanning distance.
- **Link-health check** (SSRF-safe) and **one-click backup** of all codes.

## Plans (INR, edit in `core/plans.py`)
| Plan | Monthly | Yearly (per month) | Dynamic QR | Analytics | Bulk |
|---|---|---|---|---|---|
| Free | 0 | 0 | 2 | 7 days | no |
| Starter | 249 | 199 | 10 | 30 days | no |
| Pro | 699 | 549 | 50 | 1 year | 500 |
| Business | 1799 | 1499 | 500 | 10 years | 5,000 |

## Deploy to Streamlit Community Cloud
1. Push the `qrforge/` folder to GitHub, set main file `app.py`.
2. In app Secrets set `BASE_URL = "https://<your-app>.streamlit.app"` so dynamic QR codes point at the live app.
3. **Important:** Community Cloud storage is ephemeral. SQLite data resets on restart, so move to Supabase before real customers (below).

## Supabase (Postgres) backend: implemented
Set `DATABASE_URL` (env var or Streamlit secret) to your Supabase **pooler** connection string and the app switches from SQLite to Postgres automatically: tables are created on first start (see `supabase/schema.sql`), and row-level security is enabled on every table so the public anon API cannot read them. Verified locally against PostgreSQL 17.
Supabase Auth is not used yet; accounts are still in the `users` table with bcrypt hashes.

## Email notifications
With `SMTP_SENDER` + `SMTP_PASSWORD` set, QRForge emails: a welcome message and admin copy on signup, and a "new login" alert to the user (device, OS, browser, time) with an admin copy to `OWNER_EMAIL`. Login alerts are rate-limited to one per user per 10 minutes, sent in a background thread, and never block or break login.

## Original migration notes
- `core/db.py` is the only module that touches storage. Re-implement the same functions against Supabase Postgres (tables mirror `SCHEMA`).
- `core/auth.py`: replace with Supabase Auth (`sign_up`, `sign_in_with_password`) and store the user id in `st.session_state.uid`.
- Add cookie-based session persistence (e.g. `extra-streamlit-components`) so refresh keeps users signed in. Currently a browser refresh logs out.
- `core/payments.py`: add Razorpay (UPI/cards) or Stripe; activate plans only from a verified webhook.

## Known limits (Streamlit architecture)
- Dynamic redirects go through the Streamlit app (JS redirect after a short load), so scans are slower than a dedicated redirect service. For production scale, put a tiny FastAPI/Cloudflare Worker redirect in front reading the same table.
- Scan analytics have no geo-location (no IP lookup yet).
- The centre logo is not stored for saved codes; it applies to downloads made at creation time.
- Add GST invoices, email verification and password reset before launch.
