"""
Serviço de geração de justificativa de ponto em PDF e envio SMTP.
"""
import os
import re
import datetime
import smtplib
import base64
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Dict, Optional, Tuple

from playwright.sync_api import sync_playwright

from src.utils.formatters import formatar_mes_competencia, obter_mes_extenso
from src.utils.paths import get_template_path

logger = logging.getLogger(__name__)

DIAS_ORDEM = [
    "SEGUNDA FEIRA",
    "TERÇA FEIRA",
    "QUARTA FEIRA",
    "QUINTA FEIRA",
    "SEXTA FEIRA",
    "SÁBADO / DOMINGO"
]

def normalizar_dia(d_str: str) -> str:
    """Normaliza o nome do dia da semana para o padrão do formulário."""
    if not d_str:
        return ""
    s = str(d_str).upper().strip()
    if "SEG" in s:
        return "SEGUNDA FEIRA"
    elif "TER" in s:
        return "TERÇA FEIRA"
    elif "QUA" in s:
        return "QUARTA FEIRA"
    elif "QUI" in s:
        return "QUINTA FEIRA"
    elif "SEX" in s:
        return "SEXTA FEIRA"
    elif "SÁB" in s or "SAB" in s or "DOM" in s:
        return "SÁBADO / DOMINGO"
    return s

def gerar_pdf_justificativa(
    colaborador_nome: str,
    colaborador_funcao: str,
    mes_competencia_str: str,
    data_solicitacao: str,
    justificativa_geral: str,
    gestor_nome: str,
    rh_nome: str,
    itens_ponto: List[Dict],
    output_pdf_path: str,
    template_path: Optional[str] = None,
    auto_assinar_colaborador: bool = False,
    assinatura_img_path: Optional[str] = None,
    data_assinatura_str: Optional[str] = None
) -> str:
    """
    Injeta os dados no template HTML e gera um arquivo PDF em tamanho A4 via Playwright.
    """
    mes_extenso = formatar_mes_competencia(mes_competencia_str)

    if not template_path or not os.path.exists(template_path):
        template_path = get_template_path("justificativa_template.html")

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    itens_por_dia = {dia: [] for dia in DIAS_ORDEM}
    itens_outros = []

    for item in itens_ponto:
        dia_norm = normalizar_dia(item.get("dia_semana", ""))
        if dia_norm in itens_por_dia:
            itens_por_dia[dia_norm].append(item)
        else:
            itens_outros.append(item)

    linhas_html = ""
    for dia in DIAS_ORDEM:
        lista_dia = itens_por_dia[dia]
        if lista_dia:
            for item in lista_dia:
                e1, s1 = item.get("e1", ""), item.get("s1", "")
                e2, s2 = item.get("e2", ""), item.get("s2", "")
                e3, s3 = item.get("e3", ""), item.get("s3", "")
                motivo = item.get("motivo", "")
                data_str = item.get("data", "")

                punches_list = [
                    ("ENTRADA:", e1),
                    ("SAÍDA REFEIÇÃO:", s1),
                    ("RETORNO REFEIÇÃO:", e2),
                    ("SAÍDA:", s2)
                ]
                if e3 or s3:
                    punches_list.append(("ENTRADA 2:", e3))
                    punches_list.append(("SAÍDA 2:", s3))

                num_rows = len(punches_list)
                label_0, val_0 = punches_list[0]
                linhas_html += f"""
                <tr>
                    <td rowspan="{num_rows}" class="day-title">{dia}</td>
                    <td rowspan="{num_rows}" class="date-cell">{data_str}</td>
                    <td class="punch-label-cell">{label_0}</td>
                    <td class="punch-value-cell">{val_0}</td>
                    <td rowspan="{num_rows}" class="motivo-cell">{motivo}</td>
                    <td rowspan="{num_rows}" class="visto-cell"></td>
                </tr>
                """
                for label, val in punches_list[1:]:
                    linhas_html += f"""
                    <tr>
                        <td class="punch-label-cell">{label}</td>
                        <td class="punch-value-cell">{val}</td>
                    </tr>
                    """
        else:
            punches_list = [
                ("ENTRADA:", ""),
                ("SAÍDA REFEIÇÃO:", ""),
                ("RETORNO REFEIÇÃO:", ""),
                ("SAÍDA:", "")
            ]
            num_rows = len(punches_list)
            label_0, val_0 = punches_list[0]
            linhas_html += f"""
            <tr>
                <td rowspan="{num_rows}" class="day-title">{dia}</td>
                <td rowspan="{num_rows}" class="date-cell"></td>
                <td class="punch-label-cell">{label_0}</td>
                <td class="punch-value-cell">{val_0}</td>
                <td rowspan="{num_rows}" class="motivo-cell"></td>
                <td rowspan="{num_rows}" class="visto-cell"></td>
            </tr>
            """
            for label, val in punches_list[1:]:
                linhas_html += f"""
                <tr>
                    <td class="punch-label-cell">{label}</td>
                    <td class="punch-value-cell">{val}</td>
                </tr>
                """

    for item in itens_outros:
        e1, s1 = item.get("e1", ""), item.get("s1", "")
        e2, s2 = item.get("e2", ""), item.get("s2", "")
        e3, s3 = item.get("e3", ""), item.get("s3", "")
        motivo = item.get("motivo", "")
        dia_sem = str(item.get("dia_semana", "")).upper()
        data_str = item.get("data", "")

        punches_list = [
            ("ENTRADA:", e1),
            ("SAÍDA REFEIÇÃO:", s1),
            ("RETORNO REFEIÇÃO:", e2),
            ("SAÍDA:", s2)
        ]
        if e3 or s3:
            punches_list.append(("ENTRADA 2:", e3))
            punches_list.append(("SAÍDA 2:", s3))

        num_rows = len(punches_list)
        label_0, val_0 = punches_list[0]
        linhas_html += f"""
        <tr>
            <td rowspan="{num_rows}" class="day-title">{dia_sem}</td>
            <td rowspan="{num_rows}" class="date-cell">{data_str}</td>
            <td class="punch-label-cell">{label_0}</td>
            <td class="punch-value-cell">{val_0}</td>
            <td rowspan="{num_rows}" class="motivo-cell">{motivo}</td>
            <td rowspan="{num_rows}" class="visto-cell"></td>
        </tr>
        """
        for label, val in punches_list[1:]:
            linhas_html += f"""
            <tr>
                <td class="punch-label-cell">{label}</td>
                <td class="punch-value-cell">{val}</td>
            </tr>
            """

    if justificativa_geral and justificativa_geral.strip():
        html_just_geral = f"""
        <div class="section-banner" style="margin-top: 10px;">JUSTIFICATIVA GERAL / OBSERVAÇÕES</div>
        <div style="padding: 8px 10px; border: 1px solid #81c784; background-color: #f1f8e9; margin-bottom: 12px; border-radius: 3px; font-size: 10px; color: #1b5e20;">
            {justificativa_geral.strip().replace(chr(10), '<br/>')}
        </div>
        """
    else:
        html_just_geral = ""

    if not data_assinatura_str:
        if auto_assinar_colaborador:
            data_assinatura_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        else:
            data_assinatura_str = "____/____/________"

    # Construção da Assinatura
    colab_sig_html = '<div class="signature-line-rule"></div>'
    if assinatura_img_path and os.path.isfile(assinatura_img_path):
        try:
            with open(assinatura_img_path, "rb") as img_f:
                b64_data = base64.b64encode(img_f.read()).decode("utf-8")
            ext = os.path.splitext(assinatura_img_path)[1].lower().replace(".", "")
            mime = "image/png" if ext == "png" else "image/jpeg"
            colab_sig_html = f'''<div style="text-align: center; margin-bottom: 2px;">
                <img src="data:{mime};base64,{b64_data}" style="max-height: 48px; max-width: 150px; object-fit: contain;"/>
            </div>'''
        except Exception:
            colab_sig_html = '<div class="signature-line-rule"></div>'
    elif auto_assinar_colaborador:
        colab_sig_html = f'''<div style="border: 1px dashed #166534; background-color: #f0fdf4; color: #166534; padding: 4px 6px; border-radius: 4px; font-size: 8px; line-height: 1.25; text-align: center; margin-bottom: 4px;">
            <strong style="font-size: 9px; color: #15803d;">✔ ASSINADO DIGITALMENTE</strong><br/>
            <span>{colaborador_nome or "Colaborador"}</span><br/>
            <span style="font-size: 7px; color: #166534;">Data: {data_assinatura_str}</span>
        </div>'''

    content = template.replace("{{ colaborador_nome }}", colaborador_nome or "")
    content = content.replace("{{ colaborador_funcao }}", colaborador_funcao or "")
    content = content.replace("{{ mes_competencia }}", mes_extenso)
    content = content.replace("{{ data_solicitacao }}", data_solicitacao or datetime.datetime.now().strftime("%d/%m/%Y"))
    content = content.replace("{{ justificativa_geral }}", html_just_geral)
    content = content.replace("{{ gestor_nome }}", gestor_nome or "Gestor Imediato")
    content = content.replace("{{ rh_nome }}", rh_nome or "Recursos Humanos")
    content = content.replace("{{ linhas_ponto_html }}", linhas_html)
    content = content.replace("{{ colaborador_assinatura_element }}", colab_sig_html)
    content = content.replace("{{ colaborador_data_assinatura }}", data_assinatura_str)

    temp_html_path = output_pdf_path.replace(".pdf", ".temp.html")
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(content)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("file:///" + temp_html_path.replace("\\", "/"))
            page.pdf(path=output_pdf_path, format="A4", print_background=True)
            browser.close()
    finally:
        if os.path.exists(temp_html_path):
            try:
                os.remove(temp_html_path)
            except Exception:
                pass

    return output_pdf_path

def enviar_email_smtp(
    smtp_server: str,
    smtp_port: int,
    remetente_email: str,
    remetente_senha: str,
    destinatario_email: str,
    assunto: str,
    corpo_texto: str,
    caminho_pdf: str
) -> bool:
    """Envia o PDF gerado como anexo por e-mail via SMTP."""
    msg = MIMEMultipart()
    msg['From'] = remetente_email
    msg['To'] = destinatario_email
    msg['Subject'] = assunto
    msg.attach(MIMEText(corpo_texto, 'plain', 'utf-8'))

    with open(caminho_pdf, 'rb') as attachment:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(caminho_pdf)}"')
        msg.attach(part)

    with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as server:
        server.starttls()
        server.login(remetente_email, remetente_senha)
        server.send_message(msg)

    return True
