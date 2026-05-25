import asyncio
import json
import re
import sys
import os
import streamlit as st
from playwright.async_api import async_playwright

# ==================== CONFIGURATION ====================
MAX_RECHARGE_LIMIT = 1000  
MIN_RECHARGE_LIMIT = 20    
CUSTOMER_EMAIL = "emailhere@gmail.com"  
# =======================================================

st.set_page_config(page_title="GP Recharge Bundle System", layout="centered")
st.title("📱 GP Recharge Bundle System")

# ১. নম্বর ফাইল আপলোড অপশন (আপনার চাহিদা অনুযায়ী)
uploaded_file = st.file_uploader("Upload 'gp.txt' file containing numbers", type=["txt"])

def parse_uploaded_numbers(file_content):
    """আপলোড করা ফাইল থেকে নম্বর ফিল্টার করার ফাংশন"""
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
    # সার্ভারে চালানোর জন্য headless=True করা হয়েছে
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = await browser.new_context()
        page1 = await context.new_page()
        
        session_id_container = [None]
        async def handle_response(response):
            if "payments.grameenphone.com/ui/recharge/" in response.url:
                match = re.search(r'/ui/recharge/([a-f0-9]{32})', response.url)
                if match:
                    session_id_container[0] = match.group(1)

        page1.on("response", handle_response)
        try:
            await page1.goto("https://www.grameenphone.com/recharge", wait_until="commit", timeout=40000)
            await asyncio.sleep(4)
        except Exception as e:
            return {"success": False, "error": f"GP Portal load fail: {str(e)}"}
        
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
        api_response = await page1.evaluate(js_submit_routing, {"payloadStr": json.dumps(payload_data)})
        await browser.close()
        return api_response

# --- UI Layout ---
if uploaded_file is not None:
    file_content = uploaded_file.read().decode("utf-8")
    target_numbers = parse_uploaded_numbers(file_content)
    st.success(f"Successfully loaded {len(target_numbers)} numbers from file.")
    
    # মোড সিলেকশন
    mode = st.radio("Choose Mode", ('Normal', '5-min Jitter (Anti-Duplicate)'))
    anti_duplicate = True if mode == '5-min Jitter (Anti-Duplicate)' else False

    # SEU ডাটা ইনপুট এরিয়া
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
                    
                    with st.spinner("Connecting Tunnel to Grameenphone Engine... Please wait..."):
                        # Async function রান করানো হচ্ছে
                        api_response = asyncio.run(inject_gp_live_pipeline(pipeline_plan))
                        
                    if api_response and api_response.get("success") and "data" in api_response and "redirectUrl" in api_response["data"]:
                        redirect_url = api_response["data"]["redirectUrl"]
                        st.balloons()
                        st.success("🎉 SUCCESS: GRAMEENPHONE SPLIT BUNDLE GENERATED!")
                        # bKash গেটওয়ের লিংক বাটনে ক্লিক করে ইউজার পেমেন্ট করবে
                        st.video("https://assets.mixkit.co/videos/preview/mixkit-animation-of-a-smartphone-with-a-checkmark-43224-large.mp4") # Just generic visual success
                        st.markdown(f'[👉 Click Here to Open bKash Secure Gateway]({redirect_url})')
                    else:
                        st.error(f"GP Server rejected payload or failed. Response: {api_response}")
else:
    st.warning("Please upload a 'gp.txt' file to proceed.")
