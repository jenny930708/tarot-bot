from flask import Flask, request, jsonify
import openai
from tarot import draw_tarot_cards

app = Flask(__name__)

# ✅ 請在這裡填入你的 OpenAI API 金鑰
openai.api_key = "你的 OpenAI API Key"

@app.route("/ask", methods=["POST"])
def ask_tarot():
    user_question = request.json.get("question", "")
    cards = draw_tarot_cards(num=3)

    # 整理牌面描述
    card_descriptions = []
    for idx, card in enumerate(cards, start=1):
        description = f"{idx}. {card['name']}（{card['position']}）：{card[card['position']]}"
        card_descriptions.append(description)

    prompt = f"""
你是一位溫柔神秘的塔羅占卜師，擅長解讀塔羅牌給人建議。
使用者問：「{user_question}」
你抽到了以下三張塔羅牌：
{chr(10).join(card_descriptions)}

請根據使用者的問題與牌義，給出占卜解釋與建議。
"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    reply = response.choices[0].message['content']
    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(debug=True)
