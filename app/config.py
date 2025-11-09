import os

def _get_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# Políticas globais de ponto (valores podem ser sobrescritos por contrato)
PONTO_RAIO_PADRAO_METROS = _get_int_env("PONTO_RAIO_PADRAO_METROS", 200)
PONTO_TOLERANCIA_PADRAO_MINUTOS = _get_int_env("PONTO_TOLERANCIA_PADRAO_MINUTOS", 10)
PONTO_ARREDONDAMENTO_MINUTOS = _get_int_env("PONTO_ARREDONDAMENTO_MINUTOS", 5)
JUSTIFICATIVA_SLA_HORAS = _get_int_env("JUSTIFICATIVA_SLA_HORAS", 48)
