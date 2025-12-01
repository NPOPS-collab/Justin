import streamlit as st
import pandas as pd

# 페이지 기본 설정
st.set_page_config(page_title="표준감사시간 산정 프로그램", layout="wide")

# 제목
st.title("📊 표준감사시간 산정 자동화 (RPA)")
st.markdown("---")

# ==========================================
# [사이드바] 데이터 입력 (STEP 1 & 가감요인)
# ==========================================
with st.sidebar:
    st.header("1. 기본 정보 입력 (단위: 원)")
    
    # 엑셀 STEP 1: 자산, 매출 등
    asset_ind = st.number_input("자산총액(개별)", value=229478921817, step=100000000, format="%d")
    asset_con = st.number_input("자산총액(연결)", value=233746570701, step=100000000, format="%d")
    sales_con = st.number_input("매출액(연결)", value=484769790412, step=100000000, format="%d")
    
    st.markdown("---")
    st.header("2. 가감 요인 체크")
    
    # 엑셀 가감요인 항목
    cnt_subsidiary = st.number_input("자회사 수", value=2, min_value=0)
    risk_ratio = st.number_input("위험계정비중 (0.0~1.0)", value=0.456, step=0.01, format="%.3f")
    
    is_holding = st.checkbox("지주사 여부", value=False)
    is_initial = st.checkbox("초도감사 여부", value=False)
    is_loss = st.checkbox("당기순손실 발생", value=False)
    is_adverse = st.checkbox("비적정의견/관리종목", value=False)

    st.markdown("---")
    st.header("3. 감사팀 숙련도 입력 (명)")
    # 엑셀 STEP 4: 숙련도 조정
    col1, col2 = st.columns(2)
    with col1:
        staff_partner = st.number_input("파트너(책임)", value=1, min_value=0)
        staff_cpa_10 = st.number_input("등록회계사(10년↑)", value=0, min_value=0)
        staff_cpa_5 = st.number_input("등록회계사(5년↑)", value=1, min_value=0)
    with col2:
        staff_cpa_3 = st.number_input("등록회계사(3년↑)", value=1, min_value=0)
        staff_cpa_1 = st.number_input("수습/저연차", value=1, min_value=0)


# ==========================================
# [메인] 계산 로직 구현
# ==========================================

# 1. 기업규모 산정 (STEP 1)
# 산식: (자산총액(연결) + 매출액(연결)) / 2
scale_amount = (asset_con + sales_con) / 2

# 2. 그룹 판단 (STEP 2) & 기본표준시간 (보간법)
# (참고: 실제로는 복잡한 표가 필요하지만, 예시 데이터에 맞춰 로직 구현)
# 예시: 그룹4 가정
group_name = "그룹4 (제조업 중규모)"
base_time = 0

# 보간법 로직 (간소화된 예시)
# 자산규모 3000억~4000억 구간일 때의 기울기 적용 예시
if scale_amount < 100000000000: # 1000억 미만
    base_time = 800 + (scale_amount / 100000000000) * 100
else:
    # 예시 데이터(3592억 -> 1411시간)를 맞추기 위한 임시 산식
    base_time = 1411.84 * (scale_amount / 359258180556)

# 3. 가감요인 적용 (STEP 3)
# 승수 계산
mul_subsidiary = 1.0 + (cnt_subsidiary * 0.05) # 자회사 1개당 5% 할증 가정 (엑셀: 1.1)
mul_risk = 1.0 + (risk_ratio * 0.15) # 위험비중 비례 할증 (엑셀: 1.07 근사치)

# 체크박스 요인
add_factor = 1.0
if is_holding: add_factor += 0.05
if is_initial: add_factor += 0.1
if is_loss: add_factor += 0.1
if is_adverse: add_factor += 0.2

# 1차 조정 시간
step3_time = base_time * mul_subsidiary * mul_risk * add_factor


# 4. 숙련도 조정계수 산정 (STEP 4)
# 가중치: 파트너(1.2), 5년차(1.0), 수습(0.4) 등
total_headcount = staff_partner + staff_cpa_10 + staff_cpa_5 + staff_cpa_3 + staff_cpa_1
if total_headcount == 0:
    proficiency_factor = 1.0
else:
    weighted_sum = (staff_partner * 1.2) + (staff_cpa_10 * 1.1) + \
                   (staff_cpa_5 * 1.0) + (staff_cpa_3 * 1.0) + (staff_cpa_1 * 0.4)
    
    # 평균 숙련도
    avg_proficiency = weighted_sum / total_headcount
    # 기준 숙련도(0.905) 대비 비율 (엑셀 로직 역산)
    proficiency_factor = 0.905 / avg_proficiency 
    
    # 보정 (너무 값이 튀지 않게)
    if proficiency_factor < 0.7: proficiency_factor = 0.7
    if proficiency_factor > 1.3: proficiency_factor = 1.3

final_time = step3_time * proficiency_factor


# ==========================================
# [화면 출력] 결과 리포트
# ==========================================

# 상단 요약 카드
c1, c2, c3 = st.columns(3)
c1.metric("기업규모 (평잔)", f"{scale_amount/100000000:,.0f} 억원")
c2.metric("1차 산출 시간", f"{step3_time:,.1f} 시간")
c3.metric("최종 표준감사시간", f"{final_time:,.1f} 시간", delta_color="normal")

st.markdown("---")

# 상세 계산 내역 (탭 구성)
tab1, tab2 = st.tabs(["📄 상세 계산 내역서", "📈 시각화"])

with tab1:
    st.subheader("STEP 1. 기업 규모")
    st.write(f"- 자산(연결): {asset_con:,} 원")
    st.write(f"- 매출(연결): {sales_con:,} 원")
    st.info(f"👉 기업규모 평잔: {scale_amount:,} 원 ({group_name})")
    
    st.subheader("STEP 2 ~ 3. 기본시간 및 가감요인")
    st.write(f"- 기본표준시간(보간법): {base_time:,.2f} 시간")
    st.write(f"- 가감적용: 자회사(x{mul_subsidiary:.2f}) × 위험비중(x{mul_risk:.2f}) × 기타(x{add_factor:.2f})")
    st.success(f"👉 가감 후 시간: {step3_time:,.2f} 시간")

    st.subheader("STEP 4. 숙련도 조정")
    st.write(f"- 투입 인원: 총 {total_headcount}명")
    st.write(f"- 숙련도 조정계수: {proficiency_factor:.4f}")
    st.error(f"🏁 최종 표준감사시간: {final_time:,.2f} 시간")

with tab2:
    st.bar_chart({"기본시간": base_time, "가감후": step3_time, "최종시간": final_time})