from repositories.base_repository import BaseRepository
from models.produto import Produto
from database.connection import DatabaseConnection

class ProdutoRepository(BaseRepository):
    """
    Repositório de persistência para a entidade Produto e Módulo Estoque.
    Encapsula consultas SQL diretas mantendo suporte à integridade e colunas adicionais.
    """

    def __init__(self, connection=None):
        self._connection = connection

    def _get_connection(self):
        return self._connection if self._connection else DatabaseConnection.get_connection()

    def _mapear_linha(self, l) -> Produto:
        return Produto(
            id=l['id'],
            codigo=l.get('codigo'),
            nome=l['nome'],
            categoria=l.get('categoria') or 'Geral',
            preco=l['preco'],
            estoque=l['estoque'],
            estoque_reservado=int(l.get('estoque_reservado') or 0),
            estoque_minimo=l.get('estoque_minimo') if l.get('estoque_minimo') is not None else 5,
            custo_medio=l.get('custo_medio', 0)
        )

    def listar_todos(self, busca: str = None) -> list:
        conn = self._get_connection()
        should_close = self._connection is None
        try:
            with conn.cursor() as cursor:
                if busca and str(busca).strip():
                    termo = f"%{str(busca).strip()}%"
                    cursor.execute("""
                        SELECT id, 
                               COALESCE(codigo, CONCAT('PRD-', LPAD(id, 3, '0'))) as codigo,
                               nome, 
                               COALESCE(categoria, 'Geral') as categoria,
                               CAST(preco AS FLOAT) AS preco, 
                               estoque,
                               COALESCE(estoque_reservado, 0) as estoque_reservado,
                               COALESCE(estoque_minimo, 5) as estoque_minimo,
                               COALESCE(custo_medio, 0) as custo_medio
                        FROM produtos 
                        WHERE nome LIKE %s OR codigo LIKE %s OR categoria LIKE %s
                        ORDER BY id DESC;
                    """, (termo, termo, termo))
                else:
                    cursor.execute("""
                        SELECT id, 
                               COALESCE(codigo, CONCAT('PRD-', LPAD(id, 3, '0'))) as codigo,
                               nome, 
                               COALESCE(categoria, 'Geral') as categoria,
                               CAST(preco AS FLOAT) AS preco, 
                               estoque,
                               COALESCE(estoque_reservado, 0) as estoque_reservado,
                               COALESCE(estoque_minimo, 5) as estoque_minimo
                        FROM produtos 
                        ORDER BY id DESC;
                    """)
                linhas = cursor.fetchall()
                return [self._mapear_linha(l) for l in linhas]
        finally:
            if should_close:
                conn.close()

    def buscar_por_id(self, id: int) -> Produto:
        conn = self._get_connection()
        should_close = self._connection is None
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, 
                           COALESCE(codigo, CONCAT('PRD-', LPAD(id, 3, '0'))) as codigo,
                           nome, 
                           COALESCE(categoria, 'Geral') as categoria,
                           CAST(preco AS FLOAT) AS preco, 
                           estoque,
                           COALESCE(estoque_reservado, 0) as estoque_reservado,
                           COALESCE(estoque_minimo, 5) as estoque_minimo
                    FROM produtos 
                    WHERE id = %s;
                """, (id,))
                linha = cursor.fetchone()
                if not linha:
                    return None
                return self._mapear_linha(linha)
        finally:
            if should_close:
                conn.close()

    def buscar_por_id_com_lock(self, id: int, conn) -> Produto:
        """Busca o produto aplicando bloqueio de linha (FOR UPDATE) para controle de concorrência."""
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, 
                       COALESCE(codigo, CONCAT('PRD-', LPAD(id, 3, '0'))) as codigo,
                       nome, 
                       COALESCE(categoria, 'Geral') as categoria,
                       CAST(preco AS FLOAT) AS preco, 
                       estoque,
                       COALESCE(estoque_reservado, 0) as estoque_reservado,
                       COALESCE(estoque_minimo, 5) as estoque_minimo
                FROM produtos 
                WHERE id = %s FOR UPDATE;
            """, (id,))
            linha = cursor.fetchone()
            if not linha:
                return None
            return self._mapear_linha(linha)

    def salvar(self, produto: Produto) -> int:
        conn = self._get_connection()
        should_close = self._connection is None
        try:
            with conn.cursor() as cursor:
                # Tenta inserir com as novas colunas
                try:
                    cursor.execute(
                        """
                        INSERT INTO produtos (codigo, nome, categoria, preco, estoque, estoque_minimo)
                        VALUES (%s, %s, %s, %s, %s, %s);
                        """,
                        (produto.codigo, produto.nome, produto.categoria, produto.preco, produto.estoque, produto.estoque_minimo)
                    )
                except Exception:
                    # Fallback de compatibilidade se schema legado não possuir novas colunas
                    cursor.execute(
                        "INSERT INTO produtos (nome, preco, estoque) VALUES (%s, %s, %s);",
                        (produto.nome, produto.preco, produto.estoque)
                    )

                conn.commit()
                novo_id = cursor.lastrowid
                return novo_id
        except Exception:
            conn.rollback()
            raise
        finally:
            if should_close:
                conn.close()

    def atualizar(self, produto: Produto) -> bool:
        conn = self._get_connection()
        should_close = self._connection is None
        try:
            with conn.cursor() as cursor:
                try:
                    cursor.execute(
                        """
                        UPDATE produtos 
                        SET codigo = %s, nome = %s, categoria = %s, preco = %s, estoque = %s, estoque_minimo = %s
                        WHERE id = %s;
                        """,
                        (produto.codigo, produto.nome, produto.categoria, produto.preco, produto.estoque, produto.estoque_minimo, produto.id)
                    )
                except Exception:
                    cursor.execute(
                        "UPDATE produtos SET nome = %s, preco = %s, estoque = %s WHERE id = %s;",
                        (produto.nome, produto.preco, produto.estoque, produto.id)
                    )

                if cursor.rowcount == 0:
                    cursor.execute("SELECT id FROM produtos WHERE id = %s;", (produto.id,))
                    if not cursor.fetchone():
                        return False
                conn.commit()
                return True
        except Exception:
            conn.rollback()
            raise
        finally:
            if should_close:
                conn.close()

    def atualizar_estoque_transacional(self, produto_id: int, novo_estoque: int, conn, novo_reservado: int = None):
        """Atualiza o estoque físico e opcionalmente o reservado dentro de uma transação aberta."""
        with conn.cursor() as cursor:
            if novo_reservado is not None:
                try:
                    cursor.execute(
                        "UPDATE produtos SET estoque = %s, estoque_reservado = %s WHERE id = %s;",
                        (novo_estoque, novo_reservado, produto_id)
                    )
                except Exception:
                    cursor.execute(
                        "UPDATE produtos SET estoque = %s WHERE id = %s;",
                        (novo_estoque, produto_id)
                    )
            else:
                cursor.execute(
                    "UPDATE produtos SET estoque = %s WHERE id = %s;",
                    (novo_estoque, produto_id)
                )

    def excluir(self, id: int) -> bool:
        conn = self._get_connection()
        should_close = self._connection is None
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM produtos WHERE id = %s;", (id,))
                if cursor.rowcount == 0:
                    return False
                conn.commit()
                return True
        except Exception:
            conn.rollback()
            raise
        finally:
            if should_close:
                conn.close()

    def contar_total(self) -> int:
        conn = self._get_connection()
        should_close = self._connection is None
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS total_produtos FROM produtos;")
                linha = cursor.fetchone()
                if not linha:
                    return 0
                return linha.get('total_produtos') or linha.get('total') or 0
        finally:
            if should_close:
                conn.close()

    def somar_unidades_estoque(self) -> int:
        """Soma o total de unidades físicas de todos os produtos em estoque."""
        conn = self._get_connection()
        should_close = self._connection is None
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COALESCE(SUM(estoque), 0) AS total_unidades FROM produtos;")
                linha = cursor.fetchone()
                return int(linha.get('total_unidades', 0)) if linha else 0
        finally:
            if should_close:
                conn.close()

    def listar_produtos_criticos(self) -> list:
        """Retorna produtos com estoque zerado ou abaixo/igual ao estoque mínimo."""
        conn = self._get_connection()
        should_close = self._connection is None
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, 
                           COALESCE(codigo, CONCAT('PRD-', LPAD(id, 3, '0'))) as codigo,
                           nome, 
                           COALESCE(categoria, 'Geral') as categoria,
                           CAST(preco AS FLOAT) AS preco, 
                           estoque,
                           COALESCE(estoque_reservado, 0) as estoque_reservado,
                           COALESCE(estoque_minimo, 5) as estoque_minimo
                    FROM produtos 
                    WHERE estoque <= COALESCE(estoque_minimo, 5)
                    ORDER BY estoque ASC;
                """)
                linhas = cursor.fetchall()
                return [self._mapear_linha(l) for l in linhas]
        finally:
            if should_close:
                conn.close()
