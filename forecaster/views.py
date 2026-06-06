import json
from datetime import datetime, date, timedelta
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q
from .models import ForecastEvent, ForecastTaskProgress

STANDARD_TASKS = [
    "Market Research & Niche Selection",
    "Product Sourcing / Supplier Contact",
    "Design Creation & Asset Polish",
    "Listing SEO & Keyword Placement",
    "Mockups Generation",
    "Publish Listings & Marketing Setup"
]

DEFAULT_EVENTS = [
    {
        "name": "New Year's Day",
        "month": 1,
        "day": 1,
        "target_regions": "Global",
        "sourcing_days_prior": 90,
        "design_days_prior": 60,
        "niche_categories": ["Fitness Apparel", "Resolution Journals", "Academic Calendars"],
        "seo_keywords": ["2027 planner", "fitness tracker journal", "new year shirt"],
        "aesthetic_vibe": "Clean, motivational, goal-oriented. Energetic blues, vibrant greens, minimalist planning templates, bold typographic layouts.",
        "target_buyer_profile": "Resolution makers, fitness enthusiasts, and organized planners starting the new year fresh.",
    },
    {
        "name": "St. Patrick's Day",
        "month": 3,
        "day": 17,
        "target_regions": "US, UK, IE",
        "sourcing_days_prior": 90,
        "design_days_prior": 60,
        "niche_categories": ["Green Apparel", "Shamrock Accessories", "Irish Heritage Gifts"],
        "seo_keywords": ["st patricks day shirt", "lucky charm decor", "green aesthetic clothing"],
        "aesthetic_vibe": "Festive green themes, clover patterns, Irish blessings typography, playful custom group matching shirts.",
        "target_buyer_profile": "People celebrating Irish heritage, parade attendees, and pub crawls looking for fun green gear.",
    },
    {
        "name": "Earth Day",
        "month": 4,
        "day": 22,
        "target_regions": "Global",
        "sourcing_days_prior": 90,
        "design_days_prior": 60,
        "niche_categories": ["Eco-friendly Tote Bags", "Reusable Water Bottles", "Organic Cotton Tees"],
        "seo_keywords": ["eco friendly gifts", "save the planet shirt", "reusable tote bag"],
        "aesthetic_vibe": "Nature-focused, organic textures, earth tones (olive green, warm brown, clay). Hand-drawn botanical elements and save-the-planet slogans.",
        "target_buyer_profile": "Environmentally conscious consumers, conservationists, teachers, and eco-friendly gift buyers.",
    },
    {
        "name": "Independence Day / 4th of July",
        "month": 7,
        "day": 4,
        "target_regions": "US",
        "sourcing_days_prior": 90,
        "design_days_prior": 60,
        "niche_categories": ["Patriotic T-Shirts", "Custom BBQ Aprons", "Outdoor Party Supplies"],
        "seo_keywords": ["4th of july shirt", "patriotic apparel", "funny dad bbq apron"],
        "aesthetic_vibe": "Classic Americana. Red, white, and blue. Distressed stars-and-stripes prints, retro vintage barbecue designs, bold block fonts.",
        "target_buyer_profile": "Families organizing holiday barbecues, parade attendees, and patriots looking for custom summer outfits.",
    },
    {
        "name": "Halloween",
        "month": 10,
        "day": 31,
        "target_regions": "US, UK, CA, AU",
        "sourcing_days_prior": 90,
        "design_days_prior": 60,
        "niche_categories": ["Spooky Sweatshirts", "Gothic Home Decor", "Custom Trick-or-Treat Bags"],
        "seo_keywords": ["halloween sweatshirt", "horror movie shirt", "gothic wreath", "trick or treat bag"],
        "aesthetic_vibe": "Spooky gothic or cute/playful spooky. Matte black, pumpkin orange, deep purples. Witchy patterns, custom name decals.",
        "target_buyer_profile": "Moms buying custom candy bags for children, teenagers and adults looking for cozy spooky sweatshirts.",
    },
    {
        "name": "Veterans Day / Remembrance Day",
        "month": 11,
        "day": 11,
        "target_regions": "US, UK, CA",
        "sourcing_days_prior": 90,
        "design_days_prior": 60,
        "niche_categories": ["Military Honor Ornaments", "Patriotic Gifts", "Custom Keychains"],
        "seo_keywords": ["veterans day gift", "thank you veterans shirt", "custom military keychain"],
        "aesthetic_vibe": "Respectful, solemn, and patriotic. Navy blue, olive drab, gold accents. Clean serif fonts, poppy symbols, and flag designs.",
        "target_buyer_profile": "Veterans, active military families, and individuals purchasing remembrance items to honor veterans.",
    },
    {
        "name": "Christmas",
        "month": 12,
        "day": 25,
        "target_regions": "Global",
        "sourcing_days_prior": 90,
        "design_days_prior": 60,
        "niche_categories": ["Personalized Ornaments", "Family Matching Pyjamas", "Custom Stockings"],
        "seo_keywords": ["baby first christmas", "family ornament", "custom stocking", "christmas eve box"],
        "aesthetic_vibe": "Classic holiday warmth or Scandinavian modern. Rich greens, crimson, gold details. Intricate script typography and personalized family illustrations.",
        "target_buyer_profile": "Families decorating their homes, parents seeking personalized keepsake gifts, and early holiday shoppers.",
    },
    {
        "name": "New Year's Eve",
        "month": 12,
        "day": 31,
        "target_regions": "Global",
        "sourcing_days_prior": 90,
        "design_days_prior": 60,
        "niche_categories": ["Custom Champagne Glasses", "Glitter Party Apparel", "2027 Glow Specs/Props"],
        "seo_keywords": ["new years eve outfit", "custom party glasses", "goodbye 2026 shirt"],
        "aesthetic_vibe": "Glitzy, glamorous, and celebratory. Metallic gold, silver, glitter black. Art Deco geometric patterns, elegant tall champagne glass engravings.",
        "target_buyer_profile": "NYE party hosts, event organizers, and party-goers looking for customized commemorative favors.",
    }
]

def initialize_default_events():
    """Initializes the database with standard defaults if none exist."""
    if not ForecastEvent.objects.filter(is_system_default=True).exists():
        for event_data in DEFAULT_EVENTS:
            ForecastEvent.objects.create(
                name=event_data['name'],
                month=event_data['month'],
                day=event_data['day'],
                target_regions=event_data['target_regions'],
                sourcing_days_prior=event_data['sourcing_days_prior'],
                design_days_prior=event_data['design_days_prior'],
                niche_categories=event_data['niche_categories'],
                seo_keywords=event_data['seo_keywords'],
                aesthetic_vibe=event_data['aesthetic_vibe'],
                target_buyer_profile=event_data['target_buyer_profile'],
                is_system_default=True
            )

@login_required
def forecaster_dashboard(request):
    # Ensure system default events exist
    initialize_default_events()

    # Get query parameters
    region_filter = request.GET.get('region', '')
    query = request.GET.get('q', '')
    sort_by = request.GET.get('sort', 'target_date')

    # Fetch events owned by system or the current user
    events_qs = ForecastEvent.objects.filter(Q(is_system_default=True) | Q(user=request.user))

    # Apply search filter
    if query:
        events_qs = events_qs.filter(
            Q(name__icontains=query) |
            Q(niche_categories__icontains=query) |
            Q(seo_keywords__icontains=query)
        )

    # Apply region filter
    if region_filter:
        events_qs = events_qs.filter(target_regions__icontains=region_filter)

    events = list(events_qs)

    today = date.today()
    critical_count = 0
    completed_count = 0
    total_active_count = len(events)
    upcoming_sourcing_count = 0

    # Process checklist and metrics for each event
    for event in events:
        # Get or create all progress tasks for this event & user
        tasks_progress = []
        completed_tasks_for_event = 0
        total_tasks_for_event = len(STANDARD_TASKS)

        for task_name in STANDARD_TASKS:
            progress, created = ForecastTaskProgress.objects.get_or_create(
                user=request.user,
                event=event,
                task_name=task_name
            )
            tasks_progress.append(progress)
            if progress.is_completed:
                completed_tasks_for_event += 1

        # Calculate progress percentage
        progress_percentage = int((completed_tasks_for_event / total_tasks_for_event) * 100)
        event.progress_percentage = progress_percentage
        event.tasks_list = tasks_progress
        

        # Determine stats
        is_fully_completed = (progress_percentage == 100)
        if is_fully_completed:
            completed_count += 1
        
        # Critical deadline check: deadline is in the past or within 30 days, and not completed
        days_to_sourcing = (event.sourcing_deadline - today).days
        days_to_design = (event.design_deadline - today).days
        
        event.days_to_sourcing = days_to_sourcing
        event.days_to_sourcing_abs = abs(days_to_sourcing)
        event.days_to_design = days_to_design
        event.days_to_design_abs = abs(days_to_design)

        # Critical if design or sourcing is coming up in <= 30 days (or overdue) and tasks are not finished
        if not is_fully_completed and (days_to_sourcing <= 30 or days_to_design <= 30):
            event.is_critical = True
            critical_count += 1
        else:
            event.is_critical = False

        # Upcoming sourcing count (sourcing deadline within next 60 days in future)
        if 0 <= days_to_sourcing <= 60:
            upcoming_sourcing_count += 1

    # Apply sorting in memory since target_date/sourcing_deadline/design_deadline are dynamic properties
    if sort_by == 'target_date':
        events.sort(key=lambda x: x.target_date)
    elif sort_by == '-target_date':
        events.sort(key=lambda x: x.target_date, reverse=True)
    elif sort_by == 'sourcing_deadline':
        events.sort(key=lambda x: x.sourcing_deadline)
    elif sort_by == 'design_deadline':
        events.sort(key=lambda x: x.design_deadline)

    # Get dynamic urgency priorities list
    priority_actions = []
    for event in events:
        if event.progress_percentage < 100:
            # Check outstanding tasks
            pending_tasks = [t.task_name for t in event.tasks_list if not t.is_completed]
            next_action = pending_tasks[0] if pending_tasks else "Finalize listings"
            
            if event.days_to_sourcing <= 15:
                urgency = 'Urgent'
                badge_class = 'bg-danger'
                order_val = 1
            elif event.days_to_design <= 30:
                urgency = 'High Priority'
                badge_class = 'bg-warning text-dark'
                order_val = 2
            else:
                urgency = 'Planning'
                badge_class = 'bg-success'
                order_val = 3
                
            priority_actions.append({
                'event_title': event.title,
                'action_text': f"{next_action} for {event.title}",
                'deadline_text': f"Sourcing: {event.sourcing_deadline.strftime('%b %d')} / Design: {event.design_deadline.strftime('%b %d')}",
                'urgency': urgency,
                'badge_class': badge_class,
                'order': order_val
            })
            
    # Sort priority actions by urgency order
    priority_actions.sort(key=lambda x: x['order'])

    context = {
        'events': events,
        'critical_count': critical_count,
        'completed_count': completed_count,
        'total_active_count': total_active_count,
        'upcoming_sourcing_count': upcoming_sourcing_count,
        'priority_actions': priority_actions[:5],  # top 5 priority actions
        'region_filter': region_filter,
        'query': query,
        'sort_by': sort_by,
        'current_year': datetime.now().year,
    }
    return render(request, 'forecaster/dashboard.html', context)

@login_required
@require_POST
def toggle_task(request):
    try:
        data = json.loads(request.body)
        event_id = data.get('event_id')
        task_name = data.get('task_name')
        
        progress = get_object_or_404(ForecastTaskProgress, user=request.user, event_id=event_id, task_name=task_name)
        progress.is_completed = not progress.is_completed
        progress.save()

        # Re-calculate overall progress for this event
        total_tasks = len(STANDARD_TASKS)
        completed_tasks = ForecastTaskProgress.objects.filter(user=request.user, event_id=event_id, is_completed=True).count()
        progress_percentage = int((completed_tasks / total_tasks) * 100)

        return JsonResponse({
            'success': True,
            'is_completed': progress.is_completed,
            'progress_percentage': progress_percentage
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_POST
def add_custom_event(request):
    try:
        title = request.POST.get('title')
        target_date_label = request.POST.get('target_date_label')
        target_date_str = request.POST.get('target_date')
        sourcing_deadline_str = request.POST.get('sourcing_deadline')
        design_deadline_str = request.POST.get('design_deadline')
        regions = request.POST.get('regions', 'Global')
        trending_categories = request.POST.get('trending_categories')
        seo_keywords = request.POST.get('seo_keywords')
        aesthetic_vibe = request.POST.get('aesthetic_vibe')
        target_buyer_profile = request.POST.get('target_buyer_profile', '')

        # Date conversions
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        sourcing_deadline = datetime.strptime(sourcing_deadline_str, '%Y-%m-%d').date()
        design_deadline = datetime.strptime(design_deadline_str, '%Y-%m-%d').date()

        # Parse comma-separated categories/keywords to lists
        niche_categories = [cat.strip() for cat in trending_categories.split(',') if cat.strip()]
        seo_keywords_list = [kw.strip() for kw in seo_keywords.split(',') if kw.strip()]

        # Create event
        event = ForecastEvent.objects.create(
            user=request.user,
            name=title,
            month=target_date.month,
            day=target_date.day,
            target_regions=regions,
            sourcing_days_prior=(target_date - sourcing_deadline).days,
            design_days_prior=(target_date - design_deadline).days,
            niche_categories=niche_categories,
            seo_keywords=seo_keywords_list,
            aesthetic_vibe=aesthetic_vibe,
            target_buyer_profile=target_buyer_profile,
            is_system_default=False
        )

        # Pre-initialize progress tasks
        for task_name in STANDARD_TASKS:
            ForecastTaskProgress.objects.create(
                user=request.user,
                event=event,
                task_name=task_name,
                is_completed=False
            )

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_POST
def delete_event(request, event_id):
    try:
        # Only allow users to delete their own custom events
        event = get_object_or_404(ForecastEvent, id=event_id, user=request.user, is_system_default=False)
        event.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
