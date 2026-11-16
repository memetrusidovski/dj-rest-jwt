from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView


class MeView(APIView):
    """
    Stands in for your own API. JWT-protected by the preset's DRF defaults:
    the SPA reaches it with the access cookie, a native app with Bearer.
    """

    def get(self, request):
        return Response({
            "id": request.user.pk,
            "email": request.user.email,
            "server_time": timezone.now().isoformat(),
        })
