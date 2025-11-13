from flask import Flask, request, jsonify
import os
from google import genai

# ==== CẤU HÌNH ====
app = Flask(__name__)
API_KEY = "AIzaSyCgFHdqnTebppZo71q1MDfDNtgk1T7jfzo"

if not API_KEY:
    raise SystemExit("⚠️  Bạn cần đặt biến môi trường GEMINI_API_KEY trước khi chạy.")

client = genai.Client(api_key=API_KEY)

# ==== API CHAT ====
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    msg = data.get("message", "")
    if not msg:
        return jsonify({"error": "Thiếu message"}), 400

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=msg
        )
        return jsonify({"reply": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==== GIAO DIỆN WEB CỰC NHANH ====
@app.route("/")
def index():
    return """
    <!doctype html>
    <html>
      <head><meta charset='utf-8'><title>Gemini Chatbot</title></head>
      <body>
        <h2>💬 Chatbot Gemini</h2>
        <div id='chat'></div>
        <input id='msg' placeholder='Nhập tin nhắn...' style='width:300px'>
        <button onclick='send()'>Gửi</button>
        <script>
          async function send() {
            const msg = document.getElementById('msg').value.trim();
            if(!msg) return;
            const chat = document.getElementById('chat');
            chat.innerHTML += `<p><b>Bạn:</b> ${msg}</p>`;
            document.getElementById('msg').value = '';
            const res = await fetch('/chat', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({message: msg})
            });
            const data = await res.json();
            chat.innerHTML += `<p><b>Bot:</b> ${data.reply || data.error}</p>`;
          }
        </script>
      </body>
    </html>
    """


if __name__ == "__main__":
    app.run(port=3000, debug=True)
