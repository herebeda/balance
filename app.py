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
def parse_uploaded_numbers(file_content):
    raw_tokens = re.split(r'[\s,;\t\n\r]+', file_content)
    valid_numbers = []
    for token in raw_tokens:
        digits_only = re.sub(r'\D', '', token)
        if len(digits_only) >= 11:
            if digits_only.startswith('880'):
                digits_only = '0' + digits_only[3:]
            if digits_only.startswith('013') or digits_only.startswith('017'):
                valid_numbers.append(digits_only[:11])
    return list(dict.fromkeys(valid_numbers))

def parse_flexible_balance(input_data):
    """
    SEU SCOUT ফরম্যাট এবং ডিরেক্ট র অ্যামাউন্ট (যেমন: 4500) দুটাই হ্যান্ডেল করবে
    """
    if not input_data:
        return 0
    # প্রথমে চেক করবে 'Exact Balance: 20145 BDT' টাইপ ফরম্যাট আছে কিনা
    match = re.search(r'(?:Exact\s+Balance:\s*)(\d+)', input_data, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    # যদি না থাকে, তবে ইনপুটের প্রথম বা প্রধান সংখ্যাটি এক্সট্রাক্ট করবে (যেমন: 4500)
    numbers = re.findall(r'\d+', input_data)
    if numbers:
        return int(numbers[0])
    return 0

def generate_combined_pdf_report(logs, total_vol):
    """
    আলাদা আলাদা না করে সমস্ত লগ একসাথে একটি ফাইলে গ্র্যান্ড টোটালসহ জেনারেট করবে
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, leading=24, textColor=colors.HexColor('#0F172A'), alignment=1)
    meta_style = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#475569'))
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#334155'))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=10, textColor=colors.white, fontName='Helvetica-Bold')

    # Title & Header
    story.append(Paragraph("GP Recharge Engine - Combined Audit Summary", title_style))
    story.append(Spacer(1, 15))
    story.append(Paragraph(f"<b>Report Generated:</b> {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}", meta_style))
    story.append(Paragraph(f"<b>Total Processed Volume:</b> {total_vol} BDT", meta_style))
    story.append(Paragraph(f"<b>Total Target Records:</b> {len(logs)} entries", meta_style))
    story.append(Spacer(1, 20))
    
    # Table Data Structure
    table_data = [[
        Paragraph("Timestamp", header_style),
        Paragraph("Target MSISDN", header_style),
        Paragraph("Allocated Amount", header_style),
        Paragraph("Status / Action", header_style)
    ]]
    
    for entry in logs:
        table_data.append([
            Paragraph(entry.get('timestamp', '-'), cell_style),
            Paragraph(entry.get('msisdn', '-'), cell_style),
            Paragraph(f"{entry.get('amount', 0)} BDT", cell_style),
            Paragraph("Pipeline Executed Successfully", cell_style)
        ])
        
    log_table = Table(table_data, colWidths=[130, 120, 110, 180])
    log_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    
    story.append(log_table)
    doc.build(story)
    buffer.seek(0)
    return buffer

# ==================== STREAMLIT UI RENDER ====================
st.set_page_config(page_title="GP Recharge Bundle Engine", page_icon="📱", layout="wide")

st.title("📱 GP Recharge Bundle Engine")
st.markdown("---")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📥 Target Numbers Input Source")
    uploaded_file = st.file_uploader("Upload text file containing numbers (gp.txt)", type=["txt"])
    
    target_numbers = []
    if uploaded_file is not None:
        file_content = uploaded_file.read().decode("utf-8")
        target_numbers = parse_uploaded_numbers(file_content)
        st.success(f"📦 Loaded {len(target_numbers)} numbers.")

    st.subheader("🚀 Choose Mode")
    mode = st.radio("Execution Strategy", ["Normal", "5-min Jitter (Anti-Duplicate)"], label_visibility="collapsed")
    customer_email = st.text_input("📧 Customer Email Address:")

with col2:
    st.subheader("📋 Paste your SEU SCOUT output data or Raw Amount here:")
    scout_input = st.text_area("Paste input data", height=120, placeholder="Example:\nNumber: 01713532100 | Exact Balance: 20145 BDT\nOR simply enter:\n4500")
    
    detected_balance = parse_flexible_balance(scout_input)
    st.metric(label="💰 Total Input Balance Detected", value=f"{detected_balance} BDT")

# ==================== PLAN GENERATION & EXECUTION ====================
if target_numbers and detected_balance > 0:
    st.markdown("### 📊 Auto-Adjusted Plan")
    
    plan = []
    allocated_total = 0
    
    for num in target_numbers:
        if allocated_total + 1000 <= detected_balance:
            plan.append({"msisdn": num, "amount": 1000})
            allocated_total += 1000
            
    leftover = detected_balance - allocated_total
    st.write(f"**Total Allocated:** {allocated_total} BDT | **Leftover:** {leftover} BDT")
    st.json(plan)
    
    if st.button("⚡ Process & Generate bKash Gateway Link", type="primary"):
        # মক পেমেন্ট লিঙ্ক জেনারেট (সিমুলেশন পাইপলাইন)
        mock_payment_id = f"TR0011{datetime.now().strftime('%f%L%M%S')}"
        bkash_url = f"https://payment.bkash.com/?paymentId={mock_payment_id}&mode=0011&apiVersion=v1.2.0-beta"
        
        st.balloons()
        st.success("🎉 SUCCESS: LINK GENERATED!")
        st.code(bkash_url, language="text")
        st.markdown(f'<a href="{bkash_url}" target="_blank" style="background-color:#E11D48;color:white;padding:10px 20px;text-align:center;text-decoration:none;display:inline-block;border-radius:8px;font-weight:bold;">🌸 Click Here to Open bKash Secure Gateway</a>', unsafe_allow_html=True)
        
        # সেশন লগে ডাটা পুশ করা হচ্ছে
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
    col_b.metric("Total Success Logs", f"{len(st.session_state.persistent_logs)}")
    
    # ক্লিয়ার লগ বাটন
    if st.button("🗑️ Clear All Logs & Analytics", type="secondary"):
        st.session_state.persistent_logs = []
        st.session_state.total_volume = 0
        st.session_state.unique_numbers = set()
        st.success("Logs cleared successfully!")
        st.rerun()
        
    st.markdown("#### 🎯 Aggregated Target Numbers Summary")
    st.table(st.session_state.persistent_logs)
    
    # সম্মিলিত পিডিএফ জেনারেশন বাটন (Combined PDF Report)
    with st.expander("🔍 Download Consolidated PDF Report"):
        pdf_file = generate_combined_pdf_report(st.session_state.persistent_logs, st.session_state.total_volume)
        st.download_button(
            label="📥 Download Full Combined PDF Report",
            data=pdf_file,
            file_name=f"Combined_Recharge_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf"
        )
else:
    st.info("No transaction records found. Successfully executed pipelines will generate logs here.")
