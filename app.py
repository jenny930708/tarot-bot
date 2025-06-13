import os
import json
import random
from flask import Flask, request, abort, jsonify
from tarot import draw_tarot_cards
from openai import OpenAI
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    TemplateSendMessage, ButtonsTemplate, PostbackAction, PostbackEvent
)

# 初始化
app = Flask(__name__)
client = OpenAI()
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# GPT 塔羅解讀邏輯
def generate_tarot_reply(user_question, topic="一般"):
    cards = draw_tarot_cards(num=3)
    descriptions = [
        f"{idx+1}. {card['name']}（{card['position']}）：{card[card['position']]}"
        for idx, card in enumerate(cards)
    ]
    prompt = f"""你是一位溫柔神秘的塔羅占卜師。
使用者問：「{user_question}」（主題：{topic}）
你抽到了以下三張塔羅牌：
{chr(10).join(descriptions)}
請針對「{topic}」主題給出塔羅牌解讀與實用建議。
"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# 抽牌 API（給 curl / Postman 測試用）
@app.route("/ask", methods=["POST"])
def ask_tarot():
    user_question = request.json.get("question", "")
    topic = request.json.get("topic", "一般")
    return jsonify({"reply": generate_tarot_reply(user_question, topic)})

# LINE webhook
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 文字訊息處理：觸發按鈕選單或回覆提示
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.lower()

    # 初次問候、引導語
    greetings = ["你好", "嗨", "hi", "hello", "在嗎", "安安", "哈囉"]
    if any(greet in text for greet in greetings):
        reply = "🎴 歡迎使用塔羅占卜師 AI！\n請輸入「抽卡」或「占卜」開始塔羅問答，也可以直接說「抽愛情」、「抽事業」來快速占卜哦！"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # 自然語意引導（不是關鍵字但看起來像是想占卜）
    trigger_words = ["最近", "壓力", "怎麼辦", "想問", "幫我看", "有困擾", "想占卜", "想抽"]
    if any(word in text for word in trigger_words):
        reply = "你是不是有想問的問題呢？請輸入「抽卡」開始，或直接輸入「抽愛情」、「抽事業」來占卜特定方向 🔮"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # 抽卡選單觸發
    if "抽卡" in text or "占卜" in text:
        button_template = ButtonsTemplate(
            title="請選擇想要占卜的主題：",
            text="點選下方主題即可開始占卜 🔮",
            actions=[
                PostbackAction(label="愛情", data="topic=愛情"),
                PostbackAction(label="事業", data="topic=事業"),
                PostbackAction(label="健康", data="topic=健康")
            ]
        )
        message = TemplateSendMessage(
            alt_text="請選擇占卜主題：愛情 / 事業 / 健康",
            template=button_template
        )
        line_bot_api.reply_message(event.reply_token, message)
        return

    # 直接輸入「抽愛情」等主題
    if "抽愛情" in text:
        topic = "愛情"
    elif "抽事業" in text:
        topic = "事業"
    elif "抽健康" in text:
        topic = "健康"
    else:
        topic = None

    if topic:
        reply = generate_tarot_reply(f"請幫我占卜{topic}方面的狀況", topic)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # 其他一般訊息 fallback
    reply = "您好 😊 若想要進行塔羅占卜，請輸入「抽卡」或「抽愛情 / 抽事業 / 抽健康」等主題來開始 🔮"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))


# 按鈕選單點擊後處理（Postback）
@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    if data.startswith("topic="):
        topic = data.replace("topic=", "")
        reply = generate_tarot_reply(f"請幫我占卜{topic}方面的狀況", topic)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
