import os
import logging
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import pymysql

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configuração de logging profissional
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Middlewares e Services
from controllers.auth_middleware import login_required, require_permission, require_action
from models.usuario import UsuarioFactory
from services.produto_service import ProdutoService
from services.pedido_service import PedidoService
from services.cliente_service import ClienteService
from services.dashboard_service import DashboardService
from services.usuario_service import UsuarioService
from services.financeiro_service import FinanceiroService
from services.logistica_service import LogisticaService
from services.compras_service import ComprasService

# Importação de retrocompatibilidade do db.py
from db import get_db_connection
from models.pedido import formatar_data_br

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'megavarejo_secret_key_rbac_2026')

# Configuração de cookies de sessão seguros
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)

# Instanciação dos Serviços da Arquitetura POO
from services.estoque_service import EstoqueService
estoque_service = EstoqueService()
produto_service = estoque_service # Reutilização para retrocompatibilidade
pedido_service = PedidoService()
cliente_service = ClienteService()
dashboard_service = DashboardService()
usuario_service = UsuarioService()
financeiro_service = FinanceiroService()
logistica_service = LogisticaService()
compras_service = ComprasService()

# Dicionário de permissões mantido para compatibilidade com importações em testes
ROLE_PERMISSIONS = {
    'Administrador': {'dashboard', 'produtos', 'estoque', 'pedidos', 'clientes', 'usuarios', 'financeiro', 'logistica', 'compras', 'pdv'},
    'Estoque': {'dashboard', 'produtos', 'estoque', 'logistica', 'compras'},
    'Vendas': {'dashboard', 'produtos', 'estoque', 'pedidos', 'clientes', 'logistica', 'pdv'},
    'Gerência': {'dashboard', 'produtos', 'estoque', 'pedidos', 'clientes', 'financeiro', 'logistica', 'compras', 'pdv'},
    'Financeiro': {'dashboard', 'pedidos', 'financeiro', 'compras'}
}


# --- ROTAS DE INTERFACE (PÁGINAS) ---

@app.route('/')
def index():
    if 'usuario_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('index.html')

@app.route('/login')
def login_page():
    if 'usuario_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')


# --- AUTENTICAÇÃO E SESSÃO ---

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    dados = request.get_json() or {}
    email = dados.get('email', '')
    senha = dados.get('senha', '')

    try:
        usuario = usuario_service.autenticar(email, senha)

        session.clear()
        session['usuario_id'] = usuario.id
        session['usuario_nome'] = usuario.nome
        session['usuario_email'] = usuario.email
        session['usuario_perfil'] = usuario.perfil_nome

        # Obtenção polimórfica das permissões através do objeto de domínio
        permissoes = usuario.obter_permissoes()

        return jsonify({
            'mensagem': 'Login efetuado com sucesso!',
            'usuario': {
                'id': usuario.id,
                'nome': usuario.nome,
                'email': usuario.email,
                'perfil': usuario.perfil_nome,
                'permissoes': permissoes
            }
        })
    except ValueError as ve:
        return jsonify({'erro': str(ve)}), 400
    except PermissionError as pe:
        status_code = 403 if "desativado" in str(pe).lower() else 401
        return jsonify({'erro': str(pe)}), status_code
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'mensagem': 'Logout realizado com sucesso!'})

@app.route('/api/auth/me', methods=['GET'])
def api_me():
    if 'usuario_id' not in session:
        return jsonify({'autenticado': False}), 401

    perfil = session.get('usuario_perfil')
    nome_sessao = session.get('usuario_nome') or 'Usuário'
    email_sessao = session.get('usuario_email') or 'usuario@megavarejo.com'
    # Objeto especializado polimórfico gerado pela factory
    usuario_obj = UsuarioFactory.criar_usuario(
        perfil_nome=perfil,
        nome=nome_sessao,
        email=email_sessao,
        id=session.get('usuario_id')
    )

    return jsonify({
        'autenticado': True,
        'usuario': {
            'id': usuario_obj.id,
            'nome': usuario_obj.nome,
            'email': usuario_obj.email,
            'perfil': usuario_obj.perfil_nome,
            'permissoes': usuario_obj.obter_permissoes()
        }
    })


# --- 1. MÓDULO DASHBOARD GERENCIAL (API) ---

@app.route('/api/dashboard', methods=['GET'])
@login_required
@require_permission('dashboard')
def get_dashboard():
    periodo = request.args.get('periodo', '30dias')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    agrupamento = request.args.get('agrupamento')

    try:
        metricas = dashboard_service.obter_metricas(
            periodo=periodo,
            data_inicio=data_inicio,
            data_fim=data_fim,
            agrupamento_forcado=agrupamento
        )
        return jsonify(metricas)
    except Exception as e:
        logger.exception("Erro ao processar métricas do dashboard: %s", e)
        return jsonify({'erro': 'Erro interno ao carregar os indicadores do dashboard.'}), 500


# --- 2. MÓDULO ESTOQUE (PRODUTOS, MOVIMENTAÇÕES, AJUSTES E RELATÓRIOS) ---

@app.route('/api/produtos', methods=['GET'])
@login_required
@require_permission('produtos')
def listar_produtos():
    busca = request.args.get('busca')
    try:
        produtos = estoque_service.listar_produtos(busca=busca)
        return jsonify(produtos)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/produtos', methods=['POST'])
@login_required
@require_permission('produtos')
def cadastrar_produto():
    dados = request.get_json() or {}
    nome = dados.get('nome')
    preco = dados.get('preco')
    estoque = dados.get('estoque')

    if nome is None or str(nome).strip() == '':
        return jsonify({"erro": "O nome do produto é obrigatório."}), 400

    # Perfil Estoquista não define preço; para outros perfis, valida se enviado
    usuario_perfil = session.get('usuario_perfil')
    if usuario_perfil != 'Estoque' and preco is None:
        return jsonify({"erro": "O preço do produto é obrigatório."}), 400

    try:
        resultado = estoque_service.cadastrar_produto(
            dados,
            responsavel=session.get('usuario_nome', 'Sistema'),
            usuario_perfil=usuario_perfil
        )
        return jsonify(resultado), 201
    except PermissionError as pe:
        return jsonify({"erro": str(pe)}), 403
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/produtos/<int:produto_id>', methods=['PUT'])
@login_required
@require_permission('produtos')
def editar_produto(produto_id):
    dados = request.get_json() or {}
    nome = dados.get('nome')
    if nome is not None and str(nome).strip() == '':
        return jsonify({"erro": "O nome do produto não pode ser vazio."}), 400

    usuario_perfil = session.get('usuario_perfil')
    try:
        resultado = estoque_service.atualizar_produto(produto_id, dados, usuario_perfil=usuario_perfil)
        return jsonify(resultado)
    except PermissionError as pe:
        return jsonify({"erro": str(pe)}), 403
    except KeyError as ke:
        return jsonify({"erro": str(ke).strip("'")}), 404
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/produtos/<int:produto_id>', methods=['DELETE'])
@login_required
@require_permission('produtos')
def excluir_produto(produto_id):
    usuario_perfil = session.get('usuario_perfil')
    try:
        resultado = estoque_service.excluir_produto(produto_id, usuario_perfil=usuario_perfil)
        return jsonify(resultado)
    except PermissionError as pe:
        return jsonify({"erro": str(pe)}), 403
    except KeyError as ke:
        return jsonify({"erro": str(ke).strip("'")}), 404
    except pymysql.err.IntegrityError:
        return jsonify({"erro": "Não é possível excluir produto vinculado a pedidos existentes."}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# --- NOVAS ROTAS ESPECÍFICAS DE GESTÃO DE ESTOQUE ---

@app.route('/api/estoque/resumo', methods=['GET'])
@login_required
@require_permission('produtos')
def obter_resumo_estoque():
    try:
        resumo = estoque_service.obter_resumo_estoque()
        return jsonify(resumo)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/estoque/movimentacoes', methods=['GET'])
@login_required
@require_permission('produtos')
def listar_historico_movimentacoes():
    produto_id = request.args.get('produto_id')
    tipo = request.args.get('tipo')
    limite = int(request.args.get('limite', 100))
    try:
        historico = estoque_service.listar_historico(limite=limite, produto_id=produto_id, tipo=tipo)
        return jsonify(historico)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/estoque/movimentacoes', methods=['POST'])
@login_required
@require_permission('produtos')
@require_action('movimentar_estoque')
def registrar_movimentacao_estoque():
    dados = request.get_json() or {}
    produto_id = dados.get('produto_id')
    tipo = dados.get('tipo')
    quantidade = dados.get('quantidade')
    motivo = dados.get('motivo')

    if not produto_id or not tipo or quantidade is None or not motivo:
        return jsonify({"erro": "Campos 'produto_id', 'tipo', 'quantidade' e 'motivo' são obrigatórios."}), 400

    try:
        resultado = estoque_service.registrar_movimentacao(
            produto_id=produto_id,
            tipo=tipo,
            quantidade=quantidade,
            motivo=motivo,
            responsavel=session.get('usuario_nome', 'Operador de Estoque')
        )
        return jsonify(resultado), 201
    except KeyError as ke:
        return jsonify({"erro": str(ke).strip("'")}), 404
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/estoque/ajustes', methods=['POST'])
@login_required
@require_permission('produtos')
@require_action('ajustar_estoque')
def registrar_ajuste_estoque():
    dados = request.get_json() or {}
    produto_id = dados.get('produto_id')
    novo_saldo = dados.get('novo_saldo')
    justificativa = dados.get('justificativa')

    if not produto_id or novo_saldo is None or not justificativa:
        return jsonify({"erro": "Campos 'produto_id', 'novo_saldo' e 'justificativa' são obrigatórios."}), 400

    try:
        resultado = estoque_service.registrar_ajuste(
            produto_id=produto_id,
            novo_saldo=novo_saldo,
            justificativa=justificativa,
            responsavel=session.get('usuario_nome', 'Conferente de Estoque')
        )
        return jsonify(resultado), 201
    except KeyError as ke:
        return jsonify({"erro": str(ke).strip("'")}), 404
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/estoque/relatorios/criticos', methods=['GET'])
@login_required
@require_permission('produtos')
def relatorio_estoque_critico():
    try:
        criticos = estoque_service.obter_relatorio_estoque_baixo()
        return jsonify(criticos)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/estoque/relatorios/mais-movimentados', methods=['GET'])
@login_required
@require_permission('produtos')
def relatorio_mais_movimentados():
    limite = int(request.args.get('limite', 5))
    try:
        rel = estoque_service.obter_relatorio_mais_movimentados(limite=limite)
        return jsonify(rel)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


# --- 3. MÓDULO PEDIDOS ---

@app.route('/api/pedidos', methods=['GET'])
@login_required
@require_permission('pedidos')
def listar_pedidos():
    busca = request.args.get('busca')
    status_pedido = request.args.get('status_pedido')
    status_pagamento = request.args.get('status_pagamento')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    apenas_atrasados = request.args.get('apenas_atrasados', 'false').lower() == 'true'

    try:
        pedidos = pedido_service.listar_pedidos(
            busca=busca,
            status_pedido=status_pedido,
            status_pagamento=status_pagamento,
            data_inicio=data_inicio,
            data_fim=data_fim,
            apenas_atrasados=apenas_atrasados
        )
        return jsonify(pedidos)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/pedidos/indicadores', methods=['GET'])
@login_required
@require_permission('pedidos')
def obter_indicadores_pedidos():
    try:
        indicadores = pedido_service.obter_indicadores_operacionais()
        return jsonify(indicadores)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/pedidos/<int:pedido_id>', methods=['GET'])
@login_required
@require_permission('pedidos')
def obter_pedido(pedido_id):
    try:
        pedido = pedido_service.obter_pedido(pedido_id)
        if not pedido:
            return jsonify({"erro": "Pedido não encontrado."}), 404
        return jsonify(pedido)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


# --- MÓDULO DE LOGÍSTICA ---
def _logistica_permitida():
    return session.get('usuario_perfil') in ('Administrador', 'Estoque', 'Vendas', 'Gerência')

@app.route('/api/logistica/transportadoras', methods=['GET'])
@login_required
def listar_transportadoras():
    if not _logistica_permitida(): return jsonify({'erro': 'Acesso não autorizado.'}), 403
    try: return jsonify(logistica_service.listar_transportadoras(incluir_inativas=True))
    except Exception:
        logger.exception("Erro ao listar transportadoras")
        return jsonify({'erro': 'Não foi possível carregar as transportadoras.'}), 500

@app.route('/api/logistica/transportadoras', methods=['POST'])
@login_required
def salvar_transportadora():
    if session.get('usuario_perfil') not in ('Administrador', 'Gerência'): return jsonify({'erro': 'Apenas Administração ou Gerência podem cadastrar transportadoras.'}), 403
    try: return jsonify(logistica_service.salvar_transportadora(request.get_json() or {})), 201
    except ValueError as e: return jsonify({'erro': str(e)}), 400
    except Exception:
        logger.exception("Erro ao salvar transportadora")
        return jsonify({'erro': 'Não foi possível salvar a transportadora.'}), 500

@app.route('/api/logistica/transportadoras/<int:transportadora_id>', methods=['PUT'])
@login_required
def editar_transportadora(transportadora_id):
    if session.get('usuario_perfil') not in ('Administrador', 'Gerência'): return jsonify({'erro': 'Apenas Administração ou Gerência podem editar transportadoras.'}), 403
    try: return jsonify(logistica_service.salvar_transportadora(request.get_json() or {}, transportadora_id))
    except KeyError as e: return jsonify({'erro': str(e)}), 404
    except ValueError as e: return jsonify({'erro': str(e)}), 400
    except Exception:
        logger.exception("Erro ao editar transportadora")
        return jsonify({'erro': 'Não foi possível editar a transportadora.'}), 500

@app.route('/api/logistica/transportadoras/<int:transportadora_id>/ativo', methods=['PATCH'])
@login_required
def alterar_transportadora_ativa(transportadora_id):
    if session.get('usuario_perfil') not in ('Administrador', 'Gerência'): return jsonify({'erro': 'Acesso não autorizado.'}), 403
    try: return jsonify(logistica_service.alterar_ativo_transportadora(transportadora_id, (request.get_json() or {}).get('ativo', False)))
    except KeyError as e: return jsonify({'erro': str(e)}), 404
    except Exception:
        logger.exception("Erro ao alterar transportadora")
        return jsonify({'erro': 'Não foi possível alterar a situação.'}), 500

@app.route('/api/logistica/cotacao', methods=['POST'])
@login_required
def cotar_frete():
    if not _logistica_permitida(): return jsonify({'erro': 'Acesso não autorizado.'}), 403
    dados = request.get_json() or {}
    try:
        return jsonify(logistica_service.calcular_frete(dados.get('transportadora_id'), dados.get('subtotal', 0), dados.get('peso_kg', 0)))
    except (ValueError, KeyError) as e: return jsonify({'erro': str(e)}), 400
    except Exception:
        logger.exception("Erro ao calcular frete")
        return jsonify({'erro': 'Não foi possível calcular o frete.'}), 500

@app.route('/api/logistica/entregas', methods=['GET'])
@login_required
def listar_entregas():
    if not _logistica_permitida(): return jsonify({'erro': 'Acesso não autorizado.'}), 403
    try: return jsonify(logistica_service.listar_entregas())
    except Exception:
        logger.exception("Erro ao listar entregas")
        return jsonify({'erro': 'Não foi possível carregar as entregas.'}), 500

@app.route('/api/logistica/entregas/<int:pedido_id>', methods=['PUT'])
@login_required
def salvar_dados_entrega(pedido_id):
    if not _logistica_permitida(): return jsonify({'erro': 'Acesso não autorizado.'}), 403
    try:
        return jsonify(logistica_service.registrar_entrega(pedido_id, request.get_json() or {}, session.get('usuario_nome') or 'Operador'))
    except KeyError as e: return jsonify({'erro': str(e)}), 404
    except ValueError as e: return jsonify({'erro': str(e)}), 400
    except Exception:
        logger.exception("Erro ao salvar dados da entrega")
        return jsonify({'erro': 'Não foi possível salvar os dados logísticos.'}), 500

@app.route('/api/logistica/entregas/<int:pedido_id>/status', methods=['PATCH'])
@login_required
def atualizar_status_entrega(pedido_id):
    if not _logistica_permitida(): return jsonify({'erro': 'Acesso não autorizado.'}), 403
    dados = request.get_json() or {}
    novo_status = str(dados.get('status') or '').strip()
    if novo_status not in ('Enviado', 'Em Transporte', 'Entregue'):
        return jsonify({'erro': 'Etapa logística inválida.'}), 400
    try:
        resultado = pedido_service.atualizar_status(pedido_id, novo_status, responsavel=session.get('usuario_nome') or 'Operador', usuario_perfil=session.get('usuario_perfil'), observacao=dados.get('observacoes'))
        logistica_service.atualizar_evento_entrega(pedido_id, novo_status, session.get('usuario_nome') or 'Operador', dados.get('observacoes'))
        return jsonify(resultado)
    except KeyError as e: return jsonify({'erro': str(e)}), 404
    except (ValueError, PermissionError) as e: return jsonify({'erro': str(e)}), 400
    except Exception:
        logger.exception("Erro ao atualizar etapa logística")
        return jsonify({'erro': 'Não foi possível atualizar a etapa da entrega.'}), 500

@app.route('/api/pedidos', methods=['POST'])
@login_required
@require_permission('pedidos')
@require_action('criar_pedido')
def criar_pedido():
    dados = request.get_json() or {}
    itens = dados.get('itens', [])
    cliente_id = dados.get('cliente_id')
    desconto = dados.get('desconto', 0.0)
    frete = dados.get('frete', 0.0)
    transportadora_id = dados.get('transportadora_id')
    peso_kg = dados.get('peso_kg', 0)
    cotacao = None
    forma_pagamento = dados.get('forma_pagamento', 'PIX')
    endereco_entrega = dados.get('endereco_entrega')
    data_prevista_entrega = dados.get('data_prevista_entrega')
    observacoes = dados.get('observacoes')
    responsavel = session.get('usuario_nome') or 'Vendedor'

    try:
        if transportadora_id:
            conn_cotacao = get_db_connection()
            try:
                subtotal_estimado = 0.0
                with conn_cotacao.cursor() as cursor:
                    for item in itens:
                        cursor.execute("SELECT preco FROM produtos WHERE id = %s", (item.get('produto_id'),))
                        produto_cotacao = cursor.fetchone()
                        if not produto_cotacao:
                            raise KeyError("Produto não encontrado para cálculo do frete.")
                        subtotal_estimado += float(produto_cotacao['preco']) * int(item.get('quantidade') or 0)
            finally:
                conn_cotacao.close()
            cotacao = logistica_service.calcular_frete(transportadora_id, subtotal_estimado, peso_kg)
            frete = cotacao['frete']
            if not data_prevista_entrega:
                data_prevista_entrega = cotacao['data_prevista']

        resultado = pedido_service.criar_pedido(
            itens=itens,
            cliente_id=cliente_id,
            desconto=desconto,
            frete=frete,
            forma_pagamento=forma_pagamento,
            endereco_entrega=endereco_entrega,
            responsavel=responsavel,
            data_prevista_entrega=data_prevista_entrega,
            observacoes=observacoes
        )
        if transportadora_id:
            try:
                logistica_service.registrar_entrega(resultado['pedido_id'], {
                    'transportadora_id': transportadora_id,
                    'peso_kg': peso_kg,
                    'valor_frete': frete,
                    'data_prevista': data_prevista_entrega
                }, responsavel)
            except Exception:
                logger.exception("Pedido criado, mas houve falha ao registrar os dados logísticos.")
                resultado['aviso_logistica'] = 'Pedido criado, mas os dados de transporte precisam ser configurados no módulo de Logística.'
        return jsonify(resultado), 201
    except KeyError as ke:
        return jsonify({"erro": str(ke).strip("'")}), 404
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/pedidos/<int:pedido_id>/status', methods=['PATCH'])
@login_required
def atualizar_status_pedido(pedido_id):
    perfil = session.get('usuario_perfil')
    # Permissão para gerenciar status: Vendas, Gerência, Administrador, ou Estoque (operações de separação/expedição)
    if perfil not in ['Vendas', 'Gerência', 'Administrador', 'Estoque']:
        return jsonify({"erro": "Acesso não autorizado ao controle de pedidos."}), 403

    dados = request.get_json() or {}
    novo_status = dados.get('status', '').strip()
    observacao = dados.get('observacao')
    responsavel = session.get('usuario_nome') or 'Usuário'

    # RBAC Específico: Estoque só pode avançar Em Separação, Pronto para Envio e Enviado
    if perfil == 'Estoque' and novo_status not in ['Em Separação', 'Pronto para Envio', 'Enviado']:
        return jsonify({"erro": f"Perfil 'Estoque' só pode executar operações de separação e expedição ('Em Separação', 'Pronto para Envio', 'Enviado')."}), 403

    # Financeiro não pode alterar status operacional do pedido
    if perfil == 'Financeiro':
        return jsonify({"erro": "Perfil 'Financeiro' não tem permissão para alterar status operacional de pedidos."}), 403

    try:
        resultado = pedido_service.atualizar_status(
            pedido_id=pedido_id,
            novo_status=novo_status,
            responsavel=responsavel,
            observacao=observacao
        )
        return jsonify(resultado)
    except KeyError as ke:
        return jsonify({"erro": str(ke).strip("'")}), 404
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/pedidos/<int:pedido_id>/pagamento', methods=['PATCH'])
@login_required
@require_action('confirmar_pagamento')
def confirmar_pagamento_pedido(pedido_id):
    dados = request.get_json() or {}
    novo_status_pagamento = dados.get('status_pagamento', 'Aprovado')
    transacao_id = dados.get('transacao_id')
    comprovante = dados.get('comprovante')
    valor = dados.get('valor')
    responsavel = session.get('usuario_nome') or 'Operador Financeiro'
    usuario_perfil = session.get('usuario_perfil')

    try:
        resultado = pedido_service.confirmar_pagamento(
            pedido_id=pedido_id,
            novo_status_pagamento=novo_status_pagamento,
            responsavel=responsavel,
            usuario_perfil=usuario_perfil,
            transacao_id=transacao_id,
            comprovante=comprovante,
            valor=float(valor) if valor is not None else None
        )
        return jsonify(resultado)
    except KeyError as ke:
        return jsonify({"erro": str(ke).strip("'")}), 404
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except PermissionError as pe:
        return jsonify({"erro": str(pe)}), 403
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/pedidos/<int:pedido_id>/cancelar', methods=['POST'])
@login_required
@require_permission('pedidos')
@require_action('cancelar_pedido')
def cancelar_pedido(pedido_id):
    dados = request.get_json() or {}
    motivo = dados.get('motivo')
    if not motivo:
        return jsonify({"erro": "Motivo do cancelamento é obrigatório."}), 400

    responsavel = session.get('usuario_nome') or 'Usuário'

    try:
        resultado = pedido_service.cancelar_pedido(
            pedido_id=pedido_id,
            motivo=motivo,
            responsavel=responsavel
        )
        return jsonify(resultado)
    except KeyError as ke:
        return jsonify({"erro": str(ke).strip("'")}), 404
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/pedidos/<int:pedido_id>/devolucao', methods=['POST'])
@login_required
@require_permission('pedidos')
@require_action('solicitar_devolucao')
def solicitar_devolucao_pedido(pedido_id):
    dados = request.get_json() or {}
    motivo = dados.get('motivo')
    if not motivo:
        return jsonify({"erro": "Motivo da devolução é obrigatório."}), 400

    responsavel = session.get('usuario_nome') or 'Atendente'

    try:
        resultado = pedido_service.solicitar_devolucao(
            pedido_id=pedido_id,
            motivo=motivo,
            responsavel=responsavel
        )
        return jsonify(resultado)
    except KeyError as ke:
        return jsonify({"erro": str(ke).strip("'")}), 404
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/pedidos/<int:pedido_id>/conferir-devolucao', methods=['POST'])
@login_required
@require_action('conferir_devolucao')
def conferir_devolucao_pedido(pedido_id):
    dados = request.get_json() or {}
    condicao_itens = dados.get('condicao_itens', 'Itens conferidos em perfeito estado.')
    retornar_ao_estoque = dados.get('retornar_ao_estoque', True)
    responsavel = session.get('usuario_nome') or 'Conferente Estoque'

    try:
        resultado = pedido_service.conferir_e_retornar_devolucao(
            pedido_id=pedido_id,
            conferente=responsavel,
            condicao_itens=condicao_itens,
            retornar_ao_estoque=retornar_ao_estoque
        )
        return jsonify(resultado)
    except KeyError as ke:
        return jsonify({"erro": str(ke).strip("'")}), 404
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# --- 4. MÓDULO CLIENTES ---


# --- MÓDULO DE COMPRAS, FORNECEDORES E RECEBIMENTO ---
@app.route('/api/compras/fornecedores', methods=['GET'])
@login_required
@require_permission('compras')
def listar_fornecedores_compras():
    try:
        return jsonify(financeiro_service.listar_fornecedores(request.args.get('busca')))
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/compras/fornecedores', methods=['POST'])
@login_required
@require_permission('compras')
def cadastrar_fornecedor_compras():
    if session.get('usuario_perfil') not in ['Administrador', 'Gerência', 'Financeiro']:
        return jsonify({"erro": "Somente Administração, Gerência ou Financeiro podem cadastrar fornecedores."}), 403
    dados = request.get_json() or {}
    try:
        resultado = financeiro_service.cadastrar_fornecedor(
            razao_social=dados.get('razao_social'),
            cnpj_cpf=dados.get('cnpj_cpf', ''),
            email=dados.get('email', ''),
            telefone=dados.get('telefone', ''),
            categoria=dados.get('categoria', 'Geral')
        )
        return jsonify(resultado), 201
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/compras', methods=['GET'])
@login_required
@require_permission('compras')
def listar_compras():
    try:
        return jsonify(compras_service.listar_compras(request.args.get('status')))
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/compras/<int:compra_id>', methods=['GET'])
@login_required
@require_permission('compras')
def obter_compra(compra_id):
    try:
        compra = compras_service.obter_compra(compra_id)
        return (jsonify(compra), 200) if compra else (jsonify({"erro": "Ordem de compra não encontrada."}), 404)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/compras', methods=['POST'])
@login_required
@require_permission('compras')
def criar_compra():
    if session.get('usuario_perfil') not in ['Administrador', 'Gerência', 'Compras']:
        return jsonify({"erro": "Seu perfil não pode criar ordens de compra."}), 403
    try:
        resultado = compras_service.criar_compra(request.get_json() or {}, session.get('usuario_nome', 'Compras'))
        return jsonify(resultado), 201
    except KeyError as e:
        return jsonify({"erro": str(e).strip("'")}), 404
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        logger.exception("Falha ao criar ordem de compra")
        return jsonify({"erro": "Não foi possível criar a ordem de compra."}), 500

@app.route('/api/compras/<int:compra_id>/recebimento', methods=['POST'])
@login_required
@require_permission('compras')
def receber_compra(compra_id):
    if session.get('usuario_perfil') not in ['Administrador', 'Gerência', 'Estoque', 'Compras']:
        return jsonify({"erro": "Seu perfil não pode registrar recebimentos."}), 403
    try:
        resultado = compras_service.receber_compra(compra_id, request.get_json() or {}, session.get('usuario_nome', 'Estoque'))
        return jsonify(resultado)
    except KeyError as e:
        return jsonify({"erro": str(e).strip("'")}), 404
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception:
        logger.exception("Falha ao receber compra")
        return jsonify({"erro": "Não foi possível registrar o recebimento."}), 500

@app.route('/api/estoque/reposicao', methods=['GET'])
@login_required
@require_permission('produtos')
def listar_sugestoes_reposicao():
    try:
        return jsonify(compras_service.obter_reposicao())
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/estoque/lotes', methods=['GET'])
@login_required
@require_permission('produtos')
def listar_lotes_validade():
    try:
        return jsonify(compras_service.listar_lotes(request.args.get('dias', 30)))
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# --- FRENTE DE CAIXA (PDV) ---
@app.route('/api/pdv/caixa', methods=['GET'])
@login_required
@require_permission('pdv')
def obter_caixa_pdv():
    try:
        return jsonify(compras_service.obter_caixa_aberto(session.get('usuario_nome')))
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/pdv/caixa/abrir', methods=['POST'])
@login_required
@require_permission('pdv')
def abrir_caixa_pdv():
    try:
        dados = request.get_json() or {}
        return jsonify(compras_service.abrir_caixa(session.get('usuario_nome', 'Operador'), dados.get('saldo_inicial', 0))), 201
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/pdv/caixa/fechar', methods=['POST'])
@login_required
@require_permission('pdv')
def fechar_caixa_pdv():
    try:
        dados = request.get_json() or {}
        return jsonify(compras_service.fechar_caixa(session.get('usuario_nome', 'Operador'), dados.get('saldo_informado', 0)))
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/pdv/vendas', methods=['POST'])
@login_required
@require_permission('pdv')
def concluir_venda_pdv():
    perfil = session.get('usuario_perfil')
    if perfil not in ['Administrador', 'Gerência', 'Vendas']:
        return jsonify({"erro": "Seu perfil não pode operar o caixa."}), 403
    dados = request.get_json() or {}
    operador = session.get('usuario_nome', 'Operador de Caixa')
    try:
        caixa = compras_service.obter_caixa_aberto(operador)
        if not caixa:
            raise ValueError("Abra o caixa antes de registrar uma venda.")
        pedido = pedido_service.criar_pedido(
            itens=dados.get('itens', []),
            cliente_id=dados.get('cliente_id'),
            desconto=dados.get('desconto', 0),
            frete=0,
            forma_pagamento=dados.get('forma_pagamento', 'Dinheiro'),
            endereco_entrega='',
            responsavel=operador,
            observacoes='Venda realizada no PDV',
            usuario_perfil=perfil
        )
        pedido_id = pedido['pedido_id']
        pedido_service.confirmar_pagamento(
            pedido_id=pedido_id,
            responsavel=operador,
            usuario_perfil='Financeiro',
            valor=pedido['valor_total']
        )
        pedido_service.atualizar_status(pedido_id, 'Em Separação', responsavel=operador, usuario_perfil=perfil)
        pedido_service.atualizar_status(pedido_id, 'Pronto para Envio', responsavel=operador, usuario_perfil=perfil)
        pedido_service.atualizar_status(pedido_id, 'Enviado', responsavel=operador, usuario_perfil=perfil)
        pedido_service.atualizar_status(pedido_id, 'Entregue', responsavel=operador, usuario_perfil=perfil)
        compras_service.vincular_venda_pdv(pedido_id, caixa['id'], operador)
        return jsonify({"mensagem": "Venda concluída e registrada no caixa.", "pedido_id": pedido_id,
                        "numero_pedido": pedido['numero_pedido'], "valor_total": pedido['valor_total']}), 201
    except (KeyError, ValueError, PermissionError) as e:
        return jsonify({"erro": str(e).strip("'")}), 400
    except Exception:
        logger.exception("Falha no checkout do PDV")
        return jsonify({"erro": "Não foi possível concluir a venda. Verifique os pedidos antes de tentar novamente."}), 500

@app.route('/api/clientes', methods=['GET'])
@login_required
@require_permission('clientes')
def listar_clientes():
    busca = request.args.get('busca')
    try:
        clientes = cliente_service.listar_clientes(busca=busca)
        return jsonify(clientes)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/clientes/<int:cliente_id>', methods=['GET'])
@login_required
@require_permission('clientes')
def obter_cliente(cliente_id):
    try:
        cliente = cliente_service.obter_cliente(cliente_id, incluir_pedidos=True)
        if not cliente:
            return jsonify({"erro": "Cliente não encontrado."}), 404
        return jsonify(cliente)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/clientes', methods=['POST'])
@login_required
@require_permission('clientes')
@require_action('cadastrar_cliente')
def cadastrar_cliente():
    dados = request.get_json() or {}
    nome = dados.get('nome')
    email = dados.get('email')
    cpf = dados.get('cpf')
    telefone = dados.get('telefone', '')
    cep = dados.get('cep', '')
    logradouro = dados.get('logradouro', '')
    numero = dados.get('numero', '')
    complemento = dados.get('complemento', '')
    bairro = dados.get('bairro', '')
    cidade = dados.get('cidade', '')
    uf = dados.get('uf', '')

    # Se veio um campo legado 'endereco' e logradouro vazio
    if not logradouro and dados.get('endereco'):
        logradouro = dados.get('endereco')

    try:
        resultado = cliente_service.cadastrar_cliente(
            nome=nome,
            email=email,
            cpf=cpf,
            telefone=telefone,
            cep=cep,
            logradouro=logradouro,
            numero=numero,
            complemento=complemento,
            bairro=bairro,
            cidade=cidade,
            uf=uf
        )
        return jsonify(resultado), 201
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except pymysql.err.IntegrityError as ie:
        msg = str(ie).lower()
        if 'cpf' in msg:
            return jsonify({"erro": "Já existe um cliente cadastrado com este CPF."}), 400
        return jsonify({"erro": "Já existe um cliente cadastrado com este e-mail."}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/clientes/<int:cliente_id>', methods=['PUT', 'PATCH'])
@login_required
@require_permission('clientes')
@require_action('editar_cliente')
def atualizar_cliente(cliente_id):
    dados = request.get_json() or {}
    nome = dados.get('nome')
    email = dados.get('email')
    cpf = dados.get('cpf')
    telefone = dados.get('telefone', '')
    cep = dados.get('cep', '')
    logradouro = dados.get('logradouro', '')
    numero = dados.get('numero', '')
    complemento = dados.get('complemento', '')
    bairro = dados.get('bairro', '')
    cidade = dados.get('cidade', '')
    uf = dados.get('uf', '')

    if not logradouro and dados.get('endereco'):
        logradouro = dados.get('endereco')

    try:
        resultado = cliente_service.atualizar_cliente(
            id=cliente_id,
            nome=nome,
            email=email,
            cpf=cpf,
            telefone=telefone,
            cep=cep,
            logradouro=logradouro,
            numero=numero,
            complemento=complemento,
            bairro=bairro,
            cidade=cidade,
            uf=uf
        )
        return jsonify(resultado)
    except KeyError as ke:
        return jsonify({"erro": str(ke).strip("'")}), 404
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except pymysql.err.IntegrityError as ie:
        msg = str(ie).lower()
        if 'cpf' in msg:
            return jsonify({"erro": "Já existe outro cliente cadastrado com este CPF."}), 400
        return jsonify({"erro": "Já existe outro cliente cadastrado com este e-mail."}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/clientes/<int:cliente_id>', methods=['DELETE'])
@login_required
@require_permission('clientes')
@require_action('excluir_cliente')
def excluir_cliente(cliente_id):
    try:
        resultado = cliente_service.excluir_cliente(cliente_id)
        return jsonify(resultado)
    except KeyError as ke:
        return jsonify({"erro": str(ke).strip("'")}), 404
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# --- 5. MÓDULO ADMINISTRAÇÃO DE USUÁRIOS (SOMENTE ADMINISTRADOR) ---

@app.route('/api/perfis', methods=['GET'])
@login_required
@require_permission('usuarios')
def listar_perfis():
    try:
        perfis = usuario_service.listar_perfis()
        return jsonify(perfis)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/usuarios', methods=['GET'])
@login_required
@require_permission('usuarios')
def listar_usuarios():
    try:
        usuarios = usuario_service.listar_usuarios()
        return jsonify(usuarios)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/usuarios', methods=['POST'])
@login_required
@require_permission('usuarios')
def cadastrar_usuario():
    dados = request.get_json() or {}
    nome = dados.get('nome')
    email = dados.get('email')
    senha = dados.get('senha')
    perfil_id = dados.get('perfil_id')
    ativo = dados.get('ativo', True)

    if not nome or not email or not senha or not perfil_id:
        return jsonify({"erro": "Todos os campos (nome, email, senha e perfil) são obrigatórios."}), 400

    try:
        resultado = usuario_service.cadastrar_usuario(nome, email, senha, perfil_id, ativo)
        return jsonify(resultado), 201
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except pymysql.err.IntegrityError:
        return jsonify({"erro": "Já existe um usuário com este e-mail."}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/usuarios/<int:usuario_id>', methods=['PUT'])
@login_required
@require_permission('usuarios')
def editar_usuario(usuario_id):
    dados = request.get_json() or {}
    nome = dados.get('nome')
    email = dados.get('email')
    perfil_id = dados.get('perfil_id')
    senha = dados.get('senha')

    if not nome or not email or not perfil_id:
        return jsonify({"erro": "Nome, e-mail e perfil são obrigatórios."}), 400

    try:
        resultado = usuario_service.atualizar_usuario(usuario_id, nome, email, perfil_id, senha)
        return jsonify(resultado)
    except KeyError as ke:
        return jsonify({"erro": str(ke).strip("'")}), 404
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except pymysql.err.IntegrityError:
        return jsonify({"erro": "Já existe outro usuário com este e-mail."}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/usuarios/<int:usuario_id>/status', methods=['PATCH'])
@login_required
@require_permission('usuarios')
def alternar_status_usuario(usuario_id):
    dados = request.get_json() or {}
    ativo = dados.get('ativo')

    if ativo is None:
        return jsonify({"erro": "Campo 'ativo' (boolean) é obrigatório."}), 400

    try:
        resultado = usuario_service.alternar_status(usuario_id, ativo, session.get('usuario_id'))
        return jsonify(resultado)
    except KeyError as ke:
        return jsonify({"erro": str(ke).strip("'")}), 404
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# --- ROTAS DA API: MÓDULO FINANCEIRO ---

@app.route('/api/financeiro/visao-geral', methods=['GET'])
@login_required
@require_permission('financeiro')
def obter_visao_geral_financeiro():
    try:
        dados = financeiro_service.obter_visao_geral()
        return jsonify(dados)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/financeiro/fornecedores', methods=['GET'])
@login_required
@require_permission('financeiro')
def listar_fornecedores():
    busca = request.args.get('busca')
    try:
        fornecedores = financeiro_service.listar_fornecedores(busca)
        return jsonify(fornecedores)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/financeiro/fornecedores', methods=['POST'])
@login_required
@require_permission('financeiro')
@require_action('cadastrar_fornecedor')
def cadastrar_fornecedor():
    dados = request.get_json() or {}
    razao_social = dados.get('razao_social')
    if not razao_social:
        return jsonify({"erro": "A razão social ou nome do credor é obrigatória."}), 400

    try:
        resultado = financeiro_service.cadastrar_fornecedor(
            razao_social=razao_social,
            cnpj_cpf=dados.get('cnpj_cpf', ''),
            email=dados.get('email', ''),
            telefone=dados.get('telefone', ''),
            categoria=dados.get('categoria', 'Geral')
        )
        return jsonify(resultado), 201
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/financeiro/contas-pagar', methods=['GET'])
@login_required
@require_permission('financeiro')
def listar_contas_pagar():
    status = request.args.get('status')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    try:
        contas = financeiro_service.listar_contas_pagar(status, data_inicio, data_fim)
        return jsonify(contas)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/financeiro/contas-pagar', methods=['POST'])
@login_required
@require_permission('financeiro')
@require_action('cadastrar_despesa')
def cadastrar_conta_pagar():
    dados = request.get_json() or {}
    descricao = dados.get('descricao')
    valor = dados.get('valor')
    data_vencimento = dados.get('data_vencimento')

    if not descricao or not valor or not data_vencimento:
        return jsonify({"erro": "Descrição, valor e data de vencimento são obrigatórios."}), 400

    try:
        resultado = financeiro_service.cadastrar_conta_pagar(
            descricao=descricao,
            valor=float(valor),
            data_vencimento=data_vencimento,
            fornecedor_id=dados.get('fornecedor_id'),
            categoria=dados.get('categoria', 'Operacional'),
            observacoes=dados.get('observacoes', '')
        )
        return jsonify(resultado), 201
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/financeiro/contas-pagar/<int:conta_id>/pagar', methods=['POST'])
@login_required
@require_permission('financeiro')
@require_action('pagar_despesa')
def pagar_conta_pagar(conta_id):
    dados = request.get_json() or {}
    valor = dados.get('valor')
    forma_pagamento = dados.get('forma_pagamento', 'PIX')
    comprovante = dados.get('comprovante')
    operacao_id = dados.get('operacao_id')
    responsavel = session.get('usuario_nome') or 'Operador Financeiro'

    if not valor:
        return jsonify({"erro": "O valor do pagamento é obrigatório."}), 400

    try:
        resultado = financeiro_service.pagar_conta(
            conta_id=conta_id,
            valor=float(valor),
            forma_pagamento=forma_pagamento,
            responsavel=responsavel,
            operacao_id=operacao_id,
            comprovante=comprovante
        )
        return jsonify(resultado)
    except KeyError as ke:
        return jsonify({"erro": str(ke).strip("'")}), 404
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/financeiro/contas-receber', methods=['GET'])
@login_required
@require_permission('financeiro')
def listar_contas_receber():
    busca = request.args.get('busca')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    try:
        contas = financeiro_service.listar_contas_receber(busca, data_inicio, data_fim)
        return jsonify(contas)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/financeiro/contas-receber/<int:pedido_id>/receber', methods=['POST'])
@login_required
@require_permission('financeiro')
@require_action('confirmar_pagamento')
def receber_pagamento_pedido(pedido_id):
    dados = request.get_json() or {}
    valor = dados.get('valor')
    forma_pagamento = dados.get('forma_pagamento', 'PIX')
    comprovante = dados.get('comprovante')
    operacao_id = dados.get('operacao_id')
    responsavel = session.get('usuario_nome') or 'Operador Financeiro'

    if not valor:
        return jsonify({"erro": "O valor de recebimento é obrigatório."}), 400

    try:
        resultado = financeiro_service.receber_pagamento_pedido(
            pedido_id=pedido_id,
            valor=float(valor),
            forma_pagamento=forma_pagamento,
            responsavel=responsavel,
            operacao_id=operacao_id,
            comprovante=comprovante
        )
        return jsonify(resultado)
    except KeyError as ke:
        return jsonify({"erro": str(ke).strip("'")}), 404
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/financeiro/pedidos/<int:pedido_id>/estornar', methods=['POST'])
@login_required
@require_permission('financeiro')
@require_action('registrar_reembolso')
def estornar_pagamento_pedido(pedido_id):
    dados = request.get_json() or {}
    valor = dados.get('valor')
    motivo = dados.get('motivo')
    operacao_id = dados.get('operacao_id')
    responsavel = session.get('usuario_nome') or 'Operador Financeiro'

    if not valor or not motivo:
        return jsonify({"erro": "Valor e motivo do estorno são obrigatórios."}), 400

    try:
        resultado = financeiro_service.estornar_pagamento_pedido(
            pedido_id=pedido_id,
            valor=float(valor),
            motivo=motivo,
            responsavel=responsavel,
            operacao_id=operacao_id
        )
        return jsonify(resultado)
    except KeyError as ke:
        return jsonify({"erro": str(ke).strip("'")}), 404
    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/financeiro/fluxo-caixa', methods=['GET'])
@login_required
@require_permission('financeiro')
def listar_fluxo_caixa():
    tipo = request.args.get('tipo')
    origem = request.args.get('origem')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    try:
        transacoes = financeiro_service.listar_fluxo_caixa(tipo, origem, data_inicio, data_fim)
        return jsonify(transacoes)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
