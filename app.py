import streamlit as st
import pandas as pd
import json
import os
import io
from datetime import datetime

# --- ТОХИРГОО Ба ФАЙЛУУД ---
HISTORY_FILE = "inventory_history.json"

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def clean_numeric(val):
    try:
        if pd.isna(val) or val == "":
            return 0
        return int(float(str(val).replace(',', '').replace(' ', '')))
    except:
        return 0

def style_diff(val):
    if val < 0: return 'background-color: #ffcccc; color: black'
    if val > 0: return 'background-color: #ccffcc; color: black'
    return ''

st.set_page_config(page_title="Bene Inventory Pro", layout="wide")
st.markdown("""<style>.stButton>button { width: 100%; height: 3em; border-radius: 10px; font-weight: bold; margin-top: 10px; }</style>""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📝 2 ФАЙЛ ТУЛГАХ", "📊 САРЫН АРХИВ / ТАЙЛАН"])

# =====================================================================
# TAB 1: ТООЛЛОГО ХЭСЭГ (ФАЙЛ ОРУУЛАХ)
# =====================================================================
with tab1:
    st.subheader("📝 Өдрийн тооллого - Автомат тулгалт")
    
    history = load_json(HISTORY_FILE)
    
    c1, c2, c3 = st.columns([1, 1.2, 1.2])
    with c1:
        date_str = st.date_input("Тооллого хийх огноо:", datetime.now()).strftime("%Y-%m-%d")
        staff_name = st.text_input("👨‍🍳 ПОС ажилтан:", placeholder="Жишээ нь: Болд")
    with c2:
        pos_excel = st.file_uploader("📂 1. ПОС-ын Excel (5.22i.xlsx мэт)", type=['xlsx', 'csv'])
    with c3:
        toollogo_excel = st.file_uploader("📋 2. Тооллогын Excel (2026.5.22.xlsx мэт)", type=['xlsx', 'csv'])

    st.write("---")
    
    past_dates = [d for d in history.keys() if d < date_str]
    latest_date = max(past_dates) if past_dates else None
    prev_evening_dict = {}
    
    if latest_date:
        st.info(f"💡 Өмнөх өдрийн ({latest_date}) архиваас оройн үлдэгдлийг автоматаар татаж, өнөөдрийн 'Өглөө'-ний тоог баталгаажуулна.")
        for item in history[latest_date]:
            prev_evening_dict[str(item["Код"])] = item["Орой"]
    else:
        st.warning("⚠️ Өмнөх өдрийн архив олдсонгүй. Тооллогын файл дээрх 'Өглөө'-ний дүнгээр бодогдоно.")

    if st.button("📊 ХОЁР ФАЙЛЫГ ТУЛГАЖ ШАЛГАХ", type="primary"):
        if not staff_name:
            st.error("Ажилтны нэрийг заавал оруулна уу!")
        elif not pos_excel or not toollogo_excel:
            st.error("⚠️ ПОС-ын болон Тооллогын 2 файлыг ХОЁУЛАГ НЬ оруулна уу!")
        else:
            try:
                # Файлыг санах ойд тогтвортойгоор уншиж авах (Хамгийн чухал засвар энд байна)
                pos_bytes = pos_excel.getvalue()
                tool_bytes = toollogo_excel.getvalue()

                # ---------------------------------------------------------
                # 1. ПОС-ЫН ФАЙЛЫГ УНШИХ
                # ---------------------------------------------------------
                if pos_excel.name.endswith('.csv'):
                    df_pos_raw = pd.read_csv(io.BytesIO(pos_bytes), header=None)
                else:
                    df_pos_raw = pd.read_excel(io.BytesIO(pos_bytes), header=None)
                
                h_idx_pos = 0
                for i, row in df_pos_raw.iterrows():
                    row_text = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
                    if 'item #' in row_text and 'qty sold' in row_text:
                        h_idx_pos = i
                        break
                
                if pos_excel.name.endswith('.csv'):
                    df_pos = pd.read_csv(io.BytesIO(pos_bytes), skiprows=h_idx_pos)
                else:
                    df_pos = pd.read_excel(io.BytesIO(pos_bytes), skiprows=h_idx_pos)
                
                df_pos.columns = df_pos.columns.str.strip()
                df_pos['Item #'] = df_pos['Item #'].astype(str).str.replace(r'\.0$', '', regex=True)
                df_pos['Qty Sold'] = pd.to_numeric(df_pos['Qty Sold'], errors='coerce').fillna(0)
                sys_sales = df_pos.groupby('Item #')['Qty Sold'].sum().to_dict()

                # ---------------------------------------------------------
                # 2. ТООЛЛОГЫН ФАЙЛЫГ УНШИХ
                # ---------------------------------------------------------
                df_tool = None
                
                if toollogo_excel.name.endswith('.csv'):
                    df_tool_raw = pd.read_csv(io.BytesIO(tool_bytes), header=None)
                    for i, row in df_tool_raw.iterrows():
                        row_text = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
                        if 'өглөө' in row_text and 'орой' in row_text:
                            df_tool = pd.read_csv(io.BytesIO(tool_bytes), skiprows=i)
                            break
                else:
                    xls = pd.ExcelFile(io.BytesIO(tool_bytes))
                    for sheet_name in xls.sheet_names:
                        temp_df = pd.
