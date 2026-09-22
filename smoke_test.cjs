/* 纯本地版工作台 · 运行时冒烟测试（jsdom 真跑页面脚本，抓 JS 报错 + 校验渲染） */
const fs = require('fs');
const { JSDOM, VirtualConsole } = require('jsdom');

const HTML = fs.readFileSync(__dirname + '/personal-office-workbench.html', 'utf8');
const PAGE_URL = 'http://127.0.0.1:8799/personal-office-workbench.html';

function seedTasks(n) {
  const tasks = [];
  for (let i = 1; i <= n; i++) {
    tasks.push({ id: 't' + i, title: '压测任务 ' + i, prio: (i % 4) + 1, due: '', done: false, pid: '', createdAt: Date.now(), doneAt: null, rolls: 0 });
  }
  return { v: 1, tasks, notes: [], projects: [], meta: { initialized: true, sample: false, itemsAtExport: 0, lastExport: null, lastOpen: '2026-09-20', created: Date.now() }, generation: 0 };
}

function run(label, seedState) {
  const errors = [];
  let apiState = seedState ? JSON.parse(JSON.stringify(seedState)) : {
    v: 1, tasks: [], notes: [], projects: [],
    meta: { initialized: true, sample: false, itemsAtExport: 0, lastExport: null, lastOpen: '2026-09-20', created: Date.now() }, generation: 0
  };
  const vc = new VirtualConsole();
  vc.on('jsdomError', e => errors.push('[jsdomError] ' + (e && e.message)));
  vc.on('error', (...a) => errors.push('[console.error] ' + a.join(' ')));

  const dom = new JSDOM(HTML, {
    url: PAGE_URL,
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    virtualConsole: vc,
    beforeParse(window) {
      window.matchMedia = q => ({ matches: false, media: q, onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent() { return false; } });
      window.scrollTo = () => {};
      window.scroll = () => {};
      window.URL.createObjectURL = () => 'blob:mock';
      window.URL.revokeObjectURL = () => {};
      window.HTMLAnchorElement.prototype.click = function () {};
      window.fetch = async (url, opts = {}) => {
        if (url === '/api/workbench' && (!opts.method || opts.method === 'GET')) {
          return { ok: true, json: async () => JSON.parse(JSON.stringify(apiState)) };
        }
        if (url === '/api/workbench' && opts.method === 'PUT') {
          apiState = JSON.parse(opts.body);
          apiState.generation = (apiState.generation || 0) + 1;
          apiState.meta.generation = apiState.generation;
          return { ok: true, json: async () => JSON.parse(JSON.stringify(apiState)) };
        }
        if (url === '/api/backup/export' && opts.method === 'POST') {
          return { ok: true, blob: async () => new window.Blob(['mock zip'], { type: 'application/zip' }) };
        }
        throw new Error('unexpected fetch: ' + url);
      };
      window.addEventListener('error', ev => errors.push('[window.onerror] ' + ((ev.error && ev.error.stack) || ev.message)));
    }
  });

  const w = dom.window, d = w.document;

  return new Promise(res => setTimeout(async () => {
    const o = { label, errors: errors.slice() };
    o.navItems = d.querySelectorAll('#navScroll .nav-item').length;
    o.heroLen = d.getElementById('hero').innerHTML.length;
    o.viewLen = d.getElementById('view').innerHTML.length;
    o.nudge = d.getElementById('nudge').textContent.replace(/\s+/g, ' ').trim();
    o.footStore = d.getElementById('footStore').textContent.trim();
    o.navFoot = d.getElementById('navFoot').textContent.trim();
    o.apiLoaded = !!apiState.meta;

    // 走一遍所有视图切换
    const before = errors.length;
    ['focus', 'tasks', 'notes', 'projects', 'logs', 'review', 'backup'].forEach(k => {
      const b = d.querySelector('#navScroll [data-nav="' + k + '"]');
      if (b) b.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    });
    o.viewSwitchErrors = errors.length - before;
    o.viewLenAfterSwitch = d.getElementById('view').innerHTML.length;

    // 未提交的表单内容在切换标签后也必须保留，避免用户编辑中的内容被 render() 销毁。
    const switchTo = key => d.querySelector('#navScroll [data-nav="' + key + '"]')
      .dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    switchTo('projects');
    d.getElementById('pName').value = '项目草稿';
    d.getElementById('pStage').value = '方案评审中';
    d.getElementById('pNext').value = '约产品确认范围';
    d.getElementById('pDetails').value = '项目背景和关键决策';
    switchTo('notes');
    switchTo('projects');
    o.projectDraftRetained = d.getElementById('pName').value === '项目草稿'
      && d.getElementById('pStage').value === '方案评审中'
      && d.getElementById('pNext').value === '约产品确认范围'
      && d.getElementById('pDetails').value === '项目背景和关键决策';
    d.getElementById('projForm').dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));

    switchTo('tasks');
    d.getElementById('tTitle').value = '带详情的待办';
    d.getElementById('tDetails').value = '从入口 A 操作，完成后核对结果';
    d.getElementById('taskForm').dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(resolve => setTimeout(resolve, 20));
    o.detailsSaved = apiState.projects.some(p => p.name === '项目草稿' && p.details === '项目背景和关键决策')
      && apiState.tasks.some(t => t.title === '带详情的待办' && t.details === '从入口 A 操作，完成后核对结果');
    const taskDetailsToggle = d.querySelector('[data-act="toggle-details"]');
    o.taskDetailsToggle = !!taskDetailsToggle;
    if (taskDetailsToggle) taskDetailsToggle.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    o.taskDetailsShown = d.getElementById('view').textContent.includes('从入口 A 操作，完成后核对结果');
    switchTo('projects');
    const projectDetailsToggle = d.querySelector('[data-act="toggle-details"]');
    o.projectDetailsToggle = !!projectDetailsToggle;
    if (projectDetailsToggle) projectDetailsToggle.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    o.projectDetailsShown = d.getElementById('view').textContent.includes('项目背景和关键决策');

    switchTo('logs');
    d.getElementById('logText').value = '同一条日志关联多个项目';
    [...d.getElementById('logProjects').options].forEach(option => option.selected = true);
    d.getElementById('logForm').dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
    await new Promise(resolve => setTimeout(resolve, 20));
    o.logSaved = apiState.logs.some(log => log.text === '同一条日志关联多个项目' && log.projectIds.length === 1 && log.hasContent === true);
    o.logAddFormHidden = false;
    o.logReadOnly = d.getElementById('logText').readOnly && d.querySelector('[data-act="delete-log"]') && d.querySelector('[data-act="delete-log"]').textContent === '删除';
    o.logCalendarEntry = !!d.querySelector('[data-act="log-date"].has-log');
    switchTo('projects');
    const timeline = d.querySelector('[data-act="log-project"]');
    o.projectTimelineEntry = !!timeline;
    if (timeline) timeline.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    o.projectTimelineShown = d.getElementById('view').textContent.includes('同一条日志关联多个项目');
    switchTo('logs');
    const savedDateButton = d.querySelector('[data-act="log-date"].has-log');
    if (savedDateButton) savedDateButton.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    o.logEditControls = !!d.getElementById('logText') && !!d.getElementById('logProjects');
    if (o.logEditControls) {
      d.getElementById('logForm').dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
      d.getElementById('logText').value = '同一条日志继续编辑';
      d.getElementById('logForm').dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
      await new Promise(resolve => setTimeout(resolve, 20));
      o.logEdited = apiState.logs.filter(log => log.text === '同一条日志继续编辑').length === 1
        && apiState.logs.length === 1;
      w.confirm = () => false;
      d.querySelector('[data-act="delete-log"]').dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
      o.logDeleteCancel = apiState.logs.length === 1 && !!d.querySelector('[data-act="delete-log"]');
      w.confirm = () => true;
      d.querySelector('[data-act="delete-log"]').dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
      await new Promise(resolve => setTimeout(resolve, 20));
      o.logDeleted = apiState.logs.length === 0 && !d.querySelector('[data-act="delete-log"]');
    }

    // 逐个视图单独渲染，检查备份页导出/导入卡片
    ['focus', 'tasks', 'notes', 'projects', 'logs', 'review', 'backup'].forEach(k => {
      const b = d.querySelector('#navScroll [data-nav="' + k + '"]');
      if (b) b.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
      o[k + 'Html'] = d.getElementById('view').innerHTML.length;
    });
    const bkBtn = d.querySelector('#navScroll [data-nav="backup"]');
    if (bkBtn) bkBtn.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    const bkHtml = d.getElementById('view').innerHTML;
    o.backupHasExportBtn = /data-act="export"/.test(bkHtml);
    o.backupHasImportInput = /id="impFile"/.test(bkHtml);
    o.backupText = d.getElementById('view').textContent.replace(/\s+/g, ' ').trim().slice(0, 180);

    // 触发导出（走真实代码路径）
    const beforeExport = errors.length;
    try { await w.doExport(); } catch (e) { errors.push('[doExport threw] ' + e.message); }
    o.exportErrors = errors.length - beforeExport;
    o.footAfterExport = d.getElementById('navFoot').textContent.trim();
    o.nudgeAfterExport = d.getElementById('nudge').textContent.replace(/\s+/g, ' ').trim();

    o.errors = errors.slice();
    res(o);
  }, 400));
}

(async () => {
  const A = await run('A · 首次打开（空本地数据）', null);
  const B = await run('B · 已有 25 条数据、未备份过（应触发导出提醒）', seedTasks(25));

  const show = o => {
    console.log('\n========== ' + o.label + ' ==========');
    console.log('  JS 错误数            :', o.errors.length, o.errors.length ? JSON.stringify(o.errors, null, 2) : '');
    console.log('  侧边栏导航项数        :', o.navItems);
    console.log('  hero 渲染长度        :', o.heroLen);
    console.log('  首页 view 长度        :', o.viewLen);
    console.log('  切 6 个视图新增错误数  :', o.viewSwitchErrors);
    console.log('  各视图渲染长度        : focus=' + o.focusHtml + ' tasks=' + o.tasksHtml + ' notes=' + o.notesHtml + ' projects=' + o.projectsHtml + ' review=' + o.reviewHtml + ' backup=' + o.backupHtml);
    console.log('  备份页有「导出」按钮   :', o.backupHasExportBtn, ' 有导入文件框:', o.backupHasImportInput);
    console.log('  备份页文案           :', o.backupText);
    console.log('  footer 存储说明       :', o.footStore);
    console.log('  footer 记录数         :', o.navFoot);
    console.log('  本地 API 已加载       :', o.apiLoaded);
    console.log('  导出提醒(加载后)      :', o.nudge || '(无)');
    console.log('  doExport 新增错误     :', o.exportErrors);
    console.log('  导出后 footer         :', o.footAfterExport);
    console.log('  导出后提醒            :', o.nudgeAfterExport || '(无)');
  };
  show(A);
  show(B);

  const fail = [];
  if (A.errors.length) fail.push('A 有 JS 错误');
  if (B.errors.length) fail.push('B 有 JS 错误');
  if (A.navItems !== 7) fail.push('A 导航项数异常');
  if (!A.apiLoaded) fail.push('A 未加载本地 API 数据');
  if (A.viewLen === 0) fail.push('A 首页未渲染');
  if (!A.backupHasExportBtn || !A.backupHasImportInput) fail.push('A 备份页缺导出/导入');
  if (!B.nudge.includes('该导出一次备份了')) fail.push('B 未触发导出提醒');
  if (!B.footAfterExport.includes('上次备份')) fail.push('B 导出后 footer 未更新');
  if (!A.projectDraftRetained || !B.projectDraftRetained) fail.push('切换标签后项目草稿丢失');
  if (!A.detailsSaved || !B.detailsSaved) fail.push('项目或待办详情未保存');
  if (!A.taskDetailsToggle || !B.taskDetailsToggle || !A.taskDetailsShown || !B.taskDetailsShown) fail.push('待办详情不能按需展开');
  if (!A.projectDetailsToggle || !B.projectDetailsToggle || !A.projectDetailsShown || !B.projectDetailsShown) fail.push('项目详情不能按需展开');
  if (!A.logSaved || !B.logSaved || !A.logCalendarEntry || !B.logCalendarEntry) fail.push('日志未保存或未出现在日历入口');
  if (A.logAddFormHidden || B.logAddFormHidden) fail.push('日志输入框没有保留为单条保存/修改入口');
  if (!A.projectTimelineEntry || !B.projectTimelineEntry || !A.projectTimelineShown || !B.projectTimelineShown) fail.push('项目时间线未显示关联日志');
  if (!A.logEditControls || !B.logEditControls) fail.push('日志详情不能编辑正文或关联项目');
  if (!A.logReadOnly || !B.logReadOnly) fail.push('保存后的日志不是默认只读');
  if (!A.logEdited || !B.logEdited) fail.push('日志编辑后未原地保存或产生重复记录');
  if (!A.logDeleteCancel || !B.logDeleteCancel || !A.logDeleted || !B.logDeleted) fail.push('日志删除缺少确认或确认后未删除');
  console.log('\n================ 结论 ================');
  console.log(fail.length ? '❌ 未通过：' + fail.join('；') : '✅ 全部通过');
  process.exit(fail.length ? 1 : 0);
})();
