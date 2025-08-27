import streamlit as st
import sqlite3
import os
from fpdf import FPDF
from datetime import datetime

# Função para inicializar banco de dados
def init_db():
    conn = sqlite3.connect('ocorrencias.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS ocorrencias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    titulo TEXT,
                    categoria TEXT,
                    data TEXT,
                    hora TEXT,
                    descricao TEXT,
                    anexos TEXT,
                    assinatura TEXT,
                    loja TEXT)''')
    conn.commit()
    conn.close()

# Função para salvar ocorrência
def salvar_ocorrencia(titulo, categoria, data, hora, descricao, anexos, assinatura, loja):
    conn = sqlite3.connect('ocorrencias.db')
    c = conn.cursor()
    c.execute("INSERT INTO ocorrencias (titulo, categoria, data, hora, descricao, anexos, assinatura, loja) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (titulo, categoria, data, hora, descricao, str(anexos), assinatura, loja))
    conn.commit()
    conn.close()

# Função para listar ocorrências
def listar_ocorrencias():
    conn = sqlite3.connect('ocorrencias.db')
    c = conn.cursor()
    c.execute("SELECT * FROM ocorrencias ORDER BY id DESC")
    ocorrencias = c.fetchall()
    conn.close()
    return ocorrencias

# Função para gerar PDF
def gerar_pdf(ocorrencia):
    pdf = FPDF()
    pdf.add_page()
    
    if os.path.exists('logo.png'):
        pdf.image('logo.png', 10, 8, 33)
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Nexus PPN: Controle Inteligente de Ocorrências', 0, 1, 'C')
    pdf.ln(10)
    
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
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 10, 'Anexos:', 0, 1)
        pdf.set_font('Arial', '', 10)
        for nome, _ in anexos:
            pdf.cell(0, 8, f'- {nome}', 0, 1)
    
    pdf.ln(10)
    pdf.cell(0, 10, f'Assinatura: {ocorrencia[7] or "Pendente"}', 0, 1)
    
    # Correção de encoding (UTF-8)
    return pdf.output(dest='S').encode('utf-8')

# Inicializa banco
init_db()

# Layout da aplicação
st.set_page_config(page_title="Nexus PPN", layout="wide")

st.title("📋 Nexus PPN - Controle de Ocorrências")

menu = ["Registrar Ocorrência", "Consultar Ocorrências"]
escolha = st.sidebar.selectbox("Menu", menu)

if escolha == "Registrar Ocorrência":
    st.subheader("Registrar Nova Ocorrência")

    lojas = ["Loja 16-7", "Loja 22-5", "Loja 10-3"]
    if "lojas_acesso" not in st.session_state:
        st.session_state["lojas_acesso"] = lojas

    loja = st.selectbox("Selecione a Loja:", st.session_state["lojas_acesso"])
    titulo = st.text_input("Título da Ocorrência")
    
    categorias = ["FURTO", "PERDA", "DIVERGÊNCIA", "MANUTENÇÃO", "ABORDAGEM", "REUNIÃO"]
    categoria = st.selectbox("Categoria", categorias)
    
    data = st.date_input("Data da Ocorrência", datetime.today())
    hora = st.time_input("Hora da Ocorrência", datetime.now().time())
    
    descricao = st.text_area("Descrição da Ocorrência")
    anexos = st.file_uploader("Anexos", accept_multiple_files=True)
    assinatura = st.text_input("Responsável pela Assinatura")
    
    if st.button("Salvar Ocorrência"):
        arquivos_salvos = []
        for anexo in anexos:
            caminho = os.path.join("anexos", anexo.name)
            with open(caminho, "wb") as f:
                f.write(anexo.getbuffer())
            arquivos_salvos.append((anexo.name, caminho))
        
        salvar_ocorrencia(titulo, categoria, str(data), str(hora), descricao, arquivos_salvos, assinatura, loja)
        st.success("✅ Ocorrência registrada com sucesso!")

elif escolha == "Consultar Ocorrências":
    st.subheader("Ocorrências Registradas")
    
    ocorrencias = listar_ocorrencias()
    for o in ocorrencias:
        with st.expander(f"#{o[0]} - {o[1]} ({o[2]}) - {o[3]} {o[4]}"):
            st.write(f"**Loja:** {o[8]}")
            st.write(f"**Descrição:** {o[5]}")
            st.write(f"**Assinatura:** {o[7] or 'Pendente'}")
            
            anexos = eval(o[6]) if o[6] else []
            if anexos:
                st.write("**Anexos:**")
                for nome, caminho in anexos:
                    st.write(f"- {nome}")
            
            pdf_bytes = gerar_pdf(o)
            st.download_button(
                label="📥 Baixar PDF",
                data=pdf_bytes,
                file_name=f"ocorrencia_{o[0]}.pdf",
                mime="application/pdf"
            )

# Limpeza de sessão
if "lojas_acesso" in st.session_state:
    del st.session_state["lojas_acesso"]
