import streamlit as st
import os
import sys
import re
import asyncio
import json
import io
from datetime import datetime

# ==================== AUTOMATIC BROWSER INSTALLATION ====================
@st.cache_resource
def initialize_playwright_browser():
    try:
        import playwright
    except ModuleNotFoundError:
        os.system(f"{sys.executable} -m pip install playwright")
    os.system(f"{sys.executable} -m playwright install-deps")
    os.system(f"{sys.executable} -m playwright install chromium")
    return True

initialize_playwright_browser()

from playwright.async_api import async_playwright

# Try importing ReportLab for PDF generation
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
except ImportError:
    os.system(f"{sys.executable} -m pip install reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

# ==================== CONFIGURATION & PERSISTENCE ====================
MAX_RECHARGE_LIMIT = 1000  
MIN_RECHARGE_LIMIT = 20    
HISTORY_FILE = "recharge_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(history_data):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history_data, f, indent=4)

# Initialize Session State Variables safely across reruns
if "history" not in st.session_state:
    st.session_state.history = load_history()
if "temp_url" not in st.session_state:
    st.session_state.temp_url = None
if "temp_plan" not in st.session_state:
    st.session_state.temp_plan = None
if "temp_total_planned" not in st.session_state:
    st.session_state.temp_total_planned = 0
if "payment_confirmed" not in st.session_state:
    st.session_state.payment_confirmed = False

# ==================== PREMIUM CYBERPUNK CUSTOM CSS ====================
st.set_page_config(page_title="GP Recharge Bundle Engine", page_icon="⚡", layout="wide")

cyberpunk_css = """
<style>
    /* Glowing Dark Cyberpunk Background */
    .stApp {
        background-color: #030307 !important;
        background-image: radial-gradient(at 50% 0%, hsla(242,50%,15%,1) 0, transparent 50%),
                          radial-gradient(at 0% 100%, hsla(325,40%,10%,1) 0, transparent 50%) !important;
        color: #f1f5f9 !important;
    }
    
    /* Input Boxes and Tabs Design */
    div.stForm, div[data-testid="stBlock"], .stTabs {
        background: rgba(255, 255, 255, 0.02) !important;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid rgba(0, 240, 255, 0.15) !important;
        backdrop-filter: blur(10px);
    }
    
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {
        background-color: rgba(0, 0, 0, 0.4) !important;
        color: #00f0ff !important;
        border: 1px solid rgba(0, 240, 255, 0.2) !important;
        border-radius: 8px !important;
    }
    
    code, pre {
        word-break: break-all !important;
        white-space: pre-wrap !important;
        background-color: #05050d !important;
        border: 1px solid #00f0ff !important;
        color: #00f0ff !important;
    }
    
    .ui-title {
        color: #00f0ff !important;
        text-shadow: 0 0 12px rgba(0, 240, 255, 0.6);
        font-family: 'Courier New', Courier, monospace;
        font-weight: bold;
    }

    /* Premium Pulsating Neon bKash Button */
    @keyframes bkash-pulse {
        0% { box-shadow: 0 0 0 0 rgba(226, 19, 110, 0.8); }
        70% { box-shadow: 0 0 0 20px rgba(226, 19, 110, 0); }
        100% { box-shadow: 0 0 0 0 rgba(226, 19, 110, 0); }
    }
    @keyframes gradient-shift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    .premium-bkash-btn {
        background: linear-gradient(-45deg, #E2136E, #F81F8F, #C30B5C, #E2136E);
        background-size: 300% 300%;
        animation: gradient-shift 3s ease infinite, bkash-pulse 2s infinite;
        color: white !important;
        padding: 16px 40px;
        text-align: center;
        border-radius: 12px;
        font-size: 20px;
        font-weight: bold;
        cursor: pointer;
        display: block;
        text-decoration: none;
        border: 1px solid rgba(255, 255, 255, 0.2);
        margin: 20px auto;
        width: 80%;
        transition: transform 0.2s;
    }
    .premium-bkash-btn:hover {
        transform: scale(1.03);
    }
</style>
"""
st.markdown(cyberpunk_css, unsafe_allow_html=True)

st.markdown("<h1 class='ui-title'>⚡ GP RECHARGE BUNDLE ENGINE Pro</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#ff007f; font-weight:bold;'>[ PIPELINE INTERCEPTOR MODE: ACTIVE ]</p>", unsafe_allow_html=True)
st.markdown("---")

# ==================== HELPERS & CORE PARSING LOGIC ====================
def parse_uploaded_numbers(file_content):
    raw_tokens = re.split(r'[\s,;\t\n\r]+', file_content)
    valid_numbers = []
    for token in raw_tokens:
        digits_only = re.sub(r'\D', '', token)
        if digits_only.startswith('880'):
            digits_only = digits_only[2:]
        elif digits_only.startswith('1') and len(digits_only) == 10:
            digits_only = '0' + digits_only
        if len(digits_only) > 11 and digits_only.startswith('01'):
            digits_only = digits_only[:11]
        if len(digits_only) == 11 and digits_only.startswith('01'):
            if digits_only not in valid_numbers:
                valid_numbers.append(digits_only)
    return valid_numbers

def parse_seu_balances(raw_input):
    pattern = r"Exact Balance:\s*([0-9]+)"
    matches = re.findall(pattern, raw_input)
    total_balance = 0
    for amount in matches:
        total_balance += int(amount)
    return total_balance

def distribute_amount(total_amount, target_numbers, anti_duplicate=False):
    distribution = []
    remaining = (total_amount // 10) * 10
    chunk_amount = 980 if anti_duplicate else MAX_RECHARGE_LIMIT

    for number in target_numbers:
        if remaining < MIN_RECHARGE_LIMIT:
            break
        allocate = min(remaining, chunk_amount)
        allocate = (allocate // 10) * 10
        if allocate >= MIN_RECHARGE_LIMIT:
            distribution.append({"msisdn": number, "amount": allocate})
            remaining -= allocate

    total_planned = sum(item["amount"] for item in distribution)
    leftover_balance = total_amount - total_planned
    return distribution, total_planned, leftover_balance

# Beautiful PDF Generation Engine using ReportLab
def generate_pdf_report(session_data):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor("#E2136E"), spaceAfter=15, alignment=1)
    meta_style = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor("#333333"), spaceAfter=6)
    
    story.append(Paragraph("<b>GP RECHARGE BUNDLE SYSTEM</b>", title_style))
    story.append(Paragraph("<b>Official Transaction Summary Report</b>", ParagraphStyle('Sub', parent=title_style, fontSize=13, textColor=colors.HexColor("#555555"), spaceAfter=20)))
    story.append(Spacer(1, 10))
    
    story.append(Paragraph(f"<b>Date & Time:</b> {session_data['timestamp']}", meta_style))
    story.append(Paragraph(f"<b>Total Processed Amount:</b> {session_data['total_amount']} BDT", meta_style))
    story.append(Paragraph(f"<b>Total Target Numbers:</b> {session_data['total_numbers']}", meta_style))
    story.append(Spacer(1, 20))
    
    table_data = [["SL", "Phone Number", "Allocated Amount (BDT)"]]
    for idx, item in enumerate(session_data['breakdown'], 1):
        table_data.append([str(idx), item['msisdn'], f"{item['amount']} BDT"])
        
    t = Table(table_data, colWidths=[50, 250, 200])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2136E")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E0E0E0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F2F4F7")]),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer

async def inject_gp_live_pipeline(pipeline_plan, customer_email):
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled']
            )
            context = await browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page1 = await context.new_page()
            await page1.add_init_script("delete navigator.__proto__.webdriver;")
        except Exception as e:
            return {"success": False, "error": f"Browser Initialization Failed: {str(e)}"}
        
        session_id_container = [None]
        async def handle_response(response):
            if "payments.grameenphone.com/ui/recharge/" in response.url:
                match = re.search(r'/ui/recharge/([a-f0-9]{32})', response.url)
                if match: session_id_container[0] = match.group(1)

        page1.on("response", handle_response)
        try:
            await page1.goto("https://www.grameenphone.com/recharge", wait_until="domcontentloaded", timeout=50000)
            await asyncio.sleep(4)
        except Exception as e:
            await browser.close()
            return {"success": False, "error": f"GP Portal connection timeout: {str(e)}"}
        
        if not session_id_container[0]:
            current_url = page1.url
            match = re.search(r'/recharge/([a-f0-9]{32})', current_url)
            if match: session_id_container[0] = match.group(1)
            else:
                await browser.close()
                return {"success": False, "error": "Could not intercept GP Gateway Session ID."}

        session_id = session_id_container[0]
        products_list = [{"type": "postpaid", "msisdn": item["msisdn"], "amount": item["amount"]} for item in pipeline_plan]

        payload_data = {
            "sessionId": session_id,
            "paymentType": "bkash",
            "customerEmail": customer_email,
            "products": products_list,
            "language": "en",
            "ui": "bulk_recharge"
        }

        js_submit_routing = """
        async (config) => {
            try {
                const response = await fetch('https://payments.grameenphone.com/ui/api/submit-routing', {
                    method: 'POST',
                    headers: {'Accept': 'application/json, text/plain, */*', 'Content-Type': 'application/json'},
                    body: config.payloadStr
                });
                return await response.json();
            } catch (err) { return {"success": false, "error": err.toString()}; }
        }
        """
        try:
            api_response = await page1.evaluate(js_submit_routing, {"payloadStr": json.dumps(payload_data)})
        except Exception as e:
            api_response = {"success": False, "error": f"JS Injection failed: {str(e)}"}
            
        await browser.close()
        return api_response

# ==================== DUAL INPUT INTERFACE (TABS) ====================
st.subheader("📥 STEP 1: Target Numbers Input Source")
tab1, tab2 = st.tabs(["📁 Upload 'gp.txt' File", "✍️ Paste Numbers Manually"])

raw_numbers_content = ""
with tab1:
    uploaded_file = st.file_uploader("Upload text file containing numbers", type=["txt"], key="gp_file_uploader")
    if uploaded_file is not None:
        raw_numbers_content = uploaded_file.read().decode("utf-8")
with tab2:
    pasted_numbers = st.text_area("Paste your numbers here:", height=100, placeholder="01711XXXXXX\n01301XXXXXX", key="gp_text_paster")
    if pasted_numbers.strip():
        raw_numbers_content = pasted_numbers

# --- Main Automation Segment ---
if raw_numbers_content.strip():
    target_numbers = parse_uploaded_numbers(raw_numbers_content)
    
    if not target_numbers:
        st.error("❌ No valid 11-digit numbers extracted.")
    else:
        st.success(f"📦 Loaded {len(target_numbers)} unique target numbers.")
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            mode = st.radio("🚀 Choose Execution Mode", ['Normal', '5-min Jitter (Anti-Duplicate)'])
            anti_duplicate = True if mode == '5-min Jitter (Anti-Duplicate)' else False
        with col2:
            customer_email_input = st.text_input("📧 Customer Email Address:", value="emailhere@gmail.com")

        seu_input = st.text_area("📋 STEP 2: Paste your SEU SCOUT output data here:", height=120)

        # বাটন ১: শুধুমাত্র লিংক ইন্টারসেপ্ট করবে (কোনো লগ বা পিডিএফ সেভ করবে না)
        if st.button("⚡ Process & Generate Recharge Link", type="primary"):
            if not seu_input.strip():
                st.error("Please paste SEU output data first.")
            else:
                total_exact_balance = parse_seu_balances(seu_input)
                if total_exact_balance == 0:
                    st.error("Could not extract any valid Exact Balance.")
                else:
                    st.metric(label="💰 Total Input Balance Detected", value=f"{total_exact_balance} BDT")
                    pipeline_plan, total_planned, leftover = distribute_amount(total_exact_balance, target_numbers, anti_duplicate)
                    
                    if not pipeline_plan:
                        st.error("No valid distribution plan generated.")
                    else:
                        st.subheader("📊 Preview: Auto-Adjusted Distribution Plan")
                        st.write(f"**Total Allocated:** `{total_planned} BDT` | **Leftover Amount:** `{leftover} BDT`")
                        st.json(pipeline_plan)
                        
                        with st.spinner("Intercepting secure token routing from Grameenphone gateway..."):
                            api_response = asyncio.run(inject_gp_live_pipeline(pipeline_plan, customer_email_input.strip()))
                            
                        if api_response and api_response.get("success") and "data" in api_response and "redirectUrl" in api_response["data"]:
                            raw_url = api_response["data"]["redirectUrl"].strip()
                            if raw_url.endswith('/'): raw_url = raw_url[:-1]
                            
                            # ডেটা সেশন স্টেটে হোল্ড করে রাখা হচ্ছে, কনফার্ম করার আগে লগে যাবে না
                            st.session_state.temp_url = raw_url
                            st.session_state.temp_plan = pipeline_plan
                            st.session_state.temp_total_planned = total_planned
                            st.session_state.payment_confirmed = False
                            st.success("🎯 Live Secure Token Link Intercepted successfully! Verify below to Sync.")
                        else:
                            st.error("GP Server rejected payload routing or verification failed.")
                            st.json(api_response)

        # --- STEP 3: STRICT CLICK-TO-SYNC VALIDATION PANEL ---
        if st.session_state.temp_url:
            st.markdown("---")
            st.subheader("🛡️ STEP 3: Secure Target Audit & Logging Option")
            st.warning("নিচের কনফার্ম বাটনে ক্লিক করার পরই কেবল এই ডেটা সামারি চার্ট ও পিডিএফ রিপোর্টে স্থায়ীভাবে যুক্ত হবে।")
            
            # ব্যাকআপ লিংক ফুল উইডথ ফিক্স
            st.markdown("**📡 Gateway URL Content (Full String Copy-Paste Optimized):**")
            st.code(st.session_state.temp_url, language="text")
            
            # বাটন ২: এই বাটনে ক্লিক করলেই কেবল লগ ফাইল আপডেট ও সেভ হবে
            if st.button("🔗 Confirm Payment & Sync to Database Logs", key="strict_sync_btn"):
                new_log = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
                    "total_amount": st.session_state.temp_total_planned,
                    "total_numbers": len(st.session_state.temp_plan),
                    "breakdown": st.session_state.temp_plan
                }
                st.session_state.history.insert(0, new_log)
                save_history(st.session_state.history)
                st.session_state.payment_confirmed = True
                st.balloons()
            
            # কনফার্ম করার পর প্রিমিয়াম অ্যানিমেটেড বাটনটি ভিজিবল হবে গেটওয়েতে রিডাইরেক্টের জন্য
            if st.session_state.payment_confirmed:
                st.success("🎉 SYNC COMPLETE: History Database updated and locked!")
                button_html = f"""
                    <div style="text-align: center;">
                        <a href='{st.session_state.temp_url}' target="_blank" class="premium-bkash-btn">
                            🌸 Open Official bKash Gateway Session Tab
                        </a>
                    </div>
                """
                st.markdown(button_html, unsafe_allow_html=True)
else:
    st.info("💡 Getting Started: Please upload a file OR paste numbers to unlock the engine interfaces.")

# ==================== 📊 CLEAN ANALYTICS & LOGS (HIDDEN IN EXPANDERS) ====================
st.markdown("---")
st.subheader("📊 Persistent Recharge Logs & Analytics Dashboard")

if st.session_state.history:
    num_frequency = {}
    num_amount = {}
    total_spent_overall = 0
    
    for session in st.session_state.history:
        total_spent_overall += session["total_amount"]
        for entry in session["breakdown"]:
            msisdn = entry["msisdn"]
            num_frequency[msisdn] = num_frequency.get(msisdn, 0) + 1
            num_amount[msisdn] = num_amount.get(msisdn, 0) + entry["amount"]
            
    m1, m2, m3 = st.columns(3)
    m1.metric("All-Time Total Volume", f"{total_spent_overall} BDT")
    m2.metric("Total Unique Target Numbers", f"{len(num_frequency)}")
    m3.metric("Total Successful Batches", f"{len(st.session_state.history)}")

    # আপনার রিকোয়েস্ট অনুযায়ী টেবিল ও পিডিএফ পুরো পার্টটা এক্সপান্ডারের নিচে ক্লিন রাখা হয়েছে
    with st.expander("👁️ View Aggregated Target Numbers Summary Table"):
        summary_table = []
        for num in num_frequency:
            summary_table.append({
                "Phone Number": num,
                "Recharge Frequency": f"{num_frequency[num]} Times",
                "Total Amount Distributed": f"{num_amount[num]} BDT"
            })
        st.table(summary_table)

    with st.expander("🔍 Show Detailed Session Records & Download PDFs"):
        if st.button("🗑️ Clear All Permanent Logs", type="secondary"):
            st.session_state.history = []
            save_history([])
            st.session_state.temp_url = None
            st.success("Database history records wiped clean successfully!")
            st.rerun()
            
        st.write("### 📂 Individual Session Sub-Logs")
        for i, session in enumerate(st.session_state.history):
            st.markdown(f"#### 📅 Session {i+1}: {session['timestamp']}")
            
            c1, c2 = st.columns(2)
            c1.write(f"**Total Dispatched Amount:** `{session['total_amount']} BDT`")
            c2.write(f"**Total Accounts Target:** `{session['total_numbers']}`")
            
            pdf_data = generate_pdf_report(session)
            st.download_button(
                label=f"📥 Download PDF Summary ({session['timestamp']})",
                data=pdf_data,
                file_name=f"Recharge_Report_{session['timestamp'].replace(':', '-').replace(' ', '_')}.pdf",
                mime="application/pdf",
                key=f"pdf_download_core_{i}"
            )
            st.write("---")
else:
    st.info("No persistent history logs discovered. Successfully synchronized executions populate ledger entries here.")
