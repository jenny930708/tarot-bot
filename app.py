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
    else:
        # 一般聊天
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="歡迎使用塔羅占卜師！請輸入「抽卡」或「占卜」來開始使用 😊")
        )

# 按鈕選單點擊後處理（Postback）
@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    if data.startswith("topic="):
        topic = data.replace("topic=", "")
        reply = generate_tarot_reply(f"請幫我占卜{topic}方面的狀況", topic)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
