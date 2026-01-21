from abc import ABC, abstractmethod

import httpx

from app.config import settings


class OAuthAdapter(ABC):
    @abstractmethod
    def get_authorize_url(
        self,
        redirect_uri: str,
        state: str | None,
        code_challenge: str | None,
        code_challenge_method: str | None,
    ) -> str: ...

    @abstractmethod
    def exchange_code(self, code: str, redirect_uri: str, code_verifier: str | None) -> dict: ...

    @abstractmethod
    def fetch_profile(self, token_data: dict) -> dict: ...


class GoogleOAuthAdapter(OAuthAdapter):
    def get_authorize_url(
        self,
        redirect_uri: str,
        state: str | None,
        code_challenge: str | None,
        code_challenge_method: str | None,
    ) -> str:
        if not settings.google_client_id:
            raise ValueError("Google OAuth not configured")
        url = (
            "https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={settings.google_client_id}"
            f"&redirect_uri={redirect_uri}"
            "&response_type=code"
            f"&scope={settings.google_scope.replace(' ', '%20')}"
            "&access_type=offline&include_granted_scopes=true"
        )
        if code_challenge:
            method = code_challenge_method or "S256"
            url += f"&code_challenge={code_challenge}&code_challenge_method={method}"
        if state:
            url += f"&state={state}"
        return url

    def exchange_code(self, code: str, redirect_uri: str, code_verifier: str | None) -> dict:
        data = {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
        resp = httpx.post("https://oauth2.googleapis.com/token", data=data, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def fetch_profile(self, token_data: dict) -> dict:
        access_token = token_data.get("access_token")
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = httpx.get("https://openidconnect.googleapis.com/v1/userinfo", headers=headers, timeout=10)
        resp.raise_for_status()
        profile = resp.json()
        return {
            "provider_user_id": profile.get("sub"),
            "email": profile.get("email"),
            "name": profile.get("name"),
            "avatar_url": profile.get("picture"),
        }


class GithubOAuthAdapter(OAuthAdapter):
    def get_authorize_url(
        self,
        redirect_uri: str,
        state: str | None,
        code_challenge: str | None,
        code_challenge_method: str | None,
    ) -> str:
        if not settings.github_client_id:
            raise ValueError("GitHub OAuth not configured")
        url = (
            "https://github.com/login/oauth/authorize"
            f"?client_id={settings.github_client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&scope={settings.github_scope.replace(' ', '%20')}"
        )
        if code_challenge:
            method = code_challenge_method or "S256"
            url += f"&code_challenge={code_challenge}&code_challenge_method={method}"
        if state:
            url += f"&state={state}"
        return url

    def exchange_code(self, code: str, redirect_uri: str, code_verifier: str | None) -> dict:
        data = {
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
        headers = {"Accept": "application/json"}
        resp = httpx.post("https://github.com/login/oauth/access_token", data=data, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def fetch_profile(self, token_data: dict) -> dict:
        access_token = token_data.get("access_token")
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        user_resp = httpx.get("https://api.github.com/user", headers=headers, timeout=10)
        user_resp.raise_for_status()
        user = user_resp.json()
        email = user.get("email")

        if not email:
            emails_resp = httpx.get("https://api.github.com/user/emails", headers=headers, timeout=10)
            if emails_resp.status_code == 200:
                emails = emails_resp.json()
                primary = next((item for item in emails if item.get("primary") and item.get("verified")), None)
                if primary:
                    email = primary.get("email")

        return {
            "provider_user_id": str(user.get("id")),
            "email": email,
            "name": user.get("name") or user.get("login"),
            "avatar_url": user.get("avatar_url"),
        }


def get_oauth_adapter(provider: str) -> OAuthAdapter:
    provider_key = provider.lower()
    if provider_key == "google":
        return GoogleOAuthAdapter()
    if provider_key == "github":
        return GithubOAuthAdapter()
    raise ValueError("Unsupported OAuth provider")
