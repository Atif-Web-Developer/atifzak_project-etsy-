from django.shortcuts import redirect
from django.urls import reverse

class ApprovedUserMiddleware:
    """
    Middleware that ensures users must be approved by the admin 
    before accessing any dashboard or system feature.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Paths that are allowed without approval
        exempt_paths = [
            reverse('login'),
            reverse('logout'),
            reverse('signup'),
            reverse('pending_approval'),
        ]
        
        # Check if the requested URL is exempt or is the django admin panel
        is_exempt = any(request.path == path for path in exempt_paths) or request.path.startswith('/admin')
        
        # If the user is authenticated but not approved, redirect to pending approval page
        if request.user.is_authenticated and not request.user.is_superuser:
            if not getattr(request.user, 'is_approved', False) and not is_exempt:
                return redirect('pending_approval')

        response = self.get_response(request)
        return response
