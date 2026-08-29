/* 文档库：上传（进度）+ 列表（状态筛选）+ 轮询解析 + 重新解析。 */
window.Views = window.Views || {};

window.Views.Documents = {
  name: 'DocumentsView',
  template: `
    <div>
      <div class="dropzone" :class="{ drag: dragging }"
        @click="$refs.file.click()"
        @dragover.prevent="dragging = true"
        @dragleave="dragging = false"
        @drop.prevent="onDrop">
        <div class="big">拖入文件，或点击选择</div>
        <div class="meta">支持 PDF / DOCX / TXT / MD，单个 ≤ 20MB，可多选</div>
        <input ref="file" type="file" multiple hidden
          accept=".pdf,.docx,.txt,.md"
          @change="onPick" />
      </div>

      <div class="uploads" v-if="uploads.length">
        <div class="upload-row" v-for="u in uploads" :key="u.name + u.ts">
          <div class="fname">{{ u.name }}</div>
          <div class="progress"><span :style="{ width: u.pct + '%' }"></span></div>
          <div class="pct">{{ u.pct }}%</div>
        </div>
      </div>

      <div class="section-head">
        <h3>文档库 <span class="mono" style="color:var(--text-faint);font-weight:400">（{{ total }}）</span></h3>
        <div style="display:flex;gap:8px;align-items:center">
          <select class="input input--mono" v-model="statusFilter" @change="refresh" style="width:auto;padding:7px 10px;font-size:12.5px">
            <option value="">全部状态</option>
            <option value="pending">待解析</option>
            <option value="parsing">解析中</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
          </select>
        </div>
      </div>

      <div v-if="loading" class="empty"><div class="glyph">· · ·</div></div>
      <div v-else-if="docs.length === 0" class="empty">
        <div class="glyph">✦</div>
        <p>{{ statusFilter ? '该状态下暂无文档。' : '还没有文档。上传一篇，开始构建知识图谱。' }}</p>
      </div>
      <div v-else class="doc-list">
        <div class="doc-list__head">
          <span>文件名</span><span>格式</span><span>大小</span><span>状态</span><span>实体 / 关系</span><span>操作</span>
        </div>
        <div class="doc-row" v-for="d in docs" :key="d.id">
          <div class="fname" :title="d.filename" @click="openDetail(d)">{{ d.filename }}</div>
          <div class="mono">{{ d.file_type.toUpperCase() }}</div>
          <div class="mono">{{ formatBytes(d.size) }}</div>
          <div>
            <span class="badge" :class="'badge--' + statusMeta(d.status).cls"
              :title="d.parse_error || ''">{{ statusMeta(d.status).label }}</span>
          </div>
          <div class="stats-inline">{{ d.stats.entities }} / {{ d.stats.relations }}</div>
          <div class="actions">
            <button v-if="d.status === 'failed'" class="btn btn--sm" @click="reparse(d)">重新解析</button>
            <button v-else-if="d.status === 'completed'" class="btn btn--ghost btn--sm" @click="reparse(d)">重解析</button>
            <span v-else class="mono" style="font-size:11px;color:var(--text-faint)">—</span>
          </div>
        </div>
      </div>

      <div class="pager" v-if="total > pageSize">
        <button class="btn btn--sm" :disabled="page <= 1" @click="go(page - 1)">←</button>
        <span>第 {{ page }} / {{ totalPages }} 页</span>
        <button class="btn btn--sm" :disabled="page >= totalPages" @click="go(page + 1)">→</button>
      </div>
    </div>
  `,
  data() {
    return {
      docs: [],
      total: 0,
      page: 1,
      pageSize: 20,
      statusFilter: '',
      loading: true,
      dragging: false,
      uploads: [],
    };
  },
  computed: {
    totalPages() {
      return Math.max(1, Math.ceil(this.total / this.pageSize));
    },
  },
  async mounted() {
    await this.refresh();
  },
  methods: {
    openDetail(d) {
      location.hash = '#/document/' + d.id;
    },
    async refresh() {
      this.loading = true;
      try {
        const res = await api.get('/documents', {
          page: this.page,
          page_size: this.pageSize,
          status: this.statusFilter || undefined,
        });
        this.docs = res.items;
        this.total = res.total;
      } catch (e) {
        this.$emit('toast', e.message, 'err');
      } finally {
        this.loading = false;
      }
    },
    go(p) {
      this.page = p;
      this.refresh();
    },
    onPick(e) {
      const files = Array.from(e.target.files || []);
      files.forEach((f) => this.upload(f));
      e.target.value = '';
    },
    onDrop(e) {
      this.dragging = false;
      const files = Array.from(e.dataTransfer.files || []);
      files.forEach((f) => this.upload(f));
    },
    upload(file) {
      // 扩展名校验（与后端白名单一致，快速失败）
      const ext = (file.name.split('.').pop() || '').toLowerCase();
      if (!['pdf', 'docx', 'txt', 'md'].includes(ext)) {
        this.$emit('toast', '不支持的文件类型：.' + ext, 'err');
        return;
      }
      const row = { name: file.name, pct: 0, ts: Date.now() };
      this.uploads.push(row);

      const xhr = new XMLHttpRequest();
      const fd = new FormData();
      fd.append('file', file);

      xhr.upload.onprogress = (ev) => {
        if (ev.lengthComputable) row.pct = Math.round((ev.loaded / ev.total) * 100);
      };
      xhr.onload = () => {
        this.uploads = this.uploads.filter((u) => u !== row);
        try {
          const data = JSON.parse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300) {
            this.page = 1;
            this.refresh();
            this.$emit('toast', '已上传，开始解析', 'ok');
            this.poll(data.id);
          } else {
            this.$emit('toast', (data && data.detail) || '上传失败', 'err');
          }
        } catch (e) {
          this.$emit('toast', '上传失败', 'err');
        }
      };
      xhr.onerror = () => {
        this.uploads = this.uploads.filter((u) => u !== row);
        this.$emit('toast', '网络错误，上传失败', 'err');
      };
      xhr.open('POST', window.APP_CONFIG.apiBase + '/documents/upload');
      xhr.setRequestHeader('Authorization', 'Bearer ' + localStorage.getItem('token'));
      xhr.send(fd);
    },
    poll(id) {
      const tick = async () => {
        try {
          const d = await api.get('/documents/' + id);
          this.replaceDoc(d);
          if (d.status === 'parsing' || d.status === 'pending') {
            setTimeout(tick, 2500);
          } else if (d.status === 'completed') {
            this.$emit('toast', '「' + d.filename + '」解析完成，去看看图谱', 'ok');
          } else if (d.status === 'failed') {
            this.$emit('toast', '「' + d.filename + '」解析失败：' + (d.parse_error || '未知错误'), 'err');
          }
        } catch (e) {
          /* 文档被删等场景，停止轮询 */
        }
      };
      tick();
    },
    replaceDoc(d) {
      const i = this.docs.findIndex((x) => x.id === d.id);
      if (i >= 0) this.docs[i] = d;
      else this.docs.unshift(d);
    },
    async reparse(d) {
      try {
        await api.post('/documents/' + d.id + '/parse');
        this.$emit('toast', '已触发重新解析', 'ok');
        this.poll(d.id);
      } catch (e) {
        this.$emit('toast', e.message, 'err');
      }
    },
  },
};
