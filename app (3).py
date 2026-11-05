"""저축 씨앗 | Streamlit 교육용 목표 저축 앱
실행: pip install -r requirements.txt && streamlit run app.py
배포: GitHub에 이 파일과 requirements.txt 업로드 → Streamlit Community Cloud
→ 저장소와 app.py 선택 → Deploy. 배포 URL을 앱의 QR 탭에 입력합니다.
선택: Cloud의 Settings > Secrets에서 PUBLIC_APP_URL = "https://....streamlit.app"
을 지정하면 QR 주소를 자동 입력합니다. API 키/계좌/로그인 정보는 필요 없습니다.
중요: 기록은 세션 메모리에만 존재합니다. 새로고침·재접속·서버 재시작 시
사라질 수 있으므로 JSON 백업을 내려받으세요. QR은 앱 주소만 공유하며,
개인 기록은 공유하거나 동기화하지 않습니다. 실제 금융 거래는 하지 않습니다.
"""
from __future__ import annotations

import calendar
import html
import io
import json
import uuid
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

import pandas as pd
import qrcode
import streamlit as st

MAX_MONEY = 1_000_000_000
LESSONS = [
    {"id": "goal", "title": "1. 목표를 숫자로 바꾸기", "body": "'돈을 모으자' 대신 '90일 안에 자전거 비용 30만 원 모으기'처럼 금액과 기한을 정해 보세요. 필요한 하루 저축액은 남은 금액을 남은 일수로 나누면 됩니다. 빠듯하면 기간을 늘리거나 목표를 조정할 수 있어요.", "question": "실행 계획을 세우기 가장 좋은 목표는?", "options": ["언젠가 많이 모으기", "90일 안에 자전거 비용 30만 원 모으기", "친구보다 많이 모으기"], "answer": 1, "explain": "금액·기한·목적이 구체적이면 행동으로 옮기고 진행 상황을 확인하기 쉬워요."},
    {"id": "first", "title": "2. 선저축과 예산", "body": "선저축은 수입이 들어오면 계획한 금액을 먼저 따로 두고 나머지로 소비하는 방법입니다. 식비·교통비 등 꼭 필요한 지출을 먼저 확인하고, 지속 가능한 금액을 정하세요. 특정 저축 비율이 모든 사람에게 정답인 것은 아니에요.", "question": "수입이 불규칙할 때 더 합리적인 방법은?", "options": ["생활비를 무시하고 무조건 절반 저축", "필수 지출과 수입 변동을 고려해 저축액 조정", "저축하려고 매달 대출받기"], "answer": 1, "explain": "무리해서 시작하기보다 실제 생활에 맞는 금액으로 꾸준히 이어가는 것이 중요해요."},
    {"id": "needs", "title": "3. 필요와 욕구, 기회비용", "body": "필요는 생활에 꼭 필요한 지출, 욕구는 있으면 좋지만 미룰 수 있는 지출입니다. 상황에 따라 구분은 달라져요. 기회비용은 어떤 선택을 하느라 포기한 가장 가치 있는 다른 선택입니다. 소비를 모두 나쁘게 보기보다 나의 우선순위를 생각해 보세요.", "question": "간식 5천 원 대신 저축하기로 했다면 포기한 간식의 만족은?", "options": ["공짜 이자", "기회비용", "원금 보장"], "answer": 1, "explain": "선택에는 포기하는 가치가 있어요. 소비와 저축의 장단점을 함께 비교해 보세요."},
    {"id": "interest", "title": "4. 단리와 복리", "body": "단리는 원금에만 이자가 붙고, 복리는 이전 이자를 포함한 잔액에 이자가 붙습니다. 같은 조건이라면 복리는 시간이 길수록 누적 효과가 커져요. 실제 상품은 세금·수수료·납입 시점·계약상 이자 계산 방식에 따라 결과가 달라집니다.", "question": "복리를 가장 잘 설명하는 것은?", "options": ["원금에만 이자가 붙는다", "항상 원금의 두 배가 된다", "이전 이자를 포함한 잔액에도 이자가 붙는다"], "answer": 2, "explain": "복리는 이자에도 이자가 붙는 구조입니다. 높은 수익이 보장된다는 의미는 아니에요."},
    {"id": "buffer", "title": "5. 비상금과 안전한 습관", "body": "예상치 못한 지출에 대비하는 비상금은 목표 저축과 별도로 생각할 수 있어요. 쉽게 꺼낼 수 있는지, 손실 위험이 있는지 확인하세요. '고수익 보장'이나 계좌·비밀번호를 요구하는 낯선 링크는 경계하세요. 이 앱에는 계좌번호 등 민감정보를 적지 마세요.", "question": "비상금의 중요한 조건은?", "options": ["필요할 때 쉽게 쓸 수 있는 유동성과 안전성", "언제나 가장 높은 수익률", "친구에게 비밀번호 공유"], "answer": 0, "explain": "비상금은 급할 때 쓸 수 있어야 해요. 필요한 규모는 생활비와 소득 안정성에 따라 달라집니다."},
]
MISSIONS = {
    "pause": ("소비 전 10분 멈추기", "사고 싶은 물건 하나를 고르고, 필요한 이유와 미뤄도 되는 이유를 생각해 보세요."),
    "budget": ("오늘의 필수 지출 점검", "오늘 꼭 필요한 지출 하나와 줄일 수 있는 지출 하나를 구분해 보세요."),
    "plan": ("다음 저축 계획 세우기", "언제, 얼마를 저축할지 구체적으로 정해 보세요. 실천 전에는 입금으로 기록하지 마세요."),
}


def fresh_data():
    return {"version": 1, "goal": None, "entries": [], "learned": [], "missions": {}}


def money(value):
    return f"{value:,.0f}원"


def balance(entries):
    return sum(e["amount"] if e["kind"] == "저축" else -e["amount"] for e in entries)


def valid_url(raw):
    try:
        p = urlsplit(raw.strip())
        return bool(p.scheme == "https" and p.hostname and "." in p.hostname and not p.username and not p.password and not p.fragment and not p.query)
    except ValueError:
        return False


def simulate(initial, monthly, annual_rate, months):
    """월말 납입, 연 명목금리/12, 세전. 단리: 누적 납입원금에만 이자."""
    principal = float(initial)
    simple = float(initial)
    compound = float(initial)
    rows = [{"개월": 0, "납입 원금": principal, "단리 잔액": simple, "복리 잔액": compound}]
    r = annual_rate / 100 / 12
    for month in range(1, months + 1):
        simple += principal * r + monthly
        compound = compound * (1 + r) + monthly
        principal += monthly
        rows.append({"개월": month, "납입 원금": principal, "단리 잔액": simple, "복리 잔액": compound})
    return rows


def validate_backup(obj):
    """엄격하게 검증하고 허용한 필드만 새 객체로 복원합니다."""
    if not isinstance(obj, dict) or type(obj.get("version")) is not int or obj["version"] != 1:
        raise ValueError("지원하는 버전의 JSON 백업이 아닙니다.")
    out = fresh_data()
    g = obj.get("goal")
    if g is not None:
        if not isinstance(g, dict) or not isinstance(g.get("name"), str) or not 1 <= len(g["name"].strip()) <= 60:
            raise ValueError("목표 이름을 확인하세요.")
        if type(g.get("target")) is not int or not 1 <= g["target"] <= MAX_MONEY:
            raise ValueError("목표 금액을 확인하세요.")
        due = date.fromisoformat(g["due"])
        out["goal"] = {"name": g["name"].strip(), "target": g["target"], "due": due.isoformat()}
    entries = obj.get("entries", [])
    if not isinstance(entries, list) or len(entries) > 3000:
        raise ValueError("거래 내역은 최대 3,000건입니다.")
    ids = set()
    for e in entries:
        if not isinstance(e, dict) or e.get("kind") not in ("저축", "사용"):
            raise ValueError("거래 종류가 올바르지 않습니다.")
        amount = e.get("amount")
        if type(amount) is not int or not 1 <= amount <= MAX_MONEY:
            raise ValueError("거래 금액이 올바르지 않습니다.")
        day = date.fromisoformat(e["date"])
        if day > date.today():
            raise ValueError("미래 날짜의 거래는 복원할 수 없습니다.")
        note = e.get("note", "")
        if not isinstance(note, str) or len(note) > 120:
            raise ValueError("메모는 120자 이내여야 합니다.")
        eid = e.get("id")
        if not isinstance(eid, str) or not 1 <= len(eid) <= 64 or eid in ids:
            raise ValueError("거래 ID가 잘못되었거나 중복되었습니다.")
        ids.add(eid)
        out["entries"].append({"id": eid, "date": day.isoformat(), "kind": e["kind"], "amount": amount, "note": note})
    if balance(out["entries"]) < 0:
        raise ValueError("전체 잔액은 음수가 될 수 없습니다.")
    learned = obj.get("learned", [])
    allowed = {x["id"] for x in LESSONS}
    if not isinstance(learned, list) or any(not isinstance(x, str) or x not in allowed for x in learned):
        raise ValueError("학습 기록이 올바르지 않습니다.")
    out["learned"] = sorted(set(learned))
    missions = obj.get("missions", {})
    if not isinstance(missions, dict) or len(missions) > 3660:
        raise ValueError("미션 기록이 올바르지 않습니다.")
    for day, values in missions.items():
        parsed = date.fromisoformat(day)
        if parsed > date.today() or not isinstance(values, list) or any(not isinstance(x, str) or x not in MISSIONS for x in values):
            raise ValueError("미션 날짜 또는 내용이 올바르지 않습니다.")
        out["missions"][parsed.isoformat()] = sorted(set(values))
    return out


def main():
    st.set_page_config(page_title="저축 씨앗 · 배우며 모으기", page_icon="🌱", layout="centered")
    st.markdown("""<style>
    .stApp {background:linear-gradient(180deg,#f0fdf4 0%,#ffffff 380px);color:#16352b;}
    h1,h2,h3 {color:#14532d !important;}
    .block-container {max-width:1000px;padding-top:2rem;padding-bottom:3rem;}
    div[data-testid="stMetric"] {background:#ffffff;border:1px solid #bbdfc8;border-radius:16px;padding:16px;}
    .seed-hero {background:#14532d;color:#fff;padding:24px;border-radius:22px;margin-bottom:20px;}
    .seed-hero h1 {color:white !important;margin:0;}
    button[kind="primary"] {background:#166534;border-color:#166534;}
    </style>""", unsafe_allow_html=True)
    if "seed_data" not in st.session_state:
        st.session_state.seed_data = fresh_data()
    data = st.session_state.seed_data
    today = date.today()
    st.markdown('<div class="seed-hero"><h1>🌱 저축 씨앗</h1><p>목표를 향해 조금씩, 저축의 원리도 차곡차곡.</p></div>', unsafe_allow_html=True)
    st.caption("교육용 기록 앱 · 실제 입출금/은행 연결 없음 · 학습 점수는 가상이며 현금 가치가 없습니다.")
    st.warning("기록은 현재 접속 세션에만 보관됩니다. 새로고침·재접속 시 사라질 수 있으니 ‘백업’ 탭에서 파일을 저장하세요.")
    if st.session_state.pop("flash", None):
        st.success("변경 내용을 반영했습니다.")
    tabs = st.tabs(["🎯 내 목표", "📝 저축 기록", "📚 배움터", "🧮 이자 실험", "📱 QR · 백업"])

    with tabs[0]:
        g = data["goal"]
        if g:
            current = balance(data["entries"])
            remaining = max(g["target"] - current, 0)
            due = date.fromisoformat(g["due"])
            days = (due - today).days
            st.subheader(g["name"])
            c1, c2 = st.columns(2)
            c1.metric("현재 기록 잔액", money(current))
            c2.metric("목표 금액", money(g["target"]))
            st.progress(min(current / g["target"], 1.0), text=f"달성률 {current / g['target'] * 100:.1f}%")
            st.write(f"목표일: {due.isoformat()} · 남은 금액: {money(remaining)}")
            if remaining == 0:
                st.success("🎉 목표 달성! 어떤 습관이 도움이 되었는지 돌아보세요. 목표를 바꿔도 기존 기록은 유지됩니다.")
            elif days >= 0:
                divisor = days + 1
                daily = (remaining + divisor - 1) // divisor
                st.info(f"오늘을 포함한 {divisor}일 동안 하루 약 {money(daily)}씩 모으면 도달할 수 있어요. 이자는 제외한 계획입니다.")
            else:
                st.info("목표일이 지났어요. 실패가 아니라 계획을 조정할 기회입니다. 아래에서 날짜나 금액을 바꿔 보세요.")
            if data["entries"]:
                df = pd.DataFrame(data["entries"])
                df["변동"] = df.apply(lambda r: r["amount"] if r["kind"] == "저축" else -r["amount"], axis=1)
                trend = df.groupby("date", sort=True)["변동"].sum().cumsum().rename("기록 잔액")
                st.line_chart(trend, color="#15803d")
                st.caption("거래일별 누적 잔액입니다. 과거 날짜 입력에 따라 중간 시점 잔액이 음수가 될 수 있습니다.")
        else:
            st.info("첫 씨앗을 심어 보세요. 이루고 싶은 목표와 금액, 날짜를 정하면 시작됩니다.")
        with st.expander("목표 설정 / 변경", expanded=g is None):
            with st.form("goal_form"):
                name = st.text_input("목표 이름", value=g["name"] if g else "나만의 여행 경비", max_chars=60)
                target = st.number_input("목표 금액 (원)", min_value=1, max_value=MAX_MONEY, value=g["target"] if g else 300000, step=1000)
                default_due = max(date.fromisoformat(g["due"]), today) if g else today + timedelta(days=90)
                due_new = st.date_input("목표 날짜", value=default_due, min_value=today, max_value=date(today.year + 20, 12, 31))
                st.caption("목표 변경은 잔액과 거래 내역을 초기화하지 않습니다.")
                if st.form_submit_button("목표 저장", type="primary"):
                    if not name.strip():
                        st.error("목표 이름을 입력하세요.")
                    else:
                        data["goal"] = {"name": name.strip(), "target": int(target), "due": due_new.isoformat()}
                        st.session_state.flash = True
                        st.rerun()
        st.divider()
        st.subheader("오늘의 실천 미션")
        st.caption("실제로 실천한 것만 체크하세요. 미션 완료는 잔액을 늘리지 않습니다.")
        completed = data["missions"].get(today.isoformat(), [])
        for mid, (title, desc) in MISSIONS.items():
            checked = st.checkbox(title, value=mid in completed, key=f"mission_{today}_{mid}")
            st.caption(desc)
            if checked and mid not in completed:
                completed.append(mid)
            elif not checked and mid in completed:
                completed.remove(mid)
        data["missions"][today.isoformat()] = completed
        points = len(data["learned"]) * 20 + sum(len(v) for v in data["missions"].values()) * 5
        st.write(f"✨ 학습 포인트 **{points}점** · 퀴즈 최초 정답 +20점 / 실천 미션 하루 각 +5점")

    with tabs[1]:
        st.subheader("실제로 모은 돈을 기록해요")
        st.caption("‘저축’은 잔액 증가, ‘사용’은 잔액 감소입니다. 이 앱은 돈을 이체하지 않습니다.")
        with st.form("entry_form", clear_on_submit=True):
            kind = st.radio("기록 종류", ["저축", "사용"], horizontal=True)
            amount = st.number_input("금액 (원)", min_value=1, max_value=MAX_MONEY, value=1000, step=1000)
            entry_date = st.date_input("기록 날짜", value=today, min_value=date(2000, 1, 1), max_value=today)
            note = st.text_input("짧은 메모 (민감정보 입력 금지)", max_chars=120, placeholder="예: 간식 대신 모은 돈")
            if st.form_submit_button("기록 추가", type="primary"):
                if len(data["entries"]) >= 3000:
                    st.error("최대 3,000건까지 기록할 수 있습니다. 백업 후 정리하세요.")
                elif kind == "사용" and amount > balance(data["entries"]):
                    st.error("현재 잔액보다 많이 사용할 수 없습니다.")
                else:
                    data["entries"].append({"id": uuid.uuid4().hex, "date": entry_date.isoformat(), "kind": kind, "amount": int(amount), "note": note.strip()})
                    st.session_state.flash = True
                    st.rerun()
        if data["entries"]:
            st.metric("현재 기록 잔액", money(balance(data["entries"])))
            frame = pd.DataFrame(data["entries"]).sort_values("date", ascending=False, kind="stable")
            view = frame.rename(columns={"date": "날짜", "kind": "종류", "amount": "금액(원)", "note": "메모"})
            st.dataframe(view[["날짜", "종류", "금액(원)", "메모"]], hide_index=True, use_container_width=True)
            with st.expander("잘못 입력한 기록 삭제"):
                choices = {e["id"]: f"{e['date']} · {e['kind']} {money(e['amount'])} · {e['note']}" for e in data["entries"]}
                selected = st.selectbox("삭제할 기록", list(choices), format_func=lambda x: choices[x])
                confirm = st.checkbox("선택한 기록을 삭제합니다.")
                if st.button("선택 기록 삭제", disabled=not confirm):
                    rest = [e for e in data["entries"] if e["id"] != selected]
                    if balance(rest) < 0:
                        st.error("삭제하면 잔액이 음수가 됩니다. 관련 ‘사용’ 기록부터 정리하세요.")
                    else:
                        data["entries"] = rest
                        st.session_state.flash = True
                        st.rerun()
        else:
            st.info("아직 기록이 없습니다. 적은 금액부터 시작해도 괜찮아요.")

    with tabs[2]:
        st.subheader("알고 모으면 습관이 돼요")
        st.progress(len(data["learned"]) / len(LESSONS), text=f"학습 완료 {len(data['learned'])}/{len(LESSONS)}")
        for lesson in LESSONS:
            passed = lesson["id"] in data["learned"]
            with st.expander(("✅ " if passed else "📖 ") + lesson["title"]):
                st.write(lesson["body"])
                with st.form("quiz_" + lesson["id"]):
                    answer = st.radio(lesson["question"], range(len(lesson["options"])), format_func=lambda i, opts=lesson["options"]: opts[i], index=None)
                    if st.form_submit_button("정답 확인"):
                        if answer is None:
                            st.warning("답을 먼저 골라 주세요.")
                        elif answer == lesson["answer"]:
                            if lesson["id"] not in data["learned"]:
                                data["learned"].append(lesson["id"])
                                st.session_state["quiz_feedback"] = lesson["explain"]
                                st.rerun()
                            st.success("정답! " + lesson["explain"] + " (이미 완료한 퀴즈는 점수가 중복 지급되지 않습니다.)")
                        else:
                            st.info("다시 생각해 보세요. " + lesson["explain"])
        feedback = st.session_state.pop("quiz_feedback", None)
        if feedback:
            st.success("정답! 학습 포인트 +20점 · " + feedback)

    with tabs[3]:
        st.subheader("같은 저축, 다른 시간의 힘")
        st.write("월말에 같은 금액을 넣는다고 가정하고 원금·단리·복리를 비교해 보세요.")
        initial = st.number_input("처음 넣는 돈 (원)", 0, 100000000, 100000, step=10000)
        monthly = st.number_input("매월 말 저축액 (원)", 0, 10000000, 30000, step=10000)
        rate = st.slider("가정한 연 명목금리 (%)", 0.0, 15.0, 3.0, 0.1)
        months = st.slider("기간 (개월)", 1, 120, 36)
        rows = simulate(initial, monthly, rate, months)
        end = rows[-1]
        c1, c2 = st.columns(2)
        c1.metric("총 납입 원금", money(end["납입 원금"]))
        c2.metric("복리 예상 잔액", money(end["복리 잔액"]), delta=f"이자 {money(end['복리 잔액'] - end['납입 원금'])}")
        st.line_chart(pd.DataFrame(rows).set_index("개월"), color=["#64748b", "#d97706", "#15803d"])
        st.caption("교육용 가정: 금리는 기간 내 고정, 월 이율=연 명목금리÷12, 매월 이자 계산 후 월말 납입. 단리는 누적 납입원금에만, 복리는 직전 잔액에 이자를 계산합니다. 세금·수수료·물가·실제 상품의 일수 계산은 제외합니다. 마지막 월말 납입금에는 해당 월 이자가 붙지 않습니다. 금리는 실제 상품 제안이나 수익 보장이 아니며 기록 잔액에 반영되지 않습니다.")
        st.info("실험 질문: 기간을 두 배로 바꾸면 이자는 정확히 두 배일까요? 금리를 0%로 바꾸면 세 선은 어떻게 될까요?")

    with tabs[4]:
        st.subheader("QR로 내 휴대폰에서 열기")
        st.write("GitHub에 코드를 올리는 것만으로는 실행되지 않습니다. Streamlit Community Cloud에 배포한 뒤, 공개 HTTPS 주소를 입력하세요.")
        try:
            default_url = str(st.secrets.get("PUBLIC_APP_URL", ""))
        except Exception:
            default_url = ""
        public_url = st.text_input("배포된 앱의 HTTPS 주소", value=default_url, placeholder="https://내앱.streamlit.app")
        if public_url:
            if valid_url(public_url):
                qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=4)
                qr.add_data(public_url.strip())
                qr.make(fit=True)
                buffer = io.BytesIO()
                qr.make_image(fill_color="#14532d", back_color="white").save(buffer, format="PNG")
                st.image(buffer.getvalue(), width=240, caption="카메라로 스캔하면 앱 접속 화면이 열립니다.")
                st.download_button("QR 이미지 다운로드", buffer.getvalue(), "saving-seed-qr.png", "image/png")
            else:
                st.error("쿼리·프래그먼트·로그인 정보가 없는 공개 HTTPS 주소를 입력하세요.")
        st.caption("QR에는 입력한 앱 주소만 들어갑니다. 개인 저축 기록은 담기지 않습니다. 다른 기기에서는 JSON 백업을 직접 복원해야 합니다. 비공개 앱은 별도 접근 권한이 필요할 수 있습니다.")
        st.divider()
        st.subheader("기록 백업 · 복원")
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        st.download_button("💾 전체 기록 JSON 백업", payload, f"saving-seed-{today}.json", "application/json", type="primary")
        st.caption("백업에는 목표·거래·메모·학습 기록이 포함됩니다. 개인 파일로 안전하게 보관하세요.")
        upload = st.file_uploader("백업 JSON 불러오기 (최대 2MB)", type=["json"])
        replace = st.checkbox("복원 시 현재 세션의 모든 기록이 백업 내용으로 교체됨을 확인합니다.")
        if st.button("백업 복원", disabled=upload is None or not replace):
            try:
                if upload.size > 2 * 1024 * 1024:
                    raise ValueError("파일 크기는 2MB 이하여야 합니다.")
                restored = validate_backup(json.loads(upload.getvalue().decode("utf-8-sig")))
                st.session_state.seed_data = restored
                for key in list(st.session_state):
                    if key.startswith("mission_"):
                        del st.session_state[key]
                st.session_state.flash = True
                st.rerun()
            except (ValueError, TypeError, KeyError, UnicodeError, OverflowError, RecursionError):
                st.error("백업 형식 또는 값이 올바르지 않습니다. 이 앱에서 내려받은 원본 JSON을 사용하세요. 현재 기록은 변경하지 않았습니다.")
        with st.expander("처음부터 다시 시작"):
            reset = st.checkbox("현재 세션의 목표·거래·학습 기록을 모두 삭제합니다.")
            if st.button("모든 기록 초기화", disabled=not reset):
                st.session_state.clear()
                st.rerun()
        with st.expander("GitHub → Streamlit 배포 안내"):
            st.markdown("1. GitHub 저장소에 **app.py**와 **requirements.txt**를 같은 폴더에 올립니다.\n2. Streamlit Community Cloud에서 GitHub 계정을 연결하고 **Create app**을 선택합니다.\n3. 저장소·브랜치를 고르고 Main file path를 **app.py**로 지정해 배포합니다.\n4. 배포된 HTTPS 주소를 위 입력란에 붙여 넣고 QR 이미지를 받습니다.\n5. 선택 사항: 배포 설정의 Secrets에 `PUBLIC_APP_URL = \"https://배포주소.streamlit.app\"`를 추가하면 주소가 자동 입력됩니다.")
            st.caption("로컬 실행: pip install -r requirements.txt → streamlit run app.py. GitHub Pages는 Python 서버를 실행하지 않으므로 이 앱의 실행 호스팅으로 사용할 수 없습니다.")
    st.divider()
    st.caption("🌱 작은 습관이 큰 목표를 만듭니다. 금액을 남과 비교하지 말고 나의 상황에 맞춰 계획하세요.")


if __name__ == "__main__":
    main()
