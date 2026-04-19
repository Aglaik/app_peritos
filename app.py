import streamlit as st
import google.generativeai as genai
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import os
import io
import tempfile

# ==========================================
# 1. CONFIGURAÇÕES INICIAIS DA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Assistente de Laudos Periciais IA",
    page_icon="🛡️",
    layout="wide"
)

TIPOS_LAUDO = [
    "Furto", 
    "Roubo", 
    "Trânsito", 
    "Morte suspeita", 
    "Homicídio", 
    "Identificação veicular", 
    "Outro tipo de laudo"
]

TOPICOS_PADRAO = [
    "Histórico",
    "Objetivo",
    "Isolamento e preservação do local",
    "Dos Exames (Do local, Dos veículos, Do cadáver, Dos demais vestígios)",
    "Considerações técnico-científicas",
    "Discussão",
    "Conclusão"
]

# ==========================================
# 2. INICIALIZAÇÃO DE ESTADO (SESSION STATE)
# ==========================================
# O Streamlit recarrega a página a cada interação. 
# Usamos session_state para não perder os textos digitados e fotos anexadas.
if "dados_laudo" not in st.session_state:
    st.session_state.dados_laudo = {
        topico: {"rascunho": "", "final": "", "fotos": []} for topico in TOPICOS_PADRAO
    }

# ==========================================
# 3. FUNÇÕES AUXILIARES
# ==========================================
@st.cache_data
def carregar_modelos_txt():
    """Carrega os arquivos TXT uma vez e guarda em cache para não ler do disco toda hora."""
    modelo_1, modelo_2 = "Nenhum modelo de estrutura encontrado.", "Nenhum modelo de palavras encontrado."
    if os.path.exists("LAUDO PERICIAL MODELO.txt"):
        with open("LAUDO PERICIAL MODELO.txt", "r", encoding="utf-8") as f:
            modelo_1 = f.read()
    if os.path.exists("MODELO COM PALAVRAS.txt"):
        with open("MODELO COM PALAVRAS.txt", "r", encoding="utf-8") as f:
            modelo_2 = f.read()
    return modelo_1, modelo_2

def transcrever_audio(api_key, audio_file_bytes):
    """Salva o áudio temporariamente, envia para o Gemini transcrever e apaga."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # Criar um arquivo temporário físico para o upload do Gemini
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
        temp_audio.write(audio_file_bytes)
        temp_path = temp_audio.name

    try:
        arquivo_gemini = genai.upload_file(path=temp_path)
        prompt = "Transcreva este áudio exatamente como foi falado, de forma precisa. Retorne apenas o texto transcrito, sem introduções."
        response = model.generate_content([prompt, arquivo_gemini])
        genai.delete_file(arquivo_gemini.name) # Deleta da nuvem
        return response.text.strip()
    except Exception as e:
        st.error(f"Erro na transcrição: {e}")
        return ""
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path) # Deleta do servidor local

def processar_texto_ia(api_key, tipo_laudo, topico, rascunho, mod1, mod2):
    """Envia o rascunho para a IA gerar o texto técnico final."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    Você é um Perito Criminal sênior. Sua tarefa é analisar o relato falado do perito de campo e reescrever o texto em linguagem técnica, formal e objetiva para compor APENAS a seção específica solicitada do laudo.
    
    TIPO DA OCORRÊNCIA: {tipo_laudo}
    SEÇÃO A SER REDIGIDA: {topico}
    
    REGRAS ABSOLUTAS:
    1. Escreva SOMENTE o que pertence ao tópico solicitado ({topico}). Não adicione informações de outros tópicos, introduções gerais ou encerramentos do laudo inteiro.
    2. Corrija gírias, linguagem coloquial e estruture os parágrafos de forma técnica.
    3. Utilize obrigatoriamente a estrutura técnica, o tom e as palavras-chave adequadas com base nos modelos fornecidos abaixo.
    
    === MODELO DE ESTRUTURA ===
    {mod1}
    
    === MODELO DE PALAVRAS E ESTILO ===
    {mod2}
    
    === RELATO DO PERITO (RASCUNHO A SER CONVERTIDO) ===
    {rascunho}
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        st.error(f"Erro na geração de texto: {e}")
        return ""

def gerar_documento_word(tipo_laudo):
    """Gera o arquivo .docx em memória e retorna os bytes para download."""
    doc = Document()
    
    # Estilo Normal
    style_normal = doc.styles['Normal']
    font_normal = style_normal.font
    font_normal.name = 'Arial'
    font_normal.size = Pt(12)
    style_normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    style_normal.paragraph_format.line_spacing = 1.5
    
    def formatar_titulo(paragrafo, tamanho=12, negrito=True, centralizado=False):
        for run in paragrafo.runs:
            run.font.name = 'Arial'
            run.font.size = Pt(tamanho)
            run.font.color.rgb = RGBColor(0, 0, 0)
            run.font.bold = negrito
        if centralizado:
            paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Cabeçalho do Documento
    formatar_titulo(doc.add_heading('LAUDO PERICIAL', level=1), centralizado=True)
    formatar_titulo(doc.add_heading(f'Natureza da Ocorrência: {tipo_laudo}', level=2), centralizado=True)
    doc.add_paragraph() 

    # Preenchendo as seções
    for topico in TOPICOS_PADRAO:
        dados = st.session_state.dados_laudo[topico]
        texto_final = dados['final']
        fotos = dados['fotos']
        
        if texto_final or fotos:
            formatar_titulo(doc.add_heading(topico, level=3))
            
            if texto_final:
                doc.add_paragraph(texto_final)
                
            if fotos:
                doc.add_paragraph() # Espaço antes das fotos
                for foto in fotos:
                    p_img = doc.add_paragraph()
                    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run_img = p_img.add_run()
                    # A foto é lida diretamente da memória (UploadedFile do Streamlit)
                    run_img.add_picture(foto, width=Inches(6.0))
                    
                    p_legenda = doc.add_paragraph("Legenda: _________________________")
                    p_legenda.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for run in p_legenda.runs:
                        run.font.size = Pt(10)
                        run.font.color.rgb = RGBColor(100, 100, 100)

    # Salva o arquivo em memória ao invés do disco
    arquivo_io = io.BytesIO()
    doc.save(arquivo_io)
    arquivo_io.seek(0)
    return arquivo_io

# ==========================================
# 4. INTERFACE PRINCIPAL (UI)
# ==========================================
st.title("🛡️ Assistente de Laudos Periciais IA")

modelo_1_texto, modelo_2_texto = carregar_modelos_txt()

# --- BARRA LATERAL (CONFIGURAÇÕES E EXPORTAÇÃO) ---
with st.sidebar:
    st.header("⚙️ Configurações")
    # Agora a chave não fica fixa no código. Você (ou o usuário) cola ela aqui.
    chave_api = st.text_input("Sua Chave API do Gemini:", type="password", help="Cole sua chave aqui. Ela não será salva.")
    
    st.divider()
    
    st.header("📄 Dados do Laudo")
    tipo_laudo_selecionado = st.selectbox("Tipo de Ocorrência:", TIPOS_LAUDO)
    
    st.divider()
    st.header("📥 Exportar")
    if st.button("Gerar Arquivo Word", type="primary"):
        if not chave_api:
            st.warning("Insira sua chave de API do Gemini para garantir que o laudo foi finalizado.")
        else:
            docx_bytes = gerar_documento_word(tipo_laudo_selecionado)
            st.download_button(
                label="Baixar Laudo (.docx)",
                data=docx_bytes,
                file_name=f"laudo_{tipo_laudo_selecionado.replace(' ', '_').lower()}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

# --- ÁREA PRINCIPAL (TÓPICOS DO LAUDO) ---
if not chave_api:
    st.info("👈 Por favor, insira sua Chave API do Gemini na barra lateral para começar a usar as funções de áudio e inteligência artificial.")

st.markdown("### Preencha as seções abaixo:")

for topico in TOPICOS_PADRAO:
    with st.expander(f"📝 {topico}", expanded=False):
        col_esq, col_dir = st.columns([1, 1])
        
        # --- LADO ESQUERDO: ENTRADAS (Áudio, Texto e Imagens) ---
        with col_esq:
            st.markdown("**1. Entrada de Dados (Rascunho / Áudio)**")
            
            # Gravação de Áudio Nativa do Streamlit
            audio_gravado = st.audio_input(f"Gravar relato ({topico})", key=f"audio_{topico}")
            
            if st.button("Transcrever Áudio 🎙️", key=f"btn_transcrever_{topico}", disabled=not audio_gravado):
                if chave_api:
                    with st.spinner("Transcrevendo..."):
                        texto_transcrito = transcrever_audio(chave_api, audio_gravado.getvalue())
                        if texto_transcrito:
                            # Atualiza o estado
                            st.session_state.dados_laudo[topico]['rascunho'] += ("\n" + texto_transcrito).strip()
                            st.rerun() # Atualiza a tela para mostrar o novo texto
                else:
                    st.error("Insira a chave da API na lateral.")

            # Campo de Texto do Rascunho (pode ser editado manualmente ou preenchido pela IA)
            rascunho_atual = st.text_area(
                "Texto Rascunho:", 
                value=st.session_state.dados_laudo[topico]['rascunho'], 
                height=150, 
                key=f"txt_rasc_{topico}"
            )
            # Salva o que for digitado no estado
            st.session_state.dados_laudo[topico]['rascunho'] = rascunho_atual
            
            # Anexo de Fotos
            fotos_upadas = st.file_uploader(
                "Anexar Fotos para esta seção", 
                type=["jpg", "jpeg", "png"], 
                accept_multiple_files=True, 
                key=f"fotos_{topico}"
            )
            if fotos_upadas:
                st.session_state.dados_laudo[topico]['fotos'] = fotos_upadas

        # --- LADO DIREITO: PROCESSAMENTO E TEXTO FINAL ---
        with col_dir:
            st.markdown("**2. Processamento IA e Texto Final**")
            
            if st.button("🪄 Converter p/ Laudo (IA)", key=f"btn_ia_{topico}", type="secondary"):
                if not chave_api:
                    st.error("Insira a chave da API na lateral.")
                elif not rascunho_atual.strip():
                    st.warning("Não há rascunho para converter. Escreva ou grave um áudio.")
                else:
                    with st.spinner("Processando linguagem técnica..."):
                        texto_gerado = processar_texto_ia(
                            chave_api, 
                            tipo_laudo_selecionado, 
                            topico, 
                            rascunho_atual, 
                            modelo_1_texto, 
                            modelo_2_texto
                        )
                        if texto_gerado:
                            st.session_state.dados_laudo[topico]['final'] = texto_gerado
                            st.rerun()

            # Campo de Texto Final
            texto_final_atual = st.text_area(
                "Texto Convertido (Pronto para o Laudo):", 
                value=st.session_state.dados_laudo[topico]['final'], 
                height=250, 
                key=f"txt_final_{topico}"
            )
            # Permite que o perito edite o texto final gerado pela IA antes de exportar
            st.session_state.dados_laudo[topico]['final'] = texto_final_atual