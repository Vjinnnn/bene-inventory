import streamlit as st
import pandas as pd
import json
import os
import io
from datetime import datetime

# --- ТОХИРГОО Ба ФАЙЛУУД ---
HISTORY_FILE = "inventory_history.json"
CURRENT_FILE = "inventory_current.json"

# Танай бодит Excel-ээс авсан барааны жагсаалт (Код: Нэр)
# '0' кодтой байсан бараануудын жинхэнэ ПОС кодыг нь олж солиорой!
BARAANI_JAGSAALT = {
    "10": "Gift card 10k",
    "20": "Gift card 20k",
    "30": "Gift card 30k",
    "127": "Lactose free milk",
    "391": "Цэнхэр ус",
    "2": "Ягаан ус",
    "731": "Creamcheese",
    "929": "PORORO/ EDDY/RUBY CANDY",
    "1195": "Fonte dripbag",
    "1198": "MD coffee bean 250gr",
    "0001": "Milk (Кодыг засах)",
    "0002": "Аяга (Кодыг засах)",
    "0003": "Лаа 8000 (Кодыг засах)",
    "0004": "Coffee bean 1kg (Кодыг засах)"
}

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def calculate_input(text):
    try:
        if not text: return 0
        return sum(map(int, str(text).replace('+', ' ').split()))
    except:
        return 0

def style_diff(val):
    if val < 0: return 'background-color: #ffcccc; color: black'
    if val > 0: return 'background-color: #ccffcc; color: black'
    return ''

st.set_page_config(page_title="Bene Inventory Pro", layout="wide")
st.markdown("""<style>.stButton>button { width: 100%; height: 3em; border-radius: 10px; font-weight: bold; margin-top: 10px; } .item-label { font-size: 14px; font-weight: bold; margin-bottom: -15px; }</style>""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📝 ӨДРИЙН ТООЛЛОГО", "📊 САРЫН АРХИВ / ТАЙЛАН"])

# =====================================================================
# TAB 1: ТООЛЛОГО ХЭСЭГ
# =====================================================================
with tab1:
    st.subheader("📝 Өдрийн тооллого ба Тулгалт")
    
    history = load_json(HISTORY_FILE)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        date_str = st.date_input("Тооллого хийх огноо:", datetime.now()).strftime("%Y-%m-%d")
    with col2:
        excel_file = st.file_uploader("📂 Посын Excel (5.22i.xlsx мэт)", type=['xlsx'])
    with col3:
        staff_name = st.text_input("👨‍🍳 ПОС дээр суусан ажилтан:", placeholder="Жишээ нь: Болд")

    st.write("---")
    
    # Өмнөх өдрийн оройны үлдэгдлийг олох
    past_dates = [d for d in history.keys() if d < date_str]
    latest_date = max(past_dates) if past_dates else None
    
    if latest_date:
        st.info(f"💡 Өглөөний үлдэгдлийг өмнөх өдрийн ({latest_date}) оройн тооцооноос автоматаар татаж түгжлээ.")
    else:
        st.warning("⚠️ Өмнөх өдрийн архив олдсонгүй. Өглөөний үлдэгдлийг гараар оруулах боломжтой.")

    current_data = {}
    saved_current = load_json(CURRENT_FILE)
    
    h = st.columns([2, 0.7, 0.7, 0.7, 1.5])
    h[0].caption("Барааны код ба нэр")
    h[1].caption("Өглөө")
    h[2].caption("Хүргэлт")
    h[3].caption("Орой")
    h[4].caption("Тайлбар")

    for code, name in BARAANI_JAGSAALT.items():
        u_val = ""
        is_disabled = False
        
        # 3-р дүрэм: Өчигдрийн орой = Өнөөдрийн өглөө (Түгжих)
        if latest_date:
            prev_item = next((item for item in history[latest_date] if item["Код"] == code), None)
            if prev_item:
                u_val = str(prev_item["Орой"])
                is_disabled = True
        
        if not is_disabled:
            u_val = saved_current.get(code, {}).get("u", "")
            
        prev_h = saved_current.get(code, {}).get("h", "")
        prev_o = saved_current.get(code, {}).get("o", "")
        prev_c = saved_current.get(code, {}).get("comm", "")

        cols = st.columns([2, 0.7, 0.7, 0.7, 1.5])
        cols[0].markdown(f"<p class='item-label'><b>[{code}]</b> {name}</p>", unsafe_allow_html=True)
        
        u = cols[1].text_input("Ө", value=u_val, key=f"u_{code}", disabled=is_disabled, label_visibility="collapsed")
        h = cols[2].text_input("Х", value=prev_h, key=f"h_{code}", label_visibility="collapsed")
        o = cols[3].text_input("О", value=prev_o, key=f"o_{code}", label_visibility="collapsed")
        comm = cols[4].text_input("Т", value=prev_c, key=f"c_{code}", label_visibility="collapsed", placeholder="...")
        
        current_data[code] = {"u": u, "h": h, "o": o, "comm": comm}

    st.markdown("---")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("💾 Явцыг түр хадгалах"):
            save_json(current_data, CURRENT_FILE)
            st.toast("Явц хадгалагдлаа")
            
    with b2:
        if st.button("📊 Системтэй тулгаж шалгах", type="primary"):
            if not staff_name:
                st.error("Ажилтны нэрийг заавал оруулна уу!")
            elif excel_file:
                try:
                    # Excel-ийг бүтнээр нь уншаад 'Item #' гэсэн толгойг автоматаар хайж олох
                    df_raw = pd.read_excel(excel_file, header=None)
                    header_idx = 0
                    for i, row in df_raw.iterrows():
                        if 'Item #' in str(row.values):
                            header_idx = i
                            break
                    
                    # Зөв толгойноос эхэлж дахин унших
                    df = pd.read_excel(excel_file, skiprows=header_idx)
                    df.columns = df.columns.str.strip()
                    
                    # 'Item #' баганыг текст болгож, Qty Sold баганаас хоосон биш утгуудыг авна
                    df['Item #'] = df['Item #'].astype(str).str.replace(r'\.0$', '', regex=True)
                    df['Qty Sold'] = pd.to_numeric(df['Qty Sold'], errors='coerce').fillna(0)
                    
                    # Барааны кодоор нь зарсан тоог нэгтгэх
                    sys_sales = df.groupby('Item #')['Qty Sold'].sum().to_dict()
                    
                    report_list = []
                    for code, v in current_data.items():
                        u_v = calculate_input(v['u'])
                        h_v = calculate_input(v['h'])
                        o_v = calculate_input(v['o'])
                        
                        # Кодоор хайж зарсан тоог олох (Байхгүй бол 0)
                        sys_v = sys_sales.get(str(code), 0)
                        
                        act_sold = (u_v + h_v) - o_v
                        diff = act_sold - sys_v
                        
                        report_list.append({
                            "Код": code,
                            "Барааны нэр": name,
                            "Өглөө": u_v,
                            "Хүргэлт": h_v,
                            "Орой": o_v,
                            "Бодит борлуулалт": int(act_sold),
                            "Систем борлуулалт": int(sys_v),
                            "Зөрүү (Илүү/Дутуу)": int(diff),
                            "ПОС Ажилтан": staff_name,
                            "Тайлбар": v['comm']
                        })
                    st.session_state['temp_report'] = report_list
                    st.success("Амжилттай! Доошоо гүйлгэж харна уу.")
                except Exception as e:
                    st.error(f"Excel уншихад алдаа гарлаа. Файлын загвар зөв эсэхийг шалгана уу. Алдаа: {e}")
            else:
                st.warning("⚠️ Посын Excel файлаа оруулна уу!")

    if 'temp_report' in st.session_state:
        st.divider()
        st.subheader(f"🔍 Тулгалтын дүн ({date_str})")
        res_df = pd.DataFrame(st.session_state['temp_report'])
        st.dataframe(res_df.style.applymap(style_diff, subset=['Зөрүү (Илүү/Дутуу)']).format(precision=0), use_container_width=True)
        
        if st.button("🏁 ЭНЭ ӨДРИЙГ АРХИВТ ХАДГАЛАХ", type="primary"):
            history[date_str] = st.session_state['temp_report']
            save_json(history, HISTORY_FILE)
            if os.path.exists(CURRENT_FILE): os.remove(CURRENT_FILE)
            del st.session_state['temp_report']
            st.balloons()
            st.rerun()

# =====================================================================
# TAB 2: АРХИВ БА САРЫН ТАЙЛАН
# =====================================================================
with tab2:
    st.subheader("📊 Сарын тайлан ба Суутгал тооцоолол")
    history = load_json(HISTORY_FILE)
    
    if history:
        c1, c2 = st.columns(2)
        with c1: start_date = st.date_input("Эхлэх огноо:", datetime.now())
        with c2: end_date = st.date_input("Дуусах огноо:", datetime.now())
            
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        
        all_recs = []
        for d, items in history.items():
            if start_str <= d <= end_str:
                for i in items:
                    i['Огноо'] = d
                    all_recs.append(i)
                    
        if all_recs:
            df_all = pd.DataFrame(all_recs)
            df_all = df_all[["Огноо", "ПОС Ажилтан", "Код", "Барааны нэр", "Өглөө", "Хүргэлт", "Орой", "Бодит борлуулалт", "Систем борлуулалт", "Зөрүү (Илүү/Дутуу)", "Тайлбар"]]
            
            st.write(f"### 📅 {start_str} -аас {end_str} хүртэлх тайлан")
            st.dataframe(df_all.style.applymap(style_diff, subset=['Зөрүү (Илүү/Дутуу)']).format(precision=0), use_container_width=True)
            
            # --- СУУТГАЛЫН НЭГТГЭЛ ---
            st.divider()
            st.subheader("💰 Ажилчдын суутгалын нэгтгэл (Зөвхөн дутсан)")
            
            dut_df = df_all[df_all["Зөрүү (Илүү/Дутуу)"] < 0].copy()
            if not dut_df.empty:
                summary_df = dut_df.groupby(["ПОС Ажилтан", "Барааны нэр"])["Зөрүү (Илүү/Дутуу)"].sum().reset_index()
                summary_df["Зөрүү (Илүү/Дутуу)"] = summary_df["Зөрүү (Илүү/Дутуу)"].abs()
                summary_df.columns = ["ПОС Ажилтан", "Дутсан бараа", "Нийт дутсан ширхэг"]
                st.table(summary_df)
            else:
                st.info("🥳 Энэ хугацаанд ямар ч бараа дутаагүй байна!")
            
            # EXCEL ТАТАХ
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_all.to_excel(writer, sheet_name="Өдрийн дэлгэрэнгүй", index=False)
                if not dut_df.empty:
                    summary_df.to_excel(writer, sheet_name="Суутгалын хуудас", index=False)
                    
            st.download_button("📥 EXCEL ТАЙЛАН ТАТАХ", buffer.getvalue(), f"Tailan_{start_str}_{end_str}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        else:
            st.warning("📅 Сонгосон хугацаанд архив олдсонгүй.")
