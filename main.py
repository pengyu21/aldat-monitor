import os
import re
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

LIST_URL = "https://www.uplusmvno.com/plan/plan-list"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("텔레그램 설정 누락")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload)
    print("텔레그램 전송 완료")

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # 1. 알닷 요금제 목록 페이지 접속
        page.goto(LIST_URL, wait_until="networkidle")
        page.wait_for_timeout(3000)

        # 팝업 닫기
        try:
            close_btn = page.locator("button").filter(has_text=re.compile(r"닫기|오늘 하루 보지 않기")).first
            if close_btn.is_visible():
                close_btn.click()
                page.wait_for_timeout(500)
        except Exception:
            pass

        # 2. 필터 버튼 클릭 및 옵션 선택
        try:
            filter_btn = page.locator("button, a, div, span").filter(has_text=re.compile(r"^필터$")).first
            if filter_btn.is_visible():
                filter_btn.click()
                page.wait_for_timeout(1000)

                # '10Mbps' 속도 선택
                page.locator("button, label, span, div").filter(has_text=re.compile(r"^10Mbps$")).first.click()
                page.wait_for_timeout(500)

                # '평생할인' 선택
                page.locator("button, label, span, div").filter(has_text=re.compile(r"^평생할인$|^평생$")).first.click()
                page.wait_for_timeout(500)

                # 적용 클릭
                apply_btn = page.locator("button").filter(has_text=re.compile(r"적용|보기")).last
                if apply_btn.is_visible():
                    apply_btn.click()
                    page.wait_for_timeout(2500)
        except Exception as e:
            print("필터 조작 예외:", e)

        # 3. 정렬: '낮은 가격순' 선택
        try:
            sort_btn = page.locator("button, div, span").filter(has_text=re.compile(r"추천 순|추천순|랭킹순|인기순")).first
            if sort_btn.is_visible():
                sort_btn.click()
                page.wait_for_timeout(500)
                page.locator("button, li, span, div").filter(has_text=re.compile(r"^낮은 가격순$|^낮은가격순$")).first.click()
                page.wait_for_timeout(2500)
        except Exception as e:
            print("정렬 조작 예외:", e)

        # 4. 카드 요소 직접 파싱 (각 요금제 카드 및 링크)
        card_elements = page.locator("a[href*='/plan/plan-list/detail']").all()
        valid_plans = []
        excluded_keywords = [
            "개월 할인", "개월할인", "개월특가", "개월간", "개월 이후",
            "카드할인", "카드 결합", "카드제휴", "제휴카드"
        ]

        for card in card_elements:
            try:
                text = card.inner_text()
                flat_card = " ".join(text.split())
                href = card.get_attribute("href") or ""

                # 필수 조건: 10Mbps 또는 180GB 포함, 평생 포함 (150GB 제외)
                if ("10Mbps" not in flat_card and "180GB" not in flat_card) or ("평생" not in flat_card):
                    continue

                # 12개월/24개월 납부 총액 단순 계산기 문구 제거 후 제외 키워드 검사
                check_text = re.sub(r"\d+개월\s*납부\s*총액", "", flat_card)
                if any(k in check_text for k in excluded_keywords):
                    continue

                # 월 요금 추출
                m_price = re.search(r"월\s*([\d,]+)\s*원", flat_card)
                if not m_price:
                    continue
                price = int(m_price.group(1).replace(",", ""))
                if price < 20000:  # 카드 결합 할인 착시 제외
                    continue

                # 통신사명 및 요금제명 추출
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                carrier = lines[0] if len(lines) > 0 else ""
                title = lines[1] if len(lines) > 1 else lines[0]

                # 직통 URL 구성
                full_url = "https://www.uplusmvno.com" + href if href.startswith("/") else href

                valid_plans.append({
                    "carrier": carrier,
                    "title": title,
                    "price": price,
                    "url": full_url
                })
            except Exception:
                continue

        # 가격순 정렬
        valid_plans.sort(key=lambda x: x["price"])

        # 중복 제거
        unique_plans = []
        seen = set()
        for p_item in valid_plans:
            key = (p_item["title"][:10], p_item["price"])
            if key not in seen:
                seen.add(key)
                unique_plans.append(p_item)

        if not unique_plans:
            print("조건에 일치하는 평생 10Mbps 요금제를 찾지 못했습니다.")
            browser.close()
            return

        # TOP 3 구성 및 개별 직통 링크 포함
        top3 = unique_plans[:3]
        medals = ["🥇 1위", "🥈 2위", "🥉 3위"]

        lines = []
        for i, item in enumerate(top3):
            rank = medals[i] if i < len(medals) else f"• {i+1}위"
            c_name = item["carrier"]
            t_name = item["title"]
            p_price = "{:,}".format(item["price"])
            url = item["url"]
            lines.append(
                f"{rank}: <b>[{c_name}] {t_name}</b>\n"
                f"   ├ 월 <b>{p_price}원</b> (평생 / 카드할인 제외)\n"
                f"   └ 👉 <a href='{url}'>요금제 바로가기</a>"
            )

        top3_text = "\n\n".join(lines)
        today = datetime.now().strftime("%Y-%m-%d")

        msg = (
            f"📊 <b>[알닷] 10Mbps 순수 평생 요금제 최저가 TOP 3</b> ({today})\n\n"
            f"{top3_text}"
        )

        send_alert(msg)
        browser.close()

if __name__ == "__main__":
    run()
