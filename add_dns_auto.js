// ═══════════════════════════════════════════════════════════════
// АВТОМАТИЧЕСКОЕ ДОБАВЛЕНИЕ DNS ЗАПИСЕЙ ДЛЯ HOUSLER.RU
// ═══════════════════════════════════════════════════════════════
//
// ИНСТРУКЦИЯ:
// 1. Откройте https://www.reg.ru/user/account/#/card/104046009
// 2. Нажмите F12 (откроется консоль разработчика)
// 3. Вставьте весь этот код в консоль
// 4. Нажмите Enter
//
// ═══════════════════════════════════════════════════════════════

(async function addDNSRecords() {
    console.log('🚀 Начинаем добавление DNS записей для housler.ru...');

    const DOMAIN = 'housler.ru';
    const SERVER_IP = '91.229.8.221';
    const records = [
        { subdomain: '@', ip: SERVER_IP, description: 'основной домен' },
        { subdomain: 'www', ip: SERVER_IP, description: 'www поддомен' }
    ];

    // Функция для добавления записи через API Reg.ru
    async function addRecord(subdomain, ip) {
        try {
            console.log(`➕ Добавление записи: ${subdomain} -> ${ip}`);

            const response = await fetch('/api/zone/add_record', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    domain: DOMAIN,
                    subdomain: subdomain,
                    type: 'A',
                    content: ip,
                    ttl: 3600
                })
            });

            const result = await response.json();

            if (result.result === 'success' || response.ok) {
                console.log(`✅ Запись ${subdomain} добавлена!`);
                return true;
            } else {
                console.error(`❌ Ошибка при добавлении ${subdomain}:`, result);
                return false;
            }
        } catch (error) {
            console.error(`❌ Ошибка запроса для ${subdomain}:`, error);
            return false;
        }
    }

    // Добавляем записи
    for (const record of records) {
        console.log(`\n📝 Обработка записи: ${record.description}`);
        await addRecord(record.subdomain, record.ip);
        // Пауза между запросами
        await new Promise(resolve => setTimeout(resolve, 1000));
    }

    console.log('\n═══════════════════════════════════════════════════════════');
    console.log('✅ ГОТОВО!');
    console.log('═══════════════════════════════════════════════════════════');
    console.log('\n⏱️  DNS записи начнут работать через 5-30 минут');
    console.log('🌐 Сайт будет доступен: http://housler.ru');
    console.log('\n💡 Проверьте добавленные записи в разделе DNS');
})();

// АЛЬТЕРНАТИВНЫЙ СПОСОБ - если API не работает
// Раскомментируйте код ниже:

/*
console.log('📋 ПОШАГОВАЯ ИНСТРУКЦИЯ:');
console.log('1. Найдите кнопку "DNS-серверы и зона" и нажмите');
console.log('2. Нажмите "Добавить запись"');
console.log('3. Заполните:');
console.log('   Тип: A');
console.log('   Поддомен: @');
console.log('   IP: 91.229.8.221');
console.log('   TTL: 3600');
console.log('4. Сохраните');
console.log('5. Повторите для www');
*/
