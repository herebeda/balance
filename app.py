import streamlit as st
import os
import asyncio
import re
from playwright.async_api import async_playwright

# পেজ কনফিগারেশন এবং টাইটেল (macOS/Modern Dark Aesthetic Style)
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
    
    # মোড সিলেকশন
    mode = st.radio("Choose Mode", ["Normal", "5-min Jitter (Anti-Duplicate)"])
    
    # SEU SCOUT ডেটা ইনপুট
    scout_data = st.text_area("Paste your SEU SCOUT output data here:", placeholder="Number: 01713532100 | Exact Balance: 20145 BDT | ...")
    
    if scout_data:
        # 🎯 ডাইনামিক ব্যালেন্স ডিটেকশন (Regex দিয়ে Exact Balance এর পাশের সংখ্যাটি নেওয়া হচ্ছে)
        balance_match = re.search(r"Exact Balance:\s*(\d+)", scout_data)
        
        if balance_match:
            total_balance = int(balance_match.group(1))
        else:
            total_balance = 0
            st.error("⚠️ Scout data থেকে ব্যালেন্স ডিটেক্ট করা যায়নি! দয়া করে সঠিক ফরম্যাট দিন।")
            
        if total_balance > 0:
            st.metric(label="Total Input Balance Detected", value=f"{total_balance} BDT")
            st.subheader("Auto-Adjusted Recharge Plan")
            
            # 🧮 অটোমেটিক স্প্লিট লজিক (আপনার রিকোয়ারমেন্ট অনুযায়ী ৯৮০ টাকার বান্ডেল বিভাজন)
            pipeline_plan = []
            remaining_balance = total_balance
            
            for msisdn in msisdns:
                if remaining_balance >= 980:
                    amount = 980
                elif remaining_balance > 0:
                    amount = remaining_balance
                else:
                    break
                
                pipeline_plan.append({"msisdn": msisdn, "amount": amount})
                remaining_balance -= amount
                
            allocated = total_balance - remaining_balance
            st.caption(f"Total Allocated: {allocated} BDT | Leftover: {remaining_balance} BDT")
            st.json(pipeline_plan)
            
            # Playwright এর মাধ্যমে GP Server হিট করার এসিনক্রোনাস ফাংশন
            async def inject_gp_live_pipeline(plan_data):
                async with async_playwright() as p:
                    try:
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
                        # ⚠️ আপনার জিপি পোর্টালের ব্যাকএন্ড রিকোয়েস্ট কোড এখানে ট্রিগার হবে
                        # -------------------------------------------------------------
                        
                        # ডেমো সাকসেস রেসপন্স ইউআরএল (আপনার জেনারেট হওয়া লাইভ লিঙ্কটি এখানে রিপ্লেস হবে)
                        mock_bkash_url = "https://payment.bkash.com/redirect?token=tXw50pPeGBbCKWsCZ_)Qupy7hu!gpjcDBWQd(BluouazhGlbjVsGE_2vI1bwTX3!n8bE!Vgqex)Vfw0t7TFFeRH*.qk1779733163570&mode=0011&apiVersion=v1.2.0-beta/"
                        
                        await browser.close()
                        return {"success": True, "data": {"redirectUrl": mock_bkash_url}}
                        
                    except Exception as e:
                        return {"success": False, "error": str(e)}

            # এক্সিকিউট বাটন
            if st.button("Execute GP Recharge Pipeline"):
                with st.spinner("Connecting Tunnel to Grameenphone Gateway & Generating bKash Session..."):
                    api_response = asyncio.run(inject_gp_live_pipeline(pipeline_plan))
                    
                    if api_response and api_response.get("success"):
                        bkash_url = api_response["data"]["redirectUrl"]
                        
                        st.success("🎉 SUCCESS: GRAMEENPHONE SPLIT BUNDLE GENERATED!")
                        
                        # 🚨 বিকাশ লিঙ্ক অক্ষুণ্ণ রাখার জন্য নিরাপদ HTML মডিউল (No Character Encoding Break)
                        button_html = """
                            <div style="text-align: center; margin-top: 20px;">
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
                                        transition: 0.3s;
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
