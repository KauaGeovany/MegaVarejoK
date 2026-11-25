from datetime import date
from decimal import Decimal, InvalidOperation
from database.connection import DatabaseConnection


class LogisticaService:
    """Regras de negócio de transportadoras, cotação de frete e controle manual de entregas."""

    def garantir_estrutura(self):
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS transportadoras (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        nome VARCHAR(150) NOT NULL,
                        documento VARCHAR(30) DEFAULT NULL,
                        modelo_frete VARCHAR(30) NOT NULL DEFAULT 'PESO',
                        taxa_fixa DECIMAL(10,2) NOT NULL DEFAULT 0,
                        valor_por_kg DECIMAL(10,2) NOT NULL DEFAULT 0,
                        percentual DECIMAL(7,3) NOT NULL DEFAULT 0,
                        frete_minimo DECIMAL(10,2) NOT NULL DEFAULT 0,
                        prazo_dias INT NOT NULL DEFAULT 5,
                        ativo TINYINT(1) NOT NULL DEFAULT 1,
                        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS entregas (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        pedido_id INT NOT NULL UNIQUE,
                        transportadora_id INT DEFAULT NULL,
                        peso_kg DECIMAL(10,3) NOT NULL DEFAULT 0,
                        valor_frete DECIMAL(10,2) NOT NULL DEFAULT 0,
                        codigo_rastreamento VARCHAR(100) DEFAULT NULL,
                        data_prevista DATE DEFAULT NULL,
                        data_envio DATETIME DEFAULT NULL,
                        data_entrega DATETIME DEFAULT NULL,
                        observacoes TEXT DEFAULT NULL,
                        responsavel VARCHAR(100) NOT NULL,
                        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                        atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        CONSTRAINT fk_entrega_pedido FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE,
                        CONSTRAINT fk_entrega_transportadora FOREIGN KEY (transportadora_id) REFERENCES transportadoras(id) ON DELETE SET NULL
                    )
                """)
                cursor.execute("SELECT COUNT(*) AS total FROM transportadoras")
                if int(cursor.fetchone()["total"]) == 0:
                    cursor.executemany("""
                        INSERT INTO transportadoras
                        (nome, modelo_frete, taxa_fixa, valor_por_kg, percentual, frete_minimo, prazo_dias, ativo)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
                    """, [
                        ("Entrega Econômica", "PESO", 12.00, 2.50, 0, 15.00, 6),
                        ("Entrega Expressa", "PERCENTUAL", 18.00, 0, 4.0, 18.00, 2),
                        ("Transportadora Regional", "FIXO", 22.00, 0, 0, 22.00, 3)
                    ])
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def listar_transportadoras(self, incluir_inativas=False):
        self.garantir_estrutura()
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                sql = """SELECT id, nome, documento, modelo_frete, taxa_fixa, valor_por_kg,
                         percentual, frete_minimo, prazo_dias, ativo
                         FROM transportadoras"""
                if not incluir_inativas:
                    sql += " WHERE ativo = 1"
                sql += " ORDER BY nome"
                cursor.execute(sql)
                resultado = []
                for row in cursor.fetchall():
                    item = dict(row)
                    for campo in ("taxa_fixa", "valor_por_kg", "percentual", "frete_minimo"):
                        item[campo] = float(item.get(campo) or 0)
                    item["prazo_dias"] = int(item.get("prazo_dias") or 0)
                    item["ativo"] = int(item.get("ativo") or 0)
                    resultado.append(item)
                return resultado
        finally:
            conn.close()

    def salvar_transportadora(self, dados, transportadora_id=None):
        self.garantir_estrutura()
        nome = str(dados.get("nome") or "").strip()
        modelo = str(dados.get("modelo_frete") or "PESO").upper()
        if not nome:
            raise ValueError("Informe o nome da transportadora.")
        if modelo not in ("PESO", "PERCENTUAL", "FIXO"):
            raise ValueError("Modelo de frete inválido.")
        try:
            taxa = Decimal(str(dados.get("taxa_fixa") or 0))
            por_kg = Decimal(str(dados.get("valor_por_kg") or 0))
            percentual = Decimal(str(dados.get("percentual") or 0))
            minimo = Decimal(str(dados.get("frete_minimo") or 0))
            prazo = int(dados.get("prazo_dias") or 1)
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("Os valores da regra de frete são inválidos.")
        if min(taxa, por_kg, percentual, minimo) < 0 or prazo < 1 or percentual > 100:
            raise ValueError("Valores de frete devem ser positivos e o prazo deve ser de pelo menos 1 dia.")
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                valores = (nome, dados.get("documento") or None, modelo, taxa, por_kg, percentual, minimo, prazo)
                if transportadora_id:
                    cursor.execute("""UPDATE transportadoras SET nome=%s, documento=%s, modelo_frete=%s,
                        taxa_fixa=%s, valor_por_kg=%s, percentual=%s, frete_minimo=%s, prazo_dias=%s
                        WHERE id=%s""", valores + (transportadora_id,))
                    if cursor.rowcount == 0:
                        raise KeyError("Transportadora não encontrada.")
                    resultado_id = transportadora_id
                else:
                    cursor.execute("""INSERT INTO transportadoras
                        (nome, documento, modelo_frete, taxa_fixa, valor_por_kg, percentual, frete_minimo, prazo_dias)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""", valores)
                    resultado_id = cursor.lastrowid
            conn.commit()
            return {"mensagem": "Transportadora salva com sucesso.", "id": resultado_id}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def alterar_ativo_transportadora(self, transportadora_id, ativo):
        self.garantir_estrutura()
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE transportadoras SET ativo=%s WHERE id=%s", (1 if ativo else 0, transportadora_id))
                if cursor.rowcount == 0:
                    cursor.execute("SELECT id FROM transportadoras WHERE id=%s", (transportadora_id,))
                    if not cursor.fetchone():
                        raise KeyError("Transportadora não encontrada.")
            conn.commit()
            return {"mensagem": "Situação da transportadora atualizada."}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def calcular_frete(self, transportadora_id, subtotal, peso_kg=0):
        transportadoras = self.listar_transportadoras()
        t = next((x for x in transportadoras if int(x["id"]) == int(transportadora_id)), None)
        if not t:
            raise KeyError("Transportadora não encontrada ou inativa.")
        try:
            base = Decimal(str(subtotal or 0))
            peso = Decimal(str(peso_kg or 0))
        except InvalidOperation:
            raise ValueError("Subtotal ou peso inválido.")
        if base < 0 or peso < 0:
            raise ValueError("Subtotal e peso não podem ser negativos.")
        frete = Decimal(str(t["taxa_fixa"] or 0))
        if t["modelo_frete"] == "PESO":
            frete += peso * Decimal(str(t["valor_por_kg"] or 0))
        elif t["modelo_frete"] == "PERCENTUAL":
            frete += base * Decimal(str(t["percentual"] or 0)) / Decimal("100")
        frete = max(frete, Decimal(str(t["frete_minimo"] or 0)))
        return {
            "transportadora_id": int(t["id"]),
            "transportadora": t["nome"],
            "frete": float(frete.quantize(Decimal("0.01"))),
            "prazo_dias": int(t["prazo_dias"]),
            "data_prevista": (date.today().fromordinal(date.today().toordinal() + int(t["prazo_dias"]))).isoformat()
        }

    def registrar_entrega(self, pedido_id, dados, responsavel):
        self.garantir_estrutura()
        transportadora_id = dados.get("transportadora_id") or None
        peso = Decimal(str(dados.get("peso_kg") or 0))
        frete = Decimal(str(dados.get("valor_frete") or 0))
        if peso < 0 or frete < 0:
            raise ValueError("Peso e frete não podem ser negativos.")
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, status, data_prevista_entrega FROM pedidos WHERE id=%s", (pedido_id,))
                pedido = cursor.fetchone()
                if not pedido:
                    raise KeyError("Pedido não encontrado.")
                if pedido["status"] in ("Cancelado", "Devolvido", "Recusado", "Devolução Solicitada"):
                    raise ValueError("Não é possível organizar a entrega de um pedido cancelado ou em devolução.")
                cursor.execute("SELECT id FROM entregas WHERE pedido_id=%s", (pedido_id,))
                existente = cursor.fetchone()
                valores = (transportadora_id, peso, frete, dados.get("codigo_rastreamento") or None,
                           dados.get("data_prevista") or pedido.get("data_prevista_entrega"),
                           dados.get("observacoes") or None, responsavel)
                if existente:
                    cursor.execute("""UPDATE entregas SET transportadora_id=%s, peso_kg=%s, valor_frete=%s,
                        codigo_rastreamento=%s, data_prevista=%s, observacoes=%s, responsavel=%s
                        WHERE pedido_id=%s""", valores + (pedido_id,))
                else:
                    cursor.execute("""INSERT INTO entregas
                        (pedido_id, transportadora_id, peso_kg, valor_frete, codigo_rastreamento,
                         data_prevista, observacoes, responsavel)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (pedido_id,) + valores)
            with conn.cursor() as cursor:
                if dados.get("data_prevista"):
                    cursor.execute("UPDATE pedidos SET data_prevista_entrega=%s WHERE id=%s", (dados.get("data_prevista"), pedido_id))
            conn.commit()
            return {"mensagem": "Dados logísticos salvos com sucesso."}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def atualizar_evento_entrega(self, pedido_id, novo_status, responsavel, observacoes=None):
        self.garantir_estrutura()
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, status FROM pedidos WHERE id=%s", (pedido_id,))
                pedido = cursor.fetchone()
                if not pedido:
                    raise KeyError("Pedido não encontrado.")
                cursor.execute("SELECT id FROM entregas WHERE pedido_id=%s", (pedido_id,))
                entrega = cursor.fetchone()
                if not entrega:
                    raise ValueError("Cadastre a transportadora e os dados da entrega antes de avançar o transporte.")
                cursor.execute("""UPDATE entregas SET
                    data_envio = CASE WHEN %s='Enviado' AND data_envio IS NULL THEN NOW() ELSE data_envio END,
                    data_entrega = CASE WHEN %s='Entregue' THEN NOW() ELSE data_entrega END,
                    observacoes = CASE WHEN %s IS NOT NULL AND %s <> '' THEN %s ELSE observacoes END,
                    responsavel=%s
                    WHERE pedido_id=%s""",
                    (novo_status, novo_status, observacoes, observacoes, observacoes, responsavel, pedido_id))
            conn.commit()
            return {"mensagem": "Etapa logística registrada."}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def listar_entregas(self):
        self.garantir_estrutura()
        conn = DatabaseConnection.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT p.id AS pedido_id, COALESCE(p.numero_pedido, CONCAT('PED-', LPAD(p.id,4,'0'))) AS numero_pedido,
                           COALESCE(c.nome, 'Cliente não informado') AS cliente, p.status AS status_pedido,
                           p.status_pagamento, p.data_pedido, p.data_prevista_entrega,
                           p.endereco_entrega, p.valor_total,
                           e.id AS entrega_id, e.peso_kg, e.valor_frete, e.codigo_rastreamento,
                           e.data_prevista AS previsao_logistica, e.data_envio, e.data_entrega,
                           e.observacoes AS observacoes_logistica, e.responsavel,
                           t.nome AS transportadora,
                           CASE WHEN COALESCE(e.data_prevista, p.data_prevista_entrega) < CURDATE()
                                AND p.status NOT IN ('Entregue','Cancelado','Devolvido','Recusado','Devolução Solicitada')
                                THEN 1 ELSE 0 END AS atrasado
                    FROM pedidos p
                    LEFT JOIN clientes c ON c.id=p.cliente_id
                    LEFT JOIN entregas e ON e.pedido_id=p.id
                    LEFT JOIN transportadoras t ON t.id=e.transportadora_id
                    WHERE p.status IN ('Pronto para Envio','Enviado','Em Transporte','Entregue')
                    ORDER BY
                        CASE WHEN COALESCE(e.data_prevista,p.data_prevista_entrega) < CURDATE()
                                  AND p.status NOT IN ('Entregue','Cancelado','Devolvido','Recusado','Devolução Solicitada') THEN 0 ELSE 1 END,
                        COALESCE(e.data_prevista,p.data_prevista_entrega) ASC, p.id DESC
                """)
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    item = dict(row)
                    item["valor_total"] = float(item["valor_total"] or 0)
                    item["valor_frete"] = float(item["valor_frete"] or 0)
                    item["peso_kg"] = float(item["peso_kg"] or 0)
                    item["atrasado"] = bool(item["atrasado"])
                    result.append(item)
                cursor.execute("""
                    SELECT
                      SUM(CASE WHEN p.status='Pronto para Envio' THEN 1 ELSE 0 END) AS aguardando_expedicao,
                      SUM(CASE WHEN p.status IN ('Enviado','Em Transporte') THEN 1 ELSE 0 END) AS em_transporte,
                      SUM(CASE WHEN p.status='Entregue' THEN 1 ELSE 0 END) AS entregues,
                      SUM(CASE WHEN COALESCE(e.data_prevista,p.data_prevista_entrega) < CURDATE()
                                    AND p.status NOT IN ('Entregue','Cancelado','Devolvido','Recusado','Devolução Solicitada')
                               THEN 1 ELSE 0 END) AS atrasadas
                    FROM pedidos p LEFT JOIN entregas e ON e.pedido_id=p.id
                    WHERE p.status IN ('Pronto para Envio','Enviado','Em Transporte','Entregue')
                """)
                kpis = cursor.fetchone()
                return {"entregas": result, "indicadores": {k: int(v or 0) for k, v in kpis.items()}}
        finally:
            conn.close()
