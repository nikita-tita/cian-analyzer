"""
Маршруты для контактных форм

Blueprint: /api/contact-request, /api/client-request
"""

import logging
from datetime import datetime
from flask import Blueprint, request, jsonify

from src.services import telegram_notifier, validate_phone, validate_name
from src.services.telegram import TelegramNotifier

logger = logging.getLogger(__name__)

contacts_bp = Blueprint('contacts', __name__)


@contacts_bp.route('/api/contact-request', methods=['POST'])
def contact_request():
    """
    Обработка заявки на контакт от клиента (из отчёта)
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Неверный формат данных'}), 400

        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip()
        comment = data.get('comment', '').strip()
        session_id = data.get('session_id', '')

        # Валидация обязательных полей
        if not name or not phone:
            return jsonify({'error': 'Имя и телефон обязательны'}), 400

        if not validate_name(name):
            return jsonify({'error': 'Введите корректное имя'}), 400

        if not validate_phone(phone):
            return jsonify({'error': 'Введите корректный номер телефона'}), 400

        # Логируем заявку
        logger.info(f"=== НОВАЯ ЗАЯВКА НА КОНТАКТ ===")
        logger.info(f"Имя: {name}")
        logger.info(f"Телефон: {phone}")
        logger.info(f"Email: {email if email else 'не указан'}")
        logger.info(f"Комментарий: {comment if comment else 'нет'}")
        logger.info(f"Session ID: {session_id}")
        logger.info(f"================================")

        # Отправляем в Telegram
        safe_name = TelegramNotifier.sanitize_html(name)
        safe_phone = TelegramNotifier.sanitize_html(phone)
        safe_email = TelegramNotifier.sanitize_html(email) if email else 'не указан'
        safe_comment = TelegramNotifier.sanitize_html(comment) if comment else 'нет'

        timestamp = datetime.now().strftime('%d.%m.%Y %H:%M')
        message = f"""📋 <b>Заявка на контакт с HOUSLER</b>

<b>Имя:</b> {safe_name}
<b>Телефон:</b> {safe_phone}
<b>Email:</b> {safe_email}
<b>Комментарий:</b> {safe_comment}

<i>📅 {timestamp}</i>"""

        telegram_notifier.send(message)

        return jsonify({
            'success': True,
            'message': 'Заявка принята'
        }), 200

    except Exception as e:
        logger.error(f"Ошибка обработки заявки: {e}", exc_info=True)
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500


@contacts_bp.route('/api/client-request', methods=['POST'])
def client_request():
    """
    Обработка заявки от клиента (вариативная форма с главной страницы)
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Неверный формат данных'}), 400

        # Honeypot - если заполнено, это бот
        if data.get('website') or data.get('url') or data.get('email_confirm'):
            logger.warning(f"Bot detected via honeypot from IP: {request.remote_addr}")
            return jsonify({'success': True, 'message': 'Заявка принята'}), 200

        operation = data.get('operation', '').strip()
        property_type = data.get('property_type', '').strip()
        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()
        contact_method = data.get('contact_method', '').strip()

        # Строгая валидация enum полей
        valid_operations = {'buy', 'sell', 'rent'}
        valid_property_types = {'residential', 'commercial'}
        valid_contact_methods = {'call', 'whatsapp', 'telegram'}

        if operation not in valid_operations:
            return jsonify({'error': 'Неверная операция'}), 400
        if property_type not in valid_property_types:
            return jsonify({'error': 'Неверный тип недвижимости'}), 400
        if contact_method not in valid_contact_methods:
            return jsonify({'error': 'Неверный способ связи'}), 400

        # Валидация имени и телефона
        if not name or not validate_name(name):
            return jsonify({'error': 'Введите корректное имя (2-100 символов)'}), 400
        if not phone or not validate_phone(phone):
            return jsonify({'error': 'Введите корректный номер телефона'}), 400

        # Маппинг для читаемости
        operation_map = {
            'buy': 'Купить',
            'sell': 'Продать',
            'rent': 'Сдать в аренду'
        }
        property_map = {
            'residential': 'Жилая недвижимость',
            'commercial': 'Коммерческая недвижимость'
        }
        contact_map = {
            'call': 'Позвонить',
            'whatsapp': 'WhatsApp',
            'telegram': 'Telegram'
        }

        operation_text = operation_map[operation]
        property_text = property_map[property_type]
        contact_text = contact_map[contact_method]

        # Санитизация пользовательского ввода
        safe_name = TelegramNotifier.sanitize_html(name)
        safe_phone = TelegramNotifier.sanitize_html(phone)

        # Логируем
        logger.info(f"=== НОВАЯ ЗАЯВКА ОТ КЛИЕНТА ===")
        logger.info(f"Операция: {operation_text}")
        logger.info(f"Тип недвижимости: {property_text}")
        logger.info(f"Имя: {name}")
        logger.info(f"Телефон: {phone}")
        logger.info(f"Способ связи: {contact_text}")
        logger.info(f"IP: {request.remote_addr}")
        logger.info(f"================================")

        # Формируем сообщение для Telegram
        timestamp = datetime.now().strftime('%d.%m.%Y %H:%M')
        message = f"""🏠 <b>Новая заявка с сайта HOUSLER</b>

<b>Операция:</b> {operation_text}
<b>Тип недвижимости:</b> {property_text}

<b>Контактные данные:</b>
• Имя: {safe_name}
• Телефон: {safe_phone}
• Связаться через: {contact_text}

<i>📅 {timestamp}</i>"""

        telegram_notifier.send(message)

        return jsonify({
            'success': True,
            'message': 'Заявка принята'
        }), 200

    except Exception as e:
        logger.error(f"Ошибка обработки заявки: {e}", exc_info=True)
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
