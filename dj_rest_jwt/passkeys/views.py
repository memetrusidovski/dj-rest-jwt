import json

from rest_framework import status
from rest_framework.generics import (
    GenericAPIView, ListAPIView, RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from dj_rest_jwt.app_settings import api_settings
from dj_rest_jwt.throttling import (
    CredentialActionRateThrottle, PasskeyChallengeRateThrottle,
    SensitiveAccountActionRateThrottle,
)
from dj_rest_jwt.views import LoginView

from .models import WebAuthnCredential


class PasskeyRegisterBeginView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (CredentialActionRateThrottle,)

    def get_serializer_class(self):
        return api_settings.PASSKEY_REGISTER_BEGIN_SERIALIZER

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        options_json = serializer.validated_data['options_json']
        return Response(json.loads(options_json), status=status.HTTP_200_OK)


class PasskeyRegisterCompleteView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (CredentialActionRateThrottle,)

    def get_serializer_class(self):
        return api_settings.PASSKEY_REGISTER_COMPLETE_SERIALIZER

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credential = serializer.validated_data['credential_obj']
        list_serializer = api_settings.PASSKEY_LIST_SERIALIZER(credential)
        return Response(list_serializer.data, status=status.HTTP_201_CREATED)


class PasskeyLoginBeginView(GenericAPIView):
    permission_classes = (AllowAny,)
    throttle_classes = (PasskeyChallengeRateThrottle,)

    def get_serializer_class(self):
        return api_settings.PASSKEY_LOGIN_BEGIN_SERIALIZER

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        options_json = serializer.validated_data['options_json']
        session_id = serializer.validated_data['session_id']
        response_data = json.loads(options_json)
        response_data['session_id'] = session_id
        return Response(response_data, status=status.HTTP_200_OK)


class PasskeyLoginCompleteView(LoginView):

    def get_serializer_class(self):
        return api_settings.PASSKEY_LOGIN_COMPLETE_SERIALIZER

    def mfa_required(self):
        """
        A passkey is possession + (usually) user verification, so for many
        deployments it already is multi-factor and challenging again is just
        friction. That's a policy call rather than a security one, so it's a
        setting - and it defaults to still challenging, because silently
        skipping a second factor the user deliberately enrolled is the more
        surprising of the two behaviours.
        """
        if api_settings.PASSKEY_SATISFIES_MFA:
            return False
        return super().mfa_required()

    def post(self, request, *args, **kwargs):
        self.request = request
        self.serializer = self.get_serializer(data=self.request.data)
        self.serializer.is_valid(raise_exception=True)
        self.login()
        return self.get_response()


class PasskeyListView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (SensitiveAccountActionRateThrottle,)

    def get_serializer_class(self):
        return api_settings.PASSKEY_LIST_SERIALIZER

    def get_queryset(self):
        return WebAuthnCredential.objects.filter(user=self.request.user).order_by('-created_at')


class PasskeyDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (CredentialActionRateThrottle,)

    def get_queryset(self):
        return WebAuthnCredential.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return api_settings.PASSKEY_LIST_SERIALIZER
        if self.request.method == 'DELETE':
            return api_settings.PASSKEY_DELETE_SERIALIZER
        return api_settings.PASSKEY_UPDATE_SERIALIZER

    def destroy(self, request, *args, **kwargs):
        # Removing someone's passkey locks them out, so it gets the same
        # step-up check as adding one. DELETE with a body is unusual but is the
        # only way to carry the proof without inventing a second endpoint.
        #
        # Resolve the object first: a passkey belonging to someone else should
        # answer 404 whether or not the caller sent valid credentials.
        instance = self.get_object()
        serializer = self.get_serializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
