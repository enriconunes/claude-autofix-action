# CLAUDE.md

Este ficheiro fornece orientações ao Claude Code (claude.ai/code) ao trabalhar com código neste repositório.

## Visão Geral do Projeto

Este repositório implementa **correção automatizada de testes com IA** utilizando o Claude AI (API da Anthropic) integrado nos workflows do GitHub Actions. O sistema analisa automaticamente testes falhados em Pull Requests, gera correções e cria novos PRs com as correções.

**Conceito-Chave**: Os ficheiros Python na pasta raiz (`dividir.py`, `media.py`, etc.) são **fixtures de teste** utilizados para demonstrar e validar os workflows. São intencionalmente simples e contêm erros para acionar os workflows de correção automática. O verdadeiro valor deste repositório são os **workflows reutilizáveis do GitHub Actions** que podem ser integrados em qualquer projeto Python.

## Arquitetura

### Fluxo de Execução do Workflow

```
1. Programador cria PR → main
2. claude-ci.yml é acionado:
   - Executa pytest com relatório JSON
   - Envia falhas ao Claude AI para análise
   - Publica comentário de análise no PR

3. Se os testes falharem → claude-auto-fix.yml é acionado:
   - Deteta o branch com falhas
   - Executa os testes novamente para gerar relatório de falhas
   - Envia falhas ao Claude AI para correções de código
   - Aplica correções nos ficheiros fonte
   - Cria novo branch de correção (claude-auto-fix-TIMESTAMP)
   - Cria PR com correções → branch original com falhas
   - Comenta no PR original com ligação para o PR de correção
```

### Diagramas de Fluxo de Execução

#### GitHub Action: `claude-ci.yml` → Análise de Testes

```
.github/workflows/claude-ci.yml
    │
    ├─ Executa: pytest --json-report
    │         └─ Gera: .report.json
    │
    └─ Executa: ci/claude_report.py
                    │
                    ├─ Importa: api/
                    │           ├─ client.py
                    │           │   └─ Chama: Claude API (Anthropic)
                    │           └─ models.py
                    │               └─ Resolve: nome do modelo Claude
                    │
                    ├─ Importa: pytest/
                    │           ├─ parser.py
                    │           │   └─ Carrega: .report.json
                    │           │   └─ Extrai: falhas de testes
                    │           └─ formatter.py
                    │               └─ Formata: tracebacks, respostas
                    │
                    ├─ Importa: file_utils.py
                    │           └─ Lê: ficheiros fonte
                    │
                    ├─ Importa: config.py
                    │           └─ Fornece: BASE_ANALYSIS_PROMPT
                    │
                    └─ Gera: claude_comment.md
                                  └─ Publicado no PR como comentário
```

#### GitHub Action: `claude-auto-fix.yml` → Geração Automatizada de Correções

```
.github/workflows/claude-auto-fix.yml
    │
    ├─ Executa: pytest --json-report
    │         └─ Gera: .report.json
    │
    └─ Executa: ci/claude_fix.py
                    │
                    ├─ Importa: api/
                    │           ├─ client.py
                    │           │   └─ Chama: Claude API (Anthropic)
                    │           └─ models.py
                    │               └─ Resolve: nome do modelo Claude
                    │
                    ├─ Importa: pytest/
                    │           ├─ parser.py
                    │           │   └─ Carrega: .report.json
                    │           │   └─ Extrai: falhas de testes
                    │           └─ formatter.py
                    │               └─ Formata: tracebacks
                    │
                    ├─ Importa: fix/
                    │           ├─ inference.py
                    │           │   └─ Infere: test_X.py → X.py
                    │           ├─ extractor.py
                    │           │   └─ Extrai: código Python da resposta
                    │           └─ patcher.py
                    │               └─ Valida/aplica: patches
                    │
                    ├─ Importa: file_utils.py
                    │           └─ Lê: ficheiros fonte
                    │
                    ├─ Importa: config.py
                    │           └─ Fornece: FIX_PROMPT
                    │
                    ├─ Gera: claude-patches/
                    │             ├─ 01_response.txt (debug)
                    │             ├─ 01_<filename>.py (código corrigido)
                    │             └─ summary.json
                    │
                    └─ Modifica: ficheiros fonte (com flag --apply)
                                 └─ Cria: branch de correção + PR
```

### Estrutura de Módulos Python

```
ci/
├─ claude_report.py (Ponto de entrada para análise)
│  └─ Dependências:
│     ├─ api.client → send_to_claude()
│     ├─ api.models → resolve_model_name()
│     ├─ pytest.parser → load_report(), extract_failures()
│     ├─ pytest.formatter → format_longrepr(), extract_response_text()
│     ├─ file_utils → read_source()
│     └─ config → BASE_ANALYSIS_PROMPT
│
├─ claude_fix.py (Ponto de entrada para correção automática)
│  └─ Dependências:
│     ├─ api.client → send_to_claude()
│     ├─ api.models → resolve_model_name()
│     ├─ pytest.parser → load_report(), extract_failures()
│     ├─ pytest.formatter → format_longrepr()
│     ├─ fix.inference → infer_source_file()
│     ├─ fix.extractor → extract_code_from_response()
│     ├─ file_utils → read_source()
│     └─ config → FIX_PROMPT
│
├─ api/
│  ├─ client.py
│  │  ├─ send_to_claude() → Faz pedido HTTP à Claude API
│  │  ├─ send_health_check() → Verifica conectividade da API
│  │  └─ Dependências: config (API_BASE_URL, ANTHROPIC_VERSION)
│  │
│  └─ models.py
│     ├─ resolve_model_name() → Obtém modelo do env ou predefinido
│     └─ iter_candidate_models() → Fornece modelos de reserva
│
├─ pytest/
│  ├─ parser.py
│  │  ├─ load_report() → Carrega .report.json
│  │  └─ extract_failures() → Filtra testes falhados
│  │
│  └─ formatter.py
│     ├─ format_longrepr() → Formata tracebacks do pytest
│     ├─ extract_response_text() → Analisa resposta do Claude
│     └─ build_comment_section() → Constrói comentário do PR
│
├─ fix/
│  ├─ inference.py
│  │  └─ infer_source_file() → mapeamento test_X.py → X.py
│  │
│  ├─ extractor.py
│  │  ├─ extract_code_from_response() → Extrai Python do Claude
│  │  ├─ extract_diff_from_response() → Extrai diff unificado
│  │  └─ extract_file_path_from_diff() → Obtém ficheiro de destino
│  │
│  └─ patcher.py
│     ├─ validate_diff() → Verifica formato do diff
│     ├─ apply_patch() → Aplica usando git apply
│     └─ generate_patch_filename() → Cria nome do ficheiro patch
│
├─ file_utils.py
│  └─ read_source() → Lê ficheiros fonte com fallback de codificação
│
└─ config.py
   ├─ API_BASE_URL, ANTHROPIC_VERSION
   ├─ DEFAULT_CLAUDE_MODEL, FALLBACK_MODELS
   ├─ BASE_ANALYSIS_PROMPT → Para claude_report.py
   └─ FIX_PROMPT → Para claude_fix.py
```

### Componentes Principais

#### 1. Workflows do GitHub Actions (`.github/workflows/`)

**`claude-ci.yml`** - Workflow principal de CI
- Acionadores: Pull requests para `main`
- Executa pytest com geração de relatório JSON
- Chama `ci/claude_report.py` para analisar falhas
- Publica análise de IA como comentário no PR
- Utiliza: segredo `ANTHROPIC_API_KEY`

**`claude-auto-fix.yml`** - Workflow de correção automática
- Acionadores: Quando `claude-ci.yml` falha OU acionamento manual
- Deteta o branch de origem que falhou
- Gera correções usando `ci/claude_fix.py`
- **Crítico**: Usa `git add -u` (apenas ficheiros rastreados) para evitar commit de ficheiros temporários
- Cria PR com correções automaticamente
- Publica comentário com ligação do PR no PR original
- Utiliza: segredo `ANTHROPIC_API_KEY`

#### 2. Scripts Python (`ci/`)

**`claude_report.py`** - Analisador de falhas de testes
- Analisa relatório JSON do pytest (`.report.json`)
- Envia falhas à API do Claude com contexto completo (código fonte, traceback, informação do teste)
- Gera análise em markdown para comentários do PR
- Usa Claude Sonnet 4.5 por predefinição
- Modelos de reserva: Sonnet 4, Claude 3.5 Sonnet

**`claude_fix.py`** - Corretor de código automatizado
- Lê falhas do pytest
- Infere ficheiros fonte a partir dos nomes dos testes (ex.: `test_dividir.py` → `dividir.py`)
- Solicita ficheiros corrigidos completos ao Claude AI
- Aplica correções diretamente nos ficheiros fonte (quando a flag `--apply` é usada)
- Guarda informação de debug na pasta `claude-patches/`
- Limita a 5 correções por execução para evitar alterações excessivas

### Detalhes Técnicos Importantes

#### Lógica de Inferência de Ficheiros
O script de correção automática infere automaticamente qual ficheiro fonte corrigir a partir dos nomes dos ficheiros de teste:
- Padrão: `test_<modulo>.py` → `<modulo>.py`
- Exemplo: `test_dividir.py::test_dividir_ok` → corrige `dividir.py`
- Recorre à inspeção do traceback se a inferência falhar

#### Gestão de Ficheiros Temporários
Os seguintes ficheiros são gerados mas **intencionalmente não são commitados**:
- `.report.json` - relatório JSON do pytest
- `claude_comment.md` - conteúdo do comentário do PR
- `claude-patches/` - informação de debug e pré-visualizações de correções

Estes estão definidos no `.gitignore` e o workflow usa `git add -u` (atualiza apenas ficheiros rastreados) para garantir que nunca são acidentalmente commitados.

#### Integração com a API do Claude
- Endpoint: `https://api.anthropic.com/v1/messages`
- Modelo: `claude-sonnet-4-5-20250929` (Sonnet 4.5)
- Versão da API: `2023-06-01`
- Máximo de tokens: 4096 por resposta
- Lógica de repetição: Fallback automático para modelos mais antigos se o principal falhar
- Limitação de taxa: Repetição incorporada com atraso de 2 segundos para erros 529

## Instruções de Configuração para Novos Projetos

### 1. Segredo do GitHub Obrigatório
Adicione `ANTHROPIC_API_KEY` aos segredos do repositório:
- Aceda a: Settings → Secrets and variables → Actions
- Crie o segredo: `ANTHROPIC_API_KEY`
- Valor: A sua chave API da Anthropic de https://console.anthropic.com/

### 2. Copiar Ficheiros Necessários
```bash
# Copiar workflows
cp -r .github/workflows/claude-*.yml <projeto-destino>/.github/workflows/

# Copiar scripts Python
cp -r ci/ <projeto-destino>/ci/

# Atualizar .gitignore
cat >> <projeto-destino>/.gitignore << EOF
# Ficheiros temporários do Claude CI
.report.json
claude_comment.md
claude-patches/
EOF
```

### 3. Dependências
Adicione ao ambiente de testes do projeto de destino:
```bash
pip install pytest pytest-json-report
```

### 4. Verificar Configuração
- Certifique-se de que os testes são executáveis com: `pytest --json-report`
- Verifique se os ficheiros de teste seguem a convenção de nomes `test_*.py`
- Certifique-se de que os ficheiros fonte estão na mesma pasta ou localização previsível

## Comandos de Desenvolvimento

### Testar Workflows Localmente

```bash
# Gerar relatório de teste (simula o que o CI faz)
pytest --json-report

# Testar análise do Claude (requer variável de ambiente ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY="sua-chave"
python ci/claude_report.py --report .report.json --comment-file claude_comment.md

# Testar geração de correção automática (execução seca - não aplica)
python ci/claude_fix.py --report .report.json --output-dir claude-patches

# Testar correção automática com aplicação
python ci/claude_fix.py --report .report.json --apply --max-fixes 5
```

### Acionamento Manual do Workflow

Para acionar manualmente a correção automática num branch específico:
1. Aceda a: Actions → Claude Auto-Fix → Run workflow
2. Selecione o branch
3. Clique em "Run workflow"

## Personalização do Workflow

### Alterar Modelo do Claude
Defina a variável de ambiente `CLAUDE_MODEL` no workflow:
```yaml
env:
  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  CLAUDE_MODEL: "claude-opus-4-5-20251101"  # Usar Opus em vez disso
```

### Ajustar Limite de Correções
Modifique o parâmetro `--max-fixes` em `claude-auto-fix.yml`:
```yaml
python ci/claude_fix.py --report .report.json --apply --max-fixes 10
```

### Alterar Branch de Destino
Por predefinição, os workflows têm como destino `main`. Para alterar:
```yaml
on:
  pull_request:
    branches: [ main, develop ]  # Adicionar mais branches
```

## Notas Importantes

### Operações Git
- O workflow usa `git add -u` em vez de `git add .` para evitar commit de ficheiros temporários
- Apenas ficheiros rastreados modificados são incluídos nos commits de correção
- Os branches de correção são nomeados: `claude-auto-fix-AAAAMMDD-HHMMSS`

### Custos da API
- Cada teste falhado gera ~2 chamadas à API (análise + correção)
- Aplicam-se os preços do Sonnet 4.5 (verifique os preços da Anthropic)
- Considere definir `--max-fixes` para controlar custos em conjuntos de testes grandes

### Limitações
- Atualmente apenas Python/pytest
- Requer que os ficheiros de teste sigam a convenção `test_*.py`
- A inferência de ficheiros fonte pode falhar em estruturas de projeto complexas
- O Claude pode nem sempre gerar correções corretas (revisão necessária)

### Segurança
- Nunca faça commit de `ANTHROPIC_API_KEY` no repositório
- Guarde apenas nos GitHub Secrets
- Os workflows executam com permissões mínimas necessárias
- Os PRs de correção requerem revisão e aprovação manual antes de serem merged
