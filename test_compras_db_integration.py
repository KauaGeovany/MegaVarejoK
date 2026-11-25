import datetime
import os
import unittest
import uuid

from database.connection import DatabaseConnection
from services.compras_service import ComprasService
from services.estoque_service import EstoqueService


@unittest.skipUnless(os.getenv("CI_MYSQL_TEST") == "1", "Requer MySQL isolado do CI")
class TestComprasBancoIntegracao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compras = ComprasService()
        cls.compras.garantir_estrutura()

    def criar_produto_e_fornecedor(self, estoque=0, custo_medio=0):
        sufixo = uuid.uuid4().hex[:10]
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO fornecedores (razao_social, categoria) VALUES (%s, 'Teste CI')",
                    (f"Fornecedor CI {sufixo}",)
                )
                fornecedor_id = cursor.lastrowid
                cursor.execute(
                    """INSERT INTO produtos (codigo,nome,categoria,preco,estoque,estoque_reservado,estoque_minimo,custo_medio)
                       VALUES (%s,%s,'Teste CI',20,%s,0,5,%s)""",
                    (f"CI-{sufixo}", f"Produto CI {sufixo}", estoque, custo_medio)
                )
                produto_id = cursor.lastrowid
            conn.commit()
            return fornecedor_id, produto_id
        finally:
            conn.close()

    def test_compra_recebimento_atualiza_estoque_custo_lote_e_conta_pagar(self):
        fornecedor_id, produto_id = self.criar_produto_e_fornecedor(estoque=10, custo_medio=5)
        ordem = self.compras.criar_compra({
            "fornecedor_id": fornecedor_id,
            "condicao_pagamento": "30 dias",
            "itens": [{"produto_id": produto_id, "quantidade": 10, "custo_unitario": 15}]
        }, "Teste CI")
        compra = self.compras.obter_compra(ordem["id"])
        item = compra["itens"][0]
        validade = (datetime.date.today() + datetime.timedelta(days=90)).isoformat()
        resultado = self.compras.receber_compra(ordem["id"], {
            "itens": [{
                "item_id": item["id"],
                "quantidade_recebida": 10,
                "lote": "LOTE-CI-001",
                "data_validade": validade
            }]
        }, "Teste CI")
        self.assertEqual(resultado["status"], "Recebida")
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT estoque,custo_medio FROM produtos WHERE id=%s", (produto_id,))
                produto = cursor.fetchone()
                self.assertEqual(int(produto["estoque"]), 20)
                self.assertAlmostEqual(float(produto["custo_medio"]), 10.0, places=3)
                cursor.execute("SELECT lote,quantidade_atual,data_validade FROM lotes_estoque WHERE compra_id=%s", (ordem["id"],))
                lote = cursor.fetchone()
                self.assertEqual(lote["lote"], "LOTE-CI-001")
                self.assertEqual(int(lote["quantidade_atual"]), 10)
                cursor.execute("SELECT valor_original,status FROM contas_pagar WHERE fornecedor_id=%s ORDER BY id DESC LIMIT 1", (fornecedor_id,))
                conta = cursor.fetchone()
                self.assertAlmostEqual(float(conta["valor_original"]), 150.0, places=2)
                self.assertEqual(conta["status"], "Pendente")
        finally:
            conn.close()

    def test_baixa_fefo_prioriza_lote_com_validade_mais_proxima(self):
        fornecedor_id, produto_id = self.criar_produto_e_fornecedor()
        conn = DatabaseConnection.get_connection()
        hoje = datetime.date.today()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO lotes_estoque (produto_id,lote,quantidade_entrada,quantidade_atual,custo_unitario,data_validade)
                       VALUES (%s,'LOTE-FEFO-1',5,5,2,%s),(%s,'LOTE-FEFO-2',5,5,2,%s)""",
                    (produto_id, hoje + datetime.timedelta(days=2), produto_id, hoje + datetime.timedelta(days=10))
                )
            conn.commit()
            EstoqueService()._baixar_lotes_por_validade(produto_id, 6, conn)
            with conn.cursor() as cursor:
                cursor.execute("SELECT lote,quantidade_atual FROM lotes_estoque WHERE produto_id=%s ORDER BY data_validade", (produto_id,))
                lotes = cursor.fetchall()
            self.assertEqual([int(x["quantidade_atual"]) for x in lotes], [0, 4])
        finally:
            conn.close()

    def test_abertura_e_fechamento_de_caixa_confere_saldo(self):
        caixa = self.compras.abrir_caixa("Operador CI", 100)
        self.assertGreater(caixa["id"], 0)
        fechamento = self.compras.fechar_caixa("Operador CI", 100)
        self.assertAlmostEqual(float(fechamento["saldo_sistema"]), 100.0, places=2)
        self.assertAlmostEqual(float(fechamento["diferenca"]), 0.0, places=2)


if __name__ == "__main__":
    unittest.main()
