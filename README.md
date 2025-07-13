# HermesAI

## ✨ O que é?

O **HermesAI** é um assistente pessoal inteligente, com memória vetorial persistente (FAISS), integração com Google Agenda, e-mail, busca na web, previsão do tempo e muito mais. Ele aprende com o usuário, lembra de fatos importantes e responde de forma contextual.

---

## 🛠️ Stack Tecnológica

- **Python 3.8+**
- **FAISS** — indexação e busca vetorial para memória de longo prazo
- **Sentence Transformers (Hugging Face)** — embeddings de texto
- **LangChain** — orquestração de LLMs e fluxos conversacionais
- **LangGraph** — orquestração de fluxos conversacionais baseados em grafos
- **Chainlit** — interface de chat interativa
- **Google API Client** — integração com Google Calendar e Gmail
- **WeatherAPI** — previsão do tempo
- **Requests, BeautifulSoup** — utilidades para web scraping e requisições
- **dotenv** — gerenciamento de variáveis de ambiente

---

## 🚀 Funcionalidades Atuais

- **Memória vetorial persistente (FAISS):**
  - Lembra de fatos, preferências e histórico de conversas.
  - Recupera contexto relevante para respostas mais inteligentes.
  - Persistência automática dos vetores e metadados em disco (pasta `memory_faiss`).
  - Só responde que lembra de algo se realmente já viu aquela informação antes.
- **Conversação contextual:** 
  - Usa a memória para lembrar do usuário e de informações já compartilhadas.
- **Agenda Google:**
  - Cria, lista e verifica eventos na sua agenda.
- **E-mail (Gmail):**
  - Lê, busca, envia e-mails.
- **Previsão do tempo:** 
  - Busca informações meteorológicas usando uma API externa (WeatherAPI).
- **Busca na web:** 
  - Responde perguntas e busca notícias.
- **Execução de múltiplas intenções:** 
  - Entende e executa vários pedidos em uma só mensagem.
- **Separação de estado de conversa por sessão:** 
  - Cada usuário tem seu próprio fluxo de diálogo (RAM).

---

## 🧠 Como funciona a memória vetorial FAISS?

- Cada interação relevante é embutida (embedding) usando o modelo `all-MiniLM-L6-v2` da Hugging Face (Sentence Transformers).
- Os vetores são armazenados e indexados pelo FAISS, com persistência automática em disco.
- Quando o usuário faz uma nova pergunta, o sistema busca na memória vetorial por conversas similares e insere o contexto relevante no prompt do LLM.
- O agente só "lembra" de fatos que realmente já foram mencionados, evitando respostas genéricas.
- A memória é global (compartilhada entre usuários) por padrão.

---

## 🤖 Uso do LLM (Hugging Face)

- O HermesAI utiliza o modelo Llama 3 (ou similar) via Hugging Face Inference API.
- É necessário um token de autenticação Hugging Face (`HUGGINGFACEHUB_API_TOKEN`).
- O LLM é chamado via LangChain, com prompts customizados e contexto recuperado da memória vetorial.

### Como gerar o token Hugging Face

1. Crie uma conta gratuita em https://huggingface.co
2. Acesse https://huggingface.co/settings/tokens
3. Clique em "New token", dê um nome e selecione o escopo "Read".
4. Copie o token gerado e coloque no arquivo `.env` como `HUGGINGFACEHUB_API_TOKEN`.

---

## ☁️ Uso da API de Clima (WeatherAPI)

- O assistente usa a WeatherAPI para buscar previsão do tempo.
- É necessário um token de API (`WEATHER_API_KEY`).

### Como gerar o token WeatherAPI

1. Crie uma conta gratuita em https://www.weatherapi.com/
2. Após login, acesse "API Keys" e copie sua chave.
3. Coloque no arquivo `.env` como `WEATHER_API_KEY`.

---

## 📅 Configuração do Google Calendar & Gmail via API

Para acessar sua agenda e e-mails, siga este passo a passo para configurar o OAuth do Google (cliente do tipo **Aplicativo da Web**):

1. No [Google Cloud Console](https://console.cloud.google.com/), vá em **APIs e serviços > Tela de permissão OAuth**.
   - Escolha tipo de usuário "Externo", preencha as informações e adicione você como usuário de teste.
   - Adicione os escopos necessários (Google Calendar e Gmail).
2. Vá em **APIs e serviços > Credenciais > Criar credenciais > ID do cliente OAuth**.
   - Selecione **Aplicativo da Web**.
   - Adicione os seguintes URIs autorizados de redirecionamento:
     - `http://localhost`
     - `http://localhost:8080`
   - Crie e baixe o arquivo `credentials.json` e coloque na raiz do projeto.
3. Na primeira execução, o app abrirá uma URL para você autorizar o acesso à sua conta Google. O token será salvo como `token.json`.

**Links úteis:**
- [Configurar tela de permissão OAuth](https://developers.google.com/workspace/guides/configure-oauth-consent?hl=pt-br)
- [Criar credencial OAuth](https://support.google.com/workspacemigrate/answer/9222992?hl=PT)

**Importante:**
- Sem esse passo, as funções de agenda e e-mail não funcionarão.
- O acesso é local e seguro: o app só acessa sua conta após sua autorização explícita.

---

## 📂 Estrutura de Pastas

```
HermesAI/
├── app.py
├── faiss_memory/
│   └── memory.py
├── graph/
│   └── graph_setup.py
├── tools/
├── utils/
│   └── llm_utils.py
├── memory_faiss/         # Persistência da memória vetorial
├── requirements.txt
├── ideias_expansao.txt
└── README.md
```

---

## 🛠️ Instalação e Configuração

### 1. Instale as dependências

```bash
pip install -r requirements.txt
pip install faiss-cpu  # (importante para memória vetorial)
```

### 2. Configure o arquivo `.env`

Crie um arquivo `.env` na raiz do projeto com o seguinte conteúdo (veja `.env.example`):

```
HUGGINGFACEHUB_API_TOKEN=seu_token_huggingface
WEATHER_API_KEY=seu_token_weatherapi
```

### 3. Configure o Google para agenda e e-mail

- Siga as instruções da seção "Configuração do Google Calendar & Gmail via API" acima.
- Coloque o `credentials.json` na raiz do projeto.

### 4. Rode o assistente

```bash
chainlit run app.py -w --port 8500
```

- Acesse em [http://localhost:8500](http://localhost:8500)
- Converse com o HermesAI e experimente as funcionalidades!

---

## ⚡ Exemplos de uso

- "Meu nome é Icaro José Batista de Oliveira"
- "Me lembre de comprar pão amanhã"
- "Quais meus compromissos amanhã?"
- "Me envie meus e-mails e marque dentista para sexta"
- "Qual é o meu nome completo?"
- "Você lembra do que eu gosto de fazer?"

---

## 🧩 Ideias de expansão

- Tarefas, lembretes e notas inteligentes
- Resumo diário
- Rotinas e automatizações
- Integração com mensageiros (WhatsApp/Telegram)
- Alertas inteligentes

---

## 🟠 Limitações e próximos passos

- [ ] Memória vetorial por usuário (login/autenticação)
- [ ] Persistência do grafo/estado do usuário
- [ ] Limpeza/gerenciamento de memória
- [ ] Segurança multiusuário

---

## 🤝 Contribuição

Sugestões, bugs ou ideias?  
Abra uma issue ou envie um PR!

