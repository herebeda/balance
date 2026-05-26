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
    from reportlab.pdfgen import canvas
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
except ModuleNotFoundError:
    os.system(f"{sys.executable} -m pip install reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

# ==================== INITIALIZE SESSION STATES ====================
if "persistent_logs" not in st.session_state:
    st.session_state.persistent_logs = []
if "total_volume" not in st.session_state:
    st.session_state.total_volume = 0
if "unique_numbers" not in st.session_state:
    st.session_state.unique_numbers = set()
if "temp_url" not in st.session_state:
    st.session_state.temp_url = None
if "temp_plan" not in st.session_state:
    st.session_state.temp_plan = None
if "temp_total_planned" not in st.session_state:
    st.session_state.temp_total_planned = 0
if "payment_confirmed" not in st.session_state:
    st.session_state.payment_confirmed = False

# ==================== HELPER FUNCTIONS ====================
def parse_numbers(raw_text):
    if not raw_text:
        return []
    matches = re.findall(r'(?:88)?01[37]\d{8}', raw_text)
    valid_numbers = []
    for num in matches:
        if num.startswith('880'):
            cleaned = num[2:]
        else:
            cleaned = num
        valid_numbers.append(cleaned)
    return list(dict.fromkeys(valid_numbers))

def parse_flexible_balance(input_data):
    if not input_data:
        return 0
    input_data = input_data.strip()
    
    match = re.search(r'(?:Exact\s+Balance:\s*)(\d+)', input_data, re.IGNORECASE)
    if match:
        return int(match.group(1))
        
    match_bdt = re.search(r'(\d+)\s*(?:BDT|TK|Taka)', input_data, re.IGNORECASE)
    if match_bdt:
        return int(match_bdt.group(1))
    
    tokens = re.split(r'[\s,;\t\n\r|]+', input_data)
    for token in tokens:
        d = re.sub(r'\D', '', token)
        if d:
            if len(d) in [11, 13] and (d.startswith('01') or d.startswith('880')):
                continue
            if len(d) <= 6:
                return int(d)
    return 0

def generate_combined_pdf_report(logs, total_vol):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, leading=22, textColor=colors.HexColor('#0F172A'), alignment=1)
    meta_style = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#475569'))
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#334155'))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=10, textColor=colors.white, fontName='Helvetica-Bold')

    story.append(Paragraph("GP Recharge Engine - Combined Audit Summary", title_style))
    story.append(Spacer(1, 15))
    story.append(Paragraph(f"<b>Report Generated:</b> {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}", meta_style))
    story.append(Paragraph(f"<b>Total Processed Volume:</b> {total_vol} BDT", meta_style))
    story.append(Paragraph(f"<b>Total Target Records:</b> {len(logs)} entries", meta_style))
    story.append(Spacer(1, 15))
    
    table_data = [[
        Paragraph("Timestamp", header_style),
        Paragraph("Target MSISDN", header_style),
        Paragraph("Allocated Amount", header_style),
        Paragraph("Status", header_style)
    ]]
    
    for entry in logs:
        table_data.append([
            Paragraph(entry.get('timestamp', '-'), cell_style),
            Paragraph(entry.get('msisdn', '-'), cell_style),
            Paragraph(f"{entry.get('amount', 0)} BDT", cell_style),
            Paragraph("Pipeline Executed", cell_style)
        ])
        
    log_table = Table(table_data, colWidths=[140, 110, 110, 160])
    log_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    
    story.append(log_table)
    doc.build(story)
    buffer.seek(0)
    return buffer

# ==================== PLAYWRIGHT GP CORE ENGINE ====================
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

# ==================== STREAMLIT UI & ULTRA ANIMATED CYBERPUNK CSS ====================
st.set_page_config(page_title="GP Recharge Bundle Engine", page_icon="⚡", layout="wide")

cyberpunk_animations = """
<style>
    .stApp {
        background-color: #030307 !important;
        background-image: radial-gradient(at 50% 0%, hsla(242,50%,15%,1) 0, transparent 50%),
                          radial-gradient(at 0% 100%, hsla(325,40%,10%,1) 0, transparent 50%) !important;
        color: #f1f5f9 !important;
    }
    code, pre {
        word-break: break-all !important;
        white-space: pre-wrap !important;
        background-color: #090914 !important;
        border: 1px solid #00f0ff !important;
        color: #00f0ff !important;
    }
    h1 {
        color: #00f0ff !important;
        text-shadow: 0 0 10px rgba(0, 240, 255, 0.6), 0 0 30px rgba(0, 240, 255, 0.3) !important;
        font-family: 'Courier New', Courier, monospace !important;
    }
    .animated-section {
        animation: fadeInSlide 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    @keyframes fadeInSlide {
        from { opacity: 0; transform: translateY(15px); }
        to { opacity: 1; transform: translateY(0); }
    }
    div[data-baseweb="textarea"], div[data-baseweb="input"], .stFileUploader {
        background: rgba(255, 255, 255, 0.02) !important;
        border: 1px solid rgba(0, 240, 255, 0.2) !important;
        border-radius: 12px !important;
    }
    .stButton>button[kind="primary"] {
        background: linear-gradient(45deg, #ff007f, #b500ff) !important;
        color: #ffffff !important;
        border-radius: 10px !important;
        font-weight: bold !important;
        box-shadow: 0 0 15px rgba(255, 0, 127, 0.6) !important;
    }
    
    /* Premium Pulsating Neon bKash Button Style */
    @keyframes bkash-pulse {
        0% { box-shadow: 0 0 0 0 rgba(226, 19, 110, 0.8); }
        70% { box-shadow: 0 0 0 18px rgba(226, 19, 110, 0); }
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
        padding: 14px 35px;
        text-align: center;
        border-radius: 10px;
        font-size: 19px;
        font-weight: bold;
        cursor: pointer;
        display: inline-block;
        text-decoration: none;
        border: 1px solid rgba(255, 255, 255, 0.2);
        transition: transform 0.2s;
    }
    .premium-bkash-btn:hover {
        transform: scale(1.03);
    }
</style>
"""
st.markdown(cyberpunk_animations, unsafe_allow_html=True)

st.title("⚡ GP RECHARGE BUNDLE ENGINE")
st.markdown("<p style='color:#00f0ff; font-weight:bold;'>[ SYSTEM STATUS: CYBER-PIPELINE INTERCEPTOR ONLINE ]</p>", unsafe_allow_html=True)
st.markdown("---")

# ==================== STEP 1: TARGET NUMBERS ====================
st.subheader("📥 STEP 1: Target Numbers Input Source")
col_file, col_paste = st.columns([1, 1])
with col_file:
    uploaded_file = st.file_uploader("Option A: Upload text file (gp.txt)", type=["txt"])
with col_paste:
    pasted_numbers = st.text_area("Option B: Paste Target Numbers directly here:", height=120)

combined_raw_numbers = uploaded_file.read().decode("utf-8") + "\n" if uploaded_file else ""
if pasted_numbers:
    combined_raw_numbers += pasted_numbers

target_numbers = parse_numbers(combined_raw_numbers)

# ==================== CONDITIONAL RENDERING ====================
if target_numbers:
    st.success(f"📦 Total Loaded: {len(target_numbers)} unique numbers.")
    st.markdown("---")
    
    st.markdown('<div class="animated-section">', unsafe_allow_html=True)
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.subheader("📋 STEP 2: Balance/SCOUT Input")
        scout_input = st.text_area("Paste SEU SCOUT output data or Raw Amount here:", height=120)
        detected_balance = parse_flexible_balance(scout_input)
        st.metric(label="💰 Total Input Balance Detected", value=f"{detected_balance} BDT")
        
    with col_right:
        st.subheader("🚀 STEP 3: Configuration & Mode")
        mode = st.radio("Choose Execution Strategy", ["Normal", "5-min Jitter (Anti-Duplicate)"])
        customer_email = st.text_input("📧 Customer Email Address:", value="test@cyber.com")
        
    st.markdown('</div>', unsafe_allow_html=True)

# ==================== PLAN GRID GENERATION ====================
if detected_balance > 0:
    st.markdown("---")
    st.markdown("### 📊 Auto-Adjusted Plan Grid")
    
    plan = []
    allocated_total = 0
    
    for num in target_numbers:
        amt_to_charge = 1000 if mode == "Normal" else 980
        
        # যদি পুরো ১০০০ টাকা দেওয়ার মতো ব্যালেন্স থাকে
        if allocated_total + amt_to_charge <= detected_balance:
            plan.append({"msisdn": num, "amount": amt_to_charge})
            allocated_total += amt_to_charge
        else:
            # বাকি বা অবশিষ্ট ব্যালেন্সটুকু হিসাব করা হচ্ছে (যেমন: ২৯৯০০ - ২৯০০০ = ৯০০)
            remainder = detected_balance - allocated_total
            if remainder > 0:
                plan.append({"msisdn": num, "amount": remainder})
                allocated_total += remainder
            break  # ব্যালেন্স শেষ হলে লুপ বন্ধ হবে
            
    st.json(plan)
        
        st.markdown("### ⚡ Step 4: Secure Gateway Action")
        st.write("নিচের বাটনে ক্লিক করলে ব্যাকগ্রাউন্ডে প্লে-রাইট ইঞ্জিন সরাসরি জিপি সার্ভার থেকে লাইভ টোকেন গেটওয়ে লিংক ক্যাচ করবে।")
        
        # বাটন ১: লাইভ লিঙ্কের জন্য জিপি সার্ভার ইন্টারসেপ্ট করবে
        if st.button("🚀 Intercept Live GP Secure Link", type="primary"):
            with st.spinner("Connecting Secure Tunnel to Grameenphone Engine Architecture..."):
                api_response = asyncio.run(inject_gp_live_pipeline(plan, customer_email.strip()))
                
            if api_response and api_response.get("success") and "data" in api_response and "redirectUrl" in api_response["data"]:
                raw_url = api_response["data"]["redirectUrl"].strip()
                if raw_url.endswith('/'): 
                    raw_url = raw_url[:-1]
                
                # সেশন স্টেটে টেম্পোরারি ডেটা সেভ রাখা হচ্ছে (কনফার্ম করার আগ পর্যন্ত মূল লগে ঢুকবে না)
                st.session_state.temp_url = raw_url
                st.session_state.temp_plan = plan
                st.session_state.temp_total_planned = allocated_total
                st.session_state.payment_confirmed = False
                st.success("🎯 Live Secure Token Link Intercepted successfully! Verify below to Sync.")
            else:
                st.error("GP Server rejected payload routing or verification failed.")
                st.json(api_response)

        # ==================== CONFIRM & SYNC SEGMENT ====================
        if st.session_state.temp_url:
            st.markdown("---")
            st.markdown("#### 📡 Intercepted Dynamic bKash URL (Full Payload Verified):")
            st.code(st.session_state.temp_url, language="text")
            
            # ডেটাবেজ লগে সিঙ্ক করার বাটন
            if not st.session_state.payment_confirmed:
                if st.button("🔗 Confirm Payment & Sync to Logs/PDF"):
                    timestamp_now = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
                    for item in st.session_state.temp_plan:
                        st.session_state.persistent_logs.append({
                            "timestamp": timestamp_now,
                            "msisdn": item["msisdn"],
                            "amount": item["amount"]
                        })
                        st.session_state.unique_numbers.add(item["msisdn"])
                    st.session_state.total_volume += st.session_state.temp_total_planned
                    st.session_state.payment_confirmed = True
                    st.balloons()
                    st.rerun()
            
            # লগ সিঙ্ক হওয়ার পর প্রিমিয়াম বিকাশ বাটন দৃশ্যমান হবে
            if st.session_state.payment_confirmed:
                st.success("🎉 SYNC COMPLETE: History Database updated and locked!")
                button_html = f"""
                    <div style="text-align: center; margin-top: 15px; margin-bottom: 15px;">
                        <a href='{st.session_state.temp_url}' target="_blank" class="premium-bkash-btn">
                            🌸 Open Dynamic bKash Gateway Tab
                        </a>
                    </div>
                """
                st.markdown(button_html, unsafe_allow_html=True)

else:
    st.info("💡 Awaiting Target Input in STEP 1 to unlock configuration panels.")

# ==================== LOGS & ANALYTICS ====================
st.markdown("---")
st.subheader("📊 Persistent Recharge Logs & Analytics")

if st.session_state.persistent_logs:
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Total Volume Processed", f"{st.session_state.total_volume} BDT")
    col_b.metric("Unique Target Numbers", f"{len(st.session_state.unique_numbers)}")
    col_c.metric("Total Success Entries", f"{len(st.session_state.persistent_logs)}")
    
    if st.button("🗑️ Clear All Logs", type="secondary"):
        st.session_state.persistent_logs = []
        st.session_state.total_volume = 0
        st.session_state.unique_numbers = set()
        st.session_state.temp_url = None
        st.session_state.payment_confirmed = False
        st.rerun()
        
    with st.expander("👁️ Click to View Aggregated Summary Table"):
        st.table(st.session_state.persistent_logs)
    
    with st.expander("🔍 Download Consolidated PDF Report"):
        pdf_file = generate_combined_pdf_report(st.session_state.persistent_logs, st.session_state.total_volume)
        st.download_button(
            label="📥 Download Full Combined PDF Report",
            data=pdf_file,
            file_name=f"Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf"
        )
else:
    st.info("No transaction records found. Successfully executed pipelines will generate combined logs here.")
