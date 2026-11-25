from database.connection import DatabaseConnection
from models.produto import Produto
from models.movimentacao_estoque import MovimentacaoEstoque
from repositories.produto_repository import ProdutoRepository
from repositories.movimentacao_repository import MovimentacaoRepository

class EstoqueService:
    """
    Camada de serviço centralizada para a gestão de Estoque e Produtos.
    Aplica encapsulamento, regras de negócio de saldo, validações de perfil
    e garante que toda alteração física gere um registro de auditoria.
    """

    def __init__(self, produto_repo: ProdutoRepository = None, mov_repo: MovimentacaoRepository = None):
        self._produto_repo = produto_repo or ProdutoRepository()
        self._mov_repo = mov_repo or MovimentacaoRepository()

    def _baixar_lotes_por_validade(self, produto_id: int, quantidade: int, conn):
        """Consome primeiro os lotes com validade mais próxima (FEFO), quando houver rastreio."""
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) total FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='lotes_estoque'")
            if int(cursor.fetchone()["total"]) == 0:
                return
            cursor.execute("""
                SELECT id, quantidade_atual FROM lotes_estoque
                WHERE produto_id=%s AND quantidade_atual>0
                ORDER BY COALESCE(data_validade, '9999-12-31') ASC, recebido_em ASC, id ASC
                FOR UPDATE
            """, (produto_id,))
            restante = int(quantidade)
            for lote in cursor.fetchall():
                if restante <= 0:
                    break
                baixa = min(restante, int(lote["quantidade_atual"]))
                cursor.execute("UPDATE lotes_estoque SET quantidade_atual=quantidade_atual-%s WHERE id=%s", (baixa, lote["id"]))
                restante -= baixa

    # --- CONSULTA E CRUD DE PRODUTOS ---

    def listar_produtos(self, busca: str = None) -> list:
        produtos = self._produto_repo.listar_todos(busca=busca)
        return [p.to_dict() for p in produtos]

    def obter_produto(self, id: int) -> dict:
        produto = self._produto_repo.buscar_por_id(id)
        if not produto:
            return None
        return produto.to_dict()

    def cadastrar_produto(self, dados: dict, responsavel: str = "Sistema", usuario_perfil: str = None) -> dict:
        nome = dados.get('nome')
        preco = dados.get('preco')
        estoque = dados.get('estoque', 0)
        codigo = dados.get('codigo')
        categoria = dados.get('categoria', 'Geral')
        estoque_minimo = dados.get('estoque_minimo', 5)

        # Regra de negócio: Estoquista não pode definir ou alterar preços
        if usuario_perfil == 'Estoque':
            preco = 0.00 if preco is None else preco

        produto = Produto(
            nome=nome,
            preco=preco,
            estoque=estoque,
            codigo=codigo,
            categoria=categoria,
            estoque_minimo=estoque_minimo
        )

        novo_id = self._produto_repo.salvar(produto)
        produto._id = novo_id

        # Se houver estoque inicial informado, registra a movimentação inicial de auditoria
        if produto.estoque > 0:
            conn = DatabaseConnection.get_connection()
            try:
                mov = MovimentacaoEstoque(
                    produto_id=novo_id,
                    tipo='Entrada',
                    quantidade=produto.estoque,
                    saldo_anterior=0,
                    novo_saldo=produto.estoque,
                    motivo="Estoque inicial de cadastro",
                    responsavel=responsavel
                )
                self._mov_repo.salvar_transacional(mov, conn)
                conn.commit()
            except Exception:
                conn.rollback()
            finally:
                conn.close()

        return {"mensagem": "Produto cadastrado com sucesso no estoque!", "id": novo_id}

    def atualizar_produto(self, id: int, dados: dict, usuario_perfil: str = None) -> dict:
        produto_atual = self._produto_repo.buscar_por_id(id)
        if not produto_atual:
            raise KeyError("Produto não encontrado.")

        # Regra de negócio: Estoquista não pode alterar preços de produtos
        if usuario_perfil == 'Estoque' and 'preco' in dados:
            novo_preco = float(dados['preco'])
            if round(novo_preco, 2) != round(produto_atual.preco, 2):
                raise PermissionError("Operadores de estoque não têm permissão para alterar preços de produtos.")

        nome = dados.get('nome', produto_atual.nome)
        preco = dados.get('preco', produto_atual.preco)
        codigo = dados.get('codigo', produto_atual.codigo)
        categoria = dados.get('categoria', produto_atual.categoria)
        estoque_minimo = dados.get('estoque_minimo', produto_atual.estoque_minimo)
        # O estoque físico deve ser alterado pelas operações de entrada, saída ou ajuste
        estoque = produto_atual.estoque

        produto_atualizado = Produto(
            id=id,
            nome=nome,
            preco=preco,
            estoque=estoque,
            codigo=codigo,
            categoria=categoria,
            estoque_minimo=estoque_minimo
        )

        atualizado = self._produto_repo.atualizar(produto_atualizado)
        if not atualizado:
            raise KeyError("Produto não encontrado.")

        return {"mensagem": "Produto atualizado com sucesso!"}

    def excluir_produto(self, id: int, usuario_perfil: str = None) -> dict:
        if usuario_perfil == 'Estoque':
            raise PermissionError("Operadores de estoque não têm permissão para excluir produtos.")

        excluido = self._produto_repo.excluir(id)
        if not excluido:
            raise KeyError("Produto não encontrado.")
        return {"mensagem": "Produto excluído com sucesso!"}

    # --- ENTRADAS, SAÍDAS E AJUSTES DE ESTOQUE (TRANSAÇÕES SEGURAS) ---

    def registrar_movimentacao(self, produto_id: int, tipo: str, quantidade: int, motivo: str, responsavel: str) -> dict:
        """
        Registra uma movimentação de Entrada ou Saída com atualização do saldo e histórico.
        Garante que não ocorra estoque negativo.
        """
        tipo_normalizado = str(tipo).strip().capitalize()
        if tipo_normalizado not in ['Entrada', 'Saída']:
            raise ValueError("O tipo de movimentação deve ser 'Entrada' ou 'Saída'.")

        try:
            qtd = int(quantidade)
            if qtd <= 0:
                raise ValueError("A quantidade movimentada deve ser maior que zero.")
        except (TypeError, ValueError):
            raise ValueError("Quantidade inválida informada.")

        if not motivo or not str(motivo).strip():
            raise ValueError("O motivo da movimentação é obrigatório.")

        conn = DatabaseConnection.get_connection()
        try:
            produto = self._produto_repo.buscar_por_id_com_lock(int(produto_id), conn)
            if not produto:
                raise KeyError("Produto não encontrado.")

            saldo_anterior = produto.estoque

            if tipo_normalizado == 'Entrada':
                produto.creditar_estoque(qtd)
            elif tipo_normalizado == 'Saída':
                if not produto.possui_estoque(qtd):
                    raise ValueError(f"Saldo insuficiente! Disponível: {saldo_anterior}, Tentativa de saída: {qtd}.")
                produto.debitar_estoque(qtd)

            novo_saldo = produto.estoque

            # Atualiza produto no banco
            self._produto_repo.atualizar_estoque_transacional(produto.id, novo_saldo, conn)
            if tipo_normalizado == 'Saída':
                self._baixar_lotes_por_validade(produto.id, qtd, conn)

            # Grava movimentação de auditoria
            mov = MovimentacaoEstoque(
                produto_id=produto.id,
                tipo=tipo_normalizado,
                quantidade=qtd,
                saldo_anterior=saldo_anterior,
                novo_saldo=novo_saldo,
                motivo=motivo,
                responsavel=responsavel
            )
            mov_id = self._mov_repo.salvar_transacional(mov, conn)

            conn.commit()

            return {
                "mensagem": f"{tipo_normalizado} de estoque realizada com sucesso!",
                "movimentacao_id": mov_id,
                "produto_id": produto.id,
                "saldo_anterior": saldo_anterior,
                "novo_saldo": novo_saldo
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def registrar_ajuste(self, produto_id: int, novo_saldo: int, justificativa: str, responsavel: str) -> dict:
        """
        Permite corrigir a contagem física do estoque exigindo justificativa e registrando auditoria.
        """
        try:
            novo_saldo_int = int(novo_saldo)
            if novo_saldo_int < 0:
                raise ValueError("O saldo ajustado não pode ser negativo.")
        except (TypeError, ValueError):
            raise ValueError("Saldo ajustado inválido.")

        if not justificativa or not str(justificativa).strip():
            raise ValueError("A justificativa para o ajuste de estoque é obrigatória.")

        conn = DatabaseConnection.get_connection()
        try:
            produto = self._produto_repo.buscar_por_id_com_lock(int(produto_id), conn)
            if not produto:
                raise KeyError("Produto não encontrado.")

            saldo_anterior = produto.estoque
            diferenca = abs(novo_saldo_int - saldo_anterior)

            # Aplica ajuste no objeto de domínio
            produto.ajustar_estoque(novo_saldo_int)

            # Atualiza no banco
            self._produto_repo.atualizar_estoque_transacional(produto.id, novo_saldo_int, conn)
            if novo_saldo_int < saldo_anterior:
                self._baixar_lotes_por_validade(produto.id, saldo_anterior - novo_saldo_int, conn)

            # Grava movimentação de auditoria tipo 'Ajuste'
            mov = MovimentacaoEstoque(
                produto_id=produto.id,
                tipo='Ajuste',
                quantidade=diferenca,
                saldo_anterior=saldo_anterior,
                novo_saldo=novo_saldo_int,
                motivo=f"Ajuste de inventário: {justificativa.strip()}",
                responsavel=responsavel
            )
            mov_id = self._mov_repo.salvar_transacional(mov, conn)

            conn.commit()

            return {
                "mensagem": "Ajuste de estoque registrado com sucesso!",
                "movimentacao_id": mov_id,
                "produto_id": produto.id,
                "saldo_anterior": saldo_anterior,
                "novo_saldo": novo_saldo_int
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # --- HISTÓRICO E RELATÓRIOS DE AUDITORIA ---

    def listar_historico(self, limite: int = 100, produto_id: int = None, tipo: str = None) -> list:
        movs = self._mov_repo.listar_todos(limite=limite, produto_id=produto_id, tipo=tipo)
        return [m.to_dict() for m in movs]

    def obter_relatorio_estoque_baixo(self) -> list:
        produtos = self._produto_repo.listar_produtos_criticos()
        return [p.to_dict() for p in produtos]

    def obter_relatorio_mais_movimentados(self, limite: int = 5) -> list:
        return self._mov_repo.relatorio_produtos_mais_movimentados(limite=limite)

    def obter_resumo_estoque(self) -> dict:
        """Retorna indicadores consolidados para o dashboard do módulo de Estoque."""
        total_produtos = self._produto_repo.contar_total()
        total_unidades = self._produto_repo.somar_unidades_estoque()
        produtos_criticos = self._produto_repo.listar_produtos_criticos()
        movimentacoes_recentes = self._mov_repo.listar_todos(limite=5)

        return {
            "total_produtos": total_produtos,
            "total_unidades": total_unidades,
            "total_criticos": len(produtos_criticos),
            "produtos_criticos": [p.to_dict() for p in produtos_criticos],
            "movimentacoes_recentes": [m.to_dict() for m in movimentacoes_recentes]
        }
