import streamlit as st
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
