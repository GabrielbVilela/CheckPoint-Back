from math import radians, cos, sin, asin, sqrt
from datetime import timezone, datetime

def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    Calcula a distância em metros entre dois pontos geográficos
    (especificados em graus decimais) usando a fórmula de Haversine.
    """
    # Converte graus decimais para radianos
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # Fórmula de Haversine
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    
    # Raio da Terra em quilômetros é 6371
    metros = c * 6371 * 1000
    return metros


def ensure_aware(dt: datetime) -> datetime:
    """Garante que um datetime seja timezone-aware (UTC) para operar com deltas com segurança.
    Se for naive, assume UTC.
    """
    if dt is None:
        return None
    try:
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        # Em caso de tzinfo estranho, força UTC
        return dt.replace(tzinfo=timezone.utc)
