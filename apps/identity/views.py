from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import ApiError
from apps.notifications.models import Device

from .models import OTPCode, User, Verification
from .serializers import (
    AuthorSerializer,
    DeviceSerializer,
    MeSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    PublicUserSerializer,
    VerificationSerializer,
    tokens_for,
)


class OTPRequestView(APIView):
    """POST /auth/otp/request — issue an OTP for a phone number (§9.2)."""

    permission_classes = [AllowAny]
    throttle_scope = "otp"

    @extend_schema(request=OTPRequestSerializer, responses=None)
    def post(self, request):
        ser = OTPRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        phone = ser.validated_data["phone"]
        otp = OTPCode.issue(phone, fixed_code=settings.OTP_DEBUG_CODE or None)
        body = {"request_id": otp.request_id, "expires_in": 120}
        if settings.DEBUG and settings.OTP_DEBUG_CODE:
            body["debug_code"] = otp.code  # convenience for the mockup app
        return Response(body, status=status.HTTP_200_OK)


class OTPVerifyView(APIView):
    """POST /auth/otp/verify — verify code, create/return user, issue tokens (§9.2)."""

    permission_classes = [AllowAny]

    @extend_schema(request=OTPVerifySerializer, responses=None)
    def post(self, request):
        ser = OTPVerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        request_id = ser.validated_data["request_id"].strip()
        code = ser.validated_data["code"].strip()

        otp = OTPCode.objects.filter(request_id=request_id, consumed=False).first()
        if not otp or not otp.is_valid():
            raise ApiError("OTP_INVALID", "Code expired or not found. Request a new one.")
        if otp.code != code:
            otp.attempts += 1
            otp.save(update_fields=["attempts"])
            raise ApiError("OTP_INCORRECT", "Incorrect code.")

        otp.consumed = True
        otp.save(update_fields=["consumed"])

        user, created = User.objects.get_or_create(
            phone=otp.phone, defaults={"is_phone_verified": True}
        )
        if not user.is_phone_verified:
            user.is_phone_verified = True
            user.save(update_fields=["is_phone_verified"])

        toks = tokens_for(user)
        return Response(
            {
                "access_token": toks["access_token"],
                "refresh_token": toks["refresh_token"],
                "is_new_user": created,
                "user": {"id": str(user.id), "phone": user.phone,
                         "display_name": user.display_name or None},
            }
        )


class LogoutView(APIView):
    """POST /auth/logout — blacklist refresh token + drop the device (§9.2)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get("refresh_token")
        if token:
            try:
                from rest_framework_simplejwt.tokens import RefreshToken

                RefreshToken(token).blacklist()
            except Exception:
                pass  # blacklist app optional; logout is best-effort
        fcm = request.data.get("fcm_token")
        if fcm:
            Device.objects.filter(user=request.user, fcm_token=fcm).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """GET/PATCH /me — the authenticated user's full profile (§9.3)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)

    @extend_schema(request=MeSerializer, responses=MeSerializer)
    def patch(self, request):
        ser = MeSerializer(request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class PublicUserView(APIView):
    """GET /users/{id} — public profile, no phone/location (§9.3)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        return Response(PublicUserSerializer(user).data)


class VerificationView(APIView):
    """POST /me/verification — submit ID document for the Verified badge (§9.3)."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(request=VerificationSerializer, responses=None)
    def post(self, request):
        ser = VerificationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ver = ser.save(user=request.user)
        return Response(
            {"verification_id": str(ver.id), "status": ver.status},
            status=status.HTTP_202_ACCEPTED,
        )


class DeviceView(APIView):
    """POST /me/devices — register an FCM token for push (§9.3, §11)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=DeviceSerializer, responses=DeviceSerializer)
    def post(self, request):
        ser = DeviceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        device, _ = Device.objects.update_or_create(
            fcm_token=ser.validated_data["fcm_token"],
            defaults={
                "user": request.user,
                "platform": ser.validated_data.get("platform", Device.Platform.ANDROID),
                "last_seen": timezone.now(),
            },
        )
        return Response(DeviceSerializer(device).data, status=status.HTTP_201_CREATED)
