/* 知识图谱（hero 页）：ECharts 力导向图 = 星座。
 * 节点按实体类型着色（星温色阶），边为连线；点击节点弹「证据即引文」抽屉。
 */
window.Views = window.Views || {};

window.Views.Graph = {
  name: 'GraphView',
  template: `
    <div class="graph">
      <div class="graph__toolbar">
        <span class="readout">NODES <b style="color:var(--text)">{{ overview.total_nodes }}</b> · EDGES <b style="color:var(--text)">{{ overview.total_edges }}</b>{{ overview.sampled ? ' · SAMPLED' : '' }}</span>
        <input class="input" v-model="query" @keyup.enter="locateNode" placeholder="定位实体名…" style="width:200px;padding:7px 11px;font-size:13px" />
        <button class="btn btn--sm" @click="setLayout('force')" :class="{'btn--primary': layout==='force'}">力导向</button>
        <button class="btn btn--sm" @click="setLayout('circular')" :class="{'btn--primary': layout==='circular'}">环形</button>
        <button class="btn btn--ghost btn--sm" @click="loadOverview">刷新</button>
      </div>

      <div class="graph__canvas" ref="canvas">
        <div class="graph__legend" v-if="categories.length">
          <div class="eyebrow" style="margin-bottom:2px">图例</div>
          <div class="lg-item" v-for="c in categories" :key="c.id" :class="{ off: hiddenTypes.includes(c.name) }" @click="toggleType(c.name)">
            <span class="dot" :style="{ background: typeColor(c.name) }"></span>
            <span>{{ c.name }}</span>
          </div>
        </div>
        <div v-if="empty" class="empty" style="height:100%">
          <div class="glyph">✦</div>
          <p>图谱还是空的。</p>
          <p style="font-size:12.5px;max-width:320px">先上传一篇文档并等待解析完成，这里会亮起实体（点）与关系（线）。若解析已完成仍为空，请确认后端已接入真实抽取引擎。</p>
        </div>
        <div class="graph__hint">滚轮缩放 · 拖拽平移 · 点击节点看详情</div>
      </div>

      <!-- 实体详情抽屉：证据即引文 -->
      <div v-if="drawer">
        <div class="overlay" @click="drawer = null"></div>
        <div class="drawer">
          <div class="drawer__head">
            <div>
              <h2>{{ drawer.entity.name }}</h2>
              <div class="type-line">
                <span class="dot" style="width:9px;height:9px;border-radius:50%;display:inline-block" :style="{ background: drawer.entity.type.color || typeColor(drawer.entity.type.name) }"></span>
                {{ drawer.entity.type.name }}
                <span class="mono">· 频次 {{ drawer.entity.frequency }}</span>
              </div>
            </div>
            <button class="btn btn--ghost btn--icon" @click="drawer = null" title="关闭">✕</button>
          </div>
          <div class="drawer__body">
            <template v-if="drawer.relations.length">
              <h4>关联（{{ drawer.relations.length }}）</h4>
              <div class="rel-item" v-for="r in drawer.relations" :key="r.id" @click="openEntity(r.other.id)">
                <span class="rel-type">{{ r.relation_type_name }}</span>
                <span class="rel-name">{{ r.other.name }}</span>
                <span class="rel-dir">{{ r.direction === 'out' ? '→' : '←' }}</span>
              </div>
            </template>

            <template v-if="drawer.evidences.length">
              <h4>证据句（{{ drawer.evidences.length }}）</h4>
              <div class="evidence" v-for="ev in drawer.evidences" :key="ev.id">
                <div class="quote">「{{ ev.sentence }}」</div>
                <div class="src">
                  <span>📄 {{ ev.document_filename }}</span>
                  <span class="mono">seg#{{ ev.segment_id }}</span>
                </div>
              </div>
            </template>

            <div v-if="!drawer.relations.length && !drawer.evidences.length" class="empty">
              <p style="font-size:13px">该实体暂无关联与证据句。</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  data() {
    return {
      overview: { nodes: [], edges: [], categories: [], total_nodes: 0, total_edges: 0, sampled: false },
      categories: [],
      hiddenTypes: [],
      layout: 'force',
      query: '',
      drawer: null,
      chart: null,
      empty: false,
      nodeIndex: {}, // name -> id（定位用）
    };
  },
  mounted() {
    this.chart = echarts.init(this.$refs.canvas);
    window.addEventListener('resize', this.onResize);
    this.loadOverview();
    // 从检索页跳转：定位到指定实体
    if (window.__pendingEntity != null) {
      const id = window.__pendingEntity;
      window.__pendingEntity = null;
      this.openEntity(id);
    }
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.onResize);
    if (this.chart) this.chart.dispose();
  },
  methods: {
    async loadOverview() {
      try {
        const data = await api.get('/graph/overview', { limit: 500 });
        this.overview = data;
        this.categories = data.categories;
        this.empty = data.nodes.length === 0;
        this.render();
      } catch (e) {
        this.$emit('toast', e.message, 'err');
      }
    },
    render() {
      if (!this.chart) return;
      const cats = this.categories.map((c) => ({
        name: c.name,
        itemStyle: { color: window.typeColor(c.name) },
      }));
      const catIndex = {};
      this.categories.forEach((c, i) => (catIndex[c.id] = i));
      this.nodeIndex = {};

      const hidden = this.hiddenTypes;
      const nodes = this.overview.nodes
        .filter((n) => !hidden.includes(n.type_name))
        .map((n) => {
          this.nodeIndex[n.name] = n.id;
          return {
            id: n.id,
            name: n.name,
            typeName: n.type_name,
            value: n.value,
            category: catIndex[n.category] !== undefined ? catIndex[n.category] : 0,
            symbolSize: Math.min(34, Math.max(11, Math.sqrt(n.value || 1) * 5 + 7)),
          };
        });

      this._seriesNodeIds = nodes.map((n) => n.id);
      const keep = new Set(nodes.map((n) => n.id));
      const edges = this.overview.edges
        .filter((e) => keep.has(e.source) && keep.has(e.target))
        .map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          value: e.weight,
          lineStyle: { width: Math.min(4, Math.max(0.6, e.weight * 0.6)) },
          label: { show: this.overview.total_edges < 40, formatter: e.relation_type_name, fontSize: 9, color: '#5e6480' },
        }));

      this.chart.setOption(
        {
          backgroundColor: 'transparent',
          tooltip: {
            backgroundColor: 'rgba(15,18,32,0.95)',
            borderColor: '#333c5e',
            textStyle: { color: '#e8eaf2', fontSize: 12 },
            formatter: (p) => {
              if (p.dataType === 'edge') {
                return p.data.label ? '关系：' + p.data.label.formatter : '关系';
              }
              const d = p.data;
              return '<b>' + d.name + '</b><br/>' + d.typeName + ' · 频次 ' + d.value;
            },
          },
          series: [
            {
              type: 'graph',
              layout: this.layout,
              data: nodes,
              links: edges,
              categories: cats,
              roam: true,
              draggable: true,
              cursor: 'pointer',
              label: { show: true, position: 'right', color: '#9aa1bc', fontSize: 11, distance: 6 },
              edgeSymbol: ['none', 'arrow'],
              edgeSymbolSize: 6,
              lineStyle: { color: 'source', opacity: 0.32, curveness: 0.08 },
              itemStyle: { borderColor: 'rgba(255,255,255,0.25)', borderWidth: 0.5 },
              emphasis: {
                focus: 'adjacency',
                lineStyle: { width: 2.5, opacity: 0.95 },
                label: { color: '#fff' },
                itemStyle: { shadowBlur: 18, shadowColor: 'rgba(242,193,78,0.7)' },
              },
              force: {
                repulsion: 320,
                edgeLength: [80, 160],
                gravity: 0.08,
                friction: 0.1,
              },
              circular: { rotateLabel: false },
            },
          ],
        },
        true
      );
      this.chart.off('click');
      this.chart.on('click', (params) => {
        if (params.dataType === 'node') this.openEntity(params.data.id);
      });
    },
    toggleType(name) {
      const i = this.hiddenTypes.indexOf(name);
      if (i >= 0) this.hiddenTypes.splice(i, 1);
      else this.hiddenTypes.push(name);
      this.render();
    },
    setLayout(l) {
      this.layout = l;
      this.render();
    },
    async openEntity(id) {
      try {
        const data = await api.get('/graph/node/' + id);
        this.drawer = data;
      } catch (e) {
        this.$emit('toast', e.message, 'err');
      }
    },
    locateNode() {
      const q = (this.query || '').trim();
      if (!q) return;
      const id = this.nodeIndex[q];
      if (id == null) {
        this.$emit('toast', '未找到实体「' + q + '」，试试实体检索', 'err');
        return;
      }
      this.highlightNode(id);
      this.openEntity(id);
    },
    highlightNode(id) {
      const idx = (this._seriesNodeIds || []).indexOf(id);
      if (idx < 0 || !this.chart) return;
      this.chart.dispatchAction({ type: 'focusNodeAdjacency', seriesIndex: 0, dataIndex: idx });
    },
    onResize() {
      if (this.chart) this.chart.resize();
    },
  },
};
