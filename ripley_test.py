# -*- coding: utf-8 -*-
# ------------------------------------------------------------
# ripley_test.py
# Versión para GitHub Actions · SIN envío de correo
# ------------------------------------------------------------

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import re
from datetime import datetime
import traceback
import random
import time

# ---------------------------------------
# Config scraping
# ---------------------------------------

URL = "https://simple.ripley.cl/tecno/computacion/notebooks?s=mdco&type=catalog"

BRANDS = ["asus", "hp", "lenovo", "dell", "samsung", "acer", "huawei", "apple"]
TARGET_BRAND = "asus"

TRACKING_PATTERNS = ["utm_", "mai=", "gclid=", "fbclid=", "mc_eid=", "icid="]

# Para GitHub Actions: siempre headless
HEADLESS = True

# ---------------------------------------
# User Agents
# ---------------------------------------

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

# ---------------------------------------
# Stealth JavaScript
# ---------------------------------------

STEALTH_JS = """
() => {
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });
    
    delete navigator.__proto__.webdriver;
    
    Object.defineProperty(navigator, 'plugins', {
        get: () => [
            {
                0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                description: "Portable Document Format",
                filename: "internal-pdf-viewer",
                length: 1,
                name: "Chrome PDF Plugin"
            }
        ]
    });
    
    Object.defineProperty(navigator, 'languages', {
        get: () => ['es-CL', 'es', 'en-US', 'en']
    });
    
    window.chrome = {
        runtime: {},
        loadTimes: function() {},
        csi: function() {},
        app: {}
    };
    
    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => 8
    });
    
    Object.defineProperty(navigator, 'deviceMemory', {
        get: () => 8
    });
    
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
}
"""

# ---------------------------------------
# Utilidades
# ---------------------------------------

def strip_html(html: str) -> str:
    html = re.sub(r"<script.*?>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style.*?>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html).strip()


def detect_brand(text: str, href: str) -> str | None:
    blob = f"{text} {href}".lower()
    found = [b for b in BRANDS if b in blob]
    if not found:
        return None
    if TARGET_BRAND in found:
        return TARGET_BRAND
    return found[0]


def extract_prices(fragment: str):
    internet_price = None
    card_price = None

    m1 = re.search(
        r'<li[^>]*catalog-prices__offer-price[^>]*>\s*(\$[\d\.\,]+)',
        fragment,
        flags=re.IGNORECASE
    )
    if m1:
        internet_price = m1.group(1)

    m2 = re.search(
        r'<li[^>]*catalog-prices__card-price[^>]*>\s*(\$[\d\.\,]+)',
        fragment,
        flags=re.IGNORECASE
    )
    if m2:
        card_price = m2.group(1)

    return internet_price or "N/A", card_price or "N/A"


def is_tracking_href(href: str) -> bool:
    href_lower = href.lower()
    return any(pat in href_lower for pat in TRACKING_PATTERNS)


def random_sleep(min_sec=1, max_sec=3):
    time.sleep(random.uniform(min_sec, max_sec))


def human_like_mouse_movement(page):
    try:
        for _ in range(random.randint(2, 4)):
            x = random.randint(100, 1200)
            y = random.randint(100, 700)
            page.mouse.move(x, y, steps=random.randint(10, 30))
            time.sleep(random.uniform(0.1, 0.3))
    except Exception:
        pass


def try_solve_cloudflare_captcha(page):
    """Intento básico de interactuar con el desafío (solo logging, puede fallar)."""
    print("🤖 Buscando CAPTCHA de Cloudflare...")
    try:
        random_sleep(2, 3)
        iframe_found = False
        captcha_frame = None

        frames = page.frames
        print(f"🔍 Total de frames: {len(frames)}")

        for idx, frame in enumerate(frames):
            try:
                frame_url = frame.url
                print(f"   Frame {idx}: {frame_url[:80]}")
                if 'cloudflare' in frame_url.lower() or 'challenges' in frame_url.lower() or 'turnstile' in frame_url.lower():
                    captcha_frame = frame
                    iframe_found = True
                    print("✅ Frame de Cloudflare encontrado!")
                    break
            except Exception:
                continue

        if not iframe_found:
            print("⚠️ No se encontró iframe directamente, buscando con JS...")
            iframe_js = """
            () => {
                const iframes = document.querySelectorAll('iframe');
                for (let iframe of iframes) {
                    if (iframe.src.includes('cloudflare') || iframe.src.includes('challenges')) {
                        return iframe.src;
                    }
                }
                return null;
            }
            """
            iframe_src = page.evaluate(iframe_js)
            if iframe_src:
                print(f"✅ Iframe encontrado: {iframe_src[:60]}")
                for frame in page.frames:
                    if frame.url == iframe_src:
                        captcha_frame = frame
                        iframe_found = True
                        break

        if not iframe_found or not captcha_frame:
            print("❌ No se pudo localizar iframe de challenge")
            return False

        print("🎯 Buscando checkbox en el iframe...")
        random_sleep(1, 2)

        checkbox_selectors = [
            'input[type="checkbox"]',
            '.cb-lb',
            'label.ctp-checkbox-label',
            'span.cb-lb',
            '#challenge-stage input',
            'div.cb-c input',
            'label[for*="cf"]',
        ]

        for selector in checkbox_selectors:
            try:
                checkbox = captcha_frame.query_selector(selector)
                if checkbox:
                    print(f"✅ Checkbox encontrado: {selector}")
                    captcha_frame.evaluate(f"""
                        (selector) => {{
                            const el = document.querySelector('{selector}');
                            if (el) {{
                                el.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                            }}
                        }}
                    """)
                    random_sleep(0.5, 1)

                    box = checkbox.bounding_box()
                    if box:
                        center_x = box['x'] + box['width'] / 2
                        center_y = box['y'] + box['height'] / 2
                        page.mouse.move(center_x, center_y, steps=25)
                        random_sleep(0.3, 0.6)
                        checkbox.click(delay=random.randint(50, 120), force=True)
                        print("✅ Click ejecutado!")
                        random_sleep(3, 5)
                        return True
                    else:
                        checkbox.click(delay=random.randint(50, 120), force=True)
                        print("✅ Click directo ejecutado!")
                        random_sleep(3, 5)
                        return True
            except Exception as e:
                print(f"   ⚠️ Error con {selector}: {str(e)[:50]}")
                continue

        print("🔧 Intentando click via JavaScript...")
        click_js = """
        () => {
            try {
                const wrapper = document.querySelector('div.main-wrapper') ||
                                document.querySelector('#content');
                if (!wrapper) return 'wrapper_not_found';

                const labels = wrapper.querySelectorAll('label, .cb-lb, span.cb-lb');
                if (labels.length > 0) {
                    labels[0].click();
                    return 'clicked_label';
                }

                return 'not_found';
            } catch (e) {
                return 'error: ' + e.message;
            }
        }
        """
        result = captcha_frame.evaluate(click_js)
        print(f"   Resultado JS: {result}")

        if 'clicked' in str(result):
            print("✅ Click via JavaScript!")
            random_sleep(3, 5)
            return True

        print("🎲 Intentando por coordenadas aproximadas...")
        try:
            viewport = page.viewport_size
            center_x = viewport['width'] / 2
            center_y = viewport['height'] / 2
            page.mouse.move(center_x - 50, center_y, steps=20)
            random_sleep(0.3, 0.5)
            page.mouse.click(center_x - 50, center_y, delay=random.randint(50, 100))
            print("✅ Click por coordenadas!")
            random_sleep(3, 5)
            return True
        except Exception as e:
            print(f"   ❌ Error coordenadas: {str(e)}")

        return False

    except Exception as e:
        print(f"❌ Error general en try_solve_cloudflare_captcha: {str(e)}")
        return False


# ---------------------------------------
# Scraping principal
# ---------------------------------------

def run_scraper():
    print("="*60)
    print("🚀 RIPLEY SCRAPER - GitHub Actions (sin email)")
    print(f"🕐 Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    print(f"\n📍 URL: {URL}")
    print(f"🎯 Marca objetivo: {TARGET_BRAND.upper()}")
    print(f"👁️  Modo: {'HEADLESS' if HEADLESS else 'VISIBLE'}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-size=1920,1080",
            ],
        )

        user_agent = random.choice(USER_AGENTS)

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=user_agent,
            locale="es-CL",
            timezone_id="America/Santiago",
            geolocation={"longitude": -70.6693, "latitude": -33.4489},
            permissions=["geolocation"],
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "es-CL,es;q=0.9,en;q=0.7",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

        page = context.new_page()
        page.add_init_script(STEALTH_JS)
        page.set_default_timeout(120000)

        print("🔒 Stealth mode activado")
        print(f"🌐 User Agent: {user_agent[:60]}...\n")

        try:
            random_sleep(2, 3)
            print("📡 Conectando a Ripley...\n")

            page.goto(URL, wait_until="domcontentloaded", timeout=120000)
            random_sleep(5, 7)

            page_content = page.content().lower()
            is_captcha = any(word in page_content for word in ['cloudflare', 'captcha', 'verifica que eres', 'challenge'])

            if is_captcha:
                print("⚠️ CAPTCHA DETECTADO!\n")
                for attempt in range(3):
                    print(f"🔄 Intento {attempt + 1}/3 de resolver...\n")
                    success = try_solve_cloudflare_captcha(page)
                    if success:
                        print("\n✅ Esperando validación...\n")
                        random_sleep(6, 9)
                        new_content = page.content().lower()
                        if not any(word in new_content for word in ['cloudflare', 'verifica que eres']):
                            print("🎉 ¡CAPTCHA RESUELTO!\n")
                            break
                        else:
                            print("⚠️ CAPTCHA aún presente...\n")
                            random_sleep(2, 3)
                    if attempt == 2:
                        print("❌ No se resolvió automáticamente (GitHub seguirá igual)\n")
            else:
                print("✅ No hay CAPTCHA!\n")

            print("⏳ Esperando grilla de productos...\n")
            try:
                page.wait_for_selector("div.catalog-product-border", timeout=30000)
                print("✅ Grilla cargada!\n")
            except PlaywrightTimeout:
                print("⚠️ Timeout esperando grilla\n")
                page.screenshot(path="debug_timeout.png")
                print("📸 Screenshot guardado: debug_timeout.png\n")
                browser.close()
                return

            print("📜 Scrolling página...\n")
            last_height = 0
            scrolls_done = 0

            for scroll in range(20):
                page.evaluate("window.scrollBy(0, 800)")
                random_sleep(1.0, 1.8)

                if scroll % 3 == 0:
                    human_like_mouse_movement(page)

                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
                scrolls_done = scroll + 1

            print(f"✅ Scroll completo ({scrolls_done} iteraciones)\n")
            random_sleep(2, 3)

        except Exception as e:
            print(f"\n❌ ERROR durante navegación: {str(e)}\n")
            page.screenshot(path="error_nav.png")
            print("📸 Screenshot error_nav.png\n")
            browser.close()
            raise

        # Extracción de datos
        print("="*60)
        print("📊 EXTRAYENDO DATOS")
        print("="*60 + "\n")

        anchors = page.query_selector_all("div.catalog-product-border a[href*='2000']")
        print(f"🔧 Anchors encontrados: {len(anchors)}\n")

        sku_infos = {}
        skipped_tracking = skipped_no_sku = skipped_no_price = position = 0
        sku_pattern = re.compile(r"(2000\d+)", re.IGNORECASE)

        for a in anchors:
            href_rel = a.get_attribute("href") or ""
            if is_tracking_href(href_rel):
                skipped_tracking += 1
                continue

            sku_match = sku_pattern.search(href_rel)
            if not sku_match:
                skipped_no_sku += 1
                continue

            sku = sku_match.group(1)
            if sku in sku_infos:
                continue

            try:
                card_html = a.evaluate("node => node.parentElement.innerHTML")
            except Exception:
                continue

            price_internet, price_ripley = extract_prices(card_html)
            if price_internet == "N/A":
                skipped_no_price += 1
                continue

            position += 1
            href = href_rel if href_rel.startswith("http") else f"https://simple.ripley.cl{href_rel}"
            text_clean = strip_html(a.inner_html())
            brand = detect_brand(text_clean, href)

            sku_infos[sku] = {
                "sku": sku,
                "brand": brand,
                "href": href,
                "text": text_clean,
                "position": position,
                "price_internet": price_internet,
                "price_ripley": price_ripley,
            }

        browser.close()

    # Resultados y log final
    all_skus = list(sku_infos.keys())
    total_products = len(all_skus)

    print(f"🔧 Descartados:")
    print(f"   - Por tracking: {skipped_tracking}")
    print(f"   - Sin SKU: {skipped_no_sku}")
    print(f"   - Sin precio: {skipped_no_price}\n")

    if total_products == 0:
        print("❌ No se encontraron SKUs válidos\n")
        print("="*60)
        print("🔚 Fin de ejecución (sin datos suficientes).")
        print("="*60)
        return

    asus_products = [s for s in all_skus if sku_infos[s]["brand"] == TARGET_BRAND]
    share = (len(asus_products) / total_products * 100) if total_products else 0

    print("="*60)
    print("📊 RESULTADOS FINALES")
    print("="*60)
    print(f"✅ Total SKUs válidos: {total_products}")
    print(f"✅ Total ASUS: {len(asus_products)}")
    print(f"📈 Share ASUS: {share:.2f}%\n")

    if asus_products:
        print("📌 MODELOS ASUS ENCONTRADOS:")
        print("-" * 60)
        print(f"{'Pos':<5} | {'SKU':<12} | {'Internet':<12} | {'Tarjeta':<12}")
        print("-" * 60)
        for sku in sorted(asus_products, key=lambda s: sku_infos[s]["position"]):
            info = sku_infos[sku]
            print(f"{info['position']:<5} | {info['sku']:<12} | {info['price_internet']:<12} | {info['price_ripley']:<12}")
            print(f"       Link: {info['href'][:90]}...")
        print("-" * 60)
    else:
        print("⚠️ No se detectaron modelos ASUS\n")

    print(f"\n✔ Proceso completado: {datetime.now().strftime('%H:%M:%S')}")
    print("="*60)


# ---------------------------------------
# Main
# ---------------------------------------

def main():
    try:
        run_scraper()
    except Exception:
        print("\n❌ ERROR FATAL en ripley_test.py\n")
        print(traceback.format_exc())
        print("\n" + "="*60)


if __name__ == "__main__":
    main()
