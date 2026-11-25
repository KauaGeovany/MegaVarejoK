"""
Testes específicos para validar o Módulo de Estoque:
- Consulta, pesquisa e cálculo de estoque mínimo
- Entradas, Saídas e Ajustes de inventário
- Validação contra saldo negativo
- Auditoria e histórico de movimentações
- Restrições específicas de permissão do Estoquista (sem permissão para alterar preços ou excluir)
"""

import unittest
from unittest.mock import patch, MagicMock
from app import app
from models.produto import Produto
from models.movimentacao_estoque import MovimentacaoEstoque
from services.estoque_service import EstoqueService

class TestModuloEstoque(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-estoque'
        self.client = app.test_client()

    def test_encapsulamento_produto_estoque(self):
        """Valida regras de domínio da classe Produto no contexto de Estoque."""
        prod = Produto(nome="SSD 1TB", preco=400.0, estoque=10, estoque_minimo=5, codigo="SSD-001", categoria="Armazenamento")

        self.assertEqual(prod.codigo, "SSD-001")
        self.assertEqual(prod.categoria, "Armazenamento")
        self.assertEqual(prod.status_estoque(), "Normal")

        # Entrada
        prod.creditar_estoque(15)
        self.assertEqual(prod.estoque, 25)

        # Saída
        prod.debitar_estoque(21)
        self.assertEqual(prod.estoque, 4)
        self.assertEqual(prod.status_estoque(), "Baixo")

        # Ajuste
        prod.ajustar_estoque(0)
        self.assertEqual(prod.status_estoque(), "Zerado")

        # Não permite estoque negativo em saída
        with self.assertRaises(ValueError):
            prod.debitar_estoque(1)

        # Não permite ajuste negativo
        with self.assertRaises(ValueError):
            prod.ajustar_estoque(-5)

    def test_encapsulamento_movimentacao_estoque(self):
        """Valida que MovimentacaoEstoque protege integridade e tipos."""
        mov = MovimentacaoEstoque(
            produto_id=1,
            tipo="Entrada",
            quantidade=10,
            saldo_anterior=5,
            novo_saldo=15,
            motivo="Recebimento NF 555",
            responsavel="Almoxarife"
        )
        self.assertEqual(mov.tipo, "Entrada")
        self.assertEqual(mov.novo_saldo, 15)

        # Tipo inválido
        with self.assertRaises(ValueError):
            MovimentacaoEstoque(1, "Invalido", 5, 0, 5, "Motivo", "Resp")

        # Quantidade <= 0
        with self.assertRaises(ValueError):
            MovimentacaoEstoque(1, "Entrada", 0, 0, 0, "Motivo", "Resp")

        # Motivo vazio
        with self.assertRaises(ValueError):
            MovimentacaoEstoque(1, "Entrada", 5, 0, 5, "", "Resp")

    @patch('repositories.produto_repository.ProdutoRepository.buscar_por_id_com_lock')
    @patch('repositories.produto_repository.ProdutoRepository.atualizar_estoque_transacional')
    @patch('repositories.movimentacao_repository.MovimentacaoRepository.salvar_transacional')
    @patch('database.connection.DatabaseConnection.get_connection')
    def test_service_entradas_e_saidas(self, mock_conn, mock_salvar_mov, mock_upd_est, mock_buscar_lock):
        """Valida service de registro de movimentações com persistência e atualização."""
        mock_db = MagicMock()
        mock_conn.return_value = mock_db

        prod = Produto(id=1, nome="Mouse USB", preco=50.0, estoque=20, codigo="MOU-01")
        mock_buscar_lock.return_value = prod

        service = EstoqueService()

        # Entrada de 10 unidades
        res_entrada = service.registrar_movimentacao(
            produto_id=1,
            tipo="Entrada",
            quantidade=10,
            motivo="Reposição",
            responsavel="Estoquista"
        )
        self.assertEqual(res_entrada['saldo_anterior'], 20)
        self.assertEqual(res_entrada['novo_saldo'], 30)
        mock_upd_est.assert_called_with(1, 30, mock_db)

        # Saída de 5 unidades
        res_saida = service.registrar_movimentacao(
            produto_id=1,
            tipo="Saída",
            quantidade=5,
            motivo="Envio filial",
            responsavel="Estoquista"
        )
        self.assertEqual(res_saida['saldo_anterior'], 30)
        self.assertEqual(res_saida['novo_saldo'], 25)

        # Impedir saída acima do estoque
        with self.assertRaises(ValueError):
            service.registrar_movimentacao(1, "Saída", 50, "Tentativa excesso", "Estoquista")

    @patch('repositories.produto_repository.ProdutoRepository.buscar_por_id_com_lock')
    @patch('repositories.produto_repository.ProdutoRepository.atualizar_estoque_transacional')
    @patch('repositories.movimentacao_repository.MovimentacaoRepository.salvar_transacional')
    @patch('database.connection.DatabaseConnection.get_connection')
    def test_service_ajuste_inventario(self, mock_conn, mock_salvar_mov, mock_upd_est, mock_buscar_lock):
        """Valida ajuste de contagem física com justificativa."""
        mock_db = MagicMock()
        mock_conn.return_value = mock_db

        prod = Produto(id=2, nome="Teclado", preco=150.0, estoque=15, codigo="TEC-01")
        mock_buscar_lock.return_value = prod

        service = EstoqueService()
        res_ajuste = service.registrar_ajuste(
            produto_id=2,
            novo_saldo=12,
            justificativa="Avaria em 3 caixas identificada no inventário",
            responsavel="Conferente"
        )
        self.assertEqual(res_ajuste['saldo_anterior'], 15)
        self.assertEqual(res_ajuste['novo_saldo'], 12)
        mock_upd_est.assert_called_with(2, 12, mock_db)

        # Justificativa obrigatória
        with self.assertRaises(ValueError):
            service.registrar_ajuste(2, 10, "", "Resp")

    @patch('repositories.produto_repository.ProdutoRepository.buscar_por_id')
    def test_regra_permissao_estoquista_nao_altera_preco_nem_exclui(self, mock_buscar):
        """Garante que operador com perfil Estoque não altera preço nem exclui produtos."""
        prod = Produto(id=5, nome="Monitor", preco=900.0, estoque=10)
        mock_buscar.return_value = prod

        service = EstoqueService()

        # Tentativa de alterar preço por Estoquista gera PermissionError
        with self.assertRaises(PermissionError):
            service.atualizar_produto(5, {'preco': 850.0}, usuario_perfil="Estoque")

        # Tentativa de excluir gera PermissionError
        with self.assertRaises(PermissionError):
            service.excluir_produto(5, usuario_perfil="Estoque")

    @patch('app.compras_service.garantir_estrutura')
    @patch('repositories.produto_repository.ProdutoRepository.listar_todos')
    def test_api_consulta_estoque_com_pesquisa(self, mock_listar, mock_garantir_estrutura):
        """Testa o endpoint /api/produtos recebendo parâmetro de busca."""
        mock_listar.return_value = [
            Produto(id=1, nome="Notebook Gamer", preco=4500.0, estoque=10, codigo="NOT-001", categoria="Informática")
        ]

        with self.client.session_transaction() as sess:
            sess['usuario_id'] = 2
            sess['usuario_perfil'] = 'Estoque'

        res = self.client.get('/api/produtos?busca=Gamer')
        self.assertEqual(res.status_code, 200)
        dados = res.get_json()
        self.assertEqual(len(dados), 1)
        self.assertEqual(dados[0]['codigo'], 'NOT-001')
        self.assertEqual(dados[0]['status_estoque'], 'Normal')

    @patch('services.estoque_service.EstoqueService.obter_resumo_estoque')
    def test_api_estoque_resumo_dashboard(self, mock_resumo):
        """Testa a rota /api/estoque/resumo para indicadores da tela de estoque."""
        mock_resumo.return_value = {
            "total_produtos": 4,
            "total_unidades": 89,
            "total_criticos": 1,
            "produtos_criticos": [],
            "movimentacoes_recentes": []
        }

        with self.client.session_transaction() as sess:
            sess['usuario_id'] = 2
            sess['usuario_perfil'] = 'Estoque'

        res = self.client.get('/api/estoque/resumo')
        self.assertEqual(res.status_code, 200)
        dados = res.get_json()
        self.assertEqual(dados['total_unidades'], 89)
        self.assertEqual(dados['total_criticos'], 1)

if __name__ == '__main__':
    unittest.main()
