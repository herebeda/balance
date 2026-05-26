import streamlit as st
import os
import sys
import re
import asyncio
import json
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
    """
    গ্লোবাল রেগুলার এক্সপ্রেশন ইঞ্জিন: টেক্সটের ভেতর থেকে সমস্ত 013 এবং 017 নাম্বার 
    সেপারেটর নির্বিশেষে (কমা, স্পেস, নিউলাইন) নিখুঁতভাবে এক্সট্রাক্ট করবে।
    """
    if not raw_text:
        return []
    
    matches = re.findall(r'(?:88)?01[37]\d{8}', raw_text)
    
    valid_numbers = []
    for num in matches:
        if num.startswith('880'):
            cleaned = num[2:]  # 88 বাদ দিয়ে মূল ১১ ডিজিট রাখবে
        else:
            cleaned = num
        valid_numbers.append(cleaned)
        
    return list(dict.fromkeys(valid_numbers))  # ডুপ্লিকেট রিমুভ করবে

def parse_flexible_balance(input_data):
    """
    SEU SCOUT ফরম্যাট এবং ডিরেক্ট র অ্যামাউন্ট (যেমন: 5000) দুটাই হ্যান্ডেল করবে
    """
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
    """
    সমস্ত লগ হিস্ট্রি এবং গ্র্যান্ড টোটাল একসাথে সিঙ্গেল ফাইলে জেনারেট করার ইঞ্জিন
    """
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

# ==================== STREAMLIT UI & CYBERPUNK CSS CUSTOMIZATION ====================
st.set_page_config(page_title="GP Recharge Bundle Engine", page_icon="📱", layout="wide")

cyberpunk_css = """
<style>
    /* Global Cyberpunk Dark Theme with Subtle Neon Gradient Radial */
    .stApp {
        background-color: #05050a !important;
        background-image: radial-gradient(at 0% 0%, hsla(250,30%,10%,1) 0, transparent 40%),
                          radial-gradient(at 100% 100%, hsla(330,50%,12%,1) 0, transparent 40%) !important;
        color: #e2e8f0 !important;
    }
    
    /* Neon Text Styling for Headers */
    h1, h2, h3, h4 {
        color: #00f0ff !important;
        text-shadow: 0 0 10px rgba(0, 240, 255, 0.5), 0 0 20px rgba(0, 240, 255, 0.2) !important;
        font-family: 'Courier New', Courier, monospace !important;
    }
    
    /* Input Fields Glassmorphism Effect */
    div[data-baseweb="textarea"], div[data-baseweb="input"], .stFileUploader {
        background: rgba(255, 255, 255, 0.03) !important;
        backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(0, 240, 255, 0.25) !important;
        border-radius: 12px !important;
        box-shadow: inset 0 0 12px rgba(0, 240, 255, 0.05), 0 4px 15px rgba(0,0,0,0.5) !important;
        color: #ffffff !important;
        transition: all 0.3s ease;
    }
    div[data-baseweb="textarea"]:focus-within, div[data-baseweb="input"]:focus-within {
        border-color: #ff007f !important;
        box-shadow: 0 0 15px rgba(255, 0, 127, 0.4) !important;
    }
    
    /* Labels styling */
    label, .stWidgetFormLabel p {
        color: #00f0ff !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px;
    }
    
    /* Primary Neon Pink Button */
    .stButton>button[kind="primary"] {
        background: linear-gradient(45deg, #ff007f, #b500ff) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        font-size: 16px !important;
        padding: 12px 28px !important;
        box-shadow: 0 0 15px rgba(255, 0, 127, 0.5) !important;
        text-shadow: 0 1px 2px rgba(0,0,0,0.5);
        transition: all 0.3s ease-in-out !important;
    }
    .stButton>button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 0 25px rgba(255, 0, 127, 0.9), 0 0 35px rgba(181, 0, 255, 0.4) !important;
    }
    
    /* Secondary Neon Yellow/Orange Button */
    .stButton>button[kind="secondary"] {
        background: rgba(15, 15, 25, 0.8) !important;
        color: #fdee11 !important;
        border: 1px solid #fdee11 !important;
        border-radius: 8px !important;
        box-shadow: 0 0 10px rgba(253, 238, 17, 0.2) !important;
        transition: all 0.3s ease !important;
    }
    .stButton>button[kind="secondary"]:hover {
        background: #fdee11 !important;
        color: #000000 !important;
        box-shadow: 0 0 20px rgba(253, 238, 17, 0.7) !important;
    }
    
    /* Glassy Analytics / Alert Cards */
    div[data-testid="stNotification"] {
        background: rgba(10, 10, 20, 0.6) !important;
        backdrop-filter: blur(10px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-left: 5px solid #00f0ff !important;
        border-radius: 10px !important;
    }
    
    /* Metric Vibe */
    div[data-testid="stMetricValue"] {
        color: #ff007f !important;
        font-weight: 800 !important;
        text-shadow: 0 0 12px rgba(255, 0, 127, 0.6) !important;
    }
    
    /* Transparent Background for Tables & JSON JSON */
    .stJson, div[data-testid="stTable"] {
        background: rgba(255, 255, 255, 0.02) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 10px;
    }
</style>
"""
st.markdown(cyberpunk_css, unsafe_allow_html=True)

st.title("⚡ GP RECHARGE BUNDLE ENGINE")
st.markdown("<p style='color:#ff007f; font-weight:bold; letter-spacing:1px;'>[ SYSTEM STATUS: CYBER-PIPELINE ONLINE ]</p>", unsafe_allow_html=True)
st.markdown("---")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📥 Target Numbers Input Source")
    
    # ফাইল আপলোড অপশন
    uploaded_file = st.file_uploader("Option A: Upload text file containing numbers (gp.txt)", type=["txt"])
    
    # ডিরেক্ট পেস্ট বক্স (স্মার্ট রেগুলার এক্সপ্রেশন সাপোর্টেড)
    pasted_numbers = st.text_area("Option B: Paste Target Numbers directly here (Any format):", height=120, placeholder="017XXXXXXXX\n013XXXXXXXX, 88017XXXXXXXX")
    
    # দুটো সোর্স কম্বাইন করা হচ্ছে
    combined_raw_numbers = ""
    if uploaded_file is not None:
        combined_raw_numbers += uploaded_file.read().decode("utf-8") + "\n"
    if pasted_numbers:
        combined_raw_numbers += pasted_numbers

    target_numbers = parse_numbers(combined_raw_numbers)
    if target_numbers:
        st.success(f"📦 Total Loaded & Filtered: {len(target_numbers)} unique numbers.")

    st.subheader("🚀 Choose Mode")
    mode = st.radio("Execution Strategy", ["Normal", "5-min Jitter (Anti-Duplicate)"], label_visibility="collapsed")
    customer_email = st.text_input("📧 Customer Email Address:")

with col2:
    st.subheader("📋 Paste your SEU SCOUT output data or Raw Amount here:")
    scout_input = st.text_area("Paste balance info here", height=150, placeholder="Example 1 (SCOUT):\nNumber: 01713532100 | Exact Balance: 20145 BDT\n\nExample 2 (Raw Amount):\n5000")
    
    detected_balance = parse_flexible_balance(scout_input)
    st.metric(label="💰 Total Input Balance Detected", value=f"{detected_balance} BDT")

# ==================== PLAN GENERATION & EXECUTION ====================
if target_numbers and detected_balance > 0:
    st.markdown("---")
    st.markdown("### 📊 Auto-Adjusted Plan Grid")
    
    plan = []
    allocated_total = 0
    jitter_amount = 1000  # জিটার মোডের জন্য প্রারম্ভিক বেস অ্যামাউন্ট
    
    for num in target_numbers:
        # মোড অনুযায়ী অ্যামাউন্ট লজিক
        if mode == "Normal":
            amt_to_charge = 1000
        else:  # 5-min Jitter (Anti-Duplicate)
            amt_to_charge = jitter_amount
            
        # ব্যালেন্স চেক করে প্ল্যানে সেট করা
        if allocated_total + amt_to_charge <= detected_balance:
            if amt_to_charge > 0:
                plan.append({"msisdn": num, "amount": amt_to_charge})
                allocated_total += amt_to_charge
                
                # জিটার মোড অ্যাক্টিভ থাকলে পরবর্তী নাম্বারের জন্য ২০ টাকা মাইনাস হবে
                if mode == "5-min Jitter (Anti-Duplicate)":
                    jitter_amount -= 20
                    if jitter_amount < 20:  
                        jitter_amount = 1000
        else:
            break
            
    leftover = detected_balance - allocated_total
    
    c1, c2 = st.columns(2)
    c1.info(f"**Total Allocated:** {allocated_total} BDT")
    c2.warning(f"**Leftover / Unallocated:** {leftover} BDT")
    
    st.json(plan)
    
    if st.button("⚡ Process & Generate bKash Gateway Link", type="primary"):
        mock_payment_id = f"TR0011{datetime.now().strftime('%f%M%S')}"
        bkash_url = f"https://payment.bkash.com/?paymentId={mock_payment_id}&mode=0011&apiVersion=v1.2.0-beta"
        
        st.balloons()
        st.success("🎉 SUCCESS: CYBER LINK GENERATED!")
        st.code(bkash_url, language="text")
        st.markdown(f'<a href="{bkash_url}" target="_blank" style="background: linear-gradient(45deg, #E11D48, #ff007f); color:white; padding:14px 28px; text-align:center; text-decoration:none; display:inline-block; border-radius:10px; font-weight:bold; font-size:16px; box-shadow: 0 0 20px rgba(225,29,72,0.6);">🌸 Click Here to Open bKash Secure Gateway</a>', unsafe_allow_html=True)
        
        # ডাটাবেজ বা সেশন লগে পুশ
        timestamp_now = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        for item in plan:
            st.session_state.persistent_logs.append({
                "timestamp": timestamp_now,
                "msisdn": item["msisdn"],
                "amount": item["amount"]
            })
            st.session_state.unique_numbers.add(item["msisdn"])
        st.session_state.total_volume += allocated_total

st.markdown("---")
# ==================== PERSISTENT RECHARGE LOGS & ANALYTICS ====================
st.subheader("📊 Persistent Recharge Logs & Analytics")

if st.session_state.persistent_logs:
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Total Volume Processed", f"{st.session_state.total_volume} BDT")
    col_b.metric("Unique Target Numbers", f"{len(st.session_state.unique_numbers)}")
    col_c.metric("Total Success Entries", f"{len(st.session_state.persistent_logs)}")
    
    # নিয়ন ইয়েলো থিমের ক্লিয়ার লগ বাটন
    if st.button("🗑️ Clear All Logs & Analytics", type="secondary"):
        st.session_state.persistent_logs = []
        st.session_state.total_volume = 0
        st.session_state.unique_numbers = set()
        st.success("All core database logs and metrics cleared!")
        st.rerun()
        
    st.markdown("#### 🎯 Aggregated Summary Table")
    st.table(st.session_state.persistent_logs)
    
    # একত্রে সম্পূর্ণ পিডিএফ রিপোর্ট ডাউনলোড
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
