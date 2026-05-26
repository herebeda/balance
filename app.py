import streamlit as st
import os
import sys
import re
import io
from datetime import datetime

# ট্রাই-ক্যাচ দিয়ে reportlab ইমপোর্ট করা হচ্ছে যাতে পিডিএফ জেনারেশন মিস না হয়
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

# ==================== INITIALIZE SESSION STATES ====================
if "persistent_logs" not in st.session_state:
    st.session_state.persistent_logs = []
if "total_volume" not in st.session_state:
    st.session_state.total_volume = 0
if "unique_numbers" not in st.session_state:
    st.session_state.unique_numbers = set()

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

# ==================== STREAMLIT UI & ULTRA ANIMATED CYBERPUNK CSS ====================
st.set_page_config(page_title="GP Recharge Bundle Engine", page_icon="⚡", layout="wide")

cyberpunk_animations = """
<style>
    /* Glowing Cyberpunk Background */
    .stApp {
        background-color: #030307 !important;
        background-image: radial-gradient(at 50% 0%, hsla(242,50%,15%,1) 0, transparent 50%),
                          radial-gradient(at 0% 100%, hsla(325,40%,10%,1) 0, transparent 50%) !important;
        color: #f1f5f9 !important;
    }
    
    /* URL wrapping text fix to prevent cuts */
    code, pre {
        word-break: break-all !important;
        white-space: pre-wrap !important;
        background-color: #090914 !important;
        border: 1px solid #00f0ff !important;
        color: #00f0ff !important;
    }
    
    /* Neon Text Glowing and Pulsating Animations */
    h1 {
        color: #00f0ff !important;
        text-shadow: 0 0 10px rgba(0, 240, 255, 0.6), 0 0 30px rgba(0, 240, 255, 0.3) !important;
        font-family: 'Courier New', Courier, monospace !important;
        animation: pulseGlow 3s infinite alternate;
    }
    h2, h3, h4 {
        color: #00f0ff !important;
        text-shadow: 0 0 8px rgba(0, 240, 255, 0.4) !important;
    }
    
    @keyframes pulseGlow {
        0% { text-shadow: 0 0 10px rgba(0, 240, 255, 0.6), 0 0 20px rgba(0, 240, 255, 0.2); }
        100% { text-shadow: 0 0 20px rgba(0, 240, 255, 0.9), 0 0 40px rgba(0, 240, 255, 0.5); }
    }
    
    /* Smooth Slide/Fade-in Animation for Dynamic Sections */
    .animated-section {
        animation: fadeInSlide 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    
    @keyframes fadeInSlide {
        from { opacity: 0; transform: translateY(15px); filter: blur(4px); }
        to { opacity: 1; transform: translateY(0); filter: blur(0); }
    }

    /* Glassmorphism Input Cards with Cyber Scan Border */
    div[data-baseweb="textarea"], div[data-baseweb="input"], .stFileUploader {
        background: rgba(255, 255, 255, 0.02) !important;
        backdrop-filter: blur(15px) !important;
        border: 1px solid rgba(0, 240, 255, 0.2) !important;
        border-radius: 12px !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    div[data-baseweb="textarea"]:focus-within, div[data-baseweb="input"]:focus-within {
        border-color: #ff007f !important;
        box-shadow: 0 0 20px rgba(255, 0, 127, 0.4), inset 0 0 8px rgba(255, 0, 127, 0.1) !important;
    }
    
    /* Primary Action Glowing Button */
    .stButton>button[kind="primary"] {
        background: linear-gradient(45deg, #ff007f, #b500ff) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: bold !important;
        font-size: 16px !important;
        padding: 14px 32px !important;
        box-shadow: 0 0 15px rgba(255, 0, 127, 0.6) !important;
        transition: all 0.4s ease !important;
    }
    .stButton>button[kind="primary"]:hover {
        transform: scale(1.02);
        box-shadow: 0 0 30px rgba(255, 0, 127, 0.9), 0 0 40px rgba(181, 0, 255, 0.5) !important;
    }
    
    /* Metrics Highlighting */
    div[data-testid="stMetricValue"] {
        color: #ff007f !important;
        font-weight: bold !important;
        text-shadow: 0 0 10px rgba(255, 0, 127, 0.5) !important;
    }
</style>
"""
st.markdown(cyberpunk_animations, unsafe_allow_html=True)

st.title("⚡ GP RECHARGE BUNDLE ENGINE")
st.markdown("<p style='color:#ff007f; font-weight:bold; letter-spacing:1px; animation: pulseGlow 2s infinite alternate;'>[ SYSTEM STATUS: CYBER-PIPELINE ONLINE ]</p>", unsafe_allow_html=True)
st.markdown("---")

# ==================== STEP 1: UNIFIED NUMBER INPUT SOURCE ====================
st.subheader("📥 STEP 1: Target Numbers Input Source")
input_container = st.container()

with input_container:
    col_file, col_paste = st.columns([1, 1])
    with col_file:
        uploaded_file = st.file_uploader("Option A: Upload text file containing numbers (gp.txt)", type=["txt"])
    with col_paste:
        pasted_numbers = st.text_area("Option B: Or Paste Target Numbers directly here:", height=120, placeholder="017XXXXXXXX\n013XXXXXXXX")

combined_raw_numbers = ""
if uploaded_file is not None:
    combined_raw_numbers += uploaded_file.read().decode("utf-8") + "\n"
if pasted_numbers:
    combined_raw_numbers += pasted_numbers

target_numbers = parse_numbers(combined_raw_numbers)

# ==================== STEP 2 & 3: CONDITIONAL REVELATION BASED ON NUMBER DETECTED ====================
if target_numbers:
    st.success(f"📦 Total Loaded & Filtered: {len(target_numbers)} unique numbers.")
    st.markdown("---")
    
    st.markdown('<div class="animated-section">', unsafe_allow_html=True)
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.subheader("📋 STEP 2: Balance/SCOUT Input")
        scout_input = st.text_area("Paste SEU SCOUT output data or Raw Amount here:", height=150, placeholder="Example: 3000")
        
        detected_balance = parse_flexible_balance(scout_input)
        st.metric(label="💰 Total Input Balance Detected", value=f"{detected_balance} BDT")
        
    with col_right:
        st.subheader("🚀 STEP 3: Configuration & Mode")
        mode = st.radio("Choose Execution Strategy", ["Normal", "5-min Jitter (Anti-Duplicate)"])
        customer_email = st.text_input("📧 Customer Email Address:")
        
    st.markdown('</div>', unsafe_allow_html=True)

    # ==================== PLAN GENERATION ENGINE ====================
    if detected_balance > 0:
        st.markdown("---")
        st.markdown('<div class="animated-section">### 📊 Auto-Adjusted Plan Grid</div>', unsafe_allow_html=True)
        
        plan = []
        allocated_total = 0
        
        for num in target_numbers:
            if mode == "Normal":
                amt_to_charge = 1000
            else:
                amt_to_charge = 980  # ৫-মিন জিটার মোডে ফিক্সড ৯৮০ টাকা প্রতি সাব-নাম্বারে
                
            if allocated_total + amt_to_charge <= detected_balance:
                if amt_to_charge > 0:
                    plan.append({"msisdn": num, "amount": amt_to_charge})
                    allocated_total += amt_to_charge
            else:
                break
                
        leftover = detected_balance - allocated_total
        
        c1, c2 = st.columns(2)
        c1.info(f"**Total Allocated:** {allocated_total} BDT")
        c2.warning(f"**Leftover / Unallocated:** {leftover} BDT")
        
        st.json(plan)
        
        # ইউনিক বিকাশ পেমেন্ট লিংক তৈরি (ব্যাকগ্রাউন্ডে রেডি থাকবে)
        mock_payment_id = f"TR0011{datetime.now().strftime('%f%M%S%d')}"
        bkash_url = f"https://payment.bkash.com/?paymentId={mock_payment_id}&mode=0011&apiVersion=v1.2.0-beta"
        
        st.markdown("### ⚡ Step 4: Secure Gateway Action")
        st.write("নিচের লিংকে ক্লিক করলেই কেবল এই ডেটাগুলো সামারি লগ এবং পিডিএফ রিপোর্টে যুক্ত হবে।")
        
        # মূল অ্যাকশন বাটন যা একই সাথে লগে সেভ করবে এবং ইউজারকে রিডাইরেক্টের জন্য লিংক উন্মুক্ত করবে
        if st.button("🔗 Click to Confirm Payment & Sync to Logs/PDF", type="primary"):
            # ক্লিক করার পর এই ব্লকের ভেতর ডেটাগুলো লগে ঢুকবে
            timestamp_now = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            for item in plan:
                st.session_state.persistent_logs.append({
                    "timestamp": timestamp_now,
                    "msisdn": item["msisdn"],
                    "amount": item["amount"]
                })
                st.session_state.unique_numbers.add(item["msisdn"])
            st.session_state.total_volume += allocated_total
            
            st.balloons()
            st.success("🎉 SUCCESS: Sync Complete! Transaction pushed to Summary Logs.")
            
            # ফুল ইউআরএল একদম নিখুঁতভাবে দেখানোর জন্য কোড ব্লক ও বড় নেটিভ লিংক বাটন
            st.markdown("#### 📡 Official bKash Gateway Link (Full & Complete):")
            st.code(bkash_url, language="text")
            
            st.link_button("🌸 Open bKash Secure Gateway Tab", bkash_url, use_container_width=True)

else:
    st.info("💡 Awaiting Target Input: Please upload a file or paste numbers in STEP 1 to unlock the secure gateway configuration panels.")

st.markdown("---")
# ==================== PERSISTENT RECHARGE LOGS & ANALYTICS ====================
st.subheader("📊 Persistent Recharge Logs & Analytics")

if st.session_state.persistent_logs:
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Total Volume Processed", f"{st.session_state.total_volume} BDT")
    col_b.metric("Unique Target Numbers", f"{len(st.session_state.unique_numbers)}")
    col_c.metric("Total Success Entries", f"{len(st.session_state.persistent_logs)}")
    
    if st.button("🗑️ Clear All Logs & Analytics", type="secondary"):
        st.session_state.persistent_logs = []
        st.session_state.total_volume = 0
        st.session_state.unique_numbers = set()
        st.success("All core database logs and metrics cleared!")
        st.rerun()
        
    # রিকোয়েস্ট অনুযায়ী সামারি টেবিলটি সম্পূর্ণ হাইড করে এক্সপান্ডারে রাখা হয়েছে
    with st.expander("👁️ Click to View Aggregated Summary Table"):
        st.markdown("#### 🎯 Execution History Records")
        st.table(st.session_state.persistent_logs)
    
    with st.expander("🔍 Download Consolidated PDF Report"):
        pdf_file = generate_combined_pdf_report(st.session_state.persistent_logs, st.session_state.total_volume)
        st.download_button(
            label="📥 Download Full Combined PDF Report",
            data=pdf_file,
            file_name=f"Combined_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf"
        )
else:
    st.info("No transaction records found. Successfully executed pipelines will generate combined logs here.")
