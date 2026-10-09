# -*- coding: utf-8 -*-
"""
report.py — 每周俄罗斯文学动态简报生成器
原理：抓取俄罗斯文化新闻的 RSS 源 → 按文学关键词筛选最近7天的新闻
      → 生成邮件 → 用163邮箱发给你
"""

import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

import feedparser

# ========== 1. 读取配置（之后从 GitHub 加密保险箱获取）==========
EMAIL_USER = os.environ["EMAIL_USER"]              # 你的163邮箱地址
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]      # 163授权码（不是登录密码！）
EMAIL_TO = os.environ.get("EMAIL_TO", EMAIL_USER)  # 收件人，默认发给自己

# ========== 2. 新闻源（俄罗斯主流文化频道 RSS）==========
FEEDS = {
    "俄新社 · 文化": "https://ria.ru/export/rss2/culture/index.xml",
    "Lenta.ru · 文化": "https://lenta.ru/rss/culture",
    "Газета.ru · 文化": "https://www.gazeta.ru/rss/culture.xml",
    "俄罗斯报 · 文化": "https://rg.ru/rss/culture.xml",
}

# ========== 3. 文学关键词（只保留标题沾边的）==========
KEYWORDS = ["литератур", "книг", "поэт", "поэз", "проза", "писател",
            "роман", "рассказ", "повест", "премия", "издат", "автор",
            "читател", "библиотек", "перевод", "стих", "букер"]

LOOKBACK_DAYS = 7
BEIJING = timezone(timedelta(hours=8))  # 北京时间

# ========== 4. 抓取并筛选新闻 ==========
def fetch_news():
    items, seen = [], set()
    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"[警告] {source} 抓取失败：{e}")
            continue
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            if not title or not link or link in seen:
                continue
            seen.add(link)
            # 只保留文学相关标题
            if not any(k in title.lower() for k in KEYWORDS):
                continue
            # 只保留最近7天
            published = None
            for key in ("published_parsed", "updated_parsed"):
                if entry.get(key):
                    published = datetime(*entry[key][:6], tzinfo=timezone.utc)
                    break
            if published is None:
                published = datetime.now(timezone.utc)
            if datetime.now(timezone.utc) - published > timedelta(days=LOOKBACK_DAYS):
                continue
            items.append({
                "source": source,
                "title": title,
                "link": link,
                "date": published.astimezone(BEIJING).strftime("%m月%d日"),
            })
    items.sort(key=lambda x: x["date"])
    return items

# ========== 5. 生成邮件 ==========
def build_email(items):
    today = datetime.now(BEIJING)
    week_start = (today - timedelta(days=7)).strftime("%m月%d日")
    week_end = today.strftime("%m月%d日")

    if not items:
        body = "<p>本周没有找到匹配的文学新闻（可能是新闻源暂时不可用）。</p>"
    else:
        rows = "".join(
            f'<tr><td style="color:#888;white-space:nowrap">{i["date"]}</td>'
            f'<td>[{i["source"]}] <a href="{i["link"]}">{i["title"]}</a></td></tr>'
            for i in items
        )
        body = f"""
        <h2>📚 上周俄罗斯文学动态（{week_start}–{week_end}）</h2>
        <p>共筛选出 {len(items)} 条文学相关新闻，点击标题查看原文：</p>
        <table cellpadding="6">{rows}</table>
        <hr>
        <p style="color:#aaa;font-size:12px">由 russian-lit-weekly 自动生成</p>
        """

    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = Header(f"📚 俄罗斯文学动态（{week_start}–{week_end}）", "utf-8")
    msg["From"] = formataddr((str(Header("文学小助手", "utf-8")), EMAIL_USER))
    msg["To"] = EMAIL_TO
    return msg

# ========== 6. 发送邮件 ==========
def send_email(msg):
    with smtplib.SMTP_SSL("smtp.163.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, [EMAIL_TO], msg.as_string())

# ========== 主程序入口 ==========
if __name__ == "__main__":
    print("开始抓取俄罗斯文学新闻…")
    items = fetch_news()
    print(f"筛选出 {len(items)} 条")
    send_email(build_email(items))
    print("邮件已发送！")
