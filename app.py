import streamlit as st
import pandas as pd
import re
import io

# 1. Хуудасны үндсэн тохиргоо (Дэлгэцийг өргөнөөр харуулах)
st.set_page_config(page_title="Ухаалаг Аудит & Тулгалт", layout="wide")

# 2. CSS Загварчлал (Theme өөрчлөгдсөн ч текст, хүснэгтийг маш тод харуулна)
st.markdown("""
    <style>
    /* Гарчиг болон дэд бичвэрүүдийг ямар ч үед тод харуулах */
    h1, h2, h3, h4 { color: #1E293B !important; font-weight: 700; }
    .stMarkdown p { color: #334155 !important; font-size: 15px; }
    .sub-title { color: #475569 !important; font-size: 16px; margin-bottom: 20px; }
    
    /* Ногоон амжилттай мэдэгдлийн текстийн өнгө */
    .stAlert p { color: #065F46 !important; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

# 3. Файлын нэрнээс Огноог (Сар.Өдөр) алдаагүй салгах ухаалаг функц
def extract_date_key(file_name):
    # Файлын нэрийг жижиг үсэг рүү шилжүүлж, өргөтгөлийг хасна
    name_clean = file_name.lower().replace(".xlsx", "").replace(".xls", "")
    
    # Нэр дотор байгаа 4 оронтой жилийн тоог (жишээ нь 2026) устгана
    name_clean = re.sub(r'202\d', '', name_clean) 
    
    # Зөвхөн үлдсэн Сар болон Өдөр хоёрыг хайж олно (Жишээ нь: .5.21i -> 5 ба 21)
    match = re.search(r'(\d+)[.-](\d+)', name_clean)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        return f"{month}.{day}" # "5.21" гэсэн формат буцаана
        
    return None

# Session State-ийг эхлүүлэх (Товчлуур дарахад дата устхаас сэргийлнэ)
if "reconciliation_done" not in st.session_state:
    st.session_state.reconciliation_done = False
if "reconciliation_result" not in st.session_state:
    st.session_state.reconciliation_result = None

# Апп-ын нүүр хэсэг
st.title("📊 Ухаалаг Аудит болон Тулгалтын Систем")
st.markdown("<p class='sub-title'>ПОС болон Ажилчдын бодит тооллогын файлуудыг огноогоор нь автоматаар тулгах цонх</p>", unsafe_allow_html=True)

st.divider()

# Файл оруулах 2 багана
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

# 4. Файлууд системд орсон үед боловсруулах логик
if pos_files and audit_files:
    # Огноонуудыг давхардалгүйгээр тоолох
    unique_dates = set([extract_date_key(f.name) for f in pos_files if extract_date_key(f.name)])
    total_days = len(unique_dates)
    
    st.success(f"🎉 Амжилттай! Сарын нийт {total_days} өдрийн файлыг системд уншиж дууслаа. Доорх товчийг дарж тулгана уу.")
    
    # Тулгах улаан товчлуур
    if st.button("🔥 БҮТНИЙН САРААР НЬ АВТОМАТ ТУЛГАХ", type="primary", use_container_width=True):
        
        # ПОС-ын файлуудыг уншиж дата болгон хадгалах
        pos_data = {}
        for f in pos_files:
            date_key = extract_date_key(f.name)
            if date_key:
                try:
                    df = pd.read_excel(f)
                    pos_data[date_key] = df
                except Exception as e:
                    st.error(f"ПОС файл уншихад алдаа гарлаа ({f.name}): {e}")

        # Тооллогын файлуудыг уншиж дата болгон хадгалах
        audit_data = {}
        for f in audit_files:
            date_key = extract_date_key(f.name)
            if date_key:
                try:
                    df = pd.read_excel(f)
                    audit_data[date_key] = df
                except Exception as e:
                    st.error(f"Тооллогын файл уншихад алдаа гарлаа ({f.name}): {e}")

        # 5. ТУЛГАЛТЫН ҮНДСЭН ТОГЛОЛТ (Огноо тааруулж бодох)
        reconciled_summary = []
        all_dates = sorted(list(set(pos_data.keys()) | set(audit_data.keys())), key=lambda x: [int(i) for i in x.split('.')])
        
        for dkey in all_dates:
            # Огноог харуулахдаа '2026.' гэж зөв залгаж харуулна
            display_date = f"2026.{dkey}"
            
            if dkey in pos_data and dkey in audit_data:
                df_pos = pos_data[dkey]
                df_audit = audit_data[dkey]
                
                # --- Баганын нийт дүнгүүдийг бодож гаргах хэсэг ---
                # (Тэмдэглэл: Энд та өөрийн Excel файлын баганын нэрээр сольж болно, одоогоор бүх тоон баганын нийлбэрийг авч байгаа)
                pos_sum = df_pos.select_dtypes(include='number').sum().iloc[0] if not df_pos.empty and len(df_pos.select_dtypes(include='number').columns) > 0 else 0
                audit_sum = df_audit.select_dtypes(include='number').sum().iloc[0] if not df_audit.empty and len(df_audit.select_dtypes(include='number').columns) > 0 else 0
                
                diff = pos_sum - audit_sum
                status = "✅ Таарсан" if diff == 0 else "❌ Зөрсөн"
                
                reconciled_summary.append({
                    "Огноо": display_date,
                    "ПОС Нийт дүн": f"{pos_sum:,.2f}",
                    "Тооллого Нийт дүн": f"{audit_sum:,.2f}",
                    "Зөрүү": f"{diff:,.2f}",
                    "Төлөв": status
                })
            else:
                # Хэрэв аль нэг файл нь огноогоороо олдоогүй бол
                pos_status = "Байгаа" if dkey in pos_data else "Файл дутуу"
                audit_status = "Байгаа" if dkey in audit_data else "Файл дутуу"
                
                reconciled_summary.append({
                    "Огноо": display_date,
                    "ПОС Нийт дүн": pos_status,
                    "Тооллого Нийт дүн": audit_status,
                    "Зөрүү": "-",
                    "Төлөв": "⚠️ Тулгах боломжгүй (Дутуу)"
                })
        
        # Үр дүнгээ хуудас шинэчлэгдэхэд алга болгохгүйн тулд Session State-д хадгална
        st.session_state.reconciliation_result = pd.DataFrame(reconciled_summary)
        st.session_state.reconciliation_done = True

st.divider()

# 6. ТУЛГАЛТЫН ҮР ДҮНГ ХАРУУЛАХ ХЭСЭГ ("УХААЛАГ АУДИТЫН ХЯНАЛТЫН ЦОНХ")
if st.session_state.reconciliation_done:
    st.markdown("## 🔍 УХААЛАГ АУДИТЫН ХЯНАЛТЫН ЦОНХ")
    st.markdown("Сарын файлуудыг огнооны дагуу нэгтгэсэн аудитын дүгнэлт:")
    
    # Үр дүнгийн хүснэгт
    st.dataframe(
        st.session_state.reconciliation_result, 
        use_container_width=True,
        hide_index=True
    )
    
    # Excel файл болгож татаж авах хэсэг
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        st.session_state.reconciliation_result.to_excel(writer, sheet_name='Аудитын Тулгалт', index=False)
    
    st.space = st.markdown("<br>", unsafe_allow_html=True)
    st.download_button(
        label="📥 Тулгалтын тайланг Excel-ээр татах",
        data=buffer.getvalue(),
        file_name="Сарын_Тулгалтын_Тайлан.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="secondary"
    )
else:
    st.info("💡 Дээрх файлуудыг хоёр талдаа бүрэн оруулж 'Автомат тулгах' товчийг дарснаар хяналтын цонх идэвхжинэ.")
