import streamlit as st
import sqlite3
from fpdf import FPDF
from datetime import datetime

# =========================
# Funções auxiliares
# =========================

def init_db():
    conn = sqlite3.connect("ocorrencias.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS ocorrencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            loja TEXT,
            categoria TEXT,
            descricao TEXT,
            usuario TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE,
            senha TEXT,
            perfil TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_usuario(usuario, senha, perfil):
    conn = sqlite3.connect("ocorrencias.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO usuarios (usuario, senha, perfil) VALUES (?, ?, ?)", (usuario, senha, perfil))
        conn.commit()
    except sqlite3.IntegrityError:
        st.error("Usuário já existe!")
    conn.close()

def validar_usuario(usuario, senha):
    conn = sqlite3.connect("ocorrencias.db")
    c = conn.cursor()
    c.execute("SELECT perfil FROM usuarios WHERE usuario=? AND senha=?", (usuario, senha))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def salvar_ocorrencia(data, loja, categoria, descricao, usuario):
    conn = sqlite3.connect("ocorrencias.db")
    c = conn.cursor()
    c.execute("INSERT INTO ocorrencias (data, loja, categoria, descricao, usuario) VALUES (?, ?, ?, ?, ?)",
              (data, loja, categoria, descricao, usuario))
    conn.commit()
    conn.close()

def listar_ocorrencias():
    conn = sqlite3.connect("ocorrencias.db")
    c = conn.cursor()
    c.execute("SELECT * FROM ocorrencias ORDER BY id DESC")
    data = c.fetchall()
    conn.close()
    return data

def gerar_pdf(ocorrencia):
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Relatório de Ocorrência", ln=True, align="C")

    pdf.ln(10)
    pdf.set_font("Arial", "", 12)

    campos = ["ID", "Data", "Loja", "Categoria", "Descrição", "Usuário"]
    for i, chave in enumerate(campos):
        valor = ocorrencia[i]
        pdf.multi_cell(0, 10, f"{chave}: {valor}")

    return pdf.output(dest="S").encode("latin1")

# =========================
# APP STREAMLIT
# =========================

init_db()

st.title("📋 Sistema de Ocorrências - Prevenção")

# Login
if "usuario" not in st.session_state:
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Login"):
        perfil = validar_usuario(usuario, senha)
        if perfil:
            st.session_state.usuario = usuario
            st.session_state.perfil = perfil
            st.success(f"Bem-vindo, {usuario}!")
        else:
            st.error("Usuário ou senha inválidos.")
    st.stop()

# Menu
menu = ["Registrar Ocorrência", "Consultar Ocorrências"]
if st.session_state.perfil == "admin":
    menu.append("Gerenciar Usuários")

escolha = st.sidebar.radio("Menu", menu)

# =========================
# REGISTRAR OCORRÊNCIA
# =========================
if escolha == "Registrar Ocorrência":
    st.subheader("➕ Registrar Ocorrência")
    data = st.date_input("Data", datetime.today())
    loja = st.text_input("Loja")
    categoria = st.selectbox("Categoria", [
        "FURTO",
        "PERDA",
        "QUEBRA",
        "MANUTENÇÃO",
        "ABORDAGEM",
        "REUNIÃO"
    ])
    descricao = st.text_area("Descrição")

    if st.button("Salvar Ocorrência"):
        salvar_ocorrencia(str(data), loja, categoria, descricao, st.session_state.usuario)
        st.success("Ocorrência registrada com sucesso!")

# =========================
# CONSULTAR OCORRÊNCIAS
# =========================
elif escolha == "Consultar Ocorrências":
    st.subheader("🔍 Consultar Ocorrências")
    dados = listar_ocorrencias()
    if dados:
        for row in dados:
            with st.expander(f"Ocorrência #{row[0]} - {row[3]}"):
                st.write(f"**Data:** {row[1]}")
                st.write(f"**Loja:** {row[2]}")
                st.write(f"**Categoria:** {row[3]}")
                st.write(f"**Descrição:** {row[4]}")
                st.write(f"**Usuário:** {row[5]}")

                if st.download_button("📥 Baixar PDF", gerar_pdf(row), file_name=f"ocorrencia_{row[0]}.pdf"):
                    st.success("Download iniciado!")
    else:
        st.info("Nenhuma ocorrência registrada.")

# =========================
# GERENCIAR USUÁRIOS (APENAS ADMIN)
# =========================
elif escolha == "Gerenciar Usuários" and st.session_state.perfil == "admin":
    st.subheader("👤 Gerenciar Usuários")
    novo_usuario = st.text_input("Novo Usuário")
    nova_senha = st.text_input("Senha", type="password")
    perfil = st.selectbox("Perfil", ["usuario", "admin"])
    if st.button("Adicionar Usuário"):
        add_usuario(novo_usuario, nova_senha, perfil)
        st.success("Usuário adicionado com sucesso!")

# =========================
# LOGOUT
# =========================
if st.sidebar.button("Logout"):
    if 'lojas_acesso' in st.session_state:
        del st.session_state['lojas_acesso']
    del st.session_state['usuario']
    del st.session_state['perfil']
    st.experimental_rerun()
