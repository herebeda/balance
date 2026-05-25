import os
import sys
import asyncio
import json
import re
import streamlit as st

# ==================== AUTOMATIC BROWSER INSTALLATION ====================
@st.cache_resource
def initialize_playwright_browser():
    os.system(f"{sys.executable} -m playwright install chromium")
    return True

initialize_playwright_browser()
# ========================================================================

from playwright.async_api import async_playwright

# ==================== CONFIGURATION ====================
MAX_RECHARGE_LIMIT = 1000  
MIN_RECHARGE_LIMIT = 20    
# =======================================================

# --- PREMIUM UI CUSTOM CSS INJECTION ---
st.set_page_config(page_title="GP Recharge Bundle System", page_icon="📱", layout="centered")

st.markdown("""
    <style>
        /* Main Background & Font Tweak */
        .main {
            background-color: #0e1117;
            font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
        }
        
        /* Modern Card Layout for inputs */
        div.stForm, div[data-testid="stBlock"] {
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
            backdrop-filter: blur(5px);
        }
        
        /* macOS Style Inputs */
        .stTextInput>div>div>input, .stTextArea>div>div>textarea {
            background-color: rgba(255, 255, 255, 0.05) !important;
            color: #ffffff !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            border-radius: 8px !important;
            transition: all 0.3s ease-in-out;
        }
        .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {
            border-color: #007aff !important;
            box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.25) !important;
        }
        
        /* Process Button Custom Styling */
        .stButton>button {
            width: 100%;
            background: linear-gradient(135deg, #007aff, #0051a8);
            color: white !important;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            letter-spacing: 0.5px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(0, 122, 255, 0.3);
        }
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 122, 255, 0.5);
            background: linear-gradient(135deg, #0088ff, #0066cc);
        }
        
        /* Title Header Animation */
        .ui-title {
            text-align: center;
            background: linear-gradient(45deg, #007aff, #34c759, #ffcc00);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
            margin-bottom: 25px;
        }

        /* 👑 bKash Premium Animated Button Keyframes */
        @keyframes bkash-pulse {
            0% { box-shadow: 0 0 0 0 rgba(226, 19, 110, 0.7); }
            70% { box-shadow: 0 0 0 18px rgba(226, 19, 110, 0); }
            100% { box-shadow: 0 0 0 0 rgba(226, 19, 110, 0); }
        }
        @keyframes gradient-shift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        /* Animated Button Class */
        .premium-bkash-btn {
            background: linear-gradient(-45deg, #E2136E, #F81F8F, #C30B5C, #E2136E);
            background-size: 300% 300%;
            animation: gradient-shift 4s ease infinite, bkash-pulse 2s infinite;
            color: white !important;
            padding: 16px 35px;
            text-align: center;
            border-radius: 12px;
            font-size: 19px;
            font-weight: bold;
            font-family: 'Arial', sans-serif;
            cursor: pointer;
            display: inline-block;
            text-decoration: none;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .premium-bkash-btn:hover {
            transform: scale(1.06) translateY(-3px);
            filter: brightness(1.1);
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='ui-title'>📱 GP Recharge Bundle Engine</h1>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload 'gp.txt' file containing numbers", type=["txt"])

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

async def inject_gp_live_pipeline(pipeline_plan, customer_email):
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--no-zygote',
                    '--single-process',
                    '--ignore-certificate-errors'
                ]
            )
            context = await browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page1 = await context.new_page()
            await page1.add_init_script("delete navigator.__proto__.webdriver;")
        except Exception as e:
            return {"success": False, "error": f"Browser Initialization Failed: {str(e)}"}
        
        session_id_container = [None]
        async def handle_response(response):
            if "payments.grameenphone.com/ui/recharge/" in response.url:
                match = re.search(r'/ui/recharge/([a-f0-9]{32})', response.url)
                if match:
                    session_id_container[0] = match.group(1)

        page1.on("response", handle_response)
        try:
            await page1.goto("https://www.grameenphone.com/recharge", wait_until="domcontentloaded", timeout=50000)
            await asyncio.sleep(5)
        except Exception as e:
            await browser.close()
            return {"success": False, "error": f"GP Portal connection timeout: {str(e)}"}
        
        if not session_id_container[0]:
            current_url = page1.url
            match = re.search(r'/recharge/([a-f0-9]{32})', current_url)
            if match:
                session_id_container[0] = match.group(1)
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
            "ui": "bulk_recharge",
            "campaign_code": "",
            "campaign_payment_method": "bkash",
            "channel_campaign_codes": "",
            "identifier": "",
            "agreementType": 0
        }

        js_submit_routing = """
        async (config) => {
            try {
                const response = await fetch('https://payments.grameenphone.com/ui/api/submit-routing', {
                    method: 'POST',
                    headers: {
                        'Accept': 'application/json, text/plain, */*',
                        'Content-Type': 'application/json'
                    },
                    body: config.payloadStr
                });
                return await response.json();
            } catch (err) {
                return {"success": false, "error": err.toString()};
            }
        }
        """
        try:
            api_response = await page1.evaluate(js_submit_routing, {"payloadStr": json.dumps(payload_data)})
        except Exception as e:
            api_response = {"success": False, "error": f"JS Injection failed: {str(e)}"}
            
        await browser.close()
        return api_response

# --- UI Layout Logic ---
if uploaded_file is not None:
    file_content = uploaded_file.read().decode("utf-8")
    target_numbers = parse_uploaded_numbers(file_content)
    st.success(f"📦 Successfully loaded {len(target_numbers)} numbers from file.")
    
    col1, col2 = st.columns(2)
    with col1:
        mode = st.radio("🚀 Choose Mode", ['Normal', '5-min Jitter (Anti-Duplicate)'])
        anti_duplicate = True if mode == '5-min Jitter (Anti-Duplicate)' else False
    with col2:
        customer_email_input = st.text_input("📧 Customer Email Address:", value="emailhere@gmail.com")

    seu_input = st.text_area("📋 Paste your SEU SCOUT output data here:", height=150)

    if st.button("⚡ Process & Generate Recharge Link"):
        if not seu_input.strip():
            st.error("Please paste SEU output data first.")
        elif not customer_email_input.strip():
            st.error("Please provide a valid email address.")
        else:
            total_exact_balance = parse_seu_balances(seu_input)
            if total_exact_balance == 0:
                st.error("Could not extract any valid Exact Balance.")
            else:
                st.metric(label="💰 Total Input Balance Detected", value=f"{total_exact_balance} BDT")
                pipeline_plan, total_planned, leftover = distribute_amount(total_exact_balance, target_numbers, anti_duplicate)
                
                if not pipeline_plan:
                    st.error("No valid round recharge plan could be generated.")
                else:
                    st.subheader("📊 Auto-Adjusted Recharge Plan")
                    st.write(f"**Total Allocated:** `{total_planned} BDT` | **Leftover:** `{leftover} BDT`")
                    st.json(pipeline_plan)
                    
                    with st.spinner("Connecting Secure Tunnel to Grameenphone Engine Architecture..."):
                        api_response = asyncio.run(inject_gp_live_pipeline(pipeline_plan, customer_email_input.strip()))
                        
                    if api_response and api_response.get("success") and "data" in api_response and "redirectUrl" in api_response["data"]:
                        raw_url = api_response["data"]["redirectUrl"].strip()
                        
                        if raw_url.endswith('/'):
                            raw_url = raw_url[:-1]
                        
                        st.balloons()
                        st.success("🎉 SUCCESS: GRAMEENPHONE SPLIT BUNDLE GENERATED!")
                        
                        st.info("💡 বাটন কাজ না করলে নিচের বক্স থেকে লিঙ্কটি দ্রুত কপি করে ব্রাউজারে পেস্ট করুন:")
                        st.text_area("🔗 bKash URL Backup Link", value=raw_url, height=70)
                        
                        # ✨ সুপার অ্যানিমেটেড প্রিমিয়াম বিকাশ বাটন (Gradient Wave + Pulsing Glow Effect)
                        button_html = """
                            <div style="text-align: center; margin-top: 25px; margin-bottom: 25px;">
                                <a href='CHANGE_TO_REAL_URL' target="_blank" class="premium-bkash-btn">
                                    🌸 Click Here to Open bKash Secure Gateway
                                </a>
                            </div>
                        """.replace("CHANGE_TO_REAL_URL", raw_url)
                        
                        st.markdown(button_html, unsafe_allow_html=True)
                    else:
                        st.error("GP Server rejected payload or connection dropped.")
                        st.json(api_response)
else:
    st.info("💡 Getting Started: Please upload a 'gp.txt' file to unlock the system core.")
