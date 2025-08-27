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
    
    # Logo
    if os.path.exists('logo.png'):
        pdf.image('logo.png', 10, 8, 33)
    
    # Fonte UTF-8
    fonte_path = 'DejaVuSans.ttf'  # ou 'fonts/DejaVuSans.ttf'
    if os.path.exists(fonte_path):
        pdf.add_font('DejaVu', '', fonte_path, uni=True)
        pdf.set_font('DejaVu', 'B', 12)
    else:
        pdf.set_font('Arial', 'B', 12)
    
    pdf.cell(0, 10, 'Nexus PPN: Controle Inteligente de Ocorrências', 0, 1, 'C')
    pdf.ln(10)
    
    # Conteúdo
    if os.path.exists(fonte_path):
        pdf.set_font('DejaVu', '', 10)
    else:
        pdf.set_font('Arial', '', 10)
    
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
            'JURÍDICO', 'REUNIÃO', 'MANUTENÇÃO', 'TROCA DE PRODUTO', 'ABORDAGEM', 'RECLAMAÇÃO', 'ENTREGA DE CURRÍCULO',
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

    # --- Consultar Ocorrência ---
    elif menu == 'Consultar':
        data_ini = st.date_input('Data inicial')
        data_fim = st.date_input('Data final')
        loja_filtro = st.selectbox('Filtrar por loja', [l[1] for l in st.session_state.lojas_acesso])
        if st.button('Filtrar'):
            c.execute('SELECT * FROM ocorrencias WHERE date(data) BETWEEN ? AND ? AND loja = ?', 
                      (str(data_ini), str(data_fim), loja_filtro))
            ocorrencias = c.fetchall()
            for o in ocorrencias:
                col1, col2, col3 = st.columns([1,2,1])
                with col1:
                    st.subheader(f'{o[1]}')
                    st.write(f"Categoria: {o[2]}")
                    data_formatada = datetime.strptime(o[3], '%Y-%m-%d').strftime('%d/%m/%Y')
                    hora_formatada = datetime.strptime(o[4], '%H:%M:%S').strftime('%H:%M')
                    st.write(f"Data/Hora: {data_formatada} {hora_formatada}")
                    st.write(f"Loja: {o[8]}")
                    st.write(f"Assinatura: {o[7] or 'Pendente'}")
                with col2:
                    st.write(o[5])
                with col3:
                    if o[6]:
                        st.write('Anexos:')
                        for nome, dados in eval(o[6]):
                            b64 = base64.b64encode(base64.b64decode(dados)).decode()
                            href = f'<a href="data:file/octet-stream;base64,{b64}" download="{nome}">{nome}</a>'
                            st.markdown(href, unsafe_allow_html=True)
                    pdf_bytes = gerar_pdf(o)
                    b64_pdf = base64.b64encode(pdf_bytes).decode()
                    st.markdown(f'<a href="data:application/pdf;base64,{b64_pdf}" download="ocorrencia_{o[0]}.pdf">Baixar PDF</a>', unsafe_allow_html=True)

    # --- Validação / Exclusão ---
    elif menu == 'Validação':
        st.header("Validação de Ocorrências")
        c.execute('SELECT * FROM ocorrencias')
        ocorrencias = c.fetchall()
        for o in ocorrencias:
            col1, col2, col3 = st.columns([1,2,1])
            with col1:
                st.subheader(f'{o[1]}')
                st.write(f"Categoria: {o[2]}")
                data_formatada = datetime.strptime(o[3], '%Y-%m-%d').strftime('%d/%m/%Y')
                hora_formatada = datetime.strptime(o[4], '%H:%M:%S').strftime('%H:%M')
                st.write(f"Data/Hora: {data_formatada} {hora_formatada}")
                st.write(f"Loja: {o[8]}")
                st.write(f"Assinatura: {o[7] or 'Pendente'}")
            with col2:
                st.write(o[5])
            with col3:
                if o[6]:
                    st.write('Anexos:')
                    for nome, dados in eval(o[6]):
                        b64 = base64.b64encode(base64.b64decode(dados)).decode()
                        href = f'<a href="data:file/octet-stream;base64,{b64}" download="{nome}">{nome}</a>'
                        st.markdown(href, unsafe_allow_html=True)
                pdf_bytes = gerar_pdf(o)
                b64_pdf = base64.b64encode(pdf_bytes).decode()
                st.markdown(f'<a href="data:application/pdf;base64,{b64_pdf}" download="ocorrencia_{o[0]}.pdf">Baixar PDF</a>', unsafe_allow_html=True)

                if st.session_state.usuario == admin_user or st.session_state.usuario == o[7]:
                    if st.button(f'Excluir', key=f'excluir_{o[0]}'):
                        c.execute('DELETE FROM ocorrencias WHERE id = ?', (o[0],))
                        conn.commit()
                        st.success("Ocorrência excluída")
                        st.rerun()

    # --- Gerenciar Usuários (admin) ---
    elif menu == 'Gerenciar Usuários' and st.session_state.usuario == admin_user:
        st.header("Gerenciar Usuários")
        c.execute('SELECT usuario FROM usuarios WHERE usuario != ?', (admin_user,))
        usuarios = [u[0] for u in c.fetchall()]
        if usuarios:
            user_selecionado = st.selectbox("Selecionar usuário", usuarios)

            # Mostrar lojas disponíveis e atribuídas
            c.execute('SELECT * FROM lojas')
            lojas = c.fetchall()
            lojas_dict = {loja[1]: loja[0] for loja in lojas}

            c.execute('SELECT loja_id FROM usuario_lojas WHERE usuario = ?', (user_selecionado,))
            lojas_atribuídas_ids = [l[0] for l in c.fetchall()]
            lojas_atribuídas_nomes = [l[1] for l in lojas if l[0] in lojas_atribuídas_ids]

            # Atualizar lojas
            novas_lojas = st.multiselect("Lojas atribuídas", list(lojas_dict.keys()), default=lojas_atribuídas_nomes)
            if st.button("Atualizar lojas"):
                c.execute('DELETE FROM usuario_lojas WHERE usuario = ?', (user_selecionado,))
                for loja in novas_lojas:
                    c.execute('INSERT INTO usuario_lojas VALUES (?,?)', (user_selecionado, lojas_dict[loja]))
                conn.commit()
                st.success("Lojas atualizadas!")

            # Alterar senha
            nova_senha_alt = st.text_input('Nova senha', type='password')
            if st.button('Alterar senha'):
                if nova_senha_alt:
                    c.execute('UPDATE usuarios SET senha = ? WHERE usuario = ?', (hash_senha(nova_senha_alt), user_selecionado))
                    conn.commit()
                    st.success('Senha alterada')
                else:
                    st.warning("Digite uma nova senha!")

            # Excluir usuário
            if st.button('Excluir usuário'):
                c.execute('DELETE FROM usuarios WHERE usuario = ?', (user_selecionado,))
                c.execute('DELETE FROM usuario_lojas WHERE usuario = ?', (user_selecionado,))
                conn.commit()
                st.success('Usuário excluído')
        else:
            st.info("Nenhum usuário cadastrado além do admin.")
