/**
 * Wizard интерфейс для анализа недвижимости
 * Управляет 3-экранным процессом парсинга и анализа
 */

// Глобальное состояние
const state = {
    currentStep: 1,
    sessionId: null,
    targetProperty: null,
    comparables: [],
    analysis: null,
    csrfToken: null  // SECURITY: CSRF token for POST requests
};

// Утилиты
const utils = {
    showLoading(text = 'Загрузка...') {
        document.getElementById('loading-overlay').style.display = 'flex';
        document.getElementById('loading-text').textContent = text;
    },

    hideLoading() {
        document.getElementById('loading-overlay').style.display = 'none';
    },

    /**
     * Show toast notification with configurable duration
     * @param {string} message - Message to display
     * @param {string} type - 'success', 'error', 'warning', 'info'
     * @param {object} options - Optional: { duration, action: { text, onClick } }
     */
    showToast(message, type = 'info', options = {}) {
        const toast = document.getElementById('toast');
        const toastBody = document.getElementById('toast-body');

        // Default durations based on type (in ms)
        const defaultDurations = {
            success: 5000,
            info: 5000,
            warning: 6000,
            error: 8000  // Errors stay longer
        };

        const duration = options.duration || defaultDurations[type] || 5000;

        // Build message with optional action button
        if (options.action) {
            toastBody.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <span>${this.escapeHtml(message)}</span>
                    <button class="btn btn-sm btn-outline-dark ms-2 toast-action-btn">${this.escapeHtml(options.action.text)}</button>
                </div>
            `;
            // Attach click handler
            const actionBtn = toastBody.querySelector('.toast-action-btn');
            if (actionBtn && options.action.onClick) {
                actionBtn.addEventListener('click', () => {
                    options.action.onClick();
                    bootstrap.Toast.getInstance(toast)?.hide();
                });
            }
        } else {
            toastBody.textContent = message;
        }

        // Remove old toast type classes
        toast.classList.remove('toast-success', 'toast-error', 'toast-warning', 'toast-info');

        // Add new toast type class (for colored left border)
        toast.classList.add(`toast-${type}`);

        // Create toast with configured delay
        const bsToast = new bootstrap.Toast(toast, {
            delay: duration,
            autohide: true
        });
        bsToast.show();
    },

    formatPrice(price) {
        return new Intl.NumberFormat('ru-RU', {
            style: 'currency',
            currency: 'RUB',
            maximumFractionDigits: 0
        }).format(price);
    },

    formatNumber(num, decimals = 0) {
        return new Intl.NumberFormat('ru-RU', {
            maximumFractionDigits: decimals
        }).format(num);
    },

    /**
     * SECURITY: Escape HTML to prevent XSS
     * Используется для текста, который не должен содержать HTML
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * SECURITY: Sanitize HTML using DOMPurify
     * Используется когда нужно вставить HTML, но безопасно
     */
    sanitizeHtml(html) {
        if (typeof DOMPurify === 'undefined') {
            console.warn('DOMPurify not loaded, falling back to escapeHtml');
            return this.escapeHtml(html);
        }
        return DOMPurify.sanitize(html, {
            ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'div', 'span', 'p', 'br', 'ul', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'small'],
            ALLOWED_ATTR: ['href', 'target', 'class', 'style'],
            ALLOW_DATA_ATTR: false
        });
    },

    /**
     * SECURITY: Safely set innerHTML with DOMPurify
     */
    setInnerHTML(element, html) {
        if (!element) return;
        element.innerHTML = this.sanitizeHtml(html);
    },

    /**
     * SECURITY: Fetch CSRF token from server
     */
    async fetchCsrfToken() {
        try {
            const response = await fetch('/api/csrf-token');
            const data = await response.json();
            state.csrfToken = data.csrf_token;
            console.log('CSRF token fetched successfully');
        } catch (error) {
            console.error('Failed to fetch CSRF token:', error);
            utils.showToast('Ошибка получения токена безопасности', 'error');
        }
    },

    /**
     * SECURITY: Get headers with CSRF token for POST requests
     */
    getCsrfHeaders() {
        const headers = {
            'Content-Type': 'application/json'
        };
        if (state.csrfToken) {
            headers['X-CSRFToken'] = state.csrfToken;
        }
        return headers;
    },

    /**
     * Validate and normalize CIAN URL
     * @param {string} url - URL to validate
     * @returns {object} - { valid: boolean, url: string, error: string|null }
     */
    validateCianUrl(url) {
        if (!url || typeof url !== 'string') {
            return { valid: false, url: null, error: 'invalid_cian_url' };
        }

        // Trim and lowercase for checking
        const trimmedUrl = url.trim();

        // Pattern for CIAN flat URLs (sale/flat with numeric ID)
        // Supports any subdomain: www.cian.ru, spb.cian.ru, ekb.cian.ru, etc.
        // Region is detected on backend from address, not from URL
        const cianPattern = /^https?:\/\/([a-z0-9-]+\.)?cian\.ru\/sale\/flat\/\d+\/?$/i;

        // First, try to normalize the URL
        let normalizedUrl = trimmedUrl;

        // If URL doesn't match pattern, try to fix common issues
        if (!cianPattern.test(normalizedUrl)) {
            // Check if it's a cian.ru URL without any subdomain
            const noSubdomainPattern = /^https?:\/\/cian\.ru\/sale\/flat\/\d+\/?$/i;
            if (noSubdomainPattern.test(normalizedUrl)) {
                // Add www to the URL
                normalizedUrl = normalizedUrl.replace(/^(https?:\/\/)cian\.ru/i, '$1www.cian.ru');
            }
        }

        // Validate final URL
        if (cianPattern.test(normalizedUrl)) {
            return { valid: true, url: normalizedUrl, error: null };
        }

        return { valid: false, url: null, error: 'invalid_cian_url' };
    },

    /**
     * Session Management: Save session ID to localStorage
     */
    saveSessionToLocalStorage(sessionId) {
        try {
            localStorage.setItem('housler_session_id', sessionId);
            console.log('Session saved to localStorage:', sessionId);
        } catch (error) {
            console.error('Failed to save session to localStorage:', error);
        }
    },

    /**
     * Session Management: Get session ID from localStorage
     */
    getSessionFromLocalStorage() {
        try {
            return localStorage.getItem('housler_session_id');
        } catch (error) {
            console.error('Failed to get session from localStorage:', error);
            return null;
        }
    },

    /**
     * Session Management: Clear session from localStorage
     */
    clearSessionFromLocalStorage() {
        try {
            localStorage.removeItem('housler_session_id');
            console.log('Session cleared from localStorage');
        } catch (error) {
            console.error('Failed to clear session from localStorage:', error);
        }
    },

    /**
     * Session Management: Update URL with session ID
     */
    updateUrlWithSession(sessionId, step = null) {
        try {
            const url = new URL(window.location);
            url.searchParams.set('session', sessionId);
            if (step) {
                url.hash = `#step-${step}`;
            }
            window.history.replaceState({}, '', url);
            console.log('URL updated with session:', sessionId);
        } catch (error) {
            console.error('Failed to update URL:', error);
        }
    },

    /**
     * Session Management: Load session data from server
     */
    async loadSession(sessionId) {
        try {
            pixelLoader.show('parsing');
            console.log('Loading session:', sessionId);

            const response = await fetch(`/api/session/${sessionId}`);
            const result = await response.json();

            if (result.status === 'success' && result.data) {
                const sessionData = result.data;

                // Restore state
                state.sessionId = sessionId;
                state.targetProperty = sessionData.target_property || null;
                state.comparables = sessionData.comparables || [];
                state.analysis = sessionData.analysis || null;

                // Save to localStorage
                this.saveSessionToLocalStorage(sessionId);

                // Determine which step to go to based on available data
                let targetStep = 1;
                if (state.analysis) {
                    targetStep = 3;
                } else if (state.comparables.length > 0) {
                    targetStep = 2;
                } else if (state.targetProperty) {
                    targetStep = 1;
                }

                // ПРИОРИТЕТ: Check URL hash for step override (пользователь поделился ссылкой на конкретный шаг)
                const hash = window.location.hash;
                const hashMatch = hash.match(/#step-(\d+)/);
                if (hashMatch) {
                    const hashStep = parseInt(hashMatch[1]);
                    // Проверяем, что запрошенный шаг доступен
                    if (hashStep >= 1 && hashStep <= 3) {
                        // Если запрошен шаг 3, но анализа нет - игнорируем hash
                        if (hashStep === 3 && !state.analysis) {
                            console.warn('Шаг 3 запрошен, но анализа нет. Переход на доступный шаг:', targetStep);
                        }
                        // Если запрошен шаг 2, но аналогов нет - игнорируем hash
                        else if (hashStep === 2 && state.comparables.length === 0) {
                            console.warn('Шаг 2 запрошен, но аналогов нет. Переход на доступный шаг:', targetStep);
                        }
                        // Если данные есть - используем hash
                        else {
                            targetStep = hashStep;
                            console.log('Переход на шаг из URL hash:', targetStep);
                        }
                    }
                }

                // Display data in appropriate screens
                if (state.targetProperty) {
                    screen1.displayParseResult(state.targetProperty, []);
                }
                if (state.comparables.length > 0) {
                    screen2.renderComparables();
                }
                if (state.analysis) {
                    screen3.displayAnalysis(state.analysis);
                }

                // Navigate to the appropriate step
                navigation.goToStep(targetStep);

                // Update floating buttons
                if (window.floatingButtons) {
                    floatingButtons.updateButtons();
                }

                console.log(`Сессия загружена: шаг ${targetStep}, анализ: ${!!state.analysis}, аналогов: ${state.comparables.length}`);
                pixelLoader.complete();
                this.showToast('Сессия загружена успешно', 'success');
                return true;
            } else {
                console.warn('Session not found or expired:', sessionId);
                this.clearSessionFromLocalStorage();
                return false;
            }
        } catch (error) {
            console.error('Failed to load session:', error);
            this.showToast('Не удалось загрузить сессию', 'error');
            return false;
        } finally {
            pixelLoader.hide();
        }
    },

    /**
     * Session Management: Get current shareable URL
     */
    getShareableUrl() {
        if (!state.sessionId) {
            return null;
        }
        const url = new URL(window.location.origin + '/calculator');
        url.searchParams.set('session', state.sessionId);
        url.hash = `#step-${state.currentStep}`;
        return url.toString();
    },

    /**
     * Session Management: Copy shareable URL to clipboard
     */
    async copyShareableUrl() {
        const url = this.getShareableUrl();
        if (!url) {
            this.showToast('Нет активной сессии для шаринга', 'warning');
            return;
        }

        try {
            await navigator.clipboard.writeText(url);
            this.showToast('Ссылка скопирована в буфер обмена!', 'success');
        } catch (error) {
            console.error('Failed to copy URL:', error);
            this.showToast('Не удалось скопировать ссылку', 'error');
        }
    }
};

// Навигация между экранами
const navigation = {
    goToStep(step) {
        // Обновляем прогресс-бар
        document.querySelectorAll('.progress-step').forEach((el, index) => {
            const stepNum = index + 1;
            if (stepNum < step) {
                el.classList.add('completed');
                el.classList.remove('active');
            } else if (stepNum === step) {
                el.classList.add('active');
                el.classList.remove('completed');
            } else {
                el.classList.remove('active', 'completed');
            }
        });

        // Скрываем все экраны
        document.querySelectorAll('.wizard-screen').forEach(screen => {
            screen.classList.remove('active');
        });

        // Показываем нужный экран
        document.getElementById(`screen-${step}`).classList.add('active');

        state.currentStep = step;

        // Session Management: Update URL hash when navigating
        if (state.sessionId) {
            utils.updateUrlWithSession(state.sessionId, step);
        } else {
            // Just update hash if no session yet
            window.location.hash = `#step-${step}`;
        }

        // Автоматический запуск анализа при переходе на шаг 3
        if (step === 3 && state.sessionId && state.comparables.length > 0) {
            // Запускаем анализ автоматически, если есть данные
            setTimeout(() => {
                if (window.screen3) {
                    screen3.runAnalysis();
                }
            }, 300); // Небольшая задержка для плавного перехода
        }

        // Обновляем floating кнопки
        if (window.floatingButtons) {
            window.floatingButtons.updateButtons();
        }

        // Скроллим наверх
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
};

// Экран 1: Парсинг
const screen1 = {
    init() {
        document.getElementById('parse-btn').addEventListener('click', this.parse.bind(this));
        document.getElementById('manual-input-btn').addEventListener('click', this.showManualForm.bind(this));
        document.getElementById('cancel-manual-btn').addEventListener('click', this.hideManualForm.bind(this));
        document.getElementById('manual-property-form').addEventListener('submit', this.submitManualForm.bind(this));

        // Setup form validation
        this.setupFormValidation();
    },

    showManualForm() {
        document.getElementById('manual-input-form').style.display = 'block';
        // Скроллим к форме
        document.getElementById('manual-input-form').scrollIntoView({ behavior: 'smooth', block: 'start' });
        // Update required fields counter
        this.updateRequiredCounter();
    },

    hideManualForm() {
        document.getElementById('manual-input-form').style.display = 'none';
    },

    // === FORM VALIDATION ===

    requiredFields: [
        { id: 'manual-address', name: 'Адрес', minLength: 5 },
        { id: 'manual-price', name: 'Цена', min: 100000, max: 10000000000 },
        { id: 'manual-area', name: 'Площадь', min: 10, max: 1000 },
        { id: 'manual-rooms', name: 'Комнаты', isSelect: true }
    ],

    setupFormValidation() {
        // Add blur validation to required fields
        this.requiredFields.forEach(field => {
            const element = document.getElementById(field.id);
            if (element) {
                element.addEventListener('blur', () => this.validateField(field));
                element.addEventListener('input', () => {
                    // Remove error state on input
                    element.classList.remove('is-invalid');
                    this.updateRequiredCounter();
                });
                if (field.isSelect) {
                    element.addEventListener('change', () => {
                        element.classList.remove('is-invalid');
                        this.updateRequiredCounter();
                    });
                }
            }
        });

        // Initial counter update
        this.updateRequiredCounter();
    },

    validateField(field) {
        const element = document.getElementById(field.id);
        if (!element) return true;

        const value = element.value.trim();
        let isValid = true;
        let errorMessage = '';

        if (field.isSelect) {
            isValid = value !== '';
            errorMessage = `Выберите ${field.name.toLowerCase()}`;
        } else if (field.minLength) {
            isValid = value.length >= field.minLength;
            errorMessage = `${field.name}: минимум ${field.minLength} символов`;
        } else if (field.min !== undefined) {
            const numValue = parseFloat(value);
            if (isNaN(numValue) || numValue < field.min) {
                isValid = false;
                errorMessage = `${field.name}: минимум ${field.min.toLocaleString('ru-RU')}`;
            } else if (field.max && numValue > field.max) {
                isValid = false;
                errorMessage = `${field.name}: максимум ${field.max.toLocaleString('ru-RU')}`;
            }
        }

        if (!isValid) {
            element.classList.add('is-invalid');
            element.classList.remove('is-valid');
            // Update invalid-feedback text if exists
            const feedback = element.parentElement.querySelector('.invalid-feedback');
            if (feedback) feedback.textContent = errorMessage;
        } else if (value) {
            element.classList.remove('is-invalid');
            element.classList.add('is-valid');
        }

        this.updateRequiredCounter();
        return isValid;
    },

    validateAllFields() {
        let allValid = true;
        let firstInvalid = null;

        this.requiredFields.forEach(field => {
            const isValid = this.validateField(field);
            if (!isValid && !firstInvalid) {
                firstInvalid = document.getElementById(field.id);
            }
            if (!isValid) allValid = false;
        });

        // Scroll to first invalid field
        if (firstInvalid) {
            firstInvalid.focus();
            firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }

        return allValid;
    },

    getEmptyRequiredCount() {
        let count = 0;
        this.requiredFields.forEach(field => {
            const element = document.getElementById(field.id);
            if (element) {
                const value = element.value.trim();
                if (!value || (field.min !== undefined && parseFloat(value) < field.min)) {
                    count++;
                }
            }
        });
        return count;
    },

    updateRequiredCounter() {
        const counter = document.getElementById('required-fields-counter');
        if (!counter) return;

        const emptyCount = this.getEmptyRequiredCount();
        const countSpan = counter.querySelector('span');

        if (emptyCount > 0) {
            counter.style.display = 'block';
            if (countSpan) {
                // Склонение слова "поле"
                let word = 'полей';
                if (emptyCount === 1) word = 'поле';
                else if (emptyCount >= 2 && emptyCount <= 4) word = 'поля';
                countSpan.textContent = `${emptyCount} ${word}`;
            }
        } else {
            counter.style.display = 'none';
        }
    },

    async submitManualForm(e) {
        e.preventDefault();

        // Validate all required fields first
        if (!this.validateAllFields()) {
            const emptyCount = this.getEmptyRequiredCount();
            utils.showToast(`Заполните обязательные поля (${emptyCount})`, 'warning', {
                action: {
                    text: 'Показать',
                    onClick: () => {
                        // Scroll to first invalid field
                        const firstInvalid = document.querySelector('.is-invalid');
                        if (firstInvalid) {
                            firstInvalid.focus();
                            firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }
                    }
                }
            });
            return;
        }

        // Собираем данные из формы
        const rooms = document.getElementById('manual-rooms').value;
        const total_area = parseFloat(document.getElementById('manual-area').value);
        const price_raw = parseFloat(document.getElementById('manual-price').value);

        const formData = {
            address: document.getElementById('manual-address').value.trim(),
            price_raw: price_raw,
            total_area: total_area,
            rooms: rooms,
            floor: document.getElementById('manual-floor').value.trim(),
            living_area: parseFloat(document.getElementById('manual-living-area').value) || null,
            kitchen_area: parseFloat(document.getElementById('manual-kitchen-area').value) || null,
            repair_level: document.getElementById('manual-repair').value || 'стандартная',
            view_type: document.getElementById('manual-view').value || 'улица'
        };

        pixelLoader.show('parsing');

        try {
            const response = await fetch('/api/create-manual', {
                method: 'POST',
                headers: utils.getCsrfHeaders(),
                body: JSON.stringify(formData)
            });

            const result = await response.json();

            if (result.status === 'success') {
                state.sessionId = result.session_id;
                state.targetProperty = result.data;

                // Session Management: Save and update URL
                utils.saveSessionToLocalStorage(state.sessionId);
                utils.updateUrlWithSession(state.sessionId, 1);

                // Обновляем кнопки навигации
                if (window.floatingButtons) {
                    floatingButtons.updateButtons();
                }

                // Скрываем форму
                this.hideManualForm();

                // Показываем результат
                this.displayParseResult(result.data, result.missing_fields || []);
                pixelLoader.complete();
                utils.showToast('Объект создан!', 'success');
            } else {
                const errorData = getErrorMessage(result.message || 'parsing_error');
                utils.showToast(`${errorData.title}: ${errorData.message}`, 'error');
            }
        } catch (error) {
            console.error('Manual input error:', error);
            const errorData = getErrorMessage('network_error');
            utils.showToast(`${errorData.title}: ${errorData.message}`, 'error');
        } finally {
            pixelLoader.hide();
        }
    },

    async parse() {
        const rawUrl = document.getElementById('url-input').value.trim();

        if (!rawUrl) {
            utils.showToast('Введите URL объявления', 'warning');
            return;
        }

        // Validate and normalize CIAN URL
        const validation = utils.validateCianUrl(rawUrl);
        if (!validation.valid) {
            const errorData = getErrorMessage(validation.error);
            utils.showToast(`${errorData.title}: ${errorData.message}`, 'error');
            return;
        }

        const url = validation.url;
        pixelLoader.show('parsing');

        try {
            const response = await fetch('/api/parse', {
                method: 'POST',
                headers: utils.getCsrfHeaders(),
                body: JSON.stringify({ url })
            });

            const result = await response.json();

            if (result.status === 'success') {
                state.sessionId = result.session_id;
                state.targetProperty = result.data;

                // Session Management: Save and update URL
                utils.saveSessionToLocalStorage(state.sessionId);
                utils.updateUrlWithSession(state.sessionId, 1);

                // Обновляем кнопки навигации
                if (window.floatingButtons) {
                    floatingButtons.updateButtons();
                }

                this.displayParseResult(result.data, result.missing_fields);
                pixelLoader.complete();
                utils.showToast('Объект успешно загружен!', 'success');
            } else {
                // Используем getErrorMessage для перевода технических ошибок
                const errorData = getErrorMessage(result.message || 'parsing_error');
                utils.showToast(`${errorData.title}: ${errorData.message}`, 'error');
            }
        } catch (error) {
            console.error('Parse error:', error);
            // Используем getErrorMessage для обработки любых ошибок
            const errorData = getErrorMessage('network_error');
            utils.showToast(`${errorData.title}: ${errorData.message}`, 'error');
        } finally {
            pixelLoader.hide();
        }
    },

    displayParseResult(data, missingFields) {
        // Показываем результат
        document.getElementById('parse-result').style.display = 'block';

        // Отображаем основную информацию
        const propertyInfo = document.getElementById('property-info');
        propertyInfo.innerHTML = `
            <div class="col-md-12 mb-3">
                <h4>${data.title || 'Объект недвижимости'}</h4>
            </div>
            <div class="col-md-6 mb-2">
                <strong><i class="bi bi-currency-dollar me-2"></i>Цена:</strong>
                ${data.price ? utils.formatPrice(data.price_raw || data.price) : 'Не указана'}
            </div>
            <div class="col-md-6 mb-2">
                <strong><i class="bi bi-rulers me-2"></i>Площадь:</strong>
                ${data.total_area ? data.total_area + ' м²' : (data.area || 'Не указана')}
            </div>
            <div class="col-md-6 mb-2">
                <strong><i class="bi bi-door-open me-2"></i>Комнат:</strong>
                ${data.rooms || 'Не указано'}
            </div>
            <div class="col-md-6 mb-2">
                <strong><i class="bi bi-building me-2"></i>Этаж:</strong>
                ${data.floor || 'Не указан'}
            </div>
            <div class="col-md-12 mb-2">
                <strong><i class="bi bi-geo-alt me-2"></i>Адрес:</strong>
                ${data.address || 'Не указан'}
            </div>
            ${data.metro && data.metro.length > 0 ? `
            <div class="col-md-12 mb-2">
                <strong><i class="bi bi-train-front me-2"></i>Метро:</strong>
                ${data.metro.join(', ')}
            </div>
            ` : ''}
            ${data.residential_complex ? `
            <div class="col-md-12 mb-2">
                <strong><i class="bi bi-building me-2"></i>ЖК:</strong>
                ${data.residential_complex}
            </div>
            ` : ''}
        `;

        // Показываем характеристики если есть
        if (data.characteristics && Object.keys(data.characteristics).length > 0) {
            propertyInfo.innerHTML += `
                <div class="col-md-12 mt-3">
                    <h5><i class="bi bi-list-check me-2"></i>Характеристики</h5>
                    <div class="row">
                        ${Object.entries(data.characteristics).map(([key, value]) => `
                            <div class="col-md-6 mb-2">
                                <strong>${key}:</strong> ${value}
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        // Показываем недостающие поля
        if (missingFields && missingFields.length > 0) {
            document.getElementById('missing-fields').style.display = 'block';
            this.renderMissingFields(missingFields);

            // Автоматически скроллим к дополнительным полям с небольшой задержкой
            setTimeout(() => {
                const missingFieldsSection = document.getElementById('missing-fields');
                if (missingFieldsSection) {
                    missingFieldsSection.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                    // Показываем тост с подсказкой
                    utils.showToast('Пожалуйста, заполните дополнительные поля для точного анализа', 'info');
                }
            }, 500);
        }
    },

    renderMissingFields(fields) {
        const form = document.getElementById('missing-fields-form');
        form.innerHTML = fields.map(field => {
            if (field.type === 'boolean') {
                return `
                    <div class="mb-3 form-check">
                        <input type="checkbox" class="form-check-input" id="${field.field}" name="${field.field}" ${field.default ? 'checked' : ''}>
                        <label class="form-check-label" for="${field.field}">
                            <strong>${field.label}</strong>
                            <small class="text-muted d-block">${field.description}</small>
                        </label>
                    </div>
                `;
            } else if (field.type === 'select') {
                return `
                    <div class="mb-3">
                        <label for="${field.field}" class="form-label"><strong>${field.label}</strong></label>
                        <select class="form-select" id="${field.field}" name="${field.field}">
                            ${field.options.map(opt => `
                                <option value="${opt}" ${opt === field.default ? 'selected' : ''}>${opt}</option>
                            `).join('')}
                        </select>
                        <small class="form-text text-muted">${field.description}</small>
                    </div>
                `;
            } else if (field.type === 'number') {
                return `
                    <div class="mb-3">
                        <label for="${field.field}" class="form-label"><strong>${field.label}</strong></label>
                        <input
                            type="number"
                            class="form-control"
                            id="${field.field}"
                            name="${field.field}"
                            value="${field.default || ''}"
                            min="${field.min || ''}"
                            max="${field.max || ''}"
                            step="0.1"
                        >
                        <small class="form-text text-muted">${field.description}</small>
                    </div>
                `;
            }
        }).join('');
    },

    async updateTargetProperty() {
        const form = document.getElementById('missing-fields-form');

        // Если формы нет (нет недостающих полей), сразу переходим на следующий шаг
        if (!form || !form.querySelector('[name]')) {
            navigation.goToStep(2);
            return;
        }

        const formData = new FormData(form);
        const data = {};

        formData.forEach((value, key) => {
            // Преобразуем типы
            const input = form.querySelector(`[name="${key}"]`);
            if (input.type === 'checkbox') {
                data[key] = input.checked;
            } else if (input.type === 'number') {
                data[key] = parseFloat(value) || 0;
            } else {
                data[key] = value;
            }
        });

        // Если есть данные для сохранения
        if (Object.keys(data).length > 0) {
            pixelLoader.show('parsing');

            try {
                const response = await fetch('/api/update-target', {
                    method: 'POST',
                    headers: utils.getCsrfHeaders(),
                    body: JSON.stringify({
                        session_id: state.sessionId,
                        data
                    })
                });

                const result = await response.json();

                if (result.status === 'success') {
                    Object.assign(state.targetProperty, data);

                    // Скрываем форму недостающих полей
                    document.getElementById('missing-fields').style.display = 'none';

                    pixelLoader.complete();
                    utils.showToast('Данные сохранены', 'success');

                    // Переходим на шаг 2
                    navigation.goToStep(2);
                } else {
                    const errorData = getErrorMessage(result.message || 'parsing_error');
                    utils.showToast(`${errorData.title}: ${errorData.message}`, 'error');
                }
            } catch (error) {
                console.error('Update error:', error);
                const errorData = getErrorMessage('network_error');
                utils.showToast(`${errorData.title}: ${errorData.message}`, 'error');
            } finally {
                pixelLoader.hide();
            }
        } else {
            // Нет данных для сохранения, просто переходим
            navigation.goToStep(2);
        }
    }
};

// Экран 2: Аналоги
const screen2 = {
    init() {
        document.getElementById('find-similar-btn').addEventListener('click', this.findSimilar.bind(this));
        document.getElementById('add-comparable-btn').addEventListener('click', this.addComparable.bind(this));
    },

    async findSimilar() {
        pixelLoader.show('searching');

        try {
            const response = await fetch('/api/find-similar', {
                method: 'POST',
                headers: utils.getCsrfHeaders(),
                body: JSON.stringify({
                    session_id: state.sessionId,
                    limit: 50  // Увеличено до 50 чтобы не терять объекты
                })
            });

            const result = await response.json();

            if (result.status === 'success') {
                // Debug logging - trace object count
                console.log('🔍 DEBUG: Received comparables from API:', result.comparables.length);
                console.log('🔍 DEBUG: API reported count:', result.count);

                // FIX ISSUE #2: Normalize data format for frontend compatibility
                state.comparables = result.comparables.map(comp => ({
                    ...comp,
                    // Ensure 'area' field exists (backend returns 'total_area')
                    area: comp.area || comp.total_area || null,
                    // Ensure 'price' field exists (backend might return 'price_raw')
                    price: comp.price || comp.price_raw || null,
                    // Ensure 'title' field exists for display
                    title: comp.title || comp.address || 'Объект недвижимости',
                    // Ensure excluded flag exists
                    excluded: comp.excluded || false
                }));
                console.log('🔍 DEBUG: State comparables normalized and set to:', state.comparables.length);
                console.log('🔍 DEBUG: Sample comparable:', state.comparables[0]);

                this.renderComparables();

                // Обновляем кнопки навигации (для разблокировки "К анализу")
                if (window.floatingButtons) {
                    floatingButtons.updateButtons();
                }

                // ДОРАБОТКА #4: Отображение предупреждений о качестве аналогов
                pixelLoader.complete();
                if (result.warnings && result.warnings.length > 0) {
                    this.showQualityWarnings(result.warnings);
                } else {
                    utils.showToast(`Найдено ${result.count} похожих объектов`, 'success');
                }
            } else {
                // Show detailed error message
                let errorMessage = result.message || 'no_comparables';
                let errorDetails = result.details || '';

                console.error('Find similar failed:', errorMessage, errorDetails);

                const errorData = getErrorMessage(errorMessage);
                const fullMessage = errorDetails ?
                    `${errorData.title}: ${errorDetails}` :
                    `${errorData.title}: ${errorData.message}`;

                utils.showToast(fullMessage, 'error');
            }
        } catch (error) {
            console.error('Find similar error:', error);
            const errorData = getErrorMessage('network_error');
            utils.showToast(`${errorData.title}: ${errorData.message}`, 'error');
        } finally {
            pixelLoader.hide();
        }
    },

    async addComparable() {
        const rawUrl = document.getElementById('add-comparable-input').value.trim();

        if (!rawUrl) {
            utils.showToast('Введите URL объявления', 'warning');
            return;
        }

        // Validate and normalize CIAN URL
        const validation = utils.validateCianUrl(rawUrl);
        if (!validation.valid) {
            const errorData = getErrorMessage(validation.error);
            utils.showToast(`${errorData.title}: ${errorData.message}`, 'error');
            return;
        }

        const url = validation.url;
        pixelLoader.show('searching');

        try {
            const response = await fetch('/api/add-comparable', {
                method: 'POST',
                headers: utils.getCsrfHeaders(),
                body: JSON.stringify({
                    session_id: state.sessionId,
                    url
                })
            });

            const result = await response.json();

            if (result.status === 'success') {
                state.comparables.push(result.comparable);
                this.renderComparables();

                // Обновляем кнопки навигации (для разблокировки "К анализу")
                if (window.floatingButtons) {
                    floatingButtons.updateButtons();
                }

                document.getElementById('add-comparable-input').value = '';
                pixelLoader.complete();
                utils.showToast('Объект добавлен', 'success');
            } else {
                // Show detailed error message
                let errorMessage = result.message || 'parsing_error';
                let errorDetails = result.details || '';

                console.error('Add comparable failed:', errorMessage, errorDetails);

                const errorData = getErrorMessage(errorMessage);
                const fullMessage = errorDetails ?
                    `${errorData.title}: ${errorDetails}` :
                    `${errorData.title}: ${errorData.message}`;

                utils.showToast(fullMessage, 'error');
            }
        } catch (error) {
            console.error('Add comparable error:', error);
            const errorData = getErrorMessage('network_error');
            utils.showToast(`${errorData.title}: ${errorData.message}`, 'error');
        } finally {
            pixelLoader.hide();
        }
    },

    renderComparables() {
        try {
            const container = document.getElementById('comparables-list');

            if (!container) {
                console.error('❌ ERROR: comparables-list container not found in DOM');
                return;
            }

            console.log('🔍 DEBUG: renderComparables called with', state.comparables.length, 'items');

            if (state.comparables.length === 0) {
                container.innerHTML = `
                    <div class="alert alert-info">
                        <i class="bi bi-info-circle me-2"></i>
                        Нажмите кнопку "Автоматически найти" или добавьте объекты вручную
                    </div>
                `;
                return;
            }

            // FIX ISSUE #2: Render comparables list with error handling
            container.innerHTML = `
                <div class="mb-3">
                    <h5>Найдено аналогов: ${state.comparables.filter(c => !c.excluded).length} / ${state.comparables.length}</h5>
                </div>
                ${state.comparables.map((comp, index) => {
                    try {
                        return this.renderComparableCard(comp, index);
                    } catch (err) {
                        console.error('❌ ERROR rendering comparable card', index, ':', err, comp);
                        return `<div class="alert alert-warning">Ошибка отображения объекта ${index + 1}</div>`;
                    }
                }).join('')}
            `;

            console.log('✅ Successfully rendered', state.comparables.length, 'comparables');
        } catch (error) {
            console.error('❌ CRITICAL ERROR in renderComparables:', error);
            console.error('State comparables:', state.comparables);
        }
    },

    renderComparableCard(comp, index) {
        const excluded = comp.excluded || false;

        // FIX ISSUE #2: Format price properly (handle both string and number)
        let priceText = 'Цена не указана';
        if (comp.price) {
            priceText = typeof comp.price === 'number' ?
                `${utils.formatNumber(comp.price)} ₽` :
                comp.price;
        }

        // Форматируем цену за кв.м
        let pricePerSqmText = '';
        if (comp.price_per_sqm) {
            pricePerSqmText = `<div class="detail-item" style="font-weight: 600; color: var(--black);"><i class="bi bi-cash-stack"></i> ${utils.formatNumber(comp.price_per_sqm)} ₽/м²</div>`;
        }

        // FIX ISSUE #2: Format area properly (handle both string and number)
        let areaText = '';
        if (comp.area) {
            areaText = typeof comp.area === 'number' ?
                `<div class="detail-item"><i class="bi bi-rulers"></i> ${comp.area.toFixed(1)} м²</div>` :
                `<div class="detail-item"><i class="bi bi-rulers"></i> ${comp.area}</div>`;
        }

        // Форматируем ремонт
        let renovationText = '';
        if (comp.renovation) {
            renovationText = `<div class="detail-item"><i class="bi bi-paint-bucket"></i> ${comp.renovation}</div>`;
        }

        return `
            <div class="property-card ${excluded ? 'excluded' : ''}" data-index="${index}">
                <div class="property-title text-truncate-2">
                    ${comp.title || 'Объект недвижимости'}
                </div>
                <div class="property-price">
                    ${priceText}
                </div>
                <div class="property-details">
                    ${pricePerSqmText}
                    ${comp.rooms ? `<div class="detail-item"><i class="bi bi-door-open"></i> ${comp.rooms} комн.</div>` : ''}
                    ${areaText}
                    ${comp.floor ? `<div class="detail-item"><i class="bi bi-building"></i> ${comp.floor}</div>` : ''}
                    ${renovationText}
                    ${comp.metro ? `<div class="detail-item"><i class="bi bi-train-front"></i> ${comp.metro}</div>` : ''}
                </div>
                ${comp.address ? `<div class="text-muted small mb-2"><i class="bi bi-geo-alt"></i> ${comp.address}</div>` : ''}
                <div class="property-actions">
                    <a href="${comp.url}" target="_blank" class="btn btn-sm btn-outline-dark">
                        <i class="bi bi-box-arrow-up-right"></i> Открыть
                    </a>
                    ${!excluded ? `
                        <button class="btn btn-sm btn-outline-danger" onclick="screen2.excludeComparable(${index})">
                            <i class="bi bi-x-circle"></i> Исключить
                        </button>
                    ` : `
                        <button class="btn btn-sm btn-outline-success" onclick="screen2.includeComparable(${index})">
                            <i class="bi bi-check-circle"></i> Вернуть
                        </button>
                    `}
                </div>
            </div>
        `;
    },

    async excludeComparable(index) {
        try {
            await fetch('/api/exclude-comparable', {
                method: 'POST',
                headers: utils.getCsrfHeaders(),
                body: JSON.stringify({
                    session_id: state.sessionId,
                    index
                })
            });

            state.comparables[index].excluded = true;
            this.renderComparables();

            // Обновляем кнопки навигации (может заблокировать "К анализу")
            if (window.floatingButtons) {
                floatingButtons.updateButtons();
            }

            utils.showToast('Объект исключен из анализа', 'info');
        } catch (error) {
            console.error('Exclude error:', error);
            const errorData = getErrorMessage('network_error');
            utils.showToast(`${errorData.title}: ${errorData.message}`, 'error');
        }
    },

    async includeComparable(index) {
        try {
            await fetch('/api/include-comparable', {
                method: 'POST',
                headers: utils.getCsrfHeaders(),
                body: JSON.stringify({
                    session_id: state.sessionId,
                    index
                })
            });

            state.comparables[index].excluded = false;
            this.renderComparables();

            // Обновляем кнопки навигации (может разблокировать "К анализу")
            if (window.floatingButtons) {
                floatingButtons.updateButtons();
            }

            utils.showToast('Объект возвращен в анализ', 'success');
        } catch (error) {
            console.error('Include error:', error);
            utils.showToast('Ошибка включения', 'error');
        }
    },

    showQualityWarnings(warnings) {
        /**
         * ДОРАБОТКА #4: Отображение предупреждений о качестве аналогов
         *
         * Показывает алерты с предупреждениями о проблемах с подобранными аналогами:
         * - error (красный): критичные проблемы (мало аналогов, нет цен, очень большой разброс)
         * - warning (желтый): некритичные проблемы (средний разброс, неполные данные)
         */
        const container = document.getElementById('comparables-list');

        // Группируем warnings по типу
        const errors = warnings.filter(w => w.type === 'error');
        const warningsOnly = warnings.filter(w => w.type === 'warning');

        let alertsHtml = '';

        // Показываем errors (критичные)
        errors.forEach(warning => {
            alertsHtml += `
                <div class="alert alert-danger alert-dismissible fade show mb-3" role="alert">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>
                    <strong>${warning.title}</strong><br>
                    ${warning.message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            `;
        });

        // Показываем warnings (некритичные)
        warningsOnly.forEach(warning => {
            alertsHtml += `
                <div class="alert alert-warning alert-dismissible fade show mb-3" role="alert">
                    <i class="bi bi-exclamation-circle-fill me-2"></i>
                    <strong>${warning.title}</strong><br>
                    ${warning.message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            `;
        });

        // Вставляем алерты в начало контейнера
        container.insertAdjacentHTML('afterbegin', alertsHtml);

        // Также показываем toast для быстрого уведомления
        if (errors.length > 0) {
            utils.showToast(`Обнаружено ${errors.length + warningsOnly.length} проблем с аналогами. Проверьте предупреждения выше.`, 'warning');
        } else if (warningsOnly.length > 0) {
            utils.showToast(`Найдено ${state.comparables.length} аналогов (есть ${warningsOnly.length} замечание)`, 'info');
        }
    }
};

// Экран 3: Анализ
const screen3 = {
    init() {
        // Кнопка "Рассчитать анализ" удалена - анализ запускается автоматически
    },

    async runAnalysis() {
        pixelLoader.show('analyzing');

        // Показываем skeleton-плейсхолдеры пока грузятся данные
        const resultsContainer = document.getElementById('analysis-results');
        if (resultsContainer) {
            resultsContainer.style.display = 'block';
            skeletonLoader.showForReport('fair-price-details');
        }

        try {
            console.log('🔄 Запуск анализа для сессии:', state.sessionId);

            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: utils.getCsrfHeaders(),
                body: JSON.stringify({
                    session_id: state.sessionId,
                    filter_outliers: true,
                    use_median: true
                })
            });

            console.log('📡 Получен ответ от сервера, статус:', response.status);

            const result = await response.json();
            console.log('📦 Данные ответа:', result);

            if (result.status === 'success') {
                console.log('✅ Анализ успешен, данные:', result.analysis);
                state.analysis = result.analysis;
                this.displayAnalysis(result.analysis);
                pixelLoader.complete();
                utils.showToast('Анализ завершен!', 'success');
            } else {
                console.error('❌ Ошибка анализа:', result);
                const errorData = getErrorMessage(result.message || 'analysis_failed');
                utils.showToast(`${errorData.title}: ${errorData.message}`, 'error');

                // Показываем техническую информацию для диагностики
                if (result.technical_details) {
                    console.error('Технические детали:', result.technical_details);
                }
            }
        } catch (error) {
            console.error('❌ Критическая ошибка анализа:', error);
            const errorData = getErrorMessage('network_error');
            utils.showToast(`${errorData.title}: ${errorData.message}`, 'error');
        } finally {
            pixelLoader.hide();
        }
    },

    displayAnalysis(analysis) {
        console.log('📊 Отображение анализа:', analysis);

        try {
            // Валидация структуры данных
            if (!analysis) {
                throw new Error('Данные анализа отсутствуют');
            }

            if (!analysis.market_statistics || !analysis.market_statistics.all) {
                throw new Error('Отсутствуют данные рыночной статистики');
            }

            if (!analysis.fair_price_analysis) {
                throw new Error('Отсутствуют данные о справедливой цене');
            }

            // PATCH: Проверяем достаточность данных
            if (analysis.market_statistics.all.count === 0) {
                throw new Error('Недостаточно аналогов для анализа. После фильтрации не осталось подходящих объектов.');
            }

            if (analysis.fair_price_analysis.status === 'insufficient_data') {
                console.warn('⚠️ Недостаточно данных для расчета справедливой цены');
                // Продолжаем показ результатов, но с предупреждением
            }

            document.getElementById('analysis-results').style.display = 'block';

            // Сводная информация
            this.renderSummary(analysis);

            // Справедливая цена
            this.renderFairPrice(analysis.fair_price_analysis);

            // Сценарии
            this.renderScenarios(analysis.price_scenarios);

            // Сильные/слабые стороны
            this.renderStrengthsWeaknesses(analysis.strengths_weaknesses);

            // График
            this.renderChart(analysis.comparison_chart_data);

            // Рекомендации (показываем всегда, даже если пустые)
            const recommendations = analysis.recommendations || [];
            this.renderRecommendations(recommendations);

            // Персонализированный оффер Housler
            if (analysis.housler_offer) {
                this.renderHouslerOffer(analysis.housler_offer);
            }
        } catch (error) {
            console.error('❌ Ошибка отображения анализа:', error);
            utils.showToast(`Ошибка отображения результатов: ${error.message}`, 'error');

            // Показываем хотя бы частичные данные, если они есть
            document.getElementById('analysis-results').style.display = 'block';
            const summaryInfo = document.getElementById('summary-info');
            if (summaryInfo) {
                summaryInfo.innerHTML = `
                    <div class="alert alert-warning">
                        <h5>⚠️ Ошибка отображения результатов</h5>
                        <p><strong>Причина:</strong> ${error.message}</p>
                        <p>Пожалуйста, проверьте данные и попробуйте снова, или обратитесь в поддержку.</p>
                        <hr>
                        <p class="mb-0"><small>Для диагностики откройте консоль браузера (F12) и проверьте логи.</small></p>
                    </div>
                `;
            }
        }
    },

    renderSummary(analysis) {
        const summaryInfo = document.getElementById('summary-info');
        const target = analysis.target_property;
        const stats = analysis.market_statistics.all;

        summaryInfo.innerHTML = `
            <div class="row">
                <div class="col-md-4 mb-3">
                    <div class="metric-item">
                        <div class="metric-label">Целевая цена</div>
                        <div class="metric-value">${utils.formatPrice(target.price || 0)}</div>
                    </div>
                </div>
                <div class="col-md-4 mb-3">
                    <div class="metric-item">
                        <div class="metric-label">Медиана рынка</div>
                        <div class="metric-value">${utils.formatPrice(stats.median || 0)} / м²</div>
                    </div>
                </div>
                <div class="col-md-4 mb-3">
                    <div class="metric-item">
                        <div class="metric-label">Аналогов в анализе</div>
                        <div class="metric-value">${stats.count || 0}</div>
                    </div>
                </div>
            </div>
        `;
    },

    renderFairPrice(fairPrice) {
        const container = document.getElementById('fair-price-details');

        // PATCH: Проверяем статус данных
        if (fairPrice.status === 'insufficient_data') {
            container.innerHTML = `
                <div class="alert alert-warning">
                    <h5>⚠️ Недостаточно данных для расчета</h5>
                    <p>${fairPrice.detailed_report || 'Недостаточно аналогов для расчета справедливой цены'}</p>
                </div>
            `;
            return;
        }

        const overpricing = fairPrice.overpricing_percent || 0;

        const overpricingClass = overpricing > 10 ? 'danger' : overpricing > 5 ? 'warning' : 'success';
        const overpricingIcon = overpricing > 0 ? 'arrow-up' : 'arrow-down';

        container.innerHTML = `
            <div class="row mb-3">
                <div class="col-md-6">
                    <div class="metric-item">
                        <div class="metric-label">Базовая цена/м²</div>
                        <div class="metric-value">${utils.formatPrice(fairPrice.base_price_per_sqm || 0)}</div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="metric-item">
                        <div class="metric-label">Справедливая цена</div>
                        <div class="metric-value text-success">${utils.formatPrice(fairPrice.fair_price_total || 0)}</div>
                    </div>
                </div>
            </div>
            <div class="alert alert-${overpricingClass}">
                <strong><i class="bi bi-${overpricingIcon} me-2"></i>Переоценка:</strong>
                ${utils.formatNumber(Math.abs(overpricing), 2)}%
                ${overpricing > 0 ? '(цена выше справедливой)' : '(цена ниже справедливой)'}
            </div>
            <div class="mt-3">
                <div class="alert alert-info mb-3">
                    <strong>💡 Что такое "медиана"?</strong><br>
                    Медиана — это среднее значение параметра по всем аналогам на рынке.
                    Половина объектов лучше медианы, половина хуже. Мы сравниваем ваш объект с медианой,
                    чтобы понять, насколько он отличается от типичного предложения.
                </div>
                <h6>Сравнение с рынком:</h6>
                <p class="text-muted small mb-3">Показываем, как ваши параметры отличаются от медианы рынка и как это влияет на цену</p>
                <div class="table-responsive">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>Параметр</th>
                                <th>У вас</th>
                                <th>Медиана рынка</th>
                                <th>Влияние на цену</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${Object.entries(fairPrice.adjustments || {}).map(([key, adj]) => {
                                const impact = (adj.value - 1) * 100;
                                const impactClass = impact > 0 ? 'text-success' : impact < 0 ? 'text-danger' : 'text-muted';
                                const impactIcon = impact > 0 ? '↑' : impact < 0 ? '↓' : '=';

                                // Парсим описание: "Параметр: значение1 vs значение2 (медиана)"
                                const descParts = (adj.description || '').split(':');
                                const paramName = descParts[0] || key;
                                const valuePart = descParts[1] || '';
                                const values = valuePart.split(' vs ');
                                const yourValue = (values[0] || '').trim();
                                const medianValue = (values[1] || '').replace('(медиана)', '').trim();

                                return `
                                <tr>
                                    <td><strong>${paramName}</strong></td>
                                    <td>${yourValue || '-'}</td>
                                    <td>${medianValue || '-'}</td>
                                    <td class="${impactClass}">
                                        <strong>${impactIcon} ${utils.formatNumber(Math.abs(impact), 2)}%</strong>
                                    </td>
                                </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    },

    renderScenarios(scenarios) {
        const container = document.getElementById('scenarios-list');

        container.innerHTML = scenarios.map(scenario => `
            <div class="scenario-card">
                <div class="scenario-header">
                    <div class="scenario-title">${scenario.name}</div>
                    <span class="scenario-badge badge" style="background: var(--black); color: var(--white);">${scenario.time_months} мес</span>
                </div>
                <div class="scenario-description">${scenario.description}</div>
                <div class="scenario-metrics">
                    <div class="metric-item">
                        <div class="metric-label">Начальная цена</div>
                        <div class="metric-value">${utils.formatPrice(scenario.start_price)}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Ожидаемая итоговая</div>
                        <div class="metric-value text-success">${utils.formatPrice(scenario.expected_final_price)}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Вероятность</div>
                        <div class="metric-value">${scenario.base_probability}%</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Чистый доход</div>
                        <div class="metric-value">${utils.formatPrice(scenario.financials.net_after_opportunity)}</div>
                    </div>
                </div>
            </div>
        `).join('');
    },

    renderStrengthsWeaknesses(data) {
        const container = document.getElementById('strengths-weaknesses');

        container.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    <h6 class="text-success"><i class="bi bi-check-circle me-2"></i>Сильные стороны</h6>
                    ${data.strengths.map(s => `
                        <div class="strength-item">
                            <span class="factor-name">${s.factor}</span>
                            <span class="factor-impact">+${s.premium_percent}%</span>
                        </div>
                    `).join('')}
                    ${data.strengths.length === 0 ? '<p class="text-muted">Нет выраженных сильных сторон</p>' : ''}
                </div>
                <div class="col-md-6">
                    <h6 class="text-danger"><i class="bi bi-x-circle me-2"></i>Слабые стороны</h6>
                    ${data.weaknesses.map(w => `
                        <div class="weakness-item">
                            <span class="factor-name">${w.factor}</span>
                            <span class="factor-impact">-${w.discount_percent}%</span>
                        </div>
                    `).join('')}
                    ${data.weaknesses.length === 0 ? '<p class="text-muted">Нет выраженных слабых сторон</p>' : ''}
                </div>
            </div>
            <div class="mt-3 alert alert-info">
                <strong>Итого:</strong> Премия ${data.total_premium_percent}% - Скидка ${data.total_discount_percent}% =
                <strong>${data.net_adjustment > 0 ? '+' : ''}${data.net_adjustment}%</strong>
            </div>
        `;
    },

    renderChart(chartData) {
        const ctx = document.getElementById('comparison-chart');

        if (window.comparisonChart) {
            window.comparisonChart.destroy();
        }

        window.comparisonChart = new Chart(ctx, {
            type: 'bar',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: false
                    },
                    title: {
                        display: true,
                        text: 'Сравнение цен за м² (млн ₽)'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    },

    renderRecommendations(recommendations) {
        const container = document.getElementById('recommendations-list');
        const recommendationsContainer = document.getElementById('recommendations-container');

        // ВСЕГДА показываем контейнер рекомендаций
        recommendationsContainer.style.display = 'block';

        // Если нет рекомендаций, показываем сообщение
        if (!recommendations || recommendations.length === 0) {
            container.innerHTML = '<p class="text-muted">Нет рекомендаций для данного объекта</p>';
            return;
        }

        // Группируем рекомендации по приоритету
        const priorities = {
            1: { label: 'КРИТИЧНО', emoji: '🔴', class: 'danger', recs: [] },
            2: { label: 'ВАЖНО', emoji: '🟠', class: 'warning', recs: [] },
            3: { label: 'СРЕДНЕ', emoji: '🟡', class: 'info', recs: [] },
            4: { label: 'ИНФО', emoji: '🔵', class: 'secondary', recs: [] }
        };

        recommendations.forEach(rec => {
            const priority = rec.priority || 4;
            if (priorities[priority]) {
                priorities[priority].recs.push(rec);
            }
        });

        // Формируем HTML
        let html = '';
        for (let priority = 1; priority <= 4; priority++) {
            const priorityData = priorities[priority];
            const recs = priorityData.recs;

            if (recs.length > 0) {
                html += `
                    <div class="recommendation-priority-group mb-4">
                        <h6 class="mb-3">
                            ${priorityData.emoji} <span class="badge bg-${priorityData.class}">${priorityData.label}</span>
                        </h6>
                `;

                recs.forEach(rec => {
                    const icon = rec.icon || '💡';
                    const title = rec.title || '';
                    const message = rec.message || '';
                    const action = rec.action || '';
                    const expected = rec.expected_result || '';
                    const roi = rec.roi;
                    const financial = rec.financial_impact || {};

                    html += `
                        <div class="card mb-3 shadow-sm">
                            <div class="card-body">
                                <h6 class="card-title">${icon} ${title}</h6>
                                <p class="card-text"><strong>Проблема:</strong> ${message}</p>
                                <p class="card-text"><strong>Действие:</strong> ${action}</p>
                                <p class="card-text text-success"><strong>Ожидаемый результат:</strong> ${expected}</p>
                    `;

                    // ROI если есть
                    if (roi != null && roi > 0) {
                        html += `<p class="card-text"><strong>ROI:</strong> <span class="badge bg-success">${roi.toFixed(1)}%</span></p>`;
                    }

                    // Финансовый эффект если есть
                    if (Object.keys(financial).length > 0) {
                        html += '<div class="alert alert-light mt-2"><strong>Финансовый эффект:</strong><ul class="mb-0 mt-2">';

                        // Маппинг технических названий на понятные
                        const keyLabels = {
                            'investment': 'Инвестиции',
                            'views_increase_percent': 'Увеличение просмотров',
                            'conversion_boost_percent': 'Увеличение конверсии',
                            'estimated_time_reduction': 'Сокращение времени продажи',
                            'expected_time': 'Ожидаемое время',
                            'expected_time_months': 'Ожидаемое время',
                            'торг_диапазон': 'Диапазон торга',
                            'expected_value': 'Ожидаемый доход',
                            'net_profit': 'Чистая прибыль',
                            'probability_percent': 'Вероятность',
                            'scenario': 'Сценарий',
                            'difference': 'Разница',
                            'explanation': 'Пояснение',
                            'fast_scenario_expected': 'Быстрая продажа (ожидаемое)',
                            'max_scenario_expected': 'Максимум (ожидаемое)'
                        };

                        for (const [key, value] of Object.entries(financial)) {
                            const label = keyLabels[key] || key;

                            if (typeof value === 'number') {
                                if (Math.abs(value) > 1000) {
                                    // Большие числа - это деньги
                                    html += `<li><strong>${label}:</strong> ${utils.formatPrice(value)}</li>`;
                                } else if (key.includes('percent')) {
                                    // Проценты
                                    html += `<li><strong>${label}:</strong> ${value}%</li>`;
                                } else if (key.includes('months')) {
                                    // Месяцы
                                    html += `<li><strong>${label}:</strong> ${value} мес.</li>`;
                                } else {
                                    html += `<li><strong>${label}:</strong> ${value}</li>`;
                                }
                            } else {
                                html += `<li><strong>${label}:</strong> ${value}</li>`;
                            }
                        }
                        html += '</ul></div>';
                    }

                    html += `
                            </div>
                        </div>
                    `;
                });

                html += `</div>`;
            }
        }

        if (html === '') {
            html = '<p class="text-muted">Нет рекомендаций для данного объекта</p>';
        }

        container.innerHTML = html;
    },

    renderHouslerOffer(offer) {
        const container = document.getElementById('housler-offer-container');
        if (!container) {
            // Создаем контейнер если его нет
            const recommendationsContainer = document.getElementById('recommendations-container');
            const newContainer = document.createElement('div');
            newContainer.id = 'housler-offer-container';
            newContainer.className = 'section mt-5';
            recommendationsContainer.parentNode.insertBefore(newContainer, recommendationsContainer.nextSibling);
        }

        const { situation, goal, actions, result, commission_option, prepay_option, price_tier } = offer;

        let html = `
            <div style="border-top: 1px solid var(--gray-300); padding-top: var(--spacing-3xl); margin-top: var(--spacing-3xl);">

                <!-- Заголовок секции -->
                <h2 style="font-size: var(--text-2xl); font-weight: 400; letter-spacing: -0.02em; margin-bottom: var(--spacing-xl); color: var(--black);">
                    Как Housler продаст ваш объект
                </h2>

                <!-- Текущая ситуация -->
                <div style="background: var(--gray-100); padding: var(--spacing-xl); border-left: 2px solid var(--gray-800); margin-bottom: var(--spacing-xl);">
                    <div style="font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.1em; color: var(--gray-600); margin-bottom: var(--spacing-sm); font-weight: 500;">
                        Первичный анализ
                    </div>
                    <div style="font-size: var(--text-base); line-height: var(--leading-relaxed); color: var(--gray-800);">
        `;

        // Анализ ситуации в зависимости от статуса цены
        if (situation.price_status === 'overpriced') {
            html += `
                Ваш объект оценен в <strong style="font-weight: 600;">${utils.formatPrice(situation.current_price || 0)}</strong>.
                Математическая модель показывает отклонение <strong style="font-weight: 600;">на ${Math.abs(situation.price_diff_percent || 0).toFixed(0)}% выше</strong> средних аналогов.
                <br><br>
                <span style="color: var(--gray-600); font-size: var(--text-sm);">
                Это лишь математика по базовым параметрам. При работе мы учтём десятки дополнительных факторов —
                от уникальности планировки до эмоциональной привлекательности объекта.
                </span>
            `;
        } else if (situation.price_status === 'underpriced') {
            html += `
                Ваш объект оценен в <strong style="font-weight: 600;">${utils.formatPrice(situation.current_price || 0)}</strong>.
                Математическая модель показывает, что цена <strong style="font-weight: 600;">на ${Math.abs(situation.price_diff_percent || 0).toFixed(0)}% ниже</strong> средних аналогов.
                <br><br>
                <span style="color: var(--gray-600); font-size: var(--text-sm);">
                Это может быть конкурентным преимуществом, но также проанализируем возможность повышения
                стоимости за счет улучшения презентации и позиционирования.
                </span>
            `;
        } else {
            html += `
                Ваш объект оценен в <strong style="font-weight: 600;">${utils.formatPrice(situation.current_price || 0)}</strong>,
                что соответствует средним показателям аналогов по базовым параметрам.
                <br><br>
                <span style="color: var(--gray-600); font-size: var(--text-sm);">
                При работе мы найдем уникальные преимущества вашего объекта, которые математика не учитывает,
                и построим стратегию максимально выгодной продажи.
                </span>
            `;
        }

        html += `
                    </div>
                </div>

                <!-- Наша цель -->
                <div style="background: var(--gray-100); padding: var(--spacing-xl); margin-bottom: var(--spacing-xl);">
                    <div style="font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.1em; color: var(--gray-600); margin-bottom: var(--spacing-sm); font-weight: 500;">
                        Наша цель
                    </div>
                    <div style="font-size: var(--text-base); line-height: var(--leading-relaxed); color: var(--gray-800);">
                        ${goal}
                    </div>
                </div>

                <!-- План действий -->
                <div style="margin-bottom: var(--spacing-xl);">
                    <div style="font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.1em; color: var(--gray-600); margin-bottom: var(--spacing-md); font-weight: 500;">
                        Что мы сделаем
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1px; background: var(--gray-300);">
        `;

        actions.forEach((action, index) => {
            html += `
                <div style="background: white; padding: var(--spacing-lg); transition: background var(--transition-base);"
                     onmouseover="this.style.background='var(--gray-100)'"
                     onmouseout="this.style.background='white'">
                    <div style="font-weight: 500; margin-bottom: var(--spacing-xs); color: var(--black);">
                        ${action.title}
                    </div>
                    <div style="font-size: var(--text-sm); color: var(--gray-600); line-height: var(--leading-normal);">
                        ${action.description}
                    </div>
                </div>
            `;
        });

        html += `
                    </div>
                </div>

                <!-- Прогноз результата (черный блок) -->
                <div style="background: linear-gradient(135deg, var(--gray-900) 0%, var(--black) 100%); color: white; padding: var(--spacing-xl); margin-bottom: var(--spacing-xl);">
                    <div style="font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.7; margin-bottom: var(--spacing-md); font-weight: 500;">
                        Наш прогноз
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--spacing-lg); margin-bottom: var(--spacing-md);">
                        <div>
                            <div style="font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.6; margin-bottom: var(--spacing-xs);">
                                Целевой срок
                            </div>
                            <div style="font-size: var(--text-xl); font-weight: 300;">
                                ${result.timeline}
                            </div>
                        </div>
                        <div>
                            <div style="font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.6; margin-bottom: var(--spacing-xs);">
                                Целевой диапазон
                            </div>
                            <div style="font-size: var(--text-xl); font-weight: 300;">
                                ${result.final_price_formatted}
                            </div>
                        </div>
                        <div>
                            <div style="font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.6; margin-bottom: var(--spacing-xs);">
                                Уверенность
                            </div>
                            <div style="font-size: var(--text-xl); font-weight: 300; text-transform: capitalize;">
                                ${result.confidence}
                            </div>
                        </div>
                    </div>
                    <div style="font-size: var(--text-sm); opacity: 0.7; line-height: var(--leading-relaxed); padding-top: var(--spacing-md); border-top: 1px solid rgba(255,255,255,0.1);">
                        Точная стратегия и финальная цена будут определены после детальной диагностики
                        и анализа всех факторов, которые математическая модель не учитывает.
                    </div>
                </div>

                <!-- Стоимость услуг - единый компонент -->
                <div style="margin-bottom: var(--spacing-xl);">
                    <div style="font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.1em; color: var(--gray-600); margin-bottom: var(--spacing-lg); font-weight: 500;">
                        Стоимость услуг
                    </div>

                    <div style="border: 2px solid var(--black); padding: var(--spacing-xl);">
                        <div style="text-align: center; margin-bottom: var(--spacing-xl);">
                            <div style="font-size: 56px; font-weight: 300; letter-spacing: -0.02em; color: var(--black);">2%</div>
                            <div style="font-size: var(--text-sm); color: var(--gray-600); margin-top: var(--spacing-xs);">от стоимости продажи</div>
                            <div style="font-size: var(--text-base); color: var(--black); font-weight: 500; margin-top: var(--spacing-sm);">Эксклюзивный договор, оплата по результату</div>
                        </div>

                        <div style="border-top: 1px solid var(--gray-300); padding-top: var(--spacing-lg); margin-bottom: var(--spacing-lg);">
                            <div style="display: flex; align-items: center; gap: var(--spacing-sm); margin-bottom: var(--spacing-sm);">
                                <span style="color: #28a745; font-size: var(--text-lg);">✓</span>
                                <span style="font-size: var(--text-sm);">Никаких авансов и предоплат</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: var(--spacing-sm); margin-bottom: var(--spacing-sm);">
                                <span style="color: #28a745; font-size: var(--text-lg);">✓</span>
                                <span style="font-size: var(--text-sm);">Оплата после успешной сделки</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: var(--spacing-sm);">
                                <span style="color: #28a745; font-size: var(--text-lg);">✓</span>
                                <span style="font-size: var(--text-sm);">Полное сопровождение до ключей</span>
                            </div>
                        </div>

                        <div style="border-top: 1px solid var(--gray-300); padding-top: var(--spacing-lg);">
                            <div style="font-weight: 500; margin-bottom: var(--spacing-md); font-size: var(--text-sm);">Что входит в стоимость</div>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--spacing-md);">
                                <div style="background: var(--gray-100); padding: var(--spacing-md);">
                                    <div style="font-weight: 500; font-size: var(--text-sm);">Подготовка</div>
                                    <div style="color: var(--gray-600); font-size: var(--text-xs);">Фотосъёмка, видео, 3D-тур</div>
                                </div>
                                <div style="background: var(--gray-100); padding: var(--spacing-md);">
                                    <div style="font-weight: 500; font-size: var(--text-sm);">Аналитика</div>
                                    <div style="color: var(--gray-600); font-size: var(--text-xs);">Оценка, аналоги, цена</div>
                                </div>
                                <div style="background: var(--gray-100); padding: var(--spacing-md);">
                                    <div style="font-weight: 500; font-size: var(--text-sm);">Маркетинг</div>
                                    <div style="color: var(--gray-600); font-size: var(--text-xs);">Площадки, продвижение</div>
                                </div>
                                <div style="background: var(--gray-100); padding: var(--spacing-md);">
                                    <div style="font-weight: 500; font-size: var(--text-sm);">Сделка</div>
                                    <div style="color: var(--gray-600); font-size: var(--text-xs);">Показы, переговоры, оформление</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- CTA кнопка -->
                <div style="margin-top: var(--spacing-3xl); padding-top: var(--spacing-xl); border-top: 1px solid var(--gray-300); text-align: center;">
                    <button
                        id="housler-cta-button"
                        style="background: var(--black); color: var(--white); border: 2px solid var(--black); padding: 18px 48px; font-size: var(--text-lg); font-weight: 500; cursor: pointer; transition: all var(--transition-base); letter-spacing: 0.02em;"
                        onmouseover="this.style.background='var(--white)'; this.style.color='var(--black)'"
                        onmouseout="this.style.background='var(--black)'; this.style.color='var(--white)'">
                        Начать работать
                    </button>
                    <div style="margin-top: var(--spacing-md); font-size: var(--text-sm); color: var(--gray-600);">
                        Оставьте заявку, и мы свяжемся с вами в течение часа
                    </div>
                </div>
            </div>
        `;

        document.getElementById('housler-offer-container').innerHTML = html;
        document.getElementById('housler-offer-container').style.display = 'block';

        // Привязываем обработчик к кнопке CTA после рендеринга
        const ctaButton = document.getElementById('housler-cta-button');
        if (ctaButton) {
            ctaButton.addEventListener('click', () => {
                if (window.screen3 && typeof window.screen3.showContactForm === 'function') {
                    window.screen3.showContactForm();
                } else {
                    console.error('screen3.showContactForm is not available');
                    utils.showToast('Ошибка загрузки формы. Попробуйте обновить страницу.', 'error');
                }
            });
        }
    },

    showContactForm() {
        // Создаем модальное окно если его еще нет
        let modal = document.getElementById('housler-contact-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'housler-contact-modal';
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content" style="border: none; border-radius: 0;">
                        <div class="modal-header" style="border-bottom: 1px solid var(--gray-300);">
                            <h5 class="modal-title" style="font-weight: 400; letter-spacing: -0.02em;">Оставить заявку</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body" style="padding: var(--spacing-xl);">
                            <form id="housler-contact-form">
                                <div class="mb-3">
                                    <label for="contact-name" class="form-label" style="font-size: var(--text-sm); text-transform: uppercase; letter-spacing: 0.1em; color: var(--gray-600);">Ваше имя</label>
                                    <input type="text" class="form-control" id="contact-name" required style="border-radius: 0; border: 1px solid var(--gray-300); padding: 12px;">
                                </div>
                                <div class="mb-3">
                                    <label for="contact-phone" class="form-label" style="font-size: var(--text-sm); text-transform: uppercase; letter-spacing: 0.1em; color: var(--gray-600);">Телефон</label>
                                    <input type="tel" class="form-control" id="contact-phone" required style="border-radius: 0; border: 1px solid var(--gray-300); padding: 12px;">
                                </div>
                                <div class="mb-3">
                                    <label for="contact-email" class="form-label" style="font-size: var(--text-sm); text-transform: uppercase; letter-spacing: 0.1em; color: var(--gray-600);">Email (необязательно)</label>
                                    <input type="email" class="form-control" id="contact-email" style="border-radius: 0; border: 1px solid var(--gray-300); padding: 12px;">
                                </div>
                                <div class="mb-3">
                                    <label for="contact-comment" class="form-label" style="font-size: var(--text-sm); text-transform: uppercase; letter-spacing: 0.1em; color: var(--gray-600);">Комментарий (необязательно)</label>
                                    <textarea class="form-control" id="contact-comment" rows="3" style="border-radius: 0; border: 1px solid var(--gray-300); padding: 12px;"></textarea>
                                </div>
                                <button type="submit" class="btn btn-dark w-100" style="border-radius: 0; padding: 14px; font-weight: 500; letter-spacing: 0.02em;">
                                    Отправить заявку
                                </button>
                            </form>
                            <div id="contact-form-success" style="display: none; margin-top: var(--spacing-lg); padding: var(--spacing-md); background: var(--gray-100); text-align: center;">
                                <div style="font-weight: 500; margin-bottom: var(--spacing-xs);">Спасибо за заявку!</div>
                                <div style="font-size: var(--text-sm); color: var(--gray-600);">Мы свяжемся с вами в ближайшее время</div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);

            // Обработчик отправки формы
            document.getElementById('housler-contact-form').addEventListener('submit', async (e) => {
                e.preventDefault();

                const name = document.getElementById('contact-name').value;
                const phone = document.getElementById('contact-phone').value;
                const email = document.getElementById('contact-email').value;
                const comment = document.getElementById('contact-comment').value;

                try {
                    // Отправляем данные на сервер
                    const response = await fetch('/api/contact-request', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            name,
                            phone,
                            email,
                            comment,
                            session_id: state.sessionId
                        })
                    });

                    if (response.ok) {
                        // Показываем успешное сообщение
                        document.getElementById('housler-contact-form').style.display = 'none';
                        document.getElementById('contact-form-success').style.display = 'block';

                        // Закрываем модал через 3 секунды
                        setTimeout(() => {
                            bootstrap.Modal.getInstance(modal).hide();
                            document.getElementById('housler-contact-form').style.display = 'block';
                            document.getElementById('contact-form-success').style.display = 'none';
                            document.getElementById('housler-contact-form').reset();
                        }, 3000);
                    } else {
                        alert('Произошла ошибка при отправке заявки. Пожалуйста, попробуйте позже.');
                    }
                } catch (error) {
                    console.error('Error submitting contact form:', error);
                    alert('Произошла ошибка при отправке заявки. Пожалуйста, попробуйте позже.');
                }
            });
        }

        // Открываем модал
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    }
};

// Floating buttons
const floatingButtons = {
    init() {
        const nextBtn = document.getElementById('floating-next-btn');
        const backBtn = document.getElementById('floating-back-btn');
        const shareBtn = document.getElementById('share-btn');

        nextBtn.addEventListener('click', () => {
            if (state.currentStep === 1) {
                screen1.updateTargetProperty();
            } else if (state.currentStep === 2) {
                // Проверяем наличие аналогов перед переходом к анализу
                const activeComparables = state.comparables.filter(c => !c.excluded);
                if (activeComparables.length === 0) {
                    utils.showToast('Сначала добавьте объекты для сравнения', 'warning');
                    return;
                }
                navigation.goToStep(3);
            } else if (state.currentStep === 3) {
                // На последнем экране кнопка скачивает отчет
                this.downloadReport();
            }
        });

        backBtn.addEventListener('click', () => {
            if (state.currentStep > 1) {
                navigation.goToStep(state.currentStep - 1);
            }
        });

        // Session Management: Share button handler
        if (shareBtn) {
            shareBtn.addEventListener('click', () => {
                utils.copyShareableUrl();
            });
        }

        // Обновляем видимость кнопок при смене экрана
        this.updateButtons();
    },

    updateButtons() {
        const nextBtn = document.getElementById('floating-next-btn');
        const backBtn = document.getElementById('floating-back-btn');
        const shareBtn = document.getElementById('share-btn');

        // Показываем кнопку "Назад" только не на первом экране
        if (state.currentStep === 1) {
            backBtn.style.display = 'none';
        } else {
            backBtn.style.display = 'flex';
        }

        // Кнопка "Далее" показывается только если есть sessionId
        if (state.currentStep === 1 && !state.sessionId) {
            nextBtn.style.display = 'none';
        } else {
            nextBtn.style.display = 'flex';
        }

        // На втором шаге блокируем кнопку если нет аналогов
        if (state.currentStep === 2) {
            const activeComparables = state.comparables.filter(c => !c.excluded);
            if (activeComparables.length === 0) {
                nextBtn.classList.add('disabled');
                nextBtn.style.opacity = '0.5';
                nextBtn.style.cursor = 'not-allowed';
            } else {
                nextBtn.classList.remove('disabled');
                nextBtn.style.opacity = '1';
                nextBtn.style.cursor = 'pointer';
            }
        } else {
            // На других шагах убираем блокировку
            nextBtn.classList.remove('disabled');
            nextBtn.style.opacity = '1';
            nextBtn.style.cursor = 'pointer';
        }

        // Session Management: Show "Share" button only if session exists
        if (shareBtn) {
            if (state.sessionId) {
                shareBtn.style.display = 'inline-block';
            } else {
                shareBtn.style.display = 'none';
            }
        }

        // Обновляем текст кнопки "Далее"
        const nextText = nextBtn.querySelector('span');
        if (state.currentStep === 1) {
            nextText.textContent = 'Далее';
        } else if (state.currentStep === 2) {
            nextText.textContent = 'К анализу';
        } else if (state.currentStep === 3) {
            nextText.textContent = 'Скачать отчет';
        }
    },

    async downloadReport() {
        if (!state.sessionId) {
            utils.showToast('Сессия не найдена', 'error');
            return;
        }

        if (!state.analysis) {
            utils.showToast('Сначала выполните анализ', 'warning');
            return;
        }

        try {
            // Показываем лоадер
            pixelLoader.show('analyzing');

            const response = await fetch(`/api/export-report/${state.sessionId}`, {
                method: 'GET',
                headers: utils.getCsrfHeaders()
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.message || 'Ошибка генерации отчёта');
            }

            // Получаем имя файла из заголовков
            const contentDisposition = response.headers.get('Content-Disposition');

            // Генерируем имя с датой
            const today = new Date().toISOString().split('T')[0];
            let filename = `housler_report_${today}.pdf`;

            if (contentDisposition) {
                // Поддерживаем оба формата: filename="name" и filename=name
                const filenameMatch = contentDisposition.match(/filename="([^"]+)"|filename=([^\s;]+)/);
                if (filenameMatch) {
                    filename = filenameMatch[1] || filenameMatch[2];
                }
            }

            // Получаем blob
            const blob = await response.blob();

            // Завершаем лоадер
            pixelLoader.complete();

            // Показываем модалку с результатом
            reportModal.showSuccess(filename, blob);

        } catch (error) {
            console.error('Download error:', error);
            pixelLoader.hide();

            // Показываем модалку с ошибкой
            reportModal.showError(error.message || 'Произошла ошибка при генерации PDF. Попробуйте ещё раз или напишите нам.');
        }
    }
};

// ══════════════════════════════════════════════════════════════
// Report Modal - Модальное окно для скачивания отчёта
// ══════════════════════════════════════════════════════════════

const reportModal = {
    currentBlob: null,
    currentFilename: null,

    init() {
        // Close button
        document.getElementById('report-modal-close')?.addEventListener('click', () => this.hide());

        // Backdrop click
        document.querySelector('.report-modal-backdrop')?.addEventListener('click', () => this.hide());

        // Download button
        document.getElementById('report-download-btn')?.addEventListener('click', () => this.download());

        // Email button
        document.getElementById('report-email-btn')?.addEventListener('click', () => this.showEmailForm());

        // Back to download
        document.getElementById('report-back-btn')?.addEventListener('click', () => this.showSuccess());

        // Send email button
        document.getElementById('report-send-email-btn')?.addEventListener('click', () => this.sendEmail());

        // Retry button
        document.getElementById('report-retry-btn')?.addEventListener('click', () => {
            this.hide();
            floatingButtons.downloadReport();
        });

        // ESC to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && document.getElementById('report-modal').style.display !== 'none') {
                this.hide();
            }
        });
    },

    showSuccess(filename, blob) {
        if (filename) this.currentFilename = filename;
        if (blob) this.currentBlob = blob;

        const modal = document.getElementById('report-modal');
        const successState = document.getElementById('report-modal-success');
        const errorState = document.getElementById('report-modal-error');
        const emailState = document.getElementById('report-modal-email');
        const filenameEl = document.getElementById('report-filename');

        // Show success state
        successState.style.display = 'block';
        errorState.style.display = 'none';
        emailState.style.display = 'none';

        // Update filename
        if (filenameEl && this.currentFilename) {
            filenameEl.textContent = this.currentFilename;
        }

        modal.style.display = 'flex';
    },

    showError(errorMessage) {
        const modal = document.getElementById('report-modal');
        const successState = document.getElementById('report-modal-success');
        const errorState = document.getElementById('report-modal-error');
        const emailState = document.getElementById('report-modal-email');
        const errorText = document.getElementById('report-error-text');

        // Show error state
        successState.style.display = 'none';
        errorState.style.display = 'block';
        emailState.style.display = 'none';

        // Update error message
        if (errorText) {
            errorText.textContent = errorMessage || 'Произошла ошибка при генерации PDF. Попробуйте ещё раз или напишите нам.';
        }

        modal.style.display = 'flex';
    },

    showEmailForm() {
        const successState = document.getElementById('report-modal-success');
        const errorState = document.getElementById('report-modal-error');
        const emailState = document.getElementById('report-modal-email');

        successState.style.display = 'none';
        errorState.style.display = 'none';
        emailState.style.display = 'block';

        // Focus email input
        document.getElementById('report-email-input')?.focus();
    },

    hide() {
        const modal = document.getElementById('report-modal');
        modal.style.display = 'none';
    },

    download() {
        if (!this.currentBlob || !this.currentFilename) {
            utils.showToast('Файл недоступен', 'error');
            return;
        }

        const url = window.URL.createObjectURL(this.currentBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = this.currentFilename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        utils.showToast('Отчёт скачан!', 'success');
        this.hide();
    },

    async sendEmail() {
        const emailInput = document.getElementById('report-email-input');
        const email = emailInput?.value.trim();

        if (!email) {
            utils.showToast('Введите email', 'warning');
            return;
        }

        // Basic email validation
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            utils.showToast('Некорректный email', 'warning');
            return;
        }

        // For now, just show that this feature is coming soon
        utils.showToast('Функция отправки на email скоро будет доступна', 'info');

        // TODO: Implement actual email sending
        // try {
        //     const response = await fetch('/api/send-report-email', {
        //         method: 'POST',
        //         headers: utils.getCsrfHeaders(),
        //         body: JSON.stringify({ session_id: state.sessionId, email })
        //     });
        //     ...
        // }
    }
};

// ══════════════════════════════════════════════════════════════
// Pixel Loader - Веселые пиксельные лоадеры
// ══════════════════════════════════════════════════════════════

const pixelLoader = {
    // Этапы для каждого типа операции
    stages: {
        parsing: [
            { label: 'Загрузка', duration: 2 },
            { label: 'Парсинг', duration: 3 },
            { label: 'Проверка', duration: 2 }
        ],
        searching: [
            { label: 'Поиск', duration: 4 },
            { label: 'Парсинг', duration: 6 },
            { label: 'Обработка', duration: 3 }
        ],
        analyzing: [
            { label: 'Парсинг', duration: 2 },
            { label: 'Поиск аналогов', duration: 3 },
            { label: 'Расчёт цены', duration: 3 },
            { label: 'Генерация', duration: 2 }
        ]
    },

    // Сообщения для бегущей строки
    messages: {
        parsing: [
            'Загрузка объекта',
            'Проверка данных',
            'Получение информации',
            'Анализ параметров'
        ],
        searching: [
            'Звоню агентам... опять не берут трубку',
            'Бегаю по всем квартирам на районе',
            'Уже на середине! База наполовину собрана',
            'Почти готово! Финальные штрихи'
        ],
        analyzing: [
            'Расчет стоимости',
            'Анализ данных',
            'Формирование отчета',
            'Построение графиков'
        ]
    },

    // Состояние
    currentLoader: null,
    currentStage: 0,
    currentMessageIndex: 0,
    messageInterval: null,
    progressInterval: null,
    timerInterval: null,
    startTime: null,
    estimatedTime: 0,
    currentProgress: 0,
    disabledElements: [],
    isCompleting: false, // Флаг для избежания двойного вызова

    // Показать лоадер
    show(type = 'parsing') {
        const loader = document.getElementById('pixel-loader');
        if (!loader) {
            console.error('Pixel loader element not found');
            return;
        }

        const textElement = document.getElementById('pixel-text');
        const iconElement = loader.querySelector('.pixel-icon');
        const stepsContainer = document.getElementById('pixel-progress-steps');
        const progressFill = document.getElementById('pixel-progress-fill');
        const percentageEl = document.getElementById('pixel-percentage');
        const timerEl = document.getElementById('pixel-timer');
        const lineFill = document.getElementById('pixel-line-fill');

        // Сброс состояния
        this.currentLoader = type;
        this.currentStage = 0;
        this.currentMessageIndex = 0;
        this.currentProgress = 0;
        this.startTime = Date.now();
        this.isCompleting = false;

        // Расчёт общего времени
        const stages = this.stages[type] || this.stages.parsing;
        this.estimatedTime = stages.reduce((sum, s) => sum + s.duration, 0);

        // Устанавливаем тип лоадера
        loader.className = 'pixel-loader ' + type;

        // Устанавливаем иконку
        const icons = { parsing: 'agent', searching: 'house', analyzing: 'document' };
        iconElement.className = 'pixel-icon ' + icons[type];

        // Генерируем этапы
        this.renderStages(stepsContainer, stages);

        // Сброс прогресса
        progressFill.style.width = '0%';
        percentageEl.textContent = '0%';
        timerEl.textContent = `Осталось ~${this.estimatedTime} сек`;
        lineFill.style.width = '0%';

        // Показываем первое сообщение
        const messages = this.messages[type] || this.messages.parsing;
        textElement.textContent = messages[0] + ' ⚡ ' + messages[0] + ' ⚡ ';

        // Показываем лоадер
        loader.style.display = 'flex';

        // Блокируем кнопки
        this.disableButtons();

        // Запускаем анимации
        this.startProgressAnimation(type);
        this.startMessageRotation(type);
        this.startTimer();
    },

    // Рендер этапов
    renderStages(container, stages) {
        // Сохраняем линию прогресса
        const line = container.querySelector('.pixel-progress-line');
        container.innerHTML = '';
        container.appendChild(line);

        stages.forEach((stage, index) => {
            const stepEl = document.createElement('div');
            stepEl.className = 'pixel-progress-step' + (index === 0 ? ' active' : '');
            stepEl.dataset.index = index;
            stepEl.innerHTML = `
                <div class="pixel-progress-step-dot">${index + 1}</div>
                <div class="pixel-progress-step-label">${stage.label}</div>
            `;
            container.appendChild(stepEl);
        });
    },

    // Анимация прогресса
    startProgressAnimation(type) {
        const stages = this.stages[type] || this.stages.parsing;
        const totalDuration = this.estimatedTime * 1000;
        const progressFill = document.getElementById('pixel-progress-fill');
        const percentageEl = document.getElementById('pixel-percentage');
        const lineFill = document.getElementById('pixel-line-fill');
        const stepsContainer = document.getElementById('pixel-progress-steps');

        let elapsed = 0;
        const interval = 100; // Обновление каждые 100мс

        if (this.progressInterval) clearInterval(this.progressInterval);

        this.progressInterval = setInterval(() => {
            elapsed += interval;
            const progress = Math.min((elapsed / totalDuration) * 100, 95); // Макс 95% до завершения
            this.currentProgress = progress;

            // Обновляем прогресс-бар
            progressFill.style.width = progress + '%';
            percentageEl.textContent = Math.round(progress) + '%';

            // Обновляем линию между этапами
            lineFill.style.width = progress + '%';

            // Определяем текущий этап
            let accumulatedTime = 0;
            let newStage = 0;
            for (let i = 0; i < stages.length; i++) {
                accumulatedTime += stages[i].duration * 1000;
                if (elapsed < accumulatedTime) {
                    newStage = i;
                    break;
                }
                newStage = i;
            }

            // Обновляем активный этап
            if (newStage !== this.currentStage) {
                this.currentStage = newStage;
                const steps = stepsContainer.querySelectorAll('.pixel-progress-step');
                steps.forEach((step, idx) => {
                    step.classList.remove('active', 'completed');
                    if (idx < newStage) {
                        step.classList.add('completed');
                    } else if (idx === newStage) {
                        step.classList.add('active');
                    }
                });
            }
        }, interval);
    },

    // Таймер обратного отсчёта
    startTimer() {
        const timerEl = document.getElementById('pixel-timer');

        if (this.timerInterval) clearInterval(this.timerInterval);

        this.timerInterval = setInterval(() => {
            const elapsed = (Date.now() - this.startTime) / 1000;
            const remaining = Math.max(0, this.estimatedTime - elapsed);

            if (remaining > 0) {
                timerEl.textContent = `Осталось ~${Math.ceil(remaining)} сек`;
            } else {
                timerEl.textContent = 'Почти готово...';
            }
        }, 1000);
    },

    // Ротация сообщений
    startMessageRotation(type) {
        const messages = this.messages[type] || this.messages.parsing;
        const textElement = document.getElementById('pixel-text');

        if (this.messageInterval) clearInterval(this.messageInterval);

        this.messageInterval = setInterval(() => {
            this.currentMessageIndex = (this.currentMessageIndex + 1) % messages.length;
            const message = messages[this.currentMessageIndex];
            textElement.textContent = message + ' ⚡ ' + message + ' ⚡ ';
        }, 3000);
    },

    // Блокировка кнопок
    disableButtons() {
        const selectors = [
            '#floating-next-btn',
            '#floating-back-btn',
            '.btn-parse-url',
            '.btn-find-similar',
            '.btn-run-analysis',
            '.btn-download-report',
            '#btn-add-comparable'
        ];

        this.disabledElements = [];

        selectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => {
                if (el && !el.disabled) {
                    el.disabled = true;
                    el.classList.add('btn-loading');
                    this.disabledElements.push(el);
                }
            });
        });
    },

    // Разблокировка кнопок
    enableButtons() {
        this.disabledElements.forEach(el => {
            el.disabled = false;
            el.classList.remove('btn-loading');
        });
        this.disabledElements = [];
    },

    // Завершить с успехом (100%)
    complete() {
        if (this.isCompleting) return; // Уже завершается
        this.isCompleting = true;

        const progressFill = document.getElementById('pixel-progress-fill');
        const percentageEl = document.getElementById('pixel-percentage');
        const lineFill = document.getElementById('pixel-line-fill');
        const timerEl = document.getElementById('pixel-timer');
        const stepsContainer = document.getElementById('pixel-progress-steps');

        // Останавливаем анимацию прогресса
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }

        // Устанавливаем 100%
        if (progressFill) progressFill.style.width = '100%';
        if (percentageEl) percentageEl.textContent = '100%';
        if (lineFill) lineFill.style.width = '100%';
        if (timerEl) timerEl.textContent = 'Готово!';

        // Все этапы завершены
        if (stepsContainer) {
            const steps = stepsContainer.querySelectorAll('.pixel-progress-step');
            steps.forEach(step => {
                step.classList.remove('active');
                step.classList.add('completed');
            });
        }

        // Скрываем через 500мс
        setTimeout(() => this.hide(true), 500);
    },

    // Скрыть лоадер
    hide(fromComplete = false) {
        // Если уже завершается через complete(), игнорируем прямой вызов hide()
        if (this.isCompleting && !fromComplete) return;

        const loader = document.getElementById('pixel-loader');
        if (loader) {
            loader.style.display = 'none';
        }

        // Останавливаем все интервалы
        if (this.messageInterval) {
            clearInterval(this.messageInterval);
            this.messageInterval = null;
        }
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }

        // Разблокируем кнопки
        this.enableButtons();
        this.isCompleting = false;
    },

    // Обновить прогресс вручную (для длительных операций)
    setProgress(percent) {
        const progressFill = document.getElementById('pixel-progress-fill');
        const percentageEl = document.getElementById('pixel-percentage');
        const lineFill = document.getElementById('pixel-line-fill');

        this.currentProgress = percent;
        if (progressFill) progressFill.style.width = percent + '%';
        if (percentageEl) percentageEl.textContent = Math.round(percent) + '%';
        if (lineFill) lineFill.style.width = percent + '%';
    }
};

// Утилиты для skeleton-загрузки
const skeletonLoader = {
    // Показать skeleton для секции отчёта
    showForReport(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = `
            <div class="skeleton-report-section">
                <div class="skeleton skeleton-title"></div>
                <div class="skeleton-row">
                    <div class="skeleton-col">
                        <div class="skeleton skeleton-price"></div>
                        <div class="skeleton skeleton-text"></div>
                        <div class="skeleton skeleton-text medium"></div>
                    </div>
                    <div class="skeleton-col">
                        <div class="skeleton skeleton-badge"></div>
                        <div class="skeleton skeleton-badge"></div>
                        <div class="skeleton skeleton-text short"></div>
                    </div>
                </div>
                <div class="skeleton skeleton-chart"></div>
                <div class="skeleton skeleton-text"></div>
                <div class="skeleton skeleton-text medium"></div>
                <div class="skeleton skeleton-text short"></div>
            </div>
        `;
    },

    // Скрыть skeleton (контент заменяется автоматически)
    hide(containerId) {
        // Skeleton убирается при заполнении реальным контентом
    }
};

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', async () => {
    // SECURITY: Fetch CSRF token first
    await utils.fetchCsrfToken();

    screen1.init();
    screen2.init();
    screen3.init();
    floatingButtons.init();
    reportModal.init();

    // Экспортируем для доступа из navigation
    window.floatingButtons = floatingButtons;
    window.screen3 = screen3; // Нужно для auto-run анализа

    // Breadcrumbs: Make progress bar clickable
    document.querySelectorAll('.progress-step').forEach((stepEl) => {
        stepEl.style.cursor = 'pointer';
        stepEl.addEventListener('click', () => {
            const stepNum = parseInt(stepEl.getAttribute('data-step'));

            // Only allow navigation to completed steps or current step
            if (stepEl.classList.contains('completed') || stepEl.classList.contains('active')) {
                // For step 2 and 3, require sessionId
                if (stepNum > 1 && !state.sessionId) {
                    utils.showToast('Сначала загрузите объект', 'warning');
                    return;
                }

                navigation.goToStep(stepNum);
            } else {
                utils.showToast('Сначала завершите предыдущие шаги', 'warning');
            }
        });
    });

    // Session Management: Check for reset parameter from landing page
    const urlParams = new URLSearchParams(window.location.search);
    const shouldReset = urlParams.get('reset') === '1';

    if (shouldReset) {
        console.log('Reset parameter detected - clearing session and starting fresh');
        utils.clearSessionFromLocalStorage();

        // Clean up URL by removing reset parameter
        urlParams.delete('reset');
        const newUrl = window.location.pathname + (urlParams.toString() ? '?' + urlParams.toString() : '');
        window.history.replaceState({}, '', newUrl);
    }

    // Session Management: Try to restore session (skip if reset=1)
    let sessionLoaded = false;

    if (!shouldReset) {
        // Priority 1: Check URL parameter (from server or shared link)
        if (window.SERVER_SESSION_ID) {
            console.log('Found session in URL from server:', window.SERVER_SESSION_ID);
            sessionLoaded = await utils.loadSession(window.SERVER_SESSION_ID);
        }

        // Priority 2: Check localStorage (user's own previous session)
        if (!sessionLoaded) {
            const localSessionId = utils.getSessionFromLocalStorage();
            if (localSessionId) {
                console.log('Found session in localStorage:', localSessionId);
                sessionLoaded = await utils.loadSession(localSessionId);
            }
        }
    }

    // If no session loaded, just stay on step 1
    if (!sessionLoaded) {
        console.log('No session to restore, starting fresh');
    }
});
