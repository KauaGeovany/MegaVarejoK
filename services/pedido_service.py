import datetime
from database.connection import DatabaseConnection
from models.pedido import Pedido, ItemPedido
from models.movimentacao_estoque import MovimentacaoEstoque
from models.financeiro import ContaReceber, TransacaoCaixa
import uuid
from repositories.pedido_repository import PedidoRepository
from repositories.produto_repository import ProdutoRepository
from repositories.movimentacao_repository import MovimentacaoRepository
from repositories.financeiro_repository import FinanceiroRepository

class PedidoService:
    """
    Camada de serviço para o módulo de Pedidos reformulado.
    Implementa:
    - Ciclo de vida com separação de status de pedido e status de pagamento.
    - Reserva automática de estoque no momento da criação/aprovação.
    - Baixa física do estoque e encerramento da reserva na expedição (Pronto para Envio / Enviado).
    - Liberação de reserva em cancelamentos.
    - Fluxo de devolução com conferência física prévia.
    - Validação de permissões baseada no cargo do usuário (Vendedor, Estoquista, Gerente, Financeiro, Administrador).
    """

    def __init__(self, pedido_repo: PedidoRepository = None, produto_repo: ProdutoRepository = None,
                 mov_repo: MovimentacaoRepository = None, financeiro_repo: FinanceiroRepository = None):
        self._pedido_repo = pedido_repo or PedidoRepository()
        self._produto_repo = produto_repo or ProdutoRepository()
        self._mov_repo = mov_repo or MovimentacaoRepository()
        self._financeiro_repo = financeiro_repo or FinanceiroRepository()

    def listar_pedidos(self, busca: str = None, status_pedido: str = None, status_pagamento: str = None,
                       data_inicio: str = None, data_fim: str = None, apenas_atrasados: bool = False) -> list:
        pedidos = self._pedido_repo.listar_todos(
            busca=busca,
            status_pedido=status_pedido,
            status_pagamento=status_pagamento,
            data_inicio=data_inicio,
            data_fim=data_fim,
            apenas_atrasados=apenas_atrasados
        )
        return [p.to_dict() for p in pedidos]

    def obter_pedido(self, id: int) -> dict:
        pedido = self._pedido_repo.buscar_por_id(id)
        if not pedido:
            return None
        dados = pedido.to_dict()
        dados['historico'] = self._pedido_repo.listar_historico(id)
        dados['cancelamentos_devolucoes'] = self._pedido_repo.listar_cancelamentos_devolucoes(id)
        return dados

    def obter_indicadores_operacionais(self) -> dict:
        return self._pedido_repo.obter_indicadores_operacionais()

    def criar_pedido(self, itens: list, responsavel: str = "Vendedor", usuario_perfil: str = None,
                     cliente_id: int = None, desconto: float = 0.0, frete: float = 0.0,
                     forma_pagamento: str = "Boleto Bancário", endereco_entrega: str = "",
                     data_prevista_entrega=None, observacoes: str = "") -> dict:
        """
        Criação de pedidos:
        - Vendedor, Gerente e Administrador podem criar pedidos.
        - Reserva os produtos no estoque garantindo que o mesmo item não seja vendido em duplicidade.
        - Não considera pago automaticamente: status inicial é 'Aguardando Pagamento' e pagamento 'Pendente'.
        """
        if usuario_perfil in ['Estoque']:
            raise PermissionError("Operadores de estoque não têm permissão para criar novos pedidos.")

        itens_dados = itens if isinstance(itens, list) else []
        if not itens_dados:
            raise ValueError("O pedido deve conter pelo menos um item.")

        conn = DatabaseConnection.get_connection()
        try:
            pedido = Pedido(
                cliente_id=cliente_id,
                status='Aguardando Pagamento',
                status_pagamento='Pendente',
                forma_pagamento=forma_pagamento,
                desconto=desconto,
                frete=frete,
                endereco_entrega=endereco_entrega,
                responsavel=responsavel,
                data_prevista_entrega=data_prevista_entrega,
                observacoes=observacoes
            )

            produtos_para_atualizar = []
            movimentacoes_para_salvar = []

            for item_info in itens_dados:
                produto_id = item_info.get('produto_id')
                quantidade = item_info.get('quantidade')

                if not produto_id or not quantidade:
                    raise ValueError("Item com produto ou quantidade inválida.")

                try:
                    qtd = int(quantidade)
                    if qtd <= 0:
                        raise ValueError("A quantidade de cada produto deve ser maior que zero.")
                except (TypeError, ValueError):
                    raise ValueError("Quantidade inválida informada.")

                # Bloqueia a linha no banco com lock transacional
                produto = self._produto_repo.buscar_por_id_com_lock(int(produto_id), conn)
                if not produto:
                    raise KeyError(f"Produto ID {produto_id} não encontrado.")

                # Validação de disponibilidade considerando o estoque reservado
                if not produto.possui_estoque(qtd):
                    raise ValueError(f"Estoque disponível insuficiente para '{produto.nome}'. Disponível: {produto.estoque_disponivel}, Solicitado: {qtd}.")

                # Reserva o estoque no domínio
                produto.reservar_estoque(qtd)
                produtos_para_atualizar.append(produto)

                # Registro de auditoria de reserva
                mov = MovimentacaoEstoque(
                    produto_id=produto.id,
                    tipo='Reserva',
                    quantidade=qtd,
                    saldo_anterior=produto.estoque,
                    novo_saldo=produto.estoque, # físico não muda, muda o disponível
                    motivo=f"Reserva para novo pedido ({forma_pagamento})",
                    responsavel=responsavel
                )
                movimentacoes_para_salvar.append(mov)

                # Cria o item do pedido
                item_pedido = ItemPedido(
                    produto_id=produto.id,
                    produto_nome=produto.nome,
                    quantidade=qtd,
                    preco_unitario=produto.preco
                )
                pedido.adicionar_item(item_pedido)

            # Salva o pedido no banco
            pedido_id = self._pedido_repo.salvar_transacional(pedido, conn)

            # Atualiza o estoque reservado no banco
            for prod in produtos_para_atualizar:
                self._produto_repo.atualizar_estoque_transacional(prod.id, prod.estoque, conn, novo_reservado=prod.estoque_reservado)

            # Persiste histórico e movimentações
            for mov in movimentacoes_para_salvar:
                mov.motivo = f"Reserva de estoque para Pedido #{pedido_id}"
                self._mov_repo.salvar_transacional(mov, conn)

            self._pedido_repo.registrar_historico(
                pedido_id=pedido_id,
                status_anterior="Novo",
                status_novo="Aguardando Pagamento",
                responsavel=responsavel,
                tipo_alteracao="Criação de Pedido",
                observacao=f"Pedido criado com {len(pedido.itens)} itens e reserva garantida.",
                conn=conn
            )

            # Integração com Contas a Receber (Módulo Financeiro):
            # Gera a conta a receber vinculada ao pedido e cliente na mesma transação atômica
            vencimento_conta = data_prevista_entrega or (datetime.date.today() + datetime.timedelta(days=7))
            conta_receber = ContaReceber(
                pedido_id=pedido_id,
                cliente_id=cliente_id,
                valor_original=pedido.valor_total,
                valor_recebido=0.0,
                data_vencimento=vencimento_conta,
                status='Pendente',
                forma_pagamento=forma_pagamento,
                observacoes=f"Conta a receber gerada automaticamente na criação do Pedido #{pedido_id}"
            )
            self._financeiro_repo.criar_conta_receber(conta_receber, conn=conn)

            conn.commit()

            return {
                "mensagem": "Pedido criado com sucesso! Itens reservados no estoque.",
                "pedido_id": pedido_id,
                "numero_pedido": f"PED-{pedido_id:04d}",
                "valor_total": pedido.valor_total
            }

        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def atualizar_status(self, pedido_id: int, novo_status: str, responsavel: str = "Sistema",
                         usuario_perfil: str = None, observacao: str = None) -> dict:
        """
        Atualiza o status operacional com validações de transição e regras por perfil:
        - Estoquista: pode alterar para 'Em Separação', 'Pronto para Envio' e 'Enviado'.
        - Vendedor: pode acompanhar e cancelar pedidos não enviados.
        - Gerente / Administrador: controle e aprovação geral.
        """
        conn = DatabaseConnection.get_connection()
        try:
            pedido = self._pedido_repo.buscar_por_id(pedido_id)
            if not pedido:
                raise KeyError("Pedido não encontrado.")

            status_anterior = pedido.status

            # Validação da máquina de estados
            if not pedido.transicao_valida(novo_status):
                raise ValueError(f"Transição inválida de '{status_anterior}' para '{novo_status}'.")

            # Validações por perfil
            if usuario_perfil == 'Estoque':
                if novo_status not in ['Em Separação', 'Pronto para Envio', 'Enviado']:
                    raise PermissionError("Operadores de estoque só podem alterar status de separação e expedição.")

            # Se a transição for para 'Enviado' (ou 'Pronto para Envio'), consolida a saída física
            if novo_status in ['Enviado', 'Pronto para Envio', 'Entregue'] and status_anterior not in ['Pronto para Envio', 'Enviado', 'Em Transporte', 'Entregue']:
                for item in pedido.itens:
                    prod = self._produto_repo.buscar_por_id_com_lock(item.produto_id, conn)
                    if prod:
                        saldo_ant = prod.estoque
                        prod.expedir_reserva(item.quantidade)
                        self._produto_repo.atualizar_estoque_transacional(prod.id, prod.estoque, conn, novo_reservado=prod.estoque_reservado)

                        # Registra saída definitiva no Kardex
                        mov = MovimentacaoEstoque(
                            produto_id=prod.id,
                            tipo='Saída',
                            quantidade=item.quantidade,
                            saldo_anterior=saldo_ant,
                            novo_saldo=prod.estoque,
                            motivo=f"Expedição física do Pedido #{pedido.id}",
                            responsavel=responsavel
                        )
                        self._mov_repo.salvar_transacional(mov, conn)

            # Atualiza no banco
            self._pedido_repo.atualizar_status(pedido.id, novo_status, conn=conn)

            # Registra auditoria
            self._pedido_repo.registrar_historico(
                pedido_id=pedido.id,
                status_anterior=status_anterior,
                status_novo=novo_status,
                responsavel=responsavel,
                tipo_alteracao="Mudança de Status",
                observacao=observacao or f"Status alterado para {novo_status}.",
                conn=conn
            )

            conn.commit()
            return {"mensagem": f"Status do pedido atualizado para '{novo_status}' com sucesso!"}

        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def confirmar_pagamento(self, pedido_id: int, responsavel: str = "Financeiro", usuario_perfil: str = None,
                            novo_status_pagamento: str = "Confirmado", transacao_id: str = None,
                            comprovante: str = None, valor: float = None, via_pdv: bool = False) -> dict:
        """
        Confirmação de pagamento (Módulo Financeiro / Gerência / Admin).
        Após o pagamento confirmado, o pedido transita automaticamente para 'Confirmado' / 'Aguardando Separação'.
        Atualiza a conta a receber correspondente e gera entrada efetiva no Fluxo de Caixa.
        """
        if usuario_perfil not in ['Financeiro', 'Gerência', 'Administrador', None] and not (via_pdv and usuario_perfil == 'Vendas'):
            raise PermissionError("Apenas Financeiro, Gerência, Administração ou uma venda autenticada no PDV podem confirmar pagamentos.")

        conn = DatabaseConnection.get_connection()
        try:
            pedido = self._pedido_repo.buscar_por_id(pedido_id)
            if not pedido:
                raise KeyError("Pedido não encontrado.")

            if pedido.status in ['Cancelado', 'Devolvido', 'Recusado']:
                raise ValueError(f"Não é possível confirmar pagamento de um pedido com status '{pedido.status}'.")

            # Verifica quanto já foi pago anteriormente
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(valor), 0.00) AS total_recebido
                    FROM pagamentos_reembolsos
                    WHERE pedido_id = %s AND tipo = 'Pagamento' AND status = 'Confirmado'
                    FOR UPDATE
                    """,
                    (pedido_id,)
                )
                total_ja_recebido = float(cursor.fetchone().get('total_recebido') or 0.0)

            saldo_pendente = max(0.0, round(pedido.valor_total - total_ja_recebido, 2))

            # Se valor não foi especificado, quita o saldo pendente restante
            v_recebido = round(float(valor) if valor is not None else saldo_pendente, 2)
            if v_recebido <= 0 and saldo_pendente > 0:
                raise ValueError("O valor de pagamento deve ser positivo maior que zero.")
            if v_recebido > saldo_pendente + 0.001:
                raise ValueError(f"O valor de R$ {v_recebido:.2f} excede o saldo pendente de R$ {saldo_pendente:.2f}.")

            # Gera operacao_id único para idempotência
            operacao_id = transacao_id or f"PED-PG-{pedido_id}-{uuid.uuid4().hex[:12]}"
            if self._financeiro_repo.existe_operacao_caixa(operacao_id, conn=conn):
                raise ValueError("Esta transação de pagamento já foi registrada no caixa anteriormente.")

            # Registra o pagamento na tabela pagamentos_reembolsos
            if v_recebido > 0:
                self._financeiro_repo.registrar_pagamento_reembolso(
                    pedido_id=pedido.id,
                    tipo='Pagamento',
                    valor=v_recebido,
                    forma_pagamento=pedido.forma_pagamento or "PIX",
                    status='Confirmado',
                    operacao_id=operacao_id,
                    confirmado_por=responsavel,
                    comprovante=comprovante,
                    conn=conn
                )

                # Registra a entrada no Fluxo de Caixa efetivo
                transacao_caixa = TransacaoCaixa(
                    operacao_id=operacao_id,
                    tipo='Entrada',
                    origem='Pedido',
                    referencia_id=pedido.id,
                    valor=v_recebido,
                    forma_pagamento=pedido.forma_pagamento or "PIX",
                    descricao=f"Recebimento de Pedido #{pedido.numero_pedido or pedido.id}",
                    responsavel=responsavel
                )
                self._financeiro_repo.registrar_transacao_caixa(transacao_caixa, conn=conn)

            novo_total_recebido = round(total_ja_recebido + v_recebido, 2)
            esta_totalmente_pago = novo_total_recebido >= round(pedido.valor_total, 2) - 0.001

            status_pag_final = "Confirmado" if esta_totalmente_pago else "Parcialmente Pago"

            # Atualiza status_pagamento no pedido
            self._pedido_repo.atualizar_status_pagamento(pedido.id, status_pag_final, conn=conn)

            # Transita status_pedido para Confirmado se estiver Aguardando Pagamento e totalmente pago
            if pedido.status == 'Aguardando Pagamento' and status_pag_final == 'Confirmado':
                self._pedido_repo.atualizar_status(pedido.id, "Confirmado", conn=conn)

            # Atualiza a tabela contas_receber vinculada
            conta_rec = self._financeiro_repo.buscar_conta_receber_por_pedido(pedido.id, conn=conn, for_update=True)
            if conta_rec:
                conta_rec.valor_recebido = novo_total_recebido
                if esta_totalmente_pago:
                    conta_rec._status = 'Pago'
                else:
                    conta_rec._status = 'Parcialmente Pago'
                self._financeiro_repo.atualizar_conta_receber(conta_rec, conn=conn)
            else:
                # Se não existia ainda (legado), cria a conta a receber
                nova_cr = ContaReceber(
                    pedido_id=pedido.id,
                    cliente_id=pedido.cliente_id,
                    valor_original=pedido.valor_total,
                    valor_recebido=novo_total_recebido,
                    data_vencimento=pedido.data_prevista_entrega or datetime.date.today(),
                    status='Pago' if esta_totalmente_pago else 'Parcialmente Pago',
                    forma_pagamento=pedido.forma_pagamento or "Boleto Bancário"
                )
                self._financeiro_repo.criar_conta_receber(nova_cr, conn=conn)

            obs_historico = f"Pagamento de R$ {v_recebido:.2f} confirmado ({status_pag_final})."
            if transacao_id:
                obs_historico += f" Transação: {transacao_id}."
            if comprovante:
                obs_historico += f" Comprovante: {comprovante}."

            self._pedido_repo.registrar_historico(
                pedido_id=pedido.id,
                status_anterior=pedido.status_pagamento,
                status_novo=status_pag_final,
                responsavel=responsavel,
                tipo_alteracao="Pagamento",
                observacao=obs_historico,
                conn=conn
            )

            conn.commit()
            return {
                "mensagem": f"Pagamento de R$ {v_recebido:.2f} registrado com sucesso! Status: '{status_pag_final}'.",
                "status_pagamento": status_pag_final,
                "valor_recebido": v_recebido,
                "saldo_restante": max(0.0, round(pedido.valor_total - novo_total_recebido, 2))
            }

        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def cancelar_pedido(self, pedido_id: int, motivo: str, responsavel: str = "Vendedor", usuario_perfil: str = None) -> dict:
        """
        Cancelamento de pedidos:
        - Pedidos já enviados não podem ser simplesmente cancelados (devem seguir o fluxo de Devolução).
        - Cancela o pedido, libera as reservas de estoque e gera log de auditoria.
        """
        if not motivo or not str(motivo).strip():
            raise ValueError("O motivo do cancelamento é obrigatório.")

        conn = DatabaseConnection.get_connection()
        try:
            pedido = self._pedido_repo.buscar_por_id(pedido_id)
            if not pedido:
                raise KeyError("Pedido não encontrado.")

            if pedido.status in ['Enviado', 'Em Transporte', 'Entregue']:
                raise ValueError("Pedidos já enviados não podem ser cancelados diretamente. Utilize a solicitação de Devolução.")

            if pedido.status == 'Cancelado':
                raise ValueError("Este pedido já se encontra cancelado.")

            # Libera reservas dos produtos
            for item in pedido.itens:
                prod = self._produto_repo.buscar_por_id_com_lock(item.produto_id, conn)
                if prod:
                    prod.liberar_reserva(item.quantidade)
                    self._produto_repo.atualizar_estoque_transacional(prod.id, prod.estoque, conn, novo_reservado=prod.estoque_reservado)

                    mov = MovimentacaoEstoque(
                        produto_id=prod.id,
                        tipo='Liberação',
                        quantidade=item.quantidade,
                        saldo_anterior=prod.estoque,
                        novo_saldo=prod.estoque,
                        motivo=f"Liberação de reserva por cancelamento do Pedido #{pedido.id}",
                        responsavel=responsavel
                    )
                    self._mov_repo.salvar_transacional(mov, conn)

            # 2. Atualiza a conta a receber vinculada (se existir)
            conta_rec = self._financeiro_repo.buscar_conta_receber_por_pedido(pedido.id, conn=conn, for_update=True)
            if conta_rec:
                conta_rec.cancelar()
                self._financeiro_repo.atualizar_conta_receber(conta_rec, conn=conn)

            # Atualiza status
            self._pedido_repo.atualizar_status(pedido.id, "Cancelado", conn=conn)
            self._pedido_repo.registrar_cancelamento_devolucao(
                pedido_id=pedido.id,
                tipo="Cancelamento",
                motivo=motivo,
                solicitante=responsavel,
                status_aprovacao="Aprovado",
                aprovador=responsavel,
                conn=conn
            )

            self._pedido_repo.registrar_historico(
                pedido_id=pedido.id,
                status_anterior=pedido.status,
                status_novo="Cancelado",
                responsavel=responsavel,
                tipo_alteracao="Cancelamento",
                observacao=f"Cancelado. Motivo: {motivo}",
                conn=conn
            )

            conn.commit()
            return {"mensagem": f"Pedido #{pedido.id} cancelado com sucesso e reservas liberadas no estoque!"}

        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def solicitar_devolucao(self, pedido_id: int, motivo: str, solicitante: str = "Vendedor") -> dict:
        """
        Inicia a solicitação de devolução de produtos enviados/entregues.
        Os produtos NÃO retornam ao estoque imediatamente; exigem conferência física prévia.
        """
        if not motivo or not str(motivo).strip():
            raise ValueError("O motivo da devolução é obrigatório.")

        conn = DatabaseConnection.get_connection()
        try:
            pedido = self._pedido_repo.buscar_por_id(pedido_id)
            if not pedido:
                raise KeyError("Pedido não encontrado.")

            if pedido.status not in ['Enviado', 'Em Transporte', 'Entregue']:
                raise ValueError("Devolução só pode ser solicitada para pedidos que já foram enviados ou entregues.")

            self._pedido_repo.atualizar_status(pedido.id, "Devolução Solicitada", conn=conn)
            self._pedido_repo.registrar_cancelamento_devolucao(
                pedido_id=pedido.id,
                tipo="Devolução",
                motivo=motivo,
                solicitante=solicitante,
                status_aprovacao="Pendente",
                conn=conn
            )

            self._pedido_repo.registrar_historico(
                pedido_id=pedido.id,
                status_anterior=pedido.status,
                status_novo="Devolução Solicitada",
                responsavel=solicitante,
                tipo_alteracao="Devolução",
                observacao=f"Devolução solicitada. Motivo: {motivo}",
                conn=conn
            )

            conn.commit()
            return {"mensagem": "Solicitação de devolução registrada com sucesso! Aguardando conferência física de recebimento."}

        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def conferir_e_retornar_devolucao(self, pedido_id: int, conferente: str = "Estoquista",
                                      usuario_perfil: str = None, condicao_itens: str = None,
                                      retornar_ao_estoque: bool = True, responsavel: str = None) -> dict:
        """
        Conferência física da devolução pelo Estoquista ou Gerente:
        Após a conferência física dos produtos recebidos, as mercadorias são creditadas novamente no estoque disponível.
        O parâmetro `retornar_ao_estoque` permite rejeitar o retorno (itens avariados).
        """
        nome_conferente = responsavel or conferente or "Estoquista"
        if usuario_perfil not in ['Estoque', 'Gerência', 'Administrador', None]:
            raise PermissionError("Apenas o Estoquista, Gerência e Administrador podem realizar a conferência física de devoluções.")

        conn = DatabaseConnection.get_connection()
        try:
            pedido = self._pedido_repo.buscar_por_id(pedido_id)
            if not pedido:
                raise KeyError("Pedido não encontrado.")

            if pedido.status != 'Devolução Solicitada':
                raise ValueError("A conferência física só pode ser realizada para pedidos com 'Devolução Solicitada'.")

            # Retorna produtos ao estoque físico apenas se aprovado pelo conferente
            if retornar_ao_estoque:
                for item in pedido.itens:
                    prod = self._produto_repo.buscar_por_id_com_lock(item.produto_id, conn)
                    if prod:
                        saldo_ant = prod.estoque
                        prod.creditar_estoque(item.quantidade)
                        self._produto_repo.atualizar_estoque_transacional(prod.id, prod.estoque, conn, novo_reservado=prod.estoque_reservado)

                        mov = MovimentacaoEstoque(
                            produto_id=prod.id,
                            tipo='Entrada',
                            quantidade=item.quantidade,
                            saldo_anterior=saldo_ant,
                            novo_saldo=prod.estoque,
                            motivo=f"Retorno de devolução conferida (Pedido #{pedido.id})",
                            responsavel=nome_conferente
                        )
                        self._mov_repo.salvar_transacional(mov, conn)

            self._pedido_repo.atualizar_status(pedido.id, "Devolvido", conn=conn)

            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE cancelamentos_devolucoes 
                    SET produtos_conferidos = 1, conferente = %s, data_conferencia = NOW(), status_aprovacao = 'Aprovado'
                    WHERE pedido_id = %s;
                """, (nome_conferente, pedido.id))

            obs_conf = condicao_itens or "Mercadorias inspecionadas fisicamente e reincorporadas ao estoque."
            if not retornar_ao_estoque:
                obs_conf = (condicao_itens or "Itens não reincorporados ao estoque (avariados ou descartados).")

            self._pedido_repo.registrar_historico(
                pedido_id=pedido.id,
                status_anterior="Devolução Solicitada",
                status_novo="Devolvido",
                responsavel=nome_conferente,
                tipo_alteracao="Devolução Conferida",
                observacao=obs_conf,
                conn=conn
            )

            conn.commit()
            msg = "Devolução conferida com sucesso! Produtos reincorporados ao estoque disponível." if retornar_ao_estoque else "Devolução conferida. Itens não reincorporados ao estoque."
            return {"mensagem": msg}

        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
