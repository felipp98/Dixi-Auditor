"""
Serviço de integração GraphQL com a API do Autentique v2.
"""
import json
import logging
import requests
from typing import List, Dict, Any, Union
from src.config.constants import AUTENTIQUE_GRAPHQL_URL, ROLE_SIGN
from src.core.models import Signatario

logger = logging.getLogger(__name__)

def enviar_justificativa_autentique(
    token: str,
    caminho_pdf: str,
    nome_documento: str,
    lista_signatarios: List[Union[Dict[str, Any], Signatario]]
) -> Dict[str, Any]:
    """
    Envia um documento PDF para a API do Autentique com múltiplos signatários (Colaborador, Gestor, RH, Testemunhas).
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
        if isinstance(sig, Signatario):
            email = sig.email
            action = sig.role
            positions = sig.positions
        else:
            email = sig.get("email", "")
            action = sig.get("action") or sig.get("role", ROLE_SIGN)
            positions = sig.get("positions", [])

        item = {
            "email": email,
            "action": action
        }

        if positions:
            pos_cleaned = []
            for p in positions:
                try:
                    px = float(p.get("x", 0))
                    py = float(p.get("y", 0))
                    pz = int(p.get("z", 1))
                    scale_val = float(p.get("scale", 0.85))
                    pos_cleaned.append({
                        "x": px,
                        "y": py,
                        "z": pz,
                        "element": str(p.get("element", "SIGNATURE")).upper(),
                        "scale": scale_val
                    })
                except (ValueError, TypeError):
                    pass
            if pos_cleaned:
                item["positions"] = pos_cleaned

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
        response = requests.post(AUTENTIQUE_GRAPHQL_URL, headers=headers, files=files, timeout=30)

    response.raise_for_status()
    data = response.json()

    if "errors" in data and data["errors"]:
        msg = data["errors"][0].get("message", str(data["errors"]))
        logger.error(f"Erro da API Autentique: {msg}")
        raise Exception(f"Erro da API Autentique: {msg}")

    return data

def listar_documentos_autentique(token: str, page: int = 1, limit: int = 60) -> Dict[str, Any]:
    """
    Lista os documentos da conta do Autentique trazendo o status das assinaturas.
    """
    query = """
    query ListDocuments($limit: Int, $page: Int) {
      documents(limit: $limit, page: $page) {
        total
        data {
          id
          name
          created_at
          signatures {
            public_id
            name
            email
            created_at
            action {
              name
            }
            link {
              short_link
            }
            user {
              id
              name
              email
            }
            viewed {
              created_at
            }
            signed {
              created_at
            }
            rejected {
              created_at
            }
          }
          files {
            original
            signed
          }
        }
      }
    }
    """
    payload = {
        "query": query,
        "variables": {"limit": limit, "page": page}
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    response = requests.post(AUTENTIQUE_GRAPHQL_URL, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "errors" in data and data["errors"]:
        msg = data["errors"][0].get("message", str(data["errors"]))
        logger.error(f"Erro ao listar documentos no Autentique: {msg}")
        raise Exception(f"Erro da API Autentique: {msg}")

    return data.get("data", {}).get("documents", {})

def resgatar_documento_autentique(token: str, document_id: str) -> Dict[str, Any]:
    """
    Resgata os detalhes completos de um documento específico no Autentique pelo ID.
    """
    query = """
    query GetDocument($id: String!) {
      document(id: $id) {
        id
        name
        created_at
        files {
          original
          signed
        }
        signatures {
          public_id
          name
          email
          created_at
          action {
            name
          }
          link {
            short_link
          }
          user {
            id
            name
            email
          }
          viewed {
            created_at
          }
          signed {
            created_at
          }
          rejected {
            created_at
          }
        }
      }
    }
    """
    payload = {
        "query": query,
        "variables": {"id": document_id}
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    response = requests.post(AUTENTIQUE_GRAPHQL_URL, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "errors" in data and data["errors"]:
        msg = data["errors"][0].get("message", str(data["errors"]))
        logger.error(f"Erro ao resgatar documento no Autentique: {msg}")
        raise Exception(f"Erro da API Autentique: {msg}")

    return data.get("data", {}).get("document", {})
