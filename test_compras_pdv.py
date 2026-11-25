import unittest

from models.pedido import Pedido
from models.produto import Produto


class TestComprasEPDV(unittest.TestCase):
    def test_produto_aceita_custo_medio(self):
        produto = Produto(nome="Café", preco=20, estoque=10, custo_medio=12.3456)
        self.assertEqual(produto.to_dict()["custo_medio"], 12.3456)

    def test_produto_rejeita_custo_medio_negativo(self):
        produto = Produto(nome="Café", preco=20, estoque=10)
        with self.assertRaises(ValueError):
            produto.custo_medio = -1

    def test_pedido_aceita_pagamento_em_dinheiro(self):
        pedido = Pedido(forma_pagamento="Dinheiro")
        self.assertEqual(pedido.forma_pagamento, "Dinheiro")

    def test_pedido_aceita_cartao_de_debito(self):
        pedido = Pedido(forma_pagamento="Cartão de Débito")
        self.assertEqual(pedido.forma_pagamento, "Cartão de Débito")

    def test_venda_presencial_pode_ser_concluida_direto(self):
        pedido = Pedido(status="Confirmado", forma_pagamento="PIX")
        self.assertTrue(pedido.transicao_valida("Entregue"))


if __name__ == "__main__":
    unittest.main()
