import streamlit as st
import pandas as pd
import json
import os
import io
import re
from datetime import datetime

st.set_page_config(page_title="Bene Inventory Audit Pro Max", page_icon="☕", layout="wide")

HISTORY_FILE = "inventory_history.json"

# --- 🖤 PRO DARK CSS СТИЛЬ ---
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .report-title { font-size: 24px; font-weight: bold; color: #58a6ff; margin-top: 25px; margin-bottom: 15px; padding-bottom: 8px; border-bottom: 2px solid #21262d; }
    .stButton>button { width: 100%; height: 3.5em; border-radius: 12px; font-weight: bold; background-color: #238636 !important; color: white !important; border: none; }
    .stButton>button:hover { background-color: #2ea44f !important; }
    
    /* KPI Картуудын дизайн */
    .kpi-container { display: flex; gap: 15px; margin-bottom: 20px; }
    .kpi-card { flex: 1; padding: 20px; border-radius: 12px; background-color: #161b22; border: 1px solid #30363d; text-align: center; }
    .kpi-value { font-size: 28px; font-weight: bold; margin-top: 5px; }
</style>
""", unsafe_allow_html=True)

# ЖИШЭЭ БАРААНЫ ҮНЭ (Та энд өөрийн барааны өртөг эсвэл зарах үнийг тавьчихвал суутгалыг шууд Төгрөгөөр бодно)
PRICE_LIST = {
    "панини": 8500,
    "сэндвич": 7500,
    "бялуу": 6500,
    "cake": 6500,
    "default": 5000  # Жагсаалтад байхгүй бол дундаж үнэ 5000-аар бодно
}

def get_item_price(item_name):
    name_lower = str(item_name).lower()
    for key, price in PRICE_LIST.items():
        if key in name_lower: return price
    return PRICE_LIST["default"]

def load_json():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f: return json.load(f)
    return {}

def save_json(data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

def clean_numeric(val):
    try:
        if isinstance(val, pd.Series): val = val.iloc[0]
        if pd.isna(val) or val == "": return 0
        return int(float(str(val).replace(',', '').replace(' ', '')))
    except: return 0

def get_item_group(item_name):
    name_lower = str(item_name).lower()
    if "панини" in name_lower or "panini" in name_lower: return "🥪 ПАНИНИ БҮЛЭГ"
    elif any(x in name_lower for x in ["cake", "бялуу", "кекс", "roll", "торт"]): return "🍰 БЯЛУУ БҮЛЭГ"
    elif "сэндвич" in name_lower or "sandwich" in name_lower: return "🥪 СЭНДВИЧ БҮЛЭГ"
    else: return "📦 БУСАД БАРАА"

def extract_date_from_filename(filename):
    filename = filename.lower()
    match = re.search(r'(\d{4})[-.](\d{1,2})[-.](\d{1,2})', filename)
    if match: return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    match_short = re.search(r'(\d{1,2})[-.](\d{1,2})', filename)
    if match_short:
        month, day = int(match_short.group(1)), int(match_short.group(2))
        return f"2026-{month:02d}-{day:02d}"
    return None

def style_discrepancy(row):
    val = row['Зөрүү (Илүү/Дутуу)']
    if val < 0: return ['background-color: #3e1616; color: #ff7b72; font-weight: bold;'] * len(row)
    elif val > 0: return ['background-color: #342810; color: #d4a373; font-weight: bold;'] * len(row)
    return [''] * len(row)

def style_counting_errors(row):
    return ['background-color: #11253d; color: #58a6ff; font-weight: bold;'] * len(row)

# --- ҮНДСЭН СҮҮЛЧИЙН АУДИТ МАТЕМАТИК ---
def process_single_day(pos_bytes, tool_bytes, is_pos_csv, is_tool_csv, prev_evening_dict):
    try:
        df_pos_raw = pd.read_csv(io.BytesIO(pos_bytes), header=None) if is_pos_csv else pd.read_excel(io.BytesIO(pos_bytes), header=None)
        h_idx_pos = 0
        for i, row in df_pos_raw.iterrows():
            row_text = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
            if 'item #' in row_text and 'qty sold' in row_text:
                h_idx_pos = i; break
        df_pos = pd.read_csv(io.BytesIO(pos_bytes), skiprows=h_idx_pos) if is_pos_csv else pd.read_excel(io.BytesIO(pos_bytes), skiprows=h_idx_pos)
        df_pos.columns = df_pos.columns.str.strip()
        df_pos['Item #'] = df_pos['Item #'].astype(str).str.replace(r'\.0$', '', regex=True)
        sys_sales = df_pos.groupby('Item #')['Qty Sold'].sum().to_dict()

        df_tool = None
        xls = pd.ExcelFile(io.BytesIO(tool_bytes))
        for sheet_name in xls.sheet_names:
            temp_df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
            for i, row in temp_df.iterrows():
                row_text = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
                if 'өглөө' in row_text or 'орой' in row_text:
                    df_tool = pd.read_excel(xls, sheet_name=sheet_name, skiprows=i); break
            if df_tool is not None: break

        if df_tool is None: return None
        df_tool.columns = df_tool.columns.astype(str).str.strip().str.lower()
        cols = df_tool.columns.tolist()
        
        c_code = [c for c in cols if any(x in c for x in ['№', 'код', 'code'])][0]
        c_name = [c for c in cols if any(x in c for x in ['бүтээгдэхүүн', 'нэр', 'name']) and 'unnamed' not in c][0]
        c_morn = [c for c in cols if 'өглөө' in c][0]
        c_delv = [c for c in cols if 'хүргэлт' in c][0] if [c for c in cols if 'хүргэлт' in c] else None
        c_even = [c for c in cols if 'орой' in c][0] if [c for c in cols if 'орой' in c] else None
        c_comm =
