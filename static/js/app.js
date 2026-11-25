// Estado do ERP MegaVarejo S.A.
let usuarioAtual = null;
let produtosCache = [];
let clientesCache = [];
let itensNovoPedido = [];
let perfisCache = [];
let usuariosCache = [];
let filtroAtivoIndicador = null;
let itensNovaCompra = [];
let itensVendaPDV = [];
let compraSelecionadaRecebimento = null;

// Formatar moeda brasileira (BRL)
function formatarMoeda(valor) {
    return Number(valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

// Formatar data no padrão brasileiro (DD/MM/AAAA ou DD/MM/AAAA HH:MM)
function formatarDataBR(valor, incluirHora = true) {
    if (!valor) return '-';

    // Se já estiver no formato brasileiro DD/MM/AAAA ou DD/MM/AAAA HH:MM
    const regexBR = /^\d{2}\/\d{2}\/\d{4}( \d{2}:\d{2}(:\d{2})?)?$/;
    if (typeof valor === 'string' && regexBR.test(valor.trim())) {
        const partes = valor.trim().split(' ');
        if (!incluirHora) return partes[0];
        if (partes.length > 1) {
            const horaMin = partes[1].substring(0, 5);
            return `${partes[0]} ${horaMin}`;
        }
        return partes[0];
    }

    const d = new Date(valor);
    if (isNaN(d.getTime())) return String(valor);

    const dia = String(d.getDate()).padStart(2, '0');
    const mes = String(d.getMonth() + 1).padStart(2, '0');
    const ano = d.getFullYear();

    if (!incluirHora) {
        return `${dia}/${mes}/${ano}`;
    }

    const horas = String(d.getHours()).padStart(2, '0');
    const minutos = String(d.getMinutes()).padStart(2, '0');
    return `${dia}/${mes}/${ano} ${horas}:${minutos}`;
}

/**
 * Retorna a classe CSS adequada para o badge de status do pedido.
 * Utilizada no Dashboard Gerencial e nas listagens de pedidos.
 */
function obterClasseBadge(status) {
    return obterClasseBadgeStatusPedido(status);
}

// Exibir alertas amigáveis na interface
function mostrarAlerta(mensagem, tipo = 'sucesso') {
    const alerta = document.getElementById('alerta');
    alerta.textContent = mensagem;
    alerta.className = `alerta ${tipo}`;
    alerta.style.display = 'block';

    setTimeout(() => {
        alerta.style.display = 'none';
    }, 4500);
}

// ----------------------------------------------------
// CONTROLE DE SESSÃO E RBAC
// ----------------------------------------------------
async function checarAutenticacao() {
    try {
        const res = await fetch('/api/auth/me');
        if (!res.ok) {
            window.location.href = '/login';
            return;
        }

        const data = await res.json();
        usuarioAtual = data.usuario;

        // Atualiza cabeçalho do sidebar
        document.getElementById('sidebar-user-name').textContent = usuarioAtual.nome;
        document.getElementById('sidebar-user-role').textContent = usuarioAtual.perfil;
        document.getElementById('sidebar-avatar').textContent = (usuarioAtual.nome || 'U').charAt(0).toUpperCase();

        // Configura visibilidade do menu lateral com base no RBAC
        aplicarPermissoesMenu(usuarioAtual.permissoes);

        // Abre o primeiro módulo permitido (preferencialmente dashboard)
        if (usuarioAtual.permissoes.includes('dashboard')) {
            navegarPara('dashboard');
        } else if (usuarioAtual.permissoes.length > 0) {
            navegarPara(usuarioAtual.permissoes[0]);
        }
    } catch (err) {
        window.location.href = '/login';
    }
}

function aplicarPermissoesMenu(permissoes) {
    const modulos = ['dashboard', 'produtos', 'pedidos', 'clientes', 'usuarios', 'financeiro', 'logistica', 'compras', 'pdv'];
    modulos.forEach(mod => {
        const btn = document.getElementById(`nav-btn-${mod}`);
        if (btn) {
            if (permissoes.includes(mod)) {
                btn.style.display = 'flex';
            } else {
                btn.style.display = 'none';
            }
        }
    });
}

async function fazerLogout() {
    if (!confirm('Deseja realmente sair do sistema?')) return;
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
        window.location.href = '/login';
    } catch (err) {
        window.location.href = '/login';
    }
}

// Navegação entre os módulos com validação de permissão
function navegarPara(moduloId) {
    // Compatibilidade: se chamado 'estoque', mapeia para o container de tela 'produtos'
    const containerId = moduloId === 'estoque' ? 'produtos' : moduloId;

    if (usuarioAtual && !usuarioAtual.permissoes.includes(moduloId) && !usuarioAtual.permissoes.includes(containerId)) {
        mostrarAlerta(`Você não tem permissão para acessar o módulo ${moduloId}.`, 'erro');
        return;
    }

    // Esconde todos os módulos
    document.querySelectorAll('.modulo').forEach(sec => sec.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));

    // Mostra o selecionado
    const alvo = document.getElementById(`modulo-${containerId}`);
    if (alvo) alvo.classList.add('active');

    // Destaca o botão correspondente no menu
    const btnAtivo = document.getElementById(`nav-btn-${containerId}`);
    if (btnAtivo) btnAtivo.classList.add('active');

    // Carregar dados frescos da tela
    if (containerId === 'dashboard') carregarDashboard();
    if (containerId === 'produtos') carregarModuloEstoque();
    if (containerId === 'pedidos') {
        carregarTransportadorasPedido();
        carregarClientesParaPedido();
        carregarProdutosParaPedido();
        carregarIndicadoresPedidos();
        carregarPedidos();
    }
    if (containerId === 'clientes') carregarClientes();
    if (containerId === 'usuarios') {
        carregarPerfisParaSelect();
        carregarUsuarios();
    }
    if (containerId === 'financeiro') {
        carregarModuloFinanceiro();
    }
    if (containerId === 'logistica') carregarLogistica();
    if (containerId === 'compras') carregarModuloCompras();
    if (containerId === 'pdv') carregarModuloPDV();
}

// ==========================================
// 1. MÓDULO DASHBOARD GERENCIAL (EXCLUSIVO ADMIN / GERÊNCIA)
// ==========================================

let dashAgrupamentoAtual = 'dia';
let dashDadosCarregados = null;

function alternarFiltroPeriodoDashboard() {
    const periodo = document.getElementById('dash-seletor-periodo').value;
    const boxPersonalizado = document.getElementById('dash-datas-personalizadas');
    if (periodo === 'personalizado') {
        boxPersonalizado.style.display = 'flex';
    } else {
        boxPersonalizado.style.display = 'none';
        carregarDashboard();
    }
}

function alterarAgrupamentoGrafico(novoAgrupamento) {
    dashAgrupamentoAtual = novoAgrupamento;
    document.querySelectorAll('.dash-agrupamento-btn-group .btn-outline').forEach(btn => btn.classList.remove('active'));
    const btn = document.getElementById(`btn-agrup-${novoAgrupamento}`);
    if (btn) btn.classList.add('active');
    carregarDashboard();
}

async function carregarDashboard() {
    const loadingElem = document.getElementById('dash-loading');
    const erroBanner = document.getElementById('dash-erro-banner');
    if (loadingElem) loadingElem.style.display = 'flex';
    if (erroBanner) erroBanner.style.display = 'none';

    try {
        const periodo = document.getElementById('dash-seletor-periodo').value;
        let url = `/api/dashboard?periodo=${encodeURIComponent(periodo)}&agrupamento=${encodeURIComponent(dashAgrupamentoAtual)}`;

        if (periodo === 'personalizado') {
            const dtIni = document.getElementById('dash-data-inicio').value;
            const dtFim = document.getElementById('dash-data-fim').value;
            if (dtIni && dtFim) {
                url += `&data_inicio=${encodeURIComponent(dtIni)}&data_fim=${encodeURIComponent(dtFim)}`;
            }
        }

        const res = await fetch(url);
        if (res.status === 401 || res.status === 403) {
            tratarErroAcesso(res);
            return;
        }

        const dados = await res.json();
        if (!res.ok) {
            throw new Error(dados.erro || 'Erro ao consultar indicadores do dashboard.');
        }

        dashDadosCarregados = dados;
        renderizarDashboardGerencial(dados);

    } catch (err) {
        if (erroBanner) {
            erroBanner.textContent = `Falha ao sincronizar dashboard: ${err.message}`;
            erroBanner.style.display = 'block';
        }
        mostrarAlerta(err.message, 'erro');
    } finally {
        if (loadingElem) loadingElem.style.display = 'none';
    }
}

function renderizarDashboardGerencial(d) {
    if (!d) return;

    // 1. Cabeçalho e Meta-informações
    const ultAtElem = document.getElementById('dash-ultima-atualizacao');
    if (ultAtElem && d.periodo) {
        ultAtElem.textContent = `${d.periodo.ultima_atualizacao} (${d.periodo.data_inicio} até ${d.periodo.data_fim})`;
    }

    // 2. Alertas Gerenciais
    if (d.alertas) {
        const al = d.alertas;
        document.getElementById('alerta-pedidos-atrasados').textContent = al.pedidos_atrasados || 0;
        document.getElementById('alerta-estoque-baixo').textContent = al.produtos_estoque_critico || 0;
        document.getElementById('alerta-entregas-atrasadas').textContent = al.entregas_atrasadas || 0;

        const recVenc = al.contas_receber_vencidas || {};
        document.getElementById('alerta-receber-vencidas').textContent = `${recVenc.quantidade || 0} (${formatarMoeda(recVenc.valor || 0)})`;

        const pagVenc = al.contas_pagar_proximas_vencimento || {};
        document.getElementById('alerta-pagar-vencendo').textContent = `${pagVenc.quantidade || 0} (${formatarMoeda(pagVenc.valor || 0)})`;
    }

    // 3. Indicadores Comerciais (KPIs)
    if (d.kpis_comerciais) {
        const k = d.kpis_comerciais;
        document.getElementById('dash-faturamento').textContent = formatarMoeda(k.faturamento || 0);
        document.getElementById('dash-pedidos-qtd').textContent = k.pedidos || 0;
        document.getElementById('dash-ticket-medio').textContent = formatarMoeda(k.ticket_medio || 0);
        document.getElementById('dash-novos-clientes').textContent = k.novos_clientes || 0;

        renderizarBadgeComparativo('dash-faturamento-comp', k.faturamento_variacao_pct, k.faturamento_anterior, true);
        renderizarBadgeComparativo('dash-pedidos-comp', k.pedidos_variacao_pct, k.pedidos_anterior, false);
        renderizarBadgeComparativo('dash-ticket-comp', k.ticket_medio_variacao_pct, k.ticket_medio_anterior, true);
        renderizarBadgeComparativo('dash-clientes-comp', k.novos_clientes_variacao_pct, k.novos_clientes_anterior, false);
    }

    // 4. Resumo Financeiro
    if (d.resumo_financeiro) {
        const f = d.resumo_financeiro;
        document.getElementById('dash-fin-saldo').textContent = formatarMoeda(f.saldo_disponivel_caixa || 0);
        document.getElementById('dash-fin-entradas').textContent = `+ ${formatarMoeda(f.entradas_no_periodo || 0)}`;
        document.getElementById('dash-fin-saidas').textContent = `- ${formatarMoeda(f.saidas_no_periodo || 0)}`;
        document.getElementById('dash-fin-receber').textContent = formatarMoeda(f.contas_receber_aberto || 0);
        document.getElementById('dash-fin-pagar').textContent = formatarMoeda(f.contas_pagar_aberto || 0);
    }

    // 5. Gráficos em Canvas nativo
    renderizarGraficoEvolucaoCanvas(d.grafico_evolucao || []);
    renderizarGraficoStatusCanvas(d.distribuicao_status || []);

    // 6. Operacional (Pedidos Recentes, Mais Vendidos, Entregas)
    if (d.operacional) {
        renderizarTabelaPedidosRecentes(d.operacional.pedidos_recentes || []);
        renderizarTabelaMaisVendidos(d.operacional.produtos_mais_vendidos || []);
        renderizarTabelaEntregas(d.operacional.entregas_em_andamento || []);
    }

    // 7. Atividades Recentes
    renderizarTimelineAtividades(d.atividades_recentes || []);
}

function renderizarBadgeComparativo(elemId, variacaoPct, valorAnt, ehMoeda) {
    const container = document.getElementById(elemId);
    if (!container) return;

    let classe = 'neutro';
    let icone = '➔';
    if (variacaoPct > 0) {
        classe = 'positivo';
        icone = '▲ +';
    } else if (variacaoPct < 0) {
        classe = 'negativo';
        icone = '▼ ';
    }

    const valAntFormatado = ehMoeda ? formatarMoeda(valorAnt) : valorAnt;
    container.innerHTML = `
        <span class="badge-comparativo ${classe}">${icone}${Math.abs(variacaoPct)}%</span>
        <span>vs ant. (${valAntFormatado})</span>
    `;
}

// -------------------------------------------------------------
// RENDERIZAÇÃO DOS GRÁFICOS COM CANVAS NATIVO (HTML5)
// -------------------------------------------------------------
function renderizarGraficoEvolucaoCanvas(dados) {
    const canvas = document.getElementById('canvas-evolucao-faturamento');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width = canvas.parentElement.clientWidth || 600;
    const height = canvas.height = 220;

    ctx.clearRect(0, 0, width, height);

    if (!dados || dados.length === 0) {
        ctx.fillStyle = '#94a3b8';
        ctx.font = '13px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Nenhum dado de faturamento no período selecionado.', width / 2, height / 2);
        return;
    }

    const padding = { top: 30, right: 30, bottom: 40, left: 60 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    const maxValor = Math.max(...dados.map(d => d.faturamento), 100);

    // Linhas de grade e eixos Y
    ctx.strokeStyle = '#f1f5f9';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#94a3b8';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'right';

    for (let i = 0; i <= 4; i++) {
        const yVal = (maxValor / 4) * i;
        const yPos = padding.top + chartH - (i * (chartH / 4));
        ctx.beginPath();
        ctx.moveTo(padding.left, yPos);
        ctx.lineTo(width - padding.right, yPos);
        ctx.stroke();
        ctx.fillText(formatarMoeda(yVal).replace(',00', ''), padding.left - 8, yPos + 4);
    }

    // Desenho de barras e rótulos
    const barSpacing = chartW / dados.length;
    const barWidth = Math.min(36, barSpacing * 0.65);

    dados.forEach((d, idx) => {
        const barH = (d.faturamento / maxValor) * chartH;
        const x = padding.left + (idx * barSpacing) + (barSpacing - barWidth) / 2;
        const y = padding.top + chartH - barH;

        // Barra
        ctx.fillStyle = '#0284c7';
        ctx.beginPath();
        ctx.roundRect ? ctx.roundRect(x, y, barWidth, barH, [4, 4, 0, 0]) : ctx.rect(x, y, barWidth, barH);
        ctx.fill();

        // Rótulo de data no eixo X
        ctx.fillStyle = '#64748b';
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(d.rotulo, x + (barWidth / 2), height - padding.bottom + 18);

        // Valor no topo se houver espaço
        if (barH > 20) {
            ctx.fillStyle = '#0f172a';
            ctx.font = '9px sans-serif';
            ctx.fillText(formatarMoeda(d.faturamento).replace('R$', '').trim(), x + (barWidth / 2), y - 6);
        }
    });
}

function renderizarGraficoStatusCanvas(dados) {
    const canvas = document.getElementById('canvas-distribuicao-status');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width = canvas.parentElement.clientWidth || 300;
    const height = canvas.height = 220;

    ctx.clearRect(0, 0, width, height);

    if (!dados || dados.length === 0) {
        ctx.fillStyle = '#94a3b8';
        ctx.font = '13px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Nenhum pedido no período.', width / 2, height / 2);
        return;
    }

    const cores = {
        'Aguardando Pagamento': '#f59e0b',
        'Confirmado': '#10b981',
        'Aguardando Separação': '#06b6d4',
        'Em Separação': '#3b82f6',
        'Pronto para Envio': '#8b5cf6',
        'Enviado': '#0284c7',
        'Em Transporte': '#6366f1',
        'Entregue': '#15803d',
        'Cancelado': '#ef4444',
        'Devolução Solicitada': '#ec4899',
        'Devolvido': '#64748b',
        'Recusado': '#475569'
    };

    const totalQtd = dados.reduce((acc, cur) => acc + cur.quantidade, 0);
    const centerX = width * 0.38;
    const centerY = height / 2;
    const outerRadius = Math.min(centerX, centerY) - 15;
    const innerRadius = outerRadius * 0.55;

    let startAngle = -0.5 * Math.PI;

    dados.forEach(d => {
        const sliceAngle = (d.quantidade / totalQtd) * (2 * Math.PI);
        const cor = cores[d.status] || '#94a3b8';

        ctx.fillStyle = cor;
        ctx.beginPath();
        ctx.arc(centerX, centerY, outerRadius, startAngle, startAngle + sliceAngle);
        ctx.arc(centerX, centerY, innerRadius, startAngle + sliceAngle, startAngle, true);
        ctx.closePath();
        ctx.fill();

        startAngle += sliceAngle;
    });

    // Legenda lateral
    const legendX = width * 0.68;
    let legendY = 24;
    ctx.textAlign = 'left';
    ctx.font = '11px sans-serif';

    dados.slice(0, 6).forEach(d => {
        const cor = cores[d.status] || '#94a3b8';
        ctx.fillStyle = cor;
        ctx.fillRect(legendX, legendY, 10, 10);

        ctx.fillStyle = '#334155';
        const pct = Math.round((d.quantidade / totalQtd) * 100);
        ctx.fillText(`${d.status}: ${d.quantidade} (${pct}%)`, legendX + 16, legendY + 9);
        legendY += 20;
    });
}

// -------------------------------------------------------------
// TABELAS OPERACIONAIS E AUDITORIA DE ATIVIDADES
// -------------------------------------------------------------
function renderizarTabelaPedidosRecentes(pedidos) {
    const tbody = document.getElementById('dash-tabela-pedidos-recentes');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!pedidos || pedidos.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="texto-vazio">Nenhum pedido recente registrado.</td></tr>';
        return;
    }

    pedidos.forEach(p => {
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.onclick = () => navegarPara('pedidos');
        tr.innerHTML = `
            <td><strong>${p.numero_pedido}</strong></td>
            <td>${p.cliente}</td>
            <td>${p.data}</td>
            <td><strong>${formatarMoeda(p.valor)}</strong></td>
            <td><span class="badge-status-pedido ${obterClasseBadge(p.status)}">${p.status}</span></td>
        `;
        tbody.appendChild(tr);
    });
}

function renderizarTabelaMaisVendidos(produtos) {
    const tbody = document.getElementById('dash-tabela-mais-vendidos');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!produtos || produtos.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="texto-vazio">Nenhum produto vendido no período.</td></tr>';
        return;
    }

    produtos.forEach(p => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${p.nome}</strong></td>
            <td><span class="badge" style="background: #f1f5f9; color: #475569;">${p.categoria}</span></td>
            <td><strong style="color: #0284c7;">${p.quantidade_vendida} un</strong></td>
            <td><strong style="color: #10b981;">${formatarMoeda(p.receita_total)}</strong></td>
        `;
        tbody.appendChild(tr);
    });
}

function renderizarTabelaEntregas(entregas) {
    const tbody = document.getElementById('dash-tabela-entregas');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!entregas || entregas.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="texto-vazio">Nenhuma entrega em trânsito no momento.</td></tr>';
        return;
    }

    entregas.forEach(e => {
        const tr = document.createElement('tr');
        const alertaAtraso = e.atrasado ? '<span style="color: #ef4444; font-weight: bold; margin-left: 4px;">(Atrasado)</span>' : '';
        tr.innerHTML = `
            <td><strong>${e.numero_pedido}</strong></td>
            <td>${e.cliente}<br><small style="color: #64748b;">${e.destino}</small></td>
            <td>${e.previsao_entrega} ${alertaAtraso}</td>
            <td><span class="badge-status-pedido ${obterClasseBadge(e.status)}">${e.status}</span></td>
        `;
        tbody.appendChild(tr);
    });
}

function renderizarTimelineAtividades(atividades) {
    const container = document.getElementById('dash-timeline-atividades');
    if (!container) return;
    container.innerHTML = '';

    if (!atividades || atividades.length === 0) {
        container.innerHTML = '<div class="texto-vazio">Nenhuma atividade registrada recentemente.</div>';
        return;
    }

    atividades.forEach(a => {
        const item = document.createElement('div');
        item.className = 'timeline-item';
        item.innerHTML = `
            <div class="timeline-icone"><svg class="metric-icon" aria-hidden="true"><use href="#icon-clock"></use></svg></div>
            <div class="timeline-corpo">
                <div class="timeline-titulo">${a.titulo}</div>
                <div class="timeline-desc">${a.descricao}</div>
                <div class="timeline-meta">
                    <span>${a.data_formatada}</span>
                    <span>${a.responsavel}</span>
                </div>
            </div>
        `;
        container.appendChild(item);
    });
}

// ==========================================
// 2. MÓDULO ESTOQUE (PRODUTOS, MOVIMENTAÇÕES E AJUSTES)
// ==========================================

function alternarAbaEstoque(subAbaId) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.sub-estoque-content').forEach(content => content.classList.remove('active'));

    const btnSelecionado = event ? event.target : null;
    if (btnSelecionado && btnSelecionado.classList) btnSelecionado.classList.add('active');

    const container = document.getElementById(`sub-estoque-${subAbaId}`);
    if (container) container.classList.add('active');

    if (subAbaId === 'consulta') carregarProdutos();
    if (subAbaId === 'movimentacoes') popularSelectProdutosMovimentacao();
    if (subAbaId === 'ajustes') popularSelectProdutosAjuste();
    if (subAbaId === 'historico') carregarHistoricoMovimentacoes();
    if (subAbaId === 'relatorios') carregarRelatoriosEstoque();
}

async function carregarModuloEstoque() {
    await carregarResumoEstoque();
    await carregarProdutos();
    carregarInteligenciaEstoque();

    // Regra de perfil: Se for Estoquista, oculta campos de preço
    if (usuarioAtual && usuarioAtual.perfil === 'Estoque') {
        const grupoPreco = document.getElementById('grupo-prod-preco');
        if (grupoPreco) {
            const inputPreco = document.getElementById('prod-preco');
            if (inputPreco) {
                inputPreco.required = false;
                inputPreco.value = '0.00';
            }
            grupoPreco.style.display = 'none';
        }
    }
}

async function carregarResumoEstoque() {
    try {
        const res = await fetch('/api/estoque/resumo');
        if (res.status === 401 || res.status === 403) return;
        const dados = await res.json();

        document.getElementById('kpi-estoque-produtos').textContent = dados.total_produtos || 0;
        document.getElementById('kpi-estoque-unidades').textContent = dados.total_unidades || 0;
        document.getElementById('kpi-estoque-criticos').textContent = dados.total_criticos || 0;
    } catch (err) {
        console.error('Erro ao carregar resumo de estoque:', err);
    }
}

async function carregarProdutos() {
    const termoBusca = (document.getElementById('campo-busca-produto')?.value || '').trim();
    const url = termoBusca ? `/api/produtos?busca=${encodeURIComponent(termoBusca)}` : '/api/produtos';

    try {
        const res = await fetch(url);
        if (res.status === 401 || res.status === 403) {
            tratarErroAcesso(res);
            return;
        }
        const produtos = await res.json();
        produtosCache = produtos;

        const tbody = document.getElementById('tabela-produtos-corpo');
        tbody.innerHTML = '';

        if (produtos.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center;">Nenhum produto cadastrado ou encontrado.</td></tr>';
            return;
        }

        produtos.forEach(prod => {
            const tr = document.createElement('tr');
            const isCritico = prod.status_estoque === 'Zerado' || prod.status_estoque === 'Baixo';
            if (isCritico) tr.classList.add('linha-critica');

            let badgeClass = 'badge-estoque-normal';
            if (prod.status_estoque === 'Baixo') badgeClass = 'badge-estoque-baixo';
            if (prod.status_estoque === 'Zerado') badgeClass = 'badge-estoque-zerado';

            const podeExcluir = usuarioAtual && usuarioAtual.perfil !== 'Estoque';

            tr.innerHTML = `
                <td><strong>${prod.codigo || ('#' + prod.id)}</strong></td>
                <td><strong>${prod.nome}</strong></td>
                <td>${prod.categoria || 'Geral'}</td>
                <td>${formatarMoeda(prod.preco)}</td>
                <td><span style="font-weight: 700;">${prod.estoque} un.</span></td>
                <td>${prod.estoque_minimo || 5} un.</td>
                <td><span class="status-badge ${badgeClass}">${prod.status_estoque}</span></td>
                <td>
                    <button class="btn btn-secondary btn-sm" onclick="prepararEdicaoProduto(${prod.id})">Editar</button>
                    ${podeExcluir ? `<button class="btn btn-danger btn-sm" onclick="excluirProduto(${prod.id})">Excluir</button>` : ''}
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        mostrarAlerta('Erro ao listar produtos do estoque.', 'erro');
    }
}

function filtrarProdutos() {
    clearTimeout(window._timeoutBusca);
    window._timeoutBusca = setTimeout(() => {
        carregarProdutos();
    }, 250);
}

async function salvarProduto(event) {
    event.preventDefault();
    const id = document.getElementById('prod-id').value;
    const codigo = document.getElementById('prod-codigo').value.trim();
    const nome = document.getElementById('prod-nome').value.trim();
    const categoria = document.getElementById('prod-categoria').value.trim();
    const preco = parseFloat(document.getElementById('prod-preco')?.value || 0);
    const estoque = parseInt(document.getElementById('prod-estoque')?.value || 0, 10);
    const estoque_minimo = parseInt(document.getElementById('prod-estoque-minimo')?.value || 5, 10);

    const payload = { codigo, nome, categoria, preco, estoque, estoque_minimo };
    const metodo = id ? 'PUT' : 'POST';
    const url = id ? `/api/produtos/${id}` : '/api/produtos';

    try {
        const res = await fetch(url, {
            method: metodo,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok) {
            mostrarAlerta(data.erro || 'Erro ao salvar produto.', 'erro');
            return;
        }

        mostrarAlerta(data.mensagem || 'Produto salvo com sucesso!');
        cancelarEdicaoProduto();
        carregarModuloEstoque();
    } catch (err) {
        mostrarAlerta('Erro de conexão ao salvar produto.', 'erro');
    }
}

function prepararEdicaoProduto(id) {
    const prod = produtosCache.find(p => p.id === id);
    if (!prod) return;

    document.getElementById('prod-id').value = prod.id;
    document.getElementById('prod-codigo').value = prod.codigo || '';
    document.getElementById('prod-nome').value = prod.nome;
    document.getElementById('prod-categoria').value = prod.categoria || 'Geral';
    if (document.getElementById('prod-preco')) document.getElementById('prod-preco').value = prod.preco;
    if (document.getElementById('prod-estoque-minimo')) document.getElementById('prod-estoque-minimo').value = prod.estoque_minimo || 5;

    // Na edição, o campo de estoque inicial fica oculto ou desabilitado para forçar entrada/saída/ajuste
    const grupoEstoque = document.getElementById('grupo-prod-estoque');
    if (grupoEstoque) grupoEstoque.style.display = 'none';

    document.getElementById('form-produto-titulo').textContent = `Editar Produto: ${prod.nome}`;
    document.getElementById('btn-salvar-produto').textContent = 'Atualizar Dados';
    document.getElementById('btn-cancelar-edicao').style.display = 'inline-block';

    // Rola suavemente até o formulário
    document.getElementById('painel-form-produto')?.scrollIntoView({ behavior: 'smooth' });
}

function cancelarEdicaoProduto() {
    document.getElementById('prod-id').value = '';
    document.getElementById('prod-codigo').value = '';
    document.getElementById('prod-nome').value = '';
    document.getElementById('prod-categoria').value = '';
    if (document.getElementById('prod-preco')) document.getElementById('prod-preco').value = '';
    if (document.getElementById('prod-estoque')) document.getElementById('prod-estoque').value = '0';
    if (document.getElementById('prod-estoque-minimo')) document.getElementById('prod-estoque-minimo').value = '5';

    const grupoEstoque = document.getElementById('grupo-prod-estoque');
    if (grupoEstoque) grupoEstoque.style.display = 'flex';

    document.getElementById('form-produto-titulo').textContent = 'Cadastrar Novo Produto';
    document.getElementById('btn-salvar-produto').textContent = 'Salvar Produto';
    document.getElementById('btn-cancelar-edicao').style.display = 'none';
}

async function excluirProduto(id) {
    if (!confirm(`Deseja realmente excluir o produto #${id}?`)) return;

    try {
        const res = await fetch(`/api/produtos/${id}`, { method: 'DELETE' });
        const data = await res.json();

        if (!res.ok) {
            mostrarAlerta(data.erro || 'Erro ao excluir produto.', 'erro');
            return;
        }

        mostrarAlerta(data.mensagem || 'Produto excluído!');
        carregarModuloEstoque();
    } catch (err) {
        mostrarAlerta('Erro de comunicação ao excluir produto.', 'erro');
    }
}

// --- SUB-MÓDULO: ENTRADAS E SAÍDAS ---

function popularSelectProdutosMovimentacao() {
    const select = document.getElementById('mov-produto-id');
    if (!select) return;
    select.innerHTML = '<option value="">-- Selecione o produto --</option>';

    produtosCache.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = `${p.codigo || ('#' + p.id)} - ${p.nome} (Saldo atual: ${p.estoque} un.)`;
        select.appendChild(opt);
    });
    atualizarInfoProdutoMovimentacao();
}

function atualizarInfoProdutoMovimentacao() {
    const prodId = parseInt(document.getElementById('mov-produto-id')?.value, 10);
    const span = document.getElementById('mov-info-saldo');
    if (!span) return;
    const prod = produtosCache.find(p => p.id === prodId);
    span.textContent = prod ? `Saldo Atual no Sistema: ${prod.estoque} un.` : 'Saldo Atual: -';
}

async function executarMovimentacao(e) {
    e.preventDefault();
    const produto_id = parseInt(document.getElementById('mov-produto-id').value, 10);
    const tipo = document.getElementById('mov-tipo').value;
    const quantidade = parseInt(document.getElementById('mov-quantidade').value, 10);
    const motivo = document.getElementById('mov-motivo').value.trim();

    if (!produto_id) {
        mostrarAlerta('Selecione um produto.', 'erro');
        return;
    }

    try {
        const res = await fetch('/api/estoque/movimentacoes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ produto_id, tipo, quantidade, motivo })
        });
        const data = await res.json();
        if (!res.ok) {
            mostrarAlerta(data.erro || 'Falha ao registrar movimentação.', 'erro');
            return;
        }

        mostrarAlerta(data.mensagem);
        document.getElementById('mov-quantidade').value = '1';
        document.getElementById('mov-motivo').value = '';
        await carregarModuloEstoque();
        popularSelectProdutosMovimentacao();
    } catch (err) {
        mostrarAlerta('Erro de conexão ao movimentar estoque.', 'erro');
    }
}

// --- SUB-MÓDULO: AJUSTES DE INVENTÁRIO ---

function popularSelectProdutosAjuste() {
    const select = document.getElementById('ajuste-produto-id');
    if (!select) return;
    select.innerHTML = '<option value="">-- Selecione o produto --</option>';

    produtosCache.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = `${p.codigo || ('#' + p.id)} - ${p.nome} (Saldo registrado: ${p.estoque} un.)`;
        select.appendChild(opt);
    });
    atualizarInfoProdutoAjuste();
}

function atualizarInfoProdutoAjuste() {
    const prodId = parseInt(document.getElementById('ajuste-produto-id')?.value, 10);
    const span = document.getElementById('ajuste-info-saldo');
    if (!span) return;
    const prod = produtosCache.find(p => p.id === prodId);
    span.textContent = prod ? `Saldo Atual no Sistema: ${prod.estoque} un.` : 'Saldo Atual no Sistema: -';
}

async function executarAjuste(e) {
    e.preventDefault();
    const produto_id = parseInt(document.getElementById('ajuste-produto-id').value, 10);
    const novo_saldo = parseInt(document.getElementById('ajuste-novo-saldo').value, 10);
    const justificativa = document.getElementById('ajuste-justificativa').value.trim();

    if (!produto_id) {
        mostrarAlerta('Selecione um produto para ajuste.', 'erro');
        return;
    }

    try {
        const res = await fetch('/api/estoque/ajustes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ produto_id, novo_saldo, justificativa })
        });
        const data = await res.json();
        if (!res.ok) {
            mostrarAlerta(data.erro || 'Falha ao registrar ajuste.', 'erro');
            return;
        }

        mostrarAlerta(data.mensagem);
        document.getElementById('ajuste-novo-saldo').value = '';
        document.getElementById('ajuste-justificativa').value = '';
        await carregarModuloEstoque();
        popularSelectProdutosAjuste();
    } catch (err) {
        mostrarAlerta('Erro de conexão ao ajustar estoque.', 'erro');
    }
}

// --- SUB-MÓDULO: HISTÓRICO DE MOVIMENTAÇÕES ---

async function carregarHistoricoMovimentacoes() {
    const tbody = document.getElementById('tabela-historico-corpo');
    tbody.innerHTML = '<tr><td colspan="9" style="text-align: center;">Carregando histórico...</td></tr>';

    try {
        const res = await fetch('/api/estoque/movimentacoes?limite=100');
        if (!res.ok) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align: center;">Erro ao carregar movimentações.</td></tr>';
            return;
        }
        const historico = await res.json();
        tbody.innerHTML = '';

        if (historico.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align: center;">Nenhuma movimentação registrada até o momento.</td></tr>';
            return;
        }

        historico.forEach(m => {
            const tr = document.createElement('tr');
            let badgeClass = 'badge-tipo-ajuste';
            if (m.tipo === 'Entrada') badgeClass = 'badge-tipo-entrada';
            if (m.tipo === 'Saída') badgeClass = 'badge-tipo-saida';

            tr.innerHTML = `
                <td>#${m.id}</td>
                <td>${m.data_formatada || m.data_movimentacao}</td>
                <td><strong>${m.produto_nome}</strong></td>
                <td><span class="status-badge ${badgeClass}">${m.tipo}</span></td>
                <td><strong>${m.quantidade} un.</strong></td>
                <td>${m.saldo_anterior} un.</td>
                <td><strong>${m.novo_saldo} un.</strong></td>
                <td>${m.motivo}</td>
                <td><small>${m.responsavel}</small></td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align: center;">Erro ao carregar dados do servidor.</td></tr>';
    }
}

// --- SUB-MÓDULO: RELATÓRIOS ---

async function carregarRelatoriosEstoque() {
    const tbodyCriticos = document.getElementById('tabela-rel-criticos');
    const tbodyMaisMov = document.getElementById('tabela-rel-mais-movimentados');

    tbodyCriticos.innerHTML = '<tr><td colspan="5" style="text-align: center;">Carregando...</td></tr>';
    tbodyMaisMov.innerHTML = '<tr><td colspan="4" style="text-align: center;">Carregando...</td></tr>';

    try {
        const [resCriticos, resMaisMov] = await Promise.all([
            fetch('/api/estoque/relatorios/criticos'),
            fetch('/api/estoque/relatorios/mais-movimentados')
        ]);

        const criticos = await resCriticos.json();
        const maisMov = await resMaisMov.json();

        // Renderiza Críticos
        tbodyCriticos.innerHTML = '';
        if (criticos.length === 0) {
            tbodyCriticos.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #166534;">Nenhum produto em nível crítico de estoque. Parabéns!</td></tr>';
        } else {
            criticos.forEach(c => {
                const tr = document.createElement('tr');
                tr.classList.add('linha-critica');
                tr.innerHTML = `
                    <td><strong>${c.codigo || ('#' + c.id)}</strong></td>
                    <td>${c.nome}</td>
                    <td><strong style="color: #dc2626;">${c.estoque} un.</strong></td>
                    <td>${c.estoque_minimo || 5} un.</td>
                    <td><span class="status-badge badge-estoque-zerado">${c.status_estoque}</span></td>
                `;
                tbodyCriticos.appendChild(tr);
            });
        }

        // Renderiza Mais Movimentados
        tbodyMaisMov.innerHTML = '';
        if (maisMov.length === 0) {
            tbodyMaisMov.innerHTML = '<tr><td colspan="4" style="text-align: center;">Nenhuma movimentação registrada ainda.</td></tr>';
        } else {
            maisMov.forEach(m => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${m.codigo || ('#' + m.id)}</strong></td>
                    <td>${m.nome}</td>
                    <td><strong>${m.total_movimentacoes} movimentações</strong></td>
                    <td>${m.total_unidades_movimentadas} unidades totais</td>
                `;
                tbodyMaisMov.appendChild(tr);
            });
        }
    } catch (err) {
        console.error('Erro ao carregar relatórios:', err);
    }
}

// ==========================================
// 3. MÓDULO PEDIDOS
// ==========================================

async function carregarClientesParaPedido() {
    try {
        const res = await fetch('/api/clientes');
        if (!res.ok) return;
        clientesCache = await res.json();

        const select = document.getElementById('pedido-cliente-select');
        if (!select) return;
        select.innerHTML = '<option value="">-- Selecione o cliente --</option>';

        clientesCache.forEach(cli => {
            const opt = document.createElement('option');
            opt.value = cli.id;
            opt.textContent = `${cli.nome} (CPF: ${cli.cpf || 'Não informado'})`;
            select.appendChild(opt);
        });
    } catch (err) {
        mostrarAlerta('Erro ao carregar lista de clientes para o pedido.', 'erro');
    }
}

function aoSelecionarClientePedido() {
    const select = document.getElementById('pedido-cliente-select');
    const clienteId = parseInt(select.value, 10);
    const campoEndereco = document.getElementById('pedido-endereco-entrega');
    if (!clienteId || !campoEndereco) return;

    const cliente = clientesCache.find(c => c.id === clienteId);
    if (cliente && cliente.endereco && cliente.endereco !== '-') {
        campoEndereco.value = cliente.endereco;
    }
}

async function carregarProdutosParaPedido() {
    try {
        const res = await fetch('/api/produtos');
        if (!res.ok) return;
        produtosCache = await res.json();

        const select = document.getElementById('pedido-produto-select');
        if (!select) return;
        select.innerHTML = '<option value="">-- Selecione um produto --</option>';

        produtosCache.forEach(prod => {
            const opt = document.createElement('option');
            opt.value = prod.id;
            const estoqueDisp = prod.estoque_disponivel !== undefined ? prod.estoque_disponivel : prod.estoque;
            opt.textContent = `[${prod.codigo}] ${prod.nome} - ${formatarMoeda(prod.preco)} (Disponível: ${estoqueDisp})`;
            if (estoqueDisp <= 0) {
                opt.disabled = true;
                opt.textContent += ' [Sem estoque livre]';
            }
            select.appendChild(opt);
        });
    } catch (err) {
        mostrarAlerta('Erro ao carregar lista de produtos para o pedido.', 'erro');
    }
}

function atualizarInfoDisponibilidadeProduto() {
    // Pode atualizar algum helper visual se necessário
}

function adicionarItemAoPedido() {
    const select = document.getElementById('pedido-produto-select');
    const produtoId = parseInt(select.value, 10);
    const quantidadeInput = document.getElementById('pedido-quantidade');
    const quantidade = parseInt(quantidadeInput.value, 10);

    if (!produtoId) {
        mostrarAlerta('Por favor, selecione um produto.', 'erro');
        return;
    }

    if (isNaN(quantidade) || quantidade <= 0) {
        mostrarAlerta('Informe uma quantidade válida maior que zero.', 'erro');
        return;
    }

    const produto = produtosCache.find(p => p.id === produtoId);
    if (!produto) return;

    const estoqueDisp = produto.estoque_disponivel !== undefined ? produto.estoque_disponivel : produto.estoque;
    const itemExistente = itensNovoPedido.find(i => i.produto_id === produtoId);
    const qtdTotalDesejada = (itemExistente ? itemExistente.quantidade : 0) + quantidade;

    if (qtdTotalDesejada > estoqueDisp) {
        mostrarAlerta(`Estoque disponível insuficiente para '${produto.nome}'! Livre: ${estoqueDisp}, Tentativa: ${qtdTotalDesejada}.`, 'erro');
        return;
    }

    if (itemExistente) {
        itemExistente.quantidade = qtdTotalDesejada;
        itemExistente.subtotal = itemExistente.quantidade * itemExistente.preco_unitario;
    } else {
        itensNovoPedido.push({
            produto_id: produto.id,
            codigo: produto.codigo,
            nome: produto.nome,
            preco_unitario: produto.preco,
            quantidade: quantidade,
            subtotal: produto.preco * quantidade
        });
    }

    quantidadeInput.value = 1;
    renderizarItensPedido();
    if (document.getElementById('pedido-transportadora')?.value) calcularFretePedido();
}

function removerItemDoPedido(produtoId) {
    itensNovoPedido = itensNovoPedido.filter(i => i.produto_id !== produtoId);
    renderizarItensPedido();
    if (document.getElementById('pedido-transportadora')?.value) calcularFretePedido();
}

function calcularTotaisPedido() {
    const subtotal = itensNovoPedido.reduce((acc, item) => acc + item.subtotal, 0);
    const descontoInput = document.getElementById('pedido-desconto');
    const freteInput = document.getElementById('pedido-frete');

    const desconto = Math.max(0, parseFloat(descontoInput ? descontoInput.value : 0) || 0);
    const frete = Math.max(0, parseFloat(freteInput ? freteInput.value : 0) || 0);

    const total = Math.max(0, subtotal - desconto + frete);

    const subtotalElem = document.getElementById('pedido-subtotal-display');
    const totalElem = document.getElementById('pedido-valor-total');

    if (subtotalElem) subtotalElem.textContent = formatarMoeda(subtotal);
    if (totalElem) totalElem.textContent = formatarMoeda(total);

    return { subtotal, desconto, frete, total };
}

function renderizarItensPedido() {
    const tbody = document.getElementById('tabela-itens-pedido-corpo');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (itensNovoPedido.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #777;">Nenhum item adicionado ainda.</td></tr>';
        calcularTotaisPedido();
        return;
    }

    itensNovoPedido.forEach(item => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${item.codigo || '-'}</strong></td>
            <td>${item.nome}</td>
            <td>${formatarMoeda(item.preco_unitario)}</td>
            <td>${item.quantidade}</td>
            <td>${formatarMoeda(item.subtotal)}</td>
            <td><button type="button" class="btn btn-danger btn-sm" onclick="removerItemDoPedido(${item.produto_id})">✕</button></td>
        `;
        tbody.appendChild(tr);
    });

    calcularTotaisPedido();
}

async function finalizarPedido() {
    if (itensNovoPedido.length === 0) {
        mostrarAlerta('Adicione pelo menos um item ao pedido antes de finalizar.', 'erro');
        return;
    }

    const clienteId = parseInt(document.getElementById('pedido-cliente-select').value, 10);
    if (!clienteId) {
        mostrarAlerta('Por favor, selecione o cliente para o pedido.', 'erro');
        return;
    }

    const { desconto, frete } = calcularTotaisPedido();
    const formaPagamento = document.getElementById('pedido-forma-pagamento').value;
    const dataPrevista = document.getElementById('pedido-data-prevista').value || null;
    const endereco = document.getElementById('pedido-endereco-entrega').value.trim();
    const observacoes = document.getElementById('pedido-observacoes').value.trim();

    const payload = {
        cliente_id: clienteId,
        forma_pagamento: formaPagamento,
        desconto: desconto,
        frete: frete,
        transportadora_id: document.getElementById('pedido-transportadora')?.value || null,
        peso_kg: document.getElementById('pedido-peso')?.value || 0,
        data_prevista_entrega: dataPrevista,
        endereco_entrega: endereco,
        observacoes: observacoes,
        itens: itensNovoPedido.map(i => ({
            produto_id: i.produto_id,
            quantidade: i.quantidade
        }))
    };

    try {
        const res = await fetch('/api/pedidos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok) {
            mostrarAlerta(data.erro || 'Erro ao finalizar pedido.', 'erro');
            return;
        }

        mostrarAlerta(`Pedido ${data.numero_pedido || '#' + data.pedido_id} criado com sucesso! Itens reservados no estoque.`);
        
        // Limpar formulário de novo pedido
        itensNovoPedido = [];
        renderizarItensPedido();
        document.getElementById('pedido-cliente-select').value = '';
        document.getElementById('pedido-endereco-entrega').value = '';
        document.getElementById('pedido-observacoes').value = '';
        document.getElementById('pedido-data-prevista').value = '';
        document.getElementById('pedido-desconto').value = '0.00';
        document.getElementById('pedido-frete').value = '0.00';
        if (document.getElementById('pedido-transportadora')) document.getElementById('pedido-transportadora').value = '';
        if (document.getElementById('pedido-frete')) document.getElementById('pedido-frete').readOnly = false;
        if (document.getElementById('pedido-peso')) document.getElementById('pedido-peso').value = '0';
        if (document.getElementById('pedido-frete-ajuda')) document.getElementById('pedido-frete-ajuda').textContent = 'Selecione uma transportadora para calcular automaticamente.';

        // Atualizar listagem e indicadores
        carregarProdutosParaPedido();
        carregarIndicadoresPedidos();
        carregarPedidos();
    } catch (err) {
        mostrarAlerta('Erro de conexão ao criar pedido.', 'erro');
    }
}

// ----------------------------------------------------
// Indicadores Operacionais Clicáveis
// ----------------------------------------------------
async function carregarIndicadoresPedidos() {
    try {
        const res = await fetch('/api/pedidos/indicadores');
        if (!res.ok) return;
        const ind = await res.json();

        document.getElementById('kpi-pedidos-aguardando-pagamento').textContent = ind.aguardando_pagamento || 0;
        document.getElementById('kpi-pedidos-aguardando-separacao').textContent = ind.aguardando_separacao || 0;
        document.getElementById('kpi-pedidos-em-separacao').textContent = ind.em_separacao || 0;
        document.getElementById('kpi-pedidos-prontos-envio').textContent = ind.prontos_para_envio || 0;
        document.getElementById('kpi-pedidos-atrasados').textContent = ind.atrasados || 0;
    } catch (err) {
        console.error('Erro ao carregar indicadores de pedidos:', err);
    }
}

function filtrarPorIndicador(statusFiltro) {
    const kpiCards = document.querySelectorAll('.card-kpi-pedido');

    // Se já estava ativo o mesmo filtro, desativa
    if (filtroAtivoIndicador === statusFiltro) {
        filtroAtivoIndicador = null;
        kpiCards.forEach(c => c.classList.remove('ativo'));
        document.getElementById('filtro-ped-status').value = '';
        document.getElementById('filtro-ativo-badge').style.display = 'none';
        carregarPedidos();
        return;
    }

    filtroAtivoIndicador = statusFiltro;
    kpiCards.forEach(c => c.classList.remove('ativo'));

    // Destaca o card clicado
    if (statusFiltro === 'Aguardando Pagamento') document.getElementById('kpi-card-aguardando_pagamento').classList.add('ativo');
    if (statusFiltro === 'Aguardando Separação') document.getElementById('kpi-card-aguardando_separacao').classList.add('ativo');
    if (statusFiltro === 'Em Separação') document.getElementById('kpi-card-em_separacao').classList.add('ativo');
    if (statusFiltro === 'Pronto para Envio') document.getElementById('kpi-card-pronto_para_envio').classList.add('ativo');
    if (statusFiltro === 'Atrasados') document.getElementById('kpi-card-atrasados').classList.add('ativo');

    // Atualiza badge de filtro ativo
    const badge = document.getElementById('filtro-ativo-badge');
    badge.textContent = `Filtro ativo: ${statusFiltro}`;
    badge.style.display = 'inline-block';

    if (statusFiltro === 'Atrasados') {
        document.getElementById('filtro-ped-status').value = '';
        carregarPedidos({ apenas_atrasados: true });
    } else {
        document.getElementById('filtro-ped-status').value = statusFiltro;
        carregarPedidos({ status_pedido: statusFiltro });
    }
}

function sePressionarEnterFiltro(event) {
    if (event.key === 'Enter') {
        aplicarFiltrosPedidos();
    }
}

function aplicarFiltrosPedidos() {
    filtroAtivoIndicador = null;
    document.querySelectorAll('.card-kpi-pedido').forEach(c => c.classList.remove('ativo'));
    document.getElementById('filtro-ativo-badge').style.display = 'none';

    const busca = document.getElementById('filtro-ped-busca').value.trim();
    const statusPedido = document.getElementById('filtro-ped-status').value;
    const statusPagamento = document.getElementById('filtro-ped-status-pagamento').value;
    const dataInicio = document.getElementById('filtro-ped-data-inicio').value;
    const dataFim = document.getElementById('filtro-ped-data-fim').value;

    carregarPedidos({
        busca: busca,
        status_pedido: statusPedido,
        status_pagamento: statusPagamento,
        data_inicio: dataInicio,
        data_fim: dataFim
    });
}

function limparFiltrosPedidos() {
    document.getElementById('filtro-ped-busca').value = '';
    document.getElementById('filtro-ped-status').value = '';
    document.getElementById('filtro-ped-status-pagamento').value = '';
    document.getElementById('filtro-ped-data-inicio').value = '';
    document.getElementById('filtro-ped-data-fim').value = '';
    filtroAtivoIndicador = null;
    document.querySelectorAll('.card-kpi-pedido').forEach(c => c.classList.remove('ativo'));
    document.getElementById('filtro-ativo-badge').style.display = 'none';

    carregarPedidos();
}

// ----------------------------------------------------
// Listagem e Renderização de Pedidos
// ----------------------------------------------------
function obterClasseBadgeStatusPedido(status) {
    switch (status) {
        case 'Aguardando Pagamento': return 'badge-ped-aguardando-pagamento';
        case 'Confirmado':           return 'badge-ped-confirmado';
        case 'Aguardando Separação': return 'badge-ped-aguardando-separacao';
        case 'Em Separação':         return 'badge-ped-em-separacao';
        case 'Pronto para Envio':    return 'badge-ped-pronto-para-envio';
        case 'Enviado':              return 'badge-ped-enviado';
        case 'Em Transporte':        return 'badge-ped-em-transporte';
        case 'Entregue':             return 'badge-ped-entregue';
        case 'Cancelado':            return 'badge-ped-cancelado';
        case 'Recusado':             return 'badge-ped-recusado';
        case 'Devolução Solicitada': return 'badge-ped-devolucao-solicitada';
        case 'Devolvido':            return 'badge-ped-devolvido';
        default:                     return 'badge-ped-aguardando-separacao';
    }
}

function obterClasseBadgeStatusPagamento(statusPagamento) {
    switch (statusPagamento) {
        case 'Confirmado':  return 'badge-pag-confirmado';
        case 'Recusado':    return 'badge-pag-recusado';
        case 'Reembolsado': return 'badge-pag-reembolsado';
        case 'Pendente':
        default:            return 'badge-pag-pendente';
    }
}

async function carregarPedidos(filtros = {}) {
    try {
        const params = new URLSearchParams();
        if (filtros.busca) params.append('busca', filtros.busca);
        if (filtros.status_pedido) params.append('status_pedido', filtros.status_pedido);
        if (filtros.status_pagamento) params.append('status_pagamento', filtros.status_pagamento);
        if (filtros.data_inicio) params.append('data_inicio', filtros.data_inicio);
        if (filtros.data_fim) params.append('data_fim', filtros.data_fim);
        if (filtros.apenas_atrasados) params.append('apenas_atrasados', 'true');

        const queryString = params.toString() ? `?${params.toString()}` : '';
        const res = await fetch(`/api/pedidos${queryString}`);

        if (res.status === 401 || res.status === 403) {
            tratarErroAcesso(res);
            return;
        }

        const pedidos = await res.json();
        const tbody = document.getElementById('tabela-pedidos-corpo');
        tbody.innerHTML = '';

        if (!Array.isArray(pedidos) || pedidos.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #64748b;">Nenhum pedido encontrado para os filtros selecionados.</td></tr>';
            return;
        }

        pedidos.forEach(p => {
            const tr = document.createElement('tr');
            if (p.esta_atrasado) {
                tr.style.backgroundColor = '#fff1f2';
            }

            const badgeStatusPed = obterClasseBadgeStatusPedido(p.status);
            const badgeStatusPag = obterClasseBadgeStatusPagamento(p.status_pagamento);
            const dataExibicao = formatarDataBR(p.data_formatada || p.data_pedido, true);

            const avisoAtrasado = p.esta_atrasado ? '<span title="Pedido Atrasado" style="color: #dc2626; margin-left: 4px;"></span>' : '';

            tr.innerHTML = `
                <td><strong>${p.numero_pedido || '#' + p.id}</strong>${avisoAtrasado}</td>
                <td>
                    <div><strong>${p.cliente_nome || 'Consumidor'}</strong></div>
                    <small style="color: #64748b;">CPF: ${p.cliente_cpf || '-'}</small>
                </td>
                <td><small>${dataExibicao}</small></td>
                <td><strong>${formatarMoeda(p.valor_total)}</strong></td>
                <td><span class="badge-status-pedido ${badgeStatusPed}">${p.status}</span></td>
                <td><span class="badge-status-pag ${badgeStatusPag}">${p.status_pagamento}</span></td>
                <td><small>${p.responsavel || '-'}</small></td>
                <td>
                    <button class="btn btn-secondary btn-sm" onclick="verDetalhesPedido(${p.id})"> Detalhes</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        mostrarAlerta('Erro ao carregar histórico de pedidos.', 'erro');
    }
}

// ----------------------------------------------------
// Modal de Detalhes Avançado, Auditoria e Ações por Perfil
// ----------------------------------------------------
async function verDetalhesPedido(id) {
    try {
        const res = await fetch(`/api/pedidos/${id}`);
        const pedido = await res.json();

        if (!res.ok) {
            mostrarAlerta(pedido.erro || 'Erro ao carregar detalhes.', 'erro');
            return;
        }

        document.getElementById('modal-titulo').textContent = `Pedido ${pedido.numero_pedido || '#' + pedido.id}`;

        const dataExibicao = formatarDataBR(pedido.data_formatada || pedido.data_pedido, true);
        const dataPrevistaStr = pedido.data_prevista_entrega ? formatarDataBR(pedido.data_prevista_entrega, false) : 'Não informada';
        const badgePed = obterClasseBadgeStatusPedido(pedido.status);
        const badgePag = obterClasseBadgeStatusPagamento(pedido.status_pagamento);

        let html = `
            <div class="modal-detalhes-grid">
                <div>
                    <div class="modal-section-title">Dados Gerais e Cliente</div>
                    <p><strong>Cliente:</strong> ${pedido.cliente_nome}</p>
                    <p><strong>CPF:</strong> ${pedido.cliente_cpf}</p>
                    <p><strong>Data do Pedido:</strong> ${dataExibicao}</p>
                    <p><strong>Previsão de Entrega:</strong> ${dataPrevistaStr}</p>
                    <p><strong>Endereço de Entrega:</strong> ${pedido.endereco_entrega || '-'}</p>
                    <p><strong>Vendedor / Responsável:</strong> ${pedido.responsavel}</p>
                </div>
                <div>
                    <div class="modal-section-title">Situação e Pagamento</div>
                    <p><strong>Status do Pedido:</strong> <span class="badge-status-pedido ${badgePed}">${pedido.status}</span></p>
                    <p><strong>Status do Pagamento:</strong> <span class="badge-status-pag ${badgePag}">${pedido.status_pagamento}</span></p>
                    <p><strong>Forma de Pagamento:</strong> ${pedido.forma_pagamento}</p>
                    <p><strong>Subtotal:</strong> ${formatarMoeda(pedido.valor_subtotal)}</p>
                    <p><strong>Desconto:</strong> -${formatarMoeda(pedido.desconto)} | <strong>Frete:</strong> +${formatarMoeda(pedido.frete)}</p>
                    <p><strong>Valor Total Líquido:</strong> <strong style="color: #0284c7; font-size: 1.1rem;">${formatarMoeda(pedido.valor_total)}</strong></p>
                </div>
            </div>

            <div class="modal-section-title">Itens do Pedido</div>
            <table class="tabela compact" style="margin-bottom: 20px;">
                <thead>
                    <tr>
                        <th>Produto</th>
                        <th>Preço Unit.</th>
                        <th>Qtd</th>
                        <th>Subtotal</th>
                    </tr>
                </thead>
                <tbody>
        `;

        pedido.itens.forEach(item => {
            html += `
                <tr>
                    <td>${item.produto_nome}</td>
                    <td>${formatarMoeda(item.preco_unitario)}</td>
                    <td>${item.quantidade}</td>
                    <td><strong>${formatarMoeda(item.subtotal)}</strong></td>
                </tr>
            `;
        });

        html += `
                </tbody>
            </table>
        `;

        // Histórico de Alterações / Auditoria
        html += `
            <div class="modal-section-title">Histórico de Alterações (Auditoria)</div>
            <div class="timeline-historico">
        `;

        if (pedido.historico && pedido.historico.length > 0) {
            pedido.historico.forEach(h => {
                const dataHist = formatarDataBR(h.data_registro_formatada || h.data_registro, true);
                html += `
                    <div class="timeline-item">
                        <div><strong>${h.tipo_alteracao || 'Mudança'}:</strong> ${h.status_anterior || '-'} &rarr; <strong>${h.status_novo}</strong></div>
                        <div class="timeline-meta">Por: <em>${h.responsavel}</em> em ${dataHist}</div>
                        ${h.observacao ? `<div style="font-size: 0.8rem; color: #475569; margin-top: 2px;">Obs: ${h.observacao}</div>` : ''}
                    </div>
                `;
            });
        } else {
            html += `<p style="font-size: 0.85rem; color: #64748b;">Nenhuma alteração registrada até o momento.</p>`;
        }

        html += `</div>`;

        // Ações Permitidas com base no RBAC e no Status
        html += renderizarAcoesModalPedido(pedido);

        document.getElementById('modal-corpo').innerHTML = html;
        document.getElementById('modal-detalhes').style.display = 'flex';
    } catch (err) {
        mostrarAlerta('Erro ao carregar detalhes do pedido.', 'erro');
    }
}

function renderizarAcoesModalPedido(pedido) {
    const perfil = usuarioAtual ? usuarioAtual.perfil : '';
    let botoes = '';

    // 1. Confirmação de Pagamento (Financeiro, Gerência, Administrador)
    if (['Financeiro', 'Gerência', 'Administrador'].includes(perfil)) {
        if (pedido.status_pagamento === 'Pendente' && !['Cancelado', 'Devolvido', 'Recusado'].includes(pedido.status)) {
            botoes += `<button type="button" class="btn btn-primary btn-sm" onclick="executarConfirmarPagamento(${pedido.id})"> Confirmar Pagamento</button>`;
        }
    }

    // 2. Mudança de Status do Pedido conforme a máquina de estados e o perfil
    // Estoque: Em Separação, Pronto para Envio, Enviado
    if (['Estoque', 'Gerência', 'Administrador'].includes(perfil)) {
        if (['Confirmado', 'Aguardando Separação'].includes(pedido.status)) {
            botoes += `<button type="button" class="btn btn-secondary btn-sm" onclick="executarAvancoStatus(${pedido.id}, 'Em Separação')"> Iniciar Separação</button>`;
        }
        if (pedido.status === 'Em Separação') {
            botoes += `<button type="button" class="btn btn-secondary btn-sm" onclick="executarAvancoStatus(${pedido.id}, 'Pronto para Envio')"> Pronto para Envio</button>`;
        }
        if (pedido.status === 'Pronto para Envio') {
            botoes += `<button type="button" class="btn btn-secondary btn-sm" onclick="executarAvancoStatus(${pedido.id}, 'Enviado')"> Despachar / Enviado</button>`;
        }
    }

    // Vendas/Gerência/Admin: Em Transporte -> Entregue
    if (['Vendas', 'Gerência', 'Administrador'].includes(perfil)) {
        if (pedido.status === 'Enviado') {
            botoes += `<button type="button" class="btn btn-secondary btn-sm" onclick="executarAvancoStatus(${pedido.id}, 'Em Transporte')"> Em Transporte</button>`;
        }
        if (['Enviado', 'Em Transporte'].includes(pedido.status)) {
            botoes += `<button type="button" class="btn btn-primary btn-sm" onclick="executarAvancoStatus(${pedido.id}, 'Entregue')"> Confirmar Entrega</button>`;
        }
    }

    // 3. Cancelamento (Vendas, Gerência, Admin - apenas antes do envio)
    if (['Vendas', 'Gerência', 'Administrador'].includes(perfil)) {
        if (!['Enviado', 'Em Transporte', 'Entregue', 'Cancelado', 'Devolvido', 'Devolução Solicitada', 'Recusado'].includes(pedido.status)) {
            botoes += `<button type="button" class="btn btn-danger btn-sm" onclick="abrirPromptCancelarPedido(${pedido.id})">✕ Cancelar Pedido</button>`;
        }
    }

    // 4. Solicitação de Devolução (Vendas, Gerência, Admin - apenas se Enviado/Em Transporte/Entregue)
    if (['Vendas', 'Gerência', 'Administrador'].includes(perfil)) {
        if (['Enviado', 'Em Transporte', 'Entregue'].includes(pedido.status)) {
            botoes += `<button type="button" class="btn btn-secondary btn-sm" onclick="abrirPromptDevolucaoPedido(${pedido.id})"> Solicitar Devolução</button>`;
        }
    }

    // 5. Conferência Física de Devolução (Estoque, Gerência, Admin)
    if (['Estoque', 'Gerência', 'Administrador'].includes(perfil)) {
        if (pedido.status === 'Devolução Solicitada') {
            botoes += `<button type="button" class="btn btn-primary btn-sm" onclick="abrirPromptConferirDevolucao(${pedido.id})"> Conferir e Retornar ao Estoque</button>`;
        }
    }

    if (!botoes) return '';

    return `
        <div class="modal-acoes-box">
            <span style="font-size: 0.85rem; font-weight: 600; color: #475569; width: 100%;">Ações Disponíveis:</span>
            ${botoes}
        </div>
    `;
}

// ----------------------------------------------------
// Handlers de Ações em Pedidos
// ----------------------------------------------------
async function executarConfirmarPagamento(pedidoId) {
    if (!confirm('Deseja confirmar o pagamento deste pedido no Financeiro?')) return;
    try {
        const res = await fetch(`/api/pedidos/${pedidoId}/pagamento`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status_pagamento: 'Confirmado' })
        });
        const data = await res.json();
        if (!res.ok) {
            mostrarAlerta(data.erro || 'Erro ao confirmar pagamento.', 'erro');
            return;
        }
        mostrarAlerta(data.mensagem || 'Pagamento confirmado!');
        fecharModal();
        carregarIndicadoresPedidos();
        carregarPedidos();
        // Atualiza também os módulos financeiros se estiverem acessíveis
        if (typeof carregarVisaoGeralFinanceiro === 'function') carregarVisaoGeralFinanceiro();
        if (typeof carregarContasReceber === 'function') carregarContasReceber();
        if (typeof carregarFluxoCaixa === 'function') carregarFluxoCaixa();
    } catch (err) {
        mostrarAlerta('Erro de conexão ao confirmar pagamento.', 'erro');
    }
}

async function executarAvancoStatus(pedidoId, novoStatus) {
    try {
        const res = await fetch(`/api/pedidos/${pedidoId}/status`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: novoStatus })
        });
        const data = await res.json();
        if (!res.ok) {
            mostrarAlerta(data.erro || 'Erro ao atualizar status.', 'erro');
            return;
        }
        mostrarAlerta(data.mensagem || 'Status atualizado com sucesso!');
        fecharModal();
        carregarIndicadoresPedidos();
        carregarPedidos();
    } catch (err) {
        mostrarAlerta('Erro de conexão ao atualizar status.', 'erro');
    }
}

async function abrirPromptCancelarPedido(pedidoId) {
    const motivo = prompt('Informe o motivo do cancelamento do pedido:');
    if (!motivo || !motivo.trim()) return;

    try {
        const res = await fetch(`/api/pedidos/${pedidoId}/cancelar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ motivo: motivo.trim() })
        });
        const data = await res.json();
        if (!res.ok) {
            mostrarAlerta(data.erro || 'Erro ao cancelar pedido.', 'erro');
            return;
        }
        mostrarAlerta(data.mensagem || 'Pedido cancelado e reservas liberadas!');
        fecharModal();
        carregarIndicadoresPedidos();
        carregarPedidos();
    } catch (err) {
        mostrarAlerta('Erro de conexão ao cancelar pedido.', 'erro');
    }
}

async function abrirPromptDevolucaoPedido(pedidoId) {
    const motivo = prompt('Informe o motivo da solicitação de devolução:');
    if (!motivo || !motivo.trim()) return;

    try {
        const res = await fetch(`/api/pedidos/${pedidoId}/devolucao`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ motivo: motivo.trim() })
        });
        const data = await res.json();
        if (!res.ok) {
            mostrarAlerta(data.erro || 'Erro ao solicitar devolução.', 'erro');
            return;
        }
        mostrarAlerta(data.mensagem || 'Devolução solicitada com sucesso!');
        fecharModal();
        carregarIndicadoresPedidos();
        carregarPedidos();
    } catch (err) {
        mostrarAlerta('Erro de conexão ao solicitar devolução.', 'erro');
    }
}

async function abrirPromptConferirDevolucao(pedidoId) {
    const condicao = prompt('Informe a condição física dos produtos recebidos:', 'Mercadorias conferidas em perfeito estado.');
    if (condicao === null) return;

    const retornarAoEstoque = confirm('Deseja reincorporar os produtos ao estoque disponível?\n[OK = Sim / Cancelar = Não]');

    try {
        const res = await fetch(`/api/pedidos/${pedidoId}/conferir-devolucao`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                condicao_itens: condicao.trim(),
                retornar_ao_estoque: retornarAoEstoque
            })
        });
        const data = await res.json();
        if (!res.ok) {
            mostrarAlerta(data.erro || 'Erro ao conferir devolução.', 'erro');
            return;
        }
        mostrarAlerta(data.mensagem || 'Devolução conferida!');
        fecharModal();
        carregarIndicadoresPedidos();
        carregarPedidos();
    } catch (err) {
        mostrarAlerta('Erro de conexão ao conferir devolução.', 'erro');
    }
}

function fecharModal() {
    document.getElementById('modal-detalhes').style.display = 'none';
}

// ==========================================
// 4. MÓDULO CLIENTES
// ==========================================

// Validação visual de CPF no frontend
function validarDigitosCPFJS(cpf) {
    if (!cpf) return false;
    const d = String(cpf).replace(/\D/g, '');
    if (d.length !== 11 || d === d[0].repeat(11)) return false;

    let soma = 0;
    for (let i = 0; i < 9; i++) soma += parseInt(d.charAt(i)) * (10 - i);
    let resto = (soma * 10) % 11;
    if (resto === 10 || resto === 11) resto = 0;
    if (resto !== parseInt(d.charAt(9))) return false;

    soma = 0;
    for (let i = 0; i < 10; i++) soma += parseInt(d.charAt(i)) * (11 - i);
    resto = (soma * 10) % 11;
    if (resto === 10 || resto === 11) resto = 0;
    if (resto !== parseInt(d.charAt(10))) return false;

    return true;
}

function formatarCPFInput(v) {
    v = v.replace(/\D/g, '');
    if (v.length > 11) v = v.substring(0, 11);
    if (v.length > 9) return v.replace(/(\d{3})(\d{3})(\d{3})(\d{1,2})/, '$1.$2.$3-$4');
    if (v.length > 6) return v.replace(/(\d{3})(\d{3})(\d{1,3})/, '$1.$2.$3');
    if (v.length > 3) return v.replace(/(\d{3})(\d{1,3})/, '$1.$2');
    return v;
}

function validarCampoCPFInterface(input) {
    input.value = formatarCPFInput(input.value);
    const feedback = document.getElementById('cli-cpf-feedback');
    if (!feedback) return;

    if (!input.value.trim()) {
        feedback.style.display = 'none';
        return;
    }

    if (validarDigitosCPFJS(input.value)) {
        feedback.textContent = '✓ CPF válido';
        feedback.style.color = '#15803d';
        feedback.style.display = 'block';
    } else {
        feedback.textContent = '✗ CPF inválido (dígitos incorretos)';
        feedback.style.color = '#dc2626';
        feedback.style.display = 'block';
    }
}

let timeoutBuscaClientes = null;
function filtrarClientesAoDigitar() {
    clearTimeout(timeoutBuscaClientes);
    timeoutBuscaClientes = setTimeout(() => {
        const termo = document.getElementById('busca-cliente').value.trim();
        carregarClientes(termo);
    }, 300);
}

async function carregarClientes(busca = '') {
    try {
        const url = busca ? `/api/clientes?busca=${encodeURIComponent(busca)}` : '/api/clientes';
        const res = await fetch(url);
        if (res.status === 401 || res.status === 403) {
            tratarErroAcesso(res);
            return;
        }
        const clientes = await res.json();
        const tbody = document.getElementById('tabela-clientes-corpo');
        tbody.innerHTML = '';

        if (!Array.isArray(clientes) || clientes.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #64748b;">Nenhum cliente encontrado.</td></tr>';
            return;
        }

        clientes.forEach(cli => {
            const tr = document.createElement('tr');
            const totalPed = cli.total_pedidos || 0;
            const badgePed = totalPed > 0 
                ? `<span style="background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 10px; font-weight: 600; font-size: 0.8rem;">${totalPed} pedido(s)</span>`
                : `<span style="color: #94a3b8; font-size: 0.8rem;">0</span>`;

            // Permissões de ação em clientes:
            // - Visualizar: todos com acesso à aba Clientes (Admin, Gerência, Vendas)
            // - Editar: apenas Administrador (Vendas pode cadastrar/consultar; Gerência apenas consulta)
            // - Excluir: apenas Administrador
            const podeEditar = usuarioAtual && usuarioAtual.perfil === 'Administrador';
            const podeExcluir = usuarioAtual && usuarioAtual.perfil === 'Administrador';

            let acaoBotoes = `<button class="btn btn-secondary btn-sm" onclick="verDetalhesCliente(${cli.id})" title="Ver detalhes e pedidos"> Ver</button>`;
            if (podeEditar) {
                acaoBotoes += ` <button class="btn btn-primary btn-sm" onclick="iniciarEdicaoCliente(${cli.id})" title="Editar dados"> Editar</button>`;
            }
            if (podeExcluir) {
                acaoBotoes += ` <button type="button" class="btn btn-danger btn-sm btn-excluir-cliente" onclick="excluirCliente(${cli.id}, '${cli.nome}', ${totalPed})" title="Excluir cliente" aria-label="Excluir cliente"><svg class="inline-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M3 6h18M8 6V4h8v2m3 0-1 14H6L5 6m4 4v6m6-6v6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg><span>Excluir</span></button>`;
            }

            tr.innerHTML = `
                <td>#${cli.id}</td>
                <td><strong>${cli.nome}</strong></td>
                <td><code>${cli.cpf_formatado || cli.cpf || '-'}</code></td>
                <td>${cli.email}</td>
                <td>${cli.telefone || '-'}</td>
                <td>${cli.cidade || '-'}${cli.uf && cli.uf !== '-' ? ' / ' + cli.uf : ''}</td>
                <td>${badgePed}</td>
                <td>${acaoBotoes}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        mostrarAlerta('Erro ao listar clientes.', 'erro');
    }
}

async function salvarCliente(event) {
    event.preventDefault();

    const id = document.getElementById('cli-id').value;
    const nome = document.getElementById('cli-nome').value.trim();
    const cpf = document.getElementById('cli-cpf').value.trim();
    const email = document.getElementById('cli-email').value.trim();
    const telefone = document.getElementById('cli-telefone').value.trim();
    const cep = document.getElementById('cli-cep').value.trim();
    const logradouro = document.getElementById('cli-logradouro').value.trim();
    const numero = document.getElementById('cli-numero').value.trim();
    const complemento = document.getElementById('cli-complemento').value.trim();
    const bairro = document.getElementById('cli-bairro').value.trim();
    const cidade = document.getElementById('cli-cidade').value.trim();
    const uf = document.getElementById('cli-uf').value.trim().toUpperCase();

    // Validação preventiva no frontend
    if (!validarDigitosCPFJS(cpf)) {
        mostrarAlerta('O CPF informado possui dígitos verificadores inválidos.', 'erro');
        return;
    }

    const payload = {
        nome, cpf, email, telefone,
        cep, logradouro, numero, complemento,
        bairro, cidade, uf
    };

    try {
        const url = id ? `/api/clientes/${id}` : '/api/clientes';
        const method = id ? 'PUT' : 'POST';

        const res = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (!res.ok) {
            mostrarAlerta(data.erro || 'Erro ao salvar cliente.', 'erro');
            return;
        }

        mostrarAlerta(data.mensagem || (id ? 'Cliente atualizado!' : 'Cliente cadastrado!'));
        cancelarEdicaoCliente();
        carregarClientes();
        // Atualiza cache de clientes se estiver no modal de pedidos
        carregarClientesParaPedido();
    } catch (err) {
        mostrarAlerta('Erro de conexão ao salvar cliente.', 'erro');
    }
}

async function iniciarEdicaoCliente(id) {
    if (usuarioAtual && usuarioAtual.perfil !== 'Administrador') {
        mostrarAlerta('Apenas o Administrador possui permissão para editar dados cadastrais de clientes.', 'erro');
        return;
    }
    try {
        const res = await fetch(`/api/clientes/${id}`);
        if (!res.ok) {
            mostrarAlerta('Erro ao carregar dados do cliente.', 'erro');
            return;
        }
        const cli = await res.json();

        document.getElementById('cli-id').value = cli.id;
        document.getElementById('cli-nome').value = cli.nome;
        document.getElementById('cli-cpf').value = cli.cpf_formatado || cli.cpf;
        document.getElementById('cli-email').value = cli.email;
        document.getElementById('cli-telefone').value = cli.telefone !== '-' ? cli.telefone : '';
        document.getElementById('cli-cep').value = cli.cep !== '-' ? cli.cep : '';
        document.getElementById('cli-logradouro').value = cli.logradouro !== '-' ? cli.logradouro : '';
        document.getElementById('cli-numero').value = cli.numero !== '-' ? cli.numero : '';
        document.getElementById('cli-complemento').value = cli.complemento || '';
        document.getElementById('cli-bairro').value = cli.bairro !== '-' ? cli.bairro : '';
        document.getElementById('cli-cidade').value = cli.cidade !== '-' ? cli.cidade : '';
        document.getElementById('cli-uf').value = cli.uf !== '-' ? cli.uf : '';

        document.getElementById('form-cliente-titulo').textContent = `Editar Cliente #${cli.id}`;
        document.getElementById('btn-salvar-cliente').textContent = 'Atualizar Cliente';
        document.getElementById('btn-cancelar-edicao-cliente').style.display = 'inline-block';

        validarCampoCPFInterface(document.getElementById('cli-cpf'));
        window.scrollTo({ top: document.getElementById('modulo-clientes').offsetTop, behavior: 'smooth' });
    } catch (err) {
        mostrarAlerta('Erro ao preparar edição do cliente.', 'erro');
    }
}

function cancelarEdicaoCliente() {
    document.getElementById('cli-id').value = '';
    document.getElementById('form-cliente').reset();
    document.getElementById('form-cliente-titulo').textContent = 'Cadastrar Novo Cliente';
    document.getElementById('btn-salvar-cliente').textContent = 'Cadastrar Cliente';
    document.getElementById('btn-cancelar-edicao-cliente').style.display = 'none';
    const feedback = document.getElementById('cli-cpf-feedback');
    if (feedback) feedback.style.display = 'none';
}

async function excluirCliente(id, nome, totalPedidos) {
    if (totalPedidos > 0) {
        alert(`Não é permitido excluir o cliente "${nome}" pois ele possui ${totalPedidos} pedido(s) associado(s).\n\nPara integridade dos dados fiscais e operacionais, clientes com pedidos históricos não podem ser removidos.`);
        return;
    }

    if (!confirm(`Deseja realmente excluir o cadastro do cliente "${nome}"?`)) return;

    try {
        const res = await fetch(`/api/clientes/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (!res.ok) {
            mostrarAlerta(data.erro || 'Erro ao excluir cliente.', 'erro');
            return;
        }
        mostrarAlerta(data.mensagem || 'Cliente excluído com sucesso!');
        carregarClientes();
        carregarClientesParaPedido();
    } catch (err) {
        mostrarAlerta('Erro de conexão ao excluir cliente.', 'erro');
    }
}

async function verDetalhesCliente(id) {
    try {
        const res = await fetch(`/api/clientes/${id}`);
        const cli = await res.json();
        if (!res.ok) {
            mostrarAlerta(cli.erro || 'Erro ao obter dados do cliente.', 'erro');
            return;
        }

        document.getElementById('modal-cliente-titulo').textContent = `Cliente: ${cli.nome}`;

        let html = `
            <div class="modal-detalhes-grid" style="margin-bottom: 16px;">
                <div>
                    <div class="modal-section-title">Dados Pessoais</div>
                    <p><strong>Nome:</strong> ${cli.nome}</p>
                    <p><strong>CPF:</strong> <code>${cli.cpf_formatado || cli.cpf}</code></p>
                    <p><strong>E-mail:</strong> ${cli.email}</p>
                    <p><strong>Telefone:</strong> ${cli.telefone || '-'}</p>
                    <p><strong>Data de Cadastro:</strong> ${cli.criado_em}</p>
                </div>
                <div>
                    <div class="modal-section-title">Endereço Principal de Entrega</div>
                    <p><strong>CEP:</strong> ${cli.cep || '-'}</p>
                    <p><strong>Logradouro:</strong> ${cli.logradouro || '-'}, Nº ${cli.numero || 'S/N'}</p>
                    <p><strong>Complemento:</strong> ${cli.complemento || '-'}</p>
                    <p><strong>Bairro:</strong> ${cli.bairro || '-'}</p>
                    <p><strong>Cidade / UF:</strong> ${cli.cidade || '-'}${cli.uf ? ' / ' + cli.uf : ''}</p>
                    <p><strong>Endereço Formatado:</strong> <em style="color: #475569;">${cli.endereco_completo || cli.endereco || '-'}</em></p>
                </div>
            </div>

            <div class="modal-section-title">Histórico de Pedidos Realizados (${cli.total_pedidos || 0})</div>
        `;

        if (cli.pedidos && cli.pedidos.length > 0) {
            html += `
                <table class="tabela compact">
                    <thead>
                        <tr>
                            <th>Nº Pedido</th>
                            <th>Data</th>
                            <th>Status Pedido</th>
                            <th>Status Pagamento</th>
                            <th>Total</th>
                            <th>Ação</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            cli.pedidos.forEach(p => {
                html += `
                    <tr>
                        <td><strong>${p.numero_pedido || '#' + p.id}</strong></td>
                        <td>${p.data_formatada || p.data_pedido}</td>
                        <td><span class="badge-status-pedido ${obterClasseBadgeStatusPedido(p.status)}">${p.status}</span></td>
                        <td><span class="badge-status-pag ${obterClasseBadgeStatusPagamento(p.status_pagamento)}">${p.status_pagamento}</span></td>
                        <td><strong>${formatarMoeda(p.valor_total)}</strong></td>
                        <td>
                            <button type="button" class="btn btn-secondary btn-sm" onclick="fecharModalCliente(); verDetalhesPedido(${p.id});">Visualizar Pedido</button>
                        </td>
                    </tr>
                `;
            });
            html += `</tbody></table>`;
        } else {
            html += `<p style="color: #64748b; font-size: 0.9rem; padding: 10px 0;">Este cliente ainda não realizou nenhum pedido.</p>`;
        }

        document.getElementById('modal-cliente-corpo').innerHTML = html;
        document.getElementById('modal-detalhes-cliente').style.display = 'flex';
    } catch (err) {
        mostrarAlerta('Erro ao carregar detalhes do cliente.', 'erro');
    }
}

function fecharModalCliente() {
    document.getElementById('modal-detalhes-cliente').style.display = 'none';
}

// ==========================================
// 5. MÓDULO USUÁRIOS (RBAC)
// ==========================================
async function carregarPerfisParaSelect() {
    try {
        const res = await fetch('/api/perfis');
        if (!res.ok) return;
        perfisCache = await res.json();

        const select = document.getElementById('user-perfil');
        select.innerHTML = '<option value="">-- Selecione o Perfil --</option>';

        perfisCache.forEach(perf => {
            const opt = document.createElement('option');
            opt.value = perf.id;
            opt.textContent = `${perf.nome} - ${perf.descricao}`;
            select.appendChild(opt);
        });
    } catch (err) {
        mostrarAlerta('Erro ao carregar perfis de acesso.', 'erro');
    }
}

async function carregarUsuarios() {
    try {
        const res = await fetch('/api/usuarios');
        if (res.status === 401 || res.status === 403) {
            tratarErroAcesso(res);
            return;
        }
        usuariosCache = await res.json();
        const tbody = document.getElementById('tabela-usuarios-corpo');
        tbody.innerHTML = '';

        if (usuariosCache.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center;">Nenhum usuário cadastrado.</td></tr>';
            return;
        }

        usuariosCache.forEach(user => {
            const tr = document.createElement('tr');
            const statusTexto = user.ativo ? 'Ativo' : 'Inativo';
            const statusBadgeClass = user.ativo ? 'badge-ativo' : 'badge-inativo';
            const btnStatusTexto = user.ativo ? 'Desativar' : 'Ativar';
            const btnStatusClass = user.ativo ? 'btn-danger' : 'btn-success';
            const dataCadastro = formatarDataBR(user.criado_em, false);

            tr.innerHTML = `
                <td>#${user.id}</td>
                <td><strong>${user.nome}</strong></td>
                <td>${user.email}</td>
                <td><span class="status-badge badge-perfil">${user.perfil_nome}</span></td>
                <td><span class="status-badge ${statusBadgeClass}">${statusTexto}</span></td>
                <td>
                    <button class="btn btn-secondary btn-sm" onclick="prepararEdicaoUsuario(${user.id})">Editar</button>
                    <button class="btn ${btnStatusClass} btn-sm" onclick="alternarStatusUsuario(${user.id}, ${!user.ativo})">${btnStatusTexto}</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        mostrarAlerta('Erro ao listar usuários do sistema.', 'erro');
    }
}

async function salvarUsuario(event) {
    event.preventDefault();
    const id = document.getElementById('user-id').value;
    const nome = document.getElementById('user-nome').value.trim();
    const email = document.getElementById('user-email').value.trim();
    const perfil_id = parseInt(document.getElementById('user-perfil').value, 10);
    const senha = document.getElementById('user-senha').value;

    const payload = { nome, email, perfil_id };
    if (senha) payload.senha = senha;

    const metodo = id ? 'PUT' : 'POST';
    const url = id ? `/api/usuarios/${id}` : '/api/usuarios';

    try {
        const res = await fetch(url, {
            method: metodo,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok) {
            mostrarAlerta(data.erro || 'Erro ao salvar usuário.', 'erro');
            return;
        }

        mostrarAlerta(data.mensagem || 'Usuário salvo com sucesso!');
        cancelarEdicaoUsuario();
        carregarUsuarios();
    } catch (err) {
        mostrarAlerta('Erro ao conectar ao servidor para salvar usuário.', 'erro');
    }
}

function prepararEdicaoUsuario(id) {
    const user = usuariosCache.find(u => u.id === id);
    if (!user) return;

    document.getElementById('user-id').value = user.id;
    document.getElementById('user-nome').value = user.nome;
    document.getElementById('user-email').value = user.email;
    document.getElementById('user-perfil').value = user.perfil_id;
    document.getElementById('user-senha').value = '';

    document.getElementById('form-usuario-titulo').textContent = `Editar Usuário #${user.id}`;
    document.getElementById('btn-salvar-usuario').textContent = 'Atualizar Usuário';
    document.getElementById('btn-cancelar-edicao-user').style.display = 'inline-block';
    document.getElementById('dica-senha').style.display = 'block';
}

function cancelarEdicaoUsuario() {
    document.getElementById('user-id').value = '';
    document.getElementById('user-nome').value = '';
    document.getElementById('user-email').value = '';
    document.getElementById('user-perfil').value = '';
    document.getElementById('user-senha').value = '';

    document.getElementById('form-usuario-titulo').textContent = 'Cadastrar Novo Usuário';
    document.getElementById('btn-salvar-usuario').textContent = 'Salvar Usuário';
    document.getElementById('btn-cancelar-edicao-user').style.display = 'none';
    document.getElementById('dica-senha').style.display = 'none';
}

async function alternarStatusUsuario(id, novoStatus) {
    const acao = novoStatus ? 'ativar' : 'desativar';
    if (!confirm(`Deseja realmente ${acao} este usuário?`)) return;

    try {
        const res = await fetch(`/api/usuarios/${id}/status`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ativo: novoStatus })
        });

        const data = await res.json();
        if (!res.ok) {
            mostrarAlerta(data.erro || 'Erro ao alterar status.', 'erro');
            return;
        }

        mostrarAlerta(data.mensagem);
        carregarUsuarios();
    } catch (err) {
        mostrarAlerta('Erro de conexão ao alterar status do usuário.', 'erro');
    }
}

async function tratarErroAcesso(resposta) {
    if (resposta.status === 401) {
        window.location.href = '/login';
    } else if (resposta.status === 403) {
        const dados = await resposta.json().catch(() => ({}));
        mostrarAlerta(dados.erro || 'Acesso negado a este recurso.', 'erro');
    }
}

// Iniciar verificando autenticação do usuário

// ==========================================
// 6. MÓDULO FINANCEIRO
// ==========================================

function alternarAbaFinanceiro(subAbaId) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        if (btn.id.startsWith('tab-btn-fin-')) btn.classList.remove('active');
    });
    document.querySelectorAll('.sub-fin-content').forEach(content => {
        content.classList.remove('active');
        content.style.display = 'none';
    });

    const btnAtivo = document.getElementById(`tab-btn-fin-${subAbaId}`);
    if (btnAtivo) btnAtivo.classList.add('active');

    const contentAtivo = document.getElementById(`sub-fin-${subAbaId}`);
    if (contentAtivo) {
        contentAtivo.classList.add('active');
        contentAtivo.style.display = 'block';
    }

    if (subAbaId === 'visao') carregarVisaoGeralFinanceiro();
    if (subAbaId === 'pagar') carregarContasPagar();
    if (subAbaId === 'receber') carregarContasReceber();
    if (subAbaId === 'caixa') carregarFluxoCaixa();
    if (subAbaId === 'fornecedores') carregarFornecedores();
}

function carregarModuloFinanceiro() {
    alternarAbaFinanceiro('visao');
}

// 6.1 Visão Geral
async function carregarVisaoGeralFinanceiro() {
    try {
        const res = await fetch('/api/financeiro/visao-geral');
        if (res.status === 401 || res.status === 403) {
            tratarErroAcesso(res);
            return;
        }
        const d = await res.json();

        document.getElementById('fin-saldo-caixa').textContent = formatarMoeda(d.saldo_disponivel || 0);
        document.getElementById('fin-receitas-totais').textContent = formatarMoeda(d.receitas_totais || 0);
        document.getElementById('fin-despesas-totais').textContent = formatarMoeda(d.despesas_totais || 0);

        const resElem = document.getElementById('fin-resultado-simplificado');
        const resValor = d.resultado_operacional_simplificado || 0;
        resElem.textContent = formatarMoeda(resValor);
        resElem.style.color = resValor >= 0 ? '#10b981' : '#ef4444';

        document.getElementById('fin-receber-pendente').textContent = formatarMoeda(d.contas_a_receber || 0);
        document.getElementById('fin-pagar-pendente').textContent = formatarMoeda(d.contas_a_pagar_pendentes || 0);
    } catch (err) {
        mostrarAlerta('Erro ao carregar visão geral financeira.', 'erro');
    }
}

// 6.2 Contas a Pagar
async function carregarContasPagar() {
    try {
        const status = document.getElementById('filtro-cp-status').value;
        const url = status && status !== 'Todos' ? `/api/financeiro/contas-pagar?status=${encodeURIComponent(status)}` : '/api/financeiro/contas-pagar';
        const res = await fetch(url);
        if (res.status === 401 || res.status === 403) {
            tratarErroAcesso(res);
            return;
        }
        const contas = await res.json();
        const tbody = document.getElementById('tabela-contas-pagar-corpo');
        tbody.innerHTML = '';

        if (!Array.isArray(contas) || contas.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #64748b;">Nenhuma conta a pagar encontrada.</td></tr>';
            return;
        }

        contas.forEach(c => {
            const tr = document.createElement('tr');
            let badgeClass = 'badge-pendente';
            const st = c.status_calculado;
            if (st === 'Pago') badgeClass = 'badge-entregue';
            else if (st === 'Vencido') badgeClass = 'badge-cancelado';
            else if (st === 'Parcialmente Pago') badgeClass = 'badge-separacao';

            const btnAcao = (st !== 'Pago' && st !== 'Cancelado')
                ? `<button class="btn btn-primary btn-sm" onclick="abrirModalBaixaConta(${c.id}, '${c.descricao}', ${c.valor_restante})">Pagar</button>`
                : `<span style="color: #94a3b8; font-size: 0.85rem;">Quitado</span>`;

            tr.innerHTML = `
                <td>#${c.id}</td>
                <td><strong>${c.descricao}</strong></td>
                <td>${c.fornecedor_nome || '-'}</td>
                <td><span style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem;">${c.categoria}</span></td>
                <td>${formatarMoeda(c.valor_original)}</td>
                <td style="color: ${c.valor_restante > 0 ? '#ef4444' : '#10b981'}; font-weight: 600;">${formatarMoeda(c.valor_restante)}</td>
                <td>${c.data_vencimento}</td>
                <td><span class="badge ${badgeClass}">${st}</span></td>
                <td>${btnAcao}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        mostrarAlerta('Erro ao carregar contas a pagar.', 'erro');
    }
}

async function abrirModalNovaContaPagar() {
    // Carrega fornecedores no select
    try {
        const res = await fetch('/api/financeiro/fornecedores');
        if (res.ok) {
            const fornecedores = await res.json();
            const sel = document.getElementById('cp-fornecedor-id');
            sel.innerHTML = '<option value="">Selecione um fornecedor (opcional)</option>';
            fornecedores.forEach(f => {
                const opt = document.createElement('option');
                opt.value = f.id;
                opt.textContent = `${f.razao_social} (${f.cnpj_cpf || 'S/ CPF/CNPJ'})`;
                sel.appendChild(opt);
            });
        }
    } catch (e) {}

    document.getElementById('form-conta-pagar').reset();
    document.getElementById('modal-conta-pagar').style.display = 'block';
}

function fecharModalContaPagar() {
    document.getElementById('modal-conta-pagar').style.display = 'none';
}

async function salvarContaPagar(event) {
    event.preventDefault();
    const descricao = document.getElementById('cp-descricao').value.trim();
    const fornecedor_id = document.getElementById('cp-fornecedor-id').value || null;
    const categoria = document.getElementById('cp-categoria').value.trim();
    const valor = parseFloat(document.getElementById('cp-valor').value);
    const data_vencimento = document.getElementById('cp-vencimento').value;
    const observacoes = document.getElementById('cp-observacoes').value.trim();

    try {
        const res = await fetch('/api/financeiro/contas-pagar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ descricao, fornecedor_id, categoria, valor, data_vencimento, observacoes })
        });
        const data = await res.json();
        if (!res.ok) {
            mostrarAlerta(data.erro || 'Erro ao cadastrar conta.', 'erro');
            return;
        }
        mostrarAlerta(data.mensagem);
        fecharModalContaPagar();
        carregarContasPagar();
    } catch (err) {
        mostrarAlerta('Erro de conexão ao salvar conta.', 'erro');
    }
}

function abrirModalBaixaConta(id, descricao, valorRestante) {
    document.getElementById('baixa-cp-id').value = id;
    document.getElementById('baixa-cp-info').textContent = `Conta #${id} - ${descricao} | Saldo a liquidar: ${formatarMoeda(valorRestante)}`;
    document.getElementById('baixa-cp-valor').value = valorRestante.toFixed(2);
    document.getElementById('baixa-cp-valor').max = valorRestante;
    document.getElementById('baixa-cp-comprovante').value = '';
    document.getElementById('modal-pagar-conta').style.display = 'block';
}

function fecharModalBaixaConta() {
    document.getElementById('modal-pagar-conta').style.display = 'none';
}

async function confirmarPagamentoContaPagar(event) {
    event.preventDefault();
    const id = document.getElementById('baixa-cp-id').value;
    const valor = parseFloat(document.getElementById('baixa-cp-valor').value);
    const forma_pagamento = document.getElementById('baixa-cp-forma').value;
    const comprovante = document.getElementById('baixa-cp-comprovante').value.trim();

    // Gera um identificador único de operação para prevenir requisições duplicadas
    const operacao_id = `CP-UI-${id}-${Date.now()}-${Math.floor(Math.random()*1000000)}`;

    try {
        const res = await fetch(`/api/financeiro/contas-pagar/${id}/pagar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ valor, forma_pagamento, comprovante, operacao_id })
        });
        const data = await res.json();
        if (!res.ok) {
            mostrarAlerta(data.erro || 'Erro ao processar pagamento.', 'erro');
            return;
        }
        mostrarAlerta(data.mensagem);
        fecharModalBaixaConta();
        carregarContasPagar();
        carregarVisaoGeralFinanceiro();
    } catch (err) {
        mostrarAlerta('Erro de conexão ao pagar despesa.', 'erro');
    }
}

// 6.3 Contas a Receber
let timeoutBuscaReceber = null;
function filtrarContasReceber() {
    clearTimeout(timeoutBuscaReceber);
    timeoutBuscaReceber = setTimeout(() => {
        carregarContasReceber();
    }, 300);
}

async function carregarContasReceber() {
    try {
        const busca = document.getElementById('busca-contas-receber').value.trim();
        const url = busca ? `/api/financeiro/contas-receber?busca=${encodeURIComponent(busca)}` : '/api/financeiro/contas-receber';
        const res = await fetch(url);
        if (res.status === 401 || res.status === 403) {
            tratarErroAcesso(res);
            return;
        }
        const contas = await res.json();
        const tbody = document.getElementById('tabela-contas-receber-corpo');
        tbody.innerHTML = '';

        if (!Array.isArray(contas) || contas.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #64748b;">Nenhum valor a receber pendente.</td></tr>';
            return;
        }

        contas.forEach(c => {
            const tr = document.createElement('tr');
            const badgeClass = c.status_calculado === 'Parcialmente Pago' ? 'badge-separacao' : 'badge-pendente';

            tr.innerHTML = `
                <td><strong>${c.numero_pedido}</strong></td>
                <td>${c.cliente_nome}<br><small style="color: #64748b;">CPF: ${c.cliente_cpf}</small></td>
                <td>${c.data_pedido}</td>
                <td>${c.forma_pagamento}</td>
                <td>${formatarMoeda(c.valor_total)}</td>
                <td style="color: #10b981; font-weight: 600;">${formatarMoeda(c.valor_recebido)}</td>
                <td style="color: #ef4444; font-weight: 600;">${formatarMoeda(c.valor_restante)}</td>
                <td><span class="badge ${badgeClass}">${c.status_calculado}</span></td>
                <td>
                    <button class="btn btn-primary btn-sm" onclick="abrirModalRecebimento(${c.pedido_id}, '${c.numero_pedido}', '${c.cliente_nome}', ${c.valor_restante})">Receber</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        mostrarAlerta('Erro ao carregar contas a receber.', 'erro');
    }
}

function abrirModalRecebimento(pedidoId, numeroPedido, clienteNome, saldoRestante) {
    document.getElementById('receber-ped-id').value = pedidoId;
    document.getElementById('receber-ped-info').textContent = `Pedido ${numeroPedido} - ${clienteNome} | Saldo a receber: ${formatarMoeda(saldoRestante)}`;
    document.getElementById('receber-ped-valor').value = saldoRestante.toFixed(2);
    document.getElementById('receber-ped-valor').max = saldoRestante;
    document.getElementById('receber-ped-comprovante').value = '';
    document.getElementById('modal-receber-pedido').style.display = 'block';
}

function fecharModalRecebimento() {
    document.getElementById('modal-receber-pedido').style.display = 'none';
}

async function confirmarRecebimentoPedido(event) {
    event.preventDefault();
    const pedidoId = document.getElementById('receber-ped-id').value;
    const valor = parseFloat(document.getElementById('receber-ped-valor').value);
    const forma_pagamento = document.getElementById('receber-ped-forma').value;
    const comprovante = document.getElementById('receber-ped-comprovante').value.trim();

    // Identificador único da transação para proteção contra pagamentos duplicados
    const operacao_id = `REC-UI-${pedidoId}-${Date.now()}-${Math.floor(Math.random()*1000000)}`;

    try {
        const res = await fetch(`/api/financeiro/contas-receber/${pedidoId}/receber`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ valor, forma_pagamento, comprovante, operacao_id })
        });
        const data = await res.json();
        if (!res.ok) {
            mostrarAlerta(data.erro || 'Erro ao confirmar recebimento.', 'erro');
            return;
        }
        mostrarAlerta(data.mensagem);
        fecharModalRecebimento();
        carregarContasReceber();
        carregarVisaoGeralFinanceiro();
        if (typeof carregarFluxoCaixa === 'function') carregarFluxoCaixa();
        if (typeof carregarPedidos === 'function') carregarPedidos();
        if (typeof carregarIndicadoresPedidos === 'function') carregarIndicadoresPedidos();
    } catch (err) {
        mostrarAlerta('Erro de conexão ao receber valor.', 'erro');
    }
}

// 6.4 Fluxo de Caixa / Transações Efetivas
async function carregarFluxoCaixa() {
    try {
        const tipo = document.getElementById('filtro-caixa-tipo').value;
        const origem = document.getElementById('filtro-caixa-origem').value;
        let params = [];
        if (tipo && tipo !== 'Todos') params.push(`tipo=${encodeURIComponent(tipo)}`);
        if (origem && origem !== 'Todos') params.push(`origem=${encodeURIComponent(origem)}`);
        const qs = params.length > 0 ? `?${params.join('&')}` : '';

        const res = await fetch(`/api/financeiro/fluxo-caixa${qs}`);
        if (res.status === 401 || res.status === 403) {
            tratarErroAcesso(res);
            return;
        }
        const transacoes = await res.json();
        const tbody = document.getElementById('tabela-fluxo-caixa-corpo');
        tbody.innerHTML = '';

        if (!Array.isArray(transacoes) || transacoes.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #64748b;">Nenhuma movimentação de caixa registrada.</td></tr>';
            return;
        }

        transacoes.forEach(t => {
            const tr = document.createElement('tr');
            const isEntrada = t.tipo === 'Entrada';
            const corTipo = isEntrada ? '#10b981' : '#ef4444';
            const sinal = isEntrada ? '+' : '-';

            tr.innerHTML = `
                <td>${t.data_transacao}</td>
                <td><code style="font-size: 0.75rem;">${t.operacao_id}</code></td>
                <td><span style="color: ${corTipo}; font-weight: bold;">${t.tipo}</span></td>
                <td><span style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem;">${t.origem}</span></td>
                <td>${t.descricao}</td>
                <td>${t.forma_pagamento}</td>
                <td style="color: ${corTipo}; font-weight: 600;">${sinal} ${formatarMoeda(t.valor)}</td>
                <td style="font-weight: 600;">${formatarMoeda(t.saldo_resultante)}</td>
                <td>${t.responsavel}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        mostrarAlerta('Erro ao carregar fluxo de caixa.', 'erro');
    }
}

// 6.5 Fornecedores
let timeoutBuscaFornecedor = null;
function filtrarFornecedores() {
    clearTimeout(timeoutBuscaFornecedor);
    timeoutBuscaFornecedor = setTimeout(() => {
        carregarFornecedores();
    }, 300);
}

async function carregarFornecedores() {
    try {
        const busca = document.getElementById('busca-fornecedores').value.trim();
        const url = busca ? `/api/financeiro/fornecedores?busca=${encodeURIComponent(busca)}` : '/api/financeiro/fornecedores';
        const res = await fetch(url);
        if (res.status === 401 || res.status === 403) {
            tratarErroAcesso(res);
            return;
        }
        const fornecedores = await res.json();
        const tbody = document.getElementById('tabela-fornecedores-corpo');
        tbody.innerHTML = '';

        if (!Array.isArray(fornecedores) || fornecedores.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #64748b;">Nenhum fornecedor cadastrado.</td></tr>';
            return;
        }

        fornecedores.forEach(f => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>#${f.id}</td>
                <td><strong>${f.razao_social}</strong></td>
                <td><code>${f.cnpj_cpf}</code></td>
                <td>${f.email}</td>
                <td>${f.telefone}</td>
                <td><span style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem;">${f.categoria}</span></td>
                <td>${f.criado_em}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        mostrarAlerta('Erro ao carregar fornecedores.', 'erro');
    }
}

function abrirModalNovoFornecedor() {
    document.getElementById('form-fornecedor').reset();
    document.getElementById('modal-fornecedor').style.display = 'block';
}

function fecharModalNovoFornecedor() {
    document.getElementById('modal-fornecedor').style.display = 'none';
}

async function salvarFornecedor(event) {
    event.preventDefault();
    const razao_social = document.getElementById('forn-razao').value.trim();
    const cnpj_cpf = document.getElementById('forn-cnpj').value.trim();
    const categoria = document.getElementById('forn-categoria').value.trim();
    const email = document.getElementById('forn-email').value.trim();
    const telefone = document.getElementById('forn-telefone').value.trim();

    try {
        const res = await fetch('/api/financeiro/fornecedores', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ razao_social, cnpj_cpf, categoria, email, telefone })
        });
        const data = await res.json();
        if (!res.ok) {
            mostrarAlerta(data.erro || 'Erro ao cadastrar fornecedor.', 'erro');
            return;
        }
        mostrarAlerta(data.mensagem);
        fecharModalNovoFornecedor();
        carregarFornecedores();
    } catch (err) {
        mostrarAlerta('Erro de conexão ao salvar fornecedor.', 'erro');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    checarAutenticacao();
});


// ==========================================
// COMPRAS, FORNECEDORES E RECEBIMENTO
// ==========================================
async function carregarModuloCompras() {
    await Promise.all([carregarFornecedoresCompra(), carregarCompras()]);
    const res = await fetch('/api/produtos');
    if (res.ok) {
        produtosCache = await res.json();
        const select = document.getElementById('compra-produto');
        if (select) select.innerHTML = '<option value="">Selecione um produto</option>' + produtosCache.map(p => '<option value="' + p.id + '">' + p.codigo + ' - ' + p.nome + '</option>').join('');
    }
}
async function carregarFornecedoresCompra() {
    const res = await fetch('/api/compras/fornecedores');
    if (!res.ok) return;
    const fornecedores = await res.json();
    const select = document.getElementById('compra-fornecedor');
    if (select) select.innerHTML = '<option value="">Selecione um fornecedor</option>' + fornecedores.map(f => '<option value="' + f.id + '">' + f.razao_social + '</option>').join('');
}
async function salvarFornecedorCompra(event) {
    event.preventDefault();
    const payload = {
        razao_social: document.getElementById('forn-razao').value.trim(),
        cnpj_cpf: document.getElementById('forn-documento').value.trim(),
        email: document.getElementById('forn-email').value.trim(),
        telefone: document.getElementById('forn-telefone').value.trim(),
        categoria: document.getElementById('forn-categoria').value.trim() || 'Geral'
    };
    const res = await fetch('/api/compras/fornecedores', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data = await res.json();
    if (!res.ok) return mostrarAlerta(data.erro || 'Não foi possível cadastrar o fornecedor.','erro');
    document.getElementById('form-fornecedor-compra').reset();
    mostrarAlerta(data.mensagem || 'Fornecedor cadastrado.');
    carregarFornecedoresCompra();
}
function adicionarItemCompra() {
    const produtoId = Number(document.getElementById('compra-produto').value);
    const quantidade = Number(document.getElementById('compra-quantidade').value);
    const custo = Number(document.getElementById('compra-custo').value);
    const produto = produtosCache.find(p => Number(p.id) === produtoId);
    if (!produto || !Number.isInteger(quantidade) || quantidade <= 0 || !Number.isFinite(custo) || custo <= 0) return mostrarAlerta('Selecione o produto e informe quantidade e custo válidos.','erro');
    const existente = itensNovaCompra.find(i => i.produto_id === produtoId);
    if (existente) { existente.quantidade += quantidade; existente.custo_unitario = custo; }
    else itensNovaCompra.push({produto_id:produtoId,nome:produto.nome,quantidade,custo_unitario:custo});
    renderizarItensCompra();
}
function removerItemCompra(produtoId) {
    itensNovaCompra = itensNovaCompra.filter(i => i.produto_id !== produtoId);
    renderizarItensCompra();
}
function renderizarItensCompra() {
    const tbody = document.getElementById('tabela-itens-compra');
    if (!tbody) return;
    if (!itensNovaCompra.length) tbody.innerHTML = '<tr><td colspan="5">Nenhum item adicionado.</td></tr>';
    else tbody.innerHTML = itensNovaCompra.map(i => '<tr><td>'+i.nome+'</td><td>'+i.quantidade+'</td><td>'+formatarMoeda(i.custo_unitario)+'</td><td>'+formatarMoeda(i.quantidade*i.custo_unitario)+'</td><td><button class="btn btn-danger btn-sm" onclick="removerItemCompra('+i.produto_id+')">Remover</button></td></tr>').join('');
    const total = itensNovaCompra.reduce((s,i)=>s+i.quantidade*i.custo_unitario,0);
    document.getElementById('compra-total').textContent = formatarMoeda(total);
}
async function criarOrdemCompra() {
    const fornecedorId = Number(document.getElementById('compra-fornecedor').value);
    if (!fornecedorId || !itensNovaCompra.length) return mostrarAlerta('Selecione o fornecedor e adicione produtos à ordem.','erro');
    const payload = {
        fornecedor_id: fornecedorId,
        data_prevista: document.getElementById('compra-previsao').value || null,
        condicao_pagamento: document.getElementById('compra-condicao').value,
        observacoes: document.getElementById('compra-observacoes').value,
        itens: itensNovaCompra.map(i=>({produto_id:i.produto_id,quantidade:i.quantidade,custo_unitario:i.custo_unitario}))
    };
    const res = await fetch('/api/compras',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data = await res.json();
    if (!res.ok) return mostrarAlerta(data.erro || 'Erro ao criar ordem.','erro');
    itensNovaCompra = []; renderizarItensCompra();
    document.getElementById('compra-observacoes').value = '';
    mostrarAlerta(data.mensagem || 'Ordem criada.');
    carregarCompras();
}
async function carregarCompras() {
    const tbody = document.getElementById('tabela-compras');
    if (!tbody) return;
    const res = await fetch('/api/compras');
    if (!res.ok) { tbody.innerHTML='<tr><td colspan="7">Não foi possível carregar as compras.</td></tr>'; return; }
    const compras = await res.json();
    tbody.innerHTML = compras.length ? compras.map(c => '<tr><td><strong>'+c.numero_compra+'</strong></td><td>'+c.fornecedor_nome+'</td><td>'+formatarDataBR(c.data_compra,false)+'</td><td>'+formatarMoeda(c.valor_total)+'</td><td>'+formatarMoeda(c.valor_recebido)+'</td><td><span class="status-badge">'+c.status+'</span></td><td>'+(c.status!=='Recebida' && c.status!=='Cancelada' ? '<button class="btn btn-primary btn-sm" onclick="selecionarCompraRecebimento('+c.id+')">Receber</button>' : '—')+'</td></tr>').join('') : '<tr><td colspan="7">Nenhuma ordem de compra cadastrada.</td></tr>';
    const select = document.getElementById('recebimento-compra');
    if (select) select.innerHTML = '<option value="">Selecione uma ordem</option>' + compras.filter(c=>c.status!=='Recebida' && c.status!=='Cancelada').map(c=>'<option value="'+c.id+'">'+c.numero_compra+' - '+c.fornecedor_nome+'</option>').join('');
}
async function selecionarCompraRecebimento(id) {
    document.getElementById('recebimento-compra').value = id;
    const res = await fetch('/api/compras/'+id);
    const compra = await res.json();
    if (!res.ok) return mostrarAlerta(compra.erro || 'Erro ao carregar ordem.','erro');
    compraSelecionadaRecebimento = compra;
    const pendentes = compra.itens.filter(i=>Number(i.quantidade)>Number(i.quantidade_recebida));
    document.getElementById('recebimento-itens').innerHTML = pendentes.length ? pendentes.map(i => '<div class="recebimento-item"><label>'+i.produto_nome+' — pendente: '+(i.quantidade-i.quantidade_recebida)+' un.</label><input type="number" min="0" max="'+(i.quantidade-i.quantidade_recebida)+'" value="'+(i.quantidade-i.quantidade_recebida)+'" data-item-compra="'+i.id+'" aria-label="Quantidade recebida"></div>').join('') : '<span>Todos os itens já foram recebidos.</span>';
}
async function registrarRecebimentoCompra() {
    const compraId = Number(document.getElementById('recebimento-compra').value);
    if (!compraId) return mostrarAlerta('Selecione uma ordem de compra.','erro');
    if (!compraSelecionadaRecebimento || Number(compraSelecionadaRecebimento.id)!==compraId) await selecionarCompraRecebimento(compraId);
    const itens = Array.from(document.querySelectorAll('[data-item-compra]')).map(el=>({
        item_id:Number(el.dataset.itemCompra),
        quantidade_recebida:Number(el.value),
        data_validade:document.getElementById('recebimento-validade').value || null,
        lote:document.getElementById('recebimento-lote').value || null
    })).filter(i=>i.quantidade_recebida>0);
    if (!itens.length) return mostrarAlerta('Informe ao menos uma quantidade recebida.','erro');
    const payload={itens,data_vencimento:document.getElementById('recebimento-vencimento').value || null};
    const res=await fetch('/api/compras/'+compraId+'/recebimento',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data=await res.json();
    if (!res.ok) return mostrarAlerta(data.erro || 'Erro ao registrar recebimento.','erro');
    mostrarAlerta(data.mensagem || 'Recebimento registrado.');
    compraSelecionadaRecebimento=null;
    document.getElementById('recebimento-itens').innerHTML='<span class="texto-secundario">Selecione uma ordem para carregar os itens pendentes.</span>';
    carregarCompras(); carregarModuloEstoque();
}

// ==========================================
// INTELIGÊNCIA DE ESTOQUE: REPOSIÇÃO E VALIDADE
// ==========================================
async function carregarInteligenciaEstoque() {
    const reposicaoBody=document.getElementById('tabela-reposicao');
    const lotesBody=document.getElementById('tabela-lotes-validade');
    if (!reposicaoBody || !lotesBody) return;
    try {
        const [rr,rl]=await Promise.all([fetch('/api/estoque/reposicao'),fetch('/api/estoque/lotes?dias=30')]);
        const [reposicao,lotes]=await Promise.all([rr.json(),rl.json()]);
        reposicaoBody.innerHTML=reposicao.length ? reposicao.map(p=>'<tr><td><strong>'+p.nome+'</strong></td><td>'+Math.max(0,p.estoque-p.estoque_reservado)+'</td><td>'+p.estoque_minimo+'</td><td><strong>'+p.quantidade_sugerida+' un.</strong></td></tr>').join('') : '<tr><td colspan="4">Nenhum produto precisa de reposição.</td></tr>';
        lotesBody.innerHTML=lotes.length ? lotes.map(l=>'<tr><td>'+l.produto_nome+'</td><td>'+(l.lote||'—')+'</td><td>'+l.quantidade_atual+'</td><td>'+formatarDataBR(l.data_validade,false)+'</td><td><span class="status-badge '+(Number(l.dias_para_vencer)<0?'badge-estoque-zerado':'badge-estoque-baixo')+'">'+(Number(l.dias_para_vencer)<0?'Vencido':Number(l.dias_para_vencer)===0?'Vence hoje':'Em '+l.dias_para_vencer+' dias')+'</span></td></tr>').join('') : '<tr><td colspan="5">Nenhum lote próximo do vencimento.</td></tr>';
    } catch(e) { reposicaoBody.innerHTML='<tr><td colspan="4">Erro ao carregar sugestões.</td></tr>'; }
}

// ==========================================
// FRENTE DE CAIXA / PDV
// ==========================================
async function carregarModuloPDV() {
    const [rp,rc,rl]=await Promise.all([fetch('/api/produtos'),fetch('/api/clientes'),fetch('/api/pdv/caixa')]);
    if (rp.ok) {
        produtosCache=await rp.json();
        const select=document.getElementById('pdv-produto');
        select.innerHTML='<option value="">Selecione um produto</option>'+produtosCache.filter(p=>(p.estoque_disponivel ?? p.estoque)>0).map(p=>'<option value="'+p.id+'">'+p.nome+' — '+formatarMoeda(p.preco)+' (disp. '+(p.estoque_disponivel ?? p.estoque)+')</option>').join('');
    }
    if (rc.ok) {
        clientesCache=await rc.json();
        document.getElementById('pdv-cliente').innerHTML='<option value="">Consumidor final</option>'+clientesCache.map(c=>'<option value="'+c.id+'">'+c.nome+'</option>').join('');
    }
    if (rl.ok) atualizarEstadoCaixaPDV(await rl.json());
    renderizarItensPDV();
}
function atualizarEstadoCaixaPDV(caixa) {
    const aberto=!!caixa;
    document.getElementById('pdv-status-caixa').textContent=aberto?'Aberto':'Fechado';
    document.getElementById('pdv-status-caixa').className=aberto?'pdv-status-aberto':'pdv-status-fechado';
    document.getElementById('pdv-operador-caixa').textContent=aberto?'Abertura: '+formatarDataBR(caixa.aberto_em,true):'Abra o caixa para iniciar as vendas.';
    document.getElementById('pdv-btn-abrir').style.display=aberto?'none':'inline-flex';
    document.getElementById('pdv-btn-fechar').style.display=aberto?'inline-flex':'none';
    document.getElementById('pdv-saldo-caixa').parentElement.querySelector('label').textContent=aberto?'Valor contado no fechamento (R$)':'Saldo inicial do caixa (R$)';
}
async function abrirCaixaPDV() {
    const saldo=Number(document.getElementById('pdv-saldo-caixa').value||0);
    const res=await fetch('/api/pdv/caixa/abrir',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({saldo_inicial:saldo})});
    const data=await res.json();
    if (!res.ok) return mostrarAlerta(data.erro||'Não foi possível abrir o caixa.','erro');
    mostrarAlerta(data.mensagem); carregarModuloPDV();
}
async function fecharCaixaPDV() {
    const saldo=Number(document.getElementById('pdv-saldo-caixa').value||0);
    const res=await fetch('/api/pdv/caixa/fechar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({saldo_informado:saldo})});
    const data=await res.json();
    if (!res.ok) return mostrarAlerta(data.erro||'Não foi possível fechar o caixa.','erro');
    mostrarAlerta(data.mensagem+' Saldo esperado: '+formatarMoeda(data.saldo_sistema)+'. Diferença: '+formatarMoeda(data.diferenca)+'.');
    document.getElementById('pdv-saldo-caixa').value='0'; carregarModuloPDV();
}
function adicionarItemPDV() {
    const id=Number(document.getElementById('pdv-produto').value);
    const qtd=Number(document.getElementById('pdv-quantidade').value);
    const p=produtosCache.find(x=>Number(x.id)===id);
    if (!p || !Number.isInteger(qtd) || qtd<=0) return mostrarAlerta('Selecione um produto e informe uma quantidade válida.','erro');
    const livre=Number(p.estoque_disponivel ?? p.estoque);
    const atual=itensVendaPDV.find(i=>i.produto_id===id);
    if ((atual?atual.quantidade:0)+qtd>livre) return mostrarAlerta('Estoque disponível insuficiente.','erro');
    if (atual) atual.quantidade+=qtd; else itensVendaPDV.push({produto_id:id,nome:p.nome,preco_unitario:Number(p.preco),quantidade:qtd});
    renderizarItensPDV();
}
function removerItemPDV(id) { itensVendaPDV=itensVendaPDV.filter(i=>i.produto_id!==id); renderizarItensPDV(); }
function renderizarItensPDV() {
    const tbody=document.getElementById('pdv-itens'); if(!tbody)return;
    tbody.innerHTML=itensVendaPDV.length?itensVendaPDV.map(i=>'<tr><td>'+i.nome+'</td><td>'+i.quantidade+'</td><td>'+formatarMoeda(i.preco_unitario)+'</td><td>'+formatarMoeda(i.quantidade*i.preco_unitario)+'</td><td><button class="btn btn-danger btn-sm" onclick="removerItemPDV('+i.produto_id+')">Remover</button></td></tr>').join(''):'<tr><td colspan="5">Nenhum produto adicionado.</td></tr>';
    const subtotal=itensVendaPDV.reduce((s,i)=>s+i.quantidade*i.preco_unitario,0);
    const desconto=Math.max(0,Number(document.getElementById('pdv-desconto')?.value||0));
    document.getElementById('pdv-total').textContent=formatarMoeda(Math.max(0,subtotal-desconto));
}
async function concluirVendaPDV() {
    if(!itensVendaPDV.length)return mostrarAlerta('Adicione produtos à venda.','erro');
    const desconto=Math.max(0,Number(document.getElementById('pdv-desconto').value||0));
    const subtotal=itensVendaPDV.reduce((s,i)=>s+i.quantidade*i.preco_unitario,0);
    if(desconto>subtotal)return mostrarAlerta('O desconto não pode superar o subtotal.','erro');
    const payload={cliente_id:document.getElementById('pdv-cliente').value||null,forma_pagamento:document.getElementById('pdv-forma-pagamento').value,desconto,itens:itensVendaPDV.map(i=>({produto_id:i.produto_id,quantidade:i.quantidade}))};
    const btn=document.querySelector('#modulo-pdv .pdv-resumo .btn-primary'); btn.disabled=true; btn.textContent='Processando...';
    try {
        const res=await fetch('/api/pdv/vendas',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
        const data=await res.json();
        if(!res.ok)return mostrarAlerta(data.erro||'Falha ao concluir venda.','erro');
        mostrarAlerta('Venda '+data.numero_pedido+' concluída. Total: '+formatarMoeda(data.valor_total)+'.');
        itensVendaPDV=[]; document.getElementById('pdv-desconto').value='0'; renderizarItensPDV(); carregarModuloPDV(); carregarModuloEstoque();
    } catch(e) { mostrarAlerta('Erro de conexão ao finalizar venda.','erro'); }
    finally { btn.disabled=false; btn.textContent='Finalizar venda'; }
}
