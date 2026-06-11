import streamlit as st
import pandas as pd
import json
import os
import io
import re
from datetime import datetime

st.set_page_config(page_title="Bene Inventory Audit Ultimate", page_icon="☕", layout="wide")

HISTORY_FILE = "inventory_history.json"

# Хэрэглэгчийн интерфэйсийн дизайн (CSS)
st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; }
    .stButton>button { width: 100%; height: 3.2em; border-radius: 12px; font-weight: bold; margin-top: 10px; }
    .report-title { font-size: 22px; font-weight: bold; color: #1E3A8A; margin-top: 25px; margin-bottom: 12px; padding-bottom: 6px; border-bottom: 3px solid #3B82F6; }
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
    if "панини" in name_lower or "panini" in name_lower: return "🥪 ПАНИНИ БҮЛЭГ"
    elif any(x in name_lower for x in ["cake", "бялуу", "кекс", "roll", "торт"]): return "🍰 БЯЛУУ БҮЛЭГ"
    elif "сэндвич" in name_lower or "sandwich" in name_lower: return "🥪 СЭНДВИЧ БҮЛЭГ"
    else: return "📦 БУСАД БАРАА"

# Файлын нэрнээс огноог (Жишээ нь: 5.22 эсвэл 2026.05.22) унших функц
def extract_date_from_filename(filename):
    filename = filename.lower()
    match = re.search(r'(\d{4})[-.](\d{1,2})[-.](\d{1,2})', filename)
    if match: return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    match_short = re.search(r'(\d{1,2})[-.](\d{1,2})', filename)
    if match_short:
        month, day = int(match_short.group(1)), int(match_short.group(2))
        return f"2026-{month:02d}-{day:02d}"
    return None

# --- ХҮСНЭГТИЙН ӨНГӨ ХЭЛБЭРЖҮҮЛЭЛТ ---
def style_discrepancy(row):
    val = row['Зөрүү (Илүү/Дутуу)']
    if val < 0:
        return ['background-color: #fee2e2; color: #991b1b; font-weight: bold;'] * len(row) # Дутагдал = Улаан
    elif val > 0:
        return ['background-color: #fef3c7; color: #92400e; font-weight: bold;'] * len(row) # Илүүдэл = Шар
    return [''] * len(row)

def style_counting_errors(row):
    return ['background-color: #e0f2fe; color: #0369a1; font-weight: bold;'] * len(row) # Тооллогын алдаа = Цэнхэр

# --- ХОС ФАЙЛЫГ ӨДӨР ӨДРӨӨР НЬ ТУЛГАХ ҮНДСЭН МАТЕМАТИК ЛОГИК ---
def process_single_day(pos_bytes, tool_bytes, is_pos_csv, is_tool_csv, prev_evening_dict):
    try:
        # 1. ПОС унших (Баганын толгой хайх ухаалаг хайлт)
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

        # 2. Тооллого унших (Өглөө, орой гэсэн үгтэй мөрийг автомат илрүүлэх)
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
        c_comm = [c for c in cols if 'тайлбар' in c][0] if [c for c in cols if 'тайлбар' in c] else None

        df_tool = df_tool.dropna(subset=[c_code, c_name])

        report_list = []
        for _, row in df_tool.iterrows():
            code = str(row[c_code]).replace('.0', '').strip()
            name = str(row[c_name]).strip()
            if not code or code in ['nan', ''] or name in ['nan', '']: continue
                
            morn_val = clean_numeric(row[c_morn])
            delv_val = clean_numeric(row[c_delv]) if c_delv else 0
            even_val = clean_numeric(row[c_even]) if c_even else 0
            comment_val = str(row[c_comm]).strip() if c_comm and not pd.isna(row[c_comm]) else ""

            # 🔍 ӨГЛӨӨ ОРОЙН ТООЛЛОГЫН ЗӨРҮҮГ АУДИТ ХИЙХ
            counting_error_qty = 0
            counting_comment = ""
            if code in prev_evening_dict:
                prev_even = prev_evening_dict[code]
                if prev_even != morn_val:
                    counting_error_qty = morn_val - prev_even
                    counting_comment = f"❌ ОРОЙ БУРУУ ТООЛСОН! (Орой шивсэн: {prev_even} ш -> Өглөө бодит олдсон: {morn_val} ш)"
            
            sys_v = sys_sales.get(code, 0)
            act_sold = (morn_val + delv_val) - even_val
            diff = act_sold - sys_v
            
            audit_comment = comment_val
            if diff < 0: audit_comment = f"🚨 Дутагдал! {abs(diff)} ш суутгана. " + audit_comment
            elif diff > 0: audit_comment = f"📈 Илүү гарсан! {diff} ш. " + audit_comment

            report_list.append({
                "Код": code,
                "Барааны нэр": name.title(),
                "Өглөөний үлдэгдэл": morn_val,
                "Хүргэлт авсан": delv_val,
                "Оройн үлдэгдэл": even_val,
                "Бодит борлуулалт": int(act_sold),
                "Систем борлуулалт": int(sys_v),
                "Зөрүү (Илүү/Дутуу)": int(diff),
                "Аудит Тайлбар": audit_comment.strip(),
                "Тооллогын Зөрүү Аудит": counting_comment,
                "Тооллогын Алдаа Тоо": counting_error_qty
            })
        return report_list
    except:
        return None

# --- СТРИМЛИТ СУУРЬ ЦОНХНУУД ---
tab1, tab2 = st.tabs(["📥 1. САРЫН ФАЙЛУУД ОРУУЛАХ БҮТНЭЭР НЬ", "📊 2. УХААЛАГ АУДИТ БА ӨНГӨТ ТАЙЛАНГУУД"])

# --- ЦОНХ 1: БҮТЭН САРЫН ФАЙЛУУДЫГ ХҮЛЭЭЖ АВАХ ---
with tab1:
    st.markdown("### 📅 Сарын бүх ПОС болон Тооллогын файлыг тусад нь багцаар нь оруулах")
    st.info("💡 Зүүн талын хайрцагт 5-р сарын ПОС-оос татсан бүх Excel файлыг зэрэг сонгоод хийнэ. Баруун талд ажилчдын тоолсон 5-р сарын бүх файлыг цугт нь хийнэ.")
    
    col_upload1, col_upload2 = st.columns(2)
    with col_upload1:
        uploaded_pos_files = st.file_uploader("📂 1. ПОС-ын сарын бүх файлууд (Олноор сонгох):", type=['xlsx', 'csv'], accept_multiple_files=True, key="pos_bulk")
    with col_upload2:
        uploaded_tool_files = st.file_uploader("📋 2. ТООЛЛОГЫН сарын бүх файлууд (Олноор сонгох):", type=['xlsx', 'csv'], accept_multiple_files=True, key="tool_bulk")
    
    if st.button("⚡ БУТНИЙН САРААР НЬ АВТОМАТ ТУЛГАЖ Сканнердах", type="primary"):
        if not uploaded_pos_files or not uploaded_tool_files:
            st.error("🚨 Анхаар: Та хоёр хайрцагт хоёуланд нь сарын файлуудаа оруулсан байх шаардлагатай!")
        else:
            pos_files_dict = {}
            tool_files_dict = {}
            
            for f in uploaded_pos_files:
                f_date = extract_date_from_filename(f.name)
                if f_date: pos_files_dict[f_date] = f
                    
            for f in uploaded_tool_files:
                f_date = extract_date_from_filename(f.name)
                if f_date: tool_files_dict[f_date] = f
            
            common_dates = sorted(list(set(pos_files_dict.keys()).intersection(set(tool_files_dict.keys()))))
            
            if not common_dates:
                st.error("❌ Алдаа: Хоёр хайрцаг доторх файлуудаас ижил огноотой хослол олдсонгүй! Файлын нэр дээр огноо нь байгаа эсэхийг шалгана уу.")
            else:
                history = {} # Шинэ сарын датаг цэвэрлэж шинээр бодно
                running_prev_evening = {}
                
                progress_bar = st.progress(0)
                for index, d_str in enumerate(common_dates):
                    pos_f = pos_files_dict[d_str]
                    tool_f = tool_files_dict[d_str]
                    
                    res_items = process_single_day(pos_f.getvalue(), tool_f.getvalue(), pos_f.name.endswith('.csv'), tool_f.name.endswith('.csv'), running_prev_evening)
                    if res_items:
                        history[d_str] = {"items": res_items}
                        # Өнөөдөр оройн үлдэгдлийг маргааш өглөөний тулгалтад шилжүүлнэ
                        running_prev_evening = {str(i["Код"]): i["Оройн үлдэгдэл"] for i in res_items}
                    progress_bar.progress((index + 1) / len(common_dates))
                
                save_json(history)
                st.success(f"🎉 Амжилттай! Сарын нийт {len(common_dates)} хоногийн файлыг систем өдөр өдрөөр нь холбож бодож дууслаа. Одоо 2 дахь цонх руу шилжинэ үү.")

# --- ЦОНХ 2: УХААЛАГ АУДИТЫН ТАЙЛАНГУУДЫГ ХАРУУЛАХ ---
with tab2:
    st.markdown("### 📊 Анализ болон Аудитын хяналтын самбар")
    history = load_json()
    
    if not history:
        st.warning("📋 Системд хадгалагдсан мэдээлэл байхгүй байна. Эхлээд 1-р цонхонд сарын файлуудаа уншуулна уу.")
    else:
        dates_available = sorted(list(history.keys()))
        col_s, col_e = st.columns(2)
        with col_s: start_d = st.date_input("Эхлэх огноо шүүх:", datetime.strptime(dates_available[0], "%Y-%m-%d") if dates_available else datetime.now())
        with col_e: end_d = st.date_input("Дуусах огноо шүүх:", datetime.strptime(dates_available[-1], "%Y-%m-%d") if dates_available else datetime.now())
        
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
            
            # --- 1. СУУТГАЛ БА БОРЛУУЛАЛТЫН ЗӨРҮҮ (УЛААН/ШАР) ---
            st.markdown("<div class='report-title'>🚨 1. БОРЛУУЛАЛТЫН ЗӨРҮҮ БА СУУТГАЛЫН ХУУДАС (ПОС-оос зөрсөн)</div>", unsafe_allow_html=True)
            df_discrepancy = df_master[df_master['Зөрүү (Илүү/Дутуу)'] != 0].copy()
            
            if not df_discrepancy.empty:
                st.write("ПОС борлуулалт болон Тооллогын бодит борлуулалт хоорондоо зөрж, **Суутгал (Улаан)** эсвэл **Илүү (Шар)** гарсан бараанууд:")
                show_cols1 = ["Огноо", "Код", "Барааны нэр", "Өглөөний үлдэгдэл", "Хүргэлт авсан", "Оройн үлдэгдэл", "Бодит борлуулалт", "Систем борлуулалт", "Зөрүү (Илүү/Дутуу)", "Аудит Тайлбар"]
                styled_df1 = df_discrepancy[show_cols1].style.apply(style_discrepancy, axis=1)
                st.dataframe(styled_df1, use_container_width=True)
                
                # Excel татаж авах багц файл бэлдэх
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_discrepancy[show_cols1].to_excel(writer, sheet_name="Суутгалын хуудас", index=False)
                    df_master.to_excel(writer, sheet_name="Сарын нэгдсэн хөдөлгөөн", index=False)
                st.download_button(label="📥 САРЫН НЭГДСЭН EXCEL ФАЙЛ ТАТАЖ АВАХ", data=buffer.getvalue(), file_name=f"Bene_Sariin_Audit_Tailan.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.success("🥳 Сонгосон хугацаанд ПОС болон Тооллого зөрсөн ямар нэгэн дутагдал, суутгал алга байна!")

            # --- 2. ӨГЛӨӨ ОРОЙН ТООЛЛОГЫН АЛДАА (ЦЭНХЭР) ---
            st.markdown("<div class='report-title'>🔍 2. ӨГЛӨӨ / ОРОЙН ТООЛЛОГЫН АЛДААНЫ АУДИТ (Хэн буруу тоолсон бэ?)</div>", unsafe_allow_html=True)
            df_counting_errors = df_master[df_master['Тооллогын Алдаа Тоо'] != 0].copy()
            
            if not df_counting_errors.empty:
                st.info("💡 Өчигдөр орой хаахдаа ажилтан буруу тоолж шивснийг маргааш өглөөний ээлж нь зөв тоолж барьсан тохиолдлуудыг шүүж гаргав (Оройн ээлжинд сануулга өгөх хуудас):")
                show_cols2 = ["Огноо", "Код", "Барааны нэр", "Тооллогын Зөрүү Аудит"]
                styled_df2 = df_counting_errors[show_cols2].style.apply(style_counting_errors, axis=1)
                st.dataframe(styled_df2, use_container_width=True)
            else:
                st.success("✨ Оройн хаалтын тоо, маргааш өглөөний нээлтийн тоотой бүгд яг таг таарсан байна. Ажилчид маш хариуцлагатай тоолжээ.")

            # --- 3. САРЫН НЭГДҮҮЛСЭН ЕРӨНХИЙ ТАЙЛАН ---
            st.markdown("<div class='report-title'>📋 3. САРЫН НЭГДҮҮЛСЭН ДЭЛГЭРЭНГҮЙ ХӨДӨЛГӨӨН (Бүх бараа)</div>", unsafe_allow_html=True)
            st.dataframe(df_master[["Огноо", "Барааны бүлэг", "Код", "Барааны нэр", "Өглөөний үлдэгдэл", "Хүргэлт авсан", "Оройн үлдэгдэл", "Бодит борлуулалт", "Систем борлуулалт", "Зөрүү (Илүү/Дутуу)"]], use_container_width=True)
