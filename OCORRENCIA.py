import streamlit as st
import sqlite3
import hashlib
from fpdf import FPDF
from datetime import datetime
import base64
import os

# --- Configurações iniciais ---
db = 'ocorrencias.db'
admin_user = 'admin'
admin_pass = hashlib.sha256('123456'.encode()).hexdigest()
logout_timeout = 300  # 5 minutos

# --- Banco de dados ---
conn = sqlite3.connect(db, check_same_thread=False)
c = conn.cursor()

# Criar tabelas
c.execute('''CREATE TABLE IF NOT EXISTS usuarios (usuario TEXT, senha TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS lojas (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)''')
c.execute('''CREATE TABLE IF NOT EXISTS usuario_lojas (usuario TEXT, loja_id INTEGER,
            FOREIGN KEY (usuario) REFERENCES usuarios(usuario),
            FOREIGN KEY (loja_id) REFERENCES lojas(id))''')
c.execute('''CREATE TABLE IF NOT EXISTS ocorrencias (
    id INTEGER PRIMARY KEY,
    titulo TEXT,
    categoria TEXT,
    data TEXT,
    hora TEXT,
    texto TEXT,
    anexos TEXT,
    assinatura1 TEXT,
    loja TEXT
)''')
conn.commit()

# Pré-cadastrar lojas
lojas_iniciais = ['SUSSUARANA', 'VIDA NOVA', 'ALPHAVILLE', 'VILAS', 'BURAQUINHO', 'ITINGA', 'TANCREDO NEVES']
for loja in lojas_iniciais:
    c.execute('INSERT OR IGNORE INTO lojas (nome) VALUES (?)', (loja,))
conn.commit()

# Criar usuário admin
c.execute('SELECT * FROM usuarios WHERE usuario = ?', (admin_user,))
if not c.fetchone():
    c.execute('INSERT INTO usuarios VALUES (?,?)', (admin_user, admin_pass))
    conn.commit()

# --- Funções auxiliares ---
def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def gerar_pdf(ocorrencia):
    pdf = FPDF()
    pdf.add_page()
    
    # Adiciona logo se existir
    if os.path.exists('logo.png'):
        pdf.image('logo.png', 10, 8, 33)
    
    # Caminho da fonte
    fonte_path = 'DejaVuSans.ttf'  # ou 'fonts/DejaVuSans.ttf' se estiver na pasta fonts
    if not os.path.exists(fonte_path):
        st.error(f"Fonte não encontrada: {fonte_path}. O PDF será gerado com fonte padrão Arial.")
        fonte = 'Arial'
        pdf.set_font(fonte, 'B', 12)
    else:
        pdf.add_font('DejaVu', '', fonte_path, uni=True)
        pdf.set_font('DejaVu', 'B', 12)
    
    pdf.cell(0, 10, 'Nexus PPN: Controle Inteligente de Ocorrências', 0, 1, 'C')
    pdf.ln(10)
    
    # Define fonte para conteúdo
    if os.path.exists(fonte_path):
        pdf.set_font('DejaVu', '', 10)
    else:
        pdf.set_font('Arial', '', 10)
    
    # Conteúdo da ocorrência
    pdf.cell(0, 10, f'Título: {ocorrencia[1]}', 0, 1)
    pdf.cell(0, 10, f'Categoria: {ocorrencia[2]}', 0, 1)
    pdf.cell(0, 10, f'Loja: {ocorrencia[8]}', 0, 1)
    
    data_formatada = datetime.strptime(ocorrencia[3], '%Y-%m-%d').strftime('%d/%m/%Y')
    hora_formatada = datetime.strptime(ocorrencia[4], '%H:%M:%S').strftime('%H:%M')
    pdf.cell(0, 10, f'Data/Hora: {data_formatada} {hora_formatada}', 0, 1)
    
    pdf.multi_cell(0, 8, f'Ocorrência: {ocorrencia[5]}')
    
    anexos = eval(ocorrencia[6]) if ocorrencia[6] else []
    if anexos:
        pdf.ln(5)
        if os.path.exists(fonte_path):
            pdf.set_font('DejaVu', 'B', 10)
        else:
            pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 10, 'Anexos:', 0, 1)
        if os.path.exists(fonte_path):
            pdf.set_font('DejaVu', '', 10)
        else:
            pdf.set_font('Arial', '', 10)
        for nome, _ in anexos:
            pdf.cell(0, 8, f'- {nome}', 0, 1)
    
    pdf.ln(10)
    pdf.cell(0, 10, f'Assinatura: {ocorrencia[7] or "Pendente"}', 0, 1)
    
    # Retorna PDF em bytes (UTF-8 se possível)
    return pdf.output(dest='S').encode('utf-8')

# --- Sessão ---
if 'last_activity' not in st.session_state:
    st.session_state.last_activity = datetime.now()

if 'usuario' in st.session_state and (datetime.now() - st.session_state.last_activity).seconds > logout_timeout:
    del st.session_state['usuario']
    st.warning('Sessão expirada!')
    st.rerun()

# --- Login ---
if 'usuario' not in st.session_state:
    st.title('Login')
    if os.path.exists('logo.png'):
        st.image('logo.png', width=150)
    usuario = st.text_input('Usuário')
    senha = st.text_input('Senha', type='password')
    if st.button('Entrar'):
        c.execute('SELECT * FROM usuarios WHERE usuario = ? AND senha = ?', (usuario, hash_senha(senha)))
        if c.fetchone():
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

# --- Área principal ---
else:
    st.session_state.last_activity = datetime.now()
    st.sidebar.write(f'Logado como: {st.session_state.usuario}')
    if st.sidebar.button('Sair'):
        del st.session_state['usuario']
        st.rerun()

    st.title(f'Nexus PPN - Usuário: {st.session_state.usuario}')
    menu = st.sidebar.selectbox(
        'Menu', 
        ['Registrar Ocorrência', 'Consultar', 'Validação', 'Gerenciar Usuários'] 
        if st.session_state.usuario == admin_user else ['Registrar Ocorrência', 'Consultar', 'Validação']
    )

    # --- Registrar Ocorrência ---
    if menu == 'Registrar Ocorrência':
        titulo = st.text_input('Título')
        categoria = st.selectbox('Categoria', [
            'JURÍDICO', 'TROCA DE PRODUTO', 'RECLAMAÇÃO', 'ENTREGA DE CURRÍCULO',
            'ENTREVISTA', 'ENTRADA DE PROMOTOR', 'SAÍDA DE PROMOTOR', 
            'BATIDA DE CAIXA', 'TROCA DE TURNO'
        ])
        if st.session_state.lojas_acesso:
            loja_selecionada = st.selectbox('Selecione a loja', [l[1] for l in st.session_state.lojas_acesso])
        else:
            st.warning('Nenhuma loja atribuída ao usuário.')
            loja_selecionada = None
        data = st.date_input('Data')
        hora = st.time_input('Hora')
        texto = st.text_area('Ocorrência')
        anexos = st.file_uploader('Anexos', accept_multiple_files=True)
        if st.button('Salvar') and loja_selecionada:
            arquivos = [(a.name, base64.b64encode(a.read()).decode()) for a in anexos]
            c.execute('INSERT INTO ocorrencias (titulo, categoria, data, hora, texto, anexos, assinatura1, loja) VALUES (?,?,?,?,?,?,?,?)',
                      (titulo, categoria, str(data), str(hora), texto, str(arquivos), st.session_state.usuario, loja_selecionada))
            conn.commit()
            st.success('Ocorrência registrada')

    # --- Consultar / Validação / Gerenciar Usuários ---
    # (Aqui você mantém todo o restante do seu código como antes, apenas substituindo a função gerar_pdf)
