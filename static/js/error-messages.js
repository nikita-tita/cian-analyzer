/* ============================================
   HOUSLER ERROR MESSAGES
   Human-readable error messages for better UX
   ============================================ */

const ERROR_MESSAGES = {
    // Сетевые ошибки
    'network_error': {
        title: 'Ошибка соединения',
        message: 'Не удалось подключиться к серверу. Проверьте интернет-соединение и попробуйте снова.'
    },
    'timeout': {
        title: 'Превышено время ожидания',
        message: 'Сервер не отвечает. Попробуйте повторить запрос позже.'
    },
    'server_error': {
        title: 'Ошибка сервера',
        message: 'Произошла ошибка на сервере. Наша команда уже работает над решением проблемы.'
    },

    // Ошибки валидации
    'invalid_url': {
        title: 'Некорректный URL',
        message: 'Введите корректную ссылку на объявление с Cian.ru'
    },
    'invalid_price': {
        title: 'Некорректная цена',
        message: 'Введите числовое значение, например: 15000000'
    },
    'invalid_area': {
        title: 'Некорректная площадь',
        message: 'Введите числовое значение площади в квадратных метрах'
    },
    'invalid_rooms': {
        title: 'Некорректное количество комнат',
        message: 'Укажите число от 1 до 10'
    },
    'missing_required_fields': {
        title: 'Заполните все поля',
        message: 'Необходимо заполнить: адрес, цену, площадь и количество комнат'
    },
    'missing_address': {
        title: 'Не указан адрес',
        message: 'Введите адрес объекта недвижимости'
    },

    // Ошибки данных
    'no_data': {
        title: 'Данные не найдены',
        message: 'Не удалось найти информацию по указанному объекту'
    },
    'parsing_failed': {
        title: 'Ошибка загрузки',
        message: 'Не удалось загрузить данные с Cian. Проверьте корректность ссылки.'
    },
    'no_comparables': {
        title: 'Аналоги не найдены',
        message: 'Не удалось найти похожие объекты для сравнения. Попробуйте изменить параметры поиска.'
    },
    'analysis_failed': {
        title: 'Ошибка анализа',
        message: 'Не удалось выполнить анализ. Проверьте корректность введенных данных.'
    },

    // Успешные операции
    'object_loaded': {
        title: 'Объект загружен',
        message: 'Данные успешно получены и проверены'
    },
    'comparables_found': {
        title: 'Аналоги найдены',
        message: 'Найдены подходящие объекты для сравнения'
    },
    'analysis_complete': {
        title: 'Анализ завершен',
        message: 'Отчет готов к просмотру'
    },
    'data_saved': {
        title: 'Данные сохранены',
        message: 'Информация успешно сохранена'
    },

    // Предупреждения
    'incomplete_data': {
        title: 'Неполные данные',
        message: 'Некоторые поля не заполнены. Результаты могут быть неточными.'
    },
    'low_confidence': {
        title: 'Низкая достоверность',
        message: 'Недостаточно данных для точной оценки. Рекомендуем добавить больше информации.'
    },

    // Общие ошибки
    'unknown_error': {
        title: 'Произошла ошибка',
        message: 'Что-то пошло не так. Попробуйте обновить страницу.'
    }
};

/**
 * Get formatted error message
 * @param {string} errorKey - Error key from ERROR_MESSAGES
 * @param {string} fallbackMessage - Optional fallback message if key not found
 * @returns {Object} - {title, message}
 */
function getErrorMessage(errorKey, fallbackMessage = null) {
    if (ERROR_MESSAGES[errorKey]) {
        return ERROR_MESSAGES[errorKey];
    }

    return {
        title: 'Произошла ошибка',
        message: fallbackMessage || errorKey
    };
}

/**
 * Show error using toast system
 * @param {string} errorKey - Error key from ERROR_MESSAGES
 * @param {string} type - Toast type: 'success', 'error', 'warning', 'info'
 */
function showErrorToast(errorKey, type = 'error') {
    const errorData = getErrorMessage(errorKey);
    const message = `${errorData.title}: ${errorData.message}`;

    // Use existing toast system if available
    if (typeof utils !== 'undefined' && utils.showToast) {
        utils.showToast(message, type);
    } else {
        console.error(message);
    }
}

/**
 * Validate field and show error if invalid
 * @param {string} field - Field name
 * @param {any} value - Field value
 * @returns {boolean} - True if valid, false if invalid
 */
function validateField(field, value) {
    if (!value || value.toString().trim() === '') {
        if (field === 'address') {
            showErrorToast('missing_address', 'warning');
            return false;
        }
        return false;
    }

    switch (field) {
        case 'url':
            if (!value.includes('cian.ru')) {
                showErrorToast('invalid_url', 'warning');
                return false;
            }
            break;

        case 'price':
            if (isNaN(value) || parseFloat(value) <= 0) {
                showErrorToast('invalid_price', 'warning');
                return false;
            }
            break;

        case 'area':
        case 'total_area':
            if (isNaN(value) || parseFloat(value) <= 0) {
                showErrorToast('invalid_area', 'warning');
                return false;
            }
            break;

        case 'rooms':
            const rooms = parseInt(value);
            if (isNaN(rooms) || rooms < 1 || rooms > 10) {
                showErrorToast('invalid_rooms', 'warning');
                return false;
            }
            break;
    }

    return true;
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        ERROR_MESSAGES,
        getErrorMessage,
        showErrorToast,
        validateField
    };
}
