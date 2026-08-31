/* 个人中心（P11）：账号信息（只读）+ 修改邮箱 / 修改密码（待后端 P1 PUT）。 */
window.Views = window.Views || {};

window.Views.Profile = {
  name: 'ProfileView',
  template: `
    <div class="profile-grid">
      <div class="card">
        <div class="profile-head">
          <div class="avatar lg">{{ initial }}</div>
          <div>
            <div class="p-name">{{ user.username }}</div>
            <div class="p-role">{{ roleLabel }}</div>
          </div>
        </div>
        <dl class="attr-list" style="margin-top:20px">
          <dt>邮箱</dt><dd>{{ user.email }}</dd>
          <dt>注册时间</dt><dd class="mono">{{ formatTime(user.created_at) }}</dd>
          <dt>账号状态</dt><dd>{{ user.status === 'active' ? '正常' : '已禁用' }}</dd>
        </dl>
      </div>

      <div class="card">
        <h4>修改邮箱</h4>
        <div class="field">
          <label>邮箱</label>
          <input class="input" type="email" v-model.trim="email" />
        </div>
        <button class="btn btn--primary" :disabled="saving" @click="saveEmail">保存</button>
        <p class="note">需后端 PUT /auth/me（P1）</p>
      </div>

      <div class="card">
        <h4>修改密码</h4>
        <div class="field">
          <label>当前密码</label>
          <input class="input" type="password" v-model="oldPwd" autocomplete="current-password" />
        </div>
        <div class="field">
          <label>新密码（6-64 字符）</label>
          <input class="input" type="password" v-model="newPwd" autocomplete="new-password" />
        </div>
        <button class="btn btn--primary" :disabled="saving" @click="savePassword">更新密码</button>
        <p class="note">需后端 PUT /auth/me/password（P1）</p>
      </div>
    </div>
  `,
  data() {
    const u = store.getUser() || {};
    return { user: u, email: u.email || '', oldPwd: '', newPwd: '', saving: false };
  },
  computed: {
    initial() {
      return (this.user.username ? this.user.username[0] : '?').toUpperCase();
    },
    roleLabel() {
      return this.user.role === 'admin' ? '管理员' : '普通用户';
    },
  },
  methods: {
    async saveEmail() {
      if (!this.email) return this.$emit('toast', '请输入邮箱', 'err');
      this.saving = true;
      try {
        await api.put('/auth/me', { email: this.email });
        this.user.email = this.email;
        this.$emit('toast', '邮箱已更新', 'ok');
      } catch (e) {
        this.$emit('toast', window.friendlyError(e), 'err');
      } finally {
        this.saving = false;
      }
    },
    async savePassword() {
      if (!this.oldPwd || !this.newPwd) return this.$emit('toast', '请填写完整', 'err');
      if (this.newPwd.length < 6) return this.$emit('toast', '新密码至少 6 位', 'err');
      this.saving = true;
      try {
        await api.put('/auth/me/password', { current_password: this.oldPwd, new_password: this.newPwd });
        this.oldPwd = '';
        this.newPwd = '';
        this.$emit('toast', '密码已更新', 'ok');
      } catch (e) {
        this.$emit('toast', window.friendlyError(e), 'err');
      } finally {
        this.saving = false;
      }
    },
  },
};
