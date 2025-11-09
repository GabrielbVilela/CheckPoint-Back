from typing import Iterable

from fastapi import Depends, HTTPException, status

from . import auth, models


def require_roles(*roles: Iterable[str]):
    allowed = set(roles)

    def dependency(current_user: models.Usuario = Depends(auth.get_current_active_user)) -> models.Usuario:
        if current_user.tipo_acesso not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Perfil sem permissao para esta operacao.",
            )
        return current_user

    return dependency
