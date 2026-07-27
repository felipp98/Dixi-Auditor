# Dixi Auditor - Pagare

Este é um aplicativo desktop desenvolvido em Python com interface gráfica (Tkinter) para auditoria, controle de horas e justificativa de espelho de ponto da **Dixi Ponto**. 

O sistema consome a API oficial da Dixi para buscar as batidas de ponto do colaborador, processa a jornada com tolerância e permite visualizar, auditar, recalcular e exportar os dados consolidados para planilhas Excel formatadas e relatórios oficiais em PDF para o RH via **Autentique**.

---

## ✨ Funcionalidades

- **Autenticação Segura & Auto-preenchimento:** Login integrado à API Dixi com armazenamento seguro no cofre do Windows (`keyring`). Os dados de perfil do colaborador logado (Nome Completo e E-mail) são auto-preenchidos automaticamente nos formulários.
- **Tabela Principal com Checkboxes (`[☑]` / `[☐]`):** Primeira coluna `Sel` permite marcar ou desmarcar dias com um único clique. Clique no cabeçalho **`Sel [☑]`** para marcar/desmarcar todos os dias de uma só vez.
- **Visualização Direta (Grid):** Marcações diárias com cores dinâmicas para fácil identificação auditável:
  - 🟢 **Verde:** Saldo positivo (horas extras).
  - 🔴 **Vermelho:** Saldo negativo (atrasos).
  - 🔴 **Rosa com texto vermelho:** Dias com batidas faltantes (pendências).
  - 🟢 **Verde Oliva:** Dia em andamento (desconsiderado do saldo acumulado para evitar déficits parciais).
- **Formulário de Justificativa de Ponto para o RH:**
  - **Filtro Inteligente:** Ao abrir o modal, se o usuário selecionou/marcou dias específicos na tabela principal, o formulário carrega **apenas esses dias selecionados**.
  - **Layout Fiel à Planilha Excel:** Gera PDF profissional espelhado na planilha de ponto oficial, com sub-linhas detalhadas (`ENTRADA:`, `SAÍDA REFEIÇÃO:`, `RETORNO REFEIÇÃO:`, `SAÍDA:`) e justificativas individuais por dia.
  - **Assinatura Digital via Autentique:** Permite selecionar o papel de cada signatário (**`Assinar`**, **`Testemunha`**, **`Aprovar`**) e incluir ilimitadas pessoas através do botão **`➕ Adicionar Signatário Extra`**.
  - **Interface Responsiva com Rodapé Fixo:** Barra de botões (*`👁️ Gerar e Visualizar PDF`* e *`🚀 Enviar via Autentique`*) fixada permanentemente na parte inferior da tela com formulário rolável.
- **Seletor de Datas Inteligente:** Filtros de data horizontais com lista suspensa nativa em português e ano digitável. O número máximo de dias do seletor se ajusta automaticamente com base no mês e no ano selecionado (incluindo anos bissextos).
- **Filtro de Dia Atual (Em Andamento):** Checkbox `Ignorar Dia Atual (Em Andamento)` para desconsiderar automaticamente marcações incompletas de hoje no saldo total acumulado e nas pendências da IA.
- **Auditoria Interativa & Recálculo por IA:** Painel de análise avançada por IA que permite enviar instruções de ajuste em linguagem natural (ex: *"No dia 15/07 considere saída às 18:00 e abone o dia 10/07"*). A IA reanalisa a jornada, recalcula os saldos e aplica os ajustes diretamente na tabela do aplicativo.
- **Simulação e Edição de Ponto (Modo Auditoria):** Dê um duplo clique em qualquer marcação na tabela para editar ou apagar horários. Clique no botão **"Recalcular Ponto"** para verificar em tempo real como ficará o saldo acumulado antes de exportar.
- **Regra de Almoço Inteligente:** Computação automática do intervalo de almoço. Se o colaborador retornar antes de 1 hora de intervalo, a antecipação não gera saldo de horas extras (computa no mínimo 1 hora inteira de intervalo). Se retornar após 1 hora, o atraso é contabilizado normalmente na jornada.
- **Exportação Formatada e Auditável para Excel:** Gera planilhas Excel organizadas com cabeçalhos dinâmicos, saldo geral acumulado e cores auditáveis.
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
