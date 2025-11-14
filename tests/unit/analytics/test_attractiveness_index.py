"""
Unit tests for attractiveness_index.py - property attractiveness scoring (0-100)
"""

import pytest
from src.analytics.attractiveness_index import (
    calculate_attractiveness_index,
    _calculate_price_score,
    _calculate_presentation_score,
    _calculate_features_score,
    _get_attractiveness_category,
    _generate_summary,
)
from src.models.property import TargetProperty


class TestCalculatePriceScore:
    """Tests for _calculate_price_score() function"""

    def test_strongly_underpriced(self):
        """Test overpricing < -10%"""
        target = self._create_basic_target()
        result = _calculate_price_score(target, -15.0)

        assert result['score'] == 100
        assert result['details']['status'] == 'Сильно недооценен'
        assert result['details']['emoji'] == '💰💰💰'
        assert len(result['recommendations']) > 0
        assert 'повысить цену' in result['recommendations'][0].lower()

    def test_underpriced(self):
        """Test overpricing between -10% and -5%"""
        target = self._create_basic_target()
        result = _calculate_price_score(target, -7.0)

        assert result['score'] == 95
        assert result['details']['status'] == 'Недооценен'
        assert result['details']['emoji'] == '💰💰'

    def test_fair_price(self):
        """Test overpricing between -5% and 5%"""
        target = self._create_basic_target()
        result = _calculate_price_score(target, 2.0)

        assert result['score'] == 90
        assert result['details']['status'] == 'Справедливая цена'
        assert result['details']['emoji'] == '✅'
        assert 'адекватна' in result['recommendations'][0].lower()

    def test_slightly_overpriced(self):
        """Test overpricing between 5% and 10%"""
        target = self._create_basic_target()
        result = _calculate_price_score(target, 7.5)

        assert result['score'] == 70
        assert result['details']['status'] == 'Немного переоценен'
        assert result['details']['emoji'] == '⚠️'

    def test_moderately_overpriced(self):
        """Test overpricing between 10% and 15%"""
        target = self._create_basic_target()
        result = _calculate_price_score(target, 12.0)

        assert result['score'] == 50
        assert result['details']['status'] == 'Переоценен'
        assert result['details']['emoji'] == '⚠️⚠️'
        assert 'снизить' in result['recommendations'][0].lower()

    def test_strongly_overpriced(self):
        """Test overpricing between 15% and 20%"""
        target = self._create_basic_target()
        result = _calculate_price_score(target, 18.0)

        assert result['score'] == 30
        assert result['details']['status'] == 'Сильно переоценен'
        assert result['details']['emoji'] == '🔴'
        assert 'КРИТИЧНО' in result['recommendations'][0]

    def test_extremely_overpriced(self):
        """Test overpricing > 20%"""
        target = self._create_basic_target()
        result = _calculate_price_score(target, 25.0)

        assert result['score'] == 10
        assert result['details']['status'] == 'Экстремально переоценен'
        assert result['details']['emoji'] == '🔴🔴🔴'
        assert 'СРОЧНО' in result['recommendations'][0]

    def test_overpricing_percent_in_details(self):
        """Test that overpricing percent is included in details"""
        target = self._create_basic_target()
        result = _calculate_price_score(target, 12.3)

        assert result['details']['overpricing_percent'] == 12.3

    def _create_basic_target(self):
        """Helper to create basic target property"""
        return TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )


class TestCalculatePresentationScore:
    """Tests for _calculate_presentation_score() function"""

    def test_excellent_photos_count(self):
        """Test with >=15 photos"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            images=['img1.jpg'] * 20  # 20 photos
        )

        result = _calculate_presentation_score(target)

        assert 'photos' in result['details']
        assert '20 фото' in result['details']['photos']
        assert 'Отлично' in result['details']['photos']

    def test_good_photos_count(self):
        """Test with 10-14 photos"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            images=['img1.jpg'] * 12
        )

        result = _calculate_presentation_score(target)

        assert 'Хорошо' in result['details']['photos']
        assert len(result['recommendations']) > 0

    def test_satisfactory_photos_count(self):
        """Test with 5-9 photos"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            images=['img1.jpg'] * 7
        )

        result = _calculate_presentation_score(target)

        assert 'Удовлетворительно' in result['details']['photos']
        assert any('ВАЖНО' in rec for rec in result['recommendations'])

    def test_poor_photos_count(self):
        """Test with <5 photos"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            images=['img1.jpg'] * 3
        )

        result = _calculate_presentation_score(target)

        assert 'Плохо' in result['details']['photos']
        assert any('КРИТИЧНО' in rec for rec in result['recommendations'])

    def test_no_images(self):
        """Test with no images"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )

        result = _calculate_presentation_score(target)

        assert '0 фото' in result['details']['photos']

    def test_photo_type_real(self):
        """Test with real photos"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            photo_type='реальные'
        )

        result = _calculate_presentation_score(target)

        assert 'Реальные фото ✅' in result['details']['photo_type']

    def test_photo_type_real_plus_renders(self):
        """Test with real photos + renders"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            photo_type='реальные+рендеры'
        )

        result = _calculate_presentation_score(target)

        assert 'Реальные + рендеры' in result['details']['photo_type']

    def test_photo_type_renders_with_video(self):
        """Test with renders + video"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            photo_type='рендеры+видео'
        )

        result = _calculate_presentation_score(target)

        assert 'Рендеры + видео' in result['details']['photo_type']
        assert any('реальные фотографии' in rec.lower() for rec in result['recommendations'])

    def test_photo_type_renders_only(self):
        """Test with renders only"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            photo_type='только_рендеры'
        )

        result = _calculate_presentation_score(target)

        assert 'Только рендеры ⚠️' in result['details']['photo_type']
        assert any('ВАЖНО' in rec for rec in result['recommendations'])

    def test_detailed_description(self):
        """Test with detailed description >=500 chars"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            description='A' * 600  # Long description
        )

        result = _calculate_presentation_score(target)

        assert 'Подробное описание ✅' in result['details']['description']

    def test_good_description(self):
        """Test with good description 300-499 chars"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            description='A' * 350
        )

        result = _calculate_presentation_score(target)

        assert 'Хорошее описание' in result['details']['description']

    def test_brief_description(self):
        """Test with brief description 200-299 chars"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            description='A' * 250
        )

        result = _calculate_presentation_score(target)

        assert 'Краткое описание' in result['details']['description']
        assert any('Расширьте' in rec for rec in result['recommendations'])

    def test_very_brief_description(self):
        """Test with very brief description <200 chars"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            description='Short'
        )

        result = _calculate_presentation_score(target)

        assert 'Очень краткое' in result['details']['description']

    def test_object_status_ready(self):
        """Test with object status 'готов'"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            object_status='готов'
        )

        result = _calculate_presentation_score(target)

        assert 'Готов к заселению ✅' in result['details']['object_status']

    def test_object_status_finishing(self):
        """Test with object status 'отделка'"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            object_status='отделка'
        )

        result = _calculate_presentation_score(target)

        assert 'Идет отделка' in result['details']['object_status']

    def test_object_status_construction(self):
        """Test with object status 'строительство'"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            object_status='строительство'
        )

        result = _calculate_presentation_score(target)

        assert 'В строительстве ⚠️' in result['details']['object_status']

    def test_score_capped_at_100(self):
        """Test that presentation score never exceeds 100"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            images=['img.jpg'] * 20,
            photo_type='реальные',
            description='A' * 600,
            object_status='готов'
        )

        result = _calculate_presentation_score(target)

        assert result['score'] <= 100


class TestCalculateFeaturesScore:
    """Tests for _calculate_features_score() function"""

    def test_repair_level_designer(self):
        """Test with designer repair level"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            repair_level='дизайнерская'
        )

        result = _calculate_features_score(target, {})

        assert 'Дизайнерская' in result['details']['repair_level']
        # Designer repair = 30 pts, should not trigger recommendation
        assert not any('ремонт' in rec.lower() for rec in result['recommendations'])

    def test_repair_level_economy(self):
        """Test with economy repair level"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            repair_level='эконом'
        )

        result = _calculate_features_score(target, {})

        assert 'Эконом' in result['details']['repair_level']
        # Economy repair < 20 pts, should trigger recommendation
        assert any('ремонт' in rec.lower() for rec in result['recommendations'])

    def test_view_premium(self):
        """Test with premium view"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            view_type='премиум'
        )

        result = _calculate_features_score(target, {})

        assert 'Премиум' in result['details']['view_type']

    def test_view_water(self):
        """Test with water view"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            view_type='вода'
        )

        result = _calculate_features_score(target, {})

        assert 'Вода' in result['details']['view_type']

    def test_parking_garage(self):
        """Test with garage parking"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            parking_type='гараж'
        )

        result = _calculate_features_score(target, {})

        assert 'Гараж' in result['details']['parking']

    def test_parking_none_large_apartment(self):
        """Test no parking for large apartment >80m²"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=15_000_000,
            total_area=100,  # > 80m²
            rooms=3,
            floor=5,
            total_floors=10,
            parking_type='нет'
        )

        result = _calculate_features_score(target, {})

        assert 'Нет' in result['details']['parking']
        assert any('Парковка важна' in rec for rec in result['recommendations'])

    def test_parking_none_small_apartment(self):
        """Test no parking for small apartment <=80m²"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=50,  # <= 80m²
            rooms=2,
            floor=5,
            total_floors=10,
            parking_type='нет'
        )

        result = _calculate_features_score(target, {})

        # Should not recommend parking for small apartments
        assert not any('Парковка важна' in rec for rec in result['recommendations'])

    def test_ceiling_height_very_high(self):
        """Test with very high ceilings >=3.2m"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            ceiling_height=3.5
        )

        result = _calculate_features_score(target, {})

        assert '3.5м (очень высокие) ✅' in result['details']['ceiling_height']

    def test_ceiling_height_high(self):
        """Test with high ceilings >=3.0m"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            ceiling_height=3.1
        )

        result = _calculate_features_score(target, {})

        assert '3.1м (высокие)' in result['details']['ceiling_height']

    def test_ceiling_height_standard(self):
        """Test with standard ceilings >=2.7m"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            ceiling_height=2.7
        )

        result = _calculate_features_score(target, {})

        assert '2.7м (стандарт)' in result['details']['ceiling_height']

    def test_ceiling_height_low(self):
        """Test with low ceilings >=2.5m"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            ceiling_height=2.5
        )

        result = _calculate_features_score(target, {})

        assert '2.5м (низкие)' in result['details']['ceiling_height']

    def test_ceiling_height_missing(self):
        """Test with missing ceiling height"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )

        result = _calculate_features_score(target, {})

        assert 'Не указана' in result['details']['ceiling_height']

    def test_elevator_panoramic(self):
        """Test with panoramic elevator"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            elevator_count='панорамный'
        )

        result = _calculate_features_score(target, {})

        assert 'Панорамный' in result['details']['elevator']

    def test_elevator_none_high_floor(self):
        """Test no elevator on high floor (>3)"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,  # > 3
            total_floors=10,
            elevator_count='нет'
        )

        result = _calculate_features_score(target, {})

        assert any('Отсутствие лифта критично' in rec for rec in result['recommendations'])

    def test_elevator_none_low_floor(self):
        """Test no elevator on low floor (<=3)"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=2,  # <= 3
            total_floors=10,
            elevator_count='нет'
        )

        result = _calculate_features_score(target, {})

        # Should not warn about elevator for low floors
        assert not any('лифта' in rec.lower() for rec in result['recommendations'])

    def test_security_24_7_concierge_video(self):
        """Test with full security"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            security_level='24/7+консьерж+видео'
        )

        result = _calculate_features_score(target, {})

        assert '24/7+консьерж+видео' in result['details']['security']

    def test_security_none(self):
        """Test with no security"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            security_level='нет'
        )

        result = _calculate_features_score(target, {})

        assert 'Отсутствует' in result['details']['security']

    def test_bathrooms_multiple(self):
        """Test with multiple bathrooms"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            bathrooms=3
        )

        result = _calculate_features_score(target, {})

        assert '3 ванные' in result['details']['bathrooms']

    def test_bathrooms_default_one(self):
        """Test with default one bathroom"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )

        result = _calculate_features_score(target, {})

        assert '1 ванные' in result['details']['bathrooms']

    def test_house_type_monolith(self):
        """Test with monolith house type"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            house_type='монолит'
        )

        result = _calculate_features_score(target, {})

        assert 'Монолит' in result['details']['house_type']

    def test_house_type_panel(self):
        """Test with panel house type"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            house_type='панель'
        )

        result = _calculate_features_score(target, {})

        assert 'Панель' in result['details']['house_type']

    def test_score_capped_at_100(self):
        """Test that features score never exceeds 100"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            repair_level='дизайнерская',
            view_type='премиум',
            parking_type='гараж',
            ceiling_height=3.5,
            elevator_count='панорамный',
            security_level='24/7+консьерж+видео',
            bathrooms=3,
            house_type='монолит'
        )

        result = _calculate_features_score(target, {})

        assert result['score'] <= 100


class TestGetAttractivenessCategory:
    """Tests for _get_attractiveness_category() function"""

    def test_excellent_category(self):
        """Test excellent category (>=85)"""
        category = _get_attractiveness_category(90)

        assert category['name'] == 'Отличная'
        assert category['emoji'] == '🌟'
        assert 'очень привлекателен' in category['description'].lower()

    def test_excellent_boundary(self):
        """Test excellent category boundary (exactly 85)"""
        category = _get_attractiveness_category(85)

        assert category['name'] == 'Отличная'

    def test_good_category(self):
        """Test good category (70-84)"""
        category = _get_attractiveness_category(75)

        assert category['name'] == 'Хорошая'
        assert category['emoji'] == '✅'
        assert 'конкурентоспособен' in category['description'].lower()

    def test_good_boundary(self):
        """Test good category boundary (exactly 70)"""
        category = _get_attractiveness_category(70)

        assert category['name'] == 'Хорошая'

    def test_average_category(self):
        """Test average category (55-69)"""
        category = _get_attractiveness_category(60)

        assert category['name'] == 'Средняя'
        assert category['emoji'] == '⚠️'
        assert 'недостатки' in category['description'].lower()

    def test_average_boundary(self):
        """Test average category boundary (exactly 55)"""
        category = _get_attractiveness_category(55)

        assert category['name'] == 'Средняя'

    def test_below_average_category(self):
        """Test below average category (40-54)"""
        category = _get_attractiveness_category(45)

        assert category['name'] == 'Ниже среднего'
        assert category['emoji'] == '🔴'
        assert 'слабо конкурентоспособен' in category['description'].lower()

    def test_below_average_boundary(self):
        """Test below average category boundary (exactly 40)"""
        category = _get_attractiveness_category(40)

        assert category['name'] == 'Ниже среднего'

    def test_low_category(self):
        """Test low category (<40)"""
        category = _get_attractiveness_category(30)

        assert category['name'] == 'Низкая'
        assert category['emoji'] == '🔴🔴'
        assert 'неконкурентоспособен' in category['description'].lower()

    def test_low_boundary(self):
        """Test low category boundary (exactly 0)"""
        category = _get_attractiveness_category(0)

        assert category['name'] == 'Низкая'


class TestGenerateSummary:
    """Tests for _generate_summary() function"""

    def test_summary_structure(self):
        """Test basic summary structure"""
        price_score = {
            'score': 90,
            'details': {'status': 'Справедливая цена'},
            'recommendations': ['Держите курс']
        }
        presentation_score = {
            'score': 75,
            'details': {},
            'recommendations': []
        }
        features_score = {
            'score': 80,
            'details': {},
            'recommendations': []
        }

        summary = _generate_summary(85.0, price_score, presentation_score, features_score)

        assert isinstance(summary, str)
        assert '85.0/100' in summary
        assert 'Отличная' in summary
        assert 'Компоненты:' in summary
        assert 'Цена: 90/100' in summary
        assert 'Презентация: 75/100' in summary
        assert 'Характеристики: 80/100' in summary

    def test_summary_with_recommendations(self):
        """Test summary includes top recommendations"""
        price_score = {
            'score': 50,
            'details': {'status': 'Переоценен'},
            'recommendations': ['Снизить цену на 5%']
        }
        presentation_score = {
            'score': 60,
            'details': {},
            'recommendations': ['Добавить фото', 'Улучшить описание']
        }
        features_score = {
            'score': 70,
            'details': {},
            'recommendations': ['Улучшить ремонт']
        }

        summary = _generate_summary(60.0, price_score, presentation_score, features_score)

        assert 'Ключевые рекомендации:' in summary
        assert '1. ' in summary  # First recommendation
        # Should include max 3 recommendations
        assert summary.count('. Снизить') + summary.count('. Добавить') + summary.count('. Улучшить') <= 3

    def test_summary_no_recommendations(self):
        """Test summary without recommendations"""
        price_score = {
            'score': 95,
            'details': {'status': 'Недооценен'},
            'recommendations': []
        }
        presentation_score = {
            'score': 90,
            'details': {},
            'recommendations': []
        }
        features_score = {
            'score': 85,
            'details': {},
            'recommendations': []
        }

        summary = _generate_summary(90.0, price_score, presentation_score, features_score)

        # Should not have recommendations section if no recommendations
        assert summary.count('Ключевые рекомендации:') == 0

    def test_summary_includes_category_emoji(self):
        """Test summary includes category emoji"""
        price_score = {
            'score': 90,
            'details': {'status': 'Справедливая'},
            'recommendations': []
        }
        presentation_score = {
            'score': 80,
            'details': {},
            'recommendations': []
        }
        features_score = {
            'score': 85,
            'details': {},
            'recommendations': []
        }

        summary = _generate_summary(85.0, price_score, presentation_score, features_score)

        assert '🌟' in summary  # Excellent category emoji


class TestCalculateAttractivenessIndex:
    """Tests for calculate_attractiveness_index() main function"""

    def test_basic_calculation(self):
        """Test basic attractiveness index calculation"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )

        fair_price_analysis = {
            'overpricing_percent': 3.0  # Fair price
        }

        market_stats = {}

        result = calculate_attractiveness_index(target, fair_price_analysis, market_stats)

        assert 'total_index' in result
        assert 0 <= result['total_index'] <= 100
        assert 'category' in result
        assert 'category_emoji' in result
        assert 'category_description' in result
        assert 'components' in result
        assert 'summary' in result

    def test_weighted_components(self):
        """Test that components are weighted correctly (40-30-30)"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            images=['img.jpg'] * 15,
            photo_type='реальные',
            description='A' * 500,
            object_status='готов',
            repair_level='дизайнерская',
            view_type='премиум',
            parking_type='гараж',
            ceiling_height=3.5,
            elevator_count='панорамный',
            security_level='24/7+консьерж+видео',
            bathrooms=3,
            house_type='монолит'
        )

        fair_price_analysis = {
            'overpricing_percent': 0.0  # Perfect price
        }

        market_stats = {}

        result = calculate_attractiveness_index(target, fair_price_analysis, market_stats)

        # Check component weights
        assert result['components']['price']['weight'] == 40
        assert result['components']['presentation']['weight'] == 30
        assert result['components']['features']['weight'] == 30

        # Check weighted scores
        price_weighted = result['components']['price']['weighted_score']
        presentation_weighted = result['components']['presentation']['weighted_score']
        features_weighted = result['components']['features']['weighted_score']

        # Total should be sum of weighted scores
        expected_total = price_weighted + presentation_weighted + features_weighted
        assert abs(result['total_index'] - expected_total) < 0.1  # Allow for rounding

    def test_components_structure(self):
        """Test that components have correct structure"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )

        fair_price_analysis = {
            'overpricing_percent': 5.0
        }

        market_stats = {}

        result = calculate_attractiveness_index(target, fair_price_analysis, market_stats)

        for component_name in ['price', 'presentation', 'features']:
            component = result['components'][component_name]
            assert 'score' in component
            assert 'weight' in component
            assert 'weighted_score' in component
            assert 'details' in component
            assert 'recommendations' in component

    def test_overpriced_property(self):
        """Test attractiveness for overpriced property"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=15_000_000,  # Overpriced
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )

        fair_price_analysis = {
            'overpricing_percent': 25.0  # Extremely overpriced
        }

        market_stats = {}

        result = calculate_attractiveness_index(target, fair_price_analysis, market_stats)

        # Should have low total index due to price
        assert result['total_index'] < 70
        # Price component should have low score
        assert result['components']['price']['score'] <= 30

    def test_underpriced_property(self):
        """Test attractiveness for underpriced property"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=8_000_000,  # Underpriced
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10,
            images=['img.jpg'] * 15,
            photo_type='реальные',
            description='A' * 500,
            object_status='готов',
            repair_level='дизайнерская',
            view_type='премиум'
        )

        fair_price_analysis = {
            'overpricing_percent': -12.0  # Strongly underpriced
        }

        market_stats = {}

        result = calculate_attractiveness_index(target, fair_price_analysis, market_stats)

        # Should have high price score
        assert result['components']['price']['score'] >= 95
        # Should have recommendations to raise price
        assert any('повысить' in rec.lower() for rec in result['components']['price']['recommendations'])

    def test_missing_overpricing_percent(self):
        """Test with missing overpricing_percent in analysis"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )

        fair_price_analysis = {}  # No overpricing_percent

        market_stats = {}

        result = calculate_attractiveness_index(target, fair_price_analysis, market_stats)

        # Should default to 0 (fair price)
        assert result['components']['price']['score'] == 90

    def test_summary_included(self):
        """Test that summary is generated and included"""
        target = TargetProperty(
            url='https://test.com/target/1',
            price=10_000_000,
            total_area=60,
            rooms=2,
            floor=5,
            total_floors=10
        )

        fair_price_analysis = {
            'overpricing_percent': 0.0
        }

        market_stats = {}

        result = calculate_attractiveness_index(target, fair_price_analysis, market_stats)

        assert 'summary' in result
        assert isinstance(result['summary'], str)
        assert len(result['summary']) > 0
        assert 'Индекс привлекательности' in result['summary']
