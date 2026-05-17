from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from keywords.models import KeywordSearch, KeywordResult
import re

@login_required
def vault_view(request):
    """
    The Data Hub Retrieval System.
    Prioritizes keywords matching the Parent Keyword at the top.
    """
    query = request.GET.get('q', '').strip()
    context = {
        'query': query,
        'results_found': False,
        'primary_tags': [], # Recommended Tags (Matching Parent)
        'related_research': [], # Research History / Other Leads (Peripheral)
        'is_empty_log': False,
        'not_found': False
    }

    if query:
        search_obj = KeywordSearch.objects.filter(term__iexact=query).first()
        if search_obj:
            results = search_obj.results.all()
            if not results.exists():
                context['is_empty_log'] = True
                context['results_found'] = True
            else:
                context['results_found'] = True
                
                clothing_patterns = r'(t-shirt|sweatshirt|apparel|hoodie|shirt|clothing|garment|tee|clothing|top|outfit)'
                query_words = query.lower().split()

                for res in results:
                    # Ensure display name is Title Case and clean
                    res.display_keyword = res.keyword.title()
                    kw = res.keyword.lower()
                    
                    is_relevant = any(word in kw for word in query_words) or re.search(clothing_patterns, kw)
                    
                    if is_relevant:
                        context['primary_tags'].append(res)
                    else:
                        context['related_research'].append(res)
                
                context['primary_tags'].sort(key=lambda x: x.avg_searches, reverse=True)
                context['related_research'].sort(key=lambda x: x.avg_searches, reverse=True)
        else:
            context['not_found'] = True

    return render(request, 'keyword_bank/vault.html', context)

@login_required
@require_POST
def deposit_data(request):
    """
    Automated Data Sanitizer: Strips technical noise and saves clean Title Case keywords.
    """
    parent_keyword = request.POST.get('parent_keyword', '').strip()
    discovered_keywords = request.POST.get('discovered_keywords', '').strip()

    if not parent_keyword:
        return JsonResponse({'success': False, 'message': 'Parent Keyword is required.'})

    # Sanitize Parent Keyword
    parent_keyword = re.sub(r'[()\"\'\[\]]', '', parent_keyword).strip().title()

    search_obj, _ = KeywordSearch.objects.get_or_create(term=parent_keyword)
    KeywordResult.objects.filter(search=search_obj).delete()

    if discovered_keywords.lower() == 'nothing' or not discovered_keywords:
        pass
    else:
        clean_raw = re.sub(r'[()\"\'\[\]]', '', discovered_keywords)
        raw_keywords = re.split(r'[,|\n|\r|;]', clean_raw)
        
        for kw in raw_keywords:
            kw = kw.strip()
            if not kw or kw.lower() == 'nothing':
                continue
            
            clean_kw = kw.title()
                
            KeywordResult.objects.create(
                search=search_obj,
                keyword=clean_kw,
                avg_searches=0,
                competition=0,
                category='Sanitized Deposit'
            )
    
    return JsonResponse({
        'success': True, 
        'message': f'Vault entry for "{parent_keyword}" sanitized and updated.'
    })

@login_required
def archive_view(request):
    """
    The Data Hub Archive: View ONLY manual deposits.
    Filters out scraper/upload logs starting with 'Upload_'.
    """
    # Exclude entries that start with 'Upload_'
    entries = KeywordSearch.objects.exclude(term__startswith='Upload_').order_by('-last_updated')
    
    # Optional: Further filter to ensure only those with 'Sanitized Deposit' results are shown
    # entries = entries.filter(results__category='Sanitized Deposit').distinct()
    
    return render(request, 'keyword_bank/archive.html', {'entries': entries})
