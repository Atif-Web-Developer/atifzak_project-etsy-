from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json
import re
import requests
import urllib.parse
from bs4 import BeautifulSoup

# API Key Configurations
GEMINI_API_KEY = ''
# Groq Cloud (gsk_...) or OpenAI API Key
GROK_API_KEY = ''
OPENAI_API_KEY = ''

@login_required
def pinterest_tool_view(request):
    return render(request, 'pinterest_seo/pinterest_tool.html')

@login_required
def generate_pinterest_seo(request):
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Invalid request method"}, status=400)
        
    try:
        data = json.loads(request.body)
        listing_url = data.get('listingUrl', '').strip()
        niche = data.get('niche', '').strip()
        
        if not listing_url:
            return JsonResponse({"status": "error", "message": "Etsy Listing URL is required"}, status=400)
            
        # 1. Scrape listing details
        listing_title, listing_description = scrape_etsy_listing(listing_url)
        
        # 2. Call AI Router
        prompt = f"""
You are an expert Pinterest SEO copywriter and e-commerce growth marketer for Etsy sellers.
Analyze these Etsy listing details:
Product Title: "{listing_title}"
Product Description: "{listing_description}"
Product Niche: "{niche if niche else 'E-commerce product'}"

Requirements for the generated content:
1. **Preserve Core Slogans & Quotes**: Do not drop, omit, or generalize unique slogans, quotes, or text printed on the product. For example, if the title contains 'Dad Tax Making Sure Its Not Poison', you MUST include both 'Dad Tax' and 'Making Sure It's Not Poison' in your titles and descriptions.
2. **Pin Title Format**: The Pin Title MUST be structured using search-optimized keyword phrases separated by pipes (`|`). 
   Format: `Product Slogan/Phrase | High-volume Primary Keyword | Target Audience or Gift Occasion Search Phrase`.
   Example title style: `Funny Dad Tax Shirt | Gift for Father's Day | Dad Joke T-Shirt for Men`.
   Length: MUST be detailed, utilizing 70 to 95 characters fully to maximize Pinterest search visibility and indexing.
3. **Pin Description Style**: 
   - MUST be between 300 to 500 characters, extremely SEO-rich, capturing the exact humor, emotion, or value of the product.
   - Start with a strong hook or call to action.
   - Describe who it is for (e.g., Father's Day, birthdays, gifts).
   - End with a direct call to action (e.g., 'Click to visit our Etsy shop and grab this unique gift for him today!') followed by 5 to 10 highly relevant, high-volume Pinterest hashtags.
4. **Pin Alt Text (Accessibility)**:
   - Provide a vivid, minimalist visual description of what is on the t-shirt and the design layout aesthetic (e.g., bold lettering, font style, minimalist text layout) to boost Pinterest visual search and accessibility ranking. Under 250 characters.

You must generate 3 highly optimized, unique Pinterest Pin setups in 3 different styles:
1. High Keyword Relevance (SEO Detailed): Focused on high search volume and precise indexing.
2. High CTR / Viral: Highly engaging, viral style with curiosity-driven hook to maximize click-through rate.
3. Educational / Benefit-Driven: Focused on value, how it helps the customer, and the main benefits.

For each Pin style, you must provide:
- A Pin Title (matching the pipe-separated format above, 70-95 characters).
- A Pin Description (matching the rich description, call to action, and hashtag requirements above).
- A Pin Alt Text (matching the detailed visual search requirements above).

Return ONLY a raw JSON object. Do not wrap the JSON in markdown code blocks, do not write any extra conversational text. Return exactly this JSON structure:
{{
  "high_keyword": {{
    "title": "Pin Title Here",
    "description": "Pin Description with #hashtags here",
    "alt_text": "Pin Alt Text here"
  }},
  "high_ctr": {{
    "title": "Pin Title Here",
    "description": "Pin Description with #hashtags here",
    "alt_text": "Pin Alt Text here"
  }},
  "educational": {{
    "title": "Pin Title Here",
    "description": "Pin Description with #hashtags here",
    "alt_text": "Pin Alt Text here"
  }}
}}
"""
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt}
                ]
            }]
        }
        
        response_content_text = ""
        success = False
        last_error_msg = ""
        
        # 1. Try Groq Cloud if API key is provided
        if GROK_API_KEY:
            try:
                print("Trying Groq Cloud API...")
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {GROK_API_KEY}"
                }
                payload_groq = {
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "model": "llama-3.3-70b-versatile",
                    "temperature": 0.2
                }
                response = requests.post(url, json=payload_groq, headers=headers, timeout=20)
                res_json = response.json()
                if 'choices' in res_json and res_json['choices'][0]['message']['content']:
                    response_content_text = res_json['choices'][0]['message']['content']
                    success = True
                    print("Success! Groq generated the Pinterest SEO content.")
                elif 'error' in res_json:
                    last_error_msg = f"Groq API Error: {res_json['error'].get('message', 'Unknown')}"
                    print(last_error_msg)
            except Exception as e:
                last_error_msg = f"Grok failed: {str(e)}"
                print(last_error_msg)
                
        # 2. Try OpenAI (ChatGPT) if key is provided and Grok didn't run/succeed
        if not success and OPENAI_API_KEY:
            try:
                print("Trying OpenAI API...")
                url = "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {OPENAI_API_KEY}"
                }
                payload_openai = {
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "model": "gpt-4o-mini",
                    "temperature": 0.2
                }
                response = requests.post(url, json=payload_openai, headers=headers, timeout=20)
                res_json = response.json()
                if 'choices' in res_json and res_json['choices'][0]['message']['content']:
                    response_content_text = res_json['choices'][0]['message']['content']
                    success = True
                    print("Success! OpenAI generated the Pinterest SEO content.")
                elif 'error' in res_json:
                    last_error_msg = f"OpenAI API Error: {res_json['error'].get('message', 'Unknown')}"
                    print(last_error_msg)
            except Exception as e:
                last_error_msg = f"OpenAI failed: {str(e)}"
                print(last_error_msg)
                
        # 3. Try Gemini model endpoints as ultimate fallback
        if not success:
            models_and_urls = [
                ("gemini-1.5-flash (v1)", f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"),
                ("gemini-1.5-flash-latest (v1)", f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"),
                ("gemini-1.5-pro (v1)", f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro:generateContent?key={GEMINI_API_KEY}"),
                ("gemini-1.5-flash (v1beta)", f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"),
                ("gemini-1.5-flash-latest (v1beta)", f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"),
                ("gemini-1.5-pro (v1beta)", f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={GEMINI_API_KEY}"),
                ("gemini-2.0-flash-exp (v1beta)", f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"),
                ("gemini-1.0-pro (v1beta)", f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.0-pro:generateContent?key={GEMINI_API_KEY}"),
            ]
            
            for model_name, url in models_and_urls:
                try:
                    print(f"Trying to generate content using model: {model_name}...")
                    response = requests.post(url, json=payload, timeout=20)
                    res_json = response.json()
                    
                    if 'candidates' in res_json and res_json['candidates'][0]['content']['parts']:
                        response_content_text = res_json['candidates'][0]['content']['parts'][0]['text']
                        success = True
                        print(f"Success! Model {model_name} generated the Pinterest SEO content.")
                        break
                    elif 'error' in res_json:
                        last_error_msg = res_json['error'].get('message', 'Unknown API Error')
                        print(f"Model {model_name} returned error: {last_error_msg}")
                    else:
                        last_error_msg = "No candidates or parts returned."
                        print(f"Model {model_name} returned empty candidates.")
                except Exception as e:
                    last_error_msg = str(e)
                    print(f"Request to model {model_name} failed: {e}")
                    
        if success and response_content_text:
            # Clean up potential markdown formatting
            content_text = response_content_text.strip()
            if content_text.startswith("```"):
                content_text = re.sub(r"^```(?:json)?\n", "", content_text)
                content_text = re.sub(r"\n```$", "", content_text)
            content_text = content_text.strip()
            
            try:
                pins_data = json.loads(content_text)
                return JsonResponse({
                    "status": "success",
                    "listing_title": listing_title,
                    "pins": pins_data
                })
            except json.JSONDecodeError:
                return JsonResponse({
                    "status": "error", 
                    "message": "Invalid JSON returned from AI", 
                    "raw": content_text
                }, status=500)
        else:
            return JsonResponse({
                "status": "error", 
                "message": f"All AI model endpoints failed. Last error: {last_error_msg}"
            }, status=500)
            
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

def scrape_etsy_listing(url):
    # Fallback title from slug
    fallback_title = ""
    try:
        parsed_url = urllib.parse.urlparse(url)
        path_parts = [p for p in parsed_url.path.split('/') if p]
        if len(path_parts) >= 3 and path_parts[0] == 'listing':
            slug = path_parts[2]
            fallback_title = slug.replace('-', ' ').replace('_', ' ').strip().title()
        elif len(path_parts) >= 2 and path_parts[0] == 'listing':
            slug = path_parts[1]
            if not slug.isdigit():
                fallback_title = slug.replace('-', ' ').replace('_', ' ').strip().title()
    except Exception as e:
        print(f"Error parsing fallback title: {e}")

    scraped_title = ""
    scraped_description = ""
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, y Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try Title
            title_tag = soup.find("meta", property="og:title")
            if title_tag and title_tag.get("content"):
                scraped_title = title_tag.get("content").strip()
            else:
                title_el = soup.find("title")
                if title_el:
                    scraped_title = title_el.text.strip()
                    if " | Etsy" in scraped_title:
                        scraped_title = scraped_title.split(" | Etsy")[0].strip()
            
            # Try Description
            desc_tag = soup.find("meta", property="og:description")
            if not desc_tag:
                desc_tag = soup.find("meta", name="description")
            if desc_tag and desc_tag.get("content"):
                scraped_description = desc_tag.get("content").strip()
    except Exception as e:
        print(f"Scraping failed: {e}")
        
    final_title = scraped_title or fallback_title or "Etsy Product"
    final_description = scraped_description or "Etsy listing product details"
    return final_title, final_description
