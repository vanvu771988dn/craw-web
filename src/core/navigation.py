# src/core/navigation.py
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from playwright.async_api import Page, TimeoutError

async def handle_navigation(page: "Page", url: str, config: dict):
    """Handles page navigation with configurable redirect strategies."""
    navigation_timeout = config.get("crawler", {}).get("navigation_timeout", 30000)
    redirect_config = config.get("crawler", {}).get("redirect", {"enabled": False, "strategy": "auto"})

    try:
        if not redirect_config.get("enabled"):
            print("Redirects disabled. Loading page directly.")
            await page.goto(url, wait_until="domcontentloaded", timeout=navigation_timeout)
        
        elif redirect_config.get("strategy") == "auto":
            print("Auto-redirect enabled. Waiting for navigation to complete...")
            await page.goto(url, wait_until="domcontentloaded", timeout=navigation_timeout)
            landed_url = page.url
            
            try:
                print(f"Landed on {landed_url}. Checking for client-side redirect...")
                # Wait for a potential client-side redirect by checking if the URL changes again.
                await page.wait_for_url(lambda current_url: current_url != landed_url, timeout=navigation_timeout)
                print("Client-side redirect detected. Waiting for new page to load...")
                # Use 'load' state which is more reliable than 'networkidle' for ad-heavy pages.
                await page.wait_for_load_state("load", timeout=navigation_timeout)
            except TimeoutError:
                print("No further client-side redirect detected.")
        
        elif redirect_config.get("strategy") == "button_click":
            print("Button-click redirect enabled. Loading initial page...")
            await page.goto(url, wait_until="domcontentloaded", timeout=navigation_timeout)
            
            button_selector = redirect_config.get("button_selector")
            if button_selector:
                
                button = page.locator(button_selector).first
                if await button.is_visible(timeout=5000):
                    print(f"Interactive redirect button found ('{button_selector}'). Clicking...")
                    async with page.expect_navigation(wait_until="networkidle", timeout=navigation_timeout):
                        await button.click()
                    print("Navigation after click successful.")
                else:
                    print(f"Button ('{button_selector}') not visible. Proceeding without click.")
                
            else:
                print("Warning: button_click strategy is set, but no button_selector is provided in config.")

    except TimeoutError:
        print(f"Navigation to {url} timed out after {navigation_timeout}ms.")
        raise

    final_url = page.url
    if url != final_url:
        print(f"Redirection handled. Final URL: {final_url}")
    else:
        print(f"Page loaded without redirection. URL: {final_url}")
