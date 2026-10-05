import asyncio
import aiohttp
import random
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup, Tag
from typing import Dict, Any

# Загружаем переменные окружения
load_dotenv()

SMS_API_KEY: str | None = os.getenv("SMS_API_KEY")
MY_PHONE: str | None = os.getenv("MY_PHONE")
KWORK_COOKIES: str | None = os.getenv("KWORK_COOKIES")

KWORK_INBOX_URL: str = "https://kwork.ru/inbox"
CHECK_INTERVAL: int = 60

USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
]

last_notified_msg_id: str = ""

async def send_sms(session: aiohttp.ClientSession, text: str) -> None:
    """Асинхронная отправка СМС через API-шлюз SMS.ru"""
    if not SMS_API_KEY or not MY_PHONE:
        print("[🔴 СМС] Ошибка: Настройки СМС не найдены в файле .env!")
        return
    url = "https://sms.ru/sms/send"
    params: Dict[str, str | int] = {"api_id": SMS_API_KEY, "to": MY_PHONE, "msg": text, "json": 1}
    try:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                res_json: Dict[str, Any] = await response.json()
                if res_json.get("status") == "OK":
                    print(f"[🟢 СМС] Уведомление успешно отправлено на номер +{MY_PHONE}")
    except Exception as e:
        print(f"[🔴 СМС] Ошибка отправки сообщения: {e}")

def check_unread_messages(html: str) -> Tag | None:
    """Поиск элемента непрочитанного сообщения в DOM-дереве страницы"""
    soup = BeautifulSoup(html, "lxml")
    return soup.find("li", class_="chat__list-item_unread")

async def main() -> None:
    global last_notified_msg_id
    print("[🚀 Система] Бот личных чатов запущен. Мониторинг /inbox активирован...")
    
    if not KWORK_COOKIES:
        print("[🔴 Ошибка] Переменная KWORK_COOKIES не задана в файле .env! Работа невозможна.")
        return
    
    while True:
        current_headers: Dict[str, str] = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Cookie": KWORK_COOKIES 
        }
        await asyncio.sleep(random.uniform(1.0, 3.0))
        
        try:
            async with aiohttp.ClientSession(headers=current_headers) as session:
                async with session.get(KWORK_INBOX_URL, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    if response.status == 403:
                        print("[⚠️ Защита] Cloudflare заблокировал запрос (403). Нужна свежая сессия куки!")
                        await asyncio.sleep(CHECK_INTERVAL)
                        continue
                    
                    html: str = await response.text()
                    if "chat__list" not in html and "inbox" not in response.url.path:
                        print("[⚠️ Авторизация] Куки устарели или неверные. Бот видит только страницу входа!")
                        await asyncio.sleep(CHECK_INTERVAL)
                        continue
                    
                    unread_dialog: Tag | None = await asyncio.to_thread(check_unread_messages, html)
                    
                    if unread_dialog and unread_dialog.has_attr("data-id"):
                        current_msg_id: str = str(unread_dialog["data-id"])
                        
                        if current_msg_id != last_notified_msg_id:
                            last_notified_msg_id = current_msg_id
                            sender: str = unread_dialog.find("span", class_="chat__list-item-name").text.strip() # type: ignore
                            print(f"[🔥 ВНИМАНИЕ] Новое сообщение от заказчика: {sender}!")
                            await send_sms(session, f"Kwork ЛС! Новый диалог с: {sender}")
                    else:
                        print("[💤 Мониторинг] Новых сообщений в чатах нет. Все клиенты прочитаны.")
        except Exception as e:
            print(f"[❌ Сбой] Ошибка мониторинга чатов: {e}")
            
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
