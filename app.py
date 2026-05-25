import asyncio
import json
import re
import sys
import os
import streamlit as st

# ==================== AUTOMATIC BROWSER INSTALLATION ====================
if not os.path.exists(os.path.expanduser("~/.cache/ms-playwright")):
    with st.spinner("Downloading Headless Chromium... Please wait..."):
        os.system("playwright install chromium")
# ========================================================================
from playwright.async_api import async_playwright

# ==================== CONFIGURATION ====================
MAX_RECHARGE_LIMIT = 1000  
MIN_RECHARGE_LIMIT = 20    
CUSTOMER_EMAIL = "emailhere@gmail.com"  
# =======================================================

st.set_page_config(page_title="GP Recharge Bundle System", page_icon="📱", layout="centered")
st.title("📱 GP Recharge Bundle System")

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

async def inject_gp_live_pipeline(pipeline_plan):
    async with async_playwright() as p:
        try:
            # ওএস এবং বিকাশ ব্লকিং বাইপাস করার জন্য প্রো-ফ্ল্যাগস
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
            # অবজেক্ট ডিটেকশন ট্র্যাকিং হাইড করার স্ক্রিপ্ট
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
            "customerEmail": CUSTOMER_EMAIL,
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
    st.success(f"Successfully loaded {len(target_numbers)} numbers from file.")
    
    # মোড সিলেকশন (লজিক এখন ১০০% ডায়নামিক)
    mode = st.radio("Choose Mode", ['Normal', '5-min Jitter (Anti-Duplicate)'])
    anti_duplicate = True if mode == '5-min Jitter (Anti-Duplicate)' else False

    seu_input = st.text_area("Paste your SEU SCOUT output data here:", height=150)

    if st.button("Process & Generate Recharge Link"):
        if not seu_input.strip():
            st.error("Please paste SEU output data first.")
        else:
            total_exact_balance = parse_seu_balances(seu_input)
            if total_exact_balance == 0:
                st.error("Could not extract any valid Exact Balance.")
            else:
                st.metric(label="Total Input Balance Detected", value=f"{total_exact_balance} BDT")
                pipeline_plan, total_planned, leftover = distribute_amount(total_exact_balance, target_numbers, anti_duplicate)
                
                if not pipeline_plan:
                    st.error("No valid round recharge plan could be generated.")
                else:
                    st.subheader("Auto-Adjusted Recharge Plan")
                    st.write(f"**Total Allocated:** {total_planned} BDT | **Leftover:** {leftover} BDT")
                    st.json(pipeline_plan)
                    
                    with st.spinner("Connecting Secure Tunnel to Grameenphone Engine Architecture..."):
                        api_response = asyncio.run(inject_gp_live_pipeline(pipeline_plan))
                        
                    if api_response and api_response.get("success") and "data" in api_response and "redirectUrl" in api_response["data"]:
                        raw_url = api_response["data"]["redirectUrl"].strip()
                        
                        # অবান্তর স্ল্যাশ ট্রিম করা হলো
                        if raw_url.endswith('/'):
                            raw_url = raw_url[:-1]
                        
                        st.balloons()
                        st.success("🎉 SUCCESS: GRAMEENPHONE SPLIT BUNDLE GENERATED!")
                        
                        # ব্যাকআপ টেক্সট বক্স (যদি সেশন খুব দ্রুত এক্সপায়ার হয়ে যায়)
                        st.info("💡 বাটন কাজ না করলে নিচের বক্স থেকে লিঙ্কটি দ্রুত কপি করে ব্রাউজারে পেস্ট করুন:")
                        st.text_area("bKash URL Backup Link", value=raw_url, height=70)
                        
                        # আল্ট্রা-সুরক্ষিত রিলিজ বাটন
                        button_html = """
                            <div style="text-align: center; margin-top: 15px;">
                                <a href='CHANGE_TO_REAL_URL' target="_blank" style="text-decoration: none;">
                                    <div style="
                                        background-color: #E2136E; 
                                        color: white; 
                                        padding: 14px 28px; 
                                        text-align: center; 
                                        border-radius: 8px; 
                                        font-size: 18px; 
                                        font-weight: bold;
                                        font-family: 'Arial', sans-serif;
                                        box-shadow: 0px 4px 15px rgba(226, 19, 110, 0.4);
                                        cursor: pointer;
                                        display: inline-block;
                                    ">
                                        👉 Click Here to Open bKash Secure Gateway
                                    </div>
                                </a>
                            </div>
                        """.replace("CHANGE_TO_REAL_URL", raw_url)
                        
                        st.markdown(button_html, unsafe_allow_html=True)
                    else:
                        st.error("GP Server rejected payload or connection dropped.")
                        st.json(api_response)
else:
st.warning("Please upload a 'gp.txt' file to proceed.")
import asyncio
import json
import re
import sys
import os
import streamlit as st

# ==================== AUTOMATIC BROWSER INSTALLATION ====================
if not os.path.exists(os.path.expanduser("~/.cache/ms-playwright")):
    with st.spinner("Downloading Headless Chromium... Please wait..."):
        os.system("playwright install chromium")
# ========================================================================
from playwright.async_api import async_playwright

# ==================== CONFIGURATION ====================
MAX_RECHARGE_LIMIT = 1000  
MIN_RECHARGE_LIMIT = 20    
CUSTOMER_EMAIL = "emailhere@gmail.com"  
# =======================================================

st.set_page_config(page_title="GP Recharge Bundle System", page_icon="📱", layout="centered")
st.title("📱 GP Recharge Bundle System")

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

async def inject_gp_live_pipeline(pipeline_plan):
    async with async_playwright() as p:
        try:
            # ওএস এবং বিকাশ ব্লকিং বাইপাস করার জন্য প্রো-ফ্ল্যাগস
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
            # অবজেক্ট ডিটেকশন ট্র্যাকিং হাইড করার স্ক্রিপ্ট
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
            "customerEmail": CUSTOMER_EMAIL,
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
    st.success(f"Successfully loaded {len(target_numbers)} numbers from file.")
    
    # মোড সিলেকশন (লজিক এখন ডায়নামিক)
    mode = st.radio("Choose Mode", ['Normal', '5-min Jitter (Anti-Duplicate)'])
    anti_duplicate = True if mode == '5-min Jitter (Anti-Duplicate)' else False

    seu_input = st.text_area("Paste your SEU SCOUT output data here:", height=150)

    if st.button("Process & Generate Recharge Link"):
        if not seu_input.strip():
            st.error("Please paste SEU output data first.")
        else:
            total_exact_balance = parse_seu_balances(seu_input)
            if total_exact_balance == 0:
                st.error("Could not extract any valid Exact Balance.")
            else:
                st.metric(label="Total Input Balance Detected", value=f"{total_exact_balance} BDT")
                pipeline_plan, total_planned, leftover = distribute_amount(total_exact_balance, target_numbers, anti_duplicate)
                
                if not pipeline_plan:
                    st.error("No valid round recharge plan could be generated.")
                else:
                    st.subheader("Auto-Adjusted Recharge Plan")
                    st.write(f"**Total Allocated:** {total_planned} BDT | **Leftover:** {leftover} BDT")
                    st.json(pipeline_plan)
                    
                    with st.spinner("Connecting Secure Tunnel to Grameenphone Engine Architecture..."):
                        api_response = asyncio.run(inject_gp_live_pipeline(pipeline_plan))
                        
                    if api_response and api_response.get("success") and "data" in api_response and "redirectUrl" in api_response["data"]:
                        raw_url = api_response["data"]["redirectUrl"].strip()
                        
                        # অবান্তর স্ল্যাশ ট্রিম করা হলো
                        if raw_url.endswith('/'):
                            raw_url = raw_url[:-1]
                        
                        st.balloons()
                        st.success("🎉 SUCCESS: GRAMEENPHONE SPLIT BUNDLE GENERATED!")
                        
                        # ব্যাকআপ টেক্সট বক্স (যদি সেশন খুব দ্রুত এক্সপায়ার হয়ে যায়)
                        st.info("💡 বাটন কাজ না করলে নিচের বক্স থেকে লিঙ্কটি দ্রুত কপি করে ব্রাউজারে পেস্ট করুন:")
                        st.text_area("bKash URL Backup Link", value=raw_url, height=70)
                        
                        # আল্ট্রা-সুরক্ষিত রিলিজ বাটন
                        button_html = """
                            <div style="text-align: center; margin-top: 15px;">
                                <a href='CHANGE_TO_REAL_URL' target="_blank" style="text-decoration: none;">
                                    <div style="
                                        background-color: #E2136E; 
                                        color: white; 
                                        padding: 14px 28px; 
                                        text-align: center; 
                                        border-radius: 8px; 
                                        font-size: 18px; 
                                        font-weight: bold;
                                        font-family: 'Arial', sans-serif;
                                        box-shadow: 0px 4px 15px rgba(226, 19, 110, 0.4);
                                        cursor: pointer;
                                        display: inline-block;
                                    ">
                                        👉 Click Here to Open bKash Secure Gateway
                                    </div>
                                </a>
                            </div>
                        """.replace("CHANGE_TO_REAL_URL", raw_url)
                        
                        st.markdown(button_html, unsafe_allow_html=True)
                    else:
                        st.error("GP Server rejected payload or connection dropped.")
                        st.json(api_response)
else:
    st.warning("Please upload a 'gp.txt' file to proceed.")import asyncio
import json
import re
import sys
import os
import streamlit as st

# ==================== AUTOMATIC BROWSER INSTALLATION ====================
if not os.path.exists(os.path.expanduser("~/.cache/ms-playwright")):
    with st.spinner("Downloading Headless Chromium... Please wait..."):
        # কোনো install-deps বা sudo কমান্ড এখানে দেওয়া যাবে না
        os.system("playwright install chromium")
# ========================================================================
from playwright.async_api import async_playwright

# ==================== CONFIGURATION ====================
MAX_RECHARGE_LIMIT = 1000  
MIN_RECHARGE_LIMIT = 20    
CUSTOMER_EMAIL = "emailhere@gmail.com"  
# =======================================================

st.set_page_config(page_title="GP Recharge Bundle System", layout="centered")
st.title("📱 GP Recharge Bundle System")

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
    pattern = r"Number:\s*([0-9]+)\s*\|\s*Exact Balance:\s*([0-9]+)\s*BDT"
    matches = re.findall(pattern, raw_input)
    total_balance = 0
    for _, amount in matches:
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

async def inject_gp_live_pipeline(pipeline_plan):
    async with async_playwright() as p:
        try:
            # চরম হেডলেস এনভায়রনমেন্ট ফ্রেন্ডলি আর্গুমেন্ট সেট
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--no-zygote',
                    '--single-process',
                    '--ignore-certificate-errors'
                ]
            )
            # নেটওয়ার্ক এবং জিপি পোর্টালে রিকোয়েস্ট ব্লক এড়াতে ফেইক ইউজার এজেন্ট ব্যবহার করা হয়েছে
            context = await browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page1 = await context.new_page()
        except Exception as e:
            return {"success": False, "error": f"Browser/Context Initialization Failed: {str(e)}"}
        
        session_id_container = [None]
        async def handle_response(response):
            if "payments.grameenphone.com/ui/recharge/" in response.url:
                match = re.search(r'/ui/recharge/([a-f0-9]{32})', response.url)
                if match:
                    session_id_container[0] = match.group(1)

        page1.on("response", handle_response)
        try:
            # ক্লাউডে অনেক সময় টাইমআউট ইগনোর করতে 'domcontentloaded' ওয়েট স্টেট দেওয়া হলো
            await page1.goto("https://www.grameenphone.com/recharge", wait_until="domcontentloaded", timeout=50000)
            await asyncio.sleep(5)
        except Exception as e:
            await browser.close()
            return {"success": False, "error": f"GP Portal connection timeout on Cloud Server: {str(e)}"}
        
        if not session_id_container[0]:
            current_url = page1.url
            match = re.search(r'/recharge/([a-f0-9]{32})', current_url)
            if match:
                session_id_container[0] = match.group(1)
            else:
                await browser.close()
                return {"success": False, "error": "Could not intercept GP Gateway Session ID. Gateway might be blocking automated cloud IPs."}

        session_id = session_id_container[0]
        products_list = [{"type": "postpaid", "msisdn": item["msisdn"], "amount": item["amount"]} for item in pipeline_plan]

        payload_data = {
            "sessionId": session_id,
            "paymentType": "bkash",
            "customerEmail": CUSTOMER_EMAIL,
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
    st.success(f"Successfully loaded {len(target_numbers)} numbers from file.")
    
    mode = st.radio("Choose Mode", ('Normal', '5-min Jitter (Anti-Duplicate)'))
    anti_duplicate = True if mode == '5-min Jitter (Anti-Duplicate)' else False

    seu_input = st.text_area("Paste your SEU SCOUT output data here:", height=150)

    if st.button("Process & Generate Recharge Link"):
        if not seu_input.strip():
            st.error("Please paste SEU output data first.")
        else:
            total_exact_balance = parse_seu_balances(seu_input)
            if total_exact_balance == 0:
                st.error("Could not extract any valid Exact Balance.")
            else:
                st.info(f"Total Input Balance Detected: {total_exact_balance} BDT")
                pipeline_plan, total_planned, leftover = distribute_amount(total_exact_balance, target_numbers, anti_duplicate)
                
                if not pipeline_plan:
                    st.error("No valid round recharge plan could be generated.")
                else:
                    st.subheader("Auto-Adjusted Recharge Plan")
                    st.write(f"**Total Allocated:** {total_planned} BDT | **Leftover:** {leftover} BDT")
                    st.json(pipeline_plan)
                    
                    with st.spinner("Connecting Secure Tunnel to Grameenphone Engine Architecture..."):
                        api_response = asyncio.run(inject_gp_live_pipeline(pipeline_plan))
                        
                    if api_response and api_response.get("success") and "data" in api_response and "redirectUrl" in api_response["data"]:
                        redirect_url = api_response["data"]["redirectUrl"]
                        st.balloons()
                        st.success("🎉 SUCCESS: GRAMEENPHONE SPLIT BUNDLE GENERATED!")
                        st.markdown(f'### [👉 Click Here to Open bKash Secure Gateway]({redirect_url})')
                    else:
                        st.error("GP Server rejected payload or connection dropped.")
                        st.json(api_response)
else:
    st.warning("Please upload a 'gp.txt' file to proceed.")import streamlit as st
import os
import asyncio
import json
from playwright.async_api import async_playwright

# পেজ কনফিগারেশন এবং টাইটেল
st.set_page_config(page_title="GP Recharge Bundle System", page_icon="📱", layout="centered")

# ==================== AUTOMATIC BROWSER INSTALLATION ====================
# ক্লাউড সার্ভারে প্রথম রান করার সময় প্লে-রাইটের ব্রাউজার বাইনারি সেটআপ করবে
if not os.path.exists(os.path.expanduser("~/.cache/ms-playwright")):
    with st.spinner("Configuring System Headless Chromium... Please wait..."):
        # packages.txt থেকে লাইব্রেরি পাওয়ার পর শুধু ব্রাউজার ফাইল ডাউনলোড করবে
        os.system("playwright install chromium")
# ========================================================================

st.title("📱 GP Recharge Bundle System")

# ফাইল আপলোড সেকশন
uploaded_file = st.file_uploader("Upload 'gp.txt' file containing numbers", type=["txt"])

if uploaded_file is not None:
    # ফাইল থেকে নাম্বার রিড করা
    file_contents = uploaded_file.read().decode("utf-8")
    msisdns = [line.strip() for line in file_contents.splitlines() if line.strip()]
    st.success(f"Successfully loaded {len(msisdns)} numbers from file.")
    
    # মোড সিলেকশন
    mode = st.radio("Choose Mode", ["Normal", "5-min Jitter (Anti-Duplicate)"])
    
    # SEU SCOUT ডেটা ইনপুট
    scout_data = st.text_area("Paste your SEU SCOUT output data here:", placeholder="Number: 01820... | Exact Balance: ...")
    
    if scout_data:
        # স্যাম্পল লজিক অনুযায়ী ব্যালেন্স এক্সট্রাকশন (আপনার রিয়েল লজিক অনুযায়ী এডজাস্ট করতে পারেন)
        # এখানে জাস্ট ডেমো হিসেবে আপনার দেওয়া ১০৪৫২ বিডিটি ডিটেক্ট করা হচ্ছে
        total_balance = 10452 
        st.metric(label="Total Input Balance Detected", value=f"{total_balance} BDT")
        
        st.subheader("Auto-Adjusted Recharge Plan")
        
        # আপনার দেওয়া স্প্লিট প্ল্যান ডেমো ডাটা তৈরি
        pipeline_plan = []
        allocated = 0
        for i, msisdn in enumerate(msisdns[:11]): # লগের ডাটা স্ট্রাকচার অনুযায়ী
            amount = 980 if i < 10 else 650
            pipeline_plan.append({"msisdn": msisdn, "amount": amount})
            allocated += amount
            
        leftover = total_balance - allocated
        st.caption(f"Total Allocated: {allocated} BDT | Leftover: {leftover} BDT")
        st.json(pipeline_plan)
        
        # জিপি গেটওয়ে হিট করার মেইন ফাংশন (Playwright-এর মাধ্যমে)
        async def inject_gp_live_pipeline(plan_data):
            async with async_playwright() as p:
                try:
                    # ক্লাউড সার্ভারে ক্রমিয়াম মেমোরি ক্র্যাশ এড়ানোর জন্য স্ট্যান্ডার্ড ফ্ল্যাগস
                    browser = await p.chromium.launch(
                        headless=True,
                        args=[
                            '--no-sandbox',
                            '--disable-setuid-sandbox',
                            '--disable-dev-shm-usage',
                            '--disable-gpu',
                            '--no-zygote',
                            '--single-process'
                        ]
                    )
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    )
                    page = await context.new_page()
                    
                    # -------------------------------------------------------------
                    # ⚠️ জিপি পোর্টাল বা গেটওয়ের মেইন রিকোয়েস্ট লজিকটি এখানে বসাবেন
                    # -------------------------------------------------------------
                    # উদাহরণ হিসেবে আপনার দেওয়া সাকসেস লিঙ্কটি জেনারেট করে রিটার্ন করা হচ্ছে:
                    mock_bkash_url = "https://payment.bkash.com/redirect?token=tXw50pPeGBbCKWsCZ_)Qupy7hu!gpjcDBWQd(BluouazhGlbjVsGE_2vI1bwTX3!n8bE!Vgqex)Vfw0t7TFFeRH*.qk1779733163570&mode=0011&apiVersion=v1.2.0-beta/"
                    
                    await browser.close()
                    return {"success": True, "data": {"redirectUrl": mock_bkash_url}}
                    
                except Exception as e:
                    return {"success": False, "error": str(e)}

        # রান বাটন
        if st.button("Execute GP Recharge Pipeline"):
            with st.spinner("Connecting Tunnel to Grameenphone Gateway & Generating bKash Session..."):
                # এসিনক্রোনাস ফাংশন রান করা
                api_response = asyncio.run(inject_gp_live_pipeline(pipeline_plan))
                
                if api_response and api_response.get("success"):
                    bkash_url = api_response["data"]["redirectUrl"]
                    
                    st.success("🎉 SUCCESS: GRAMEENPHONE SPLIT BUNDLE GENERATED!")
                    
                    # 🚨 কাস্টম বিকাশ পেমেন্ট বাটন (যা কোনো স্পেশাল ক্যারেক্টারে ভাঙবে না)
                    button_html = f"""
                        <div style="text-align: center; margin-top: 20px;">
                            <a href="{bkash_url}" target="_blank" style="text-decoration: none;">
                                <div style="
                                    background-color: #E2136E; 
                                    color: white; 
                                    padding: 14px 28px; 
                                    text-align: center; 
                                    border-radius: 8px; 
                                    font-size: 18px; 
                                    font-weight: bold;
                                    font-family: 'Arial', sans-serif;
                                    box-shadow: 0px 4px 15px rgba(226, 19, 110, 0.4);
                                    cursor: pointer;
                                    display: inline-block;
                                    transition: 0.3s;
                                ">
                                    👉 Click Here to Open bKash Secure Gateway
                                </div>
                            </a>
                        </div>
                    """
                    # Raw HTML রেন্ডার করার পারমিশন সহ মার্কডাউন পুশ
                    st.markdown(button_html, unsafe_allow_html=True)
                else:
                    st.error("GP Server rejected payload or connection dropped.")
                    st.json(api_response)
