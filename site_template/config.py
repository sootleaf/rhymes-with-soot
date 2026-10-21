"""Site config: set ENV_PREFIX, cookie names, and APP_NAME.
ENV_PREFIX, SESSION_COOKIE, and CSRF_COOKIE are required — the app refuses to
start without them."""
from rhymes_with_soot.config import BaseConfig


class SiteTemplateConfig(BaseConfig):
    ENV_PREFIX = "SITE_TEMPLATE"
    APP_NAME = "Site Template"
    LOGIN_REDIRECT = "/"
    SESSION_COOKIE = "site_template_session"
    CSRF_COOKIE = "site_template_csrf"
