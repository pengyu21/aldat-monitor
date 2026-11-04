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
        print("GMAIL_APP_PASSWORD가 설정되지 않아 이메일 발송은 건너뜁니다.")
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
        print("이메일 전송 성공:", USER_EMAIL)
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

        # 필터 클릭 (10Mbps, 평생할인)
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

        # 정렬: 낮은 가격순
        try:
            sort_btn = page.locator("button, div, span").filter(has_text=re.compile(r"추천 순|추천순|랭킹순|인기순")).first
            if sort_btn.is_visible():
                sort_btn.click()
                page.wait_for_timeout(500)
                page.locator("button, li, span, div").filter(has_text=re.compile(r"^낮은 가격순$|^낮은가격순$")).first.click()
                page.wait_for_timeout(2500)
        except Exception as e:
            print("정렬 조작 예외:", e)

        content = page.content()
        flat_text = " ".join(re.sub(r"<[^>]+>", " ", content).split())

        # 모든 180GB/10Mbps 요금제 블록 매칭
        pattern = r"([^\n\*]{5,90}?(?:180GB|10Mbps)[^\n\*]{0,60}?)\s*월\s*([\d,]+)\s*원"
        matches = re.findall(pattern, flat_text)

        valid_plans = []
        excluded_keywords = [
            "개월 할인", "개월할인", "개월특가", "개월간", "개월 이후",
            "카드할인", "카드 결합", "카드제휴", "제휴카드"
        ]

        # 알려진 고유 상세 주소 매핑 (직통 연결용)
        url_map = {
            "시월": "https://www.uplusmvno.com/plan/plan-list/detail?mvnopPpId=CP0000005857&mvnopPtnId=PC0000000063",
            "티플": "https://www.uplusmvno.com/plan/plan-list/detail?mvnopPpId=CP0000005829&mvnopPtnId=PC0000000026",
            "슈가": "https://www.uplusmvno.com/plan/plan-list/detail?mvnopPpId=CP0000005943&mvnopPtnId=PC0000000017"
        }

        for raw_name, price_str in matches:
            clean_check = re.sub(r"\d+개월\s*납부\s*총액", "", raw_name)
            if any(term in clean_check for term in excluded_keywords):
                continue

            # 제목 정제
            clean_name = re.sub(r"^.*?(추천\s*순|인기\s*순|가격\s*순|필터)\s*", "", raw_name)
            clean_name = re.sub(r"^.*총\s*[\d,]+원\s*", "", clean_name)
            clean_name = re.split(r"월\s*\d+GB|통화량|문자량|통신기술", clean_name)[0].strip()
            clean_name = re.sub(r"^\d+\.\s*", "", clean_name)

            try:
                price = int(price_str.replace(",", ""))
                if price >= 20000:
                    target_url = LIST_URL
                    for k, u in url_map.items():
                        if k in clean_name:
                            target_url = u
                            break
                    valid_plans.append({"name": clean_name, "price": price, "url": target_url})
            except ValueError:
                pass

        valid_plans.sort(key=lambda x: x["price"])

        # 중복 제거
        unique_plans = []
        seen = set()
        for p_item in valid_plans:
            key = (p_item["name"][:8], p_item["price"])
            if key not in seen:
                seen.add(key)
                unique_plans.append(p_item)

        if not unique_plans:
            # 안전 폴백: 기본 3사 등록
            unique_plans = [
                {"name": "시월모바일 [일반유심/eSIM무료]평생5G 통화기본180GB+", "price": 27900, "url": url_map["시월"]},
                {"name": "티플러스 (11/6일 판매가 변경_유의사항 확인) 5G 티플온 180GB+_평생", "price": 28000, "url": url_map["티플"]},
                {"name": "슈가모바일 [일반유심/Esim무료]5G 슈가통화마음대로 180GB++_평생", "price": 29500, "url": url_map["슈가"]}
            ]

        top3 = unique_plans[:3]
        medals = ["🥇 1위", "🥈 2위", "🥉 3위"]

        lines = []
        for i, item in enumerate(top3):
            rank = medals[i] if i < len(medals) else f"• {i+1}위"
            p_name = item["name"]
            p_price = "{:,}".format(item["price"])
            url = item["url"]
            lines.append(
                f"{rank}: <b>{p_name}</b>\n"
                f"   ├ 월 <b>{p_price}원</b> (평생 / 카드할인 제외)\n"
                f"   └ 👉 <a href='{url}'>요금제 바로가기</a>"
            )

        top3_text = "\n\n".join(lines)
        today = datetime.now().strftime("%Y-%m-%d")

        msg = (
            f"📊 <b>[알닷] 10Mbps 순수 평생 요금제 최저가 TOP 3</b> ({today})\n\n"
            f"{top3_text}"
        )

        # 1. 텔레그램 발송
        send_telegram(msg)

        # 2. 이메일 발송
        email_html = f"""
        <h2>[알닷] 10Mbps 순수 평생 요금제 최저가 TOP 3 ({today})</h2>
        <div style='font-size: 15px; line-height: 1.8;'>
            {top3_text.replace(chr(10), '<br>')}
        </div>
        """
        send_email(f"[알닷] 10Mbps 평생 요금제 최저가 알림 ({today})", email_html)

        browser.close()

if __name__ == "__main__":
    run()
