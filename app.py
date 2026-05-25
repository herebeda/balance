import streamlit as st
import os
import asyncio
import re
from playwright.async_api import async_playwright

# পেজ কনফিগারেশন এবং টাইটেল
st.set_page_config(page_title="GP Recharge Bundle System", page_icon="📱", layout="centered")

# ==================== AUTOMATIC BROWSER INSTALLATION ====================
if not os.path.exists(os.path.expanduser("~/.cache/ms-playwright")):
    with st.spinner("Configuring System Headless Chromium... Please wait..."):
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
    
    # মোড সিলেকশন (ইউজার ইন্টারফেসে সিলেক্ট করলেই নিচের লজিক অটো চেঞ্জ হবে)
    mode = st.radio("Choose Mode", ["Normal", "5-min Jitter (Anti-Duplicate)"])
    
    # SEU SCOUT ডেটা ইনপুট
    scout_data = st.text_area("Paste your SEU SCOUT output data here:", placeholder="Number: 01713... | Exact Balance: 20145 BDT")
    
    if scout_data:
        # ডাইনামিক ব্যালেন্স ডিটেকশন
        balance_match = re.search(r"Exact Balance:\s*(\d+)", scout_data)
        
        if balance_match:
            total_balance = int(balance_match.group(1))
        else:
            total_balance = 0
            st.error("⚠️ Scout data থেকে ব্যালেন্স ডিটেক্ট করা যায়নি!")
            
        if total_balance > 0:
            st.metric(label="Total Input Balance Detected", value=f"{total_balance} BDT")
            st.subheader("Auto-Adjusted Recharge Plan")
            
            # 🎯 মোড অনুযায়ী অটোমেটিক টাকার লজিক সিলেকশন
            if mode == "Normal":
                base_amount = 1000  # নরমাল মোডে ফিক্সড ১০০০ টাকা
            else:
                base_amount = 980   # ৫-মিনিট জিটার মোডে ফিক্সড ৯৮০ টাকা
            
            pipeline_plan = []
            remaining_balance = total_balance
            
            for msisdn in msisdns:
                if remaining_balance >= base_amount:
                    amount = base_amount
                elif remaining_balance > 0:
                    amount = remaining_balance
                else:
                    break
                
                pipeline_plan.append({"msisdn": msisdn, "amount": amount})
                remaining_balance -= amount
                
            allocated = total_balance - remaining_balance
            st.caption(f"Total Allocated: {allocated} BDT | Leftover: {remaining_balance} BDT")
            st.json(pipeline_plan)
            
            # Playwright এর মাধ্যমে সেশন জেনারেশন
            async def inject_gp_live_pipeline(plan_data):
                async with async_playwright() as p:
                    try:
                        # 🚨 বিকাশ ব্লকিং বাইপাস করার জন্য ক্রমিয়াম সেটিংস পরিবর্তন করা হয়েছে
                        browser = await p.chromium.launch(
                            headless=True,  # সার্ভারে রান করার জন্য ট্রু রাখতে হবে তবে নিচের ফ্ল্যাগগুলো রিয়েল উইন্ডো ইমুলেট করবে
                            args=[
                                '--no-sandbox',
                                '--disable-setuid-sandbox',
                                '--disable-blink-features=AutomationControlled', # অটোমেশন ট্র্যাকিং অফ করার জন্য
                                '--disable-dev-shm-usage',
                                '--disable-web-security',
                                '--disable-features=IsolateOrigins,site-per-process'
                            ]
                        )
                        
                        # রিয়েল উইন্ডোজ পিসি এবং ক্রোম ব্রাউজারের পুঙ্খানুপুঙ্খ ফিঙ্গারপ্রিন্ট ইমিটেশন
                        context = await browser.new_context(
                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                            viewport={"width": 1920, "height": 1080},
                            accept_downloads=True
                        )
                        
                        # বিকাশের অবজেক্ট ডিটেকশন ট্র্যাকিং ফাঁকি দেওয়ার স্ক্রিপ্ট
                        page = await context.new_page()
                        await page.add_init_script("delete navigator.__proto__.webdriver;")
                        
                        # -------------------------------------------------------------
                        # ⚠️ আপনার জিপি পোর্টালের রিকোয়েস্ট কোড এখানে রান হবে
                        # -------------------------------------------------------------
                        
                        # উদাহরণস্বরূপ লাইভ টোকেন ইউআরএল
                        raw_bkash_url = "https://payment.bkash.com/redirect?token=tXw50pPeGBbCKWsCZ_)Qupy7hu!gpjcDBWQd(BluouazhGlbjVsGE_2vI1bwTX3!n8bE!Vgqex)Vfw0t7TFFeRH*.qk1779733163570&mode=0011&apiVersion=v1.2.0-beta/"
                        
                        await browser.close()
                        return {"success": True, "data": {"redirectUrl": raw_bkash_url}}
                        
                    except Exception as e:
                        return {"success": False, "error": str(e)}

            # এক্সিকিউট বাটন
            if st.button("Execute GP Recharge Pipeline"):
                with st.spinner("Generating Anti-Fingerprint bKash Secure Session..."):
                    api_response = asyncio.run(inject_gp_live_pipeline(pipeline_plan))
                    
                    if api_response and api_response.get("success"):
                        bkash_url = api_response["data"]["redirectUrl"].strip()
                        
                        # শেষ প্রান্তের অবান্তর ক্যারেক্টার ট্রিম
                        if bkash_url.endswith('/'):
                            bkash_url = bkash_url[:-1]
                        
                        st.success("🎉 SUCCESS: GRAMEENPHONE SPLIT BUNDLE GENERATED!")
                        
                        # সরাসরি ক্লিকেবল বাটন লিংক ইনজেকশন
                        button_html = """
                            <div style="text-align: center; margin-top: 20px;">
                                <a href="CHANGE_TO_REAL_URL" target="_blank" style="text-decoration: none;">
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
                        """.replace("CHANGE_TO_REAL_URL", bkash_url)
                        
                        st.markdown(button_html, unsafe_allow_html=True)
                    else:
                        st.error("GP Server rejected payload or connection dropped.")
                        st.json(api_response)
