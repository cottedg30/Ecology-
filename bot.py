# -*- coding: utf-8 -*-
"""
ЭкоКонтроль — Telegram-бот для экологов предприятий.
Структура: контент зависит от категории объекта НВОС (I–IV).
Токен читается из переменной окружения TG_BOT_TOKEN.
"""

import os
import time
import logging
import requests

# --- Настройки ---
TELEGRAM_TOKEN = os.environ.get("TG_BOT_TOKEN", "").strip()
if not TELEGRAM_TOKEN:
    raise SystemExit(
        "❌ Не задан TG_BOT_TOKEN.\n"
        "Запустите так:  TG_BOT_TOKEN='xxx' python ecobot.py\n"
        "Или создайте .env (см. README)."
    )

URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("ecobot")


# ============================================================
#  БАЗА ЗНАНИЙ
# ============================================================

# Отдельные статьи (для поиска и карточек рисков)
ARTICLES_DB = {
    "waste_damage_soil": {
        "title": "Ущерб почвам от отходов (Методика № 238)",
        "article": "ст. 77, 78 ФЗ № 7-ФЗ, Приказ Минприроды № 238, ст. 8.6 КоАП РФ",
        "keywords": ["ущерб", "методика 238", "вред почвам", "захламление",
                     "порча земель", "рекультивация", "расчет ущерба"],
        "dl_fine": "10 000 – 30 000 ₽",
        "ip_fine": "20 000 – 40 000 ₽ или приостановление до 90 суток",
        "ul_fine": "100 000 – 250 000 ₽ + ИСК О ВРЕДЕ НА МИЛЛИОНЫ",
        "suspension": "Да, до 90 суток (ст. 8.6 / 8.2 КоАП РФ)",
        "damage_risk": "КРИТИЧЕСКИЙ: взыскание вреда почвам идёт отдельно от штрафа.",
        "details": (
            "📐 <b>Основание:</b> Приказ Минприроды России от 08.07.2010 № 238.\n\n"
            "⚠️ <b>Типичные случаи:</b>\n"
            "1. Сброс/накопление отходов на открытом грунте.\n"
            "2. Перекрытие почвы отходами (захламление).\n"
            "3. Загрязнение почвы опасными веществами (превышение ПДК/ОДК).\n\n"
            "📊 <b>От чего зависит сумма:</b>\n"
            "• Площадь (кв.м);\n"
            "• Класс опасности отхода (I–V);\n"
            "• Категория земель;\n"
            "• Глубина загрязнения.\n\n"
            "🛡 <b>Защита:</b> немедленная ликвидация свалки и рекультивация. "
            "Затраты на рекультивацию могут быть зачтены в счёт возмещения вреда "
            "(позиция ВС РФ) при наличии утверждённого проекта."
        ),
    },
    "waste_passports": {
        "title": "Отсутствие паспортов отходов I–IV классов",
        "article": "ч. 9 ст. 8.2 КоАП РФ",
        "keywords": ["паспорт", "паспорта", "отход", "фкко", "класс опасности"],
        "dl_fine": "20 000 – 40 000 ₽",
        "ip_fine": "40 000 – 60 000 ₽",
        "ul_fine": "200 000 – 350 000 ₽",
        "suspension": "Нет",
        "damage_risk": "Низкий (если не доказано загрязнение почв).",
        "details": "Несоставление паспортов отходов I–IV классов или ненаправление "
                   "копий в терр. орган Росприроднадзора.",
    },
    "waste_general": {
        "title": "Нарушение накопления и утилизации отходов",
        "article": "ч. 1 ст. 8.2 КоАП РФ",
        "keywords": ["мусор", "накопление", "отходы", "свалка", "площадка", "хранение"],
        "dl_fine": "10 000 – 30 000 ₽",
        "ip_fine": "30 000 – 50 000 ₽ или приостановление до 90 суток",
        "ul_fine": "100 000 – 250 000 ₽ или приостановление до 90 суток",
        "suspension": "Да, до 90 суток (для ИП и ЮЛ)",
        "damage_risk": "Высокий (при проливах, захламлении земли).",
        "details": "Несоблюдение требований при сборе, накоплении (>11 месяцев — уже хранение), "
                   "транспортировании или утилизации отходов.",
    },
    "waste_tech_report": {
        "title": "Несдача технического отчёта по отходам",
        "article": "ч. 11 ст. 8.2 КоАП РФ",
        "keywords": ["технический отчет", "техотчет", "лимиты", "ноолр", "неизменность"],
        "dl_fine": "20 000 – 40 000 ₽",
        "ip_fine": "40 000 – 60 000 ₽",
        "ul_fine": "200 000 – 350 000 ₽",
        "suspension": "Нет (но аннулируются лимиты)",
        "damage_risk": "Критический: все отходы становятся сверхлимитными с 25-кратным коэффициентом.",
        "details": "Непредставление техотчёта, подтверждающего неизменность процесса, "
                   "или отчётности об образовании и размещении отходов.",
    },
    "air_no_permit": {
        "title": "Выбросы без разрешения / КЭР / ДВОС",
        "article": "ч. 1 ст. 8.21 КоАП РФ",
        "keywords": ["выброс", "воздух", "разрешение", "кэр", "двос", "атмосфера", "источник"],
        "dl_fine": "40 000 – 50 000 ₽",
        "ip_fine": "30 000 – 50 000 ₽ или приостановление до 90 суток",
        "ul_fine": "180 000 – 250 000 ₽ или приостановление до 90 суток",
        "suspension": "Да, до 90 суток",
        "damage_risk": "Критический (расчёт ущерба по Приказу № 273).",
        "details": "Выброс вредных веществ стационарными источниками без КЭР, ДВОС "
                   "или специального разрешения.",
    },
    "air_gou": {
        "title": "Нарушение правил эксплуатации ГОУ",
        "article": "ч. 3 ст. 8.21 КоАП РФ",
        "keywords": ["гоу", "пгу", "газоочистка", "фильтр", "установка очистки"],
        "dl_fine": "1 000 – 2 000 ₽",
        "ip_fine": "1 000 – 2 000 ₽ или приостановление до 90 суток",
        "ul_fine": "10 000 – 20 000 ₽ или приостановление до 90 суток",
        "suspension": "Да, до 90 суток",
        "damage_risk": "Средний (при залповом выбросе).",
        "details": "Нарушение эксплуатации, отключение ГОУ и аппаратуры контроля выбросов.",
    },
    "water_discharge": {
        "title": "Сброс стоков без НДС / с превышением",
        "article": "ч. 1 ст. 8.14 КоАП РФ",
        "keywords": ["сброс", "стоки", "вода", "река", "коллектор", "ндс", "водопользование"],
        "dl_fine": "10 000 – 20 000 ₽",
        "ip_fine": "20 000 – 30 000 ₽ или приостановление до 90 суток",
        "ul_fine": "80 000 – 100 000 ₽ или приостановление до 90 суток",
        "suspension": "Да, до 90 суток",
        "damage_risk": "Критический (методика № 87 — иски на миллионы).",
        "details": "Сброс сточных вод с превышением НДС, без разрешения или решения "
                   "о предоставлении водного объекта.",
    },
    "eco_fee_non_payment": {
        "title": "Неуплата экологического сбора / РОП",
        "article": "ст. 8.41.1 КоАП РФ",
        "keywords": ["экосбор", "экологический сбор", "роп", "упаковка", "норматив утилизации"],
        "dl_fine": "5 000 – 7 000 ₽",
        "ip_fine": "3-кратный размер сбора, но не менее 250 000 ₽",
        "ul_fine": "3-кратный размер сбора, но не менее 500 000 ₽",
        "suspension": "Нет",
        "damage_risk": "Принудительное взыскание сбора + пени.",
        "details": "Неуплата экосбора до 15 апреля производителями/импортёрами, "
                   "не обеспечившими самостоятельную утилизацию.",
    },
    "rop_reporting": {
        "title": "Нарушение отчётности по РОП",
        "article": "ст. 8.5.1 КоАП РФ",
        "keywords": ["отчетность роп", "декларация товаров", "декларация упаковки", "отчет об утилизации"],
        "dl_fine": "3 000 – 6 000 ₽",
        "ip_fine": "50 000 – 70 000 ₽ (при недостоверных данных — до 2-кратного размера сбора, мин. 100 000 ₽)",
        "ul_fine": "70 000 – 150 000 ₽ (при недостоверных данных — до 2-кратного размера сбора, мин. 250 000 ₽)",
        "suspension": "Нет",
        "damage_risk": "Средний (доначисление экосбора).",
        "details": "Непредставление декларации о товарах/упаковке, отчёта об утилизации "
                   "или указание недостоверных сведений.",
    },
    "nvos_non_payment": {
        "title": "Невнесение платы за НВОС",
        "article": "ст. 8.41 КоАП РФ",
        "keywords": ["нвос", "плата", "расчет", "экоплатеж", "негативное воздействие"],
        "dl_fine": "3 000 – 6 000 ₽",
        "ip_fine": "Штраф как на должностное лицо",
        "ul_fine": "50 000 – 100 000 ₽",
        "suspension": "Нет",
        "damage_risk": "Взыскание задолженности + пени (1/300 ставки ЦБ за день).",
        "details": "Невнесение платы до 1 марта и декларации до 10 марта, "
                   "а также квартальных авансов.",
    },
    "eco_reports_hidden": {
        "title": "Искажение отчётов 2-ТП / ПЭК",
        "article": "ст. 8.5 КоАП РФ",
        "keywords": ["отчет", "2-тп", "пэк", "декларация", "сокрытие", "искажение"],
        "dl_fine": "3 000 – 6 000 ₽",
        "ip_fine": "Штраф как на должностное лицо",
        "ul_fine": "20 000 – 80 000 ₽",
        "suspension": "Нет",
        "damage_risk": "Средний (внеплановая проверка).",
        "details": "Сокрытие/искажение сведений в отчётах ПЭК, 2-ТП (воздух, отходы, водхоз), ДВОС.",
    },
    "nvos_categories_info": {
        "title": "Категории объектов НВОС (I–IV)",
        "article": "ст. 4.2 ФЗ № 7-ФЗ, ПП РФ № 2398",
        "keywords": ["категория", "категории", "нвос", "критерии", "1 категория", "2 категория"],
        "dl_fine": "Зависит от нарушения",
        "ip_fine": "Зависит от нарушения",
        "ul_fine": "От 50 000 до 1 000 000 ₽ + коэффициенты",
        "suspension": "Возможна по ст. 8.21, 8.2, 8.14",
        "damage_risk": "Максимальный для I и II категорий.",
        "details": (
            "🔴 <b>I категория:</b> КЭР, ПЭК, САКВ, ПНООЛР, НДТ.\n"
            "🟠 <b>II категория:</b> ДВОС (раз в 7 лет), ПЭК, ПНООЛР, НДВ/НДС.\n"
            "🟡 <b>III категория:</b> ПЭК, паспорта отходов, НДВ/НДС только для I–II класса.\n"
            "🟢 <b>IV категория:</b> учёт отходов и паспорта. Освобождена от платы НВОС, ДВОС, ПЭК."
        ),
    },
    "nvos_actualization": {
        "title": "Неактуализация сведений об объекте НВОС",
        "article": "ст. 8.46 КоАП РФ, ст. 69.2 ФЗ № 7-ФЗ",
        "keywords": ["актуализация", "изменение сведений", "смена адреса", "модернизация"],
        "dl_fine": "5 000 – 20 000 ₽",
        "ip_fine": "Штраф как на должностное лицо",
        "ul_fine": "30 000 – 100 000 ₽",
        "suspension": "Нет",
        "damage_risk": "Высокий: расхождение с реестром → «работа без разрешения».",
        "details": "Срок подачи заявки на актуализацию — не позднее 30 календарных дней "
                   "с момента изменений (адрес, ФИО, реорганизация, технологии).",
    },
    "nvos_registration": {
        "title": "Непостановка объекта НВОС на учёт",
        "article": "ст. 8.46 КоАП РФ",
        "keywords": ["постановка на учет", "первичная постановка", "свидетельство нвос"],
        "dl_fine": "5 000 – 20 000 ₽",
        "ip_fine": "Штраф как на должностное лицо",
        "ul_fine": "30 000 – 100 000 ₽",
        "suspension": "Нет",
        "damage_risk": "Средний.",
        "details": "Заявка подаётся не позднее 6 месяцев со дня начала эксплуатации объекта.",
    },
}


# Категории НВОС — что требуется по каждой
CATEGORIES = {
    "1": {
        "title": "🔴 I категория (значительное воздействие)",
        "note": "Объект НДТ. Риск проверок — высокий.",
        "docs": [
            ("КЭР (Комплексное экологическое разрешение)", "7 лет",
             "До 250 000 ₽ + 100-кратный коэффициент к плате НВОС"),
            ("ПНООЛР (Проект нормативов образования отходов и лимитов)", "5 лет",
             "100 000 – 250 000 ₽ (ч. 1 ст. 8.2 КоАП)"),
            ("Программа ПЭК", "ежегодно", "20 000 – 80 000 ₽ (ст. 8.5 КоАП)"),
            ("САКВ (система автоматического контроля)", "по проекту", "ч. 3 ст. 8.21 КоАП"),
            ("Нормативы НДВ / НДС", "в составе КЭР", "ч. 1 ст. 8.21 / 8.14 КоАП"),
            ("План мероприятий по охране ОС", "по проекту", "ч. 3 ст. 8.21 КоАП"),
        ],
        "reports": [
            ("2-ТП (воздух)", "22 января"),
            ("2-ТП (отходы)", "1 февраля"),
            ("2-ТП (водхоз)", "22 января"),
            ("Плата за НВОС", "1 марта"),
            ("Декларация о плате за НВОС", "10 марта"),
            ("Отчёт по ПЭК", "25 марта"),
            ("Отчёт о выполнении плана мероприятий", "25 марта"),
        ],
        "risks": ["air_no_permit", "water_discharge", "waste_damage_soil", "waste_general"],
    },
    "2": {
        "title": "🟠 II категория (умеренное воздействие)",
        "note": "ДВОС обновляется раз в 7 лет или при изменениях процесса.",
        "docs": [
            ("ДВОС (Декларация о воздействии на ОС)", "7 лет", "50 000 – 100 000 ₽"),
            ("ПНООЛР (Проект нормативов образования отходов и лимитов)", "5 лет",
             "100 000 – 250 000 ₽ (ч. 1 ст. 8.2 КоАП)"),
            ("Программа ПЭК", "ежегодно", "20 000 – 80 000 ₽"),
            ("Нормативы НДВ / НДС", "в составе ДВОС", "ч. 1 ст. 8.21 / 8.14 КоАП"),
            ("Паспорта отходов I–IV классов", "бессрочно при неизменности", "200 000 – 350 000 ₽"),
        ],
        "reports": [
            ("2-ТП (воздух)", "22 января"),
            ("2-ТП (отходы)", "1 февраля"),
            ("Плата за НВОС", "1 марта"),
            ("Декларация о плате за НВОС", "10 марта"),
            ("Отчёт по ПЭК", "25 марта"),
        ],
        "risks": ["air_no_permit", "waste_passports", "waste_general", "nvos_actualization"],
    },
    "3": {
        "title": "🟡 III категория (незначительное воздействие)",
        "note": "Нормативы НДВ/НДС — только для веществ I–II классов опасности.",
        "docs": [
            ("Паспорта отходов I–IV классов", "бессрочно при неизменности", "200 000 – 350 000 ₽"),
            ("Учёт отходов (журнал движения)", "постоянно", "ч. 10 ст. 8.2 КоАП"),
            ("Нормативы НДВ / НДС (только I–II класс)", "по проекту", "ч. 1 ст. 8.21 / 8.14 КоАП"),
            ("Отчёт по ПЭК", "ежегодно до 25 марта", "20 000 – 80 000 ₽"),
        ],
        "reports": [
            ("2-ТП (отходы)", "1 февраля"),
            ("Плата за НВОС", "1 марта"),
            ("Декларация о плате за НВОС", "10 марта"),
            ("Отчёт по ПЭК", "25 марта"),
        ],
        "risks": ["waste_passports", "nvos_non_payment", "nvos_registration", "eco_reports_hidden"],
    },
    "4": {
        "title": "🟢 IV категория (минимальное воздействие)",
        "note": "Плановые проверки практически не проводятся.",
        "docs": [
            ("Паспорта отходов I–IV классов", "бессрочно при неизменности", "200 000 – 350 000 ₽"),
            ("Учёт отходов (журнал движения)", "постоянно", "ч. 10 ст. 8.2 КоАП"),
        ],
        "reports": [
            ("2-ТП (отходы) — если образуются отходы", "1 февраля"),
        ],
        "risks": ["waste_passports", "nvos_registration"],
    },
}


# Экосбор / РОП — единый блок для всех категорий
ECO_FEE_INFO = {
    "deadlines": [
        ("Декларация о количестве выпущенных товаров и упаковки", "1 апреля",
         "до 2-кратного размера сбора, но не менее 250 000 ₽ (ЮЛ)"),
        ("Отчёт о выполнении нормативов утилизации", "1 апреля",
         "70 000 – 150 000 ₽ (ст. 8.5.1 КоАП)"),
        ("Расчёт суммы экологического сбора", "15 апреля",
         "3-кратный размер сбора, но не менее 500 000 ₽ (ЮЛ)"),
        ("Уплата экологического сбора", "15 апреля",
         "принудительное взыскание + пени"),
    ],
    "note": (
        "⚠️ Обязанность по РОП <b>не зависит от категории НВОС</b>.\n"
        "Даже объект IV категории платит экосбор, если производит или импортирует "
        "товары/упаковку из перечней ПП РФ № 2414 и № 2425."
    ),
}


# ============================================================
#  СЕССИИ
# ============================================================

user_sessions = {}


def get_session(chat_id):
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {"mode": "main", "category": None, "audit_cat": None}
    return user_sessions[chat_id]


# ============================================================
#  TELEGRAM API
# ============================================================

def _post(method, payload, timeout=10):
    try:
        r = requests.post(f"{URL}/{method}", json=payload, timeout=timeout)
        data = r.json()
        if not data.get("ok"):
            log.warning("TG %s error: %s", method, data)
        return data
    except requests.RequestException as e:
        log.exception("TG %s network error: %s", method, e)
        return {}


def send_tg(chat_id, text, markup=None):
    payload = {"chat_id": chat_id, "text": text,
               "parse_mode": "HTML", "disable_web_page_preview": True}
    if markup:
        payload["reply_markup"] = markup
    return _post("sendMessage", payload)


def edit_tg(chat_id, message_id, text, markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text,
               "parse_mode": "HTML", "disable_web_page_preview": True}
    if markup:
        payload["reply_markup"] = markup
    return _post("editMessageText", payload)


def answer_cq(cq_id, text=None):
    payload = {"callback_query_id": cq_id}
    if text:
        payload["text"] = text
    _post("answerCallbackQuery", payload, timeout=5)


# ============================================================
#  КЛАВИАТУРЫ
# ============================================================

def main_keyboard():
    return {"inline_keyboard": [
        [{"text": "🔴 I категория", "callback_data": "cat_sel:1"}],
        [{"text": "🟠 II категория", "callback_data": "cat_sel:2"}],
        [{"text": "🟡 III категория", "callback_data": "cat_sel:3"}],
        [{"text": "🟢 IV категория", "callback_data": "cat_sel:4"}],
        [{"text": "💰 Экосбор / РОП (все категории)", "callback_data": "ecofee"}],
        [{"text": "🔍 Поиск по нарушениям", "callback_data": "menu_search"}],
        [{"text": "🛡 Проверки Росприроднадзора (248-ФЗ)", "callback_data": "inspections"}],
    ]}


def category_menu_keyboard(cat):
    return {"inline_keyboard": [
        [{"text": "📋 Документы и проекты", "callback_data": f"c_docs:{cat}"}],
        [{"text": "📊 Отчётность и платежи", "callback_data": f"c_reports:{cat}"}],
        [{"text": "💥 Риски и штрафы", "callback_data": f"c_risks:{cat}"}],
        [{"text": "💰 Экосбор / РОП", "callback_data": "ecofee"}],
        [{"text": "◀️ Сменить категорию", "callback_data": "back_main"}],
    ]}


def risks_keyboard(cat):
    kb = []
    for rk in CATEGORIES[cat]["risks"]:
        art = ARTICLES_DB[rk]
        kb.append([{"text": art["title"][:42], "callback_data": f"item:{rk}"}])
    kb.append([{"text": "◀️ Назад", "callback_data": f"cat_sel:{cat}"}])
    return {"inline_keyboard": kb}


def back_to_cat_keyboard(cat):
    return {"inline_keyboard": [
        [{"text": "◀️ Назад в меню категории", "callback_data": f"cat_sel:{cat}"}],
        [{"text": "🏠 Главное меню", "callback_data": "back_main"}],
    ]}


def back_main_keyboard():
    return {"inline_keyboard": [
        [{"text": "◀️ Главное меню", "callback_data": "back_main"}],
    ]}


def search_back_keyboard():
    return {"inline_keyboard": [
        [{"text": "🔍 Искать снова", "callback_data": "menu_search"}],
        [{"text": "🏠 Главное меню", "callback_data": "back_main"}],
    ]}


def audit_cat_keyboard():
    return {"inline_keyboard": [
        [{"text": "I категория", "callback_data": "aud_cat:1"}],
        [{"text": "II категория", "callback_data": "aud_cat:2"}],
        [{"text": "III категория", "callback_data": "aud_cat:3"}],
        [{"text": "IV категория", "callback_data": "aud_cat:4"}],
        [{"text": "◀️ Отмена", "callback_data": "back_main"}],
    ]}


# ============================================================
#  РЕНДЕРЫ
# ============================================================

def render_category_menu(cat):
    c = CATEGORIES[cat]
    return (
        f"{c['title']}\n"
        f"<i>{c['note']}</i>\n\n"
        "Выберите раздел:"
    )


def render_docs(cat):
    c = CATEGORIES[cat]
    lines = [f"📋 <b>{c['title']} — документы и проекты</b>\n"]
    for i, (name, term, fine) in enumerate(c["docs"], 1):
        lines.append(
            f"<b>{i}. {name}</b>\n"
            f"   • Срок: {term}\n"
            f"   • Штраф: <code>{fine}</code>\n"
        )
    return "\n".join(lines)


def render_reports(cat):
    c = CATEGORIES[cat]
    lines = [f"📊 <b>{c['title']} — отчётность и платежи</b>\n"]
    for name, deadline in c["reports"]:
        lines.append(f"• {name} — <b>до {deadline}</b>")
    return "\n".join(lines)


def render_risks(cat):
    c = CATEGORIES[cat]
    return (
        f"💥 <b>{c['title']} — ключевые риски</b>\n\n"
        "Выберите состав нарушения:"
    )


def render_article(item):
    return (
        f"📋 <b>{item['title']}</b>\n"
        f"<i>Норма: {item['article']}</i>\n\n"
        f"💰 <b>Размеры штрафов:</b>\n"
        f"• Должностное лицо: <code>{item['dl_fine']}</code>\n"
        f"• ИП: <code>{item['ip_fine']}</code>\n"
        f"• Юридическое лицо: <code>{item['ul_fine']}</code>\n\n"
        f"⛔ <b>Приостановление:</b> {item['suspension']}\n\n"
        f"💥 <b>Риск вреда / доначислений:</b>\n{item['damage_risk']}\n\n"
        f"📝 <b>Суть и практика:</b>\n{item['details']}"
    )


def render_ecofee():
    lines = ["💰 <b>Экосбор / РОП — для всех категорий НВОС</b>\n"]
    for name, deadline, fine in ECO_FEE_INFO["deadlines"]:
        lines.append(
            f"<b>• {name}</b>\n"
            f"   Срок: <b>до {deadline}</b>\n"
            f"   Штраф: <code>{fine}</code>\n"
        )
    lines.append(ECO_FEE_INFO["note"])
    return "\n".join(lines)


def render_inspections():
    return (
        "🛡 <b>Проверки эконадзора (ФЗ № 248-ФЗ)</b>\n\n"
        "1️⃣ <b>Предостережение о недопустимости:</b>\n"
        "• Не штраф и не предписание.\n"
        "• Направьте мотивированное возражение в срок (10–30 дней), "
        "иначе орган может инициировать КНМ.\n\n"
        "2️⃣ <b>Профилактический визит:</b>\n"
        "• Инспектор не вправе выписывать протоколы.\n"
        "• Возможность выявить недочёты без санкций.\n\n"
        "3️⃣ <b>Внеплановая выездная проверка:</b>\n"
        "• Только по согласованию с прокуратурой.\n"
        "• Проверяйте полномочия инспектора по QR в ЕРКНМ (proverki.gov.ru).\n"
        "• При отборе проб требуйте параллельный отбор аккредитованной лабораторией."
    )


# ============================================================
#  ПОИСК
# ============================================================

def search_articles(query, limit=6):
    q = query.lower().replace("ё", "е").strip()
    matches = []
    for key, art in ARTICLES_DB.items():
        haystack = " ".join([
            art["title"].lower(),
            art["article"].lower(),
            " ".join(art["keywords"]),
        ]).replace("ё", "е")
        if q in haystack:
            matches.append((key, art))
    return matches[:limit]


# ============================================================
#  ОБРАБОТКА CALLBACK
# ============================================================

def handle_callback(cq):
    cq_id = cq["id"]
    data = cq.get("data", "")
    chat_id = cq["message"]["chat"]["id"]
    msg_id = cq["message"]["message_id"]
    sess = get_session(chat_id)

    # Главное меню
    if data == "back_main":
        answer_cq(cq_id)
        sess["category"] = None
        sess["mode"] = "main"
        edit_tg(chat_id, msg_id,
                "🏭 <b>ЭкоКонтроль: Справочник эколога</b>\n\n"
                "Выберите категорию объекта НВОС — бот покажет только "
                "релевантные отчёты, проекты и риски.",
                main_keyboard())
        return

    # Выбор категории
    if data.startswith("cat_sel:"):
        answer_cq(cq_id)
        cat = data.split(":")[1]
        sess["category"] = cat
        edit_tg(chat_id, msg_id, render_category_menu(cat), category_menu_keyboard(cat))
        return

    # Документы
    if data.startswith("c_docs:"):
        answer_cq(cq_id)
        cat = data.split(":")[1]
        edit_tg(chat_id, msg_id, render_docs(cat), back_to_cat_keyboard(cat))
        return    # Отчёты
    if data.startswith("c_reports:"):
        answer_cq(cq_id)
        cat = data.split(":")[1]
        edit_tg(chat_id, msg_id, render_reports(cat), back_to_cat_keyboard(cat))
        return

    # Риски
    if data.startswith("c_risks:"):
        answer_cq(cq_id)
        cat = data.split(":")[1]
        edit_tg(chat_id, msg_id, render_risks(cat), risks_keyboard(cat))
        return

    # Экосбор / РОП
    if data == "ecofee":
        answer_cq(cq_id)
        cat = sess.get("category")
        kb = back_to_cat_keyboard(cat) if cat else back_main_keyboard()
        edit_tg(chat_id, msg_id, render_ecofee(), kb)
        return

    # Статья
    if data.startswith("item:"):
        answer_cq(cq_id)
        key = data.split(":")[1]
        art = ARTICLES_DB.get(key)
        if not art:
            return
        cat = sess.get("category")
        kb = back_to_cat_keyboard(cat) if cat else back_main_keyboard()
        edit_tg(chat_id, msg_id, render_article(art), kb)
        return

    # Поиск
    if data == "menu_search":
        answer_cq(cq_id)
        sess["mode"] = "search"
        edit_tg(chat_id, msg_id,
                "🔍 <b>Поиск по нарушениям</b>\n\n"
                "Отправьте ключевое слово или статью:\n"
                "<i>ущерб, методика 238, экосбор, техотчет, актуализация, КЭР, 8.41.1</i>",
                back_main_keyboard())
        return

    # Проверки
    if data == "inspections":
        answer_cq(cq_id)
        edit_tg(chat_id, msg_id, render_inspections(), back_main_keyboard())
        return

    # Аудит (оставлен на будущее)
    if data == "menu_audit":
        answer_cq(cq_id)
        sess["mode"] = "audit"
        edit_tg(chat_id, msg_id,
                "⚠️ <b>Экспресс-аудит рисков</b>\n\nУкажите категорию объекта:",
                audit_cat_keyboard())
        return

    if data.startswith("aud_cat:"):
        answer_cq(cq_id)
        cat = data.split(":")[1]
        sess["audit_cat"] = cat
        edit_tg(chat_id, msg_id, "Категория выбрана. Раздел в разработке.",
                back_main_keyboard())
        return

    answer_cq(cq_id)


# ============================================================
#  ОБРАБОТКА СООБЩЕНИЙ
# ============================================================

def handle_message(msg):
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    sess = get_session(chat_id)

    if text.startswith("/start") or text.startswith("/menu"):
        sess["mode"] = "main"
        sess["category"] = None
        send_tg(chat_id,
                "🏭 <b>ЭкоКонтроль: Справочник эколога предприятия</b>\n\n"
                "Выберите категорию объекта НВОС — бот покажет только "
                "релевантные отчёты, проекты и риски:",
                main_keyboard())
        return

    if text.startswith("/help"):
        send_tg(chat_id,
                "ℹ️ <b>Как пользоваться</b>\n\n"
                "1. Выберите категорию НВОС.\n"
                "2. Смотрите документы, отчёты и риски.\n"
                "3. Отдельная кнопка — экосбор/РОП (для всех категорий).\n"
                "4. Поиск — по ключевым словам или статьям КоАП.",
                back_main_keyboard())
        return

    if text.startswith("/"):
        send_tg(chat_id, "Неизвестная команда. Используйте /start.", back_main_keyboard())
        return

    # Поиск по любому тексту
    matches = search_articles(text)
    if matches:
        kb = [[{"text": art["title"][:42], "callback_data": f"item:{key}"}]
              for key, art in matches]
        kb.append([{"text": "🏠 Главное меню", "callback_data": "back_main"}])
        send_tg(chat_id,
                f"🎯 Найдено совпадений: <b>{len(matches)}</b>",
                {"inline_keyboard": kb})
    else:
        send_tg(chat_id,
                "❌ Ничего не найдено. Попробуйте: <code>ущерб</code>, "
                "<code>экосбор</code>, <code>техотчет</code>, <code>актуализация</code>.",
                search_back_keyboard())


# ============================================================
#  MAIN LOOP
# ============================================================

def main():
    log.info(">>> Эко-бот запущен <<<")
    offset = 0
    while True:
        try:
            res = requests.get(
                f"{URL}/getUpdates",
                params={"offset": offset, "timeout": 20},
                timeout=25,
            ).json()
            if not res.get("ok"):
                time.sleep(2)
                continue

            for item in res.get("result", []):
                offset = item["update_id"] + 1
                if "callback_query" in item:
                    handle_callback(item["callback_query"])
                elif "message" in item:
                    handle_message(item["message"])
        except KeyboardInterrupt:
            log.info("Остановлено пользователем.")
            break
        except Exception:
            log.exception("Ошибка в главном цикле")
            time.sleep(3)


if __name__ == "__main__":
    main()