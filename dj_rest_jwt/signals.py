from django.dispatch import Signal

# Sent with `user_id` and `request` when a rotated refresh token is presented
# again after the grace window. The session has already been ended.
refresh_token_reused = Signal()
