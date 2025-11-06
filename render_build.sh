#!/usr/bin/env bash
set -e

echo "====================================="
echo "Render Build Script for Cian Analyzer"
echo "====================================="

echo "Step 1/4: Installing Python dependencies..."
pip install -r requirements-render.txt

echo "Step 2/4: Installing Playwright browsers (chromium)..."
playwright install chromium

echo "Step 3/4: Installing system dependencies for Playwright..."
playwright install-deps chromium

echo "Step 4/4: Verifying installation..."
python -c "import playwright; print('✓ Playwright installed successfully')"
python -c "from src.parsers.playwright_parser import PlaywrightParser; print('✓ PlaywrightParser imported successfully')"

echo "====================================="
echo "Build complete! 🚀"
echo "====================================="
