#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Исправление Wizard: убрать дублирование + добавить breadcrumbs
# ═══════════════════════════════════════════════════════════════

set -e

SERVER="91.229.8.221"
SSH_KEY="$HOME/.ssh/id_housler"
APP_DIR="/var/www/housler"

echo "🔧 Исправление Wizard..."
echo "══════════════════════════════════════════════════════════"

ssh -i "$SSH_KEY" root@$SERVER << 'ENDSSH'
cd /var/www/housler

# Бэкап файлов
echo "📦 Создание бэкапов..."
cp templates/wizard.html templates/wizard.html.backup
cp static/js/wizard.js static/js/wizard.js.backup
cp static/css/wizard.css static/css/wizard.css.backup

echo "✅ Бэкапы созданы"

# ═══════════════════════════════════════════════════════════════
# 1. Убрать floating buttons из HTML
# ═══════════════════════════════════════════════════════════════

echo "🗑️  Удаление floating buttons из HTML..."

# Удаляем секцию floating buttons (строки 448-458)
sed -i '448,458d' templates/wizard.html

echo "✅ Floating buttons удалены из HTML"

# ═══════════════════════════════════════════════════════════════
# 2. Убрать floating buttons из JS
# ═══════════════════════════════════════════════════════════════

echo "🗑️  Удаление floating buttons из JS..."

# Удаляем вызов floatingButtons.updateButtons()
sed -i '/floatingButtons.updateButtons()/d' static/js/wizard.js

# Удаляем объявление floatingButtons объекта (строки 795-852)
sed -i '/^const floatingButtons = {/,/^};$/d' static/js/wizard.js

# Удаляем window.floatingButtons
sed -i '/window.floatingButtons/d' static/js/wizard.js

echo "✅ Floating buttons удалены из JS"

# ═══════════════════════════════════════════════════════════════
# 3. Добавить breadcrumbs в HTML
# ═══════════════════════════════════════════════════════════════

echo "🍞 Добавление breadcrumbs..."

# Добавляем breadcrumbs после открытия wizard-container
# Найдем строку с <div class="wizard-container"> и добавим после неё

cat > /tmp/breadcrumbs.html << 'BREADCRUMBS'

        <!-- Breadcrumbs -->
        <nav aria-label="breadcrumb" class="mb-4">
            <ol class="breadcrumb" id="wizard-breadcrumb">
                <li class="breadcrumb-item active" data-step="1">
                    <a href="#step-1">Объект</a>
                </li>
                <li class="breadcrumb-item" data-step="2">
                    <a href="#step-2">Аналоги</a>
                </li>
                <li class="breadcrumb-item" data-step="3">
                    <a href="#step-3">Анализ</a>
                </li>
            </ol>
        </nav>
BREADCRUMBS

# Вставляем breadcrumbs после <div class="wizard-container">
sed -i '/<div class="wizard-container">/r /tmp/breadcrumbs.html' templates/wizard.html

echo "✅ Breadcrumbs добавлены"

# ═══════════════════════════════════════════════════════════════
# 4. Добавить CSS для breadcrumbs
# ═══════════════════════════════════════════════════════════════

echo "🎨 Добавление CSS для breadcrumbs..."

cat >> static/css/wizard.css << 'BREADCRUMB_CSS'

/* ══════════════════════════════════════════════════════════════
   Breadcrumbs
   ══════════════════════════════════════════════════════════════ */

.breadcrumb {
    background: transparent;
    padding: 1rem 0;
    margin-bottom: 2rem;
}

.breadcrumb-item {
    font-size: 14px;
    font-weight: 500;
}

.breadcrumb-item a {
    color: var(--color-text-muted);
    text-decoration: none;
    transition: color 0.2s;
}

.breadcrumb-item a:hover {
    color: var(--color-accent);
}

.breadcrumb-item.active a {
    color: var(--color-accent);
    font-weight: 600;
}

.breadcrumb-item + .breadcrumb-item::before {
    content: "→";
    color: var(--color-border);
}

@media (max-width: 768px) {
    .breadcrumb {
        padding: 0.5rem 0;
        margin-bottom: 1rem;
    }

    .breadcrumb-item {
        font-size: 12px;
    }
}
BREADCRUMB_CSS

echo "✅ CSS для breadcrumbs добавлен"

# ═══════════════════════════════════════════════════════════════
# 5. Добавить URL хэши и breadcrumb логику в JS
# ═══════════════════════════════════════════════════════════════

echo "🔗 Добавление URL хэшей и breadcrumb логики..."

cat >> static/js/wizard.js << 'HASH_LOGIC'

// ══════════════════════════════════════════════════════════════
// URL Hash Navigation & Breadcrumbs
// ══════════════════════════════════════════════════════════════

const hashNavigation = {
    init() {
        // Обработка изменения хэша
        window.addEventListener('hashchange', () => {
            this.handleHashChange();
        });

        // Обработка начальной загрузки
        if (window.location.hash) {
            this.handleHashChange();
        }

        // Клики по breadcrumb
        document.querySelectorAll('.breadcrumb-item a').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const step = parseInt(link.closest('.breadcrumb-item').dataset.step);

                // Проверяем что шаг доступен
                if (this.isStepAccessible(step)) {
                    this.goToStep(step);
                } else {
                    showToast('Этот шаг пока недоступен', 'warning');
                }
            });
        });
    },

    handleHashChange() {
        const hash = window.location.hash;
        const match = hash.match(/#step-(\d+)/);

        if (match) {
            const step = parseInt(match[1]);
            if (this.isStepAccessible(step)) {
                this.goToStep(step);
            }
        }
    },

    isStepAccessible(step) {
        // Шаг 1 всегда доступен
        if (step === 1) return true;

        // Шаг 2 доступен если есть sessionId
        if (step === 2) return !!window.sessionId;

        // Шаг 3 доступен если есть sessionId и аналоги
        if (step === 3) {
            return !!window.sessionId && window.comparablesCount > 0;
        }

        return false;
    },

    goToStep(step) {
        // Обновляем URL
        window.location.hash = `step-${step}`;

        // Обновляем wizard
        if (window.wizard) {
            window.wizard.showScreen(step);
        }

        // Обновляем breadcrumbs
        this.updateBreadcrumbs(step);
    },

    updateBreadcrumbs(currentStep) {
        document.querySelectorAll('.breadcrumb-item').forEach((item) => {
            const step = parseInt(item.dataset.step);

            if (step === currentStep) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }

            // Делаем недоступные шаги визуально отличными
            if (!this.isStepAccessible(step)) {
                item.style.opacity = '0.5';
                item.style.pointerEvents = 'none';
            } else {
                item.style.opacity = '1';
                item.style.pointerEvents = 'auto';
            }
        });
    }
};

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', () => {
    hashNavigation.init();
});

window.hashNavigation = hashNavigation;
HASH_LOGIC

echo "✅ URL хэши и breadcrumbs логика добавлены"

# ═══════════════════════════════════════════════════════════════
# 6. Обновить wizard.showScreen для работы с хэшами
# ═══════════════════════════════════════════════════════════════

echo "🔄 Обновление wizard.showScreen..."

# Добавим обновление хэша и breadcrumbs в showScreen функцию
sed -i '/showScreen(screenNum) {/a\        // Обновляем URL hash\n        window.location.hash = `step-${screenNum}`;\n        // Обновляем breadcrumbs\n        if (window.hashNavigation) {\n            window.hashNavigation.updateBreadcrumbs(screenNum);\n        }' static/js/wizard.js

echo "✅ wizard.showScreen обновлён"

echo ""
echo "══════════════════════════════════════════════════════════"
echo "✅ ИСПРАВЛЕНИЯ ПРИМЕНЕНЫ!"
echo "══════════════════════════════════════════════════════════"
echo ""
echo "Изменения:"
echo "  ✅ Floating buttons удалены"
echo "  ✅ Breadcrumbs добавлены"
echo "  ✅ URL хэши работают (#step-1, #step-2, #step-3)"
echo "  ✅ Можно делиться ссылками на конкретные шаги"
echo ""

ENDSSH

echo ""
echo "🔄 Перезапуск сервиса..."
ssh -i "$SSH_KEY" root@$SERVER "systemctl restart housler"
sleep 3

echo ""
echo "✅ ГОТОВО!"
echo "Проверьте: https://housler.ru/calculator#step-1"
