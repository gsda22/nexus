# -*- coding: utf-8 -*-
import streamlit as st
import sqlite3
import hashlib
from fpdf import FPDF
from datetime import datetime, date, time
import base64
import os
import json

# ==========================
# CONFIG INICIAIS
# ==========================
st.set_page_config(page_title="Nexus PPN - Ocorrências", layout="wide")
DB_FILE = 'ocorrencias.db'
ADMIN_USER = 'admin'
ADMIN_PASS = hashlib.sha256('123456'.encode()).hexdigest()
LOGOUT_TIMEOUT = 300  # segundos (5 min)

CATEGORIAS = [
    'JURÍDICO', 'REUNIÃO', 'MANUTENÇÃO', 'ABORDAGEM', 'INCIDENTE', 'TROCA DE PRODUTO', 'RECLAMAÇÃO', 'ENTREGA DE CURRÍCULO',
    'ENTREVISTA', 'ENTRADA DE PROMOTOR', 'SAÍDA DE PROMOTOR',
    'BATIDA DE CAIXA', 'TROCA DE TURNO'
]

LOJAS_INICIAIS = [
    'SUSSUARANA', 'VIDA NOVA', 'ALPHAVILLE', 'VILAS',
    'BURAQUINHO', 'ITINGA', 'TANCREDO NEVES'
]

# ==========================
# DB - CONEXÃO GLOBAL
# ==========================
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()

def init_db():
    # usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        usuario TEXT PRIMARY KEY,
        senha TEXT
    )''')

    # lojas
    c.execute('''CREATE TABLE IF NOT EXISTS lojas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE
    )''')

    # relacao usuario-lojas
    c.execute('''CREATE TABLE IF NOT EXISTS usuario_lojas (
        usuario TEXT,
        loja_id INTEGER,
        FOREIGN KEY (usuario) REFERENCES usuarios(usuario),
        FOREIGN KEY (loja_id) REFERENCES lojas(id)
    )''')

    # ocorrencias
    c.execute('''CREATE TABLE IF NOT EXISTS ocorrencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT,
        categoria TEXT,
        data TEXT,
        hora TEXT,
        texto TEXT,
        anexos TEXT,         -- JSON: [[nome, base64], ...]
        assinatura1 TEXT,    -- usuário que registrou
        loja TEXT
    )''')
    conn.commit()

    # lojas iniciais
    for loja in LOJAS_INICIAIS:
        c.execute('INSERT OR IGNORE INTO lojas (nome) VALUES (?)', (loja,))
    conn.commit()

    # admin
    c.execute('SELECT 1 FROM usuarios WHERE usuario=?', (ADMIN_USER,))
    if not c.fetchone():
        c.execute('INSERT INTO usuarios (usuario, senha) VALUES (?,?)', (ADMIN_USER, ADMIN_PASS))
        conn.commit()

init_db()

# ==========================
# HELPERS
# ==========================
def hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()

def dumps_json(obj) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return "[]"

def loads_anexos(s: str):
    """Lê anexos tanto do formato JSON quanto do legado (eval)."""
    if not s:
        return []
    try:
        v = json.loads(s)
        if isinstance(v, list):
            return v
        return []
    except Exception:
        # fallback para registros antigos que foram salvos com str(list(...))
        try:
            return list(eval(s))
        except Exception:
            return []

def str_latin1_safe(x: str) -> str:
    """Garante que a string cabe em latin1, trocando chars inválidos por '?'. """
    if x is None:
        return ""
    return x.encode("latin1", "replace").decode("latin1")

# ==========================
# PDF (Arial padrão, sem TTF externo)
# ==========================
def gerar_pdf(o_row):
    """
    o_row é a tupla completa da tabela 'ocorrencias'
    Índices:
      0:id 1:titulo 2:categoria 3:data 4:hora 5:texto 6:anexos 7:assinatura1 8:loja
    """
    pdf = FPDF()
    pdf.add_page()

    # Cabeçalho
    if os.path.exists('logo.png'):
        try:
            pdf.image('logo.png', 10, 8, 33)
        except Exception:
            pass

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, str_latin1_safe('Nexus PPN: Controle Inteligente de Ocorrências'), 0, 1, 'C')
    pdf.ln(5)

    pdf.set_font("Arial", "", 10)
    # Campos
    pdf.cell(0, 8, str_latin1_safe(f'Título: {o_row[1] or ""}'), 0, 1)
    pdf.cell(0, 8, str_latin1_safe(f'Categoria: {o_row[2] or ""}'), 0, 1)
    pdf.cell(0, 8, str_latin1_safe(f'Loja: {o_row[8] or ""}'), 0, 1)

    # Data/Hora (formatar se possível)
    data_fmt = o_row[3]
    hora_fmt = o_row[4]
    try:
        data_fmt = datetime.strptime(o_row[3], '%Y-%m-%d').strftime('%d/%m/%Y')
    except Exception:
        pass
    try:
        hora_fmt = datetime.strptime(o_row[4], '%H:%M:%S').strftime('%H:%M')
    except Exception:
        pass
    pdf.cell(0, 8, str_latin1_safe(f'Data/Hora: {data_fmt} {hora_fmt}'), 0, 1)

    # Texto
    pdf.ln(2)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 6, str_latin1_safe(f'Ocorrência: {o_row[5] or ""}'))

    # Anexos
    anexos = loads_anexos(o_row[6])
    if anexos:
        pdf.ln(4)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 8, str_latin1_safe('Anexos:'), 0, 1)
        pdf.set_font("Arial", "", 10)
        for nome, _dados in anexos:
            pdf.cell(0, 6, str_latin1_safe(f'- {nome}'), 0, 1)

    # Assinatura
    pdf.ln(4)
    pdf.cell(0, 8, str_latin1_safe(f'Assinatura: {o_row[7] or "Pendente"}'), 0, 1)

    # Retorna bytes prontos
    return pdf.output(dest='S').encode('latin1')

# ==========================
# SESSÃO
# ==========================
if 'last_activity' not in st.session_state:
    st.session_state.last_activity = datetime.now()
if 'usuario' in st.session_state and (datetime.now() - st.session_state.last_activity).seconds > LOGOUT_TIMEOUT:
    del st.session_state['usuario']
    del st.session_state['lojas_acesso'] if 'lojas_acesso' in st.session_state else None
    st.warning('Sessão expirada!')
    st.rerun()

# ==========================
# LOGIN
# ==========================
if 'usuario' not in st.session_state:
    st.title('Login - Nexus PPN')
    if os.path.exists('logo.png'):
        st.image('logo.png', width=150)

    usuario = st.text_input('Usuário')
    senha = s
