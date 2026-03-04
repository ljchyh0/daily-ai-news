import requests
import smtplib
import os
import json
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.header import Header

# 从环境变量读取加密配置
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
DOUBAO_ENDPOINT_ID = os.getenv("DOUBAO_ENDPOINT_ID")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
EMAIL_AUTH_CODE = os.getenv("EMAIL_AUTH_CODE")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = 465

# 自动计算日期
today = datetime.now() + timedelta(hours=8)
yesterday = today - timedelta(days=1)
date_range_str = yesterday.strftime('%Y-%m-%d') + "至" + today.strftime('%Y-%m-%d')

# 去重库文件路径
BLACKLIST_FILE = "news_blacklist.json"
# API请求地址
API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

def load_blacklist():
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_blacklist(blacklist):
    with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(blacklist, f, ensure_ascii=False, indent=2)

def generate_ai_news(blacklist):
    blacklist_str = "\n".join(["- " + item for item in blacklist])
    
    # 构建prompt，不用f-string，避免语法错误
    prompt_parts = [
        "生成", date_range_str, " AI专属资讯，共30条，严格遵循以下所有规则：\n",
        "1. 固定分6大模块：大模型与技术突破（8条）、算力与硬件（6条）、医疗与科学AI（5条）、资本与产业（5条）、安全与监管（3条）、端侧与应用（3条）\n",
        "2. 单条资讯固定格式：事件时间+核心内容+核心影响+可验证信源\n",
        "3. 重点加粗规则：核心内容的关键主体、核心产品/版本号、关键数值、核心性能指标、核心结论必须加粗\n",
        "4. 信源合规规则：仅对境内有准确可跳转地址的内容加超链接，境外仅标注来源名称\n",
        "5. 【终身去重·最高优先级】绝对不能出现以下去重库中的任何事件：\n",
        blacklist_str, "\n",
        "6. 质量优先：仅用官方公告、国家级媒体、头部财经科技媒体的一手报道\n",
        "7. 生成完30条资讯后，在最后单独列出本次所有资讯的「去重指纹」，格式为：\n",
        "---去重指纹列表---\n事件核心主体_核心动作\n...（共30条）\n"
    ]
    PROMPT_RULE = "".join(prompt_parts)

    headers = {
        "Authorization": "Bearer " + DOUBAO_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "model": DOUBAO_ENDPOINT_ID,
        "messages": [
            {"role": "system", "content": "你是专业的AI行业资讯分析师，严格按照用户给定的规则生成高质量、无重复、合规的AI资讯，终身去重是最高优先级要求"},
            {"role": "user", "content": PROMPT_RULE}
        ],
        "temperature": 0.7,
        "max_tokens": 18000,
        "stream": False
    }
    try:
        print("✅ 开始生成", date_range_str, " AI资讯，已加载", len(blacklist), "条历史去重指纹...")
        response = requests.post(API_URL, headers=headers, json=data, timeout=180)
        response.raise_for_status()
        full_content = response.json()["choices"][0]["message"]["content"]
        
        news_content = full_content
        new_fingerprints = []
        if "---去重指纹列表---" in full_content:
            parts = full_content.split("---去重指纹列表---", 1)
            news_content = parts[0]
            fingerprints_part = parts[1].strip()
            new_fingerprints = [line.strip() for line in fingerprints_part.split("\n") if line.strip()]
        
        print("✅ 资讯生成成功，内容长度：", len(news_content))
        print("✅ 提取到", len(new_fingerprints), "条新去重指纹")
        
        with open(today.strftime('%Y-%m-%d') + "_AI资讯.md", "w", encoding="utf-8") as f:
            f.write(news_content)
        
        return news_content, new_fingerprints
    except Exception as e:
        print("❌ 资讯生成失败：", str(e))
        return None, []


def send_email(news_content):
    """将生成的资讯发送到指定邮箱，完全兼容QQ邮箱格式"""
    # 构建适配邮箱的HTML内容
    email_html = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{today.strftime('%Y-%m-%d')} 每日AI专属资讯</title>
        <style>
            body {{ font-family: "微软雅黑", "PingFang SC", Arial; line-height: 1.8; color: #333; max-width: 900px; margin: 0 auto; padding: 20px; }}
            h2 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; margin-top: 30px; }}
            h3 {{ color: #34495e; margin-top: 25px; }}
            p {{ margin: 10px 0; }}
            a {{ color: #3498db; text-decoration: none; }}
            strong {{ color: #e74c3c; }}
        </style>
    </head>
    <body>
        <h1 style="text-align: center; color: #2c3e50;">{today.strftime('%Y-%m-%d')} 每日AI专属资讯</h1>
        <div style="margin-top: 20px;">
            {news_content.replace('\n', '<br>').replace('---', '<hr>')}
        </div>
        <div style="margin-top: 50px; padding-top: 20px; border-top: 1px solid #eee; color: #999; font-size: 12px; text-align: center;">
            本资讯由豆包大模型自动生成，严格遵循终身去重规则，每日定时推送
        </div>
    </body>
    </html>
    """
    
    # 配置邮件（核心修改：From只用纯邮箱地址，不加昵称，完全符合QQ邮箱要求）
    message = MIMEText(email_html, 'html', 'utf-8')
    message['From'] = SENDER_EMAIL  # 核心修改：直接用纯邮箱地址
    message['To'] = RECEIVER_EMAIL
    message['Subject'] = Header(f"{today.strftime('%Y-%m-%d')} 每日AI专属资讯", 'utf-8')

    try:
        print("✅ 开始发送邮件...")
        smtp_obj = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30)
        smtp_obj.login(SENDER_EMAIL, EMAIL_AUTH_CODE)
        smtp_obj.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL], message.as_string())
        smtp_obj.quit()
        print("✅ 邮件发送成功，已推送至：", RECEIVER_EMAIL)
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败：{e}")
        return False

if __name__ == "__main__":
    required_env = [DOUBAO_API_KEY, DOUBAO_ENDPOINT_ID, SENDER_EMAIL, EMAIL_AUTH_CODE, RECEIVER_EMAIL, SMTP_SERVER]
    if None in required_env:
        print("❌ 错误：缺少必要的环境变量，请检查GitHub Secrets配置")
        exit(1)
    
    blacklist = load_blacklist()
    news_content, new_fingerprints = generate_ai_news(blacklist)
    if not news_content:
        exit(1)
    
    send_email(news_content)
    
    if new_fingerprints:
        updated_blacklist = blacklist + new_fingerprints
        save_blacklist(updated_blacklist)
        print("✅ 永久去重库已更新，新增", len(new_fingerprints), "条，总计", len(updated_blacklist), "条")
