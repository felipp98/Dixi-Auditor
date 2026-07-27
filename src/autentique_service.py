import requests
import json
from typing import List, Dict, Any

API_URL = "https://api.autentique.com.br/v2/graphql"

def enviar_justificativa_autentique(
    token: str,
    caminho_pdf: str,
    nome_documento: str,
    lista_signatarios: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Envia um documento PDF para a API do Autentique com suporte a múltiplos signatários (Colaborador, Gestor, RH).
    
    Exemplo de lista_signatarios:
    [
        {"email": "colaborador@empresa.com", "action": "SIGN", "positions": [{"x": "15", "y": "85", "z": 1, "element": "SIGNATURE"}]},
        {"email": "gestor@empresa.com", "action": "SIGN", "positions": [{"x": "50", "y": "85", "z": 1, "element": "SIGNATURE"}]},
        {"email": "rh@empresa.com", "action": "SIGN", "positions": [{"x": "80", "y": "85", "z": 1, "element": "SIGNATURE"}]}
    ]
    """
    query = """
    mutation CreateDocumentMutation($document: DocumentInput!, $signers: [SignerInput!]!, $file: Upload!) {
      createDocument(document: $document, signers: $signers, file: $file) {
        id
        name
        signatures {
          public_id
          name
          email
          link { short_link }
        }
      }
    }
    """

    signers_input = []
    for sig in lista_signatarios:
        item = {
            "email": sig["email"],
            "action": sig.get("action", "SIGN")
        }
        if "positions" in sig and sig["positions"]:
            item["positions"] = sig["positions"]
        signers_input.append(item)

    variables = {
        "document": {
            "name": nome_documento,
            "new_signature_style": True
        },
        "signers": signers_input,
        "file": None
    }

    operations = json.dumps({
        "query": query,
        "variables": variables
    })

    map_part = json.dumps({
        "file": ["variables.file"]
    })

    with open(caminho_pdf, "rb") as pdf_file:
        files = {
            "operations": (None, operations),
            "map": (None, map_part),
            "file": pdf_file
        }
        headers = {
            "Authorization": f"Bearer {token}"
        }
        response = requests.post(API_URL, headers=headers, files=files, timeout=30)

    response.raise_for_status()
    data = response.json()

    if "errors" in data and data["errors"]:
        msg = data["errors"][0].get("message", str(data["errors"]))
        raise Exception(f"Erro da API Autentique: {msg}")

    return data
