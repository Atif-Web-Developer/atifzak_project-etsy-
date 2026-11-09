from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameBackend(ModelBackend):
    """Lets users sign in with either their username or their email address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        User = get_user_model()
        user = User.objects.filter(username__iexact=username).first()
        if user is None:
            user = User.objects.filter(email__iexact=username).order_by('pk').first()
        if user is None:
            User().set_password(password)  # equalise timing with the found-user path
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
