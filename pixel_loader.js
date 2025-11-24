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
        ],

        // Клонирование (когда парсим много аналогов)
        cloning: [
            '🧬 Клонирование началось...',
            '👥 Один я... Два я... Три я...',
            '🔄 Размножаюсь как амёба...',
            '👯 Нас уже целая армия!',
            '🎭 Играю все роли сам...',
        ]
    },

    currentLoader: null,
    currentMessageIndex: 0,
    messageInterval: null,
    iconClass: 'agent',

    // Показать лоадер
    show(type = 'parsing') {
        // Создаем лоадер если его нет
        if (!document.getElementById('pixel-loader')) {
            this.create();
        }

        const loader = document.getElementById('pixel-loader');
        const textElement = document.getElementById('pixel-text');
        const iconElement = document.querySelector('.pixel-icon');

        // Устанавливаем тип лоадера
        loader.className = 'pixel-loader ' + type;
        this.currentLoader = type;
        this.currentMessageIndex = 0;

        // Устанавливаем иконку в зависимости от типа
        const icons = {
            parsing: 'agent',
            searching: 'house',
            analyzing: 'document',
            cloning: 'agent'
        };
        iconElement.className = 'pixel-icon ' + icons[type];

        // Показываем первое сообщение
        const messages = this.messages[type] || this.messages.parsing;
        textElement.textContent = messages[0] + ' ' + messages[0]; // Дублируем для бесшовной анимации

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

        // Сбрасываем прогресс
        this.resetProgress();
    },

    // Создать лоадер в DOM
    create() {
        const loaderHTML = `
            <div id="pixel-loader" class="pixel-loader" style="display: none;">
                <div class="pixel-loader-content">
                    <div class="pixel-loader-screen">
                        <!-- Бегущая строка с пиксельным текстом -->
                        <div class="pixel-marquee">
                            <div class="pixel-marquee-track" id="pixel-text">
                                🏃 Загрузка...
                            </div>
                        </div>

                        <!-- Пиксельный прогресс бар -->
                        <div class="pixel-progress-bar">
                            <div class="pixel-progress-fill"></div>
                        </div>

                        <!-- Пиксельная иконка -->
                        <div class="pixel-icon agent"></div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', loaderHTML);
    },

    // Ротация сообщений
    startMessageRotation(type) {
        const messages = this.messages[type] || this.messages.parsing;
        const textElement = document.getElementById('pixel-text');

        // Меняем сообщение каждые 3 секунды
        this.messageInterval = setInterval(() => {
            this.currentMessageIndex = (this.currentMessageIndex + 1) % messages.length;
            const message = messages[this.currentMessageIndex];

            // Дублируем текст для бесшовной бегущей строки
            textElement.textContent = message + ' ⚡ ' + message + ' ⚡ ';
        }, 3000);
    },

    // Показать конкретное сообщение
    showMessage(message, type = 'parsing') {
        if (!document.getElementById('pixel-loader')) {
            this.create();
        }

        const loader = document.getElementById('pixel-loader');
        const textElement = document.getElementById('pixel-text');

        loader.className = 'pixel-loader ' + type;
        textElement.textContent = message + ' ⚡ ' + message + ' ⚡ ';
        loader.style.display = 'flex';
    },

    // Обновить прогресс (0-100)
    updateProgress(percentage) {
        const progressFill = document.querySelector('.pixel-progress-fill');
        if (progressFill) {
            // Ограничиваем от 0 до 100
            const clampedPercentage = Math.max(0, Math.min(100, percentage));
            progressFill.style.width = clampedPercentage + '%';
        }
    },

    // Показать прогресс с сообщением
    showProgress(percentage, message = null, type = 'parsing') {
        this.show(type);
        this.updateProgress(percentage);

        if (message) {
            const textElement = document.getElementById('pixel-text');
            if (textElement) {
                textElement.textContent = message + ' ⚡ ' + message + ' ⚡ ';
            }
        }
    },

    // Сброс прогресса
    resetProgress() {
        const progressFill = document.querySelector('.pixel-progress-fill');
        if (progressFill) {
            progressFill.style.width = '0%';
        }
    }
};

// Экспортируем для использования
window.pixelLoader = pixelLoader;

// ══════════════════════════════════════════════════════════════
// Интеграция с существующим кодом wizard
// ══════════════════════════════════════════════════════════════

// Пример использования:

/*
// При парсинге URL
pixelLoader.show('parsing');
// ... парсинг ...
pixelLoader.hide();

// При поиске аналогов
pixelLoader.show('searching');
// ... поиск ...
pixelLoader.hide();

// При анализе
pixelLoader.show('analyzing');
// ... анализ ...
pixelLoader.hide();

// Для показа конкретного сообщения
pixelLoader.showMessage('🏃 Бегу за кофе...', 'parsing');

// С индикатором прогресса (новое!)
pixelLoader.showProgress(0, 'Начинаем поиск...', 'searching');
// ... поиск 1/3 ...
pixelLoader.updateProgress(33);
// ... поиск 2/3 ...
pixelLoader.updateProgress(66);
// ... поиск завершен ...
pixelLoader.updateProgress(100);
pixelLoader.hide();

// Короткий способ с прогрессом и сообщением
pixelLoader.showProgress(50, '🔍 Найдено 25 из 50 объектов...', 'searching');
*/
