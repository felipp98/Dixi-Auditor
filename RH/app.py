import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pdfplumber
from PyPDF2 import PdfReader, PdfWriter

from autentique_service import enviar_documento
from database import (
    get_employee_by_codigo,
    get_all_employees,
    save_employee,
    get_token,
    save_token,
    create_tables
)

create_tables()


class PDFProcessorApp:

    def __init__(self, root):
        self.root = root
        self.root.title("RH - Holerites + Autentique")
        self.root.geometry("600x420")

        self.input_path = ""
        self.output_path = ""

        self.build_menu()

    # =====================================
    # MENU PRINCIPAL
    # =====================================

    def build_menu(self):

        frame = tk.Frame(self.root)
        frame.pack(pady=40)

        tk.Button(frame, text="Processar PDF", width=30, command=self.open_processor).pack(pady=5)
        tk.Button(frame, text="Cadastrar / Editar Funcionários", width=30, command=self.open_employee_screen).pack(pady=5)
        tk.Button(frame, text="Configurar Token Autentique", width=30, command=self.open_token_screen).pack(pady=5)

    # =====================================
    # TELA PROCESSAMENTO
    # =====================================

    def open_processor(self):

        window = tk.Toplevel(self.root)
        window.title("Processar Holerites")
        window.geometry("520x360")

        tk.Label(window, text="Arquivo PDF:", font=("Arial", 10, "bold")).pack(pady=5)

        input_label = tk.Label(window, text="Nenhum arquivo selecionado", wraplength=480)
        input_label.pack()

        def select_pdf():
            path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
            if path:
                self.input_path = path
                input_label.config(text=path)

        tk.Button(window, text="Selecionar PDF", command=select_pdf).pack(pady=5)

        tk.Label(window, text="Pasta de destino:", font=("Arial", 10, "bold")).pack(pady=5)

        output_label = tk.Label(window, text="Nenhuma pasta selecionada", wraplength=480)
        output_label.pack()

        def select_folder():
            path = filedialog.askdirectory()
            if path:
                self.output_path = path
                output_label.config(text=path)

        tk.Button(window, text="Selecionar Pasta", command=select_folder).pack(pady=5)

        progress = ttk.Progressbar(window, length=460)
        progress.pack(pady=15)

        def start_processing():

            if not self.input_path or not self.output_path:
                messagebox.showerror("Erro", "Selecione PDF e pasta.")
                return

            token = get_token()
            if not token:
                messagebox.showerror("Erro", "Token não configurado.")
                return

            threading.Thread(target=process_pdf).start()

        def process_pdf():

            try:
                token = get_token()
                reader = PdfReader(self.input_path)

                with pdfplumber.open(self.input_path) as pdf:

                    total = len(pdf.pages)
                    progress["maximum"] = total

                    for i, page in enumerate(pdf.pages):

                        text = page.extract_text()
                        if not text:
                            continue

                        codigo, nome = self.extract_nome_codigo(text)

                        if not nome:
                            continue

                        funcionario = get_employee_by_codigo(codigo)
                        if not funcionario:
                            continue

                        _, _, email = funcionario

                        writer = PdfWriter()
                        writer.add_page(reader.pages[i])

                        safe_name = re.sub(r'[^\w\s-]', '', nome).replace(" ", "_")
                        filename = f"{codigo}_{safe_name}.pdf"
                        output_file = os.path.join(self.output_path, filename)

                        with open(output_file, "wb") as f:
                            writer.write(f)

                        # Detectar assinatura e data
                        palavras = page.extract_words()
                        largura = page.width
                        altura = page.height

                        posicoes = []

                        for palavra in palavras:
                            texto_palavra = palavra["text"].lower()

                            if texto_palavra == "assinatura":

                                x_percent = (palavra["x0"] / largura) * 100
                                y_percent = (palavra["top"] / altura) * 100

                                posicoes.append({
                                    "x": str(x_percent - 7),   # 5% para esquerda
                                    "y": str(y_percent - 5),   # 5% para cima
                                    "z": 1,
                                    "element": "SIGNATURE"
                                })


                            if texto_palavra == "data":

                                x_percent = (palavra["x0"] / largura) * 100
                                y_percent = (palavra["top"] / altura) * 100

                                posicoes.append({
                                    "x": str(x_percent - 10),
                                    "y": str(y_percent - 3),
                                    "z": 1,
                                    "element": "DATE"
                                })

                        enviar_documento(
                            token,
                            output_file,
                            filename,
                            email,
                            posicoes
                        )

                        progress["value"] = i + 1

                messagebox.showinfo("Sucesso", "Processamento concluído!")

            except Exception as e:
                messagebox.showerror("Erro", str(e))

        tk.Button(window, text="Processar e Enviar", command=start_processing).pack(pady=10)

    # =====================================
    # EXTRAÇÃO NOME/CÓDIGO
    # =====================================

    def extract_nome_codigo(self, text):

        linhas = text.split("\n")

        for linha in linhas:
            linha = linha.strip()

            if re.match(r"^\d+\s+", linha):

                partes = linha.split()
                codigo = partes[0]
                nome_partes = []

                for parte in partes[1:]:
                    if re.search(r"\d", parte):
                        break
                    nome_partes.append(parte)

                nome = " ".join(nome_partes)

                if len(nome) > 5:
                    return codigo, nome

        return None, None

    # =====================================
    # TELA FUNCIONÁRIOS
    # =====================================

    def open_employee_screen(self):

        window = tk.Toplevel(self.root)
        window.title("Funcionários")
        window.geometry("500x400")

        tk.Label(window, text="Código").pack()
        codigo_entry = tk.Entry(window)
        codigo_entry.pack()

        tk.Label(window, text="Nome").pack()
        nome_entry = tk.Entry(window)
        nome_entry.pack()

        tk.Label(window, text="Email").pack()
        email_entry = tk.Entry(window)
        email_entry.pack()

        def salvar():
            codigo = codigo_entry.get()
            nome = nome_entry.get()
            email = email_entry.get()

            if not codigo or not nome or not email:
                messagebox.showerror("Erro", "Preencha todos os campos.")
                return

            save_employee(codigo, nome, email)
            atualizar_lista()

        tk.Button(window, text="Salvar / Atualizar", command=salvar).pack(pady=10)

        tree = ttk.Treeview(window, columns=("codigo", "nome", "email"), show="headings")
        tree.heading("codigo", text="Código")
        tree.heading("nome", text="Nome")
        tree.heading("email", text="Email")
        tree.pack(fill="both", expand=True)

        def atualizar_lista():
            for item in tree.get_children():
                tree.delete(item)
            for emp in get_all_employees():
                tree.insert("", "end", values=emp)

        atualizar_lista()

    # =====================================
    # TELA TOKEN
    # =====================================

    def open_token_screen(self):

        window = tk.Toplevel(self.root)
        window.title("Token Autentique")
        window.geometry("400x200")

        tk.Label(window, text="Token da API").pack(pady=10)

        token_entry = tk.Entry(window, width=50)
        token_entry.pack()

        token_atual = get_token()
        if token_atual:
            token_entry.insert(0, token_atual)

        def salvar_token_action():
            token = token_entry.get()
            if not token:
                messagebox.showerror("Erro", "Token inválido.")
                return
            save_token(token)
            messagebox.showinfo("Sucesso", "Token salvo.")

        tk.Button(window, text="Salvar Token", command=salvar_token_action).pack(pady=15)


# =====================================
# EXECUÇÃO
# =====================================

if __name__ == "__main__":
    root = tk.Tk()
    app = PDFProcessorApp(root)
    root.mainloop()