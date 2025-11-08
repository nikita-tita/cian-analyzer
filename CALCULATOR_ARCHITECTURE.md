# CIAN-Analyzer Calculator System - Comprehensive Architecture Overview

## Executive Summary

The CIAN-Analyzer is a sophisticated real estate analysis platform that calculates fair market prices for properties using a **median-based comparative analysis methodology** with a **6-cluster coefficient system**. The system comprises multiple integrated modules working together to analyze properties, find comparable listings, calculate fair prices, and generate detailed reports.

**Key Statistics:**
- 20+ property parameters analyzed
- 6 parameter clusters for comprehensive evaluation
- 95% confidence intervals for statistical validity
- Median-based methodology (resilient to outliers)
- 4 dynamic price scenarios with financial projections

---

## 1. ARCHITECTURE OVERVIEW

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Flask Web App (app_new.py)               │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Web UI      │  │  Rate Limit  │  │  CSRF Token  │          │
│  │  (wizard.js) │  │  (Limiter)   │  │  (WTF)       │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
   ┌─────────┐   ┌──────────────┐  ┌─────────────┐
   │ Parser  │   │ Analyzer     │  │ Cache       │
   │ Module  │   │ (RealEstate) │  │ (Redis)     │
   │         │   │ Module       │  │             │
   └─────────┘   └──────────────┘  └─────────────┘
        │              │
        │     ┌────────┼────────┐
        │     │        │        │
        ▼     ▼        ▼        ▼
   ┌──────┐ ┌────────┐ ┌──────────┐ ┌──────────────┐
   │Parser│ │Median  │ │Coefficient│ │Price Scenario│
   │Logic │ │Calculator│ System    │ │Generator      │
   └──────┘ └────────┘ └──────────┘ └──────────────┘
        │
        └─────→ ┌──────────────────────┐
                │ Export Modules        │
                │ - Markdown Exporter  │
                │ - TXT Exporter       │
                │ - Report Generator   │
                └──────────────────────┘
```

### Core Module Structure

```
/home/user/cian-analyzer/
├── src/
│   ├── analytics/                    # CALCULATION ENGINE
│   │   ├── analyzer.py              # Main RealEstateAnalyzer class
│   │   ├── fair_price_calculator.py # Fair price calculation logic
│   │   ├── median_calculator.py     # Median & comparison calculations
│   │   ├── coefficients.py          # 6-cluster coefficient system
│   │   ├── parameter_classifier.py  # Fixed vs Variable parameters
│   │   ├── property_tracker.py      # Event logging & tracking
│   │   ├── recommendations.py       # Smart recommendation engine
│   │   ├── markdown_exporter.py     # Report generation (Markdown)
│   │   └── __init__.py
│   │
│   ├── models/                      # DATA MODELS
│   │   ├── property.py              # TargetProperty, ComparableProperty
│   │   └── __init__.py
│   │
│   ├── parsers/                     # PROPERTY PARSING
│   │   ├── playwright_parser.py     # Web scraping with Playwright
│   │   ├── simple_parser.py         # Fallback parser
│   │   ├── async_parser.py          # Async parsing
│   │   ├── browser_pool.py          # Browser resource management
│   │   └── __init__.py
│   │
│   ├── cache/                       # CACHING LAYER
│   │   ├── redis_cache.py           # Redis integration
│   │   └── __init__.py
│   │
│   ├── utils/                       # UTILITIES
│   │   ├── session_storage.py       # Session management
│   │   └── __init__.py
│   │
│   └── __init__.py
│
├── app_new.py                        # MAIN FLASK APPLICATION
├── requirements.txt                  # Python dependencies
└── pyproject.toml                    # Project configuration
```

---

## 2. MAIN CALCULATOR FILES AND MODULES

### 2.1 RealEstateAnalyzer (Core Engine)
**File:** `/home/user/cian-analyzer/src/analytics/analyzer.py`

**Purpose:** Main orchestrator for all calculation and analysis operations.

**Key Methods:**
```python
class RealEstateAnalyzer:
    def analyze(request: AnalysisRequest) -> AnalysisResult:
        # Complete analysis workflow:
        # 1. Filter outliers (±3σ rule)
        # 2. Calculate market statistics
        # 3. Calculate fair price with medians
        # 4. Generate 4 price scenarios
        # 5. Calculate strengths/weaknesses
        # 6. Generate chart data
        
    def calculate_fair_price() -> Dict:
        # New logic: applies coefficients only for DIFFERENCES from median
        # Returns: fair_price_per_sqm, fair_price_total, price_diff_percent
        
    def calculate_market_statistics() -> Dict:
        # Calculates: mean, median, stdev, confidence intervals (95%)
        # Separates: all comparables vs with_design vs without_design
        
    def generate_price_scenarios() -> List[PriceScenario]:
        # Generates 4 scenarios: fast, optimal, standard, maximum
        # Includes: price trajectory, monthly probability, financials
```

**Key Features:**
- ✅ Outlier filtering using 3-sigma rule
- ✅ 95% confidence interval calculations
- ✅ Median-based price calculation (resistant to outliers)
- ✅ 4 dynamic price scenarios
- ✅ Event tracking and logging
- ✅ Redis caching support

---

### 2.2 Fair Price Calculator
**File:** `/home/user/cian-analyzer/src/analytics/fair_price_calculator.py`

**Purpose:** Advanced price calculation using median adjustments.

**Key Formula:**
```
Fair Price = Base Price Per SqM × Multiplier × Total Area

Multiplier = Product of:
  1. Repair Level Adjustment
  2. Apartment Features (ceiling, bathrooms, windows, elevators)
  3. Position Adjustments (floor)
  4. Individual Adjustments
  5. View Adjustments (max 5%)
  6. Risk Adjustments (photo type, building age, liquidity)
```

**Critical Logic:**
1. **Calculates medians** from comparable properties
2. **Compares target** with medians for each parameter
3. **Applies coefficients ONLY for differences** (not for matches)
4. **If target equals median** → coefficient = 1.0 (no change)
5. **Multiplier range** limited to 0.7-1.4 (±30%)

**Coefficient Clusters:**
```python
1. REPAIR LEVEL:          0.75-2.00 (черновая to дизайнерская)
2. APARTMENT FEATURES:    Multiple sub-coefficients
   - Ceiling height:      0.95-1.05
   - Bathrooms:           0.90-1.15
   - Window type:         0.85-1.06
   - Elevator count:      0.95-1.07
3. POSITION:              Floor-based (0.97-1.04)
4. VIEW:                  0.97-1.05 (limited to 5%)
5. RISKS:                 Photo type, object status, building age
6. LIQUIDITY:             0.90-1.00 (high prices reduced)
```

---

### 2.3 Median Calculator
**File:** `/home/user/cian-analyzer/src/analytics/median_calculator.py`

**Purpose:** Calculate medians and compare target with medians.

**Key Functions:**
```python
def calculate_medians_from_comparables(comparables) -> Dict[str, Any]:
    # Returns medians for:
    # - Numeric: total_area, living_area, ceiling_height, bathrooms, floor, build_year
    # - Categorical: repair_level, window_type, elevator_count, view_type, photo_type, object_status
    # - Special: living_area_percent, price_per_sqm

def compare_target_with_medians(target, medians) -> Dict[str, Dict]:
    # Returns comparison for each parameter:
    # {
    #     parameter: {
    #         'target_value': ...,
    #         'median_value': ...,
    #         'equals_median': bool,
    #         'direction': 'above'|'below'|'equals',
    #         'difference': ... (for numeric)
    #     }
    # }
```

**Usage:** Only parameters where target ≠ median get coefficient adjustments.

---

### 2.4 Coefficients System
**File:** `/home/user/cian-analyzer/src/analytics/coefficients.py`

**Purpose:** Define all coefficient values organized in 6 clusters.

**Structure:**
```python
# КЛАСТЕР 1: REPAIR & CONDITION
REPAIR_LEVEL_COEFFICIENTS = {
    'черновая': 0.75,
    'эконом': 0.85,
    'стандартная': 1.00,  # Base level
    'капитальная': 1.15,
    'улучшенная': 1.25,
    'премиум': 1.50,
    'люкс': 1.80,
    'дизайнерская': 2.00,
}

# КЛАСТЕР 2: HOUSE CHARACTERISTICS
ELEVATOR_COUNT_COEFFICIENTS = {'нет': 0.95, 'один': 1.00, 'два': 1.03, 'три+': 1.05}
WINDOW_TYPE_COEFFICIENTS = {'деревянные': 0.85, ..., 'панорамные': 1.06}
BATHROOMS_COEFFICIENTS = {0: 0.70, 1: 1.00, 2: 1.05, 3: 1.08}

# КЛАСТЕР 3-6: Location, Security, View, Risks
# ... (additional coefficients)

# DYNAMIC FUNCTIONS:
def get_area_coefficient(target_area, median_area) -> float
def get_ceiling_height_coefficient(height) -> float
def get_living_area_coefficient(living_area, total_area) -> float
def get_floor_coefficient(floor, total_floors) -> float
def get_building_age_coefficient(build_year) -> float
def get_price_liquidity_coefficient(price) -> float
```

---

### 2.5 Parameter Classifier
**File:** `/home/user/cian-analyzer/src/analytics/parameter_classifier.py`

**Purpose:** Classify parameters as FIXED (for filtering) or VARIABLE (for adjustments).

**Fixed Parameters** (used for filtering, no coefficients):
```
- district_type, transport_accessibility  (Locação)
- house_type, house_condition             (Дом)
- security_level, parking_type            (Инфраструктура)
```

**Variable Parameters** (apply coefficients for differences):
```
- repair_level                            (Отделка)
- ceiling_height, bathrooms, window_type (Характеристики)
- floor, metro_distance                   (Положение)
- view_type                               (Вид)
- photo_type, object_status, build_year   (Риски)
```

**Critical Concept:**
- Fixed parameters define the comparable group (homogeneous selection)
- Variable parameters show differences within the group
- Coefficients only applied for variable parameters with differences

---

## 3. DATA MODELS

### 3.1 Property Models
**File:** `/home/user/cian-analyzer/src/models/property.py`

**Core Classes:**
```python
class PropertyBase(BaseModel):
    # Basic info
    url: str
    price: float
    total_area: float
    living_area: float
    kitchen_area: float
    rooms: int
    floor: int
    total_floors: int
    address: str
    metro: List[str]

class TargetProperty(PropertyBase):
    # Target object for analysis
    price_per_sqm: float (calculated)
    
    # 6 Clusters of parameters
    # CLUSTER 1: REPAIR & CONDITION
    repair_level: str (черновая|стандартная|премиум|люкс)
    build_year: int
    
    # CLUSTER 2: HOUSE CHARACTERISTICS
    elevator_count: str
    ceiling_height: float
    bathrooms: int
    window_type: str
    
    # CLUSTER 3: LOCATION & ACCESSIBILITY
    metro_distance_min: int
    district_type: str
    transport_accessibility: str
    
    # CLUSTER 4: SECURITY & SERVICE
    security_level: str
    parking_type: str
    parking_spaces: int
    sports_amenities: List[str]
    
    # CLUSTER 5: VIEW & AESTHETICS
    view_type: str
    noise_level: str
    crowded_level: str
    
    # CLUSTER 6: INFO & RISKS
    photo_type: str
    object_status: str

class ComparableProperty(PropertyBase):
    # Comparable listing for analysis
    price_per_sqm: float
    has_design: bool
    distance_km: float
    similarity_score: float (0-1)
    excluded: bool

class AnalysisRequest(BaseModel):
    target_property: TargetProperty
    comparables: List[ComparableProperty]
    filter_outliers: bool = True
    use_median: bool = True

class AnalysisResult(BaseModel):
    timestamp: datetime
    target_property: TargetProperty
    comparables: List[ComparableProperty]
    market_statistics: Dict
    fair_price_analysis: Dict
    price_scenarios: List[PriceScenario]
    strengths_weaknesses: Dict
    comparison_chart_data: Dict
    box_plot_data: Dict
```

**Data Validation:**
- Pydantic validators for numeric ranges
- Russian name mapping (automatic translation)
- Smart defaults for missing fields
- Living area < total area validation

---

## 4. CALCULATION LOGIC AND FORMULAS

### 4.1 Fair Price Calculation Flow

```
INPUT:
  - Target Property (with all 20+ parameters)
  - List of Comparable Properties

STEP 1: FILTER COMPARABLES
  - Remove outliers using 3-sigma rule
  - Keep only non-excluded comparables
  - Minimum 3 comparables required

STEP 2: CALCULATE MEDIANS
  - Numeric parameters: use statistical median
  - Categorical parameters: use mode (most frequent)
  - Median = "average" comparable property

STEP 3: COMPARE TARGET WITH MEDIANS
  - For each variable parameter:
    - Extract target value
    - Extract median value
    - Calculate difference
    - Determine if equals, above, or below

STEP 4: APPLY COEFFICIENTS (6 clusters)
  - ONLY if target ≠ median (skip if equal)
  
  Cluster 1 - REPAIR LEVEL:
    coef = target_repair_coef / median_repair_coef
    multiplier *= coef
  
  Cluster 2 - APARTMENT FEATURES:
    For each (ceiling, bathrooms, windows, elevators, living%, area):
      coef = target_coef / median_coef
      multiplier *= coef
  
  Cluster 3 - POSITION:
    If floor differs from median:
      coef = target_floor_coef / median_floor_coef
      multiplier *= coef
  
  Cluster 5 - VIEW:
    If view differs (max 5% impact):
      coef = target_view_coef / median_view_coef
      multiplier *= coef
  
  Cluster 6 - RISKS:
    For photo_type, object_status, build_year:
      coef = target_coef / median_coef
      multiplier *= coef

STEP 5: VALIDATE MULTIPLIER
  - If multiplier < 0.7: limit to 0.7 (max -30%)
  - If multiplier > 1.4: limit to 1.4 (max +40%)
  - Protects from excessive discounts/premiums

STEP 6: FINAL CALCULATION
  fair_price_per_sqm = base_price_per_sqm × multiplier
  fair_price_total = fair_price_per_sqm × target_area
  
  price_diff_amount = current_price - fair_price_total
  price_diff_percent = price_diff_amount / fair_price_total × 100

STEP 7: STATUS DETERMINATION
  - is_overpriced: if price_diff_percent > 5%
  - is_underpriced: if price_diff_percent < -5%
  - is_fair: if -5% ≤ price_diff_percent ≤ 5%

OUTPUT:
  {
    'base_price_per_sqm': 150000,
    'medians': {...all medians...},
    'comparison': {...parameter comparisons...},
    'adjustments': {
      'repair_level': {'value': 1.25, 'description': '...'},
      'ceiling_height': {'value': 1.02, ...},
      ...
    },
    'final_multiplier': 1.089,
    'fair_price_per_sqm': 163350,
    'fair_price_total': 8167500,
    'current_price': 8500000,
    'price_diff_amount': 332500,
    'price_diff_percent': 4.07,
    'is_overpriced': False,
    'is_underpriced': False,
    'is_fair': True,
    'confidence_interval_95': {...}
  }
```

### 4.2 Market Statistics Calculation

```python
def calculate_market_statistics():
    # QUANTILE STATISTICS
    prices_per_sqm = [c.price_per_sqm for c in comparables]
    
    statistics = {
        'all': {
            'mean': mean(prices_per_sqm),
            'median': median(prices_per_sqm),  # ← More robust than mean
            'min': min(prices_per_sqm),
            'max': max(prices_per_sqm),
            'stdev': stdev(prices_per_sqm),
            'count': len(prices_per_sqm),
            'confidence_interval_95': {
                'lower': ...,
                'upper': ...,
                'margin': ...
            }
        },
        'with_design': {...},      # Only design apartments
        'without_design': {...}    # Regular apartments
    }
    
    return statistics
```

### 4.3 Confidence Interval Calculation

```python
def calculate_confidence_interval(data, confidence=0.95):
    n = len(data)
    mean = statistics.mean(data)
    stdev = statistics.stdev(data)
    
    if n < 30:
        # Student's t-distribution (more accurate for small samples)
        df = n - 1
        t_critical = scipy_stats.t.ppf((1 + confidence) / 2, df)
        margin = t_critical * (stdev / sqrt(n))
    else:
        # Normal z-distribution
        z_critical = scipy_stats.norm.ppf((1 + confidence) / 2)
        margin = z_critical * (stdev / sqrt(n))
    
    return (mean - margin, mean + margin)
```

---

## 5. REPORT GENERATION CODE

### 5.1 Markdown Exporter
**File:** `/home/user/cian-analyzer/src/analytics/markdown_exporter.py`

**Purpose:** Generate human-readable Markdown reports from analysis results.

**Key Sections Generated:**
1. Property Information (price, area, rooms, floor, address)
2. Timeline of Processing (events with timestamps)
3. Parsing Results (extracted data)
4. Found Comparables (table with price/area)
5. Market Statistics (median, mean, confidence intervals)
6. Fair Price Analysis (calculated price, adjustments)
7. Metrics (calculation time, comparables filtered)

**Usage:**
```python
from src.analytics.markdown_exporter import MarkdownExporter

exporter = MarkdownExporter()
markdown_report = exporter.export_single_property(property_log)
# Output: beautifully formatted Markdown
```

### 5.2 Recommendation Engine
**File:** `/home/user/cian-analyzer/src/analytics/recommendations.py`

**Purpose:** Generate actionable recommendations based on analysis.

**Priority Levels:**
- **CRITICAL (1):** Price significantly above market
- **HIGH (2):** Important improvements with ROI
- **MEDIUM (3):** Presentation improvements
- **INFO (4):** Strategic information

**Example Recommendations:**
```python
Recommendation(
    priority=1,  # CRITICAL
    icon='⚠️',
    title='CRITICAL: Price overvaluation',
    message='Property overpriced by 15%',
    action='Reduce price to fair market value',
    expected_result='Increase sale probability to 75%',
    roi=0.15,
    financial_impact={'time_saved_months': 8, 'opportunity_cost_saved': 500000}
)
```

---

## 6. CONFIGURATION FILES

### 6.1 Environment Configuration
**File:** `.env.example`
```
# Redis Caching
REDIS_ENABLED=false
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_NAMESPACE=housler

# Security
SECRET_KEY=your-secret-key-here  # Generate: openssl rand -hex 32
FLASK_ENV=development  # or production

# Browser Configuration
MAX_BROWSERS=3
PLAYWRIGHT_HEADLESS=true

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=200 per day
```

### 6.2 Dependencies
**File:** `requirements.txt`
```
# Core
Flask>=3.0.0
pydantic>=2.5.0
requests>=2.31.0

# Parsing
beautifulsoup4>=4.12.0
lxml>=4.9.0
playwright>=1.40.0

# Statistics
numpy>=1.24.0
scipy>=1.11.0

# Production
gunicorn>=21.2.0
redis>=5.0.0

# Security
Flask-Limiter>=3.5.0
Flask-WTF>=1.2.0

# Testing
pytest>=7.4.0
pytest-cov>=4.1.0
```

### 6.3 Project Configuration
**File:** `pyproject.toml`
```toml
[project]
name = "housler"
version = "2.0.0"
requires-python = ">=3.10"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["--cov=src", "--cov=app_new"]
```

---

## 7. CALCULATION WORKFLOW EXAMPLE

### Complete End-to-End Example

**INPUT:**
```json
{
  "target_property": {
    "url": "https://cian.ru/sale/flat/123456/",
    "price": 8500000,
    "total_area": 50.0,
    "living_area": 35.0,
    "rooms": 2,
    "floor": 7,
    "total_floors": 10,
    "repair_level": "премиум",
    "ceiling_height": 3.0,
    "bathrooms": 2,
    "window_type": "панорамные",
    "elevator_count": "два",
    "view_type": "на воду",
    "build_year": 2018
  },
  "comparables": [
    {
      "price": 8200000,
      "total_area": 48.0,
      "repair_level": "стандартная",
      ...
    },
    {
      "price": 8450000,
      "total_area": 51.0,
      "repair_level": "улучшенная",
      ...
    },
    {
      "price": 8100000,
      "total_area": 49.5,
      "repair_level": "стандартная",
      ...
    }
  ],
  "filter_outliers": true,
  "use_median": true
}
```

**PROCESSING:**

1. **STEP 1 - Calculate Comparables' Price per SqM:**
   - Property 1: 8,200,000 / 48 = 170,833 ₽/м²
   - Property 2: 8,450,000 / 51 = 165,686 ₽/м²
   - Property 3: 8,100,000 / 49.5 = 163,636 ₽/м²

2. **STEP 2 - Filter Outliers (3-sigma):**
   - Mean: 166,718 ₽/м²
   - StDev: 3,533 ₽/м²
   - Range: 155,618 - 177,819 ₽/м²
   - All within range → keep all 3

3. **STEP 3 - Calculate Medians:**
   ```
   Numeric Parameters:
   - median(total_area) = 49.5
   - median(ceiling_height) = 2.8
   - median(bathrooms) = 1
   - median(floor) = 6
   - median(build_year) = 2015
   
   Categorical Parameters:
   - mode(repair_level) = 'стандартная'
   - mode(window_type) = 'пластиковые'
   - mode(elevator_count) = 'один'
   - mode(view_type) = 'улица'
   ```

4. **STEP 4 - Compare Target with Medians:**
   ```
   target_repair_level: 'премиум'    vs median: 'стандартная'     → DIFFERENT
   target_ceiling_height: 3.0        vs median: 2.8               → DIFFERENT
   target_bathrooms: 2               vs median: 1                 → DIFFERENT
   target_floor: 7                   vs median: 6                 → DIFFERENT
   target_view_type: 'на воду'       vs median: 'улица'           → DIFFERENT
   target_build_year: 2018           vs median: 2015              → DIFFERENT
   ```

5. **STEP 5 - Apply Coefficients:**
   ```
   Base price per SqM (median) = 165,686 ₽
   
   1. Repair Level:
      target_coef = 1.50 (премиум)
      median_coef = 1.00 (стандартная)
      coef = 1.50 / 1.00 = 1.50
      multiplier = 1.0 × 1.50 = 1.50
   
   2. Ceiling Height:
      target_coef = 1.02 (3.0м)
      median_coef = 0.98 (2.8м)
      coef = 1.02 / 0.98 = 1.041
      multiplier = 1.50 × 1.041 = 1.561
   
   3. Bathrooms:
      target_coef = 1.05 (2)
      median_coef = 1.00 (1)
      coef = 1.05 / 1.00 = 1.05
      multiplier = 1.561 × 1.05 = 1.639
   
   4. Floor:
      target_coef = 1.04 (7/10 = 0.70 = middle)
      median_coef = 1.01 (6/10 = 0.60 = middle)
      coef = 1.04 / 1.01 = 1.029
      multiplier = 1.639 × 1.029 = 1.686
   
   5. View Type:
      target_coef = 1.05 (на воду)
      median_coef = 1.00 (улица)
      coef = 1.05 / 1.00 = 1.05
      multiplier = 1.686 × 1.05 = 1.770
   
   6. Building Age:
      target_age = 2024 - 2018 = 6 years (< 10) → coef = 1.0
      median_age = 2024 - 2015 = 9 years (< 10) → coef = 1.0
      No adjustment needed
   
   Final multiplier = 1.770
   BUT: Limited to max 1.4 (protection against overpricing)
   Final multiplier = 1.40 (capped)
   ```

6. **STEP 6 - Calculate Fair Price:**
   ```
   Fair price per SqM = 165,686 × 1.40 = 231,960 ₽/м²
   Fair price total = 231,960 × 50.0 = 11,598,000 ₽
   
   Current price = 8,500,000 ₽
   Price difference = 8,500,000 - 11,598,000 = -3,098,000 ₽
   Price diff % = -3,098,000 / 11,598,000 × 100 = -26.7%
   
   Status: UNDERPRICED (below -5%)
   ```

**OUTPUT:**
```json
{
  "base_price_per_sqm": 165686,
  "final_multiplier": 1.40,
  "fair_price_per_sqm": 231960,
  "fair_price_total": 11598000,
  "current_price": 8500000,
  "price_diff_amount": -3098000,
  "price_diff_percent": -26.7,
  "is_overpriced": false,
  "is_underpriced": true,
  "is_fair": false,
  "confidence_interval_95": {
    "lower": 8050000,
    "upper": 9210000,
    "margin": 580000,
    "description": "11,598,000 ± 580,000 ₽ (95% confidence)"
  },
  "adjustments": {
    "repair_level": {
      "value": 1.50,
      "description": "Отделка: премиум vs стандартная (медиана)"
    },
    "ceiling_height": {
      "value": 1.041,
      "description": "Высота потолков: 3.0м vs 2.8м (медиана)"
    },
    ...
  }
}
```

---

## 8. KEY ARCHITECTURAL DECISIONS

### 8.1 Why Median-Based Calculation?

**Advantages over mean:**
- ✅ Resistant to outliers
- ✅ Represents "typical" property better
- ✅ More stable with small sample sizes (3-5 comparables)
- ✅ More realistic for real estate markets

**Why apply coefficients only for differences?**
- ✅ Avoids double-counting (base price already includes median)
- ✅ More accurate when target matches median (coef = 1.0)
- ✅ Mathematically sound (ratio method)
- ✅ Prevents excessive adjustments

### 8.2 6-Cluster Organization

**Benefits:**
- ✅ Logical grouping of related parameters
- ✅ Easy to maintain and update coefficients
- ✅ Clear semantics for each adjustment
- ✅ Easier to explain to users (transparency)

### 8.3 Multiplier Bounds (0.7 - 1.4)

**Protection:**
- ✅ Prevents excessive discounts (max -30%)
- ✅ Prevents unrealistic premiums (max +40%)
- ✅ Catches potential calculation errors
- ✅ Ensures results are within market reality

### 8.4 Confidence Intervals (95%)

**Why needed?**
- ✅ Statistical validity of price estimates
- ✅ Shows uncertainty due to small sample
- ✅ Professional reporting requirement
- ✅ Uses Student's t-distribution for small n < 30

---

## 9. TESTING AND QUALITY

### Test Coverage

**File:** `/home/user/cian-analyzer/tests/`
- `test_api.py`: API endpoints and calculation tests
- `test_security.py`: SSRF, CSRF, rate limiting tests
- `test_session_storage.py`: Session management
- `test_browser_pool.py`: Browser resource management

**Key Test Categories:**
- ✅ Unit tests for coefficients
- ✅ Integration tests for full analysis
- ✅ Security tests (SSRF, CSRF protection)
- ✅ Performance tests (caching effectiveness)

---

## 10. KEY FILES SUMMARY

| File | Purpose | Key Classes/Functions |
|------|---------|----------------------|
| `analyzer.py` | Main calculation engine | `RealEstateAnalyzer`, `.analyze()`, `.calculate_fair_price()` |
| `fair_price_calculator.py` | Fair price calculation | `calculate_fair_price_with_medians()`, adjustment helpers |
| `median_calculator.py` | Median & comparison logic | `calculate_medians_from_comparables()`, `compare_target_with_medians()` |
| `coefficients.py` | Coefficient definitions | `REPAIR_LEVEL_COEFFICIENTS`, `get_area_coefficient()`, etc. |
| `parameter_classifier.py` | Parameter classification | `FIXED_PARAMETERS`, `VARIABLE_PARAMETERS`, `classify_parameter()` |
| `property.py` | Data models & validation | `TargetProperty`, `ComparableProperty`, `AnalysisRequest`, `AnalysisResult` |
| `markdown_exporter.py` | Report generation | `MarkdownExporter`, `.export_single_property()` |
| `recommendations.py` | Smart recommendations | `RecommendationEngine`, `Recommendation` |
| `app_new.py` | Flask web application | Flask routes, request handling, security |
| `property_tracker.py` | Event logging | `PropertyTracker`, `PropertyLog`, event tracking |

---

## 11. SUMMARY OF CALCULATION ARCHITECTURE

The calculator system is a **multi-layered, mathematically sound valuation engine** that:

1. **Accepts** a target property and comparable listings
2. **Validates** data using Pydantic models
3. **Filters** outliers using statistical methods
4. **Calculates** medians from comparables
5. **Compares** target with medians
6. **Applies** coefficients from 6 clusters (only for differences)
7. **Validates** multiplier stays within bounds
8. **Calculates** final fair price with confidence intervals
9. **Generates** 4 price scenarios with financial projections
10. **Exports** results to various formats (Markdown, JSON, etc.)

**Mathematical Foundation:**
- Median-based (resistant to outliers)
- Ratio-based coefficients (target/median)
- 95% confidence intervals (Student's t-distribution)
- Protected by multiplier bounds (0.7 - 1.4)

**Architecture Benefits:**
- Scalable (modular design)
- Maintainable (clear separation of concerns)
- Testable (pure functions)
- Production-ready (Redis caching, rate limiting, security)
- User-friendly (transparent reporting)

---

**Version:** 2.0.0
**Last Updated:** November 8, 2024
**Project:** Housler - Intelligent Real Estate Analytics
