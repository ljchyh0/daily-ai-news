import requests
import smtplib
import os
import json
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.header import Header

# ================= 配置区域（从环境变量读取，无需修改） =================
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
DOUBAO_ENDPOINT_ID = os.getenv("DOUBAO_ENDPOINT_ID")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
EMAIL_AUTH_CODE = os.getenv("EMAIL_AUTH_CODE")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = 465

# ================= 自动计算日期 =================
today = datetime.now() + timedelta(hours=8)
yesterday = today - timedelta(days=1)
date_range_str = yesterday.strftime('%Y-%m-%d') + "至" + today.strftime('%Y-%m-%d')
today_str = today.strftime('%Y-%m-%d')

# ================= 文件路径配置 =================
BLACKLIST_FILE = "news_blacklist.json"
API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

# ================= 核心功能函数 =================

def load_blacklist():
    """加载历史去重库"""
    if os.path.exists(BLACKLIST_FILE):
        try:
            with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_blacklist(blacklist):
    """保存更新后的去重库"""
    with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(blacklist, f, ensure_ascii=False, indent=2)

def build_prompt(date_range, blacklist):
    """【核心优化·满足新需求】构建强制格式Prompt，新增目录+标题，彻底去掉时间字段"""
    blacklist_str = "\n".join(["- " + item for item in blacklist])
    
    prompt_parts = [
        "生成", date_range, " AI日报资讯，共30条，严格遵循以下所有规则，不得有任何偏差：\n",
        "1. 【全文结构固定·顺序不可变】全文必须严格按照以下顺序生成：\n",
        "   第一部分：核心资讯总览目录\n",
        "   第二部分：分模块详细资讯内容\n",
        "   第三部分：去重指纹列表\n",
        "\n",
        "2. 【第一部分：核心资讯总览目录·强制规则】\n",
        "   - 目录标题固定为：一、核心资讯总览目录\n",
        "   - 目录共30条，和后文30条资讯一一对应，序号完全一致\n",
        "   - 单条目录格式：序号. 核心标题，单条内容严格控制在20个汉字以内，禁止超字数\n",
        "   - 正确目录示例：\n",
        "     1. 荣耀发布Magic UI 9 AI版系统\n",
        "     2. 字节跳动发布豆包4.5多模态模型\n",
        "     3. 智谱AI发布多模态增强版大模型\n",
        "\n",
        "3. 【第二部分：分模块详细资讯·强制规则】\n",
        "   - 固定分6大模块，模块顺序固定为：二、大模型与技术突破（8条）、三、算力与硬件（6条）、四、医疗与科学AI（5条）、五、资本与产业（5条）、六、安全与监管（3条）、七、端侧与应用（3条）\n",
        "   - 【格式最高优先级】彻底删除「事件时间」字段，单条资讯必须严格按照以下固定格式输出，段落之间必须空一行，绝对禁止用|符号拼接内容，绝对禁止把多个字段挤在同一行：\n",
        "   【正确单条资讯格式示例】\n",
        "   28. 荣耀发布Magic UI 9 AI版系统\n",
        "\n",
        "   核心内容：荣耀正式发布Magic UI 9 AI版操作系统，内置自研端侧AI大模型“YOYO大模型4.0”，仅5B参数，支持离线语音交互、图像理解、文档处理、自动化操作全功能，可在手机、平板、笔记本、智能家居设备上跨端协同运行，响应速度较前代提升8倍，功耗降低55%。\n",
        "\n",
        "   核心影响：推动端侧AI在消费电子领域的规模化落地，重构了移动终端的人机交互范式，完善了荣耀全场景AI生态布局。\n",
        "\n",
        "   可验证信源：荣耀官方公告、IT之家、爱范儿\n",
        "\n",
        "   - 【标题强制规则】每条资讯的第一个字段必须是「序号. 标题」，标题必须和前文核心资讯总览目录里的对应标题完全一致，不得修改\n",
        "   - 【段落规则】大模块之间必须空两行，每条资讯之间必须空一行，不得出现连续无换行的密集内容\n",
        "   - 【加粗规则】核心内容里的关键主体、核心产品/版本号、关键数值、核心性能指标、核心结论必须加粗，其余内容不得随意加粗\n",
        "   - 【信源合规规则】仅对境内有准确可跳转地址的内容加超链接，境外来源、无准确可跳转地址的内容，仅标注来源名称，绝不配置任何无效超链接\n",
        "\n",
        "4. 【终身去重·最高优先级】绝对不能出现以下去重库中的任何事件，哪怕换表述、补细节、换角度也不行：\n",
        blacklist_str, "\n",
        "\n",
        "5. 【质量规则】仅选用官方公告、国家级媒体、头部财经科技媒体的一手报道，严格剔除抖音、个人自媒体、非权威来源内容\n",
        "\n",
        "6. 【第三部分：去重指纹列表规则】生成完所有资讯后，在全文最后单独列出本次所有资讯的「去重指纹」，格式为：\n",
        "---去重指纹列表---\n事件核心主体_核心动作\n事件核心主体_核心动作\n...（共30条，和前面的资讯一一对应）\n"
    ]
    return "".join(prompt_parts)

def generate_ai_news(blacklist):
    """调用豆包API生成资讯，优化生成稳定性与内容长度"""
    PROMPT_RULE = build_prompt(date_range_str, blacklist)

    headers = {
        "Authorization": "Bearer " + DOUBAO_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "model": DOUBAO_ENDPOINT_ID,
        "messages": [
            {"role": "system", "content": "你是专业的AI行业日报分析师，严格按照用户给定的格式规则生成内容，格式合规是最高优先级要求，绝对禁止违规拼接内容，终身去重规则必须严格遵守，标题与目录必须一一对应"},
            {"role": "user", "content": PROMPT_RULE}
        ],
        "temperature": 0.6,
        "max_tokens": 16000,
        "stream": False
    }
    try:
        print("✅ 开始生成", date_range_str, " AI日报，已加载", len(blacklist), "条历史去重指纹...")
        response = requests.post(API_URL, headers=headers, json=data, timeout=360)
        response.raise_for_status()
        full_content = response.json()["choices"][0]["message"]["content"]
        
        # 分离资讯内容和去重指纹
        news_content = full_content
        new_fingerprints = []
        if "---去重指纹列表---" in full_content:
            parts = full_content.split("---去重指纹列表---", 1)
            news_content = parts[0]
            fingerprints_part = parts[1].strip()
            new_fingerprints = [line.strip() for line in fingerprints_part.split("\n") if line.strip()]
        
        print("✅ 资讯生成成功，内容长度：", len(news_content))
        print("✅ 提取到", len(new_fingerprints), "条新去重指纹")
        
        # 保存资讯文件
        try:
            with open(today_str + "_AI日报.md", "w", encoding="utf-8") as f:
                f.write(news_content)
        except:
            pass
        
        return news_content, new_fingerprints
    except Exception as e:
        print("❌ 资讯生成失败：", str(e))
        return None, []

def send_email(news_content):
    """【优化HTML样式】适配新增目录，兼容QQ邮箱，段落更清晰"""
    # 构建HTML内容，新增目录专属样式，优化段落间距
    email_html_parts = [
        "<html><head><meta charset='UTF-8'><title>", today_str, " 每日AI专属日报</title>",
        "<style>",
        "body { font-family: '微软雅黑', 'PingFang SC', Arial; line-height: 1.8; color: #333; max-width: 900px; margin: 0 auto; padding: 20px; }",
        "h1 { text-align: center; color: #2c3e50; margin-bottom: 40px; }",
        ".module-title { font-size: 22px; font-weight: bold; color: #2c3e50; margin: 35px 0 20px 0; padding-bottom: 8px; border-bottom: 2px solid #3498db; }",
        ".catalog-box { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }",
        ".catalog-item { line-height: 2; font-size: 15px; }",
        ".news-item { margin: 30px 0; }",
        ".news-title { font-size: 17px; font-weight: 600; color: #2c3e50; margin-bottom: 15px; }",
        "p { margin: 12px 0; text-align: justify; }",
        "strong { color: #e74c3c; font-weight: 600; }",
        "a { color: #3498db; text-decoration: none; }",
        "hr { border: none; border-top: 1px solid #eee; margin: 30px 0; }",
        "</style></head><body>",
        "<h1>", today_str, " 每日AI专属日报</h1>",
        "<div class='main-content'>",
        news_content.replace('\n\n', '</p><p>').replace('\n', '<br>'),
        "</div>",
        "<div style='margin-top: 60px; padding-top: 20px; border-top: 1px solid #eee; color: #999; font-size: 12px; text-align: center;'>",
        "本日报由豆包大模型自动生成，严格遵循终身去重规则，每日定时推送",
        "</div></body></html>"
    ]
    email_html = "".join(email_html_parts)
    
    # QQ邮箱完全兼容的邮件配置
    message = MIMEText(email_html, 'html', 'utf-8')
    message['From'] = SENDER_EMAIL
    message['To'] = RECEIVER_EMAIL
    message['Subject'] = Header(today_str + " 每日AI专属日报", 'utf-8')

    try:
        print("✅ 开始发送邮件...")
        smtp_obj = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30)
        smtp_obj.login(SENDER_EMAIL, EMAIL_AUTH_CODE)
        smtp_obj.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL], message.as_string())
        smtp_obj.quit()
        print("✅ 邮件发送成功，已推送至：", RECEIVER_EMAIL)
        return True
    except Exception as e:
        print("❌ 邮件发送失败：", str(e))
        return False

# ================= 主程序入口 =================
if __name__ == "__main__":
    # 检查环境变量
    required_env = [DOUBAO_API_KEY, DOUBAO_ENDPOINT_ID, SENDER_EMAIL, EMAIL_AUTH_CODE, RECEIVER_EMAIL, SMTP_SERVER]
    if None in required_env:
        print("❌ 错误：缺少必要的环境变量，请检查GitHub Secrets配置")
        exit(1)
    
    # 执行完整流程
    blacklist = load_blacklist()
    news_content, new_fingerprints = generate_ai_news(blacklist)
    
    if not news_content:
        exit(1)
    
    send_email(news_content)
    
    # 更新去重库
    if new_fingerprints:
        updated_blacklist = blacklist + new_fingerprints
        save_blacklist(updated_blacklist)
        print("✅ 永久去重库已更新，新增", len(new_fingerprints), "条，总计", len(updated_blacklist), "条")
