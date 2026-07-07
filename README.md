# Dixi Auditor - Pagare

Este é um aplicativo desktop desenvolvido em Python com interface gráfica (Tkinter) para auditoria e controle de horas do espelho de ponto da **Dixi Ponto**. 

O sistema consome a API oficial da Dixi para buscar as batidas de ponto do colaborador, processa a jornada com tolerância e permite visualizar, auditar e exportar os dados consolidados.

---

## ✨ Funcionalidades

- **Autenticação Segura:** Login integrado e armazenamento seguro da última senha utilizada usando o cofre de credenciais do Windows (`keyring`).
- **Visualização Direta (Grid):** Visualização interativa das marcações diárias na própria aplicação com cores dinâmicas para fácil identificação:
  - 🟢 **Verde:** Saldo positivo (horas extras).
  - 🔴 **Vermelho:** Saldo negativo (atrasos).
  - 🔴 **Rosa com texto vermelho:** Dias com batidas faltantes (pendências).
- **Seletor de Datas Inteligente:** Filtros de data horizontais com lista suspensa nativa em português e ano digitável. O número máximo de dias do seletor se ajusta automaticamente com base no mês e no ano selecionado (incluindo anos bissextos).
- **Simulação e Edição de Ponto (Modo Auditoria):** Dê um duplo clique em qualquer marcação na tabela para editar ou apagar horários. Clique no botão **"Recalcular Ponto"** para verificar em tempo real como ficará o saldo acumulado antes de exportar.
- **Exportação Formatada para Excel:** Gera planilhas Excel organizadas com cabeçalhos de batidas que se adaptam dinamicamente se o funcionário tiver mais que 6 batidas por dia. O Excel gerado já vem com formatação de cores e o saldo geral calculado.
- **Suporte a Turnos Noturnos:** Reconhece viradas de turno e calcula corretamente marcações que passam da meia-noite.

---

## 🚀 Como Executar

### 📋 Pré-requisitos

Certifique-se de ter o Python 3 instalado e as dependências necessárias. Você pode instalar as dependências executando:

```bash
pip install pandas requests openpyxl keyring
```

### 💻 Rodando o Aplicativo

Para iniciar o programa, basta executar o script principal no terminal:

```bash
python Registro.py
```

---

## 📦 Como Gerar o Executável (`.exe`)

O projeto já inclui um arquivo de especificação do PyInstaller ([RH_Holerites.spec](RH_Holerites.spec)) pré-configurado com o ícone corporativo.

1. Instale o PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. Compile o executável:
   ```bash
   pyinstaller RH_Holerites.spec --clean
   ```

3. O arquivo executável standalone (`RH_Holerites.exe`) estará disponível na pasta `dist/`.

---

## 📁 Estrutura do Repositório

- `Registro.py`: Script principal contendo o mecanismo de cálculo, integrações com APIs e a interface gráfica (Tkinter).
- `teste.py`: Script experimental de raspagem de dados com Selenium (Wikipedia).
- `RH_Holerites.spec`: Arquivo de configuração de empacotamento do PyInstaller.
- `PAGARE.ico` / `PAGARE.png`: Arquivos de ícone e imagem utilizados no visual do projeto.
- `.gitignore`: Arquivo para evitar o upload de arquivos temporários, planilhas geradas e pastas de build para o Git.
