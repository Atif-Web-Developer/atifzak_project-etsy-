import pandas as pd
import io
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

@login_required
def dashboard_view(request):
    return render(request, 'etsypulse/etsypulse_dashboard.html')

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

        # Detect columns dynamically
        columns = [str(c).lower().strip() for c in df.columns]
        
        # Determine column mappings
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

        # Build list of dicts
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
            
            # Status badge logic
            if volume >= 2000 and comp <= 5000:
                status = 'Golden'
            elif comp <= 15000:
                status = 'Good'
            else:
                status = 'Hard'

            data_list.append({
                'keyword': keyword,
                'volume': volume,
                'competition': comp,
                'status': status
            })

        # Save to session
        request.session['etsypulse_data'] = data_list
        request.session.modified = True

        return JsonResponse({'message': 'success', 'total': len(data_list)})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def filter_keywords_ajax(request):
    data = request.session.get('etsypulse_data', [])
    if not data:
        return JsonResponse({'data': [], 'total': 0, 'golden_count': 0, 'low_comp_count': 0})

    min_vol = request.GET.get('min_volume', 0)
    max_comp = request.GET.get('max_competition', 99999999)
    status_filter = request.GET.get('status', 'All')
    search_text = request.GET.get('search', '').lower().strip()

    try:
        min_vol = int(min_vol)
    except:
        min_vol = 0
    
    try:
        max_comp = int(max_comp)
    except:
        max_comp = 99999999

    filtered_data = []
    golden_count = 0
    low_comp_count = 0

    include_words = []
    exclude_words = []
    
    if search_text:
        parts = [p.strip() for p in search_text.split(',')]
        for part in parts:
            if part.startswith('-'):
                word = part[1:].strip()
                if word:
                    exclude_words.append(word)
            elif part:
                include_words.append(part)

    for item in data:
        # Check volume and competition
        if item['volume'] < min_vol:
            continue
        if item['competition'] > max_comp:
            continue
        
        # Check status
        if status_filter != 'All' and item['status'] != status_filter:
            continue

        # Check search text
        k_lower = item['keyword'].lower()
        if include_words and not any(w in k_lower for w in include_words):
            continue
        if exclude_words and any(w in k_lower for w in exclude_words):
            continue

        filtered_data.append(item)
        if item['status'] == 'Golden':
            golden_count += 1
        if item['competition'] <= 15000:
            low_comp_count += 1

    # Save the currently filtered view for export
    request.session['etsypulse_filtered'] = filtered_data
    request.session.modified = True

    return JsonResponse({
        'data': filtered_data,
        'total': len(filtered_data),
        'golden_count': golden_count,
        'low_comp_count': low_comp_count
    })

@login_required
def export_filtered_data(request):
    filtered_data = request.session.get('etsypulse_filtered', [])
    if not filtered_data:
        return HttpResponse("No data to export.", status=400)

    df = pd.DataFrame(filtered_data)
    
    output = io.StringIO()
    df.to_csv(output, index=False)
    
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="etsypulse_filtered.csv"'
    return response
