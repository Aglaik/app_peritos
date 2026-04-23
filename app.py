import streamlit as st
import google.generativeai as genai
from docx import Document
from docx.shared import Pt, RGBColor, Cm
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
if "dados_laudo" not in st.session_state:
    st.session_state.dados_laudo = {
        # Foi adicionado a chave 'incluir' com padrão True
        topico: {"rascunho": "", "final": "", "fotos": [], "incluir": True} for topico in TOPICOS_PADRAO
    }

for topico in TOPICOS_PADRAO:
    if f"txt_rasc_{topico}" not in st.session_state:
        st.session_state[f"txt_rasc_{topico}"] = ""
    if f"txt_final_{topico}" not in st.session_state:
        st.session_state[f"txt_final_{topico}"] = ""

# ==========================================
# 3. FUNÇÕES AUXILIARES
# ==========================================
@st.cache_data
def carregar_modelos_txt():
    modelo_1, modelo_2 = "Nenhum modelo de estrutura encontrado.", "Nenhum modelo de palavras encontrado."
    if os.path.exists("LAUDO PERICIAL MODELO.txt"):
        with open("LAUDO PERICIAL MODELO.txt", "r", encoding="utf-8") as f:
            modelo_1 = f.read()
    if os.path.exists("MODELO COM PALAVRAS.txt"):
        with open("MODELO COM PALAVRAS.txt", "r", encoding="utf-8") as f:
            modelo_2 = f.read()
    return modelo_1, modelo_2

def transcrever_audio(api_key, audio_file_bytes):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
        temp_audio.write(audio_file_bytes)
        temp_path = temp_audio.name

    try:
        arquivo_gemini = genai.upload_file(path=temp_path)
        prompt = "Transcreva este áudio exatamente como foi falado, de forma precisa. Retorne apenas o texto transcrito, sem introduções."
        response = model.generate_content([prompt, arquivo_gemini])
        genai.delete_file(arquivo_gemini.name)
        return response.text.strip()
    except Exception as e:
        st.error(f"Erro na transcrição: {e}")
        return ""
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def processar_texto_ia(api_key, tipo_laudo, topico, rascunho, mod1, mod2):
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

def gerar_documento_word(tipo_laudo, arquivo_template=None):
    # Se o usuário enviou um template, abre ele para manter capa, rodapé e cabeçalho.
    if arquivo_template is not None:
        doc = Document(io.BytesIO(arquivo_template.getvalue()))
    else:
        # Se não enviou, cria um em branco e faz um cabeçalho simples.
        doc = Document()
        p_titulo = doc.add_paragraph()
        p_titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_titulo = p_titulo.add_run('LAUDO PERICIAL\n\n')
        run_titulo.font.name = 'Arial'
        run_titulo.font.size = Pt(12)
        run_titulo.font.bold = True
        
        p_sub = doc.add_paragraph()
        p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_sub = p_sub.add_run(f'Natureza da Ocorrência: {tipo_laudo}')
        run_sub.font.name = 'Arial'
        run_sub.font.size = Pt(12)
        run_sub.font.bold = True
        doc.add_paragraph() 

    contador_topico = 1
    contador_foto = 1

    for topico in TOPICOS_PADRAO:
        dados = st.session_state.dados_laudo[topico]
        
        # Ignora o tópico se o usuário desmarcou a opção de incluir
        if not dados.get('incluir', True):
            continue
            
        texto_final = dados['final']
        fotos = dados['fotos']
        
        if texto_final or fotos:
            # 1. Título do Tópico: Maiúsculo, Negrito, Tamanho 14, Numerado
            p_heading = doc.add_paragraph()
            run_heading = p_heading.add_run(f"{contador_topico}. {topico.upper()}")
            run_heading = p_heading.add_run(f"\n")  # Adiciona quebra de linha após o título
            run_heading.font.name = 'Arial'
            run_heading.font.size = Pt(14)
            run_heading.font.bold = True
            
            # 2. Texto do Tópico: Fonte 12 e Justificado (CORRIGIDO AQUI)
            if texto_final:
                # Divide o texto onde houver \n
                linhas = texto_final.split('\n')
                
                for linha in linhas:
                    # Verifica se a linha não está vazia
                    if linha.strip(): 
                        # Limpa espaços duplos que atrapalham a justificação
                        linha_limpa = linha.strip().replace("  ", " ")
                        
                        p_text = doc.add_paragraph(linha_limpa)
                        p_text.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                        
                        for run in p_text.runs:
                            run.font.name = 'Arial'
                            run.font.size = Pt(12)
                
            # 3. Tratamento das Fotos
            if fotos:
                for foto in fotos:
                    # Inserção da Imagem
                    p_img = doc.add_paragraph()
                    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p_img.paragraph_format.space_after = Pt(0) # Retira espaço abaixo da foto
                    
                    run_img = p_img.add_run()
                    # Define dimensão exata 14.67 de largura por 11.0 de altura (Formato Paisagem/Retrato)
                    run_img.add_picture(foto, width=Cm(14.67), height=Cm(11.0))
                    
                    # Legenda da Imagem colada na foto
                    p_legenda = doc.add_paragraph()
                    p_legenda.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p_legenda.paragraph_format.space_before = Pt(0) # Retira espaço acima da legenda
                    
                    run_legenda = p_legenda.add_run(f"Imagem {contador_foto} - _________________________")
                    run_legenda.font.name = 'Arial'
                    run_legenda.font.size = Pt(10)
                    
                    contador_foto += 1 # Incrementa o número global da foto
            
            contador_topico += 1 # Incrementa o número do tópico para o próximo

    arquivo_io = io.BytesIO()
    doc.save(arquivo_io)
    arquivo_io.seek(0)
    return arquivo_io

# ==========================================
# 4. INTERFACE PRINCIPAL (UI)
# ==========================================
st.title("🛡️ Assistente de Laudos Periciais IA")

modelo_1_texto, modelo_2_texto = carregar_modelos_txt()

with st.sidebar:
    st.header("⚙️ Configurações")
    chave_api = st.text_input("Sua Chave API do Gemini:", type="password", help="Cole sua chave aqui. Ela não será salva.")
    
    st.divider()
    
    st.header("📄 Dados do Laudo")
    tipo_laudo_selecionado = st.selectbox("Tipo de Ocorrência:", TIPOS_LAUDO)
    
    # Campo Novo: Upload do Template
    st.markdown("**Modelo de Documento (Opcional)**")
    template_upload = st.file_uploader(
        "Faça o upload do documento padrão (.docx) com capa e rodapé.", 
        type=["docx"],
        help="Se enviado, o laudo será adicionado no final deste documento original."
    )
    
    st.divider()
    st.header("📥 Exportar")
    if st.button("Gerar Arquivo Word", type="primary"):
        if not chave_api:
            st.warning("Insira sua chave de API do Gemini para garantir que o laudo foi finalizado.")
        else:
            docx_bytes = gerar_documento_word(tipo_laudo_selecionado, template_upload)
            st.download_button(
                label="Baixar Laudo (.docx)",
                data=docx_bytes,
                file_name=f"laudo_{tipo_laudo_selecionado.replace(' ', '_').lower()}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

if not chave_api:
    st.info("👈 Por favor, insira sua Chave API do Gemini na barra lateral para começar a usar as funções de áudio e inteligência artificial.")

st.markdown("### Preencha as seções abaixo:")

for topico in TOPICOS_PADRAO:
    with st.expander(f"📝 {topico}", expanded=False):
        
        # Checkbox para incluir ou não o tópico no Word Final
        incluir_checkbox = st.checkbox(
            "✅ Incluir este tópico no documento gerado", 
            value=st.session_state.dados_laudo[topico].get('incluir', True), 
            key=f"check_{topico}"
        )
        st.session_state.dados_laudo[topico]['incluir'] = incluir_checkbox
        
        # Opcional: Se desmarcar, oculta o conteúdo para o layout ficar mais limpo
        if incluir_checkbox:
            col_esq, col_dir = st.columns([1, 1])
            
            # --- LADO ESQUERDO ---
            with col_esq:
                st.markdown("**1. Entrada de Dados (Rascunho / Áudio)**")
                
                audio_gravado = st.audio_input(f"Gravar relato ({topico})", key=f"audio_{topico}")
                
                if st.button("Transcrever Áudio 🎙️", key=f"btn_transcrever_{topico}", disabled=not audio_gravado):
                    if chave_api:
                        with st.spinner("Transcrevendo..."):
                            texto_transcrito = transcrever_audio(chave_api, audio_gravado.getvalue())
                            if texto_transcrito:
                                texto_existente = st.session_state.dados_laudo[topico]['rascunho']
                                texto_combinado = f"{texto_existente}\n{texto_transcrito}".strip()
                                
                                st.session_state.dados_laudo[topico]['rascunho'] = texto_combinado
                                st.session_state[f"txt_rasc_{topico}"] = texto_combinado
                                st.rerun()
                    else:
                        st.error("Insira a chave da API na lateral.")

                rascunho_atual = st.text_area(
                    "Texto Rascunho:", 
                    height=150, 
                    key=f"txt_rasc_{topico}"
                )
                st.session_state.dados_laudo[topico]['rascunho'] = rascunho_atual
                
                fotos_upadas = st.file_uploader(
                    "Anexar Fotos para esta seção", 
                    type=["jpg", "jpeg", "png"], 
                    accept_multiple_files=True, 
                    key=f"fotos_{topico}"
                )
                if fotos_upadas:
                    st.session_state.dados_laudo[topico]['fotos'] = fotos_upadas

            # --- LADO DIREITO ---
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
                                st.session_state[f"txt_final_{topico}"] = texto_gerado
                                st.rerun()

                texto_final_atual = st.text_area(
                    "Texto Convertido (Pronto para o Laudo):", 
                    height=250, 
                    key=f"txt_final_{topico}"
                )
                st.session_state.dados_laudo[topico]['final'] = texto_final_atual