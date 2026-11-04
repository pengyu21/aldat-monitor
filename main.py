import os
import re
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

TARGET_URL = "https://www.uplusmvno.com/plan/plan-list/detail?mvnopPpId=CP0000005829&mvnopPtnId=PC0000000026"

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
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    res = requests.post(url, json=payload)
    print("텔레그램 전송 상태:", res.status_code)

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(TARGET_URL, wait_until="networkidle")
        page.wait_for_timeout(3000)

        content = page.content()
        flat_text = " ".join(re.sub(r"<[^>]+>", " ", content).split())

        # 180GB 요금제 이름 및 월 금액 추출 (부가서비스 6,600원 등 제외)
        pattern = r"(\[[^\]]+\][^\*]*?180GB[^\*]*?)\s*월\s*([\d,]+)\s*원"
        matches = re.findall(pattern, flat_text)

        if not matches:
            pattern2 = r"([^\*]{3,50}?180GB[^\*]{0,40}?)\s*월\s*([\d,]+)\s*원"
            matches = re.findall(pattern2, flat_text)

        plans = []
        for name, price_str in matches:
            clean_name = name.replace("현재 보고 있는 요금제", "").replace("이 요금제가 좋은 이유", "").strip()
            try:
                price = int(price_str.replace(",", ""))
                if price >= 10000:
                    plans.append({"name": clean_name, "price": price})
            except ValueError:
                pass

        # 가격순 오름차순 정렬
        plans.sort(key=lambda x: x["price"])

        # 중복 제거
        unique_plans = []
        seen = set()
        for p_item in plans:
            key = (p_item["name"][:15], p_item["price"])
            if key not in seen:
                seen.add(key)
                unique_plans.append(p_item)

        if not unique_plans:
            print("180GB 요금제 데이터를 파싱하지 못했습니다.")
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
            lines.append(f"{rank}: <b>{p_name}</b>\n   └ 월 <b>{p_price}원</b>")

        top3_text = "\n\n".join(lines)
        today = datetime.now().strftime("%Y-%m-%d")

        msg = (
            f"📊 <b>[알닷] 5G 180GB+10Mbps 평생 요금제 TOP 3</b> ({today})\n\n"
            f"{top3_text}\n\n"
            f"🔗 <a href='{TARGET_URL}'>알닷 요금제 상세 바로가기</a>"
        )

        send_alert(msg)
        print("TOP 3 알림 전송 완료!")
        browser.close()

if __name__ == "__main__":
    run()
