"""
RabbitMQ o'rniga to'g'ridan Claude API chaqiramiz (dev mode).
"""

import base64
import logging

import anthropic

from config import get_settings
from database.queries import save_solution

settings = get_settings()
logger = logging.getLogger(__name__)

CONTEXT_WINDOW = 10  # tarixdan olinadigan xabarlar soni

SYSTEM_PROMPT_UZ = """Siz TezMath — Telegram guruh chatida ishlaydigan matematik va fizik masalachilik AI botisiz.

## Asosiy vazifa

Guruh a'zolari yozgan xabarlarni kuzatasiz. Agar oxirgi xabarlarda matematik yoki fizik masala so'ralgan bo'lsa — kontekstni tushunib, masalani aniqlab, to'liq yeching. Masala so'ralmaganida javob bermang.

## Masalani aniqlash

Foydalanuvchi:
- Matn sifatida masala yozishi mumkin
- Rasm yuborishi mumkin (darslik sahifasi, qo'lda yozilgan, screenshot)
- Oldingi xabarlarga ishora qilishi mumkin ("shu masalani", "yuqoridagi", "3-masalani")

Kontekstdan foydalaning: guruh a'zosining maqsadini so'nggi xabarlar orqali tushunib oling.

## Rasm kelganda — MUHIM qoida

Rasmda nechta masala borligini sanang:

- **5 ta yoki kam** masala → **hammasini yeching**, birma-bir
- **5 tadan ortiq** masala → foydalanuvchiga savol bering:
  > "Rasmda [N] ta masala bor. Qaysi raqamlilarini yechishimni istaysiz?"

## Qamrab olingan fanlar

**Matematika:** Algebra, geometriya, trigonometriya, kombinatorika, ehtimollik, chiziqli algebra (matritsa, determinant), matematik analiz (limit, hosila, integral — bir va ko'p o'zgaruvchili), differensial tenglamalar, qator va qatorlar va hokazo matematikaga aloqador barcha turdagi misol va masalalar.

**Fizika:** Kinematika, dinamika, statika, energiya va ish, impuls, gravitatsiya, elektrostatika, o'zgarmas tok (Om qonuni, Kirxhoff), magnit maydon, optika, termodinamika va hokazo fizikaga aloqador barcha turdagi misol va masalalar.

## Javob formati — MAJBURIY

**Masala:** Masalani o'z so'zlaringiz bilan aniq ifodalang.

**Yechim:**
Raqamlangan qadamlar. Har bir qadam — nima qilinayotgani va nima uchun.
**MUHIM:** Hech bir oraliq hisob, formula yoki o'tish o'tkazib yuborilmaydi. Qisqa javob QABUL QILINMAYDI. Hosila olish, sistem tuzish, hisoblash — barchasini ko'rsating.

**Javob:** Yakuniy natija. Tekshirib ko'rsating.

## LaTeX qoidalari

Barcha matematik va fizik ifodalar LaTeX bilan:
- Satr ichida: `$F = ma$`, `$E = mc^2$`
- Blokda: `$$\\iiint_V 2xy^2z^2\\,dx\\,dy\\,dz = 56$$`

## Til

O'zbek tilida yozing. Agar foydalanuvchi rus tilida yozgan bo'lsa — rus tilida javob bering."""

SYSTEM_PROMPT_RU = """Вы TezMath — AI-бот для решения математических и физических задач в Telegram-группе.

## Основная задача

Вы наблюдаете за сообщениями участников группы. Если в последних сообщениях задан математический или физический вопрос — поймите контекст, определите задачу и решите её полностью. Не отвечайте, если задача не задана.

## Определение задачи

Пользователь может:
- Написать задачу текстом
- Прислать изображение (страница учебника, рукопись, скриншот)
- Ссылаться на предыдущие сообщения ("эту задачу", "третий номер", "то, что выше")

Используйте контекст: поймите намерение участника группы по последним сообщениям.

## Когда приходит изображение — ВАЖНОЕ правило

Посчитайте количество задач на изображении:

- **5 или менее** задач → **решите все**, по порядку
- **Более 5** задач → уточните у пользователя:
  > "На изображении [N] задач. Какие номера решить?"

## Охватываемые дисциплины

**Математика:** Алгебра, геометрия, тригонометрия, комбинаторика, теория вероятностей, линейная алгебра (матрицы, определители), математический анализ (пределы, производные, интегралы — одно- и многомерные), дифференциальные уравнения, ряды и другие математические задачи.

**Физика:** Кинематика, динамика, статика, работа и энергия, импульс, гравитация, электростатика, постоянный ток (закон Ома, правила Кирхгофа), магнитное поле, оптика, термодинамика и другие физические задачи.

## Формат ответа — ОБЯЗАТЕЛЬНО

**Задача:** Чётко перефразируйте условие своими словами.

**Решение:**
Пронумерованные шаги. Каждый шаг — что делается и почему.
**ВАЖНО:** Ни один промежуточный вычислительный шаг не пропускается. Краткий ответ НЕ ПРИНИМАЕТСЯ. Показывайте вычисление производных, составление систем, все промежуточные вычисления.

**Ответ:** Итоговый результат. Проверьте подстановкой.

## Правила LaTeX

Все математические и физические выражения — через LaTeX:
- Строчные: `$F = ma$`, `$E = mc^2$`
- Блочные: `$$\\iiint_V 2xy^2z^2\\,dx\\,dy\\,dz = 56$$`

## Язык

Отвечайте на русском языке. Если пользователь пишет на узбекском — отвечайте на узбекском."""

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


def _build_messages(
    *,
    history: list[dict],
    current_text: str,
    current_image: bytes | None,
    lang: str,
) -> list[dict]:
    """
    Tarix xabarlarini kontekst blokiga birlashtiradi, joriy xabarni
    to'liq (rasm bilan) oxiriga qo'shadi.

    Tarixdagi rasmlar: base64 yuklanmaydi — matn tavsif sifatida uzatiladi.
    Joriy rasm: to'liq base64 sifatida yuboriladi.
    """
    messages: list[dict] = []

    if history:
        if lang == "uz":
            header = "--- Guruh suhbati konteksti (oxirgi xabarlar) ---"
            footer = "--- Kontekst tugadi ---\n\nYuqoridagi kontekstga asoslanib so'rovga javob bering."
            ack = "Tushundim, guruh suhbati kontekstini ko'rib chiqdim."
        else:
            header = "--- Контекст группового чата (последние сообщения) ---"
            footer = "--- Конец контекста ---\n\nОтвечайте на вопрос с учётом контекста выше."
            ack = "Понял, изучил контекст группового чата."

        lines = [header]
        for msg in history:
            name = msg.get("full_name") or msg.get("username") or "Foydalanuvchi"
            if msg["has_image"]:
                desc = msg.get("image_desc") or ("rasm" if lang == "uz" else "изображение")
                line = f"[{name}]: 📷 {desc}"
            else:
                line = f"[{name}]: {msg.get('text') or ''}"
            lines.append(line)
        lines.append(footer)

        messages.append({"role": "user", "content": "\n".join(lines)})
        messages.append({"role": "assistant", "content": ack})

    # Joriy xabar — rasm va/yoki matn
    current_content: list = []

    if current_image:
        current_content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.b64encode(current_image).decode(),
                },
            }
        )

    fallback = "Rasmda ko'rsatilgan masalani yeching." if lang == "uz" else "Решите задачу на изображении."
    current_content.append({"type": "text", "text": current_text or fallback})

    messages.append({"role": "user", "content": current_content})
    return messages


async def publish_solver_task(
    *,
    user_id: int,
    telegram_id: int,
    input_type: str,
    content: str,
    lang: str,
    image_data: bytes | None = None,
    chat_history: list[dict] | None = None,
) -> dict:
    client = _get_client()
    system = SYSTEM_PROMPT_UZ if lang == "uz" else SYSTEM_PROMPT_RU

    messages = _build_messages(
        history=chat_history or [],
        current_text=content,
        current_image=image_data,
        lang=lang,
    )

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=system,
        messages=messages,
    )

    solution_text = response.content[0].text
    tokens = response.usage.input_tokens + response.usage.output_tokens
    logger.info(
        "Claude solved: user=%d tokens=%d context_msgs=%d",
        telegram_id,
        tokens,
        len(chat_history or []),
    )

    solution_id = await save_solution(
        user_id=user_id,
        input_type=input_type,
        input_text=content[:500],
        solution_text=solution_text,
        model_used="claude-sonnet-4-6",
        tokens_used=tokens,
    )

    return {
        "solution_id": solution_id,
        "solution_text": solution_text,
        "render_url": None,
    }
