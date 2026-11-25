class Produto:
    """
    Representa a entidade de domínio Produto no módulo de Estoque.
    Demonstra ENCAPSULAMENTO controlando atributos privados, validações de preço,
    estoque físico, estoque reservado, estoque disponível, estoque mínimo, código e categoria.
    """

    def __init__(self, nome: str, preco: float, estoque: int, codigo: str = None,
                 categoria: str = "Geral", estoque_minimo: int = 5, estoque_reservado: int = 0, id: int = None):
        self._id = id
        self.codigo = codigo or (f"PRD-{id:03d}" if id else "")
        self.nome = nome
        self.categoria = categoria or "Geral"
        self.preco = preco
        self.estoque = estoque
        self.estoque_reservado = estoque_reservado
        self.estoque_minimo = estoque_minimo

    @property
    def id(self):
        return self._id

    @property
    def codigo(self):
        return self._codigo

    @codigo.setter
    def codigo(self, valor: str):
        self._codigo = str(valor).strip().upper() if valor else ""

    @property
    def nome(self):
        return self._nome

    @nome.setter
    def nome(self, valor: str):
        if not valor or not str(valor).strip():
            raise ValueError("O nome do produto não pode ser vazio.")
        self._nome = str(valor).strip()

    @property
    def categoria(self):
        return self._categoria

    @categoria.setter
    def categoria(self, valor: str):
        self._categoria = str(valor).strip() if valor else "Geral"

    @property
    def preco(self):
        return self._preco

    @preco.setter
    def preco(self, valor: float):
        try:
            val = float(valor)
            if val < 0:
                raise ValueError("O preço do produto não pode ser negativo.")
            self._preco = val
        except (TypeError, ValueError):
            raise ValueError("Preço inválido para o produto.")

    @property
    def estoque(self):
        """Estoque físico total presente no almoxarifado."""
        return self._estoque

    @estoque.setter
    def estoque(self, valor: int):
        try:
            val = int(valor)
            if val < 0:
                raise ValueError("A quantidade em estoque físico não pode ser negativa.")
            self._estoque = val
        except (TypeError, ValueError):
            raise ValueError("Quantidade em estoque inválida.")

    @property
    def estoque_reservado(self):
        """Quantidade de unidades comprometidas em pedidos pendentes de expedição."""
        return self._estoque_reservado

    @estoque_reservado.setter
    def estoque_reservado(self, valor: int):
        try:
            val = int(valor)
            if val < 0:
                raise ValueError("O estoque reservado não pode ser negativo.")
            self._estoque_reservado = val
        except (TypeError, ValueError):
            raise ValueError("Estoque reservado inválido.")

    @property
    def estoque_disponivel(self) -> int:
        """Estoque livre para novas vendas: físico - reservado."""
        return max(0, self._estoque - self._estoque_reservado)

    @property
    def estoque_minimo(self):
        return self._estoque_minimo

    @estoque_minimo.setter
    def estoque_minimo(self, valor: int):
        try:
            val = int(valor) if valor is not None else 5
            if val < 0:
                raise ValueError("O estoque mínimo não pode ser negativo.")
            self._estoque_minimo = val
        except (TypeError, ValueError):
            raise ValueError("Estoque mínimo inválido.")

    def possui_estoque(self, quantidade: int) -> bool:
        """Verifica se há estoque disponível (livre de reservas) para atender à quantidade."""
        return self.estoque_disponivel >= quantidade

    def reservar_estoque(self, quantidade: int):
        """Reserva produtos para um pedido sem realizar a baixa física imediata."""
        if quantidade <= 0:
            raise ValueError("A quantidade a reservar deve ser maior que zero.")
        if not self.possui_estoque(quantidade):
            raise ValueError(f"Estoque disponível insuficiente para o produto '{self._nome}'. Disponível: {self.estoque_disponivel}, Solicitado: {quantidade}.")
        self._estoque_reservado += quantidade

    def liberar_reserva(self, quantidade: int):
        """Libera produtos reservados (ex: cancelamento de pedido)."""
        if quantidade <= 0:
            raise ValueError("A quantidade a liberar deve ser maior que zero.")
        liberar = min(quantidade, self._estoque_reservado)
        self._estoque_reservado -= liberar

    def expedir_reserva(self, quantidade: int):
        """Consolida a saída física da mercadoria no momento da expedição/envio."""
        if quantidade <= 0:
            raise ValueError("A quantidade a expedir deve ser maior que zero.")
        if self._estoque < quantidade:
            raise ValueError(f"Estoque físico insuficiente para expedição de '{self._nome}'. Físico: {self._estoque}, Expedição: {quantidade}.")
        # Baixa o reservado correspondente e debita o físico
        liberar = min(quantidade, self._estoque_reservado)
        self._estoque_reservado -= liberar
        self._estoque -= quantidade

    def debitar_estoque(self, quantidade: int):
        """Debita diretamente a quantidade do estoque com validação de consistência."""
        if quantidade <= 0:
            raise ValueError("A quantidade a debitar deve ser maior que zero.")
        if self._estoque < quantidade:
            raise ValueError(f"Estoque físico insuficiente para o produto '{self._nome}'. Disponível: {self._estoque}, Solicitado: {quantidade}.")
        self._estoque -= quantidade

    def creditar_estoque(self, quantidade: int):
        """Adiciona produtos ao estoque físico (Entrada ou devolução conferida)."""
        if quantidade <= 0:
            raise ValueError("A quantidade de entrada deve ser maior que zero.")
        self._estoque += quantidade

    def ajustar_estoque(self, novo_saldo: int):
        """Ajusta o saldo físico do estoque."""
        if novo_saldo < 0:
            raise ValueError("O novo saldo de estoque não pode ser negativo.")
        self._estoque = novo_saldo

    def status_estoque(self) -> str:
        """Retorna a situação do estoque com base no saldo disponível."""
        if self.estoque_disponivel <= 0:
            return "Zerado"
        if self.estoque_disponivel <= self._estoque_minimo:
            return "Baixo"
        return "Normal"

    def to_dict(self):
        return {
            "id": self._id,
            "codigo": self._codigo or f"PRD-{self._id:03d}" if self._id else "",
            "nome": self._nome,
            "categoria": self._categoria,
            "preco": float(self._preco),
            "estoque": int(self._estoque),
            "estoque_reservado": int(self._estoque_reservado),
            "estoque_disponivel": int(self.estoque_disponivel),
            "estoque_minimo": int(self._estoque_minimo),
            "status_estoque": self.status_estoque()
        }
