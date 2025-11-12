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

    showToast(message, type = 'info') {
        const toast = document.getElementById('toast');
        const toastBody = document.getElementById('toast-body');
        toastBody.textContent = message;

        // Remove old toast type classes
        toast.classList.remove('toast-success', 'toast-error', 'toast-warning', 'toast-info');

        // Add new toast type class (for colored left border)
        toast.classList.add(`toast-${type}`);

        const bsToast = new bootstrap.Toast(toast);
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
    },

    showManualForm() {
        document.getElementById('manual-input-form').style.display = 'block';
        // Скроллим к форме
        document.getElementById('manual-input-form').scrollIntoView({ behavior: 'smooth', block: 'start' });
    },

    hideManualForm() {
        document.getElementById('manual-input-form').style.display = 'none';
    },

    async submitManualForm(e) {
        e.preventDefault();

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
        const url = document.getElementById('url-input').value.trim();

        if (!url) {
            utils.showToast('Введите URL объявления', 'warning');
            return;
        }

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

                state.comparables = result.comparables;
                console.log('🔍 DEBUG: State comparables set to:', state.comparables.length);

                this.renderComparables();

                // Обновляем кнопки навигации (для разблокировки "К анализу")
                if (window.floatingButtons) {
                    floatingButtons.updateButtons();
                }

                // ДОРАБОТКА #4: Отображение предупреждений о качестве аналогов
                if (result.warnings && result.warnings.length > 0) {
                    this.showQualityWarnings(result.warnings);
                } else {
                    utils.showToast(`Найдено ${result.count} похожих объектов`, 'success');
                }
            } else {
                const errorData = getErrorMessage(result.message || 'no_comparables');
                utils.showToast(`${errorData.title}: ${errorData.message}`, 'error');
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
        const url = document.getElementById('add-comparable-input').value.trim();

        if (!url) {
            utils.showToast('Введите URL объявления', 'warning');
            return;
        }

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
                utils.showToast('Объект добавлен', 'success');
            } else {
                const errorData = getErrorMessage(result.message || 'parsing_error');
                utils.showToast(`${errorData.title}: ${errorData.message}`, 'error');
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
        const container = document.getElementById('comparables-list');

        if (state.comparables.length === 0) {
            container.innerHTML = `
                <div class="alert alert-info">
                    <i class="bi bi-info-circle me-2"></i>
                    Нажмите кнопку "Автоматически найти" или добавьте объекты вручную
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div class="mb-3">
                <h5>Найдено аналогов: ${state.comparables.filter(c => !c.excluded).length} / ${state.comparables.length}</h5>
            </div>
            ${state.comparables.map((comp, index) => this.renderComparableCard(comp, index)).join('')}
        `;
    },

    renderComparableCard(comp, index) {
        const excluded = comp.excluded || false;

        // Форматируем цену за кв.м
        let pricePerSqmText = '';
        if (comp.price_per_sqm) {
            pricePerSqmText = `<div class="detail-item" style="font-weight: 600; color: var(--black);"><i class="bi bi-cash-stack"></i> ${utils.formatNumber(comp.price_per_sqm)} ₽/м²</div>`;
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
                    ${comp.price || 'Цена не указана'}
                </div>
                <div class="property-details">
                    ${pricePerSqmText}
                    ${comp.rooms ? `<div class="detail-item"><i class="bi bi-door-open"></i> ${comp.rooms} комн.</div>` : ''}
                    ${comp.area ? `<div class="detail-item"><i class="bi bi-rulers"></i> ${comp.area}</div>` : ''}
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

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: utils.getCsrfHeaders(),
                body: JSON.stringify({
                    session_id: state.sessionId,
                    filter_outliers: true,
                    use_median: true
                })
            });

            const result = await response.json();

            if (result.status === 'success') {
                state.analysis = result.analysis;
                this.displayAnalysis(result.analysis);
                utils.showToast('Анализ завершен!', 'success');
            } else {
                const errorData = getErrorMessage(result.message || 'analysis_failed');
                utils.showToast(`${errorData.title}: ${errorData.message}`, 'error');
            }
        } catch (error) {
            console.error('Analysis error:', error);
            const errorData = getErrorMessage('network_error');
            utils.showToast(`${errorData.title}: ${errorData.message}`, 'error');
        } finally {
            pixelLoader.hide();
        }
    },

    displayAnalysis(analysis) {
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
                        html += `<p class="card-text"><strong>ROI:</strong> <span class="badge bg-success">${roi.toFixed(1)}x</span></p>`;
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

                <!-- Варианты оплаты -->
                <div style="margin-bottom: var(--spacing-xl);">
                    <div style="font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.1em; color: var(--gray-600); margin-bottom: var(--spacing-xs); font-weight: 500;">
                        Выберите удобный вариант
                    </div>
                    <div style="font-size: var(--text-sm); color: var(--gray-600); margin-bottom: var(--spacing-lg);">
                        Ваш объект: <strong style="color: var(--black);">${price_tier.range}</strong>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: var(--spacing-lg);">

                        <!-- Опция A -->
                        <div style="border: 1px solid var(--gray-300); padding: var(--spacing-xl); transition: all var(--transition-base); cursor: pointer;"
                             onmouseover="this.style.borderColor='var(--black)'; this.style.boxShadow='var(--shadow-md)'"
                             onmouseout="this.style.borderColor='var(--gray-300)'; this.style.boxShadow='none'">
                            <div style="font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.1em; color: var(--gray-600); margin-bottom: var(--spacing-lg); font-weight: 500;">
                                Опция A — Комиссия
                            </div>
                            <div style="font-size: 40px; font-weight: 300; letter-spacing: -0.02em; margin-bottom: var(--spacing-lg); color: var(--black);">
                                ${commission_option.value}
                            </div>
                            <div style="font-size: var(--text-sm); color: var(--gray-600); line-height: var(--leading-relaxed);">
                                ${commission_option.description}
                            </div>
                        </div>

                        <!-- Опция B -->
                        <div style="border: 1px solid var(--gray-300); padding: var(--spacing-xl); transition: all var(--transition-base); cursor: pointer;"
                             onmouseover="this.style.borderColor='var(--black)'; this.style.boxShadow='var(--shadow-md)'"
                             onmouseout="this.style.borderColor='var(--gray-300)'; this.style.boxShadow='none'">
                            <div style="font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.1em; color: var(--gray-600); margin-bottom: var(--spacing-lg); font-weight: 500;">
                                Опция B — Предоплата + успех
                            </div>
                            <div style="font-size: 40px; font-weight: 300; letter-spacing: -0.02em; margin-bottom: var(--spacing-lg); color: var(--black);">
                                ${prepay_option.prepay}
                            </div>
                            <div style="font-size: var(--text-sm); color: var(--gray-600); line-height: var(--leading-relaxed);">
                                ${prepay_option.description}
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
                throw new Error('Ошибка загрузки отчета');
            }

            // Получаем имя файла из заголовков
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'housler_report.md';
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
                if (filenameMatch) {
                    filename = filenameMatch[1];
                }
            }

            // Скачиваем файл
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            utils.showToast('Отчет успешно скачан!', 'success');
        } catch (error) {
            console.error('Download error:', error);
            utils.showToast('Ошибка при скачивании отчета', 'error');
        } finally {
            pixelLoader.hide();
        }
    }
};

// ══════════════════════════════════════════════════════════════
// Pixel Loader - Веселые пиксельные лоадеры
// ══════════════════════════════════════════════════════════════

const pixelLoader = {
    // Профессиональные тексты для разных этапов (без emoji, до 30 символов)
    messages: {
        // Парсинг объекта
        parsing: [
            'Загрузка объекта',
            'Проверка данных',
            'Получение информации',
            'Анализ параметров',
            'Валидация адреса',
            'Обработка запроса'
        ],

        // Поиск аналогов - веселые вовлекающие сообщения с прогрессом
        searching: [
            // Начало поиска (0-5 объектов)
            'Звоню агентам... опять не берут трубку, видимо заняты другими важными объектами',
            'Применяю технику клонирования и бегаю по всем квартирам на районе',
            'Записался на консультацию к ИИ, который поможет обзвонить все объявления',
            // Середина (5-10 объектов)
            'Уже на середине! Наклеил баннер что ищем похожую квартиру',
            'Еще немного... база данных уже наполовину собрана',
            'Продолжаю поиск, совсем скоро найдем все лучшие варианты',
            // Почти готово (10-15+ объектов)
            'Уже почти готово! База почти вся собралась',
            'Осталось совсем чуть-чуть, заканчиваю сбор данных',
            'Финальные штрихи... сейчас покажу все что нашел'
        ],

        // Анализ
        analyzing: [
            'Расчет стоимости',
            'Анализ данных',
            'Формирование отчета',
            'Построение графиков',
            'Оценка рисков',
            'Финализация'
        ]
    },

    currentLoader: null,
    currentMessageIndex: 0,
    messageInterval: null,

    // Показать лоадер
    show(type = 'parsing') {
        // Создаем лоадер если его нет
        const loader = document.getElementById('pixel-loader');
        if (!loader) {
            console.error('Pixel loader element not found');
            return;
        }

        const textElement = document.getElementById('pixel-text');
        const iconElement = loader.querySelector('.pixel-icon');

        // Устанавливаем тип лоадера
        loader.className = 'pixel-loader ' + type;
        this.currentLoader = type;
        this.currentMessageIndex = 0;

        // Устанавливаем иконку в зависимости от типа
        const icons = {
            parsing: 'agent',
            searching: 'house',
            analyzing: 'document'
        };
        iconElement.className = 'pixel-icon ' + icons[type];

        // Показываем первое сообщение
        const messages = this.messages[type] || this.messages.parsing;
        textElement.textContent = messages[0] + ' ⚡ ' + messages[0] + ' ⚡ '; // Дублируем для бесшовной анимации

        // Показываем лоадер
        loader.style.display = 'flex';

        // Запускаем смену сообщений
        this.startMessageRotation(type);
    },

    // Скрыть лоадер
    hide() {
        const loader = document.getElementById('pixel-loader');
        if (loader) {
            loader.style.display = 'none';
        }

        // Останавливаем смену сообщений
        if (this.messageInterval) {
            clearInterval(this.messageInterval);
            this.messageInterval = null;
        }
    },

    // Ротация сообщений
    startMessageRotation(type) {
        const messages = this.messages[type] || this.messages.parsing;
        const textElement = document.getElementById('pixel-text');

        // Останавливаем предыдущий интервал
        if (this.messageInterval) {
            clearInterval(this.messageInterval);
        }

        // Меняем сообщение каждые 3 секунды
        this.messageInterval = setInterval(() => {
            this.currentMessageIndex = (this.currentMessageIndex + 1) % messages.length;
            const message = messages[this.currentMessageIndex];

            // Дублируем текст для бесшовной бегущей строки
            textElement.textContent = message + ' ⚡ ' + message + ' ⚡ ';
        }, 3000);
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
