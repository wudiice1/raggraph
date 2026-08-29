/* fetch 封装：统一 baseURL、Bearer token 注入、401 拦截、错误归一化。
 * 用法：
 *   await api.get('/documents', { page: 1 })
 *   await api.post('/auth/login', { username, password })
 *   await api.postForm('/documents/upload', formData)
 */
(function () {
  const cfg = window.APP_CONFIG;

  function buildUrl(path, query) {
    let url = cfg.apiBase + path;
    if (query) {
      const p = new URLSearchParams();
      Object.keys(query).forEach((k) => {
        const v = query[k];
        if (v !== undefined && v !== null && v !== '') p.set(k, v);
      });
      const qs = p.toString();
      if (qs) url += '?' + qs;
    }
    return url;
  }

  async function request(method, path, opts) {
    opts = opts || {};
    const headers = {};
    const token = localStorage.getItem('token');
    if (token) headers['Authorization'] = 'Bearer ' + token;

    let payload;
    if (opts.form) {
      payload = opts.form; // FormData：由浏览器自动设置 multipart 边界
    } else if (opts.body !== undefined) {
      headers['Content-Type'] = 'application/json';
      payload = JSON.stringify(opts.body);
    }

    const res = await fetch(buildUrl(path, opts.query), {
      method: method,
      headers: headers,
      body: payload,
    });

    // 统一 401 处理：清会话回登录页（token 失效/过期）
    if (res.status === 401 && token) {
      window.store && window.store.clear();
      if (!location.pathname.endsWith('index.html')) location.href = 'index.html';
      throw new Error('登录已过期，请重新登录');
    }

    if (res.status === 204) return null;

    let data = null;
    try {
      data = await res.json();
    } catch (e) {
      /* 空响应体 */
    }

    if (!res.ok) {
      const err = new Error(
        data && data.detail
          ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
          : '请求失败（' + res.status + '）'
      );
      err.status = res.status;
      throw err;
    }
    return data;
  }

  window.api = {
    get: (path, query) => request('GET', path, { query: query }),
    post: (path, body) => request('POST', path, { body: body }),
    postForm: (path, form) => request('POST', path, { form: form }),
    put: (path, body) => request('PUT', path, { body: body }),
    del: (path) => request('DELETE', path),
  };
})();
