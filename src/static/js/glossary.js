/**
 * Интерактивный глоссарий терминов
 *
 * Автоматически добавляет всплывающие подсказки для всех терминов,
 * помеченных атрибутом data-term
 *
 * Использование:
 * <span data-term="median">медиана</span>
 */

const GLOSSARY = {
    'median': {
        title: 'Медиана',
        simple: 'Среднее значение при сортировке',
        detailed: 'Медиана более устойчива к выбросам, чем среднее. Если одна квартира стоит 100 млн, она не искажает картину рынка.',
        example: `
            <strong>Пример:</strong><br>
            Цены: [1, 2, 3, 100] млн ₽<br>
            <span style="color: #e74c3c;">Среднее = 26.5 млн</span> ❌<br>
            <span style="color: #27ae60;">Медиана = 2.5 млн</span> ✓
        `,
        why: 'Мы используем медиану, чтобы случайные аномально дорогие или дешевые квартиры не влияли на расчет справедливой цены.'
    },

    'sigma': {
        title: 'Правило ±3σ (три сигмы)',
        simple: 'Фильтрация выбросов',
        detailed: '99.7% нормальных данных находятся в пределах ±3 стандартных отклонений от среднего. Все, что выходит за эти границы - аномалия.',
        formula: 'μ ± 3σ',
        example: `
            <strong>Пример:</strong><br>
            Средняя цена: 200k ₽/м²<br>
            Стандартное отклонение: 30k<br>
            Границы: 200k ± (3 × 30k) = <strong>110k - 290k</strong><br>
            <br>
            Квартира за 350k? <span style="color: #e74c3c;">Исключаем</span><br>
            Квартира за 80k? <span style="color: #e74c3c;">Исключаем</span>
        `,
        why: 'Убираем квартиры с ошибками в объявлениях или уникальные объекты (пентхаусы, аварийное жилье), которые не отражают реальный рынок.'
    },

    'opportunity_cost': {
        title: 'Упущенная выгода',
        simple: 'Потерянный доход от альтернативных вложений',
        detailed: 'Пока квартира не продана, вы теряете потенциальный доход, который могли бы получить, вложив деньги в другое место (депозит, облигации, недвижимость в аренду).',
        formula: 'Цена × Годовая ставка × (Месяцы / 12)',
        example: `
            <strong>Пример:</strong><br>
            Квартира: 25 млн ₽<br>
            Альтернативная доходность: 8% годовых<br>
            Время ожидания: 6 месяцев<br>
            <br>
            <strong>Упущенная выгода:</strong><br>
            25,000,000 × 0.08 × (6/12) = <span style="color: #e74c3c; font-size: 1.2em;">1,000,000 ₽</span>
        `,
        why: 'Важно учитывать альтернативную стоимость времени. Иногда быстрая продажа с небольшой скидкой выгоднее, чем долгое ожидание "идеальной" цены.'
    },

    'cumulative_probability': {
        title: 'Кумулятивная вероятность',
        simple: 'Шанс продать ДО конца месяца N',
        detailed: 'В отличие от месячной вероятности (шанс продать ИМЕННО в этом месяце), кумулятивная показывает накопленную вероятность продать К КОНЦУ указанного месяца.',
        formula: 'P_кум(N) = 1 - ∏[1 - P(t)] для t=1 до N',
        example: `
            <strong>Пример:</strong><br>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="background: #ecf0f1;">
                    <th style="padding: 5px; text-align: left;">Месяц</th>
                    <th style="padding: 5px;">Месячная P</th>
                    <th style="padding: 5px;">Кумулятивная P</th>
                </tr>
                <tr>
                    <td style="padding: 5px;">1</td>
                    <td style="padding: 5px; text-align: center;">40%</td>
                    <td style="padding: 5px; text-align: center;"><strong>40%</strong></td>
                </tr>
                <tr style="background: #ecf0f1;">
                    <td style="padding: 5px;">2</td>
                    <td style="padding: 5px; text-align: center;">35%</td>
                    <td style="padding: 5px; text-align: center;"><strong>61%</strong></td>
                </tr>
                <tr>
                    <td style="padding: 5px;">3</td>
                    <td style="padding: 5px; text-align: center;">25%</td>
                    <td style="padding: 5px; text-align: center;"><strong>71%</strong></td>
                </tr>
            </table>
            <br>
            К концу 3-го месяца вероятность продажи = <strong>71%</strong>
        `,
        why: 'Помогает планировать: "С вероятностью 75% я продам за 4 месяца" - более полезная информация, чем "В 4-м месяце вероятность 20%".'
    },

    'roi': {
        title: 'ROI (Return on Investment)',
        simple: 'Возврат на инвестиции',
        detailed: 'Показывает, сколько вы заработаете на каждый вложенный рубль. ROI > 100% означает, что инвестиция окупается с прибылью.',
        formula: 'ROI = (Прибыль - Затраты) / Затраты × 100%',
        example: `
            <strong>Пример:</strong><br>
            Инвестиция в дизайн-ремонт: 500,000 ₽<br>
            Прирост стоимости квартиры: 800,000 ₽<br>
            <br>
            <strong>ROI:</strong><br>
            (800,000 - 500,000) / 500,000 × 100% = <span style="color: #27ae60; font-size: 1.2em;">60%</span><br>
            <br>
            На каждый вложенный рубль заработаете <strong>0.60 ₽</strong>
        `,
        why: 'Позволяет сравнивать разные улучшения и выбрать наиболее выгодные. Не все улучшения окупаются!'
    },

    'price_per_sqm': {
        title: 'Цена за м²',
        simple: 'Стоимость одного квадратного метра',
        detailed: 'Универсальная метрика для сравнения квартир разной площади. Позволяет понять, не переплачиваете ли вы за "лишние" метры.',
        formula: 'Цена за м² = Общая цена / Общая площадь',
        example: `
            <strong>Сравнение:</strong><br>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="background: #ecf0f1;">
                    <th style="padding: 5px; text-align: left;">Квартира</th>
                    <th style="padding: 5px;">Цена</th>
                    <th style="padding: 5px;">Площадь</th>
                    <th style="padding: 5px;">Цена/м²</th>
                </tr>
                <tr>
                    <td style="padding: 5px;">A</td>
                    <td style="padding: 5px;">20 млн</td>
                    <td style="padding: 5px;">100 м²</td>
                    <td style="padding: 5px;"><strong>200k</strong></td>
                </tr>
                <tr style="background: #ecf0f1;">
                    <td style="padding: 5px;">B</td>
                    <td style="padding: 5px;">18 млн</td>
                    <td style="padding: 5px;">80 м²</td>
                    <td style="padding: 5px;"><strong>225k</strong> ❌</td>
                </tr>
            </table>
            <br>
            Квартира B меньше и дешевле, но <strong>дороже за м²</strong>!
        `,
        why: 'Основная метрика для анализа рынка и определения справедливой цены.'
    },

    'overpricing': {
        title: 'Переоценка',
        simple: 'Насколько цена выше справедливой',
        detailed: 'Показывает, на сколько процентов текущая цена выше расчетной справедливой цены рынка.',
        formula: 'Переоценка = (Текущая - Справедливая) / Справедливая × 100%',
        example: `
            <strong>Интерпретация:</strong><br>
            <ul style="margin: 10px 0; padding-left: 20px;">
                <li><span style="color: #27ae60;">0-5%</span> - В пределах нормы</li>
                <li><span style="color: #f39c12;">5-10%</span> - Умеренная переоценка</li>
                <li><span style="color: #e67e22;">10-15%</span> - Сильная переоценка</li>
                <li><span style="color: #e74c3c;">>15%</span> - Критическая переоценка</li>
            </ul>
        `,
        why: 'Чем выше переоценка, тем ниже вероятность продажи и дольше время на рынке.'
    },

    'living_area_percent': {
        title: 'Процент жилой площади',
        simple: 'Доля полезной площади от общей',
        detailed: 'Показывает, сколько из общей площади квартиры составляет жилое пространство (комнаты). Остальное - коридоры, санузлы, кладовки.',
        formula: 'Жилая площадь / Общая площадь × 100%',
        example: `
            <strong>Норма:</strong><br>
            <ul style="margin: 10px 0; padding-left: 20px;">
                <li><span style="color: #27ae60;">>60%</span> - Отлично</li>
                <li><span style="color: #f39c12;">40-60%</span> - Нормально</li>
                <li><span style="color: #e74c3c;"><30%</span> - Плохая планировка</li>
            </ul>
            <br>
            <strong>Пример:</strong><br>
            Общая площадь: 100 м²<br>
            Жилая площадь: 70 м²<br>
            Процент: <strong>70%</strong> ✓
        `,
        why: 'Низкий процент означает много "непродуктивной" площади, за которую вы переплачиваете.'
    }
};

class GlossaryTooltip {
    constructor() {
        this.tooltip = null;
        this.currentTerm = null;
        this.hideTimeout = null;
        this.init();
    }

    init() {
        // Создаем tooltip элемент
        this.tooltip = document.createElement('div');
        this.tooltip.className = 'glossary-tooltip';
        this.tooltip.style.display = 'none';
        document.body.appendChild(this.tooltip);

        // Подключаем ко всем терминам
        this.attachToTerms();

        // Обработчики для tooltip
        this.tooltip.addEventListener('mouseenter', () => {
            clearTimeout(this.hideTimeout);
        });

        this.tooltip.addEventListener('mouseleave', () => {
            this.hide();
        });
    }

    attachToTerms() {
        document.querySelectorAll('[data-term]').forEach(el => {
            // Добавляем класс для стилизации
            el.classList.add('glossary-term');

            // Обработчики событий
            el.addEventListener('mouseenter', (e) => {
                clearTimeout(this.hideTimeout);
                this.show(e, el.dataset.term);
            });

            el.addEventListener('mouseleave', () => {
                this.hideTimeout = setTimeout(() => this.hide(), 300);
            });

            // Для мобильных устройств
            el.addEventListener('click', (e) => {
                e.preventDefault();
                if (this.currentTerm === el.dataset.term && this.tooltip.style.display !== 'none') {
                    this.hide();
                } else {
                    this.show(e, el.dataset.term);
                }
            });
        });
    }

    show(event, termKey) {
        const term = GLOSSARY[termKey];
        if (!term) {
            console.warn(`Term not found in glossary: ${termKey}`);
            return;
        }

        this.currentTerm = termKey;

        // Формируем HTML
        this.tooltip.innerHTML = `
            <div class="tooltip-header">
                <h4>${term.title}</h4>
                <span class="tooltip-close" onclick="this.closest('.glossary-tooltip').style.display='none'">×</span>
            </div>
            <div class="tooltip-body">
                <div class="tooltip-simple">
                    <strong>Простыми словами:</strong> ${term.simple}
                </div>
                <div class="tooltip-detailed">
                    ${term.detailed}
                </div>
                ${term.formula ? `
                    <div class="tooltip-formula">
                        <strong>Формула:</strong><br>
                        <code>${term.formula}</code>
                    </div>
                ` : ''}
                ${term.example ? `
                    <div class="tooltip-example">
                        ${term.example}
                    </div>
                ` : ''}
                <div class="tooltip-why">
                    <strong>💡 Зачем это нужно:</strong><br>
                    ${term.why}
                </div>
            </div>
        `;

        // Позиционирование
        this.position(event.target);

        // Показываем
        this.tooltip.style.display = 'block';

        // Добавляем анимацию появления
        this.tooltip.style.opacity = '0';
        setTimeout(() => {
            this.tooltip.style.opacity = '1';
        }, 10);
    }

    position(targetElement) {
        const rect = targetElement.getBoundingClientRect();
        const tooltipRect = this.tooltip.getBoundingClientRect();

        // Позиция по умолчанию - снизу
        let top = rect.bottom + window.scrollY + 10;
        let left = rect.left + window.scrollX;

        // Проверяем, не выходит ли за границы экрана
        if (left + tooltipRect.width > window.innerWidth) {
            left = window.innerWidth - tooltipRect.width - 20;
        }

        if (left < 10) {
            left = 10;
        }

        // Если не помещается снизу, показываем сверху
        if (top + tooltipRect.height > window.innerHeight + window.scrollY) {
            top = rect.top + window.scrollY - tooltipRect.height - 10;
        }

        this.tooltip.style.top = top + 'px';
        this.tooltip.style.left = left + 'px';
    }

    hide() {
        this.tooltip.style.opacity = '0';
        setTimeout(() => {
            this.tooltip.style.display = 'none';
            this.currentTerm = null;
        }, 200);
    }

    // Публичный метод для добавления новых терминов динамически
    refresh() {
        this.attachToTerms();
    }
}

// Автоматическая инициализация при загрузке DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.glossary = new GlossaryTooltip();
    });
} else {
    window.glossary = new GlossaryTooltip();
}

// Экспортируем для использования в модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { GlossaryTooltip, GLOSSARY };
}
