import argparse
import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright

parser=argparse.ArgumentParser(description='Browser smoke tests; start API on 8000 and static server from /workspace on 8001 first.')
parser.add_argument('--api-url',default='http://127.0.0.1:8000/')
parser.add_argument('--static-url',default='http://127.0.0.1:8001/vinit-s-personal-reserach-terminal/')
args=parser.parse_args()

async def run():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  findings=[]
  for base in [args.api_url,args.static_url]:
   for mobile in [False,True]:
    page=await browser.new_page(viewport={'width':390 if mobile else 1440,'height':900})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    for path in ['index.html','overview.html','research.html?ticker=RELIANCE','research.html?ticker=RELIANCE&exchange=BSE','compare.html?target=TCS','watchlist.html','reports.html','valuation_lab.html','quant_lab.html','data_quality.html','stock_intelligence.html?ticker=INFY']:
     errors.clear();r=await page.goto(base+path);await page.wait_for_timeout(350)
     assert r.status==200,(base,path,r.status)
     assert not errors,(base,path,errors)
     findings.append({'mode':'api' if ':8000' in base else 'static','mobile':mobile,'page':path,'errors':list(errors)})
    await page.goto(base+'research.html?ticker=RELIANCE');await page.wait_for_selector('#researchContainer:not(.hidden)')
    assert 'Reliance' in await page.locator('#businessSummaryText').inner_text()
    await page.locator('#watchlistBtn').click();await page.goto(base+'watchlist.html');await page.wait_for_selector('#watchlistBody a');assert 'RELIANCE' in await page.locator('#watchlistBody').inner_text()
    await page.goto(base+'quant_lab.html');await page.wait_for_function("document.getElementById('rows').children.length > 1")
    await page.locator('#filter').fill('TCS');await page.wait_for_timeout(100);assert 'TCS' in await page.locator('#rows').inner_text()
    await page.goto(base+'compare.html?target=TCS');await page.wait_for_timeout(500);assert '₹' in await page.locator('#compareBody').inner_text()
    await page.goto(base+'valuation_lab.html');await page.locator('#tabBanking').click();await page.locator('#bankROE').fill('0');assert 'positive income' in await page.locator('#modelError').inner_text()
    await page.goto(base+'reports.html');await page.wait_for_function("document.getElementById('reportContent').innerText.includes('Sources and limits')");assert 'SYNTHETIC DATA' not in await page.locator('#reportContent').inner_text();assert 'Reliance Industries' in await page.locator('#reportContent').inner_text()
    await page.close()
  await browser.close()
  print(json.dumps(findings))
  print(f'{len(findings)} page loads passed; research, watchlist, screener, reports and invalid valuation interactions passed in local/static and desktop/mobile modes.')
asyncio.run(run())
