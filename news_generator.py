import requests
import smtplib
import os
import json
import markdown2
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.header import Header

# ================= 配置区域（完全沿用你之前的Secrets，无需修改） =================
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
DOUBAO_ENDPOINT_ID = os.getenv("DOUBAO_ENDPOINT_ID")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
EMAIL_AUTH_CODE = os.getenv("EMAIL_AUTH_CODE")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = 465

# ================= 自动计算日期（北京时间） =================
today = datetime.now() + timedelta(hours=8)
yesterday = today - timedelta(days=1)
date_range_str = yesterday.strftime('%Y-%m-%d') + "至" + today.strftime('%Y-%m-%d')
today_str = today.strftime('%Y-%m-%d')

# ================= 路径&接口配置（官方正确接口地址） =================
BLACKLIST_FILE = "news_blacklist.json"
API_URL = "https://ark.cn-beijing.volces.com/api/v3/responses"

# ================= 核心Markdown转HTML函数（邮件渲染用，完全保留） =================
def markdown_to_html_document(markdown_text: str) -> str:
    html_content = markdown2.markdown(
        markdown_text,
        extras=["tables", "fenced-code-blocks", "break-on-newline", "cuddled-lists"],
    )

    css_style = """
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, "微软雅黑", "PingFang SC", sans-serif;
                line-height: 1.6;
                color: #24292e;
                font-size: 15px;
                padding: 20px;
                max-width: 900px;
                margin: 0 auto;
            }
            h1 {
                font-size: 24px;
                border-bottom: 1px solid #eaecef;
                padding-bottom: 0.5em;
                margin-top: 1.5em;
                margin-bottom: 1em;
                color: #0366d6;
                text-align: center;
            }
            h2 {
                font-size: 20px;
                border-bottom: 1px solid #eaecef;
                padding-bottom: 0.3em;
                margin-top: 1.2em;
                margin-bottom: 0.8em;
                color: #24292e;
            }
            h3 {
                font-size: 17px;
                margin-top: 1em;
                margin-bottom: 0.5em;
            }
            p {
                margin-top: 0;
                margin-bottom: 10px;
            }
            strong {
                color: #d73a49;
                font-weight: 600;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 12px 0;
                display: block;
                overflow-x: auto;
                font-size: 13px;
            }
            th, td {
                border: 1px solid #dfe2e5;
                padding: 6px 10px;
                text-align: left;
            }
            th {
                background-color: #f6f8fa;
                font-weight: 600;
            }
            tr:nth-child(2n) {
                background-color: #f8f8f8;
            }
            tr:hover {
                background-color: #f1f8ff;
            }
            blockquote {
                color: #6a737d;
                border-left: 0.25em solid #dfe2e5;
                padding: 0 1em;
                margin: 0 0 10px 0;
            }
            code {
                padding: 0.2em 0.4em;
                margin: 0;
                font-size: 85%;
                background-color: rgba(27,31,35,0.05);
                border-radius: 3px;
                font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
            }
            pre {
                padding: 12px;
                overflow: auto;
                line-height: 1.45;
                background-color: #f6f8fa;
                border-radius: 3px;
                margin-bottom: 10px;
            }
            hr {
                height: 0.25em;
                padding: 0;
                margin: 16px 0;
                background-color: #e1e4e8;
                border: 0;
            }
            ul, ol {
                padding-left: 20px;
                margin-bottom: 10px;
            }
            li {
                margin: 2px 0;
            }
        """

    return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                {css_style}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

# ================= 核心功能函数（完全保留原有逻辑，仅修改响应解析部分） =================
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
    """【完全使用你优化后的Prompt】未做任何修改，100%保留你的配置"""
    blacklist_str = "\n".join(["- " + item for item in blacklist])
    
    prompt_parts = [
        "生成", date_range, " AI日报资讯，共30条，严格遵循以下所有规则，优先级从高到低，不得有任何偏差：\n",
        "\n",
        "【最高优先级·绝对禁止违规】\n",
        "1. 必须全程使用内置联网搜索功能，所有内容100%来自本次搜索到的、", date_range, "区间内全球AI领域真实发生的事件，绝对禁止使用模型离线知识库内容，绝对禁止杜撰、虚构、未发生的内容\n",
        "2. 【终身去重·不可突破】绝对不能出现以下去重库中的任何事件，哪怕换表述、补细节、换角度也不行：\n",
        blacklist_str, "\n",
        "3. 所有资讯必须有至少2个权威信源支撑，优先选用厂商官方公告、国家级媒体、全球顶级科技媒体、头部财经科技媒体的一手报道，严格剔除抖音、个人自媒体、非权威来源内容\n",
        "\n",
        "【第二优先级·内容筛选规则·决定内容全不全、精不精】\n",
        "1. 资讯收录优先级严格按以下顺序，前两类内容必须占总条数的70%以上，绝对不能只收录国内非核心厂商内容：\n",
        "   第一优先级：全球头部AI厂商重磅发布/技术突破（OpenAI、谷歌DeepMind、Anthropic、英伟达、微软、苹果、亚马逊AWS）\n",
        "   第二优先级：国内头部厂商核心动态（字节跳动、百度、华为、智谱AI、蚂蚁集团、腾讯、阿里）\n",
        "   第三优先级：国家级AI政策/监管规则、全球顶级学术期刊（Nature/Science/Cell）的AI科研突破\n",
        "   第四优先级：AI领域重大产业融资、行业战略合作、标杆落地应用\n",
        "2. 【内容精度强制要求】每条资讯必须包含可量化的核心数据（如准确率提升比例、参数规模、融资额、性能提升幅度），核心影响必须具体、有行业价值，绝对不能用空泛的套话、废话\n",
        "\n",
        "【第三优先级·全文结构固定·顺序不可变】\n",
        "全文必须严格按照以下顺序生成，全部使用标准Markdown格式：\n",
        "   第一部分：核心资讯总览目录\n",
        "   第二部分：分模块详细资讯内容\n",
        "   第三部分：去重指纹列表\n",
        "\n",
        "【第四优先级·格式强制规则·100%匹配渲染要求】\n",
        "1. 【第一部分：核心资讯总览目录】\n",
        "   - 标题固定为：## 一、核心资讯总览目录\n",
        "   - 目录共30条，和后文30条资讯一一对应，序号完全一致\n",
        "   - 单条目录格式：`序号. 核心标题`，单条内容严格控制在20个汉字以内，禁止超字数\n",
        "   - 正确目录示例：\n",
        "     1. OpenAI发布GPT-5.4旗舰大模型\n",
        "     2. 英伟达发布全新架构AI芯片\n",
        "     3. 智谱AI发布多模态增强版大模型\n",
        "\n",
        "2. 【第二部分：分模块详细资讯】\n",
        "   - 固定分6大模块，模块顺序固定，标题使用标准Markdown二级标题：\n",
        "     ## 二、大模型与技术突破（n条）\n",
        "     ## 三、算力与硬件（n条）\n",
        "     ## 四、医疗与科学AI（n条）\n",
        "     ## 五、资本与产业（n条）\n",
        "     ## 六、安全与监管（n条）\n",
        "     ## 七、端侧与应用（n条）\n",
        "   - 单条资讯必须严格按照以下固定格式输出，段落之间必须空一行，绝对禁止用|符号拼接内容，绝对禁止把多个字段挤在同一行：\n",
        "   【正确单条资讯格式示例·必须严格对齐】\n",
        "   ### 1. OpenAI发布GPT-5.4旗舰大模型\n",
        "\n",
        "   **核心内容**：**OpenAI**正式发布**GPT-5.4系列旗舰大模型**，首次内置原生计算机操控能力，支持100万Token上下文窗口，在OSWorld计算机操作基准测试中任务成功率达75%，超越人类平均水平，API已全面开放调用。\n",
        "\n",
        "   **核心影响**：大幅拓展AI智能体的应用边界，推动办公自动化、复杂工作流处理场景的规模化落地，巩固了OpenAI在通用大模型领域的技术领先地位。\n",
        "\n",
        "   **可验证信源**：OpenAI官方公告、新浪新闻、每日经济新闻\n",
        "\n",
        "   - 标题强制规则：每条资讯的标题必须是三级Markdown标题`### 序号. 标题`，序号和标题之间必须有空格，标题必须和前文核心资讯总览目录里的对应标题完全一致，不得修改\n",
        "   - 加粗规则：核心内容里的关键主体、核心产品/版本号、关键数值、核心性能指标、核心结论必须用**包裹加粗，字段名「核心内容」「核心影响」「可验证信源」也必须加粗\n",
        "   - 段落规则：大模块之间必须空两行，每条资讯之间必须空一行，不得出现连续无换行的密集内容\n",
        "   - 信源规则：仅对境内有准确可跳转地址的内容加超链接，境外来源仅标注来源名称，绝不配置无效超链接\n",
        "\n",
        "3. 【第三部分：去重指纹列表】\n",
        "   生成完所有资讯后，在全文最后单独列出本次所有资讯的「去重指纹」，格式为：\n",
        "   ---\n",
        "   ## 去重指纹列表\n",
        "   事件核心主体_核心动作\n",
        "   事件核心主体_核心动作\n",
        "...（共30条，和前面的资讯一一对应）\n"
    ]
    return "".join(prompt_parts)

def generate_ai_news(blacklist):
    """【100%符合官方规范】Responses API + Web Search 正确调用方式，仅修改响应解析逻辑"""
    PROMPT_RULE = build_prompt(date_range_str, blacklist)

    headers = {
        "Authorization": "Bearer " + DOUBAO_API_KEY,
        "Content-Type": "application/json"
    }

    # 【官方标准格式·完全对齐文档】请求体配置
    data = {
        "model": DOUBAO_ENDPOINT_ID,
        "stream": False,
        # 【官方规范】web_search工具完整参数配置，对应文档第3章参数说明
        "tools": [
            {
                "type": "web_search",
                "max_keyword": 3,  # 单轮最多3个关键词，控制成本，对应文档3.4节
                "limit": 15,  # 单次搜索最多返回15条结果，对应文档3.4节
                "user_location": {  # 优化国内搜索结果，对应文档3.3节
                    "type": "approximate",
                    "country": "中国",
                    "region": "广东",
                    "city": "深圳"
                }
            }
        ],
        "max_tool_calls": 3,  # 限制最多3轮工具调用，避免无限循环，对应文档3.4节
        "max_output_tokens": 16000,
        "temperature": 0.6,
        # 【官方规范·核心修正】input字段完全对齐文档格式，content必须是input_text数组
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": "你是专业的AI行业日报分析师，严格遵循用户给定的所有规则，优先使用web_search联网搜索获取最新、真实的资讯，格式合规是最高优先级要求，终身去重规则必须严格遵守，标题与目录必须一一对应"
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": PROMPT_RULE
                    }
                ]
            }
        ]
    }

    try:
        print("✅ 开始生成", date_range_str, " AI日报，已加载", len(blacklist), "条历史去重指纹...")
        print("📡 正在调用火山方舟Responses API+联网搜索...")
        response = requests.post(API_URL, headers=headers, json=data, timeout=360)
        
        # 【关键调试信息】打印完整响应，方便排查问题
        print(f"📊 API响应状态码：{response.status_code}")
        print(f"📄 API完整返回内容：{response.text}")
        
        response.raise_for_status()
        response_json = response.json()

        # ======================== 【核心修复】正确解析API返回结构 ========================
        full_content = None
        # 1. 先找最外层的 output 数组
        if "output" in response_json and isinstance(response_json["output"], list):
            # 2. 在 output 数组里找 type 为 "message" 的对象
            for output_item in response_json["output"]:
                if output_item.get("type") == "message" and "content" in output_item:
                    # 3. 在 message 的 content 数组里找 type 为 "output_text" 的对象
                    for content_item in output_item["content"]:
                        if content_item.get("type") == "output_text" and content_item.get("text"):
                            full_content = content_item["text"]
                            break
                    if full_content:
                        break
        # =================================================================================
        

        if not full_content:
            print("❌ API返回内容结构异常，未找到有效文本内容")
            return None, []
        
        # 【官方规范】打印搜索用量统计，对应文档3.5节
        if "usage" in response_json:
            tool_usage = response_json["usage"].get("tool_usage", {})
            tool_usage_details = response_json["usage"].get("tool_usage_details", {})
            print(f"🔍 联网搜索调用统计：总调用次数 {tool_usage.get('web_search', 0)}，明细 {tool_usage_details}")
        
        # 分离资讯内容和去重指纹
        news_content = full_content
        new_fingerprints = []
        if "## 去重指纹列表" in full_content:
            parts = full_content.split("## 去重指纹列表", 1)
            news_content = parts[0]
            fingerprints_part = parts[1].strip()
            new_fingerprints = [line.strip() for line in fingerprints_part.split("\n") if line.strip() and not line.startswith("---")]
        
        # 给全文加上主标题
        full_markdown = f"# {today_str} 每日AI专属日报\n\n" + news_content
        
        print("✅ 资讯生成成功，内容长度：", len(full_markdown))
        print("✅ 提取到", len(new_fingerprints), "条新去重指纹")
        
        # 保存Markdown源文件
        try:
            with open(today_str + "_AI日报.md", "w", encoding="utf-8") as f:
                f.write(full_markdown)
        except Exception as save_err:
            print(f"⚠️  Markdown文件保存失败：{save_err}")
        
        return full_markdown, new_fingerprints

    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP错误：{e}")
        print(f"❌ 火山方舟API返回的具体错误：{response.text if 'response' in locals() else '无响应内容'}")
        return None, []
    except Exception as e:
        print(f"❌ 资讯生成失败：{e}")
        if 'response' in locals():
            print(f"❌ API返回内容：{response.text}")
        return None, []

def send_email(markdown_content):
    """【完全保留】支持多收件人，专业HTML渲染，兼容QQ邮箱"""
    email_html = markdown_to_html_document(markdown_content)
    
    # 支持多收件人，英文逗号分隔
    receiver_list = [email.strip() for email in RECEIVER_EMAIL.split(',')]
    
    # QQ邮箱完全兼容的邮件配置
    message = MIMEText(email_html, 'html', 'utf-8')
    message['From'] = SENDER_EMAIL
    message['To'] = RECEIVER_EMAIL
    message['Subject'] = Header(f"{today_str} 每日AI专属日报", 'utf-8')

    try:
        print("✅ 开始发送邮件，收件人：", receiver_list)
        smtp_obj = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30)
        smtp_obj.login(SENDER_EMAIL, EMAIL_AUTH_CODE)
        smtp_obj.sendmail(SENDER_EMAIL, receiver_list, message.as_string())
        smtp_obj.quit()
        print("✅ 邮件发送成功，已推送至所有收件人")
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败：{e}")
        return False

# ================= 主程序入口（完全保留原有逻辑） =================
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
        print("❌ 资讯生成失败，任务终止")
        exit(1)
    
    send_email(news_content)
    
    # 更新去重库
    if new_fingerprints:
        updated_blacklist = blacklist + new_fingerprints
        save_blacklist(updated_blacklist)
        print(f"✅ 永久去重库已更新，新增 {len(new_fingerprints)} 条，总计 {len(updated_blacklist)} 条")
