from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import UserCreationForm
from .models import User, KeywordSearch, KeywordResult
from .scraper import scrape_keyword_data
import pandas as pd
import io
from django.http import HttpResponse

def signup_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name', '')
        
        if username and password:
            if User.objects.filter(username=username).exists():
                return render(request, 'keywords/signup.html', {'error': 'Username already exists'})
            
            user = User.objects.create_user(username=username, password=password, first_name=first_name)
            login(request, user)
            return redirect('pending_approval')
    return render(request, 'keywords/signup.html')

def pending_approval_view(request):
    return render(request, 'keywords/pending_approval.html')

@login_required
def dashboard_view(request):
    return render(request, 'keywords/dashboard.html')

@login_required
@require_POST
def upload_csv(request):
    csv_file = request.FILES.get('csv_file')
    if not csv_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    
    if not csv_file.name.endswith('.csv'):
        return JsonResponse({'error': 'File is not CSV'}, status=400)

    try:
        data = pd.read_csv(csv_file)
        # Fill missing values (NaN) with 0 to avoid conversion errors
        data = data.fillna(0)
        
        results = []
        search_obj, _ = KeywordSearch.objects.get_or_create(user=request.user, term=f"Upload_{csv_file.name}")
        existing_favs = set(KeywordResult.objects.filter(search=search_obj, is_favorite=True).values_list('keyword', flat=True))
        KeywordResult.objects.filter(search=search_obj).delete()

        for index, row in data.iterrows():
            # Flexible mapping for eRank column names
            keyword = str(row.get('Keywords', row.get('Keyword', '')))
            
            # Searches mapping
            searches = int(float(row.get('Average Searches', row.get('Avg. Searches', row.get('Searches', 0)))))
            
            # Clicks mapping
            clicks = int(float(row.get('Average Clicks', row.get('Avg. Clicks', row.get('Clicks', 0)))))
            
            # CTR mapping
            ctr_raw = row.get('CTR', row.get('Average CTR', row.get('Avg. CTR', '0')))
            if isinstance(ctr_raw, str):
                ctr = int(float(ctr_raw.replace('%', '')))
            else:
                ctr = int(float(ctr_raw))

            # Competition mapping
            comp = int(float(row.get('Competition', row.get('Etsy Competition', 0))))
            
            # KD mapping
            kd = int(float(row.get('KD', 0)))

            # COLOR LOGIC & PRIORITY
            if comp < 5000 and searches > 1000:
                cat = 'Dark Green'
                priority = 1
            elif comp < 10000:
                cat = 'Light Green'
                priority = 2
            elif comp <= 20000:
                cat = 'Orange'
                priority = 3
            else:
                cat = 'Red'
                priority = 4

            res_obj = KeywordResult.objects.create(
                search=search_obj,
                keyword=keyword,
                avg_searches=searches,
                avg_clicks=clicks,
                avg_ctr=ctr,
                competition=comp,
                kd=kd,
                category=cat,
                is_favorite=(keyword in existing_favs)
            )
            results.append({
                'id': res_obj.id,
                'keyword': keyword,
                'avg_searches': searches,
                'avg_clicks': clicks,
                'avg_ctr': ctr,
                'competition': comp,
                'kd': kd,
                'category': cat,
                'priority': priority,
                'is_favorite': res_obj.is_favorite
            })
            
        return JsonResponse({'results': results, 'term': csv_file.name})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def analyze_keyword(request):
    term = request.POST.get('keyword', '').strip()
    if not term:
        return JsonResponse({'error': 'Keyword is required'}, status=400)

    search_obj, created = KeywordSearch.objects.get_or_create(user=request.user, term=term)
    results = scrape_keyword_data(term)
    
    KeywordResult.objects.filter(search=search_obj).delete()
    for res in results:
        comp = res['competition']
        searches = res['demand_score']
        
        if comp < 5000 and searches > 1000:
            cat = 'Dark Green'
            priority = 1
        elif comp < 10000:
            cat = 'Light Green'
            priority = 2
        elif comp <= 20000:
            cat = 'Orange'
            priority = 3
        else:
            cat = 'Red'
            priority = 4

        KeywordResult.objects.create(
            search=search_obj,
            keyword=res['keyword'],
            avg_searches=searches,
            competition=comp,
            category=cat
        )
    
    # Refresh results with full data and priority
    final_results = []
    for r in KeywordResult.objects.filter(search=search_obj):
        # Calculate priority on the fly for old data or cached
        if r.competition < 5000 and r.avg_searches > 1000: p = 1
        elif r.competition < 10000: p = 2
        elif r.competition <= 20000: p = 3
        else: p = 4
        
        final_results.append({
            'keyword': r.keyword,
            'avg_searches': r.avg_searches,
            'avg_clicks': r.avg_clicks,
            'avg_ctr': r.avg_ctr,
            'competition': r.competition,
            'kd': r.kd,
            'category': r.category,
            'priority': p
        })
    return JsonResponse({'results': final_results})

@login_required
def export_csv(request):
    term = request.GET.get('term', '')
    if not term:
        return HttpResponse("No term provided", status=400)
    
    search_obj = KeywordSearch.objects.filter(term=term, user=request.user).first()
    if not search_obj:
        return HttpResponse("Search results not found", status=404)
    
    results = KeywordResult.objects.filter(search=search_obj).values(
        'keyword', 'avg_searches', 'avg_clicks', 'avg_ctr', 'competition', 'kd', 'opportunity_score', 'category'
    )
    
    df = pd.DataFrame(list(results))
    
    output = io.StringIO()
    df.to_csv(output, index=False)
    
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="etsy_keywords_{term}.csv"'
    return response

@login_required
def history_view(request):
    searches = KeywordSearch.objects.filter(user=request.user).order_by('-last_updated')
    return render(request, 'keywords/history.html', {'searches': searches})

@login_required
def load_results(request, search_id):
    search_obj = KeywordSearch.objects.filter(id=search_id, user=request.user).first()
    if not search_obj:
        return JsonResponse({'error': 'Search not found'}, status=404)
    
    results = []
    for r in KeywordResult.objects.filter(search=search_obj):
        # Priority logic
        if r.competition < 5000 and r.avg_searches > 1000: p = 1
        elif r.competition < 10000: p = 2
        elif r.competition <= 20000: p = 3
        else: p = 4
        
        results.append({
            'id': r.id,
            'keyword': r.keyword,
            'avg_searches': r.avg_searches,
            'avg_clicks': r.avg_clicks,
            'avg_ctr': r.avg_ctr,
            'competition': r.competition,
            'kd': r.kd,
            'category': r.category,
            'priority': p,
            'is_favorite': r.is_favorite
        })
    return JsonResponse({'results': results, 'term': search_obj.term})

@login_required
def overview_dashboard(request):
    total_files = KeywordSearch.objects.filter(user=request.user).count()
    total_keywords = KeywordResult.objects.filter(search__user=request.user).count()
    favorites_count = KeywordResult.objects.filter(is_favorite=True, search__user=request.user).count()
    
    # Golden Nuggets: High Demand (>1000) + Low Comp (<5000)
    golden_nuggets = KeywordResult.objects.filter(competition__lt=5000, avg_searches__gte=1000, search__user=request.user).order_by('-avg_searches')[:10]
    
    # Easy to Rank: Good Demand (>500) + Med-Low Comp (<15000)
    easy_to_rank = KeywordResult.objects.filter(competition__lt=15000, avg_searches__gte=500, search__user=request.user).exclude(id__in=[g.id for g in golden_nuggets]).order_by('-avg_searches')[:10]
    
    # All Favorites
    favorites = KeywordResult.objects.filter(is_favorite=True, search__user=request.user).order_by('-avg_searches')
    
    from customer_detail.models import Customer
    total_customers_db = Customer.objects.count()
    
    context = {
        'total_files': total_files,
        'total_keywords': total_keywords,
        'favorites_count': favorites_count,
        'golden_nuggets': golden_nuggets,
        'easy_to_rank': easy_to_rank,
        'favorites': favorites,
        'total_customers_db': total_customers_db,
    }
    return render(request, 'keywords/overview.html', context)

@login_required
@require_POST
def toggle_favorite(request):
    keyword_id = request.POST.get('keyword_id')
    try:
        res = KeywordResult.objects.get(id=keyword_id, search__user=request.user)
        res.is_favorite = not res.is_favorite
        res.save()
        
        # Sync with Rank Optimizer session data
        ro_data = request.session.get('rank_optimizer_data', [])
        modified = False
        for item in ro_data:
            if item.get('id') == res.id:
                item['is_favorite'] = res.is_favorite
                modified = True
                break
        if modified:
            request.session['rank_optimizer_data'] = ro_data
            ro_filtered = request.session.get('rank_optimizer_filtered', [])
            for item in ro_filtered:
                if item.get('id') == res.id:
                    item['is_favorite'] = res.is_favorite
                    break
            request.session['rank_optimizer_filtered'] = ro_filtered
            request.session.modified = True
            
        return JsonResponse({'status': 'success', 'is_favorite': res.is_favorite})
    except KeywordResult.DoesNotExist:
        return JsonResponse({'error': 'Keyword not found'}, status=404)

@login_required
def saved_keywords(request):
    favorites = KeywordResult.objects.filter(is_favorite=True, search__user=request.user).order_by('-opportunity_score', '-avg_searches')
    return render(request, 'keywords/saved.html', {'favorites': favorites})

@login_required
def delete_history(request, search_id):
    search_obj = KeywordSearch.objects.filter(id=search_id, user=request.user).first()
    if search_obj:
        # Explicitly delete results to ensure clean up, though CASCADE usually handles it
        KeywordResult.objects.filter(search=search_obj).delete()
        search_obj.delete()
    return redirect('view_history')

def logout_view(request):
    logout(request)
    return redirect('login')
