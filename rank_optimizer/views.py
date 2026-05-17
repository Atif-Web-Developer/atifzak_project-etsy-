import pandas as pd
import io
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from keywords.models import KeywordSearch, KeywordResult

@login_required
def dashboard_view(request):
    load_id = request.GET.get('load')
    if load_id:
        search_obj = KeywordSearch.objects.filter(id=load_id, user=request.user).first()
        if search_obj:
            results = KeywordResult.objects.filter(search=search_obj)
            data_list = []
            for r in results:
                data_list.append({
                    'keyword': r.keyword,
                    'volume': r.avg_searches,
                    'competition': r.competition
                })
            request.session['rank_optimizer_data'] = data_list
            request.session['rank_optimizer_filename'] = search_obj.term
            request.session.modified = True
            return redirect('rank_optimizer_dashboard')
            
    return render(request, 'rank_optimizer/rank_optimizer_dashboard.html')

@login_required
@require_POST
def upload_file_view(request):
    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    
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

        request.session['rank_optimizer_data'] = data_list
        request.session['rank_optimizer_filename'] = f"[Opt] {file.name}"
        request.session.modified = True

        # Save to global File History database
        search_obj, _ = KeywordSearch.objects.get_or_create(user=request.user, term=f"[Opt] {file.name}")
        KeywordResult.objects.filter(search=search_obj).delete()
        
        results_to_create = []
        for d in data_list:
            results_to_create.append(KeywordResult(
                search=search_obj,
                keyword=d['keyword'],
                avg_searches=d['volume'],
                competition=d['competition'],
                category='Optimizer'
            ))
        KeywordResult.objects.bulk_create(results_to_create)

        return JsonResponse({'message': 'success', 'total': len(data_list)})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def filter_keywords_ajax(request):
    data = request.session.get('rank_optimizer_data', [])
    if not data:
        return JsonResponse({'data': [], 'total': 0, 'golden_count': 0, 'low_comp_count': 0})

    min_vol = request.GET.get('min_volume', 500)
    max_comp = request.GET.get('max_competition', '')
    status_filter = request.GET.get('status', 'All')
    include_words = request.GET.get('include', '').lower().strip()
    exclude_words = request.GET.get('exclude', '').lower().strip()
    
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

    # sort by competition ASC by default to implement 'Smart Ranking'
    filtered_data.sort(key=lambda x: (x['competition'], -x['volume']))

    request.session['rank_optimizer_filtered'] = filtered_data
    request.session.modified = True

    return JsonResponse({
        'data': filtered_data,
        'total': len(filtered_data),
        'golden_count': golden_count,
        'low_comp_count': low_comp_count
    })

@login_required
def export_filtered_data(request):
    filtered_data = request.session.get('rank_optimizer_filtered', [])
    if not filtered_data:
        return HttpResponse("No data to export.", status=400)

    df = pd.DataFrame(filtered_data)
    
    output = io.StringIO()
    df.to_csv(output, index=False)
    
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="rank_optimizer_filtered.csv"'
    return response
