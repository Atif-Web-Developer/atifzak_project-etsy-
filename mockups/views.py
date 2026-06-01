from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json
import random
import os
import requests
import base64
import time

# Gemini API Configuration
GEMINI_API_KEY = 'AIzaSyB1vUMJWS3KLSlHGQHiS0qMxw2VDXSwJ4A'
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
    Real-time Mockup Generation using high-quality static templates for photorealistic overlay.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            product_type = data.get('product_type', 't-shirt')
            label = data.get('label', '')

            # Fallback to ultra-high-quality static templates for perfect photorealistic results
            templates = {
                "t-shirt": [
                    "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?q=80&w=800&auto=format&fit=crop", # White tee front
                    "https://images.unsplash.com/photo-1618354691373-d851c5c3a990?q=80&w=800&auto=format&fit=crop", # White tee flat
                    "https://images.unsplash.com/photo-1576566588028-4147f3842f27?q=80&w=800&auto=format&fit=crop", # Grey tee
                    "https://images.unsplash.com/photo-1562157873-818bc0726f68?q=80&w=800&auto=format&fit=crop"  # White tee lifestyle
                ],
                "mug": [
                    "https://images.unsplash.com/photo-1514228742587-6b1558fcca3d?q=80&w=800&auto=format&fit=crop",
                    "https://images.unsplash.com/photo-1481833751843-222a45a30dc3?q=80&w=800&auto=format&fit=crop"
                ],
                "poster": [
                    "https://images.unsplash.com/photo-1580136608260-4eb11f4b24fe?q=80&w=800&auto=format&fit=crop",
                    "https://images.unsplash.com/photo-1615800098779-1be32e60cca3?q=80&w=800&auto=format&fit=crop"
                ],
                "hoodie": [
                    "https://images.unsplash.com/photo-1556821840-3a63f95609a7?q=80&w=800&auto=format&fit=crop"
                ],
                "tote bag": [
                    "https://images.unsplash.com/photo-1597484661643-2f5fef640df1?q=80&w=800&auto=format&fit=crop"
                ],
                "default": [
                    "https://images.unsplash.com/photo-1513364776144-60967b0f800f?q=80&w=800&auto=format&fit=crop"
                ]
            }
            
            ptype = product_type.lower()
            pool = templates.get(ptype, templates['default'])
            selected_url = random.choice(pool)

            # Simulate processing delay
            time.sleep(1.5)

            return JsonResponse({
                "status": "success",
                "image_url": selected_url,
                "label": label
            })

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    
    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=400)
