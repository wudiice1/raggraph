/* 本体管理（P9）：实体类型 / 关系类型。P0 只读；增删改待后端 P1。 */
window.Views = window.Views || {};

window.Views.Ontology = {
  name: 'OntologyView',
  template: `
    <div>
      <div class="tabs">
        <div class="tab" :class="{ active: tab === 'entities' }" @click="tab = 'entities'">实体类型</div>
        <div class="tab" :class="{ active: tab === 'relations' }" @click="tab = 'relations'">关系类型</div>
      </div>

      <div class="notice" v-if="isAdmin">
        类型增删改需后端 P1 接口（POST/PUT/DELETE /ontology/*），当前为只读展示。
      </div>

      <div v-if="loading" class="empty"><div class="glyph">· · ·</div></div>

      <div v-else-if="tab === 'entities'" class="onto-grid">
        <div class="onto-card" v-for="t in entityTypes" :key="t.id">
          <span class="onto-dot" :style="{ background: typeColor(t.name) }"></span>
          <div class="onto-main">
            <div class="onto-name">{{ t.name }}</div>
            <div class="onto-desc">{{ t.description || '—' }}</div>
          </div>
          <span class="mono onto-hex">{{ t.color }}</span>
        </div>
      </div>

      <div v-else class="onto-grid">
        <div class="onto-card" v-for="t in relationTypes" :key="t.id">
          <div class="onto-main">
            <div class="onto-name">{{ t.name }}</div>
            <div class="onto-desc">{{ t.description || '—' }}</div>
          </div>
        </div>
      </div>

      <p class="onto-foot">节点着色按「星温色阶」在图表中映射；此处 {{ tab === 'entities' ? '右侧' : '仅' }}列出后端存储的原始色值，二者保持一致由前端 typeColor() 统一。</p>
    </div>
  `,
  data() {
    return {
      tab: 'entities',
      entityTypes: [],
      relationTypes: [],
      loading: true,
      isAdmin: store.getUser() && store.getUser().role === 'admin',
    };
  },
  async mounted() {
    try {
      const [et, rt] = await Promise.all([
        api.get('/ontology/entity-types'),
        api.get('/ontology/relation-types'),
      ]);
      this.entityTypes = et.items || [];
      this.relationTypes = rt.items || [];
    } catch (e) {
      this.$emit('toast', e.message, 'err');
    } finally {
      this.loading = false;
    }
  },
};
