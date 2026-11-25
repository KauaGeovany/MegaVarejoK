from decimal import Decimal, InvalidOperation
import uuid
import datetime
from database.connection import DatabaseConnection


class ComprasService:
    """Compras, recebimento físico, fornecedores e integração com estoque/financeiro."""

    def garantir_estrutura(self):
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS compras (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        fornecedor_id INT NOT NULL,
                        numero_compra VARCHAR(30) NOT NULL UNIQUE,
                        status VARCHAR(30) NOT NULL DEFAULT 'Aberta',
                        data_compra DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        data_prevista DATE DEFAULT NULL,
                        data_recebimento DATETIME DEFAULT NULL,
                        condicao_pagamento VARCHAR(100) DEFAULT 'A prazo',
                        observacoes TEXT DEFAULT NULL,
                        valor_total DECIMAL(12,2) NOT NULL DEFAULT 0,
                        valor_recebido DECIMAL(12,2) NOT NULL DEFAULT 0,
                        responsavel VARCHAR(100) NOT NULL,
                        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT fk_compras_fornecedor FOREIGN KEY (fornecedor_id) REFERENCES fornecedores(id) ON DELETE RESTRICT
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS itens_compra (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        compra_id INT NOT NULL,
                        produto_id INT NOT NULL,
                        quantidade INT NOT NULL,
                        quantidade_recebida INT NOT NULL DEFAULT 0,
                        custo_unitario DECIMAL(12,4) NOT NULL,
                        CONSTRAINT fk_item_compra FOREIGN KEY (compra_id) REFERENCES compras(id) ON DELETE CASCADE,
                        CONSTRAINT fk_item_compra_produto FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE RESTRICT
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS lotes_estoque (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        produto_id INT NOT NULL,
                        compra_id INT DEFAULT NULL,
                        lote VARCHAR(80) DEFAULT NULL,
                        quantidade_entrada INT NOT NULL,
                        quantidade_atual INT NOT NULL,
                        custo_unitario DECIMAL(12,4) NOT NULL DEFAULT 0,
                        data_validade DATE DEFAULT NULL,
                        recebido_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT fk_lote_produto FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE RESTRICT,
                        CONSTRAINT fk_lote_compra FOREIGN KEY (compra_id) REFERENCES compras(id) ON DELETE SET NULL
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS caixas (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        usuario_abertura VARCHAR(100) NOT NULL,
                        aberto_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        saldo_inicial DECIMAL(12,2) NOT NULL DEFAULT 0,
                        fechado_em DATETIME DEFAULT NULL,
                        saldo_informado DECIMAL(12,2) DEFAULT NULL,
                        saldo_sistema DECIMAL(12,2) DEFAULT NULL,
                        diferenca DECIMAL(12,2) DEFAULT NULL,
                        status VARCHAR(20) NOT NULL DEFAULT 'Aberto'
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vendas_pdv (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        pedido_id INT NOT NULL UNIQUE,
                        caixa_id INT DEFAULT NULL,
                        operador VARCHAR(100) NOT NULL,
                        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT fk_pdv_pedido FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE RESTRICT,
                        CONSTRAINT fk_pdv_caixa FOREIGN KEY (caixa_id) REFERENCES caixas(id) ON DELETE SET NULL
                    )
                """)
                cursor.execute("""
                    SELECT COUNT(*) total FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'produtos' AND COLUMN_NAME = 'custo_medio'
                """)
                if not cursor.fetchone()["total"]:
                    cursor.execute("ALTER TABLE produtos ADD COLUMN custo_medio DECIMAL(12,4) NOT NULL DEFAULT 0")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def listar_compras(self, status=None):
        self.garantir_estrutura()
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT c.*, f.razao_social fornecedor_nome,
                           (SELECT COUNT(*) FROM itens_compra i WHERE i.compra_id=c.id) total_itens
                    FROM compras c JOIN fornecedores f ON f.id=c.fornecedor_id
                """
                params = []
                if status:
                    sql += " WHERE c.status=%s"
                    params.append(status)
                sql += " ORDER BY c.id DESC LIMIT 200"
                cursor.execute(sql, params)
                return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def obter_compra(self, compra_id):
        self.garantir_estrutura()
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT c.*, f.razao_social fornecedor_nome FROM compras c JOIN fornecedores f ON f.id=c.fornecedor_id WHERE c.id=%s", (compra_id,))
                compra = cursor.fetchone()
                if not compra:
                    return None
                cursor.execute("""
                    SELECT i.*, p.nome produto_nome, p.codigo
                    FROM itens_compra i JOIN produtos p ON p.id=i.produto_id
                    WHERE i.compra_id=%s ORDER BY i.id
                """, (compra_id,))
                compra = dict(compra)
                compra["itens"] = [dict(r) for r in cursor.fetchall()]
                return compra
        finally:
            conn.close()

    def criar_compra(self, dados, responsavel):
        self.garantir_estrutura()
        fornecedor_id = int(dados.get("fornecedor_id") or 0)
        itens = dados.get("itens") or []
        if not fornecedor_id or not itens:
            raise ValueError("Informe o fornecedor e pelo menos um produto.")
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM fornecedores WHERE id=%s", (fornecedor_id,))
                if not cursor.fetchone():
                    raise KeyError("Fornecedor não encontrado.")
                linhas = []
                total = Decimal("0")
                for item in itens:
                    produto_id = int(item.get("produto_id") or 0)
                    qtd = int(item.get("quantidade") or 0)
                    custo = Decimal(str(item.get("custo_unitario") or "0"))
                    if not produto_id or qtd <= 0 or custo <= 0:
                        raise ValueError("Cada item precisa ter produto, quantidade e custo unitário positivo.")
                    cursor.execute("SELECT id FROM produtos WHERE id=%s", (produto_id,))
                    if not cursor.fetchone():
                        raise KeyError(f"Produto {produto_id} não encontrado.")
                    linhas.append((produto_id, qtd, custo))
                    total += custo * qtd
                cursor.execute("""
                    INSERT INTO compras (fornecedor_id, numero_compra, data_prevista, condicao_pagamento,
                        observacoes, valor_total, responsavel)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (fornecedor_id, f"TMP-{uuid.uuid4().hex[:12]}", dados.get("data_prevista") or None,
                      dados.get("condicao_pagamento") or "A prazo",
                      dados.get("observacoes") or "", total, responsavel))
                compra_id = cursor.lastrowid
                numero = f"COMP-{compra_id:05d}"
                cursor.execute("UPDATE compras SET numero_compra=%s WHERE id=%s", (numero, compra_id))
                for produto_id, qtd, custo in linhas:
                    cursor.execute("INSERT INTO itens_compra (compra_id, produto_id, quantidade, custo_unitario) VALUES (%s,%s,%s,%s)",
                                   (compra_id, produto_id, qtd, custo))
            conn.commit()
            return {"id": compra_id, "numero_compra": numero, "mensagem": f"Ordem {numero} criada."}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def receber_compra(self, compra_id, dados, responsavel):
        self.garantir_estrutura()
        recebimentos = dados.get("itens") or []
        if not recebimentos:
            raise ValueError("Informe os itens e as quantidades recebidas.")
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM compras WHERE id=%s FOR UPDATE", (compra_id,))
                compra = cursor.fetchone()
                if not compra:
                    raise KeyError("Ordem de compra não encontrada.")
                if compra["status"] == "Cancelada":
                    raise ValueError("Não é possível receber uma compra cancelada.")
                valor_recebido = Decimal("0")
                recebidos_total = 0
                for item in recebimentos:
                    item_id = int(item.get("item_id") or 0)
                    qtd = int(item.get("quantidade_recebida") or 0)
                    if qtd <= 0:
                        raise ValueError("A quantidade recebida deve ser maior que zero.")
                    cursor.execute("SELECT * FROM itens_compra WHERE id=%s AND compra_id=%s FOR UPDATE", (item_id, compra_id))
                    linha = cursor.fetchone()
                    if not linha:
                        raise KeyError("Item da ordem de compra não encontrado.")
                    restante = int(linha["quantidade"]) - int(linha["quantidade_recebida"])
                    if qtd > restante:
                        raise ValueError("A quantidade recebida não pode superar o saldo pendente do item.")
                    produto_id = int(linha["produto_id"])
                    custo = Decimal(str(item.get("custo_unitario") or linha["custo_unitario"]))
                    if custo <= 0:
                        raise ValueError("Custo unitário inválido.")
                    cursor.execute("SELECT estoque, COALESCE(custo_medio,0) custo_medio FROM produtos WHERE id=%s FOR UPDATE", (produto_id,))
                    produto = cursor.fetchone()
                    saldo = int(produto["estoque"])
                    custo_medio = Decimal(str(produto["custo_medio"] or 0))
                    novo_custo = ((Decimal(saldo) * custo_medio) + (Decimal(qtd) * custo)) / Decimal(saldo + qtd) if saldo + qtd else custo
                    novo_saldo = saldo + qtd
                    cursor.execute("UPDATE produtos SET estoque=%s, custo_medio=%s WHERE id=%s", (novo_saldo, novo_custo, produto_id))
                    cursor.execute("""
                        INSERT INTO movimentacoes_estoque (produto_id,tipo,quantidade,saldo_anterior,novo_saldo,motivo,responsavel)
                        VALUES (%s,'Entrada',%s,%s,%s,%s,%s)
                    """, (produto_id, qtd, saldo, novo_saldo, f"Recebimento da ordem {compra['numero_compra']}", responsavel))
                    cursor.execute("""
                        INSERT INTO lotes_estoque (produto_id,compra_id,lote,quantidade_entrada,quantidade_atual,custo_unitario,data_validade)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """, (produto_id, compra_id, item.get("lote") or None, qtd, qtd, custo, item.get("data_validade") or None))
                    cursor.execute("UPDATE itens_compra SET quantidade_recebida=quantidade_recebida+%s WHERE id=%s", (qtd, item_id))
                    valor_recebido += custo * qtd
                cursor.execute("SELECT COALESCE(SUM(quantidade_recebida),0) recebido, COALESCE(SUM(quantidade),0) total FROM itens_compra WHERE compra_id=%s", (compra_id,))
                totais = cursor.fetchone()
                status = "Recebida" if int(totais["recebido"]) == int(totais["total"]) else "Recebimento parcial"
                cursor.execute("UPDATE compras SET status=%s, valor_recebido=valor_recebido+%s, data_recebimento=NOW() WHERE id=%s",
                               (status, valor_recebido, compra_id))
                # Cada recebimento gera obrigação financeira pelo valor efetivamente recebido.
                vencimento = dados.get("data_vencimento") or (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
                if vencimento:
                    cursor.execute("""
                        INSERT INTO contas_pagar (descricao,fornecedor_id,categoria,valor_original,valor_pago,data_vencimento,status,responsavel,observacoes)
                        VALUES (%s,%s,'Compra de mercadorias',%s,0,%s,'Pendente',%s,%s)
                    """, (f"Recebimento {compra['numero_compra']}", compra["fornecedor_id"], valor_recebido,
                          vencimento, responsavel, "Gerado automaticamente pelo recebimento de compra"))
            conn.commit()
            return {"mensagem": "Recebimento registrado e estoque atualizado.", "valor_recebido": float(valor_recebido), "status": status}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def obter_reposicao(self):
        self.garantir_estrutura()
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id,codigo,nome,categoria,estoque,estoque_reservado,estoque_minimo,
                           GREATEST(estoque_minimo*2-(estoque-estoque_reservado),1) quantidade_sugerida
                    FROM produtos
                    WHERE (estoque-estoque_reservado)<=estoque_minimo
                    ORDER BY (estoque-estoque_reservado) ASC, nome
                """)
                return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def listar_lotes(self, dias=30):
        self.garantir_estrutura()
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT l.*, p.nome produto_nome, p.codigo,
                           DATEDIFF(l.data_validade,CURDATE()) dias_para_vencer
                    FROM lotes_estoque l JOIN produtos p ON p.id=l.produto_id
                    WHERE l.quantidade_atual>0 AND l.data_validade IS NOT NULL
                      AND l.data_validade<=DATE_ADD(CURDATE(), INTERVAL %s DAY)
                    ORDER BY l.data_validade ASC
                """, (int(dias),))
                return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()


    def obter_caixa_aberto(self, operador=None):
        self.garantir_estrutura()
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM caixas WHERE status='Aberto' ORDER BY id DESC LIMIT 1")
                row = cursor.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def abrir_caixa(self, operador, saldo_inicial):
        self.garantir_estrutura()
        saldo = Decimal(str(saldo_inicial or 0))
        if saldo < 0:
            raise ValueError("O saldo inicial não pode ser negativo.")
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM caixas WHERE status='Aberto' FOR UPDATE")
                if cursor.fetchone():
                    raise ValueError("Já existe um caixa aberto.")
                cursor.execute("INSERT INTO caixas (usuario_abertura,saldo_inicial,status) VALUES (%s,%s,'Aberto')", (operador, saldo))
                caixa_id = cursor.lastrowid
            conn.commit()
            return {"id": caixa_id, "mensagem": "Caixa aberto com sucesso."}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def fechar_caixa(self, operador, saldo_informado):
        self.garantir_estrutura()
        saldo = Decimal(str(saldo_informado or 0))
        if saldo < 0:
            raise ValueError("O valor contado não pode ser negativo.")
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM caixas WHERE status='Aberto' ORDER BY id DESC LIMIT 1 FOR UPDATE")
                caixa = cursor.fetchone()
                if not caixa:
                    raise ValueError("Não existe caixa aberto.")
                cursor.execute("""
                    SELECT COALESCE(SUM(CASE WHEN tipo='Entrada' THEN valor ELSE -valor END),0) movimento
                    FROM transacoes_caixa
                    WHERE data_transacao >= %s AND forma_pagamento='Dinheiro'
                """, (caixa["aberto_em"],))
                movimento = Decimal(str(cursor.fetchone()["movimento"] or 0))
                saldo_sistema = Decimal(str(caixa["saldo_inicial"] or 0)) + movimento
                diferenca = saldo - saldo_sistema
                cursor.execute("UPDATE caixas SET fechado_em=NOW(),saldo_informado=%s,saldo_sistema=%s,diferenca=%s,status='Fechado' WHERE id=%s",
                               (saldo, saldo_sistema, diferenca, caixa["id"]))
            conn.commit()
            return {"mensagem": "Caixa fechado e conferido.", "saldo_sistema": float(saldo_sistema), "diferenca": float(diferenca)}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def vincular_venda_pdv(self, pedido_id, caixa_id, operador):
        self.garantir_estrutura()
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO vendas_pdv (pedido_id,caixa_id,operador) VALUES (%s,%s,%s)", (pedido_id, caixa_id, operador))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
