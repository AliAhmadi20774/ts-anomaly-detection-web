from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import CurrentUserSerializer, LoginSerializer


@method_decorator(never_cache, name="dispatch")
class CsrfView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response({"csrfToken": get_token(request._request)})


@method_decorator([csrf_protect, never_cache], name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request=request._request, **serializer.validated_data)
        if user is None:
            raise AuthenticationFailed("Incorrect personnel code or password.")
        login(request._request, user)
        get_token(request._request)
        return Response(CurrentUserSerializer(user).data)


@method_decorator(never_cache, name="dispatch")
class CurrentUserView(APIView):
    def get(self, request: Request) -> Response:
        get_token(request._request)
        return Response(CurrentUserSerializer(request.user).data)


@method_decorator([csrf_protect, never_cache], name="dispatch")
class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        logout(request._request)
        return Response(status=204)
