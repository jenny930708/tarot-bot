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
    FlexSendMessage, PostbackEvent, ImageSendMessage
)

app = Flask(__name__)
client = OpenAI()
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
user_states = {}  # 儲存使用者狀態

# 產生塔羅解讀文字（繁體中文）
def generate_tarot_reply(user_question, topic="一般"):
    cards = draw_tarot_cards(num=3)
    descriptions = [
        f"{idx+1}. {card['name']}（{card['position']}）：{card[card['position']]}"
        for idx, card in enumerate(cards)
    ]
    prompt = f"""你是一位溫柔神秘的塔羅占卜師，請用繁體中文回應。
使用者問：「{user_question}」（主題：{topic}）
你抽到了以下三張塔羅牌：
{chr(10).join(descriptions)}
請針對「{topic}」主題給出塔羅牌解讀與實用建議。
"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    image_urls = [card.get('image_url') for card in cards if card.get('image_url')]
    return response.choices[0].message.content, image_urls

# 判斷是否是情緒或聊天訊息
def is_emotional_message(text):
    emotional_keywords = ["心情", "不開心", "好累", "可以陪我", "聊聊", "情緒", "想哭", "壓力", "煩", "孤單"]
    return any(kw in text for kw in emotional_keywords)

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

# Flex Bubble 主題選單（無 hero）
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
                    {"type": "button", "action": {"type": "postback", "label": "❤️‍🩹 健康", "data": "topic=健康"}, "style": "primary"}
                ]}
            ]
        }
    }
    line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="請選擇塔羅占卜主題", contents=flex_content))

# 背景線程延遲處理塔羅占卜
def delayed_tarot(user_id, user_question, topic):
    reply_text, image_urls = generate_tarot_reply(user_question, topic)
    messages = [ImageSendMessage(original_content_url=url, preview_image_url=url) for url in image_urls]
    messages.append(TextSendMessage(text=reply_text))
    line_bot_api.push_message(user_id, messages)

# 文字訊息事件處理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # 如果使用者先前選擇了主題，現在輸入的是問題內容
    if user_id in user_states and "topic" in user_states[user_id]:
        topic = user_states[user_id].pop("topic")
        user_question = event.message.text
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🔮 占卜師正在洗牌並抽牌中..."))
        threading.Thread(target=delayed_tarot, args=(user_id, user_question, topic)).start()
        return

    # 每日運勢觸發
    if "每日運勢" in text or "今日運勢" in text:
        horoscope_prompt = "請給我今日的幸運運勢建議，請用繁體中文，語氣溫暖，內容精簡溫馨。"
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": horoscope_prompt}]
        )
        reply_text = response.choices[0].message.content
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    # 情緒關心模式
    if is_emotional_message(text):
        reply = "聽起來你有些情緒在心中，我在這裡陪你。想說說是什麼讓你這麼煩嗎？或是你想要抽張塔羅牌看看現在的狀況？輸入「抽卡」也可以開始占卜唷。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # 啟動畫面輸入
    if any(word in text for word in ["抽卡", "占卜"]):
        send_flex_menu(event)
        return

    # 問候引導
    if text in ["你好", "嗨", "hi", "hello", "在嗎"]:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🌴 歡迎來到塔羅占卜 AI！輸入「抽卡」或「占卜」來開始抽牌喔～"))
        return

    # 一般聊天回應（繁體中文）
    prompt = f"請用繁體中文友善回答以下訊息：{text}"
    reply = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    reply_text = reply.choices[0].message.content
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

# Flex 選單點擊後處理
@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    if data.startswith("topic="):
        topic = data.replace("topic=", "")
        user_states[user_id] = {"topic": topic}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"請問你想針對「{topic}」方面問什麼問題呢？"))
