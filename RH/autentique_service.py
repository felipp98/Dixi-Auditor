import requests
import json

API_URL = "https://api.autentique.com.br/v2/graphql"


def enviar_documento(token, caminho_pdf, nome_documento, email, posicoes):

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

    variables = {
        "document": {
            "name": nome_documento,
            "new_signature_style": True
        },
        "signers": [{
            "email": email,
            "action": "SIGN",
            "positions": posicoes
        }],
        "file": None
    }

    operations = json.dumps({
        "query": query,
        "variables": variables
    })

    map_part = json.dumps({
        "file": ["variables.file"]
    })

    files = {
        "operations": (None, operations),
        "map": (None, map_part),
        "file": open(caminho_pdf, "rb")
    }

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = requests.post(API_URL, headers=headers, files=files)

    return response.json()