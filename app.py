import streamlit as st
import pandas as pd
import json
import os
import io
import re
from datetime import datetime

# --- СИСТЕМИЙН ҮНДСЭН ТОХИРГОО ---
st.set_page_config(
    page_title="Bene Inventory Enterprise", 
    page_icon="☕",
    layout="wide"
)

HISTORY_FILE = "inventory_history.json"

st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; }
    .stButton>button { width: 100%; height: 3.2em; border-radius: 12px; font-weight: bold; margin-top: 10px; transition: 0.3s; }
    .stButton>button:hover { background-color: #1E88E5; color: white; transform: scale(1.01); }
    .metric-card { background-color: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center; border-left: 5px solid #2196F3; }
    .metric-card.loss { border-left-color: #ef5350; }
    .metric-card.gain { border-left-color: #66bb6a; }
</style>
""", unsafe_allow_html=True)

# --- ТУСЛАХ ФУНКЦҮҮД ---
def load_json():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def clean_numeric(val):
    try:
        if isinstance(val, pd.Series): val = val.iloc[0]
        if pd.isna(val) or val == "": return 0
        return int(float(str(val).replace(',', '').replace(' ', '')))
    except:
        return 0

def safe_style_dataframe(df):
    def highlight_rows(row):
        val = row.get("Зөрүү (Илүү/Дутуу)", 0)
        status = row.get("Суутгал бодох эсэх", "")
        styles = [""] * len(row)
        if "Зөрүү (Илүү/Дутуу)" in df.columns:
            idx = df.columns.get_loc("Зөрүү (Илүү/Дутуу)")
            if val < 0: styles[idx] = "background-color: #ffebee; color: #c62828; font-weight: bold;"
            elif val > 0: styles[idx] = "background-color: #e8f5e9; color: #2e7d32; font-weight: bold;"
        if "Суутгал бодох эсэх" in df.columns:
            s_idx = df.columns.get_loc("Суутгал бодох эсэх")
            if status == "Бодит дутагдал (Суутгана)": styles[s_idx] = "background-color: #ffcdd2; color: #b71c1c; font-weight: bold;"
            elif status == "Зөрүүгээр хаасан (Суутгахгүй)": styles[s_idx] = "background-color: #fff9c4; color: #f57f17;"
        return styles
    return df.style.apply(highlight_rows, axis=1)

def get_item_group(item_name):
    name_lower = str(item_name).lower()
    if "панини" in name_lower or "panini" in name_lower: return "🥪 ПАНИНИ БҮЛЭГ"
    elif any(x in name_lower for x in ["cake", "бялуу", "кекс", "roll", "торт"]): return "🍰 БЯЛУУ БҮЛЭГ"
    elif "сэндвич" in name_lower or "sandwich" in name_lower: return "🥪 СЭНДВИЧ БҮЛЭГ"
    elif any(x in name_lower for x in ["ade", "smoothie", "шүүс", "juice", "tea"]): return "🍹 УНДАА БҮЛЭГ"
    else: return "📦 БУСАД БАРАА"

# Файлын нэрнээс огноог ухаалгаар олж илрүүлэх функц (Жишээ нь: 2026.5.22, 5.22i -> 2026-05-22)
def extract_date_from_filename(filename):
    filename = filename.lower()
    match = re.search(r'(\d{4})[-.](\d{1,2})[-.](\d{1,2})', filename)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    match_short = re.search(r'(\d{1,2})[-.](\d{1,2})', filename)
    if match_short:
        month = int(match_short.group(1))
        day = int(match_short.group(2))
        if month in [5, 6]:  # Таны хэлж буй 5 болон 6-р сарын файлууд дахь хамгаалалт
            return f"2026-{month:02d}-{day:02d}"
    return None

# ПОС болон Тооллогын 1 өдрийн файлыг тулгаж боддог үндсэн функц
def process_single_day(pos_bytes, tool_bytes, is_pos_csv, is_tool_csv, prev_evening_dict):
    try:
        # 1. ПОС унших
        if is_pos_csv:
            df_pos_raw = pd.read_csv(io.BytesIO(pos_bytes), header=None)
        else:
            df_pos_raw = pd.read_excel(io.BytesIO(pos_bytes), header=None)
        h_idx_pos = 0
        for i, row in df_pos_raw.iterrows():
            row_text = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
            if 'item #' in row_text and 'qty sold' in row_text:
                h_idx_pos = i
                break
        df_pos = pd.read_csv(io.BytesIO(pos_bytes), skiprows=h_idx_pos) if is_pos_csv else pd.read_excel(io.BytesIO(pos_bytes), skiprows=h_idx_pos)
        df_pos.columns = df_pos.columns.str.strip()
        df_pos = df_pos.loc[:, ~df_pos.columns.duplicated()]
        df_pos['Item #'] = df_pos['Item #'].astype(str).str.replace(r'\.0$', '', regex=True)
        df_pos['Qty Sold'] = pd.to_numeric(df_pos['Qty Sold'], errors='coerce').fillna(0)
        sys_sales = df_pos.groupby('Item #')['Qty Sold'].sum().to_dict()

        # 2. Тооллого унших
        df_tool = None
        if is_tool_csv:
            df_tool_raw = pd.read_csv(io.BytesIO(tool_bytes), header=None)
            for i, row in df_tool_raw.iterrows():
                if 'өглөө' in " ".join([str(x).lower() for x in row.values if pd.notna(x)]):
                    df_tool = pd.read_csv(io.BytesIO(tool_bytes), skiprows=i)
                    break
        else:
            xls = pd.ExcelFile(io.BytesIO(tool_bytes))
            for sheet_name in xls.sheet_names:
                temp_df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                for i, row in temp_df.iterrows():
                    if 'өглөө' in " ".join([str(x).lower() for x in row.values if pd.notna(x)]):
                        df_tool = pd.read_excel(xls, sheet_name=sheet_name, skiprows=i)
                        break
                if df_tool is not None: break

        if df_tool is None: return None
        
        df_tool.columns = df_tool.columns.astype(str).str.strip().str.lower()
        df_tool = df_tool.loc[:, ~df_tool.columns.duplicated()]
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
            
            raw_comm = row[c_comm] if c_comm else ""
            comment_val = str(raw_comm).strip() if not pd.isna(raw_comm) and str(raw_comm) != "nan" else ""

            # Өмнөх оройн үлдэгдлээр солих ухаалаг логик
            if code in prev_evening_dict:
                morn_val = prev_evening_dict[code]

            sys_v = sys_sales.get(code, 0)
            act_sold = (morn_val + delv_val) - even_val
            diff = act_sold - sys_v
            
            report_list.append({
                "Код": code,
                "Барааны нэр": name.title(),
                "Өглөө": morn_val,
                "Хүргэлт": delv_val,
                "Орой": even_val,
                "Бодит борлуулалт": int(act_sold),
                "Систем борлуулалт": int(sys_v),
                "Зөрүү (Илүү/Дутуу)": int(diff),
                "Тайлбар": comment_val
            })
        return report_list
    except:
        return None

# --- ТАВУУДЫН ХУВААЛТ ---
tab1, tab2, tab3 = st.tabs(["📝 НЭГ ӨДРӨӨР ТУЛГАХ", "📅 БАГЦ ФАЙЛ УНШИХ (БҮХ САРЫН)", "📊 УХААЛАГ САРЫН ХЯНАЛТ (DASHBOARD)"])

# =====================================================================
# TAB 1: НЭГ ӨДРӨӨР ТУЛГАХ (Хуучин хэвээрээ)
# =====================================================================
with tab1:
    st.markdown("### 📝 Өдрийн тооллогын тулгалт хийх")
    history = load_json()
    with st.container(border=True):
        c_date, c_staff1, c_staff2 = st.columns(3)
        with c_date: date_str = st.date_input("Тооллого хийх огноо:", datetime.now()).strftime("%Y-%m-%d")
        with c_staff1: staff_m = st.text_input("🌅 Өглөөний ээлж (M):", key="m1", placeholder="Болд")
        with c_staff2: staff_c = st.text_input("🌃 Оройн ээлж (C):", key="c1", placeholder="Бат")
    c_f1, c_f2 = st.columns(2)
    with c_f1: pos_excel = st.file_uploader("📂 ПОС-ын файл", type=['xlsx', 'csv'], key="pos1")
    with c_f2: toollogo_excel = st.file_uploader("📋 Тооллогын файл", type=['xlsx', 'csv'], key="tool1")

    past_dates = [d for d in history.keys() if d < date_str]
    latest_date = max(past_dates) if past_dates else None
    prev_evening_dict = {}
    if latest_date:
        day_data = history[latest_date]
        items_to_load = day_data if isinstance(day_data, list) else day_data.get('items', [])
        for item in items_to_load: prev_evening_dict[str(item["Код"])] = item["Орой"]

    if st.button("🚀 ТУЛГАХ", key="btn1"):
        if pos_excel and toollogo_excel:
            res = process_single_day(pos_excel.getvalue(), toollogo_excel.getvalue(), pos_excel.name.endswith('.csv'), toollogo_excel.name.endswith('.csv'), prev_evening_dict)
            if res:
                st.session_state['temp_report'] = {"staff_m": staff_m, "staff_c": staff_c, "items": res}
                st.success("🎯 Тулгаж дууслаа.")
        else: st.error("Файлуудаа оруулна уу.")

    if 'temp_report' in st.session_state:
        st.divider()
        report_data = st.session_state['temp_report']
        res_df = pd.DataFrame(report_data["items"])
        st.dataframe(safe_style_dataframe(res_df).format(precision=0), use_container_width=True)
        if st.button("🏁 АРХИВТ ХАДГАЛАХ"):
            history[date_str] = report_data
            save_json(history)
            del st.session_state['temp_report']
            st.rerun()

# =====================================================================
# TAB 2: БАГЦ ФАЙЛ УНШИХ (БҮХ САРЫН ФАЙЛУУДЫГ НЭГ ДОР УНШИХ ХЭСЭГ)
# =====================================================================
with tab2:
    st.markdown("### 📅 Сарын бүх Excel файлыг нэг дор уншуулах")
    st.info("ℹ️ Та энд 5-р сарынхаа ПОС-ын бүх файл, Тооллогын бүх файлуудыг цугт нь нэг дор сонгоод хийчихэж болно. Систем өөрөө огноогоор нь дараалуулан автоматаар бодно.")
    
    uploaded_files = st.file_uploader("📂 Сонгох эсвэл файлыг чирч оруулна уу (Олон файл зэрэг сонгож болно):", type=['xlsx', 'csv'], accept_multiple_files=True)
    
    if st.button("⚡ БҮХ САРЫН ФАЙЛЫГ БӨӨНД НЬ БОДОХ", type="primary"):
        if not uploaded_files:
            st.error("🚨 Наад зах нь хэд хэдэн Excel файл оруулна уу!")
        else:
            pos_files_dict = {}
            tool_files_dict = {}
            
            # Файлуудыг ПОС болон Тооллогоор нь огноогоор нь ангилах
            for f in uploaded_files:
                f_date = extract_date_from_filename(f.name)
                if f_date:
                    f_name_lower = f.name.lower()
                    if 'summary' in f_name_lower or 'pos' in f_name_lower or 'i.xlsx' in f_name_lower or 'i.csv' in f_name_lower:
                        pos_files_dict[f_date] = f
                    else:
                        tool_files_dict[f_date] = f
            
            # Нийтлэг олдсон огноонуудыг эрэмбэлэх (Хамгийн эхний өдрөөс эхэлж бодно)
            common_dates = sorted(list(set(pos_files_dict.keys()).intersection(set(tool_files_dict.keys()))))
            
            if not common_dates:
                st.error("🚨 Алдаа: Файлуудын нэрнээс ижил огноотой ПОС болон Тооллогын хослол олдсонгүй! Файлын нэр дээр огноо нь байгаа эсэхийг шалгана уу (Жишээ нь: 5.21 эсвэл 2026.05.21).")
            else:
                st.write(f"🔄 Нийт **{len(common_dates)}** өдрийн файлыг илрүүллээ. Дарааллаар нь бодож байна...")
                
                history = load_json()
                running_prev_evening = {}
                
                # Хэрэв баазад өмнөх өдрүүд байвал хамгийн сүүлчийн өдрийн оройг авна
                past_existing = [d for d in history.keys() if d < common_dates[0]]
                if past_existing:
                    last_d = max(past_existing)
                    items_load = history[last_d] if isinstance(history[last_d], list) else history[last_d].get('items', [])
                    for item in items_load:
                        running_prev_evening[str(item["Код"])] = item["Орой"]
                        
                success_count = 0
                for d_str in common_dates:
                    pos_f = pos_files_dict[d_str]
                    tool_f = tool_files_dict[d_str]
                    
                    res_items = process_single_day(pos_f.getvalue(), tool_f.getvalue(), pos_f.name.endswith('.csv'), tool_f.name.endswith('.csv'), running_prev_evening)
                    
                    if res_items:
                        # Түүхэнд хадгалах
                        history[d_str] = {
                            "staff_m": "Багц уншилт",
                            "staff_c": "Багц уншилт",
                            "items": res_items
                        }
                        # Дараагийн өдөрт зориулж оройн үлдэгдлийг шинэчлэх
                        running_prev_evening = {}
                        for item in res_items:
                            running_prev_evening[str(item["Код"])] = item["Орой"]
                        success_count += 1
                
                save_json(history)
                st.success(f"🎉 Амжилттай! Нийт {success_count} өдрийн тооллогыг багцаар нь бодож архивд орууллаа. Одоо хажуугийн цонх руу орж Сарын нэгдсэн Excel файлаа шууд татаж авна уу.")

# =====================================================================
# TAB 3: САРЫН ХЯНАЛТ (DASHBOARD & EXCEL ТАТАХ СЕКЦ)
# =====================================================================
with tab3:
    st.markdown("### 📊 Сарын нэгдсэн хяналтын самбар")
    history = load_json()
    if history:
        with st.container(border=True):
            col_d1, col_d2, col_filter = st.columns([1, 1, 1])
            with col_d1: start_date = st.date_input("Эхлэх огноо:", datetime.now().replace(day=1), key="sd")
            with col_d2: end_date = st.date_input("Дуусах огноо:", datetime.now(), key="ed")
        start_str, end_str = start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
        
        all_recs = []
        for d, day_data in history.items():
            if start_str <= d <= end_str:
                items = day_data if isinstance(day_data, list) else day_data.get("items", [])
                staff_m_val = "Үл мэдэгдэх" if isinstance(day_data, list) else day_data.get("staff_m", "Үл мэдэгдэх")
                staff_c_val = "Үл мэдэгдэх" if isinstance(day_data, list) else day_data.get("staff_c", "Үл мэдэгдэх")
                for i in items:
                    rec = i.copy()
                    rec['Огноо'] = d
                    rec['Өглөө (M)'] = staff_m_val
                    rec['Орой (C)'] = staff_c_val
                    rec['Барааны Бүлэг'] = get_item_group(rec['Барааны нэр'])
                    all_recs.append(rec)
                    
        if all_recs:
            df_all = pd.DataFrame(all_recs)
            df_all['Бүлэг_Өдрийн_Нийлбэр'] = df_all.groupby(['Огноо', 'Барааны Бүлэг'])['Зөрүү (Илүү/Дутуу)'].transform('sum')
            
            def calculate_smart_status(row):
                diff = row['Зөрүү (Илүү/Дутуу)']
                g_sum = row['Бүлэг_Өдрийн_Нийлбэр']
                if diff >= 0: return "Илүүдэл (Суутгахгүй)"
                if diff < 0 and g_sum >= 0: return "Зөрүүгээр хаасан (Суутгахгүй)"
                return "Бодит дутагдал (Суутгана)"
            df_all['Суутгал бодох эсэх'] = df_all.apply(calculate_smart_status, axis=1)
            
            loss_cnt = abs(df_all[df_all['Sub-Status' if 'Sub-Status' in df_all.columns else 'Суутгал бодох эсэх'] == "Бодит дутагдал (Суутгана)"]['Зөрүү (Илүү/Дутуу)'].sum())
            saved_cnt = abs(df_all[df_all['Суутгал бодох эсэх'] == "Зөрүүгээр хаасан (Суутгахгүй)"]['Зөрүү (Илүү/Дутуу)'].sum())
            gain_cnt = df_all[df_all['Зөрүү (Илүү/Дутуу)'] > 0]['Зөрүү (Илүү/Дутуу)'].sum()
            
            m1, m2, m3 = st.columns(3)
            with m1: st.markdown(f'<div class="metric-card loss"><h4>🚨 Нийт бодит дутагдал</h4><h2>{loss_cnt} ширхэг</h2></div>', unsafe_allow_html=True)
            with m2: st.markdown(f'<div class="metric-card"><h4>🥪 Зөрүүгээр хаагдсан</h4><h2>{saved_cnt} ширхэг</h2></div>', unsafe_allow_html=True)
            with m3: st.markdown(f'<div class="metric-card gain"><h4>📈 Илүү гарсан бараа</h4><h2>{gain_cnt} ширхэг</h2></div>', unsafe_allow_html=True)
                
            show_cols = ["Огноо", "Өглөө (M)", "Орой (C)", "Код", "Барааны нэр", "Барааны Бүлэг", "Өглөө", "Хүргэлт", "Орой", "Бодит борлуулалт", "Систем борлуулалт", "Зөрүү (Илүү/Дутуу)", "Суутгал бодох эсэх", "Тайлбар"]
            df_all_display = df_all[[c for c in show_cols if c in df_all.columns]]
            
            st.write("#### 📋 Сарын дэлгэрэнгүй тайлан")
            st.dataframe(safe_style_dataframe(df_all_display).format(precision=0), use_container_width=True)
            
            st.divider()
            st.subheader("💰 Жинхэнэ суутгал тооцох хуудас")
            deduct_filter = df_all[df_all['Суутгал бодох эсэх'] == "Бодит дутагдал (Суутгана)"].copy()
            if not deduct_filter.empty:
                deduct_filter['Тайлбар'] = deduct_filter['Тайлбар'].apply(lambda x: "🚨 ТАЙЛБАРГҮЙ ДУТАГДАЛ!" if x.strip() == "" else x)
                show_deduct = deduct_filter[["Огноо", "Орой (C)", "Барааны нэр", "Барааны Бүлэг", "Зөрүү (Илүү/Дутуу)", "Тайлбар"]].copy()
                show_deduct["Зөрүү (Илүү/Дутуу)"] = show_deduct["Зөрүү (Илүү/Дутуу)"].abs()
                show_deduct.columns = ["Огноо", "Хариуцагч (Орой)", "Дутсан бараа", "Ангилал", "Тоо ширхэг", "Ажилчны бичсэн тайлбар"]
                st.dataframe(show_deduct, use_container_width=True)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_all_display.to_excel(writer, sheet_name="Сарын дэлгэрэнгүй тайлан", index=False)
                if not deduct_filter.empty:
                    show_deduct.to_excel(writer, sheet_name="Суутгалын хуудас", index=False)
            
            st.download_button(
                label="📥 НЭГДСЭН САРЫН EXCEL ФАЙЛ ТАТАЖ АВАХ",
                data=buffer.getvalue(),
                file_name=f"Bene_Nizgdsen_Tailan_{start_str}_{end_str}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
