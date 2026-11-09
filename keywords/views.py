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

# Signup and pending approval views removed as per requirements.

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
    from datetime import date
    from django.db.models import Count, Sum
    from django.db.models.functions import TruncMonth
    from django.utils import timezone

    user = request.user
    my_results = KeywordResult.objects.filter(search__user=user)

    total_files = KeywordSearch.objects.filter(user=user).count()
    total_keywords = my_results.count()
    favorites_count = my_results.filter(is_favorite=True).count()
    total_searches = my_results.aggregate(s=Sum('avg_searches'))['s'] or 0

    # Golden Nuggets: High Demand (>1000) + Low Comp (<5000)
    golden_qs = my_results.filter(competition__lt=5000, avg_searches__gte=1000)
    golden_count = golden_qs.count()
    golden_nuggets = list(golden_qs.select_related('search').order_by('-avg_searches')[:8])

    # Easy to Rank: Good Demand (>500) + Med-Low Comp (<15000)
    easy_to_rank = my_results.filter(competition__lt=15000, avg_searches__gte=500).exclude(
        id__in=[g.id for g in golden_nuggets]).select_related('search').order_by('-avg_searches')[:8]

    favorites = my_results.filter(is_favorite=True).select_related('search').order_by('-avg_searches')[:10]

    # Chart: keyword opportunity mix.
    category_order = ['Dark Green', 'Light Green', 'Orange', 'Red']
    category_counts = dict(my_results.values_list('category').annotate(n=Count('id')))
    category_chart = {
        'labels': ['Golden (Dark Green)', 'Good (Light Green)', 'Moderate (Orange)', 'Hard (Red)'],
        'series': [category_counts.get(c, 0) for c in category_order],
    }

    # Chart: biggest analysed files.
    top_files = (KeywordSearch.objects.filter(user=user).annotate(n=Count('results'))
                 .filter(n__gt=0).order_by('-n')[:7])
    files_chart = {
        'labels': [f.term.replace('Upload_', '')[:28] for f in top_files],
        'series': [f.n for f in top_files],
    }

    context = {
        'total_files': total_files,
        'total_keywords': total_keywords,
        'favorites_count': favorites_count,
        'total_searches': total_searches,
        'golden_count': golden_count,
        'golden_nuggets': golden_nuggets,
        'easy_to_rank': easy_to_rank,
        'favorites': favorites,
        'category_chart': category_chart,
        'files_chart': files_chart,
        'recent_activity': user.activity.all()[:6],
    }

    # Customers & suppliers growth over the last six months.
    if user.has_module('customers') or user.has_module('suppliers'):
        today = timezone.now().date().replace(day=1)
        months = []
        for i in range(5, -1, -1):
            y, m = today.year, today.month - i
            while m <= 0:
                m += 12
                y -= 1
            months.append(date(y, m, 1))
        since = months[0]

        def monthly(qs, field):
            rows = (qs.filter(**{f'{field}__date__gte': since}).annotate(month=TruncMonth(field))
                    .values('month').annotate(n=Count('id')))
            counts = {r['month'].date() if hasattr(r['month'], 'date') else r['month']: r['n'] for r in rows}
            return [counts.get(mo, 0) for mo in months]

        growth = {'labels': [mo.strftime('%b %Y') for mo in months], 'series': []}
        if user.has_module('customers'):
            from customer_detail.models import Customer
            context['total_customers'] = Customer.objects.count()
            context['recent_customers'] = Customer.objects.order_by('-created_date')[:5]
            growth['series'].append({'name': 'Customers', 'data': monthly(Customer.objects.all(), 'created_date')})
        if user.has_module('suppliers'):
            from supplier_management.models import Supplier
            context['total_suppliers'] = Supplier.objects.count()
            growth['series'].append({'name': 'Suppliers', 'data': monthly(Supplier.objects.all(), 'created_at')})
        context['growth_chart'] = growth

    if user.has_module('competitors'):
        from competitor_shop_analysis.models import CompetitorShop
        context['total_competitors'] = CompetitorShop.objects.filter(category__user=user).count()

    if user.has_module('forecaster'):
        from django.db.models import Q
        from forecaster.models import ForecastEvent
        events = ForecastEvent.objects.filter(Q(is_system_default=True) | Q(user=user))
        upcoming = sorted(events, key=lambda e: e.target_date)[:4]
        today_d = date.today()
        context['upcoming_events'] = [
            {'name': e.name, 'date': e.target_date, 'days': (e.target_date - today_d).days,
             'regions': e.target_regions} for e in upcoming
        ]

    if user.can_manage_users:
        context['team'] = {
            'total': User.objects.count(),
            'active': User.objects.filter(is_active=True).count(),
            'online_today': User.objects.filter(last_login__date=timezone.now().date()).count(),
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
