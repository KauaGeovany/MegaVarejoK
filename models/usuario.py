import datetime
from abc import ABC, abstractmethod
from werkzeug.security import generate_password_hash, check_password_hash
from models.pedido import formatar_data_br

class Usuario(ABC):
    """
    Classe base abstrata para os usuários do sistema.
    Demonstra:
    - ABSTRAÇÃO: Define o contrato abstrato 'pode_acessar(modulo)'.
    - ENCAPSULAMENTO: Controla senhas com hash seguro e integridade de e-mail.
    - HERANÇA: Serve como superclasse para os perfis especializados.
    """

    def __init__(self, nome: str, email: str, perfil_id: int, perfil_nome: str,
                 senha_hash: str = None, ativo: bool = True, criado_em=None, id: int = None):
        self._id = id
        self.nome = nome
        self.email = email
        self._perfil_id = int(perfil_id)
        self._perfil_nome = perfil_nome
        self._senha_hash = senha_hash
        self.ativo = bool(ativo)
        self._criado_em = criado_em or datetime.datetime.now()

    @property
    def id(self):
        return self._id

    @property
    def nome(self):
        return self._nome

    @nome.setter
    def nome(self, valor: str):
        if not valor or not str(valor).strip():
            raise ValueError("O nome do usuário é obrigatório.")
        self._nome = str(valor).strip()

    @property
    def email(self):
        return self._email

    @email.setter
    def email(self, valor: str):
        if not valor or not str(valor).strip():
            raise ValueError("O e-mail do usuário é obrigatório.")
        self._email = str(valor).strip().lower()

    @property
    def perfil_id(self):
        return self._perfil_id

    @perfil_id.setter
    def perfil_id(self, valor: int):
        self._perfil_id = int(valor)

    @property
    def perfil_nome(self):
        return self._perfil_nome

    @property
    def senha_hash(self):
        return self._senha_hash

    @property
    def ativo(self):
        return self._ativo

    @ativo.setter
    def ativo(self, valor: bool):
        self._ativo = bool(valor)

    @property
    def criado_em(self):
        return self._criado_em

    def definir_senha(self, senha: str):
        """Aplica hash seguro na senha informada."""
        if not senha or len(str(senha).strip()) < 6:
            raise ValueError("A senha deve conter no mínimo 6 caracteres.")
        self._senha_hash = generate_password_hash(str(senha).strip())

    def verificar_senha(self, senha: str) -> bool:
        """Compara a senha informada com o hash armazenado."""
        if not self._senha_hash:
            return False
        return check_password_hash(self._senha_hash, senha)

    @abstractmethod
    def pode_acessar(self, modulo: str) -> bool:
        """
        Método polimórfico obrigatório. Cada especialização define suas permissões de abas/módulos.
        """
        pass

    @abstractmethod
    def obter_permissoes(self) -> list:
        """Retorna a lista de módulos aos quais este perfil tem acesso."""
        pass

    @abstractmethod
    def pode_executar(self, acao: str) -> bool:
        """
        Método polimórfico para controle de acesso granular por operação.
        Ações conhecidas:
        - 'criar_pedido', 'gerenciar_pedido', 'cancelar_pedido', 'solicitar_devolucao'
        - 'conferir_devolucao', 'separar_expedir_pedido'
        - 'confirmar_pagamento', 'registrar_reembolso', 'pagar_despesa', 'cadastrar_despesa', 'cadastrar_fornecedor'
        - 'cadastrar_cliente', 'editar_cliente', 'excluir_cliente'
        - 'cadastrar_produto', 'editar_produto', 'excluir_produto', 'alterar_preco_produto'
        - 'movimentar_estoque', 'ajustar_estoque'
        - 'gerenciar_usuarios'
        """
        pass

    def to_dict(self):
        return {
            "id": self._id,
            "nome": self._nome,
            "email": self._email,
            "perfil_id": self._perfil_id,
            "perfil_nome": self._perfil_nome,
            "ativo": 1 if self._ativo else 0,
            "criado_em": formatar_data_br(self._criado_em, incluir_hora=False)
        }


# --- ESPECIALIZAÇÕES (HERANÇA E POLIMORFISMO) ---

class Administrador(Usuario):
    """
    Especialização Administrador: Acesso completo ao sistema e à gestão de usuários.
    Demonstra POLIMORFISMO implementando 'pode_acessar', 'obter_permissoes' e 'pode_executar'.
    """
    PERMISSOES = {'dashboard', 'produtos', 'estoque', 'pedidos', 'clientes', 'usuarios', 'financeiro', 'logistica', 'compras', 'pdv'}

    def __init__(self, nome: str, email: str, senha_hash: str = None, ativo: bool = True, criado_em=None, id: int = None, perfil_id: int = 1):
        super().__init__(nome, email, perfil_id, "Administrador", senha_hash, ativo, criado_em, id)

    def pode_acessar(self, modulo: str) -> bool:
        return modulo in self.PERMISSOES

    def obter_permissoes(self) -> list:
        return list(self.PERMISSOES)

    def pode_executar(self, acao: str) -> bool:
        # Administrador possui acesso e execução irrestritos a todas as operações
        return True


class Estoquista(Usuario):
    """
    Especialização Estoque: Acesso a Estoque/Produtos.
    Operações permitidas: entradas, saídas, ajustes, conferência de devoluções e separação/expedição.
    Operações proibidas: alterar preços, cadastrar/editar pedidos, gerenciar clientes, usuários ou financeiro.
    Demonstra POLIMORFISMO.
    """
    PERMISSOES = {'produtos', 'estoque', 'logistica', 'compras'}
    ACOES_PERMITIDAS = {
        'cadastrar_produto', 'editar_produto', 'movimentar_estoque', 'ajustar_estoque',
        'conferir_devolucao', 'separar_expedir_pedido'
    }

    def __init__(self, nome: str, email: str, senha_hash: str = None, ativo: bool = True, criado_em=None, id: int = None, perfil_id: int = 2):
        super().__init__(nome, email, perfil_id, "Estoque", senha_hash, ativo, criado_em, id)

    def pode_acessar(self, modulo: str) -> bool:
        return modulo in self.PERMISSOES

    def obter_permissoes(self) -> list:
        return list(self.PERMISSOES)

    def pode_executar(self, acao: str) -> bool:
        return acao in self.ACOES_PERMITIDAS


class Vendedor(Usuario):
    """
    Especialização Vendas: Acesso a Estoque (apenas consulta), Pedidos e Clientes.
    Operações permitidas: cadastrar e consultar clientes, criar e gerenciar pedidos, solicitar cancelamento e devolução.
    Operações proibidas: editar dados de clientes cadastrados, exclusão de clientes, movimentação manual ou ajuste de estoque,
    alteração de produtos/preços, confirmação manual de pagamentos, financeiro ou usuários.
    Demonstra POLIMORFISMO.
    """
    PERMISSOES = {'produtos', 'estoque', 'pedidos', 'clientes', 'logistica', 'pdv'}
    ACOES_PERMITIDAS = {
        'cadastrar_cliente', 'criar_pedido', 'gerenciar_pedido',
        'cancelar_pedido', 'solicitar_devolucao'
    }

    def __init__(self, nome: str, email: str, senha_hash: str = None, ativo: bool = True, criado_em=None, id: int = None, perfil_id: int = 3):
        super().__init__(nome, email, perfil_id, "Vendas", senha_hash, ativo, criado_em, id)

    def pode_acessar(self, modulo: str) -> bool:
        return modulo in self.PERMISSOES

    def obter_permissoes(self) -> list:
        return list(self.PERMISSOES)

    def pode_executar(self, acao: str) -> bool:
        return acao in self.ACOES_PERMITIDAS


class Gerente(Usuario):
    """
    Especialização Gerência: Supervisão e consulta geral dos módulos permitidos, incluindo o Dashboard Gerencial.
    Acesso a Dashboard, Estoque (consulta), Pedidos, Clientes (consulta) e Financeiro (consulta).
    Operações permitidas: supervisão, alteração de status operacional de pedidos, conferência/aprovação de devoluções.
    Operações proibidas: confirmação manual de pagamentos (restrita ao Financeiro/Admin), alteração de preços,
    cadastro de despesas/pagamentos de caixa, e administração de usuários.
    Demonstra POLIMORFISMO.
    """
    PERMISSOES = {'dashboard', 'produtos', 'estoque', 'pedidos', 'clientes', 'financeiro', 'logistica', 'compras', 'pdv'}
    ACOES_PERMITIDAS = {
        'gerenciar_pedido', 'cancelar_pedido', 'solicitar_devolucao', 'conferir_devolucao',
        'separar_expedir_pedido'
    }

    def __init__(self, nome: str, email: str, senha_hash: str = None, ativo: bool = True, criado_em=None, id: int = None, perfil_id: int = 4):
        super().__init__(nome, email, perfil_id, "Gerência", senha_hash, ativo, criado_em, id)

    def pode_acessar(self, modulo: str) -> bool:
        return modulo in self.PERMISSOES

    def obter_permissoes(self) -> list:
        return list(self.PERMISSOES)

    def pode_executar(self, acao: str) -> bool:
        return acao in self.ACOES_PERMITIDAS


class Financeiro(Usuario):
    """
    Especialização Financeiro: Acesso a Pedidos (apenas consulta) e Financeiro.
    Operações permitidas: consultar pedidos, confirmar pagamentos, registrar estornos/reembolsos,
    cadastrar fornecedores, cadastrar contas a pagar, quitar contas (saída de caixa) e conciliações.
    Operações proibidas: criação ou alteração operacional de pedidos (itens, frete, status operacional),
    movimentações de estoque, alteração de clientes ou usuários.
    Demonstra POLIMORFISMO.
    """
    PERMISSOES = {'pedidos', 'financeiro', 'compras'}
    ACOES_PERMITIDAS = {
        'confirmar_pagamento', 'registrar_reembolso', 'pagar_despesa',
        'cadastrar_despesa', 'cadastrar_fornecedor'
    }

    def __init__(self, nome: str, email: str, senha_hash: str = None, ativo: bool = True, criado_em=None, id: int = None, perfil_id: int = 5):
        super().__init__(nome, email, perfil_id, "Financeiro", senha_hash, ativo, criado_em, id)

    def pode_acessar(self, modulo: str) -> bool:
        return modulo in self.PERMISSOES

    def obter_permissoes(self) -> list:
        return list(self.PERMISSOES)

    def pode_executar(self, acao: str) -> bool:
        return acao in self.ACOES_PERMITIDAS


class UsuarioFactory:
    """
    Padrão Factory (Fábrica) para instanciar a especialização correta de Usuario
    com base no perfil_nome ou perfil_id registrado no banco de dados.
    """

    @staticmethod
    def criar_usuario(perfil_nome: str, nome: str, email: str, senha_hash: str = None,
                      ativo: bool = True, criado_em=None, id: int = None, perfil_id: int = None) -> Usuario:
        nome_perfil = (perfil_nome or "").strip()

        if nome_perfil == "Administrador" or perfil_id == 1:
            return Administrador(nome, email, senha_hash, ativo, criado_em, id, perfil_id or 1)
        elif nome_perfil == "Estoque" or perfil_id == 2:
            return Estoquista(nome, email, senha_hash, ativo, criado_em, id, perfil_id or 2)
        elif nome_perfil == "Vendas" or perfil_id == 3:
            return Vendedor(nome, email, senha_hash, ativo, criado_em, id, perfil_id or 3)
        elif nome_perfil == "Gerência" or perfil_id == 4:
            return Gerente(nome, email, senha_hash, ativo, criado_em, id, perfil_id or 4)
        elif nome_perfil == "Financeiro" or perfil_id == 5:
            return Financeiro(nome, email, senha_hash, ativo, criado_em, id, perfil_id or 5)
        else:
            # Fallback seguro para perfis desconhecidos
            return Vendedor(nome, email, senha_hash, ativo, criado_em, id, perfil_id or 3)
