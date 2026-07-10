from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json
import random
import os
import requests
import base64
import time

import os

# Gemini API Configuration
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

@login_required
def design_lab(request):
    return render(request, 'mockups/design_lab.html')

@login_required
def ai_smart_generate(request):
    """
    Real-time AI Analysis using Gemini 1.5 Flash.
    Sends the design to Gemini to get smart placement and SEO data.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_raw = data.get('image_data')
            
            if not image_raw:
                return JsonResponse({"status": "error", "message": "No image data provided"}, status=400)
            
            # Extract Mime Type and Base64 Data
            mime_type = "image/png"
            image_b64 = image_raw
            if 'data:' in image_raw and ';base64,' in image_raw:
                header, image_b64 = image_raw.split(';base64,')
                mime_type = header.replace('data:', '')

            payload = {
                "contents": [{
                    "parts": [
                        {"text": "Analyze this T-shirt design image. You must return ONLY a raw JSON object. NO markdown, NO code blocks. The JSON must contain: 'niche' (string), 'recommended_placement' (object: 'scale' (number 150-250), 'x' (300), 'y' (number 280-420)), 'seo_tags' (array of 5), 'color_palette' (array of 3 hex), 'ai_caption' (string)."},
                        {
                            "inline_data": {
                                "mimeType": mime_type,
                                "data": image_b64
                            }
                        }
                    ]
                }],
                "generationConfig": {
                    "responseMimeType": "application/json",
                }
            }

            response = requests.post(GEMINI_URL, json=payload)
            response_data = response.json()
            
            if 'candidates' in response_data and response_data['candidates'][0]['content']['parts']:
                content_text = response_data['candidates'][0]['content']['parts'][0]['text']
                content_text = content_text.replace('```json', '').replace('```', '').strip()
                
                try:
                    ai_insights = json.loads(content_text)
                    return JsonResponse({
                        "status": "success",
                        "ai_insights": ai_insights
                    })
                except json.JSONDecodeError:
                    return JsonResponse({"status": "error", "message": "Invalid JSON returned from AI", "raw": content_text}, status=500)
            
            elif 'error' in response_data:
                err_msg = response_data['error'].get('message', 'Unknown API Error')
                if 'API key not valid' in err_msg:
                    err_msg = "Invalid API Key. Please check the key you provided."
                return JsonResponse({"status": "error", "message": f"Gemini API Error: {err_msg}"}, status=500)
            
            else:
                candidate = response_data.get('candidates', [{}])[0]
                finish_reason = candidate.get('finishReason', 'UNKNOWN')
                msg = f"AI Blocked/Failed. Reason: {finish_reason}"
                return JsonResponse({"status": "error", "message": msg}, status=500)

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    
    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=400)

@login_required
def get_ai_suggestions(request):
    suggestions = [
        {
            "title": "Retro Aesthetic",
            "text": "Your design has a great focal point. Try adding a 'Distressed' texture and using a 70s color palette for a vintage Etsy look."
        },
        {
            "title": "Social Media Hook",
            "text": "For TikTok/Instagram Reels, use a 'Process' video showing this design on the white mockup. It's currently trending."
        }
    ]
    selected = random.sample(suggestions, 2)
    return JsonResponse({"status": "success", "suggestions": selected})

@login_required
def generate_mockup_api(request):
    """
    Real-time Mockup Generation with temporary diagnostic logging.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            product_type = data.get('product_type', 't-shirt')
            custom_instructions = data.get('custom_instructions', '')
            label = data.get('label', '')

            prompt = f"A professional, photorealistic mockup of a blank, empty, unpatterned white {product_type}. Studio lighting, clean minimal background, realistic fabric folds, shadows, highly detailed, 8k resolution."
            if custom_instructions:
                prompt += f" Style details: {custom_instructions}"

            api_key = GEMINI_API_KEY
            log_data = []

            # ----------------------------------------------------
            # Attempt 1: Legacy Imagen 3 (imagen-3.0-generate-002)
            # ----------------------------------------------------
            url1 = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={api_key}"
            payload1 = {
                "instances": [{"prompt": prompt}],
                "parameters": {
                    "sampleCount": 1,
                    "aspectRatio": "1:1",
                    "outputMimeType": "image/jpeg"
                }
            }
            log_data.append("=== ATTEMPT 1: imagen-3.0-generate-002:predict ===")
            log_data.append(f"URL: {url1.split('?')[0]}")
            log_data.append(f"Payload: {json.dumps(payload1)}")
            try:
                res1 = requests.post(url1, json=payload1, headers={"Content-Type": "application/json"}, timeout=20)
                log_data.append(f"Status Code: {res1.status_code}")
                log_data.append(f"Response: {res1.text[:2000]}")
            except Exception as e:
                log_data.append(f"Exception: {str(e)}")

            # ----------------------------------------------------
            # Attempt 2: New Gemini 3.1 Flash Image
            # ----------------------------------------------------
            url2 = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image:generateContent?key={api_key}"
            payload2 = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "responseModalities": ["IMAGE"]
                }
            }
            log_data.append("\n=== ATTEMPT 2: gemini-3.1-flash-image:generateContent ===")
            log_data.append(f"URL: {url2.split('?')[0]}")
            log_data.append(f"Payload: {json.dumps(payload2)}")
            try:
                res2 = requests.post(url2, json=payload2, headers={"Content-Type": "application/json"}, timeout=20)
                log_data.append(f"Status Code: {res2.status_code}")
                log_data.append(f"Response: {res2.text[:2000]}")
            except Exception as e:
                log_data.append(f"Exception: {str(e)}")

            # Write logs to file
            log_filepath = r"e:\etsy related product\diagnosis.log"
            with open(log_filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(log_data))

            # Return fallback for now so the UI doesn't break during diagnosis
            templates = {
                "t-shirt": [
                    "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?q=80&w=800&auto=format&fit=crop"
                ],
                "default": [
                    "https://images.unsplash.com/photo-1513364776144-60967b0f800f?q=80&w=800&auto=format&fit=crop"
                ]
            }
            ptype = product_type.lower()
            pool = templates.get(ptype, templates['default'])
            selected_url = random.choice(pool)

            return JsonResponse({
                "status": "success",
                "image_url": selected_url,
                "label": label + " (Template Fallback - Diagnosing)"
            })

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    
    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=400)
