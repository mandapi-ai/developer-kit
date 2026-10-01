from .api_catalog import APIMartAdapter, OminiGateAdapter
from .provider_html import RoteiaAdapter, RunAPIAdapter, KunavoAdapter, TokenRecargaAdapter
from .base import Adapter
from .generic_html import GenericHtmlTableAdapter
from .openrouter import OpenRouterAdapter
from .profile_only import ProfileOnlyAdapter


def adapter_for(name: str) -> Adapter:
    if name == "apimart":
        return APIMartAdapter()
    if name == "ominigate":
        return OminiGateAdapter()
    if name == "tokenrecarga":
        return TokenRecargaAdapter()
    if name == "kunavo":
        return KunavoAdapter()
    if name == "roteia":
        return RoteiaAdapter()
    if name == "runapi":
        return RunAPIAdapter()
    if name == "openrouter":
        return OpenRouterAdapter()
    if name == "generic_html":
        return GenericHtmlTableAdapter()
    if name == "profile_only":
        return ProfileOnlyAdapter()
    raise ValueError(f"Unknown adapter: {name}")
