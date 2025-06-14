
import os
import json
import random
import threading
from flask import Flask, request, abort
from tarot import draw_tarot_cards
from openai import OpenAI
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    TemplateSendMessage, ButtonsTemplate, PostbackAction, PostbackEvent,
    FlexSendMessage, URIAction
)

app = Flask(__name__)
client = OpenAI()
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
user_states = {}

# GPT 塔羅解讀
def generate_tarot_reply(user_question, topic="一般"):
    try:
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
    except Exception:
        return "占卜過程發生錯誤，請稍後再試～"

# Webhook
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 主題 Flex
def send_flex_menu(event):
    flex_content = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "選擇塔羅占卜主題", "weight": "bold", "size": "lg", "align": "center"},
                {"type": "box", "layout": "vertical", "margin": "lg", "spacing": "sm", "contents": [
                    {"type": "button", "action": {"type": "postback", "label": "💘 愛情", "data": "topic=愛情"}, "style": "primary"},
                    {"type": "button", "action": {"type": "postback", "label": "💼 事業", "data": "topic=事業"}, "style": "primary"},
                    {"type": "button", "action": {"type": "postback", "label": "❤️‍🩹 健康", "data": "topic=健康"}, "style": "primary"},
                ]}
            ]
        }
    }
    line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="請選擇塔羅占卜主題", contents=flex_content))

# 處理文字訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.lower()

    if user_id in user_states and "topic" in user_states[user_id]:
        topic = user_states[user_id].pop("topic")
        user_question = event.message.text

        line_bot_api.reply_message(event.reply_token, [
            TextSendMessage(text="🔮 占卜師正在洗牌中..."),
            TextSendMessage(text="🃏 正在抽出三張牌...")
        ])

        def send_result():
            reply = generate_tarot_reply(user_question, topic)
            result_messages = [
                TextSendMessage(text=reply),
                TemplateSendMessage(
                    alt_text="分享占卜結果",
                    template=ButtonsTemplate(
                        text="想跟朋友分享這次占卜結果嗎？",
                        actions=[URIAction(label="🔗 點我分享", uri="https://line.me")]
                    )
                )
            ]
            line_bot_api.push_message(user_id, result_messages)

        threading.Thread(target=send_result).start()
        return

    if any(word in text for word in ["抽卡", "占卜"]):
        send_flex_menu(event)
        return

    if text in ["你好", "嗨", "hi", "hello", "在嗎"]:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🌴 歡迎來到塔羅占卜 AI！輸入「抽卡」或「占卜」來開始抽牌喔～"))
        return

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="您好～請輸入「抽卡」、「抽愛情」、「抽事業」來開始塔羅占卜喔！"))

# 處理按鈕點擊
@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    if data.startswith("topic="):
        topic = data.replace("topic=", "")
        user_states[user_id] = {"topic": topic}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"請問你想針對「{topic}」方面問什麼問題呢？"))
