from math import radians, cos, sin, asin, sqrt

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
