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

        # 2. 필터 버튼 클릭
        try:
            filter_btn = page.locator("button, a, div, span").filter(has_text=re.compile(r"^필터$")).first
            if filter_btn.is_visible():
                filter_btn.click()
                page.wait_for_timeout(1000)

                # 3. '10Mbps' 및 '평생할인' 선택
                page.locator("button, label, span, div").filter(has_text=re.compile(r"^10Mbps$")).first.click()
                page.wait_for_timeout(500)

                page.locator("button, label, span, div").filter(has_text=re.compile(r"^평생할인$|^평생$")).first.click()
                page.wait_for_timeout(500)

                # 4. 필터 적용 클릭
                apply_btn = page.locator("button").filter(has_text=re.compile(r"적용|보기")).last
                if apply_btn.is_visible():
                    apply_btn.click()
                    page.wait_for_timeout(2500)
        except Exception as e:
            print("필터 조작 예외:", e)

        # 5. 정렬: '낮은 가격순' 선택
        try:
            sort_btn = page.locator("button, div, span").filter(has_text=re.compile(r"추천 순|추천순|랭킹순|인기순")).first
            if sort_btn.is_visible():
                sort_btn.click()
                page.wait_for_timeout(500)
                page.locator("button, li, span, div").filter(has_text=re.compile(r"^낮은 가격순$|^낮은가격순$")).first.click()
                page.wait_for_timeout(2500)
        except Exception as e:
            print("정렬 조작 예외:", e)

        # 6. 화면 텍스트 수집 및 정밀 검증
        content = page.content()
        flat_text = " ".join(re.sub(r"<[^>]+>", " ", content).split())

        # 180GB/10Mbps 요금제 블록 매칭
        pattern = r"(\[[^\]]+\][^\*]*?180GB[^\*]*?)\s*월\s*([\d,]+)\s*원"
        matches = re.findall(pattern, flat_text)

        if not matches:
            pattern2 = r"([^\*]{3,60}?180GB[^\*]{0,40}?)\s*월\s*([\d,]+)\s*원"
            matches = re.findall(pattern2, flat_text)

        valid_plans = []
        excluded_keywords = [
            "개월 할인", "개월할인", "개월특가", "개월간", "개월 이후",
            "카드할인", "카드 결합", "카드제휴", "제휴카드"
        ]

        for raw_name, price_str in matches:
            # '12개월 납부 총액', '24개월 납부 총액' 단순 계산기 문구 임시 제거 후 검사
            clean_check = re.sub(r"\d+개월\s*납부\s*총액", "", raw_name)

            # 진짜 기간 한정 할인 요금제 및 카드 결합 요금제 배제
            if any(term in clean_check for term in excluded_keywords):
                continue

            # 요금제 이름 깔끔하게 정제 (부가 설명 문구 분리)
            clean_name = re.split(r"월\s*\d+GB|통화량|문자량|통신기술", raw_name)[0].strip()

            try:
                price = int(price_str.replace(",", ""))
                # 카드 할인 거품(몇천 원대) 및 부가서비스 제외: 순수 통신료 20,000원 이상만 수집
                if price >= 20000:
                    valid_plans.append({"name": clean_name, "price": price})
            except ValueError:
                pass

        # 가격 오름차순 정렬
        valid_plans.sort(key=lambda x: x["price"])

        # 중복 제거
        unique_plans = []
        seen = set()
        for p_item in valid_plans:
            key = (p_item["name"][:10], p_item["price"])
            if key not in seen:
                seen.add(key)
                unique_plans.append(p_item)

        if not unique_plans:
            print("조건에 일치하는 평생 10Mbps 요금제를 찾지 못했습니다.")
            browser.close()
            return

        # TOP 3 구성
        top3 = unique_plans[:3]
        medals = ["🥇 1위", "🥈 2위", "🥉 3위"]

        lines = []
        for i, item in enumerate(top3):
            rank = medals[i] if i < len(medals) else f"• {i+1}위"
            p_name = item["name"]
            p_price = "{:,}".format(item["price"])
            lines.append(f"{rank}: <b>{p_name}</b>\n   └ 월 <b>{p_price}원</b> (평생 / 카드할인 제외)")

        top3_text = "\n\n".join(lines)
        today = datetime.now().strftime("%Y-%m-%d")

        msg = (
            f"📊 <b>[알닷] 10Mbps 순수 평생 요금제 최저가 TOP 3</b> ({today})\n\n"
            f"{top3_text}\n\n"
            f"🔗 <a href='{LIST_URL}'>알닷 요금제 목록 바로가기</a>"
        )

        send_alert(msg)
        browser.close()

if __name__ == "__main__":
    run()
