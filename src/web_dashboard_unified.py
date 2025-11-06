"""
Унифицированный веб-дашборд для анализа недвижимости
Объединяет все лучшие фичи из предыдущих версий + новые улучшения

Новые возможности:
- Recommendation Engine (персонализированные рекомендации)
- Водопадная диаграмма (формирование цены)
- Интерактивные tooltips
- Улучшенная визуализация
"""

from flask import Flask, render_template, request, jsonify
from typing import Dict, List
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent))

from analytics.analyzer import RealEstateAnalyzer
from analytics.recommendations import RecommendationEngine
from models.property import (
    TargetProperty,
    ComparableProperty,
    AnalysisRequest,
    AnalysisResult
)

app = Flask(__name__, template_folder='templates')


@app.route('/')
def index():
    """Главная страница unified dashboard"""
    return render_template('dashboard_unified.html')


@app.route('/api/v2/analyze', methods=['POST'])
def analyze_v2():
    """
    Полный анализ объекта с рекомендациями (API v2)

    POST data:
        {
            "target_property": {
                "price": 25000000,
                "total_area": 120,
                "living_area": 80,
                "rooms": 3,
                "has_design": true,
                ...
            },
            "comparables": [
                {"price": 24000000, "total_area": 115, ...},
                ...
            ],
            "filter_outliers": true,
            "use_median": true
        }

    Returns:
        {
            "success": true,
            "analysis_result": {...},
            "recommendations": [...],
            "recommendations_summary": {...},
            "waterfall_chart_data": {...},
            "version": "v2.0"
        }
    """
    try:
        data = request.json

        # Валидация через Pydantic
        target_data = data.get('target_property', {})
        comparables_data = data.get('comparables', [])

        target = TargetProperty(**target_data)
        comparables = [ComparableProperty(**c) for c in comparables_data]

        analysis_request = AnalysisRequest(
            target_property=target,
            comparables=comparables,
            filter_outliers=data.get('filter_outliers', True),
            use_median=data.get('use_median', True)
        )

        # Выполняем анализ
        analyzer = RealEstateAnalyzer()
        analysis_result = analyzer.analyze(analysis_request)

        # Конвертируем в dict для JSON
        result_dict = {
            'timestamp': analysis_result.timestamp.isoformat(),
            'target_property': target.dict(),
            'comparables': [c.dict() for c in analysis_result.comparables],
            'market_statistics': analysis_result.market_statistics,
            'fair_price_analysis': analysis_result.fair_price_analysis,
            'price_scenarios': [s.dict() for s in analysis_result.price_scenarios],
            'strengths_weaknesses': analysis_result.strengths_weaknesses,
            'comparison_chart_data': analysis_result.comparison_chart_data,
            'box_plot_data': analysis_result.box_plot_data
        }

        # Генерируем рекомендации
        rec_engine = RecommendationEngine(result_dict)
        recommendations = rec_engine.generate()
        recommendations_summary = rec_engine.get_summary()

        # Генерируем данные для водопадной диаграммы
        waterfall_data = _generate_waterfall_chart_data(
            analysis_result.fair_price_analysis
        )

        return jsonify({
            'success': True,
            'analysis_result': result_dict,
            'recommendations': [r.to_dict() for r in recommendations],
            'recommendations_summary': recommendations_summary,
            'waterfall_chart_data': waterfall_data,
            'metrics': analyzer.get_metrics(),
            'version': 'v2.0'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }), 400


@app.route('/api/v2/recommendations', methods=['POST'])
def get_recommendations():
    """
    Получить только рекомендации для готового анализа

    POST data:
        {
            "analysis_result": {...}
        }

    Returns:
        {
            "success": true,
            "recommendations": [...],
            "summary": {...}
        }
    """
    try:
        data = request.json
        analysis_result = data.get('analysis_result', {})

        rec_engine = RecommendationEngine(analysis_result)
        recommendations = rec_engine.generate()
        summary = rec_engine.get_summary()

        return jsonify({
            'success': True,
            'recommendations': [r.to_dict() for r in recommendations],
            'summary': summary
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


def _generate_waterfall_chart_data(fair_price_analysis: Dict) -> Dict:
    """
    Генерация данных для водопадной диаграммы

    Показывает пошаговое формирование справедливой цены

    Args:
        fair_price_analysis: Результат расчета справедливой цены

    Returns:
        Данные для Chart.js waterfall chart
    """
    base_price = fair_price_analysis.get('base_price_per_sqm', 0)
    adjustments = fair_price_analysis.get('adjustments', {})
    final_price = fair_price_analysis.get('fair_price_per_sqm', 0)

    # Формируем шаги водопада
    steps = [
        {
            'label': 'Базовая цена (медиана)',
            'value': base_price,
            'type': 'base',
            'description': 'Медиана цен по рынку для квартир с аналогичными характеристиками',
            'color': '#3498db'
        }
    ]

    # Положительные корректировки
    positive_adjustments = [
        ('design', 'Дизайнерская отделка'),
        ('panoramic_views', 'Панорамные виды'),
        ('metro_proximity', 'Близко к метро'),
        ('premium_location', 'Премиум локация'),
        ('house_type', 'Тип дома'),
        ('parking', 'Парковка'),
        ('ceiling_height', 'Высокие потолки'),
        ('security', 'Охрана 24/7'),
        ('elevator', 'Лифт'),
        ('large_size', 'Большая площадь')
    ]

    # Негативные корректировки
    negative_adjustments = [
        ('low_living_area', 'Низкая жилая площадь'),
        ('building_age', 'Возраст дома'),
        ('high_price', 'Низкая ликвидность'),
        ('renders_only', 'Только рендеры')
    ]

    # Добавляем положительные
    for key, label in positive_adjustments:
        if key in adjustments:
            adj = adjustments[key]
            if isinstance(adj, dict):
                value = adj.get('value', 1.0)
                description = adj.get('description', label)
            else:
                value = adj
                description = label

            change = base_price * (value - 1)
            if change > 0:
                steps.append({
                    'label': label,
                    'value': change,
                    'type': 'positive',
                    'description': description,
                    'percentage': f'+{(value - 1) * 100:.1f}%',
                    'color': '#2ecc71'
                })

    # Добавляем негативные
    for key, label in negative_adjustments:
        if key in adjustments:
            adj = adjustments[key]
            if isinstance(adj, dict):
                value = adj.get('value', 1.0)
                description = adj.get('description', label)
            else:
                value = adj
                description = label

            change = base_price * (value - 1)
            if change < 0:
                steps.append({
                    'label': label,
                    'value': change,
                    'type': 'negative',
                    'description': description,
                    'percentage': f'{(value - 1) * 100:.1f}%',
                    'color': '#e74c3c'
                })

    # Итоговая цена
    steps.append({
        'label': 'ИТОГОВАЯ ЦЕНА',
        'value': final_price,
        'type': 'total',
        'description': 'Справедливая цена за м² с учетом всех факторов',
        'color': '#9b59b6'
    })

    return {
        'steps': steps,
        'base_price': base_price,
        'final_price': final_price,
        'total_change': final_price - base_price,
        'total_change_percent': ((final_price - base_price) / base_price * 100) if base_price > 0 else 0
    }


@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'version': 'v2.0',
        'features': [
            'recommendations',
            'waterfall_chart',
            'interactive_tooltips',
            'pydantic_validation'
        ]
    })


if __name__ == '__main__':
    print("""
    ╔═══════════════════════════════════════════════════════╗
    ║  Unified Real Estate Analysis Dashboard v2.0        ║
    ╠═══════════════════════════════════════════════════════╣
    ║  Новые возможности:                                  ║
    ║  ✓ Recommendation Engine                             ║
    ║  ✓ Водопадная диаграмма                             ║
    ║  ✓ Интерактивные tooltips                           ║
    ║  ✓ Улучшенная визуализация                          ║
    ╠═══════════════════════════════════════════════════════╣
    ║  Запущено на: http://localhost:5001                  ║
    ╚═══════════════════════════════════════════════════════╝
    """)
    app.run(debug=True, host='0.0.0.0', port=5001)
