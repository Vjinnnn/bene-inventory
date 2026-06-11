import streamlit as st
import pandas as pd
import re
import io

# Хуудасны тохиргоо (Dark/Light үл хамааран загварлаг харагдуулах)
st.set_page_config(page_title="Ухаалаг Аудит & Тулгалт", layout="wide")

# CSS загварчлал (Цагаан theme дээр ч текстүүдийг тод харагдуулах)
st.markdown("""
    <style>
    .reportview-container { background: #0e1117; }
    h1, h2, h3 { color: #1E293B !important; font-weight: 700; }
    .stAlert p { color: #065F46 !important; font-weight: 500; }
    .sub-title { color: #475569 !important; font-size: 16px; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

# 1. Файлын нэрнээс Огноог (Сар, Өдөр) ялган авах ухаалаг функц
def extract_date_key(file_name):
    # Жишээ нь: "2026.5.26.xlsx" эсвэл "5.26i.xlsx"-ээс 5.26 гэдгийг уншина
    match = re.search(r'(\d+)[.-](\d+)', file_name)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        return f"{month}.{day}" # "5.26" гэсэн формат буцаана
    return None

# Session State-ийг эхлүүлэх (Товчлуур дарахад дата устахаас сэргийлнэ)
if "reconciliation_done" not in st.session_state:
    st.session_state.reconciliation_done = False
if "reconciliation_result" not in st.session_state:
    st.session_state.reconciliation_result = None

st.title("📊 Ухаалаг Аудит болон Тулгалтын Систем")
st.markdown("<p class='sub-title'>ПОС болон Ажилчдын бодит тооллогын файлуудыг огноогоор нь автоматаар тулгах цонх</p>", unsafe_allow_html=True)

st.divider()

# Хоёр багана үүсгэх (Файл оруулах хэсэг)
col1, col2 = st.columns(2)

with col1:
    st.subheader("🏪 ПОС-оос татсан файлууд (Зүүн тал)")
    pos_files = st.file_uploader(
        "ПОС-ын сарын бүх файлаа энд оруулна уу", 
        accept_multiple_files=True, 
        key="pos_uploader"
    )

with col2:
    st.subheader("📝 Ажилчдын бөглөсөн тооллого (Баруун тал)")
    audit_files = st.file_uploader(
        "Тооллогын сарын бүх файлаа энд оруулна уу", 
        accept_multiple_files=True, 
        key="audit_uploader"
    )

st.space = st.empty()

# 2. Файлууд орсон үед боловсруулах логик
if pos_files and audit_files:
    total_days = len(set([extract_date_key(f.name) for f in pos_files if extract_date_key(f.name)]))
    
    # Амжилттай уншсан мэдэгдэл
    st.success(f"🎉 Амжилттай! Сарын нийт {total_days} өдрийн файлыг системд уншиж дууслаа. Доорх товчийг дарж тулгана уу.")
    
    # Тулгах улаан товчлуур
    if st.button("🔥 БҮТНИЙН САРААР НЬ АВТОМАТ ТУЛГАХ", type="primary", use_container_width=True):
        
        # ПОС файлуудыг дата болгож бэлдэх dict
        pos_data = {}
        for f in pos_files:
            date_key = extract_date_key(f.name)
            if date_key:
                try:
                    # Эхний sheet-ийг унших (Та өөрийн кодонд тааруулж өөрчилж болно)
                    df = pd.read_excel(f)
                    pos_data[date_key] = df
                except Exception as e:
                    st.error(f"ПОС файл уншихад алдаа гарлаа ({f.name}): {e}")

        # Тооллогын файлуудыг дата болгож бэлдэх dict
        audit_data = {}
        for f in audit_files:
            date_key = extract_date_key(f.name)
            if date_key:
                try:
                    df = pd.read_excel(f)
                    audit_data[date_key] = df
                except Exception as e:
                    st.error(f"Тооллогын файл уншихад алдаа гарлаа ({f.name}): {e}")

        # 3. АВТОМАТ ТУЛГАЛТЫН ҮНДСЭН ЛОГИК (Огноогоор нь match хийх)
        reconciled_summary = []
        
        # Бүх огнооны жагсаалт гаргах
        all_dates = sorted(list(set(pos_data.keys()) | set(audit_data.keys())))
        
        for dkey in all_dates:
            if dkey in pos_data and dkey in audit_data:
                df_pos = pos_data[dkey]
                df_audit = audit_data[dkey]
                
                # --- ЭНД ТАНЫ ДАТА ДЭЭРХ БОДОЛТЫН ЛОГИК ОРНО ---
                # Жишээ дүрслэл: Файл бүрийн нийт дүнг тулгаж байна гэж үзье
                # (Жишээ нь танай файлын багана 'Нийт' эсвэл 'Дүн' гэсэн нэртэй бол)
                pos_sum = df_pos.select_dtypes(include='number').sum().iloc[0] if not df_pos.empty else 0
                audit_sum = df_audit.select_dtypes(include='number').sum().iloc[0] if not df_audit.empty else 0
                diff = pos_sum - audit_sum
                
                status = "✅ Таарсан" if diff == 0 else "❌ Зөрсөн"
                
                reconciled_summary.append({
                    "Огноо": f"2026.{dkey}",
                    "ПОС Нийт дүн": pos_sum,
                    "Тооллого Нийт дүн": audit_sum,
                    "Зөрүү": diff,
                    "Төлөв": status
                })
            else:
                # Аль нэг талд нь файл дутуу байвал
                reconciled_summary.append({
                    "Огноо": f"2026.{dkey}",
                    "ПОС Нийт дүн": "Файл дутуу" if dkey not in pos_data else "Байгаа",
                    "Тооллого Нийт дүн": "Файл дутуу" if dkey not in audit_data else "Байгаа",
                    "Зөрүү": "-",
                    "Төлөв": "⚠️ Тулгах боломжгүй (Дутуу)"
                })
        
        # Үр дүнгээ Session State-д хадгалах
        st.session_state.reconciliation_result = pd.DataFrame(reconciled_summary)
        st.session_state.reconciliation_done = True

st.divider()

# 4. ТУЛГАЛТЫН ҮР ДҮНГ ХАРУУЛАХ ХЭСЭГ ("УХААЛАГ АУДИТЫН ХЯНАЛТЫН ЦОНХ")
if st.session_state.reconciliation_done:
    st.markdown("## 🔍 УХААЛАГ АУДИТЫН ХЯНАЛТЫН ЦОНХ")
    st.markdown("Сарын файлуудыг огнооны дагуу нэгтгэсэн аудитын дүгнэлт:")
    
    # Хүснэгтээр үр дүнг харуулах
    st.dataframe(
        st.session_state.reconciliation_result, 
        use_container_width=True,
        hide_index=True
    )
    
    # Excel-ээр татаж авах боломж олгох
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        st.session_state.reconciliation_result.to_excel(writer, sheet_name='Аудитын Тулгалт', index=False)
    
    st.download_button(
        label="📥 Тулгалтын тайланг Excel-ээр татах",
        data=buffer.getvalue(),
        file_name="Сарын_Тулгалтын_Тайлан.xlsx",
        mime="application/vnd.ms-excel"
    )
else:
    st.info("💡 Дээрх файлуудыг бүрэн оруулж 'Автомат тулгах' товчийг дарснаар хяналтын цонх идэвхжинэ.")
