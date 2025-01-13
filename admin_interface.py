import streamlit as st
import json
import os
from datetime import datetime
import requests
import pandas as pd
import plotly.express as px

# Настройка страницы должна быть первой командой
st.set_page_config(
    page_title="News Bot Admin",
    page_icon="🤖",
    layout="wide"
)

# Константы
TELEGRAM_TOKEN = "7933377403:AAG5k7ryxq45aH5RrPGb1ipuoSpVq--vxpw"
NEWS_API_KEY = "e680b2dfdf70401298769475d956616c"

# Категории и страны
CATEGORIES = ['general', 'business', 'technology', 'science', 'health', 'sports', 'entertainment']
COUNTRIES = {
    'ru': 'Россия', 
    'us': 'США', 
    'gb': 'Великобритания', 
    'de': 'Германия',
    'fr': 'Франция', 
    'it': 'Италия', 
    'es': 'Испания'
}

def custom_css():
    """Add custom CSS"""
    st.markdown("""
        <style>
        .stApp {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
        }
        .stButton button {
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
        }
        .stButton button:hover {
            background-color: #45a049;
        }
        .stTextInput input {
            background-color: rgba(255, 255, 255, 0.1);
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .stSelectbox select {
            background-color: rgba(255, 255, 255, 0.1);
            color: white;
        }
        .stDataFrame {
            background-color: rgba(255, 255, 255, 0.05);
        }
        .css-1d391kg {
            background-color: rgba(255, 255, 255, 0.05);
        }
        </style>
    """, unsafe_allow_html=True)

def load_config():
    """Load bot configuration"""
    if os.path.exists("bot_config.json"):
        with open("bot_config.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"channels": {}, "post_history": []}

def save_config(config):
    """Save bot configuration"""
    try:
        # Создаем резервную копию текущей конфигурации
        if os.path.exists("bot_config.json"):
            backup_name = f"bot_config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            os.rename("bot_config.json", backup_name)
        
        # Сохраняем новую конфигурацию
        with open("bot_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
            
    except Exception as e:
        st.error(f"Ошибка при сохранении конфигурации: {str(e)}")
        # Восстанавливаем из резервной копии если что-то пошло не так
        if 'backup_name' in locals():
            os.rename(backup_name, "bot_config.json")

def get_news_sources():
    """Get available news sources from NewsAPI"""
    url = f"https://newsapi.org/v2/sources?apiKey={NEWS_API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        if data["status"] == "ok":
            return {source["id"]: source["name"] for source in data["sources"]}
        return {}
    except Exception as e:
        st.error(f"Error fetching news sources: {e}")
        return {}

def read_logs(max_lines=100):
    """Read last N lines from the log file"""
    log_file = os.path.join('logs', 'bot_logs.txt')
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            return list(reversed(lines[-max_lines:]))  # Разворачиваем список, чтобы новые логи были вверху
    except FileNotFoundError:
        return ["Лог-файл пока не создан"]
    except Exception as e:
        return [f"Ошибка чтения лога: {e}"]

def format_channel_id(channel_id):
    """Format channel ID to proper format"""
    if not channel_id:
        return None
    if channel_id.startswith('https://t.me/'):
        channel_id = '@' + channel_id.split('/')[-1]
    elif not channel_id.startswith('@'):
        channel_id = '@' + channel_id
    return channel_id

def show_dashboard(config):
    """Show dashboard with statistics"""
    st.header("📊 Дашборд")
    
    # Статистика
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Активные каналы", len(config["channels"]))
    with col2:
        total_posts = len(config.get("post_history", []))
        st.metric("Всего постов", total_posts)
    with col3:
        today_posts = len([
            p for p in config.get("post_history", [])
            if datetime.fromisoformat(p["timestamp"]).date() == datetime.now().date()
        ])
        st.metric("Постов сегодня", today_posts)
    
    # График активности
    if config.get("post_history"):
        df = pd.DataFrame(config["post_history"])
        df["date"] = pd.to_datetime(df["timestamp"]).dt.date
        posts_by_date = df.groupby("date").size().reset_index(name="posts")
        fig = px.line(posts_by_date, x="date", y="posts", title="Активность постов по дням")
        st.plotly_chart(fig, use_container_width=True)

def show_api_stats():
    """Show API usage statistics"""
    st.header("📊 Статистика API")
    
    if 'api_stats' in st.session_state and st.session_state.api_stats:
        stats = st.session_state.api_stats
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "NewsAPI",
                f"{stats['newsapi']['total_calls']} вызовов",
                f"{stats['newsapi']['calls_per_hour']}/час"
            )
            
        with col2:
            st.metric(
                "Gemini AI",
                f"{stats['gemini']['total_calls']} вызовов",
                f"{stats['gemini']['calls_per_hour']}/час"
            )
            
        with col3:
            st.metric(
                "Telegram",
                f"{stats['telegram']['total_calls']} вызовов",
                f"{stats['telegram']['calls_per_hour']}/час"
            )
            
        # График использования API
        df = pd.DataFrame({
            'API': ['NewsAPI', 'Gemini AI', 'Telegram'],
            'Вызовов': [
                stats['newsapi']['total_calls'],
                stats['gemini']['total_calls'],
                stats['telegram']['total_calls']
            ]
        })
        
        fig = px.bar(
            df,
            x='API',
            y='Вызовов',
            title='Использование API',
            color='API',
            color_discrete_sequence=['#00ff00', '#ff0000', '#0000ff']
        )
        
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='white'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Статистика API пока недоступна")

def show_channel_list(config):
    """Show list of configured channels"""
    st.header("📺 Управление каналами")
    
    channels = config.get("channels", {})
    channels_to_delete = []
    
    for name, info in channels.items():
        with st.expander(f"📌 {name} ({info['channel_id']})"):
            # Добавляем кнопку удаления с подтверждением
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("🗑️ Удалить канал", key=f"delete_channel_{name}_{info['channel_id']}", type="primary"):
                    # Удаляем канал из конфигурации
                    if name in config["channels"]:
                        del config["channels"][name]
                        
                        # Очищаем историю постов для этого канала
                        config["post_history"] = [
                            post for post in config.get("post_history", [])
                            if post.get("channel") != name
                        ]
                        
                        # Сохраняем изменения
                        save_config(config)
                        st.success(f"Канал {name} успешно удален!")
                        st.rerun()
            
            with col1:
                info['active'] = st.checkbox(
                    "✅ Активен",
                    value=info.get('active', True),
                    key=f"active_{name}"
                )
                
                info['country'] = st.selectbox(
                    "🌍 Страна",
                    options=[''] + list(COUNTRIES.keys()),
                    format_func=lambda x: COUNTRIES.get(x, 'Все страны') if x else 'Все страны',
                    key=f"country_{name}",
                    index=list(COUNTRIES.keys()).index(info.get('country')) if info.get('country') in COUNTRIES else 0
                )
                
                # Множественный выбор категорий
                selected_categories = st.multiselect(
                    "📚 Категории",
                    options=CATEGORIES,
                    default=info.get('categories', []),
                    format_func=lambda x: x.capitalize(),
                    key=f"categories_{name}"
                )
                info['categories'] = selected_categories
            
            with col2:
                sources = get_news_sources()
                # Преобразуем строку sources в список, удаляя пустые значения
                default_sources = [s.strip() for s in info.get('sources', '').split(',') if s.strip()] if info.get('sources') else []
                # Фильтруем sources, оставляя только те, которые есть в списке доступных
                default_sources = [s for s in default_sources if s in sources]
                
                selected_sources = st.multiselect(
                    "📰 Источники новостей",
                    options=list(sources.keys()),
                    default=default_sources,
                    format_func=lambda x: f"{x} ({sources[x]})",
                    key=f"sources_{name}"
                )
                info['sources'] = ','.join(selected_sources) if selected_sources else None
                
                info['query'] = st.text_input(
                    "🔍 Ключевые слова (через запятую)",
                    value=info.get('query', ''),
                    key=f"query_{name}"
                )
            
            # Системный промпт
            info['system_prompt'] = st.text_area(
                "🤖 Системный промпт для AI",
                value=info.get('system_prompt', """
                Ты - профессиональный редактор новостного Telegram-канала. 
                Твоя задача - создавать краткие, информативные и вовлекающие посты.
                Используй современный разговорный стиль, добавляй эмодзи и хэштеги.
                """).strip(),
                key=f"prompt_{name}",
                height=100
            )
            
            col3, col4 = st.columns(2)
            with col3:
                info['max_posts_per_day'] = st.number_input(
                    "📊 Максимум постов в день",
                    min_value=1,
                    max_value=48,
                    value=info.get('max_posts_per_day', 10),
                    key=f"max_posts_{name}"
                )
                
                info['post_interval'] = st.number_input(
                    "⏱️ Интервал между постами (минуты)",
                    value=info.get('post_interval', 30),
                    key=f"interval_{name}"
                )
            
            with col4:
                info['quiet_hours'] = st.checkbox(
                    "🌙 Тихие часы (23:00 - 07:00)",
                    value=info.get('quiet_hours', True),
                    key=f"quiet_hours_{name}"
                )
                
                info['stop_words'] = st.text_input(
                    "🚫 Стоп-слова (через запятую)",
                    value=info.get('stop_words', ''),
                    key=f"stop_words_{name}"
                )
            
            col5, col6 = st.columns(2)
            with col5:
                if st.button("💾 Сохранить", key=f"save_{name}"):
                    config["channels"][name].update(info)
                    save_config(config)
                    st.success("✅ Настройки сохранены!")
            
            with col6:
                if st.button("🗑️ Удалить канал", key=f"delete_{name}"):
                    if st.session_state.get(f"confirm_delete_{name}"):
                        del config["channels"][name]
                        save_config(config)
                        st.success("Канал удален!")
                        st.rerun()
                    else:
                        st.session_state[f"confirm_delete_{name}"] = True
                        st.warning("Нажмите еще раз для подтверждения удаления")
    
    # Удаляем отмеченные каналы
    if channels_to_delete:
        for name in channels_to_delete:
            del config["channels"][name]
        save_config(config)
        st.rerun()

def show_add_channel():
    """Show form for adding new channel"""
    st.header("➕ Добавить канал")
    
    with st.form("add_channel_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Название канала")
            channel_id = st.text_input("ID канала (например: @channel_name)")
            country = st.selectbox(
                "🌍 Страна",
                options=[''] + list(COUNTRIES.keys()),
                format_func=lambda x: COUNTRIES.get(x, 'Все страны') if x else 'Все страны'
            )
            
            # Множественный выбор категорий
            selected_categories = st.multiselect(
                "📚 Категории",
                options=CATEGORIES,
                format_func=lambda x: x.capitalize()
            )
        
        with col2:
            sources = get_news_sources()
            selected_sources = st.multiselect(
                "📰 Источники новостей",
                options=list(sources.keys()),
                format_func=lambda x: f"{x} ({sources[x]})"
            )
            
            query = st.text_input("🔍 Ключевые слова (через запятую)")
            page_size = st.number_input("📊 Количество новостей", min_value=1, max_value=100, value=20)
            active = st.checkbox("🔓 Активен", value=True)
        
        submitted = st.form_submit_button("Добавить канал")
        
        if submitted:
            if name and channel_id:
                config = load_config()
                channel_id = format_channel_id(channel_id)
                
                config["channels"][name] = {
                    "channel_id": channel_id,
                    "country": country if country else None,
                    "categories": selected_categories,
                    "sources": ','.join(selected_sources) if selected_sources else None,
                    "query": query if query else None,
                    "page_size": page_size,
                    "active": active
                }
                
                save_config(config)
                st.success(f"✅ Канал {name} добавлен!")
                st.rerun()
            else:
                st.error("❌ Название и ID канала обязательны!")

def show_post_history(config):
    """Show post history"""
    st.header("📝 История постов")
    
    if not config.get("post_history"):
        st.info("История постов пуста")
        return
    
    # Фильтры
    col1, col2 = st.columns(2)
    with col1:
        channel_filter = st.multiselect(
            "Фильтр по каналам",
            options=list(config["channels"].keys())
        )
    
    with col2:
        date_filter = st.date_input("Фильтр по дате")
    
    # Отображение истории
    history = config["post_history"]
    if channel_filter:
        history = [p for p in history if p["channel"] in channel_filter]
    if date_filter:
        history = [
            p for p in history 
            if datetime.fromisoformat(p["timestamp"]).date() == date_filter
        ]
    
    if history:
        df = pd.DataFrame(history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp', ascending=False)
        st.dataframe(df)

def show_logs():
    """Show bot logs"""
    st.header("📝 Логи бота")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        max_lines = st.slider("Количество строк", min_value=10, max_value=1000, value=100, step=10)
    
    with col2:
        auto_refresh = st.checkbox("Автообновление", value=True)
    
    # Контейнер для логов
    logs_container = st.empty()
    
    def update_logs():
        logs = read_logs(max_lines)
        logs_container.code('\n'.join(logs), language='text')
    
    # Кнопка обновления
    if st.button("🔄 Обновить логи"):
        update_logs()
    
    # Автообновление
    if auto_refresh:
        update_logs()

def main():
    custom_css()
    
    # Боковое меню
    st.sidebar.title("🤖 News Bot Admin")
    menu = st.sidebar.radio(
        "Меню",
        ["📊 Дашборд", "📊 Статистика API", "📺 Управление каналами", "➕ Добавить канал", 
         "📝 История постов", "📝 Логи"]
    )
    
    # Загружаем конфигурацию
    config = load_config()
    
    # Основной контент
    if menu == "📊 Дашборд":
        show_dashboard(config)
    
    elif menu == "📊 Статистика API":
        show_api_stats()
    
    elif menu == "📺 Управление каналами":
        show_channel_list(config)
    
    elif menu == "➕ Добавить канал":
        show_add_channel()
    
    elif menu == "📝 История постов":
        show_post_history(config)
    
    elif menu == "📝 Логи":
        show_logs()

if __name__ == "__main__":
    main()
