import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import io
from datetime import datetime
from fuzzywuzzy import process

# --- ФАЙЛ ХАДГАЛАХ ---
HISTORY_FILE = "inventory_history.json"
CURRENT_FILE = "inventory_current.json"
DELETED_FILE = "inventory_deleted.json"

def save_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def calculate_input(text):
    try:
        clean_text = "".join(c for c in str(text) if c in "0123456789+-*/.")
        return int(eval(clean_text)) if clean_text else 0
    except:
        return 0

def style_diff(v):
    if v < 0: return 'background-color: #ffcccc; color: black' # Дутсан - Улаан
    if v > 0: return 'background-color: #ccffcc; color: black' # Илүүдсэн - Ногоон
    return ''

# --- CSS ТӨРХ (Гар утсанд зориулсан) ---
st.set_page_config(page_title="Bene Inventory", layout="wide")
st.markdown("""
    <style>
    /* Товчлууруудыг өндөр, том болгох */
    .stButton>button {
        width: 100%;
        height: 3em;
        border-radius: 10px;
        font-weight: bold;
        margin-top: 10px;
    }
    /* Input хэсгүүдийг утсан дээр тод харагдуулах */
    input {
        font-size: 18px !important;
    }
    /* Хүснэгтийн зайг нэмэх */
    [data-testid="stVerticalBlock"] > div:contains("Барааны нэр") {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

PAPER_ITEMS = [
    "Chocolate cookie", "Muffin", "Beef panini", "Chicken panini", 
    "Bacon panini", "Ham panini", "S.pellegrino/Purple Water",
    "Aqua panna/ Blue Water", "Buramkhan lolipop", "Cream cheese",
    "Whipping cream", "Brownie /cheese souffle/", "Waffle Walnut",
    "Waffle Plain", "MD coffee bean", "Fonte Drip Bag Coffee",
    "Coffee bean", "Lactose free milk", "Milk", "Croissant",
    "Cheese cake", "Carrot cake", "Pudding", "Bee Bakery"
]

tab1, tab2 = st.tabs(["📝 ТООЛЛОГО", "📊 АРХИВ"])

# --- TAB 1: ТООЛЛОГО ---
with tab1:
    st.subheader("📝 Өдрийн тооллого")
    
    # Огноо ба файл оруулах хэсгийг мобайлд зориулж багасгав
    c1, c2 = st.columns([1, 1])
    with c1:
        date_obj = st.date_input("Огноо:", datetime.now())
        date_str = date_obj.strftime("%Y-%m-%d")
    with c2:
        excel_file = st.file_uploader("📂 Excel", type=['xlsx'], help="Системийн борлуулалт")

    saved_current = load_json(CURRENT_FILE)
    
    st.write("---")
    current_data = {}
    
    # Утсан дээр багануудыг хэт олон болгохгүй тулд "Бараа" ба "Тоонууд" гэж хуваав
    for item in PAPER_ITEMS:
        prev = saved_current.get(item, {"u": "", "h": "", "o": "", "comm": ""})
        
        # Гар утсанд зориулсан блок дизайн
        with st.container():
            st.markdown(f"**🔹 {item}**")
            r1, r2, r3, r4 = st.columns([1, 1, 1, 2])
            u = r1.text_input("Ө", value=prev['u'], key=f"u_{item}_{date_str}", placeholder="Өглөө")
            h = r2.text_input("Х", value=prev['h'], key=f"h_{item}_{date_str}", placeholder="Хүрг")
            o = r3.text_input("О", value=prev['o'], key=f"o_{item}_{date_str}", placeholder="Орой")
            comm = r4.text_input("Тай", value=prev['comm'], key=f"c_{item}_{date_str}", placeholder="Тайлбар")
            current_data[item] = {"u": u, "h": h, "o": o, "comm": comm}
        st.write("") # Зай авах

    st.write("---")
    # Үндсэн товчлуурууд
    if st.button("💾 Явцыг түр хадгалах", type="secondary"):
        save_json(current_data, CURRENT_FILE)
        st.success("Хадгалагдлаа!")

    if st.button("📊 Тулгалт хийж шалгах", type="primary"):
        if excel_file:
            try:
                df = pd.read_excel(excel_file, skiprows=6)
                df.columns = df.columns.str.strip()
                report_list = []
                excel_names = df['Item Name'].dropna().astype(str).tolist()
                for name, v in current_data.items():
                    if v['u'] or v['h'] or v['o']:
                        u_v, h_v, o_v = calculate_input(v['u']), calculate_input(v['h']), calculate_input(v['o'])
                        match, score = process.extractOne(name, excel_names)
                        sys_v = df[df['Item Name'] == match]['Qty Sold'].values[0] if score > 70 else 0
                        act_sold = (u_v + h_v) - o_v
                        report_list.append({
                            "Бараа": name, "Бодит": int(act_sold), "Систем": int(sys_v or 0), 
                            "Зөрүү": int(act_sold - (sys_v or 0)), "Тайлбар": v['comm']
                        })
                st.session_state['temp_report'] = report_list
            except Exception as e: st.error(f"Алдаа: {e}")
        else: st.warning("⚠️ Excel-ээ оруулна уу!")

    if 'temp_report' in st.session_state:
        st.divider()
        st.subheader("🔍 Тулгалтын дүн")
        res_df = pd.DataFrame(st.session_state['temp_report'])
        st.dataframe(res_df.style.applymap(style_diff, subset=['Зөрүү']).format(precision=0), use_container_width=True)
        
        if st.button("🏁 АРХИВТ ХАДГАЛАХ", type="primary"):
            history = load_json(HISTORY_FILE)
            history[date_str] = st.session_state['temp_report']
            save_json(history, HISTORY_FILE)
            if os.path.exists(CURRENT_FILE): os.remove(CURRENT_FILE)
            del st.session_state['temp_report']
            st.balloons()
            st.rerun()

    if st.button("🗑️ Түр хадгалалт арилгах"):
        if os.path.exists(CURRENT_FILE): os.remove(CURRENT_FILE)
        st.rerun()

# --- TAB 2: АРХИВ ---
with tab2:
    st.header("📊 Сарын архив")
    history = load_json(HISTORY_FILE)
    deleted_data = load_json(DELETED_FILE)

    if history:
        # Устгах & Сэргээх хэсэг (Expander ашиглан зай хэмнэв)
        with st.expander("🛠️ Засварлах / Устгах"):
            del_date = st.selectbox("Огноо сонгох:", sorted(history.keys(), reverse=True))
            if st.button("❌ Устгах"):
                deleted_data[del_date] = history.pop(del_date)
                save_json(history, HISTORY_FILE)
                save_json(deleted_data, DELETED_FILE)
                st.rerun()
            
            if deleted_data:
                st.divider()
                res_date = st.selectbox("Сэргээх огноо:", sorted(deleted_data.keys(), reverse=True))
                if st.button("✅ Сэргээх"):
                    history[res_date] = deleted_data.pop(res_date)
                    save_json(history, HISTORY_FILE)
                    save_json(deleted_data, DELETED_FILE)
                    st.rerun()

        # Архив харуулах
        all_recs = []
        for d, items in history.items():
            for i in items:
                i['Огноо'] = d
                all_recs.append(i)
        
        df_all = pd.DataFrame(all_recs)
        df_all['Огноо'] = pd.to_datetime(df_all['Огноо'])
        df_all['Сар'] = df_all['Огноо'].dt.strftime('%Y-%m')
        
        sel_month = st.selectbox("Сар сонгох:", sorted(df_all['Сар'].unique(), reverse=True))
        month_df = df_all[df_all['Сар'] == sel_month].copy()
        
        st.dataframe(month_df.sort_values(by='Огноо', ascending=False).style.applymap(style_diff, subset=['Зөрүү']).format(precision=0), use_container_width=True)
        
        # Excel татах
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            month_df.to_excel(writer, index=False)
        st.download_button("📥 Excel татах", buffer.getvalue(), f"Bene_{sel_month}.xlsx", use_container_width=True)
    else:
        st.info("Архив хоосон байна.")
