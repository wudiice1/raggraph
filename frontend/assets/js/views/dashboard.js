/* 工作台：顶部概览 + 统计读数 + 最近文档。 */
window.Views = window.Views || {};

window.Views.Dashboard = {
  name: 'DashboardView',
  template: `
    <div>
      <div class="dash-hero">
        <div>
          <div class="eyebrow">Cognitive Knowledge Graph</div>
          <h2>{{ greeting }}，把文档读成一张星图</h2>
          <p>上传文档，系统会自动抽取实体与关系。这里能看到你知识库的全貌。</p>
        </div>
        <button class="btn btn--primary" @click="$emit('go','documents')">上传第一篇文档</button>
      </div>

      <div class="stats">
        <div class="stat">
          <div class="stat__label">文档</div>
          <div class="stat__value">{{ stats.documents }}<span class="unit">篇</span></div>
        </div>
        <div class="stat">
          <div class="stat__label">实体（节点）</div>
          <div class="stat__value">{{ stats.entities }}<span class="unit">个</span></div>
        </div>
        <div class="stat">
          <div class="stat__label">关系（连线）</div>
          <div class="stat__value">{{ stats.relations }}<span class="unit">条</span></div>
        </div>
      </div>

      <div class="section-head">
        <h3>最近上传</h3>
        <button class="btn btn--ghost btn--sm" @click="$emit('go','documents')">全部文档 →</button>
      </div>

      <div v-if="loading" class="empty"><div class="glyph">· · ·</div></div>
      <div v-else-if="recent.length === 0" class="empty">
        <div class="glyph">✦</div>
        <p>还没有文档。上传一篇 PDF / DOCX / TXT / MD，让知识库亮起来。</p>
      </div>
      <div v-else class="doc-list">
        <div class="doc-list__head">
          <span>文件名</span><span>格式</span><span>状态</span><span>分段</span><span>实体</span><span>上传时间</span>
        </div>
        <div class="doc-row" v-for="d in recent" :key="d.id">
          <div class="fname" @click="openDetail(d)">{{ d.filename }}</div>
          <div class="mono">{{ d.file_type.toUpperCase() }}</div>
          <div><span class="badge" :class="'badge--' + statusMeta(d.status).cls">{{ statusMeta(d.status).label }}</span></div>
          <div class="mono">{{ d.stats.segments }}</div>
          <div class="mono">{{ d.stats.entities }}</div>
          <div class="mono">{{ formatTime(d.created_at) }}</div>
        </div>
      </div>
    </div>
  `,
  data() {
    return { stats: { documents: 0, entities: 0, relations: 0 }, recent: [], loading: true };
  },
  computed: {
    greeting() {
      const h = new Date().getHours();
      if (h < 6) return '夜深了';
      if (h < 12) return '早上好';
      if (h < 18) return '下午好';
      return '晚上好';
    },
  },
  methods: {
    openDetail(d) {
      location.hash = '#/document/' + d.id;
    },
  },
  async mounted() {
    try {
      const [docs, graph] = await Promise.all([
        api.get('/documents', { page: 1, page_size: 5 }),
        api.get('/graph/overview', { limit: 50 }),
      ]);
      this.stats.documents = docs.total;
      this.stats.entities = graph.total_nodes;
      this.stats.relations = graph.total_edges;
      this.recent = docs.items;
    } catch (e) {
      this.$emit('toast', e.message, 'err');
    } finally {
      this.loading = false;
    }
  },
};
