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
        if isinstance(val, pd.Series):
            val = val.iloc[0]
        if pd.isna(val) or val == "":
            return 0
        return int(float(str(val).replace(',', '').replace(' ', '')))
    except:
        return 0

def safe_style_dataframe(df):
    def highlight_diff(row):
        val = row.get("Зөрүү (Илүү/Дутуу)", 0)
        color = ""
        if val < 0:
            color = "background-color: #ffcccc; color: black;"
        elif val > 0:
            color = "background-color: #ccffcc; color: black;"
        
        styles = [""] * len(row)
        # Зөрүү багана нь манай хүснэгтийн 7 дахь багана (0-ээс тоолбол 7)
        if "Зөрүү (Илүү/Дутуу)" in df.columns:
            diff_col_idx = df.columns.get_loc("Зөрүү (Илүү/Дутуу)")
            styles[diff_col_idx] = color
        return styles
    
    return df.style.apply(highlight_diff, axis=1)

st.set_page_config(page_title="Bene Inventory Pro", layout="wide")
st.markdown("""<style>.stButton>button { width: 100%; height: 3em; border-radius: 10px; font-weight: bold; margin-top: 10px; }</style>""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📝 2 ФАЙЛ ТУЛГАХ", "📊 САРЫН АРХИВ / ТАЙЛАН"])

# =====================================================================
# TAB 1: ТООЛЛОГО ХЭСЭГ
# =====================================================================
with tab1:
    st.subheader("📝 Өдрийн тооллого - Автомат тулгалт")
    
    history = load_json(HISTORY_FILE)
    
    c_date, c_staff1, c_staff2 = st.columns(3)
    with c_date:
        date_str = st.date_input("Тооллого хийх огноо:", datetime.now()).strftime("%Y-%m-%d")
    with c_staff1:
        staff_m = st.text_input("🌅 Өглөөний ээлж (M):", placeholder="Жишээ нь: Болд")
    with c_staff2:
        staff_c = st.text_input("🌃 Оройн ээлж (C):", placeholder="Жишээ нь: Бат")

    c_file1, c_file2 = st.columns(2)
    with c_file1:
        pos_excel = st.file_uploader("📂 1. ПОС-ын Excel (5.22i.xlsx мэт)", type=['xlsx', 'csv'])
    with c_file2:
        toollogo_excel = st.file_uploader("📋 2. Тооллогын Excel (2026.5.22.xlsx мэт)", type=['xlsx', 'csv'])

    st.write("---")
    
    past_dates = [d for d in history.keys() if d < date_str]
    latest_date = max(past_dates) if past_dates else None
    prev_evening_dict = {}
    
    if latest_date:
        st.info(f"💡 Өмнөх өдрийн ({latest_date}) архиваас оройн үлдэгдлийг автоматаар татаж, өнөөдрийн 'Өглөө'-ний тоог баталгаажуулна.")
        for item in history[latest_date].get('items', []):
            prev_evening_dict[str(item["Код"])] = item["Орой"]

    if st.button("📊 ХОЁР ФАЙЛЫГ ТУЛГАЖ ШАЛГАХ", type="primary"):
        if not staff_m or not staff_c:
            st.error("⚠️ Өглөө болон оройн ээлжийн ажилтны нэрийг заавал оруулна уу!")
        elif not pos_excel or not toollogo_excel:
            st.error("⚠️ ПОС-ын болон Тооллогын 2 файлыг ХОЁУЛАГ НЬ оруулна уу!")
        else:
            try:
                pos_bytes = pos_excel.getvalue()
                tool_bytes = toollogo_excel.getvalue()

                # 1. ПОС-ЫН ФАЙЛЫГ УНШИХ
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
                df_pos = df_pos.loc[:, ~df_pos.columns.duplicated()]
                
                df_pos['Item #'] = df_pos['Item #'].astype(str).str.replace(r'\.0$', '', regex=True)
                df_pos['Qty Sold'] = pd.to_numeric(df_pos['Qty Sold'], errors='coerce').fillna(0)
                sys_sales = df_pos.groupby('Item #')['Qty Sold'].sum().to_dict()

                # 2. ТООЛЛОГЫН ФАЙЛЫГ УНШИХ
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
                        temp_df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                        for i, row in temp_df.iterrows():
                            row_text = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
                            if 'өглөө' in row_text and 'орой' in row_text:
                                df_tool = pd.read_excel(xls, sheet_name=sheet_name, skiprows=i)
                                break
                        if df_tool is not None:
                            break

                if df_tool is None:
                    st.error("⚠️ 'Өглөө' болон 'Орой' баганатай мөр олдсонгүй.")
                    st.stop()
                    
                df_tool.columns = df_tool.columns.astype(str).str.strip().str.lower()
                df_tool = df_tool.loc[:, ~df_tool.columns.duplicated()]
                
                cols = df_tool.columns.tolist()
                
                c_code = [c for c in cols if '№' in c or 'код' in c or 'code' in c][0]
                c_name = [c for c in cols if ('бүтээгдэхүүн' in c or 'нэр' in c or 'name' in c) and 'unnamed' not in c][0]
                c_morn = [c for c in cols if 'өглөө' in c][0]
                c_delv = [c for c in cols if 'хүргэлт' in c][0] if [c for c in cols if 'хүргэлт' in c] else None
                c_even = [c for c in cols if 'орой' in c][0] if [c for c in cols if 'орой' in c] else None
                c_comm = [c for c in cols if 'тайлбар' in c][0] if [c for c in cols if 'тайлбар' in c] else None

                df_tool = df_tool.dropna(subset=[c_code, c_name])

                # 3. ТУЛГАЛТ ХИЙХ
                report_list = []
                for _, row in df_tool.iterrows():
                    raw_code = row[c_code]
                    raw_name = row[c_name]
                    if isinstance(raw_code, pd.Series): raw_code = raw_code.iloc[0]
                    if isinstance(raw_name, pd.Series): raw_name = raw_name.iloc[0]
                        
                    code = str(raw_code).replace('.0', '').strip()
                    name = str(raw_name).strip()
                    
                    if not code or code in ['nan', ''] or name in ['nan', '']:
                        continue
                        
                    morn_val = clean_numeric(row[c_morn])
                    delv_val = clean_numeric(row[c_delv]) if c_delv else 0
                    even_val = clean_numeric(row[c_even]) if c_even else 0
                    
                    raw_comm = row[c_comm] if c_comm else ""
                    if isinstance(raw_comm, pd.Series): raw_comm = raw_comm.iloc[0]
                    comment_val = str(raw_comm) if not pd.isna(raw_comm) and str(raw_comm) != "nan" else ""

                    if latest_date and code in prev_evening_dict:
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
                    
                st.session_state['temp_report'] = {
                    "staff_m": staff_m,
                    "staff_c": staff_c,
                    "items": report_list
                }
                st.success(f"✅ Тулгалт амжилттай хийгдлээ! (Нийт {len(report_list)} бараа)")
                
            except Exception as e:
                st.error(f"Файл уншихад алдаа гарлаа: {e}")

    if 'temp_report' in st.session_state:
        st.divider()
        st.subheader(f"🔍 ТУЛГАЛТЫН ДҮН ({date_str})")
        
        report_data = st.session_state['temp_report']
        res_df = pd.DataFrame(report_data["items"])
        
        styled_df = safe_style_dataframe(res_df).format(precision=0)
        st.dataframe(styled_df, use_container_width=True)
        
        # Хүснэгтийн доор ажилчдын мэдээллийг харуулах
        st.markdown(f"**Ээлжийн ажилчид:** 🌅 Өглөө (M): `{report_data['staff_m']}` | 🌃 Орой (C): `{report_data['staff_c']}`")
        
        if st.button("🏁 ЭНЭ ӨДРИЙГ АРХИВТ ХАДГАЛАХ", type="primary"):
            history[date_str] = report_data
            save_json(history, HISTORY_FILE)
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
        for d, day_data in history.items():
            if start_str <= d <= end_str:
                # Хуучин хувилбарын архив (жагсаалт) байвал алгасахгүй зохицуулах
                if isinstance(day_data, list):
                    items = day_data
                    staff_m_val = items[0].get("ПОС Ажилтан", "Тодорхойгүй") if items else "Тодорхойгүй"
                    staff_c_val = staff_m_val
                else:
                    items = day_data.get("items", [])
                    staff_m_val = day_data.get("staff_m", "Тодорхойгүй")
                    staff_c_val = day_data.get("staff_c", "Тодорхойгүй")

                for i in items:
                    # Дэлгэрэнгүй тайланд зориулж мэдээллээ нэмэх
                    rec = i.copy()
                    rec['Огноо'] = d
                    rec['Өглөө (M)'] = staff_m_val
                    rec['Орой (C)'] = staff_c_val
                    if "ПОС Ажилтан" in rec:
                        del rec["ПОС Ажилтан"]
                    all_recs.append(rec)
                    
        if all_recs:
            df_all = pd.DataFrame(all_recs)
            # Багануудын дарааллыг янзлах
            cols_order = ["Огноо", "Өглөө (M)", "Орой (C)", "Код", "Барааны нэр", "Өглөө", "Хүргэлт", "Орой", "Бодит борлуулалт", "Систем борлуулалт", "Зөрүү (Илүү/Дутуу)", "Тайлбар"]
            df_all = df_all[[c for c in cols_order if c in df_all.columns]]
            
            st.write(f"### 📅 {start_str} -аас {end_str} хүртэлх тайлан")
            
            styled_all_df = safe_style_dataframe(df_all).format(precision=0)
            st.dataframe(styled_all_df, use_container_width=True)
            
            st.divider()
            st.subheader("💰 Суутгалын нэгтгэл (Зөвхөн дутсан бараагаар)")
            
            dut_df = df_all[df_all["Зөрүү (Илүү/Дутуу)"] < 0].copy()
            if not dut_df.empty:
                # Оройн ээлжийн хүн голчлон хариуцах тул "Орой (C)"-ээр бүлэглэе
                summary_df = dut_df.groupby(["Орой (C)", "Барааны нэр"])["Зөрүү (Илүү/Дутуу)"].sum().reset_index()
                summary_df["Зөрүү (Илүү/Дутуу)"] = summary_df["Зөрүү (Илүү/Дутуу)"].abs()
                summary_df.columns = ["Хариуцагч (Оройн ээлж)", "Дутсан бараа", "Нийт дутсан ширхэг"]
                st.table(summary_df)
            else:
                st.info("🥳 Энэ хугацаанд ямар ч бараа дутаагүй байна!")
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_all.to_excel(writer, sheet_name="Өдрийн дэлгэрэнгүй", index=False)
                if not dut_df.empty:
                    summary_df.to_excel(writer, sheet_name="Суутгалын хуудас", index=False)
                    
            st.download_button("📥 EXCEL ТАЙЛАН ТАТАХ", buffer.getvalue(), f"Tailan_{start_str}_{end_str}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            
            st.write("---")
            with st.expander("🗑️ Хуучин архив устгах"):
                del_date = st.selectbox("Устгах огноо сонгох:", sorted(history.keys(), reverse=True))
                if st.button("❌ Архиваас бүрмөсөн устгах"):
                    del history[del_date]
                    save_json(history, HISTORY_FILE)
                    st.rerun()
        else:
            st.warning("📅 Сонгосон хугацаанд архив олдсонгүй.")
    else:
        st.info("Архив одоогоор хоосон байна.")
