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
    
    # Дээд талын мэдээлэл оруулах хэсэг
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
                # ---------------------------------------------------------
                # 1. ПОС-ЫН ФАЙЛЫГ УНШИХ
                # ---------------------------------------------------------
                if pos_excel.name.endswith('.csv'):
                    df_pos_raw = pd.read_csv(pos_excel, header=None)
                else:
                    df_pos_raw = pd.read_excel(pos_excel, header=None)
                
                h_idx_pos = 0
                for i, row in df_pos_raw.iterrows():
                    row_text = " ".join([str(x) for x in row.values if pd.notna(x)])
                    if 'Item #' in row_text or 'Item Name' in row_text:
                        h_idx_pos = i
                        break
                
                if pos_excel.name.endswith('.csv'):
                    df_pos = pd.read_csv(pos_excel, skiprows=h_idx_pos)
                else:
                    df_pos = pd.read_excel(pos_excel, skiprows=h_idx_pos)
                
                df_pos.columns = df_pos.columns.str.strip()
                df_pos['Item #'] = df_pos['Item #'].astype(str).str.replace(r'\.0$', '', regex=True)
                df_pos['Qty Sold'] = pd.to_numeric(df_pos['Qty Sold'], errors='coerce').fillna(0)
                sys_sales = df_pos.groupby('Item #')['Qty Sold'].sum().to_dict()

                # ---------------------------------------------------------
                # 2. ТООЛЛОГЫН ФАЙЛЫГ УНШИХ (БҮХ SHEET-ИЙГ ШАЛГАХ)
                # ---------------------------------------------------------
                h_idx_tool = -1
                df_tool = None
                
                if toollogo_excel.name.endswith('.csv'):
                    df_tool_raw = pd.read_csv(toollogo_excel, header=None)
                    for i, row in df_tool_raw.iterrows():
                        row_text = " ".join([str(x) for x in row.values if pd.notna(x)])
                        if 'Бүтээгдэхүүн' in row_text or 'Өглөө' in row_text:
                            h_idx_tool = i
                            break
                    if h_idx_tool != -1:
                        df_tool = pd.read_csv(toollogo_excel, skiprows=h_idx_tool)
                else:
                    # Excel байвал бүх хуудас (sheet)-рүү орж хайна
                    xls = pd.ExcelFile(toollogo_excel)
                    for sheet_name in xls.sheet_names:
                        temp_df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                        for i, row in temp_df.iterrows():
                            row_text = " ".join([str(x) for x in row.values if pd.notna(x)])
                            if 'Бүтээгдэхүүн' in row_text or 'Өглөө' in row_text:
                                h_idx_tool = i
                                df_tool = pd.read_excel(xls, sheet_name=sheet_name, skiprows=h_idx_tool)
                                break
                        if df_tool is not None:
                            break

                if df_tool is None:
                    st.error("⚠️ Тооллогын файлаас 'Бүтээгдэхүүний нэр' эсвэл 'Өглөө' гэсэн үгтэй толгой олдсонгүй.")
                    st.stop()
                    
                df_tool.columns = df_tool.columns.astype(str).str.strip()
                
                # Багануудыг аюулгүй байдлаар хайж олох
                try:
                    c_code = [c for c in df_tool.columns if '№' in c or 'Код' in c][0]
                    c_name = [c for c in df_tool.columns if 'Бүтээгдэхүүн' in c or 'нэр' in c.lower()][0]
                    c_morn = [c for c in df_tool.columns if 'Өглөө' in c][0]
                    
                    c_delv_list = [c for c in df_tool.columns if 'Хүргэлт' in c]
                    c_delv = c_delv_list[0] if c_delv_list else None
                    
                    c_even_list = [c for c in df_tool.columns if 'Орой' in c]
                    c_even = c_even_list[0] if c_even_list else None
                    
                    c_comm_list = [c for c in df_tool.columns if 'Тайлбар' in c]
                    c_comm = c_comm_list[0] if c_comm_list else None
                except IndexError:
                    st.error("⚠️ Тооллогын хуудас олдсон хэдий ч '№', 'Бүтээгдэхүүний нэр', 'Өглөө' зэрэг багануудын аль нэг нь дутуу байна.")
                    st.stop()

                df_tool = df_tool.dropna(subset=[c_code, c_name])

                # ---------------------------------------------------------
                # 3. ТУЛГАЛТ ХИЙХ
                # ---------------------------------------------------------
                report_list = []
                for _, row in df_tool.iterrows():
                    code = str(row[c_code]).replace('.0', '').strip()
                    name = str(row[c_name]).strip()
                    
                    if not code or code == 'nan' or name == 'nan':
                        continue
                        
                    morn_val = clean_numeric(row[c_morn])
                    delv_val = clean_numeric(row[c_delv]) if c_delv else 0
                    even_val = clean_numeric(row[c_even]) if c_even else 0
                    comment_val = str(row[c_comm]) if c_comm and not pd.isna(row[c_comm]) else ""

                    if latest_date and code in prev_evening_dict:
                        morn_val = prev_evening_dict[code]

                    sys_v = sys_sales.get(code, 0)
                    act_sold = (morn_val + delv_val) - even_val
                    diff = act_sold - sys_v
                    
                    report_list.append({
                        "Код": code,
                        "Барааны нэр": name,
                        "Өглөө": morn_val,
                        "Хүргэлт": delv_val,
                        "Орой": even_val,
                        "Бодит борлуулалт": int(act_sold),
                        "Систем борлуулалт": int(sys_v),
                        "Зөрүү (Илүү/Дутуу)": int(diff),
                        "ПОС Ажилтан": staff_name,
                        "Тайлбар": comment_val
                    })
                    
                st.session_state['temp_report'] = report_list
                st.success("✅ Амжилттай тулгалаа! Доошоо гүйлгэж харна уу.")
                
            except Exception as e:
                st.error(f"Файл уншихад алдаа гарлаа: {e}")

    if 'temp_report' in st.session_state:
        st.divider()
        st.subheader(f"🔍 ТУЛГАЛТЫН ДҮН ({date_str})")
        res_df = pd.DataFrame(st.session_state['temp_report'])
        st.dataframe(res_df.style.applymap(style_diff, subset=['Зөрүү (Илүү/Дутуу)']).format(precision=0), use_container_width=True)
        
        if st.button("🏁 ЭНЭ ӨДРИЙГ АРХИВТ ХАДГАЛАХ", type="primary"):
            history[date_str] = st.session_state['temp_report']
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
        st.info("Архив одоогоор хоосон байна. Тооллого хийж архивт хадгалаарай.")
