import os
import json
import openai
import random
from flask import Flask, request, abort, jsonify
from tarot import draw_tarot_cards
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# 初始化 Flask & 金鑰
app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# 🔮 占卜邏輯：GPT 解讀三張牌
def generate_tarot_reply(user_question):
    cards = draw_tarot_cards(num=3)
    descriptions = [
        f"{idx+1}. {card['name']}（{card['position']}）：{card[card['position']]}"
        for idx, card in enumerate(cards)
    ]

    prompt = f"""你是一位溫柔神秘的塔羅占卜師。
使用者問：「{user_question}」
你抽到了以下三張塔羅牌：
{chr(10).join(descriptions)}
請根據牌義與提問給出占卜建議。"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message['content']

# ✅ API 測試端點（可用 curl/postman 測試）
@app.route("/ask", methods=["POST"])
def ask_tarot():
    user_question = request.json.get("question", "")
    return jsonify({"reply": generate_tarot_reply(user_question)})

# ✅ LINE webhook 端點
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

# ✅ 處理 LINE 傳入訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text
    reply = generate_tarot_reply(user_text)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

# ✅ 主程式入口（本地開發用）
if __name__ == "__main__":
    app.run(debug=True)
