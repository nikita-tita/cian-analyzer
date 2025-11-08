#!/bin/bash
# Quick Deploy Script for Step 3 Fix
# Run this script to deploy to production

set -e  # Exit on error

echo "═══════════════════════════════════════════════════════════════════"
echo "     🚀 DEPLOYING STEP 3 NOTIFICATION FLOW FIX 🚀"
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Check current branch
echo -e "${YELLOW}[1/6]${NC} Checking current branch..."
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "claude/fix-notification-flow-step3-011CUw745P7EwkTmmJk1iYQm" ]; then
    echo -e "${YELLOW}⚠️  Not on feature branch. Checking out...${NC}"
    git checkout claude/fix-notification-flow-step3-011CUw745P7EwkTmmJk1iYQm
fi
echo -e "${GREEN}✅ On feature branch${NC}"
echo ""

# Step 2: Pull latest changes
echo -e "${YELLOW}[2/6]${NC} Pulling latest changes from remote..."
git pull origin claude/fix-notification-flow-step3-011CUw745P7EwkTmmJk1iYQm
echo -e "${GREEN}✅ Branch up to date${NC}"
echo ""

# Step 3: Switch to main
echo -e "${YELLOW}[3/6]${NC} Switching to main branch..."
git checkout main
echo -e "${GREEN}✅ On main branch${NC}"
echo ""

# Step 4: Pull main
echo -e "${YELLOW}[4/6]${NC} Pulling latest main..."
git pull origin main
echo -e "${GREEN}✅ Main up to date${NC}"
echo ""

# Step 5: Merge feature branch
echo -e "${YELLOW}[5/6]${NC} Merging feature branch..."
echo -e "${YELLOW}Commits to be merged:${NC}"
git log --oneline main..claude/fix-notification-flow-step3-011CUw745P7EwkTmmJk1iYQm | head -5
echo ""
read -p "Proceed with merge? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git merge claude/fix-notification-flow-step3-011CUw745P7EwkTmmJk1iYQm --no-ff -m "Merge: Fix step 3 notification flow error handling

Includes:
- Backend logic fix for division by zero
- Comprehensive error handling (frontend & backend)
- Graceful degradation for missing data
- Improved error messages
- Mobile ticker animation fixes
- Complete deployment documentation

Commits merged:
- 275b6a3 docs: Add deployment checklist
- 1eebce5 docs: Add deployment summary
- 810b35f fix: Add robust error handling
- 54cf393 fix: Fix division by zero

Tested: ✅
Risk: Low
Breaking changes: None
"
    echo -e "${GREEN}✅ Merge successful${NC}"
else
    echo -e "${RED}❌ Merge cancelled${NC}"
    exit 1
fi
echo ""

# Step 6: Push to production
echo -e "${YELLOW}[6/6]${NC} Pushing to production..."
read -p "Push to production? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git push origin main
    echo -e "${GREEN}✅ Deployed to production!${NC}"
else
    echo -e "${YELLOW}⚠️  Push cancelled. Run 'git push origin main' manually when ready.${NC}"
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo -e "${GREEN}     ✅ DEPLOYMENT COMPLETE! ✅${NC}"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "📋 NEXT STEPS:"
echo "1. Verify site loads: https://your-site.com/calculator"
echo "2. Check wizard.js version in DevTools (should be v=20251108220000)"
echo "3. Test analysis flow (steps 1-2-3)"
echo "4. Monitor error logs for 30 minutes"
echo "5. Review DEPLOY_CHECKLIST.md for full verification"
echo ""
echo "🆘 ROLLBACK (if needed):"
echo "   git revert HEAD"
echo "   git push origin main"
echo ""

