import streamlit as st
import pandas as pd
import json
import os
import io
import re
from datetime import datetime

st.set_page_config(page_title="Bene Inventory Audit Pro", page_icon="☕", layout="wide")

HISTORY_FILE = "inventory_history.json"

# Стиль болон дизайн
st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; }
    .stButton>button { width: 100%; height: 3.2em; border-radius: 12px; font-weight: bold; margin-top: 10px; }
    .report-title { font-size: 20px; font-weight: bold; color: #1E3A8A; margin-top: 20px; margin-bottom: 10px; padding-bottom: 5px; border-bottom: 2px solid #3B82F6; }
</style>
""", unsafe_allow_html=True)

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
    if "панини" in name_lower or "panini" in name_lower: return "🥪 ПАНИНИ"
    elif any(x in name_lower for x in ["cake", "бялуу", "кекс", "roll", "торт"]): return "🍰 БЯЛУУ"
    elif "сэндвич" in name_lower or "sandwich" in name_lower: return "🥪 СЭНДВИЧ"
    else: return "📦 БУСАД"

def extract_date_from_filename(filename):
    filename = filename.lower()
    match = re.search(r'(\d{4})[-.](\d{1,2})[-.](\d{1,2})', filename)
    if match: return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    match_short = re.search(r'(\d{1,2})[-.](\d{1,2})', filename)
    if match_short:
        month, day = int(match_short.group(1)), int(match_short.group(2))
        if month in [1,2,3,4,5,6,7,8,9,10,11,12]: return f"2026-{month:02d}-{day:02d}"
    return None

# --- ХҮСНЭГТИЙН МӨРӨНД ӨНГӨ ОРУУЛАХ ФУНКЦ ---
def highlight_rows(row):
    # Зөрүү (Илүү/Дутуу) багана дээр суурилж өнгө тавина
    val = row['Зөрүү (Илүү/Дутуу)']
    if val < 0:
        return ['background-color: #fee2e2; color: #991b1b'] * len(row) # Дутагдал = Улаан фоноор ялгана
    elif val > 0:
        return ['background-color: #fef3c7; color: #92400e'] * len(row) # Илүү гарсан = Шар фоноор ялгана
    return [''] * len(row)

# --- ҮНДСЭН БОДОЛТЫН ЛОГИК ---
def process_single_day(pos_bytes, tool_bytes, is_pos_csv, is_tool_csv, prev_evening_dict):
    try:
        # 1. ПОС файл унших
        df_pos = pd.read_csv(io.BytesIO(pos_bytes), skiprows=0) if is_pos_csv else pd.read_excel(io.BytesIO(pos_bytes), skiprows=0)
        h_idx_pos = 0
        for i, row in df_pos.iterrows():
            row_text = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
            if 'item #' in row_text and 'qty sold' in row_text:
                h_idx_pos = i; break
        df_pos = pd.read_csv(io.BytesIO(pos_bytes), skiprows=h_idx_pos) if is_pos_csv else pd.read_excel(io.BytesIO(pos_bytes), skiprows=h_idx_pos)
        df_pos.columns = df_pos.columns.str.strip()
        df_pos['Item #'] = df_pos['Item #'].astype(str).str.replace(r'\.0$', '', regex=True)
        sys_sales = df_pos.groupby('Item #')['Qty Sold'].sum().to_dict()

        # 2. Тооллогын файл унших
        df_tool = None
        xls = pd.ExcelFile(io.BytesIO(tool_bytes))
        for sheet_name in xls.sheet_names:
            temp_df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
            for i, row in temp_df.iterrows():
                if 'өглөө' in " ".join([str(x).lower() for x in row.values if pd.notna(x)]):
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
        c_comm = [c for c in cols if 'тайлбар' in c][0] if [c for c in cols if 'тайлбар' in c] else None

        df_tool = df_tool.dropna(subset=[c_code, c_name])

        report_list = []
        for _, row in df_tool.iterrows():
            code = str(row[c_code]).replace('.0', '').strip()
            name = str(row[c_name]).strip()
            if not code or code in ['nan', '']: continue
                
            morn_val = clean_numeric(row[c_morn])
            delv_val = clean_numeric(row[c_delv]) if c_delv else 0
            even_val = clean_numeric(row[c_even]) if c_even else 0
            comment_val = str(row[c_comm]).strip() if c_comm and not pd.isna(row[c_comm]) else ""

            # 🌟 ӨГЛӨӨ, ОРОЙН ТООЛЛОГЫН ЗӨРҮҮГ ОЛЖ ЯЛГАХ
            counting_error_qty = 0
            counting_comment = ""
            if code in prev_evening_dict:
                prev_even = prev_evening_dict[code]
                if prev_even != morn_val:
                    counting_error_qty = morn_val - prev_even
                    counting_comment = f"❌ Өчигдөр орой буруу тоолсон (Орой шивсэн: {prev_even} -> Өглөө бодит: {morn_val})"
            
            sys_v = sys_sales.get(code, 0)
            act_sold = (morn_val + delv_val) - even_val
            diff = act_sold - sys_v
            
            # Суутгалын тайлбар үүсгэх
            audit_comment = comment_val
            if diff < 0:
                audit_comment = f"🚨 Суутгана! {abs(diff)} ш дутсан. " + audit_comment
            elif diff > 0:
                audit_comment = f"📈 Илүү гарсан {diff} ш. " + audit_comment

            report_list.append({
                "Код": code,
                "Барааны нэр": name.title(),
                "Өглөө": morn_val,
                "Хүргэлт": delv_val,
                "Орой": even_val,
                "Бодит борлуулалт": int(act_sold),
                "Систем борлуулалт": int(sys_v),
                "Зөрүү (Илүү/Дутуу)": int(diff),
                "Аудит Тайлбар": audit_comment.strip(),
                "Тооллогын Зөрүү Чиглэл": counting_comment,
                "Тооллогын Алдаа Тоо": counting_error_qty
            })
        return report_list
    except Exception as e:
        return None

# --- СТРИМЛИТ ТАВУУД ---
tab1, tab2 = st.tabs(["📥 САРЫН ФАЙЛУУД ОРУУЛАХ", "📊 УХААЛАГ АУДИТЫН ХЯНАЛТЫН ЦОНХ"])

with tab1:
    st.markdown("### 📅 Сарын бүх ПОС болон Тооллогын файлыг бөөнд нь уншуулах")
    st.info("💡 Та энэ хэсэгт тухайн сарын бүх өдрийн ПОС-ын Excel болон Тооллогын Excel файлуудыг цугт нь идэвхжүүлээд чирч оруулж болно. Систем огноогоор нь автоматаар хослуулж өдөр өдрөөр нь тулгана.")
    
    uploaded_files = st.file_uploader("Файлуудаа сонгоно уу:", type=['xlsx', 'csv'], accept_multiple_files=True)
    
    if st.button("⚡ БУТНИЙН САРААР НЬ АВТОМАТ ТУЛГАХ"):
        if uploaded_files:
            pos_files, tool_files = {}, {}
            for f in uploaded_files:
                f_date = extract_date_from_filename(f.name)
                if f_date:
                    if any(x in f.name.lower() for x in ['summary', 'pos', 'i.xlsx', 'i.csv']): 
                        pos_files[f_date] = f
                    else: 
                        tool_files[f_date] = f
            
            common_dates = sorted(list(set(pos_files.keys()).intersection(set(tool_files.keys()))))
            
            if not common_dates:
                st.error("❌ Файлын нэрнээс тохирох огноо олдсонгүй эсвэл ПОС болон Тооллогын хос өдрүүд таарахгүй байна! (Жишээ нэр: '2026-05-10_pos.xlsx', '2026-05-10_toollogo.xlsx')")
            else:
                history = {} # Шинээр бүх сарыг цэвэр бодно
                running_prev_evening = {}
                
                progress_bar = st.progress(0)
                for index, d_str in enumerate(common_dates):
                    res_items = process_single_day(
                        pos_files[d_str].getvalue(), 
                        tool_files[d_str].getvalue(), 
                        pos_files[d_str].name.endswith('.csv'), 
                        tool_files[d_str].name.endswith('.csv'), 
                        running_prev_evening
                    )
                    if res_items:
                        history[d_str] = {"items": res_items}
                        # Маргааш өдрийн өглөөний тулгалтад зориулж өнөөдрийн оройн тоог хадгална
                        running_prev_evening = {str(i["Код"]): i["Орой"] for i in res_items}
                    progress_bar.progress((index + 1) / len(common_dates))
                
                save_json(history)
                st.success(f"🎉 Сарын нийт {len(common_dates)} өдрийн файлыг амжилттай уншиж, суутгал болон тооллогын зөрүүг бодож дууслаа! Одоо 'УХААЛАГ АУДИТЫН ХЯНАЛТЫН ЦОНХ' тав руу орж үзнэ үү.")

with tab2:
    st.markdown("### 📊 Анализ болон Ухаалаг хяналтын самбар")
    history = load_json()
    
    if not history:
        st.warning("📋 Одоогоор системд хадгалагдсан өгөгдөл алга. Эхлээд 'САРЫН ФАЙЛУУД ОРУУЛАХ' хэсэгт файлаа уншуулна уу.")
    else:
        # Огноо шүүлтүүр
        dates_available = sorted(list(history.keys()))
        col_s, col_e = st.columns(2)
        with col_s: start_d = st.date_input("Эхлэх огноо:", datetime.strptime(dates_available[0], "%Y-%m-%d") if dates_available else datetime.now())
        with col_e: end_d = st.date_input("Дуусах огноо:", datetime.strptime(dates_available[-1], "%Y-%m-%d") if dates_available else datetime.now())
        
        all_rows = []
        for d, day_data in history.items():
            if start_d.strftime("%Y-%m-%d") <= d <= end_d.strftime("%Y-%m-%d"):
                items = day_data.get("items", [])
                for i in items:
                    r = i.copy()
                    r['Огноо'] = d
                    r['Барааны бүлэг'] = get_item_group(r['Барааны нэр'])
                    all_rows.append(r)
        
        if all_rows:
            df_master = pd.DataFrame(all_rows)
            
            # -------------------------------------------------------------
            # ТАЙЛАН 1: СУУТГАЛ БА ЗӨРҮҮНИЙ ТАЙЛАН (ПОС болон Тооллого зөрсөн)
            # -------------------------------------------------------------
            st.markdown("<div class='report-title'>🚨 1. БОРЛУУЛАЛТЫН ЗӨРҮҮ БА СУУТГАЛЫН ХУУДАС</div>", unsafe_allow_html=True)
            st.write("ПОС борлуулалт болон Бодит борлуулалт хоорондоо зөрж, **Дутагдал (Улаан)** эсвэл **Илүү (Шар)** гарсан бараануудыг шүүж харуулж байна. Эндээс шууд суутгалыг тооцно.")
            
            df_discrepancy = df_master[df_master['Зөрүү (Илүү/Дутуу)'] != 0].copy()
            
            if not df_discrepancy.empty:
                # Өнгөөр ялгасан хүснэгтийг харуулах
                styled_df = df_discrepancy[["Огноо", "Код", "Барааны нэр", "Өглөө", "Хүргэлт", "Орой", "Бодит борлуулалт", "Систем борлуулалт", "Зөрүү (Илүү/Дутуу)", "Аудит Тайлбар"]]\
                    .style.apply(highlight_rows, axis=1)
                st.dataframe(styled_df, use_container_width=True)
            else:
                st.success("🥳 Сонгосон хугацаанд ПОС болон Тооллого зөрсөн ямар нэгэн дутагдал, суутгал алга байна!")

            # -------------------------------------------------------------
            # ТАЙЛАН 2: ТООЛЛОГЫН АЛДААНЫ АУДИТ (Өглөө, орой зөрсөн)
            # -------------------------------------------------------------
            st.markdown("<div class='report-title'>🔍 2. ӨГЛӨӨ / ОРОЙН ТООЛЛОГЫН АЛДААНЫ АУДИТ (Хэн буруу тоолсон бэ?)</div>", unsafe_allow_html=True)
            st.write("Өчигдөр оройн ээлжийн хааж тоолсон тоо маргааш өглөөний ээлжийн нээж тоолсон бодит тоотой **ЗӨРСӨН** тохиолдлууд. Өөрөөр хэлбэл, хэн хариуцлагагүй буруу тоолсныг эндээс шүүнэ.")
            
            df_counting_errors = df_master[df_master['Тооллогын Алдаа Тоо'] != 0].copy()
            
            if not df_counting_errors.empty:
                st.warning("⚠️ Өчигдөр оройн ээлж барааг буруу (дутуу эсвэл илүү) тоолж шивсэн байна. Өглөөний ээлж бодитоор зөв тоолж залруулсан тул өдрийн тооцоолол зөв гарсан боловч, хуучин ээлжинд тооллогын сануулга өгөх үндэслэл болно.")
                st.dataframe(df_counting_errors[["Огноо", "Код", "Барааны нэр", "Тооллогын Зөрүү Чиглэл"]], use_container_width=True)
            else:
                st.success("✨ Гайхалтай! Өмнөх оройн хаалтын тоо, маргааш өглөөний нээлтийн тоотой бүгд яг таг таарсан байна. Ажилчид маш хариуцлагатай тоолжээ.")

            # -------------------------------------------------------------
            # ТАЙЛАН 3: САРЫН НЭГДҮҮЛСЭН ЕРӨНХИЙ ТАЙЛАН
            # -------------------------------------------------------------
            st.markdown("<div class='report-title'>📋 3. САРЫН НЭГДҮҮЛСЭН ДЭЛГЭРЭНГҮЙ ХӨДӨЛГӨӨН</div>", unsafe_allow_html=True)
            st.write("Зөрүүтэй болон зөрүүгүй бүх бараа бүтээгдэхүүний сарын нэгдсэн хөдөлгөөний хүснэгт.")
            st.dataframe(df_master[["Огноо", "Барааны бүлэг", "Код", "Барааны нэр", "Өглөө", "Хүргэлт", "Орой", "Бодит борлуулалт", "Систем борлуулалт", "Зөрүү (Илүү/Дутуу)"]], use_container_width=True)
