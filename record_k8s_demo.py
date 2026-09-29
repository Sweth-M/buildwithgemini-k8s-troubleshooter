import asyncio
import os
from playwright.async_api import async_playwright

async def record():
    os.makedirs("demo_recordings", exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )
        
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir="demo_recordings/",
            record_video_size={"width": 1280, "height": 800}
        )
        
        page = await context.new_page()
        print("Navigating to http://localhost:8080/...")
        await page.goto("http://localhost:8080/")
        await page.wait_for_selector("#form")
        await asyncio.sleep(2)
        
        # Turn 1: Paste kubectl get pods output with CrashLoopBackOff and ImagePullBackOff
        kubectl_output = """NAME                          READY   STATUS             RESTARTS       AGE
api-7d9f8b6c5d-x2k4p          0/1     CrashLoopBackOff   7 (2m ago)     18m
api-7d9f8b6c5d-q8n1z          1/1     Running            0              18m
worker-5c6b7d8f9-lm3tq        0/1     CrashLoopBackOff   4 (45s ago)    12m
frontend-6f8d9c7b4-zp2wr      0/1     ImagePullBackOff   0              5m
redis-0                       1/1     Running            0              2d

What's wrong?"""
        
        print("Submitting Turn 1: kubectl get pods...")
        input_el = page.locator("#input")
        await input_el.fill(kubectl_output)
        await asyncio.sleep(1.5)
        await page.keyboard.press("Enter")
        
        # Wait for agent response
        print("Waiting for Turn 1 response...")
        try:
            await page.wait_for_selector(".msg.agent:nth-of-type(2)", timeout=60000)
        except Exception as e:
            print("Note on Turn 1 wait:", e)
        await asyncio.sleep(6)
        
        # Turn 2: "Show a diagnosis card for the OOMKilled worker pod with a cluster diagram."
        turn_2 = "Show a diagnosis card for the OOMKilled worker pod with a cluster diagram."
        print(f"Submitting Turn 2: {turn_2}")
        await input_el.fill(turn_2)
        await asyncio.sleep(1.5)
        await page.keyboard.press("Enter")
        
        # Wait 30000ms as explicitly requested
        print("Waiting 30000ms for diagram generation turn...")
        await asyncio.sleep(30)
        
        # Ensure scroll to bottom to view rendered card and diagram
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
        await asyncio.sleep(6)
        
        await context.close()
        await browser.close()
        print("Playwright recording finished successfully.")

if __name__ == "__main__":
    asyncio.run(record())
