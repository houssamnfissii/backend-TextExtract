from flask import Flask, request, jsonify
from flask_cors import CORS
from playwright.sync_api import sync_playwright
import time
import logging
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_text_only(url):
    start_time = time.time()
    try:
        with sync_playwright() as p:
            # Launch browser with aggressive optimizations
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-images",
                    "--disable-stylesheets",
                    "--disable-fonts",
                    "--disable-javascript",
                    "--no-sandbox",
                    "--disable-dev-shm-usage"
                ]
            )
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                viewport={"width": 1280, "height": 720},
                java_script_enabled=False,  # Disable JS for speed
                bypass_csp=True
            )
            
            # Block ALL non-essential resources
            def block_all(route):
                if route.request.resource_type not in {"document", "xhr", "fetch"}:
                    route.abort()
                else:
                    route.continue_()
            
            context.route("**/*", block_all)
            
            page = context.new_page()

            # Navigate with minimal waiting
            logger.info(f"Loading: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=15000)  # Faster than networkidle

            # Extract text immediately without scrolling
            logger.info("Extracting raw text...")
            text_content = page.evaluate("""() => {
                // Remove all non-text elements
                const removals = ['script', 'style', 'noscript', 'iframe', 
                                'svg', 'nav', 'footer', 'header', 'form',
                                'img', 'picture', 'video', 'audio', 'canvas'];
                
                removals.forEach(tag => {
                    document.querySelectorAll(tag).forEach(el => el.remove());
                });
                
                // Get text from body
                return document.body.innerText;
            }""")

            browser.close()

            # Fast text cleaning
            clean_text = '\n'.join([line.strip() for line in text_content.split('\n') if line.strip()])
            
            return {
                "content": clean_text,
                "word_count": len(clean_text.split()),
                "status": "success",
                "processing_time": time.time() - start_time
            }
            
    except Exception as e:
        return {
            "error": str(e),
            "status": "failed",
            "processing_time": time.time() - start_time
        }

@app.route('/extract', methods=['POST'])
def extract():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "URL required", "status": "failed"}), 400
    
    url = data['url'].strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    result = extract_text_only(url)
    return jsonify(result), 200 if result["status"] == "success" else 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)