from rest_framework_simplejwt.authentication import JWTAuthentication

class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = super().authenticate(request)
        if header:
            return header

        token = request.COOKIES.get("access_token")
        if not token:
            return None

        validated = self.get_validated_token(token)
        user = self.get_user(validated)

        return (user, validated)
