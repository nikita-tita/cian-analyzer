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
    analysis: null
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

        toast.classList.remove('bg-success', 'bg-danger', 'bg-warning', 'bg-info');
        if (type === 'success') toast.classList.add('bg-success', 'text-white');
        else if (type === 'error') toast.classList.add('bg-danger', 'text-white');
        else if (type === 'warning') toast.classList.add('bg-warning');
        else toast.classList.add('bg-info', 'text-white');

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
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            const result = await response.json();

            if (result.status === 'success') {
                state.sessionId = result.session_id;
                state.targetProperty = result.data;

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
                utils.showToast(result.message || 'Ошибка создания объекта', 'error');
            }
        } catch (error) {
            console.error('Manual input error:', error);
            utils.showToast('Ошибка соединения с сервером', 'error');
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
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            const result = await response.json();

            if (result.status === 'success') {
                state.sessionId = result.session_id;
                state.targetProperty = result.data;

                // Обновляем кнопки навигации
                if (window.floatingButtons) {
                    floatingButtons.updateButtons();
                }

                this.displayParseResult(result.data, result.missing_fields);
                utils.showToast('Объект успешно загружен!', 'success');
            } else {
                utils.showToast(result.message || 'Ошибка парсинга', 'error');
            }
        } catch (error) {
            console.error('Parse error:', error);
            utils.showToast('Ошибка соединения с сервером', 'error');
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
                    headers: { 'Content-Type': 'application/json' },
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
                    utils.showToast(result.message || 'Ошибка сохранения', 'error');
                }
            } catch (error) {
                console.error('Update error:', error);
                utils.showToast('Ошибка соединения с сервером', 'error');
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
        document.getElementById('back-to-parse-btn').addEventListener('click', () => navigation.goToStep(1));
        document.getElementById('next-to-analysis-btn').addEventListener('click', () => navigation.goToStep(3));
    },

    async findSimilar() {
        pixelLoader.show('searching');

        try {
            const response = await fetch('/api/find-similar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: state.sessionId,
                    limit: 20
                })
            });

            const result = await response.json();

            if (result.status === 'success') {
                state.comparables = result.comparables;
                this.renderComparables();
                utils.showToast(`Найдено ${result.count} похожих объектов`, 'success');
            } else {
                utils.showToast(result.message || 'Ошибка поиска', 'error');
            }
        } catch (error) {
            console.error('Find similar error:', error);
            utils.showToast('Ошибка соединения с сервером', 'error');
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
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: state.sessionId,
                    url
                })
            });

            const result = await response.json();

            if (result.status === 'success') {
                state.comparables.push(result.comparable);
                this.renderComparables();
                document.getElementById('add-comparable-input').value = '';
                utils.showToast('Объект добавлен', 'success');
            } else {
                utils.showToast(result.message || 'Ошибка добавления', 'error');
            }
        } catch (error) {
            console.error('Add comparable error:', error);
            utils.showToast('Ошибка соединения с сервером', 'error');
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
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: state.sessionId,
                    index
                })
            });

            state.comparables[index].excluded = true;
            this.renderComparables();
            utils.showToast('Объект исключен из анализа', 'info');
        } catch (error) {
            console.error('Exclude error:', error);
            utils.showToast('Ошибка исключения', 'error');
        }
    },

    includeComparable(index) {
        state.comparables[index].excluded = false;
        this.renderComparables();
        utils.showToast('Объект возвращен в анализ', 'success');
    }
};

// Экран 3: Анализ
const screen3 = {
    init() {
        document.getElementById('run-analysis-btn').addEventListener('click', this.runAnalysis.bind(this));
        document.getElementById('back-to-comparables-btn').addEventListener('click', () => navigation.goToStep(2));
    },

    async runAnalysis() {
        pixelLoader.show('analyzing');

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
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
                utils.showToast(result.message || 'Ошибка анализа', 'error');
            }
        } catch (error) {
            console.error('Analysis error:', error);
            utils.showToast('Ошибка соединения с сервером', 'error');
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
                <h6>Примененные корректировки:</h6>
                <div class="table-responsive">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>Коэффициент</th>
                                <th>Описание</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${Object.entries(fairPrice.adjustments || {}).map(([key, adj]) => `
                                <tr>
                                    <td><strong>${utils.formatNumber((adj.value - 1) * 100, 2)}%</strong></td>
                                    <td>${adj.description || ''}</td>
                                </tr>
                            `).join('')}
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
    }
};

// Floating buttons
const floatingButtons = {
    init() {
        const nextBtn = document.getElementById('floating-next-btn');
        const backBtn = document.getElementById('floating-back-btn');

        nextBtn.addEventListener('click', () => {
            if (state.currentStep === 1) {
                screen1.updateTargetProperty();
            } else if (state.currentStep === 2) {
                navigation.goToStep(3);
            } else if (state.currentStep === 3) {
                // На последнем экране кнопка может скачивать отчет
                utils.showToast('Функция скачивания в разработке', 'info');
            }
        });

        backBtn.addEventListener('click', () => {
            if (state.currentStep > 1) {
                navigation.goToStep(state.currentStep - 1);
            }
        });

        // Обновляем видимость кнопок при смене экрана
        this.updateButtons();
    },

    updateButtons() {
        const nextBtn = document.getElementById('floating-next-btn');
        const backBtn = document.getElementById('floating-back-btn');

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

        // Обновляем текст кнопки "Далее"
        const nextText = nextBtn.querySelector('span');
        if (state.currentStep === 1) {
            nextText.textContent = 'Далее';
        } else if (state.currentStep === 2) {
            nextText.textContent = 'К анализу';
        } else if (state.currentStep === 3) {
            nextText.textContent = 'Скачать отчет';
        }
    }
};

// ══════════════════════════════════════════════════════════════
// Pixel Loader - Веселые пиксельные лоадеры
// ══════════════════════════════════════════════════════════════

const pixelLoader = {
    // Смешные тексты для разных этапов
    messages: {
        // Парсинг объекта
        parsing: [
            '🏃 Звоню агенту узнать как дела...',
            '📞 Агент говорит "перезвоните через 5 минут"...',
            '🏢 Бегу в Росреестр за выпиской ЕГРН...',
            '📋 Очередь в Росреестр... стою 47-й...',
            '🔍 Проверяю есть ли у квартиры долги...',
            '💰 Смотрю кто платит за ЖКХ...',
            '🏠 Изучаю планировку через замочную скважину...',
            '📐 Меряю площадь лазерной рулеткой...',
            '🚪 Стучусь к соседям узнать про шум...',
            '🔎 Ищу подвох в объявлении...',
        ],

        // Поиск аналогов
        searching: [
            '🧬 Применяю технику клонирования...',
            '👥 Отлично, меня теперь 100!',
            '🏃‍♂️ Бегаю по району смотрю похожие квартиры...',
            '🗺️ Изучаю карту района как таксист...',
            '🔍 Заглядываю в окна соседних домов...',
            '📱 Листаю Циан как Instagram...',
            '🎯 Нашел! Нет, это не то...',
            '🔎 Ищу иголку в стоге сена...',
            '🏘️ Обхожу весь ЖК пешком...',
            '👀 Смотрю на объявления соседей...',
            '📊 Считаю сколько окон на этаж...',
            '🚶 Меряю расстояние до метро шагами...',
        ],

        // Анализ
        analyzing: [
            '🧮 Включаю режим гения математики...',
            '📊 Строю графики как безумный ученый...',
            '🔬 Анализирую данные под микроскопом...',
            '🤓 Надеваю очки для умных...',
            '📈 Рисую тренды цен на салфетке...',
            '💡 Эврика! Или нет...',
            '🎓 Применяю знания из универа...',
            '🧠 Активирую все нейроны...',
            '📐 Вывожу сложные формулы...',
            '⚡ Считаю быстрее калькулятора...',
            '🎯 Вычисляю идеальную цену...',
            '💰 Определяю стоит ли оно того...',
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
document.addEventListener('DOMContentLoaded', () => {
    screen1.init();
    screen2.init();
    screen3.init();
    floatingButtons.init();

    // Экспортируем для доступа из navigation
    window.floatingButtons = floatingButtons;
});
