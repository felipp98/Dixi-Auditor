from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

# Configuração do Driver (instala automaticamente o driver correto)
servico = Service(ChromeDriverManager().install())
options = webdriver.ChromeOptions()
# options.add_argument("--headless") # Descomente para rodar sem abrir a janela
driver = webdriver.Chrome(service=servico, options=options)

try:
    # 1. Acessa a Wikipedia
    driver.get("https://pt.wikipedia.org/")
    
    # 2. Espera o campo de busca aparecer (máximo 10 segundos)
    # Isso torna o código MUITO mais seguro que o PyAutoGUI
    wait = WebDriverWait(driver, 10)
    campo_busca = wait.until(EC.presence_of_element_located((By.NAME, "search")))
    
    # 3. Digita o termo e pesquisa
    campo_busca.send_keys("Inteligência Artificial")
    campo_busca.submit() # Envia o formulário
    
    print(f"Título da página: {driver.title}")
    
    # 4. Localiza o sumário/índice da página
    # Buscamos pela classe 'toc' ou pelos itens de lista dentro do índice
    print("\n--- Coletando tópicos do índice ---")
    
    indices = driver.find_elements(By.CSS_SELECTOR, ".mw-headline")
    
    for i, item in enumerate(indices):
        texto = item.text
        if texto: # Se o texto não estiver vazio
            print(f"{i+1}. {texto}")

    # 5. Exemplo de interação: Clicar no primeiro link do índice
    if indices:
        print(f"\nClicando no tópico: {indices[0].text}")
        indices[0].click()
        time.sleep(2) # Pausa apenas para observação visual

except Exception as e:
    print(f"Ocorreu um erro: {e}")

finally:
    print("\nTarefa finalizada. Fechando navegador...")
    driver.quit()