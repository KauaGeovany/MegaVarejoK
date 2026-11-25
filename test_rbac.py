"""
Script de testes automatizados do RBAC, Login e Logout do MegaVarejo ERP.
Utiliza o cliente de testes integrado do Flask (sem necessidade de conexao externa ativa durante o mock).
"""

import unittest
from unittest.mock import patch, MagicMock
from werkzeug.security import generate_password_hash
from app import app, ROLE_PERMISSIONS

class TestAuthRBAC(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        self.client = app.test_client()

        # Hash padrao para testes
        self.senha_plana = 'admin123'
        self.senha_hash = generate_password_hash(self.senha_plana)

    # 1. TESTE DE ROTAS PROTEGIDAS SEM LOGIN
    def test_rotas_bloqueadas_sem_login(self):
        """Verifica se qualquer rota da API retorna 401 para usuario anonimo."""
        rotas = ['/api/dashboard', '/api/produtos', '/api/pedidos', '/api/clientes', '/api/usuarios']
        for rota in rotas:
            res = self.client.get(rota)
            self.assertEqual(res.status_code, 401, f"Rota {rota} deveria exigir login.")

    # 2. TESTE DE LOGIN COM SUCESSO E SENHA INCORRETA
    @patch('app.get_db_connection')
    def test_login_sucesso_e_falha(self, mock_db_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Simula usuario retornado do MySQL
        mock_cursor.fetchone.return_value = {
            'id': 1,
            'nome': 'Admin Master',
            'email': 'admin@megavarejo.com',
            'senha_hash': self.senha_hash,
            'ativo': 1,
            'perfil_nome': 'Administrador'
        }

        # 2.1 Login com senha errada
        res_falha = self.client.post('/api/auth/login', json={
            'email': 'admin@megavarejo.com',
            'senha': 'senha_errada'
        })
        self.assertEqual(res_falha.status_code, 401)

        # 2.2 Login com sucesso
        res_sucesso = self.client.post('/api/auth/login', json={
            'email': 'admin@megavarejo.com',
            'senha': self.senha_plana
        })
        self.assertEqual(res_sucesso.status_code, 200)
        dados = res_sucesso.get_json()
        self.assertIn('usuario', dados)
        self.assertEqual(dados['usuario']['perfil'], 'Administrador')

    # 3. TESTE DE LOGOUT
    def test_logout(self):
        with self.client.session_transaction() as sess:
            sess['usuario_id'] = 1
            sess['usuario_nome'] = 'Admin'
            sess['usuario_perfil'] = 'Administrador'

        res = self.client.post('/api/auth/logout')
        self.assertEqual(res.status_code, 200)

        # Acessar /api/auth/me apos logout deve retornar 401
        res_me = self.client.get('/api/auth/me')
        self.assertEqual(res_me.status_code, 401)

    # 4. TESTE RBAC - PERFIL ESTOQUE
    @patch('app.compras_service.garantir_estrutura')
    @patch('app.get_db_connection')
    def test_rbac_perfil_estoque(self, mock_db_conn, mock_garantir_estrutura):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {'total_produtos': 10, 'total_pedidos': 5, 'total_vendas': 1500.0}

        with self.client.session_transaction() as sess:
            sess['usuario_id'] = 2
            sess['usuario_perfil'] = 'Estoque'

        # Estoque NAO PODE acessar Dashboard Gerencial, Pedidos, Clientes ou Usuarios
        res_dash = self.client.get('/api/dashboard')
        self.assertEqual(res_dash.status_code, 403)

        res_prod = self.client.get('/api/produtos')
        self.assertEqual(res_prod.status_code, 200)

        # Estoque NAO PODE acessar Pedidos, Clientes ou Usuarios
        res_ped = self.client.get('/api/pedidos')
        self.assertEqual(res_ped.status_code, 403)

        res_cli = self.client.get('/api/clientes')
        self.assertEqual(res_cli.status_code, 403)

        res_usr = self.client.get('/api/usuarios')
        self.assertEqual(res_usr.status_code, 403)

    # 5. TESTE RBAC - PERFIL VENDAS
    @patch('app.compras_service.garantir_estrutura')
    @patch('app.get_db_connection')
    def test_rbac_perfil_vendas(self, mock_db_conn, mock_garantir_estrutura):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {'total_produtos': 10, 'total_pedidos': 5, 'total_vendas': 1500.0}

        with self.client.session_transaction() as sess:
            sess['usuario_id'] = 3
            sess['usuario_perfil'] = 'Vendas'

        # Vendas PODE: Produtos, Pedidos, Clientes. NAO PODE: Dashboard Gerencial
        self.assertEqual(self.client.get('/api/dashboard').status_code, 403)
        self.assertEqual(self.client.get('/api/produtos').status_code, 200)
        self.assertEqual(self.client.get('/api/pedidos').status_code, 200)
        self.assertEqual(self.client.get('/api/clientes').status_code, 200)

        # Vendas NAO PODE: Usuarios
        self.assertEqual(self.client.get('/api/usuarios').status_code, 403)

    # 6. TESTE RBAC - PERFIL GERENCIA
    @patch('app.compras_service.garantir_estrutura')
    @patch('app.get_db_connection')
    def test_rbac_perfil_gerencia(self, mock_db_conn, mock_garantir_estrutura):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {'total_produtos': 10, 'total_pedidos': 5, 'total_vendas': 1500.0}

        with self.client.session_transaction() as sess:
            sess['usuario_id'] = 4
            sess['usuario_perfil'] = 'Gerência'

        # Gerencia PODE acessar todos os modulos operacionais
        self.assertEqual(self.client.get('/api/dashboard').status_code, 200)
        self.assertEqual(self.client.get('/api/produtos').status_code, 200)
        self.assertEqual(self.client.get('/api/pedidos').status_code, 200)
        self.assertEqual(self.client.get('/api/clientes').status_code, 200)

        # Gerencia NAO PODE administrar usuarios
        self.assertEqual(self.client.get('/api/usuarios').status_code, 403)

    # 7. TESTE RBAC - PERFIL ADMINISTRADOR
    @patch('app.compras_service.garantir_estrutura')
    @patch('app.get_db_connection')
    def test_rbac_perfil_administrador(self, mock_db_conn, mock_garantir_estrutura):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {'total_produtos': 10, 'total_pedidos': 5, 'total_vendas': 1500.0}

        with self.client.session_transaction() as sess:
            sess['usuario_id'] = 1
            sess['usuario_perfil'] = 'Administrador'

        # Administrador tem acesso a absolutamente todos os recursos
        self.assertEqual(self.client.get('/api/dashboard').status_code, 200)
        self.assertEqual(self.client.get('/api/produtos').status_code, 200)
        self.assertEqual(self.client.get('/api/pedidos').status_code, 200)
        self.assertEqual(self.client.get('/api/clientes').status_code, 200)
        self.assertEqual(self.client.get('/api/usuarios').status_code, 200)

    # 8. TESTE RBAC - PERFIL FINANCEIRO
    @patch('app.get_db_connection')
    def test_rbac_perfil_financeiro(self, mock_db_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {'total_produtos': 10, 'total_pedidos': 5, 'total_vendas': 1500.0}

        with self.client.session_transaction() as sess:
            sess['usuario_id'] = 5
            sess['usuario_perfil'] = 'Financeiro'

        # Financeiro PODE acessar Pedidos (consulta) e Financeiro. NÃO PODE: Dashboard Gerencial
        self.assertEqual(self.client.get('/api/dashboard').status_code, 403)
        self.assertEqual(self.client.get('/api/pedidos').status_code, 200)
        self.assertEqual(self.client.get('/api/financeiro/visao-geral').status_code, 200)

        # Financeiro NÃO PODE acessar Produtos/Estoque, Clientes ou Usuários
        self.assertEqual(self.client.get('/api/produtos').status_code, 403)
        self.assertEqual(self.client.get('/api/clientes').status_code, 403)
        self.assertEqual(self.client.get('/api/usuarios').status_code, 403)

    # 9. TESTE DE CRIAÇÃO DE PEDIDOS (ADMIN E VENDAS PODEM, OUTROS BLOQUEADOS)
    @patch('services.pedido_service.DatabaseConnection.get_connection')
    def test_criacao_pedidos_permissoes_e_bloqueios(self, mock_db):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchone.return_value = {
            'id': 1,
            'codigo': 'NOT-001',
            'nome': 'Notebook Gamer',
            'categoria': 'Informática',
            'preco': 4500.00,
            'estoque': 10,
            'estoque_reservado': 0,
            'estoque_minimo': 5
        }
        mock_cursor.lastrowid = 101

        payload = {
            'cliente_id': 1,
            'forma_pagamento': 'PIX',
            'itens': [{'produto_id': 1, 'quantidade': 2}]
        }

        # 9.1 Vendas PODE criar pedidos
        with self.client.session_transaction() as sess:
            sess['usuario_id'] = 3
            sess['usuario_nome'] = 'Vendedor Teste'
            sess['usuario_perfil'] = 'Vendas'

        res_vendas = self.client.post('/api/pedidos', json=payload)
        self.assertEqual(res_vendas.status_code, 201)
        self.assertIn("reservados", res_vendas.get_json()['mensagem'])

        # 9.2 Administrador PODE criar pedidos
        with self.client.session_transaction() as sess:
            sess['usuario_id'] = 1
            sess['usuario_nome'] = 'Admin Teste'
            sess['usuario_perfil'] = 'Administrador'

        res_admin = self.client.post('/api/pedidos', json=payload)
        self.assertEqual(res_admin.status_code, 201)

        # 9.3 Estoquista NÃO PODE criar pedidos
        with self.client.session_transaction() as sess:
            sess['usuario_id'] = 2
            sess['usuario_perfil'] = 'Estoque'

        res_estoque = self.client.post('/api/pedidos', json=payload)
        self.assertEqual(res_estoque.status_code, 403)

        # 9.4 Financeiro NÃO PODE criar pedidos
        with self.client.session_transaction() as sess:
            sess['usuario_id'] = 5
            sess['usuario_perfil'] = 'Financeiro'

        res_fin = self.client.post('/api/pedidos', json=payload)
        self.assertEqual(res_fin.status_code, 403)

        # 9.5 Gerência NÃO PODE criar pedidos (apenas consulta e supervisão)
        with self.client.session_transaction() as sess:
            sess['usuario_id'] = 4
            sess['usuario_perfil'] = 'Gerência'

        res_ger = self.client.post('/api/pedidos', json=payload)
        self.assertEqual(res_ger.status_code, 403)

    # 10. TESTES DE PERMISSÕES GRANULARES POR OPERAÇÃO
    def test_permissoes_granulares_especificas(self):
        # 10.1 Vendas NÃO PODE confirmar pagamento manual
        with self.client.session_transaction() as sess:
            sess['usuario_id'] = 3
            sess['usuario_perfil'] = 'Vendas'

        res_pag_vendas = self.client.patch('/api/pedidos/1/pagamento', json={'status_pagamento': 'Confirmado'})
        self.assertEqual(res_pag_vendas.status_code, 403)

        # 10.1.1 Vendas NÃO PODE editar clientes existentes (apenas cadastrar e consultar)
        res_edit_cli_vendas = self.client.put('/api/clientes/1', json={'nome': 'Nome Alterado', 'email': 'alt@t.com', 'cpf': '12345678909'})
        self.assertEqual(res_edit_cli_vendas.status_code, 403)

        res_patch_cli_vendas = self.client.patch('/api/clientes/1', json={'telefone': '11999999999'})
        self.assertEqual(res_patch_cli_vendas.status_code, 403)

        # 10.1.2 Vendas PODE cadastrar novo cliente (permissão preservada)
        from models.usuario import UsuarioFactory
        vendedor_obj = UsuarioFactory.criar_usuario("Vendas", "Vendedor", "vendas@t.com")
        self.assertTrue(vendedor_obj.pode_executar('cadastrar_cliente'))
        self.assertFalse(vendedor_obj.pode_executar('editar_cliente'))
        self.assertFalse(vendedor_obj.pode_executar('excluir_cliente'))

        # Administrador PODE editar cliente
        admin_obj = UsuarioFactory.criar_usuario("Administrador", "Admin", "admin@t.com")
        self.assertTrue(admin_obj.pode_executar('editar_cliente'))

        # 10.2 Gerência NÃO PODE confirmar pagamento manual
        with self.client.session_transaction() as sess:
            sess['usuario_id'] = 4
            sess['usuario_perfil'] = 'Gerência'

        res_pag_ger = self.client.patch('/api/pedidos/1/pagamento', json={'status_pagamento': 'Confirmado'})
        self.assertEqual(res_pag_ger.status_code, 403)

        # 10.3 Gerência NÃO PODE cadastrar ou alterar clientes (apenas consulta)
        res_cli_ger = self.client.post('/api/clientes', json={'nome': 'Novo Cli', 'email': 'cli@t.com', 'cpf': '12345678909'})
        self.assertEqual(res_cli_ger.status_code, 403)

        # 10.4 Gerência NÃO PODE alterar financeiro (pagar despesa)
        res_fin_ger = self.client.post('/api/financeiro/contas-pagar/1/pagar', json={'valor': 100.0})
        self.assertEqual(res_fin_ger.status_code, 403)

        # 10.5 Financeiro NÃO PODE alterar status operacional de pedidos
        with self.client.session_transaction() as sess:
            sess['usuario_id'] = 5
            sess['usuario_perfil'] = 'Financeiro'

        res_stat_fin = self.client.patch('/api/pedidos/1/status', json={'status': 'Entregue'})
        self.assertEqual(res_stat_fin.status_code, 403)

if __name__ == '__main__':
    unittest.main()
