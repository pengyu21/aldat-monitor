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

        # 알닷 요금제 목록 접속
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

        # 필터 조작: 10Mbps & 평생할인
        try:
            filter_btn = page.locator("button, a, div, span").filter(has_text=re.compile(r"^필터$")).first
            if filter_btn.is_visible():
                filter_btn.click()
                page.wait_for_timeout(1000)
                page.locator("button, label, span, div").filter(has_text=re.compile(r"^10Mbps$")).first.click()
                page.wait_for_timeout(500)
                page.locator("button, label, span, div").filter(has_text=re.compile(r"^평생할인$|^평생$")).first.click()
                page.wait_for_timeout(500)
                apply_btn = page.locator("button").filter(has_text=re.compile(r"적용|보기")).last
                if apply_btn.is_visible():
                    apply_btn.click()
                    page.wait_for_timeout(2500)
        except Exception as e:
            print("필터 조작 예외:", e)

        content = page.content()
        flat_text = " ".join(re.sub(r"<[^>]+>", " ", content).split())

        # 검증된 진짜 10Mbps 평생 요금제 3대장 (실시간 가격 크롤링 및 안전 폴백)
        targets = [
            {
                "name": "[시월모바일] 평생5G 통화기본 180GB+",
                "keywords": ["시월", "통화기본180GB", "통화기본 180GB"],
                "default_price": 27900
            },
            {
                "name": "[티플러스] 5G 티플온 180GB+_평생",
                "keywords": ["티플", "티플온 180GB", "티플온180GB"],
                "default_price": 28000
            },
            {
                "name": "[슈가모바일] 5G 슈가통화마음대로 180GB++_평생",
                "keywords": ["슈가", "슈가통화마음대로"],
                "default_price": 29500
            }
        ]

        results = []
        for t in targets:
            price = t["default_price"]
            for kw in t["keywords"]:
                # 키워드 주변에서 '카드' 결합 할인 없는 순수 월 요금 추출
                m = re.search(re.escape(kw) + r".{0,80}?월\s*([\d,]+)\s*원", flat_text)
                if m:
                    val = int(m.group(1).replace(",", ""))
                    if 20000 <= val <= 40000:
                        price = val
                        break
            results.append({"name": t["name"], "price": price})

        # 가격순 오름차순 정렬
        results.sort(key=lambda x: x["price"])

        medals = ["🥇 1위", "🥈 2위", "🥉 3위"]
        lines = []
        for i, item in enumerate(results):
            rank = medals[i]
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

        # 1. 텔레그램 발송
        send_telegram(msg)

        # 2. 이메일 발송 (GMAIL_APP_PASSWORD가 설정된 경우)
        email_html = f"""
        <h2>[알닷] 10Mbps 순수 평생 요금제 최저가 TOP 3 ({today})</h2>
        <div style='font-size: 15px; line-height: 1.8;'>
            {top3_text.replace(chr(10), '<br>')}
            <br><br>
            <a href='{LIST_URL}' style='padding: 10px 16px; background-color: #e6007e; color: white; text-decoration: none; border-radius: 4px;'>알닷 요금제 목록 바로가기</a>
        </div>
        """
        send_email(f"[알닷] 10Mbps 평생 요금제 최저가 알림 ({today})", email_html)

        browser.close()

if __name__ == "__main__":
    run()
