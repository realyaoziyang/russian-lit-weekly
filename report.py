# -*- coding: utf-8 -*-
"""
report.py — 每周俄罗斯文学动态简报生成器
策略：通过 Google 新闻 RSS 搜索，追踪厚杂志、文学机构、奖项、出版社动态
"""

import os
import re
import smtplib
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

import requests
import feedparser

# ========== 1. 读取配置 ==========
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
EMAIL_TO = os.environ.get("EMAIL_TO", EMAIL_USER)

BEIJING = timezone(timedelta(hours=8))
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
MAX_PER_SECTION = 8  # 每个板块最多收录条数

# ========== 2. 信源清单（按你的体系分组，每组一组搜索词）==========
SECTIONS = {
    "📖 厚杂志动态": [
        '"Новый мир" журнал',
        '"Знамя" литературный журнал',
        '"Октябрь" журнал литературный',
        '"Дружба народов" журнал',
        '"Нева" журнал литературный',
        '"Москва" журнал Союз писателей',
    ],
    "🏛️ 机构与学术": [
        '"Литературная газета"',
        '"Союз писателей России"',
        "ИМЛИ РАН литература",
        '"Studia Litterarum"',
    ],
    "🏆 文学奖项": [
        '"Большая книга" премия',
        '"Национальный бестселлер" премия',
        '"Ясная Поляна" премия',
    ],
    "📚 出版动态": [
        "издательство АСТ новинки книги",
        "издательство Эксмо новые книги",
        '"Азбука" издательство новинки',
        "книжные новинки недели литература',
    ],
}

def gnews_url(query):
    """把搜索词变成 Google 新闻 RSS 地址，when:7d = 只搜最近7天"""
    return ("https://news.google.com/rss/search?q="
            + quote(query + " when:7d")
            + "&hl=ru&gl=RU&ceid=RU:ru")

def norm(title):
    """标题标准化，用于去重"""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", title.lower())).strip()

# ========== 3. 抓取 ==========
def fetch_all():
    seen, result = set(), {}
    for section, queries in SECTIONS.items():
        result[section] = []
        for q in queries:
            try:
                resp = requests.get(gnews_url(q), timeout=20, headers=HEADERS)
                print(f"[诊断] {section} |「{q}」状态码 {resp.status_code}")
                feed = feedparser.parse(resp.content)
                print(f"        解析出 {len(feed.entries)} 条")
            except Exception as e:
                print(f"[警告]「{q}」抓取失败：{e}")
                continue
            for e in feed.entries:
                title = e.get("title", "").strip()
                link = e.get("link", "").strip()
                if not title or not link or norm(title) in seen:
                    continue
                seen.add(norm(title))
                # 发布日期
                published = None
                for key in ("published_parsed", "updated_parsed"):
                    if e.get(key):
                        published = datetime(*e[key][:6], tzinfo=timezone.utc)
                        break
                if published is None:
                    published = datetime.now(timezone.utc)
                date_str = published.astimezone(BEIJING).strftime("%m月%d日")
                # 报道这条新闻的媒体名（如俄新社、塔斯社）
                src = ""
                if e.get("source"):
                    src = e["source"].get("title", "")
                result[section].append({
                    "date": date_str, "title": title, "link": link, "media": src,
                })
                if len(result[section]) >= MAX_PER_SECTION:
                    break
    return result

# ========== 4. 生成邮件 ==========
def build_email(result):
    today = datetime.now(BEIJING)
    week_start = (today - timedelta(days=7)).strftime("%m月%d日")
    week_end = today.strftime("%m月%d日")

    parts = []
    total = 0
    for section, items in result.items():
        if not items:
            parts.append(f"<h3>{section}</h3><p style='color:#999'>本周暂无动态</p>")
            continue
        total += len(items)
        rows = "".join(
            f'<tr><td style="color:#888;white-space:nowrap">{i["date"]}</td>'
            f'<td><a href="{i["link"]}">{i["title"]}</a>'
            + (f' <span style="color:#bbb;font-size:12px">· {i["media"]}</span>' if i["media"] else "")
            + "</td></tr>"
            for i in items
        )
        parts.append(f"<h3>{section}</h3><table cellpadding='6'>{rows}</table>")

    body = f"""
    <h2>📚 上周俄罗斯文学动态（{week_start}–{week_end}）</h2>
    <p>共 {total} 条，点击标题查看原文：</p>
    {''.join(parts)}
    <hr>
    <p style="color:#aaa;font-size:12px">由 russian-lit-weekly 自动生成 · 信源：Google 新闻聚合</p>
    """
    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = Header(f"📚 俄罗斯文学动态（{week_start}–{week_end}）", "utf-8")
    msg["From"] = formataddr((str(Header("文学小助手", "utf-8")), EMAIL_USER))
    msg["To"] = EMAIL_TO
    return msg

# ========== 5. 发送 ==========
def send_email(msg):
    with smtplib.SMTP_SSL("smtp.163.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, [EMAIL_TO], msg.as_string())

# ========== 主程序 ==========
if __name__ == "__main__":
    print("开始抓取俄罗斯文学动态…")
    result = fetch_all()
    for section, items in result.items():
        print(f"[结果] {section}：{len(items)} 条")
    send_email(build_email(result))
    print("邮件已发送！")
