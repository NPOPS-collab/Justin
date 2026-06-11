import streamlit as st
import pandas as pd
from google import genai
from google.genai import types

# ==========================================
# 페이지 기본 설정 및 상태 관리(Session State) 초기화
# ==========================================
st.set_page_config(page_title="표준감사시간 산정 프로그램", layout="wide")

# AI가 추출한 값을 입력창에 연동하기 위해 세션 상태를 초기화합니다.
if 'input_asset_con' not in st.session_state:
    st.session_state['input_asset_con'] = 233746570701
if 'input_sales_con' not in st.session_state:
    st.session_state['input_sales_con'] = 484769790412
if 'input_cnt_sub' not in st.session_state:
    st.session_state['input_cnt_sub'] = 2

st.title("📊 AI 기반 표준감사시간 산정 자동화 (RPA)")
st.markdown("---")

# ==========================================
# [데이터 정의] 실제 KICPA 조견표 데이터 세팅 (예시: 그룹4 제조업 중규모)
# ==========================================
group4_table = pd.DataFrame([
    {"min_scale": 0, "max_scale": 50000000000, "min_time": 300, "max_time": 500},
    {"min_scale": 50000000000, "max_scale": 100000000000, "min_time": 500, "max_time": 800},
    {"min_scale": 100000000000, "max_scale": 300000000000, "min_time": 800, "max_time": 1300},
    {"min_scale": 300000000000, "max_scale": 500000000000, "min_time": 1300, "max_time": 1700},
    {"min_scale": 500000000000, "max_scale": 1000000000000, "min_time": 1700, "max_time": 2400},
])

# ==========================================
# [사이드바] 파일 업로드 및 데이터 입력
# ==========================================
with st.sidebar:
    st.header("🤖 AI 사업보고서 자동 추출")
    uploaded_file = st.file_uploader("PDF 사업보고서를 업로드하세요", type=["pdf"])
    
    if uploaded_file is not None:
        if st.button("데이터 추출 실행", type="primary"):
            try:
                with st.spinner("AI가 재무제표와 주석을 분석 중입니다..."):
                    # 파일 데이터 읽기
                    file_bytes = uploaded_file.read()
                    
                    # Gemini API 호출
                    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                    prompt = "이 사업보고서에서 '연결재무상태표의 자산총계(연결자산총액)', '연결포괄손익계산서의 수익(연결매출액)', '주석에 기재된 종속기업(자회사) 수'를 찾아줘. 오직 숫자만 콤마(,) 구분의 CSV 형태로 답변해줘. 예시: 233746570701, 484769790412, 2"
                    
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[
                            types.Part.from_bytes(data=file_bytes, mime_type='application/pdf'),
                            prompt
                        ]
                    )
                    
                    # 텍스트 결과 파싱
                    result_text = response.text.strip().replace(" ", "")
                    extracted_asset, extracted_sales, extracted_sub = map(int, result_text.split(','))
                    
                    # 추출된 데이터를 세션 상태에 저장하여 화면 갱신 시 반영되도록 함
                    st.session_state['input_asset_con'] = extracted_asset
                    st.session_state['input_sales_con'] = extracted_sales
                    st.session_state['input_cnt_sub'] = extracted_sub
                    
                    st.success("데이터 추출이 완료되었습니다!")
                    st.rerun() # 화면 새로고침하여 입력창에 값 반영
                    
            except Exception as e:
                st.error(f"추출 중 오류가 발생했습니다. 파일 형식을 확인해주세요. (상세 오류: {e})")
                
    st.markdown("---")
    
    st.header("1. 기본 정보 입력 (단위: 원)")
    asset_ind = st.number_input("자산총액(개별)", value=229478921817, step=100000000, format="%d")
    # 세션 상태에 저장된 값을 value로 사용하여 자동 연동
    asset_con = st.number_input("자산총액(연결)", value=st.session_state['input_asset_con'], step=100000000, format="%d")
    sales_con = st.number_input("매출액(연결)", value=st.session_state['input_sales_con'], step=100000000, format="%d")
    
    st.markdown("---")
    st.header("2. 가감 요인 체크")
    cnt_subsidiary = st.number_input("자회사 수", value=st.session_state['input_cnt_sub'], min_value=0)
    risk_ratio = st.number_input("위험계정비중 (0.0~1.0)", value=0.456, step=0.01, format="%.3f")
    
    is_holding = st.checkbox("지주사 여부", value=False)
    is_initial = st.checkbox("초도감사 여부", value=False)
    is_loss = st.checkbox("당기순손실 발생", value=False)
    is_adverse = st.checkbox("비적정의견/관리종목", value=False)

    st.markdown("---")
    st.header("3. 감사팀 숙련도 입력 (명)")
    col1, col2 = st.columns(2)
    with col1:
        staff_partner = st.number_input("파트너(책임)", value=1, min_value=0)
        staff_cpa_10 = st.number_input("등록회계사(10년↑)", value=0, min_value=0)
        staff_cpa_5 = st.number_input("등록회계사(5년↑)", value=1, min_value=0)
    with col2:
        staff_cpa_3 = st.number_input("등록회계사(3년↑)", value=1, min_value=0)
        staff_cpa_1 = st.number_input("수습/저연차", value=1, min_value=0)

# ==========================================
# [메인] 계산 로직 고도화
# ==========================================

# 1. 기업규모 산정 (STEP 1)
scale_amount = (asset_con + sales_con) / 2

# 2. 정밀 보간법 적용 (STEP 2)
group_name = "그룹4 (제조업 중규모)"
base_time = 0.0
matched_bracket = None

# 입력된 규모가 속한 구간 찾기
for idx, row in group4_table.iterrows():
    if row['min_scale'] <= scale_amount < row['max_scale']:
        matched_bracket = row
        break

if matched_bracket is not None:
    # 선형 보간법 공식 적용
    x = scale_amount
    x1, x2 = matched_bracket['min_scale'], matched_bracket['max_scale']
    y1, y2 = matched_bracket['min_time'], matched_bracket['max_time']
    base_time = y1 + ((x - x1) * (y2 - y1) / (x2 - x1))
else:
    # 범위를 초과하는 경우 최댓값 적용 등 예외 처리
    base_time = group4_table['max_time'].iloc[-1]

# 3. 가감요인 적용 (STEP 3)
mul_subsidiary = 1.0 + (cnt_subsidiary * 0.05)
mul_risk = 1.0 + (risk_ratio * 0.15)

add_factor = 1.0
if is_holding: add_factor += 0.05
if is_initial: add_factor += 0.1
if is_loss: add_factor += 0.1
if is_adverse: add_factor += 0.2

step3_time = base_time * mul_subsidiary * mul_risk * add_factor

# 4. 숙련도 조정계수 산정 (STEP 4)
total_headcount = staff_partner + staff_cpa_10 + staff_cpa_5 + staff_cpa_3 + staff_cpa_1
if total_headcount == 0:
    proficiency_factor = 1.0
else:
    weighted_sum = (staff_partner * 1.2) + (staff_cpa_10 * 1.1) + \
                   (staff_cpa_5 * 1.0) + (staff_cpa_3 * 1.0) + (staff_cpa_1 * 0.4)
    avg_proficiency = weighted_sum / total_headcount
    proficiency_factor = 0.905 / avg_proficiency 
    
    if proficiency_factor < 0.7: proficiency_factor = 0.7
    if proficiency_factor > 1.3: proficiency_factor = 1.3

final_time = step3_time * proficiency_factor

# ==========================================
# [화면 출력] 결과 리포트
# ==========================================
c1, c2, c3 = st.columns(3)
c1.metric("기업규모 (평잔)", f"{scale_amount/100000000:,.1f} 억원")
c2.metric("보간법 기준시간", f"{base_time:,.1f} 시간")
c3.metric("최종 표준감사시간", f"{final_time:,.1f} 시간")

st.markdown("---")

tab1, tab2 = st.tabs(["📄 상세 계산 내역서", "📈 시각화"])

with tab1:
    st.subheader("STEP 1. 기업 규모")
    st.write(f"- 자산(연결): {asset_con:,} 원 / 매출(연결): {sales_con:,} 원")
    st.info(f"👉 기업규모 평잔: {scale_amount:,} 원 ({group_name})")
    
    st.subheader("STEP 2. 구간 데이터 및 선형 보간 결과")
    if matched_bracket is not None:
        st.write(f"- 소속 구간: {matched_bracket['min_scale']/100000000:,.0f}억원 ~ {matched_bracket['max_scale']/100000000:,.0f}억원")
        st.write(f"- 구간 내 시간 정의: {matched_bracket['min_time']:,}시간 ~ {matched_bracket['max_time']:,}시간")
    st.success(f"👉 산출된 기본표준시간: {base_time:,.2f} 시간")

    st.subheader("STEP 3 ~ 4. 가감 및 숙련도 최종 산정")
    st.write(f"- 가감 적용 후 시간: {step3_time:,.2f} 시간")
    st.write(f"- 숙련도 보정 계수: {proficiency_factor:.4f} (총 {total_headcount}명 투입)")
    st.error(f"🏁 최종 표준감사시간: {final_time:,.2f} 시간")

with tab2:
    st.bar_chart({"기본시간(보간)": base_time, "가감후": step3_time, "최종시간": final_time})
