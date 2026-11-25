import unittest
from unittest.mock import patch

from app import app


class TestRotasComprasEPDV(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def autenticar(self, perfil="Administrador"):
        with self.client.session_transaction() as sess:
            sess["usuario_id"] = 10
            sess["usuario_nome"] = "Operador de Teste"
            sess["usuario_perfil"] = perfil

    @patch("app.compras_service.criar_compra")
    def test_criar_ordem_compra_requer_perfil_autorizado(self, mock_criar):
        self.autenticar("Administrador")
        mock_criar.return_value = {"id": 7, "numero_compra": "COMP-00007"}
        resposta = self.client.post("/api/compras", json={
            "fornecedor_id": 2,
            "itens": [{"produto_id": 3, "quantidade": 5, "custo_unitario": 10}]
        })
        self.assertEqual(resposta.status_code, 201)
        mock_criar.assert_called_once()

    @patch("app.compras_service.criar_compra")
    def test_vendedor_nao_pode_criar_ordem_compra(self, mock_criar):
        self.autenticar("Vendas")
        resposta = self.client.post("/api/compras", json={"fornecedor_id": 2, "itens": []})
        self.assertEqual(resposta.status_code, 403)
        mock_criar.assert_not_called()

    @patch("app.compras_service.obter_caixa_aberto")
    @patch("app.pedido_service.criar_pedido")
    @patch("app.pedido_service.confirmar_pagamento")
    @patch("app.pedido_service.atualizar_status")
    @patch("app.compras_service.vincular_venda_pdv")
    def test_pdv_conclui_venda_presencial_sem_etapas_logisticas(
        self, mock_vincular, mock_status, mock_pagamento, mock_criar, mock_caixa
    ):
        self.autenticar("Vendas")
        mock_caixa.return_value = {"id": 4, "aberto_em": "2026-11-25 10:00:00"}
        mock_criar.return_value = {
            "pedido_id": 21,
            "numero_pedido": "PED-0021",
            "valor_total": 50.0
        }
        resposta = self.client.post("/api/pdv/vendas", json={
            "forma_pagamento": "Dinheiro",
            "itens": [{"produto_id": 3, "quantidade": 2}]
        })
        self.assertEqual(resposta.status_code, 201)
        mock_pagamento.assert_called_once()
        mock_status.assert_called_once()
        self.assertEqual(mock_status.call_args.args[1], "Entregue")
        mock_vincular.assert_called_once_with(21, 4, "Operador de Teste")

    @patch("app.compras_service.obter_caixa_aberto")
    @patch("app.pedido_service.criar_pedido")
    def test_pdv_bloqueia_venda_sem_caixa_aberto(self, mock_criar, mock_caixa):
        self.autenticar("Vendas")
        mock_caixa.return_value = None
        resposta = self.client.post("/api/pdv/vendas", json={
            "forma_pagamento": "PIX",
            "itens": [{"produto_id": 3, "quantidade": 1}]
        })
        self.assertEqual(resposta.status_code, 400)
        mock_criar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
