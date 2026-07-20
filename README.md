# Dixi Auditor - Pagare

Este é um aplicativo desktop desenvolvido em Python com interface gráfica (Tkinter) para auditoria e controle de horas do espelho de ponto da **Dixi Ponto**. 

O sistema consome a API oficial da Dixi para buscar as batidas de ponto do colaborador, processa a jornada com tolerância e permite visualizar, auditar e exportar os dados consolidados para planilhas Excel formatadas.

---

## ✨ Funcionalidades

- **Autenticação Segura:** Login integrado e armazenamento seguro da última credencial utilizada usando o cofre de credenciais do Windows (`keyring`).
- **Visualização Direta (Grid):** Visualização interativa das marcações diárias na própria aplicação com cores dinâmicas para fácil identificação:
  - 🟢 **Verde:** Saldo positivo (horas extras).
  - 🔴 **Vermelho:** Saldo negativo (atrasos).
  - 🔴 **Rosa com texto vermelho:** Dias com batidas faltantes (pendências).
- **Seletor de Datas Inteligente:** Filtros de data horizontais com lista suspensa nativa em português e ano digitável. O número máximo de dias do seletor se ajusta automaticamente com base no mês e no ano selecionado (incluindo anos bissextos).
- **Simulação e Edição de Ponto (Modo Auditoria):** Dê um duplo clique em qualquer marcação na tabela para editar ou apagar horários. Clique no botão **"Recalcular Ponto"** para verificar em tempo real como ficará o saldo acumulado antes de exportar.
- **Regra de Almoço Inteligente:** Computação automática do intervalo de almoço. Se o colaborador retornar antes de 1 hora de intervalo, a antecipação não gera saldo de horas extras (computa no mínimo 1 hora inteira de intervalo). Se retornar após 1 hora, o atraso é contabilizado normalmente na jornada.
- **Exportação Formatada para Excel:** Gera planilhas Excel organizadas com cabeçalhos de batidas que se adaptam dinamicamente se o funcionário tiver mais que 6 batidas por dia. O Excel gerado já vem com formatação de cores e o saldo geral acumulado.
- **Suporte a Turnos Noturnos:** Reconhece viradas de turno e calcula corretamente marcações que passam da meia-noite.

---

## 🚀 Como Executar

### 📋 Pré-requisitos

Certifique-se de ter o Python 3.x instalado e as dependências necessárias. Você pode instalar as dependências executando:

```bash
pip install pandas requests openpyxl keyring
```

### 💻 Rodando o Aplicativo

Como o código-fonte foi organizado na pasta `src/`, execute o script principal usando:

```bash
python src/Registro.py
```

---

## 📦 Como Gerar o Executável (`.exe`)

O projeto é empacotado em um único executável standalone usando o **PyInstaller**. Com o arquivo de especificação `.spec`, todos os arquivos de mídia (logo da Pagare) são embutidos diretamente no executável final de forma transparente.

1. Instale o PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. Compile o executável a partir da pasta de configurações de build (`specs/`):
   ```bash
   pyinstaller specs/Registro.spec --clean
   ```

3. O arquivo executável standalone (`Registro.exe`) contendo a interface de login atualizada estará disponível na pasta `dist/`.

> [!TIP]
> **Aviso de Antivírus/SmartScreen:** Como o executável final não possui uma assinatura digital paga, o Windows Defender ou SmartScreen de computadores de terceiros pode exibir um alerta de segurança na primeira execução. Para abrir, o usuário deve clicar em **"Mais informações"** e depois em **"Executar assim mesmo"**.

---

## 📁 Estrutura do Repositório Organizada

A estrutura de diretórios do repositório está organizada da seguinte maneira:

* **assets/**: Arquivos de mídia do projeto.
  * **assets/images/**: Imagens como a logo oficial (`logo_pagare.png`) e alternativas.
  * **assets/icons/**: Ícones de atalho do aplicativo (`PAGARE.ico`).
* **src/**: Código-fonte do projeto.
  * **src/Registro.py**: Script principal do aplicativo (Tkinter + API Dixi).
  * **src/teste.py**: Testes automatizados experimentais (Selenium).
* **specs/**: Arquivos de especificação do PyInstaller para geração do executável.
  * **specs/Registro.spec**: Especificação para o módulo principal de Registro.
  * **specs/RH_Holerites.spec**: Especificação para o módulo de Holerites.
* **resumo_compilacao.md**: Histórico descritivo e instruções do processo de build.
* **.gitignore**: Arquivo para evitar o upload de pastas geradas temporariamente (`build/`, `dist/`).
