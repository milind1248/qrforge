"""Builds the static, crawlable marketing site into site/public (HTML + sitemap + robots + llms.txt + OG image).
The Streamlit app itself renders in JavaScript inside an iframe on streamlit.app, which search engines and AI crawlers read poorly; these plain-HTML
pages carry the keywords, structured data and answers, and send visitors to the app.

    python site/build_site.py                       # uses SITE_URL below
    SITE_URL=https://www.yourdomain.com python site/build_site.py
"""
import html
import json
import os
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "public"
SITE_URL = os.environ.get("SITE_URL", "https://milind1248.github.io/qrforge").rstrip("/")
APP_URL = os.environ.get("APP_URL", "https://qrcodescan.streamlit.app").rstrip("/")
BRAND = "QR Sugi"
TODAY = date.today().isoformat()
E = html.escape

PLANS = [("Free", "₹0", "Unlimited static QR codes, 2 dynamic QR codes, 7-day scan history, 1 active event up to 50 guests"),
         ("Starter", "₹249/month (₹199/month billed yearly)", "10 dynamic QR codes, 30-day analytics, your logo in the centre, PNG/JPG/SVG, 3 events up to 300 guests"),
         ("Pro", "₹699/month (₹549/month billed yearly)", "50 dynamic QR codes, 1-year analytics and heatmap, smart routing, password-protected codes, bulk CSV (500 rows), 20 events up to 2,000 guests"),
         ("Business", "₹1,799/month (₹1,499/month billed yearly)", "500 dynamic QR codes, 10-year analytics, bulk CSV (5,000 rows), 100 events up to 20,000 guests, priority support")]

# ----------------------------------------------------------------------------------------------- page content
PAGES = {
    "free-qr-code-generator": dict(
        title="Free QR Code Generator India: No Signup, No Expiry | QR Sugi",
        desc="Make a QR code free in seconds: website, text, Wi-Fi, contact card, WhatsApp, UPI. Static QR codes never expire. Custom colours and PNG download. No signup.",
        h1="Free QR code generator for India",
        intro="QR Sugi is a free QR code generator. Pick what the code should do, type the details, and download a QR code that works on any phone camera. Static QR codes are free forever, never expire, and do not depend on our servers.",
        sections=[
            ("What you can create", "<ul><li>Website link (URL) QR codes</li><li>Plain text and contact card (vCard) QR codes</li><li>Wi-Fi QR codes that connect guests without typing the password</li><li>WhatsApp chat, SMS, phone call and email QR codes</li><li>UPI payment QR codes with your UPI ID and optional amount</li><li>Location (Google Maps) and calendar event QR codes</li></ul>"),
            ("How to make a QR code in 3 steps", "<ol><li>Open the <a href=\"{app}\">QR Sugi generator</a> and choose the QR type.</li><li>Enter your link or details. The preview updates as you type.</li><li>Choose colours and download the PNG. Paid plans add SVG, PDF and your logo.</li></ol>"),
            ("Static or dynamic?", "<p>A <strong>static</strong> QR code stores the data inside the pattern itself, so it keeps working forever and even if our website is offline. A <strong>dynamic</strong> QR code points to a short link that you can edit later and that records scans. Read more in <a href=\"dynamic-qr-code-generator.html\">dynamic QR codes</a>.</p>"),
            ("Test before you print", "<p>QR Sugi includes a scan reliability test that simulates blur, small size, noise and tilt, and tells you the minimum print size for the distance people will scan from.</p>"),
        ],
        faqs=[("Is the QR code generator really free?", "Yes. Creating and downloading static QR codes is free with no signup. Free downloads carry a small QR Sugi watermark; paid plans remove it."),
              ("Do free QR codes expire?", "No. Static QR codes never expire because the information is stored in the code itself."),
              ("Do I need an account?", "No account is needed to create and download a static QR code. An account lets you save codes and create dynamic ones.")]),
    "upi-qr-code-generator": dict(
        title="UPI QR Code Generator: Free Payment QR for Any UPI ID | QR Sugi",
        desc="Create a UPI payment QR code for your shop, invoice or table. Enter your UPI ID, payee name and optional amount. Works with PhonePe, Google Pay, Paytm and BHIM.",
        h1="UPI QR code generator",
        intro="A UPI QR code lets customers pay you by scanning with any UPI app, including PhonePe, Google Pay, Paytm and BHIM. Enter your UPI ID and name, add an amount if it is fixed, and download the code.",
        sections=[
            ("What goes into a UPI QR code", "<p>The code holds a standard <code>upi://pay</code> link with your UPI ID (VPA), payee name, optional amount and an optional note. Because it is a static QR code, it works without any server and never expires.</p>"),
            ("Where to use it", "<ul><li>Shop counters and market stalls</li><li>Restaurant tables and takeaway packaging</li><li>Invoices, bills and donation boxes</li><li>Tuition fees, society maintenance and event tickets</li></ul>"),
            ("Steps", "<ol><li>Open the <a href=\"{app}\">generator</a> and select <em>UPI payment</em>.</li><li>Enter your UPI ID such as <code>shop@bank</code>, the payee name, and an amount if the price is fixed.</li><li>Download the PNG and print it at least 3 cm wide for counter use. Use the built-in scan test to check it.</li></ol>"),
            ("Safety tip", "<p>Always scan your own code with a different phone and confirm the payee name shown by the UPI app before you print or share it.</p>"),
        ],
        faqs=[("Does a UPI QR code work with all UPI apps?", "Yes. It uses the standard UPI payment link that PhonePe, Google Pay, Paytm, BHIM and bank apps understand."),
              ("Can I set a fixed amount?", "Yes. Add an amount to pre-fill it, or leave it empty so the customer enters the amount."),
              ("Is there any fee?", "QR Sugi does not charge for the code and does not touch your money. Payments go directly to your UPI ID.")]),
    "whatsapp-qr-code-generator": dict(
        title="WhatsApp QR Code Generator: Chat Link with Message | QR Sugi",
        desc="Create a WhatsApp QR code that opens a chat with your number and a pre-filled message. Free, no signup, great for shops, enquiries and orders.",
        h1="WhatsApp QR code generator",
        intro="A WhatsApp QR code opens a chat with your number as soon as someone scans it, optionally with a message already typed. Customers do not need to save your number.",
        sections=[
            ("Good uses", "<ul><li>Take orders and enquiries from a poster or shop window</li><li>Support and booking requests with a pre-filled message such as \"Hi, I want to book\"</li><li>Business cards and brochures</li></ul>"),
            ("How to create it", "<ol><li>Open the <a href=\"{app}\">generator</a> and choose <em>WhatsApp</em>.</li><li>Enter the number with country code, for example 919876543210 for India.</li><li>Optionally write the first message, then download the code.</li></ol>"),
            ("Tip", "<p>Use a dynamic QR code if you may change the number or message later without reprinting. See <a href=\"dynamic-qr-code-generator.html\">dynamic QR codes</a>.</p>"),
        ],
        faqs=[("Which number format should I use?", "Use the full number with country code and no plus sign or spaces, for example 919876543210."),
              ("Can I pre-fill the message?", "Yes. The message you add appears in the chat box ready to send.")]),
    "wifi-qr-code-generator": dict(
        title="Wi-Fi QR Code Generator: Share Wi-Fi Without Typing | QR Sugi",
        desc="Create a Wi-Fi QR code so guests join your network by scanning. Supports WPA/WPA2, WEP and open networks, including hidden SSIDs. Free, no signup.",
        h1="Wi-Fi QR code generator",
        intro="A Wi-Fi QR code connects a phone to your network when scanned. Guests in homes, cafes, offices and hotels never have to read out or type a long password.",
        sections=[
            ("What you need", "<p>The network name (SSID), the password, and the security type (WPA/WPA2, WEP or none). You can also mark the network as hidden.</p>"),
            ("Steps", "<ol><li>Open the <a href=\"{app}\">generator</a> and choose <em>Wi-Fi</em>.</li><li>Enter the SSID and password, and pick the security type.</li><li>Download and place the code near the router or on a table card.</li></ol>"),
            ("Privacy", "<p>Wi-Fi codes are static: the password lives only inside the code you print, so keep the printed code where only your guests can see it.</p>"),
        ],
        faqs=[("Does it work on iPhone and Android?", "Yes. Both read Wi-Fi QR codes with the built-in camera app."),
              ("What if I change the Wi-Fi password?", "Make a new code. A static Wi-Fi code contains the old password.")]),
    "vcard-qr-code-generator": dict(
        title="vCard QR Code Generator: Digital Business Card QR | QR Sugi",
        desc="Make a contact card QR code with your name, phone, email, company and address. Scanners can save you to their phone in one tap. Free and static.",
        h1="vCard QR code generator (contact card)",
        intro="A contact card QR code stores your details in the standard vCard format. When someone scans it, their phone offers to save your contact, so your name, number, email, company and website are added without typing.",
        sections=[
            ("Fields you can include", "<ul><li>First and last name</li><li>Phone and email</li><li>Company and job title</li><li>Website and address</li></ul>"),
            ("Where to print it", "<p>Business cards, email signatures, stall banners, conference badges and shop windows.</p>"),
            ("Steps", "<ol><li>Open the <a href=\"{app}\">generator</a> and choose <em>Contact card</em>.</li><li>Fill in your details.</li><li>Download the code. Keep the printed size at least 2.5 cm so phones read it quickly.</li></ol>"),
        ],
        faqs=[("Does it expire?", "No. The details are inside the code, so it works forever. To change details later, make a new code."),
              ("Can I add my logo?", "Yes, on Starter and higher plans you can add a logo in the centre.")]),
    "dynamic-qr-code-generator": dict(
        title="Dynamic QR Code Generator with Scan Analytics | QR Sugi",
        desc="Create editable dynamic QR codes: change the destination after printing, pause codes, and track scans by day, device and browser. Free plan includes 2.",
        h1="Dynamic QR code generator with analytics",
        intro="A dynamic QR code points to a short QR Sugi link that redirects to your destination. The printed code never changes, but you can change where it goes at any time and see how many people scanned it.",
        sections=[
            ("What dynamic codes add", "<ul><li>Edit the destination without reprinting</li><li>Pause or resume a code</li><li>Scan history by date, device, operating system and browser</li><li>Destination safety score and link health checks</li><li>On higher plans: smart rules by device or schedule, password protection and A/B destinations</li></ul>"),
            ("Never-dead promise", "<p>If you cancel a paid plan or reach a limit, your printed dynamic codes keep redirecting to the base destination. Premium rules pause, but the code does not die.</p>"),
            ("Important to know", "<p>Dynamic codes depend on the QR Sugi redirect being online. For information that should work forever with no dependency, such as Wi-Fi or a contact card, use a <a href=\"free-qr-code-generator.html\">static QR code</a>.</p>"),
            ("Plans", "<p>The free plan includes 2 dynamic QR codes. See <a href=\"pricing.html\">pricing</a>.</p>"),
        ],
        faqs=[("What is the difference between static and dynamic QR codes?", "A static code holds the data itself and never changes. A dynamic code holds a short link, so you can edit the destination and track scans."),
              ("Can I track how many people scanned my QR code?", "Yes, dynamic codes record scans with date, device, operating system and browser. Visitor IP addresses are not stored.")]),
    "event-registration-qr-code": dict(
        title="Event Registration & QR Code Entry Pass Software | QR Sugi",
        desc="Create an event, take free or UPI-paid bookings, email each guest a QR pass, scan entries at the gate with a phone, and export attendance to Excel.",
        h1="Event registration with QR code passes",
        intro="QR Sugi Events lets you create an event, collect bookings, give every attendee a unique QR pass, and check people in at the door with a phone camera. The organizer dashboard shows live attendance and exports to Excel.",
        sections=[
            ("How it works", "<ol><li>Create the event with name, venue, date, time, capacity and registration deadline. Choose free or paid (UPI, you approve each payment).</li><li>Share the booking link. Attendees enter their details and receive a QR pass by email, which they can also download as PNG or PDF, print, or send on WhatsApp.</li><li>At the gate, staff open the scanner link with a PIN and scan passes. The result is clear: valid, already used, cancelled or invalid.</li><li>Open the dashboard to see registrations and live attendance, search by name, email, booking ID or status, and export the attendee list or check-in records to Excel.</li></ol>"),
            ("Features", "<ul><li>Capacity limits that cannot be exceeded, even when many people book at once</li><li>One check-in per pass, even if two phones scan at the same instant</li><li>Attendee self-cancellation with confirmation, and organizer add or cancel for anyone</li><li>Co-organizers and a staff PIN for volunteers</li><li>Booking pages and passes in English, Hindi and Marathi</li></ul>"),
            ("Good for", "<p>Meetups, workshops, college fests, community and society events, classes, and small conferences.</p>"),
        ],
        faqs=[("Can I sell tickets?", "Yes. Paid events show your UPI QR with the amount. The attendee enters the transaction ID and you approve the payment, after which the pass is emailed."),
              ("Can attendees cancel?", "Yes. Every pass has a cancel link that asks for confirmation. The seat is released and the cancellation appears in your report."),
              ("What happens if the internet is down at the gate?", "Scanning needs the QR Sugi site. Keep an Excel export of the attendee list as a backup and use the booking ID to check people in manually.")]),
    "restaurant-menu-qr-code": dict(
        title="Restaurant Menu QR Code Generator: Contactless Menu | QR Sugi",
        desc="Create a QR code for your restaurant menu, UPI table payment and review link. Update the menu link without reprinting table cards with a dynamic QR.",
        h1="QR codes for restaurants and cafes",
        intro="A menu QR code lets guests open your menu on their own phone, pay by UPI and leave a review, without handing out printed menus. Use a dynamic QR code so you can change the menu link without reprinting table cards.",
        sections=[
            ("Three codes most restaurants need", "<ul><li><strong>Menu:</strong> a link to your PDF or online menu</li><li><strong>Pay:</strong> a <a href=\"upi-qr-code-generator.html\">UPI QR code</a> for the table or counter</li><li><strong>Review:</strong> your Google review link</li></ul>"),
            ("Why dynamic for the menu", "<p>Menus change with seasons and prices. With a <a href=\"dynamic-qr-code-generator.html\">dynamic QR code</a> the printed card stays the same while you update the destination. You also see how many guests scan per day.</p>"),
            ("Print tips", "<p>Use dark code on a light background, print at least 3 cm wide for table cards, and run the built-in scan test before printing.</p>"),
        ],
        faqs=[("Can I change the menu later?", "Yes, with a dynamic QR code you edit the destination and the printed code keeps working."),
              ("Can guests scan in low light?", "Choose a high-contrast colour pair and a larger print size. The scan test warns you about low contrast.")]),
    "pricing": dict(
        title="QR Sugi Pricing in Rupees: Free, Starter, Pro, Business",
        desc="QR Sugi plans start free. Starter ₹249/month, Pro ₹699/month, Business ₹1,799/month, with lower prices when billed yearly. Static QR codes are free forever.",
        h1="QR Sugi pricing",
        intro="Static QR codes are free forever on every plan. Paid plans add more dynamic QR codes, longer analytics, your logo, more formats, bulk generation and larger events. Prices are in Indian rupees.",
        sections=[("Plans", "<ul>" + "".join(f"<li><strong>{n}</strong> — {p}. {d}.</li>" for n, p, d in PLANS) + "</ul>"),
                  ("Payment", "<p>You pay by UPI and submit the payment details; the plan is activated after the payment is verified, usually within a day.</p>"),
                  ("Cancel any time", "<p>If you cancel, your printed dynamic QR codes keep redirecting. See the <a href=\"dynamic-qr-code-generator.html\">never-dead promise</a>.</p>")],
        faqs=[("Is there a free plan?", "Yes. It includes unlimited static QR codes, 2 dynamic QR codes and a 7-day scan history."),
              ("Are prices in rupees?", "Yes, all prices are in Indian rupees (INR).")]),
}
ORDER = ["free-qr-code-generator", "upi-qr-code-generator", "whatsapp-qr-code-generator", "wifi-qr-code-generator", "vcard-qr-code-generator",
         "dynamic-qr-code-generator", "event-registration-qr-code", "restaurant-menu-qr-code", "pricing"]
NAV_LABEL = {"free-qr-code-generator": "Free QR generator", "upi-qr-code-generator": "UPI QR", "whatsapp-qr-code-generator": "WhatsApp QR",
             "wifi-qr-code-generator": "Wi-Fi QR", "vcard-qr-code-generator": "Contact card QR", "dynamic-qr-code-generator": "Dynamic QR",
             "event-registration-qr-code": "Event passes", "restaurant-menu-qr-code": "Restaurant menu QR", "pricing": "Pricing"}

HOME_FAQ = [
    ("What is QR Sugi?", "QR Sugi is a free QR code generator made for India. It creates static and dynamic QR codes for websites, UPI payments, WhatsApp, Wi-Fi and contact cards, and includes event registration with QR passes and gate scanning."),
    ("Is QR Sugi free?", "Yes. Static QR codes are free forever with no signup. Paid plans start at ₹249 per month and add more dynamic codes, analytics, logos, bulk generation and larger events."),
    ("Do QR codes made with QR Sugi expire?", "Static QR codes never expire. Dynamic QR codes keep redirecting even if you cancel a paid plan."),
    ("Which languages does the website support?", "English, Hindi (हिन्दी) and Marathi (मराठी)."),
    ("Can I use QR Sugi for event entry?", "Yes. QR Sugi Events creates a QR pass for every booking, scans passes with a phone camera, shows live attendance and exports Excel reports."),
]

CSS = """*{box-sizing:border-box}body{margin:0;font:16px/1.65 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#0f172a;background:#f8fafc}
a{color:#4f46e5}header,footer{background:#fff;border-bottom:1px solid #e2e8f0}footer{border-top:1px solid #e2e8f0;border-bottom:0;margin-top:3rem;font-size:14px;color:#475569}
.w{max-width:960px;margin:0 auto;padding:0 20px}nav{display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center;padding:12px 0;font-size:14px}
nav .logo{font-weight:800;font-size:18px;color:#4f46e5;text-decoration:none;margin-right:8px}nav a{text-decoration:none}
.hero{padding:40px 0 20px}h1{font-size:2.2rem;line-height:1.15;margin:0 0 12px;background:linear-gradient(90deg,#4f46e5,#7c3aed 55%,#ec4899);-webkit-background-clip:text;background-clip:text;color:transparent}
h2{font-size:1.4rem;margin:2rem 0 .5rem}.lead{font-size:1.1rem;color:#334155}
.btn{display:inline-block;background:linear-gradient(90deg,#4f46e5,#7c3aed);color:#fff;padding:12px 22px;border-radius:12px;font-weight:700;text-decoration:none;margin:10px 10px 0 0}
.btn.alt{background:#fff;color:#4f46e5;border:1px solid #c7d2fe}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin:16px 0}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:16px}.card h3{margin:.1rem 0 .3rem;font-size:1.05rem}.card p{margin:0;color:#475569;font-size:.95rem}
details{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:10px 14px;margin:8px 0}summary{cursor:pointer;font-weight:700}
code{background:#eef2ff;padding:1px 6px;border-radius:6px}@media(max-width:600px){h1{font-size:1.7rem}}"""


def jsonld(*objs) -> str:
    return "".join(f'<script type="application/ld+json">{json.dumps(o, ensure_ascii=False)}</script>' for o in objs)


def faq_ld(faqs):
    return {"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]}


def crumbs(items):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(items)]}


APP_LD = {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": BRAND, "applicationCategory": "UtilitiesApplication", "operatingSystem": "Web",
          "url": APP_URL, "description": "Free QR code generator for India: static and dynamic QR codes, UPI, WhatsApp, Wi-Fi, vCard, event passes and scan analytics.",
          "offers": {"@type": "AggregateOffer", "lowPrice": "0", "highPrice": "1799", "priceCurrency": "INR", "offerCount": "4"},
          "inLanguage": ["en", "hi", "mr"], "image": f"{SITE_URL}/og-image.png"}
ORG_LD = {"@context": "https://schema.org", "@type": "Organization", "name": BRAND, "url": SITE_URL + "/", "logo": f"{SITE_URL}/logo.png"}


def layout(path, title, desc, body, ld="", lang="en", alternates=None, og_type="website"):
    url = f"{SITE_URL}/{path}".rstrip("/") if path else SITE_URL + "/"
    if path.endswith("index.html"):
        url = f"{SITE_URL}/{path[:-10]}"
    alt = "".join(f'<link rel="alternate" hreflang="{l}" href="{u}">' for l, u in (alternates or []))
    links = "".join(f'<a href="{SITE_URL}/{s}.html">{NAV_LABEL[s]}</a>' for s in ORDER)
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title><meta name="description" content="{E(desc)}"><link rel="canonical" href="{url}">{alt}
<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1"><meta name="theme-color" content="#4f46e5">
<meta property="og:type" content="{og_type}"><meta property="og:site_name" content="{BRAND}"><meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{url}"><meta property="og:image" content="{SITE_URL}/og-image.png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{E(title)}"><meta name="twitter:description" content="{E(desc)}"><meta name="twitter:image" content="{SITE_URL}/og-image.png">
<link rel="icon" href="{SITE_URL}/favicon.png"><style>{CSS}</style>{ld}</head><body>
<header><div class="w"><nav><a class="logo" href="{SITE_URL}/">QR Sugi</a>{links}<a href="{SITE_URL}/faq.html">FAQ</a><a href="{SITE_URL}/hi/">हिन्दी</a><a href="{SITE_URL}/mr/">मराठी</a></nav></div></header>
<main class="w">{body}</main>
<footer><div class="w" style="padding:22px 20px"><p><strong>{BRAND}</strong> — free QR code generator for India. Static QR codes are free forever. <a href="{APP_URL}">Open the generator</a> · <a href="{SITE_URL}/faq.html">FAQ</a> · <a href="{SITE_URL}/llms.txt">llms.txt</a> · <a href="{SITE_URL}/sitemap.xml">Sitemap</a></p></div></footer>
</body></html>"""


def faq_html(faqs):
    return "<h2>Frequently asked questions</h2>" + "".join(f"<details><summary>{E(q)}</summary><p>{E(a)}</p></details>" for q, a in faqs)


def related(slug):
    return "<h2>More QR code tools</h2><div class=\"grid\">" + "".join(
        f'<a class="card" style="text-decoration:none;color:inherit" href="{s}.html"><h3>{E(NAV_LABEL[s])}</h3><p>{E(PAGES[s]["desc"][:90])}…</p></a>' for s in ORDER if s != slug)[:100000] + "</div>"


def build_page(slug, d):
    secs = "".join(f"<h2>{E(h)}</h2>{c.replace('{app}', APP_URL)}" for h, c in d["sections"])
    body = (f'<section class="hero"><h1>{E(d["h1"])}</h1><p class="lead">{E(d["intro"])}</p>'
            f'<a class="btn" href="{APP_URL}">Create your QR code free</a><a class="btn alt" href="{SITE_URL}/pricing.html">See pricing</a></section>'
            f"{secs}{faq_html(d['faqs'])}{related(slug)}")
    ld = jsonld(APP_LD, faq_ld(d["faqs"]), crumbs([("Home", SITE_URL + "/"), (NAV_LABEL[slug], f"{SITE_URL}/{slug}.html")]))
    return layout(f"{slug}.html", d["title"], d["desc"], body, ld)


HI_HOME = dict(
    lang="hi", path="hi/index.html", title="मुफ़्त QR कोड जनरेटर: UPI, व्हाट्सऐप, Wi-Fi, इवेंट पास | QR Sugi",
    desc="मुफ़्त QR कोड बनाएँ: वेबसाइट, UPI भुगतान, व्हाट्सऐप, Wi-Fi, संपर्क कार्ड। स्टैटिक QR कभी एक्सपायर नहीं होते। इवेंट रजिस्ट्रेशन और QR एंट्री पास भी।",
    h1="भारत के लिए मुफ़्त QR कोड जनरेटर", intro="QR Sugi से आप वेबसाइट, UPI भुगतान, व्हाट्सऐप चैट, Wi-Fi और संपर्क कार्ड के QR कोड मुफ़्त बना सकते हैं। स्टैटिक QR कोड हमेशा मुफ़्त हैं और कभी एक्सपायर नहीं होते। वेबसाइट हिन्दी, मराठी और अंग्रेज़ी में उपलब्ध है।",
    cards=[("UPI QR कोड", "अपनी UPI आईडी से भुगतान QR बनाएँ। PhonePe, Google Pay, Paytm सब में चलता है।"), ("व्हाट्सऐप QR", "स्कैन करते ही आपके नंबर पर चैट खुले, पहले से लिखे संदेश के साथ।"),
           ("Wi-Fi QR", "मेहमान बिना पासवर्ड टाइप किए नेटवर्क से जुड़ें।"), ("डायनामिक QR", "प्रिंट के बाद भी लिंक बदलें और स्कैन ट्रैक करें।"),
           ("इवेंट पास", "हर बुकिंग का अपना QR पास, गेट पर फ़ोन से स्कैन और Excel रिपोर्ट।"), ("मुफ़्त और सुरक्षित", "स्टैटिक कोड हमेशा मुफ़्त, कोई साइनअप ज़रूरी नहीं।")],
    faqs=[("क्या QR Sugi मुफ़्त है?", "हाँ। स्टैटिक QR कोड बिना साइनअप हमेशा मुफ़्त हैं। पेड प्लान ₹249 प्रति माह से शुरू होते हैं।"),
          ("क्या मेरा QR कोड एक्सपायर होगा?", "स्टैटिक QR कोड कभी एक्सपायर नहीं होते। डायनामिक QR कोड प्लान रद्द करने के बाद भी चलते रहते हैं।"),
          ("UPI QR कैसे बनाएँ?", "जनरेटर खोलें, 'UPI भुगतान' चुनें, अपनी UPI आईडी और नाम लिखें, फिर PNG डाउनलोड करें।")], cta="मुफ़्त QR कोड बनाएँ")
MR_HOME = dict(
    lang="mr", path="mr/index.html", title="मोफत QR कोड जनरेटर: UPI, व्हॉट्सॲप, Wi-Fi, इव्हेंट पास | QR Sugi",
    desc="मोफत QR कोड बनवा: वेबसाइट, UPI पेमेंट, व्हॉट्सॲप, Wi-Fi, संपर्क कार्ड. स्टॅटिक QR कधीच संपत नाहीत. इव्हेंट नोंदणी आणि QR प्रवेश पासही.",
    h1="भारतासाठी मोफत QR कोड जनरेटर", intro="QR Sugi वर तुम्ही वेबसाइट, UPI पेमेंट, व्हॉट्सॲप चॅट, Wi-Fi आणि संपर्क कार्डचे QR कोड मोफत बनवू शकता. स्टॅटिक QR कोड कायम मोफत आहेत आणि कधीच संपत नाहीत. वेबसाइट मराठी, हिन्दी आणि इंग्रजीत उपलब्ध आहे.",
    cards=[("UPI QR कोड", "तुमच्या UPI आयडीने पेमेंट QR बनवा. PhonePe, Google Pay, Paytm सर्वांत चालतो."), ("व्हॉट्सॲप QR", "स्कॅन करताच तुमच्या नंबरवर चॅट उघडते, आधी लिहिलेल्या संदेशासह."),
           ("Wi-Fi QR", "पाहुणे पासवर्ड न टाकता नेटवर्कला जोडले जातात."), ("डायनॅमिक QR", "प्रिंटनंतरही लिंक बदला आणि स्कॅन ट्रॅक करा."),
           ("इव्हेंट पास", "प्रत्येक बुकिंगसाठी स्वतंत्र QR पास, गेटवर फोनने स्कॅन आणि Excel रिपोर्ट."), ("मोफत आणि सुरक्षित", "स्टॅटिक कोड कायम मोफत, साइनअपची गरज नाही.")],
    faqs=[("QR Sugi मोफत आहे का?", "होय. स्टॅटिक QR कोड साइनअपशिवाय कायम मोफत आहेत. पेड प्लॅन ₹249 प्रति महिन्यापासून सुरू होतात."),
          ("माझा QR कोड संपेल का?", "स्टॅटिक QR कोड कधीच संपत नाहीत. डायनॅमिक QR कोड प्लॅन रद्द केल्यानंतरही चालत राहतात."),
          ("UPI QR कसा बनवायचा?", "जनरेटर उघडा, 'UPI पेमेंट' निवडा, तुमचा UPI आयडी आणि नाव लिहा, मग PNG डाउनलोड करा.")], cta="मोफत QR कोड बनवा")


def build_localized(d):
    cards = "".join(f'<div class="card"><h3>{E(t)}</h3><p>{E(x)}</p></div>' for t, x in d["cards"])
    body = (f'<section class="hero"><h1>{E(d["h1"])}</h1><p class="lead">{E(d["intro"])}</p><a class="btn" href="{APP_URL}/?lang={d["lang"]}">{E(d["cta"])}</a></section>'
            f'<div class="grid">{cards}</div>{faq_html(d["faqs"])}')
    alts = [("en", SITE_URL + "/"), ("hi", SITE_URL + "/hi/"), ("mr", SITE_URL + "/mr/"), ("x-default", SITE_URL + "/")]
    return layout(d["path"], d["title"], d["desc"], body, jsonld(APP_LD, faq_ld(d["faqs"])), lang=d["lang"], alternates=alts)


def build_home():
    cards = "".join(f'<a class="card" style="text-decoration:none;color:inherit" href="{s}.html"><h3>{E(NAV_LABEL[s])}</h3><p>{E(PAGES[s]["desc"][:110])}…</p></a>' for s in ORDER)
    body = (f'<section class="hero"><h1>Free QR code generator for India</h1>'
            f'<p class="lead">{BRAND} makes static and dynamic QR codes for websites, UPI payments, WhatsApp, Wi-Fi and contact cards, with scan analytics and event registration passes. '
            f'Static QR codes are free forever, never expire, and need no signup. Available in English, Hindi and Marathi.</p>'
            f'<a class="btn" href="{APP_URL}">Create a QR code free</a><a class="btn alt" href="{SITE_URL}/pricing.html">Pricing</a></section>'
            f"<h2>QR code tools</h2><div class=\"grid\">{cards}</div>"
            "<h2>Why QR Sugi</h2><div class=\"grid\">"
            "<div class=\"card\"><h3>Made for India</h3><p>UPI payment QR, WhatsApp chat QR, rupee pricing, Hindi and Marathi.</p></div>"
            "<div class=\"card\"><h3>Never-dead codes</h3><p>Printed dynamic codes keep redirecting even if you cancel or hit a limit.</p></div>"
            "<div class=\"card\"><h3>Scan analytics</h3><p>See scans by day, device, operating system and browser.</p></div>"
            "<div class=\"card\"><h3>Event passes</h3><p>Bookings, QR passes, gate scanning and Excel attendance reports.</p></div></div>"
            f"{faq_html(HOME_FAQ)}")
    alts = [("en", SITE_URL + "/"), ("hi", SITE_URL + "/hi/"), ("mr", SITE_URL + "/mr/"), ("x-default", SITE_URL + "/")]
    ld = jsonld(APP_LD, ORG_LD, {"@context": "https://schema.org", "@type": "WebSite", "name": BRAND, "url": SITE_URL + "/"}, faq_ld(HOME_FAQ))
    return layout("index.html", "QR Sugi: Free QR Code Generator for India | UPI, WhatsApp, Wi-Fi",
                  "Free QR code generator for India: static and dynamic QR codes for websites, UPI, WhatsApp, Wi-Fi and contacts. Event passes, scan analytics. Hindi and Marathi.",
                  body, ld, alternates=alts)


def build_faq():
    allf = list(HOME_FAQ)
    for s in ORDER:
        allf += PAGES[s]["faqs"]
    seen, faqs = set(), []
    for q, a in allf:
        if q not in seen:
            seen.add(q)
            faqs.append((q, a))
    body = f'<section class="hero"><h1>QR Sugi frequently asked questions</h1><p class="lead">Answers about QR code types, expiry, pricing, UPI and events.</p></section>{faq_html(faqs)}'
    return layout("faq.html", "QR Sugi FAQ: QR Code Questions Answered", "Answers about static vs dynamic QR codes, expiry, UPI QR codes, WhatsApp and Wi-Fi codes, event passes and pricing.", body,
                  jsonld(APP_LD, faq_ld(faqs), crumbs([("Home", SITE_URL + "/"), ("FAQ", SITE_URL + "/faq.html")])))


# ----------------------------------------------------------------------------------------------- LLM files
def llms_txt():
    lines = [f"# {BRAND}", "",
             f"> {BRAND} is a free QR code generator for India. It creates static and dynamic QR codes (website, UPI payment, WhatsApp, Wi-Fi, vCard contact card, SMS, phone, email, location, calendar), "
             "shows scan analytics, and includes event registration with unique QR passes, phone-camera gate scanning and Excel attendance reports. Static QR codes are free forever and never expire. "
             "The site is available in English, Hindi and Marathi. Prices are in Indian rupees.", "",
             "## Use the tool", f"- [QR Sugi QR code generator (web app)]({APP_URL}): create, design and download QR codes", "",
             "## Guides"]
    for s in ORDER:
        lines.append(f"- [{PAGES[s]['h1']}]({SITE_URL}/{s}.html): {PAGES[s]['desc']}")
    lines += ["", "## Optional", f"- [FAQ]({SITE_URL}/faq.html)", f"- [Full content for LLMs]({SITE_URL}/llms-full.txt)", f"- [Hindi]({SITE_URL}/hi/)", f"- [Marathi]({SITE_URL}/mr/)", f"- [Sitemap]({SITE_URL}/sitemap.xml)", ""]
    return "\n".join(lines)


def strip(t):
    import re
    t = re.sub(r"</(li|p|h2|div)>", "\n", t.replace("{app}", APP_URL))
    t = re.sub(r"<li>", "- ", t)
    return re.sub(r"<[^>]+>", "", html.unescape(t)).strip()


def llms_full():
    out = [f"# {BRAND}: full content", "", f"Source: {SITE_URL}/ . App: {APP_URL}", ""]
    for s in ORDER:
        d = PAGES[s]
        out += [f"## {d['h1']}", "", d["intro"], ""]
        for h, c in d["sections"]:
            out += [f"### {h}", "", strip(c), ""]
        out += ["### FAQ", ""] + [f"**{q}** {a}" for q, a in d["faqs"]] + [""]
    out += ["## Plans (INR)", ""] + [f"- {n}: {p}. {d}." for n, p, d in PLANS] + [""]
    return "\n".join(out)


def robots():
    bots = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-Web", "anthropic-ai", "PerplexityBot", "Google-Extended", "Applebot-Extended", "CCBot", "Bytespider", "cohere-ai", "Amazonbot", "DuckAssistBot", "MistralAI-User"]
    return "User-agent: *\nAllow: /\n\n" + "\n".join(f"User-agent: {b}\nAllow: /\n" for b in bots) + f"\nSitemap: {SITE_URL}/sitemap.xml\n"


def sitemap(urls):
    alt = [("en", SITE_URL + "/"), ("hi", SITE_URL + "/hi/"), ("mr", SITE_URL + "/mr/")]
    rows = []
    for u, pri in urls:
        extra = "".join(f'<xhtml:link rel="alternate" hreflang="{l}" href="{h}"/>' for l, h in alt) if u in {a for _, a in alt} else ""
        rows.append(f"<url><loc>{u}</loc><lastmod>{TODAY}</lastmod><priority>{pri}</priority>{extra}</url>")
    return ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">' + "".join(rows) + "</urlset>")


def og_image():
    from PIL import Image, ImageDraw, ImageFont
    import qrcode
    W, H = 1200, 630
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for x in range(W):
        t = x / W
        d.line([(x, 0), (x, H)], fill=(int(79 + (236 - 79) * t * .7), int(70 + (72 - 70) * t), int(229 + (153 - 229) * t * .6)))

    def font(sz, bold=False):
        for p in ("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(p, sz)
            except OSError:
                pass
        return ImageFont.load_default()
    d.text((70, 90), "QR Sugi", font=font(84, True), fill="white")
    d.text((70, 215), "Free QR code generator", font=font(52, True), fill="white")
    d.text((70, 285), "for India", font=font(52, True), fill="white")
    d.text((70, 400), "UPI  ·  WhatsApp  ·  Wi-Fi  ·  Dynamic QR", font=font(32), fill=(238, 242, 255))
    d.text((70, 450), "Event passes  ·  English, Hindi, Marathi", font=font(32), fill=(238, 242, 255))
    q = qrcode.make(APP_URL).convert("RGB").resize((330, 330))
    box = Image.new("RGB", (370, 370), "white")
    box.paste(q, (20, 20))
    im.paste(box, (W - 440, 130))
    return im


def write(rel, text):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    write("index.html", build_home())
    write("faq.html", build_faq())
    for s in ORDER:
        write(f"{s}.html", build_page(s, PAGES[s]))
    write("hi/index.html", build_localized(HI_HOME))
    write("mr/index.html", build_localized(MR_HOME))
    write("404.html", layout("404.html", "Page not found | QR Sugi", "This page does not exist.", f'<section class="hero"><h1>Page not found</h1><p class="lead"><a href="{SITE_URL}/">Go to the QR Sugi home page</a></p></section>').replace('content="index,follow', 'content="noindex,follow'))
    write("llms.txt", llms_txt())
    write("llms-full.txt", llms_full())
    write("robots.txt", robots())
    urls = [(SITE_URL + "/", "1.0"), (SITE_URL + "/hi/", "0.7"), (SITE_URL + "/mr/", "0.7"), (SITE_URL + "/faq.html", "0.6")] + [(f"{SITE_URL}/{s}.html", "0.9" if s != "pricing" else "0.7") for s in ORDER]
    write("sitemap.xml", sitemap(urls))
    og_image().save(OUT / "og-image.png", optimize=True)
    src = ROOT.parent / "assets"
    for name, dst in (("favicon.png", "favicon.png"), ("sugi_logo.png", "logo.png")):
        if (src / name).exists():
            shutil.copy(src / name, OUT / dst)
    (OUT / ".nojekyll").write_text("")
    host = SITE_URL.split("://", 1)[1].split("/")[0]
    if "github.io" not in host:
        (OUT / "CNAME").write_text(host + chr(10))          # tells GitHub Pages which custom domain to serve
    print(f"built {len(urls)} pages -> {OUT}  (SITE_URL={SITE_URL})")


if __name__ == "__main__":
    main()
