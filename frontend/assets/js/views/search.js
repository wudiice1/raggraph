/* 知识检索：全文（高亮摘要）/ 实体 双 Tab。 */
window.Views = window.Views || {};

window.Views.Search = {
  name: 'SearchView',
  template: `
    <div>
      <div class="search-box">
        <input class="input" v-model="q" @keyup.enter="run" placeholder="输入关键词，检索知识库…" />
        <button class="btn btn--primary" @click="run" :disabled="!q.trim() || loading">检索</button>
      </div>

      <div class="tabs">
        <div class="tab" :class="{ active: tab === 'fulltext' }" @click="switchTab('fulltext')">全文检索</div>
        <div class="tab" :class="{ active: tab === 'entities' }" @click="switchTab('entities')">实体检索</div>
      </div>

      <div v-if="loading" class="empty"><div class="glyph">· · ·</div></div>

      <template v-else-if="searched">
        <div class="result-count">「{{ q }}」 命中 <b style="color:var(--text)">{{ total }}</b> 条</div>

        <div v-if="total === 0" class="empty">
          <div class="glyph">⌕</div>
          <p>没有匹配结果。换个关键词试试。</p>
        </div>

        <!-- 全文结果 -->
        <div class="hit-list" v-else-if="tab === 'fulltext'">
          <div class="hit" v-for="(h, i) in items" :key="h.segment_id + '-' + i">
            <div class="hit__top">
              <span class="hit__title">{{ h.document_filename }}</span>
              <span class="hit__meta" v-if="!h.matched">仅文件名命中</span>
            </div>
            <div class="hit__snippet" v-html="h.snippet"></div>
            <div class="hit__footer">
              <span class="mono">seg#{{ h.segment_id }}</span>
              <span class="mono">第 {{ h.seq }} 段</span>
            </div>
          </div>
        </div>

        <!-- 实体结果 -->
        <div class="hit-list" v-else>
          <div class="hit" v-for="e in items" :key="e.id">
            <div class="hit__top">
              <span class="tag tag--type" :style="{ background: e.type.color || typeColor(e.type.name) }">
                {{ e.type.name }}
              </span>
              <span class="hit__title">{{ e.name }}</span>
              <button class="btn btn--ghost btn--sm" style="margin-left:auto" @click="gotoGraph(e.id)">在图谱中查看 →</button>
            </div>
            <div class="hit__footer">
              <span>频次 <b class="mono">{{ e.frequency }}</b></span>
              <span>关联 <b class="mono">{{ e.relation_count }}</b></span>
              <span>来源文档 <b class="mono">{{ e.document_count }}</b></span>
            </div>
          </div>
        </div>

        <div class="pager" v-if="total > pageSize">
          <button class="btn btn--sm" :disabled="page <= 1" @click="go(page - 1)">←</button>
          <span>第 {{ page }} / {{ totalPages }} 页</span>
          <button class="btn btn--sm" :disabled="page >= totalPages" @click="go(page + 1)">→</button>
        </div>
      </template>

      <div v-else class="empty">
        <div class="glyph">⌕</div>
        <p>输入关键词，检索文档、分段与实体。</p>
      </div>
    </div>
  `,
  data() {
    return {
      q: '',
      tab: 'fulltext',
      items: [],
      total: 0,
      page: 1,
      pageSize: 20,
      loading: false,
      searched: false,
    };
  },
  computed: {
    totalPages() {
      return Math.max(1, Math.ceil(this.total / this.pageSize));
    },
  },
  methods: {
    switchTab(t) {
      this.tab = t;
      this.page = 1;
      if (this.searched) this.run();
    },
    async run() {
      if (!this.q.trim()) return;
      this.loading = true;
      this.page = 1;
      try {
        const path = this.tab === 'fulltext' ? '/search/fulltext' : '/search/entities';
        const res = await api.get(path, { q: this.q.trim(), page: this.page, page_size: this.pageSize });
        this.items = res.items;
        this.total = res.total;
        this.searched = true;
      } catch (e) {
        this.$emit('toast', e.message, 'err');
      } finally {
        this.loading = false;
      }
    },
    go(p) {
      this.page = p;
      this.loadPage();
    },
    async loadPage() {
      this.loading = true;
      try {
        const path = this.tab === 'fulltext' ? '/search/fulltext' : '/search/entities';
        const res = await api.get(path, { q: this.q.trim(), page: this.page, page_size: this.pageSize });
        this.items = res.items;
        this.total = res.total;
      } catch (e) {
        this.$emit('toast', e.message, 'err');
      } finally {
        this.loading = false;
      }
    },
    gotoGraph(id) {
      window.__pendingEntity = id;
      location.hash = '#/graph';
    },
  },
};
