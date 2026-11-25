// Módulo de Logística — interface e operações manuais
let logisticaEntregasCache = [];
let logisticaTransportadorasCache = [];

function escaparLogistica(valor) {
    return String(valor ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

async function carregarTransportadorasPedido() {
    try {
        const res = await fetch('/api/logistica/transportadoras');
        if (!res.ok) return;
        logisticaTransportadorasCache = await res.json();
        const select = document.getElementById('pedido-transportadora');
        if (!select) return;
        const selecionado = select.value;
        select.innerHTML = '<option value="">Frete manual</option>';
        logisticaTransportadorasCache.filter(t => Number(t.ativo)).forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.textContent = t.nome + ' — ' + t.prazo_dias + ' dia(s)';
            select.appendChild(opt);
        });
        select.value = selecionado;
    } catch (e) { console.error('Falha ao carregar transportadoras', e); }
}

async function calcularFretePedido() {
    const select = document.getElementById('pedido-transportadora');
    const peso = document.getElementById('pedido-peso');
    const frete = document.getElementById('pedido-frete');
    const ajuda = document.getElementById('pedido-frete-ajuda');
    if (!select || !select.value) {
        if (frete) frete.readOnly = false;
        if (ajuda) ajuda.textContent = 'Selecione uma transportadora para calcular automaticamente.';
        calcularTotaisPedido();
        return;
    }
    if (frete) frete.readOnly = true;
    const subtotal = itensNovoPedido.reduce((s, i) => s + Number(i.subtotal || 0), 0);
    try {
        const res = await fetch('/api/logistica/cotacao', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({transportadora_id: Number(select.value), subtotal, peso_kg: Number(peso?.value || 0)})
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.erro || 'Não foi possível calcular o frete.');
        frete.value = Number(data.frete).toFixed(2);
        const campoPrevisao = document.getElementById('pedido-data-prevista');
        if (campoPrevisao && !campoPrevisao.value) campoPrevisao.value = data.data_prevista;
        if (ajuda) ajuda.textContent = 'Calculado automaticamente. Prazo estimado: ' + data.prazo_dias + ' dia(s). Previsão sugerida: ' + formatarDataBR(data.data_prevista, false) + '.';
        calcularTotaisPedido();
    } catch (e) {
        if (ajuda) ajuda.textContent = e.message;
        mostrarAlerta(e.message, 'erro');
    }
}

async function carregarLogistica() {
    await Promise.all([carregarTransportadorasLogistica(), carregarEntregasLogistica()]);
}

async function carregarTransportadorasLogistica() {
    const tbody = document.getElementById('log-tabela-transportadoras');
    if (!tbody) return;
    try {
        const res = await fetch('/api/logistica/transportadoras');
        const dados = await res.json();
        if (!res.ok) throw new Error(dados.erro || 'Falha ao carregar transportadoras.');
        logisticaTransportadorasCache = dados;
        tbody.innerHTML = '';
        if (!dados.length) { tbody.innerHTML = '<tr><td colspan="7">Nenhuma transportadora cadastrada.</td></tr>'; return; }
        const podeGerenciarTransportadoras = usuarioAtual && ['Administrador', 'Gerência'].includes(usuarioAtual.perfil);
        const botaoCadastro = document.getElementById('btn-cadastrar-transportadora');
        if (botaoCadastro) botaoCadastro.style.display = podeGerenciarTransportadoras ? 'inline-flex' : 'none';
        dados.forEach(t => {
            const regra = t.modelo_frete === 'PESO' ? 'Por peso' : t.modelo_frete === 'PERCENTUAL' ? 'Percentual' : 'Fixo';
            const adicional = t.modelo_frete === 'PESO' ? formatarMoeda(t.valor_por_kg) + '/kg' : t.modelo_frete === 'PERCENTUAL' ? t.percentual + '%' : '—';
            const tr = document.createElement('tr');
            tr.innerHTML = '<td><strong>' + escaparLogistica(t.nome) + '</strong><br><small>' + escaparLogistica(t.documento || 'Sem documento') + '</small></td>' +
                '<td>' + regra + '</td><td>' + formatarMoeda(t.taxa_fixa) + '</td><td>' + adicional + '</td><td>' + t.prazo_dias + ' dias</td>' +
                '<td><span class="status-badge ' + (Number(t.ativo) ? 'badge-ativo':'badge-inativo') + '">' + (Number(t.ativo) ? 'Ativa':'Inativa') + '</span></td>' +
                '<td>' + (podeGerenciarTransportadoras ? '<button class="btn btn-secondary btn-sm" onclick="editarTransportadora(' + t.id + ')">Editar</button> ' +
                '<button class="btn btn-sm ' + (Number(t.ativo) ? 'btn-danger':'btn-success') + '" onclick="alternarTransportadora(' + t.id + ',' + (Number(t.ativo) ? 'false':'true') + ')">' + (Number(t.ativo) ? 'Desativar':'Ativar') + '</button>' : 'Consulta') + '</td>';
            tbody.appendChild(tr);
        });
    } catch (e) { tbody.innerHTML = '<tr><td colspan="7">' + escaparLogistica(e.message) + '</td></tr>'; }
}

function abrirFormularioTransportadora() {
    document.getElementById('log-form-transportadora').style.display = 'block';
    document.getElementById('log-transp-id').value = '';
    ['nome','documento'].forEach(k => document.getElementById('log-transp-' + k).value = '');
    document.getElementById('log-transp-modelo').value = 'PESO';
    document.getElementById('log-transp-taxa').value = '0';
    document.getElementById('log-transp-kg').value = '0';
    document.getElementById('log-transp-percentual').value = '0';
    document.getElementById('log-transp-minimo').value = '0';
    document.getElementById('log-transp-prazo').value = '5';
    alternarCamposFrete();
}
function fecharFormularioTransportadora() { document.getElementById('log-form-transportadora').style.display = 'none'; }
function alternarCamposFrete() {
    const modelo = document.getElementById('log-transp-modelo')?.value;
    document.getElementById('log-grupo-kg').style.display = modelo === 'PESO' ? 'flex' : 'none';
    document.getElementById('log-grupo-percentual').style.display = modelo === 'PERCENTUAL' ? 'flex' : 'none';
}
function editarTransportadora(id) {
    const t = logisticaTransportadorasCache.find(x => Number(x.id) === Number(id));
    if (!t) return;
    abrirFormularioTransportadora();
    document.getElementById('log-transp-id').value = t.id;
    document.getElementById('log-transp-nome').value = t.nome || '';
    document.getElementById('log-transp-documento').value = t.documento || '';
    document.getElementById('log-transp-modelo').value = t.modelo_frete;
    document.getElementById('log-transp-taxa').value = t.taxa_fixa;
    document.getElementById('log-transp-kg').value = t.valor_por_kg;
    document.getElementById('log-transp-percentual').value = t.percentual;
    document.getElementById('log-transp-minimo').value = t.frete_minimo;
    document.getElementById('log-transp-prazo').value = t.prazo_dias;
    alternarCamposFrete();
    document.getElementById('log-form-transportadora').scrollIntoView({behavior:'smooth'});
}
async function salvarTransportadora() {
    const id = document.getElementById('log-transp-id').value;
    const payload = {
        nome: document.getElementById('log-transp-nome').value.trim(),
        documento: document.getElementById('log-transp-documento').value.trim(),
        modelo_frete: document.getElementById('log-transp-modelo').value,
        taxa_fixa: document.getElementById('log-transp-taxa').value,
        valor_por_kg: document.getElementById('log-transp-kg').value,
        percentual: document.getElementById('log-transp-percentual').value,
        frete_minimo: document.getElementById('log-transp-minimo').value,
        prazo_dias: document.getElementById('log-transp-prazo').value
    };
    try {
        const res = await fetch(id ? '/api/logistica/transportadoras/' + id : '/api/logistica/transportadoras', {
            method: id ? 'PUT':'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.erro || 'Falha ao salvar.');
        mostrarAlerta(data.mensagem); fecharFormularioTransportadora();
        await carregarTransportadorasLogistica(); await carregarTransportadorasPedido();
    } catch(e) { mostrarAlerta(e.message, 'erro'); }
}
async function alternarTransportadora(id, ativo) {
    try {
        const res = await fetch('/api/logistica/transportadoras/' + id + '/ativo', {
            method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ativo})
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.erro || 'Falha ao atualizar.');
        mostrarAlerta(data.mensagem); await carregarTransportadorasLogistica(); await carregarTransportadorasPedido();
    } catch(e) { mostrarAlerta(e.message, 'erro'); }
}

async function carregarEntregasLogistica() {
    const tbody = document.getElementById('log-tabela-entregas');
    if (!tbody) return;
    try {
        const res = await fetch('/api/logistica/entregas');
        const data = await res.json();
        if (!res.ok) throw new Error(data.erro || 'Falha ao carregar entregas.');
        logisticaEntregasCache = data.entregas || [];
        const k = data.indicadores || {};
        document.getElementById('log-kpi-expedicao').textContent = k.aguardando_expedicao || 0;
        document.getElementById('log-kpi-transporte').textContent = k.em_transporte || 0;
        document.getElementById('log-kpi-entregues').textContent = k.entregues || 0;
        document.getElementById('log-kpi-atrasadas').textContent = k.atrasadas || 0;
        renderizarEntregasLogistica();
    } catch(e) { tbody.innerHTML = '<tr><td colspan="8">' + escaparLogistica(e.message) + '</td></tr>'; }
}
function renderizarEntregasLogistica() {
    const tbody = document.getElementById('log-tabela-entregas');
    if (!tbody) return;
    const status = document.getElementById('log-filtro-status')?.value || '';
    const busca = (document.getElementById('log-filtro-busca')?.value || '').toLowerCase();
    const atrasadas = document.getElementById('log-filtro-atrasadas')?.checked || false;
    const rows = logisticaEntregasCache.filter(e =>
        (!status || e.status_pedido === status) &&
        (!busca || (e.numero_pedido + ' ' + e.cliente).toLowerCase().includes(busca)) &&
        (!atrasadas || e.atrasado)
    );
    tbody.innerHTML = '';
    if (!rows.length) { tbody.innerHTML = '<tr><td colspan="8">Nenhuma entrega encontrada para os filtros selecionados.</td></tr>'; return; }
    rows.forEach(e => {
        const prazo = e.atrasado ? '<span class="status-badge badge-inativo">Atrasada</span>' :
            e.status_pedido === 'Entregue' ? '<span class="status-badge badge-ativo">Concluída</span>' :
            '<span class="status-badge badge-perfil">No prazo</span>';
        let acoes = '';
        if (e.status_pedido === 'Pronto para Envio') {
            if (e.transportadora) acoes = '<button class="btn btn-primary btn-sm" onclick="registrarEtapaEntrega(' + e.pedido_id + ',\'Enviado\')">Marcar como enviado</button> <button class="btn btn-secondary btn-sm" onclick="abrirConfiguracaoEntrega(' + e.pedido_id + ')">Editar dados</button>';
            else acoes = '<button class="btn btn-primary btn-sm" onclick="abrirConfiguracaoEntrega(' + e.pedido_id + ')">Configurar envio</button>';
        }
        else if (e.status_pedido === 'Enviado') acoes = '<button class="btn btn-secondary btn-sm" onclick="registrarEtapaEntrega(' + e.pedido_id + ',\'Em Transporte\')">Registrar transporte</button>';
        else if (e.status_pedido === 'Em Transporte') acoes = '<button class="btn btn-success btn-sm" onclick="registrarEtapaEntrega(' + e.pedido_id + ',\'Entregue\')">Confirmar entrega</button>';
        else acoes = '<button class="btn btn-secondary btn-sm" onclick="abrirConfiguracaoEntrega(' + e.pedido_id + ')">Ver dados</button>';
        const tr = document.createElement('tr');
        tr.innerHTML = '<td><strong>' + escaparLogistica(e.numero_pedido) + '</strong></td><td>' + escaparLogistica(e.cliente) + '</td>' +
            '<td>' + escaparLogistica(e.transportadora || 'Não definida') + '</td><td>' + formatarMoeda(e.valor_frete) + '</td>' +
            '<td>' + formatarDataBR(e.previsao_logistica || e.data_prevista_entrega, false) + '</td>' +
            '<td><span class="badge-status-pedido">' + escaparLogistica(e.status_pedido) + '</span></td><td>' + prazo + '</td><td>' + acoes + '</td>';
        tbody.appendChild(tr);
    });
}
function abrirConfiguracaoEntrega(pedidoId) {
    const entrega = logisticaEntregasCache.find(e => Number(e.pedido_id) === Number(pedidoId));
    if (!entrega) return;
    document.getElementById('log-entrega-pedido-id').value = pedidoId;
    document.getElementById('log-entrega-pedido-label').textContent = entrega.numero_pedido + ' — ' + entrega.cliente;
    const select = document.getElementById('log-entrega-transportadora');
    select.innerHTML = '<option value="">Selecione</option>';
    logisticaTransportadorasCache.filter(t => Number(t.ativo)).forEach(t => {
        const o = document.createElement('option'); o.value = t.id; o.textContent = t.nome; select.appendChild(o);
    });
    const t = logisticaTransportadorasCache.find(x => x.nome === entrega.transportadora);
    select.value = t ? t.id : '';
    document.getElementById('log-entrega-peso').value = entrega.peso_kg || 0;
    document.getElementById('log-entrega-frete').value = Number(entrega.valor_frete || 0).toFixed(2);
    document.getElementById('log-entrega-rastreio').value = entrega.codigo_rastreamento || '';
    document.getElementById('log-entrega-previsao').value = (entrega.previsao_logistica || entrega.data_prevista_entrega || '').slice(0,10);
    document.getElementById('log-entrega-observacoes').value = entrega.observacoes_logistica || '';
    document.getElementById('modal-logistica').style.display = 'flex';
}
function fecharModalLogistica() { document.getElementById('modal-logistica').style.display = 'none'; }
async function salvarConfiguracaoEntrega() {
    const id = document.getElementById('log-entrega-pedido-id').value;
    const payload = {
        transportadora_id: document.getElementById('log-entrega-transportadora').value || null,
        peso_kg: document.getElementById('log-entrega-peso').value,
        valor_frete: document.getElementById('log-entrega-frete').value,
        codigo_rastreamento: document.getElementById('log-entrega-rastreio').value.trim(),
        data_prevista: document.getElementById('log-entrega-previsao').value || null,
        observacoes: document.getElementById('log-entrega-observacoes').value.trim()
    };
    try {
        const res = await fetch('/api/logistica/entregas/' + id, {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
        const data = await res.json();
        if (!res.ok) throw new Error(data.erro || 'Falha ao salvar entrega.');
        mostrarAlerta(data.mensagem); fecharModalLogistica(); await carregarLogistica();
    } catch(e) { mostrarAlerta(e.message,'erro'); }
}
async function registrarEtapaEntrega(pedidoId, status) {
    try {
        const res = await fetch('/api/logistica/entregas/' + pedidoId + '/status', {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({status, observacoes: ''})
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.erro || 'Falha ao atualizar etapa.');
        mostrarAlerta(data.mensagem || 'Etapa registrada.');
        await carregarLogistica();
        if (typeof carregarIndicadoresPedidos === 'function') carregarIndicadoresPedidos();
        if (typeof carregarPedidos === 'function') carregarPedidos();
    } catch (e) {
        mostrarAlerta(e.message, 'erro');
    }
}
