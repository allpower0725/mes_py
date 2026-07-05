from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from mes_py.infrastructure.database import create_engine_from_url, init_database, make_session_factory, session_scope
from mes_py.services.auth_service import AuthService
from mes_py.settings import Settings


def bootstrap_application(settings: Settings) -> sessionmaker:
    engine = create_engine_from_url(settings.database_url)
    init_database(engine)
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        AuthService(session).ensure_bootstrap_admin(
            settings.bootstrap_email,
            settings.bootstrap_password,
        )
    return factory

