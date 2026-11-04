import os
import re
import requests
from playwright.sync_api import sync_playwright

# 감시할 요금제 상세 페이지 (티플러스 180GB+10Mbps 평생 요금제)
TARGET_URL = "https://www.uplusmvno.com/plan/plan-list/detail?mvnopPpId=CP0000005829&mvnopPtnId=PC0000000026"
BASE_PRICE = 28000  # 현재 기준 최저가 (28,000원)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("텔레그램 토큰 또는 Chat ID가 설정되지 않았습니다.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    res = requests.post(url, json=payload)
    print("텔레그램 전송 상태:", res.status_code)

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(TARGET_URL, wait_until="networkidle")
        page.wait_for_timeout(3000)

        # 페이지 텍스트에서 '월 xx,xxx원' 추출
        content = page.content()
        matches = re.findall(r"월\s*([\d,]+)\s*원", content)

        prices = []
        for m in matches:
            try:
                val = int(m.replace(",", ""))
                if 5000 <= val <= 100000:
                    prices.append(val)
            except ValueError:
                pass

        if not prices:
            print("가격 데이터를 가져오지 못했습니다.")
            browser.close()
            return

        current_lowest = min(prices)
        print(f"현재 가격: {current_lowest}원 (기준 최저가: {BASE_PRICE}원)")

        # 28,000원 미만으로 가격이 떨어졌을 때 알림 발생
        if current_lowest < BASE_PRICE:
            msg = (
                f"🚨 <b>[알닷] 180GB+10Mbps 평생 요금제 최저가 갱신!</b>\n\n"
                f"• 현재 가격: <b>{current_lowest:,}원</b> (기존: {BASE_PRICE:,}원)\n"
                f"• 링크: <a href='{TARGET_URL}'>알닷 요금제 바로가기</a>"
            )
            send_alert(msg)
        else:
            print("현재 최저가 유지 중입니다.")

        browser.close()

if __name__ == "__main__":
    run()
