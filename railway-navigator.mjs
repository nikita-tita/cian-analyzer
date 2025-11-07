import { chromium } from 'playwright';

async function navigateRailway() {
  console.log('🚀 Launching browser...');

  const browser = await chromium.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu'
    ]
  });

  const context = await browser.newContext();
  const page = await context.newPage();

  console.log('📍 Navigating to Railway...');
  await page.goto('https://railway.app', { waitUntil: 'networkidle', timeout: 30000 });

  console.log('📸 Taking screenshot...');
  await page.screenshot({ path: 'railway-screenshot.png', fullPage: true });

  console.log('✅ Success! Screenshot saved to railway-screenshot.png');
  console.log('\nNow you can:');
  console.log('1. Click "Start a New Project"');
  console.log('2. Choose "Deploy from GitHub repo"');
  console.log('3. Select: nikita-tita/cian-analyzer');
  console.log('4. Settings → Source → Branch: claude/add-browser-automation-skill-011CUtW7fq3goBrhVCRLTEK1');
  console.log('5. Settings → Networking → Generate Domain');

  await browser.close();
  console.log('\n🎉 Done!');
}

navigateRailway().catch(console.error);
