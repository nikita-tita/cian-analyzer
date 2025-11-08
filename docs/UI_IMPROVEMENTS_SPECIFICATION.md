# Спецификация UI доработок | Housler

**Дата:** 08.11.2025
**Версия:** 1.0
**Статус:** К внедрению

---

## 📋 Оглавление

1. [Обзор задачи](#обзор-задачи)
2. [Текущие проблемы](#текущие-проблемы)
3. [Единая система дизайна](#единая-система-дизайна)
4. [Детальные задачи](#детальные-задачи)
5. [Архитектурные рекомендации](#архитектурные-рекомендации)
6. [План внедрения](#план-внедрения)
7. [Контроль качества](#контроль-качества)

---

## 🎯 Обзор задачи

### Цель
Привести все UI компоненты к единому стилю **Black & White Premium** и улучшить UX взаимодействий.

### Область применения
- Уведомления (Toasts/Alerts)
- Лоадеры (Loading screens)
- Хэдеры страниц
- Информационный контент (Pricing)
- Все интерактивные элементы

---

## ❌ Текущие проблемы

### 1. **Inconsistent Design System**
- ✗ Toast уведомления используют Bootstrap цвета (синий, зеленый, желтый, красный)
- ✗ Отличается от основного Black & White стиля приложения
- ✗ Нет единой палитры для всех компонентов

**Файлы:**
- `static/js/wizard.js:26-39` - showToast() с Bootstrap классами
- `static/css/wizard.css:505-510` - белый фон Toast

### 2. **Проблемы с лоадерами**
- ✗ Текст содержит эмодзи (🏃, 📞, 🏢, etc.)
- ✗ Длинные сообщения обрываются и невозможно дочитать
- ✗ Не профессиональный тон (слишком игривый)
- ✗ Медленная анимация бегущей строки

**Файлы:**
- `static/js/wizard.js:891-982` - pixelLoader с emoji и длинными текстами
- `templates/wizard.html:420-440` - разметка Pixel Loader
- `static/css/wizard.css:688-875` - стили лоадера и advice ticker

### 3. **Отсутствие хэдера на калькуляторе**
- ✗ На главной странице лендинга есть хэдер с навигацией
- ✗ На странице калькулятора только логотип "Housler" без навигации
- ✗ Нет единообразия между страницами

**Файлы:**
- `templates/wizard.html:22-24` - простой div с логотипом
- `templates/index.html:22-35` - полноценная навигация

### 4. **Дублирование названия "Housler"**
- ✗ На странице калькулятора название "Housler" дублируется
- ✗ Если добавить полноценный хэдер, будет избыточность

**Файлы:**
- `templates/wizard.html:23` - `<div class="logo">Housler</div>`

### 5. **Непонятная секция "Стоимость услуг"**
- ✗ Не ясно, что означают "до 25 млн ₽", "25-50 млн ₽", "от 50 млн ₽"
- ✗ Не объяснено, что это диапазоны стоимости объектов недвижимости
- ✗ Не понятна разница между "Опция A" и "Опция B"
- ✗ Отсутствует информация про условия оплаты 2%

**Файлы:**
- `templates/index.html:107-176` - секция Pricing
- `static/css/landing.css` - стили pricing секции

**Текущий вид:**
```
до 25 млн ₽
  Опция A: 2% без предоплаты
  Опция B: 100 000 ₽ фиксированная сумма
```

**Проблема:** Пользователь не понимает:
- Что такое "25 млн" - это цена объекта или услуги?
- Что такое опция A и чем она отличается от B?
- Когда применяется правило 2%, а когда фикс?
- Что происходит если продали не мы?

### 6. **Алерты не в едином стиле**
- ✗ Используются разные цвета для разных типов
- ✗ Нет единого подхода к отображению ошибок
- ✗ Сообщения об ошибках могут быть техническими и непонятными

**Файлы:**
- `src/static/css/unified-dashboard.css:602-631` - Alert стили

---

## 🎨 Единая система дизайна

### Design System: "Black & White Premium"

#### Цветовая палитра

```css
:root {
    /* Основные цвета */
    --black: #000000;           /* Основной текст, фон элементов */
    --white: #FFFFFF;           /* Фон страниц, текст на черном */

    /* Оттенки серого */
    --gray-900: #1A1A1A;        /* Темный фон (hover states) */
    --gray-800: #333333;        /* Вторичный текст */
    --gray-700: #4A4A4A;        /* Границы темные */
    --gray-300: #D1D5DB;        /* Границы светлые */
    --gray-200: #E5E7EB;        /* Разделители */
    --gray-100: #F5F5F5;        /* Светлый фон секций */

    /* Функциональные цвета (для алертов) */
    --success-bg: #000000;      /* Черный фон */
    --success-text: #FFFFFF;    /* Белый текст */
    --success-border: #4ADE80;  /* Зеленый акцент */

    --error-bg: #000000;
    --error-text: #FFFFFF;
    --error-border: #EF4444;    /* Красный акцент */

    --warning-bg: #000000;
    --warning-text: #FFFFFF;
    --warning-border: #F59E0B;  /* Оранжевый акцент */

    --info-bg: #000000;
    --info-text: #FFFFFF;
    --info-border: #3B82F6;     /* Синий акцент */
}
```

#### Типографика

```css
/* Шрифты */
--font-primary: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
--font-mono: "SF Mono", Monaco, "Cascadia Code", monospace;

/* Размеры */
--text-xs: 12px;
--text-sm: 14px;
--text-base: 16px;
--text-lg: 18px;
--text-xl: 20px;
--text-2xl: 24px;
--text-3xl: 32px;
```

#### Компоненты

##### Toast/Alert (Уведомления)

**Структура:**
```
┌─────────────────────────────┐
│ ▎Уведомление           [×] │ ← Черный фон, белый текст
│ ▎                           │ ← Цветная левая граница (accent)
│ ▎Объект успешно загружен   │
└─────────────────────────────┘
```

**Спецификация:**
- Фон: `#000000` (черный)
- Текст: `#FFFFFF` (белый)
- Левая граница: 4px, цвет зависит от типа
  - Success: `#4ADE80` (зеленый)
  - Error: `#EF4444` (красный)
  - Warning: `#F59E0B` (оранжевый)
  - Info: `#3B82F6` (синий)
- Padding: 16px
- Border-radius: 0 (sharp edges)
- Box-shadow: `0 4px 16px rgba(0, 0, 0, 0.3)`

##### Loader (Лоадер)

**Принципы:**
- Минимализм - короткие, понятные фразы
- Профессионализм - без emoji и шуток
- Читаемость - текст не обрывается
- Информативность - показывает что происходит

**Структура:**
```
┌───────────────────────────┐
│                           │
│     [●●●○○○○○]           │ ← Прогресс-бар
│                           │
│   Загрузка данных...      │ ← Лаконичный текст
│                           │
└───────────────────────────┘
```

**Спецификация:**
- Фон оверлея: `rgba(0, 0, 0, 0.9)`
- Контейнер: белая рамка 2px
- Текст: белый, 16px, моноширинный шрифт
- Прогресс-бар: белый, анимация 1.5s
- Без emoji
- Максимум 30 символов на сообщение

**Тексты:**
- Парсинг: "Загрузка объекта...", "Проверка данных...", "Получение информации..."
- Поиск: "Поиск аналогов...", "Анализ рынка...", "Подбор объектов..."
- Анализ: "Расчет стоимости...", "Формирование отчета...", "Финализация..."

##### Header (Хэдер)

**Спецификация для калькулятора:**
- Высота: 80px
- Фон: `#FFFFFF`
- Нижняя граница: 1px solid `#E5E7EB`
- Логотип: "HOUSLER", 24px, слева
- Навигация: справа (опционально)
  - "Назад на главную" - ссылка на лендинг

---

## 📝 Детальные задачи

### Задача 1: Унификация Toast уведомлений

**Приоритет:** 🔴 Высокий

**Что сделать:**
1. Обновить CSS стили для Toast
2. Изменить JavaScript функцию showToast()
3. Добавить цветные левые границы вместо цветных фонов

**Файлы для изменения:**
- `static/css/wizard.css` (строки 505-510)
- `static/js/wizard.js` (строки 26-39)
- `templates/wizard.html` (строки 442-453)

**Новая реализация:**

CSS:
```css
.toast {
    background: var(--black);
    color: var(--white);
    border: 1px solid var(--gray-700);
    border-left-width: 4px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    border-radius: 0;
}

.toast-header {
    background: transparent;
    color: var(--white);
    border-bottom: 1px solid var(--gray-700);
}

.toast.toast-success {
    border-left-color: #4ADE80;
}

.toast.toast-error {
    border-left-color: #EF4444;
}

.toast.toast-warning {
    border-left-color: #F59E0B;
}

.toast.toast-info {
    border-left-color: #3B82F6;
}

.toast .btn-close {
    filter: invert(1); /* Белая иконка закрытия */
}
```

JavaScript:
```javascript
showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    const toastBody = document.getElementById('toast-body');
    toastBody.textContent = message;

    // Удаляем старые классы
    toast.classList.remove('toast-success', 'toast-error', 'toast-warning', 'toast-info');

    // Добавляем новый класс
    toast.classList.add(`toast-${type}`);

    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
}
```

**Типы сообщений:**
- `success` - Успешные операции (зеленая граница)
- `error` - Ошибки (красная граница)
- `warning` - Предупреждения (оранжевая граница)
- `info` - Информация (синяя граница)

**Примеры использования:**
```javascript
utils.showToast('Объект успешно загружен', 'success');
utils.showToast('Не удалось подключиться к серверу', 'error');
utils.showToast('Заполните все обязательные поля', 'warning');
utils.showToast('Идет загрузка данных', 'info');
```

---

### Задача 2: Улучшение Pixel Loader

**Приоритет:** 🔴 Высокий

**Что сделать:**
1. Убрать все emoji из сообщений
2. Сократить тексты до 30 символов
3. Сделать более профессиональные формулировки
4. Ускорить анимацию бегущей строки (advice ticker)

**Файлы для изменения:**
- `static/js/wizard.js` (строки 891-982)
- `static/css/wizard.css` (строки 826-875)

**Новые тексты:**

```javascript
messages: {
    parsing: [
        'Загрузка объекта',
        'Проверка данных',
        'Получение информации',
        'Анализ параметров',
        'Валидация адреса',
        'Обработка запроса'
    ],

    searching: [
        'Поиск аналогов',
        'Анализ рынка',
        'Подбор объектов',
        'Сравнение параметров',
        'Оценка района',
        'Фильтрация данных'
    ],

    analyzing: [
        'Расчет стоимости',
        'Анализ данных',
        'Формирование отчета',
        'Построение графиков',
        'Оценка рисков',
        'Финализация'
    ]
}
```

**Ускорение Advice Ticker:**

CSS (изменить):
```css
.advice-ticker-track {
    animation: ticker 60s linear infinite; /* Было 180s, стало 60s */
}
```

**Удалить emoji из Advice Ticker:**
- Убрать все эмодзи из текстов советов
- Оставить только текстовую информацию

---

### Задача 3: Добавление хэдера на страницу калькулятора

**Приоритет:** 🟡 Средний

**Что сделать:**
1. Создать полноценный хэдер с навигацией
2. Добавить ссылку "Назад на главную"
3. Стилизовать в соответствии с дизайн-системой

**Файлы для изменения:**
- `templates/wizard.html` (строки 22-24)
- `static/css/wizard.css` (строки 31-43)

**Новая реализация:**

HTML:
```html
<!-- Header -->
<header class="header">
    <div class="header-content">
        <div class="logo">HOUSLER</div>
        <nav class="header-nav">
            <a href="/" class="nav-link">← Назад на главную</a>
        </nav>
    </div>
</header>
```

CSS:
```css
.header {
    background: var(--white);
    border-bottom: 1px solid var(--border-color);
    padding: 0;
}

.header-content {
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px 40px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.logo {
    font-size: 24px;
    font-weight: 600;
    color: var(--black);
    letter-spacing: -0.02em;
}

.header-nav {
    display: flex;
    gap: 32px;
}

.nav-link {
    color: var(--gray-dark);
    text-decoration: none;
    font-size: 16px;
    transition: color 0.2s;
}

.nav-link:hover {
    color: var(--black);
}

@media (max-width: 768px) {
    .header-content {
        padding: 16px 24px;
    }

    .logo {
        font-size: 20px;
    }

    .nav-link {
        font-size: 14px;
    }
}
```

---

### Задача 4: Удаление дублирования названия "Housler"

**Приоритет:** 🟢 Низкий (зависит от Задачи 3)

**Что сделать:**
1. После добавления полноценного хэдера (Задача 3)
2. Убедиться, что название не дублируется
3. Проверить что хэдер отображается корректно на всех экранах

**Файлы для проверки:**
- `templates/wizard.html` - весь layout

**Действие:**
- Это будет автоматически решено при выполнении Задачи 3
- Текущий `<div class="logo">Housler</div>` будет заменен на полноценный хэдер

---

### Задача 5: Улучшение секции "Стоимость услуг"

**Приоритет:** 🔴 Высокий

**Что сделать:**
1. Добавить пояснение что цифры означают стоимость объекта
2. Объяснить разницу между опцией A и B
3. Добавить информацию про условия оплаты 2%
4. Сделать карточки более понятными

**Файлы для изменения:**
- `templates/index.html` (строки 107-176)
- `static/css/landing.css` - pricing секция

**Новая реализация:**

HTML:
```html
<!-- Pricing Section -->
<section class="section mobile-swipe" id="pricing">
    <div class="container">
        <h2 class="section-title">Стоимость услуг</h2>
        <p class="section-description">
            Прозрачное ценообразование в зависимости от стоимости вашего объекта.
            <br>Выберите удобный вариант оплаты.
        </p>

        <div class="swipe-container">
            <div class="pricing-grid">
                <!-- Карточка 1 -->
                <div class="pricing-card">
                    <div class="pricing-header">
                        <div class="price-range-label">Стоимость объекта</div>
                        <h3>до 25 млн ₽</h3>
                    </div>
                    <div class="pricing-body">
                        <div class="pricing-option">
                            <div class="option-label">
                                <span class="option-badge">Опция A</span>
                                <span class="option-title">Без предоплаты</span>
                            </div>
                            <div class="option-price">2%</div>
                            <div class="option-description">
                                Комиссия 2% от стоимости объекта.
                                <br>
                                <strong>Платите только если продали мы.</strong>
                            </div>
                        </div>
                        <div class="pricing-divider"></div>
                        <div class="pricing-option">
                            <div class="option-label">
                                <span class="option-badge option-badge-alt">Опция B</span>
                                <span class="option-title">Фиксированная цена</span>
                            </div>
                            <div class="option-price">100 000 ₽</div>
                            <div class="option-description">
                                Фиксированная сумма + 2% если продали мы.
                                <br>
                                <strong>Если продали не мы — доплата не нужна.</strong>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Карточка 2 -->
                <div class="pricing-card pricing-card-featured">
                    <div class="pricing-badge">Популярный</div>
                    <div class="pricing-header">
                        <div class="price-range-label">Стоимость объекта</div>
                        <h3>25–50 млн ₽</h3>
                    </div>
                    <div class="pricing-body">
                        <div class="pricing-option">
                            <div class="option-label">
                                <span class="option-badge">Опция A</span>
                                <span class="option-title">Без предоплаты</span>
                            </div>
                            <div class="option-price">2%</div>
                            <div class="option-description">
                                Комиссия 2% от стоимости объекта.
                                <br>
                                <strong>Платите только если продали мы.</strong>
                            </div>
                        </div>
                        <div class="pricing-divider"></div>
                        <div class="pricing-option">
                            <div class="option-label">
                                <span class="option-badge option-badge-alt">Опция B</span>
                                <span class="option-title">Фиксированная цена</span>
                            </div>
                            <div class="option-price">200 000 ₽</div>
                            <div class="option-description">
                                Фиксированная сумма + 2% если продали мы.
                                <br>
                                <strong>Если продали не мы — доплата не нужна.</strong>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Карточка 3 -->
                <div class="pricing-card">
                    <div class="pricing-header">
                        <div class="price-range-label">Стоимость объекта</div>
                        <h3>от 50 млн ₽</h3>
                    </div>
                    <div class="pricing-body">
                        <div class="pricing-option">
                            <div class="option-label">
                                <span class="option-badge">Опция A</span>
                                <span class="option-title">Без предоплаты</span>
                            </div>
                            <div class="option-price">2%</div>
                            <div class="option-description">
                                Комиссия 2% от стоимости объекта.
                                <br>
                                <strong>Платите только если продали мы.</strong>
                            </div>
                        </div>
                        <div class="pricing-divider"></div>
                        <div class="pricing-option">
                            <div class="option-label">
                                <span class="option-badge option-badge-alt">Опция B</span>
                                <span class="option-title">Фиксированная цена</span>
                            </div>
                            <div class="option-price">300 000 ₽</div>
                            <div class="option-description">
                                Фиксированная сумма + 2% если продали мы.
                                <br>
                                <strong>Если продали не мы — доплата не нужна.</strong>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Пояснения -->
        <div class="pricing-explanation">
            <div class="explanation-card">
                <h4>Как работают опции?</h4>
                <div class="explanation-grid">
                    <div class="explanation-item">
                        <div class="explanation-icon">A</div>
                        <div class="explanation-content">
                            <strong>Опция A — Без рисков</strong>
                            <p>Вы ничего не платите до продажи. Комиссия 2% только если сделку закрыли мы.</p>
                        </div>
                    </div>
                    <div class="explanation-item">
                        <div class="explanation-icon">B</div>
                        <div class="explanation-content">
                            <strong>Опция B — Фиксированная цена</strong>
                            <p>Фиксированная предоплата за подготовку. Доплата 2% только если покупателя привели мы.</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <p class="pricing-note">
            💡 <strong>Прозрачно и честно:</strong> Если вы нашли покупателя сами при опции B — никаких доплат.
        </p>
    </div>
</section>
```

**Дополнительные CSS стили:**

```css
/* Pricing improvements */
.price-range-label {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-light);
    margin-bottom: 8px;
}

.option-badge {
    display: inline-block;
    padding: 4px 12px;
    background: var(--black);
    color: var(--white);
    font-size: 12px;
    font-weight: 600;
    border-radius: 4px;
    margin-bottom: 8px;
}

.option-badge-alt {
    background: var(--gray-700);
}

.option-title {
    display: block;
    font-weight: 600;
    font-size: 16px;
    margin-top: 8px;
    color: var(--color-text);
}

.option-description {
    font-size: 14px;
    line-height: 1.6;
    color: var(--color-text-light);
    margin-top: 12px;
}

.option-description strong {
    color: var(--color-text);
}

.pricing-card-featured {
    position: relative;
    border: 2px solid var(--black);
    transform: scale(1.05);
}

.pricing-badge {
    position: absolute;
    top: -12px;
    right: 24px;
    background: var(--black);
    color: var(--white);
    padding: 4px 16px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.pricing-explanation {
    margin-top: 48px;
}

.explanation-card {
    background: var(--color-bg-gray);
    padding: 32px;
    border-radius: 8px;
}

.explanation-card h4 {
    font-size: 20px;
    margin-bottom: 24px;
    text-align: center;
}

.explanation-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 24px;
}

.explanation-item {
    display: flex;
    gap: 16px;
    align-items: start;
}

.explanation-icon {
    width: 40px;
    height: 40px;
    background: var(--black);
    color: var(--white);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 18px;
    flex-shrink: 0;
}

.explanation-content strong {
    display: block;
    margin-bottom: 8px;
    color: var(--color-text);
}

.explanation-content p {
    color: var(--color-text-light);
    line-height: 1.6;
    margin: 0;
}

.pricing-note {
    text-align: center;
    margin-top: 32px;
    font-size: 16px;
    color: var(--color-text-light);
}

@media (max-width: 768px) {
    .pricing-card-featured {
        transform: scale(1);
    }

    .explanation-grid {
        grid-template-columns: 1fr;
    }
}
```

---

### Задача 6: Унификация всех Alert компонентов

**Приоритет:** 🟡 Средний

**Что сделать:**
1. Привести все alert компоненты к единому стилю
2. Создать человекопонятные сообщения об ошибках
3. Добавить иконки для разных типов

**Файлы для изменения:**
- `src/static/css/unified-dashboard.css` (строки 602-631)
- Все места где используются alerts

**Новая реализация:**

CSS:
```css
.alert {
    background: var(--black);
    color: var(--white);
    border: 1px solid var(--gray-700);
    border-left-width: 4px;
    padding: 16px 20px;
    margin-bottom: 16px;
    border-radius: 0;
    display: flex;
    align-items: start;
    gap: 12px;
}

.alert-icon {
    width: 20px;
    height: 20px;
    flex-shrink: 0;
    margin-top: 2px;
}

.alert-content {
    flex: 1;
}

.alert-title {
    font-weight: 600;
    font-size: 16px;
    margin-bottom: 4px;
}

.alert-message {
    font-size: 14px;
    line-height: 1.5;
    opacity: 0.9;
}

/* Типы */
.alert-success {
    border-left-color: #4ADE80;
}

.alert-error {
    border-left-color: #EF4444;
}

.alert-warning {
    border-left-color: #F59E0B;
}

.alert-info {
    border-left-color: #3B82F6;
}
```

**Примеры человекопонятных сообщений:**

❌ **Плохо:**
```
Error: Network request failed with status 500
```

✅ **Хорошо:**
```
Не удалось подключиться к серверу
Проверьте интернет-соединение и попробуйте снова
```

❌ **Плохо:**
```
Invalid input: field 'price' must be a number
```

✅ **Хорошо:**
```
Некорректная цена
Введите числовое значение, например: 15000000
```

**Создать файл с переводами ошибок:**

`static/js/error-messages.js`:
```javascript
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

    // Ошибки валидации
    'invalid_url': {
        title: 'Некорректный URL',
        message: 'Введите корректную ссылку на объявление с Cian.ru'
    },
    'invalid_price': {
        title: 'Некорректная цена',
        message: 'Введите числовое значение, например: 15000000'
    },
    'missing_required_fields': {
        title: 'Заполните все поля',
        message: 'Необходимо заполнить: адрес, цену, площадь и количество комнат'
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

    // Успешные операции
    'object_loaded': {
        title: 'Объект загружен',
        message: 'Данные успешно получены и проверены'
    },
    'comparables_found': {
        title: 'Аналоги найдены',
        message: 'Найдено подходящих объектов для сравнения'
    }
};

function showAlert(errorKey, type = 'error') {
    const data = ERROR_MESSAGES[errorKey] || {
        title: 'Произошла ошибка',
        message: errorKey
    };

    // Использовать существующую систему Toast
    utils.showToast(`${data.title}: ${data.message}`, type);
}
```

---

## 🏗️ Архитектурные рекомендации

### 1. Создать файл Design System

**Файл:** `static/css/design-system.css`

Создать центральный файл с переменными и базовыми компонентами:

```css
/* ============================================
   HOUSLER DESIGN SYSTEM
   Version: 1.0
   Theme: Black & White Premium
   ============================================ */

:root {
    /* === COLORS === */

    /* Base */
    --black: #000000;
    --white: #FFFFFF;

    /* Grays */
    --gray-900: #1A1A1A;
    --gray-800: #333333;
    --gray-700: #4A4A4A;
    --gray-600: #6B7280;
    --gray-500: #9CA3AF;
    --gray-400: #D1D5DB;
    --gray-300: #E5E7EB;
    --gray-200: #F3F4F6;
    --gray-100: #F9FAFB;

    /* Functional Colors */
    --success: #4ADE80;
    --error: #EF4444;
    --warning: #F59E0B;
    --info: #3B82F6;

    /* === TYPOGRAPHY === */

    /* Font Families */
    --font-primary: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    --font-mono: "SF Mono", Monaco, "Cascadia Code", "Courier New", monospace;

    /* Font Sizes */
    --text-xs: 12px;
    --text-sm: 14px;
    --text-base: 16px;
    --text-lg: 18px;
    --text-xl: 20px;
    --text-2xl: 24px;
    --text-3xl: 32px;
    --text-4xl: 40px;

    /* Line Heights */
    --leading-tight: 1.25;
    --leading-normal: 1.5;
    --leading-relaxed: 1.75;

    /* === SPACING === */

    --spacing-xs: 4px;
    --spacing-sm: 8px;
    --spacing-md: 16px;
    --spacing-lg: 24px;
    --spacing-xl: 32px;
    --spacing-2xl: 48px;
    --spacing-3xl: 64px;

    /* === EFFECTS === */

    /* Shadows */
    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
    --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);
    --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.1);
    --shadow-xl: 0 20px 25px rgba(0, 0, 0, 0.15);

    /* Transitions */
    --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
    --transition-base: 300ms cubic-bezier(0.4, 0, 0.2, 1);
    --transition-slow: 500ms cubic-bezier(0.4, 0, 0.2, 1);

    /* === BORDERS === */

    --border-width: 1px;
    --border-width-thick: 2px;
    --border-color: var(--gray-300);
    --border-radius: 0; /* Sharp edges */
    --border-radius-sm: 4px;
    --border-radius-md: 8px;
    --border-radius-lg: 12px;
}

/* === COMPONENT CLASSES === */

/* Buttons */
.btn-primary {
    background: var(--black);
    color: var(--white);
    border: 2px solid var(--black);
    padding: 12px 24px;
    font-size: var(--text-base);
    font-weight: 600;
    cursor: pointer;
    transition: all var(--transition-base);
}

.btn-primary:hover {
    background: var(--white);
    color: var(--black);
}

.btn-secondary {
    background: var(--white);
    color: var(--black);
    border: 2px solid var(--black);
    padding: 12px 24px;
    font-size: var(--text-base);
    font-weight: 600;
    cursor: pointer;
    transition: all var(--transition-base);
}

.btn-secondary:hover {
    background: var(--black);
    color: var(--white);
}

/* Cards */
.card {
    background: var(--white);
    border: 1px solid var(--border-color);
    padding: var(--spacing-lg);
}

.card-dark {
    background: var(--black);
    color: var(--white);
    border: 1px solid var(--gray-700);
}

/* Alerts (см. Задача 6) */
/* Toasts (см. Задача 1) */
/* Loader (см. Задача 2) */
```

### 2. Структура файлов CSS

Рекомендуемая структура:

```
static/css/
├── design-system.css      # Центральная система дизайна
├── components/
│   ├── toast.css         # Toast уведомления
│   ├── alert.css         # Alert компоненты
│   ├── loader.css        # Loaders
│   ├── header.css        # Headers
│   ├── buttons.css       # Buttons
│   └── cards.css         # Cards
├── landing.css           # Лендинг (импортирует design-system)
├── wizard.css            # Калькулятор (импортирует design-system)
└── unified-dashboard.css # Dashboard (импортирует design-system)
```

**Порядок импорта в HTML:**

```html
<!-- 1. Design System -->
<link rel="stylesheet" href="/static/css/design-system.css">

<!-- 2. Компоненты -->
<link rel="stylesheet" href="/static/css/components/toast.css">
<link rel="stylesheet" href="/static/css/components/alert.css">
<link rel="stylesheet" href="/static/css/components/loader.css">
<link rel="stylesheet" href="/static/css/components/header.css">

<!-- 3. Страничные стили -->
<link rel="stylesheet" href="/static/css/wizard.css">
```

### 3. JavaScript компоненты

Создать модульную структуру:

```
static/js/
├── utils/
│   ├── toast.js          # Toast система
│   ├── loader.js         # Loader система
│   ├── alerts.js         # Alert система
│   └── error-messages.js # Словарь ошибок
├── wizard.js             # Основной скрипт калькулятора
└── landing.js            # Скрипт лендинга
```

**Пример модульной структуры:**

`static/js/utils/toast.js`:
```javascript
// Toast Notification System
export const Toast = {
    show(message, type = 'info', duration = 5000) {
        const toast = document.getElementById('toast');
        const toastBody = document.getElementById('toast-body');

        if (!toast || !toastBody) {
            console.error('Toast elements not found');
            return;
        }

        toastBody.textContent = message;

        // Удаляем старые классы
        toast.classList.remove('toast-success', 'toast-error', 'toast-warning', 'toast-info');

        // Добавляем новый класс
        toast.classList.add(`toast-${type}`);

        // Показываем Toast
        const bsToast = new bootstrap.Toast(toast, { delay: duration });
        bsToast.show();
    },

    success(message, duration) {
        this.show(message, 'success', duration);
    },

    error(message, duration) {
        this.show(message, 'error', duration);
    },

    warning(message, duration) {
        this.show(message, 'warning', duration);
    },

    info(message, duration) {
        this.show(message, 'info', duration);
    }
};
```

### 4. Система валидации и ошибок

Создать единый обработчик ошибок:

`static/js/utils/error-handler.js`:
```javascript
import { Toast } from './toast.js';
import { ERROR_MESSAGES } from './error-messages.js';

export class ErrorHandler {
    static handle(error, context = '') {
        console.error(`[${context}]`, error);

        // Определяем тип ошибки
        let errorKey = 'unknown_error';

        if (error.message.includes('network')) {
            errorKey = 'network_error';
        } else if (error.message.includes('timeout')) {
            errorKey = 'timeout';
        } else if (error.status === 404) {
            errorKey = 'no_data';
        } else if (error.status >= 500) {
            errorKey = 'server_error';
        }

        // Получаем человекопонятное сообщение
        const errorData = ERROR_MESSAGES[errorKey] || {
            title: 'Произошла ошибка',
            message: error.message || 'Попробуйте повторить действие'
        };

        // Показываем Toast
        Toast.error(`${errorData.title}: ${errorData.message}`);
    }

    static handleValidation(field, value) {
        // Валидация полей
        if (field === 'url' && !value.includes('cian.ru')) {
            Toast.warning(ERROR_MESSAGES.invalid_url.message);
            return false;
        }

        if (field === 'price' && (isNaN(value) || value <= 0)) {
            Toast.warning(ERROR_MESSAGES.invalid_price.message);
            return false;
        }

        return true;
    }
}
```

### 5. Документация компонентов

Создать файл с примерами использования:

`docs/COMPONENTS.md`:
```markdown
# Документация UI компонентов

## Toast Notifications

### Использование:
```javascript
import { Toast } from './utils/toast.js';

// Успех
Toast.success('Объект успешно загружен');

// Ошибка
Toast.error('Не удалось подключиться к серверу');

// Предупреждение
Toast.warning('Заполните все обязательные поля');

// Информация
Toast.info('Идет загрузка данных');
```

### Параметры:
- `message` (string) - Текст сообщения
- `type` (string) - Тип: success, error, warning, info
- `duration` (number) - Длительность в мс (по умолчанию 5000)

## Loader

### Использование:
```javascript
import { pixelLoader } from './utils/loader.js';

// Показать
pixelLoader.show('parsing');  // parsing, searching, analyzing

// Скрыть
pixelLoader.hide();
```

## Error Handler

### Использование:
```javascript
import { ErrorHandler } from './utils/error-handler.js';

try {
    // Ваш код
} catch (error) {
    ErrorHandler.handle(error, 'ParseObject');
}

// Валидация
if (!ErrorHandler.handleValidation('url', inputValue)) {
    return;
}
```
```

---

## 📅 План внедрения

### Фаза 1: Подготовка (1 день)

**Задачи:**
1. ✅ Создать файл design-system.css
2. ✅ Создать файл error-messages.js
3. ✅ Создать документацию COMPONENTS.md
4. ✅ Настроить структуру папок

**Результат:**
- Готова базовая инфраструктура

---

### Фаза 2: Критические компоненты (2-3 дня)

**Приоритет: 🔴 ВЫСОКИЙ**

#### День 1: Toast и Alert системы
- [ ] Задача 1: Унификация Toast уведомлений
  - Обновить CSS (30 мин)
  - Обновить JavaScript (30 мин)
  - Тестирование (30 мин)

- [ ] Задача 6: Унификация Alert компонентов
  - Создать новые стили (1 час)
  - Обновить все места использования (1 час)
  - Создать error-messages.js (1 час)
  - Тестирование (30 мин)

**Чеклист тестирования:**
- [ ] Toast появляется с черным фоном
- [ ] Цветная левая граница корректно отображается
- [ ] Кнопка закрытия белая (видна на черном фоне)
- [ ] Все 4 типа (success, error, warning, info) работают
- [ ] Адаптивность на мобильных устройствах

#### День 2: Loader система
- [ ] Задача 2: Улучшение Pixel Loader
  - Обновить тексты сообщений (1 час)
  - Удалить emoji (30 мин)
  - Ускорить Advice Ticker (15 мин)
  - Тестирование всех типов (1 час)

**Чеклист тестирования:**
- [ ] Все emoji удалены
- [ ] Тексты не обрываются
- [ ] Максимум 30 символов на сообщение
- [ ] Ticker движется быстрее (60s вместо 180s)
- [ ] Все 3 типа (parsing, searching, analyzing) работают

#### День 3: Pricing секция
- [ ] Задача 5: Улучшение секции "Стоимость услуг"
  - Обновить HTML разметку (1.5 часа)
  - Добавить CSS стили (1 час)
  - Создать explanation секцию (1 час)
  - Тестирование адаптивности (1 час)

**Чеклист тестирования:**
- [ ] Понятно что цифры = стоимость объекта
- [ ] Разница между опциями A и B объяснена
- [ ] Правило 2% четко описано
- [ ] Explanation секция отображается корректно
- [ ] Адаптивность на мобильных

---

### Фаза 3: Улучшения навигации (1 день)

**Приоритет: 🟡 СРЕДНИЙ**

#### День 4: Header
- [ ] Задача 3: Добавление хэдера на страницу калькулятора
  - Создать HTML разметку (30 мин)
  - Создать CSS стили (1 час)
  - Убедиться что нет дублирования (Задача 4) (30 мин)
  - Тестирование навигации (30 мин)

**Чеклист тестирования:**
- [ ] Хэдер отображается на всех экранах калькулятора
- [ ] Ссылка "Назад на главную" работает
- [ ] Нет дублирования названия "Housler"
- [ ] Адаптивность на мобильных
- [ ] Единообразие с лендингом

---

### Фаза 4: Финализация (1 день)

**Приоритет: 🟢 НИЗКИЙ**

#### День 5: Полировка и тестирование
- [ ] Проверить все компоненты на всех страницах
- [ ] Протестировать на разных разрешениях
- [ ] Проверить accessibility (a11y)
- [ ] Обновить документацию
- [ ] Code review

**Чеклист финального тестирования:**
- [ ] Все Toast работают корректно
- [ ] Все Alert работают корректно
- [ ] Loader работает стабильно
- [ ] Pricing секция понятна
- [ ] Header отображается везде
- [ ] Нет визуальных багов
- [ ] Адаптивность на всех устройствах
- [ ] Темная тема (black & white) везде применена

---

## ✅ Контроль качества

### Чеклист перед запуском в продакшн

#### Визуальная консистентность
- [ ] Все компоненты используют Black & White палитру
- [ ] Цветные акценты только для функциональных целей (границы alerts)
- [ ] Единый стиль типографики
- [ ] Единообразные отступы и padding

#### Функциональность
- [ ] Все Toast уведомления работают
- [ ] Loader отображается корректно
- [ ] Сообщения об ошибках понятны пользователю
- [ ] Навигация работает
- [ ] Все ссылки кликабельны

#### Производительность
- [ ] CSS файлы минимизированы
- [ ] JavaScript не блокирует UI
- [ ] Анимации плавные (60 FPS)
- [ ] Нет лишних перерисовок (repaints)

#### Адаптивность
- [ ] Desktop (1920px+)
- [ ] Laptop (1440px)
- [ ] Tablet (768px)
- [ ] Mobile (375px)

#### Accessibility (a11y)
- [ ] Цветовой контраст соответствует WCAG AA (4.5:1)
- [ ] Кнопки закрытия доступны с клавиатуры
- [ ] Все интерактивные элементы имеют focus states
- [ ] Alt тексты для иконок (где применимо)

#### Browser Support
- [ ] Chrome/Edge (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Mobile browsers (iOS Safari, Chrome Mobile)

---

## 📊 Метрики успеха

### KPI
1. **Визуальная консистентность:** 100% компонентов в едином стиле
2. **Понятность ошибок:** Все технические ошибки переведены на понятный язык
3. **Скорость восприятия:** Pricing секция понятна за 30 секунд
4. **Производительность:** Loader не тормозит UI

### Обратная связь
- Собрать фидбек от 5+ пользователей после внедрения
- Проверить метрики Google Analytics:
  - Время на странице Pricing
  - Bounce rate на калькуляторе
  - Конверсия после изменений

---

## 🔄 Поддержка в будущем

### Правила для новых компонентов

1. **Всегда используйте design-system.css**
   - Не создавайте новые цвета
   - Используйте CSS переменные
   - Следуйте spacing системе

2. **Следуйте паттернам**
   - Для уведомлений → Toast система
   - Для ошибок → ErrorHandler
   - Для загрузок → pixelLoader

3. **Документируйте компоненты**
   - Добавляйте примеры в COMPONENTS.md
   - Комментируйте сложную логику
   - Обновляйте чейнджлог

4. **Тестируйте на всех устройствах**
   - Desktop, Tablet, Mobile
   - Все основные браузеры
   - Темная/светлая темы (если применимо)

### Процесс code review

Перед мержем проверить:
- [ ] Соответствие дизайн-системе
- [ ] Нет дублирования кода
- [ ] Адаптивность
- [ ] Accessibility
- [ ] Документация обновлена

---

## 📚 Дополнительные ресурсы

### Документация
- `docs/COMPONENTS.md` - Документация компонентов
- `docs/DESIGN_SYSTEM.md` - Описание дизайн-системы
- `static/css/design-system.css` - CSS переменные

### Инструменты
- [Wave Accessibility Tool](https://wave.webaim.org/) - Проверка a11y
- [Contrast Checker](https://webaim.org/resources/contrastchecker/) - Проверка контраста
- Chrome DevTools - Responsive testing

---

## ✉️ Контакты

Вопросы по UI доработкам:
- Разработчик: [Имя]
- Email: [Email]
- Slack: [Channel]

---

**Версия:** 1.0
**Последнее обновление:** 08.11.2025
**Статус:** ✅ Готово к внедрению
