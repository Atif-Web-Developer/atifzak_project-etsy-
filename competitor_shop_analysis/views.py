import pandas as pd
import io
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import CompetitorCategory, CompetitorShop, CompetitorShopData
from keywords.models import KeywordSearch, KeywordResult

@login_required
def dashboard_view(request):
    categories = CompetitorCategory.objects.filter(user=request.user).prefetch_related('shops')
    
    active_shop = None
    shop_id = request.GET.get('shop_id')
    if shop_id:
        active_shop = get_object_or_404(CompetitorShop, id=shop_id, category__user=request.user)
        # Populate session data for AJAX filters (like Rank Optimizer)
        results = CompetitorShopData.objects.filter(shop=active_shop)
        data_list = []
        for r in results:
            data_list.append({
                'id': r.id,
                'keyword': r.keyword,
                'volume': r.volume,
                'competition': r.competition,
                'is_favorite': r.is_favorite
            })
        request.session['competitor_shop_data'] = data_list
        request.session['competitor_shop_name'] = active_shop.name
        request.session.modified = True

    return render(request, 'competitor_shop_analysis/dashboard.html', {
        'categories': categories,
        'active_shop': active_shop,
    })

@login_required
@require_POST
def add_category_view(request):
    category_name = request.POST.get('category_name')
    if category_name:
        CompetitorCategory.objects.get_or_create(user=request.user, name=category_name)
        return redirect('competitor_shop_dashboard')
    return redirect('competitor_shop_dashboard')

@login_required
@require_POST
def add_shop_view(request):
    category_id = request.POST.get('category_id')
    shop_name = request.POST.get('shop_name')
    file = request.FILES.get('file')
    
    if category_id and shop_name:
        category = get_object_or_404(CompetitorCategory, id=category_id, user=request.user)
        shop, created = CompetitorShop.objects.get_or_create(category=category, name=shop_name)
        
        if file:
            filename = file.name.lower()
            try:
                if filename.endswith('.csv'):
                    df = pd.read_csv(file)
                elif filename.endswith('.xlsx'):
                    df = pd.read_excel(file)
                else:
                    return redirect(f"/competitor_shops/?shop_id={shop.id}")

                columns = [str(c).lower().strip() for c in df.columns]
                keyword_col = None
                volume_col = None
                comp_col = None

                for col in df.columns:
                    lower_col = str(col).lower().strip()
                    if not keyword_col and lower_col in ['keyword', 'keywords', 'term', 'search term']:
                        keyword_col = col
                    if not volume_col and lower_col in ['volume', 'search volume', 'average searches', 'searches', 'avg searches', 'avg. searches']:
                        volume_col = col
                    if not comp_col and lower_col in ['competition', 'comp', 'etsy competition']:
                        comp_col = col

                if keyword_col:
                    data_list = []
                    for index, row in df.iterrows():
                        keyword = str(row.get(keyword_col, '')).strip()
                        if not keyword or keyword == 'nan':
                            continue
                            
                        try:
                            volume_raw = str(row.get(volume_col, 0) if volume_col else 0).replace(',', '')
                            volume = int(float(volume_raw)) if volume_raw and volume_raw.replace('.', '', 1).isdigit() else 0
                        except:
                            volume = 0

                        try:
                            comp_raw = str(row.get(comp_col, 0) if comp_col else 0).replace(',', '')
                            comp = int(float(comp_raw)) if comp_raw and comp_raw.replace('.', '', 1).isdigit() else 0
                        except:
                            comp = 0
                        
                        data_list.append(CompetitorShopData(
                            shop=shop,
                            keyword=keyword,
                            volume=volume,
                            competition=comp
                        ))

                    # Clear old data if exists
                    CompetitorShopData.objects.filter(shop=shop).delete()
                    CompetitorShopData.objects.bulk_create(data_list)

            except Exception as e:
                pass # Silent fail if file parsing fails in this direct flow, or we could handle it via messages
                
        return redirect(f"/competitor_shops/?shop_id={shop.id}")
        
    return redirect('competitor_shop_dashboard')

@login_required
@require_POST
def upload_csv_view(request):
    file = request.FILES.get('file')
    shop_id = request.POST.get('shop_id')
    
    if not file or not shop_id:
        return JsonResponse({'error': 'No file uploaded or shop not selected'}, status=400)
    
    shop = get_object_or_404(CompetitorShop, id=shop_id, category__user=request.user)
    
    filename = file.name.lower()
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(file)
        elif filename.endswith('.xlsx'):
            df = pd.read_excel(file)
        else:
            return JsonResponse({'error': 'Unsupported file format'}, status=400)

        columns = [str(c).lower().strip() for c in df.columns]
        keyword_col = None
        volume_col = None
        comp_col = None

        for col in df.columns:
            lower_col = str(col).lower().strip()
            if not keyword_col and lower_col in ['keyword', 'keywords', 'term', 'search term']:
                keyword_col = col
            if not volume_col and lower_col in ['volume', 'search volume', 'average searches', 'searches', 'avg searches', 'avg. searches']:
                volume_col = col
            if not comp_col and lower_col in ['competition', 'comp', 'etsy competition']:
                comp_col = col

        if not keyword_col:
            return JsonResponse({'error': 'Could not detect Keyword column'}, status=400)

        data_list = []
        for index, row in df.iterrows():
            keyword = str(row.get(keyword_col, '')).strip()
            if not keyword or keyword == 'nan':
                continue
                
            try:
                volume_raw = str(row.get(volume_col, 0) if volume_col else 0).replace(',', '')
                volume = int(float(volume_raw)) if volume_raw and volume_raw.replace('.', '', 1).isdigit() else 0
            except:
                volume = 0

            try:
                comp_raw = str(row.get(comp_col, 0) if comp_col else 0).replace(',', '')
                comp = int(float(comp_raw)) if comp_raw and comp_raw.replace('.', '', 1).isdigit() else 0
            except:
                comp = 0
            
            data_list.append({
                'keyword': keyword,
                'volume': volume,
                'competition': comp
            })

        # Preserve existing favorites if any
        existing_favs = set(CompetitorShopData.objects.filter(shop=shop, is_favorite=True).values_list('keyword', flat=True))
        
        # Clear old data
        CompetitorShopData.objects.filter(shop=shop).delete()
        
        results_to_create = []
        for d in data_list:
            results_to_create.append(CompetitorShopData(
                shop=shop,
                keyword=d['keyword'],
                volume=d['volume'],
                competition=d['competition'],
                is_favorite=(d['keyword'] in existing_favs)
            ))
        CompetitorShopData.objects.bulk_create(results_to_create)

        # Refresh to get IDs
        created_results = CompetitorShopData.objects.filter(shop=shop)
        final_data_list = []
        for r in created_results:
            final_data_list.append({
                'id': r.id,
                'keyword': r.keyword,
                'volume': r.volume,
                'competition': r.competition,
                'is_favorite': r.is_favorite
            })

        request.session['competitor_shop_data'] = final_data_list
        request.session['competitor_shop_name'] = shop.name
        request.session.modified = True

        return JsonResponse({'message': 'success', 'total': len(final_data_list)})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def add_shop_upload_ajax(request):
    try:
        category_id = request.POST.get('category_id')
        shop_name = request.POST.get('shop_name')
        file = request.FILES.get('file')

        if not category_id or not shop_name or not file:
            return JsonResponse({'error': 'Missing required fields'}, status=400)

        category = get_object_or_404(CompetitorCategory, id=category_id, user=request.user)
        shop, created = CompetitorShop.objects.get_or_create(category=category, name=shop_name)

        filename = file.name.lower()
        if filename.endswith('.csv'):
            df = pd.read_csv(file)
        elif filename.endswith('.xlsx'):
            df = pd.read_excel(file)
        else:
            return JsonResponse({'error': 'Unsupported file format'}, status=400)

        columns = [str(c).lower().strip() for c in df.columns]
        keyword_col = None
        volume_col = None
        comp_col = None

        for col in df.columns:
            lower_col = str(col).lower().strip()
            if not keyword_col and lower_col in ['keyword', 'keywords', 'term', 'search term']:
                keyword_col = col
            if not volume_col and lower_col in ['volume', 'search volume', 'average searches', 'searches', 'avg searches', 'avg. searches']:
                volume_col = col
            if not comp_col and lower_col in ['competition', 'comp', 'etsy competition']:
                comp_col = col

        if not keyword_col:
            return JsonResponse({'error': 'Could not detect Keyword column'}, status=400)

        data_list = []
        for index, row in df.iterrows():
            keyword = str(row.get(keyword_col, '')).strip()
            if not keyword or keyword == 'nan':
                continue
                
            try:
                volume_raw = str(row.get(volume_col, 0) if volume_col else 0).replace(',', '')
                volume = int(float(volume_raw)) if volume_raw and volume_raw.replace('.', '', 1).isdigit() else 0
            except:
                volume = 0

            try:
                comp_raw = str(row.get(comp_col, 0) if comp_col else 0).replace(',', '')
                comp = int(float(comp_raw)) if comp_raw and comp_raw.replace('.', '', 1).isdigit() else 0
            except:
                comp = 0
            
            data_list.append({
                'keyword': keyword,
                'volume': volume,
                'competition': comp
            })

        CompetitorShopData.objects.filter(shop=shop).delete()
        
        results_to_create = []
        for d in data_list:
            results_to_create.append(CompetitorShopData(
                shop=shop,
                keyword=d['keyword'],
                volume=d['volume'],
                competition=d['competition'],
                is_favorite=False
            ))
        CompetitorShopData.objects.bulk_create(results_to_create)

        return JsonResponse({'message': 'success', 'shop_id': shop.id})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def view_shop_data(request, shop_id):
    pass # Managed via dashboard_view using ?shop_id=

# ---- Category Edit / Delete ----

@login_required
@require_POST
def edit_category_view(request, cat_id):
    category = get_object_or_404(CompetitorCategory, id=cat_id, user=request.user)
    new_name = request.POST.get('category_name', '').strip()
    if new_name:
        category.name = new_name
        category.save()
    return redirect('competitor_shop_dashboard')

@login_required
@require_POST
def delete_category_view(request, cat_id):
    category = get_object_or_404(CompetitorCategory, id=cat_id, user=request.user)
    category.delete()
    # Clear session data if current shop was inside this category
    request.session.pop('competitor_shop_data', None)
    request.session.pop('competitor_shop_name', None)
    request.session.modified = True
    return redirect('competitor_shop_dashboard')

# ---- Shop Edit / Delete ----

@login_required
@require_POST
def edit_shop_view(request, shop_id):
    shop = get_object_or_404(CompetitorShop, id=shop_id, category__user=request.user)
    new_name = request.POST.get('shop_name', '').strip()
    new_cat_id = request.POST.get('category_id', '').strip()
    
    if new_name:
        shop.name = new_name
    if new_cat_id:
        new_cat = get_object_or_404(CompetitorCategory, id=new_cat_id, user=request.user)
        shop.category = new_cat
    shop.save()

    file = request.FILES.get('file')
    if file:
        filename = file.name.lower()
        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(file)
            elif filename.endswith('.xlsx'):
                df = pd.read_excel(file)
            else:
                pass # Just ignore if not supported for now

            if filename.endswith('.csv') or filename.endswith('.xlsx'):
                keyword_col = None
                volume_col = None
                comp_col = None

                for col in df.columns:
                    lower_col = str(col).lower().strip()
                    if not keyword_col and lower_col in ['keyword', 'keywords', 'term', 'search term']:
                        keyword_col = col
                    if not volume_col and lower_col in ['volume', 'search volume', 'average searches', 'searches', 'avg searches', 'avg. searches']:
                        volume_col = col
                    if not comp_col and lower_col in ['competition', 'comp', 'etsy competition']:
                        comp_col = col

                if keyword_col:
                    data_list = []
                    for index, row in df.iterrows():
                        keyword = str(row.get(keyword_col, '')).strip()
                        if not keyword or keyword == 'nan':
                            continue
                            
                        try:
                            volume_raw = str(row.get(volume_col, 0) if volume_col else 0).replace(',', '')
                            volume = int(float(volume_raw)) if volume_raw and volume_raw.replace('.', '', 1).isdigit() else 0
                        except:
                            volume = 0

                        try:
                            comp_raw = str(row.get(comp_col, 0) if comp_col else 0).replace(',', '')
                            comp = int(float(comp_raw)) if comp_raw and comp_raw.replace('.', '', 1).isdigit() else 0
                        except:
                            comp = 0
                        
                        data_list.append({
                            'keyword': keyword,
                            'volume': volume,
                            'competition': comp
                        })

                    # Preserve existing favorites if any
                    existing_favs = set(CompetitorShopData.objects.filter(shop=shop, is_favorite=True).values_list('keyword', flat=True))
                    
                    # Clear old data
                    CompetitorShopData.objects.filter(shop=shop).delete()
                    
                    results_to_create = []
                    for d in data_list:
                        results_to_create.append(CompetitorShopData(
                            shop=shop,
                            keyword=d['keyword'],
                            volume=d['volume'],
                            competition=d['competition'],
                            is_favorite=(d['keyword'] in existing_favs)
                        ))
                    CompetitorShopData.objects.bulk_create(results_to_create)

        except Exception as e:
            pass # Fails silently if file parsing fails in edit

    # Update session if this was the active shop
    if request.session.get('competitor_shop_name') == shop.name or request.session.get('competitor_shop_name') == new_name:
        request.session['competitor_shop_name'] = shop.name
        
        # If active shop was updated, we should also refresh the session data so it reflects immediately
        results = CompetitorShopData.objects.filter(shop=shop)
        final_data_list = []
        for r in results:
            final_data_list.append({
                'id': r.id,
                'keyword': r.keyword,
                'volume': r.volume,
                'competition': r.competition,
                'is_favorite': r.is_favorite
            })
        request.session['competitor_shop_data'] = final_data_list
        request.session.modified = True

    return redirect(f'/competitor_shops/?shop_id={shop.id}')

@login_required
@require_POST
def delete_shop_view(request, shop_id):
    shop = get_object_or_404(CompetitorShop, id=shop_id, category__user=request.user)
    shop.delete()
    # Clear session data if this was the active shop
    if request.session.get('competitor_shop_name') == shop.name:
        request.session.pop('competitor_shop_data', None)
        request.session.pop('competitor_shop_name', None)
        request.session.modified = True
    return redirect('competitor_shop_dashboard')

@login_required
def filter_shop_data_ajax(request):
    data = request.session.get('competitor_shop_data', [])
    if not data:
        return JsonResponse({'data': [], 'total': 0, 'golden_count': 0, 'low_comp_count': 0})

    min_vol = request.GET.get('min_volume', 500)
    max_comp = request.GET.get('max_competition', '')
    status_filter = request.GET.get('status', 'All')
    include_words = request.GET.get('include', '').lower().strip()
    exclude_words = request.GET.get('exclude', '').lower().strip()
    search_query = request.GET.get('search', '').lower().strip()
    
    green_limit = request.GET.get('green_limit', 15000)
    yellow_limit = request.GET.get('yellow_limit', 50000)

    try: min_vol = int(min_vol)
    except: min_vol = 0
    
    try: max_comp = int(max_comp) if max_comp else 99999999
    except: max_comp = 99999999
        
    try: green_limit = int(green_limit)
    except: green_limit = 15000
        
    try: yellow_limit = int(yellow_limit)
    except: yellow_limit = 50000

    inc_words_list = [w.strip() for w in include_words.split(',')] if include_words else []
    exc_words_list = [w.strip() for w in exclude_words.split(',')] if exclude_words else []

    filtered_data = []
    golden_count = 0
    low_comp_count = 0

    for item in data:
        vol = item['volume']
        comp = item['competition']
        
        if vol < min_vol: continue
        if comp > max_comp: continue
        
        if comp <= green_limit:
            color = 'green'
        elif comp <= yellow_limit:
            color = 'yellow'
        else:
            color = 'red'

        if vol >= 2000 and comp <= 5000:
            status = 'Golden'
        elif color == 'green':
            status = 'Good'
        else:
            status = 'Hard'

        if status_filter != 'All' and status != status_filter:
            continue

        k_lower = item['keyword'].lower()
        if search_query and search_query not in k_lower:
            continue
        if inc_words_list and not any(w in k_lower for w in inc_words_list):
            continue
        if exc_words_list and any(w in k_lower for w in exc_words_list):
            continue

        new_item = item.copy()
        new_item['color'] = color
        new_item['status'] = status
        
        filtered_data.append(new_item)
        if status == 'Golden':
            golden_count += 1
        if color == 'green':
            low_comp_count += 1

    # sort by competition ASC by default
    filtered_data.sort(key=lambda x: (x['competition'], -x['volume']))

    request.session['competitor_shop_filtered'] = filtered_data
    request.session.modified = True

    return JsonResponse({
        'data': filtered_data,
        'total': len(filtered_data),
        'golden_count': golden_count,
        'low_comp_count': low_comp_count
    })

@login_required
@require_POST
def toggle_favorite_ajax(request):
    try:
        item_id = request.POST.get('id')
        if not item_id:
            return JsonResponse({'error': 'No ID provided'}, status=400)

        data_obj = get_object_or_404(CompetitorShopData, id=item_id, shop__category__user=request.user)
        data_obj.is_favorite = not data_obj.is_favorite
        data_obj.save()

        # Handle global KeywordVault sync
        # So user knows which shop and category the keyword came from
        parent_term = f"Competitor Shop: {data_obj.shop.name}"
        search_obj, _ = KeywordSearch.objects.get_or_create(term=parent_term, user=request.user)
        
        if data_obj.is_favorite:
            # Create or update in vault
            KeywordResult.objects.update_or_create(
                search=search_obj,
                keyword=data_obj.keyword.title(),
                defaults={
                    'avg_searches': data_obj.volume,
                    'competition': data_obj.competition,
                    'category': f"Cat: {data_obj.shop.category.name}",
                    'is_favorite': True
                }
            )
        else:
            # Remove from vault if unfavorited
            KeywordResult.objects.filter(search=search_obj, keyword=data_obj.keyword.title()).delete()

        # Update session data so it reflects immediately without reload
        session_data = request.session.get('competitor_shop_data', [])
        for item in session_data:
            if str(item['id']) == str(item_id):
                item['is_favorite'] = data_obj.is_favorite
                break
        request.session['competitor_shop_data'] = session_data
        
        filtered_data = request.session.get('competitor_shop_filtered', [])
        for item in filtered_data:
            if str(item['id']) == str(item_id):
                item['is_favorite'] = data_obj.is_favorite
                break
        request.session['competitor_shop_filtered'] = filtered_data
        request.session.modified = True

        return JsonResponse({'status': 'success', 'is_favorite': data_obj.is_favorite})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def export_shop_data_csv(request):
    filtered_data = request.session.get('competitor_shop_filtered', [])
    if not filtered_data:
        return HttpResponse("No data to export.", status=400)

    df = pd.DataFrame(filtered_data)
    
    output = io.StringIO()
    df.to_csv(output, index=False)
    
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="competitor_shop_data.csv"'
    return response
