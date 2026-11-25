-- Script SQL para o ERP MegaVarejo S.A.
-- Criação do banco de dados, tabelas originais, RBAC, Estoque e Módulo Avançado de Pedidos.

CREATE DATABASE IF NOT EXISTS megavarejo_erp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE megavarejo_erp;

-- 1. Tabela: produtos (com estoque físico e estoque reservado)
CREATE TABLE IF NOT EXISTS produtos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(50) DEFAULT NULL,
    nome VARCHAR(150) NOT NULL,
    categoria VARCHAR(100) DEFAULT 'Geral',
    preco DECIMAL(10, 2) NOT NULL,
    estoque INT NOT NULL DEFAULT 0,
    estoque_reservado INT NOT NULL DEFAULT 0,
    estoque_minimo INT NOT NULL DEFAULT 5,
    custo_medio DECIMAL(12,4) NOT NULL DEFAULT 0
);

-- Migrações idempotentes para tabela produtos
SET @dbname = DATABASE();
SET @tablename = "produtos";

-- coluna codigo
SET @columnname = "codigo";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE produtos ADD COLUMN codigo VARCHAR(50) DEFAULT NULL AFTER id;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

-- coluna categoria
SET @columnname = "categoria";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE produtos ADD COLUMN categoria VARCHAR(100) DEFAULT 'Geral' AFTER nome;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

-- coluna estoque_reservado
SET @columnname = "estoque_reservado";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE produtos ADD COLUMN estoque_reservado INT NOT NULL DEFAULT 0 AFTER estoque;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

-- coluna custo_medio
SET @columnname = "custo_medio";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE produtos ADD COLUMN custo_medio DECIMAL(12,4) NOT NULL DEFAULT 0;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

-- coluna estoque_minimo
SET @columnname = "estoque_minimo";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE produtos ADD COLUMN estoque_minimo INT NOT NULL DEFAULT 5 AFTER estoque_reservado;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;


-- 2. Tabela: clientes (com CPF único e Endereço detalhado)
CREATE TABLE IF NOT EXISTS clientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    cpf VARCHAR(20) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    telefone VARCHAR(50),
    cep VARCHAR(10) DEFAULT NULL,
    logradouro VARCHAR(150) DEFAULT NULL,
    numero VARCHAR(20) DEFAULT NULL,
    complemento VARCHAR(100) DEFAULT NULL,
    bairro VARCHAR(100) DEFAULT NULL,
    cidade VARCHAR(100),
    uf VARCHAR(2) DEFAULT NULL,
    endereco VARCHAR(255) DEFAULT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_clientes_cpf UNIQUE (cpf)
);

-- Migrações idempotentes para tabela clientes (CPF, campos de endereço e restrições)
SET @tablename = "clientes";

SET @columnname = "cpf";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE clientes ADD COLUMN cpf VARCHAR(20) DEFAULT NULL AFTER nome;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

SET @columnname = "cep";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE clientes ADD COLUMN cep VARCHAR(10) DEFAULT NULL AFTER telefone;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

SET @columnname = "logradouro";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE clientes ADD COLUMN logradouro VARCHAR(150) DEFAULT NULL AFTER cep;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

SET @columnname = "numero";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE clientes ADD COLUMN numero VARCHAR(20) DEFAULT NULL AFTER logradouro;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

SET @columnname = "complemento";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE clientes ADD COLUMN complemento VARCHAR(100) DEFAULT NULL AFTER numero;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

SET @columnname = "bairro";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE clientes ADD COLUMN bairro VARCHAR(100) DEFAULT NULL AFTER complemento;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

SET @columnname = "uf";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE clientes ADD COLUMN uf VARCHAR(2) DEFAULT NULL AFTER cidade;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

SET @columnname = "endereco";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE clientes ADD COLUMN endereco VARCHAR(255) DEFAULT NULL AFTER uf;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;


-- 3. Tabela: pedidos (com status de pedido e status de pagamento desacoplados)
CREATE TABLE IF NOT EXISTS pedidos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    numero_pedido VARCHAR(50) DEFAULT NULL,
    cliente_id INT DEFAULT NULL,
    data_pedido DATETIME DEFAULT CURRENT_TIMESTAMP,
    data_prevista_entrega DATE DEFAULT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'Aguardando Pagamento',
    status_pagamento VARCHAR(50) NOT NULL DEFAULT 'Pendente',
    forma_pagamento VARCHAR(50) DEFAULT 'Boleto Bancário',
    valor_subtotal DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    desconto DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    frete DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    valor_total DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    endereco_entrega VARCHAR(255) DEFAULT NULL,
    responsavel VARCHAR(100) NOT NULL DEFAULT 'Vendedor',
    observacoes TEXT DEFAULT NULL,
    CONSTRAINT fk_pedidos_clientes FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE SET NULL
);

-- Migrações idempotentes para tabela pedidos
SET @tablename = "pedidos";

SET @columnname = "numero_pedido";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE pedidos ADD COLUMN numero_pedido VARCHAR(50) DEFAULT NULL AFTER id;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

SET @columnname = "cliente_id";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE pedidos ADD COLUMN cliente_id INT DEFAULT NULL AFTER numero_pedido;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

SET @columnname = "status_pagamento";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE pedidos ADD COLUMN status_pagamento VARCHAR(50) NOT NULL DEFAULT 'Pendente' AFTER status;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

SET @columnname = "forma_pagamento";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE pedidos ADD COLUMN forma_pagamento VARCHAR(50) DEFAULT 'Boleto Bancário' AFTER status_pagamento;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

SET @columnname = "valor_subtotal";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE pedidos ADD COLUMN valor_subtotal DECIMAL(10, 2) NOT NULL DEFAULT 0.00 AFTER forma_pagamento;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

SET @columnname = "desconto";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE pedidos ADD COLUMN desconto DECIMAL(10, 2) NOT NULL DEFAULT 0.00 AFTER valor_subtotal;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

SET @columnname = "frete";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE pedidos ADD COLUMN frete DECIMAL(10, 2) NOT NULL DEFAULT 0.00 AFTER desconto;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

SET @columnname = "endereco_entrega";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE pedidos ADD COLUMN endereco_entrega VARCHAR(255) DEFAULT NULL AFTER valor_total;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

SET @columnname = "responsavel";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE pedidos ADD COLUMN responsavel VARCHAR(100) NOT NULL DEFAULT 'Vendedor' AFTER endereco_entrega;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

SET @columnname = "data_prevista_entrega";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE pedidos ADD COLUMN data_prevista_entrega DATE DEFAULT NULL AFTER data_pedido;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;

SET @columnname = "observacoes";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE pedidos ADD COLUMN observacoes TEXT DEFAULT NULL AFTER responsavel;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;


-- 4. Tabela: itens_pedido
CREATE TABLE IF NOT EXISTS itens_pedido (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pedido_id INT NOT NULL,
    produto_id INT NOT NULL,
    quantidade INT NOT NULL,
    preco_unitario DECIMAL(10, 2) NOT NULL,
    subtotal DECIMAL(10, 2) NOT NULL,
    CONSTRAINT fk_itens_pedido_pedidos FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE,
    CONSTRAINT fk_itens_pedido_produtos FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE RESTRICT
);


-- 5. Tabela: historico_pedidos (auditoria de mudanças de status com data e responsável)
CREATE TABLE IF NOT EXISTS historico_pedidos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pedido_id INT NOT NULL,
    status_anterior VARCHAR(50) DEFAULT NULL,
    status_novo VARCHAR(50) NOT NULL,
    tipo_alteracao VARCHAR(50) NOT NULL DEFAULT 'Status Pedido', -- 'Status Pedido', 'Pagamento', 'Cancelamento', 'Devolução'
    observacao VARCHAR(255) DEFAULT NULL,
    responsavel VARCHAR(100) NOT NULL,
    data_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_hist_pedidos FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE
);


-- 6. Tabela: cancelamentos_devolucoes (solicitações, motivos, responsáveis e aprovações)
CREATE TABLE IF NOT EXISTS cancelamentos_devolucoes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pedido_id INT NOT NULL,
    tipo VARCHAR(30) NOT NULL, -- 'Cancelamento', 'Devolução'
    motivo VARCHAR(255) NOT NULL,
    solicitante VARCHAR(100) NOT NULL,
    status_aprovacao VARCHAR(30) NOT NULL DEFAULT 'Aprovado', -- 'Pendente', 'Aprovado', 'Rejeitado'
    aprovador VARCHAR(100) DEFAULT NULL,
    data_aprovacao DATETIME DEFAULT NULL,
    produtos_conferidos TINYINT(1) NOT NULL DEFAULT 0,
    conferente VARCHAR(100) DEFAULT NULL,
    data_conferencia DATETIME DEFAULT NULL,
    data_solicitacao DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_canc_pedidos FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE
);


-- 7. Tabela: pagamentos_reembolsos (vínculo formal com módulo financeiro)
CREATE TABLE IF NOT EXISTS pagamentos_reembolsos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pedido_id INT NOT NULL,
    tipo VARCHAR(30) NOT NULL, -- 'Pagamento', 'Reembolso', 'Estorno'
    valor DECIMAL(10, 2) NOT NULL,
    forma_pagamento VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'Pendente', -- 'Pendente', 'Confirmado', 'Recusado', 'Reembolsado'
    operacao_id VARCHAR(64) DEFAULT NULL, -- Identificador único da operação para idempotência
    confirmado_por VARCHAR(100) DEFAULT NULL,
    data_confirmacao DATETIME DEFAULT NULL,
    comprovante_ref VARCHAR(100) DEFAULT NULL,
    data_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pag_pedidos FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE,
    UNIQUE KEY uk_pag_operacao (operacao_id)
);

-- Migração idempotente para operacao_id em pagamentos_reembolsos
SET @tablename = "pagamentos_reembolsos";
SET @columnname = "operacao_id";
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, "SELECT 1", "ALTER TABLE pagamentos_reembolsos ADD COLUMN operacao_id VARCHAR(64) DEFAULT NULL AFTER status;"));
PREPARE alterCol FROM @preparedStatement; EXECUTE alterCol; DEALLOCATE PREPARE alterCol;


-- 8. Tabela: perfis (RBAC) com o novo cargo 'Financeiro'
CREATE TABLE IF NOT EXISTS perfis (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(50) NOT NULL UNIQUE,
    descricao VARCHAR(255) NOT NULL
);

INSERT INTO perfis (id, nome, descricao) VALUES
(1, 'Administrador', 'Acesso completo ao sistema e administração de usuários'),
(2, 'Estoque', 'Acesso ao Dashboard, Estoque e Separação/Expedição de Pedidos'),
(3, 'Vendas', 'Acesso ao Dashboard, Estoque, Pedidos e Clientes'),
(4, 'Gerência', 'Acesso operacional completo, supervisão e aprovação de cancelamentos/devoluções'),
(5, 'Financeiro', 'Acesso ao Dashboard, confirmação de pagamentos e reembolsos vinculados aos pedidos')
ON DUPLICATE KEY UPDATE nome = VALUES(nome), descricao = VALUES(descricao);


-- 9. Tabela: usuarios
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    senha_hash VARCHAR(255) NOT NULL,
    perfil_id INT NOT NULL,
    ativo TINYINT(1) NOT NULL DEFAULT 1,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_usuarios_perfis FOREIGN KEY (perfil_id) REFERENCES perfis(id) ON DELETE RESTRICT
);


-- 10. Tabela: movimentacoes_estoque (histórico de auditoria Kardex)
CREATE TABLE IF NOT EXISTS movimentacoes_estoque (
    id INT AUTO_INCREMENT PRIMARY KEY,
    produto_id INT NOT NULL,
    tipo VARCHAR(20) NOT NULL, -- 'Entrada', 'Saída', 'Ajuste', 'Reserva', 'Liberação'
    quantidade INT NOT NULL,
    saldo_anterior INT NOT NULL,
    novo_saldo INT NOT NULL,
    motivo VARCHAR(255) NOT NULL,
    responsavel VARCHAR(100) NOT NULL,
    data_movimentacao DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_mov_produto FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE CASCADE
);


-- 11. Tabela: fornecedores (Módulo Financeiro - Credores e Fornecedores)
CREATE TABLE IF NOT EXISTS fornecedores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    razao_social VARCHAR(150) NOT NULL,
    cnpj_cpf VARCHAR(20) DEFAULT NULL,
    email VARCHAR(150) DEFAULT NULL,
    telefone VARCHAR(50) DEFAULT NULL,
    categoria VARCHAR(100) DEFAULT 'Geral',
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);


-- 12. Tabela: contas_pagar (Módulo Financeiro - Despesas e Títulos a Pagar)
CREATE TABLE IF NOT EXISTS contas_pagar (
    id INT AUTO_INCREMENT PRIMARY KEY,
    descricao VARCHAR(200) NOT NULL,
    fornecedor_id INT DEFAULT NULL,
    categoria VARCHAR(100) NOT NULL DEFAULT 'Operacional',
    valor_original DECIMAL(10, 2) NOT NULL,
    valor_pago DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    data_vencimento DATE NOT NULL,
    data_pagamento DATETIME DEFAULT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'Pendente', -- 'Pendente', 'Parcialmente Pago', 'Pago', 'Cancelado'
    forma_pagamento VARCHAR(50) DEFAULT NULL,
    comprovante VARCHAR(100) DEFAULT NULL,
    responsavel VARCHAR(100) DEFAULT 'Financeiro',
    observacoes TEXT DEFAULT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_contas_fornecedor FOREIGN KEY (fornecedor_id) REFERENCES fornecedores(id) ON DELETE SET NULL
);


-- 13. Tabela: transacoes_caixa (Módulo Financeiro - Movimentações Efetivas de Caixa / Fluxo de Caixa)
CREATE TABLE IF NOT EXISTS transacoes_caixa (
    id INT AUTO_INCREMENT PRIMARY KEY,
    operacao_id VARCHAR(64) NOT NULL UNIQUE, -- Identificador único da operação para impedir duplicidades
    tipo VARCHAR(20) NOT NULL, -- 'Entrada', 'Saída'
    origem VARCHAR(50) NOT NULL, -- 'Pedido', 'Conta a Pagar', 'Avulso', 'Estorno'
    referencia_id INT DEFAULT NULL, -- id do pedido ou da conta a pagar
    valor DECIMAL(10, 2) NOT NULL,
    forma_pagamento VARCHAR(50) NOT NULL DEFAULT 'Outros',
    descricao VARCHAR(255) NOT NULL,
    responsavel VARCHAR(100) NOT NULL,
    data_transacao DATETIME DEFAULT CURRENT_TIMESTAMP
);


-- 14. Tabela: contas_receber (Módulo Financeiro - Integração com Pedidos e Clientes)
CREATE TABLE IF NOT EXISTS contas_receber (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pedido_id INT NOT NULL UNIQUE,
    cliente_id INT DEFAULT NULL,
    valor_original DECIMAL(10, 2) NOT NULL,
    valor_recebido DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    data_vencimento DATE NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'Pendente', -- 'Pendente', 'Parcialmente Pago', 'Pago', 'Cancelado'
    forma_pagamento VARCHAR(50) DEFAULT 'Boleto Bancário',
    observacoes TEXT DEFAULT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_contas_receber_pedido FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE,
    CONSTRAINT fk_contas_receber_cliente FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE SET NULL
);


-- Dados Iniciais / Testes
INSERT INTO produtos (id, codigo, nome, categoria, preco, estoque, estoque_reservado, estoque_minimo) VALUES
(1, 'NOT-001', 'Notebook Gamer', 'Informática', 4500.00, 10, 0, 5),
(2, 'MOU-002', 'Mouse Sem Fio', 'Periféricos', 120.50, 50, 0, 10),
(3, 'TEC-003', 'Teclado Mecânico', 'Periféricos', 350.00, 25, 0, 8),
(4, 'MON-004', 'Monitor 24 Pol', 'Monitores', 899.90, 4, 0, 6)
ON DUPLICATE KEY UPDATE
    codigo = COALESCE(codigo, VALUES(codigo)),
    categoria = COALESCE(categoria, VALUES(categoria)),
    estoque_minimo = COALESCE(estoque_minimo, VALUES(estoque_minimo));

INSERT INTO clientes (id, nome, cpf, email, telefone, cidade, endereco) VALUES
(1, 'Ana Clara Souza', '123.456.789-09', 'ana.souza@email.com', '(11) 98888-1111', 'São Paulo', 'Av. Paulista, 1000 - Bela Vista'),
(2, 'Carlos Eduardo Lima', '987.654.321-00', 'carlos.lima@email.com', '(21) 97777-2222', 'Rio de Janeiro', 'Rua das Laranjeiras, 500')
ON DUPLICATE KEY UPDATE
    cpf = COALESCE(cpf, VALUES(cpf)),
    endereco = COALESCE(endereco, VALUES(endereco));

-- Usuários padrão para teste dos perfis (Senha de todos: admin123)
INSERT INTO usuarios (id, nome, email, senha_hash, perfil_id, ativo) VALUES
(1, 'Administrador do Sistema', 'admin@megavarejo.com', 'scrypt:32768:8:1$GB2ztV7d8JxiRly5$eef19dc47f07f5088d0240ca39e317cbb2e482b6b70b10debc41d4decabdbcbd1f28ad5a7fd7a2bda94f634cc2f362d972dbd935084d0a235fd76cd04d88f6d0', 1, 1),
(2, 'Operador de Estoque', 'estoque@megavarejo.com', 'scrypt:32768:8:1$GB2ztV7d8JxiRly5$eef19dc47f07f5088d0240ca39e317cbb2e482b6b70b10debc41d4decabdbcbd1f28ad5a7fd7a2bda94f634cc2f362d972dbd935084d0a235fd76cd04d88f6d0', 2, 1),
(3, 'Vendedor Comercial', 'vendas@megavarejo.com', 'scrypt:32768:8:1$GB2ztV7d8JxiRly5$eef19dc47f07f5088d0240ca39e317cbb2e482b6b70b10debc41d4decabdbcbd1f28ad5a7fd7a2bda94f634cc2f362d972dbd935084d0a235fd76cd04d88f6d0', 3, 1),
(4, 'Gerente Geral', 'gerencia@megavarejo.com', 'scrypt:32768:8:1$GB2ztV7d8JxiRly5$eef19dc47f07f5088d0240ca39e317cbb2e482b6b70b10debc41d4decabdbcbd1f28ad5a7fd7a2bda94f634cc2f362d972dbd935084d0a235fd76cd04d88f6d0', 4, 1),
(5, 'Analista Financeiro', 'financeiro@megavarejo.com', 'scrypt:32768:8:1$GB2ztV7d8JxiRly5$eef19dc47f07f5088d0240ca39e317cbb2e482b6b70b10debc41d4decabdbcbd1f28ad5a7fd7a2bda94f634cc2f362d972dbd935084d0a235fd76cd04d88f6d0', 5, 1)
ON DUPLICATE KEY UPDATE email=VALUES(email), perfil_id=VALUES(perfil_id), ativo=VALUES(ativo);
