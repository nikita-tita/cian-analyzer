#!/bin/bash
# Скрипт для архивирования устаревших документов
# Запуск: ./archive_old_docs.sh

set -e

ARCHIVE_DIR="_archive"
mkdir -p "$ARCHIVE_DIR"

# Файлы, которые НЕ нужно архивировать (актуальные)
KEEP_FILES=(
    "README.md"
    "DEPLOY.md"
    "CLAUDE.md"
    "HOUSLER_DEPLOY.md"
    ".github/README.md"
    ".github/workflows/README.md"
)

# Функция для проверки, нужно ли сохранить файл
should_keep() {
    local file="$1"
    for keep in "${KEEP_FILES[@]}"; do
        if [[ "$file" == "$keep" ]]; then
            return 0
        fi
    done
    return 1
}

echo "Архивирование устаревших .md файлов..."
echo "Папка архива: $ARCHIVE_DIR"
echo ""

count=0
for file in *.md; do
    if [[ -f "$file" ]] && ! should_keep "$file"; then
        echo "Перемещение: $file"
        mv "$file" "$ARCHIVE_DIR/"
        ((count++))
    fi
done

echo ""
echo "Перемещено файлов: $count"
echo "Актуальные файлы остались на месте:"
for keep in "${KEEP_FILES[@]}"; do
    if [[ -f "$keep" ]]; then
        echo "  - $keep"
    fi
done

echo ""
echo "Готово!"
