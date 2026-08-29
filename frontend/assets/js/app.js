/* 应用外壳：左侧导航 + 顶部仪表条 + hash 路由（支持参数）+ 全局 toast。 */
(function () {
  // 未登录守卫
  if (!store.getUser()) {
    location.replace('index.html');
    return;
  }

  const ICON = {
    dashboard: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><rect x="1.5" y="1.5" width="5.5" height="5.5" rx="1"/><rect x="9" y="1.5" width="5.5" height="5.5" rx="1"/><rect x="1.5" y="9" width="5.5" height="5.5" rx="1"/><rect x="9" y="9" width="5.5" height="5.5" rx="1"/></svg>',
    graph: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="4" cy="4" r="1.8"/><circle cx="12" cy="3.5" r="1.5"/><circle cx="12" cy="12" r="1.8"/><circle cx="3" cy="12" r="1.5"/><path d="M4 4l8-.5M12 3.5 12 12M4 4l-1 8M3 12l9 0"/></svg>',
    search: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/></svg>',
    documents: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M4 1.5h6l2.5 2.5V14.5H4z"/><path d="M10 1.5V4h2.5"/></svg>',
    ontology: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M2 2h5l7 7-5 5-7-7z"/><circle cx="5" cy="5" r="1"/></svg>',
    settings: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="8" cy="8" r="2.2"/><path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4"/></svg>',
    profile: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="8" cy="5" r="3"/><path d="M2.5 14c.5-3 2.5-4.5 5.5-4.5s5 1.5 5.5 4.5"/></svg>',
  };

  const NAV_GROUPS = [
    {
      group: '空间',
      items: [
        { slug: 'dashboard', label: '工作台', kbd: '1' },
        { slug: 'graph', label: '知识图谱', kbd: '2' },
        { slug: 'search', label: '知识检索', kbd: '3' },
        { slug: 'documents', label: '文档库', kbd: '4' },
      ],
    },
    {
      group: '管理',
      admin: true,
      items: [
        { slug: 'ontology', label: '本体管理' },
        { slug: 'settings', label: '知识库设置' },
      ],
    },
    {
      group: '账户',
      items: [{ slug: 'profile', label: '个人中心' }],
    },
  ];

  const TITLES = {
    dashboard: { title: '工作台', sub: '知识库全貌概览' },
    documents: { title: '文档库', sub: '上传与管理文档，跟踪解析状态' },
    document: { title: '文档详情', sub: '元信息、解析结果与分段清洗预览' },
    graph: { title: '知识图谱', sub: '实体为星，关系为线——探索知识之间的关联' },
    search: { title: '知识检索', sub: '全文与实体检索，命中可溯源' },
    ontology: { title: '本体管理', sub: '实体类型与关系类型（图例着色依据）' },
    settings: { title: '知识库设置', sub: '抽取规则与过滤规则' },
    profile: { title: '个人中心', sub: '账号信息与安全' },
  };

  const ROUTE_TO_COMPONENT = {
    dashboard: 'Dashboard',
    documents: 'Documents',
    document: 'DocumentDetail',
    graph: 'Graph',
    search: 'Search',
    ontology: 'Ontology',
    settings: 'Settings',
    profile: 'Profile',
  };

  const MARK = '<svg class="mark" viewBox="0 0 24 24" fill="none"><circle cx="6" cy="6" r="2.2" fill="#F2C14E"/><circle cx="18" cy="5" r="1.6" fill="#7DA6F0"/><circle cx="17" cy="18" r="2" fill="#5EC8D6"/><circle cx="4" cy="16" r="1.4" fill="#E78FBF"/><path d="M6 6L18 5M18 5L17 18M6 6L4 16M4 16L17 18" stroke="#333c5e" stroke-width="1"/></svg>';

  let toastSeq = 0;

  function parseRoute() {
    const raw = location.hash.replace(/^#\/?/, '');
    const parts = raw.split('/');
    const slug = parts[0] || 'dashboard';
    const param = parts[1] || null;
    const valid = Object.prototype.hasOwnProperty.call(ROUTE_TO_COMPONENT, slug);
    return { slug: valid ? slug : 'dashboard', param: valid ? param : null };
  }

  const App = {
    data() {
      return {
        user: store.getUser(),
        mark: MARK,
        route: parseRoute(),
        toasts: [],
      };
    },
    computed: {
      navGroups() {
        const isAdmin = this.user && this.user.role === 'admin';
        return NAV_GROUPS.filter((g) => !g.admin || isAdmin).map((g) => ({
          group: g.group,
          items: g.items.map((it) => ({ ...it, icon: ICON[it.slug] })),
        }));
      },
      view() {
        return this.route.slug;
      },
      currentComponent() {
        return window.Views[ROUTE_TO_COMPONENT[this.view]];
      },
      currentTitle() {
        return (TITLES[this.view] || TITLES.dashboard).title;
      },
      currentSub() {
        return (TITLES[this.view] || TITLES.dashboard).sub;
      },
      routeKey() {
        return this.view + '/' + (this.route.param || '');
      },
      componentProps() {
        return this.view === 'document' ? { docId: this.route.param } : {};
      },
      initial() {
        return (this.user && this.user.username ? this.user.username[0] : '?').toUpperCase();
      },
      roleLabel() {
        return this.user && this.user.role === 'admin' ? '管理员' : '普通用户';
      },
    },
    methods: {
      nav(slug) {
        location.hash = '#/' + slug;
      },
      go(slug) {
        this.nav(slug);
      },
      logout() {
        store.clear();
        location.replace('index.html');
      },
      showToast(msg, type) {
        const id = ++toastSeq;
        this.toasts.push({ id, msg, type: type || 'ok' });
        setTimeout(() => {
          this.toasts = this.toasts.filter((t) => t.id !== id);
        }, 3200);
      },
      onHashChange() {
        this.route = parseRoute();
      },
    },
    mounted() {
      window.addEventListener('hashchange', this.onHashChange);
      window.addEventListener('keydown', (e) => {
        if (e.target && /input|textarea|select/i.test(e.target.tagName)) return;
        const map = { 1: 'dashboard', 2: 'graph', 3: 'search', 4: 'documents' };
        const slug = map[e.key];
        if (slug) location.hash = '#/' + slug;
      });
    },
    template: `
      <div class="shell">
        <aside class="rail">
          <div class="brand"><span v-html="mark" style="display:contents"></span><span class="word">认知知识库</span></div>
          <nav class="nav">
            <template v-for="g in navGroups" :key="g.group">
              <div class="nav__group">{{ g.group }}</div>
              <div class="nav__item" v-for="n in g.items" :key="n.slug"
                :class="{ active: view === n.slug }" @click="nav(n.slug)">
                <span class="ico" v-html="n.icon"></span>
                <span class="txt">{{ n.label }}</span>
                <span class="kbd" v-if="n.kbd">{{ n.kbd }}</span>
              </div>
            </template>
          </nav>
          <div class="user-block">
            <div class="avatar">{{ initial }}</div>
            <div class="uinfo">
              <div class="uname">{{ user.username }}</div>
              <div class="urole">{{ roleLabel }}</div>
            </div>
            <button class="logout" @click="logout" title="退出登录">⏻</button>
          </div>
        </aside>

        <div class="main">
          <header class="topbar">
            <div class="topbar__title">
              <h1>{{ currentTitle }}</h1>
              <p class="crumb">{{ currentSub }}</p>
            </div>
          </header>
          <main class="content" :class="{ 'content--full': view === 'graph' }">
            <component :is="currentComponent" :key="routeKey" v-bind="componentProps"
              @toast="showToast" @go="go"></component>
          </main>
        </div>

        <div class="toast-root">
          <div class="toast" v-for="t in toasts" :key="t.id" :class="'toast--' + t.type">{{ t.msg }}</div>
        </div>
      </div>
    `,
  };

  const app = Vue.createApp(App);
  // 注册全局助手：视图模板里可直接调用
  app.config.globalProperties.typeColor = window.typeColor;
  app.config.globalProperties.statusMeta = window.statusMeta;
  app.config.globalProperties.formatTime = window.formatTime;
  app.config.globalProperties.formatBytes = window.formatBytes;
  app.mount('#app');
})();
