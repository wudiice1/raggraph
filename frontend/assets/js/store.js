/* 极简会话状态：token + 当前用户，存 localStorage（CDN 无构建方案不引 vuex）。 */
window.store = {
  getUser() {
    try {
      return JSON.parse(localStorage.getItem('user'));
    } catch (e) {
      return null;
    }
  },
  setSession(session) {
    localStorage.setItem('token', session.access_token);
    localStorage.setItem('user', JSON.stringify(session.user));
  },
  clear() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  },
};
