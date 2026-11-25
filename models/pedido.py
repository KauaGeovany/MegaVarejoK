import datetime

def formatar_data_br(dt, incluir_hora=True):
    """
    Função utilitária para converter objetos datetime / date para o formato brasileiro.
    """
    if not dt:
        return ''
    if isinstance(dt, datetime.datetime):
        formato = '%d/%m/%Y %H:%M' if incluir_hora else '%d/%m/%Y'
        return dt.strftime(formato)
    if isinstance(dt, datetime.date):
        return dt.strftime('%d/%m/%Y')
    str_val = str(dt)
    try:
        parsed = datetime.datetime.fromisoformat(str_val.replace('Z', ''))
        formato = '%d/%m/%Y %H:%M' if incluir_hora else '%d/%m/%Y'
        return parsed.strftime(formato)
    except Exception:
        return str_val

class ItemPedido:
    """
    Representa o item que compõe um Pedido.
    Demonstra ENCAPSULAMENTO com cálculo de subtotal e integridade de quantidade.
    """

    def __init__(self, produto_id: int, quantidade: int, preco_unitario: float, produto_nome: str = "", id: int = None):
        self._id = id
        self._produto_id = int(produto_id)
        self.quantidade = quantidade
        self.preco_unitario = preco_unitario
        self._produto_nome = produto_nome

    @property
    def id(self):
        return self._id

    @property
    def produto_id(self):
        return self._produto_id

    @property
    def produto_nome(self):
        return self._produto_nome

    @property
    def quantidade(self):
        return self._quantidade

    @quantidade.setter
    def quantidade(self, valor: int):
        val = int(valor)
        if val <= 0:
            raise ValueError("A quantidade do item deve ser maior que zero.")
        self._quantidade = val

    @property
    def preco_unitario(self):
        return self._preco_unitario

    @preco_unitario.setter
    def preco_unitario(self, valor: float):
        val = float(valor)
        if val < 0:
            raise ValueError("O preço unitário não pode ser negativo.")
        self._preco_unitario = val

    @property
    def subtotal(self) -> float:
        """Calcula o valor subtotal do item dinamicamente."""
        return round(self._quantidade * self._preco_unitario, 2)

    def to_dict(self):
        return {
            "id": self._id,
            "produto_id": self._produto_id,
            "produto_nome": self._produto_nome,
            "quantidade": self._quantidade,
            "preco_unitario": float(self._preco_unitario),
            "subtotal": float(self.subtotal)
        }


class Pedido:
    """
    Entidade de domínio Pedido reformulada com ciclo de vida completo.
    Demonstra ENCAPSULAMENTO com:
    - Desacoplamento entre status do pedido e status do pagamento.
    - Máquina de estados com validação de transições permitidas.
    - Cálculo de valor total com frete e desconto.
    - Restrições de edição baseadas no estágio do pedido.
    """

    # Status de Pedido permitidos
    STATUS_PEDIDO_VALIDOS = [
        'Aguardando Pagamento',
        'Confirmado',
        'Aguardando Separação',
        'Em Separação',
        'Pronto para Envio',
        'Enviado',
        'Em Transporte',
        'Entregue',
        'Cancelado',
        'Devolução Solicitada',
        'Devolvido',
        'Recusado'
    ]

    # Transições de fluxo permitidas (Máquina de Estados)
    TRANSIÇÕES_PERMITIDAS = {
        'Aguardando Pagamento': ['Confirmado', 'Cancelado', 'Recusado'],
        'Confirmado': ['Aguardando Separação', 'Em Separação', 'Entregue', 'Cancelado'],
        'Aguardando Separação': ['Em Separação', 'Cancelado'],
        'Em Separação': ['Pronto para Envio', 'Cancelado'],
        'Pronto para Envio': ['Enviado', 'Cancelado'],
        'Enviado': ['Em Transporte', 'Entregue', 'Devolução Solicitada'],
        'Em Transporte': ['Entregue', 'Devolução Solicitada'],
        'Entregue': ['Devolução Solicitada'],
        'Devolução Solicitada': ['Devolvido', 'Recusado'],
        'Cancelado': [],
        'Devolvido': [],
        'Recusado': []
    }

    # Status de Pagamento permitidos (Desacoplado)
    STATUS_PAGAMENTO_VALIDOS = [
        'Pendente',
        'Confirmado',
        'Recusado',
        'Reembolsado'
    ]

    FORMAS_PAGAMENTO_VALIDAS = [
        'Boleto Bancário',
        'Cartão de Crédito',
        'PIX',
        'Transferência Bancária',
        'Dinheiro',
        'Cartão de Débito'
    ]

    def __init__(self, cliente_id: int = None, status: str = "Aguardando Pagamento",
                 status_pagamento: str = "Pendente", forma_pagamento: str = "Boleto Bancário",
                 desconto: float = 0.0, frete: float = 0.0, endereco_entrega: str = "",
                 responsavel: str = "Vendedor", data_pedido=None, data_prevista_entrega=None,
                 numero_pedido: str = None, id: int = None, valor_total: float = 0.0,
                 cliente_nome: str = "", cliente_cpf: str = "", observacoes: str = ""):
        self._id = id
        self.numero_pedido = numero_pedido or (f"PED-{id:04d}" if id else "")
        self.cliente_id = cliente_id
        self._cliente_nome = cliente_nome
        self._cliente_cpf = cliente_cpf
        self.status = status
        self.status_pagamento = status_pagamento
        self.forma_pagamento = forma_pagamento
        self.desconto = desconto
        self.frete = frete
        self.endereco_entrega = endereco_entrega
        self.responsavel = responsavel
        self.observacoes = observacoes
        self._data_pedido = data_pedido or datetime.datetime.now()
        self.data_prevista_entrega = data_prevista_entrega
        self._itens = []
        self._historico = []
        self._valor_total_informado = float(valor_total)

    @property
    def id(self):
        return self._id

    @property
    def cliente_nome(self):
        return self._cliente_nome

    @property
    def cliente_cpf(self):
        return self._cliente_cpf

    @property
    def data_pedido(self):
        return self._data_pedido

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, valor: str):
        val = str(valor).strip()
        # Mapeamento de retrocompatibilidade
        if val == 'Pendente': val = 'Aguardando Pagamento'
        if val == 'Concluído': val = 'Entregue'

        if val not in self.STATUS_PEDIDO_VALIDOS:
            raise ValueError(f"Status de pedido inválido. Permitidos: {', '.join(self.STATUS_PEDIDO_VALIDOS)}")
        self._status = val

    @property
    def status_pagamento(self):
        return self._status_pagamento

    @status_pagamento.setter
    def status_pagamento(self, valor: str):
        val = str(valor).strip().capitalize()
        if val not in self.STATUS_PAGAMENTO_VALIDOS:
            raise ValueError(f"Status de pagamento inválido. Permitidos: {', '.join(self.STATUS_PAGAMENTO_VALIDOS)}")
        self._status_pagamento = val

    @property
    def forma_pagamento(self):
        return self._forma_pagamento

    @forma_pagamento.setter
    def forma_pagamento(self, valor: str):
        val = str(valor).strip() if valor else "Boleto Bancário"
        self._forma_pagamento = val

    @property
    def desconto(self):
        return self._desconto

    @desconto.setter
    def desconto(self, valor: float):
        try:
            val = float(valor or 0.0)
            if val < 0:
                raise ValueError("O desconto não pode ser negativo.")
            self._desconto = val
        except (TypeError, ValueError):
            raise ValueError("Valor de desconto inválido.")

    @property
    def frete(self):
        return self._frete

    @frete.setter
    def frete(self, valor: float):
        try:
            val = float(valor or 0.0)
            if val < 0:
                raise ValueError("O frete não pode ser negativo.")
            self._frete = val
        except (TypeError, ValueError):
            raise ValueError("Valor de frete inválido.")

    @property
    def itens(self):
        return list(self._itens)

    def adicionar_item(self, item: ItemPedido):
        if not isinstance(item, ItemPedido):
            raise TypeError("O item adicionado deve ser uma instância de ItemPedido.")
        self._itens.append(item)

    @property
    def valor_subtotal(self) -> float:
        """Soma o valor bruto dos itens sem frete e sem desconto."""
        if self._itens:
            return round(sum(item.subtotal for item in self._itens), 2)
        return round(max(0.0, self._valor_total_informado + self._desconto - self._frete), 2)

    @property
    def valor_total(self) -> float:
        """Calcula o valor total líquido: Subtotal - Desconto + Frete."""
        total = self.valor_subtotal - self._desconto + self._frete
        return round(max(0.0, total), 2)

    def pode_editar(self) -> bool:
        """
        Regra de negócio: Edições de itens e valores só são permitidas
        antes de o pedido entrar em separação física ou envio.
        """
        return self._status in ['Aguardando Pagamento', 'Confirmado']

    def transicao_valida(self, novo_status: str) -> bool:
        """Valida se o fluxo de estados obedece à máquina de estados do ERP."""
        if self._status == novo_status:
            return True
        destinos = self.TRANSIÇÕES_PERMITIDAS.get(self._status, [])
        return novo_status in destinos

    def esta_atrasado(self) -> bool:
        """Verifica se o pedido não foi entregue e a data prevista foi ultrapassada."""
        if self._status in ['Entregue', 'Cancelado', 'Devolvido', 'Recusado']:
            return False
        if not self.data_prevista_entrega:
            return False
        hoje = datetime.date.today()
        prevista = self.data_prevista_entrega
        if isinstance(prevista, str):
            try:
                prevista = datetime.date.fromisoformat(prevista)
            except Exception:
                return False
        elif isinstance(prevista, datetime.datetime):
            prevista = prevista.date()
        return hoje > prevista

    def to_dict(self):
        data_formatada = formatar_data_br(self._data_pedido, incluir_hora=True)
        return {
            "id": self._id,
            "numero_pedido": self.numero_pedido or f"PED-{self._id:04d}" if self._id else "",
            "cliente_id": self.cliente_id,
            "cliente_nome": self._cliente_nome or "Cliente não informado",
            "cliente_cpf": self._cliente_cpf or "-",
            "data_pedido": data_formatada,
            "data_formatada": data_formatada,
            "data_prevista_entrega": str(self.data_prevista_entrega) if self.data_prevista_entrega else None,
            "status": self._status,
            "status_pagamento": self._status_pagamento,
            "forma_pagamento": self._forma_pagamento,
            "valor_subtotal": float(self.valor_subtotal),
            "desconto": float(self._desconto),
            "frete": float(self._frete),
            "valor_total": float(self.valor_total),
            "endereco_entrega": self.endereco_entrega or "-",
            "responsavel": self.responsavel,
            "observacoes": self.observacoes or "",
            "pode_editar": self.pode_editar(),
            "esta_atrasado": self.esta_atrasado(),
            "itens": [item.to_dict() for item in self._itens]
        }
