import os
import json
import random
from flask import Flask, request, abort
from tarot import draw_tarot_cards
from openai import OpenAI
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    TemplateSendMessage, ButtonsTemplate, PostbackAction, PostbackEvent,
    FlexSendMessage, ImageSendMessage, URIAction
)

app = Flask(__name__)
client = OpenAI()
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
user_states = {}  # 儲存使用者狀態

# 產生塔羅解讀文字
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
    return response.choices[0].message.content, cards[0]['image_url'] if 'image_url' in cards[0] else None

# Webhook 設定
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# Flex Bubble 主題選單
def send_flex_menu(event):
    flex_content = {
        "type": "bubble",
       "hero": {
  "type": "image",
  "url": "https://i.imgur.com/Xyoeml7.png",  # ✅ 新黑金星座風格圖
  "size": "full",
  "aspectRatio": "20:13",
  "aspectMode": "cover"
}
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "選擇塔羅占卜主題", "weight": "bold", "size": "lg"},
                {"type": "box", "layout": "vertical", "margin": "lg", "spacing": "sm", "contents": [
                    {"type": "button", "action": {"type": "postback", "label": "💘 愛情", "data": "topic=愛情"}, "style": "primary"},
                    {"type": "button", "action": {"type": "postback", "label": "💼 事業", "data": "topic=事業"}, "style": "primary"},
                    {"type": "button", "action": {"type": "postback", "label": "❤️‍🩹 健康", "data": "topic=健康"}, "style": "primary"}
                ]}
            ]
        }
    }
    line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="請選擇塔羅占卜主題", contents=flex_content))

# 文字訊息事件處理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.lower()

    # 如果使用者之前選過主題，現在輸入的是問題內容
    if user_id in user_states and "topic" in user_states[user_id]:
        topic = user_states[user_id].pop("topic")
        user_question = event.message.text
        reply_text, image_url = generate_tarot_reply(user_question, topic)
        messages = [TextSendMessage(text=reply_text)]
        if image_url:
            messages.insert(0, ImageSendMessage(
                original_content_url=image_url,
                preview_image_url=image_url
            ))
        messages.append(TemplateSendMessage(
            alt_text="分享占卜結果",
            template=ButtonsTemplate(
                text="想跟朋友分享這次占卜結果嗎？",
                actions=[
                    URIAction(label="\ud83d\udd17 點我分享", uri="https://line.me")
                ]
            )
        ))
        line_bot_api.reply_message(event.reply_token, messages)
        return

    # 啟動畫面輸入
    if any(word in text for word in ["抽卡", "占卜"]):
        send_flex_menu(event)
        return

    # 問候引導
    if text in ["你好", "嗨", "hi", "hello", "在嗎"]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="\ud83c\udf34 歡迎來到塔羅占卜 AI！輸入「抽卡」或「占卜」來開始抽牌喔～")
        )
        return

    # 其他訊息 fallback
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="您好～請輸入「抽卡」、「抽愛情」、「抽事業」來開始塔羅占卜喔！")
    )

# Flex 選單點擊後處理
@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    if data.startswith("topic="):
        topic = data.replace("topic=", "")
        user_states[user_id] = {"topic": topic}
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"請問你想針對「{topic}」方面問什麼問題呢？")
        )
