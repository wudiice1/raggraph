/* 全局配置与共享映射：所有页面先加载本文件。
 * 后端地址可在此修改，或部署时用环境变量/服务器配置覆盖。
 */
window.APP_CONFIG = {
  // 后端 API 根地址（Swagger: http://127.0.0.1:8000/docs）
  apiBase: 'http://127.0.0.1:8000/api/v1',
};

/* 实体类型 → 星温色阶（本项目视觉身份的节点着色依据，GRA-03）。
 * 后端 seed 默认色为 ECharts 默认五色，此处按「星座」身份重映射；未知类型回退灰蓝。
 */
window.TYPE_COLORS = {
  人物: '#7DA6F0', // 冷蓝
  组织: '#6BD1B0', // 青绿
  地点: '#F2C14E', // 琥珀（呼应「灯」主色）
  概念: '#E78FBF', // 玫红
  技术: '#5EC8D6', // 星蓝青
};
window.FALLBACK_COLOR = '#8B93B8';

window.typeColor = function (name) {
  return window.TYPE_COLORS[name] || window.FALLBACK_COLOR;
};

/* 文档解析状态 → 文案与样式类（前端展示口径，与后端状态机一致）。 */
window.STATUS = {
  pending: { label: '待解析', cls: 'pending' },
  parsing: { label: '解析中', cls: 'parsing' },
  completed: { label: '已完成', cls: 'completed' },
  failed: { label: '失败', cls: 'failed' },
};

window.statusMeta = function (status) {
  return window.STATUS[status] || { label: status || '未知', cls: '' };
};

/* 文件大小格式化（字节 → 人类可读）。 */
window.formatBytes = function (bytes) {
  if (bytes == null) return '—';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
};

/* 错误文案归一：对尚未接入的 P1 接口（404/405）给出可理解的提示。 */
window.friendlyError = function (e) {
  if (e && (e.status === 404 || e.status === 405)) {
    return '该功能接口尚未接入（后端 P1 待实现）';
  }
  return (e && e.message) || '请求失败';
};

/* 时间格式化（ISO → 本地短格式）。 */
window.formatTime = function (iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
};
