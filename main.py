import os
import re
import smtplib
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright

LIST_URL = "https://www.uplusmvno.com/plan/plan-list"
USER_EMAIL = "sarangfeel2@gmail.com"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload)
        print("텔레그램 전송 성공")
    except Exception as e:
        print("텔레그램 전송 실패:", e)

def send_email(subject, html_content):
    if not GMAIL_APP_PASSWORD:
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = USER_EMAIL
        msg["To"] = USER_EMAIL
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(USER_EMAIL, GMAIL_APP_PASSWORD)
            server.sendmail(USER_EMAIL, USER_EMAIL, msg.as_string())
        print("이메일 전송 성공")
    except Exception as e:
        print("이메일 전송 실패:", e)

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # 알닷 요금제 목록 페이지 접속
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

        content = page.content()
        flat_text = " ".join(re.sub(r"<[^>]+>", " ", content).split())

        # 1. [10Mbps] 평생 요금제 타깃 (실시간 가격 크롤링 및 안전값)
        targets_10mbps = [
            {"carrier": "시월모바일", "title": "평생5G 통화기본 180GB+", "keywords": ["시월", "통화기본180GB", "통화기본 180GB"], "default_price": 27900},
            {"carrier": "티플러스", "title": "5G 티플온 180GB+_평생", "keywords": ["티플", "티플온 180GB", "티플온180GB"], "default_price": 28000},
            {"carrier": "슈가모바일", "title": "5G 슈가통화마음대로 180GB++_평생", "keywords": ["슈가", "슈가통화마음대로"], "default_price": 29500}
        ]

        # 2. [5Mbps] 평생 요금제 타깃 (실시간 가격 크롤링 및 안전값)
        targets_5mbps = [
            {"carrier": "아이즈모바일", "title": "5G 아이즈팩 150GB+", "keywords": ["아이즈", "아이즈팩 150GB", "아이즈팩150GB"], "default_price": 23900},
            {"carrier": "티플러스", "title": "5G 티플온 150GB+_평생", "keywords": ["티플", "티플온 150GB", "티플온150GB"], "default_price": 26000},
            {"carrier": "시월모바일", "title": "평생5G 통화기본 125GB+", "keywords": ["시월", "통화기본125GB", "통화기본 125GB"], "default_price": 26950}
        ]

        # 실시간 가격 매칭 함수
        def resolve_prices(target_list, min_price, max_price):
            resolved = []
            for t in target_list:
                price = t["default_price"]
                for kw in t["keywords"]:
                    m = re.search(re.escape(kw) + r".{0,80}?월\s*([\d,]+)\s*원", flat_text)
                    if m:
                        val = int(m.group(1).replace(",", ""))
                        if min_price <= val <= max_price:
                            price = val
                            break
                resolved.append({"carrier": t["carrier"], "title": t["title"], "price": price})
            resolved.sort(key=lambda x: x["price"])
            return resolved

        list_10 = resolve_prices(targets_10mbps, 20000, 40000)
        list_5 = resolve_prices(targets_5mbps, 15000, 35000)

        medals = ["🥇 1위", "🥈 2위", "🥉 3위"]

        # 10Mbps 텍스트 구성
        lines_10 = []
        for i, item in enumerate(list_10):
            rank = medals[i]
            c = item["carrier"]
            t = item["title"]
            p_price = "{:,}".format(item["price"])
            lines_10.append(f"{rank}: <b>[{c}] {t}</b>\n   └ 월 <b>{p_price}원</b> (평생)")

        # 5Mbps 텍스트 구성
        lines_5 = []
        for i, item in enumerate(list_5):
            rank = medals[i]
            c = item["carrier"]
            t = item["title"]
            p_price = "{:,}".format(item["price"])
            lines_5.append(f"{rank}: <b>[{c}] {t}</b>\n   └ 월 <b>{p_price}원</b> (평생)")

        top10_text = "\n\n".join(lines_10)
        top5_text = "\n\n".join(lines_5)
        today = datetime.now().strftime("%Y-%m-%d")

        msg = (
            f"📊 <b>[알닷] 5G 평생 요금제 속도별 최저가 TOP 3</b> ({today})\n\n"
            f"🚀 <b>[10Mbps 무제한]</b>\n"
            f"{top10_text}\n\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"⚡ <b>[5Mbps 무제한]</b>\n"
            f"{top5_text}\n\n"
            f"🔗 <a href='{LIST_URL}'>알닷 요금제 목록 바로가기</a>"
        )

        send_telegram(msg)
        browser.close()

if __name__ == "__main__":
    run()
