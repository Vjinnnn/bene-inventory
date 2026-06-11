import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="Ухаалаг Аудит & Тулгалт", layout="wide")

# CSS загварчлал
st.markdown("""
    <style>
    h1, h2, h3, h4 { color: #1E293B !important; font-weight: 700; }
    .stMarkdown p { color: #334155 !important; font-size: 15px; }
    .stAlert p { color: #065F46 !important; font-weight: 500; }
    div[data-testid="stDataFrame"] { background-color: #ffffff; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

def extract_date_key(file_name):
    name_clean = file_name.lower().replace(".xlsx", "").replace(".xls", "")
    name_clean = re.sub(r'202\d', '', name_clean) 
    match = re.search(r'(\d+)[.-](\d+)', name_clean)
    if match:
        return f"{int(match.group(1))}.{int(match.group(2))}"
    return None

# ПОС файлаас борлуулалтын нийт дүнг унших (Header-ийг алгасаж)
def get_pos_total(file):
    try:
        # Эхлээд толгой хэсгийг хайж олно (7-р мөрөнд 'Item Name' байгаа)
        df = pd.read_excel(file, header=None)
        header_row = 0
        for idx, row in df.iterrows():
            if 'item name' in [str(x).lower() for x in row.values]:
                header_row = idx
                break
                
        # Жинхэнэ датаг унших
        df_clean = pd.read_excel(file, skiprows=header_row)
        
        # 'Ext Price' баганыг олох
        price_col = [c for c in df_clean.columns if 'ext price' in str(c).lower()]
        if price_col:
            # Төгсгөлийн 'Total' мөрийг алгасахын тулд зөвхөн тоон утгуудыг авна
            total_sum = pd.to_numeric(df_clean[price_col[0]], errors='coerce').dropna().sum()
            # Хэрэв Excel өөрөө доороо нийлбэртэй байсан бол хоёр дахин үржигдэхээс сэргийлж 2-т хуваана
            # (Эсвэл 'Total' гэсэн бичигтэй мөрийг хасна)
            df_no_total = df_clean[~df_clean.iloc[:, 1].astype(str).str.lower().str.contains('total|хэмжээ|нийт', na=False)]
            if price_col[0] in df_no_total.columns:
                total_sum = pd.to_numeric(df_no_total[price_col[0]], errors='coerce').sum()
            return float(total_sum)
    except Exception as e:
        st.error(f"ПОС файл уншихад алдаа: {e}")
    return 0.0

# Тооллогын Касс хаалтаас борлуулалтын дүнг унших
def get_audit_total(file):
    try:
        # 'Касс хаалт' хуудсыг унших
        df = pd.read_excel(file, sheet_name='Касс хаалт', header=None)
        
        # 'Борлуулалт' гэсэн үгтэй мөрийг хайж олох
        for idx, row in df.iterrows():
            row_str = [str(x).lower().strip() for x in row.values]
            if 'борлуулалт' in row_str:
                # Тухайн мөрний дараагийн хоосон биш тоон утгыг авна
                for val in row.values:
                    if isinstance(val, (int, float)) and val > 1000: # Борлуулалтын дүн том тоо байна
                        return float(val)
                    try:
                        clean_val = float(str(val).replace(',', '').strip())
                        if clean_val > 1000:
                            return clean_val
                    except:
                        continue
    except Exception as e:
        # Хэрэв хуудасны нэр зөрвөл эхний хуудаснаас хайна
        try:
            df = pd.read_excel(file, header=None)
            for idx, row in df.iterrows():
                if 'борлуулалт' in [str(x).lower() for x in row.values]:
                    for val in row.values:
                        if isinstance(val, (int, float)) and val > 1000:
                            return float(val)
        except:
            pass
    return 0.0

if "reconciliation_done" not in st.session_state:
    st.session_state.reconciliation_done = False
if "reconciliation_result" not in st.session_state:
    st.session_state.reconciliation_result = None

st.title("📊 Ухаалаг Аудит болон Тулгалтын Систем")
st.markdown("<p style='color: #475569;'>ПОС-ын борлуулалтыг Касс хаалтын бодит дүн болон тооллоготой тулгах</p>", unsafe_allow_html=True)

st.divider()

col1, col2 = st.columns(2)
with col1:
    st.subheader("🏪 ПОС-оос татсан файлууд (Item Summary)")
    pos_files = st.file_uploader("ПОС-ын файлуудаа оруулна уу", accept_multiple_files=True, key="pos_uploader")
with col2:
    st.subheader("📝 Касс хаалт & Тооллогын файлууд")
    audit_files = st.file_uploader("Тооллогын файлуудаа оруулна уу", accept_multiple_files=True, key="audit_uploader")

if pos_files and audit_files:
    if st.button("🔥 БҮТНИЙН САРААР НЬ АВТОМАТ ТУЛГАХ", type="primary", use_container_width=True):
        pos_data = {extract_date_key(f.name): f for f in pos_files if extract_date_key(f.name)}
        audit_data = {extract_date_key(f.name): f for f in audit_files if extract_date_key(f.name)}
        
        reconciled_summary = []
        all_dates = sorted(list(set(pos_data.keys()) | set(audit_data.keys())), key=lambda x: [int(i) for i in x.split('.')])
        
        for dkey in all_dates:
            display_date = f"2026.{dkey}"
            
            if dkey in pos_data and dkey in audit_data:
                pos_sum = get_pos_total(pos_data[dkey])
                audit_sum = get_audit_total(audit_data[dkey])
                diff = pos_sum - audit_sum
                
                status = "✅ Таарсан" if abs(diff) < 10 else f"❌ Зөрсөн ({diff:,.0f} ₮)"
                
                reconciled_summary.append({
                    "Огноо": display_date,
                    "ПОС Борлуулалт (Ext Price)": f"{pos_sum:,.0f} ₮",
                    "Касс Хаалт (Борлуулалт)": f"{audit_sum:,.0f} ₮",
                    "Зөрүү дүн": f"{diff:,.0f} ₮",
                    "Төлөв": status
                })
            else:
                reconciled_summary.append({
                    "Огноо": display_date,
                    "ПОС Борлуулалт (Ext Price)": "Байгаа" if dkey in pos_data else "Файл дутуу",
                    "Касс Хаалт (Борлуулалт)": "Байгаа" if dkey in audit_data else "Файл дутуу",
                    "Зөрүү дүн": "-",
                    "Төлөв": "⚠️ Дутуу файлтай"
                })
                
        st.session_state.reconciliation_result = pd.DataFrame(reconciled_summary)
        st.session_state.reconciliation_done = True

if st.session_state.reconciliation_done:
    st.markdown("## 🔍 УХААЛАГ АУДИТЫН ХЯНАЛТЫН ЦОНХ")
    st.dataframe(st.session_state.reconciliation_result, use_container_width=True, hide_index=True)
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        st.session_state.reconciliation_result.to_excel(writer, sheet_name='Аудитын Тулгалт', index=False)
    st.download_button(
        label="📥 Тулгалтын тайланг Excel-ээр татах",
        data=buffer.getvalue(),
        file_name="Сарын_Тулгалтын_Тайлан.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
