/* 知识库设置（P10，管理员）：抽取规则 / 过滤规则。待后端 P1 GET/PUT /settings/*。 */
window.Views = window.Views || {};

window.Views.Settings = {
  name: 'SettingsView',
  template: `
    <div class="settings-grid">
      <div class="card">
        <h4>抽取规则</h4>
        <div class="field">
          <label>实体最小频次（MIN_ENTITY_FREQ）</label>
          <input class="input input--mono" type="number" min="1" v-model.number="ext.min_entity_freq" />
          <span class="hint">低于该频次的候选实体将被剔除，降低噪声。</span>
        </div>
        <div class="field">
          <label>图谱最大节点数</label>
          <input class="input input--mono" type="number" min="1" v-model.number="ext.max_nodes" />
        </div>
        <label class="switch-row">
          <input type="checkbox" v-model="ext.relation_mode" />
          <span>启用句法模式关系抽取</span>
        </label>
        <button class="btn btn--primary" style="margin-top:18px" :disabled="saving" @click="saveExt">保存</button>
        <p class="note">需后端 GET/PUT /settings/extraction（P1）</p>
      </div>

      <div class="card">
        <h4>过滤规则</h4>
        <div class="field">
          <label>停用词表（每行一个）</label>
          <textarea class="input input--mono" rows="6" v-model="filter.stopwords" placeholder="例如：&#10;的&#10;了&#10;是"></textarea>
        </div>
        <label class="switch-row">
          <input type="checkbox" v-model="filter.remove_page_noise" />
          <span>剔除页码 / 页眉噪声</span>
        </label>
        <button class="btn btn--primary" style="margin-top:18px" :disabled="saving" @click="saveFilter">保存</button>
        <p class="note">需后端 GET/PUT /settings/filter（P1）</p>
      </div>
    </div>
  `,
  data() {
    return {
      ext: { min_entity_freq: 3, max_nodes: 500, relation_mode: true },
      filter: { stopwords: '', remove_page_noise: true },
      saving: false,
      notReady: false,
    };
  },
  async mounted() {
    // 尝试拉取已保存配置；接口未接入时保持默认值并提示。
    try {
      const [ext, filter] = await Promise.all([
        api.get('/settings/extraction'),
        api.get('/settings/filter'),
      ]);
      if (ext) this.ext = { ...this.ext, ...ext };
      if (filter) this.filter = { ...this.filter, ...filter };
    } catch (e) {
      this.notReady = true;
    }
  },
  methods: {
    async saveExt() {
      this.saving = true;
      try {
        await api.put('/settings/extraction', this.ext);
        this.$emit('toast', '抽取规则已保存', 'ok');
      } catch (e) {
        this.$emit('toast', window.friendlyError(e), 'err');
      } finally {
        this.saving = false;
      }
    },
    async saveFilter() {
      this.saving = true;
      try {
        await api.put('/settings/filter', { stopwords: this.filter.stopwords, remove_page_noise: this.filter.remove_page_noise });
        this.$emit('toast', '过滤规则已保存', 'ok');
      } catch (e) {
        this.$emit('toast', window.friendlyError(e), 'err');
      } finally {
        this.saving = false;
      }
    },
  },
};
