import gradio as gr
import google.generativeai as genai
import os

# Замените "YOUR_GOOGLE_API_KEY" на свой реальный API-ключ Gemini
GOOGLE_API_KEY = "AIzaSyDjUIyiqsZXoXSnCjHb7ofXiZzJY_F62G0"
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# Инициализируем модель
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel('gemini-2.0-flash-thinking-exp-1219')

def generate_gemini_response(prompt):
    """
    Отправляет запрос к Gemini API с заданным промптом и возвращает ответ.

    Args:
        prompt: Текст запроса.

    Returns:
        Строка: Ответ от Gemini API или сообщение об ошибке.
    """
    try:
      response = model.generate_content(prompt)
      if response and response.text:
          return response.text
      else:
          return "Не удалось получить ответ от Gemini API"
    except Exception as e:
        return f"Ошибка при запросе к Gemini API: {e}"

def chat(message, history):
    """
    Функция для обработки взаимодействия с пользователем и API.

    Args:
        message: Текст сообщения пользователя.
        history: Список истории диалога.

    Returns:
      List: обновленная история диалога в формате, ожидаемом Gradio.
    """

    history = history or []
    api_response = generate_gemini_response(message)
    history.append({"content": message, "role": "user"})
    history.append({"content": api_response, "role": "assistant"})
    return history


iface = gr.ChatInterface(
    fn=chat,
    chatbot=gr.Chatbot(),
    textbox=gr.Textbox(),
    title="Чат с Gemini через API",
    description="Введите ваш вопрос или сообщение."
)

iface.launch(debug=True)