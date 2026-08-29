/* 文档详情（P4）+ 分段清洗预览（P5）：元信息 / 解析概览 / 重解析 / 删除 / 分段对照。 */
window.Views = window.Views || {};

window.Views.DocumentDetail = {
  name: 'DocumentDetailView',
  props: ['docId'],
  template: `
    <div>
      <button class="btn btn--ghost btn--sm" @click="goBack">← 返回文档库</button>

      <div v-if="loading" class="empty"><div class="glyph">· · ·</div></div>
      <div v-else-if="!doc" class="empty">
        <div class="glyph">✕</div>
        <p>文档不存在或已删除。</p>
      </div>

      <template v-else>
        <div class="detail-head">
          <div class="detail-head__main">
            <h2>{{ doc.filename }}</h2>
            <div class="detail-meta">
              <span class="mono">{{ doc.file_type.toUpperCase() }}</span>
              <span class="sep">·</span>
              <span class="mono">{{ formatBytes(doc.size) }}</span>
              <span class="sep">·</span>
              <span class="mono">{{ formatTime(doc.created_at) }}</span>
              <span class="badge" :class="'badge--' + statusMeta(doc.status).cls">{{ statusMeta(doc.status).label }}</span>
            </div>
            <p v-if="doc.parse_error" class="parse-error">解析错误：{{ doc.parse_error }}</p>
          </div>
          <div class="detail-head__actions">
            <button class="btn btn--sm" :disabled="doc.status === 'parsing'" @click="reparse">重新解析</button>
            <button class="btn btn--danger btn--sm" :class="{ arming: confirming }" @click="remove">
              {{ confirming ? '确认删除？' : '删除文档' }}
            </button>
          </div>
        </div>

        <div class="stats">
          <div class="stat">
            <div class="stat__label">分段</div>
            <div class="stat__value">{{ doc.stats.segments }}<span class="unit">段</span></div>
          </div>
          <div class="stat">
            <div class="stat__label">实体</div>
            <div class="stat__value">{{ doc.stats.entities }}<span class="unit">个</span></div>
          </div>
          <div class="stat">
            <div class="stat__label">关系</div>
            <div class="stat__value">{{ doc.stats.relations }}<span class="unit">条</span></div>
          </div>
        </div>

        <div class="section-head" style="margin-top:28px">
          <h3>分段与清洗预览</h3>
          <span class="mono" style="font-size:12px;color:var(--text-faint)" v-if="!segError">共 {{ segTotal }} 段</span>
        </div>

        <div v-if="segError" class="empty">
          <div class="glyph">⌕</div>
          <p>分段预览接口尚未接入（待后端 GET /documents/{id}/segments，P1）。</p>
        </div>
        <div v-else-if="segments.length === 0" class="empty">
          <div class="glyph">✦</div>
          <p>暂无分段。文档解析完成后这里会展示清洗前后对照。</p>
        </div>
        <div v-else class="seg-list">
          <div class="seg-item" v-for="s in segments" :key="s.id" :class="{ noise: s.is_noise }">
            <div class="seg-head">
              <span class="mono">#{{ s.seq }}</span>
              <span v-if="s.is_noise" class="badge badge--failed">噪音</span>
            </div>
            <div class="seg-clean">{{ s.clean_text || s.raw_text }}</div>
            <div class="seg-raw" v-if="s.is_noise && s.raw_text !== s.clean_text">原始：{{ s.raw_text }}</div>
          </div>
        </div>

        <div class="pager" v-if="segTotal > segPageSize">
          <button class="btn btn--sm" :disabled="segPage <= 1" @click="segGo(segPage - 1)">←</button>
          <span>第 {{ segPage }} / {{ segTotalPages }} 页</span>
          <button class="btn btn--sm" :disabled="segPage >= segTotalPages" @click="segGo(segPage + 1)">→</button>
        </div>
      </template>
    </div>
  `,
  data() {
    return {
      doc: null,
      loading: true,
      confirming: false,
      segments: [],
      segTotal: 0,
      segPage: 1,
      segPageSize: 50,
      segError: false,
    };
  },
  computed: {
    segTotalPages() {
      return Math.max(1, Math.ceil(this.segTotal / this.segPageSize));
    },
  },
  mounted() {
    if (!this.docId) {
      this.loading = false;
      return;
    }
    this.fetchDoc();
    this.fetchSegments();
  },
  methods: {
    goBack() {
      location.hash = '#/documents';
    },
    async fetchDoc() {
      this.loading = true;
      try {
        this.doc = await api.get('/documents/' + this.docId);
      } catch (e) {
        this.doc = null;
      } finally {
        this.loading = false;
      }
    },
    async fetchSegments() {
      this.segError = false;
      try {
        const res = await api.get('/documents/' + this.docId + '/segments', {
          page: this.segPage,
          page_size: this.segPageSize,
        });
        this.segments = res.items || [];
        this.segTotal = res.total || 0;
      } catch (e) {
        this.segError = true;
      }
    },
    segGo(p) {
      this.segPage = p;
      this.fetchSegments();
    },
    async reparse() {
      try {
        await api.post('/documents/' + this.docId + '/parse');
        this.$emit('toast', '已触发重新解析', 'ok');
        this.poll();
      } catch (e) {
        this.$emit('toast', e.message, 'err');
      }
    },
    poll() {
      const tick = async () => {
        try {
          const d = await api.get('/documents/' + this.docId);
          this.doc = d;
          if (d.status === 'parsing' || d.status === 'pending') {
            setTimeout(tick, 2500);
          } else if (d.status === 'completed') {
            this.$emit('toast', '解析完成', 'ok');
            this.fetchSegments();
          }
        } catch (e) {
          /* stop */
        }
      };
      tick();
    },
    remove() {
      if (!this.confirming) {
        this.confirming = true;
        setTimeout(() => (this.confirming = false), 3000);
        return;
      }
      this.confirming = false;
      this.doRemove();
    },
    async doRemove() {
      try {
        await api.del('/documents/' + this.docId);
        this.$emit('toast', '已删除', 'ok');
        location.hash = '#/documents';
      } catch (e) {
        this.$emit('toast', window.friendlyError(e), 'err');
      }
    },
  },
};
