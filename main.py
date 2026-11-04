import os
import re
import requests
from playwright.sync_api import sync_playwright

# 감시할 요금제 상세 페이지 (티플러스 5G 180GB+10Mbps 평생)
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

        # 페이지 텍스트 가져오기 (공백 단일화)
        content = page.content()
        flat_text = " ".join(re.sub(r"<[^>]+>", " ", content).split())

        # 오직 '180GB' 요금제와 바로 붙어 있는 월 요금만 정확히 추출 (부가서비스 6,600원 등 제외)
        matches = re.findall(r"180GB.{0,60}?월\s*([\d,]+)\s*원", flat_text)

        prices = []
        for m in matches:
            try:
                val = int(m.replace(",", ""))
                # 정상적인 180GB 요금제 가격대(1만원 이상)만 수집
                if val >= 10000:
                    prices.append(val)
            except ValueError:
                pass

        if not prices:
            print("180GB 요금제 가격을 찾지 못했습니다.")
            browser.close()
            return

        current_lowest = min(prices)
        print(f"인식된 180GB 요금제 목록: {prices}")
        print(f"현재 최저가: {current_lowest:,}원 (기준 최저가: {BASE_PRICE:,}원)")

        # 현재 최저가인 28,000원 '미만'으로 떨어졌을 때만 텔레그램 발송!
        if current_lowest < BASE_PRICE:
            msg = (
                f"🚨 <b>[알닷] 180GB+10Mbps 평생 요금제 최저가 갱신!</b>\n\n"
                f"• 현재 가격: <b>{current_lowest:,}원</b> (기존: {BASE_PRICE:,}원)\n"
                f"• 링크: <a href='{TARGET_URL}'>알닷 요금제 바로가기</a>"
            )
            send_alert(msg)
        else:
            print(f"현재 최저가({current_lowest:,}원) 유지 중이므로 알림을 보내지 않습니다.")

        browser.close()

if __name__ == "__main__":
    run()
