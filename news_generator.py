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
date_range = f"{yesterday.strftime('%Y-%m-%d')}至{today.strftime('%Y-%m-%d')}"

# 去重库文件路径
BLACKLIST_FILE = "news_blacklist.json"

def load_blacklist():
    """加载永久去重库"""
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_blacklist(blacklist):
    """保存更新后的去重库"""
    with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(blacklist, f, ensure_ascii=False, indent=2)

def generate_ai_news(blacklist):
    """调用豆包API生成符合规则的AI资讯，严格避开去重库"""
    # 把去重库转换成字符串，加入prompt，让模型严格避开
    blacklist_str = "\n".join([f"- {item}" for item in blacklist])
    
    # 【永久固化你的最终规则，新增终身去重要求】
    PROMPT_RULE = f"""
生成{date_range} AI专属资讯，共30条，严格遵循以下所有规则，不得有任何偏差：
1.  固定分6大模块：大模型与技术突破（8条）、算力与硬件（6条）、医疗与科学AI（5条）、资本与产业（5条）、安全与监管（3条）、端侧与应用（3条）
2.  单条资讯固定格式：事件时间+核心内容+核心影响+可验证信源
3.  重点加粗规则：核心内容的关键主体、核心产品/版本号、关键数值、核心性能指标、核心结论必须加粗，方便读者快速抓重点
4.  信源合规规则：仅对境内新闻媒体、有准确可验证跳转地址的内容添加超链接；境外来源、无准确可跳转地址的内容，仅标注来源名称，绝不配置任何无效超链接
5.  【终身去重·最高优先级】绝对不能出现以下去重库中的任何事件，哪怕换表述、补细节、换角度也不行：
{blacklist_str}
6.  质量优先规则：仅选用官方公告、国家级媒体、头部财经科技媒体的一手报道，严格剔除抖音、个人自媒体、非权威来源内容
7.  格式要求：段落清晰，模块分明，无乱码、无格式错乱
8.  【新增】生成完30条资讯后，在最后单独列出本次所有资讯的「去重指纹」，格式为：
---去重指纹列表---
事件核心主体_核心动作
事件核心主体_核心动作
...
（共30条，和前面的资讯一一对应）
"""

    headers = {
        "Authorization": f"Bearer {DOUBAO_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": DOUBAO_ENDPOINT_ID,
        "messages": [
            {"role": "system", "content": "你是专业的AI行业资讯分析师，严格按照用户给定的规则生成高质量、无重复、合规的AI资讯，确保内容真实、权威、时效性强，终身去重是最高优先级要求"},
            {"role": "user", "content": PROMPT_RULE}
        ],
        "temperature": 0.7,
        "max_tokens": 18000,
        "stream": False
    }
    try:
        print(f"✅ 开始生成{date_range} AI资讯，已加载{len(blacklist)}条历史去重指纹...")
        response = requests.post(API_URL, headers=headers, json=data, timeout=180)
        response.raise_for_status()
        full_content = response.json()["choices"][0]["message"]["content"]
        
        # 分离正文内容和去重指纹
        if "---去重指纹列表---" in full_content:
            news_content, fingerprints_part = full_content.split("---去重指纹列表---", 1)
            # 提取去重指纹
            new_fingerprints = [line.strip() for line in fingerprints_part.strip().split("\n") if line.strip()]
        else:
            news_content = full_content
            new_fingerprints = []
        
        print("✅ 资讯生成成功，内容长度：", len(news_content))
        print(f"✅ 提取到{len(new_fingerprints)}条新去重指纹")
        
        # 本地保存日志
        with open(f"{today.strftime('%Y-%m-%d')}_AI资讯.md", "w", encoding="utf-8") as f:
            f.write(news_content)
        
        return news_content, new_fingerprints
    except Exception as e:
        print(f"❌ 资讯生成失败：{str(e)}")
        return None, []

def send_email(news_content):
    """将生成的资讯发送到指定邮箱"""
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
    message = MIMEText(email_html, 'html', 'utf-8')
    message['From'] = Header(f"每日AI资讯推送 <{SENDER_EMAIL}>", 'utf-8')
    message['To'] = Header(RECEIVER_EMAIL, 'utf-8')
    message['Subject'] = Header(f"{today.strftime('%Y-%m-%d')} 每日AI专属资讯", 'utf-8')

    try:
        print("✅ 开始发送邮件...")
        smtp_obj = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30)
        smtp_obj.login(SENDER_EMAIL, EMAIL_AUTH_CODE)
        smtp_obj.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message.as_string())
        smtp_obj.quit()
        print("✅ 邮件发送成功，已推送至：", RECEIVER_EMAIL)
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败：{str(e)}")
        return False

# 主程序执行
if __name__ == "__main__":
    # 校验环境变量
    required_env = [DOUBAO_API_KEY, DOUBAO_ENDPOINT_ID, SENDER_EMAIL, EMAIL_AUTH_CODE, RECEIVER_EMAIL, SMTP_SERVER]
    if None in required_env:
        print("❌ 错误：缺少必要的环境变量，请检查GitHub Secrets配置")
        exit(1)
    
    # 1. 加载永久去重库
    blacklist = load_blacklist()
    
    # 2. 生成资讯（严格避开去重库）
    news_content, new_fingerprints = generate_ai_news(blacklist)
    if not news_content:
        exit(1)
    
    # 3. 发送邮件
    send_email(news_content)
    
    # 4. 更新永久去重库（只有邮件发送成功才更新）
    if new_fingerprints:
        updated_blacklist = blacklist + new_fingerprints
        save_blacklist(updated_blacklist)
        print(f"✅ 永久去重库已更新，新增{len(new_fingerprints)}条，总计{len(updated_blacklist)}条")
