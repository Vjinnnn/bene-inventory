import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import io
from datetime import datetime
from fuzzywuzzy import process

# --- ТОХИРГОО ---
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
    if v < 0: return 'background-color: #ffcccc; color: black'
    if v > 0: return 'background-color: #ccffcc; color: black'
    return ''

st.set_page_config(page_title="Bene Inventory", layout="wide")

# Вэб ба Мобайл харагдацыг цэгцлэх CSS
st.markdown("""
    <style>
    /* Багануудын хоорондын зайг багасгах */
    [data-testid="column"] {
        padding: 0px 2px !important;
    }
    /* Оролтын талбаруудын өндрийг багасгах */
    .stTextInput input {
        padding: 5px 5px !important;
        height: 35px !important;
        font-size: 14px !important;
    }
    /* Барааны нэрийг жижиг боловч тод болгох */
    .item-label {
        font-size: 14px;
        font-weight: 500;
        margin-bottom: -15px;
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

with tab1:
    c1, c2 = st.columns([1, 1])
    with c1:
        date_str = st.date_input("Огноо:", datetime.now()).strftime("%Y-%m-%d")
    with c2:
        excel_file = st.file_uploader("📂 Excel", type=['xlsx'])

    saved_current = load_json(CURRENT_FILE)
    current_data = {}

    st.markdown("---")
    # Толгой хэсэг (Зөвхөн том дэлгэцэнд харагдана)
    h = st.columns([2, 0.6, 0.6, 0.6, 1.5])
    h[0].caption("Барааны нэр")
    h[1].caption("Өглөө")
    h[2].caption("Хүрг")
    h[3].caption("Орой")
    h[4].caption("Тайлбар")

    for item in PAPER_ITEMS:
        prev = saved_current.get(item, {"u": "", "h": "", "o": "", "comm": ""})
        
        # Нэг мөрөнд багтаах баганууд
        cols = st.columns([2, 0.6, 0.6, 0.6, 1.5])
        
        cols[0].markdown(f"<p class='item-label'>{item}</p>", unsafe_allow_html=True)
        
        u = cols[1].text_input("Ө", value=prev['u'], key=f"u_{item}_{date_str}", label_visibility="collapsed")
        h = cols[2].text_input("Х", value=prev['h'], key=f"h_{item}_{date_str}", label_visibility="collapsed")
        o = cols[3].text_input("О", value=prev['o'], key=f"o_{item}_{date_str}", label_visibility="collapsed")
        comm = cols[4].text_input("Т", value=prev['comm'], key=f"c_{item}_{date_str}", label_visibility="collapsed", placeholder="...")
        
        current_data[item] = {"u": u, "h": h, "o": o, "comm": comm}

    st.markdown("---")
    # Товчлууруудыг зэрэгцүүлэх
    b1, b2 = st.columns(2)
    with b1:
        if st.button("💾 Хадгалах", use_container_width=True):
            save_json(current_data, CURRENT_FILE)
            st.toast("Явц хадгалагдлаа")
    with b2:
        if st.button("📊 Тулгах", type="primary", use_container_width=True):
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
            else: st.warning("Excel оруулна уу")

    if 'temp_report' in st.session_state:
        res_df = pd.DataFrame(st.session_state['temp_report'])
        st.dataframe(res_df.style.applymap(style_diff, subset=['Зөрүү']).format(precision=0), use_container_width=True)
        if st.button("🏁 АРХИВЛАХ", type="primary", use_container_width=True):
            history = load_json(HISTORY_FILE)
            history[date_str] = st.session_state['temp_report']
            save_json(history, HISTORY_FILE)
            if os.path.exists(CURRENT_FILE): os.remove(CURRENT_FILE)
            del st.session_state['temp_report']
            st.rerun()

with tab2:
    st.header("📊 Архив")
    history = load_json(HISTORY_FILE)
    if history:
        # Устгах хэсэг
        with st.expander("🗑️ Устгах"):
            del_date = st.selectbox("Огноо:", sorted(history.keys(), reverse=True))
            if st.button("❌ Устгах"):
                del history[del_date]
                save_json(history, HISTORY_FILE)
                st.rerun()

        all_recs = []
        for d, items in history.items():
            for i in items:
                i['Огноо'] = d
                all_recs.append(i)
        df_all = pd.DataFrame(all_recs)
        df_all['Огноо'] = pd.to_datetime(df_all['Огноо'])
        df_all['Сар'] = df_all['Огноо'].dt.strftime('%Y-%m')
        
        sel_month = st.selectbox("Сар:", sorted(df_all['Сар'].unique(), reverse=True))
        month_df = df_all[df_all['Сар'] == sel_month].copy()
        st.dataframe(month_df.sort_values(by='Огноо', ascending=False).style.applymap(style_diff, subset=['Зөрүү']).format(precision=0), use_container_width=True)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            month_df.to_excel(writer, index=False)
        st.download_button("📥 Excel", buffer.getvalue(), f"Bene_{sel_month}.xlsx", use_container_width=True)
