import requests
import os
from fastapi import HTTPException

def get_coordinates_from_google(address: str):
    """
    Busca as coordenadas (latitude e longitude) de um endereço
    usando a API de Geocodificação do Google.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key or api_key == "SUA_CHAVE_API_DO_GOOGLE":
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_MAPS_API_KEY não foi configurada no ambiente."
        )

    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": api_key
    }

    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data["status"] == "OK":
            location = data["results"][0]["geometry"]["location"]
            return {"lat": location["lat"], "lng": location["lng"]}
        else:
            # Retorna None se o endereço não for encontrado pela API
            return None
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Erro ao comunicar com a API do Google: {e}")
