import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import io
from datetime import datetime
from fuzzywuzzy import process

# --- ФАЙЛ ХАДГАЛАХ ТОХИРГОО ---
HISTORY_FILE = "inventory_history.json"
CURRENT_FILE = "inventory_current.json"
DELETED_FILE = "inventory_deleted.json" # Устгасан файлуудыг хадгалах "Хогийн сав"

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
    if v < 0: return 'background-color: #ffcccc; color: black'
    if v > 0: return 'background-color: #ccffcc; color: black'
    return ''

st.set_page_config(page_title="Caffe Bene Inventory Pro", layout="wide")

PAPER_ITEMS = [
    "Chocolate cookie", "Muffin", "Beef panini", "Chicken panini", 
    "Bacon panini", "Ham panini", "S.pellegrino/Purple Water",
    "Aqua panna/ Blue Water", "Buramkhan lolipop", "Cream cheese",
    "Whipping cream", "Brownie /cheese souffle/", "Waffle Walnut",
    "Waffle Plain", "MD coffee bean", "Fonte Drip Bag Coffee",
    "Coffee bean", "Lactose free milk", "Milk", "Croissant",
    "Cheese cake", "Carrot cake", "Pudding", "Bee Bakery"
]

tab1, tab2 = st.tabs(["📅 Өдрийн тооллого", "📊 Сарын тайлан & Архив"])

# --- TAB 1: ӨДРИЙН ТООЛЛОГО ---
with tab1:
    st.header("📱 Өдрийн тооллого")
    col_date, col_file = st.columns([1, 2])
    with col_date:
        date_obj = st.date_input("Огноо сонгох:", datetime.now())
        date_str = date_obj.strftime("%Y-%m-%d")
    with col_file:
        excel_file = st.file_uploader("📂 Системийн Excel-ээ оруулна уу", type=['xlsx'])

    saved_current = load_json(CURRENT_FILE)
    st.write("---")
    current_data = {}
    h_col = st.columns([2, 0.7, 0.7, 0.7, 2.5])
    h_col[0].write("**Барааны нэр**"); h_col[1].write("**Өглөө**"); h_col[2].write("**Хүргэлт**"); h_col[3].write("**Орой**"); h_col[4].write("**Тайлбар**")
    
    for item in PAPER_ITEMS:
        prev = saved_current.get(item, {"u": "", "h": "", "o": "", "comm": ""})
        r_col = st.columns([2, 0.7, 0.7, 0.7, 2.5])
        r_col[0].info(item)
        u = r_col[1].text_input("Ө", value=prev['u'], key=f"u_{item}_{date_str}", label_visibility="collapsed")
        h = r_col[2].text_input("Х", value=prev['h'], key=f"h_{item}_{date_str}", label_visibility="collapsed")
        o = r_col[3].text_input("О", value=prev['o'], key=f"o_{item}_{date_str}", label_visibility="collapsed")
        comm = r_col[4].text_input("Тай", value=prev['comm'], key=f"c_{item}_{date_str}", label_visibility="collapsed")
        current_data[item] = {"u": u, "h": h, "o": o, "comm": comm}

    st.write("---")
    b_col1, b_col2, b_col3 = st.columns(3)
    with b_col1:
        if st.button("💾 Явцыг түр хадгалах", use_container_width=True):
            save_json(current_data, CURRENT_FILE)
            st.success("Хадгалагдлаа!")
    with b_col2:
        if st.button("📊 Тулгалт хийж шалгах", type="secondary", use_container_width=True):
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
                            report_list.append({"Бараа": name, "Бодит": int(act_sold), "Систем": int(sys_v or 0), "Зөрүү": int(act_sold - (sys_v or 0)), "Тайлбар": v['comm'], "Огноо": date_str})
                    st.session_state['temp_report'] = report_list
                except Exception as e: st.error(f"Алдаа: {e}")
            else: st.warning("⚠️ Excel-ээ оруулна уу!")

    if 'temp_report' in st.session_state:
        st.subheader(f"🔍 {date_str}-ны тулгалт")
        st.dataframe(pd.DataFrame(st.session_state['temp_report']).style.applymap(style_diff, subset=['Зөрүү']).format(precision=0), use_container_width=True)
        if st.button("🏁 АРХИВТ ХАДГАЛАХ", type="primary", use_container_width=True):
            history = load_json(HISTORY_FILE)
            history[date_str] = st.session_state['temp_report']
            save_json(history, HISTORY_FILE)
            if os.path.exists(CURRENT_FILE): os.remove(CURRENT_FILE)
            del st.session_state['temp_report']
            st.balloons()

# --- TAB 2: АРХИВ & УСТГАХ & СЭРГЭЭХ ---
with tab2:
    st.header("📊 Сарын архив")
    history = load_json(HISTORY_FILE)
    deleted_data = load_json(DELETED_FILE)

    if history:
        # Устгах хэсэг
        with st.expander("🗑️ Өгөгдөл устгах"):
            del_date = st.selectbox("Устгах огноог сонгох:", sorted(history.keys(), reverse=True))
            if st.button(f"❌ {del_date}-ны өгөгдлийг устгах", type="secondary"):
                deleted_data[del_date] = history.pop(del_date) # Түүхээс аваад "Хогийн сав" руу
                save_json(history, HISTORY_FILE)
                save_json(deleted_data, DELETED_FILE)
                st.toast(f"{del_date} устгагдлаа")
                st.rerun()

        # Сэргээх хэсэг
        if deleted_data:
            with st.expander("♻️ Устгасан өгөгдөл сэргээх (Хогийн сав)"):
                restore_date = st.selectbox("Сэргээх огноо:", sorted(deleted_data.keys(), reverse=True))
                if st.button(f"✅ {restore_date}-г буцааж сэргээх"):
                    history[restore_date] = deleted_data.pop(restore_date)
                    save_json(history, HISTORY_FILE)
                    save_json(deleted_data, DELETED_FILE)
                    st.success("Амжилттай сэргээлээ!")
                    st.rerun()

        # Тайлан харуулах
        all_recs = []
        for d, items in history.items():
            for i in items:
                i['Огноо'] = d
                all_recs.append(i)
        full_df = pd.DataFrame(all_recs)
        full_df['Огноо'] = pd.to_datetime(full_df['Огноо'])
        full_df['Сар'] = full_df['Огноо'].dt.strftime('%Y-%m')
        sel_month = st.selectbox("Сар сонгох:", sorted(full_df['Сар'].unique(), reverse=True))
        month_df = full_df[full_df['Сар'] == sel_month].copy()
        st.dataframe(month_df.sort_values(by='Огноо', ascending=False).style.applymap(style_diff, subset=['Зөрүү']).format(precision=0), use_container_width=True)
        
        # Excel татах
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            month_df.to_excel(writer, index=False)
        st.download_button("📥 Excel татах", buffer.getvalue(), f"Bene_{sel_month}.xlsx")
    else:
        st.info("Архив хоосон байна.")
