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
        message: 'Введите корректную ссылку. Поддерживаются объявления с ЦИАН (скоро: Авито, Яндекс, ДомКлик)'
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
        message: 'Не удалось загрузить данные с сайта. Проверьте корректность ссылки или попробуйте ввести данные вручную.'
    },
    'parsing_error': {
        title: 'Ошибка обработки',
        message: 'Не удалось обработать объявление. Попробуйте другую ссылку или введите данные вручную.'
    },
    'parsing_timeout': {
        title: 'Превышено время загрузки',
        message: 'Загрузка страницы заняла слишком много времени. Попробуйте другой объект или повторите попытку позже.'
    },
    'parsing_incomplete': {
        title: 'Неполные данные объекта',
        message: 'Объявление загружено, но отсутствуют важные данные (цена или площадь). Выберите другой объект.'
    },
    'signal_error': {
        title: 'Технический сбой',
        message: 'Произошел технический сбой при обработке запроса. Попробуйте еще раз через несколько секунд.'
    },
    'no_comparables': {
        title: 'Аналоги не найдены',
        message: 'Не удалось найти похожие объекты для сравнения. Попробуйте изменить параметры поиска.'
    },
    'analysis_failed': {
        title: 'Ошибка анализа',
        message: 'Не удалось выполнить анализ. Проверьте корректность введенных данных.'
    },

    // Ошибки поиска аналогов
    'search_error': {
        title: 'Ошибка поиска',
        message: 'Не удалось найти аналоги. Попробуйте изменить параметры поиска.'
    },
    'search_failed': {
        title: 'Поиск не удался',
        message: 'Не удалось выполнить поиск аналогов. Проверьте данные объекта или попробуйте добавить аналоги вручную.'
    },
    'session_error': {
        title: 'Сессия истекла',
        message: 'Ваша сессия истекла. Пожалуйста, начните сначала.'
    },
    'browser_error': {
        title: 'Техническая ошибка',
        message: 'Произошла техническая ошибка. Попробуйте повторить через несколько секунд.'
    },

    // Ошибки валидации данных
    'data_validation_error': {
        title: 'Ошибка данных',
        message: 'Некорректные данные аналогов. Проверьте введенную информацию.'
    },
    'calculation_error': {
        title: 'Ошибка расчетов',
        message: 'Не удалось выполнить расчеты. Возможно, отсутствуют необходимые данные.'
    },
    'missing_data_error': {
        title: 'Недостаточно данных',
        message: 'Отсутствуют необходимые поля данных. Проверьте полноту информации.'
    },
    'insufficient_comparables': {
        title: 'Мало аналогов',
        message: 'Недостаточно аналогов для анализа. Добавьте больше похожих объектов.'
    },
    'invalid_price_data': {
        title: 'Проблема с ценами',
        message: 'Некорректные данные о ценах. Проверьте цены у аналогов.'
    },
    'invalid_area_data': {
        title: 'Проблема с площадью',
        message: 'Некорректные данные о площади. Проверьте площади у аналогов.'
    },
    'duplicate_object': {
        title: 'Дубликат объекта',
        message: 'Этот объект уже добавлен в список аналогов. Попробуйте добавить другой объект.'
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
 * Translate technical error message to user-friendly Russian message
 * @param {string} technicalMessage - Technical error message (possibly in English)
 * @returns {string} - Error key from ERROR_MESSAGES
 */
function translateTechnicalError(technicalMessage) {
    if (!technicalMessage) {
        return 'unknown_error';
    }

    const msg = technicalMessage.toLowerCase();

    // Signal/threading errors
    if (msg.includes('signal') && msg.includes('main thread')) {
        return 'signal_error';
    }

    // Parsing errors
    if (msg.includes('parse') || msg.includes('парсинг')) {
        return 'parsing_error';
    }

    // Network errors
    if (msg.includes('network') || msg.includes('connection') || msg.includes('соединени')) {
        return 'network_error';
    }

    // Timeout errors
    if (msg.includes('timeout') || msg.includes('время')) {
        return 'timeout';
    }

    // Not found
    if (msg.includes('not found') || msg.includes('не найден')) {
        return 'no_data';
    }

    // Invalid data
    if (msg.includes('invalid') || msg.includes('некорректн')) {
        return 'parsing_failed';
    }

    // Server errors
    if (msg.includes('500') || msg.includes('internal server error')) {
        return 'server_error';
    }

    return 'unknown_error';
}

/**
 * Get formatted error message
 * @param {string} errorKey - Error key from ERROR_MESSAGES or technical message
 * @param {string} fallbackMessage - Optional fallback message if key not found
 * @returns {Object} - {title, message}
 */
function getErrorMessage(errorKey, fallbackMessage = null) {
    // First, try to use as direct key
    if (ERROR_MESSAGES[errorKey]) {
        return ERROR_MESSAGES[errorKey];
    }

    // Try to translate technical error
    const translatedKey = translateTechnicalError(errorKey);
    if (ERROR_MESSAGES[translatedKey]) {
        return ERROR_MESSAGES[translatedKey];
    }

    return {
        title: 'Произошла ошибка',
        message: fallbackMessage || 'Что-то пошло не так. Попробуйте еще раз.'
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
        translateTechnicalError,
        getErrorMessage,
        showErrorToast,
        validateField
    };
}
