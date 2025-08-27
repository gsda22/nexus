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
    'JURÍDICO', 'TROCA DE PRODUTO', 'RECLAMAÇÃO', 'ENTREGA DE CURRÍCULO',
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
    senha = st.text_input('Senha', type='password')

    colA, colB = st.columns(2)
    with colA:
        if st.button('Entrar', use_container_width=True):
            c.execute('SELECT * FROM usuarios WHERE usuario = ? AND senha = ?', (usuario, hash_senha(senha)))
            user_row = c.fetchone()
            if user_row:
                # Carrega lojas do usuário
                c.execute('''
                    SELECT lojas.id, lojas.nome
                    FROM lojas
                    JOIN usuario_lojas ON lojas.id = usuario_lojas.loja_id
                    WHERE usuario_lojas.usuario = ?
                ''', (usuario,))
                lojas_acesso = c.fetchall()
                st.session_state.usuario = usuario
                st.session_state.lojas_acesso = lojas_acesso
                st.session_state.last_activity = datetime.now()
                st.rerun()
            else:
                st.error('Usuário ou senha inválidos')

    with colB:
        st.info('Usuário admin padrão: admin / 123456')

# ==========================
# ÁREA LOGADA
# ==========================
else:
    st.session_state.last_activity = datetime.now()
    st.sidebar.write(f'Logado como: **{st.session_state.usuario}**')
    if st.sidebar.button('Sair'):
        del st.session_state['usuario']
        st.rerun()

    st.title(f'Nexus PPN - Usuário: {st.session_state.usuario}')
    menu = st.sidebar.selectbox(
        'Menu',
        ['Registrar Ocorrência', 'Consultar', 'Validação', 'Gerenciar Usuários']
        if st.session_state.usuario == ADMIN_USER else ['Registrar Ocorrência', 'Consultar', 'Validação']
    )

    # ==========================
    # REGISTRAR OCORRÊNCIA
    # ==========================
    if menu == 'Registrar Ocorrência':
        st.header('Registrar Ocorrência')

        col1, col2 = st.columns(2)
        with col1:
            titulo = st.text_input('Título')
            categoria = st.selectbox('Categoria', CATEGORIAS)

        if st.session_state.get('lojas_acesso'):
            loja_selecionada = st.selectbox('Selecione a loja', [l[1] for l in st.session_state.lojas_acesso])
        else:
            st.warning('Nenhuma loja atribuída ao usuário.')
            loja_selecionada = None

        col3, col4 = st.columns(2)
        with col3:
            data_sel = st.date_input('Data', value=date.today())
        with col4:
            hora_sel = st.time_input('Hora', value=datetime.now().time())

        texto = st.text_area('Ocorrência')
        anexos_files = st.file_uploader('Anexos', accept_multiple_files=True)

        if st.button('Salvar', type='primary', use_container_width=True) and loja_selecionada:
            anexos = []
            for a in anexos_files:
                try:
                    b64 = base64.b64encode(a.read()).decode()
                    anexos.append([a.name, b64])
                except Exception:
                    pass

            c.execute('''
                INSERT INTO ocorrencias (titulo, categoria, data, hora, texto, anexos, assinatura1, loja)
                VALUES (?,?,?,?,?,?,?,?)
            ''', (
                titulo.strip(),
                categoria,
                str(data_sel),
                str(hora_sel),
                texto,
                dumps_json(anexos),
                st.session_state.usuario,
                loja_selecionada
            ))
            conn.commit()
            st.success('Ocorrência registrada com sucesso!')

    # ==========================
    # CONSULTAR
    # ==========================
    elif menu == 'Consultar':
        st.header('Consultar Ocorrências')

        # filtros
        colf1, colf2, colf3 = st.columns([1,1,1])
        with colf1:
            data_ini = st.date_input('Data inicial', value=date.today())
        with colf2:
            data_fim = st.date_input('Data final', value=date.today())
        with colf3:
            loja_filtro = st.selectbox('Filtrar por loja', [l[1] for l in st.session_state.lojas_acesso]) if st.session_state.get('lojas_acesso') else st.text_input('Loja')

        if st.button('Filtrar', use_container_width=True):
            c.execute('''
                SELECT * FROM ocorrencias
                WHERE date(data) BETWEEN ? AND ? AND loja = ?
                ORDER BY id DESC
            ''', (str(data_ini), str(data_fim), loja_filtro))
            ocorrencias = c.fetchall()

            if not ocorrencias:
                st.info('Nenhuma ocorrência encontrada para o período/loja selecionados.')

            for o in ocorrencias:
                col1, col2, col3 = st.columns([1,2,1])
                with col1:
                    st.subheader(f'{o[1]}')
                    st.write(f"**Categoria:** {o[2]}")
                    try:
                        data_formatada = datetime.strptime(o[3], '%Y-%m-%d').strftime('%d/%m/%Y')
                    except Exception:
                        data_formatada = o[3]
                    try:
                        hora_formatada = datetime.strptime(o[4], '%H:%M:%S').strftime('%H:%M')
                    except Exception:
                        hora_formatada = o[4]
                    st.write(f"**Data/Hora:** {data_formatada} {hora_formatada}")
                    st.write(f"**Loja:** {o[8]}")
                    st.write(f"**Assinatura:** {o[7] or 'Pendente'}")

                with col2:
                    st.write(o[5])

                with col3:
                    anexos = loads_anexos(o[6])
                    if anexos:
                        st.write('**Anexos:**')
                        for nome, dados in anexos:
                            try:
                                # Re-encode para garantir base64 válido de file
                                b64 = base64.b64encode(base64.b64decode(dados)).decode()
                                href = f'<a href="data:file/octet-stream;base64,{b64}" download="{nome}">{nome}</a>'
                                st.markdown(href, unsafe_allow_html=True)
                            except Exception:
                                pass

                    # PDF
                    try:
                        pdf_bytes = gerar_pdf(o)
                        st.download_button(
                            label="📄 Baixar PDF",
                            data=pdf_bytes,
                            file_name=f"ocorrencia_{o[0]}.pdf",
                            mime="application/pdf",
                            key=f"pdf_{o[0]}"
                        )
                    except Exception as e:
                        st.error(f"Falha ao gerar PDF (ID {o[0]}).")

    # ==========================
    # VALIDAÇÃO / EXCLUSÃO
    # ==========================
    elif menu == 'Validação':
        st.header("Validação de Ocorrências")
        c.execute('SELECT * FROM ocorrencias ORDER BY id DESC')
        ocorrencias = c.fetchall()

        if not ocorrencias:
            st.info("Nenhuma ocorrência registrada.")
        for o in ocorrencias:
            col1, col2, col3 = st.columns([1,2,1])
            with col1:
                st.subheader(f'{o[1]}')
                st.write(f"**Categoria:** {o[2]}")
                try:
                    data_formatada = datetime.strptime(o[3], '%Y-%m-%d').strftime('%d/%m/%Y')
                except Exception:
                    data_formatada = o[3]
                try:
                    hora_formatada = datetime.strptime(o[4], '%H:%M:%S').strftime('%H:%M')
                except Exception:
                    hora_formatada = o[4]
                st.write(f"**Data/Hora:** {data_formatada} {hora_formatada}")
                st.write(f"**Loja:** {o[8]}")
                st.write(f"**Assinatura:** {o[7] or 'Pendente'}")
            with col2:
                st.write(o[5])
            with col3:
                anexos = loads_anexos(o[6])
                if anexos:
                    st.write('**Anexos:**')
                    for nome, dados in anexos:
                        try:
                            b64 = base64.b64encode(base64.b64decode(dados)).decode()
                            href = f'<a href="data:file/octet-stream;base64,{b64}" download="{nome}">{nome}</a>'
                            st.markdown(href, unsafe_allow_html=True)
                        except Exception:
                            pass

                try:
                    pdf_bytes = gerar_pdf(o)
                    st.download_button(
                        label="📄 Baixar PDF",
                        data=pdf_bytes,
                        file_name=f"ocorrencia_{o[0]}.pdf",
                        mime="application/pdf",
                        key=f"pdf_val_{o[0]}"
                    )
                except Exception:
                    st.error(f"Falha ao gerar PDF (ID {o[0]}).")

                # Permissão para excluir: admin ou o autor
                if st.session_state.usuario == ADMIN_USER or st.session_state.usuario == o[7]:
                    if st.button('Excluir', key=f'excluir_{o[0]}'):
                        c.execute('DELETE FROM ocorrencias WHERE id = ?', (o[0],))
                        conn.commit()
                        st.success("Ocorrência excluída.")
                        st.rerun()

    # ==========================
    # GERENCIAR USUÁRIOS (ADMIN)
    # ==========================
    elif menu == 'Gerenciar Usuários' and st.session_state.usuario == ADMIN_USER:
        st.header("Gerenciar Usuários")

        # Selecionar usuário (exceto admin)
        c.execute('SELECT usuario FROM usuarios WHERE usuario != ?', (ADMIN_USER,))
        usuarios = [u[0] for u in c.fetchall()]
        if not usuarios:
            st.info("Nenhum usuário cadastrado além do admin.")
        else:
            user_sel = st.selectbox("Selecionar usuário", usuarios)

            # Lojas disponíveis
            c.execute('SELECT * FROM lojas')
            lojas = c.fetchall()
            lojas_dict = {loja[1]: loja[0] for loja in lojas}

            # Lojas atribuídas
            c.execute('SELECT loja_id FROM usuario_lojas WHERE usuario = ?', (user_sel,))
            lojas_atr_ids = [l[0] for l in c.fetchall()]
            lojas_atr_nomes = [l[1] for l in lojas if l[0] in lojas_atr_ids]

            novas_lojas = st.multiselect("Lojas atribuídas", list(lojas_dict.keys()), default=lojas_atr_nomes)

            colu1, colu2, colu3 = st.columns(3)

            with colu1:
                if st.button("Atualizar lojas"):
                    c.execute('DELETE FROM usuario_lojas WHERE usuario = ?', (user_sel,))
                    for loja_nome in novas_lojas:
                        c.execute('INSERT INTO usuario_lojas (usuario, loja_id) VALUES (?,?)', (user_sel, lojas_dict[loja_nome]))
                    conn.commit()
                    st.success("Lojas atualizadas!")

            with colu2:
                nova_senha_alt = st.text_input('Nova senha', type='password', key='nova_senha_alt')
                if st.button('Alterar senha'):
                    if nova_senha_alt:
                        c.execute('UPDATE usuarios SET senha = ? WHERE usuario = ?', (hash_senha(nova_senha_alt), user_sel))
                        conn.commit()
                        st.success('Senha alterada!')
                    else:
                        st.warning("Digite uma nova senha!")

            with colu3:
                if st.button('Excluir usuário'):
                    c.execute('DELETE FROM usuarios WHERE usuario = ?', (user_sel,))
                    c.execute('DELETE FROM usuario_lojas WHERE usuario = ?', (user_sel,))
                    conn.commit()
                    st.success('Usuário excluído')
                    st.rerun()
